"""
Scene Objective Assignment Generation Node
Phase 6.5: Create SceneObjectiveAssignment entries based on narrative blueprint
"""
import logging
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

from .state import CampaignWorkflowState, SceneObjectiveAssignment
from .utils import add_audit_entry, publish_progress, create_checkpoint

logger = logging.getLogger(__name__)


async def generate_scene_assignments_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate SceneObjectiveAssignment entries for each scene.

    This node:
    1. Reads scene metadata from narrative blueprint
    2. Links scenes to quest objectives they support
    3. Links scenes to campaign objectives (via quest objectives)
    4. Identifies what knowledge domains/item categories each scene should provide
    5. Creates SceneObjectiveAssignment for tracking and validation

    This runs AFTER scene generation and BEFORE element generation.
    """
    try:
        state["current_node"] = "generate_scene_assignments"
        state["current_phase"] = "scene_assignment"
        state["progress_percentage"] = 80
        state["step_progress"] = 0
        state["status_message"] = "Creating scene objective assignments..."

        await publish_progress(state)

        logger.info(f"Generating scene assignments for {len(state.get('scenes', []))} scenes")

        # Initialize if needed
        if "scene_objective_assignments" not in state or state["scene_objective_assignments"] is None:
            state["scene_objective_assignments"] = []

        # Build lookup maps
        objective_decomp_map = {}  # campaign_obj_id -> ObjectiveDecomposition
        for decomp in state.get("objective_decompositions", []):
            objective_decomp_map[decomp["campaign_objective_id"]] = decomp

        quest_obj_to_campaign_obj = {}  # quest_obj_id -> campaign_obj_id
        for decomp in state.get("objective_decompositions", []):
            for qobj in decomp["quest_objectives"]:
                quest_obj_to_campaign_obj[qobj["objective_id"]] = decomp["campaign_objective_id"]

        # Build scene lookup from narrative blueprint
        scene_metadata_map = {}  # scene_id -> narrative scene data
        narrative_blueprint = state.get("narrative_blueprint", {})
        for quest_chapter in narrative_blueprint.get("quests", []):
            for place in quest_chapter.get("places", []):
                for scene_plan in place.get("scenes", []):
                    # Find matching scene ID in state.scenes by name
                    scene_name = scene_plan.get("scene_name", "")
                    for scene in state.get("scenes", []):
                        if scene.get("name") == scene_name:
                            scene_metadata_map[scene["scene_id"]] = scene_plan
                            break

        state["step_progress"] = 20
        state["status_message"] = "Processing scene assignments..."
        await publish_progress(state)

        # Generate assignments
        assignments: List[SceneObjectiveAssignment] = []
        scenes = state.get("scenes", [])
        total_scenes = len(scenes)

        for scene_idx, scene in enumerate(scenes):
            # Update progress
            scene_progress = 20 + int((scene_idx / max(total_scenes, 1)) * 70)
            state["step_progress"] = scene_progress
            await publish_progress(state)

            scene_id = scene.get("scene_id")
            scene_name = scene.get("name", "Unknown Scene")

            # Get scene metadata from blueprint
            scene_metadata = scene_metadata_map.get(scene_id, {})

            # Get quest objectives this scene supports
            quest_objective_ids = scene_metadata.get("supports_quest_objectives", [])

            # Determine campaign objectives (via quest objectives)
            campaign_objective_ids = list(set([
                quest_obj_to_campaign_obj.get(qobj_id)
                for qobj_id in quest_objective_ids
                if qobj_id in quest_obj_to_campaign_obj
            ]))

            # Get knowledge domains and item categories from blueprint
            knowledge_domains = scene_metadata.get("provides_knowledge_domains", [])
            item_categories = scene_metadata.get("provides_item_categories", [])

            # Create assignment
            assignment: SceneObjectiveAssignment = {
                "scene_id": scene_id,
                "scene_name": scene_name,
                "advances_quest_objectives": quest_objective_ids,
                "advances_campaign_objectives": campaign_objective_ids,
                "provides_knowledge": [
                    {"domain": domain, "max_level": 3}  # Default to level 3
                    for domain in knowledge_domains
                ],
                "provides_items": [
                    {"category": category, "quantity": 1}  # Default quantity 1
                    for category in item_categories
                ],
                "acquisition_methods": [],  # Will be populated during element generation
                "is_required": scene_metadata.get("is_required_for_quest_completion", False),
                "is_redundant": False  # Will be determined during validation
            }

            assignments.append(assignment)

            logger.info(f"Scene '{scene_name}' assigned to {len(quest_objective_ids)} quest objectives, "
                       f"{len(knowledge_domains)} knowledge domains, {len(item_categories)} item categories")

        # Store assignments
        state["scene_objective_assignments"] = assignments

        # === UPDATE OBJECTIVE PROGRESS ===
        # Now that we know which scenes support which objectives, update ObjectiveProgress
        state["step_progress"] = 92
        state["status_message"] = "Updating objective progress tracking..."
        await publish_progress(state)

        # Build map of objective_id -> scenes that support it
        objective_to_scenes: Dict[str, List[str]] = defaultdict(list)
        for assignment in assignments:
            for qobj_id in assignment["advances_quest_objectives"]:
                objective_to_scenes[qobj_id].append(assignment["scene_id"])

        # Update objective_progress with supporting scenes
        for obj_progress in state.get("objective_progress", []):
            obj_id = obj_progress["objective_id"]
            if obj_id in objective_to_scenes:
                obj_progress["supporting_scenes"] = objective_to_scenes[obj_id]

        # Create checkpoint
        state["step_progress"] = 96
        state["status_message"] = "Finalizing scene assignments..."
        await publish_progress(state)

        create_checkpoint(state, "scene_assignments_created")

        state["step_progress"] = 100
        state["status_message"] = f"Created {len(assignments)} scene assignments"
        await publish_progress(state)

        # Calculate statistics
        total_quest_objectives_covered = len(set(
            qobj_id
            for assignment in assignments
            for qobj_id in assignment["advances_quest_objectives"]
        ))

        total_campaign_objectives_covered = len(set(
            cobj_id
            for assignment in assignments
            for cobj_id in assignment["advances_campaign_objectives"]
            if cobj_id is not None
        ))

        add_audit_entry(
            state,
            "generate_scene_assignments",
            "Generated scene objective assignments",
            {
                "num_scenes": len(scenes),
                "num_assignments": len(assignments),
                "quest_objectives_covered": total_quest_objectives_covered,
                "campaign_objectives_covered": total_campaign_objectives_covered,
                "assignments_by_scene": [
                    {
                        "scene": a["scene_name"],
                        "quest_objectives": len(a["advances_quest_objectives"]),
                        "knowledge_domains": [k["domain"] for k in a["provides_knowledge"]],
                        "item_categories": [i["category"] for i in a["provides_items"]]
                    }
                    for a in assignments[:5]  # First 5 for audit brevity
                ]
            },
            "success"
        )

        logger.info(f"Generated {len(assignments)} scene assignments covering "
                   f"{total_quest_objectives_covered} quest objectives and "
                   f"{total_campaign_objectives_covered} campaign objectives")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating scene assignments: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_scene_assignments",
            "Failed to generate scene assignments",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state
