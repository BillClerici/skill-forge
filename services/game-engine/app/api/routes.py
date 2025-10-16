"""
FastAPI Routes for Game Engine
Includes WebSocket endpoints and REST API
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import json

from ..models.state import (
    GameSessionState,
    SessionStatus
)
from ..models.api_models import (
    SoloSessionRequest,
    PartySessionRequest
)
from ..services.redis_manager import redis_manager
from ..services.rabbitmq_client import rabbitmq_client
from ..services.mcp_client import mcp_client
from ..workflows.game_loop import game_loop
from ..core.logging import get_logger
from .websocket_manager import connection_manager
from ..database import get_db, Character, Player

logger = get_logger(__name__)

# Create router
router = APIRouter()


# ============================================
# WebSocket Endpoints
# ============================================

@router.websocket("/ws/session/{session_id}/player/{player_id}")
async def websocket_gameplay_endpoint(
    websocket: WebSocket,
    session_id: str,
    player_id: str
):
    """
    WebSocket endpoint for real-time gameplay

    Args:
        websocket: WebSocket connection
        session_id: Game session ID
        player_id: Player ID
    """
    logger.info(
        "websocket_request_received",
        session_id=session_id,
        player_id=player_id,
        headers=dict(websocket.headers),
        query_params=dict(websocket.query_params)
    )

    await connection_manager.connect(websocket, session_id, player_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            event_type = data.get("event")

            if event_type == "player_action":
                # Handle player action
                action_content = data.get("content", "")
                await connection_manager.process_player_action(
                    session_id,
                    player_id,
                    action_content,
                    websocket
                )

            elif event_type == "typing_indicator":
                # Handle typing indicator
                is_typing = data.get("is_typing", False)
                await connection_manager.handle_typing_indicator(
                    session_id,
                    player_id,
                    is_typing
                )

            elif event_type == "team_chat":
                # Handle team chat message
                channel = data.get("channel", "party")
                content = data.get("content", "")
                metadata = data.get("metadata", {})

                await connection_manager.handle_team_chat_message(
                    session_id,
                    player_id,
                    channel,
                    content,
                    metadata
                )

            elif event_type == "ping":
                # Heartbeat ping
                await connection_manager.send_personal_message(
                    {
                        "event": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    websocket
                )

            else:
                logger.warning(
                    "unknown_websocket_event",
                    event_type=event_type,
                    session_id=session_id
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, session_id)

        # Notify other players
        await connection_manager.broadcast_to_session(
            session_id,
            {
                "event": "player_left",
                "player_id": player_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        logger.error(
            "websocket_error",
            session_id=session_id,
            player_id=player_id,
            error=str(e)
        )
        connection_manager.disconnect(websocket, session_id)


# ============================================
# Session Management Endpoints
# ============================================

@router.post("/session/start-solo")
async def start_solo_session(
    request: SoloSessionRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start a solo game session

    Args:
        request: Solo session request data
        db: Database session

    Returns:
        Session creation response with session_id
    """
    try:
        logger.info(
            "starting_solo_session",
            campaign_id=request.campaign_id,
            player_id=request.player_id
        )

        # Generate session ID
        session_id = f"session_{datetime.utcnow().timestamp()}_{request.player_id}"

        # Get character directly from PostgreSQL
        character = db.query(Character).filter(
            Character.character_id == request.character_id
        ).first()

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        # Get player info
        player = db.query(Player).filter(
            Player.player_id == request.player_id
        ).first()

        # Get player cognitive profile from MCP (optional - for AI context)
        cognitive_profile = None
        try:
            cognitive_profile = await mcp_client.get_player_cognitive_profile(request.player_id)
        except Exception as e:
            logger.warning(
                "mcp_cognitive_profile_unavailable",
                player_id=request.player_id,
                error=str(e)
            )

        # Convert character to dict for game state
        character_info = character.to_dict()

        # Initialize game session state
        initial_state: GameSessionState = {
            "session_id": session_id,
            "campaign_id": request.campaign_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": SessionStatus.INITIALIZING,
            "players": [{
                "player_id": request.player_id,
                "character_id": request.character_id,
                "character_name": character_info.get("name", "Unknown"),
                "cognitive_profile": cognitive_profile or {}
            }],
            "current_turn_player_id": request.player_id,
            "current_quest_id": "",
            "current_place_id": "",
            "current_scene_id": "",
            "completed_quest_ids": [],
            "completed_scene_ids": [],
            "scene_description": "",
            "available_npcs": [],
            "available_actions": [],
            "visible_items": [],
            "active_events": [],
            "active_challenges": [],
            "conversation_history": [],
            "action_history": [],
            "event_log": [],
            "player_inventories": {},
            "player_knowledge": {},
            "player_locations": {},
            "player_dimensional_progress": {},
            "npc_states": {},
            "world_changes": [],
            "time_of_day": "morning",
            "elapsed_game_time": 0,
            "dm_narrative_notes": [],
            "dm_planned_events": [],
            "dm_difficulty_adjustments": {},
            "chat_messages": [],
            "team_chat_messages": [],
            "current_node": "initialize_session",
            "pending_action": None,
            "awaiting_player_input": False,
            "requires_assessment": False,
            "assessment_context": None,
            "last_updated": datetime.utcnow().isoformat()
        }

        # Save initial state to Redis
        await redis_manager.save_state(session_id, initial_state)

        # Start workflow execution in background
        import asyncio
        asyncio.create_task(_execute_workflow_initialization(session_id, initial_state))

        logger.info(
            "solo_session_created",
            session_id=session_id,
            campaign_id=request.campaign_id
        )

        return {
            "session_id": session_id,
            "status": "initializing",
            "message": "Session created successfully. Connect via WebSocket to begin.",
            "websocket_url": f"/ws/session/{session_id}/player/{request.player_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "solo_session_creation_failed",
            campaign_id=request.campaign_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.post("/session/create-party")
async def create_party_session(
    request: PartySessionRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a multiplayer party session

    Args:
        request: Party session request data
        db: Database session

    Returns:
        Session creation response with session_id and invite tokens
    """
    try:
        logger.info(
            "creating_party_session",
            campaign_id=request.campaign_id,
            host_player_id=request.host_player_id,
            max_players=request.max_players
        )

        # Generate session ID
        session_id = f"party_{datetime.utcnow().timestamp()}_{request.host_player_id}"

        # Get host character from PostgreSQL
        character = db.query(Character).filter(
            Character.character_id == request.host_character_id
        ).first()

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        # Get cognitive profile from MCP (optional - for AI context)
        cognitive_profile = None
        try:
            cognitive_profile = await mcp_client.get_player_cognitive_profile(request.host_player_id)
        except Exception as e:
            logger.warning(
                "mcp_cognitive_profile_unavailable",
                player_id=request.host_player_id,
                error=str(e)
            )

        # Convert character to dict
        character_info = character.to_dict()

        # Initialize party session state
        initial_state: GameSessionState = {
            "session_id": session_id,
            "campaign_id": request.campaign_id,
            "started_at": datetime.utcnow().isoformat(),
            "status": SessionStatus.WAITING_FOR_PLAYERS,
            "players": [{
                "player_id": request.host_player_id,
                "character_id": request.host_character_id,
                "character_name": character_info.get("name", "Unknown"),
                "cognitive_profile": cognitive_profile or {}
            }],
            "current_turn_player_id": None,
            "current_quest_id": "",
            "current_place_id": "",
            "current_scene_id": "",
            "completed_quest_ids": [],
            "completed_scene_ids": [],
            "scene_description": "",
            "available_npcs": [],
            "available_actions": [],
            "visible_items": [],
            "active_events": [],
            "active_challenges": [],
            "conversation_history": [],
            "action_history": [],
            "event_log": [],
            "player_inventories": {},
            "player_knowledge": {},
            "player_locations": {},
            "player_dimensional_progress": {},
            "npc_states": {},
            "world_changes": [],
            "time_of_day": "morning",
            "elapsed_game_time": 0,
            "dm_narrative_notes": [],
            "dm_planned_events": [],
            "dm_difficulty_adjustments": {},
            "chat_messages": [],
            "team_chat_messages": [],
            "current_node": "waiting_for_players",
            "pending_action": None,
            "awaiting_player_input": False,
            "requires_assessment": False,
            "assessment_context": None,
            "last_updated": datetime.utcnow().isoformat(),
            "party_settings": {
                "max_players": request.max_players,
                "host_player_id": request.host_player_id,
                "invite_token": f"invite_{session_id}",
                "auto_start": request.auto_start
            }
        }

        # Save to Redis
        await redis_manager.save_state(session_id, initial_state)

        logger.info(
            "party_session_created",
            session_id=session_id,
            max_players=request.max_players
        )

        return {
            "session_id": session_id,
            "status": "waiting_for_players",
            "invite_token": f"invite_{session_id}",
            "max_players": request.max_players,
            "current_players": 1,
            "message": "Party created. Share invite token with other players.",
            "websocket_url": f"/ws/session/{session_id}/player/{request.host_player_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "party_session_creation_failed",
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to create party session")


@router.post("/session/{session_id}/join")
async def join_session(
    session_id: str,
    player_id: str,
    character_id: str,
    invite_token: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Join an existing session

    Args:
        session_id: Session ID to join
        player_id: Player ID
        character_id: Character ID
        invite_token: Invite token (for party sessions)
        db: Database session

    Returns:
        Join confirmation
    """
    try:
        # Load session state
        state = await redis_manager.load_state(session_id)

        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if party session requires invite token
        party_settings = state.get("party_settings")
        if party_settings:
            required_token = party_settings.get("invite_token")
            if invite_token != required_token:
                raise HTTPException(status_code=403, detail="Invalid invite token")

            # Check max players
            max_players = party_settings.get("max_players", 4)
            if len(state.get("players", [])) >= max_players:
                raise HTTPException(status_code=400, detail="Session is full")

        # Get character from PostgreSQL
        character = db.query(Character).filter(
            Character.character_id == character_id
        ).first()

        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        # Get cognitive profile from MCP (optional - for AI context)
        cognitive_profile = None
        try:
            cognitive_profile = await mcp_client.get_player_cognitive_profile(player_id)
        except Exception as e:
            logger.warning(
                "mcp_cognitive_profile_unavailable",
                player_id=player_id,
                error=str(e)
            )

        # Convert character to dict
        character_info = character.to_dict()

        # Add player to session
        new_player = {
            "player_id": player_id,
            "character_id": character_id,
            "character_name": character_info.get("name", "Unknown"),
            "cognitive_profile": cognitive_profile or {}
        }

        state["players"].append(new_player)
        state["last_updated"] = datetime.utcnow().isoformat()

        # Save updated state
        await redis_manager.save_state(session_id, state)

        # Broadcast player joined event
        await connection_manager.broadcast_to_session(
            session_id,
            {
                "event": "player_joined_session",
                "player_id": player_id,
                "character_name": character_info.get("name", "Unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        logger.info(
            "player_joined_session",
            session_id=session_id,
            player_id=player_id
        )

        return {
            "session_id": session_id,
            "status": state.get("status"),
            "message": "Joined session successfully",
            "websocket_url": f"/ws/session/{session_id}/player/{player_id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "join_session_failed",
            session_id=session_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to join session")


@router.post("/session/{session_id}/pause")
async def pause_session(session_id: str) -> Dict[str, Any]:
    """Pause active game session"""
    try:
        state = await redis_manager.load_state(session_id)

        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        old_status = state.get("status")
        state["status"] = SessionStatus.PAUSED
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(session_id, state)

        await rabbitmq_client.publish_state_change(
            session_id,
            old_status,
            SessionStatus.PAUSED
        )

        logger.info("session_paused", session_id=session_id)

        return {"session_id": session_id, "status": "paused"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pause_session_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to pause session")


@router.post("/session/{session_id}/resume")
async def resume_session(session_id: str) -> Dict[str, Any]:
    """Resume paused game session"""
    try:
        state = await redis_manager.load_state(session_id)

        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        if state.get("status") != SessionStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Session is not paused")

        old_status = state.get("status")
        state["status"] = SessionStatus.ACTIVE
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(session_id, state)

        await rabbitmq_client.publish_state_change(
            session_id,
            old_status,
            SessionStatus.ACTIVE
        )

        logger.info("session_resumed", session_id=session_id)

        return {"session_id": session_id, "status": "active"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("resume_session_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resume session")


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str) -> Dict[str, Any]:
    """Get current session state"""
    try:
        state = await redis_manager.load_state(session_id)

        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Return safe subset of state (not full internal state)
        return {
            "session_id": state.get("session_id"),
            "status": state.get("status"),
            "campaign_id": state.get("campaign_id"),
            "current_quest_id": state.get("current_quest_id"),
            "current_scene_id": state.get("current_scene_id"),
            "players": state.get("players", []),
            "scene_description": state.get("scene_description", ""),
            "available_actions": state.get("available_actions", []),
            "available_npcs": state.get("available_npcs", []),
            "time_of_day": state.get("time_of_day"),
            "awaiting_player_input": state.get("awaiting_player_input", False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_session_state_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get session state")


@router.get("/session/{session_id}/chat-history")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Get chat message history for session"""
    try:
        state = await redis_manager.load_state(session_id)

        if not state:
            raise HTTPException(status_code=404, detail="Session not found")

        chat_messages = state.get("chat_messages", [])

        # Apply pagination
        total_messages = len(chat_messages)
        paginated_messages = chat_messages[offset:offset + limit]

        return {
            "session_id": session_id,
            "messages": paginated_messages,
            "total": total_messages,
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_chat_history_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get chat history")


# ============================================
# Helper Functions
# ============================================

async def _execute_workflow_initialization(
    session_id: str,
    initial_state: GameSessionState
):
    """
    Execute workflow initialization in background

    Args:
        session_id: Session ID
        initial_state: Initial game state
    """
    try:
        logger.info(
            "executing_workflow_initialization",
            session_id=session_id
        )

        # Run workflow through initialization and scene generation
        result = await game_loop.ainvoke(initial_state)

        # Broadcast initial scene to any connected players
        if result.get("scene_description"):
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "initial_scene",
                    "scene_description": result["scene_description"],
                    "available_actions": result.get("available_actions", []),
                    "available_npcs": result.get("available_npcs", []),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        logger.info(
            "workflow_initialization_complete",
            session_id=session_id,
            status=result.get("status")
        )

    except Exception as e:
        logger.error(
            "workflow_initialization_failed",
            session_id=session_id,
            error=str(e)
        )
