"""
Rubric Templates Library
Pre-built rubric templates for common interaction types

Phase 3: Template library for rubric generation
"""
import logging
from typing import Dict, Any
from .state import RubricData

logger = logging.getLogger(__name__)

# 7 Developmental Dimensions
DIMENSIONS = [
    "physical",      # Body coordination, strength, endurance, reflexes
    "emotional",     # Self-awareness, empathy, stress management
    "intellectual",  # Critical thinking, problem-solving, analysis
    "social",        # Communication, cooperation, leadership
    "spiritual",     # Purpose, values, ethics, meaning-making
    "vocational",    # Skill mastery, craftsmanship, competence
    "environmental"  # Ecological awareness, resource management
]


def get_npc_conversation_template(npc_data: Dict[str, Any]) -> RubricData:
    """
    Template for NPC conversation interactions.

    Evaluates:
    - Social skills (primary)
    - Emotional intelligence (secondary)
    - Information gathering (intellectual)
    """
    return {
        "rubric_id": f"rubric_npc_{npc_data.get('id', 'unknown')}",
        "rubric_type": "npc_conversation",
        "interaction_name": npc_data.get("name", "NPC Conversation"),
        "entity_id": npc_data.get("id", ""),
        "primary_dimension": "social",
        "secondary_dimensions": ["emotional", "intellectual"],
        "evaluation_criteria": [
            {
                "criterion": "Rapport Building",
                "weight": 0.35,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Cold or abrasive interaction, NPC is defensive"},
                    {"level": 2, "description": "Neutral interaction, NPC is polite but distant"},
                    {"level": 3, "description": "Warm interaction, NPC opens up somewhat"},
                    {"level": 4, "description": "Strong connection, NPC fully trusts player"}
                ]
            },
            {
                "criterion": "Information Gathering",
                "weight": 0.30,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "Misses key information, poor questioning"},
                    {"level": 2, "description": "Gathers some information, basic questions"},
                    {"level": 3, "description": "Gathers most information, probing questions"},
                    {"level": 4, "description": "Gathers all information, strategic questioning"}
                ]
            },
            {
                "criterion": "Emotional Intelligence",
                "weight": 0.20,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Oblivious to NPC's emotional state"},
                    {"level": 2, "description": "Recognizes obvious emotions"},
                    {"level": 3, "description": "Reads subtle emotional cues"},
                    {"level": 4, "description": "Fully empathizes, responds appropriately"}
                ]
            },
            {
                "criterion": "Dialogue Choices",
                "weight": 0.15,
                "bloom_level_target": 2,  # Understand
                "levels": [
                    {"level": 1, "description": "Inappropriate or offensive choices"},
                    {"level": 2, "description": "Safe but generic choices"},
                    {"level": 3, "description": "Thoughtful, contextually appropriate"},
                    {"level": 4, "description": "Creative, personality-matched choices"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["npc_background:1"],
                "3": ["npc_background:2", "location_lore:1"],
                "4": ["npc_background:3", "location_lore:2", "secret_information:1"]
            },
            "items": {
                "3": [],
                "4": ["trust_token"]
            }
        },
        "dimensional_rewards": {
            "social": {
                "bloom_target": 3,
                "experience_by_score": {"1": 5, "2": 15, "3": 40, "4": 80}
            },
            "emotional": {
                "bloom_target": 3,
                "experience_by_score": {"1": 3, "2": 10, "3": 25, "4": 50}
            },
            "intellectual": {
                "bloom_target": 4,
                "experience_by_score": {"1": 2, "2": 8, "3": 20, "4": 40}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "relationship_damaged", "details": "NPC dislikes player, future interactions harder"},
            "2": {"type": "neutral_standing", "details": "NPC remains neutral"}
        }
    }


def get_environmental_discovery_template(discovery_data: Dict[str, Any]) -> RubricData:
    """
    Template for environmental discovery interactions.

    Evaluates:
    - Observation skills (intellectual primary)
    - Environmental awareness (environmental secondary)
    """
    return {
        "rubric_id": f"rubric_discovery_{discovery_data.get('id', 'unknown')}",
        "rubric_type": "environmental_discovery",
        "interaction_name": discovery_data.get("name", "Discovery"),
        "entity_id": discovery_data.get("id", ""),
        "primary_dimension": "intellectual",
        "secondary_dimensions": ["environmental"],
        "evaluation_criteria": [
            {
                "criterion": "Observation",
                "weight": 0.50,
                "bloom_level_target": 2,  # Understand
                "levels": [
                    {"level": 1, "description": "Overlooks obvious details"},
                    {"level": 2, "description": "Notices surface-level details"},
                    {"level": 3, "description": "Notices subtle details"},
                    {"level": 4, "description": "Notices all details, even hidden ones"}
                ]
            },
            {
                "criterion": "Pattern Recognition",
                "weight": 0.30,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "No pattern recognition"},
                    {"level": 2, "description": "Recognizes simple patterns"},
                    {"level": 3, "description": "Recognizes complex patterns"},
                    {"level": 4, "description": "Synthesizes multiple patterns"}
                ]
            },
            {
                "criterion": "Environmental Context",
                "weight": 0.20,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Ignores environmental factors"},
                    {"level": 2, "description": "Considers basic environment"},
                    {"level": 3, "description": "Integrates environmental knowledge"},
                    {"level": 4, "description": "Full ecological understanding"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["discovery_lore:1"],
                "3": ["discovery_lore:2", "location_secrets:1"],
                "4": ["discovery_lore:3", "location_secrets:2", "hidden_knowledge:1"]
            },
            "items": {
                "2": [],
                "3": ["clue_item"],
                "4": ["clue_item", "rare_artifact"]
            }
        },
        "dimensional_rewards": {
            "intellectual": {
                "bloom_target": 4,
                "experience_by_score": {"1": 10, "2": 25, "3": 50, "4": 100}
            },
            "environmental": {
                "bloom_target": 3,
                "experience_by_score": {"1": 5, "2": 15, "3": 35, "4": 70}
            }
        },
        "consequences_by_performance": None
    }


def get_combat_template(combat_data: Dict[str, Any]) -> RubricData:
    """
    Template for combat encounters.

    Evaluates across multiple dimensions:
    - Physical (40%): Combat execution
    - Intellectual (25%): Tactical thinking
    - Emotional (20%): Stress management
    - Social (15%): Team coordination
    """
    return {
        "rubric_id": f"rubric_combat_{combat_data.get('id', 'unknown')}",
        "rubric_type": "challenge",
        "interaction_name": combat_data.get("name", "Combat"),
        "entity_id": combat_data.get("id", ""),
        "primary_dimension": "physical",
        "secondary_dimensions": ["intellectual", "emotional", "social"],
        "evaluation_criteria": [
            {
                "criterion": "Combat Execution",
                "weight": 0.40,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Poor positioning, mistimed attacks, frequent damage taken"},
                    {"level": 2, "description": "Basic positioning, some successful attacks, moderate damage"},
                    {"level": 3, "description": "Good positioning, effective attacks, minimal damage"},
                    {"level": 4, "description": "Excellent positioning, perfectly timed attacks, negligible damage"}
                ]
            },
            {
                "criterion": "Tactical Thinking",
                "weight": 0.25,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "No strategy, random actions"},
                    {"level": 2, "description": "Basic strategy, targets obvious weaknesses"},
                    {"level": 3, "description": "Advanced strategy, exploits enemy patterns"},
                    {"level": 4, "description": "Master strategy, predicts and counters all moves"}
                ]
            },
            {
                "criterion": "Stress Management",
                "weight": 0.20,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Panicked, makes rash decisions"},
                    {"level": 2, "description": "Tense but functional"},
                    {"level": 3, "description": "Calm under pressure"},
                    {"level": 4, "description": "Zen-like focus, unshakeable"}
                ]
            },
            {
                "criterion": "Team Coordination",
                "weight": 0.15,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Ignores teammates, causes friendly fire"},
                    {"level": 2, "description": "Minimal coordination"},
                    {"level": 3, "description": "Good coordination, combos with team"},
                    {"level": 4, "description": "Perfect synergy, enables team strategies"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["combat_basics:1"],
                "3": ["combat_basics:2", "enemy_weakness:1"],
                "4": ["combat_basics:3", "enemy_weakness:2", "advanced_tactics:1"]
            },
            "items": {
                "2": ["healing_potion"],
                "3": ["healing_potion", "combat_loot"],
                "4": ["healing_potion", "combat_loot", "rare_weapon"]
            }
        },
        "dimensional_rewards": {
            "physical": {
                "bloom_target": 3,
                "experience_by_score": {"1": 15, "2": 40, "3": 80, "4": 150}
            },
            "intellectual": {
                "bloom_target": 4,
                "experience_by_score": {"1": 10, "2": 25, "3": 50, "4": 100}
            },
            "emotional": {
                "bloom_target": 3,
                "experience_by_score": {"1": 8, "2": 20, "3": 40, "4": 80}
            },
            "social": {
                "bloom_target": 3,
                "experience_by_score": {"1": 5, "2": 15, "3": 30, "4": 60}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "heavy_damage", "details": "Character takes significant damage"},
            "2": {"type": "moderate_damage", "details": "Character takes some damage"}
        }
    }


def get_riddle_template(challenge_data: Dict[str, Any]) -> RubricData:
    """
    Template for riddle/puzzle challenges.

    Evaluates:
    - Intellectual (primary): Problem-solving
    """
    return {
        "rubric_id": f"rubric_riddle_{challenge_data.get('id', 'unknown')}",
        "rubric_type": "challenge",
        "interaction_name": challenge_data.get("name", "Riddle"),
        "entity_id": challenge_data.get("id", ""),
        "primary_dimension": "intellectual",
        "secondary_dimensions": [],
        "evaluation_criteria": [
            {
                "criterion": "Logical Reasoning",
                "weight": 0.50,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "No logical approach, random guesses"},
                    {"level": 2, "description": "Some logic, identifies one pattern"},
                    {"level": 3, "description": "Strong logic, connects multiple clues"},
                    {"level": 4, "description": "Flawless logic, sees all connections"}
                ]
            },
            {
                "criterion": "Lateral Thinking",
                "weight": 0.30,
                "bloom_level_target": 5,  # Evaluate
                "levels": [
                    {"level": 1, "description": "Conventional thinking only"},
                    {"level": 2, "description": "Attempts creative approaches"},
                    {"level": 3, "description": "Uses lateral thinking effectively"},
                    {"level": 4, "description": "Innovative, surprising solutions"}
                ]
            },
            {
                "criterion": "Persistence",
                "weight": 0.20,
                "bloom_level_target": 2,  # Understand
                "levels": [
                    {"level": 1, "description": "Gives up quickly"},
                    {"level": 2, "description": "Tries a few times"},
                    {"level": 3, "description": "Persistent, tries many approaches"},
                    {"level": 4, "description": "Relentless, exhaustive exploration"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["riddle_hint:1"],
                "3": ["riddle_solution:2", "puzzle_mastery:1"],
                "4": ["riddle_solution:3", "puzzle_mastery:2", "ancient_wisdom:1"]
            },
            "items": {
                "3": ["puzzle_reward"],
                "4": ["puzzle_reward", "wisdom_scroll"]
            }
        },
        "dimensional_rewards": {
            "intellectual": {
                "bloom_target": 5,
                "experience_by_score": {"1": 15, "2": 40, "3": 80, "4": 150}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "puzzle_sealed", "details": "Puzzle remains unsolved, blocks progress"}
        }
    }


def get_moral_dilemma_template(challenge_data: Dict[str, Any]) -> RubricData:
    """
    Template for moral dilemma challenges.

    Evaluates:
    - Spiritual (primary): Ethical reasoning
    - Emotional (secondary): Empathy
    - Social (secondary): Considering others
    """
    return {
        "rubric_id": f"rubric_moral_{challenge_data.get('id', 'unknown')}",
        "rubric_type": "challenge",
        "interaction_name": challenge_data.get("name", "Moral Dilemma"),
        "entity_id": challenge_data.get("id", ""),
        "primary_dimension": "spiritual",
        "secondary_dimensions": ["emotional", "social"],
        "evaluation_criteria": [
            {
                "criterion": "Ethical Reasoning",
                "weight": 0.45,
                "bloom_level_target": 5,  # Evaluate
                "levels": [
                    {"level": 1, "description": "Selfish choice, no ethical consideration"},
                    {"level": 2, "description": "Basic morality, considers right vs wrong"},
                    {"level": 3, "description": "Nuanced ethics, weighs competing values"},
                    {"level": 4, "description": "Sophisticated ethics, considers long-term impact"}
                ]
            },
            {
                "criterion": "Empathy for All Parties",
                "weight": 0.30,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "Considers only self"},
                    {"level": 2, "description": "Considers one party's perspective"},
                    {"level": 3, "description": "Considers multiple perspectives"},
                    {"level": 4, "description": "Deeply empathizes with all parties"}
                ]
            },
            {
                "criterion": "Values Consistency",
                "weight": 0.25,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Contradicts previous values"},
                    {"level": 2, "description": "Somewhat consistent"},
                    {"level": 3, "description": "Consistent with character values"},
                    {"level": 4, "description": "Exemplifies core values perfectly"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["ethical_framework:1"],
                "3": ["ethical_framework:2", "moral_wisdom:1"],
                "4": ["ethical_framework:3", "moral_wisdom:2", "spiritual_insight:1"]
            },
            "items": {
                "4": ["artifact_of_virtue"]
            }
        },
        "dimensional_rewards": {
            "spiritual": {
                "bloom_target": 5,
                "experience_by_score": {"1": 10, "2": 30, "3": 70, "4": 140}
            },
            "emotional": {
                "bloom_target": 4,
                "experience_by_score": {"1": 5, "2": 15, "3": 35, "4": 70}
            },
            "social": {
                "bloom_target": 3,
                "experience_by_score": {"1": 3, "2": 10, "3": 25, "4": 50}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "spiritual_damage", "details": "Character's conscience is troubled"},
            "2": {"type": "minor_regret", "details": "Character questions their choice"}
        }
    }


def get_craft_mastery_template(challenge_data: Dict[str, Any]) -> RubricData:
    """
    Template for vocational/crafting challenges.

    Evaluates:
    - Vocational (primary): Skill execution
    - Physical (secondary): Precision
    - Intellectual (secondary): Technical knowledge
    """
    return {
        "rubric_id": f"rubric_craft_{challenge_data.get('id', 'unknown')}",
        "rubric_type": "challenge",
        "interaction_name": challenge_data.get("name", "Craft Challenge"),
        "entity_id": challenge_data.get("id", ""),
        "primary_dimension": "vocational",
        "secondary_dimensions": ["physical", "intellectual"],
        "evaluation_criteria": [
            {
                "criterion": "Technical Skill",
                "weight": 0.45,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Clumsy, produces poor quality"},
                    {"level": 2, "description": "Basic competence, adequate quality"},
                    {"level": 3, "description": "Skilled work, good quality"},
                    {"level": 4, "description": "Master craftsmanship, exceptional quality"}
                ]
            },
            {
                "criterion": "Precision & Attention to Detail",
                "weight": 0.30,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Sloppy, many errors"},
                    {"level": 2, "description": "Some attention to detail"},
                    {"level": 3, "description": "Precise, few errors"},
                    {"level": 4, "description": "Flawless precision, no errors"}
                ]
            },
            {
                "criterion": "Technical Knowledge",
                "weight": 0.25,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "Lacks basic knowledge"},
                    {"level": 2, "description": "Knows fundamentals"},
                    {"level": 3, "description": "Understands advanced techniques"},
                    {"level": 4, "description": "Expert knowledge, innovates"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["craft_basics:1"],
                "3": ["craft_basics:2", "advanced_technique:1"],
                "4": ["craft_basics:3", "advanced_technique:2", "master_secrets:1"]
            },
            "items": {
                "2": ["crafted_item_basic"],
                "3": ["crafted_item_good"],
                "4": ["crafted_item_masterwork"]
            }
        },
        "dimensional_rewards": {
            "vocational": {
                "bloom_target": 3,
                "experience_by_score": {"1": 12, "2": 35, "3": 75, "4": 140}
            },
            "physical": {
                "bloom_target": 3,
                "experience_by_score": {"1": 5, "2": 15, "3": 30, "4": 60}
            },
            "intellectual": {
                "bloom_target": 4,
                "experience_by_score": {"1": 5, "2": 15, "3": 35, "4": 70}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "material_waste", "details": "Crafting materials wasted"}
        }
    }


def get_dynamic_event_template(event_data: Dict[str, Any]) -> RubricData:
    """
    Template for dynamic events.

    Evaluates:
    - Adaptability (intellectual primary)
    - Quick thinking (emotional secondary)
    """
    return {
        "rubric_id": f"rubric_event_{event_data.get('id', 'unknown')}",
        "rubric_type": "dynamic_event",
        "interaction_name": event_data.get("name", "Dynamic Event"),
        "entity_id": event_data.get("id", ""),
        "primary_dimension": "intellectual",
        "secondary_dimensions": ["emotional"],
        "evaluation_criteria": [
            {
                "criterion": "Adaptability",
                "weight": 0.50,
                "bloom_level_target": 4,  # Analyze
                "levels": [
                    {"level": 1, "description": "Rigid, fails to adapt"},
                    {"level": 2, "description": "Slowly adapts to changes"},
                    {"level": 3, "description": "Quickly adapts, improvises well"},
                    {"level": 4, "description": "Thrives on chaos, turns it to advantage"}
                ]
            },
            {
                "criterion": "Quick Thinking",
                "weight": 0.30,
                "bloom_level_target": 3,  # Apply
                "levels": [
                    {"level": 1, "description": "Freezes, makes no decisions"},
                    {"level": 2, "description": "Slow to react"},
                    {"level": 3, "description": "Makes quick decisions"},
                    {"level": 4, "description": "Instantaneous, perfect timing"}
                ]
            },
            {
                "criterion": "Risk Assessment",
                "weight": 0.20,
                "bloom_level_target": 5,  # Evaluate
                "levels": [
                    {"level": 1, "description": "Reckless or paralyzed by fear"},
                    {"level": 2, "description": "Basic risk awareness"},
                    {"level": 3, "description": "Good risk evaluation"},
                    {"level": 4, "description": "Perfect risk/reward calculation"}
                ]
            }
        ],
        "knowledge_level_mapping": {
            "1.0-1.75": 1,
            "1.76-2.5": 2,
            "2.51-3.25": 3,
            "3.26-4.0": 4
        },
        "rewards_by_performance": {
            "knowledge": {
                "1": [],
                "2": ["event_context:1"],
                "3": ["event_context:2", "improvisation:1"],
                "4": ["event_context:3", "improvisation:2", "chaos_mastery:1"]
            },
            "items": {
                "3": ["event_reward"],
                "4": ["event_reward", "chaos_token"]
            }
        },
        "dimensional_rewards": {
            "intellectual": {
                "bloom_target": 4,
                "experience_by_score": {"1": 10, "2": 30, "3": 60, "4": 120}
            },
            "emotional": {
                "bloom_target": 3,
                "experience_by_score": {"1": 5, "2": 15, "3": 35, "4": 70}
            }
        },
        "consequences_by_performance": {
            "1": {"type": "event_escalates", "details": "Situation worsens significantly"}
        }
    }


# Template selector mapping
TEMPLATE_SELECTORS = {
    "npc_conversation": get_npc_conversation_template,
    "environmental_discovery": get_environmental_discovery_template,
    "combat": get_combat_template,
    "riddle": get_riddle_template,
    "cipher": get_riddle_template,  # Same as riddle
    "memory_game": get_riddle_template,
    "strategy_game": get_riddle_template,
    "mathematical_puzzle": get_riddle_template,
    "lateral_thinking": get_riddle_template,
    "moral_dilemma": get_moral_dilemma_template,
    "purpose_quest": get_moral_dilemma_template,
    "value_conflict": get_moral_dilemma_template,
    "sacrifice_decision": get_moral_dilemma_template,
    "forgiveness_scenario": get_moral_dilemma_template,
    "faith_test": get_moral_dilemma_template,
    "craft_mastery": get_craft_mastery_template,
    "professional_puzzle": get_craft_mastery_template,
    "skill_competition": get_craft_mastery_template,
    "innovation_challenge": get_craft_mastery_template,
    "apprenticeship_test": get_craft_mastery_template,
    "quality_control": get_craft_mastery_template,
    "dynamic_event": get_dynamic_event_template
}


def get_template_for_interaction(
    interaction_type: str,
    challenge_type: str,
    entity_data: Dict[str, Any]
) -> RubricData:
    """
    Get appropriate template for an interaction.

    Args:
        interaction_type: Type of interaction (npc_conversation, challenge, etc.)
        challenge_type: Specific challenge type (riddle, combat, etc.) if applicable
        entity_data: Entity data

    Returns:
        RubricData template
    """
    try:
        # For challenges, use challenge_type to select template
        if interaction_type == "challenge" and challenge_type:
            selector = TEMPLATE_SELECTORS.get(challenge_type)
            if selector:
                return selector(entity_data)

        # Otherwise use interaction_type
        selector = TEMPLATE_SELECTORS.get(interaction_type)
        if selector:
            return selector(entity_data)

        # Fallback to NPC conversation template
        logger.warning(f"No template found for {interaction_type}/{challenge_type}, using NPC template")
        return get_npc_conversation_template(entity_data)

    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        return get_npc_conversation_template(entity_data)
