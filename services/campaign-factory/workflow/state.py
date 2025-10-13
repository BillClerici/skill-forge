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
    level_3_location_name: str
    is_world_permanent: bool  # True if added to world's NPC pool


class KnowledgePartialLevel(TypedDict):
    """Partial understanding level for knowledge"""
    level: int  # 1-4 (25%, 50%, 75%, 100%)
    description: str
    sufficient_for: List[str]  # Objective IDs this level can satisfy


class AcquisitionMethod(TypedDict):
    """Method to acquire knowledge or item"""
    type: str  # npc_conversation, discovery, challenge, event
    entity_id: str  # ID of the NPC, discovery, challenge, or event
    difficulty: str  # Easy, Medium, Hard, Expert
    max_level_obtainable: int  # For knowledge: 1-4, for items: 1 (binary)
    rubric_id: str
    conditions: Dict[str, Any]  # Prerequisites (required_knowledge, required_items, etc.)


class KnowledgeData(TypedDict):
    """Enhanced Knowledge entity with progression tracking"""
    knowledge_id: Optional[str]
    name: str
    description: str
    knowledge_type: str  # skill, lore, clue, secret, technique, insight
    primary_dimension: str  # Which of 7 dimensions this primarily develops
    bloom_level_target: int  # Target Bloom's level (1-6)
    supports_objectives: List[str]  # Quest/Campaign objective IDs

    # Progression system
    partial_levels: List[KnowledgePartialLevel]  # 4 levels of understanding
    acquisition_methods: List[AcquisitionMethod]  # Multiple ways to acquire

    # Metadata
    created_at: Optional[str]
    scene_id: Optional[str]  # Scene where this knowledge originates


class DiscoveryData(TypedDict):
    """Discovery/Knowledge element (DEPRECATED - use KnowledgeData)"""
    discovery_id: Optional[str]
    name: str
    description: str
    knowledge_type: str  # lore, secret, clue, information
    blooms_level: int
    unlocks_scenes: List[str]  # Scene IDs this unlocks

    # NEW: Link to KnowledgeData
    provides_knowledge_ids: List[str]  # Knowledge IDs this discovery provides


class EventData(TypedDict):
    """Event definition"""
    event_id: Optional[str]
    name: str
    description: str
    event_type: str  # scripted, conditional, random
    trigger_conditions: Dict[str, Any]
    outcomes: List[Dict[str, Any]]


class ItemData(TypedDict):
    """Item entity with multiple acquisition paths"""
    item_id: Optional[str]
    name: str
    description: str
    item_type: str  # tool, consumable, key_item, quest_item, equipment, resource
    supports_objectives: List[str]  # Quest/Campaign objective IDs

    # Acquisition system
    acquisition_methods: List[AcquisitionMethod]  # Multiple ways to acquire
    quantity: int
    is_consumable: bool
    is_quest_critical: bool

    # Metadata
    created_at: Optional[str]
    scene_id: Optional[str]


class RubricCriterion(TypedDict):
    """Single evaluation criterion in a rubric"""
    criterion: str  # Name of what's being evaluated
    weight: float  # 0.0-1.0, must sum to 1.0 across all criteria
    bloom_level_target: int  # Target Bloom's level for this criterion (1-6)
    levels: List[Dict[str, Any]]  # Score levels with descriptions


class RubricData(TypedDict):
    """Evaluation rubric for interactions"""
    rubric_id: str
    rubric_type: str  # npc_conversation, environmental_discovery, challenge, dynamic_event
    interaction_name: str
    entity_id: str  # ID of the NPC, discovery, challenge, or event

    # Primary dimension this interaction develops
    primary_dimension: str  # physical, emotional, intellectual, social, spiritual, vocational, environmental

    # Secondary dimensions (can develop multiple)
    secondary_dimensions: List[str]

    # Evaluation criteria
    evaluation_criteria: List[RubricCriterion]

    # Mapping from average score to knowledge/item level
    knowledge_level_mapping: Dict[str, int]  # "1.0-1.75": 1, "1.76-2.5": 2, etc.

    # Rewards based on performance
    rewards_by_performance: Dict[str, Dict[str, List[str]]]  # {"knowledge": {"1": [...], "2": [...]}, "items": {...}}

    # Dimensional experience rewards
    dimensional_rewards: Dict[str, Dict[str, Any]]  # dimension -> {bloom_target, experience_by_score}

    # Consequences for poor performance (optional)
    consequences_by_performance: Optional[Dict[str, Dict[str, Any]]]


class ChallengeData(TypedDict):
    """Enhanced Challenge/Obstacle definition"""
    challenge_id: Optional[str]
    name: str
    description: str

    # Challenge classification
    challenge_type: str  # See expanded list below
    challenge_category: str  # mental, physical, social, emotional, spiritual, vocational, environmental
    primary_dimension: str  # Which dimension this primarily develops
    secondary_dimensions: List[str]  # Other dimensions this engages

    # Difficulty and requirements
    difficulty: str  # Easy, Medium, Hard, Expert
    blooms_level: int
    required_knowledge: List[Dict[str, Any]]  # [{"knowledge_id": "kg_001", "min_level": 2}]
    required_items: List[Dict[str, Any]]  # [{"item_id": "item_001", "quantity": 1}]

    # Rewards system
    provides_knowledge_ids: List[str]  # Knowledge IDs this challenge can provide
    provides_item_ids: List[str]  # Item IDs this challenge can provide
    rubric_id: str  # Link to evaluation rubric

    # Legacy support
    success_rewards: Dict[str, Any]
    failure_consequences: Dict[str, Any]


"""
EXPANDED CHALLENGE TYPES:

A. Mental Challenges (Intellectual):
- riddle, cipher, memory_game, strategy_game, mathematical_puzzle, lateral_thinking

B. Physical Challenges (Physical):
- combat, obstacle_course, endurance_test, precision_task, reflex_challenge, strength_test

C. Social Challenges (Social):
- negotiation, persuasion, deception_detection, team_coordination, leadership_test, cultural_navigation

D. Emotional Challenges (Emotional):
- stress_management, empathy_scenario, trauma_processing, temptation_resistance, fear_confrontation, relationship_repair

E. Spiritual Challenges (Spiritual):
- moral_dilemma, purpose_quest, value_conflict, sacrifice_decision, forgiveness_scenario, faith_test

F. Vocational Challenges (Vocational):
- craft_mastery, professional_puzzle, skill_competition, innovation_challenge, apprenticeship_test, quality_control

G. Environmental Challenges (Environmental):
- ecosystem_management, resource_optimization, pollution_solution, wildlife_interaction, climate_adaptation, conservation_decision
"""


class DimensionalMaturity(TypedDict):
    """Character maturity in one dimension"""
    current_level: int  # 1-6 (Bloom's levels)
    bloom_level: str  # Remember, Understand, Apply, Analyze, Evaluate, Create
    experience_points: int
    next_level_threshold: int
    strengths: List[str]
    growth_areas: List[str]


class CharacterDevelopmentProfile(TypedDict):
    """Multi-dimensional character development tracking"""
    character_id: str
    dimensional_maturity: Dict[str, DimensionalMaturity]  # 7 dimensions

    # Balance metrics
    balance_score: float  # Average across all dimensions
    most_developed: List[str]  # Top 3 dimensions
    least_developed: List[str]  # Bottom 3 dimensions
    recommended_focus: List[str]  # Dimensions to work on for balance

    # Knowledge and items acquired
    acquired_knowledge: Dict[str, Dict[str, Any]]  # knowledge_id -> {current_level, max_level, history}
    acquired_items: Dict[str, Dict[str, Any]]  # item_id -> {quantity, acquisition_source, etc.}

    # Quest progression
    quest_progress: Dict[str, Dict[str, Any]]  # quest_id -> {status, objectives_completed, requirements_met}


class QuestObjective(TypedDict):
    """Quest objective with requirements"""
    objective_id: str
    description: str
    required_knowledge: List[Dict[str, Any]]  # [{"knowledge_id": "kg_001", "min_level": 2}]
    required_items: List[Dict[str, Any]]  # [{"item_id": "item_001", "quantity": 1}]
    status: str  # not_started, in_progress, completed


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
    region_data: Dict[str, Any]  # Full region details (description, backstory, climate, terrain, inhabitants)
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

    # User approval flags for workflow gates
    user_approved_quests: Optional[bool]  # Phase 4 approval
    user_approved_places: Optional[bool]  # Phase 5 approval

    # Generated content
    quests: List[QuestData]
    places: List[PlaceData]
    scenes: List[SceneData]
    npcs: List[NPCData]

    # Legacy elements (being phased out)
    discoveries: List[DiscoveryData]
    events: List[EventData]
    challenges: List[ChallengeData]

    # NEW: Enhanced progression system
    knowledge_entities: List[KnowledgeData]  # All knowledge in campaign
    item_entities: List[ItemData]  # All items in campaign
    rubrics: List[RubricData]  # All evaluation rubrics

    # Character development
    character_profile: Optional[CharacterDevelopmentProfile]  # Player character's development

    # World enrichment tracking
    new_species_ids: List[str]  # Species created and added to world
    new_location_ids: List[str]  # DEPRECATED: Use new_locations instead
    new_locations: List[Dict[str, Any]]  # Full details of new locations (id, name, type, description, level)
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
