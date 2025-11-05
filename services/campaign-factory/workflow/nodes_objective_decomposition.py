"""
Objective Decomposition Node
Phase 3.5: Decompose campaign objectives into quest objectives
This creates the objective cascade framework before narrative planning
"""
import logging
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .state import (
    CampaignWorkflowState,
    ObjectiveDecomposition,
    ObjectiveProgress,
    CampaignObjective,
    QuestObjective
)
from .utils import add_audit_entry, publish_progress, create_checkpoint

logger = logging.getLogger(__name__)

# Pydantic models for structured output
class QuestObjectiveResponse(BaseModel):
    """Structured response for a single quest objective"""
    quest_number: int = Field(description="Quest number (1-based)")
    objective_id: str = Field(description="Unique identifier for this objective")
    description: str = Field(description="Specific, measurable quest objective")
    contribution: str = Field(description="How this advances the campaign objective")
    success_criteria: List[str] = Field(description="List of success criteria")
    required_knowledge_domains: List[str] = Field(default_factory=list, description="Knowledge domains needed")
    required_item_categories: List[str] = Field(default_factory=list, description="Item categories needed")
    blooms_level: int = Field(default=3, description="Bloom's taxonomy level (1-6)")
    is_required: bool = Field(default=True, description="Whether this objective is required")
    is_alternative_path: bool = Field(default=False, description="Whether this is an alternative path")

class ObjectiveDecompositionResponse(BaseModel):
    """Structured response for campaign objective decomposition"""
    campaign_objective_id: str = Field(description="ID of the campaign objective being decomposed")
    campaign_objective_description: str = Field(description="Description of the campaign objective")
    quest_objectives: List[QuestObjectiveResponse] = Field(description="List of quest-level sub-objectives")
    completion_criteria: List[str] = Field(description="Overall completion criteria for the campaign objective")
    minimum_quests_required: int = Field(default=1, description="Minimum number of quests required")

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0.7,  # Balanced creativity and structure
    max_tokens=4096
)


async def decompose_campaign_objectives_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Decompose each campaign objective into quest-level sub-objectives.

    This node:
    1. Takes each campaign primary objective
    2. Breaks it into 2-3 quest-level sub-objectives
    3. Distributes these across the planned number of quests
    4. Defines success criteria for each
    5. Identifies required knowledge domains and item categories
    6. Creates objective progress tracking structures

    This ensures that quest objectives explicitly support campaign objectives.
    """
    try:
        state["current_node"] = "decompose_campaign_objectives"
        state["current_phase"] = "objective_decomp"
        state["progress_percentage"] = 20
        state["step_progress"] = 0
        state["status_message"] = "Decomposing campaign objectives into quest objectives..."

        await publish_progress(state)

        logger.info(f"Decomposing {len(state['campaign_core']['primary_objectives'])} campaign objectives into quest objectives")

        # Initialize tracking lists if not exists
        if "objective_decompositions" not in state or state["objective_decompositions"] is None:
            state["objective_decompositions"] = []
        if "objective_progress" not in state or state["objective_progress"] is None:
            state["objective_progress"] = []
        if "campaign_objectives" not in state or state["campaign_objectives"] is None:
            state["campaign_objectives"] = []
        if "quest_objectives" not in state or state["quest_objectives"] is None:
            state["quest_objectives"] = []

        # Get campaign objectives
        campaign_objectives = state["campaign_core"]["primary_objectives"]
        num_quests = state["num_quests"]

        # Calculate optimal quest objectives per campaign objective
        # Target: 3-4 quest objectives per quest
        # Formula: Distribute evenly across campaign objectives
        target_quest_objectives = num_quests * 3.5  # 3-4 per quest
        quest_objs_per_campaign = max(1, round(target_quest_objectives / len(campaign_objectives)))

        # Ensure we don't go too high for small campaigns
        if num_quests <= 2:
            quest_objs_per_campaign = min(quest_objs_per_campaign, 2)
        elif num_quests <= 3:
            quest_objs_per_campaign = min(quest_objs_per_campaign, 2)
        else:
            quest_objs_per_campaign = min(quest_objs_per_campaign, 3)

        logger.info(f"Target: {target_quest_objectives:.1f} total quest objectives ({quest_objs_per_campaign} per campaign objective)")

        state["step_progress"] = 10
        state["status_message"] = "Analyzing campaign objective structure..."
        await publish_progress(state)

        # Create prompt for AI decomposition with dynamic objective count
        decomp_guidance = f"1-{quest_objs_per_campaign}" if quest_objs_per_campaign > 1 else "1"

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an expert in educational game design and objective decomposition.

Your task is to decompose a high-level campaign objective into specific quest-level sub-objectives.

DECOMPOSITION PRINCIPLES:
1. Each campaign objective should be supported by {decomp_guidance} quest-level sub-objectives (keep it minimal and focused)
2. Sub-objectives should be distributed across different quests (not all in one quest)
3. Each sub-objective should be SPECIFIC and MEASURABLE
4. Sub-objectives should build progressively (easier → harder)
5. Define CLEAR success criteria (what proves this is done?)
6. Identify required knowledge DOMAINS (not specific items, but categories like "ancient history", "combat tactics", "negotiation skills")
7. Identify required item CATEGORIES (not specific items, but types like "investigation tools", "combat equipment", "diplomatic gifts")

IMPORTANT: Create focused, essential objectives only. Quality over quantity.

OUTPUT FORMAT: Return valid JSON with fields: campaign_objective_id, campaign_objective_description, quest_objectives (array), completion_criteria (array), minimum_quests_required.
Each quest_objective must have: quest_number (integer), objective_id (string), description (string), contribution (string), success_criteria (array of strings), required_knowledge_domains (array of strings), required_item_categories (array of strings), blooms_level (INTEGER 1-6, NOT text), is_required (boolean), is_alternative_path (boolean).

CRITICAL: blooms_level MUST be an integer number from 1 to 6, NOT a text description like "Remember" or "Apply"."""),
            ("user", """Campaign Context:
Name: {campaign_name}
Plot: {plot}
Number of Quests: {num_quests}
Target Bloom's Level: {blooms_level}

Campaign Objective to Decompose:
Description: {objective_description}
Bloom's Level: {objective_blooms}

Decompose this campaign objective into {decomp_guidance} quest-level sub-objectives distributed across the {num_quests} quests.
Focus on creating ESSENTIAL objectives only - be selective and avoid redundancy.

Return ONLY the JSON object, no markdown formatting.""")
        ])

        # Create chain for AI invocation with structured output
        structured_llm = anthropic_client.with_structured_output(ObjectiveDecompositionResponse, include_raw=False)
        chain = prompt | structured_llm

        decompositions: List[ObjectiveDecomposition] = []
        progress_tracking: List[ObjectiveProgress] = []
        campaign_obj_list: List[CampaignObjective] = []
        quest_obj_list: List[QuestObjective] = []

        total_objectives = len(campaign_objectives)
        for obj_idx, campaign_obj in enumerate(campaign_objectives):
            # Update step progress for each objective (10% to 80% range)
            obj_step_progress = 10 + int((obj_idx / total_objectives) * 70)
            state["step_progress"] = obj_step_progress
            state["status_message"] = f"Decomposing objective {obj_idx + 1} of {total_objectives}..."
            await publish_progress(state)

            # Generate objective ID if not exists
            campaign_obj_id = campaign_obj.get("objective_id", f"campaign_obj_{uuid.uuid4().hex[:8]}")
            campaign_obj["objective_id"] = campaign_obj_id

            # Call AI to decompose with guaranteed structured output
            decomp_response: ObjectiveDecompositionResponse = await chain.ainvoke({
                "campaign_name": state["campaign_core"]["name"],
                "plot": state["campaign_core"]["plot"],
                "num_quests": num_quests,
                "blooms_level": state["campaign_core"]["target_blooms_level"],
                "objective_description": campaign_obj["description"],
                "objective_blooms": campaign_obj.get("blooms_level", 3),
                "decomp_guidance": decomp_guidance
            })

            # Convert Pydantic model to dict for processing
            decomp_data = decomp_response.model_dump()

            # Create ObjectiveDecomposition
            decomposition: ObjectiveDecomposition = {
                "campaign_objective_id": campaign_obj_id,
                "campaign_objective_description": campaign_obj["description"],
                "quest_objectives": decomp_data.get("quest_objectives", []),
                "total_knowledge_required": list(set(
                    domain
                    for qobj in decomp_data.get("quest_objectives", [])
                    for domain in qobj.get("required_knowledge_domains", [])
                )),
                "total_items_required": list(set(
                    category
                    for qobj in decomp_data.get("quest_objectives", [])
                    for category in qobj.get("required_item_categories", [])
                )),
                "completion_criteria": decomp_data.get("completion_criteria", []),
                "minimum_quests_required": decomp_data.get("minimum_quests_required", 1),
                "created_at": datetime.utcnow().isoformat()
            }

            decompositions.append(decomposition)

            # Create CampaignObjective instance
            campaign_objective: CampaignObjective = {
                "objective_id": campaign_obj_id,
                "campaign_id": state["campaign_core"].get("campaign_id", ""),
                "description": campaign_obj["description"],
                "bloom_level": campaign_obj.get("blooms_level", 3),
                "status": "not_started",
                "completion_type": "threshold",  # Default: most quest objectives must be done
                "required_quest_count": decomposition["minimum_quests_required"],
                "narrative_significance": decomposition.get("completion_criteria", [""])[0] if decomposition.get("completion_criteria") else "",
                "reward": {
                    "experience": 500,
                    "narrative_unlock": f"Major progress in: {campaign_obj['description']}"
                }
            }
            campaign_obj_list.append(campaign_objective)

            # Create ObjectiveProgress for campaign objective
            campaign_progress: ObjectiveProgress = {
                "objective_id": campaign_obj_id,
                "level": "campaign",
                "parent_id": None,
                "description": campaign_obj["description"],
                "blooms_level": campaign_obj.get("blooms_level", 3),
                "status": "not_started",
                "completion_percentage": 0.0,
                "success_criteria": decomposition["completion_criteria"],
                "supporting_quest_objectives": [
                    qobj["objective_id"] for qobj in decomposition["quest_objectives"]
                ],
                "supporting_scenes": [],  # Will be populated later
                "required_knowledge": [],  # Will be populated from quest objectives
                "required_items": [],  # Will be populated from quest objectives
                "knowledge_acquired": [],
                "items_acquired": [],
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": None
            }

            progress_tracking.append(campaign_progress)

            # Create ObjectiveProgress for each quest objective
            for qobj in decomposition["quest_objectives"]:
                # Create QuestObjective instance
                quest_objective: QuestObjective = {
                    "objective_id": qobj["objective_id"],
                    "quest_id": f"quest_{qobj['quest_number']}",  # Placeholder, will be updated
                    "quest_number": qobj["quest_number"],
                    "campaign_objective_ids": [campaign_obj_id],
                    "description": qobj["description"],
                    "bloom_level": qobj.get("blooms_level", 3),
                    "required_knowledge": [],  # Will be populated during scene/element generation
                    "required_items": [],  # Will be populated during scene/element generation
                    "completion_type": "all",  # Default: all child objectives must be done
                    "required_threshold": None,
                    "status": "not_started"
                }
                quest_obj_list.append(quest_objective)

                quest_progress: ObjectiveProgress = {
                    "objective_id": qobj["objective_id"],
                    "level": "quest",
                    "parent_id": campaign_obj_id,  # Link to campaign objective
                    "description": qobj["description"],
                    "blooms_level": qobj.get("blooms_level", 3),
                    "status": "not_started",
                    "completion_percentage": 0.0,
                    "success_criteria": qobj.get("success_criteria", []),
                    "supporting_quest_objectives": [],  # N/A for quest-level
                    "supporting_scenes": [],  # Will be populated later
                    "required_knowledge": [],  # Will be populated in quest generation
                    "required_items": [],  # Will be populated in quest generation
                    "knowledge_acquired": [],
                    "items_acquired": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "last_updated": None
                }

                progress_tracking.append(quest_progress)

            logger.info(f"Decomposed campaign objective '{campaign_obj['description']}' into {len(decomposition['quest_objectives'])} quest objectives")

        # Store in state
        state["objective_decompositions"] = decompositions
        state["objective_progress"] = progress_tracking
        state["campaign_objectives"] = campaign_obj_list
        state["quest_objectives"] = quest_obj_list

        # Calculate total quest objectives created
        total_quest_objectives = sum(len(d["quest_objectives"]) for d in decompositions)

        # Create checkpoint
        state["step_progress"] = 90
        state["status_message"] = "Finalizing objective decomposition..."
        await publish_progress(state)

        create_checkpoint(state, "objectives_decomposed")

        state["step_progress"] = 100
        state["status_message"] = f"Decomposed {len(campaign_objectives)} campaign objectives into {total_quest_objectives} quest objectives"
        await publish_progress(state)

        add_audit_entry(
            state,
            "decompose_campaign_objectives",
            "Decomposed campaign objectives into quest objectives",
            {
                "num_campaign_objectives": len(campaign_objectives),
                "num_quest_objectives": total_quest_objectives,
                "decompositions": [
                    {
                        "campaign_obj": d["campaign_objective_description"],
                        "quest_objs": [qo["description"] for qo in d["quest_objectives"]],
                        "knowledge_domains": d["total_knowledge_required"],
                        "item_categories": d["total_items_required"]
                    }
                    for d in decompositions
                ]
            },
            "success"
        )

        logger.info(f"Objective decomposition complete: {len(decompositions)} decompositions, {total_quest_objectives} quest objectives")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error decomposing campaign objectives: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "decompose_campaign_objectives",
            "Failed to decompose campaign objectives",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state
