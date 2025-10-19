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
        state: GameSessionState,
        stream_callback=None
    ) -> str:
        """
        Generate immersive scene description for current location

        Args:
            state: Current game session state
            stream_callback: Optional async callback to receive text chunks as they're generated

        Returns:
            Complete scene description text
        """
        try:
            logger.info(
                "generating_scene_description",
                session_id=state["session_id"],
                scene_id=state["current_scene_id"]
            )

            # Check if this is the first scene (beginning of the adventure)
            is_first_scene = len(state.get("action_history", [])) == 0

            # Get scene data from MongoDB (not MCP)
            from .mongo_persistence import mongo_persistence

            scene_data = await mongo_persistence.get_scene(state["current_scene_id"])

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
                    ("user", """This is the beginning of a new adventure! Generate a comprehensive introduction with the following structure:

FIRST - GAME MASTER INTRODUCTION:
Greet the player warmly and introduce yourself as the Game Master. Explain:
- Your role as their guide and storyteller throughout this adventure
- That you will narrate the world, control NPCs, and adjudicate their actions
- How they should interact: describe what they want to do in natural language, ask questions, talk to NPCs
- That this is an educational RPG designed to help them grow and learn through gameplay
- Encourage them to be creative and immersive in their roleplay

THEN - CAMPAIGN AND QUEST:

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

After your introduction, generate a rich, engaging campaign/quest introduction that:
1. Provides the campaign background story and sets the overall narrative context
2. Explains the current quest and its backstory/importance
3. Lists the quest objectives clearly
4. Describes the starting location vividly with sensory details
5. Introduces any NPCs present naturally
6. Ends by asking if the player has any questions or is ready to begin
7. Adapts language complexity to player's Bloom's level: {blooms_level}

FORMATTING REQUIREMENTS:
- Use markdown headers (##) for major section titles like "Welcome to Your Adventure", campaign name, and quest name
- Use paragraph breaks for readability
- Use bold (**text**) for emphasis on important terms
- Use bullet points (-) for quest objectives
- Write campaign/quest content in second person ("You find yourself...")
- Be warm, welcoming, and engaging in the GM introduction (first person: "I am...")
- Be immersive and exciting in the campaign narration

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

                prompt_params = {
                    "campaign_name": campaign.get("name", "Unknown Campaign") if campaign else "Unknown Campaign",
                    "campaign_description": campaign.get("description", "") if campaign else "",
                    "campaign_setting": campaign.get("storyline", "") if campaign else "",
                    "quest_title": quest.get("name") or quest.get("title", "Quest") if quest else "Quest",
                    "quest_description": quest.get("description", "") if quest else "",
                    "quest_objectives": quest_objectives_str,
                    "scene_name": scene_data.get("name", "Unknown"),
                    "scene_type": scene_data.get("scene_type", "location"),
                    "scene_description": scene_data.get("description", ""),
                    "npcs_present": self._format_npc_list(state.get("available_npcs", [])),
                    "time_of_day": state.get("time_of_day", "morning"),
                    "blooms_level": cognitive_profile.get("current_bloom_tier", "Understand")
                }

                # Use streaming if callback provided
                if stream_callback:
                    scene_description = ""
                    async for chunk in chain.astream(prompt_params):
                        if hasattr(chunk, 'content'):
                            chunk_text = chunk.content
                            scene_description += chunk_text
                            await stream_callback(chunk_text)
                    scene_description = scene_description.strip()
                else:
                    response = await chain.ainvoke(prompt_params)
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
                prompt_params = {
                    "scene_name": scene_data.get("name", "Unknown"),
                    "scene_type": scene_data.get("location_type", "room"),
                    "scene_description": scene_data.get("description", ""),
                    "npcs_present": self._format_npc_list(state.get("available_npcs", [])),
                    "time_of_day": state.get("time_of_day", "midday"),
                    "recent_actions": self._format_recent_actions(state.get("action_history", [])[-3:]),
                    "blooms_level": cognitive_profile.get("current_bloom_tier", "Understand")
                }

                # Use streaming if callback provided
                if stream_callback:
                    scene_description = ""
                    async for chunk in chain.astream(prompt_params):
                        if hasattr(chunk, 'content'):
                            chunk_text = chunk.content
                            scene_description += chunk_text
                            await stream_callback(chunk_text)
                    scene_description = scene_description.strip()
                else:
                    response = await chain.ainvoke(prompt_params)
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
- player_ready: Player acknowledges they're ready to begin, understands, or is responding affirmatively to the GM (keywords: "ready", "yes", "ok", "I understand", "let's go", "I'm prepared", "understood", "no questions")
- ask_gm_question: Player is asking the Game Master a question about the world, rules, quest, or story (keywords: "what", "how", "why", "who", "where", "when", "?")
- move_to_location: Player wants to go somewhere (keywords: "go to", "move to", "walk to", "head to", "enter")
- talk_to_npc: Player wants to talk to an NPC (keywords: "talk to", "speak with", "ask", "tell", "say to")
- investigate_discovery: Player wants to investigate a specific discovery in the scene (keywords: "investigate", "examine", "inspect" + discovery name from available discoveries)
- examine_object: Player wants to look at something closely or investigate the scene generally (keywords: "examine", "look at", "inspect", "search")
- take_item: Player wants to pick up/take an item from the scene (keywords: "take", "pick up", "grab", "get", "collect" + item name from visible items)
- use_item: Player wants to use an item from inventory (keywords: "use", "drink", "eat", "equip", "activate")
- attempt_challenge: Player wants to attempt a challenge/puzzle (keywords: "attempt", "try", "solve")
- perform_action: Player wants to perform a creative/freeform action that doesn't fit other categories (e.g., "climb the wall", "push the statue", "light the torch", "break down the door")

IMPORTANT PRIORITY ORDER:
1. If the player is indicating readiness or acknowledgment (ready, yes, ok, understood, let's begin, no questions), use "player_ready"
2. If the player input is a question (contains ?, or starts with who/what/where/when/why/how), use "ask_gm_question"
3. If the player wants to move to a location, use "move_to_location"
4. If the player wants to talk to an NPC, use "talk_to_npc"
5. If the player wants to investigate a specific discovery that matches one in the available discoveries list, use "investigate_discovery"
6. If the player wants to examine something generally, use "examine_object"
7. If the player wants to take/pick up an item that matches one in the visible items list, use "take_item"
8. If the player wants to use an item, use "use_item"
9. If the player wants to attempt a challenge, use "attempt_challenge"
10. Otherwise, use "perform_action" for creative/freeform actions

Return ONLY valid JSON with NO markdown formatting, NO code blocks, NO additional text.

For player_ready:
{{
    "action_type": "player_ready",
    "target_id": null,
    "parameters": {{}},
    "success_probability": 1.0
}}

For ask_gm_question:
{{
    "action_type": "ask_gm_question",
    "target_id": null,
    "parameters": {{"question": "the actual question text"}},
    "success_probability": 1.0
}}

For perform_action:
{{
    "action_type": "perform_action",
    "target_id": null,
    "parameters": {{"action_description": "what the player is trying to do"}},
    "success_probability": 0.5 to 1.0 (estimate based on difficulty)
}}

For other actions, follow similar structure with appropriate action_type and parameters."""),
                ("user", """Player Input: "{player_input}"

Current Scene: {scene_name}
Available NPCs: {available_npcs}
Available Discoveries: {available_discoveries}
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
                "available_discoveries": json.dumps([d.get("name") for d in state.get("available_discoveries", [])]),
                "available_actions": json.dumps(state.get("available_actions", [])),
                "visible_items": json.dumps(state.get("visible_items", [])),
                "active_challenges": json.dumps([c.get("name") for c in state.get("active_challenges", [])])
            })

            # Parse JSON response - handle markdown code blocks
            response_text = response.content.strip()

            # Log raw response for debugging
            logger.debug(
                "raw_action_interpreter_response",
                session_id=state.get("session_id"),
                response_preview=response_text[:200]
            )

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                # Extract JSON from code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            # Log cleaned response
            logger.debug(
                "cleaned_action_interpreter_response",
                session_id=state.get("session_id"),
                response_preview=response_text[:200]
            )

            action_data = json.loads(response_text)

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
    # Game Master Q&A
    # ============================================

    async def answer_player_question(
        self,
        question: str,
        state: GameSessionState,
        stream_callback=None
    ) -> str:
        """
        Answer player's question about the game world, quest, or story

        Args:
            question: Player's question
            state: Current game session state
            stream_callback: Optional async callback to receive text chunks as they're generated

        Returns:
            Game Master's response
        """
        try:
            logger.info(
                "answering_player_question",
                session_id=state["session_id"],
                question_length=len(question)
            )

            # Get current context
            from .mongo_persistence import mongo_persistence
            campaign = await mongo_persistence.get_campaign(state.get("campaign_id", ""))
            quest = await mongo_persistence.get_quest(state.get("current_quest_id", ""))
            scene = await mongo_persistence.get_scene(state.get("current_scene_id", ""))

            # Load World data
            world = None
            if campaign and campaign.get("world_id"):
                world = await mongo_persistence.get_world(campaign["world_id"])

            # Load sample regions from world (first 3)
            regions_info = []
            if world and world.get("regions"):
                region_ids = world["regions"][:3]  # Load first 3 regions
                for region_id in region_ids:
                    region = await mongo_persistence.get_region(region_id)
                    if region:
                        regions_info.append(f"{region.get('region_name', 'Unknown')}: {region.get('description', 'No description')[:100]}")

            # Load sample species from world (first 5)
            species_info = []
            if world and world.get("species"):
                species_ids = world["species"][:5]  # Load first 5 species
                for species_id in species_ids:
                    species = await mongo_persistence.get_species(species_id)
                    if species:
                        species_info.append(f"{species.get('species_name', 'Unknown')}: {species.get('description', 'No description')[:100]}")

            # Format world context
            world_description = world.get("description", "") if world else ""
            world_backstory = world.get("backstory", "")[:200] if world else ""

            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_gm_system_prompt(state)),
                ("user", """The player has asked you a question about the game. Answer it helpfully and in character as the Game Master.

Player's Question: {question}

Recent Conversation History:
{conversation_history}

Current Context:
- World: {world_name}
- World Description: {world_description}
- World Backstory: {world_backstory}
- Regions: {regions_info}
- Species: {species_info}
- Campaign: {campaign_name}
- Quest: {quest_title}
- Location: {scene_name}
- Recent Actions: {recent_actions}

IMPORTANT:
- Use the conversation history to provide contextual answers
- Remember what has been discussed and build on it
- Use ONLY the EXACT information provided above
- Do NOT make up or hallucinate names, places, or details

Provide a clear, helpful answer that:
1. Directly addresses their question based on the conversation context
2. Stays in character as the Game Master
3. References previous discussion when relevant
4. Uses the current world/campaign/quest context
5. Uses ONLY the factual information provided above
6. Encourages them to continue their adventure
7. Is brief and to the point (2-3 sentences maximum unless more detail is needed)

Return ONLY your answer (no JSON, no additional commentary).""")
            ])

            chain = prompt | self.llm

            prompt_params = {
                "question": question,
                "conversation_history": self._format_chat_history(state.get("chat_messages", []), last_n=10),
                "world_name": world.get("world_name", "Unknown World") if world else "Unknown World",
                "world_description": world_description[:200] if world_description else "Unknown",
                "world_backstory": world_backstory,
                "regions_info": "\n- ".join(regions_info) if regions_info else "Information not available",
                "species_info": "\n- ".join(species_info) if species_info else "Information not available",
                "campaign_name": campaign.get("name", "Unknown Campaign") if campaign else "Unknown Campaign",
                "quest_title": quest.get("name", "Current Quest") if quest else "Current Quest",
                "scene_name": scene.get("name", "Current Location") if scene else "Current Location",
                "recent_actions": self._format_recent_actions(state.get("action_history", [])[-3:])
            }

            # Use streaming if callback provided
            if stream_callback:
                answer = ""
                async for chunk in chain.astream(prompt_params):
                    if hasattr(chunk, 'content'):
                        chunk_text = chunk.content
                        answer += chunk_text
                        await stream_callback(chunk_text)
                answer = answer.strip()
            else:
                response = await chain.ainvoke(prompt_params)
                answer = response.content.strip()

            logger.info(
                "player_question_answered",
                session_id=state["session_id"],
                answer_length=len(answer)
            )

            return answer

        except Exception as e:
            logger.error(
                "question_answering_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            return "I'm not sure how to answer that right now. Could you try rephrasing your question?"

    # ============================================
    # Generic Action Handling
    # ============================================

    async def generate_generic_action_outcome(
        self,
        action_description: str,
        state: GameSessionState,
        stream_callback=None
    ) -> str:
        """
        Generate narrative outcome for a freeform/creative player action

        Args:
            action_description: What the player is attempting to do
            state: Current game session state
            stream_callback: Optional async callback to receive text chunks as they're generated

        Returns:
            Narrative description of the action's outcome
        """
        try:
            logger.info(
                "generating_generic_action_outcome",
                session_id=state["session_id"],
                action_length=len(action_description)
            )

            # Get current context
            from .mongo_persistence import mongo_persistence
            scene = await mongo_persistence.get_scene(state.get("current_scene_id", ""))

            # Get player context
            player = state["players"][0] if state["players"] else None
            cognitive_profile = player["cognitive_profile"] if player else {}

            prompt = ChatPromptTemplate.from_messages([
                ("system", self._get_gm_system_prompt(state)),
                ("user", """The player is attempting a creative action. As the Game Master, narrate the outcome.

Player's Action: {action_description}

Recent Conversation History:
{conversation_history}

Current Scene Context:
- Location: {scene_name}
- Description: {scene_description}
- NPCs Present: {npcs_present}
- Available Items: {visible_items}
- Active Events: {active_events}
- Recent Actions: {recent_actions}

Your task:
1. Determine if the action is possible in this context
2. If possible, determine the outcome (success, partial success, or interesting failure)
3. Narrate the result vividly in second person
4. Include sensory details and consequences
5. Adapt language complexity to player's Bloom's level: {blooms_level}
6. If the action reveals something new, describe it
7. If the action changes the scene state, describe that change
8. Reference the conversation history if relevant to maintain continuity

IMPORTANT:
- Be creative and say "yes, and..." when possible
- Even failures should be interesting and move the story forward
- Consider physics, logic, and story consistency
- Keep the narrative engaging and educational
- Maintain awareness of what has been discussed and revealed

Return ONLY the narrative outcome (no JSON, no additional commentary).""")
            ])

            chain = prompt | self.llm

            prompt_params = {
                "action_description": action_description,
                "conversation_history": self._format_chat_history(state.get("chat_messages", []), last_n=10),
                "scene_name": scene.get("name", "Current Location") if scene else "Current Location",
                "scene_description": scene.get("description", "")[:300] if scene else "",
                "npcs_present": self._format_npc_list(state.get("available_npcs", [])),
                "visible_items": ", ".join(state.get("visible_items", [])) or "None visible",
                "active_events": ", ".join([e.get("name", "") for e in state.get("active_events", [])]) or "None",
                "recent_actions": self._format_recent_actions(state.get("action_history", [])[-3:]),
                "blooms_level": cognitive_profile.get("current_bloom_tier", "Understand")
            }

            # Use streaming if callback provided
            if stream_callback:
                outcome = ""
                async for chunk in chain.astream(prompt_params):
                    if hasattr(chunk, 'content'):
                        chunk_text = chunk.content
                        outcome += chunk_text
                        await stream_callback(chunk_text)
                outcome = outcome.strip()
            else:
                response = await chain.ainvoke(prompt_params)
                outcome = response.content.strip()

            logger.info(
                "generic_action_outcome_generated",
                session_id=state["session_id"],
                outcome_length=len(outcome)
            )

            return outcome

        except Exception as e:
            logger.error(
                "generic_action_outcome_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            return f"You attempt to {action_description}, but the outcome is unclear. The Game Master will need to consider this further."

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

    def _format_chat_history(self, chat_messages: List[Dict[str, Any]], last_n: int = 10) -> str:
        """Format recent chat messages for conversation context"""
        if not chat_messages:
            return "No previous conversation."

        # Get last N messages
        recent_messages = chat_messages[-last_n:]

        formatted = []
        for msg in recent_messages:
            sender = msg.get("sender_name", "Unknown")
            content = msg.get("content", "")
            msg_type = msg.get("message_type", "")

            # Format based on message type
            if msg_type == "PLAYER_ACTION":
                formatted.append(f"PLAYER: {content}")
            elif msg_type in ["DM_NARRATIVE", "DM_SYSTEM"]:
                formatted.append(f"GM: {content}")
            elif msg_type == "DM_NPC_DIALOGUE":
                formatted.append(f"{sender}: {content}")
            else:
                formatted.append(f"{sender}: {content}")

        return "\n".join(formatted)


# Global instance
gm_agent = GameMasterAgent()
