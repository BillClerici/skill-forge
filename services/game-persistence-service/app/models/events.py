"""
Event models for MongoDB persistence
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID


class EventSource(BaseModel):
    """Source of the event"""
    type: Literal["player", "system", "npc", "dm"]
    player_id: Optional[UUID] = None
    npc_id: Optional[UUID] = None


class GameEventDocument(BaseModel):
    """Game event document for MongoDB"""

    session_id: UUID
    event_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence_number: int

    # Event Classification
    event_type: str

    # Event Source
    source: EventSource

    # Event Data
    data: Dict[str, Any]

    # State Changes
    state_changes: Optional[Dict[str, Any]] = None

    # AI Context
    ai_context: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
