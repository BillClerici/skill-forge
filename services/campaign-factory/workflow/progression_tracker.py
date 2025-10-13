"""
Character Progression Tracker
Manages multi-dimensional character development

Phase 5: Progression tracking and balance system
"""
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from .state import (
    CharacterDevelopmentProfile,
    DimensionalMaturity,
    QuestObjective,
    KnowledgeData,
    ItemData
)

logger = logging.getLogger(__name__)

# Bloom's level descriptions
BLOOMS_LEVELS = {
    1: "Remember",
    2: "Understand",
    3: "Apply",
    4: "Analyze",
    5: "Evaluate",
    6: "Create"
}

# Experience thresholds for each Bloom's level
LEVEL_THRESHOLDS = {
    1: 0,      # Level 1 starts at 0
    2: 100,    # Level 2 requires 100 exp
    3: 300,    # Level 3 requires 300 exp (200 more)
    4: 600,    # Level 4 requires 600 exp (300 more)
    5: 1000,   # Level 5 requires 1000 exp (400 more)
    6: 1500    # Level 6 requires 1500 exp (500 more)
}


def create_character_profile(character_id: str) -> CharacterDevelopmentProfile:
    """
    Create a new character development profile with all dimensions at level 1.

    Args:
        character_id: ID of the character

    Returns:
        CharacterDevelopmentProfile initialized at level 1
    """
    dimensions = ["physical", "emotional", "intellectual", "social", "spiritual", "vocational", "environmental"]

    dimensional_maturity = {}
    for dimension in dimensions:
        dimensional_maturity[dimension] = DimensionalMaturity(
            current_level=1,
            bloom_level="Remember",
            experience_points=0,
            next_level_threshold=LEVEL_THRESHOLDS[2],
            strengths=[],
            growth_areas=[]
        )

    profile: CharacterDevelopmentProfile = {
        "character_id": character_id,
        "dimensional_maturity": dimensional_maturity,
        "balance_score": 1.0,
        "most_developed": [],
        "least_developed": dimensions.copy(),
        "recommended_focus": dimensions[:3],  # Start with first 3
        "acquired_knowledge": {},
        "acquired_items": {},
        "quest_progress": {}
    }

    return profile


def award_knowledge(
    profile: CharacterDevelopmentProfile,
    knowledge_id: str,
    knowledge_name: str,
    level: int,
    source: str = "unknown"
) -> CharacterDevelopmentProfile:
    """
    Award knowledge at a specific level to the character.

    Args:
        profile: Character's development profile
        knowledge_id: ID of the knowledge entity
        knowledge_name: Name of the knowledge
        level: Level of mastery (1-4)
        source: Source of the knowledge (e.g., "npc_conversation", "challenge")

    Returns:
        Updated profile
    """
    try:
        current_time = datetime.now().isoformat()

        if knowledge_id not in profile["acquired_knowledge"]:
            # First time acquiring this knowledge
            profile["acquired_knowledge"][knowledge_id] = {
                "name": knowledge_name,
                "current_level": level,
                "max_level": 4,
                "acquisition_history": [
                    {
                        "level": level,
                        "source": source,
                        "timestamp": current_time
                    }
                ]
            }
            logger.info(f"Awarded new knowledge: {knowledge_name} (Level {level})")
        else:
            # Upgrading existing knowledge
            existing = profile["acquired_knowledge"][knowledge_id]
            if level > existing["current_level"]:
                existing["current_level"] = level
                existing["acquisition_history"].append({
                    "level": level,
                    "source": source,
                    "timestamp": current_time
                })
                logger.info(f"Upgraded knowledge: {knowledge_name} (Level {existing['current_level']} -> {level})")
            else:
                logger.debug(f"Knowledge {knowledge_name} already at level {existing['current_level']}, not downgrading")

        return profile

    except Exception as e:
        logger.error(f"Error awarding knowledge: {str(e)}")
        return profile


def award_item(
    profile: CharacterDevelopmentProfile,
    item_id: str,
    item_name: str,
    quantity: int = 1,
    source: str = "unknown"
) -> CharacterDevelopmentProfile:
    """
    Add item to character's inventory.

    Args:
        profile: Character's development profile
        item_id: ID of the item entity
        item_name: Name of the item
        quantity: Quantity to add
        source: Source of the item (e.g., "challenge", "event")

    Returns:
        Updated profile
    """
    try:
        current_time = datetime.now().isoformat()

        if item_id not in profile["acquired_items"]:
            # First time acquiring this item
            profile["acquired_items"][item_id] = {
                "name": item_name,
                "quantity": quantity,
                "acquisition_source": source,
                "first_acquired": current_time,
                "history": [
                    {
                        "quantity_change": quantity,
                        "source": source,
                        "timestamp": current_time
                    }
                ]
            }
            logger.info(f"Awarded new item: {item_name} x{quantity}")
        else:
            # Adding more of existing item
            existing = profile["acquired_items"][item_id]
            existing["quantity"] += quantity
            existing["history"].append({
                "quantity_change": quantity,
                "source": source,
                "timestamp": current_time
            })
            logger.info(f"Added to existing item: {item_name} x{quantity} (Total: {existing['quantity']})")

        return profile

    except Exception as e:
        logger.error(f"Error awarding item: {str(e)}")
        return profile


def add_dimensional_experience(
    profile: CharacterDevelopmentProfile,
    dimension: str,
    exp: int
) -> CharacterDevelopmentProfile:
    """
    Add experience points to a dimension and handle level-ups.
    Also updates Personal Evolution Arc if dimensional requirements are met.

    Args:
        profile: Character's development profile
        dimension: Dimension to add experience to
        exp: Experience points to add

    Returns:
        Updated profile with possible level-up and Personal Evolution Arc update
    """
    try:
        if dimension not in profile["dimensional_maturity"]:
            logger.error(f"Invalid dimension: {dimension}")
            return profile

        maturity = profile["dimensional_maturity"][dimension]

        # Add experience
        maturity["experience_points"] += exp
        logger.info(f"Added {exp} exp to {dimension} (Total: {maturity['experience_points']})")

        # Check for level-up
        current_level = maturity["current_level"]
        new_level = _calculate_level_from_exp(maturity["experience_points"])

        dimensional_level_up = False
        if new_level > current_level:
            maturity["current_level"] = new_level
            maturity["bloom_level"] = BLOOMS_LEVELS[new_level]
            maturity["next_level_threshold"] = LEVEL_THRESHOLDS.get(new_level + 1, float('inf'))
            dimensional_level_up = True

            logger.info(f"LEVEL UP! {dimension}: {current_level} -> {new_level} ({BLOOMS_LEVELS[new_level]})")

        # Recalculate balance score after experience gain
        profile["balance_score"] = calculate_balance_score(profile)
        profile["most_developed"], profile["least_developed"] = _identify_dimension_extremes(profile)
        profile["recommended_focus"] = recommend_focus_dimensions(profile)

        # Check Personal Evolution Arc update (if dimensional level-up occurred)
        if dimensional_level_up:
            try:
                from . import personal_evolution

                pe_level, pe_blooms, pe_friendly = personal_evolution.calculate_personal_evolution_level(
                    profile["dimensional_maturity"]
                )

                # Store in profile metadata for later sync with Django Character model
                if "personal_evolution" not in profile:
                    profile["personal_evolution"] = {}

                old_pe_level = profile["personal_evolution"].get("level", 1)
                profile["personal_evolution"]["level"] = pe_level
                profile["personal_evolution"]["blooms_level"] = pe_blooms
                profile["personal_evolution"]["friendly_name"] = pe_friendly

                if pe_level > old_pe_level:
                    logger.info(f"PERSONAL EVOLUTION ARC LEVEL UP! {old_pe_level} -> {pe_level} ({pe_friendly})")
                    logger.info(f"Character has achieved {pe_blooms.upper()} level of integrated development!")

            except Exception as e:
                logger.error(f"Error updating Personal Evolution Arc: {str(e)}")

        return profile

    except Exception as e:
        logger.error(f"Error adding dimensional experience: {str(e)}")
        return profile


def check_objective_completion(
    profile: CharacterDevelopmentProfile,
    objective: QuestObjective
) -> Tuple[bool, str]:
    """
    Check if character has met all requirements for an objective.

    Args:
        profile: Character's development profile
        objective: Quest objective to check

    Returns:
        Tuple of (is_complete, reason)
    """
    try:
        # Check knowledge requirements
        for req_kg in objective.get("required_knowledge", []):
            kg_id = req_kg.get("knowledge_id", "")
            min_level = req_kg.get("min_level", 1)

            if kg_id not in profile["acquired_knowledge"]:
                return False, f"Missing required knowledge: {req_kg.get('knowledge_name', kg_id)}"

            current_level = profile["acquired_knowledge"][kg_id]["current_level"]
            if current_level < min_level:
                return False, f"Knowledge {req_kg.get('knowledge_name', kg_id)} is only level {current_level}, needs {min_level}"

        # Check item requirements
        for req_item in objective.get("required_items", []):
            item_id = req_item.get("item_id", "")
            required_qty = req_item.get("quantity", 1)

            if item_id not in profile["acquired_items"]:
                return False, f"Missing required item: {req_item.get('item_name', item_id)}"

            current_qty = profile["acquired_items"][item_id]["quantity"]
            if current_qty < required_qty:
                return False, f"Item {req_item.get('item_name', item_id)} has only {current_qty}, needs {required_qty}"

        return True, "All requirements met"

    except Exception as e:
        logger.error(f"Error checking objective completion: {str(e)}")
        return False, f"Error: {str(e)}"


def calculate_balance_score(profile: CharacterDevelopmentProfile) -> float:
    """
    Calculate how balanced the character's development is across all dimensions.

    A score of 1.0 means perfectly balanced (all dimensions at same level).
    Lower scores indicate more imbalance.

    Args:
        profile: Character's development profile

    Returns:
        Balance score (0.0 to 1.0)
    """
    try:
        levels = [
            maturity["current_level"]
            for maturity in profile["dimensional_maturity"].values()
        ]

        if not levels:
            return 1.0

        # Calculate average and standard deviation
        avg_level = sum(levels) / len(levels)
        variance = sum((level - avg_level) ** 2 for level in levels) / len(levels)
        std_dev = variance ** 0.5

        # Convert standard deviation to balance score
        # 0 std dev = perfect balance (1.0)
        # Higher std dev = lower balance
        # Use formula: 1 / (1 + std_dev)
        balance = 1.0 / (1.0 + std_dev)

        logger.debug(f"Balance score: {balance:.2f} (avg: {avg_level:.1f}, std: {std_dev:.2f})")
        return round(balance, 2)

    except Exception as e:
        logger.error(f"Error calculating balance score: {str(e)}")
        return 0.5


def recommend_focus_dimensions(profile: CharacterDevelopmentProfile, count: int = 3) -> List[str]:
    """
    Recommend which dimensions the character should focus on for better balance.

    Args:
        profile: Character's development profile
        count: Number of dimensions to recommend (default 3)

    Returns:
        List of dimension names to focus on
    """
    try:
        # Sort dimensions by current level (ascending)
        dimensions_by_level = sorted(
            profile["dimensional_maturity"].items(),
            key=lambda x: x[1]["current_level"]
        )

        # Return the lowest N dimensions
        recommended = [dim for dim, _ in dimensions_by_level[:count]]

        logger.debug(f"Recommended focus dimensions: {recommended}")
        return recommended

    except Exception as e:
        logger.error(f"Error recommending focus dimensions: {str(e)}")
        return ["intellectual", "social", "emotional"]


def update_quest_progress(
    profile: CharacterDevelopmentProfile,
    quest_id: str,
    quest_name: str,
    objectives: List[QuestObjective]
) -> CharacterDevelopmentProfile:
    """
    Update quest progress tracking.

    Args:
        profile: Character's development profile
        quest_id: ID of the quest
        quest_name: Name of the quest
        objectives: Quest objectives

    Returns:
        Updated profile
    """
    try:
        # Check which objectives are complete
        objectives_completed = []
        requirements_met = {}

        for objective in objectives:
            is_complete, reason = check_objective_completion(profile, objective)
            if is_complete:
                objectives_completed.append(objective["objective_id"])
            requirements_met[objective["objective_id"]] = {
                "complete": is_complete,
                "reason": reason
            }

        # Determine quest status
        if len(objectives_completed) == 0:
            status = "not_started"
        elif len(objectives_completed) == len(objectives):
            status = "completed"
        else:
            status = "in_progress"

        # Update quest progress
        profile["quest_progress"][quest_id] = {
            "name": quest_name,
            "status": status,
            "objectives_completed": objectives_completed,
            "requirements_met": requirements_met,
            "last_updated": datetime.now().isoformat()
        }

        logger.info(f"Updated quest progress: {quest_name} - {status} ({len(objectives_completed)}/{len(objectives)} objectives)")
        return profile

    except Exception as e:
        logger.error(f"Error updating quest progress: {str(e)}")
        return profile


def _calculate_level_from_exp(exp: int) -> int:
    """
    Calculate Bloom's level based on total experience points.

    Args:
        exp: Total experience points

    Returns:
        Bloom's level (1-6)
    """
    for level in range(6, 0, -1):
        if exp >= LEVEL_THRESHOLDS[level]:
            return level
    return 1


def _identify_dimension_extremes(profile: CharacterDevelopmentProfile) -> Tuple[List[str], List[str]]:
    """
    Identify the most and least developed dimensions.

    Args:
        profile: Character's development profile

    Returns:
        Tuple of (most_developed, least_developed) lists (top 3 each)
    """
    try:
        # Sort dimensions by level and experience
        dimensions_sorted = sorted(
            profile["dimensional_maturity"].items(),
            key=lambda x: (x[1]["current_level"], x[1]["experience_points"]),
            reverse=True
        )

        most_developed = [dim for dim, _ in dimensions_sorted[:3]]
        least_developed = [dim for dim, _ in dimensions_sorted[-3:]]

        return most_developed, least_developed

    except Exception as e:
        logger.error(f"Error identifying dimension extremes: {str(e)}")
        return [], []


def get_progression_summary(profile: CharacterDevelopmentProfile) -> Dict[str, Any]:
    """
    Get a summary of character's progression.

    Args:
        profile: Character's development profile

    Returns:
        Dict with progression summary
    """
    try:
        total_knowledge = len(profile["acquired_knowledge"])
        total_items = len(profile["acquired_items"])

        # Count quests by status
        quests_by_status = {"not_started": 0, "in_progress": 0, "completed": 0}
        for quest_progress in profile["quest_progress"].values():
            status = quest_progress.get("status", "not_started")
            quests_by_status[status] = quests_by_status.get(status, 0) + 1

        # Dimensional levels
        dimension_levels = {
            dim: f"{maturity['current_level']} ({maturity['bloom_level']})"
            for dim, maturity in profile["dimensional_maturity"].items()
        }

        summary = {
            "character_id": profile["character_id"],
            "balance_score": profile["balance_score"],
            "most_developed": profile["most_developed"],
            "least_developed": profile["least_developed"],
            "recommended_focus": profile["recommended_focus"],
            "total_knowledge": total_knowledge,
            "total_items": total_items,
            "total_item_quantity": sum(
                item["quantity"] for item in profile["acquired_items"].values()
            ),
            "quests_by_status": quests_by_status,
            "dimension_levels": dimension_levels
        }

        return summary

    except Exception as e:
        logger.error(f"Error getting progression summary: {str(e)}")
        return {}
