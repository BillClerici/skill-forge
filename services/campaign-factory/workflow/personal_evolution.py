"""
Personal Evolution Arc Calculator
Calculates overall character development based on balanced dimensional growth

The Personal Evolution Arc represents meta-cognitive development - the character's
ability to reflect on, integrate, and synthesize learning across all 7 dimensions.
It requires balanced development and represents wisdom, not just skill.
"""
import logging
from typing import Dict
from .state import CharacterDevelopmentProfile, DimensionalMaturity

logger = logging.getLogger(__name__)

# Bloom's levels for Personal Evolution Arc (Meta-Cognitive Development)
PERSONAL_EVOLUTION_LEVELS = {
    1: ("remembering", "Novice", "Developing awareness across multiple dimensions"),
    2: ("understanding", "Apprentice", "Understanding connections between growth areas"),
    3: ("applying", "Journeyman", "Applying integrated knowledge across domains"),
    4: ("analyzing", "Expert", "Analyzing patterns across all dimensions"),
    5: ("evaluating", "Master", "Evaluating holistic development with wisdom"),
    6: ("creating", "Grandmaster", "Creating transformative synthesis and original frameworks")
}


def calculate_personal_evolution_level(
    dimensional_maturity: Dict[str, DimensionalMaturity]
) -> tuple[int, str, str]:
    """
    Calculate Personal Evolution Arc level based on dimensional development.

    Requires balanced growth across dimensions:
    - Level 1 (Novice): Starting point - all dimensions at level 1
    - Level 2 (Apprentice): Developing - 5+ dimensions at level 2+
    - Level 3 (Journeyman): Applying - 4+ dimensions at level 3+, all at 2+
    - Level 4 (Expert): Analyzing - 3+ dimensions at level 4+, 6+ at 3+
    - Level 5 (Master): Evaluating - 2+ dimensions at level 5+, 5+ at 4+
    - Level 6 (Grandmaster): Creating - 1+ dimension at 6, 4+ at 5+, all at 4+

    Args:
        dimensional_maturity: Character's dimensional maturity data

    Returns:
        Tuple of (level: int, blooms_level: str, friendly_name: str)
    """
    try:
        # Extract dimension levels
        dimension_levels = [
            dim_data.get("current_level", 1)
            for dim_data in dimensional_maturity.values()
        ]

        if not dimension_levels or len(dimension_levels) != 7:
            logger.warning(f"Invalid dimensional maturity data, defaulting to level 1")
            return 1, "remembering", "Novice"

        # Count dimensions at each level threshold
        def count_at_level(min_level: int) -> int:
            return sum(1 for level in dimension_levels if level >= min_level)

        # Check requirements from highest to lowest

        # Level 6: Grandmaster (Create)
        # At least 1 dimension at 6, 4+ at level 5+, all at level 4+
        if count_at_level(6) >= 1 and count_at_level(5) >= 4 and count_at_level(4) == 7:
            logger.info("Personal Evolution: Grandmaster (Level 6) - Transformative wisdom")
            return 6, "creating", "Grandmaster"

        # Level 5: Master (Evaluate)
        # At least 2 dimensions at 5+, 5+ at level 4+
        if count_at_level(5) >= 2 and count_at_level(4) >= 5:
            logger.info("Personal Evolution: Master (Level 5) - Evaluative judgment")
            return 5, "evaluating", "Master"

        # Level 4: Expert (Analyze)
        # At least 3 dimensions at 4+, 6+ at level 3+
        if count_at_level(4) >= 3 and count_at_level(3) >= 6:
            logger.info("Personal Evolution: Expert (Level 4) - Analytical insight")
            return 4, "analyzing", "Expert"

        # Level 3: Journeyman (Apply)
        # At least 4 dimensions at 3+, all at level 2+
        if count_at_level(3) >= 4 and count_at_level(2) == 7:
            logger.info("Personal Evolution: Journeyman (Level 3) - Practical application")
            return 3, "applying", "Journeyman"

        # Level 2: Apprentice (Understand)
        # At least 5 dimensions at level 2+
        if count_at_level(2) >= 5:
            logger.info("Personal Evolution: Apprentice (Level 2) - Developing understanding")
            return 2, "understanding", "Apprentice"

        # Level 1: Novice (Remember) - Default
        logger.info("Personal Evolution: Novice (Level 1) - Beginning journey")
        return 1, "remembering", "Novice"

    except Exception as e:
        logger.error(f"Error calculating personal evolution level: {str(e)}")
        return 1, "remembering", "Novice"


def update_personal_evolution_arc(
    profile: CharacterDevelopmentProfile
) -> tuple[int, str, str]:
    """
    Update the character's Personal Evolution Arc based on dimensional maturity.

    Call this function after dimensional level-ups to check if the character
    has achieved the requirements for a new Personal Evolution level.

    Args:
        profile: Character development profile

    Returns:
        Tuple of (level: int, blooms_level: str, friendly_name: str)
    """
    return calculate_personal_evolution_level(profile["dimensional_maturity"])


def get_next_evolution_requirements(current_level: int) -> Dict[str, any]:
    """
    Get the requirements for the next Personal Evolution level.

    Args:
        current_level: Current Personal Evolution level (1-6)

    Returns:
        Dict with requirements for next level
    """
    requirements = {
        1: {
            "target_level": 2,
            "target_name": "Apprentice (Understand)",
            "requirements": "Reach level 2+ in at least 5 dimensions",
            "encouragement": "Continue developing multiple areas to demonstrate understanding"
        },
        2: {
            "target_level": 3,
            "target_name": "Journeyman (Apply)",
            "requirements": "Reach level 3+ in 4 dimensions, level 2+ in all dimensions",
            "encouragement": "Apply your knowledge practically across all areas of development"
        },
        3: {
            "target_level": 4,
            "target_name": "Expert (Analyze)",
            "requirements": "Reach level 4+ in 3 dimensions, level 3+ in 6 dimensions",
            "encouragement": "Analyze patterns and connections across your developed dimensions"
        },
        4: {
            "target_level": 5,
            "target_name": "Master (Evaluate)",
            "requirements": "Reach level 5+ in 2 dimensions, level 4+ in 5 dimensions",
            "encouragement": "Evaluate and make judgments demonstrating integrated wisdom"
        },
        5: {
            "target_level": 6,
            "target_name": "Grandmaster (Create)",
            "requirements": "Reach level 6 in 1 dimension, level 5+ in 4 dimensions, level 4+ in all dimensions",
            "encouragement": "Create original synthesis and transformative insights from your mastery"
        },
        6: {
            "target_level": 6,
            "target_name": "Grandmaster (Create)",
            "requirements": "You have achieved the highest level of Personal Evolution",
            "encouragement": "Continue growing and sharing your wisdom with others"
        }
    }

    return requirements.get(current_level, requirements[1])


def get_evolution_gap_analysis(
    dimensional_maturity: Dict[str, DimensionalMaturity]
) -> Dict[str, any]:
    """
    Analyze the gap between current state and next evolution level.

    Args:
        dimensional_maturity: Character's dimensional maturity data

    Returns:
        Dict with gap analysis and recommendations
    """
    current_level, _, _ = calculate_personal_evolution_level(dimensional_maturity)
    next_requirements = get_next_evolution_requirements(current_level)

    # Get current dimension levels
    dimension_status = {}
    for dimension, data in dimensional_maturity.items():
        dimension_status[dimension] = {
            "name": dimension.capitalize(),
            "current_level": data.get("current_level", 1),
            "friendly_name": _get_friendly_name(data.get("current_level", 1)),
            "experience_points": data.get("experience_points", 0),
            "next_threshold": data.get("next_level_threshold", 100)
        }

    # Sort dimensions by level (lowest first)
    weakest_dimensions = sorted(
        dimension_status.items(),
        key=lambda x: (x[1]["current_level"], x[1]["experience_points"])
    )

    return {
        "current_evolution_level": current_level,
        "next_evolution_level": next_requirements["target_level"],
        "next_evolution_name": next_requirements["target_name"],
        "requirements": next_requirements["requirements"],
        "encouragement": next_requirements["encouragement"],
        "dimension_status": dimension_status,
        "focus_dimensions": [dim[0] for dim in weakest_dimensions[:3]],
        "focus_explanation": "Focus on developing your weakest dimensions to achieve balanced growth"
    }


def _get_friendly_name(level: int) -> str:
    """Get friendly name for a Bloom's level"""
    friendly_names = {
        1: "Novice",
        2: "Apprentice",
        3: "Journeyman",
        4: "Expert",
        5: "Master",
        6: "Grandmaster"
    }
    return friendly_names.get(level, "Novice")
