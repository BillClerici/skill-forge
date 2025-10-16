"""
LangGraph Game Loop Workflow
Orchestrates the main gameplay loop using state machine
"""
from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from datetime import datetime
import json

from ..models.state import (
    GameSessionState,
    SessionStatus,
    ActionInterpretation,
    NPCDialogueResponse,
    AssessmentResult,
    PlayerAction,
    GameEvent
)
from ..services.game_master import gm_agent
from ..services.mcp_client import mcp_client
from ..services.redis_manager import redis_manager
from ..services.rabbitmq_client import rabbitmq_client
from ..core.logging import get_logger

logger = get_logger(__name__)


# ============================================
# Workflow Nodes
# ============================================

async def initialize_session_node(state: GameSessionState) -> GameSessionState:
    """
    Initialize game session with campaign data

    Load campaign, set starting location, initialize player states
    """
    try:
        # Check if session is already initialized (has scene_description)
        # If so, skip initialization and go directly to the current node
        if state.get("scene_description") and state.get("current_node") and state.get("current_node") != "generate_scene":
            logger.info(
                "session_already_initialized_skipping",
                session_id=state["session_id"],
                current_node=state.get("current_node")
            )
            # Session already initialized, return state as-is
            # The workflow will route based on current_node
            return state

        logger.info(
            "initializing_session",
            session_id=state["session_id"],
            campaign_id=state["campaign_id"]
        )

        # Load campaign data directly from MongoDB
        from ..services.mongo_persistence import mongo_persistence

        campaign = await mongo_persistence.get_campaign(state["campaign_id"])

        if campaign and campaign.get("quest_ids") and len(campaign["quest_ids"]) > 0:
            # Get ALL quests to sort by order_sequence
            quest_ids = campaign["quest_ids"]
            all_quests = []
            for qid in quest_ids:
                quest = await mongo_persistence.get_quest(qid)
                if quest:
                    all_quests.append(quest)

            # Sort quests by order_sequence
            all_quests.sort(key=lambda q: q.get("order_sequence", 0))

            if all_quests:
                first_quest = all_quests[0]
                first_quest_id = first_quest.get("_id") or first_quest.get("quest_id")
                state["current_quest_id"] = first_quest_id

                # Use Place/Scene structure: Get first place (by order_sequence), then first scene
                place_ids = first_quest.get("place_ids", [])
                if place_ids and len(place_ids) > 0:
                    # Load all places to sort by order_sequence
                    all_places = []
                    for pid in place_ids:
                        place = await mongo_persistence.get_place(pid)
                        if place:
                            all_places.append(place)

                    # Sort places by order_sequence
                    all_places.sort(key=lambda p: p.get("order_sequence", 0))

                    if all_places:
                        first_place = all_places[0]
                        first_place_id = first_place.get("_id") or first_place.get("place_id")

                        # Load all scenes to sort by order_sequence
                        scene_ids = first_place.get("scene_ids", [])
                        if scene_ids:
                            all_scenes = []
                            for sid in scene_ids:
                                scene = await mongo_persistence.get_scene(sid)
                                if scene:
                                    all_scenes.append(scene)

                            # Sort scenes by order_sequence
                            all_scenes.sort(key=lambda s: s.get("order_sequence", 0))

                            if all_scenes:
                                first_scene_id = all_scenes[0].get("_id") or all_scenes[0].get("scene_id")
                                state["current_scene_id"] = first_scene_id
                                state["current_place_id"] = first_place_id
                                logger.info(
                                    "loaded_campaign_quest",
                                    quest_id=first_quest_id,
                                    quest_title=first_quest.get("name", "Unknown"),
                                    place_id=first_place_id,
                                    scene_id=first_scene_id
                                )
                            else:
                                logger.warning("place_has_no_scenes", place_id=first_place_id)
                                state["current_scene_id"] = "starting_location"
                                state["current_place_id"] = campaign.get("world_id", "")
                        else:
                            logger.warning("place_has_no_scene_ids", place_id=first_place_id)
                            state["current_scene_id"] = "starting_location"
                            state["current_place_id"] = campaign.get("world_id", "")
                    else:
                        logger.warning("quest_has_no_places", quest_id=first_quest_id)
                        state["current_scene_id"] = "starting_location"
                        state["current_place_id"] = campaign.get("world_id", "")
                else:
                    logger.warning("quest_has_no_place_ids", quest_id=first_quest_id)
                    state["current_scene_id"] = "starting_location"
                    state["current_place_id"] = campaign.get("world_id", "")
            else:
                # Quests not found
                logger.warning("quests_not_found_in_mongodb", quest_ids=quest_ids)
                state["current_scene_id"] = "starting_location"
                state["current_place_id"] = campaign.get("world_id", "")
        else:
            # No quests in campaign - ERROR condition
            logger.error(
                "no_quests_in_campaign",
                campaign_id=state["campaign_id"]
            )
            raise ValueError(f"Campaign {state['campaign_id']} has no quests configured")

        # Initialize player states
        if not state.get("player_inventories"):
            state["player_inventories"] = {}
        if not state.get("player_knowledge"):
            state["player_knowledge"] = {}
        if not state.get("player_locations"):
            state["player_locations"] = {}

        for player in state.get("players", []):
            player_id = player["player_id"]
            state["player_locations"][player_id] = state["current_scene_id"]

            # Initialize inventory from MCP (optional)
            try:
                inventory_data = await mcp_client.get_player_inventory(player_id)
                if inventory_data:
                    state["player_inventories"][player_id] = inventory_data.get("items", [])
                else:
                    state["player_inventories"][player_id] = []
            except Exception as e:
                logger.warning(
                    "inventory_load_failed",
                    player_id=player_id,
                    error=str(e)
                )
                state["player_inventories"][player_id] = []

        # Initialize lists
        state["conversation_history"] = state.get("conversation_history", [])
        state["action_history"] = state.get("action_history", [])
        state["event_log"] = state.get("event_log", [])
        state["chat_messages"] = state.get("chat_messages", [])
        state["completed_quest_ids"] = state.get("completed_quest_ids", [])
        state["completed_scene_ids"] = state.get("completed_scene_ids", [])

        # Set game time
        state["time_of_day"] = "morning"
        state["elapsed_game_time"] = 0

        # Check if session was paused before updating status
        current_state = await redis_manager.load_state(state["session_id"])
        if current_state and current_state.get("status") == "paused":
            logger.info("session_paused_during_init", session_id=state["session_id"])
            state["status"] = "paused"
            return state

        # Update status
        state["status"] = SessionStatus.ACTIVE
        state["current_node"] = "generate_scene"
        state["awaiting_player_input"] = False
        state["last_updated"] = datetime.utcnow().isoformat()

        # Save to Redis
        await redis_manager.save_state(state["session_id"], state)

        # Publish state change event
        await rabbitmq_client.publish_state_change(
            state["session_id"],
            "initializing",
            "active"
        )

        logger.info(
            "session_initialized",
            session_id=state["session_id"],
            starting_quest=state["current_quest_id"],
            starting_scene=state["current_scene_id"]
        )

        return state

    except Exception as e:
        logger.error(
            "session_initialization_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        state["status"] = SessionStatus.ERROR
        return state


async def generate_scene_node(state: GameSessionState) -> GameSessionState:
    """
    Generate immersive scene description using Game Master agent
    """
    try:
        logger.info(
            "generating_scene",
            session_id=state["session_id"],
            scene_id=state["current_scene_id"]
        )

        # Import connection manager for broadcasting chunks
        from ..api.websocket_manager import connection_manager

        # Define streaming callback to broadcast chunks via WebSocket
        async def stream_chunk(chunk: str):
            """Callback to broadcast streaming chunks"""
            await connection_manager.broadcast_to_session(
                state["session_id"],
                {
                    "event": "scene_chunk",
                    "chunk": chunk,
                    "is_complete": False
                }
            )

        # Generate scene description via Game Master with streaming
        scene_description = await gm_agent.generate_scene_description(
            state,
            stream_callback=stream_chunk
        )
        state["scene_description"] = scene_description

        # Broadcast final completion chunk
        await connection_manager.broadcast_to_session(
            state["session_id"],
            {
                "event": "scene_chunk",
                "chunk": "",
                "is_complete": True
            }
        )

        # Load scene data from MongoDB
        from ..services.mongo_persistence import mongo_persistence

        scene_data = await mongo_persistence.get_scene(state["current_scene_id"])

        # Get NPCs at current location
        npcs_at_location = await mongo_persistence.get_npcs_at_location(state["current_scene_id"])

        if npcs_at_location:
            state["available_npcs"] = npcs_at_location
            logger.info(
                "npcs_loaded_from_mongodb",
                session_id=state["session_id"],
                scene_id=state["current_scene_id"],
                npc_count=len(npcs_at_location)
            )
        else:
            state["available_npcs"] = []
            logger.warning(
                "no_npcs_found_at_location",
                session_id=state["session_id"],
                scene_id=state["current_scene_id"]
            )

        # Load all scene-related content if scene data exists
        if scene_data:
            # Load discoveries
            discovery_ids = scene_data.get("discovery_ids", [])
            if discovery_ids:
                discoveries = await mongo_persistence.get_discoveries_by_ids(discovery_ids)
                state["available_discoveries"] = discoveries
                logger.info(
                    "discoveries_loaded",
                    session_id=state["session_id"],
                    count=len(discoveries)
                )
            else:
                state["available_discoveries"] = []

            # Load events
            event_ids = scene_data.get("event_ids", [])
            if event_ids:
                events = await mongo_persistence.get_events_by_ids(event_ids)
                state["active_events"] = events
                logger.info(
                    "events_loaded",
                    session_id=state["session_id"],
                    count=len(events)
                )
            else:
                state["active_events"] = []

            # Load challenges
            challenge_ids = scene_data.get("challenge_ids", [])
            if challenge_ids:
                challenges = await mongo_persistence.get_challenges_by_ids(challenge_ids)
                state["active_challenges"] = challenges
                logger.info(
                    "challenges_loaded",
                    session_id=state["session_id"],
                    count=len(challenges)
                )
            else:
                state["active_challenges"] = []

            # Load visible items (items present in the scene)
            # Note: This is different from player inventory
            # Items in the scene can be picked up or interacted with
            visible_item_ids = scene_data.get("visible_item_ids", [])
            if visible_item_ids:
                visible_items = await mongo_persistence.get_items_by_ids(visible_item_ids)
                state["visible_items"] = [item.get("name") for item in visible_items]
                logger.info(
                    "visible_items_loaded",
                    session_id=state["session_id"],
                    count=len(visible_items)
                )
            else:
                state["visible_items"] = []

            # Load required knowledge (knowledge needed to access this scene)
            required_knowledge_ids = scene_data.get("required_knowledge", [])
            if required_knowledge_ids:
                required_knowledge = await mongo_persistence.get_knowledge_by_ids(required_knowledge_ids)
                state["scene_required_knowledge"] = required_knowledge
                logger.info(
                    "scene_required_knowledge_loaded",
                    session_id=state["session_id"],
                    count=len(required_knowledge)
                )
            else:
                state["scene_required_knowledge"] = []

            # Load required items (items needed to access this scene)
            required_item_ids = scene_data.get("required_items", [])
            if required_item_ids:
                required_items = await mongo_persistence.get_items_by_ids(required_item_ids)
                state["scene_required_items"] = required_items
                logger.info(
                    "scene_required_items_loaded",
                    session_id=state["session_id"],
                    count=len(required_items)
                )
            else:
                state["scene_required_items"] = []
        else:
            # No scene data found, initialize empty lists
            state["available_discoveries"] = []
            state["active_events"] = []
            state["active_challenges"] = []
            state["visible_items"] = []
            state["scene_required_knowledge"] = []
            state["scene_required_items"] = []

        # Determine available actions based on scene context
        available_actions = ["look around", "examine surroundings"]

        if state["available_npcs"]:
            available_actions.append("talk to NPC")

        if state.get("active_challenges"):
            available_actions.append("attempt challenge")

        if state.get("visible_items"):
            available_actions.append("take item")

        if state.get("available_discoveries"):
            available_actions.append("investigate discovery")

        available_actions.extend(["check inventory", "view quest log"])
        state["available_actions"] = available_actions

        # Create chat message for scene description
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "DM_NARRATIVE",
            "sender_id": "game_master",
            "sender_name": "Game Master",
            "content": scene_description,
            "metadata": {
                "scene_id": state["current_scene_id"],
                "available_actions": available_actions,
                "npcs_present": [npc.get("name") for npc in state["available_npcs"]]
            }
        }

        state["chat_messages"].append(chat_message)

        # Publish scene update
        await rabbitmq_client.publish_scene_update(
            state["session_id"],
            scene_description,
            available_actions,
            state["available_npcs"]
        )

        # Update workflow state
        state["current_node"] = "await_player_input"
        state["awaiting_player_input"] = True
        state["scene_just_generated"] = True  # Flag to indicate scene was just generated
        state["last_updated"] = datetime.utcnow().isoformat()

        # Save state
        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "scene_generated",
            session_id=state["session_id"],
            npcs_count=len(state["available_npcs"]),
            actions_count=len(available_actions)
        )

        return state

    except Exception as e:
        logger.error(
            "scene_generation_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def await_player_input_node(state: GameSessionState) -> GameSessionState:
    """
    Wait for player input via WebSocket

    This node marks the state as awaiting input. The actual input
    will be injected via WebSocket handler, which will reload state,
    add the pending_action, and trigger workflow continuation.
    """
    try:
        logger.info(
            "awaiting_player_input",
            session_id=state["session_id"]
        )

        # This node just marks that we're waiting
        # The WebSocket handler will:
        # 1. Receive player input
        # 2. Load state from Redis
        # 3. Set state["pending_action"] = player_input
        # 4. Set state["awaiting_player_input"] = False
        # 5. Save state back to Redis
        # 6. Trigger workflow to continue to interpret_action_node

        # Check if session was externally paused before saving
        current_state = await redis_manager.load_state(state["session_id"])
        current_status = current_state.get("status") if current_state else None
        logger.info(
            "checking_pause_status",
            session_id=state["session_id"],
            current_status=current_status,
            paused_check=current_status == "paused"
        )
        if current_status == "paused":
            # Session was paused externally, don't overwrite
            logger.info("session_paused_externally", session_id=state["session_id"])
            state["status"] = "paused"
            return state

        state["current_node"] = "await_player_input"
        state["awaiting_player_input"] = True
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        # This node will "pause" here until WebSocket provides input
        # The workflow will be retriggered when input arrives

        return state

    except Exception as e:
        logger.error(
            "await_input_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def interpret_action_node(state: GameSessionState) -> GameSessionState:
    """
    Interpret player's natural language input into structured action
    """
    try:
        logger.info(
            "interpreting_action",
            session_id=state["session_id"]
        )

        # Get pending action (set by WebSocket handler)
        pending_action = state.get("pending_action")
        if not pending_action:
            logger.warning("no_pending_action", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            return state

        player_input = pending_action.get("player_input", "")
        player_id = pending_action.get("player_id", "")

        # Find player data
        player = None
        for p in state.get("players", []):
            if p["player_id"] == player_id:
                player = p
                break

        if not player:
            logger.error("player_not_found", player_id=player_id)
            state["pending_action"] = None
            state["current_node"] = "await_player_input"
            return state

        # Use Game Master agent to interpret action
        action_interpretation = await gm_agent.interpret_player_action(
            player_input,
            state,
            player
        )

        # Store interpreted action for execution
        state["pending_action"]["interpretation"] = action_interpretation

        # Add to chat history
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "PLAYER_ACTION",
            "sender_id": player_id,
            "sender_name": player.get("character_name", "Unknown"),
            "content": player_input,
            "metadata": {
                "action_type": action_interpretation["action_type"],
                "target_id": action_interpretation.get("target_id")
            }
        }
        state["chat_messages"].append(chat_message)

        # Update workflow state
        state["current_node"] = "execute_action"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "action_interpreted",
            session_id=state["session_id"],
            action_type=action_interpretation["action_type"],
            target_id=action_interpretation.get("target_id")
        )

        return state

    except Exception as e:
        logger.error(
            "action_interpretation_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def execute_action_node(state: GameSessionState) -> GameSessionState:
    """
    Execute the interpreted action and generate outcome
    """
    try:
        logger.info(
            "executing_action",
            session_id=state["session_id"]
        )

        pending_action = state.get("pending_action")
        if not pending_action:
            logger.warning("no_pending_action_in_execute", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            return state

        interpretation: ActionInterpretation = pending_action.get("interpretation")

        if not interpretation:
            logger.warning("no_interpretation", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            state["pending_action"] = None
            return state

        action_type = interpretation["action_type"]
        target_id = interpretation.get("target_id")
        parameters = interpretation.get("parameters", {})
        player_id = pending_action.get("player_id")

        # Execute based on action type
        outcome = None
        requires_assessment = False

        if action_type == "player_ready":
            # Player is acknowledging readiness or understanding
            # Provide encouraging response and prompt them to take action
            encouragement = "Excellent! Your adventure awaits. Take a moment to look around, speak with anyone present, or take your first action."

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": encouragement,
                "metadata": {"action_type": "acknowledgment"}
            }
            state["chat_messages"].append(chat_message)

            outcome = {"player_acknowledged": True}

        elif action_type == "ask_gm_question":
            # Player is asking the Game Master a question
            question = parameters.get("question", pending_action.get("player_input", ""))

            answer = await gm_agent.answer_player_question(question, state)

            # Add GM answer to chat
            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": answer,
                "metadata": {"action_type": "question_answer"}
            }
            state["chat_messages"].append(chat_message)

            outcome = {"question_answered": True}

        elif action_type == "talk_to_npc":
            # Check if there are available NPCs
            if not state.get("available_npcs"):
                # No NPCs available - GM should narrate that player needs to progress
                gm_response = f"""Looking around the chaotic marketplace, you're surrounded by hundreds of frightened, confused people from all three societies. However, in this moment of panic and darkness, identifying and approaching someone who can actually help with the investigation will be crucial.

Let me help guide you: The scene description mentions several key elements - marketplace buildings where groups are sheltering, the reservoir control room showing signs of sabotage, and emerging conflicts between groups.

Consider these actionable next steps:
• Examine the scene more carefully to identify specific NPCs or locations
• Look for the reservoir control room to investigate the sabotage
• Check on one of the marketplace buildings where groups are trapped
• Search for guards, merchants, or officials who might have information

What would you like to do?"""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": gm_response,
                    "metadata": {"action_type": "gm_guidance"}
                }
                state["chat_messages"].append(chat_message)

                outcome = {"gm_guidance_provided": True}
            else:
                # NPCs available - proceed with normal dialogue
                player_statement = parameters.get("statement", pending_action.get("player_input", ""))

                npc_response = await gm_agent.generate_npc_dialogue(
                    target_id,
                    {"quest": state.get("current_quest_id")},
                    player_statement,
                    state
                )

                # Add NPC response to chat
                npc_name = "Unknown NPC"
                for npc in state.get("available_npcs", []):
                    if npc.get("npc_id") == target_id:
                        npc_name = npc.get("name", "Unknown NPC")
                        break

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NPC_DIALOGUE",
                    "sender_id": target_id,
                    "sender_name": npc_name,
                    "content": npc_response["dialogue"],
                    "metadata": {
                        "affinity_change": npc_response["affinity_change"],
                        "knowledge_revealed": npc_response["knowledge_revealed"]
                    }
                }
                state["chat_messages"].append(chat_message)

                # Record interaction
                await mcp_client.record_npc_interaction({
                    "npc_id": target_id,
                    "player_id": player_id,
                    "session_id": state["session_id"],
                    "interaction_type": "dialogue",
                    "affinity_change": npc_response["affinity_change"],
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Publish NPC response event
                await rabbitmq_client.publish_npc_response(
                    state["session_id"],
                    npc_response
                )

                outcome = npc_response
                requires_assessment = bool(npc_response.get("rubric_id"))

        elif action_type == "move_to_location":
            # Move player to new location - validate and resolve to scene
            new_location_id = target_id

            # Try multiple resolution strategies
            from .mongo_persistence import mongo_persistence

            # Strategy 1: Check if it's a valid Scene
            scene_data = await mongo_persistence.get_scene(new_location_id)

            target_scene_id = None
            if scene_data:
                # Direct scene reference
                target_scene_id = new_location_id
            else:
                # Strategy 2: Check if it's a Place - if so, navigate to first scene in that place
                place_data = await mongo_persistence.get_place(new_location_id)
                if place_data and place_data.get("scene_ids"):
                    # Load all scenes to sort by order_sequence
                    place_scenes = []
                    for sid in place_data["scene_ids"]:
                        scene = await mongo_persistence.get_scene(sid)
                        if scene:
                            place_scenes.append(scene)

                    # Sort by order_sequence
                    place_scenes.sort(key=lambda s: s.get("order_sequence", 0))

                    if place_scenes:
                        target_scene_id = place_scenes[0].get("_id") or place_scenes[0].get("scene_id")
                        logger.info(
                            "resolved_place_to_scene",
                            session_id=state["session_id"],
                            place_id=new_location_id,
                            scene_id=target_scene_id
                        )

            if not target_scene_id:
                # Location doesn't exist - provide GM guidance
                gm_response = f"""You express interest in going to "{new_location_id}", but that location isn't available or doesn't exist here.

The scene description mentions various elements you can explore. To move to a new location, you should:

1. **Examine your surroundings** more carefully to identify specific, accessible locations
2. **Ask me questions** about where you can go or what's nearby
3. **Look for clues** in the narrative about available paths or destinations

What would you like to do?"""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": gm_response,
                    "metadata": {"action_type": "invalid_movement"}
                }
                state["chat_messages"].append(chat_message)

                outcome = {"invalid_location": new_location_id, "gm_guidance_provided": True}
            else:
                # Valid location - proceed with move
                old_scene = state["current_scene_id"]
                state["player_locations"][player_id] = target_scene_id
                state["current_scene_id"] = target_scene_id

                # Update current_place_id if we resolved from a place
                if scene_data:
                    # Scene move - place stays the same or gets updated from scene metadata
                    pass
                else:
                    # Place move - update place_id
                    state["current_place_id"] = new_location_id

                # Mark previous scene as completed
                if old_scene and old_scene not in state["completed_scene_ids"]:
                    state["completed_scene_ids"].append(old_scene)

                outcome = {"moved_to": target_scene_id}

                # Will regenerate scene
                state["current_node"] = "generate_scene"

        elif action_type == "examine_object":
            # Generate examination description using Game Master
            query = parameters.get("query", pending_action.get("player_input", ""))

            # Use Game Master to generate detailed examination outcome
            examination_text = await gm_agent.generate_generic_action_outcome(
                f"look around and examine {query}" if query else "look around and observe the surroundings",
                state
            )

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": examination_text,
                "metadata": {"action_type": "examine"}
            }
            state["chat_messages"].append(chat_message)

            outcome = {"examined": query}

        elif action_type == "perform_action":
            # Handle generic/creative freeform action
            action_description = parameters.get("action_description", pending_action.get("player_input", ""))

            # Use Game Master to generate narrative outcome for this creative action
            outcome_text = await gm_agent.generate_generic_action_outcome(action_description, state)

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": outcome_text,
                "metadata": {"action_type": "generic_action"}
            }
            state["chat_messages"].append(chat_message)

            outcome = {"action_performed": action_description}

        elif action_type == "use_item":
            # Use item from inventory
            item_id = target_id
            # TODO: Implement item usage logic with MCP
            outcome = {"used_item": item_id}

        elif action_type == "attempt_challenge":
            # Attempt a challenge/puzzle
            challenge_id = target_id
            # TODO: Implement challenge resolution logic
            outcome = {"attempted_challenge": challenge_id}
            requires_assessment = True

        # Record action in history
        player_action: PlayerAction = {
            "action_id": f"action_{datetime.utcnow().timestamp()}",
            "player_id": player_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action_type,
            "target_id": target_id,
            "parameters": parameters,
            "outcome": outcome
        }
        state["action_history"].append(player_action)

        # Store outcome and assessment requirement
        state["pending_action"]["outcome"] = outcome
        state["requires_assessment"] = requires_assessment

        if requires_assessment:
            state["assessment_context"] = {
                "action": interpretation,
                "outcome": outcome,
                "rubric_id": outcome.get("rubric_id") if isinstance(outcome, dict) else None
            }

        # Determine next node
        if action_type == "move_to_location":
            state["current_node"] = "generate_scene"
        elif requires_assessment:
            state["current_node"] = "assess_performance"
        else:
            state["current_node"] = "update_world_state"

        state["last_updated"] = datetime.utcnow().isoformat()
        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "action_executed",
            session_id=state["session_id"],
            action_type=action_type,
            requires_assessment=requires_assessment
        )

        return state

    except Exception as e:
        logger.error(
            "action_execution_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def assess_performance_node(state: GameSessionState) -> GameSessionState:
    """
    Assess player performance using rubrics and Bloom's Taxonomy
    """
    try:
        logger.info(
            "assessing_performance",
            session_id=state["session_id"]
        )

        assessment_context = state.get("assessment_context", {})
        if not assessment_context:
            logger.warning("no_assessment_context", session_id=state["session_id"])
            state["current_node"] = "update_world_state"
            state["requires_assessment"] = False
            return state

        # TODO: Implement rubric-based assessment agent
        # For now, create a placeholder assessment

        assessment: AssessmentResult = {
            "assessment_id": f"assess_{datetime.utcnow().timestamp()}",
            "player_id": state.get("pending_action", {}).get("player_id", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "rubric_id": assessment_context.get("rubric_id", ""),
            "performance_indicators": {},
            "bloom_level_demonstrated": "Understand",
            "dimensional_scores": {},
            "strengths": ["Engaged with NPC effectively"],
            "areas_for_improvement": [],
            "feedback_message": "Good interaction! You're making progress.",
            "experience_gained": 10
        }

        # Store assessment
        if "assessments" not in state:
            state["assessments"] = []
        state["assessments"].append(assessment)

        # Add assessment to chat
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "DM_ASSESSMENT",
            "sender_id": "game_master",
            "sender_name": "Game Master",
            "content": assessment["feedback_message"],
            "metadata": {
                "bloom_level": assessment["bloom_level_demonstrated"],
                "experience_gained": assessment["experience_gained"]
            }
        }
        state["chat_messages"].append(chat_message)

        # Publish assessment event
        await rabbitmq_client.publish_assessment(
            state["session_id"],
            assessment
        )

        state["current_node"] = "update_world_state"
        state["requires_assessment"] = False
        state["assessment_context"] = None
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "performance_assessed",
            session_id=state["session_id"],
            bloom_level=assessment["bloom_level_demonstrated"]
        )

        return state

    except Exception as e:
        logger.error(
            "assessment_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        state["current_node"] = "update_world_state"
        return state


async def update_world_state_node(state: GameSessionState) -> GameSessionState:
    """
    Update world state based on action outcomes
    Apply consequences, update NPCs, persist changes
    """
    try:
        logger.info(
            "updating_world_state",
            session_id=state["session_id"]
        )

        # Get action outcome
        pending_action = state.get("pending_action")
        outcome = pending_action.get("outcome", {}) if pending_action else {}

        # Update game time
        state["elapsed_game_time"] = state.get("elapsed_game_time", 0) + 1

        # Update time of day (simple progression)
        elapsed = state["elapsed_game_time"]
        if elapsed < 10:
            state["time_of_day"] = "morning"
        elif elapsed < 20:
            state["time_of_day"] = "afternoon"
        elif elapsed < 30:
            state["time_of_day"] = "evening"
        else:
            state["time_of_day"] = "night"

        # Record world change
        # TODO: Persist to MongoDB and Neo4j
        if outcome:
            world_change = {
                "change_id": f"change_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": "action_outcome",
                "affected_entities": [pending_action.get("player_id")],
                "description": f"Player action resulted in: {outcome}",
                "data": outcome
            }

            if "world_changes" not in state:
                state["world_changes"] = []
            state["world_changes"].append(world_change)

        # Clear pending action
        state["pending_action"] = None

        # Move to next node
        state["current_node"] = "check_quest_objectives"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "world_state_updated",
            session_id=state["session_id"],
            elapsed_time=state["elapsed_game_time"]
        )

        return state

    except Exception as e:
        logger.error(
            "world_state_update_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def check_quest_objectives_node(state: GameSessionState) -> GameSessionState:
    """
    Check if quest objectives or campaign goals are completed
    """
    try:
        logger.info(
            "checking_quest_objectives",
            session_id=state["session_id"]
        )

        # TODO: Implement quest objective checking with quest-mission MCP
        # For now, just check action count as simple progression

        quest_completed = False
        campaign_completed = False

        # Simple check: if 20 actions taken, mark quest as complete
        if len(state.get("action_history", [])) >= 20:
            current_quest_id = state.get("current_quest_id")
            if current_quest_id and current_quest_id not in state.get("completed_quest_ids", []):
                state["completed_quest_ids"].append(current_quest_id)
                quest_completed = True

                # Add completion message
                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": "Quest completed! You've successfully finished this chapter of your adventure.",
                    "metadata": {
                        "event_type": "quest_complete",
                        "quest_id": current_quest_id
                    }
                }
                state["chat_messages"].append(chat_message)

        # Check if all quests complete (campaign done)
        # TODO: Get total quest count from MCP

        state["current_node"] = "provide_bloom_feedback"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "quest_objectives_checked",
            session_id=state["session_id"],
            quest_completed=quest_completed
        )

        return state

    except Exception as e:
        logger.error(
            "quest_check_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def provide_bloom_feedback_node(state: GameSessionState) -> GameSessionState:
    """
    Provide Bloom's Taxonomy progression feedback
    """
    try:
        logger.info(
            "providing_bloom_feedback",
            session_id=state["session_id"]
        )

        # TODO: Implement comprehensive Bloom's analysis
        # For now, provide periodic feedback every 5 actions

        action_count = len(state.get("action_history", []))

        if action_count % 5 == 0 and action_count > 0:
            # Generate feedback message
            feedback_content = f"""You're progressing well! So far, you've demonstrated skills at the 'Understand' and 'Apply' levels of Bloom's Taxonomy.

Keep exploring and engaging with NPCs to unlock higher-order thinking challenges."""

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_BLOOM_FEEDBACK",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": feedback_content,
                "metadata": {
                    "action_count": action_count,
                    "current_bloom_tier": "Understand"
                }
            }
            state["chat_messages"].append(chat_message)

        state["current_node"] = "check_session_end"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        return state

    except Exception as e:
        logger.error(
            "bloom_feedback_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def check_session_end_node(state: GameSessionState) -> GameSessionState:
    """
    Check if session should end or continue
    """
    try:
        logger.info(
            "checking_session_end",
            session_id=state["session_id"]
        )

        should_end = False

        # Check end conditions
        if state.get("status") == SessionStatus.PAUSED:
            should_end = True
        elif state.get("status") == SessionStatus.COMPLETED:
            should_end = True
        elif state.get("status") == SessionStatus.ERROR:
            should_end = True

        # TODO: Check if all campaign quests completed

        if should_end:
            state["current_node"] = "END"
            logger.info("session_ending", session_id=state["session_id"])
        else:
            # Continue game loop - go back to await player input
            state["current_node"] = "await_player_input"
            state["awaiting_player_input"] = True

        state["last_updated"] = datetime.utcnow().isoformat()
        await redis_manager.save_state(state["session_id"], state)

        return state

    except Exception as e:
        logger.error(
            "session_end_check_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


# ============================================
# Conditional Edge Functions
# ============================================

def should_continue_session(state: GameSessionState) -> str:
    """Determine if session should continue or end"""
    if state.get("current_node") == "END":
        return "end"
    elif state.get("status") in [SessionStatus.PAUSED, SessionStatus.COMPLETED, SessionStatus.ERROR]:
        return "end"
    else:
        return "continue"


def route_after_execution(state: GameSessionState) -> str:
    """Route to appropriate node after action execution"""
    if state.get("current_node") == "generate_scene":
        return "generate_scene"
    elif state.get("requires_assessment"):
        return "assess_performance"
    else:
        return "update_world_state"


def route_from_await_input(state: GameSessionState) -> str:
    """Route from await_player_input based on whether there's pending action"""
    # If there's a pending action, continue to interpret it
    if state.get("pending_action"):
        return "interpret_action"
    # Otherwise, pause workflow (end for now, will be restarted by WebSocket)
    else:
        return "end"


def route_from_initialize(state: GameSessionState) -> str:
    """Route from initialize_session based on whether session was already initialized"""
    # If session already has a scene_description or current_node set to something other than
    # generate_scene, it was already initialized
    # Route to the current node instead of generate_scene
    current_node = state.get("current_node")
    has_scene = bool(state.get("scene_description"))

    if has_scene and current_node and current_node != "generate_scene":
        logger.info(
            "routing_to_current_node",
            session_id=state.get("session_id"),
            current_node=current_node
        )
        return current_node
    else:
        # New session, proceed to generate_scene
        return "generate_scene"


# ============================================
# Build Workflow Graph
# ============================================

def build_game_loop_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for game loop

    Returns:
        Compiled StateGraph workflow
    """

    # Create workflow graph
    workflow = StateGraph(GameSessionState)

    # Add all nodes
    workflow.add_node("initialize_session", initialize_session_node)
    workflow.add_node("generate_scene", generate_scene_node)
    workflow.add_node("await_player_input", await_player_input_node)
    workflow.add_node("interpret_action", interpret_action_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("assess_performance", assess_performance_node)
    workflow.add_node("update_world_state", update_world_state_node)
    workflow.add_node("check_quest_objectives", check_quest_objectives_node)
    workflow.add_node("provide_bloom_feedback", provide_bloom_feedback_node)
    workflow.add_node("check_session_end", check_session_end_node)

    # Set entry point
    workflow.set_entry_point("initialize_session")

    # Conditional routing from initialize_session
    # If already initialized, route to current_node; otherwise, route to generate_scene
    workflow.add_conditional_edges(
        "initialize_session",
        route_from_initialize,
        {
            "generate_scene": "generate_scene",
            "interpret_action": "interpret_action",
            "execute_action": "execute_action",
            "assess_performance": "assess_performance",
            "update_world_state": "update_world_state",
            "check_quest_objectives": "check_quest_objectives",
            "provide_bloom_feedback": "provide_bloom_feedback",
            "check_session_end": "check_session_end",
            "await_player_input": "await_player_input"
        }
    )

    # Add edges
    workflow.add_edge("generate_scene", "await_player_input")

    # Conditional routing from await_player_input
    workflow.add_conditional_edges(
        "await_player_input",
        route_from_await_input,
        {
            "interpret_action": "interpret_action",
            "end": END
        }
    )

    workflow.add_edge("interpret_action", "execute_action")

    # Conditional routing after action execution
    workflow.add_conditional_edges(
        "execute_action",
        route_after_execution,
        {
            "generate_scene": "generate_scene",
            "assess_performance": "assess_performance",
            "update_world_state": "update_world_state"
        }
    )

    workflow.add_edge("assess_performance", "update_world_state")
    workflow.add_edge("update_world_state", "check_quest_objectives")
    workflow.add_edge("check_quest_objectives", "provide_bloom_feedback")
    workflow.add_edge("provide_bloom_feedback", "check_session_end")

    # Conditional routing at session end check
    workflow.add_conditional_edges(
        "check_session_end",
        should_continue_session,
        {
            "continue": "await_player_input",
            "end": END
        }
    )

    # Compile workflow
    # Note: recursion_limit must be set when invoking the workflow, not during compilation
    # The default limit is 25, but the game loop can legitimately go through many nodes
    # in a single turn (initialize -> generate_scene -> await_input -> interpret -> execute ->
    # assess -> update -> check_quest -> bloom_feedback -> check_end -> await_input)
    # That's 11 nodes, so with player interactions we can easily hit 25
    compiled_workflow = workflow.compile()

    logger.info("game_loop_workflow_built")

    return compiled_workflow


# Global compiled workflow instance
game_loop = build_game_loop_workflow()
