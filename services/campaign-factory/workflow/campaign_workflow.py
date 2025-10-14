"""
Campaign Factory LangGraph Workflow
Complete orchestration of campaign generation with 22-step process
"""
import os
import logging
from langgraph.graph import StateGraph, END

from .state import CampaignWorkflowState
from .nodes_story import (
    generate_story_ideas_node,
    wait_for_story_selection_node,
    handle_story_regeneration_node
)
from .nodes_core import (
    generate_campaign_core_node,
    wait_for_core_approval_node
)
from .nodes_quest import generate_quests_node
from .nodes_place_scene import (
    generate_places_node,
    generate_scenes_node
)
from .nodes_elements import generate_scene_elements_node
from .nodes_finalize import finalize_campaign_node

logger = logging.getLogger(__name__)


def route_after_story_ideas(state: CampaignWorkflowState) -> str:
    """Route after story idea generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_story"

    # If a story is already selected, skip waiting and go directly to core generation
    if state.get("selected_story_id"):
        return "generate_core"

    return "wait_for_selection"


def route_after_story_selection(state: CampaignWorkflowState) -> str:
    """Route after user story selection"""
    if state.get("regenerate_stories", False):
        return "regenerate"
    if state.get("selected_story_id"):
        return "generate_core"
    return "wait_for_selection"


def route_after_core_generation(state: CampaignWorkflowState) -> str:
    """Route after campaign core generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_core"
    return "wait_for_approval"


def route_after_core_approval(state: CampaignWorkflowState) -> str:
    """Route after user approves campaign core"""
    if state.get("user_approved_core", False):
        # FIX: Check if workflow has already progressed past quest generation
        # This prevents restart from quest generation after finalization failures
        if state.get("quests") and len(state.get("quests", [])) > 0:
            # Quests already generated, skip to places or further
            if state.get("scenes") and len(state.get("scenes", [])) > 0:
                # Scenes generated, check if elements are done
                if state.get("npcs") or state.get("discoveries") or state.get("challenges"):
                    # Elements generated, go to finalize
                    return "finalize"
                else:
                    # Need to generate elements
                    return "generate_elements"
            elif state.get("places") and len(state.get("places", [])) > 0:
                # Places generated, need scenes
                return "generate_scenes"
            else:
                # Quests generated, need places
                return "generate_places"
        return "generate_quests"
    return "wait_for_approval"


def route_after_quests(state: CampaignWorkflowState) -> str:
    """Route after quest generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_quests"
    return "generate_places"


def route_after_places(state: CampaignWorkflowState) -> str:
    """Route after place generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_places"
    return "generate_scenes"


def route_after_scenes(state: CampaignWorkflowState) -> str:
    """Route after scene generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_scenes"
    return "generate_elements"


def route_after_elements(state: CampaignWorkflowState) -> str:
    """Route after scene element generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_elements"
    return "finalize"


def route_after_finalize(state: CampaignWorkflowState) -> str:
    """Route after finalization"""
    if state.get("errors", []):
        # FIX: Add retry logic for finalization instead of immediately failing
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "retry_finalize"
        return "failed"
    return "completed"


def create_campaign_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for campaign factory

    Workflow Phases:
    1. Story Generation - Generate 3 story ideas
    2. Story Selection - User selects or regenerates
    3. Campaign Core - Generate plot, storyline, objectives
    4. Core Approval - User approves or modifies
    5. Quest Generation - Generate quests with locations
    6. Place Generation - Generate Level 2 locations (places)
    7. Scene Generation - Generate Level 3 locations (scenes)
    8. Element Generation - Generate NPCs, discoveries, events, challenges
    9. Finalization - Validate and persist

    Human-in-the-loop gates:
    - Story selection (can regenerate)
    - Campaign core approval (can modify)
    """

    # Create workflow graph
    workflow = StateGraph(CampaignWorkflowState)

    # Add nodes
    workflow.add_node("generate_story_ideas", generate_story_ideas_node)
    workflow.add_node("wait_for_story_selection", wait_for_story_selection_node)
    workflow.add_node("handle_story_regeneration", handle_story_regeneration_node)
    workflow.add_node("generate_campaign_core", generate_campaign_core_node)
    workflow.add_node("wait_for_core_approval", wait_for_core_approval_node)
    workflow.add_node("generate_quests", generate_quests_node)
    workflow.add_node("generate_places", generate_places_node)
    workflow.add_node("generate_scenes", generate_scenes_node)
    workflow.add_node("generate_elements", generate_scene_elements_node)
    workflow.add_node("finalize", finalize_campaign_node)

    # Set entry point
    workflow.set_entry_point("generate_story_ideas")

    # Add conditional edges
    workflow.add_conditional_edges(
        "generate_story_ideas",
        route_after_story_ideas,
        {
            "wait_for_selection": "wait_for_story_selection",
            "generate_core": "generate_campaign_core",
            "retry_story": "generate_story_ideas",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "wait_for_story_selection",
        route_after_story_selection,
        {
            "regenerate": "handle_story_regeneration",
            "generate_core": "generate_campaign_core",
            "wait_for_selection": "wait_for_story_selection"
        }
    )

    workflow.add_edge("handle_story_regeneration", "generate_story_ideas")

    workflow.add_conditional_edges(
        "generate_campaign_core",
        route_after_core_generation,
        {
            "wait_for_approval": "wait_for_core_approval",
            "retry_core": "generate_campaign_core",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "wait_for_core_approval",
        route_after_core_approval,
        {
            "generate_quests": "generate_quests",
            "generate_places": "generate_places",
            "generate_scenes": "generate_scenes",
            "generate_elements": "generate_elements",
            "finalize": "finalize",
            "wait_for_approval": "wait_for_core_approval"
        }
    )

    workflow.add_conditional_edges(
        "generate_quests",
        route_after_quests,
        {
            "generate_places": "generate_places",
            "retry_quests": "generate_quests",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_places",
        route_after_places,
        {
            "generate_scenes": "generate_scenes",
            "retry_places": "generate_places",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_scenes",
        route_after_scenes,
        {
            "generate_elements": "generate_elements",
            "retry_scenes": "generate_scenes",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_elements",
        route_after_elements,
        {
            "finalize": "finalize",
            "retry_elements": "generate_elements",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "finalize",
        route_after_finalize,
        {
            "completed": END,
            "retry_finalize": "finalize",  # FIX: Add retry route for finalization
            "failed": END
        }
    )

    # Compile the workflow
    return workflow.compile()


# Export for use in main service
__all__ = ['create_campaign_workflow', 'CampaignWorkflowState']
