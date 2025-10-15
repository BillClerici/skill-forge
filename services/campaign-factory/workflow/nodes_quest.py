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
    Generate quests from narrative blueprint

    This node:
    1. Reads the narrative blueprint created in narrative planning phase
    2. Fetches available Level 1 locations from region
    3. Converts narrative chapter plans into full quest objects with objectives
    4. Assigns each quest to a Level 1 location
    5. Stores quests in state

    The narrative blueprint ensures each quest has unique places/scenes planned upfront.
    """
    try:
        state["current_node"] = "generate_quests"
        state["current_phase"] = "quest_gen"
        state["progress_percentage"] = 35
        state["status_message"] = f"Generating {state['num_quests']} quests from narrative blueprint..."

        await publish_progress(state)

        logger.info(f"Generating {state['num_quests']} quests from narrative blueprint")

        # Get narrative blueprint
        narrative_blueprint = state.get("narrative_blueprint")
        if not narrative_blueprint:
            raise ValueError("No narrative blueprint found - plan_narrative must run first")

        quest_chapters = narrative_blueprint.get("quests", [])
        if not quest_chapters:
            raise ValueError("Narrative blueprint has no quest chapters")

        # Fetch existing Level 1 locations for region via MCP
        from .mcp_client import fetch_level1_locations
        existing_level1_locations = await fetch_level1_locations(state["region_id"])

        if not existing_level1_locations:
            logger.warning(f"No existing Level 1 locations found for region {state['region_id']}")
            existing_level1_locations = []

        # Convert narrative chapters into full quest objects with objectives
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are converting a narrative chapter plan into a detailed quest with objectives.

Your task is to take the narrative chapter summary and create:
1. A detailed quest description that captures the narrative beats
2. 2-4 specific, actionable objectives that align with the story beats
3. Select an appropriate Level 1 location from existing locations (or suggest a new one)
4. Create backstory that connects to the campaign plot

The narrative plan already ensures unique places/scenes for each quest.
Your job is to create the quest mechanics (objectives, blooms levels, etc.).

Bloom's Taxonomy Levels:
1. Remembering - Recall facts and basic concepts
2. Understanding - Explain ideas or concepts
3. Applying - Use information in new situations
4. Analyzing - Draw connections among ideas
5. Evaluating - Justify a decision or course of action
6. Creating - Produce new or original work

Return your response as a JSON object with this EXACT structure:
{{
  "quest_name": "Chapter title from narrative plan",
  "description": "Detailed quest description that captures narrative beats",
  "objectives": [
    {{
      "description": "Specific, actionable objective",
      "blooms_level": 3,
      "required_for_completion": true
    }}
  ],
  "level_1_location": {{
    "use_existing": true,
    "existing_location_id": "loc_id",
    "existing_location_name": "Location name",
    "or_create_new": false,
    "new_location_name": "",
    "new_location_type": "",
    "new_location_description": ""
  }},
  "backstory": "Quest backstory",
  "estimated_duration_minutes": 60,
  "difficulty_level": "Medium",
  "order_sequence": 1
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """Campaign Context:
Name: {campaign_name}
Plot: {plot}
Primary Objectives: {primary_objectives}

Narrative Chapter Plan:
- Chapter Title: {chapter_title}
- Chapter Summary: {chapter_summary}
- Narrative Purpose: {narrative_purpose}
- Story Beats:
{story_beats}

Quest Specifications:
- Quest Number: {quest_number} of {total_quests}
- Difficulty: {difficulty}
- Duration: {duration} minutes
- Target Bloom's Level: {blooms_level}

Existing Level 1 Locations in Region:
{existing_locations}

Convert this narrative chapter into a detailed quest with objectives.""")
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

        # Generate quests from narrative blueprint
        quests: List[QuestData] = []
        chain = prompt | anthropic_client

        for chapter in quest_chapters:
            # Format story beats
            story_beats_str = "\n".join([f"  {beat}" for beat in chapter.get("story_beats", [])])

            response = await chain.ainvoke({
                "campaign_name": state["campaign_core"]["name"],
                "plot": state["campaign_core"]["plot"],
                "primary_objectives": objectives_str,
                "chapter_title": chapter.get("chapter_title", f"Quest {chapter.get('quest_number', len(quests) + 1)}"),
                "chapter_summary": chapter.get("chapter_summary", ""),
                "narrative_purpose": chapter.get("narrative_purpose", ""),
                "story_beats": story_beats_str,
                "quest_number": chapter.get("quest_number", len(quests) + 1),
                "total_quests": state["num_quests"],
                "difficulty": state["quest_difficulty"],
                "duration": state["quest_playtime_minutes"],
                "blooms_level": state["campaign_core"]["target_blooms_level"],
                "existing_locations": locations_str
            })

            quest_data = json.loads(response.content.strip())

            # Handle location assignment
            location_info = quest_data.get("level_1_location", {})

            if location_info.get("use_existing", True):
                location_id = location_info.get("existing_location_id", "")
                location_name = location_info.get("existing_location_name", "")
            else:
                # Create new Level 1 location
                new_location_id = f"new_loc_{uuid.uuid4().hex[:8]}"
                state["new_location_ids"].append(new_location_id)
                location_id = new_location_id
                location_name = location_info.get("new_location_name", f"Location for {quest_data.get('quest_name', 'Quest')}")
                logger.info(f"Quest requires new location: {location_name} ({location_info.get('new_location_type')})")

            quest: QuestData = {
                "quest_id": None,
                "name": quest_data.get("quest_name", chapter.get("chapter_title", f"Quest {len(quests) + 1}")),
                "description": quest_data.get("description", chapter.get("chapter_summary", "")),
                "objectives": quest_data.get("objectives", []),
                "level_1_location_id": location_id,
                "level_1_location_name": location_name,
                "difficulty_level": quest_data.get("difficulty_level", state["quest_difficulty"]),
                "estimated_duration_minutes": quest_data.get("estimated_duration_minutes", state["quest_playtime_minutes"]),
                "order_sequence": chapter.get("quest_number", len(quests) + 1),
                "backstory": quest_data.get("backstory", "")
            }

            # Store narrative chapter info for later use by place/scene generation
            quest["narrative_chapter"] = chapter

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
