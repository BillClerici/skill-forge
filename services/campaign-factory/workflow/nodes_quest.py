"""
Campaign Quest Generation Nodes
Phase 4: Generate quests with objectives and Level 1 location assignments
"""
import os
import logging
import json
import uuid
from typing import List, Dict
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, QuestData
from .utils import add_audit_entry, publish_progress, create_checkpoint, get_blooms_level_description
from .objective_system import (
    generate_quest_objectives,
    create_knowledge_entities_from_objectives,
    create_item_entities_from_objectives,
    validate_objective_achievability
)

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # API key read from ANTHROPIC_API_KEY env var
    temperature=0.8,
    max_tokens=4096
)


async def generate_quests_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate quests for the campaign

    This node:
    1. Takes user specifications (num_quests, difficulty, playtime)
    2. Fetches available Level 1 locations from region
    3. Generates quests with objectives
    4. Assigns each quest to a Level 1 location
    5. May create new Level 1 locations if needed (enriches world)
    6. Stores quests in state
    """
    try:
        state["current_node"] = "generate_quests"
        state["current_phase"] = "quest_gen"
        state["progress_percentage"] = 35
        state["status_message"] = f"Generating {state['num_quests']} quests..."

        await publish_progress(state)

        logger.info(f"Generating {state['num_quests']} quests for campaign")

        # Fetch existing Level 1 locations for region via MCP
        from .mcp_client import fetch_level1_locations
        existing_level1_locations = await fetch_level1_locations(state["region_id"])

        if not existing_level1_locations:
            logger.warning(f"No existing Level 1 locations found for region {state['region_id']}")
            existing_level1_locations = []

        # Create prompt for quest generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master quest designer for RPG games with expertise in educational design and Bloom's Taxonomy.

Your task is to generate a series of quests that form a coherent campaign progression.

Each quest should:
- Advance the overall campaign storyline
- Have 2-4 specific objectives with Bloom's Taxonomy levels
- Be assigned to an appropriate Level 1 location (settlement, dungeon, natural feature)
- Build on previous quests in complexity
- Match the specified difficulty and duration

You can:
- Use existing Level 1 locations from the region
- Suggest NEW Level 1 locations if they would better serve the narrative (these will be added to the world permanently)

Bloom's Taxonomy Levels:
1. Remembering - Recall facts and basic concepts
2. Understanding - Explain ideas or concepts
3. Applying - Use information in new situations
4. Analyzing - Draw connections among ideas
5. Evaluating - Justify a decision or course of action
6. Creating - Produce new or original work

Return your response as a JSON array with this structure:
[
  {{
    "quest_name": "Quest title",
    "description": "Quest description and narrative context",
    "objectives": [
      {{
        "description": "Objective description",
        "blooms_level": 3,
        "required_for_completion": true
      }}
    ],
    "level_1_location": {{
      "use_existing": true,
      "existing_location_id": "loc1",
      "existing_location_name": "Crystal City",
      "or_create_new": false,
      "new_location_name": "",
      "new_location_type": "",
      "new_location_description": ""
    }},
    "backstory": "Quest backstory and context",
    "estimated_duration_minutes": 90,
    "difficulty_level": "Medium",
    "order_sequence": 1
  }}
]

CRITICAL: Return ONLY the JSON array, no other text."""),
            ("user", """Campaign Context:
Name: {campaign_name}
Plot: {plot}
Primary Objectives: {primary_objectives}

Quest Specifications:
- Number of Quests: {num_quests}
- Difficulty: {difficulty}
- Duration per Quest: {duration} minutes
- Target Bloom's Level: {blooms_level} ({blooms_desc})

Existing Level 1 Locations in Region:
{existing_locations}

Generate {num_quests} quests that form a coherent campaign progression.""")
        ])

        # Format existing locations
        locations_str = "\n".join([
            f"- {loc['name']} ({loc['type']}) [ID: {loc['id']}]"
            for loc in existing_level1_locations
        ])

        # Format primary objectives
        objectives_str = "\n".join([
            f"- {obj['description']} (Bloom's: {obj['blooms_level']})"
            for obj in state["campaign_core"]["primary_objectives"]
        ])

        # Generate quests
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "campaign_name": state["campaign_core"]["name"],
            "plot": state["campaign_core"]["plot"],
            "primary_objectives": objectives_str,
            "num_quests": state["num_quests"],
            "difficulty": state["quest_difficulty"],
            "duration": state["quest_playtime_minutes"],
            "blooms_level": state["campaign_core"]["target_blooms_level"],
            "blooms_desc": get_blooms_level_description(state["campaign_core"]["target_blooms_level"]),
            "existing_locations": locations_str
        })

        # Parse response
        quests_raw = json.loads(response.content.strip())

        # Process quests and handle location assignment
        quests: List[QuestData] = []
        for quest_data in quests_raw:
            location_info = quest_data.get("level_1_location", {})

            # Determine location ID (use existing or create new)
            if location_info.get("use_existing", True):
                location_id = location_info.get("existing_location_id", "")
                location_name = location_info.get("existing_location_name", "")
            else:
                # TODO: Create new Level 1 location via orchestrator
                # For now, generate placeholder ID
                new_location_id = f"new_loc_{uuid.uuid4().hex[:8]}"
                state["new_location_ids"].append(new_location_id)
                location_id = new_location_id
                location_name = location_info.get("new_location_name", f"Location for {quest_data.get('quest_name', 'Quest')}")

                logger.info(f"Quest requires new location: {location_name} ({location_info.get('new_location_type')})")

            quest: QuestData = {
                "quest_id": None,  # Will be set on persistence
                "name": quest_data.get("quest_name", f"{state['campaign_core']['name']} - Quest {len(quests) + 1}"),
                "description": quest_data.get("description", ""),
                "objectives": quest_data.get("objectives", []),
                "level_1_location_id": location_id,
                "level_1_location_name": location_name,
                "difficulty_level": quest_data.get("difficulty_level", state["quest_difficulty"]),
                "estimated_duration_minutes": quest_data.get("estimated_duration_minutes", state["quest_playtime_minutes"]),
                "order_sequence": quest_data.get("order_sequence", len(quests) + 1),
                "backstory": quest_data.get("backstory", "")
            }

            quests.append(quest)

        state["quests"] = quests

        # NEW: Phase 2 - Objective Linking System
        # For each quest, generate structured objectives with knowledge/item requirements
        logger.info("Generating structured objectives with knowledge/item requirements...")

        all_knowledge_entities = []
        all_item_entities = []

        for quest in quests:
            try:
                # Generate structured objectives
                structured_objectives = await generate_quest_objectives(
                    quest,
                    state["campaign_core"]["primary_objectives"],
                    state
                )

                # Create knowledge entities from objectives
                knowledge_entities = await create_knowledge_entities_from_objectives(
                    structured_objectives,
                    quest,
                    state
                )
                all_knowledge_entities.extend(knowledge_entities)

                # Create item entities from objectives
                item_entities = await create_item_entities_from_objectives(
                    structured_objectives,
                    quest,
                    state
                )
                all_item_entities.extend(item_entities)

                # Store structured objectives back on the quest
                quest["structured_objectives"] = structured_objectives

                logger.info(f"Quest '{quest['name']}': {len(knowledge_entities)} knowledge, {len(item_entities)} items")

            except Exception as e:
                logger.error(f"Error processing objectives for quest '{quest['name']}': {str(e)}")
                continue

        # Store knowledge and item entities in state
        state["knowledge_entities"] = all_knowledge_entities
        state["item_entities"] = all_item_entities

        logger.info(f"Total campaign resources: {len(all_knowledge_entities)} knowledge, {len(all_item_entities)} items")

        # Create checkpoint after quest generation
        create_checkpoint(state, "quests_generated")

        add_audit_entry(
            state,
            "generate_quests",
            "Generated quests with objectives",
            {
                "num_quests": len(quests),
                "new_locations_created": len([q for q in quests if q["level_1_location_id"].startswith("new_loc_")]),
                "quests": [{"name": q["name"], "location": q["level_1_location_name"]} for q in quests],
                "total_knowledge_entities": len(all_knowledge_entities),
                "total_item_entities": len(all_item_entities),
                "knowledge_by_dimension": _count_by_dimension(all_knowledge_entities),
                "items_by_type": _count_by_type(all_item_entities)
            },
            "success"
        )

        logger.info(f"Generated {len(quests)} quests")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating quests: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_quests",
            "Failed to generate quests",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


def _count_by_dimension(knowledge_entities: List) -> Dict[str, int]:
    """Helper to count knowledge entities by primary dimension"""
    counts = {}
    for kg in knowledge_entities:
        dim = kg.get("primary_dimension", "unknown")
        counts[dim] = counts.get(dim, 0) + 1
    return counts


def _count_by_type(item_entities: List) -> Dict[str, int]:
    """Helper to count item entities by type"""
    counts = {}
    for item in item_entities:
        item_type = item.get("item_type", "unknown")
        counts[item_type] = counts.get(item_type, 0) + 1
    return counts
