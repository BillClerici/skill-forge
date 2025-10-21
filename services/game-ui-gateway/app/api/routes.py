"""
REST API routes for Game UI Gateway
"""
from fastapi import APIRouter
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["gateway"])


@router.get("/status")
async def get_status():
    """Get gateway status"""
    from ..main import connection_manager

    return {
        "status": "healthy",
        "service": "game-ui-gateway",
        "active_sessions": connection_manager.get_session_count(),
        "active_connections": connection_manager.get_connection_count(),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/sessions/{session_id}/players")
async def get_connected_players(session_id: str):
    """Get connected players for a session"""
    from ..main import connection_manager
    from uuid import UUID

    players = connection_manager.get_connected_players(UUID(session_id))

    return {
        "session_id": session_id,
        "player_count": len(players),
        "player_ids": list(players)
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "game-ui-gateway",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "game-ui-gateway",
        "version": "1.0.0",
        "description": "WebSocket gateway for SkillForge game UI"
    }
