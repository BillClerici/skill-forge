"""
Campaign Place and Scene Generation Nodes
Phase 5-6: Generate places (Level 2) and scenes (Level 3)
"""
import os
import logging
import json
import uuid
from typing import List
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, PlaceData, SceneData
from .utils import add_audit_entry, publish_progress, create_checkpoint

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # API key read from ANTHROPIC_API_KEY env var
    temperature=0.8,
    max_tokens=4096
)


async def generate_places_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate places (Level 2 locations) from narrative blueprint

    This node:
    1. Reads places planned in the narrative blueprint for each quest
    2. Converts narrative place plans into full PlaceData objects
    3. Fetches existing Level 2 locations and maps to them when appropriate
    4. Creates new locations as needed
    5. Stores places in state

    The narrative blueprint allows places to be reused across quests with different scenes.
    """
    try:
        state["current_node"] = "generate_places"
        state["current_phase"] = "place_gen"
        state["progress_percentage"] = 55
        state["step_progress"] = 0
        state["status_message"] = "Generating places from narrative blueprint..."

        await publish_progress(state)

        total_quests = len(state['quests'])
        logger.info(f"Generating places for {total_quests} quests from narrative blueprint")

        all_places: List[PlaceData] = []

        # Generate places for each quest from its narrative chapter
        for quest_idx, quest in enumerate(state["quests"]):
            # Update progress for each quest (55% to 70% range)
            quest_progress = 55 + int((quest_idx / total_quests) * 15)
            state["progress_percentage"] = quest_progress

            # Update step progress (0% to 100% for this phase)
            quest_step_progress = int((quest_idx / total_quests) * 100)
            state["step_progress"] = quest_step_progress
            state["status_message"] = f"Generating places for quest {quest_idx + 1} of {total_quests}..."
            await publish_progress(state, f"Quest: {quest['name']}")

            logger.info(f"Generating places for quest {quest_idx + 1}/{total_quests}: {quest['name']}")

            # Get narrative chapter with places planned
            narrative_chapter = quest.get("narrative_chapter")
            if not narrative_chapter:
                logger.warning(f"Quest '{quest['name']}' has no narrative chapter - falling back to basic generation")
                continue

            planned_places = narrative_chapter.get("places", [])
            if not planned_places:
                logger.warning(f"No places planned for quest '{quest['name']}'")
                continue

            # Fetch existing Level 2 locations under quest's Level 1 location via MCP
            from .mcp_client import fetch_level2_locations
            existing_level2_locations = await fetch_level2_locations(quest["level_1_location_id"])

            if not existing_level2_locations:
                logger.info(f"No existing Level 2 locations found under {quest['level_1_location_name']}")
                existing_level2_locations = []

            # Process each planned place from the narrative blueprint
            quest_places: List[PlaceData] = []
            for place_plan in planned_places:
                place_name = place_plan.get("place_name", f"Place {len(quest_places) + 1}")
                place_description = place_plan.get("place_description", "")

                # Create new Level 2 location for each planned place
                # The narrative blueprint has already ensured uniqueness
                new_location_id = f"new_place_{uuid.uuid4().hex[:8]}"
                location_type = "Place"  # Generic type for narrative-planned locations

                # Store full location details
                state["new_location_ids"].append(new_location_id)  # DEPRECATED
                state["new_locations"].append({
                    "id": new_location_id,
                    "name": place_name,
                    "type": location_type,
                    "description": place_description,
                    "level": 2,
                    "parent_location_id": quest["level_1_location_id"]
                })

                logger.info(f"Creating place from narrative: {place_name}")

                # Generate place ID immediately (needed for scene parent relationships)
                place_id = f"place_{uuid.uuid4().hex[:16]}"

                place: PlaceData = {
                    "place_id": place_id,
                    "name": place_name,
                    "description": place_description,
                    "level_2_location_id": new_location_id,
                    "level_2_location_name": place_name,
                    "parent_quest_id": quest.get("quest_id", ""),
                    "scenes": []  # Will be populated in scene generation
                }

                # Store narrative plan for later use by scene generation
                place["narrative_place_plan"] = place_plan

                quest_places.append(place)
                all_places.append(place)

            logger.info(f"Generated {len(quest_places)} places for quest '{quest['name']}'")

        state["places"] = all_places

        # Create checkpoint after place generation
        create_checkpoint(state, "places_generated")

        add_audit_entry(
            state,
            "generate_places",
            "Generated places",
            {
                "num_places": len(all_places),
                "new_locations_created": len([p for p in all_places if p["level_2_location_id"].startswith("new_place_")]),
                "places_by_quest": {q["name"]: len([p for p in all_places if p["parent_quest_id"] == q.get("quest_id", "")]) for q in state["quests"]}
            },
            "success"
        )

        logger.info(f"Generated {len(all_places)} places total")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating places: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_places",
            "Failed to generate places",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


async def generate_scenes_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate scenes (Level 3 locations) from narrative blueprint

    This node:
    1. Reads scenes planned in the narrative blueprint for each place
    2. Converts narrative scene plans into full SceneData objects
    3. Creates new Level 3 locations for each planned scene
    4. Stores scenes in state (NPCs, discoveries, events, challenges added later)

    The narrative blueprint ensures all scenes are globally unique across the campaign.
    """
    try:
        state["current_node"] = "generate_scenes"
        state["current_phase"] = "scene_gen"
        state["progress_percentage"] = 75
        state["step_progress"] = 0
        state["status_message"] = "Generating scenes from narrative blueprint..."

        await publish_progress(state)

        total_places = len(state['places'])
        logger.info(f"Generating scenes for {total_places} places from narrative blueprint")

        all_scenes: List[SceneData] = []

        # Generate scenes for each place from its narrative plan
        for place_idx, place in enumerate(state["places"]):
            # Update progress for each place (75% to 90% range)
            place_progress = 75 + int((place_idx / total_places) * 15)
            state["progress_percentage"] = place_progress

            # Update step progress (0% to 100% for this phase)
            place_step_progress = int((place_idx / total_places) * 100)
            state["step_progress"] = place_step_progress
            state["status_message"] = f"Generating scenes for place {place_idx + 1} of {total_places}..."
            await publish_progress(state, f"Place: {place['name']}")

            logger.info(f"Generating scenes for place {place_idx + 1}/{total_places}: {place['name']}")

            # Get narrative place plan with scenes
            narrative_place_plan = place.get("narrative_place_plan")
            if not narrative_place_plan:
                logger.warning(f"Place '{place['name']}' has no narrative plan - skipping scene generation")
                continue

            planned_scenes = narrative_place_plan.get("scenes", [])
            if not planned_scenes:
                logger.warning(f"No scenes planned for place '{place['name']}'")
                continue

            # Process each planned scene from the narrative blueprint
            place_scenes: List[SceneData] = []
            for scene_plan in planned_scenes:
                scene_name = scene_plan.get("scene_name", f"Scene {len(place_scenes) + 1}")
                scene_description = scene_plan.get("scene_description", "")

                # Create new Level 3 location for each planned scene
                # The narrative blueprint has already ensured uniqueness
                new_location_id = f"new_scene_{uuid.uuid4().hex[:8]}"
                location_type = "Scene"  # Generic type for narrative-planned scenes

                # Store full location details
                state["new_location_ids"].append(new_location_id)  # DEPRECATED
                state["new_locations"].append({
                    "id": new_location_id,
                    "name": scene_name,
                    "type": location_type,
                    "description": scene_description,
                    "level": 3,
                    "parent_location_id": place["level_2_location_id"]
                })

                logger.info(f"Creating scene from narrative: {scene_name}")

                # Generate scene ID immediately (not during persistence)
                scene_id = f"scene_{uuid.uuid4().hex[:16]}"

                scene: SceneData = {
                    "scene_id": scene_id,  # Generated immediately for entity linking
                    "name": scene_name,
                    "description": scene_description,
                    "level_3_location_id": new_location_id,
                    "level_3_location_name": scene_name,
                    "parent_place_id": place.get("place_id", ""),
                    "npc_ids": [],  # Will be populated in NPC generation
                    "discovery_ids": [],  # Will be populated in discovery generation
                    "event_ids": [],  # Will be populated in event generation
                    "challenge_ids": [],  # Will be populated in challenge generation
                    "required_knowledge": [],  # May be set based on narrative flow
                    "required_items": [],  # May be set based on narrative flow
                    "order_sequence": len(place_scenes) + 1
                }

                place_scenes.append(scene)
                all_scenes.append(scene)

            # Update place with scene IDs
            place["scenes"] = [s.get("scene_id", "") for s in place_scenes]

            logger.info(f"Generated {len(place_scenes)} scenes for place '{place['name']}'")

        state["scenes"] = all_scenes

        # Create checkpoint after scene generation
        create_checkpoint(state, "scenes_generated")

        add_audit_entry(
            state,
            "generate_scenes",
            "Generated scenes",
            {
                "num_scenes": len(all_scenes),
                "new_locations_created": len([s for s in all_scenes if s["level_3_location_id"].startswith("new_scene_")]),
                "scenes_by_place": {p["name"]: len([s for s in all_scenes if s["parent_place_id"] == p.get("place_id", "")]) for p in state["places"]}
            },
            "success"
        )

        logger.info(f"Generated {len(all_scenes)} scenes total")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating scenes: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_scenes",
            "Failed to generate scenes",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state
