"""
Pydantic Models for API Requests
These are used by FastAPI for request validation
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SoloSessionRequest(BaseModel):
    """Request to start solo session"""
    campaign_id: str = Field(..., description="Campaign ID to start")
    player_id: str = Field(..., description="Player ID")
    character_id: str = Field(..., description="Character ID to use")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional session settings")


class PartySessionRequest(BaseModel):
    """Request to create multiplayer session"""
    campaign_id: str = Field(..., description="Campaign ID to start")
    host_player_id: str = Field(..., description="Host player ID")
    host_character_id: str = Field(..., description="Host character ID")
    max_players: int = Field(default=4, description="Maximum players allowed")
    auto_start: bool = Field(default=False, description="Auto-start when all players join")
    invited_player_ids: Optional[List[str]] = Field(default_factory=list, description="Pre-invited player IDs")
    is_public: bool = Field(default=False, description="Allow public joining")
    game_mode: str = Field(default="turn_based", description="Game mode: turn_based or cooperative")
    scheduled_start: Optional[str] = Field(default=None, description="Scheduled start time (ISO format)")
    estimated_session_duration_minutes: Optional[int] = Field(default=None, description="Expected session duration")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional session settings")
