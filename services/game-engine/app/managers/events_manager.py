"""
Dynamic Events and Challenges Manager
Creates and manages dynamic game events, challenges, and encounters
"""
from typing import Dict, Any, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from datetime import datetime
import json
import random

from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import GameSessionState
from ..api.websocket_manager import connection_manager

logger = get_logger(__name__)


class EventsManager:
    """
    Manages dynamic events, challenges, and encounters
    """

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.9,  # Higher temperature for creative events
            max_tokens=1024
        )

        # Track active events
        self.active_events: Dict[str, List[Dict[str, Any]]] = {}

    async def generate_dynamic_event(
        self,
        session_id: str,
        state: GameSessionState,
        trigger_type: str = "random"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate dynamic event based on game state

        Args:
            session_id: Session ID
            state: Game session state
            trigger_type: What triggered the event

        Returns:
            Event data
        """
        try:
            logger.info(
                "generating_dynamic_event",
                session_id=session_id,
                trigger_type=trigger_type
            )

            # Build context
            context = self._build_event_context(state)

            # Generate event using LLM
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a creative game master generating dynamic events.

Create engaging, contextually appropriate events that:
1. Fit the current scene and quest
2. Match the player's Bloom's level
3. Present meaningful choices
4. Advance the story or provide character development opportunities

Event types:
- encounter: Meet unexpected character/creature
- discovery: Find something interesting
- challenge: Face an obstacle
- choice: Make an important decision
- environmental: Something happens in the world"""),
                ("user", """Create a dynamic event for this situation:

CONTEXT:
- Current Location: {location}
- Current Quest: {quest}
- Time of Day: {time_of_day}
- Player Level: {bloom_level}
- Recent Actions: {recent_actions}
- NPCs Present: {npcs}

Generate event as JSON:
{{
    "event_type": "encounter/discovery/challenge/choice/environmental",
    "title": "Event Title",
    "description": "Vivid description of what happens (second person, 2-3 sentences)",
    "bloom_level_target": "Remember/Understand/Apply/Analyze/Evaluate/Create",
    "choices": [
        {{
            "choice_id": "choice_1",
            "text": "Option text",
            "consequences": "What happens if chosen",
            "difficulty": "easy/medium/hard"
        }}
    ],
    "duration_turns": 1-5,
    "rewards": {{
        "experience": 0-30,
        "items": [],
        "knowledge": []
    }}
}}""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "location": state.get("scene_description", "")[:100],
                "quest": state.get("current_quest_id", "Unknown"),
                "time_of_day": state.get("time_of_day", "day"),
                "bloom_level": state.get("players", [{}])[0].get("cognitive_profile", {}).get("current_bloom_tier", "Understand"),
                "recent_actions": self._format_recent_actions(state.get("action_history", [])[-3:]),
                "npcs": ", ".join([npc.get("name", "") for npc in state.get("available_npcs", [])])
            })

            # Parse event
            event_data = json.loads(response.content.strip())

            # Add metadata
            event_id = f"event_{datetime.utcnow().timestamp()}"
            event_data["event_id"] = event_id
            event_data["triggered_at"] = datetime.utcnow().isoformat()
            event_data["trigger_type"] = trigger_type
            event_data["session_id"] = session_id
            event_data["status"] = "active"

            # Store active event
            if session_id not in self.active_events:
                self.active_events[session_id] = []

            self.active_events[session_id].append(event_data)

            # Broadcast event
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "dynamic_event_triggered",
                    "event_data": event_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "dynamic_event_generated",
                session_id=session_id,
                event_id=event_id,
                event_type=event_data.get("event_type")
            )

            return event_data

        except Exception as e:
            logger.error(
                "event_generation_failed",
                session_id=session_id,
                error=str(e)
            )
            return None

    def _build_event_context(self, state: GameSessionState) -> Dict[str, Any]:
        """Build context for event generation"""
        return {
            "location": state.get("current_scene_id"),
            "quest": state.get("current_quest_id"),
            "npcs": state.get("available_npcs", []),
            "items": state.get("visible_items", []),
            "time": state.get("time_of_day"),
            "player_actions": len(state.get("action_history", [])),
            "player_level": state.get("players", [{}])[0].get("cognitive_profile", {}).get("current_bloom_tier")
        }

    def _format_recent_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format recent actions"""
        if not actions:
            return "No recent actions"

        return ", ".join([
            action.get("action_type", "action")
            for action in actions
        ])

    async def resolve_event_choice(
        self,
        session_id: str,
        event_id: str,
        choice_id: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Resolve player's choice for an event

        Args:
            session_id: Session ID
            event_id: Event ID
            choice_id: Chosen option ID
            state: Game session state

        Returns:
            Resolution result
        """
        try:
            # Find event
            event = self._get_active_event(session_id, event_id)

            if not event:
                return {
                    "success": False,
                    "error": "Event not found"
                }

            # Find choice
            choices = event.get("choices", [])
            selected_choice = next(
                (c for c in choices if c.get("choice_id") == choice_id),
                None
            )

            if not selected_choice:
                return {
                    "success": False,
                    "error": "Choice not found"
                }

            # Generate consequences
            consequences = await self._generate_consequences(
                event,
                selected_choice,
                state
            )

            # Mark event as resolved
            event["status"] = "resolved"
            event["chosen_option"] = choice_id
            event["resolved_at"] = datetime.utcnow().isoformat()

            # Apply consequences
            await self._apply_consequences(session_id, consequences, state)

            # Broadcast resolution
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "event_resolved",
                    "event_id": event_id,
                    "choice": selected_choice,
                    "consequences": consequences,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "event_resolved",
                session_id=session_id,
                event_id=event_id,
                choice_id=choice_id
            )

            return {
                "success": True,
                "consequences": consequences
            }

        except Exception as e:
            logger.error("event_resolution_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def _generate_consequences(
        self,
        event: Dict[str, Any],
        choice: Dict[str, Any],
        state: GameSessionState
    ) -> Dict[str, Any]:
        """Generate detailed consequences for choice"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are generating consequences for a player's choice in an RPG."),
                ("user", """The player chose: "{choice_text}"

Predicted outcome: {consequences}

Generate detailed consequences as JSON:
{{
    "narrative": "What happens as a result (2-3 sentences)",
    "experience_gained": 0-30,
    "items_gained": [],
    "knowledge_gained": [],
    "affinity_changes": {{}},
    "state_changes": {{}}
}}""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "choice_text": choice.get("text", ""),
                "consequences": choice.get("consequences", "")
            })

            return json.loads(response.content.strip())

        except Exception as e:
            logger.error("consequence_generation_failed", error=str(e))
            return {
                "narrative": choice.get("consequences", "Something happens..."),
                "experience_gained": 5,
                "items_gained": [],
                "knowledge_gained": [],
                "affinity_changes": {},
                "state_changes": {}
            }

    async def _apply_consequences(
        self,
        session_id: str,
        consequences: Dict[str, Any],
        state: GameSessionState
    ):
        """Apply consequences to game state"""
        try:
            # Award experience
            xp = consequences.get("experience_gained", 0)

            # Add items
            items = consequences.get("items_gained", [])
            for item_id in items:
                # Add to player inventory
                player_id = state.get("players", [{}])[0].get("player_id")
                if player_id:
                    inventories = state.get("player_inventories", {})
                    if player_id not in inventories:
                        inventories[player_id] = []
                    inventories[player_id].append(item_id)

            # Record knowledge
            knowledge = consequences.get("knowledge_gained", [])
            # TODO: Record to knowledge graph

            # Apply affinity changes
            affinity_changes = consequences.get("affinity_changes", {})
            # TODO: Update NPC relationships

            logger.info(
                "consequences_applied",
                session_id=session_id,
                xp=xp,
                items_count=len(items)
            )

        except Exception as e:
            logger.error("consequence_application_failed", error=str(e))

    def _get_active_event(
        self,
        session_id: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get active event"""
        if session_id not in self.active_events:
            return None

        return next(
            (e for e in self.active_events[session_id] if e.get("event_id") == event_id),
            None
        )

    async def create_challenge(
        self,
        session_id: str,
        challenge_type: str,
        difficulty: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Create a challenge (puzzle, combat, skill check)

        Args:
            session_id: Session ID
            challenge_type: Type of challenge
            difficulty: Difficulty level
            state: Game session state

        Returns:
            Challenge data
        """
        try:
            logger.info(
                "creating_challenge",
                session_id=session_id,
                type=challenge_type,
                difficulty=difficulty
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", "You create engaging challenges for an educational RPG."),
                ("user", """Create a {challenge_type} challenge with {difficulty} difficulty.

Current context:
- Location: {location}
- Player Bloom's Level: {bloom_level}

Generate as JSON:
{{
    "challenge_type": "{challenge_type}",
    "title": "Challenge Title",
    "description": "What the player faces",
    "difficulty": "{difficulty}",
    "bloom_level_required": "Remember/Understand/Apply/Analyze/Evaluate/Create",
    "success_criteria": "What player must do to succeed",
    "hints": ["hint 1", "hint 2"],
    "time_limit_seconds": 0 (0 = no limit),
    "rewards": {{
        "success": {{"experience": 20-50}},
        "failure": {{"experience": 5-10}}
    }}
}}""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "challenge_type": challenge_type,
                "difficulty": difficulty,
                "location": state.get("scene_description", "")[:100],
                "bloom_level": state.get("players", [{}])[0].get("cognitive_profile", {}).get("current_bloom_tier", "Understand")
            })

            challenge_data = json.loads(response.content.strip())

            # Add metadata
            challenge_id = f"challenge_{datetime.utcnow().timestamp()}"
            challenge_data["challenge_id"] = challenge_id
            challenge_data["created_at"] = datetime.utcnow().isoformat()
            challenge_data["status"] = "active"
            challenge_data["attempts"] = 0

            # Store in state
            if "active_challenges" not in state:
                state["active_challenges"] = []

            state["active_challenges"].append(challenge_data)

            # Broadcast challenge
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "challenge_created",
                    "challenge": challenge_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "challenge_created",
                session_id=session_id,
                challenge_id=challenge_id
            )

            return challenge_data

        except Exception as e:
            logger.error("challenge_creation_failed", error=str(e))
            return {}

    async def attempt_challenge(
        self,
        session_id: str,
        challenge_id: str,
        player_attempt: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Process player's challenge attempt

        Args:
            session_id: Session ID
            challenge_id: Challenge ID
            player_attempt: Player's attempt/solution
            state: Game session state

        Returns:
            Attempt result
        """
        try:
            # Find challenge
            challenge = next(
                (c for c in state.get("active_challenges", []) if c.get("challenge_id") == challenge_id),
                None
            )

            if not challenge:
                return {
                    "success": False,
                    "error": "Challenge not found"
                }

            # Evaluate attempt
            success = await self._evaluate_challenge_attempt(
                challenge,
                player_attempt,
                state
            )

            # Update attempt count
            challenge["attempts"] += 1

            # Build result
            result = {
                "success": success,
                "attempt_number": challenge["attempts"],
                "feedback": "Correct! Well done!" if success else "Not quite. Try again.",
                "rewards": challenge["rewards"]["success"] if success else challenge["rewards"]["failure"]
            }

            if success:
                challenge["status"] = "completed"
                challenge["completed_at"] = datetime.utcnow().isoformat()

                # Add to completed challenges
                if "completed_challenges" not in state:
                    state["completed_challenges"] = []

                state["completed_challenges"].append(challenge_id)

            # Broadcast result
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "challenge_attempt_result",
                    "challenge_id": challenge_id,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "challenge_attempted",
                session_id=session_id,
                challenge_id=challenge_id,
                success=success
            )

            return result

        except Exception as e:
            logger.error("challenge_attempt_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def _evaluate_challenge_attempt(
        self,
        challenge: Dict[str, Any],
        player_attempt: str,
        state: GameSessionState
    ) -> bool:
        """Evaluate if challenge attempt succeeds"""
        try:
            # Use LLM to evaluate attempt
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You evaluate if a player's attempt solves a challenge."),
                ("user", """Challenge: {challenge_description}

Success Criteria: {success_criteria}

Player's Attempt: "{player_attempt}"

Does this attempt successfully solve the challenge? Respond with JSON:
{{
    "success": true/false,
    "reasoning": "Why it does or doesn't meet criteria"
}}""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "challenge_description": challenge.get("description", ""),
                "success_criteria": challenge.get("success_criteria", ""),
                "player_attempt": player_attempt
            })

            evaluation = json.loads(response.content.strip())

            return evaluation.get("success", False)

        except Exception as e:
            logger.error("challenge_evaluation_failed", error=str(e))
            # Default to 50% chance on error
            return random.random() > 0.5


# Global instance
events_manager = EventsManager()
