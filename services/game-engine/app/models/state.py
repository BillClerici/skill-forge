"""
Game Session State Models
Defines the complete state structure for game sessions
"""
from typing import List, Dict, Optional, Any
from typing_extensions import TypedDict
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Session lifecycle states"""
    INITIALIZING = "initializing"
    WAITING_FOR_PLAYERS = "waiting_for_players"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"


class ChatMessageType(str, Enum):
    """Types of messages in game chat"""
    DM_NARRATIVE = "dm_narrative"
    DM_NPC_DIALOGUE = "dm_npc_dialogue"
    DM_SYSTEM = "dm_system"
    DM_ASSESSMENT = "dm_assessment"
    PLAYER_ACTION = "player_action"
    PLAYER_OOC = "player_ooc"
    MEDIA_SCENE = "media_scene"
    MEDIA_AUDIO = "media_audio"
    LEVEL_UP = "level_up"
    QUEST_UPDATE = "quest_update"


class TeamChatChannel(str, Enum):
    """Team chat channels"""
    PARTY = "party"
    WHISPER = "whisper"
    OOC = "ooc"
    STRATEGY = "strategy"
    SYSTEM = "system"


# ============================================
# Core Data Structures
# ============================================

class MediaAttachment(TypedDict, total=False):
    """Media embedded in a message"""
    media_id: str
    media_type: str  # image, video, audio, document
    url: str
    thumbnail_url: Optional[str]
    caption: Optional[str]
    alt_text: str
    width: Optional[int]
    height: Optional[int]
    duration: Optional[int]
    size_bytes: Optional[int]
    mime_type: str


class ChatMessage(TypedDict, total=False):
    """Single message in game chat"""
    message_id: str
    session_id: str
    timestamp: str
    message_type: ChatMessageType
    sender: str
    sender_display_name: str
    content: str
    formatted_content: Optional[str]
    media_attachments: List[MediaAttachment]
    related_entity_id: Optional[str]
    related_entity_type: Optional[str]
    scene_id: Optional[str]
    quest_id: Optional[str]
    triggered_by_action: Optional[str]
    assessment_id: Optional[str]
    importance: str
    style: Optional[str]
    collapse_after: Optional[int]
    visible_to_players: List[str]
    player_id: Optional[str]
    requires_response: bool
    available_actions: List[str]
    quick_replies: List[str]


class TeamChatMessage(TypedDict, total=False):
    """Team chat message"""
    message_id: str
    session_id: str
    channel: TeamChatChannel
    timestamp: str
    sender_id: str
    sender_character_name: str
    sender_display_name: str
    recipient_ids: List[str]
    content: str
    formatted_content: Optional[str]
    is_edited: bool
    edited_at: Optional[str]
    replied_to_message_id: Optional[str]
    mentioned_player_ids: List[str]
    is_urgent: bool
    reactions: Dict[str, List[str]]  # emoji -> player_ids
    visible_to_dm: bool
    deleted: bool
    deleted_at: Optional[str]
    attachments: List[str]
    poll: Optional[Dict[str, Any]]


class NPCState(TypedDict, total=False):
    """Runtime NPC state"""
    npc_id: str
    current_location: str
    current_mood: str
    is_present: bool
    affinity_with_players: Dict[str, int]  # player_id -> affinity
    recent_interactions: List[str]
    knowledge_shared: Dict[str, List[str]]  # player_id -> knowledge_ids
    active_quest_status: Dict[str, str]


class DimensionalMaturity(TypedDict, total=False):
    """Player dimensional progress"""
    dimension: str
    current_level: int  # Bloom's level 1-6
    bloom_level_name: str  # Remember, Understand, Apply, Analyze, Evaluate, Create
    experience_points: int
    next_level_threshold: int
    total_xp_earned: int


class PlayerSessionData(TypedDict, total=False):
    """Player data in active session"""
    player_id: str
    character_id: str
    character_name: str
    current_blooms_levels: Dict[str, int]  # dimension -> level
    session_interactions: int
    session_dimensional_xp: Dict[str, int]
    cognitive_profile: Dict[str, Any]
    is_connected: bool
    last_action_timestamp: str


class ConversationTurn(TypedDict, total=False):
    """Single conversation turn"""
    player_id: str
    npc_id: str
    player_statement: str
    npc_response: str
    timestamp: str
    affinity_change: int


class PlayerAction(TypedDict, total=False):
    """Player action record"""
    action_id: str
    player_id: str
    action_type: str  # move, talk, examine, use_item, attempt_challenge
    target_id: Optional[str]
    parameters: Dict[str, Any]
    timestamp: str
    success: bool
    result: str


class GameEvent(TypedDict, total=False):
    """Game event record"""
    event_id: str
    event_type: str
    triggered_by: str
    description: str
    timestamp: str
    affected_entities: List[str]


class WorldChange(TypedDict, total=False):
    """Permanent world state change"""
    change_id: str
    change_type: str  # npc_moved, item_taken, location_unlocked, event_triggered
    affected_entity_id: str
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    caused_by_player: str
    timestamp: str


class EventData(TypedDict, total=False):
    """Dynamic event data"""
    event_id: str
    event_type: str
    name: str
    description: str
    trigger_conditions: Dict[str, Any]
    consequences: Dict[str, Any]


class ChallengeData(TypedDict, total=False):
    """Challenge data"""
    challenge_id: str
    name: str
    description: str
    challenge_category: str
    difficulty: str
    required_knowledge: List[str]
    rubric_id: str


class NPCData(TypedDict, total=False):
    """NPC data"""
    npc_id: str
    name: str
    title: Optional[str]
    personality_traits: Dict[str, int]
    dialogue_style: Dict[str, str]
    current_mood: str
    rubric_id: str


# ============================================
# Main Game Session State
# ============================================

class GameSessionState(TypedDict, total=False):
    """Complete game session state for LangGraph workflow"""

    # Session metadata
    session_id: str
    campaign_id: str
    started_at: str
    status: SessionStatus

    # Player(s)
    players: List[PlayerSessionData]
    current_turn_player_id: Optional[str]

    # Campaign progress
    current_quest_id: str
    current_place_id: str
    current_scene_id: str
    completed_quest_ids: List[str]
    completed_scene_ids: List[str]

    # Scene context
    scene_description: str
    available_npcs: List[NPCData]
    available_actions: List[str]
    visible_items: List[str]
    active_events: List[EventData]
    active_challenges: List[ChallengeData]

    # Interaction history (living world memory)
    conversation_history: List[ConversationTurn]
    action_history: List[PlayerAction]
    event_log: List[GameEvent]

    # Player state
    player_inventories: Dict[str, List[str]]  # player_id -> item_ids
    player_knowledge: Dict[str, Dict[str, int]]  # player_id -> {knowledge_id: level}
    player_locations: Dict[str, str]  # player_id -> location_id
    player_dimensional_progress: Dict[str, Dict[str, DimensionalMaturity]]

    # World state (living world)
    npc_states: Dict[str, NPCState]
    world_changes: List[WorldChange]
    time_of_day: str
    elapsed_game_time: int  # minutes

    # DM context
    dm_narrative_notes: List[str]
    dm_planned_events: List[Dict[str, Any]]
    dm_difficulty_adjustments: Dict[str, Any]

    # Chat history
    chat_messages: List[ChatMessage]
    team_chat_messages: List[TeamChatMessage]

    # Workflow state
    current_node: str
    pending_action: Optional[Dict[str, Any]]
    awaiting_player_input: bool
    requires_assessment: bool
    assessment_context: Optional[Dict[str, Any]]
    last_updated: str

    # Assessment
    last_assessment: Optional[Dict[str, Any]]


# ============================================
# Action Interpretation
# ============================================

class ActionInterpretation(TypedDict, total=False):
    """Interpreted player action"""
    action_type: str  # move, talk, examine, use_item, attempt_challenge
    target_id: Optional[str]
    parameters: Dict[str, Any]
    success_probability: float
    player_input: str


class NPCDialogueResponse(TypedDict, total=False):
    """NPC dialogue generation response"""
    dialogue: str
    affinity_change: int
    knowledge_revealed: List[str]
    rubric_id: str
    performance_indicators: Dict[str, Any]


class AssessmentResult(TypedDict, total=False):
    """Performance assessment result"""
    rubric_id: str
    criterion_scores: Dict[str, Dict[str, Any]]  # criterion -> {score, evidence, feedback}
    overall_score: float
    performance_level: int  # 1-4
    strengths: List[str]
    growth_areas: List[str]
    knowledge_rewards: List[Dict[str, Any]]
    item_rewards: List[Dict[str, Any]]
    dimensional_xp: Dict[str, int]  # dimension -> xp
    timestamp: str


# ============================================
# Session Creation Requests
# ============================================

class SoloSessionRequest(TypedDict, total=False):
    """Request to start solo session"""
    campaign_id: str
    character_id: str
    settings: Dict[str, Any]


class PartySessionRequest(TypedDict, total=False):
    """Request to create multiplayer session"""
    campaign_id: str
    host_character_id: str
    invited_player_ids: List[str]
    max_players: int
    is_public: bool
    game_mode: str  # turn_based or cooperative
    scheduled_start: Optional[str]
    estimated_session_duration_minutes: Optional[int]
    settings: Dict[str, Any]
