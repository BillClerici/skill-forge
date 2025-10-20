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
from .nodes_objective_decomposition import decompose_campaign_objectives_node
from .nodes_narrative_planner import plan_campaign_narrative
from .nodes_quest import generate_quests_node
from .nodes_place_scene import (
    generate_places_node,
    generate_scenes_node
)
from .nodes_scene_assignments import generate_scene_assignments_node
from .nodes_elements import generate_scene_elements_node
from .nodes_validation import validate_objective_cascade_node
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
                    # Elements generated, check if validation is done
                    if state.get("validation_report"):
                        # Validation done, go to finalize
                        return "finalize"
                    else:
                        # Need validation
                        return "validate_cascade"
                else:
                    # Need to generate elements
                    return "generate_elements"
            elif state.get("places") and len(state.get("places", [])) > 0:
                # Places generated, need scenes
                return "generate_scenes"
            else:
                # Quests generated, need places
                return "generate_places"
        # NEW: Go to objective decomposition first
        return "decompose_objectives"
    return "wait_for_approval"


def route_after_narrative_planning(state: CampaignWorkflowState) -> str:
    """Route after narrative planning"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_narrative"
    return "generate_quests"


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


def route_after_objective_decomposition(state: CampaignWorkflowState) -> str:
    """Route after objective decomposition"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_decomp"
    return "plan_narrative"


def route_after_scenes(state: CampaignWorkflowState) -> str:
    """Route after scene generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_scenes"
    return "generate_scene_assignments"


def route_after_scene_assignments(state: CampaignWorkflowState) -> str:
    """Route after scene objective assignments"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_assignments"
    return "generate_elements"


def route_after_elements(state: CampaignWorkflowState) -> str:
    """Route after scene element generation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_elements"
    return "validate_cascade"


def route_after_validation(state: CampaignWorkflowState) -> str:
    """Route after objective cascade validation"""
    if state.get("errors", []):
        return "failed" if state.get("retry_count", 0) >= state.get("max_retries", 3) else "retry_validation"

    # Check if validation passed
    validation_report = state.get("validation_report", {})
    if validation_report.get("validation_passed", False):
        return "finalize"
    else:
        # Validation failed - for now, warn and continue to finalization
        # In future, could route to auto-fix node here
        logger.warning("Objective cascade validation failed but continuing to finalization")
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
    5. Objective Decomposition - Decompose campaign objectives into quest objectives (NEW)
    6. Narrative Planning - Plan entire campaign story arc with objective awareness (NEW)
    7. Quest Generation - Generate quests from narrative blueprint
    8. Place Generation - Generate Level 2 locations (places)
    9. Scene Generation - Generate Level 3 locations (scenes)
    10. Scene Assignment - Link scenes to objectives (NEW)
    11. Element Generation - Generate NPCs, discoveries, events, challenges
    12. Cascade Validation - Validate objective cascade (NEW)
    13. Finalization - Persist to databases

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
    workflow.add_node("decompose_objectives", decompose_campaign_objectives_node)  # NEW: Objective decomposition
    workflow.add_node("plan_narrative", plan_campaign_narrative)  # NEW: Objective-aware narrative planning
    workflow.add_node("generate_quests", generate_quests_node)
    workflow.add_node("generate_places", generate_places_node)
    workflow.add_node("generate_scenes", generate_scenes_node)
    workflow.add_node("generate_scene_assignments", generate_scene_assignments_node)  # NEW: Scene-objective linking
    workflow.add_node("generate_elements", generate_scene_elements_node)
    workflow.add_node("validate_cascade", validate_objective_cascade_node)  # NEW: Cascade validation
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
            "wait_for_selection": END  # FIX: End workflow instead of looping
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
            "decompose_objectives": "decompose_objectives",  # NEW: Route to objective decomposition
            "generate_quests": "generate_quests",
            "generate_places": "generate_places",
            "generate_scenes": "generate_scenes",
            "generate_elements": "generate_elements",
            "validate_cascade": "validate_cascade",
            "finalize": "finalize",
            "wait_for_approval": END  # FIX: End workflow instead of looping
        }
    )

    workflow.add_conditional_edges(
        "decompose_objectives",
        route_after_objective_decomposition,
        {
            "plan_narrative": "plan_narrative",
            "retry_decomp": "decompose_objectives",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "plan_narrative",
        route_after_narrative_planning,
        {
            "generate_quests": "generate_quests",
            "retry_narrative": "plan_narrative",
            "failed": END
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
            "generate_scene_assignments": "generate_scene_assignments",
            "retry_scenes": "generate_scenes",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_scene_assignments",
        route_after_scene_assignments,
        {
            "generate_elements": "generate_elements",
            "retry_assignments": "generate_scene_assignments",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_elements",
        route_after_elements,
        {
            "validate_cascade": "validate_cascade",
            "retry_elements": "generate_elements",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "validate_cascade",
        route_after_validation,
        {
            "finalize": "finalize",
            "retry_validation": "validate_cascade",
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
    # Note: recursion_limit is set at invocation time in main.py
    return workflow.compile()


# Export for use in main service
__all__ = ['create_campaign_workflow', 'CampaignWorkflowState']
