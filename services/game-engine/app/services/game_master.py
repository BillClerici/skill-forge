"""
Game Master Agent
AI agent that orchestrates all gameplay using LangChain and Claude
"""
from typing import Dict, Any, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferWindowMemory
import json

from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import (
    GameSessionState,
    PlayerSessionData,
    ActionInterpretation,
    NPCDialogueResponse
)
from .mcp_client import mcp_client

logger = get_logger(__name__)


class GameMasterAgent:
    """
    AI Agent that orchestrates all gameplay
    Central intelligence for narrative, NPCs, and player interpretation
    """

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            temperature=0.7,
            max_tokens=4096
        )
        self.memory = ConversationBufferWindowMemory(k=20)

    # ============================================
    # Scene Generation
    # ============================================

    async def generate_scene_description(
        self,
        state: GameSessionState
    ) -> str:
        """
        Generate immersive scene description for current location

        Args:
            state: Current game session state

        Returns:
            Scene description text
        """
        try:
            logger.info(
                "generating_scene_description",
                session_id=state["session_id"],
                scene_id=state["current_scene_id"]
            )

            # Check if this is the first scene (beginning of the adventure)
            is_first_scene = len(state.get("action_history", [])) == 0

            # Get scene data from MCP
            scene_data = await mcp_client.get_location(
                state.get("current_place_id", ""),
                state["current_scene_id"]
            )

            if not scene_data:
                logger.error("scene_data_not_found", scene_id=state["current_scene_id"])
                return "You find yourself in an unfamiliar place..."

            # Get player context
            player = state["players"][0] if state["players"] else None
            cognitive_profile = player["cognitive_profile"] if player else {}

            # For first scene, load campaign and quest data for full introduction
            if is_first_scene:
                from .mongo_persistence import mongo_persistence

                campaign = await mongo_persistence.get_campaign(state.get("campaign_id", ""))
                quest = await mongo_persistence.get_quest(state.get("current_quest_id", ""))

                logger.info(
                    "generating_campaign_introduction",
                    session_id=state["session_id"],
                    campaign_id=state.get("campaign_id"),
                    quest_id=state.get("current_quest_id")
                )

                # Build introduction prompt with campaign and quest context
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self._get_gm_system_prompt(state)),
                    ("user", """This is the beginning of a new adventure! Generate a comprehensive introduction that:

CAMPAIGN BACKGROUND:
Name: {campaign_name}
Description: {campaign_description}
Setting: {campaign_setting}

CURRENT QUEST:
Title: {quest_title}
Description: {quest_description}
Objectives:
{quest_objectives}

STARTING LOCATION:
Name: {scene_name}
Type: {scene_type}
Description: {scene_description}

NPCs Present: {npcs_present}
Time of Day: {time_of_day}

Generate a rich, engaging introduction that:
1. Provides the campaign background story and sets the overall narrative context
2. Explains the current quest and its backstory/importance
3. Lists the quest objectives clearly
4. Describes the starting location vividly with sensory details
5. Introduces any NPCs present naturally
6. Ends by asking if the player has any questions or is ready to begin
7. Adapts language complexity to player's Bloom's level: {blooms_level}

Use second person ("You find yourself..."). Be immersive and engaging, making the player excited to start their adventure.

Return ONLY the introduction text (no JSON, no additional commentary).""")
                ])

                # Invoke LLM with campaign and quest data
                chain = prompt | self.llm
                # Extract quest objectives - handle both string and object formats
                quest_objectives_list = []
                if quest and quest.get("objectives"):
                    for obj in quest.get("objectives", []):
                        if isinstance(obj, dict):
                            quest_objectives_list.append(f"- {obj.get('description', str(obj))}")
                        else:
                            quest_objectives_list.append(f"- {obj}")
                quest_objectives_str = "\n".join(quest_objectives_list) if quest_objectives_list else "- Begin your adventure"

                response = await chain.ainvoke({
                    "campaign_name": campaign.get("name", "Unknown Campaign") if campaign else "Unknown Campaign",
                    "campaign_description": campaign.get("description", "") if campaign else "",
                    "campaign_setting": campaign.get("setting", {}).get("description", "") if campaign else "",
                    "quest_title": quest.get("name") or quest.get("title", "Quest") if quest else "Quest",
                    "quest_description": quest.get("description", "") if quest else "",
                    "quest_objectives": quest_objectives_str,
                    "scene_name": scene_data.get("name", "Unknown"),
                    "scene_type": scene_data.get("location_type", "room"),
                    "scene_description": scene_data.get("description", ""),
                    "npcs_present": self._format_npc_list(state.get("available_npcs", [])),
                    "time_of_day": state.get("time_of_day", "morning"),
                    "blooms_level": cognitive_profile.get("current_bloom_tier", "Understand")
                })

                scene_description = response.content.strip()

                logger.info(
                    "campaign_introduction_generated",
                    session_id=state["session_id"],
                    length=len(scene_description)
                )

            else:
                # Regular scene generation for subsequent scenes
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self._get_gm_system_prompt(state)),
                    ("user", """Generate an immersive scene description for the following location:

Location Name: {scene_name}
Location Type: {scene_type}
Description: {scene_description}

NPCs Present: {npcs_present}
Time of Day: {time_of_day}

Previous Player Actions: {recent_actions}

Generate a vivid, second-person scene description that:
1. Sets the atmosphere and mood
2. Describes key visual/sensory details
3. Introduces NPCs naturally
4. Hints at available actions
5. Adapts language complexity to player's Bloom's level: {blooms_level}

Return ONLY the scene description text (no JSON, no additional commentary).""")
                ])

                # Invoke LLM
                chain = prompt | self.llm
                response = await chain.ainvoke({
                    "scene_name": scene_data.get("name", "Unknown"),
                    "scene_type": scene_data.get("location_type", "room"),
                    "scene_description": scene_data.get("description", ""),
                    "npcs_present": self._format_npc_list(state.get("available_npcs", [])),
                    "time_of_day": state.get("time_of_day", "midday"),
                    "recent_actions": self._format_recent_actions(state.get("action_history", [])[-3:]),
                    "blooms_level": cognitive_profile.get("current_bloom_tier", "Understand")
                })

                scene_description = response.content.strip()

                logger.info(
                    "scene_description_generated",
                    session_id=state["session_id"],
                    length=len(scene_description)
                )

            return scene_description

        except Exception as e:
            logger.error(
                "scene_generation_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            return "You find yourself in a new location..."

    # ============================================
    # Player Action Interpretation
    # ============================================

    async def interpret_player_action(
        self,
        player_input: str,
        state: GameSessionState,
        player: PlayerSessionData
    ) -> ActionInterpretation:
        """
        Convert natural language player input to structured game action

        Args:
            player_input: Player's natural language input
            state: Current game session state
            player: Player session data

        Returns:
            Structured action interpretation
        """
        try:
            logger.info(
                "interpreting_player_action",
                session_id=state["session_id"],
                player_id=player["player_id"],
                input_length=len(player_input)
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are the Game Master's action interpreter.
Convert player's natural language input into a structured game action.

Available action types:
- move_to_location: Player wants to go somewhere
- talk_to_npc: Player wants to talk to an NPC
- examine_object: Player wants to look at something closely
- use_item: Player wants to use an item
- attempt_challenge: Player wants to attempt a challenge/puzzle

Return JSON with this structure:
{{
    "action_type": "talk_to_npc",
    "target_id": "npc_dr_voss",
    "parameters": {{"topic": "dampeners"}},
    "success_probability": 0.85,
    "player_input": "original input"
}}"""),
                ("user", """Player Input: "{player_input}"

Current Scene: {scene_name}
Available NPCs: {available_npcs}
Available Actions: {available_actions}
Visible Items: {visible_items}
Active Challenges: {active_challenges}

What action is the player attempting?""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "player_input": player_input,
                "scene_name": state.get("scene_description", "")[:100],
                "available_npcs": json.dumps([npc.get("name") for npc in state.get("available_npcs", [])]),
                "available_actions": json.dumps(state.get("available_actions", [])),
                "visible_items": json.dumps(state.get("visible_items", [])),
                "active_challenges": json.dumps([c.get("name") for c in state.get("active_challenges", [])])
            })

            # Parse JSON response
            action_data = json.loads(response.content.strip())

            action: ActionInterpretation = {
                "action_type": action_data.get("action_type", "examine_object"),
                "target_id": action_data.get("target_id"),
                "parameters": action_data.get("parameters", {}),
                "success_probability": action_data.get("success_probability", 0.5),
                "player_input": player_input
            }

            logger.info(
                "action_interpreted",
                session_id=state["session_id"],
                action_type=action["action_type"],
                target_id=action.get("target_id")
            )

            return action

        except Exception as e:
            logger.error(
                "action_interpretation_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            # Fallback: treat as examination
            return {
                "action_type": "examine_object",
                "target_id": None,
                "parameters": {"query": player_input},
                "success_probability": 0.5,
                "player_input": player_input
            }

    # ============================================
    # NPC Dialogue Generation
    # ============================================

    async def generate_npc_dialogue(
        self,
        npc_id: str,
        context: Dict[str, Any],
        player_statement: str,
        state: GameSessionState
    ) -> NPCDialogueResponse:
        """
        Generate NPC response to player statement

        Args:
            npc_id: NPC identifier
            context: Scene/quest context
            player_statement: What player said
            state: Game session state

        Returns:
            NPC dialogue response with metadata
        """
        try:
            logger.info(
                "generating_npc_dialogue",
                session_id=state["session_id"],
                npc_id=npc_id
            )

            # Get NPC data from MCP
            player = state["players"][0] if state["players"] else None
            npc_context = await mcp_client.get_npc_context(
                npc_id,
                player["character_id"] if player else ""
            )

            if not npc_context:
                logger.error("npc_context_not_found", npc_id=npc_id)
                return {
                    "dialogue": "I'm not sure what to say...",
                    "affinity_change": 0,
                    "knowledge_revealed": [],
                    "rubric_id": "",
                    "performance_indicators": {}
                }

            npc = npc_context.get("npc", {})
            relationship = npc_context.get("relationship", {})

            # Build NPC prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are {npc_name}, an NPC in SkillForge RPG.

Your Personality:
{personality_description}

Dialogue Style:
- Formality: {formality}
- Verbosity: {verbosity}
- Current Mood: {current_mood}

Relationship with Player:
- Affinity: {affinity}/100
- Interaction Count: {interaction_count}

Quest Context:
{quest_context}

Respond to the player IN CHARACTER. Generate a JSON response:
{{
    "dialogue": "Your spoken response (in quotes if dialogue)",
    "affinity_change": 0 to 10 (how this interaction affected relationship),
    "knowledge_revealed": ["knowledge_id_1"],
    "performance_indicators": {{"rapport": "good", "questioning": "excellent"}}
}}"""),
                ("user", """Player says: "{player_statement}"

Respond as {npc_name}.""")
            ])

            chain = prompt | self.llm
            response = await chain.ainvoke({
                "npc_name": npc.get("name", "Unknown"),
                "personality_description": npc.get("backstory", "")[:200],
                "formality": npc.get("dialogue_style", {}).get("formality", "neutral"),
                "verbosity": npc.get("dialogue_style", {}).get("verbosity", "moderate"),
                "current_mood": npc.get("current_mood", "neutral"),
                "affinity": relationship.get("total_affinity", 0),
                "interaction_count": relationship.get("interaction_count", 0),
                "quest_context": context.get("quest", {}).get("description", "")[:200],
                "player_statement": player_statement
            })

            # Parse response
            npc_response_data = json.loads(response.content.strip())

            npc_response: NPCDialogueResponse = {
                "dialogue": npc_response_data.get("dialogue", "..."),
                "affinity_change": npc_response_data.get("affinity_change", 0),
                "knowledge_revealed": npc_response_data.get("knowledge_revealed", []),
                "rubric_id": npc.get("rubric_id", ""),
                "performance_indicators": npc_response_data.get("performance_indicators", {})
            }

            logger.info(
                "npc_dialogue_generated",
                session_id=state["session_id"],
                npc_id=npc_id,
                affinity_change=npc_response["affinity_change"]
            )

            return npc_response

        except Exception as e:
            logger.error(
                "npc_dialogue_generation_failed",
                npc_id=npc_id,
                error=str(e)
            )
            return {
                "dialogue": "...",
                "affinity_change": 0,
                "knowledge_revealed": [],
                "rubric_id": "",
                "performance_indicators": {}
            }

    # ============================================
    # Helper Methods
    # ============================================

    def _get_gm_system_prompt(self, state: GameSessionState) -> str:
        """Get Game Master system prompt"""
        campaign_name = state.get("campaign_id", "Unknown Campaign")
        return f"""You are the Game Master for SkillForge, an AI-powered educational RPG.

Campaign: {campaign_name}

Your responsibilities:
1. Guide players with engaging narrative
2. Describe scenes vividly in second person
3. Adapt language to player's Bloom's Taxonomy level
4. Create memorable, educational moments
5. Maintain consistency with world lore

Remember:
- Speak in second person ("You see...")
- Show, don't tell
- Engage multiple senses
- Create atmosphere"""

    def _format_npc_list(self, npcs: List[Dict[str, Any]]) -> str:
        """Format NPC list for prompt"""
        if not npcs:
            return "None"
        return ", ".join([npc.get("name", "Unknown") for npc in npcs])

    def _format_recent_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format recent action history"""
        if not actions:
            return "This is the first action in this scene."
        return "\n".join([
            f"- {action.get('action_type')}: {action.get('parameters', {})}"
            for action in actions
        ])


# Global instance
gm_agent = GameMasterAgent()
