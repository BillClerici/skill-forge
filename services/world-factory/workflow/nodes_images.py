"""
World Factory Image Generation Nodes
Nodes 5, 7, 9, 11: Image generation for worlds, regions, locations, and species
"""
import os
import uuid
import logging
import httpx
from datetime import datetime

from .state import WorldFactoryState, AuditEntry
from .utils import publish_progress, save_audit_trail, calculate_tokens_and_cost, publish_entity_event
from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

DJANGO_URL = os.getenv('DJANGO_URL', 'http://django-web:8000')


async def generate_world_images_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 5: Generate 1 DALL-E image for the world
    Creates world in MongoDB first, then calls existing image generator
    """
    step_name = "generate_world_images"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            "Creating world in database and generating 1 image (Full Planet)"
        )

        # First, create the world in MongoDB if not already created
        if not state.world_id:
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

        # Now generate images using existing Django endpoint
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{DJANGO_URL}/worlds/{state.world_id}/generate-image/",
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                result = response.json()
                images = result.get('images', [])

                # Cost calculation (DALL-E 3: $0.04 per 1024x1792 or 1792x1024 image)
                cost_usd = len(images) * 0.04
                state.total_cost_usd += cost_usd

                audit_entry = AuditEntry(
                    step=step_name,
                    status="completed",
                    message=f"Generated {len(images)} world images",
                    data={'world_id': state.world_id, 'image_count': len(images)},
                    cost_usd=cost_usd
                )
                state.audit_trail.append(audit_entry)
                save_audit_trail(state.workflow_id, audit_entry.dict())

                publish_progress(
                    state.workflow_id,
                    step_name,
                    "completed",
                    f"Generated {len(images)} world images",
                    {'world_id': state.world_id, 'image_count': len(images)}
                )

                state.retry_count = 0
            else:
                raise Exception(f"Image generation returned status {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        # Images are optional - log error but don't fail workflow
        logger.warning(f"World image generation failed, continuing: {e}")

        audit_entry = AuditEntry(
            step=step_name,
            status="completed_with_warnings",
            message="World image generation had errors but continuing",
            error=str(e)
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        # CRITICAL: Clear errors since images are optional
        # State mutations in routing functions don't persist in LangGraph!
        state.errors = []

    return state


async def generate_region_images_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 7: Generate 1 image for each region
    """
    step_name = "generate_region_images"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating 1 image for each of {len(state.region_ids)} regions"
        )

        total_images = 0
        async with httpx.AsyncClient(timeout=180.0) as client:
            for region_id in state.region_ids:
                try:
                    response = await client.post(
                        f"{DJANGO_URL}/worlds/{state.world_id}/regions/{region_id}/generate-image/",
                        headers={'Content-Type': 'application/json'}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        images = result.get('images', [])
                        total_images += len(images)
                        logger.info(f"Generated {len(images)} images for region {region_id}")
                    else:
                        logger.warning(f"Failed to generate images for region {region_id}: {response.status_code}")

                except Exception as e:
                    logger.warning(f"Error generating images for region {region_id}: {e}")
                    continue

        # Cost calculation
        cost_usd = total_images * 0.04
        state.total_cost_usd += cost_usd

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {total_images} region images across {len(state.region_ids)} regions",
            data={'total_images': total_images, 'region_count': len(state.region_ids)},
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {total_images} region images",
            {'total_images': total_images}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        # Images are optional
        logger.warning(f"Region image generation failed, continuing: {e}")

        audit_entry = AuditEntry(
            step=step_name,
            status="completed_with_warnings",
            message="Region image generation had errors but continuing",
            error=str(e)
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        # CRITICAL: Clear errors since images are optional
        state.errors = []

    return state


async def generate_location_images_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 9: Generate 1 image for each Level 1 and Level 2 location (not Level 3)
    """
    step_name = "generate_location_images"
    state.current_step = step_name

    try:
        # Filter to only Level 1 and Level 2 locations
        eligible_locations = [loc for loc in state.locations_data if loc.get('hierarchy_level', 1) in [1, 2]]

        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating 1 image for each of {len(eligible_locations)} Level 1 & 2 locations"
        )

        total_images = 0
        async with httpx.AsyncClient(timeout=180.0) as client:
            for location_data in eligible_locations:
                location_id = location_data.get('_id')
                region_id = location_data.get('region_id')

                try:
                    response = await client.post(
                        f"{DJANGO_URL}/worlds/{state.world_id}/regions/{region_id}/locations/{location_id}/generate-image/",
                        headers={'Content-Type': 'application/json'}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        images = result.get('images', [])
                        total_images += len(images)
                        logger.info(f"Generated {len(images)} images for location {location_id}")
                    else:
                        logger.warning(f"Failed to generate images for location {location_id}: {response.status_code}")

                except Exception as e:
                    logger.warning(f"Error generating images for location {location_id}: {e}")
                    continue

        # Cost calculation
        cost_usd = total_images * 0.04
        state.total_cost_usd += cost_usd

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {total_images} location images across {len(state.location_ids)} locations",
            data={'total_images': total_images, 'location_count': len(state.location_ids)},
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {total_images} location images",
            {'total_images': total_images}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        # Images are optional
        logger.warning(f"Location image generation failed, continuing: {e}")

        audit_entry = AuditEntry(
            step=step_name,
            status="completed_with_warnings",
            message="Location image generation had errors but continuing",
            error=str(e)
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        # CRITICAL: Clear errors since images are optional
        state.errors = []

    return state


async def generate_species_images_node(state: WorldFactoryState) -> WorldFactoryState:
    """
    Node 11: Generate 1 image for each species
    """
    step_name = "generate_species_images"
    state.current_step = step_name

    try:
        publish_progress(
            state.workflow_id,
            step_name,
            "started",
            f"Generating 1 image (Full Body) for each of {len(state.species_ids)} species"
        )

        total_images = 0
        async with httpx.AsyncClient(timeout=180.0) as client:
            for species_id in state.species_ids:
                try:
                    response = await client.post(
                        f"{DJANGO_URL}/worlds/{state.world_id}/species/{species_id}/generate-image/",
                        headers={'Content-Type': 'application/json'}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        images = result.get('images', [])
                        total_images += len(images)
                        logger.info(f"Generated {len(images)} images for species {species_id}")
                    else:
                        logger.warning(f"Failed to generate images for species {species_id}: {response.status_code}")

                except Exception as e:
                    logger.warning(f"Error generating images for species {species_id}: {e}")
                    continue

        # Cost calculation
        cost_usd = total_images * 0.04
        state.total_cost_usd += cost_usd

        audit_entry = AuditEntry(
            step=step_name,
            status="completed",
            message=f"Generated {total_images} species images across {len(state.species_ids)} species",
            data={'total_images': total_images, 'species_count': len(state.species_ids)},
            cost_usd=cost_usd
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        publish_progress(
            state.workflow_id,
            step_name,
            "completed",
            f"Generated {total_images} species images",
            {'total_images': total_images}
        )

        state.retry_count = 0

    except Exception as e:
        logger.error(f"Error in {step_name}: {e}", exc_info=True)
        # Images are optional
        logger.warning(f"Species image generation failed, continuing: {e}")

        audit_entry = AuditEntry(
            step=step_name,
            status="completed_with_warnings",
            message="Species image generation had errors but continuing",
            error=str(e)
        )
        state.audit_trail.append(audit_entry)
        save_audit_trail(state.workflow_id, audit_entry.dict())

        # CRITICAL: Clear errors since images are optional
        state.errors = []

    return state
