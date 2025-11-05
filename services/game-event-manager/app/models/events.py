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


# NEW: Hierarchical Objective Events

class ObjectiveProgressEvent(BaseModel):
    """Event for any objective progress update"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID
    campaign_id: UUID

    # Objective identification
    objective_id: str
    objective_type: Literal["campaign", "quest", "child"]  # Level in hierarchy
    objective_subtype: Optional[str] = None  # For child: "discovery", "challenge", "event", "conversation"
    description: str

    # Progress information
    previous_status: str  # "not_started", "in_progress", "completed"
    new_status: str
    completion_percentage: float  # 0-100
    rubric_scores: Optional[Dict[str, float]] = None  # If evaluated with rubrics

    # Trigger information
    triggered_by: str  # "discovery", "challenge", "event", "conversation", "item_acquisition", "knowledge_gain"
    trigger_entity_id: Optional[str] = None  # ID of entity that triggered progress

    # Cascade updates
    cascade_updates: list[Dict[str, Any]] = []  # Parent objectives affected

    # Player info
    player_id: UUID


class ChildObjectiveCompletedEvent(BaseModel):
    """Event when a child objective (discovery/challenge/event/conversation) is completed"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID
    campaign_id: UUID
    player_id: UUID

    # Child objective details
    child_objective_id: str
    child_objective_type: Literal["discovery", "challenge", "event", "conversation"]
    description: str

    # Parent objectives
    quest_objective_id: str
    quest_objective_description: str
    campaign_objective_ids: list[str]

    # Performance evaluation
    rubric_score: float  # 1.0 - 4.0 scale
    completion_quality: Literal["minimal", "good", "excellent"]  # Based on rubric score
    evaluation_details: Dict[str, Any]  # Detailed rubric breakdown

    # Rewards earned
    rewards_earned: Dict[str, Any]  # Knowledge, items, experience, dimensional XP

    # Progression impact
    quest_objective_progress: float  # Updated % for parent quest objective
    campaign_objective_progress: list[Dict[str, float]]  # Updated % for each campaign objective


class QuestObjectiveCompletedEvent(BaseModel):
    """Event when a quest objective is completed (all required child objectives done)"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID
    campaign_id: UUID
    player_id: UUID

    # Quest objective details
    quest_objective_id: str
    quest_id: str
    quest_name: str
    description: str

    # Parent campaign objectives
    campaign_objective_ids: list[str]

    # Completion details
    completed_child_objectives: list[str]  # All child objective IDs completed
    total_child_objectives: int
    completion_timestamp: datetime

    # Overall quality
    average_rubric_score: float  # Average across all child objectives
    overall_quality: Literal["minimal", "good", "excellent"]

    # Rewards
    rewards: Dict[str, Any]  # Cumulative rewards

    # Campaign progression
    campaign_objective_progress: list[Dict[str, float]]  # Updated % for campaign objectives


class CampaignObjectiveCompletedEvent(BaseModel):
    """Event when a major campaign objective is completed"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID
    campaign_id: UUID
    player_id: UUID

    # Campaign objective details
    campaign_objective_id: str
    description: str
    bloom_level: int
    narrative_significance: str  # Why this matters to the story

    # Completion tracking
    completion_timestamp: datetime
    contributing_quest_objectives: list[str]  # All quest objectives that contributed
    contributing_child_objectives: list[str]  # All child objectives that contributed

    # Overall performance
    overall_quality_score: float  # Average rubric score across all child objectives
    dimensional_development: Dict[str, Any]  # How each dimension progressed

    # Major rewards
    rewards: Dict[str, Any]  # Major milestone rewards

    # Narrative unlocks
    narrative_unlock: Optional[str] = None  # New content available (quest, scene, NPC)
    unlocked_content_ids: list[str] = []  # IDs of unlocked quests, scenes, etc.

    # Campaign progress
    campaign_completion_percentage: float  # Overall campaign completion


class ObjectiveCascadeUpdateEvent(BaseModel):
    """Event for cascading objective updates (child -> quest -> campaign)"""
    message_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID
    campaign_id: UUID
    player_id: UUID

    # Trigger
    trigger_objective_id: str
    trigger_objective_type: Literal["child", "quest", "campaign"]

    # Cascade chain
    updated_objectives: list[Dict[str, Any]]  # All objectives updated in cascade
    # Format: [{"objective_id": "...", "type": "...", "old_status": "...", "new_status": "...", "completion_%": ...}]

    # Summary
    total_objectives_updated: int
    quests_completed: list[str]
    campaign_objectives_completed: list[str]
