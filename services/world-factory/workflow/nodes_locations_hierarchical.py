"""
Hierarchical Location Generation Nodes
Enforces proper parent-child relationships and location type constraints
"""
import os
import uuid
import logging
import httpx
import random
from datetime import datetime
from typing import List, Dict, Any

from .state import WorldFactoryState, AuditEntry
from .location_taxonomy import (
    LocationLevel,
    validate_location_type,
    get_valid_child_types,
    REGION_TYPES
)
from .utils import publish_progress, save_audit_trail, publish_entity_event
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')


async def generate_locations_hierarchical_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 8: Generate 3-level hierarchical locations with proper type constraints

    Hierarchy:
    - Region (already created) → Level 1 (2-3 locations)
    - Level 1 → Level 2 (2-3 locations per Level 1)
    - Level 2 → Level 3 (4-8 locations per Level 2)

    Each level enforces valid location types based on parent type
    """
    step_name = "generate_locations"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating hierarchical locations for {len(state.region_ids)} regions with type constraints"
        )

        total_locations = 0
        all_locations_data = []

        # Get world from MongoDB
        world = db.world_definitions.find_one({'_id': state.world_id})
        if not world:
            world = db.world_definitions.find_one({'created_by_workflow': state.workflow_id})

        if not world:
            raise Exception(f"World not found: world_id={state.world_id}, workflow_id={state.workflow_id}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            for region_data in state.regions_data:
                region_id = region_data.get('_id')
                region_type = region_data.get('region_type', 'Plains')  # Default if missing

                # Validate region type
                is_valid_region, region_error = validate_location_type(
                    region_type,
                    LocationLevel.REGION
                )

                if not is_valid_region:
                    logger.warning(f"Invalid region type '{region_type}': {region_error}. Using 'Plains' as fallback.")
                    region_type = "Plains"
                    # Update region with valid type
                    db.region_definitions.update_one(
                        {'_id': region_id},
                        {'$set': {'region_type': region_type}}
                    )

                logger.info(f"Generating locations for region: {region_data.get('region_name')} ({region_type})")

                # =============================================================================
                # LEVEL 1: Generate 2-3 Primary locations
                # =============================================================================
                num_primary = random.randint(2, 3)
                valid_level1_types = get_valid_child_types(region_type, LocationLevel.REGION)

                if not valid_level1_types:
                    logger.warning(f"No valid Level 1 types for region type '{region_type}'. Using generic types.")
                    valid_level1_types = ["Settlement", "Town", "Village"]

                level1_locations = await generate_level1_locations(
                    client=client,
                    world=world,
                    region_data=region_data,
                    region_type=region_type,
                    num_locations=num_primary,
                    valid_types=valid_level1_types,
                    genre=state.genre
                )

                for primary_data in level1_locations:
                    # Validate Level 1 type
                    primary_type = primary_data.get('location_type', valid_level1_types[0])
                    is_valid, error = validate_location_type(
                        primary_type,
                        LocationLevel.LEVEL_1,
                        parent_type=region_type
                    )

                    if not is_valid:
                        logger.warning(f"Invalid Level 1 type '{primary_type}': {error}. Using first valid type.")
                        primary_type = valid_level1_types[0]
                        primary_data['location_type'] = primary_type

                    # Create Level 1 location
                    primary_id = str(uuid.uuid4())
                    primary_doc = {
                        '_id': primary_id,
                        'location_name': primary_data.get('location_name'),
                        'location_type': primary_type,
                        'description': primary_data.get('description', ''),
                        'features': primary_data.get('features', []),
                        'backstory': primary_data.get('backstory', ''),
                        'region_id': region_id,
                        'world_id': state.world_id,
                        'parent_location_id': None,
                        'child_locations': [],
                        'level': 1,
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

                    logger.info(f"Created Level 1 location: {primary_data.get('location_name')} ({primary_type})")

                    # Publish Neo4j event
                    publish_entity_event('location', 'created', primary_id, {
                        'location_name': primary_data.get('location_name'),
                        'location_type': primary_type,
                        'world_id': state.world_id,
                        'region_id': region_id,
                        'parent_location_id': None,
                        'hierarchy_level': 1
                    })

                    # =============================================================================
                    # LEVEL 2: Generate 2-3 Secondary locations per Level 1
                    # =============================================================================
                    num_secondary = random.randint(2, 3)
                    valid_level2_types = get_valid_child_types(primary_type, LocationLevel.LEVEL_1)

                    if not valid_level2_types:
                        logger.warning(f"No valid Level 2 types for '{primary_type}'. Using generic types.")
                        valid_level2_types = ["Building", "House", "Shop"]

                    level2_locations = await generate_level2_locations(
                        client=client,
                        world=world,
                        region_data=region_data,
                        parent_location=primary_data,
                        parent_type=primary_type,
                        num_locations=num_secondary,
                        valid_types=valid_level2_types,
                        genre=state.genre
                    )

                    for secondary_data in level2_locations:
                        # Validate Level 2 type
                        secondary_type = secondary_data.get('location_type', valid_level2_types[0])
                        is_valid, error = validate_location_type(
                            secondary_type,
                            LocationLevel.LEVEL_2,
                            parent_type=primary_type
                        )

                        if not is_valid:
                            logger.warning(f"Invalid Level 2 type '{secondary_type}': {error}")
                            secondary_type = valid_level2_types[0]
                            secondary_data['location_type'] = secondary_type

                        # Create Level 2 location
                        secondary_id = str(uuid.uuid4())
                        secondary_doc = {
                            '_id': secondary_id,
                            'location_name': secondary_data.get('location_name'),
                            'location_type': secondary_type,
                            'description': secondary_data.get('description', ''),
                            'features': secondary_data.get('features', []),
                            'backstory': secondary_data.get('backstory', ''),
                            'region_id': region_id,
                            'world_id': state.world_id,
                            'parent_location_id': primary_id,
                            'child_locations': [],
                            'level': 2,
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

                        logger.info(f"Created Level 2 location: {secondary_data.get('location_name')} ({secondary_type})")

                        # Publish Neo4j event
                        publish_entity_event('location', 'created', secondary_id, {
                            'location_name': secondary_data.get('location_name'),
                            'location_type': secondary_type,
                            'world_id': state.world_id,
                            'region_id': region_id,
                            'parent_location_id': primary_id,
                            'hierarchy_level': 2
                        })

                        # =============================================================================
                        # LEVEL 3: Generate 4-8 Tertiary locations per Level 2
                        # =============================================================================
                        num_tertiary = random.randint(4, 8)
                        valid_level3_types = get_valid_child_types(secondary_type, LocationLevel.LEVEL_2)

                        if not valid_level3_types:
                            logger.warning(f"No valid Level 3 types for '{secondary_type}'. Using generic types.")
                            valid_level3_types = ["Room", "Chamber", "Storage Room"]

                        level3_locations = await generate_level3_locations(
                            client=client,
                            world=world,
                            region_data=region_data,
                            parent_location=secondary_data,
                            parent_type=secondary_type,
                            grandparent_location=primary_data,
                            num_locations=num_tertiary,
                            valid_types=valid_level3_types,
                            genre=state.genre
                        )

                        for tertiary_data in level3_locations:
                            # Validate Level 3 type
                            tertiary_type = tertiary_data.get('location_type', valid_level3_types[0])
                            is_valid, error = validate_location_type(
                                tertiary_type,
                                LocationLevel.LEVEL_3,
                                parent_type=secondary_type
                            )

                            if not is_valid:
                                logger.warning(f"Invalid Level 3 type '{tertiary_type}': {error}")
                                tertiary_type = valid_level3_types[0]
                                tertiary_data['location_type'] = tertiary_type

                            # Create Level 3 location
                            tertiary_id = str(uuid.uuid4())
                            tertiary_doc = {
                                '_id': tertiary_id,
                                'location_name': tertiary_data.get('location_name'),
                                'location_type': tertiary_type,
                                'description': tertiary_data.get('description', ''),
                                'features': tertiary_data.get('features', []),
                                'backstory': tertiary_data.get('backstory', ''),
                                'region_id': region_id,
                                'world_id': state.world_id,
                                'parent_location_id': secondary_id,
                                'child_locations': [],
                                'level': 3,
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

                            # Publish Neo4j event
                            publish_entity_event('location', 'created', tertiary_id, {
                                'location_name': tertiary_data.get('location_name'),
                                'location_type': tertiary_type,
                                'world_id': state.world_id,
                                'region_id': region_id,
                                'parent_location_id': secondary_id,
                                'hierarchy_level': 3
                            })

        state.locations_data = all_locations_data

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {total_locations} hierarchical locations with type constraints across {len(state.region_ids)} regions",
            data={
                'location_count': total_locations,
                'region_count': len(state.region_ids),
                'hierarchy_enforced': True
            }
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {total_locations} hierarchical locations",
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
            message="Failed to generate hierarchical locations",
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


# =============================================================================
# HELPER FUNCTIONS FOR EACH LEVEL
# =============================================================================

async def generate_level1_locations(
    client: httpx.AsyncClient,
    world: Dict,
    region_data: Dict,
    region_type: str,
    num_locations: int,
    valid_types: List[str],
    genre: str
) -> List[Dict[str, Any]]:
    """Generate Level 1 locations with type constraints"""

    prompt_context = {
        'world_name': world.get('world_name'),
        'world_genre': genre,
        'world_backstory': world.get('backstory', ''),
        'region_name': region_data.get('region_name'),
        'region_type': region_type,
        'climate': region_data.get('climate'),
        'terrain': region_data.get('terrain', []),
        'region_description': region_data.get('description', ''),
        'region_backstory': region_data.get('backstory', ''),
        'num_locations': num_locations,
        'valid_location_types': ', '.join(valid_types),
        'hierarchy_instruction': f"""
CRITICAL: Generate Level 1 locations that are LARGE SETTLEMENTS or MAJOR FEATURES within the {region_type} region.
They must be SMALLER than and CONTAINED within the region '{region_data.get('region_name')}'.
Valid types for this region: {', '.join(valid_types)}

Examples:
- Region: "The Shire" (Plains) → Level 1: "Hobbiton" (Village)
- Region: "Misty Mountains" (Mountain Range) → Level 1: "Goblin Caverns" (Cave System)
        """
    }

    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/generate-locations-hierarchical",
        json=prompt_context
    )

    if response.status_code == 200:
        result = response.json()
        return result.get('locations', [])
    else:
        logger.error(f"Failed to generate Level 1 locations: {response.text}")
        return []


async def generate_level2_locations(
    client: httpx.AsyncClient,
    world: Dict,
    region_data: Dict,
    parent_location: Dict,
    parent_type: str,
    num_locations: int,
    valid_types: List[str],
    genre: str
) -> List[Dict[str, Any]]:
    """Generate Level 2 locations (buildings/areas) within Level 1"""

    prompt_context = {
        'world_name': world.get('world_name'),
        'world_genre': genre,
        'parent_location_name': parent_location.get('location_name'),
        'parent_location_type': parent_type,
        'parent_description': parent_location.get('description', ''),
        'region_name': region_data.get('region_name'),
        'num_locations': num_locations,
        'valid_location_types': ', '.join(valid_types),
        'hierarchy_instruction': f"""
CRITICAL: Generate Level 2 locations that are BUILDINGS or SUB-AREAS within the {parent_type} called '{parent_location.get('location_name')}'.
They must be SMALLER than and INSIDE the Level 1 location.
Valid types: {', '.join(valid_types)}

Examples:
- Level 1: "Hobbiton" (Village) → Level 2: "The Green Dragon" (Tavern), "Bag End" (House)
- Level 1: "Goblin Caverns" (Cave System) → Level 2: "Throne Chamber" (Cave)
        """
    }

    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/generate-locations-hierarchical",
        json=prompt_context
    )

    if response.status_code == 200:
        result = response.json()
        return result.get('locations', [])
    else:
        logger.error(f"Failed to generate Level 2 locations: {response.text}")
        return []


async def generate_level3_locations(
    client: httpx.AsyncClient,
    world: Dict,
    region_data: Dict,
    parent_location: Dict,
    parent_type: str,
    grandparent_location: Dict,
    num_locations: int,
    valid_types: List[str],
    genre: str
) -> List[Dict[str, Any]]:
    """Generate Level 3 locations (rooms/spaces) within Level 2"""

    prompt_context = {
        'world_name': world.get('world_name'),
        'world_genre': genre,
        'parent_location_name': parent_location.get('location_name'),
        'parent_location_type': parent_type,
        'parent_description': parent_location.get('description', ''),
        'grandparent_location_name': grandparent_location.get('location_name'),
        'num_locations': num_locations,
        'valid_location_types': ', '.join(valid_types),
        'hierarchy_instruction': f"""
CRITICAL: Generate Level 3 locations that are ROOMS or SPECIFIC SPACES within the {parent_type} called '{parent_location.get('location_name')}'.
These are the final level - scenes will take place here.
Valid types: {', '.join(valid_types)}

Examples:
- Level 2: "The Green Dragon" (Tavern) → Level 3: "The Bar", "Common Room", "Private Room 1"
- Level 2: "Throne Chamber" (Cave) → Level 3: "The Throne Alcove", "Prisoner Pit"
        """
    }

    response = await client.post(
        f"{ORCHESTRATOR_URL}/api/generate-locations-hierarchical",
        json=prompt_context
    )

    if response.status_code == 200:
        result = response.json()
        return result.get('locations', [])
    else:
        logger.error(f"Failed to generate Level 3 locations: {response.text}")
        return []
