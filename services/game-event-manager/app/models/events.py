"""
Event models for the Game Event Manager
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID, uuid4


class EventSource(BaseModel):
    """Source of the event"""
    type: Literal["player", "system", "npc", "dm"]
    player_id: Optional[UUID] = None
    npc_id: Optional[UUID] = None


class GameEvent(BaseModel):
    """Base game event model"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    routing_key: str

    # Session Context
    session_id: UUID
    campaign_id: UUID

    # Event Data
    event_type: str
    payload: Dict[str, Any]

    # Metadata
    source_service: str = "game-event-manager"
    correlation_id: Optional[UUID] = None
    requires_ack: bool = False
    priority: int = Field(default=5, ge=0, le=9)


class SessionCreatedEvent(BaseModel):
    """Event when a game session is created"""
    session_id: UUID
    campaign_id: UUID
    players: list[Dict[str, Any]]
    created_at: datetime


class PlayerActionEvent(BaseModel):
    """Event when a player performs an action"""
    session_id: UUID
    player_id: UUID
    action: str
    timestamp: datetime


class QuestProgressEvent(BaseModel):
    """Event for quest progress updates"""
    session_id: UUID
    quest_id: UUID
    objectives_completed: list[str]
    overall_completion: float
    timestamp: datetime


class DiscoveryEvent(BaseModel):
    """Event when a discovery is made"""
    session_id: UUID
    player_id: UUID
    discovery_id: UUID
    discovery_name: str
    knowledge_gained: list[UUID]
    timestamp: datetime


class ConversationEvent(BaseModel):
    """Event for conversation messages"""
    session_id: UUID
    message_id: UUID
    message_type: Literal["dm_narrative", "npc_dialogue", "player_action", "team_chat", "whisper", "ooc", "system"]
    sender: Dict[str, Any]
    recipient: Dict[str, Any]
    content: Dict[str, Any]
    timestamp: datetime


class ChallengeEvent(BaseModel):
    """Event for challenges"""
    session_id: UUID
    player_id: UUID
    challenge_type: str
    difficulty: int
    success: bool
    rewards: Dict[str, Any]
    timestamp: datetime


class NPCInteractionEvent(BaseModel):
    """Event for NPC interactions"""
    session_id: UUID
    player_id: UUID
    npc_id: UUID
    interaction_type: str
    outcome: str
    affinity_change: float
    timestamp: datetime


class ItemAcquisitionEvent(BaseModel):
    """Event when an item is acquired"""
    session_id: UUID
    player_id: UUID
    item_id: UUID
    item_name: str
    quantity: int
    source: str
    timestamp: datetime


class KnowledgeGainEvent(BaseModel):
    """Event when knowledge is gained"""
    session_id: UUID
    player_id: UUID
    knowledge_id: UUID
    knowledge_name: str
    level: int
    xp_gained: int
    source: str
    timestamp: datetime


class SceneChangeEvent(BaseModel):
    """Event when the scene changes"""
    session_id: UUID
    old_scene_id: Optional[UUID]
    new_scene_id: UUID
    scene_description: str
    available_npcs: list[Dict[str, Any]]
    available_actions: list[str]
    timestamp: datetime
