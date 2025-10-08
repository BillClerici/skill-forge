"""
World Factory Entity Generation Nodes
Nodes 6, 8, 10, 12: Generate regions, locations, species, and finalization
"""
import os
import uuid
import logging
import httpx
from datetime import datetime

from .state import WorldFactoryState, AuditEntry
from .utils import publish_progress, save_audit_trail, publish_entity_event
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')


async def generate_regions_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 6: Generate 3-5 regions with backstories using existing orchestrator
    """
    step_name = "generate_regions"
    state.current_step = step_name

    try:
        # Calculate number of regions based on world features (at least 1 per feature, max 8)
        world_features = state.world_data.get('physical_properties', {}).get('world_features', [])
        num_regions = max(len(world_features), 1)  # At least 1
        num_regions = min(num_regions, 8)  # Max 8

        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating {num_regions} regions (1 per world feature, max 8)"
        )

        num_locations_per_region = 0  # We'll generate locations separately in next step

        world_context = {
            'world_name': state.world_data.get('world_name'),
            'description': state.world_data.get('description', ''),
            'genre': state.genre,
            'themes': state.world_data.get('themes', []),
            'visual_style': state.world_data.get('visual_style', []),
            'backstory': state.world_data.get('backstory', ''),
            'physical_properties': state.world_data.get('physical_properties', {}),
            'biological_properties': state.world_data.get('biological_properties', {}),
            'technological_properties': state.world_data.get('technological_properties', {}),
            'societal_properties': state.world_data.get('societal_properties', {}),
            'historical_properties': state.world_data.get('historical_properties', {})
        }

        # Call orchestrator to generate regions
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/api/generate-regions",
                json={
                    'world_context': world_context,
                    'num_regions': num_regions,
                    'num_locations_per_region': num_locations_per_region  # 0 means no locations yet
                }
            )

            if response.status_code == 200:
                result = response.json()
                regions_data = result.get('regions', [])
                tokens_used = result.get('tokens_used', 0)
                cost_usd = result.get('cost_usd', 0.0)

                # Create regions in MongoDB
                region_ids = []
                for region_data in regions_data:
                    region_id = str(uuid.uuid4())
                    region_doc = {
                        '_id': region_id,
                        'region_name': region_data.get('region_name'),
                        'region_type': region_data.get('region_type'),
                        'climate': region_data.get('climate'),
                        'terrain': region_data.get('terrain', []),
                        'description': region_data.get('description', ''),
                        'backstory': region_data.get('backstory', ''),
                        'world_id': state.world_id,
                        'locations': [],
                        'region_images': [],
                        'primary_image_index': None,
                        'created_by_workflow': state.workflow_id,
                        'created_at': datetime.utcnow()
                    }

                    db.region_definitions.insert_one(region_doc)
                    region_ids.append(region_id)

                    # Add region to world's regions array
                    db.world_definitions.update_one(
                        {'_id': state.world_id},
                        {'$push': {'regions': region_id}}
                    )

                    logger.info(f"Created region: {region_id} - {region_data.get('region_name')}")

                    # Publish Neo4j event for region creation
                    publish_entity_event('region', 'created', region_id, {
                        'region_name': region_data.get('region_name'),
                        'region_type': region_data.get('region_type'),
                        'world_id': state.world_id
                    })

                # Store in state
                state.region_ids = region_ids
                state.regions_data = [{'_id': rid, **rd} for rid, rd in zip(region_ids, regions_data)]

                state.total_tokens_used += tokens_used
                state.total_cost_usd += cost_usd

                audit_entry = AuditEntry(
                    step=step_name,
                    status="completed",
                    message=f"Generated {len(region_ids)} regions",
                    data={'region_count': len(region_ids), 'region_names': [r.get('region_name') for r in regions_data]},
                    tokens_used=tokens_used,
                    cost_usd=cost_usd
                )
                state.audit_trail.append(audit_entry)
                save_audit_trail(state.workflow_id, audit_entry.dict())

                publish_progress(
                    state.workflow_id,
                    step_name,
                    "completed",
                    f"Generated {len(region_ids)} regions",
                    {'region_count': len(region_ids)}
                )

                state.retry_count = 0
            else:
                raise Exception(f"Orchestrator returned status {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to generate regions",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Region generation failed: {str(e)}"
        )

    return state


async def generate_locations_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 8: Generate 3-level hierarchical locations for each region
    Level 1: 2-3 Primary locations (Island, Forest, District, etc.)
    Level 2: 2-3 Secondary locations per primary (City, Town, Settlement, etc.)
    Level 3: 4-8 Tertiary locations per secondary (House, Shop, Inn, etc.)
    """
    step_name = "generate_locations"
    state.current_step = step_name

    try:
        import random

        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating 3-level hierarchical locations for {len(state.region_ids)} regions"
        )

        total_locations = 0
        all_locations_data = []

        # Get world from MongoDB once - try by ID first, then by workflow_id
        world = db.world_definitions.find_one({'_id': state.world_id})
        if not world:
            logger.warning(f"World not found by ID {state.world_id}, trying by workflow_id")
            world = db.world_definitions.find_one({'created_by_workflow': state.workflow_id})

        if not world:
            raise Exception(f"World not found in database: world_id={state.world_id}, workflow_id={state.workflow_id}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            for region_data in state.regions_data:
                region_id = region_data.get('_id')

                # LEVEL 1: Generate 2-3 Primary locations per region
                num_primary = random.randint(2, 3)

                context_primary = {
                    'world_name': world.get('world_name'),
                    'world_genre': state.genre,
                    'world_backstory': world.get('backstory', ''),
                    'region_name': region_data.get('region_name'),
                    'region_type': region_data.get('region_type'),
                    'climate': region_data.get('climate'),
                    'terrain': region_data.get('terrain', []),
                    'region_description': region_data.get('description', ''),
                    'region_backstory': region_data.get('backstory', ''),
                    'num_locations': num_primary
                }

                response = await client.post(
                    f"{ORCHESTRATOR_URL}/api/generate-locations",
                    json=context_primary
                )

                if response.status_code == 200:
                    result = response.json()
                    primary_locations = result.get('locations', [])

                    for primary_data in primary_locations:
                        # Create primary location
                        primary_id = str(uuid.uuid4())
                        primary_doc = {
                            '_id': primary_id,
                            'location_name': primary_data.get('location_name'),
                            'location_type': primary_data.get('location_type'),
                            'description': primary_data.get('description', ''),
                            'features': primary_data.get('features', []),
                            'backstory': primary_data.get('backstory', ''),
                            'region_id': region_id,
                            'world_id': state.world_id,
                            'parent_location_id': None,
                            'child_locations': [],
                            'depth': 1,
                            'location_images': [],
                            'primary_image_index': None,
                            'created_by_workflow': state.workflow_id,
                            'created_at': datetime.utcnow()
                        }

                        db.location_definitions.insert_one(primary_doc)
                        state.location_ids.append(primary_id)
                        all_locations_data.append(primary_doc)

                        # Add to region's locations
                        db.region_definitions.update_one(
                            {'_id': region_id},
                            {'$push': {'locations': primary_id}}
                        )
                        total_locations += 1
                        logger.info(f"Created Level 1 location: {primary_data.get('location_name')}")

                        # Publish Neo4j event for location creation
                        publish_entity_event('location', 'created', primary_id, {
                            'location_name': primary_data.get('location_name'),
                            'location_type': primary_data.get('location_type'),
                            'world_id': state.world_id,
                            'region_id': region_id,
                            'parent_location_id': None,
                            'hierarchy_level': 1
                        })

                        # LEVEL 2: Generate 2-3 Secondary locations per primary
                        num_secondary = random.randint(2, 3)

                        context_secondary = {
                            'world_name': world.get('world_name'),
                            'world_genre': state.genre,
                            'world_backstory': world.get('backstory', ''),
                            'region_name': region_data.get('region_name'),
                            'region_type': region_data.get('region_type'),
                            'climate': region_data.get('climate'),
                            'terrain': region_data.get('terrain', []),
                            'region_description': f"Within {primary_data.get('location_name')} ({primary_data.get('location_type')}) - {primary_data.get('description', '')}",
                            'region_backstory': region_data.get('backstory', ''),
                            'num_locations': num_secondary
                        }

                        response_sec = await client.post(
                            f"{ORCHESTRATOR_URL}/api/generate-locations",
                            json=context_secondary
                        )

                        if response_sec.status_code == 200:
                            result_sec = response_sec.json()
                            secondary_locations = result_sec.get('locations', [])

                            for secondary_data in secondary_locations:
                                # Create secondary location
                                secondary_id = str(uuid.uuid4())
                                secondary_doc = {
                                    '_id': secondary_id,
                                    'location_name': secondary_data.get('location_name'),
                                    'location_type': secondary_data.get('location_type'),
                                    'description': secondary_data.get('description', ''),
                                    'features': secondary_data.get('features', []),
                                    'backstory': secondary_data.get('backstory', ''),
                                    'region_id': region_id,
                                    'world_id': state.world_id,
                                    'parent_location_id': primary_id,
                                    'child_locations': [],
                                    'depth': 2,
                                    'location_images': [],
                                    'primary_image_index': None,
                                    'created_by_workflow': state.workflow_id,
                                    'created_at': datetime.utcnow()
                                }

                                db.location_definitions.insert_one(secondary_doc)
                                state.location_ids.append(secondary_id)
                                all_locations_data.append(secondary_doc)

                                # Add to parent's child_locations
                                db.location_definitions.update_one(
                                    {'_id': primary_id},
                                    {'$push': {'child_locations': secondary_id}}
                                )
                                total_locations += 1
                                logger.info(f"Created Level 2 location: {secondary_data.get('location_name')}")

                                # Publish Neo4j event for location creation
                                publish_entity_event('location', 'created', secondary_id, {
                                    'location_name': secondary_data.get('location_name'),
                                    'location_type': secondary_data.get('location_type'),
                                    'world_id': state.world_id,
                                    'region_id': region_id,
                                    'parent_location_id': primary_id,
                                    'hierarchy_level': 2
                                })

                                # LEVEL 3: Generate 4-8 Tertiary locations per secondary
                                num_tertiary = random.randint(4, 8)

                                context_tertiary = {
                                    'world_name': world.get('world_name'),
                                    'world_genre': state.genre,
                                    'world_backstory': world.get('backstory', ''),
                                    'region_name': region_data.get('region_name'),
                                    'region_type': region_data.get('region_type'),
                                    'climate': region_data.get('climate'),
                                    'terrain': region_data.get('terrain', []),
                                    'region_description': f"In {secondary_data.get('location_name')} ({secondary_data.get('location_type')}) within {primary_data.get('location_name')} - {secondary_data.get('description', '')}",
                                    'region_backstory': region_data.get('backstory', ''),
                                    'num_locations': num_tertiary
                                }

                                response_ter = await client.post(
                                    f"{ORCHESTRATOR_URL}/api/generate-locations",
                                    json=context_tertiary
                                )

                                if response_ter.status_code == 200:
                                    result_ter = response_ter.json()
                                    tertiary_locations = result_ter.get('locations', [])

                                    for tertiary_data in tertiary_locations:
                                        # Create tertiary location
                                        tertiary_id = str(uuid.uuid4())
                                        tertiary_doc = {
                                            '_id': tertiary_id,
                                            'location_name': tertiary_data.get('location_name'),
                                            'location_type': tertiary_data.get('location_type'),
                                            'description': tertiary_data.get('description', ''),
                                            'features': tertiary_data.get('features', []),
                                            'backstory': tertiary_data.get('backstory', ''),
                                            'region_id': region_id,
                                            'world_id': state.world_id,
                                            'parent_location_id': secondary_id,
                                            'child_locations': [],
                                            'depth': 3,
                                            'location_images': [],
                                            'primary_image_index': None,
                                            'created_by_workflow': state.workflow_id,
                                            'created_at': datetime.utcnow()
                                        }

                                        db.location_definitions.insert_one(tertiary_doc)
                                        state.location_ids.append(tertiary_id)
                                        all_locations_data.append(tertiary_doc)

                                        # Add to parent's child_locations
                                        db.location_definitions.update_one(
                                            {'_id': secondary_id},
                                            {'$push': {'child_locations': tertiary_id}}
                                        )
                                        total_locations += 1

                                        # Publish Neo4j event for location creation
                                        publish_entity_event('location', 'created', tertiary_id, {
                                            'location_name': tertiary_data.get('location_name'),
                                            'location_type': tertiary_data.get('location_type'),
                                            'world_id': state.world_id,
                                            'region_id': region_id,
                                            'parent_location_id': secondary_id,
                                            'hierarchy_level': 3
                                        })

                    # Track tokens/cost
                    state.total_tokens_used += result.get('tokens_used', 0)
                    state.total_cost_usd += result.get('cost_usd', 0.0)

        state.locations_data = all_locations_data

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {total_locations} locations across {len(state.region_ids)} regions",
            data={'location_count': total_locations, 'region_count': len(state.region_ids)}
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {total_locations} locations",
            {'location_count': total_locations}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to generate locations",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Location generation failed: {str(e)}"
        )

    return state


async def generate_species_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 10: Generate at least 4 primary species per world feature (max 12)
    Species can exist in multiple regions based on terrain, climate, etc.
    """
    step_name = "generate_species"
    state.current_step = step_name

    try:
        # Calculate number of species based on world features (at least 4 per feature, max 12)
        world_features = state.world_data.get('physical_properties', {}).get('world_features', [])
        num_species = len(world_features) * 4 if world_features else 6  # At least 6 if no features
        num_species = min(num_species, 12)  # Max 12

        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating {num_species} unique species (4 per world feature, max 12)"
        )

        from langchain_anthropic import ChatAnthropic
        from langchain.prompts import ChatPromptTemplate
        import json

        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            temperature=0.9,
            max_tokens=4096
        )

        # Build comprehensive region info with terrain and climate
        regions_info = []
        for r in state.regions_data:
            region_summary = {
                'name': r.get('region_name', ''),
                'terrain': r.get('terrain', []),
                'climate': r.get('climate', ''),
                'type': r.get('region_type', '')
            }
            regions_info.append(region_summary)

        regions_summary = "\n".join([
            f"- {r['name']}: {r['type']} (Terrain: {', '.join(r['terrain'])}, Climate: {r['climate']})"
            for r in regions_info
        ])

        # Define available character traits from the form
        available_traits = [
            "Aggressive", "Peaceful", "Intelligent", "Cunning", "Loyal", "Territorial",
            "Nomadic", "Social", "Solitary", "Mystical", "Adaptive", "Traditional",
            "Innovative", "Honorable", "Deceptive", "Brave", "Cautious", "Industrious",
            "Lazy", "Curious"
        ]

        # Extract additional properties for richer context
        world_data = state.world_data
        physical = world_data.get('physical_properties', {})
        biological = world_data.get('biological_properties', {})
        technological = world_data.get('technological_properties', {})
        societal = world_data.get('societal_properties', {})
        historical = world_data.get('historical_properties', {})

        # Build context strings
        tech_level = technological.get('technology_level', 'varied')
        power_sources = ', '.join(technological.get('power_sources', []))
        governance = ', '.join(societal.get('governance_types', []))
        social_structure = societal.get('social_structure', '')
        visual_style_str = ', '.join(world_data.get('visual_style', []))

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are creating unique species for an RPG world.
Generate {num_species} diverse and interesting species that fit the world's genre, themes, environmental features, technology level, and society.

WORLD CONTEXT:
- Visual Style: {visual_style_str if visual_style_str else 'varied'}
- Technology Level: {tech_level}
- Power Sources: {power_sources if power_sources else 'varied'}
- Governance: {governance if governance else 'varied'}
- Social Structure: {social_structure if social_structure else 'varied'}

IMPORTANT: Species can exist in multiple regions based on:
- Compatible terrain types (e.g., mountain species can live in all mountain regions)
- Climate compatibility (e.g., cold-adapted species in arctic/tundra regions)
- Ecological niches (predators, herbivores, magical beings, etc.)
- Technology level (some species may be more/less technologically advanced)
- Social structures (how they interact with governance and society)

CHARACTER TRAITS INSTRUCTIONS:
You must select 3-5 character traits for each species that align with:
1. The species' description and backstory
2. The environments/regions they inhabit (e.g., mountain dwellers might be "Brave", "Territorial", arctic species might be "Adaptive", "Cautious")
3. The world's genre, themes, and technology level
4. The societal structures they interact with

Available predefined traits (use these first):
{', '.join(available_traits)}

You may also create 1-2 custom traits if needed to capture unique aspects of the species, but prioritize using the predefined traits above.

Output valid JSON with this structure:
{{{{
    "species": [
        {{{{
            "species_name": "name",
            "species_type": "humanoid/creature/elemental/plant-based/mechanical/etc",
            "category": "sentient/wildlife/magical/symbiotic",
            "description": "detailed description including adaptations and how they fit the world's technology/society",
            "backstory": "rich backstory and origin that references the world's history and culture",
            "character_traits": ["trait1", "trait2", "trait3", "trait4"],
            "habitat_requirements": {{{{
                "terrain_types": ["terrain1", "terrain2"],
                "climate_preference": "climate description",
                "special_needs": "any special environmental needs"
            }}}},
            "suitable_regions": ["region_name1", "region_name2", "region_name3"]
        }}}}
    ]
}}}}

Create {num_species} species with variety in types, sizes, intelligence, technological adaptation, and ecological roles!"""),
            ("human", """World: {world_name}
Genre: {genre}
Description: {description}
World Features: {world_features}
Themes: {themes}
Visual Style: {visual_style}
Backstory: {backstory}

Regions in this world:
{regions}

Physical Environment:
- Terrain Types: {terrain}
- Climate: {climate}
- Flora: {flora}
- Fauna: {fauna}

Biological Properties:
- Habitability: {habitability}
- Native Species Hints: {native_species}

Technology & Society:
- Technology Level: {tech_level}
- Power Sources: {power_sources}
- Governance: {governance}
- Social Structure: {social_structure}

Create {num_species} unique species. Ensure each species is assigned to ALL suitable regions based on terrain/climate compatibility, and that they fit the world's technology level and societal structures.
Return ONLY the JSON object.""")
        ])

        world_data = state.world_data
        physical = world_data.get('physical_properties', {})
        biological = world_data.get('biological_properties', {})

        chain = prompt | llm
        response = await chain.ainvoke({
            "world_name": world_data.get('world_name'),
            "genre": state.genre,
            "description": world_data.get('description', '')[:300],
            "world_features": ', '.join(world_features),
            "themes": ', '.join(world_data.get('themes', [])),
            "visual_style": visual_style_str,
            "backstory": world_data.get('backstory', '')[:600],
            "regions": regions_summary,
            "terrain": ', '.join(physical.get('terrain', [])),
            "climate": physical.get('climate', ''),
            "flora": ', '.join(biological.get('flora', [])[:3]),
            "fauna": ', '.join(biological.get('fauna', [])[:3]),
            "habitability": biological.get('habitability', 'Unknown'),
            "native_species": ', '.join(biological.get('native_species', [])),
            "tech_level": tech_level,
            "power_sources": power_sources,
            "governance": governance,
            "social_structure": social_structure,
            "num_species": num_species
        })

        # Parse JSON
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        species_result = json.loads(content)
        species_list = species_result.get('species', [])

        # Map region names to IDs
        region_name_to_id = {r.get('region_name'): r.get('_id') for r in state.regions_data}

        # Create species in MongoDB
        for species_data in species_list:
            species_id = str(uuid.uuid4())

            # Map suitable_regions (multiple) to region IDs
            suitable_region_names = species_data.get('suitable_regions', [])
            region_ids = [region_name_to_id.get(name) for name in suitable_region_names
                         if name in region_name_to_id]

            # If no suitable_regions provided, fall back to 'regions' field
            if not region_ids:
                region_names = species_data.get('regions', [])
                region_ids = [region_name_to_id.get(name) for name in region_names if name in region_name_to_id]

            # Store habitat requirements
            habitat_reqs = species_data.get('habitat_requirements', {})

            species_doc = {
                '_id': species_id,
                'world_id': state.world_id,
                'species_name': species_data.get('species_name'),
                'species_type': species_data.get('species_type'),
                'category': species_data.get('category'),
                'description': species_data.get('description', ''),
                'backstory': species_data.get('backstory', ''),
                'character_traits': species_data.get('character_traits', []),
                'habitat_requirements': habitat_reqs,
                'regions': region_ids,
                'relationships': [],
                'species_images': [],
                'primary_image_index': None,
                'created_by_workflow': state.workflow_id,
                'created_at': datetime.utcnow()
            }

            db.species_definitions.insert_one(species_doc)
            state.species_ids.append(species_id)
            state.species_data.append(species_doc)

            # Add species to world
            db.world_definitions.update_one(
                {'_id': state.world_id},
                {'$push': {'species': species_id}}
            )

            logger.info(f"Created species: {species_id} - {species_data.get('species_name')}")

            # Publish Neo4j event for species creation
            publish_entity_event('species', 'created', species_id, {
                'species_name': species_data.get('species_name'),
                'species_type': species_data.get('species_type'),
                'world_id': state.world_id
            })

        # Calculate tokens and cost
        from .utils import calculate_tokens_and_cost
        tokens_used, cost_usd = calculate_tokens_and_cost(
            'claude-3-5-sonnet-20241022',
            response.response_metadata.get('usage', {}).get('input_tokens', 0),
            response.response_metadata.get('usage', {}).get('output_tokens', 0)
        )
        state.total_tokens_used += tokens_used
        state.total_cost_usd += cost_usd

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {len(species_list)} species",
            data={'species_count': len(species_list), 'species_names': [s.get('species_name') for s in species_list]},
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {len(species_list)} species",
            {'species_count': len(species_list)}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to generate species",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Species generation failed: {str(e)}"
        )

    return state


async def finalize_world_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 12: Finalize world - validation, publish completion event, final audit trail
    """
    step_name = "finalize"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            "Finalizing world and validating all components"
        )

        # Mark workflow as completed
        state.completed_at = datetime.utcnow()

        # Calculate total duration
        duration_seconds = (state.completed_at - state.started_at).total_seconds()

        # Final summary
        summary = {
            'workflow_id': state.workflow_id,
            'world_id': state.world_id,
            'world_name': state.world_data.get('world_name'),
            'genre': state.genre,
            'region_count': len(state.region_ids),
            'location_count': len(state.location_ids),
            'species_count': len(state.species_ids),
            'total_tokens_used': state.total_tokens_used,
            'total_cost_usd': round(state.total_cost_usd, 4),
            'duration_seconds': int(duration_seconds),
            'duration_minutes': round(duration_seconds / 60, 2),
            'errors': state.errors
        }

        # Store final workflow result
        db.world_factory_results.insert_one({
            'workflow_id': state.workflow_id,
            'world_id': state.world_id,
            'user_id': state.user_id,
            'genre': state.genre,
            'summary': summary,
            'audit_trail': [entry.dict() for entry in state.audit_trail],
            'completed_at': state.completed_at,
            'status': 'completed' if not state.errors else 'completed_with_warnings'
        })

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"World factory completed successfully! Created world '{state.world_data.get('world_name')}' with {len(state.region_ids)} regions, {len(state.location_ids)} locations, and {len(state.species_ids)} species.",
            data=summary
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"World factory completed! Total cost: ${summary['total_cost_usd']}, Duration: {summary['duration_minutes']} min",
            summary
        )

        logger.info(f"World factory workflow completed: {state.workflow_id}")
        logger.info(f"Summary: {summary}")

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to finalize world",
            error=str(e)
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Finalization failed: {str(e)}"
        )

    return state
