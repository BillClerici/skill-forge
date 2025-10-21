"""
Session models for MongoDB
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class PlayerSessionData(BaseModel):
    """Player data in a session"""
    player_id: str
    character_id: str
    character_name: str
    cognitive_profile: Optional[Dict[str, Any]] = None
    joined_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    is_host: bool = False
    connection_status: Literal["connected", "disconnected"] = "disconnected"


class QuestObjective(BaseModel):
    """Quest objective status"""
    objective_id: str
    description: str
    type: str
    completed: bool = False
    progress_percentage: float = 0.0


class QuestProgress(BaseModel):
    """Quest progress tracking"""
    objectives: List[QuestObjective]
    overall_completion: float = 0.0


class CurrentGameState(BaseModel):
    """Current game state"""
    scene_description: str
    time_of_day: str = "day"
    weather: Optional[str] = None
    available_npcs: List[Dict[str, Any]] = []
    available_actions: List[str] = []
    player_locations: Dict[str, str] = {}  # player_id -> location


class GameSessionV2(BaseModel):
    """Game session document model for MongoDB"""

    # Core Identity
    session_id: UUID
    campaign_id: str  # MongoDB ObjectId string

    # Session Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: Literal["active", "paused", "completed", "abandoned"] = "active"

    # Players
    players: List[PlayerSessionData]

    # Campaign Progress
    progress: Dict[str, Any] = Field(default_factory=dict)

    # Current Game State
    current_state: Optional[CurrentGameState] = None

    # Indexes for quick access
    indices: Dict[str, int] = Field(default_factory=lambda: {
        "conversation_count": 0,
        "action_count": 0,
        "event_count": 0,
        "discovery_count": 0,
        "challenge_count": 0
    })

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
