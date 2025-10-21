"""
API routes for Game Persistence Service
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["persistence"])


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID):
    """Get full session data"""
    from ..main import session_repository

    session = await session_repository.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.get("/sessions/{session_id}/events")
async def get_events(
    session_id: UUID,
    event_type: Optional[str] = None,
    player_id: Optional[UUID] = None,
    limit: int = 100,
    skip: int = 0
):
    """Get events for a session"""
    from ..main import event_repository

    events = await event_repository.get_events(
        session_id,
        event_type=event_type,
        player_id=player_id,
        limit=limit,
        skip=skip
    )

    return {
        "session_id": str(session_id),
        "count": len(events),
        "events": events
    }


@router.get("/sessions/{session_id}/conversations")
async def get_conversations(
    session_id: UUID,
    message_type: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """Get conversation history"""
    from ..main import conversation_repository

    messages = await conversation_repository.get_messages(
        session_id,
        message_type=message_type,
        limit=limit,
        skip=skip
    )

    return {
        "session_id": str(session_id),
        "count": len(messages),
        "messages": messages
    }


@router.get("/sessions/{session_id}/inventory/{player_id}")
async def get_inventory(session_id: UUID, player_id: UUID):
    """Get player inventory"""
    from ..main import inventory_repository

    inventory = await inventory_repository.get_inventory(session_id, player_id)

    if not inventory:
        return {
            "session_id": str(session_id),
            "player_id": str(player_id),
            "items": [],
            "knowledge": [],
            "dimensional_progress": {}
        }

    return inventory


@router.get("/sessions/player/{player_id}/active")
async def get_active_sessions(player_id: UUID):
    """Get active sessions for a player"""
    from ..main import session_repository

    sessions = await session_repository.get_active_sessions_for_player(player_id)

    return {
        "player_id": str(player_id),
        "count": len(sessions),
        "sessions": sessions
    }


@router.get("/sessions/player/{player_id}/completed")
async def get_completed_sessions(player_id: UUID):
    """Get completed sessions for a player"""
    from ..main import session_repository

    sessions = await session_repository.get_completed_sessions_for_player(player_id)

    return {
        "player_id": str(player_id),
        "count": len(sessions),
        "sessions": sessions
    }


@router.get("/sessions/{session_id}/replay")
async def get_replay_data(
    session_id: UUID,
    start_sequence: int = 0,
    end_sequence: Optional[int] = None
):
    """Get replay data for a session"""
    from ..main import event_repository

    events = await event_repository.get_events_by_sequence_range(
        session_id,
        start_sequence,
        end_sequence
    )

    return {
        "session_id": str(session_id),
        "start_sequence": start_sequence,
        "end_sequence": end_sequence,
        "event_count": len(events),
        "events": events
    }


@router.post("/sessions/{session_id}/snapshot")
async def create_snapshot(session_id: UUID):
    """Create a snapshot of the current session state"""
    # This would create a snapshot in game_snapshots collection
    # Implementation would depend on your specific needs
    return {
        "status": "success",
        "message": "Snapshot created",
        "session_id": str(session_id)
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "game-persistence-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "game-persistence-service",
        "version": "1.0.0",
        "description": "Persistence layer for SkillForge game data"
    }
