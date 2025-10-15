"""
Campaign Core Generation Nodes
Phase 3: Generate campaign plot, storyline, and primary objectives
"""
import os
import logging
import json
import uuid
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, CampaignCore
from .utils import add_audit_entry, publish_progress, create_checkpoint, get_blooms_level_description

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # API key read from ANTHROPIC_API_KEY env var
    temperature=0.8,
    max_tokens=4096
)


async def generate_campaign_core_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate campaign core: name, plot, storyline, primary objectives

    This node:
    1. Takes selected story idea
    2. Generates detailed plot and storyline
    3. Creates 3-5 primary objectives with Bloom's taxonomy levels
    4. Estimates duration and difficulty
    5. Stores in state for user approval
    """
    try:
        state["current_node"] = "generate_campaign_core"
        state["current_phase"] = "core_gen"
        state["progress_percentage"] = 15
        state["step_progress"] = 0
        state["status_message"] = "Generating campaign plot and objectives..."

        await publish_progress(state)

        logger.info(f"Generating campaign core from story idea: {state['selected_story_id']}")

        # Find selected story idea
        state["step_progress"] = 10
        state["status_message"] = "Loading selected story idea..."
        await publish_progress(state)

        selected_story = None
        for story in state["story_ideas"]:
            if story["id"] == state["selected_story_id"]:
                selected_story = story
                break

        if not selected_story:
            raise ValueError(f"Selected story ID {state['selected_story_id']} not found")

        # Get target Bloom's level from character (or default)
        # TODO: Fetch from character via MCP
        target_blooms_level = 3  # Default to "Applying"

        state["step_progress"] = 25
        state["status_message"] = "Generating campaign plot..."
        await publish_progress(state)

        # Create prompt for campaign core generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master campaign designer for RPG games with expertise in educational design and Bloom's Taxonomy.

Your task is to develop a complete campaign based on the selected story idea.

The campaign should include:
1. **Campaign Name**: Compelling, memorable title
2. **Plot**: 3-4 paragraph overview of the main story arc
3. **Storyline**: Detailed 5-7 paragraph narrative describing the campaign's progression
4. **Primary Objectives**: 3-5 high-level objectives that guide the entire campaign

Each Primary Objective must include:
- Clear, actionable description
- Associated Bloom's Taxonomy level (1-6)
- How it contributes to the overall campaign goal

Bloom's Taxonomy Levels:
1. Remembering - Recall facts and basic concepts
2. Understanding - Explain ideas or concepts
3. Applying - Use information in new situations
4. Analyzing - Draw connections among ideas
5. Evaluating - Justify a decision or course of action
6. Creating - Produce new or original work

Return your response as JSON with this structure:
{{
  "campaign_name": "The campaign name",
  "plot": "Multi-paragraph plot description",
  "storyline": "Multi-paragraph storyline",
  "primary_objectives": [
    {{
      "description": "Objective description",
      "blooms_level": 3,
      "contribution": "How this objective advances the campaign"
    }}
  ],
  "estimated_duration_hours": 20,
  "difficulty_level": "Medium"
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """Story Idea Selected:
Title: {title}
Summary: {summary}
Themes: {themes}
Target Difficulty: {difficulty}

World Context:
- Universe: {universe}
- World: {world}
- Region: {region}
- Genre: {genre}

Target Bloom's Level: {blooms_level} ({blooms_desc})

Generate a complete campaign based on this story idea.""")
        ])

        # Generate campaign core
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "title": selected_story["title"],
            "summary": selected_story["summary"],
            "themes": ", ".join(selected_story["themes"]),
            "difficulty": selected_story["difficulty_level"],
            "universe": state["universe_name"],
            "world": state["world_name"],
            "region": state["region_name"],
            "genre": state["genre"],
            "blooms_level": target_blooms_level,
            "blooms_desc": get_blooms_level_description(target_blooms_level)
        })

        # Parse response
        state["step_progress"] = 70
        state["status_message"] = "Parsing campaign details..."
        await publish_progress(state)

        core_data = json.loads(response.content.strip())

        # Create CampaignCore
        state["step_progress"] = 85
        state["status_message"] = "Finalizing campaign core..."
        await publish_progress(state)

        campaign_core: CampaignCore = {
            "campaign_id": None,  # Will be set on finalization
            "name": core_data.get("campaign_name", selected_story["title"]),
            "plot": core_data.get("plot", ""),
            "storyline": core_data.get("storyline", ""),
            "primary_objectives": core_data.get("primary_objectives", []),
            "universe_id": state["universe_id"],
            "world_id": state["world_id"],
            "region_id": state["region_id"],
            "genre": state["genre"],
            "estimated_duration_hours": core_data.get("estimated_duration_hours", 20),
            "difficulty_level": core_data.get("difficulty_level", selected_story["difficulty_level"]),
            "target_blooms_level": target_blooms_level
        }

        state["campaign_core"] = campaign_core

        # Create checkpoint after core generation
        create_checkpoint(state, "campaign_core_generated")

        state["step_progress"] = 100
        state["status_message"] = f"Generated campaign: {campaign_core['name']}"
        await publish_progress(state)

        add_audit_entry(
            state,
            "generate_campaign_core",
            "Generated campaign core",
            {
                "campaign_name": campaign_core["name"],
                "num_objectives": len(campaign_core["primary_objectives"]),
                "estimated_duration": campaign_core["estimated_duration_hours"],
                "difficulty": campaign_core["difficulty_level"]
            },
            "success"
        )

        logger.info(f"Generated campaign core: {campaign_core['name']}")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating campaign core: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_campaign_core",
            "Failed to generate campaign core",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


async def wait_for_core_approval_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Wait for user to approve campaign core

    This is a human-in-the-loop node that pauses workflow until:
    - User approves the campaign core
    - User requests modifications
    - User cancels workflow

    In practice, this node sets state to indicate waiting, and the workflow
    is resumed via API call when user makes decision.
    """
    try:
        state["current_node"] = "wait_for_core_approval"
        state["status_message"] = "Waiting for user to review campaign core..."

        await publish_progress(state)

        logger.info("Workflow paused - waiting for campaign core approval")

        add_audit_entry(
            state,
            "wait_for_core_approval",
            "Waiting for user campaign core approval",
            {"campaign_name": state["campaign_core"]["name"] if state["campaign_core"] else "N/A"},
            "success"
        )

    except Exception as e:
        error_msg = f"Error in core approval wait: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)

        add_audit_entry(
            state,
            "wait_for_core_approval",
            "Error in core approval wait",
            {"error": str(e)},
            "error"
        )

    return state
