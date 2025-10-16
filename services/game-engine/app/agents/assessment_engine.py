"""
Assessment Engine Agent
Rubric-based evaluation and Bloom's Taxonomy progression tracking
"""
from typing import Dict, Any, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from datetime import datetime
import json

from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import AssessmentResult, GameSessionState

logger = get_logger(__name__)


class AssessmentEngineAgent:
    """
    AI-powered assessment engine for evaluating player performance
    """

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.3,  # Lower temperature for consistent evaluation
            max_tokens=2048
        )

        # Bloom's Taxonomy levels with cognitive descriptors
        self.blooms_levels = {
            "Remember": {
                "level": 1,
                "verbs": ["recall", "recognize", "identify", "name", "list"],
                "description": "Retrieve relevant knowledge from memory"
            },
            "Understand": {
                "level": 2,
                "verbs": ["explain", "summarize", "interpret", "classify", "compare"],
                "description": "Construct meaning from information"
            },
            "Apply": {
                "level": 3,
                "verbs": ["execute", "implement", "use", "demonstrate", "solve"],
                "description": "Use information in new situations"
            },
            "Analyze": {
                "level": 4,
                "verbs": ["differentiate", "organize", "attribute", "examine", "deconstruct"],
                "description": "Break material into parts and determine relationships"
            },
            "Evaluate": {
                "level": 5,
                "verbs": ["check", "critique", "judge", "assess", "defend"],
                "description": "Make judgments based on criteria and standards"
            },
            "Create": {
                "level": 6,
                "verbs": ["design", "construct", "plan", "produce", "invent"],
                "description": "Put elements together to form a new whole"
            }
        }

    async def assess_action(
        self,
        action: Dict[str, Any],
        outcome: Dict[str, Any],
        rubric_id: str,
        state: GameSessionState
    ) -> AssessmentResult:
        """
        Assess player action using rubric and Bloom's Taxonomy

        Args:
            action: Player action interpretation
            outcome: Action outcome
            rubric_id: Rubric identifier
            state: Game session state

        Returns:
            Assessment result with feedback
        """
        try:
            logger.info(
                "assessing_action",
                session_id=state.get("session_id"),
                rubric_id=rubric_id,
                action_type=action.get("action_type")
            )

            # Get player
            player = state.get("players", [{}])[0]
            player_id = player.get("player_id", "")

            # Build assessment prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._build_assessment_system_prompt()),
                ("user", """Assess the following player action:

ACTION:
- Type: {action_type}
- Input: "{player_input}"
- Target: {target_id}
- Success Probability: {success_probability}

OUTCOME:
{outcome}

CONTEXT:
- Current Quest: {current_quest}
- Player's Current Bloom's Level: {current_bloom_level}
- Recent Performance: {recent_performance}

RUBRIC CRITERIA:
{rubric_criteria}

Provide assessment in JSON:
{{
    "bloom_level_demonstrated": "Remember/Understand/Apply/Analyze/Evaluate/Create",
    "cognitive_reasoning": "Why this Bloom's level was demonstrated",
    "dimensional_scores": {{
        "intellectual": 0-100,
        "social": 0-100,
        "emotional": 0-100,
        "physical": 0-100,
        "vocational": 0-100,
        "spiritual": 0-100,
        "environmental": 0-100
    }},
    "performance_indicators": {{
        "criterion_1": "excellent/good/fair/poor",
        "criterion_2": "excellent/good/fair/poor"
    }},
    "strengths": ["strength 1", "strength 2"],
    "areas_for_improvement": ["area 1", "area 2"],
    "feedback_message": "Personalized encouraging feedback",
    "next_level_guidance": "How to reach next Bloom's level",
    "experience_gained": 0-50
}}""")
            ])

            # Get rubric criteria
            rubric_criteria = await self._get_rubric_criteria(rubric_id)

            # Get recent performance
            recent_performance = self._analyze_recent_performance(state)

            # Invoke LLM
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "action_type": action.get("action_type", ""),
                "player_input": action.get("player_input", ""),
                "target_id": action.get("target_id", ""),
                "success_probability": action.get("success_probability", 0.5),
                "outcome": json.dumps(outcome),
                "current_quest": state.get("current_quest_id", ""),
                "current_bloom_level": player.get("cognitive_profile", {}).get("current_bloom_tier", "Understand"),
                "recent_performance": recent_performance,
                "rubric_criteria": rubric_criteria
            })

            # Parse assessment
            assessment_data = json.loads(response.content.strip())

            # Build assessment result
            assessment: AssessmentResult = {
                "assessment_id": f"assess_{datetime.utcnow().timestamp()}",
                "player_id": player_id,
                "timestamp": datetime.utcnow().isoformat(),
                "rubric_id": rubric_id,
                "performance_indicators": assessment_data.get("performance_indicators", {}),
                "bloom_level_demonstrated": assessment_data.get("bloom_level_demonstrated", "Understand"),
                "dimensional_scores": assessment_data.get("dimensional_scores", {}),
                "strengths": assessment_data.get("strengths", []),
                "areas_for_improvement": assessment_data.get("areas_for_improvement", []),
                "feedback_message": assessment_data.get("feedback_message", "Good effort!"),
                "experience_gained": assessment_data.get("experience_gained", 10),
                "metadata": {
                    "cognitive_reasoning": assessment_data.get("cognitive_reasoning", ""),
                    "next_level_guidance": assessment_data.get("next_level_guidance", "")
                }
            }

            logger.info(
                "action_assessed",
                session_id=state.get("session_id"),
                bloom_level=assessment["bloom_level_demonstrated"],
                experience_gained=assessment["experience_gained"]
            )

            return assessment

        except Exception as e:
            logger.error(
                "assessment_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            return self._create_fallback_assessment(state)

    def _build_assessment_system_prompt(self) -> str:
        """Build system prompt for assessment"""
        return """You are an expert educational assessor for SkillForge RPG.

Your role is to:
1. Evaluate player actions using Bloom's Taxonomy
2. Assess performance across 7 human dimensions
3. Provide constructive, encouraging feedback
4. Guide players to higher cognitive levels

BLOOM'S TAXONOMY LEVELS (Lowest to Highest):
1. Remember: Recall facts, recognize information
2. Understand: Explain ideas, interpret meaning
3. Apply: Use knowledge in new situations
4. Analyze: Break down complex problems, find patterns
5. Evaluate: Make judgments, critique solutions
6. Create: Design novel solutions, synthesize ideas

SEVEN HUMAN DIMENSIONS:
1. Intellectual: Cognitive ability, problem-solving, critical thinking
2. Social: Collaboration, communication, empathy
3. Emotional: Self-awareness, emotional regulation, resilience
4. Physical: Action, coordination, spatial awareness
5. Vocational: Skill development, task completion, resourcefulness
6. Spiritual: Meaning-making, values alignment, purpose
7. Environmental: Context awareness, adaptation, systems thinking

ASSESSMENT PRINCIPLES:
- Be encouraging and constructive
- Recognize effort and progress
- Provide specific, actionable feedback
- Celebrate strengths while gently addressing weaknesses
- Guide players toward next cognitive level
- Award experience based on complexity and execution quality
- Consider player's current level when assessing

Remember: This is educational game-based learning. Assessment should inspire growth, not discourage."""

    async def _get_rubric_criteria(self, rubric_id: str) -> str:
        """Get rubric criteria (placeholder - would fetch from MCP in production)"""
        # TODO: Fetch from quest-mission MCP
        return """
Dialogue Effectiveness Rubric:
- Rapport Building: Did the player build positive relationship?
- Information Gathering: Did the player ask relevant questions?
- Empathy: Did the player show understanding of NPC's perspective?
- Goal Orientation: Did the player work toward quest objectives?
"""

    def _analyze_recent_performance(self, state: GameSessionState) -> str:
        """Analyze recent performance history"""
        assessments = state.get("assessments", [])
        if not assessments:
            return "No previous assessments available."

        recent = assessments[-3:] if len(assessments) >= 3 else assessments

        bloom_levels = [a.get("bloom_level_demonstrated", "Understand") for a in recent]
        avg_experience = sum(a.get("experience_gained", 0) for a in recent) / len(recent)

        return f"""Recent assessments: {len(recent)} actions
Bloom's levels: {', '.join(bloom_levels)}
Average XP: {avg_experience:.1f}
Trend: {"Improving" if len(set(bloom_levels)) > 1 else "Consistent"}"""

    def _create_fallback_assessment(self, state: GameSessionState) -> AssessmentResult:
        """Create fallback assessment when main assessment fails"""
        player = state.get("players", [{}])[0]

        return {
            "assessment_id": f"assess_{datetime.utcnow().timestamp()}",
            "player_id": player.get("player_id", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "rubric_id": "",
            "performance_indicators": {},
            "bloom_level_demonstrated": "Understand",
            "dimensional_scores": {},
            "strengths": ["Engaged with the game"],
            "areas_for_improvement": [],
            "feedback_message": "Good effort! Keep exploring and engaging with NPCs.",
            "experience_gained": 5
        }

    async def assess_dialogue_interaction(
        self,
        player_statement: str,
        npc_response: Dict[str, Any],
        dialogue_skills_eval: Dict[str, Any],
        state: GameSessionState
    ) -> AssessmentResult:
        """
        Assess dialogue-specific interaction

        Args:
            player_statement: What player said
            npc_response: NPC's response
            dialogue_skills_eval: Dialogue skills evaluation
            state: Game session state

        Returns:
            Dialogue-specific assessment
        """
        try:
            player = state.get("players", [{}])[0]
            player_id = player.get("player_id", "")

            # Determine Bloom's level from dialogue
            bloom_level = self._determine_dialogue_bloom_level(
                player_statement,
                dialogue_skills_eval
            )

            # Calculate dimensional scores
            dimensional_scores = {
                "intellectual": self._score_from_rating(dialogue_skills_eval.get("information_gathering", "fair")),
                "social": self._score_from_rating(dialogue_skills_eval.get("rapport_building", "fair")),
                "emotional": self._score_from_rating(dialogue_skills_eval.get("empathy", "fair")),
                "physical": 0,  # Not applicable for dialogue
                "vocational": self._score_from_rating(dialogue_skills_eval.get("goal_orientation", "fair")),
                "spiritual": 0,  # Not directly assessed in dialogue
                "environmental": 50  # Default
            }

            # Calculate experience
            avg_score = sum(dimensional_scores.values()) / len([s for s in dimensional_scores.values() if s > 0])
            experience_gained = int(avg_score / 2)  # 0-50 XP based on performance

            # Build feedback
            feedback_parts = [
                f"Your conversation demonstrated {bloom_level} level thinking."
            ]

            if dialogue_skills_eval.get("overall_assessment"):
                feedback_parts.append(dialogue_skills_eval["overall_assessment"])

            assessment: AssessmentResult = {
                "assessment_id": f"assess_{datetime.utcnow().timestamp()}",
                "player_id": player_id,
                "timestamp": datetime.utcnow().isoformat(),
                "rubric_id": "dialogue_rubric",
                "performance_indicators": {
                    "rapport_building": dialogue_skills_eval.get("rapport_building", "fair"),
                    "active_listening": dialogue_skills_eval.get("active_listening", "fair"),
                    "empathy": dialogue_skills_eval.get("empathy", "fair"),
                    "goal_orientation": dialogue_skills_eval.get("goal_orientation", "fair")
                },
                "bloom_level_demonstrated": bloom_level,
                "dimensional_scores": dimensional_scores,
                "strengths": dialogue_skills_eval.get("strengths", []),
                "areas_for_improvement": dialogue_skills_eval.get("improvement_tips", []),
                "feedback_message": " ".join(feedback_parts),
                "experience_gained": experience_gained
            }

            logger.info(
                "dialogue_assessed",
                bloom_level=bloom_level,
                experience=experience_gained
            )

            return assessment

        except Exception as e:
            logger.error("dialogue_assessment_failed", error=str(e))
            return self._create_fallback_assessment(state)

    def _determine_dialogue_bloom_level(
        self,
        player_statement: str,
        dialogue_eval: Dict[str, Any]
    ) -> str:
        """Determine Bloom's level from dialogue"""

        # Simple heuristic - in production, use LLM analysis
        excellent_count = sum(
            1 for v in dialogue_eval.values()
            if isinstance(v, str) and v == "excellent"
        )

        if excellent_count >= 3:
            return "Analyze"
        elif excellent_count >= 2:
            return "Apply"
        elif "?" in player_statement:  # Player asking questions
            return "Understand"
        else:
            return "Remember"

    def _score_from_rating(self, rating: str) -> int:
        """Convert rating to score"""
        rating_map = {
            "excellent": 90,
            "good": 75,
            "fair": 60,
            "poor": 40
        }
        return rating_map.get(rating, 60)

    async def track_dimensional_progression(
        self,
        player_id: str,
        assessments: List[AssessmentResult]
    ) -> Dict[str, Any]:
        """
        Track player's progression across 7 human dimensions

        Args:
            player_id: Player ID
            assessments: List of assessments

        Returns:
            Dimensional progression summary
        """
        try:
            if not assessments:
                return self._create_empty_progression()

            # Aggregate scores per dimension
            dimension_totals = {
                "intellectual": [],
                "social": [],
                "emotional": [],
                "physical": [],
                "vocational": [],
                "spiritual": [],
                "environmental": []
            }

            for assessment in assessments:
                scores = assessment.get("dimensional_scores", {})
                for dim, score in scores.items():
                    if score > 0:
                        dimension_totals[dim].append(score)

            # Calculate averages and trends
            progression = {}
            for dim, scores in dimension_totals.items():
                if scores:
                    avg = sum(scores) / len(scores)
                    trend = "improving" if len(scores) > 1 and scores[-1] > scores[0] else "stable"

                    progression[dim] = {
                        "current_level": avg,
                        "maturity_tier": self._get_maturity_tier(avg),
                        "trend": trend,
                        "assessment_count": len(scores)
                    }
                else:
                    progression[dim] = {
                        "current_level": 0,
                        "maturity_tier": "Emerging",
                        "trend": "no_data",
                        "assessment_count": 0
                    }

            logger.info(
                "dimensional_progression_tracked",
                player_id=player_id,
                assessment_count=len(assessments)
            )

            return progression

        except Exception as e:
            logger.error("progression_tracking_failed", error=str(e))
            return self._create_empty_progression()

    def _get_maturity_tier(self, score: float) -> str:
        """Get maturity tier from score"""
        if score >= 85:
            return "Mastery"
        elif score >= 70:
            return "Proficient"
        elif score >= 55:
            return "Developing"
        else:
            return "Emerging"

    def _create_empty_progression(self) -> Dict[str, Any]:
        """Create empty progression structure"""
        return {
            dim: {
                "current_level": 0,
                "maturity_tier": "Emerging",
                "trend": "no_data",
                "assessment_count": 0
            }
            for dim in ["intellectual", "social", "emotional", "physical", "vocational", "spiritual", "environmental"]
        }


# Global instance
assessment_engine = AssessmentEngineAgent()
