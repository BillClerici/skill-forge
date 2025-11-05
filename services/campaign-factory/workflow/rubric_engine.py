"""
Rubric Engine for Campaign Factory
Evaluates player performance and distributes rewards

Phase 3: Rubric-based evaluation system
"""
import logging
import json
from typing import Dict, Any, List, Tuple, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .state import (
    RubricData,
    RubricCriterion,
    KnowledgeData,
    ItemData,
    CharacterDevelopmentProfile
)

logger = logging.getLogger(__name__)

# Pydantic models for structured output
class PerformanceLevel(BaseModel):
    """Performance level within a criterion"""
    level: int = Field(description="Level number (1-4)", ge=1, le=4)
    description: str = Field(description="Description of this performance level")

class EvaluationCriterion(BaseModel):
    """Evaluation criterion for rubric"""
    criterion: str = Field(description="Name of the criterion")
    weight: float = Field(description="Weight of this criterion (0-1)", ge=0, le=1)
    bloom_level_target: int = Field(description="Target Bloom's taxonomy level (1-6)", ge=1, le=6)
    levels: List[PerformanceLevel] = Field(description="4 performance levels", min_length=4, max_length=4)

class DimensionalReward(BaseModel):
    """Dimensional reward structure"""
    bloom_target: int = Field(description="Target Bloom's level", ge=1, le=6)
    experience_by_score: Dict[str, int] = Field(description="XP by performance level")

class ConsequenceDetails(BaseModel):
    """Consequence details for a performance level"""
    type: str = Field(description="Type of consequence")
    details: str = Field(description="Details of consequence")

class RubricResponse(BaseModel):
    """Structured response for rubric generation"""
    primary_dimension: str = Field(description="Primary developmental dimension")
    secondary_dimensions: List[str] = Field(default_factory=list, description="Secondary dimensions")
    evaluation_criteria: List[EvaluationCriterion] = Field(description="Evaluation criteria", min_length=3, max_length=5)
    knowledge_level_mapping: Dict[str, int] = Field(description="Score range to level mapping")
    rewards_by_performance: Dict[str, Dict[str, List[str]]] = Field(description="Rewards by performance level")
    dimensional_rewards: Dict[str, DimensionalReward] = Field(description="Dimensional XP rewards")
    consequences_by_performance: Optional[Dict[str, ConsequenceDetails]] = Field(default=None, description="Consequences by level")

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0.7,
    max_tokens=4096
)


async def generate_rubric_for_interaction(
    interaction_type: str,
    entity_data: Dict[str, Any],
    context: Dict[str, Any],
    state: Dict[str, Any]
) -> RubricData:
    """
    AI-generates a customized rubric for a specific interaction.

    Args:
        interaction_type: Type of interaction (npc_conversation, environmental_discovery, challenge, dynamic_event)
        entity_data: Data about the entity (NPC, discovery, challenge, event)
        context: Additional context (quest, scene, campaign objectives)
        state: Campaign workflow state

    Returns:
        RubricData with weighted criteria and reward mappings
    """
    try:
        logger.info(f"Generating rubric for {interaction_type}: {entity_data.get('name', 'Unknown')}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in educational assessment and RPG game design.

Your task is to create an evaluation rubric for a specific player interaction. The rubric should:

1. Have 3-5 weighted evaluation criteria (weights must sum to 1.0)
2. Each criterion has 4 performance levels (1=Poor, 2=Fair, 3=Good, 4=Excellent)
3. Target specific Bloom's Taxonomy levels for each criterion
4. Map to one or more of the 7 developmental dimensions:
   - Physical: Body coordination, strength, endurance, reflexes
   - Emotional: Self-awareness, empathy, stress management, relationship skills
   - Intellectual: Critical thinking, problem-solving, memory, analysis
   - Social: Communication, cooperation, leadership, cultural awareness
   - Spiritual: Purpose, values, ethics, meaning-making
   - Vocational: Skill mastery, craftsmanship, professional competence
   - Environmental: Ecological awareness, resource management, sustainability

5. Define what knowledge/items are earned at each performance level

Return your response as a JSON object with this structure:
{{
  "primary_dimension": "intellectual",
  "secondary_dimensions": ["social"],
  "evaluation_criteria": [
    {{
      "criterion": "Problem Analysis",
      "weight": 0.4,
      "bloom_level_target": 4,
      "levels": [
        {{"level": 1, "description": "Minimal analysis, misses key details"}},
        {{"level": 2, "description": "Basic analysis, identifies some patterns"}},
        {{"level": 3, "description": "Good analysis, connects multiple clues"}},
        {{"level": 4, "description": "Excellent analysis, synthesizes all information"}}
      ]
    }}
  ],
  "knowledge_level_mapping": {{
    "1.0-1.75": 1,
    "1.76-2.5": 2,
    "2.51-3.25": 3,
    "3.26-4.0": 4
  }},
  "rewards_by_performance": {{
    "knowledge": {{
      "1": ["knowledge_name_1:level_1"],
      "2": ["knowledge_name_1:level_2"],
      "3": ["knowledge_name_1:level_3", "knowledge_name_2:level_1"],
      "4": ["knowledge_name_1:level_4", "knowledge_name_2:level_2"]
    }},
    "items": {{
      "3": ["item_name_1"],
      "4": ["item_name_1", "item_name_2"]
    }}
  }},
  "dimensional_rewards": {{
    "intellectual": {{
      "bloom_target": 4,
      "experience_by_score": {{"1": 10, "2": 25, "3": 50, "4": 100}}
    }},
    "social": {{
      "bloom_target": 3,
      "experience_by_score": {{"1": 5, "2": 15, "3": 30, "4": 60}}
    }}
  }},
  "consequences_by_performance": {{
    "1": {{"type": "knowledge_denied", "details": "Missed opportunity to learn"}},
    "2": {{"type": "partial_learning", "details": "Learned some but not all"}}
  }}
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """Interaction Type: {interaction_type}

Entity Details:
Name: {entity_name}
Description: {entity_description}
Type/Category: {entity_category}
Difficulty: {difficulty}

Context:
Quest: {quest_name}
Scene: {scene_name}
Campaign Objectives: {campaign_objectives}
Available Knowledge: {available_knowledge}
Available Items: {available_items}

Generate a customized rubric that evaluates player performance in this interaction.""")
        ])

        # Prepare context data
        entity_name = entity_data.get("name", "Unknown")
        entity_description = entity_data.get("description", "")
        entity_category = entity_data.get("challenge_category") or entity_data.get("event_type") or entity_data.get("knowledge_type") or "general"
        difficulty = entity_data.get("difficulty", "Medium")

        quest_name = context.get("quest", {}).get("name", "Unknown Quest")
        scene_name = context.get("scene", {}).get("name", "Unknown Scene")

        campaign_objectives_str = "\n".join([
            f"- {obj.get('description', 'Unnamed objective')}"
            for obj in context.get("campaign_objectives", [])
        ])

        available_knowledge_str = "\n".join([
            f"- {kg.get('name', 'Unknown')} ({kg.get('knowledge_type', 'skill')})"
            for kg in context.get("available_knowledge", [])[:5]  # Limit to 5 for brevity
        ])

        available_items_str = "\n".join([
            f"- {item.get('name', 'Unknown')} ({item.get('item_type', 'tool')})"
            for item in context.get("available_items", [])[:5]  # Limit to 5 for brevity
        ])

        # Generate rubric with structured output
        structured_llm = anthropic_client.with_structured_output(RubricResponse, include_raw=False)
        chain = prompt | structured_llm
        rubric_response: RubricResponse = await chain.ainvoke({
            "interaction_type": interaction_type,
            "entity_name": entity_name,
            "entity_description": entity_description,
            "entity_category": entity_category,
            "difficulty": difficulty,
            "quest_name": quest_name,
            "scene_name": scene_name,
            "campaign_objectives": campaign_objectives_str,
            "available_knowledge": available_knowledge_str,
            "available_items": available_items_str
        })

        # Convert Pydantic model to dict
        rubric_raw = rubric_response.model_dump()

        # Create RubricData
        rubric: RubricData = {
            "rubric_id": f"rubric_{interaction_type}_{entity_data.get('id', 'unknown')}",
            "rubric_type": interaction_type,
            "interaction_name": entity_name,
            "entity_id": entity_data.get("id", ""),
            "primary_dimension": rubric_raw.get("primary_dimension", "intellectual"),
            "secondary_dimensions": rubric_raw.get("secondary_dimensions", []),
            "evaluation_criteria": rubric_raw.get("evaluation_criteria", []),
            "knowledge_level_mapping": rubric_raw.get("knowledge_level_mapping", {}),
            "rewards_by_performance": rubric_raw.get("rewards_by_performance", {}),
            "dimensional_rewards": rubric_raw.get("dimensional_rewards", {}),
            "consequences_by_performance": rubric_raw.get("consequences_by_performance", None)
        }

        logger.info(f"Generated rubric with {len(rubric['evaluation_criteria'])} criteria")
        return rubric

    except Exception as e:
        logger.error(f"Error generating rubric: {str(e)}")
        # Return a basic fallback rubric
        return _create_fallback_rubric(interaction_type, entity_data)


def calculate_rubric_score(
    rubric: RubricData,
    player_actions: Dict[str, Any]
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate weighted average score from player performance.

    Args:
        rubric: The evaluation rubric
        player_actions: Dict mapping criterion names to performance levels (1-4)

    Returns:
        Tuple of (total_score, criterion_scores)
    """
    try:
        criterion_scores = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for criterion in rubric["evaluation_criteria"]:
            criterion_name = criterion["criterion"]
            weight = criterion["weight"]

            # Get player's performance level for this criterion
            performance_level = player_actions.get(criterion_name, 1)  # Default to 1 (Poor)

            # Clamp to valid range
            performance_level = max(1, min(4, performance_level))

            criterion_scores[criterion_name] = float(performance_level)
            weighted_sum += performance_level * weight
            total_weight += weight

        # Calculate weighted average
        total_score = weighted_sum / total_weight if total_weight > 0 else 1.0

        logger.info(f"Rubric score: {total_score:.2f} (weights: {total_weight})")
        return total_score, criterion_scores

    except Exception as e:
        logger.error(f"Error calculating rubric score: {str(e)}")
        return 1.0, {}


def distribute_rewards(
    rubric: RubricData,
    score: float,
    available_knowledge: List[KnowledgeData],
    available_items: List[ItemData]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Determine knowledge levels and items earned based on score.

    Args:
        rubric: The evaluation rubric
        score: Player's total score (1.0-4.0)
        available_knowledge: All available knowledge entities
        available_items: All available item entities

    Returns:
        Dict with 'knowledge' and 'items' lists
    """
    try:
        # Determine performance level from score
        performance_level = _score_to_performance_level(score, rubric["knowledge_level_mapping"])

        logger.info(f"Score {score:.2f} maps to performance level {performance_level}")

        # Get rewards for this performance level
        rewards = {
            "knowledge": [],
            "items": []
        }

        # Knowledge rewards
        knowledge_rewards = rubric["rewards_by_performance"].get("knowledge", {})
        for level in range(1, performance_level + 1):
            level_key = str(level)
            if level_key in knowledge_rewards:
                for kg_spec in knowledge_rewards[level_key]:
                    # Parse "knowledge_name:level" format
                    if ":" in kg_spec:
                        kg_name, kg_level = kg_spec.split(":", 1)
                        rewards["knowledge"].append({
                            "name": kg_name.strip(),
                            "level": int(kg_level)
                        })
                    else:
                        rewards["knowledge"].append({
                            "name": kg_spec.strip(),
                            "level": performance_level
                        })

        # Item rewards
        item_rewards = rubric["rewards_by_performance"].get("items", {})
        for level in range(1, performance_level + 1):
            level_key = str(level)
            if level_key in item_rewards:
                for item_name in item_rewards[level_key]:
                    rewards["items"].append({
                        "name": item_name.strip(),
                        "quantity": 1
                    })

        logger.info(f"Distributed {len(rewards['knowledge'])} knowledge, {len(rewards['items'])} items")
        return rewards

    except Exception as e:
        logger.error(f"Error distributing rewards: {str(e)}")
        return {"knowledge": [], "items": []}


def calculate_dimensional_experience(
    rubric: RubricData,
    score: float,
    criterion_scores: Dict[str, float]
) -> Dict[str, int]:
    """
    Calculate experience points for each dimension based on criterion-level performance.

    This function uses a more granular approach:
    1. Maps each criterion to relevant dimensions
    2. Awards XP based on individual criterion scores
    3. Aggregates XP across all criteria for each dimension

    Args:
        rubric: The evaluation rubric
        score: Player's total score (1.0-4.0)
        criterion_scores: Scores for each criterion (e.g., {"Rapport Building": 3.0})

    Returns:
        Dict mapping dimension names to experience points
    """
    try:
        experience = {}

        # Get criterion-to-dimension mapping
        criterion_mapping = _get_criterion_dimension_mapping(rubric["rubric_type"])

        # Award XP for each criterion
        for criterion_name, criterion_score in criterion_scores.items():
            # Get dimensions affected by this criterion
            affected_dimensions = criterion_mapping.get(criterion_name, [])

            if not affected_dimensions:
                # Fallback to rubric's primary/secondary dimensions
                affected_dimensions = [rubric["primary_dimension"]] + rubric.get("secondary_dimensions", [])

            # Convert score to XP amount
            # Score 1 = +5 XP, Score 2 = +15 XP, Score 3 = +35 XP, Score 4 = +70 XP
            xp_amount = _score_to_experience_amount(int(criterion_score))

            # Distribute XP to affected dimensions
            for dimension in affected_dimensions:
                if dimension not in experience:
                    experience[dimension] = 0
                experience[dimension] += xp_amount

        # Also add base dimensional rewards from rubric (for backward compatibility)
        dimensional_rewards = rubric.get("dimensional_rewards", {})
        performance_level = _score_to_performance_level(score, rubric["knowledge_level_mapping"])

        for dimension, reward_data in dimensional_rewards.items():
            exp_by_score = reward_data.get("experience_by_score", {})
            level_key = str(performance_level)

            if level_key in exp_by_score:
                bonus_exp = exp_by_score[level_key]
                if dimension not in experience:
                    experience[dimension] = 0
                # Add bonus (but don't double-count if already awarded above)
                # Use max to prevent double-counting
                experience[dimension] = max(experience[dimension], bonus_exp)

        logger.info(f"Dimensional experience awarded: {experience}")
        return experience

    except Exception as e:
        logger.error(f"Error calculating dimensional experience: {str(e)}")
        return {}


def _get_criterion_dimension_mapping(rubric_type: str) -> Dict[str, List[str]]:
    """
    Get mapping of criterion names to dimensions for a specific rubric type.

    Args:
        rubric_type: Type of rubric (npc_conversation, challenge, etc.)

    Returns:
        Dict mapping criterion names to list of dimension names
    """
    # NPC Conversation criterion mappings
    if rubric_type == "npc_conversation":
        return {
            "Rapport Building": ["social", "emotional"],
            "Information Gathering": ["intellectual", "social"],
            "Emotional Intelligence": ["emotional", "social"],
            "Dialogue Choices": ["social", "intellectual"],
            "Relationship Building": ["social", "emotional"],
            "Question Quality": ["intellectual", "social"],
            "Active Listening": ["emotional", "social"],
            "Context Understanding": ["intellectual", "social"]
        }

    # Environmental Discovery criterion mappings
    elif rubric_type == "environmental_discovery":
        return {
            "Observation": ["intellectual", "environmental"],
            "Pattern Recognition": ["intellectual", "environmental"],
            "Environmental Context": ["environmental", "intellectual"],
            "Observation Detail": ["intellectual", "environmental"],
            "Investigation Method": ["intellectual", "vocational"],
            "Knowledge Application": ["intellectual", "vocational"]
        }

    # Challenge criterion mappings
    elif rubric_type == "challenge":
        return {
            # Combat-related
            "Combat Execution": ["physical", "vocational"],
            "Tactical Thinking": ["intellectual", "physical"],
            "Stress Management": ["emotional", "physical"],
            "Team Coordination": ["social", "emotional"],
            # Puzzle/Riddle-related
            "Logical Reasoning": ["intellectual"],
            "Lateral Thinking": ["intellectual"],
            "Persistence": ["emotional", "vocational"],
            # Moral Dilemma-related
            "Ethical Reasoning": ["spiritual", "intellectual"],
            "Empathy for All Parties": ["emotional", "spiritual"],
            "Values Consistency": ["spiritual"],
            # Craft-related
            "Technical Skill": ["vocational", "physical"],
            "Precision & Attention to Detail": ["vocational", "physical"],
            "Technical Knowledge": ["intellectual", "vocational"],
            # General challenge criteria
            "Problem Solving": ["intellectual", "vocational"],
            "Resource Management": ["environmental", "vocational"],
            "Risk Assessment": ["intellectual", "physical"],
            "Adaptability": ["emotional", "intellectual"]
        }

    # Dynamic Event criterion mappings
    elif rubric_type == "dynamic_event":
        return {
            "Adaptability": ["emotional", "intellectual"],
            "Quick Thinking": ["intellectual", "physical"],
            "Risk Assessment": ["intellectual", "emotional"],
            "Situation Assessment": ["intellectual", "emotional"],
            "Decision Speed": ["emotional", "physical"],
            "Action Effectiveness": ["physical", "vocational"],
            "Ethical Considerations": ["spiritual", "social"]
        }

    # Default: return empty mapping (will use rubric's primary/secondary dimensions)
    return {}


def _score_to_experience_amount(score: int) -> int:
    """
    Convert a criterion score (1-4) to an experience point amount.

    Args:
        score: Performance score (1-4)

    Returns:
        Experience points
    """
    xp_mapping = {
        1: 5,    # Beginning
        2: 15,   # Developing
        3: 35,   # Proficient
        4: 70    # Exemplary
    }
    return xp_mapping.get(score, 5)


def _score_to_performance_level(score: float, mapping: Dict[str, int]) -> int:
    """
    Convert a score (1.0-4.0) to a performance level (1-4) using the rubric's mapping.

    Args:
        score: Score between 1.0 and 4.0
        mapping: Dict mapping score ranges to levels (e.g., "1.0-1.75": 1)

    Returns:
        Performance level (1-4)
    """
    try:
        for range_str, level in mapping.items():
            # Parse range string (e.g., "1.0-1.75")
            if "-" in range_str:
                min_score, max_score = range_str.split("-")
                min_score = float(min_score)
                max_score = float(max_score)

                if min_score <= score <= max_score:
                    return level

        # Default fallback
        return min(4, max(1, int(round(score))))

    except Exception as e:
        logger.error(f"Error converting score to performance level: {str(e)}")
        return min(4, max(1, int(round(score))))


def _create_fallback_rubric(interaction_type: str, entity_data: Dict[str, Any]) -> RubricData:
    """
    Create a basic fallback rubric if AI generation fails.

    Args:
        interaction_type: Type of interaction
        entity_data: Entity data

    Returns:
        Basic RubricData
    """
    return {
        "rubric_id": f"rubric_fallback_{interaction_type}",
        "rubric_type": interaction_type,
        "interaction_name": entity_data.get("name", "Unknown"),
        "entity_id": entity_data.get("id", ""),
        "primary_dimension": "intellectual",
        "secondary_dimensions": [],
        "evaluation_criteria": [
            {
                "criterion": "Overall Performance",
                "weight": 1.0,
                "bloom_level_target": 3,
                "levels": [
                    {"level": 1, "description": "Poor performance"},
                    {"level": 2, "description": "Fair performance"},
                    {"level": 3, "description": "Good performance"},
                    {"level": 4, "description": "Excellent performance"}
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
            "knowledge": {},
            "items": {}
        },
        "dimensional_rewards": {
            "intellectual": {
                "bloom_target": 3,
                "experience_by_score": {"1": 10, "2": 25, "3": 50, "4": 100}
            }
        },
        "consequences_by_performance": None
    }


def process_rubric_result_and_award_progression(
    rubric: RubricData,
    score: float,
    criterion_scores: Dict[str, float],
    profile: CharacterDevelopmentProfile,
    available_knowledge: List[KnowledgeData],
    available_items: List[ItemData],
    source: str = "interaction"
) -> CharacterDevelopmentProfile:
    """
    Comprehensive function to process rubric results and update character progression.

    This function:
    1. Calculates dimensional experience from rubric scores
    2. Awards dimensional XP and handles level-ups
    3. Distributes knowledge and item rewards
    4. Returns the updated character profile

    Args:
        rubric: The evaluation rubric
        score: Player's total score (1.0-4.0)
        criterion_scores: Scores for each criterion
        profile: Character's development profile
        available_knowledge: Available knowledge entities
        available_items: Available item entities
        source: Source identifier for tracking (e.g., "scene_123")

    Returns:
        Updated CharacterDevelopmentProfile
    """
    try:
        from . import progression_tracker

        logger.info(f"Processing rubric result for {profile['character_id']}: Score {score:.2f}")

        # 1. Calculate and award dimensional experience
        dimensional_exp = calculate_dimensional_experience(rubric, score, criterion_scores)

        for dimension, exp in dimensional_exp.items():
            profile = progression_tracker.add_dimensional_experience(profile, dimension, exp)
            logger.info(f"Awarded {exp} XP to {dimension} dimension")

        # 2. Distribute knowledge and item rewards
        rewards = distribute_rewards(rubric, score, available_knowledge, available_items)

        # Award knowledge
        for kg_reward in rewards["knowledge"]:
            kg_name = kg_reward["name"]
            kg_level = kg_reward["level"]
            kg_id = f"kg_{kg_name.lower().replace(' ', '_')}"

            profile = progression_tracker.award_knowledge(
                profile,
                kg_id,
                kg_name,
                kg_level,
                source=f"{rubric['rubric_type']}_{source}"
            )

        # Award items
        for item_reward in rewards["items"]:
            item_name = item_reward["name"]
            item_qty = item_reward.get("quantity", 1)
            item_id = f"item_{item_name.lower().replace(' ', '_')}"

            profile = progression_tracker.award_item(
                profile,
                item_id,
                item_name,
                item_qty,
                source=f"{rubric['rubric_type']}_{source}"
            )

        logger.info(f"Rubric result processed successfully for {profile['character_id']}")
        return profile

    except Exception as e:
        logger.error(f"Error processing rubric result: {str(e)}")
        return profile


def validate_rubric(rubric: RubricData) -> Tuple[bool, str]:
    """
    Validate that a rubric is well-formed.

    Checks:
    - Weights sum to 1.0
    - All criteria have 4 levels
    - Valid dimension names
    - Valid Bloom's levels

    Args:
        rubric: Rubric to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check weights sum to 1.0
        total_weight = sum(c["weight"] for c in rubric["evaluation_criteria"])
        if abs(total_weight - 1.0) > 0.01:
            return False, f"Weights sum to {total_weight}, should be 1.0"

        # Check all criteria have 4 levels
        for criterion in rubric["evaluation_criteria"]:
            if len(criterion["levels"]) != 4:
                return False, f"Criterion '{criterion['criterion']}' has {len(criterion['levels'])} levels, should have 4"

        # Check valid dimensions
        valid_dimensions = ["physical", "emotional", "intellectual", "social", "spiritual", "vocational", "environmental"]
        if rubric["primary_dimension"] not in valid_dimensions:
            return False, f"Invalid primary dimension: {rubric['primary_dimension']}"

        for dim in rubric["secondary_dimensions"]:
            if dim not in valid_dimensions:
                return False, f"Invalid secondary dimension: {dim}"

        # Check Bloom's levels (1-6)
        for criterion in rubric["evaluation_criteria"]:
            bloom_level = criterion["bloom_level_target"]
            if bloom_level < 1 or bloom_level > 6:
                return False, f"Invalid Bloom's level {bloom_level} for criterion '{criterion['criterion']}'"

        return True, ""

    except Exception as e:
        return False, f"Validation error: {str(e)}"


# ==============================================================================
# WORKFLOW NODE FOR CHILD OBJECTIVES RUBRIC ASSIGNMENT
# ==============================================================================

async def assign_objective_rubrics_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Workflow node: Create rubrics for all child objectives

    This node:
    1. For each child objective, generates a customized rubric
    2. Uses templates for each objective type (discovery, challenge, event, conversation)
    3. Links rubrics to objectives
    4. Validates all rubrics
    5. Returns updated state with rubrics

    Args:
        state: Campaign workflow state

    Returns:
        Updated state with rubrics list
    """
    from .utils import add_audit_entry, publish_progress
    import uuid

    print("\n📊 Creating Rubrics for Child Objectives...")

    try:
        child_objectives = state.get("child_objectives", [])
        if not child_objectives:
            print("  ⚠️  No child objectives found")
            return {"warnings": ["No child objectives to create rubrics for"]}

        rubrics = []
        rubric_mapping = {}  # child_obj_id -> rubric_id

        total_objectives = len(child_objectives)
        for idx, child_obj in enumerate(child_objectives):
            obj_type = child_obj["objective_type"]
            obj_id = child_obj["objective_id"]

            print(f"  Creating rubric {idx + 1}/{total_objectives}: {obj_type} - {child_obj['description'][:50]}...")

            # Create rubric based on type
            if obj_type == "discovery":
                rubric = _create_discovery_rubric(child_obj, state)
            elif obj_type == "challenge":
                rubric = _create_challenge_rubric(child_obj, state)
            elif obj_type == "event":
                rubric = _create_event_rubric(child_obj, state)
            elif obj_type == "conversation":
                rubric = _create_conversation_rubric(child_obj, state)
            else:
                print(f"    ⚠️  Unknown objective type: {obj_type}, using fallback")
                rubric = _create_fallback_rubric(obj_type, child_obj)

            # Validate rubric
            is_valid, error_msg = validate_rubric(rubric)
            if not is_valid:
                print(f"    ⚠️  Rubric validation failed: {error_msg}, adjusting...")
                rubric = _fix_rubric(rubric)

            rubrics.append(rubric)
            rubric_mapping[obj_id] = rubric["rubric_id"]

            # Update child objective with rubric ID
            child_obj["rubric_ids"] = [rubric["rubric_id"]]

            print(f"    ✅ Rubric created: {rubric['rubric_id']}")

        print(f"\n✅ Rubrics Created: {len(rubrics)} total")
        print(f"   - Discovery: {sum(1 for r in rubrics if r['rubric_type'] == 'environmental_discovery')}")
        print(f"   - Challenge: {sum(1 for r in rubrics if r['rubric_type'] == 'challenge')}")
        print(f"   - Event: {sum(1 for r in rubrics if r['rubric_type'] == 'dynamic_event')}")
        print(f"   - Conversation: {sum(1 for r in rubrics if r['rubric_type'] == 'npc_conversation')}")

        # Log audit
        add_audit_entry(
            state,
            "assign_objective_rubrics",
            f"Created {len(rubrics)} rubrics for child objectives",
            status="success"
        )

        # Update progress
        state["progress_percentage"] = 40
        state["status_message"] = "Objective rubrics assigned"

        # Publish progress
        await publish_progress(state, "Objective rubrics assigned")

        return {
            "rubrics": rubrics,
            "child_objectives": child_objectives,  # Updated with rubric IDs
            "progress_percentage": 40,
            "current_node": "assign_objective_rubrics"
        }

    except Exception as e:
        print(f"\n❌ Error creating rubrics: {e}")
        return {
            "errors": [f"Rubric creation failed: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1
        }


def _create_discovery_rubric(child_obj: Dict[str, Any], state: Dict[str, Any]) -> RubricData:
    """Create rubric for discovery-type child objective"""
    import uuid

    rubric: RubricData = {
        "rubric_id": f"rubric_{uuid.uuid4().hex[:8]}",
        "rubric_type": "environmental_discovery",
        "interaction_name": child_obj["description"],
        "entity_id": child_obj.get("discovery_entity_id", child_obj["objective_id"]),
        "primary_dimension": "environmental",
        "secondary_dimensions": ["intellectual"],
        "evaluation_criteria": [
            {
                "criterion": "Thoroughness of Exploration",
                "weight": 0.3,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Superficial search, missed key details"},
                    {"level": 2, "description": "Basic search, found some elements"},
                    {"level": 3, "description": "Methodical search, thorough exploration"},
                    {"level": 4, "description": "Exhaustive search, expert attention to detail"}
                ]
            },
            {
                "criterion": "Understanding of Discovery",
                "weight": 0.4,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Minimal understanding, missed significance"},
                    {"level": 2, "description": "Basic understanding, grasped main points"},
                    {"level": 3, "description": "Good understanding, connected to context"},
                    {"level": 4, "description": "Deep understanding, synthesized with prior knowledge"}
                ]
            },
            {
                "criterion": "Environmental Awareness",
                "weight": 0.3,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Ignored environmental cues"},
                    {"level": 2, "description": "Noticed some environmental details"},
                    {"level": 3, "description": "Good awareness of surroundings"},
                    {"level": 4, "description": "Exceptional environmental awareness and pattern recognition"}
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
                "1": ["discovery_basic:level_1"],
                "2": ["discovery_basic:level_2"],
                "3": ["discovery_basic:level_3", "contextual_knowledge:level_1"],
                "4": ["discovery_basic:level_4", "contextual_knowledge:level_2"]
            },
            "items": {
                "3": ["discovered_item"],
                "4": ["discovered_item", "bonus_item"]
            }
        },
        "dimensional_rewards": {
            "environmental": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 5, "2": 15, "3": 30, "4": 60}
            },
            "intellectual": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 3, "2": 8, "3": 15, "4": 30}
            }
        },
        "consequences_by_performance": None
    }

    return rubric


def _create_challenge_rubric(child_obj: Dict[str, Any], state: Dict[str, Any]) -> RubricData:
    """Create rubric for challenge-type child objective"""
    import uuid

    rubric: RubricData = {
        "rubric_id": f"rubric_{uuid.uuid4().hex[:8]}",
        "rubric_type": "challenge",
        "interaction_name": child_obj["description"],
        "entity_id": child_obj.get("challenge_entity_id", child_obj["objective_id"]),
        "primary_dimension": "intellectual",
        "secondary_dimensions": ["vocational"],
        "evaluation_criteria": [
            {
                "criterion": "Problem-Solving Approach",
                "weight": 0.35,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Trial-and-error, no clear strategy"},
                    {"level": 2, "description": "Basic strategy, some logical steps"},
                    {"level": 3, "description": "Methodical approach, clear reasoning"},
                    {"level": 4, "description": "Strategic approach, optimal solution path"}
                ]
            },
            {
                "criterion": "Use of Available Knowledge",
                "weight": 0.35,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Ignored relevant knowledge"},
                    {"level": 2, "description": "Applied some relevant knowledge"},
                    {"level": 3, "description": "Effectively applied knowledge"},
                    {"level": 4, "description": "Synthesized multiple knowledge domains"}
                ]
            },
            {
                "criterion": "Creativity and Innovation",
                "weight": 0.3,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Rigid thinking, no alternatives"},
                    {"level": 2, "description": "Considered some alternatives"},
                    {"level": 3, "description": "Creative thinking, multiple approaches"},
                    {"level": 4, "description": "Innovative solution, exceptional creativity"}
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
                "1": ["problem_solving_basic:level_1"],
                "2": ["problem_solving_basic:level_2"],
                "3": ["problem_solving_basic:level_3", "strategic_thinking:level_1"],
                "4": ["problem_solving_basic:level_4", "strategic_thinking:level_2"]
            },
            "items": {
                "3": ["puzzle_reward"],
                "4": ["puzzle_reward", "mastery_token"]
            }
        },
        "dimensional_rewards": {
            "intellectual": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 10, "2": 25, "3": 50, "4": 100}
            },
            "vocational": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 5, "2": 12, "3": 25, "4": 50}
            }
        },
        "consequences_by_performance": None
    }

    return rubric


def _create_event_rubric(child_obj: Dict[str, Any], state: Dict[str, Any]) -> RubricData:
    """Create rubric for event-type child objective"""
    import uuid

    rubric: RubricData = {
        "rubric_id": f"rubric_{uuid.uuid4().hex[:8]}",
        "rubric_type": "dynamic_event",
        "interaction_name": child_obj["description"],
        "entity_id": child_obj.get("event_entity_id", child_obj["objective_id"]),
        "primary_dimension": "social",
        "secondary_dimensions": ["emotional"],
        "evaluation_criteria": [
            {
                "criterion": "Level of Engagement",
                "weight": 0.35,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Passive observation, minimal participation"},
                    {"level": 2, "description": "Basic participation, followed instructions"},
                    {"level": 3, "description": "Active participation, contributed meaningfully"},
                    {"level": 4, "description": "Led or significantly influenced the event"}
                ]
            },
            {
                "criterion": "Appropriateness of Actions",
                "weight": 0.35,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Inappropriate actions, disrupted event"},
                    {"level": 2, "description": "Generally appropriate, minor missteps"},
                    {"level": 3, "description": "Appropriate and respectful actions"},
                    {"level": 4, "description": "Exemplary conduct, enhanced the event"}
                ]
            },
            {
                "criterion": "Impact on Outcome",
                "weight": 0.3,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "No positive impact"},
                    {"level": 2, "description": "Small positive impact"},
                    {"level": 3, "description": "Significant positive impact"},
                    {"level": 4, "description": "Transformative impact on event outcome"}
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
                "1": ["event_experience:level_1"],
                "2": ["event_experience:level_2"],
                "3": ["event_experience:level_3", "social_dynamics:level_1"],
                "4": ["event_experience:level_4", "social_dynamics:level_2"]
            },
            "items": {
                "3": ["event_memento"],
                "4": ["event_memento", "special_recognition"]
            }
        },
        "dimensional_rewards": {
            "social": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 8, "2": 20, "3": 40, "4": 80}
            },
            "emotional": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 5, "2": 12, "3": 25, "4": 50}
            }
        },
        "consequences_by_performance": None
    }

    return rubric


def _create_conversation_rubric(child_obj: Dict[str, Any], state: Dict[str, Any]) -> RubricData:
    """Create rubric for conversation-type child objective"""
    import uuid

    rubric: RubricData = {
        "rubric_id": f"rubric_{uuid.uuid4().hex[:8]}",
        "rubric_type": "npc_conversation",
        "interaction_name": child_obj["description"],
        "entity_id": child_obj.get("npc_id", child_obj["objective_id"]),
        "primary_dimension": "social",
        "secondary_dimensions": ["emotional", "intellectual"],
        "evaluation_criteria": [
            {
                "criterion": "Active Listening",
                "weight": 0.25,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Ignored NPC's information"},
                    {"level": 2, "description": "Listened but missed nuances"},
                    {"level": 3, "description": "Actively engaged with NPC's points"},
                    {"level": 4, "description": "Deep engagement, insightful responses"}
                ]
            },
            {
                "criterion": "Question Quality",
                "weight": 0.3,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "No relevant questions asked"},
                    {"level": 2, "description": "Basic questions, missed opportunities"},
                    {"level": 3, "description": "Relevant, well-timed questions"},
                    {"level": 4, "description": "Insightful, probing questions that deepen understanding"}
                ]
            },
            {
                "criterion": "Rapport Building",
                "weight": 0.25,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Antagonistic or dismissive"},
                    {"level": 2, "description": "Neutral, transactional interaction"},
                    {"level": 3, "description": "Built positive rapport"},
                    {"level": 4, "description": "Established strong connection and trust"}
                ]
            },
            {
                "criterion": "Achievement of Conversation Goal",
                "weight": 0.2,
                "bloom_level_target": child_obj["bloom_level"],
                "levels": [
                    {"level": 1, "description": "Goal not achieved"},
                    {"level": 2, "description": "Partial achievement of goal"},
                    {"level": 3, "description": "Goal achieved effectively"},
                    {"level": 4, "description": "Goal exceeded, gained additional insights"}
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
                "1": ["basic_info:level_1"],
                "2": ["basic_info:level_2"],
                "3": ["basic_info:level_3", "deeper_knowledge:level_1"],
                "4": ["basic_info:level_4", "deeper_knowledge:level_2", "secret_knowledge:level_1"]
            },
            "items": {
                "3": ["npc_gift"],
                "4": ["npc_gift", "special_item"]
            }
        },
        "dimensional_rewards": {
            "social": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 10, "2": 25, "3": 50, "4": 100}
            },
            "emotional": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 5, "2": 12, "3": 25, "4": 50}
            },
            "intellectual": {
                "bloom_target": child_obj["bloom_level"],
                "experience_by_score": {"1": 5, "2": 12, "3": 25, "4": 50}
            }
        },
        "consequences_by_performance": None
    }

    return rubric


def _fix_rubric(rubric: RubricData) -> RubricData:
    """Fix common rubric validation issues"""

    # Fix weights if they don't sum to 1.0
    criteria = rubric["evaluation_criteria"]
    total_weight = sum(c["weight"] for c in criteria)
    if abs(total_weight - 1.0) > 0.01:
        # Normalize weights
        for criterion in criteria:
            criterion["weight"] = criterion["weight"] / total_weight

    # Ensure all criteria have exactly 4 levels
    for criterion in criteria:
        if len(criterion["levels"]) < 4:
            # Add missing levels
            while len(criterion["levels"]) < 4:
                level_num = len(criterion["levels"]) + 1
                criterion["levels"].append({
                    "level": level_num,
                    "description": f"Level {level_num} performance"
                })
        elif len(criterion["levels"]) > 4:
            # Trim to 4 levels
            criterion["levels"] = criterion["levels"][:4]

    return rubric
