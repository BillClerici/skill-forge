"""
NPC Controller Agent
Dedicated agent for managing NPC personalities, dialogue, and relationships
"""
from typing import Dict, Any, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from datetime import datetime
import json

from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import NPCDialogueResponse, GameSessionState
from ..services.mcp_client import mcp_client

logger = get_logger(__name__)


class NPCControllerAgent:
    """
    Advanced NPC controller with personality modeling and relationship tracking
    """

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.8,  # Higher temperature for more varied dialogue
            max_tokens=2048
        )
        # Store conversation memories per NPC
        self.npc_memories: Dict[str, ConversationBufferMemory] = {}

    def _get_npc_memory(self, npc_id: str) -> ConversationBufferMemory:
        """Get or create conversation memory for NPC"""
        if npc_id not in self.npc_memories:
            self.npc_memories[npc_id] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                k=10  # Keep last 10 exchanges
            )
        return self.npc_memories[npc_id]

    async def generate_contextual_dialogue(
        self,
        npc_id: str,
        player_statement: str,
        state: GameSessionState,
        npc_context: Dict[str, Any]
    ) -> NPCDialogueResponse:
        """
        Generate NPC dialogue with deep personality modeling

        Args:
            npc_id: NPC identifier
            player_statement: What player said
            state: Current game session state
            npc_context: NPC context from MCP

        Returns:
            NPC dialogue response with metadata
        """
        try:
            logger.info(
                "generating_contextual_npc_dialogue",
                npc_id=npc_id,
                session_id=state.get("session_id")
            )

            npc = npc_context.get("npc", {})
            relationship = npc_context.get("relationship", {})

            # Get NPC's conversation memory
            memory = self._get_npc_memory(npc_id)

            # Build comprehensive personality prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._build_npc_system_prompt(npc, relationship, state)),
                ("user", """Player says: "{player_statement}"

Context:
- Current Quest: {current_quest}
- Scene: {scene_description}
- Recent Events: {recent_events}

Respond as {npc_name} with a JSON structure:
{{
    "dialogue": "Your in-character spoken response",
    "internal_thought": "What the NPC is thinking (not spoken)",
    "emotional_state": "current emotion (e.g., happy, concerned, angry)",
    "affinity_change": -5 to +5 (how this affects relationship),
    "knowledge_revealed": ["knowledge_id_1", "knowledge_id_2"],
    "quest_hints": ["hint about quest objective"],
    "performance_indicators": {{"rapport": "excellent/good/fair/poor", "questioning": "excellent/good/fair/poor"}},
    "suggested_actions": ["action player might take based on this dialogue"]
}}""")
            ])

            # Get recent events
            recent_events = self._format_recent_events(state.get("event_log", [])[-3:])

            # Invoke LLM
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "player_statement": player_statement,
                "npc_name": npc.get("name", "Unknown"),
                "current_quest": state.get("current_quest_id", "None"),
                "scene_description": state.get("scene_description", "")[:150],
                "recent_events": recent_events
            })

            # Parse response
            dialogue_data = json.loads(response.content.strip())

            # Store in memory
            memory.save_context(
                {"input": player_statement},
                {"output": dialogue_data.get("dialogue", "")}
            )

            # Build response
            npc_response: NPCDialogueResponse = {
                "dialogue": dialogue_data.get("dialogue", "..."),
                "affinity_change": dialogue_data.get("affinity_change", 0),
                "knowledge_revealed": dialogue_data.get("knowledge_revealed", []),
                "rubric_id": npc.get("rubric_id", ""),
                "performance_indicators": dialogue_data.get("performance_indicators", {}),
                "metadata": {
                    "internal_thought": dialogue_data.get("internal_thought", ""),
                    "emotional_state": dialogue_data.get("emotional_state", "neutral"),
                    "quest_hints": dialogue_data.get("quest_hints", []),
                    "suggested_actions": dialogue_data.get("suggested_actions", [])
                }
            }

            logger.info(
                "npc_dialogue_generated",
                npc_id=npc_id,
                affinity_change=npc_response["affinity_change"],
                emotional_state=dialogue_data.get("emotional_state")
            )

            return npc_response

        except Exception as e:
            logger.error(
                "npc_dialogue_generation_failed",
                npc_id=npc_id,
                error=str(e)
            )
            return {
                "dialogue": "I... I'm not sure what to say.",
                "affinity_change": 0,
                "knowledge_revealed": [],
                "rubric_id": "",
                "performance_indicators": {}
            }

    def _build_npc_system_prompt(
        self,
        npc: Dict[str, Any],
        relationship: Dict[str, Any],
        state: GameSessionState
    ) -> str:
        """Build comprehensive NPC system prompt"""

        personality = npc.get("personality", {})
        dialogue_style = npc.get("dialogue_style", {})

        return f"""You are {npc.get("name", "Unknown")}, an NPC in SkillForge RPG.

CORE IDENTITY:
- Role: {npc.get("role", "Character")}
- Age: {npc.get("age", "Unknown")}
- Occupation: {npc.get("occupation", "Unknown")}

BACKSTORY & MOTIVATION:
{npc.get("backstory", "No backstory available.")}

Goals: {npc.get("goals", "Unknown")}
Fears: {npc.get("fears", "Unknown")}

PERSONALITY TRAITS:
- Openness: {personality.get("openness", 5)}/10
- Conscientiousness: {personality.get("conscientiousness", 5)}/10
- Extraversion: {personality.get("extraversion", 5)}/10
- Agreeableness: {personality.get("agreeableness", 5)}/10
- Neuroticism: {personality.get("neuroticism", 5)}/10

DIALOGUE STYLE:
- Formality: {dialogue_style.get("formality", "neutral")}
- Verbosity: {dialogue_style.get("verbosity", "moderate")}
- Humor: {dialogue_style.get("humor_level", "moderate")}
- Speech Patterns: {dialogue_style.get("speech_patterns", "standard")}

CURRENT STATE:
- Mood: {npc.get("current_mood", "neutral")}
- Location: {npc.get("current_location", "unknown")}
- Time of Day: {state.get("time_of_day", "unknown")}

RELATIONSHIP WITH PLAYER:
- Affinity: {relationship.get("total_affinity", 0)}/100
- Trust Level: {relationship.get("trust_level", "stranger")}
- Interactions: {relationship.get("interaction_count", 0)} previous conversations
- Last Interaction: {relationship.get("last_interaction_summary", "This is your first meeting")}

KNOWLEDGE & SECRETS:
- What I Know: {json.dumps(npc.get("knowledge_keys", []))}
- Secrets I Guard: {json.dumps(npc.get("secrets", []))}
- Reveal Threshold: Affinity must be {npc.get("reveal_threshold", 50)}+ to share secrets

INSTRUCTIONS:
1. Stay deeply in character at all times
2. Show emotion and personality through dialogue
3. Remember past conversations (use context)
4. React authentically based on affinity level
5. Only reveal knowledge/secrets when appropriate
6. Provide quest hints subtly, don't be too obvious
7. Adapt tone based on current mood and relationship
8. Use personality traits to shape responses
9. Consider player's Bloom's level: {state.get("players", [{}])[0].get("cognitive_profile", {}).get("current_bloom_tier", "Understand")}

Remember: You are a living character with goals, fears, and depth. Be authentic."""

    def _format_recent_events(self, events: List[Dict[str, Any]]) -> str:
        """Format recent events for context"""
        if not events:
            return "No recent events."

        return "\n".join([
            f"- {event.get('event_type', 'event')}: {event.get('description', 'Unknown')}"
            for event in events
        ])

    async def evaluate_player_dialogue_skills(
        self,
        player_statement: str,
        npc_response: NPCDialogueResponse,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate how well player engaged in dialogue

        Args:
            player_statement: What player said
            npc_response: NPC's response
            context: Conversation context

        Returns:
            Dialogue skill evaluation
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a dialogue skills evaluator for an educational RPG.
Evaluate the player's conversational effectiveness based on:
1. Rapport building
2. Active listening/questioning
3. Empathy/emotional intelligence
4. Goal-oriented conversation
5. Information gathering

Rate each dimension as: excellent, good, fair, or poor."""),
                ("user", """Player said: "{player_statement}"

NPC responded: "{npc_response}"

Context:
- Quest Objective: {quest_objective}
- Conversation Goal: {conversation_goal}

Evaluate the player's dialogue skills in JSON:
{{
    "rapport_building": "excellent/good/fair/poor",
    "active_listening": "excellent/good/fair/poor",
    "empathy": "excellent/good/fair/poor",
    "goal_orientation": "excellent/good/fair/poor",
    "information_gathering": "excellent/good/fair/poor",
    "overall_assessment": "Overall evaluation",
    "improvement_tips": ["tip 1", "tip 2"]
}}""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "player_statement": player_statement,
                "npc_response": npc_response.get("dialogue", ""),
                "quest_objective": context.get("quest_objective", "Unknown"),
                "conversation_goal": context.get("conversation_goal", "Build relationship")
            })

            evaluation = json.loads(response.content.strip())

            logger.info(
                "dialogue_skills_evaluated",
                overall=evaluation.get("overall_assessment")
            )

            return evaluation

        except Exception as e:
            logger.error("dialogue_evaluation_failed", error=str(e))
            return {
                "rapport_building": "fair",
                "active_listening": "fair",
                "empathy": "fair",
                "goal_orientation": "fair",
                "information_gathering": "fair",
                "overall_assessment": "Unable to evaluate",
                "improvement_tips": []
            }

    async def update_npc_relationship(
        self,
        npc_id: str,
        player_id: str,
        affinity_change: int,
        interaction_summary: str
    ) -> bool:
        """
        Update NPC-Player relationship in MCP

        Args:
            npc_id: NPC ID
            player_id: Player ID
            affinity_change: Change in affinity (-5 to +5)
            interaction_summary: Summary of interaction

        Returns:
            Success status
        """
        try:
            interaction_data = {
                "npc_id": npc_id,
                "player_id": player_id,
                "interaction_type": "dialogue",
                "affinity_change": affinity_change,
                "summary": interaction_summary,
                "timestamp": datetime.utcnow().isoformat()
            }

            result = await mcp_client.record_npc_interaction(interaction_data)

            if result:
                logger.info(
                    "npc_relationship_updated",
                    npc_id=npc_id,
                    player_id=player_id,
                    affinity_change=affinity_change
                )
                return True
            else:
                logger.warning("npc_relationship_update_failed", npc_id=npc_id)
                return False

        except Exception as e:
            logger.error("npc_relationship_update_error", error=str(e))
            return False


# Global instance
npc_controller = NPCControllerAgent()
