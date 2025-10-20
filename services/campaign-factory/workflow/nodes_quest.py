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


def validate_quest_objective_uniqueness(quests: List[QuestData]) -> List[str]:
    """
    Validate that quest objectives are reasonably unique across quests.

    Returns list of warning messages (not hard errors, since some overlap is OK).
    """
    warnings = []

    # Track objective descriptions (normalized to lowercase for comparison)
    objective_descriptions = {}

    for quest in quests:
        quest_name = quest.get("name", "Unknown Quest")
        objectives = quest.get("objectives", [])

        for obj in objectives:
            obj_desc = obj.get("description", "").strip().lower()

            if not obj_desc:
                warnings.append(f"Quest '{quest_name}' has an objective with no description")
                continue

            # Check for exact duplicates
            if obj_desc in objective_descriptions:
                warnings.append(
                    f"Duplicate objective '{obj.get('description')}' found in '{quest_name}' "
                    f"(already used in '{objective_descriptions[obj_desc]}')"
                )
            else:
                objective_descriptions[obj_desc] = quest_name

    # Check for high similarity (simple word overlap check)
    obj_list = list(objective_descriptions.keys())
    for i, obj1 in enumerate(obj_list):
        words1 = set(obj1.split())
        for obj2 in obj_list[i+1:]:
            words2 = set(obj2.split())
            overlap = len(words1 & words2) / max(len(words1), len(words2))

            # If 80%+ word overlap, flag as too similar
            if overlap >= 0.8:
                warnings.append(
                    f"Objectives too similar: '{obj1}' in '{objective_descriptions[obj1]}' "
                    f"and '{obj2}' in '{objective_descriptions[obj2]}' "
                    f"({int(overlap*100)}% word overlap)"
                )

    logger.info(f"Objective validation: {len(objective_descriptions)} unique objectives across {len(quests)} quests")

    return warnings


async def generate_quests_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate quests from narrative blueprint

    This node:
    1. Reads the narrative blueprint created in narrative planning phase
    2. Fetches available Level 1 locations from region
    3. Converts narrative chapter plans into full quest objects with objectives
    4. Assigns each quest to a Level 1 location
    5. Stores quests in state

    The narrative blueprint allows places to be reused across quests but ensures unique scenes.
    """
    try:
        state["current_node"] = "generate_quests"
        state["current_phase"] = "quest_gen"
        state["progress_percentage"] = 35
        state["step_progress"] = 0
        state["status_message"] = f"Generating {state['num_quests']} quests from narrative blueprint..."

        await publish_progress(state)

        logger.info(f"Generating {state['num_quests']} quests from narrative blueprint")

        # Get narrative blueprint
        state["step_progress"] = 5
        state["status_message"] = "Loading narrative blueprint..."
        await publish_progress(state)

        narrative_blueprint = state.get("narrative_blueprint")
        if not narrative_blueprint:
            raise ValueError("No narrative blueprint found - plan_narrative must run first")

        quest_chapters = narrative_blueprint.get("quests", [])
        if not quest_chapters:
            raise ValueError("Narrative blueprint has no quest chapters")

        # Validate blueprint has correct number of quests
        if len(quest_chapters) != state['num_quests']:
            logger.warning(f"Blueprint has {len(quest_chapters)} quests but {state['num_quests']} were requested - using blueprint count")
            state['num_quests'] = len(quest_chapters)

        # Fetch existing Level 1 locations for region via MCP
        state["step_progress"] = 10
        state["status_message"] = "Fetching available locations..."
        await publish_progress(state)

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

The narrative plan allows places to be reused but ensures unique scenes.
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

        total_quests = len(quest_chapters)
        for quest_idx, chapter in enumerate(quest_chapters):
            # Update step progress for each quest (15% to 50% range for quest generation)
            quest_step_progress = 15 + int((quest_idx / total_quests) * 35)
            state["step_progress"] = quest_step_progress
            state["status_message"] = f"Generating quest {quest_idx + 1} of {total_quests}: {chapter.get('chapter_title', 'Quest')}..."
            await publish_progress(state)
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

            # Generate quest ID immediately (needed for place/scene parent relationships)
            quest_id = f"quest_{uuid.uuid4().hex[:16]}"

            quest: QuestData = {
                "quest_id": quest_id,
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

            # Log blueprint usage for traceability
            logger.info(f"Quest '{quest['name']}' generated from blueprint chapter {chapter.get('quest_number')} with {len(chapter.get('places', []))} planned places")

            quests.append(quest)

        state["quests"] = quests

        # VALIDATE: Check that quest objectives are diverse
        objective_validation_errors = validate_quest_objective_uniqueness(quests)
        if objective_validation_errors:
            logger.warning(f"Quest objective validation warnings: {'; '.join(objective_validation_errors)}")
            # NOTE: These are warnings, not hard errors, since some overlap is acceptable

        # NEW: Phase 2 - Objective Linking System
        # For each quest, generate structured objectives with knowledge/item requirements
        state["step_progress"] = 55
        state["status_message"] = "Generating knowledge and item requirements..."
        await publish_progress(state)

        logger.info("Generating structured objectives with knowledge/item requirements...")

        all_knowledge_entities = []
        all_item_entities = []

        total_quests_for_objectives = len(quests)
        for obj_quest_idx, quest in enumerate(quests):
            # Update step progress for objective generation (55% to 90% range)
            obj_step_progress = 55 + int((obj_quest_idx / total_quests_for_objectives) * 35)
            state["step_progress"] = obj_step_progress
            state["status_message"] = f"Generating objectives for quest {obj_quest_idx + 1} of {total_quests_for_objectives}..."
            await publish_progress(state)
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

        # Deduplicate knowledge and item entities across all quests
        # Multiple quests may create objectives for the same knowledge/item
        unique_knowledge = {}
        for kg in all_knowledge_entities:
            kg_name = kg.get("name", "")
            if kg_name and kg_name not in unique_knowledge:
                unique_knowledge[kg_name] = kg

        unique_items = {}
        for item in all_item_entities:
            item_name = item.get("name", "")
            if item_name and item_name not in unique_items:
                unique_items[item_name] = item

        deduplicated_knowledge = list(unique_knowledge.values())
        deduplicated_items = list(unique_items.values())

        logger.info(f"Deduplication: {len(all_knowledge_entities)} -> {len(deduplicated_knowledge)} knowledge, {len(all_item_entities)} -> {len(deduplicated_items)} items")

        # Store knowledge and item entities in state
        state["knowledge_entities"] = deduplicated_knowledge
        state["item_entities"] = deduplicated_items

        logger.info(f"Total campaign resources: {len(deduplicated_knowledge)} knowledge, {len(deduplicated_items)} items")

        # Create checkpoint after quest generation
        state["step_progress"] = 95
        state["status_message"] = "Finalizing quest generation..."
        await publish_progress(state)

        create_checkpoint(state, "quests_generated")

        state["step_progress"] = 100
        state["status_message"] = f"Generated {len(quests)} quests with {len(all_knowledge_entities)} knowledge and {len(all_item_entities)} items"
        await publish_progress(state)

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
