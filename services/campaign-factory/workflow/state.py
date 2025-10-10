"""
Campaign Factory Workflow State Definition
Complete state management for 22-step campaign generation
"""
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime


class AuditEntry(TypedDict):
    """Single audit trail entry"""
    timestamp: str
    node: str
    action: str
    details: Dict[str, Any]
    status: str  # success, error, warning


class StoryIdea(TypedDict):
    """Generated story idea"""
    id: str
    title: str
    summary: str
    themes: List[str]
    estimated_length: str  # Short, Medium, Long
    difficulty_level: str  # Easy, Medium, Hard, Expert


class CampaignCore(TypedDict):
    """Core campaign metadata"""
    campaign_id: Optional[str]
    name: str
    plot: str
    storyline: str
    primary_objectives: List[Dict[str, Any]]  # Each with blooms_level
    universe_id: str
    world_id: str
    region_id: str
    genre: str
    estimated_duration_hours: int
    difficulty_level: str
    target_blooms_level: int


class QuestData(TypedDict):
    """Quest definition"""
    quest_id: Optional[str]
    name: str
    description: str
    objectives: List[Dict[str, Any]]  # Each with blooms_level
    level_1_location_id: str
    level_1_location_name: str
    difficulty_level: str
    estimated_duration_minutes: int
    order_sequence: int
    backstory: str


class PlaceData(TypedDict):
    """Place (Level 2 Location) definition"""
    place_id: Optional[str]
    name: str
    description: str
    level_2_location_id: str
    level_2_location_name: str
    parent_quest_id: str
    scenes: List[str]  # Scene IDs


class SceneData(TypedDict):
    """Scene (Level 3 Location) definition"""
    scene_id: Optional[str]
    name: str
    description: str
    level_3_location_id: str
    level_3_location_name: str
    parent_place_id: str
    npc_ids: List[str]
    discovery_ids: List[str]
    event_ids: List[str]
    challenge_ids: List[str]
    required_knowledge: List[str]  # Knowledge IDs that unlock this scene
    required_items: List[str]  # Item IDs that unlock this scene
    order_sequence: int


class NPCData(TypedDict):
    """NPC definition"""
    npc_id: Optional[str]
    name: str
    species_id: str
    species_name: str
    personality_traits: List[str]
    role: str  # quest_giver, merchant, enemy, ally, neutral
    dialogue_style: str
    backstory: str
    level_3_location_id: str
    is_world_permanent: bool  # True if added to world's NPC pool


class DiscoveryData(TypedDict):
    """Discovery/Knowledge element"""
    discovery_id: Optional[str]
    name: str
    description: str
    knowledge_type: str  # lore, secret, clue, information
    blooms_level: int
    unlocks_scenes: List[str]  # Scene IDs this unlocks


class EventData(TypedDict):
    """Event definition"""
    event_id: Optional[str]
    name: str
    description: str
    event_type: str  # scripted, conditional, random
    trigger_conditions: Dict[str, Any]
    outcomes: List[Dict[str, Any]]


class ChallengeData(TypedDict):
    """Challenge/Obstacle definition"""
    challenge_id: Optional[str]
    name: str
    description: str
    challenge_type: str  # combat, puzzle, social, skill_check
    difficulty: str
    blooms_level: int
    success_rewards: Dict[str, Any]
    failure_consequences: Dict[str, Any]


class CampaignWorkflowState(TypedDict):
    """
    Complete state for Campaign Factory workflow

    Workflow Phases:
    1. Initialization (user selections)
    2. Story Generation (3 ideas, user selection)
    3. Campaign Core Generation (plot, storyline, objectives)
    4. Quest Generation (based on user specs)
    5. Place Generation (Level 2 locations)
    6. Scene Generation (Level 3 locations)
    7. Scene Element Generation (NPCs, discoveries, events, challenges)
    8. Finalization (validation, persistence)
    """

    # Request metadata
    request_id: str
    user_id: str
    character_id: str
    created_at: str

    # User selections (Phase 1)
    universe_id: str
    universe_name: str
    world_id: str
    world_name: str
    region_id: str
    region_name: str
    genre: str
    user_story_idea: Optional[str]  # Optional user input for story direction

    # Story generation (Phase 2)
    story_ideas: List[StoryIdea]
    selected_story_id: Optional[str]
    story_regeneration_count: int
    regenerate_stories: bool  # Flag for story regeneration workflow

    # Campaign specifications (Phase 3)
    campaign_core: Optional[CampaignCore]
    user_approved_core: bool

    # Quest specifications (Phase 4)
    num_quests: int  # User specified
    quest_difficulty: str  # User specified
    quest_playtime_minutes: int  # User specified per quest
    generate_images: bool  # User specified

    # Generated content
    quests: List[QuestData]
    places: List[PlaceData]
    scenes: List[SceneData]
    npcs: List[NPCData]
    discoveries: List[DiscoveryData]
    events: List[EventData]
    challenges: List[ChallengeData]

    # World enrichment tracking
    new_species_ids: List[str]  # Species created and added to world
    new_location_ids: List[str]  # Locations created and added to world
    new_npc_ids: List[str]  # NPCs created and added to world

    # Workflow state management
    current_phase: str  # init, story_gen, core_gen, quest_gen, place_gen, scene_gen, element_gen, finalize
    current_node: str
    errors: List[str]
    warnings: List[str]
    retry_count: int
    max_retries: int

    # Audit trail
    audit_trail: List[AuditEntry]

    # Checkpoints for rollback
    checkpoints: Dict[str, Dict[str, Any]]  # phase_name -> state snapshot

    # Progress tracking
    progress_percentage: int
    status_message: str

    # Results
    final_campaign_id: Optional[str]
    mongodb_campaign_id: Optional[str]
    neo4j_relationships_created: int
    postgres_records_created: int
