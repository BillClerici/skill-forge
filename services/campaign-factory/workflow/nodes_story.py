"""
Campaign Story Generation Nodes
Phase 2: Generate story ideas and get user selection
"""
import os
import logging
import json
import uuid
from typing import List
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, StoryIdea
from .utils import add_audit_entry, publish_progress, create_checkpoint

logger = logging.getLogger(__name__)

# Initialize Claude client
# Note: API key is read from ANTHROPIC_API_KEY environment variable
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0.9,  # Higher creativity for story generation
    max_tokens=4096
)


async def generate_story_ideas_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate 3 creative story ideas based on world/region context

    This node:
    1. Fetches world/region context from MongoDB
    2. Uses Claude to generate 3 diverse story ideas
    3. Each idea includes title, summary, themes, length, difficulty
    4. Stores ideas in state for user selection
    """
    try:
        # Skip if story is already selected (resuming workflow)
        if state.get("selected_story_id") and state.get("story_ideas"):
            logger.info(f"Skipping story generation - story already selected: {state['selected_story_id']}")
            return state

        state["current_node"] = "generate_story_ideas"
        state["current_phase"] = "story_gen"
        state["progress_percentage"] = 10
        state["status_message"] = "Generating campaign story ideas..."

        await publish_progress(state)

        logger.info(f"Generating story ideas for world={state['world_name']}, region={state['region_name']}")

        # TODO: Fetch world and region data from MongoDB via MCP
        # For now, use placeholder context
        world_context = f"""
        World: {state['world_name']}
        Region: {state['region_name']}
        Genre: {state['genre']}
        """

        user_direction = ""
        if state.get("user_story_idea"):
            user_direction = f"\n\nUser's Story Direction: {state['user_story_idea']}"

        # Create prompt for story generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master storyteller and campaign designer for RPG games.

Your task is to generate 3 diverse, compelling campaign story ideas based on the provided world context.

Each story idea should:
- Be unique and different from the others in theme and approach
- Fit the world's genre and setting
- Have clear narrative potential for a multi-quest campaign
- Include interesting themes and conflicts
- Be appropriate for the specified difficulty level

Return your response as a JSON array with this structure:
[
  {{
    "title": "Engaging campaign title",
    "summary": "2-3 sentence summary of the story",
    "themes": ["theme1", "theme2", "theme3"],
    "estimated_length": "Short|Medium|Long",
    "difficulty_level": "Easy|Medium|Hard|Expert"
  }}
]

CRITICAL: Return ONLY the JSON array, no other text."""),
            ("user", "{context}{user_direction}\n\nGenerate 3 diverse campaign story ideas.")
        ])

        # Generate story ideas
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "context": world_context,
            "user_direction": user_direction
        })

        # Parse response
        story_ideas_raw = json.loads(response.content.strip())

        # Convert to StoryIdea format
        story_ideas: List[StoryIdea] = []
        for idx, idea in enumerate(story_ideas_raw):
            story_idea: StoryIdea = {
                "id": f"story_{uuid.uuid4().hex[:8]}",
                "title": idea.get("title", f"Story Idea {idx + 1}"),
                "summary": idea.get("summary", ""),
                "themes": idea.get("themes", []),
                "estimated_length": idea.get("estimated_length", "Medium"),
                "difficulty_level": idea.get("difficulty_level", "Medium")
            }
            story_ideas.append(story_idea)

        state["story_ideas"] = story_ideas

        add_audit_entry(
            state,
            "generate_story_ideas",
            "Generated story ideas",
            {
                "num_ideas": len(story_ideas),
                "regeneration_count": state["story_regeneration_count"],
                "ideas": [{"id": s["id"], "title": s["title"]} for s in story_ideas]
            },
            "success"
        )

        logger.info(f"Generated {len(story_ideas)} story ideas")

        # Clear errors and regeneration flag on success
        state["errors"] = []
        state["retry_count"] = 0
        state["regenerate_stories"] = False

    except Exception as e:
        error_msg = f"Error generating story ideas: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_story_ideas",
            "Failed to generate story ideas",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


async def wait_for_story_selection_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Wait for user to select a story idea

    This is a human-in-the-loop node that pauses workflow until:
    - User selects one of the generated story ideas
    - User requests regeneration of story ideas
    - User provides custom modifications

    In practice, this node sets state to indicate waiting, and the workflow
    is resumed via API call when user makes selection.
    """
    try:
        state["current_node"] = "wait_for_story_selection"
        state["status_message"] = "Waiting for user to select story idea..."

        await publish_progress(state)

        logger.info("Workflow paused - waiting for user story selection")

        add_audit_entry(
            state,
            "wait_for_story_selection",
            "Waiting for user story selection",
            {"num_story_options": len(state["story_ideas"])},
            "success"
        )

    except Exception as e:
        error_msg = f"Error in story selection wait: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)

        add_audit_entry(
            state,
            "wait_for_story_selection",
            "Error in story selection wait",
            {"error": str(e)},
            "error"
        )

    return state


async def handle_story_regeneration_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Handle user request to regenerate story ideas

    Increments regeneration counter and routes back to generation
    """
    try:
        state["current_node"] = "handle_story_regeneration"
        state["story_regeneration_count"] += 1
        state["status_message"] = f"Regenerating story ideas (attempt {state['story_regeneration_count']})..."

        await publish_progress(state)

        logger.info(f"Regenerating story ideas - attempt {state['story_regeneration_count']}")

        add_audit_entry(
            state,
            "handle_story_regeneration",
            "User requested story regeneration",
            {"regeneration_count": state["story_regeneration_count"]},
            "success"
        )

    except Exception as e:
        error_msg = f"Error handling story regeneration: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)

    return state
