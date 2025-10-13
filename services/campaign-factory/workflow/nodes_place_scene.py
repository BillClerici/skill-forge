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
    Generate places (Level 2 locations) for each quest

    This node:
    1. For each quest, fetches Level 2 locations under its Level 1 location
    2. Generates 2-4 places where quest objectives occur
    3. May create new Level 2 locations if needed (enriches world)
    4. Stores places in state
    """
    try:
        state["current_node"] = "generate_places"
        state["current_phase"] = "place_gen"
        state["progress_percentage"] = 55
        state["status_message"] = "Generating places for quests..."

        await publish_progress(state)

        total_quests = len(state['quests'])
        logger.info(f"Generating places for {total_quests} quests")

        all_places: List[PlaceData] = []

        # Generate places for each quest
        for quest_idx, quest in enumerate(state["quests"]):
            # Update progress for each quest (55% to 70% range)
            quest_progress = 55 + int((quest_idx / total_quests) * 15)  # 55% to 70%
            state["progress_percentage"] = quest_progress
            state["status_message"] = f"Generating places for quest {quest_idx + 1} of {total_quests}..."
            await publish_progress(state, f"Quest: {quest['name']}")

            logger.info(f"Generating places for quest {quest_idx + 1}/{total_quests}: {quest['name']}")

            # Fetch existing Level 2 locations under quest's Level 1 location via MCP
            from .mcp_client import fetch_level2_locations
            existing_level2_locations = await fetch_level2_locations(quest["level_1_location_id"])

            if not existing_level2_locations:
                logger.info(f"No existing Level 2 locations found under {quest['level_1_location_name']}")
                existing_level2_locations = []

            # Create prompt for place generation
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a master quest and location designer for RPG games.

Your task is to generate Places (Level 2 locations) where quest objectives occur.

Places are specific buildings, outdoor areas, or sub-locations within a Level 1 location.
Examples: Tavern, Shop, Temple, Park, Cave, Marketplace, Manor, Guard Post

Each place should:
- Be logically located within the quest's Level 1 location
- Support specific quest objectives
- Have narrative significance

You can:
- Use existing Level 2 locations
- Suggest NEW Level 2 locations if needed for the narrative (these will be added to the world permanently)

Return your response as a JSON array with this structure:
[
  {{
    "place_name": "Place name",
    "description": "Place description and atmosphere",
    "level_2_location": {{
      "use_existing": true,
      "existing_location_id": "place1",
      "existing_location_name": "The Silver Tavern",
      "or_create_new": false,
      "new_location_name": "",
      "new_location_type": "",
      "new_location_description": ""
    }},
    "objectives_supported": ["Objective 1", "Objective 2"]
  }}
]

Generate 2-4 places for this quest.

CRITICAL: Return ONLY the JSON array, no other text."""),
                ("user", """Quest Context:
Quest Name: {quest_name}
Description: {quest_description}
Objectives: {objectives}
Level 1 Location: {level_1_location}

Existing Level 2 Locations:
{existing_locations}

Generate 2-4 places where this quest's objectives occur.""")
            ])

            # Format objectives
            objectives_str = "\n".join([
                f"- {obj['description']}"
                for obj in quest.get("objectives", [])
            ])

            # Format existing locations
            locations_str = "\n".join([
                f"- {loc['name']} ({loc['type']}) [ID: {loc['id']}]"
                for loc in existing_level2_locations
            ])

            # Generate places
            chain = prompt | anthropic_client
            response = await chain.ainvoke({
                "quest_name": quest["name"],
                "quest_description": quest["description"],
                "objectives": objectives_str,
                "level_1_location": quest["level_1_location_name"],
                "existing_locations": locations_str
            })

            # Parse response
            places_raw = json.loads(response.content.strip())

            # Process places
            quest_places: List[PlaceData] = []
            for place_data in places_raw:
                location_info = place_data.get("level_2_location", {})

                # Determine location ID
                if location_info.get("use_existing", True):
                    location_id = location_info.get("existing_location_id", "")
                    location_name = location_info.get("existing_location_name", "")
                else:
                    # Create new Level 2 location
                    new_location_id = f"new_place_{uuid.uuid4().hex[:8]}"
                    location_name = location_info.get("new_location_name", f"Place in {quest['level_1_location_name']}")
                    location_type = location_info.get("new_location_type", "Place")
                    location_desc = location_info.get("new_location_description", "")

                    # Store full location details
                    state["new_location_ids"].append(new_location_id)  # DEPRECATED
                    state["new_locations"].append({
                        "id": new_location_id,
                        "name": location_name,
                        "type": location_type,
                        "description": location_desc,
                        "level": 2,
                        "parent_location_id": quest["level_1_location_id"]
                    })

                    location_id = new_location_id

                    logger.info(f"Place requires new location: {location_name} ({location_type})")

                place: PlaceData = {
                    "place_id": None,  # Will be set on persistence
                    "name": place_data.get("place_name", f"{quest['level_1_location_name']} - Place {len(quest_places) + 1}"),
                    "description": place_data.get("description", ""),
                    "level_2_location_id": location_id,
                    "level_2_location_name": location_name,
                    "parent_quest_id": quest.get("quest_id", ""),
                    "scenes": []  # Will be populated in scene generation
                }

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
    Generate scenes (Level 3 locations) for each place

    This node:
    1. For each place, fetches Level 3 locations under its Level 2 location
    2. Generates 1-3 scenes where specific interactions occur
    3. May create new Level 3 locations if needed (enriches world)
    4. Stores scenes in state (NPCs, discoveries, events, challenges added later)
    """
    try:
        state["current_node"] = "generate_scenes"
        state["current_phase"] = "scene_gen"
        state["progress_percentage"] = 75
        state["status_message"] = "Generating scenes for places..."

        await publish_progress(state)

        total_places = len(state['places'])
        logger.info(f"Generating scenes for {total_places} places")

        all_scenes: List[SceneData] = []

        # Generate scenes for each place
        for place_idx, place in enumerate(state["places"]):
            # Update progress for each place (75% to 90% range)
            place_progress = 75 + int((place_idx / total_places) * 15)  # 75% to 90%
            state["progress_percentage"] = place_progress
            state["status_message"] = f"Generating scenes for place {place_idx + 1} of {total_places}..."
            await publish_progress(state, f"Place: {place['name']}")

            logger.info(f"Generating scenes for place {place_idx + 1}/{total_places}: {place['name']}")

            # Fetch existing Level 3 locations under place's Level 2 location via MCP
            from .mcp_client import fetch_level3_locations
            existing_level3_locations = await fetch_level3_locations(place["level_2_location_id"])

            if not existing_level3_locations:
                logger.info(f"No existing Level 3 locations found under {place['level_2_location_name']}")
                existing_level3_locations = []

            # Create prompt for scene generation
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a master scene designer for RPG games.

Your task is to generate Scenes (Level 3 locations) where specific interactions occur.

Scenes are specific rooms, areas, or spaces within a Level 2 location.
Examples: The Bar, Kitchen, Bedroom, Chamber, Altar Room, Storage Area, Garden Corner

Each scene should:
- Be logically located within the place's Level 2 location
- Support specific narrative moments or interactions
- Have distinct atmosphere and purpose

You can:
- Use existing Level 3 locations
- Suggest NEW Level 3 locations if needed for the narrative (these will be added to the world permanently)

Return your response as a JSON array with this structure:
[
  {{
    "scene_name": "Scene name",
    "description": "Scene description, atmosphere, and narrative purpose",
    "level_3_location": {{
      "use_existing": true,
      "existing_location_id": "scene1",
      "existing_location_name": "The Bar",
      "or_create_new": false,
      "new_location_name": "",
      "new_location_type": "",
      "new_location_description": ""
    }},
    "narrative_purpose": "What happens in this scene",
    "order_sequence": 1
  }}
]

Generate 1-3 scenes for this place.

CRITICAL: Return ONLY the JSON array, no other text."""),
                ("user", """Place Context:
Place Name: {place_name}
Description: {place_description}
Level 2 Location: {level_2_location}

Existing Level 3 Locations:
{existing_locations}

Generate 1-3 scenes within this place.""")
            ])

            # Format existing locations
            locations_str = "\n".join([
                f"- {loc['name']} ({loc['type']}) [ID: {loc['id']}]"
                for loc in existing_level3_locations
            ])

            # Generate scenes
            chain = prompt | anthropic_client
            response = await chain.ainvoke({
                "place_name": place["name"],
                "place_description": place["description"],
                "level_2_location": place["level_2_location_name"],
                "existing_locations": locations_str
            })

            # Parse response
            scenes_raw = json.loads(response.content.strip())

            # Process scenes
            place_scenes: List[SceneData] = []
            for scene_data in scenes_raw:
                location_info = scene_data.get("level_3_location", {})

                # Determine location ID
                if location_info.get("use_existing", True):
                    location_id = location_info.get("existing_location_id", "")
                    location_name = location_info.get("existing_location_name", "")
                else:
                    # Create new Level 3 location
                    new_location_id = f"new_scene_{uuid.uuid4().hex[:8]}"
                    location_name = location_info.get("new_location_name", f"Scene in {place['level_2_location_name']}")
                    location_type = location_info.get("new_location_type", "Scene")
                    location_desc = location_info.get("new_location_description", "")

                    # Store full location details
                    state["new_location_ids"].append(new_location_id)  # DEPRECATED
                    state["new_locations"].append({
                        "id": new_location_id,
                        "name": location_name,
                        "type": location_type,
                        "description": location_desc,
                        "level": 3,
                        "parent_location_id": place["level_2_location_id"]
                    })

                    location_id = new_location_id

                    logger.info(f"Scene requires new location: {location_name} ({location_type})")

                scene: SceneData = {
                    "scene_id": None,  # Will be set on persistence
                    "name": scene_data.get("scene_name", f"{place['name']} - Scene {len(place_scenes) + 1}"),
                    "description": scene_data.get("description", ""),
                    "level_3_location_id": location_id,
                    "level_3_location_name": location_name,
                    "parent_place_id": place.get("place_id", ""),
                    "npc_ids": [],  # Will be populated in NPC generation
                    "discovery_ids": [],  # Will be populated in discovery generation
                    "event_ids": [],  # Will be populated in event generation
                    "challenge_ids": [],  # Will be populated in challenge generation
                    "required_knowledge": [],  # May be set based on narrative flow
                    "required_items": [],  # May be set based on narrative flow
                    "order_sequence": scene_data.get("order_sequence", len(place_scenes) + 1)
                }

                place_scenes.append(scene)
                all_scenes.append(scene)

            # Update place with scene IDs (will be set after persistence)
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
