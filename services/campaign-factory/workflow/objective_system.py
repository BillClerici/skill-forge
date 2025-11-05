"""
Objective Linking System for Campaign Factory
Connects campaign objectives -> quest objectives -> knowledge/items -> scenes

Phase 2: Objective decomposition and resource mapping
"""
import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .state import (
    CampaignWorkflowState,
    QuestData,
    QuestObjective,
    KnowledgeData,
    ItemData,
    SceneData
)
from .utils import extract_json_from_llm_response

logger = logging.getLogger(__name__)

# Pydantic models for structured output
class KnowledgeRequirement(BaseModel):
    """Knowledge requirement for an objective"""
    knowledge_name: str = Field(description="Name of required knowledge")
    knowledge_description: str = Field(description="What this knowledge entails")
    min_level: int = Field(description="Minimum level required (1-4)", ge=1, le=4)
    knowledge_type: str = Field(description="Type: skill, lore, clue, secret, technique, or insight")
    primary_dimension: str = Field(description="Dimension: physical, emotional, intellectual, social, spiritual, vocational, or environmental")

class ItemRequirement(BaseModel):
    """Item requirement for an objective"""
    item_name: str = Field(description="Name of required item")
    item_description: str = Field(description="What this item is")
    quantity: int = Field(description="Quantity required", ge=1)
    item_type: str = Field(description="Type: tool, consumable, key_item, quest_item, equipment, or resource")

class QuestObjectiveResponse(BaseModel):
    """Structured response for a quest objective"""
    objective_id: str = Field(description="Unique identifier")
    description: str = Field(description="Objective description")
    required_knowledge: List[KnowledgeRequirement] = Field(default_factory=list, description="Knowledge requirements")
    required_items: List[ItemRequirement] = Field(default_factory=list, description="Item requirements")
    supports_campaign_objective: str = Field(description="Campaign objective this supports")

class QuestObjectivesResponse(BaseModel):
    """Structured response containing all quest objectives"""
    objectives: List[QuestObjectiveResponse] = Field(description="List of quest objectives")

class PartialLevel(BaseModel):
    """Partial mastery level for knowledge"""
    level: int = Field(description="Level number (1-4)", ge=1, le=4)
    description: str = Field(description="What the player knows at this level")
    sufficient_for: List[str] = Field(default_factory=list, description="Objective IDs this level satisfies")

class PartialLevelsResponse(BaseModel):
    """Structured response for partial knowledge levels"""
    partial_levels: List[PartialLevel] = Field(description="4 progressive levels", min_length=4, max_length=4)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0.7,
    max_tokens=4096
)


async def generate_quest_objectives(
    quest: QuestData,
    campaign_objectives: List[Dict[str, Any]],
    state: CampaignWorkflowState
) -> List[QuestObjective]:
    """
    Generate structured quest objectives that support campaign objectives.

    For each objective, determines:
    - What knowledge is required (and at what level)
    - What items are required (and in what quantities)
    - How it connects to campaign-level objectives

    Args:
        quest: Quest to generate objectives for
        campaign_objectives: Campaign's primary objectives
        state: Full campaign workflow state

    Returns:
        List of QuestObjective with knowledge/item requirements
    """
    try:
        logger.info(f"Generating structured objectives for quest: {quest['name']}")

        # Create prompt for AI to decompose objectives into requirements
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in educational game design and learning objective decomposition.

Your task is to take high-level quest objectives and break them down into specific KNOWLEDGE and ITEMS that a player would need to complete them.

For example:
- Objective: "Discover the source of contamination in the mine"
  Might require:
  - Knowledge: "Mining Safety Protocols" (Level 2 - 50% understanding)
  - Knowledge: "Chemical Analysis Basics" (Level 3 - 75% understanding)
  - Item: "Sample Collection Kit" (Quantity: 1)

Guidelines:
- Knowledge requirements should have levels 1-4 (25%, 50%, 75%, 100% mastery)
- Items should have specific quantities
- Be specific about what needs to be known/obtained
- Consider prerequisite knowledge (need to know X before learning Y)
- Provide specific objective IDs and descriptions
- Link each objective to campaign objectives it supports"""),
            ("user", """Quest Context:
Name: {quest_name}
Description: {quest_description}
Backstory: {quest_backstory}
Difficulty: {difficulty}

Existing Quest Objectives (high-level):
{existing_objectives}

Campaign Objectives This Quest Should Support:
{campaign_objectives}

Generate structured objectives with specific knowledge and item requirements.""")
        ])

        # Format existing objectives
        existing_objectives_str = "\n".join([
            f"- {obj.get('description', 'Unnamed objective')} (Bloom's Level: {obj.get('blooms_level', 1)})"
            for obj in quest.get("objectives", [])
        ])

        # Format campaign objectives
        campaign_objectives_str = "\n".join([
            f"- {obj.get('description', 'Unnamed objective')} (Bloom's Level: {obj.get('blooms_level', 1)})"
            for obj in campaign_objectives
        ])

        # Generate structured objectives using Pydantic for validation
        structured_llm = anthropic_client.with_structured_output(QuestObjectivesResponse, include_raw=False)
        chain = prompt | structured_llm

        objectives_response: QuestObjectivesResponse = await chain.ainvoke({
            "quest_name": quest["name"],
            "quest_description": quest["description"],
            "quest_backstory": quest.get("backstory", ""),
            "difficulty": quest["difficulty_level"],
            "existing_objectives": existing_objectives_str,
            "campaign_objectives": campaign_objectives_str
        })

        # Convert Pydantic model to dict
        objectives_raw = objectives_response.model_dump()["objectives"]

        # Convert to QuestObjective format
        structured_objectives: List[QuestObjective] = []
        for obj_data in objectives_raw:
            objective: QuestObjective = {
                "objective_id": obj_data.get("objective_id", f"obj_{len(structured_objectives)}"),
                "description": obj_data.get("description", ""),
                "required_knowledge": [
                    {
                        "knowledge_id": f"kg_{quest['name'].lower().replace(' ', '_')}_{i}",
                        "knowledge_name": kg.get("knowledge_name", ""),
                        "min_level": kg.get("min_level", 1)
                    }
                    for i, kg in enumerate(obj_data.get("required_knowledge", []))
                ],
                "required_items": [
                    {
                        "item_id": f"item_{quest['name'].lower().replace(' ', '_')}_{i}",
                        "item_name": item.get("item_name", ""),
                        "quantity": item.get("quantity", 1)
                    }
                    for i, item in enumerate(obj_data.get("required_items", []))
                ],
                "status": "not_started"
            }

            structured_objectives.append(objective)

            # Also store the full knowledge/item descriptions for later use
            # We'll use these when generating KnowledgeData and ItemData entities
            objective["_knowledge_specs"] = obj_data.get("required_knowledge", [])
            objective["_item_specs"] = obj_data.get("required_items", [])

        logger.info(f"Generated {len(structured_objectives)} structured objectives")
        return structured_objectives

    except Exception as e:
        logger.error(f"Error generating quest objectives: {str(e)}")
        # Return basic objectives if AI generation fails
        return [
            QuestObjective(
                objective_id=f"obj_{i}",
                description=obj.get("description", ""),
                required_knowledge=[],
                required_items=[],
                status="not_started"
            )
            for i, obj in enumerate(quest.get("objectives", []))
        ]


async def create_knowledge_entities_from_objectives(
    objectives: List[QuestObjective],
    quest: QuestData,
    state: CampaignWorkflowState
) -> List[KnowledgeData]:
    """
    Create KnowledgeData entities from quest objectives.

    For each required knowledge in objectives:
    - Creates full KnowledgeData with 4 partial levels
    - Determines which dimension it develops
    - Links to quest objectives

    Args:
        objectives: Quest objectives with knowledge requirements
        quest: Parent quest
        state: Full campaign workflow state

    Returns:
        List of KnowledgeData entities
    """
    try:
        logger.info(f"Creating knowledge entities for quest: {quest['name']}")

        knowledge_entities: List[KnowledgeData] = []

        # Collect all unique knowledge requirements
        unique_knowledge: Dict[str, Any] = {}
        for objective in objectives:
            if "_knowledge_specs" in objective:
                for kg_spec in objective["_knowledge_specs"]:
                    kg_name = kg_spec.get("knowledge_name", "")
                    if kg_name not in unique_knowledge:
                        unique_knowledge[kg_name] = kg_spec

        # Create prompt for AI to generate partial levels
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in creating progressive learning paths.

Your task is to take a knowledge entity and break it into 4 progressive levels of understanding:
- Level 1 (25%): Basic awareness - Can recognize the concept
- Level 2 (50%): Working understanding - Can explain and use in simple contexts
- Level 3 (75%): Proficient application - Can apply in complex situations
- Level 4 (100%): Expert mastery - Can analyze, evaluate, and create new applications

For each level, describe what the player knows and which objectives this level can satisfy."""),
            ("user", """Knowledge Entity:
Name: {knowledge_name}
Description: {knowledge_description}
Type: {knowledge_type}
Primary Dimension: {primary_dimension}

Quest Objectives That Need This Knowledge:
{objectives_needing_this}

Generate 4 progressive levels of understanding.""")
        ])

        chain = prompt | anthropic_client

        # Generate partial levels for each knowledge entity
        for kg_name, kg_spec in unique_knowledge.items():
            try:
                # Find objectives that need this knowledge
                objectives_needing = [
                    obj["objective_id"]
                    for obj in objectives
                    if any(
                        req.get("knowledge_name") == kg_name
                        for req in obj.get("_knowledge_specs", [])
                    )
                ]

                objectives_str = "\n".join([
                    f"- {obj['description']} (requires level {req.get('min_level', 1)})"
                    for obj in objectives
                    for req in obj.get("_knowledge_specs", [])
                    if req.get("knowledge_name") == kg_name
                ])

                # Use structured output for validation
                structured_llm = anthropic_client.with_structured_output(PartialLevelsResponse, include_raw=False)
                chain_with_struct = prompt | structured_llm

                levels_response: PartialLevelsResponse = await chain_with_struct.ainvoke({
                    "knowledge_name": kg_name,
                    "knowledge_description": kg_spec.get("knowledge_description", ""),
                    "knowledge_type": kg_spec.get("knowledge_type", "skill"),
                    "primary_dimension": kg_spec.get("primary_dimension", "intellectual"),
                    "objectives_needing_this": objectives_str
                })

                partial_levels_raw = levels_response.model_dump()

                # Create KnowledgeData entity with ID now (needed for name-to-ID conversion)
                import uuid
                knowledge_id = f"knowledge_{uuid.uuid4().hex[:16]}"

                knowledge_entity: KnowledgeData = {
                    "knowledge_id": knowledge_id,  # Generate ID immediately for linking
                    "name": kg_name,
                    "description": kg_spec.get("knowledge_description", ""),
                    "knowledge_type": kg_spec.get("knowledge_type", "skill"),
                    "primary_dimension": kg_spec.get("primary_dimension", "intellectual"),
                    "bloom_level_target": kg_spec.get("min_level", 3),  # Default to Apply level
                    "supports_objectives": objectives_needing,
                    "partial_levels": partial_levels_raw.get("partial_levels", []),
                    "acquisition_methods": [],  # Will be populated in Phase 4
                    "created_at": None,
                    "scene_id": None
                }

                knowledge_entities.append(knowledge_entity)

            except Exception as e:
                logger.error(f"Error generating partial levels for {kg_name}: {str(e)}")
                continue

        logger.info(f"Created {len(knowledge_entities)} knowledge entities")
        return knowledge_entities

    except Exception as e:
        logger.error(f"Error creating knowledge entities: {str(e)}")
        return []


async def create_item_entities_from_objectives(
    objectives: List[QuestObjective],
    quest: QuestData,
    state: CampaignWorkflowState
) -> List[ItemData]:
    """
    Create ItemData entities from quest objectives.

    For each required item in objectives:
    - Creates full ItemData entity
    - Determines if it's quest-critical
    - Links to quest objectives

    Args:
        objectives: Quest objectives with item requirements
        quest: Parent quest
        state: Full campaign workflow state

    Returns:
        List of ItemData entities
    """
    try:
        logger.info(f"Creating item entities for quest: {quest['name']}")

        item_entities: List[ItemData] = []

        # Collect all unique item requirements
        unique_items: Dict[str, Any] = {}
        for objective in objectives:
            if "_item_specs" in objective:
                for item_spec in objective["_item_specs"]:
                    item_name = item_spec.get("item_name", "")
                    if item_name not in unique_items:
                        unique_items[item_name] = item_spec

        # Create ItemData entities
        for item_name, item_spec in unique_items.items():
            # Find objectives that need this item
            objectives_needing = [
                obj["objective_id"]
                for obj in objectives
                if any(
                    req.get("item_name") == item_name
                    for req in obj.get("_item_specs", [])
                )
            ]

            # Generate item ID immediately for linking
            import uuid
            item_id = f"item_{uuid.uuid4().hex[:16]}"

            item_entity: ItemData = {
                "item_id": item_id,  # Generate ID immediately for linking
                "name": item_name,
                "description": item_spec.get("item_description", ""),
                "item_type": item_spec.get("item_type", "tool"),
                "supports_objectives": objectives_needing,
                "acquisition_methods": [],  # Will be populated in Phase 4
                "quantity": item_spec.get("quantity", 1),
                "is_consumable": item_spec.get("item_type") == "consumable",
                "is_quest_critical": True,  # Items in objectives are quest-critical
                "created_at": None,
                "scene_id": None
            }

            item_entities.append(item_entity)

        logger.info(f"Created {len(item_entities)} item entities")
        return item_entities

    except Exception as e:
        logger.error(f"Error creating item entities: {str(e)}")
        return []


def validate_objective_achievability(
    quest: QuestData,
    objectives: List[QuestObjective],
    available_knowledge: List[KnowledgeData],
    available_items: List[ItemData]
) -> Tuple[bool, str]:
    """
    Validate that all quest objectives can be completed with available resources.

    Checks:
    - All required knowledge entities exist
    - Knowledge partial levels can reach required minimums
    - All required items exist
    - Item quantities are achievable

    Args:
        quest: Quest to validate
        objectives: Quest objectives with requirements
        available_knowledge: All knowledge entities in campaign
        available_items: All item entities in campaign

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        logger.info(f"Validating objective achievability for quest: {quest['name']}")

        # Build lookup maps
        knowledge_map = {kg["name"]: kg for kg in available_knowledge}
        item_map = {item["name"]: item for item in available_items}

        # Check each objective
        for objective in objectives:
            # Check knowledge requirements
            for req_kg in objective.get("_knowledge_specs", []):
                kg_name = req_kg.get("knowledge_name", "")
                min_level = req_kg.get("min_level", 1)

                if kg_name not in knowledge_map:
                    return False, f"Objective '{objective['description']}' requires knowledge '{kg_name}' which doesn't exist"

                knowledge = knowledge_map[kg_name]
                max_achievable_level = len(knowledge.get("partial_levels", []))

                if min_level > max_achievable_level:
                    return False, f"Objective '{objective['description']}' requires knowledge '{kg_name}' at level {min_level}, but only {max_achievable_level} levels are achievable"

            # Check item requirements
            for req_item in objective.get("_item_specs", []):
                item_name = req_item.get("item_name", "")
                quantity = req_item.get("quantity", 1)

                if item_name not in item_map:
                    return False, f"Objective '{objective['description']}' requires item '{item_name}' which doesn't exist"

                item = item_map[item_name]
                available_quantity = item.get("quantity", 0)

                if quantity > available_quantity:
                    return False, f"Objective '{objective['description']}' requires {quantity}x '{item_name}', but only {available_quantity} are available"

        logger.info(f"All objectives are achievable for quest: {quest['name']}")
        return True, ""

    except Exception as e:
        logger.error(f"Error validating objective achievability: {str(e)}")
        return False, f"Validation error: {str(e)}"


def map_knowledge_to_scenes(
    knowledge_entities: List[KnowledgeData],
    scene_assignments: List[Dict[str, Any]],
    redundancy_factor: int = 3
) -> Dict[str, List[str]]:
    """
    Map knowledge entities to scenes based on objective assignments.

    Uses scene_objective_assignments to determine which scenes should provide which knowledge.
    Creates redundancy by assigning each knowledge entity to multiple scenes.

    Args:
        knowledge_entities: All knowledge entities to distribute
        scene_assignments: Scene objective assignments with knowledge domain requirements
        redundancy_factor: How many scenes should provide each knowledge (default 3)

    Returns:
        Dict mapping knowledge_id -> list of scene_ids
    """
    try:
        logger.info(f"Mapping {len(knowledge_entities)} knowledge entities to {len(scene_assignments)} scene assignments")

        knowledge_to_scenes: Dict[str, List[str]] = {}

        # Build map of knowledge_id -> knowledge entity
        kg_id_to_entity = {kg.get("knowledge_id", kg.get("name")): kg for kg in knowledge_entities}

        # Strategy 1: Use objective-driven assignment from scene_objective_assignments
        # Build map of domain -> scenes that should provide that domain
        domain_to_scenes: Dict[str, List[str]] = {}
        for assignment in scene_assignments:
            scene_id = assignment.get("scene_id")
            for kg_spec in assignment.get("provides_knowledge", []):
                domain = kg_spec.get("domain", kg_spec.get("knowledge_id", ""))
                if domain not in domain_to_scenes:
                    domain_to_scenes[domain] = []
                domain_to_scenes[domain].append(scene_id)

        # Match knowledge entities to domains
        for knowledge in knowledge_entities:
            kg_id = knowledge.get("knowledge_id", knowledge["name"])
            kg_name = knowledge["name"]
            kg_type = knowledge.get("knowledge_type", "skill")

            # Try exact name match first
            if kg_name in domain_to_scenes:
                knowledge_to_scenes[kg_id] = domain_to_scenes[kg_name][:redundancy_factor]
                logger.debug(f"Knowledge '{kg_name}' matched to {len(knowledge_to_scenes[kg_id])} scenes by name")
                continue

            # Try type-based matching
            type_matches = [
                scene_id
                for domain, scene_ids in domain_to_scenes.items()
                if kg_type.lower() in domain.lower()
                for scene_id in scene_ids
            ]

            if len(type_matches) >= redundancy_factor:
                knowledge_to_scenes[kg_id] = type_matches[:redundancy_factor]
                logger.debug(f"Knowledge '{kg_name}' matched to {len(knowledge_to_scenes[kg_id])} scenes by type")
                continue

            # Fallback: Distribute evenly across all scenes with knowledge assignments
            scenes_with_knowledge = list(set([
                assignment["scene_id"]
                for assignment in scene_assignments
                if len(assignment.get("provides_knowledge", [])) > 0
            ]))

            if len(scenes_with_knowledge) > 0:
                # Use modulo to distribute evenly
                i = len(knowledge_to_scenes)  # Use number of already-assigned knowledge as offset
                selected_scenes = [
                    scenes_with_knowledge[(i + j) % len(scenes_with_knowledge)]
                    for j in range(min(redundancy_factor, len(scenes_with_knowledge)))
                ]
                knowledge_to_scenes[kg_id] = selected_scenes
                logger.debug(f"Knowledge '{kg_name}' distributed to {len(selected_scenes)} scenes (fallback)")
            else:
                logger.warning(f"No scenes available for knowledge '{kg_name}'")
                knowledge_to_scenes[kg_id] = []

        return knowledge_to_scenes

    except Exception as e:
        logger.error(f"Error mapping knowledge to scenes: {str(e)}")
        return {}


def map_items_to_scenes(
    item_entities: List[ItemData],
    scene_assignments: List[Dict[str, Any]],
    redundancy_factor: int = 2
) -> Dict[str, List[str]]:
    """
    Map item entities to scenes based on objective assignments.

    Uses scene_objective_assignments to determine which scenes should provide which items.
    Creates redundancy by assigning each item to multiple scenes.

    Args:
        item_entities: All item entities to distribute
        scene_assignments: Scene objective assignments with item category requirements
        redundancy_factor: How many scenes should provide each item (default 2)

    Returns:
        Dict mapping item_id -> list of scene_ids
    """
    try:
        logger.info(f"Mapping {len(item_entities)} item entities to {len(scene_assignments)} scene assignments")

        item_to_scenes: Dict[str, List[str]] = {}

        # Build map of item_id -> item entity
        item_id_to_entity = {item.get("item_id", item.get("name")): item for item in item_entities}

        # Strategy 1: Use objective-driven assignment from scene_objective_assignments
        # Build map of category -> scenes that should provide that category
        category_to_scenes: Dict[str, List[str]] = {}
        for assignment in scene_assignments:
            scene_id = assignment.get("scene_id")
            for item_spec in assignment.get("provides_items", []):
                category = item_spec.get("category", item_spec.get("item_id", ""))
                if category not in category_to_scenes:
                    category_to_scenes[category] = []
                category_to_scenes[category].append(scene_id)

        # Match item entities to categories
        for item in item_entities:
            item_id = item.get("item_id", item["name"])
            item_name = item["name"]
            item_type = item.get("item_type", "tool")

            # Quest-critical items get +1 redundancy
            actual_redundancy = redundancy_factor + (1 if item.get("is_quest_critical") else 0)

            # Try exact name match first
            if item_name in category_to_scenes:
                item_to_scenes[item_id] = category_to_scenes[item_name][:actual_redundancy]
                logger.debug(f"Item '{item_name}' matched to {len(item_to_scenes[item_id])} scenes by name")
                continue

            # Try type-based matching
            type_matches = [
                scene_id
                for category, scene_ids in category_to_scenes.items()
                if item_type.lower() in category.lower()
                for scene_id in scene_ids
            ]

            if len(type_matches) >= actual_redundancy:
                item_to_scenes[item_id] = type_matches[:actual_redundancy]
                logger.debug(f"Item '{item_name}' matched to {len(item_to_scenes[item_id])} scenes by type")
                continue

            # Fallback: Distribute evenly across all scenes with item assignments
            scenes_with_items = list(set([
                assignment["scene_id"]
                for assignment in scene_assignments
                if len(assignment.get("provides_items", [])) > 0
            ]))

            if len(scenes_with_items) > 0:
                # Use modulo to distribute evenly
                i = len(item_to_scenes)  # Use number of already-assigned items as offset
                selected_scenes = [
                    scenes_with_items[(i + j) % len(scenes_with_items)]
                    for j in range(min(actual_redundancy, len(scenes_with_items)))
                ]
                item_to_scenes[item_id] = selected_scenes
                logger.debug(f"Item '{item_name}' distributed to {len(selected_scenes)} scenes (fallback)")
            else:
                logger.warning(f"No scenes available for item '{item_name}'")
                item_to_scenes[item_id] = []

        return item_to_scenes

    except Exception as e:
        logger.error(f"Error mapping items to scenes: {str(e)}")
        return {}
