"""
World Factory Workflow Nodes
Each node is a discrete, retriable step in the world generation process
"""
import os
import uuid
import json
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List
from pymongo import MongoClient

from .state import WorldFactoryState, AuditEntry, NodeResult
from .utils import (
    publish_progress,
    save_audit_trail,
    get_existing_worlds_for_genre,
    calculate_tokens_and_cost,
    store_workflow_state
)

logger = logging.getLogger(__name__)

# Database connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Orchestrator URL for existing generators
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')

# Django web service URL for image generation
DJANGO_URL = os.getenv('DJANGO_URL', 'http://django-web:8000')


async def check_uniqueness_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 1: Check uniqueness - ensure generated world will be different from existing ones
    """
    step_name = "check_uniqueness"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Checking existing worlds for genre: {state.genre}"
        )

        # Get existing worlds for this genre
        existing_worlds = get_existing_worlds_for_genre(state.genre, limit=20)

        # Store in state for use by generation nodes
        if not state.world_data:
            state.world_data = {}
        state.world_data['existing_worlds'] = existing_worlds

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Found {len(existing_worlds)} existing worlds for genre {state.genre}",
            data={'existing_count': len(existing_worlds), 'genre': state.genre}
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Uniqueness check complete: {len(existing_worlds)} existing worlds found",
            {'existing_count': len(existing_worlds)}
        )

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message=f"Failed to check uniqueness",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Uniqueness check failed: {str(e)}"
        )

    return state


async def generate_world_core_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 2: Generate world core - name, description, themes, visual style
    Uses Claude to generate unique, genre-appropriate world basics
    """
    step_name = "generate_world_core"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating world core for genre: {state.genre}"
        )

        from langchain_anthropic import ChatAnthropic
        from langchain.prompts import ChatPromptTemplate

        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            temperature=0.9,
            max_tokens=2048
        )

        # Get existing worlds context
        existing_worlds = state.world_data.get('existing_worlds', [])
        existing_summary = "\n".join([
            f"- {w.get('world_name', 'Unknown')}: {w.get('description', '')[:100]}"
            for w in existing_worlds[:10]
        ])

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master world builder creating unique and compelling RPG worlds.
Your task is to create a world that is DIFFERENT and FRESH compared to existing worlds in this genre.

Output your response as valid JSON with this exact structure:
{{
    "world_name": "Unique and evocative world name",
    "description": "Compelling 2-3 sentence description",
    "themes": ["theme1", "theme2", "theme3", "theme4"],
    "visual_style": ["style1", "style2", "style3"]
}}

Be creative and avoid clichés. Make it memorable and unique!"""),
            ("human", """Genre: {genre}

Existing worlds to differentiate from:
{existing_worlds}

Create a completely NEW and UNIQUE world for this genre that stands apart from the existing ones.
Focus on fresh themes, unexpected combinations, and innovative concepts.

Return ONLY the JSON object, no other text.""")
        ])

        chain = prompt | llm
        response = await chain.ainvoke({
            "genre": state.genre,
            "existing_worlds": existing_summary or "None yet - be creative!"
        })

        # Parse JSON response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        world_core = json.loads(content)

        # Store in state
        if not state.world_data:
            state.world_data = {}
        state.world_data.update(world_core)

        # Calculate tokens and cost
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
            message=f"Generated world core: {world_core.get('world_name')}",
            data=world_core,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"World core generated: {world_core.get('world_name')}",
            {'world_name': world_core.get('world_name')}
        )

        # Reset retry count on success
        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to generate world core",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"World core generation failed: {str(e)}"
        )

    return state


async def generate_world_properties_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 3: Generate world properties - physical, biological, technological, societal, historical
    Uses Claude to generate comprehensive world properties
    """
    step_name = "generate_world_properties"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            "Generating world properties (physical, biological, tech, societal, historical)"
        )

        from langchain_anthropic import ChatAnthropic
        from langchain.prompts import ChatPromptTemplate

        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            temperature=0.8,
            max_tokens=3072
        )

        world_core = state.world_data

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are creating detailed properties for an RPG world.
Generate comprehensive properties across 5 categories.

IMPORTANT: Create diverse and unique world features. Avoid overusing ANY single concept, element, or resource (such as crystals, magic stones, energy sources, ancient artifacts, etc.) across multiple categories. Each world should feel distinctive with its own characteristics. If you use a special resource or unique element in one category, avoid repeating it in other categories. Distribute special features sparingly and vary the types of resources, materials, and concepts used throughout the world properties.

Output valid JSON with this exact structure:
{{
    "physical_properties": {{
        "star_system": "description",
        "planetary_classification": "type",
        "world_features": ["feature1", "feature2", "feature3"],
        "resources": ["resource1", "resource2", "resource3"],
        "terrain": ["terrain1", "terrain2", "terrain3"],
        "climate": "climate description"
    }},
    "biological_properties": {{
        "habitability": "description",
        "flora": ["flora1", "flora2", "flora3"],
        "fauna": ["fauna1", "fauna2", "fauna3"],
        "native_species": ["species1", "species2"]
    }},
    "technological_properties": {{
        "technology_level": "level description",
        "technology_history": ["history1", "history2"],
        "automation": "automation level",
        "weapons_tools": ["weapon1", "weapon2", "weapon3"]
    }},
    "societal_properties": {{
        "government": ["gov_type1", "gov_type2"],
        "culture_traditions": ["tradition1", "tradition2", "tradition3"],
        "inhabitants": ["inhabitant_type1", "inhabitant_type2"],
        "social_issues": ["issue1", "issue2"]
    }},
    "historical_properties": {{
        "major_events": ["event1", "event2", "event3"],
        "significant_sites": ["site1", "site2", "site3"],
        "timeline": "timeline description",
        "myths_origin": ["myth1", "myth2"]
    }}
}}"""),
            ("human", """World: {world_name}
Genre: {genre}
Description: {description}
Themes: {themes}
Visual Style: {visual_style}

Generate detailed properties that align with the genre, themes, and visual style.
Return ONLY the JSON object.""")
        ])

        chain = prompt | llm
        response = await chain.ainvoke({
            "world_name": world_core.get('world_name', ''),
            "genre": state.genre,
            "description": world_core.get('description', ''),
            "themes": ', '.join(world_core.get('themes', [])),
            "visual_style": ', '.join(world_core.get('visual_style', []))
        })

        # Parse JSON response
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        properties = json.loads(content)

        # Merge into world_data
        state.world_data.update(properties)

        # Calculate tokens and cost
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
            message="Generated world properties",
            data={'properties_generated': list(properties.keys())},
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            "World properties generated",
            {'properties': list(properties.keys())}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        state.errors.append(str(e))
        state.retry_count += 1

        audit_entry = AuditEntry(
            step=step_name,
            status="failed",
            message="Failed to generate world properties",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"World properties generation failed: {str(e)}"
        )

    return state


async def generate_world_backstory_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 4: Generate world backstory and timeline using existing orchestrator generator
    """
    step_name = "generate_world_backstory"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            "Generating world backstory and timeline"
        )

        world_data = state.world_data

        # Call orchestrator's backstory generator
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/generate-backstory",
                json={
                    'world_id': 'temp',  # Temporary, we'll create the world after
                    'world_name': world_data.get('world_name', ''),
                    'description': world_data.get('description', ''),
                    'genre': state.genre,
                    'themes': world_data.get('themes', []),
                    'visual_style': world_data.get('visual_style', []),
                    'physical_properties': world_data.get('physical_properties', {}),
                    'biological_properties': world_data.get('biological_properties', {}),
                    'technological_properties': world_data.get('technological_properties', {}),
                    'societal_properties': world_data.get('societal_properties', {}),
                    'historical_properties': world_data.get('historical_properties', {})
                }
            )

            if response.status_code == 200:
                result = response.json()
                backstory = result.get('backstory', '')
                tokens_used = result.get('tokens_used', 0)
                cost_usd = result.get('cost_usd', 0.0)

                # Generate timeline
                timeline_response = await client.post(
                    f"{ORCHESTRATOR_URL}/generate-timeline",
                    json={
                        'world_id': 'temp',
                        'world_name': world_data.get('world_name', ''),
                        'genre': state.genre,
                        'backstory': backstory,
                        'historical_properties': world_data.get('historical_properties', {})
                    }
                )

                timeline = []
                if timeline_response.status_code == 200:
                    timeline_result = timeline_response.json()
                    timeline = timeline_result.get('timeline', [])
                    tokens_used += timeline_result.get('tokens_used', 0)
                    cost_usd += timeline_result.get('cost_usd', 0.0)

                # Store in world_data
                state.world_data['backstory'] = backstory
                state.world_data['timeline'] = timeline

                state.total_tokens_used += tokens_used
                state.total_cost_usd += cost_usd

                audit_entry = AuditEntry(
                    step=step_name,
                    status="completed",
                    message=f"Generated backstory ({len(backstory)} chars) and timeline ({len(timeline)} events)",
                    data={'backstory_length': len(backstory), 'timeline_events': len(timeline)},
                    tokens_used=tokens_used,
                    cost_usd=cost_usd
                )
                state.audit_trail.append(audit_entry)
                save_audit_trail(state.workflow_id, audit_entry.dict())

                publish_progress(
                    state.workflow_id,
                    step_name,
                    "completed",
                    f"Backstory and timeline generated",
                    {'backstory_length': len(backstory), 'timeline_events': len(timeline)}
                )

                # Create world in MongoDB now that we have all the data
                # (Previously this was in generate_world_images_node, but we need it here
                # so the world exists even when image generation is skipped)
                if not state.world_id:
                    from .utils import publish_entity_event
                    world_id = str(uuid.uuid4())
                    world_doc = {
                        '_id': world_id,
                        'world_name': state.world_data.get('world_name'),
                        'description': state.world_data.get('description', ''),
                        'genre': state.genre,
                        'themes': state.world_data.get('themes', []),
                        'visual_style': state.world_data.get('visual_style', []),
                        'physical_properties': state.world_data.get('physical_properties', {}),
                        'biological_properties': state.world_data.get('biological_properties', {}),
                        'technological_properties': state.world_data.get('technological_properties', {}),
                        'societal_properties': state.world_data.get('societal_properties', {}),
                        'historical_properties': state.world_data.get('historical_properties', {}),
                        'backstory': state.world_data.get('backstory', ''),
                        'timeline': state.world_data.get('timeline', []),
                        'universe_ids': [],
                        'regions': [],
                        'species': [],
                        'world_images': [],
                        'primary_image_index': None,
                        'created_by_workflow': state.workflow_id,
                        'created_at': datetime.utcnow()
                    }

                    db.world_definitions.insert_one(world_doc)
                    state.world_id = world_id

                    logger.info(f"Created world in MongoDB: {world_id}")

                    # Publish Neo4j event for world creation
                    publish_entity_event('world', 'created', world_id, {
                        'world_name': state.world_data.get('world_name'),
                        'description': state.world_data.get('description', ''),
                        'genre': state.genre
                    })

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
            message="Failed to generate backstory",
            error=str(e),
            retry_attempt=state.retry_count
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "failed",
            f"Backstory generation failed: {str(e)}"
        )

    return state


# Continuing in next part due to length...
