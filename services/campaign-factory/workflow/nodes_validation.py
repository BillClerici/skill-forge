"""
Objective Cascade Validation Node
Phase 9: Validate the complete objective cascade and suggest auto-fixes
"""
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict

from .state import CampaignWorkflowState, ValidationReport
from .utils import add_audit_entry, publish_progress, create_checkpoint

logger = logging.getLogger(__name__)


async def validate_objective_cascade_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Comprehensive validation of the objective cascade.

    Validates:
    1. Campaign objectives → Quest objectives linkage
    2. Quest objectives → Scene assignments
    3. Scene encounters → Knowledge/Item provision
    4. Redundancy requirements (2-3 paths to same objective)
    5. Completion criteria achievability

    Creates ValidationReport with errors, warnings, and auto-fix suggestions.
    """
    try:
        state["current_node"] = "validate_objective_cascade"
        state["current_phase"] = "validation"
        state["progress_percentage"] = 98
        state["step_progress"] = 0
        state["status_message"] = "Validating objective cascade..."

        await publish_progress(state)

        logger.info("Starting objective cascade validation")

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        auto_fix_suggestions: List[Dict[str, Any]] = []
        stats: Dict[str, Any] = {}

        # === VALIDATION 1: Campaign → Quest Objective Coverage ===
        state["step_progress"] = 10
        state["status_message"] = "Validating campaign → quest objective linkage..."
        await publish_progress(state)

        campaign_obj_coverage = await _validate_campaign_quest_linkage(state, errors, warnings)
        stats["campaign_objective_coverage"] = campaign_obj_coverage

        # === VALIDATION 2: Quest Objectives → Scene Assignments ===
        state["step_progress"] = 25
        state["status_message"] = "Validating quest → scene assignments..."
        await publish_progress(state)

        scene_coverage = await _validate_quest_scene_linkage(state, errors, warnings)
        stats["scene_coverage"] = scene_coverage

        # === VALIDATION 3: Scene Encounters → Knowledge/Items ===
        state["step_progress"] = 40
        state["status_message"] = "Validating scene → knowledge/item provision..."
        await publish_progress(state)

        knowledge_item_coverage = await _validate_knowledge_item_provision(state, errors, warnings)
        stats["knowledge_item_coverage"] = knowledge_item_coverage

        # === VALIDATION 4: Redundancy Check ===
        state["step_progress"] = 55
        state["status_message"] = "Checking redundancy requirements..."
        await publish_progress(state)

        redundancy_stats = await _validate_redundancy(state, errors, warnings)
        stats["redundancy"] = redundancy_stats

        # === VALIDATION 5: Completion Criteria ===
        state["step_progress"] = 70
        state["status_message"] = "Validating completion criteria..."
        await publish_progress(state)

        completion_stats = await _validate_completion_criteria(state, errors, warnings)
        stats["completion_criteria"] = completion_stats

        # === AUTO-FIX SUGGESTIONS ===
        state["step_progress"] = 85
        state["status_message"] = "Generating auto-fix suggestions..."
        await publish_progress(state)

        auto_fix_suggestions = await _generate_auto_fix_suggestions(state, errors, warnings)

        # === CREATE VALIDATION REPORT ===
        state["step_progress"] = 95
        state["status_message"] = "Creating validation report..."
        await publish_progress(state)

        validation_passed = len(errors) == 0

        # Create display-friendly stats with both key and display_name
        stats_display = []
        stat_display_names = {
            "campaign_objective_coverage": "Campaign Objective Coverage",
            "scene_coverage": "Scene Coverage",
            "knowledge_item_coverage": "Knowledge & Item Coverage",
            "total_critical_knowledge": "Total Critical Knowledge",
            "knowledge_with_redundancy": "Knowledge With Redundancy",
            "knowledge_single_path": "Knowledge Single Path",
            "total_critical_items": "Total Critical Items",
            "items_with_redundancy": "Items With Redundancy",
            "items_single_path": "Items Single Path",
            "campaign_objectives_with_criteria": "Campaign Objectives With Criteria",
            "campaign_objectives_without_criteria": "Campaign Objectives Without Criteria",
            "quest_objectives_with_criteria": "Quest Objectives With Criteria",
            "quest_objectives_without_criteria": "Quest Objectives Without Criteria"
        }

        # Flatten nested stats and add display names
        def flatten_stats(stats_dict, prefix=""):
            for key, value in stats_dict.items():
                full_key = f"{prefix}{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_stats(value, f"{full_key}_")
                else:
                    display_name = stat_display_names.get(full_key, full_key.replace("_", " ").title())
                    stats_display.append({
                        "key": full_key,
                        "display_name": display_name,
                        "value": value
                    })

        flatten_stats(stats)

        validation_report: ValidationReport = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "validation_passed": validation_passed,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,  # Keep raw stats for backward compatibility
            "stats_display": stats_display,  # New display-friendly format
            "auto_fix_suggestions": auto_fix_suggestions
        }

        state["validation_report"] = validation_report

        # Log summary
        logger.info(f"Validation {'PASSED' if validation_passed else 'FAILED'}: "
                   f"{len(errors)} errors, {len(warnings)} warnings, "
                   f"{len(auto_fix_suggestions)} auto-fix suggestions")

        # Create checkpoint
        create_checkpoint(state, "cascade_validated")

        state["step_progress"] = 100
        state["status_message"] = f"Validation complete: {len(errors)} errors, {len(warnings)} warnings"
        await publish_progress(state)

        add_audit_entry(
            state,
            "validate_objective_cascade",
            "Validated objective cascade",
            {
                "validation_passed": validation_passed,
                "num_errors": len(errors),
                "num_warnings": len(warnings),
                "num_auto_fix_suggestions": len(auto_fix_suggestions),
                "stats": stats
            },
            "success" if validation_passed else "warning"
        )

        # Add warnings to state if validation failed
        if not validation_passed:
            for error in errors:
                state["warnings"].append(f"Validation error: {error['message']}")

    except Exception as e:
        error_msg = f"Error during cascade validation: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "validate_objective_cascade",
            "Failed to validate cascade",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


async def _validate_campaign_quest_linkage(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate that campaign objectives are properly supported by quest objectives."""
    coverage = {
        "total_campaign_objectives": 0,
        "fully_covered": 0,
        "partially_covered": 0,
        "uncovered": 0
    }

    decompositions = state.get("objective_decompositions", [])
    coverage["total_campaign_objectives"] = len(decompositions)

    for decomp in decompositions:
        campaign_obj_id = decomp["campaign_objective_id"]
        quest_objectives = decomp["quest_objectives"]

        # Check if quest objectives exist in the quest data
        quest_ids_with_objectives = set()
        for qobj in quest_objectives:
            quest_num = qobj.get("quest_number")
            if quest_num and 1 <= quest_num <= len(state.get("quests", [])):
                quest_ids_with_objectives.add(quest_num)

        # Determine coverage
        min_required = decomp.get("minimum_quests_required", 1)
        if len(quest_ids_with_objectives) >= min_required:
            coverage["fully_covered"] += 1
        elif len(quest_ids_with_objectives) > 0:
            coverage["partially_covered"] += 1
            warnings.append({
                "type": "weak_campaign_quest_link",
                "severity": "medium",
                "message": f"Campaign objective '{decomp['campaign_objective_description']}' is only supported by {len(quest_ids_with_objectives)} quests (requires {min_required})",
                "affected_ids": [campaign_obj_id],
                "recommendations": [f"Add support in {min_required - len(quest_ids_with_objectives)} more quests"]
            })
        else:
            coverage["uncovered"] += 1
            errors.append({
                "type": "missing_campaign_quest_link",
                "severity": "critical",
                "message": f"Campaign objective '{decomp['campaign_objective_description']}' has no supporting quest objectives",
                "affected_ids": [campaign_obj_id],
                "recommendations": ["Create quest objectives that support this campaign objective"]
            })

    return coverage


async def _validate_quest_scene_linkage(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate that quest objectives are addressable in scenes."""
    coverage = {
        "total_quest_objectives": 0,
        "objectives_in_multiple_scenes": 0,
        "objectives_in_single_scene": 0,
        "objectives_in_no_scenes": 0
    }

    # Build map of objective_id -> scenes that support it
    objective_to_scenes: Dict[str, Set[str]] = defaultdict(set)

    for scene_assignment in state.get("scene_objective_assignments", []):
        scene_id = scene_assignment["scene_id"]
        for qobj_id in scene_assignment.get("advances_quest_objectives", []):
            objective_to_scenes[qobj_id].add(scene_id)

    # Check all quest objectives from decompositions
    for decomp in state.get("objective_decompositions", []):
        for qobj in decomp["quest_objectives"]:
            qobj_id = qobj["objective_id"]
            coverage["total_quest_objectives"] += 1

            num_scenes = len(objective_to_scenes[qobj_id])

            if num_scenes >= 2:
                coverage["objectives_in_multiple_scenes"] += 1
            elif num_scenes == 1:
                coverage["objectives_in_single_scene"] += 1
                warnings.append({
                    "type": "single_scene_objective",
                    "severity": "medium",
                    "message": f"Quest objective '{qobj['description']}' is only addressable in 1 scene (redundancy requirement: 2+)",
                    "affected_ids": [qobj_id],
                    "recommendations": ["Add support for this objective in at least 1 more scene"]
                })
            else:
                coverage["objectives_in_no_scenes"] += 1
                errors.append({
                    "type": "objective_not_in_scenes",
                    "severity": "critical",
                    "message": f"Quest objective '{qobj['description']}' is not addressable in any scene",
                    "affected_ids": [qobj_id],
                    "recommendations": ["Create scenes that allow player to achieve this objective"]
                })

    return coverage


async def _validate_knowledge_item_provision(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate that required knowledge/items are actually provided in scenes."""
    coverage = {
        "total_knowledge": 0,
        "knowledge_with_acquisition": 0,
        "knowledge_without_acquisition": 0,
        "total_items": 0,
        "items_with_acquisition": 0,
        "items_without_acquisition": 0
    }

    # Check knowledge entities
    for knowledge in state.get("knowledge_entities", []):
        coverage["total_knowledge"] += 1
        kg_name = knowledge.get("name", "Unknown")
        kg_id = knowledge.get("knowledge_id")

        # Check if this knowledge has acquisition methods
        acquisition_methods = knowledge.get("acquisition_methods", [])
        if len(acquisition_methods) > 0:
            coverage["knowledge_with_acquisition"] += 1
        else:
            coverage["knowledge_without_acquisition"] += 1
            errors.append({
                "type": "knowledge_no_acquisition",
                "severity": "critical",
                "message": f"Knowledge '{kg_name}' has no acquisition methods defined",
                "affected_ids": [kg_id] if kg_id else [],
                "recommendations": ["Add NPCs, discoveries, challenges, or events that provide this knowledge"]
            })

    # Check item entities
    for item in state.get("item_entities", []):
        coverage["total_items"] += 1
        item_name = item.get("name", "Unknown")
        item_id = item.get("item_id")

        # Check if this item has acquisition methods
        acquisition_methods = item.get("acquisition_methods", [])
        if len(acquisition_methods) > 0:
            coverage["items_with_acquisition"] += 1
        else:
            coverage["items_without_acquisition"] += 1
            errors.append({
                "type": "item_no_acquisition",
                "severity": "critical",
                "message": f"Item '{item_name}' has no acquisition methods defined",
                "affected_ids": [item_id] if item_id else [],
                "recommendations": ["Add NPCs, discoveries, challenges, or events that provide this item"]
            })

    return coverage


async def _validate_redundancy(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate redundancy requirements (2-3 paths to objectives)."""
    stats = {
        "total_critical_knowledge": 0,
        "knowledge_with_redundancy": 0,
        "knowledge_single_path": 0,
        "total_critical_items": 0,
        "items_with_redundancy": 0,
        "items_single_path": 0
    }

    # Check critical knowledge (quest-critical)
    for knowledge in state.get("knowledge_entities", []):
        supports_objectives = knowledge.get("supports_objectives", [])
        if len(supports_objectives) > 0:
            stats["total_critical_knowledge"] += 1
            kg_name = knowledge.get("name", "Unknown")

            acquisition_count = len(knowledge.get("acquisition_methods", []))
            if acquisition_count >= 2:
                stats["knowledge_with_redundancy"] += 1
            elif acquisition_count == 1:
                stats["knowledge_single_path"] += 1
                warnings.append({
                    "type": "single_path_knowledge",
                    "severity": "medium",
                    "message": f"Quest-critical knowledge '{kg_name}' has only 1 acquisition path (recommended: 2-3)",
                    "affected_ids": [knowledge.get("knowledge_id")],
                    "recommendations": ["Add alternative ways to acquire this knowledge"]
                })

    # Check critical items (quest-critical)
    for item in state.get("item_entities", []):
        if item.get("is_quest_critical", False):
            stats["total_critical_items"] += 1
            item_name = item.get("name", "Unknown")

            acquisition_count = len(item.get("acquisition_methods", []))
            if acquisition_count >= 2:
                stats["items_with_redundancy"] += 1
            elif acquisition_count == 1:
                stats["items_single_path"] += 1
                warnings.append({
                    "type": "single_path_item",
                    "severity": "medium",
                    "message": f"Quest-critical item '{item_name}' has only 1 acquisition path (recommended: 2-3)",
                    "affected_ids": [item.get("item_id")],
                    "recommendations": ["Add alternative ways to acquire this item"]
                })

    return stats


async def _validate_completion_criteria(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate that completion criteria are well-defined and achievable."""
    stats = {
        "campaign_objectives_with_criteria": 0,
        "campaign_objectives_without_criteria": 0,
        "quest_objectives_with_criteria": 0,
        "quest_objectives_without_criteria": 0
    }

    # Check campaign objectives
    for decomp in state.get("objective_decompositions", []):
        criteria = decomp.get("completion_criteria", [])
        if len(criteria) > 0:
            stats["campaign_objectives_with_criteria"] += 1
        else:
            stats["campaign_objectives_without_criteria"] += 1
            warnings.append({
                "type": "missing_completion_criteria",
                "severity": "low",
                "message": f"Campaign objective '{decomp['campaign_objective_description']}' has no explicit completion criteria",
                "affected_ids": [decomp["campaign_objective_id"]],
                "recommendations": ["Define measurable success criteria for this objective"]
            })

        # Check quest objectives within this decomposition
        for qobj in decomp["quest_objectives"]:
            criteria = qobj.get("success_criteria", [])
            if len(criteria) > 0:
                stats["quest_objectives_with_criteria"] += 1
            else:
                stats["quest_objectives_without_criteria"] += 1
                warnings.append({
                    "type": "missing_quest_criteria",
                    "severity": "low",
                    "message": f"Quest objective '{qobj['description']}' has no explicit success criteria",
                    "affected_ids": [qobj["objective_id"]],
                    "recommendations": ["Define measurable success criteria for this objective"]
                })

    return stats


async def _generate_auto_fix_suggestions(
    state: CampaignWorkflowState,
    errors: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Generate actionable auto-fix suggestions based on validation results."""
    suggestions = []

    # For missing knowledge acquisition methods
    for error in errors:
        if error["type"] == "knowledge_no_acquisition":
            suggestions.append({
                "action": "add_knowledge_acquisition",
                "priority": "high",
                "description": error["message"],
                "suggested_fix": "Add an NPC conversation or discovery that provides this knowledge",
                "affected_ids": error["affected_ids"]
            })

        elif error["type"] == "item_no_acquisition":
            suggestions.append({
                "action": "add_item_acquisition",
                "priority": "high",
                "description": error["message"],
                "suggested_fix": "Add an NPC, discovery, or challenge that provides this item",
                "affected_ids": error["affected_ids"]
            })

        elif error["type"] == "objective_not_in_scenes":
            suggestions.append({
                "action": "add_scene_for_objective",
                "priority": "critical",
                "description": error["message"],
                "suggested_fix": "Create a scene where player can work toward this objective",
                "affected_ids": error["affected_ids"]
            })

    # For single-path warnings
    for warning in warnings:
        if warning["type"] in ["single_path_knowledge", "single_path_item"]:
            suggestions.append({
                "action": "add_redundant_path",
                "priority": "medium",
                "description": warning["message"],
                "suggested_fix": "Add an alternative acquisition method in a different scene",
                "affected_ids": warning["affected_ids"]
            })

    return suggestions


async def apply_auto_fixes_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Optional node: Apply auto-fixes from validation report.

    This node would automatically fix common issues like:
    - Adding redundant acquisition paths
    - Creating missing encounters for knowledge/items
    - Adjusting scene assignments

    This is a placeholder for future implementation.
    """
    try:
        state["current_node"] = "apply_auto_fixes"
        state["status_message"] = "Auto-fixes not implemented yet - manual review required"

        logger.info("Auto-fix application is not yet implemented")

        # Future implementation would apply fixes from validation_report["auto_fix_suggestions"]

    except Exception as e:
        logger.error(f"Error in auto-fix node: {str(e)}")

    return state
