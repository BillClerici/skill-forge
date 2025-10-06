# AI Campaign Factory - Architecture & Design 🎭⚔️

## Executive Summary

The **AI Campaign Factory** is an intelligent campaign generation engine that creates rich, personalized RPG campaigns by analyzing existing World data (properties, backstory, species, regions, locations) and tailoring narrative experiences to individual player Bloom's Taxonomy levels and cognitive progress.

---

## 🎯 Core Value Propositions

### 1. **World-Integrated Campaign Generation**
- Leverages ALL existing world data: properties, backstory, timeline, species, regions, locations
- Creates narratives that feel native to the world's lore and themes
- Ensures internal consistency with established world facts

### 2. **Bloom's Taxonomy-Driven Personalization**
- Dynamically adjusts challenge difficulty based on player's cognitive mastery levels
- Provides scaffolded learning experiences (Remember → Understand → Apply → Analyze → Evaluate → Create)
- Tracks progression and adjusts in real-time

### 3. **Multi-Dimensional Engagement**
- **Stories**: Rich narrative arcs tied to world backstory and timeline events
- **Puzzles**: Logic-based challenges using world-specific resources and mechanics
- **Riddles**: Linguistic/conceptual challenges drawing from world mythology
- **Competitions**: Skill-based contests involving world species and cultures
- **Activities**: Exploration, crafting, diplomacy using world properties
- **Goals & Outcomes**: Measurable objectives with branching consequences

---

## 🏗️ Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE (Django)                          │
│  ┌──────────────────┐        ┌────────────────────────────────┐   │
│  │  World Detail    │        │  AI Campaign Factory Modal      │   │
│  │  - Generate      │───────▶│  - World Selection (pre-filled) │   │
│  │    Campaign      │        │  - Target Bloom's Level         │   │
│  │  - View Existing │        │  - Campaign Length (quests)     │   │
│  │    Campaigns     │        │  - Focus Areas (skills)         │   │
│  └──────────────────┘        │  - Player Selection             │   │
│                               │  - Generate Images Checkbox     │   │
│                               └────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                    DJANGO REST API LAYER                            │
│  POST   /api/campaign-factory/initiate/     - Start workflow       │
│  GET    /api/campaign-factory/{id}/status/  - Poll progress        │
│  GET    /api/campaign-factory/{id}/result/  - Get final campaign   │
│  POST   /api/campaign-factory/{id}/cancel/  - Cancel generation    │
└────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                   MESSAGE QUEUE (RabbitMQ)                          │
│  campaign_factory_jobs  │  campaign_factory_progress               │
└────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│             CAMPAIGN FACTORY SERVICE (LangGraph)                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  LangGraph Workflow (10 Nodes + Conditional Routing)         │  │
│  │                                                               │  │
│  │  1. Load World Context    ──▶ 2. Analyze Player Profile      │  │
│  │     - World properties          - Bloom's levels              │  │
│  │     - Timeline events           - Skill levels                │  │
│  │     - Species/Regions           - Learning patterns           │  │
│  │     - Locations                                               │  │
│  │                                                               │  │
│  │  3. Generate Campaign Arc  ──▶ 4. Create Quest Chain         │  │
│  │     - Main storyline            - 3-7 interconnected quests   │  │
│  │     - Narrative hooks           - Progressive difficulty      │  │
│  │     - Character arcs            - Bloom's alignment           │  │
│  │                                                               │  │
│  │  5. Design Challenges      ──▶ 6. Generate Encounters        │  │
│  │     - Puzzles (world logic)     - Species interactions        │  │
│  │     - Riddles (mythology)       - Location-based events       │  │
│  │     - Activities                - Combat/social/exploration   │  │
│  │                                                               │  │
│  │  7. Create Rewards         ──▶ 8. Generate Branches          │  │
│  │     - Items (world resources)   - Decision points            │  │
│  │     - Skills (Bloom's match)    - Multiple outcomes           │  │
│  │     - Knowledge unlocks         - Failure paths               │  │
│  │                                                               │  │
│  │  9. Generate Images (optional)                                │  │
│  │     - Quest locations                                         │  │
│  │     - Key NPCs                                                │  │
│  │     - Important items                                         │  │
│  │                                                               │  │
│  │  10. Finalize & Validate  ──▶ END                             │  │
│  │     - Internal consistency                                    │  │
│  │     - Bloom's progression                                     │  │
│  │     - Save to MongoDB                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                         DATA STORES                                 │
│  MongoDB: campaign_definitions, quest_definitions, encounter_defs  │
│  PostgreSQL: member_cognitive_progress, activity_logs              │
│  Neo4j: Campaign knowledge graph, quest relationships               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Campaign Structure

### **Campaign Goal Hierarchy**

Each campaign has a clear goal structure that drives player motivation:

**Primary Goals (1-3 required)**:
- Main objectives that define campaign success
- Must be achieved to complete the campaign
- Aligned with world genre and narrative arc
- Example: "Prevent the Eternal Weave Crisis", "Discover the source of Promise ore corruption"

**Secondary Goals (1-3 optional)**:
- Enhancement objectives that enrich the experience
- Provide additional rewards and narrative depth
- Unlock alternate endings or bonus content
- Example: "Resolve Guild conflict", "Establish alliance with Pattern Wolves"

**Goal → Quest → Challenge Hierarchy**:
```
Campaign (1 Primary + 2 Secondary Goals)
  ├── Quest 1 (3-5 Challenges) → Advances Primary Goal
  ├── Quest 2 (3-5 Challenges) → Advances Primary Goal
  ├── Quest 3 (3-5 Challenges) → Advances Secondary Goal A
  ├── Quest 4 (3-5 Challenges) → Advances Primary Goal
  └── Quest 5 (3-5 Challenges) → Advances Secondary Goal B + Resolution
```

### **Quest Composition**

**Structure**: Each quest contains a sequence of challenges that lead to an objective

**Components**:
1. **Quest Objective**: Clear success criteria (e.g., "Recover stolen memory-silk")
2. **Challenge Sequence**: 3-5 escalating challenges that progress toward objective
3. **Location Context**: Takes place at specific world location(s)
4. **NPC Interactions**: Involves world species inhabiting the location
5. **Bloom's Progression**: Challenges range across cognitive levels

**Example Quest Flow**:
```
Quest: "Echoes in the Quarries"
Objective: Discover source of reality distortions in Shattered Promise Quarries

Challenge 1 (Remember): Navigate to quarry, identify Promise ore types
  └─ Location: Shattered Promise Quarries entrance
  └─ NPCs: Guild surveyor (Thread Weaver)

Challenge 2 (Understand): Interpret Pattern Wolf warnings about danger zones
  └─ Location: Deep quarry tunnels
  └─ NPCs: Pattern Wolf pack

Challenge 3 (Apply): Repair minor reality tear using learned technique
  └─ Location: Unstable quarry chamber
  └─ NPCs: Trapped miner (Thread Weaver)

Challenge 4 (Analyze): Investigate divine thread corruption patterns
  └─ Location: Ancient excavation site
  └─ NPCs: Corrupted Dream Unraveler

Challenge 5 (Evaluate): Decide whether to seal or study the corruption source
  └─ Location: Core reality breach
  └─ NPCs: Guild Master, Council representative

→ Quest Objective Achieved: Source identified + decision made
```

### **Challenge Taxonomy**

Challenges represent the core player interactions. Each challenge type tests different abilities:

| Challenge Type | Description | Player Actions Required | Bloom's Levels |
|---------------|-------------|------------------------|----------------|
| **Combat** | Engage foes in tactical confrontations | Strategy, resource management, skill execution | Apply, Analyze |
| **Skill-based Trials** | Tests of specific abilities (lockpicking, crafting, etc.) | Precision, technique application, timing | Remember, Apply |
| **Exploration** | Navigate obstacles, find paths, discover locations | Observation, mapping, environmental interaction | Remember, Understand |
| **Social Encounters** | Negotiation, persuasion, diplomacy | Communication, empathy, reading intentions | Understand, Evaluate |
| **Puzzles** | Intellectual problems requiring logical solutions | Pattern recognition, deduction, problem-solving | Understand, Analyze |
| **Moral Dilemmas** | Ethical choices with consequences | Judgment, values assessment, decision-making | Evaluate, Create |
| **Environmental Hazards** | Traps, natural dangers, reality distortions | Awareness, adaptation, risk mitigation | Apply, Analyze |
| **Mystery** | Uncovering hidden information through investigation | Research, deduction, connecting clues | Analyze, Evaluate |

**Challenge Design Principles**:
- Each challenge is Bloom's-aligned (matched to cognitive level)
- Challenges occur at specific world locations
- Species (NPCs) inhabit locations and interact with players
- Players must demonstrate appropriate Bloom's behavior level to succeed
- AI evaluates player responses for cognitive level matching

## 📊 Campaign Generation Recommendations

### **Recommendation 1: Multi-Layered Narrative Architecture** ⭐ RECOMMENDED

**Concept**: Create campaigns with 3 interwoven narrative layers that adapt to player Bloom's level

#### **Layer 1: Surface Story (Remember/Understand)**
- **What**: Simple, linear narrative
- **Example from Threadweave**:
  - "The Promise Archives have been burgled! Help the Guild of Master Weavers recover stolen memory-silk before it destabilizes local reality"
- **Activities**:
  - **Exploration**: Visit The Shattered Promise Quarries, interview Pattern Wolves
  - **Puzzle**: Match memory fragments to their original owners
  - **Competition**: Textile-weaving contest to prove competence to the Guild
  - **Goal**: Recover 5/7 stolen memory-silks
- **Bloom's Focus**: Recognition, recall, pattern matching

#### **Layer 2: Hidden Depth (Apply/Analyze)**
- **What**: Reveals complex connections to world history
- **Example from Threadweave**:
  - "The theft is actually an inside job by corrupted Dream Unravelers trying to trigger a second Great Unraveling by rewriting the Memory Market Collapse event"
- **Activities**:
  - **Puzzle**: Decode timeline manipulation attempts using Promise ore resonance
  - **Riddle**: Interpret prophecies from "The First Thread of Creation" mythology
  - **Investigation**: Analyze divine thread corruption patterns
  - **Goal**: Prevent timeline alteration while maintaining political neutrality
- **Bloom's Focus**: Application of concepts, causal analysis, systems thinking

#### **Layer 3: Meta-Narrative (Evaluate/Create)**
- **What**: Player shapes world evolution
- **Example from Threadweave**:
  - "Discovery: The theft was orchestrated by the world itself (conscious Promise fragments) testing if Thread Weavers are worthy successors to manage reality"
- **Activities**:
  - **Moral Choice**: Judge whether Thread Weavers should continue monopolizing Promise ore
  - **Creative Solution**: Design new reality-stabilization protocols
  - **World-Building**: Establish new societal structures or guilds
  - **Goal**: Define the future relationship between mortals and divine threads
- **Bloom's Focus**: Ethical evaluation, creative synthesis, paradigm creation

**Why This Works**:
- ✅ Same campaign serves players at all Bloom's levels (inclusive design)
- ✅ Natural progression from simple to complex thinking
- ✅ Leverages world's rich backstory (Promise shatter → Great Unraveling → Memory Market Collapse)
- ✅ Integrates all world properties (Promise ore, timeline events, species, locations)
- ✅ Creates mentoring moments when players discover deeper layers
- ✅ Provides multiple "win states" depending on cognitive level

---

### **Recommendation 2: Bloom's-Aligned Challenge Matrix** ⭐ RECOMMENDED

**Concept**: Design each quest with 6 challenge types mapped to Bloom's levels

| Bloom's Level | Challenge Type | Threadweave Example |
|--------------|----------------|---------------------|
| **Remember** | **Scavenger Hunt** | Collect 5 different Promise ore types from specified locations in Sorrowspun Reaches |
| **Understand** | **Translation/Decoding** | Interpret Pattern Wolf howl patterns to find hidden memory pools |
| **Apply** | **Crafting/Synthesis** | Use Memory weaving techniques to repair a reality tear in The Unraveled Wastes |
| **Analyze** | **Investigation/Forensics** | Determine which God-Thread manifestation caused recent quarry accidents by analyzing divine thread signatures |
| **Evaluate** | **Judgment/Debate** | Mediate dispute between Guild of Master Weavers and Council of Dream Interpreters over mining quotas |
| **Create** | **Innovation/Design** | Invent new binding ritual to stabilize corrupted dream entities in the Grand Loom Cathedral |

**Campaign Structure**:
```
Quest 1: Introduction (80% Remember/Understand, 20% Apply)
Quest 2: Rising Action (50% Understand/Apply, 30% Analyze, 20% Remember)
Quest 3: Development (40% Apply, 40% Analyze, 20% Evaluate)
Quest 4: Climax (30% Analyze, 30% Evaluate, 40% Create)
Quest 5: Resolution (20% Each level - showcase mastery)
```

**Adaptive Difficulty**:
- **If player excels at Analyze**: Inject more forensic investigations, pattern recognition
- **If player struggles with Apply**: Provide crafting tutorials, guided practice scenarios
- **If player masters Create**: Unlock "Architect Mode" - design their own quest branches

**Why This Works**:
- ✅ Clear progression path with measurable milestones
- ✅ Each challenge leverages unique world properties
- ✅ Balances skills (empathy, strategy, courage, collaboration, resilience)
- ✅ Provides data for cognitive progress tracking
- ✅ Natural difficulty ramp while maintaining engagement
- ✅ Accommodates mixed-ability groups (side quests at different Bloom's levels)

---

## 🎮 Engagement Mechanics

### **Stories - Narrative Integration**
Use world backstory and timeline as narrative anchors:

**Threadweave Example**:
- **Hook**: "The Threadbare Era prophecy (timeline event) is accelerating"
- **Connection**: Player discovers their actions during campaign affect divine thread stability
- **Payoff**: Player's choices become new timeline events in world history

### **Puzzles - Logic Challenges**
Base puzzles on world-specific mechanics:

**Threadweave Examples**:
- **Promise Ore Resonance Puzzle**: Arrange crystals to form harmonic patterns
- **Memory Weaving Logic**: Reconstruct fragmented memories in correct sequence
- **Fate-Line Navigation**: Calculate safe paths across unstable thread bridges using emotional resonance

### **Riddles - Cultural/Mythological**
Draw from world's myths and cultural traditions:

**Threadweave Examples**:
```
"I am born when mortals sleep, yet feed on wakefulness.
I can be spun and sold, yet possess no physical form.
Pattern Wolves track my scent, yet I leave no trail.
What am I?"
[Answer: A broken promise / Promise ore precursor]
```

### **Competitions - Skill Contests**
Leverage world's cultural practices:

**Threadweave Examples**:
- **Annual Unraveling Ceremony Tournament**: Speed-weaving competition
- **Promise-Binding Duel**: Oath-keeping contest judged by Pattern Wolves
- **Memory Trade Auction**: Negotiation and valuation challenge
- **Dream Interpretation Olympics**: Collaborative puzzle-solving with Dream Unravelers

### **Activities - Exploration & Discovery**
Use world's diverse locations and species:

**Threadweave Examples**:
- **Species Diplomacy**: Negotiate with Dream Unravelers in their ethereal habitat
- **Resource Gathering**: Mine Promise ore while managing Pattern Wolf territories
- **Cartography**: Map the constantly-shifting textile forests
- **Archaeology**: Excavate timeline fragments from The Unraveled Wastes
- **Crafting**: Learn Master Weaver techniques at Grand Loom Cathedral

### **Goals & Outcomes - Branching Paths**

**Structure**:
```javascript
{
  main_goal: "Prevent the Eternal Weave Crisis",
  sub_goals: [
    {goal: "Stabilize divine threads", bloom_level: "Apply", required: true},
    {goal: "Resolve Guild conflict", bloom_level: "Evaluate", required: false},
    {goal: "Discover Promise origin", bloom_level: "Analyze", required: false}
  ],
  outcomes: {
    "all_required_only": "Crisis delayed, political tensions remain",
    "required_+_guild": "Crisis delayed, new cooperative structure formed",
    "required_+_origin": "Crisis understood, long-term solution possible",
    "all_goals": "Crisis resolved, player becomes Council member, world stability achieved"
  }
}
```

---

## 🧠 Bloom's Taxonomy Integration

### **AI Challenge Evaluation System**

The Game AI evaluates player responses to challenges and determines success based on cognitive behavior matching:

**Evaluation Process**:
1. **Challenge Presentation**: AI presents challenge with defined Bloom's level (e.g., "Analyze")
2. **Player Response**: Player provides answer, action, or decision
3. **Behavior Analysis**: AI analyzes response for cognitive level indicators
4. **Level Matching**: AI determines if response demonstrates required Bloom's behavior
5. **Success Determination**: AI assigns success level (Full/Partial/Failure)
6. **Feedback Generation**: AI provides explanatory feedback

**Bloom's Level Indicators**:

| Level | Required Behaviors | AI Evaluation Criteria |
|-------|-------------------|----------------------|
| **Remember** | Recall facts, list items, identify elements | Accuracy of factual recall, completeness of lists |
| **Understand** | Explain concepts, interpret meaning, summarize | Clarity of explanation, correct interpretation |
| **Apply** | Use techniques, implement solutions, execute procedures | Correct application of method, functional solution |
| **Analyze** | Investigate patterns, compare elements, deduce causes | Logical reasoning, pattern identification, causal links |
| **Evaluate** | Judge options, assess value, make justified decisions | Criteria-based judgment, justification quality |
| **Create** | Design solutions, synthesize new approaches, innovate | Originality, feasibility, integration of concepts |

**Success Levels**:
- **Full Success (100%)**: Response fully demonstrates required Bloom's level
- **Partial Success (50-99%)**: Response shows some required behaviors but incomplete
- **Minimal Success (25-49%)**: Response attempts correct approach but lacks depth
- **Failure (0-24%)**: Response demonstrates lower cognitive level than required

**Example Evaluation**:
```
Challenge (Analyze level): "Investigate the divine thread corruption pattern and identify its source"

Player Response A: "The corruption comes from the old mine shaft"
└─ AI Evaluation: Partial Success (60%)
   - Shows basic deduction but lacks analysis of patterns
   - Missing causal reasoning and evidence examination
   - Demonstrates Understand level, not Analyze level

Player Response B: "The corruption radiates from three epicenters in the quarry. All three align with sites where Promise ore was extracted during the Memory Market Collapse timeline event. The pattern suggests the corruption is temporally linked to that historical trauma, not a physical source."
└─ AI Evaluation: Full Success (100%)
   - Identifies multiple data points (pattern recognition)
   - Connects spatial and temporal patterns (causal analysis)
   - Links to world history (systems thinking)
   - Demonstrates full Analyze level behavior
```

### **Player Progression Tracking**

**Data Sources**:
1. **member_cognitive_progress** table:
   - Current mastery levels (remember, understand, apply)
   - Progress percentages (analyze, evaluate, create)
   - Skill levels (empathy, strategy, creativity, courage, collaboration, resilience)
   - Successful encounters per Bloom's level
   - Encounters required for next level-up

2. **activity_logs** table:
   - Historical performance on challenges
   - Decision-making patterns
   - Learning strategies
   - Time-to-completion metrics
   - Challenge attempts and success rates

### **Mastery & Level-Up System**

**Core Principle**: Players advance to the next Bloom's level by demonstrating consistent mastery at their current level.

**Mastery Thresholds**:

| Bloom's Level | Encounters Required | Success Rate Required | Difficulty Increase |
|--------------|--------------------|--------------------|-------------------|
| **Remember** | 10 successful | 80% success rate | Baseline |
| **Understand** | 12 successful | 80% success rate | 1.2x harder |
| **Apply** | 15 successful | 75% success rate | 1.5x harder |
| **Analyze** | 18 successful | 75% success rate | 2x harder |
| **Evaluate** | 20 successful | 70% success rate | 2.5x harder |
| **Create** | 25 successful | 70% success rate | 3x harder (mastery) |

**Success Counting**:
- Full Success (100%): Counts as 1.0 toward mastery
- Partial Success (75-99%): Counts as 0.75 toward mastery
- Minimal Success (50-74%): Counts as 0.5 toward mastery
- Below 50%: Does not count toward mastery

**Level-Up Criteria**:
```
Player levels up when:
1. Successful encounters >= Required threshold
   AND
2. Overall success rate >= Required rate (last 20 attempts)
   AND
3. No more than 2 consecutive failures in recent attempts
```

**Progressive Difficulty**:
- Each Bloom's level is progressively more difficult
- Higher levels require more demonstrations of mastery
- Success rate thresholds slightly lower at higher levels (acknowledging difficulty)
- AI adjusts challenge complexity within each level based on player performance

**Example Progression**:
```
Player at "Apply" level:
├─ Current status: 12/15 successful encounters (80% success rate)
├─ Needs: 3 more successful Apply-level challenges
├─ Recent performance: [Success, Success, Partial, Success, Success]
├─ Next level: Analyze (will require 18 successful encounters at 75% rate)
└─ AI Strategy: Continue presenting Apply challenges with 80% at level, 20% Analyze preview

After achieving 15/15:
├─ LEVEL UP to "Analyze"
├─ Counter resets: 0/18 successful encounters
├─ New challenges target Analyze behaviors
└─ Player role evolves: "Practitioner" → "Scholar"
```

**Tracking Table Update**:
```sql
-- member_cognitive_progress table addition
ALTER TABLE member_cognitive_progress ADD COLUMN
  encounters_at_current_level INT DEFAULT 0,
  encounters_required_for_levelup INT,
  recent_success_rate DECIMAL(5,2),
  current_bloom_level VARCHAR(20),
  next_bloom_level VARCHAR(20),
  level_up_eligible BOOLEAN DEFAULT FALSE;
```

### **Adaptive Challenge Selection**

**Algorithm**:
```python
def select_challenge(player_profile, available_challenges):
    current_bloom = get_current_bloom_level(player_profile)
    target_bloom = get_next_bloom_level(current_bloom)

    # Check mastery progress
    progress = get_mastery_progress(player_profile, current_bloom)

    # Adjust distribution based on mastery proximity
    if progress < 0.5:  # Early in level
        # 70% at current level (mastery), 20% at target (preview), 10% review
        challenge_distribution = {
            current_bloom: 0.7,
            target_bloom: 0.2,
            previous_bloom: 0.1
        }
    elif progress < 0.8:  # Mid level
        # 60% at current level, 30% at target (stretch), 10% review
        challenge_distribution = {
            current_bloom: 0.6,
            target_bloom: 0.3,
            previous_bloom: 0.1
        }
    else:  # Near mastery
        # 50% at current level, 40% at target (transition), 10% review
        challenge_distribution = {
            current_bloom: 0.5,
            target_bloom: 0.4,
            previous_bloom: 0.1
        }

    # Filter challenges by world context relevance
    relevant_challenges = filter_by_world_context(available_challenges)

    # Weight by player's skill strengths/weaknesses
    weighted_challenges = apply_skill_weighting(relevant_challenges, player_profile.skills)

    return select_weighted_random(weighted_challenges, challenge_distribution)
```

### **Mentoring & Feedback**

**Real-Time Guidance**:
- **Stuck Detection**: If player attempts same puzzle 3+ times, provide hints
  - Hint Level 1 (Remember): "Remember the properties of Promise ore..."
  - Hint Level 2 (Understand): "This puzzle requires understanding harmonic resonance..."
  - Hint Level 3 (Apply): "Try applying the weaving technique you learned earlier..."

- **Success Recognition**: When player solves challenge, explicitly name the cognitive skill used
  - "Excellent analysis! You connected the divine thread corruption pattern to the timeline event."
  - "Creative solution! Your new binding ritual demonstrates mastery of synthesis."

- **Progress Visualization**: Show cognitive growth arc
  ```
  Your Evolution Arc:
  Remember ████████ 100% (Mastered)
  Understand ████████ 100% (Mastered)
  Apply ██████░░ 75% (Developing)
  Analyze ███░░░░░ 40% (Learning)
  ```

### **Personal Evolution Arc**

**Narrative Integration**:
As players progress through Bloom's levels, their role in the world evolves:

```
Remember → "Apprentice": Learn world basics, follow instructions
Understand → "Journeyman": Interpret world lore, explain connections
Apply → "Practitioner": Use world resources, solve practical problems
Analyze → "Scholar": Investigate mysteries, uncover hidden truths
Evaluate → "Advisor": Judge situations, make ethical decisions
Create → "Architect": Design solutions, shape world evolution
```

**Campaign Reflection**:
Campaign storyline mirrors player's cognitive journey:
- Early quests: "You are learning the ways of Thread Weavers..."
- Mid quests: "Your insights have impressed the Council..."
- Late quests: "The Guild seeks your counsel on future direction..."
- Endgame: "You will define what Threadweave becomes..."

---

## 🗄️ Data Model

### **MongoDB - campaign_definitions**
```javascript
{
  _id: "campaign_uuid",
  campaign_name: "The Threadbare Prophecy",
  world_id: "world_uuid",
  genre: "Mythological",

  // World Context (loaded from world data)
  world_properties: {...},
  relevant_timeline_events: [...],
  featured_species: [...],
  featured_regions: [...],
  key_locations: [...],

  // Player Personalization
  target_player_id: "player_uuid",
  target_bloom_levels: ["apply", "analyze"],
  target_skills: ["strategy", "empathy", "courage"],

  // Campaign Goals
  primary_goals: [
    {
      id: "primary_goal_1",
      description: "Prevent the Eternal Weave Crisis",
      success_criteria: "Stabilize divine threads in all key locations",
      required: true,
      aligned_quests: ["quest_id_1", "quest_id_2", "quest_id_4"]
    },
    {
      id: "primary_goal_2",
      description: "Discover the source of Promise ore corruption",
      success_criteria: "Identify and contain corruption epicenter",
      required: true,
      aligned_quests: ["quest_id_2", "quest_id_5"]
    }
  ],

  secondary_goals: [
    {
      id: "secondary_goal_1",
      description: "Resolve Guild conflict",
      success_criteria: "Establish new cooperative structure between guilds",
      required: false,
      aligned_quests: ["quest_id_3"],
      unlock_rewards: ["Council membership", "Guild influence points"]
    },
    {
      id: "secondary_goal_2",
      description: "Establish alliance with Pattern Wolves",
      success_criteria: "Complete diplomacy challenges and gain trust",
      required: false,
      aligned_quests: ["quest_id_1", "quest_id_4"],
      unlock_rewards: ["Pattern Wolf companion", "Advanced tracking ability"]
    }
  ],

  // Campaign Structure
  narrative_layers: [
    {layer: 1, bloom_levels: ["remember", "understand"], storyline: "..."},
    {layer: 2, bloom_levels: ["apply", "analyze"], storyline: "..."},
    {layer: 3, bloom_levels: ["evaluate", "create"], storyline: "..."}
  ],

  quest_chain: ["quest_id_1", "quest_id_2", "quest_id_3", "quest_id_4", "quest_id_5"],
  num_quests: 5,

  // Campaign Outcomes
  possible_endings: [
    {
      id: "optimal_ending",
      requirements: ["all_primary_goals", "all_secondary_goals"],
      description: "Crisis resolved, world stability achieved, player becomes Council member",
      narrative: "..."
    },
    {
      id: "primary_only_ending",
      requirements: ["all_primary_goals"],
      description: "Crisis delayed, political tensions remain",
      narrative: "..."
    },
    {
      id: "partial_ending",
      requirements: ["primary_goal_1"],
      description: "Immediate crisis averted, but corruption source remains",
      narrative: "..."
    }
  ],

  // Generation Metadata
  created_by_workflow: "workflow_uuid",
  generation_parameters: {
    num_quests: 5,
    campaign_length_hours: 8-12,
    generate_images: true
  },

  created_at: ISODate()
}
```

### **MongoDB - quest_definitions**
```javascript
{
  _id: "quest_uuid",
  campaign_id: "campaign_uuid",
  world_id: "world_uuid",

  quest_name: "Echoes in the Quarries",
  quest_type: "Investigation",
  quest_order: 2,

  // Goal Alignment
  contributes_to_goals: ["primary_goal_2", "secondary_goal_2"],

  // Quest Objective
  objective: {
    description: "Discover source of reality distortions in Shattered Promise Quarries",
    success_criteria: "Identify corruption epicenter and assess threat level",
    bloom_level_range: ["remember", "understand", "apply", "analyze", "evaluate"]
  },

  // World Integration
  primary_location_id: "location_uuid",
  secondary_locations: ["location_uuid_2", "location_uuid_3"],
  involved_species: [
    {species_id: "species_uuid_1", role: "ally", location: "quarry_entrance"},
    {species_id: "species_uuid_2", role: "neutral", location: "deep_tunnels"},
    {species_id: "species_uuid_3", role: "antagonist", location: "corruption_site"}
  ],
  related_timeline_event: "The Memory Market Collapse",
  uses_world_resources: ["Promise ore", "Memory silk", "Divine threads"],

  // Narrative
  description: "Strange echoes in the Shattered Promise Quarries suggest reality itself is unraveling. Pattern Wolves refuse to enter the deeper tunnels, and Guild surveyors report temporal anomalies.",
  narrative_hooks: [
    "Pattern Wolf pack leader hints at ancient danger",
    "Guild Master requests investigation before shutdown",
    "Timeline fragments found suggesting historical connection"
  ],

  // Challenge Sequence (3-5 challenges leading to objective)
  challenges: [
    {
      challenge_id: "chal_uuid_1",
      challenge_number: 1,
      type: "exploration",
      bloom_level: "remember",
      skills_tested: ["observation", "resilience"],

      location_id: "quarry_entrance",
      npcs_present: ["guild_surveyor"],

      description: "Navigate to the quarry and identify different Promise ore types along the way",
      instructions: "The Guild surveyor will test your knowledge of ore varieties",

      success_criteria: {
        required_behaviors: ["recall_facts", "identify_elements", "list_items"],
        evaluation_rubric: "Player must correctly identify 4 of 5 ore types"
      },

      rewards: {
        items: ["basic_mining_tools"],
        knowledge: ["Promise ore properties"],
        progression: "Unlocks deeper quarry access"
      },

      failure_consequences: {
        blocks_progress: false,
        alternate_path: "Guild surveyor provides tutorial",
        retry_allowed: true
      }
    },
    {
      challenge_id: "chal_uuid_2",
      challenge_number: 2,
      type: "social_encounter",
      bloom_level: "understand",
      skills_tested: ["empathy", "communication"],

      location_id: "deep_tunnels",
      npcs_present: ["pattern_wolf_pack"],

      description: "Interpret Pattern Wolf howl patterns to understand their warnings about danger zones",
      instructions: "Listen to the pack's communication and explain what they're warning you about",

      success_criteria: {
        required_behaviors: ["explain_concepts", "interpret_meaning", "demonstrate_understanding"],
        evaluation_rubric: "Player must correctly interpret the spatial and temporal nature of the warnings"
      },

      rewards: {
        items: [],
        knowledge: ["Pattern Wolf communication", "Danger zone locations"],
        skills: ["empathy +2"],
        progression: "Pattern Wolves allow safe passage"
      },

      failure_consequences: {
        blocks_progress: false,
        alternate_path: "Pattern Wolves remain wary, hints provided",
        retry_allowed: true
      }
    },
    {
      challenge_id: "chal_uuid_3",
      challenge_number: 3,
      type: "skill_trial",
      bloom_level: "apply",
      skills_tested: ["strategy", "problem_solving"],

      location_id: "unstable_chamber",
      npcs_present: ["trapped_miner"],

      description: "Repair minor reality tear using memory-weaving technique learned from Guild",
      instructions: "A miner is trapped behind a reality distortion. Apply the weaving technique to stabilize the tear",

      success_criteria: {
        required_behaviors: ["implement_solution", "execute_procedure", "use_technique"],
        evaluation_rubric: "Player must correctly sequence the weaving steps and use appropriate Promise ore resonance"
      },

      rewards: {
        items: ["memory_silk_fragment"],
        knowledge: ["Reality stabilization technique"],
        skills: ["strategy +3"],
        progression: "Miner provides information about corruption epicenter"
      },

      failure_consequences: {
        blocks_progress: true,
        alternate_path: "Must retry or find alternate route",
        retry_allowed: true,
        hint_after_attempts: 2
      }
    },
    {
      challenge_id: "chal_uuid_4",
      challenge_number: 4,
      type: "mystery",
      bloom_level: "analyze",
      skills_tested: ["deduction", "pattern_recognition"],

      location_id: "ancient_excavation",
      npcs_present: ["corrupted_dream_unraveler"],

      description: "Investigate divine thread corruption patterns to identify the source",
      instructions: "Examine the corruption at multiple sites. Analyze the patterns to determine the source location and cause",

      success_criteria: {
        required_behaviors: ["investigate_patterns", "deduce_causes", "connect_evidence", "systems_thinking"],
        evaluation_rubric: "Player must identify spatial patterns, connect to timeline events, and provide causal explanation"
      },

      rewards: {
        items: ["corruption_sample"],
        knowledge: ["Corruption source location", "Connection to Memory Market Collapse"],
        skills: ["deduction +4"],
        progression: "Corruption epicenter revealed"
      },

      failure_consequences: {
        blocks_progress: true,
        alternate_path: "Corrupted Dream Unraveler provides cryptic hints",
        retry_allowed: true
      }
    },
    {
      challenge_id: "chal_uuid_5",
      challenge_number: 5,
      type: "moral_dilemma",
      bloom_level: "evaluate",
      skills_tested: ["judgment", "ethical_reasoning"],

      location_id: "corruption_epicenter",
      npcs_present: ["guild_master", "council_representative"],

      description: "Decide whether to seal the corruption source (safe but uninformative) or study it (risky but may lead to cure)",
      instructions: "The Guild Master wants immediate sealing. The Council wants research. Evaluate the options and make a justified decision",

      success_criteria: {
        required_behaviors: ["assess_options", "weigh_consequences", "justify_decision", "apply_criteria"],
        evaluation_rubric: "Player must articulate clear evaluation criteria, weigh pros/cons, and provide reasoned justification"
      },

      rewards: {
        seal_choice: {
          items: ["safety_commendation"],
          knowledge: ["Immediate threat contained"],
          progression: "Safe path, primary_goal_2 partially complete"
        },
        study_choice: {
          items: ["research_access"],
          knowledge: ["Corruption mechanism understanding"],
          skills: ["courage +5"],
          progression: "Risky path, potential for primary_goal_2 full completion"
        }
      },

      failure_consequences: {
        blocks_progress: false,
        alternate_path: "Guild Master makes decision, player loses influence",
        retry_allowed: false
      }
    }
  ],

  // Branching
  decision_points: [
    {
      point_id: "decision_uuid",
      occurs_after_challenge: "chal_uuid_5",
      description: "Choose investigation approach for corruption",
      bloom_level_required: "evaluate",
      choices: [
        {
          id: "seal",
          description: "Seal the corruption immediately (safe approach)",
          consequences: "Primary goal partially achieved, secondary goal blocked",
          leads_to_quest: "quest_uuid_4",
          affects_goals: ["primary_goal_2: partial"]
        },
        {
          id: "study",
          description: "Study the corruption before acting (risky approach)",
          consequences: "Potential for full solution, but introduces danger",
          leads_to_quest: "quest_uuid_5",
          affects_goals: ["primary_goal_2: full_potential"]
        }
      ]
    }
  ],

  // Quest Outcomes
  possible_outcomes: [
    {
      outcome_id: "full_success",
      description: "All challenges completed successfully, optimal decision made",
      requirements: ["all_challenges_success", "evaluate_level_decision"],
      unlocks: ["corruption_research_path"],
      affects_world: true,
      world_changes: ["Quarry stability improved", "Guild influence increased"],
      goal_progress: {
        "primary_goal_2": 60,  // 60% progress toward goal
        "secondary_goal_2": 40  // 40% progress toward goal
      }
    },
    {
      outcome_id: "partial_success",
      description: "Major challenges completed, suboptimal decision",
      requirements: ["3_of_5_challenges", "any_decision"],
      unlocks: ["basic_information"],
      affects_world: false,
      goal_progress: {
        "primary_goal_2": 40
      }
    },
    {
      outcome_id: "minimal_success",
      description: "Minimum challenges completed, threat identified but not resolved",
      requirements: ["2_of_5_challenges"],
      unlocks: [],
      opens_alternate_path: true,
      alternate_quest: "quest_uuid_4_alt",
      goal_progress: {
        "primary_goal_2": 20
      }
    }
  ]
}
```

---

## 🔄 LangGraph Workflow Details

### **Node 1: Load World Context**
- Query MongoDB for world_definitions, regions, locations, species
- Extract: properties, backstory, timeline, themes, visual style
- Build world knowledge graph in memory for AI reference

### **Node 2: Analyze Player Profile**
- Query PostgreSQL member_cognitive_progress
- Query activity_logs for recent performance
- Determine: current Bloom's tier, skill strengths/weaknesses, learning preferences
- Generate player persona for AI: "Strategic player comfortable with Apply/Analyze, needs Evaluate practice"

### **Node 3: Generate Campaign Arc**
- Use Claude with world context + player profile
- Create 3-layer narrative (surface, hidden depth, meta)
- Define main conflict tied to world timeline
- Establish character arcs using world species
- Output: Campaign storyline with narrative beats

### **Node 4: Create Quest Chain**
- Generate 3-7 interconnected quests
- Ensure Bloom's progression (easy → complex)
- Map quests to locations (variety across regions)
- Create decision points with branching paths
- Output: Ordered quest summaries

### **Node 5: Design Challenges**
- For each quest, generate 3-5 challenges
- Types: puzzles, riddles, competitions, activities
- Bloom's alignment based on player profile
- World-specific mechanics (Promise ore puzzles, memory weaving)
- Output: Challenge definitions with solutions

### **Node 6: Generate Encounters**
- Create species interactions (NPCs, allies, antagonists)
- Design location-based events (environmental hazards, discoveries)
- Combat/Social/Exploration balance
- Skill testing moments (empathy, courage, collaboration)
- Output: Encounter specifications

### **Node 7: Create Rewards**
- Items using world resources (Promise ore weapons, memory silk armor)
- Skills matching player's growth areas
- Knowledge unlocks (lore, new locations, species relationships)
- Bloom's-appropriate rewards (Apply: tools, Analyze: information, Create: blueprints)
- Output: Reward catalog

### **Node 8: Generate Branches**
- Define decision points at quest conclusions
- Multiple outcomes based on Bloom's-level choices
- Failure paths that remain engaging
- Convergence points (branches rejoin main story)
- Output: Decision tree

### **Node 9: Generate Images (optional)**
- Quest location establishing shots
- Key NPC character portraits
- Important items (legendary weapons, artifacts)
- If disabled: skip to Node 10

### **Node 10: Finalize & Validate**
- Check internal consistency (no timeline contradictions)
- Verify Bloom's progression (challenge escalation)
- Confirm world integration (uses established lore)
- Save to MongoDB (campaign_definitions, quest_definitions)
- Publish completion event
- Output: Campaign ID + summary

---

## 🚀 Implementation Phases

### **Phase 1: Core Infrastructure** (Week 1-2)
- [ ] Create campaign-factory service (Docker container)
- [ ] Set up RabbitMQ queues (campaign_factory_jobs, campaign_factory_progress)
- [ ] Define MongoDB schemas (campaign_definitions, quest_definitions)
- [ ] Build LangGraph workflow skeleton (10 nodes)
- [ ] Create Django API endpoints

### **Phase 2: World Context Loading** (Week 2-3)
- [ ] Implement Node 1: Load World Context
- [ ] Build world data aggregation queries
- [ ] Create world knowledge graph builder
- [ ] Test with Threadweave world data

### **Phase 3: Player Analysis** (Week 3-4)
- [ ] Implement Node 2: Analyze Player Profile
- [ ] Query member_cognitive_progress + activity_logs
- [ ] Build player persona generator
- [ ] Create adaptive difficulty algorithm

### **Phase 4: Narrative Generation** (Week 4-6)
- [ ] Implement Nodes 3-4: Campaign Arc + Quest Chain
- [ ] Create Claude prompts with world context injection
- [ ] Build 3-layer narrative generator
- [ ] Test with multiple Bloom's level targets

### **Phase 5: Challenge Design** (Week 6-7)
- [ ] Implement Nodes 5-6: Challenges + Encounters
- [ ] Build Bloom's-aligned challenge templates
- [ ] Create world-specific puzzle generators
- [ ] Implement species interaction system

### **Phase 6: Rewards & Branching** (Week 7-8)
- [ ] Implement Nodes 7-8: Rewards + Branches
- [ ] Build reward catalog system
- [ ] Create decision tree generator
- [ ] Implement outcome tracking

### **Phase 7: Image Generation & Polish** (Week 8-9)
- [ ] Implement Node 9: Generate Images (optional)
- [ ] Integrate DALL-E for quest visuals
- [ ] Create Node 10: Finalize & Validate
- [ ] Build consistency checking

### **Phase 8: UI Integration** (Week 9-10)
- [ ] Build Campaign Factory modal in Django
- [ ] Create progress tracking UI
- [ ] Implement campaign browsing interface
- [ ] Add campaign editing tools

### **Phase 9: Testing & Iteration** (Week 10-12)
- [ ] Generate campaigns for all world types
- [ ] Test with players at different Bloom's levels
- [ ] Validate cognitive progress tracking
- [ ] Refine AI prompts based on feedback

---

## 📈 Success Metrics

- **World Integration**: 95%+ of campaign elements use existing world data
- **Bloom's Alignment**: Challenges match target Bloom's level ±1 tier
- **Player Engagement**: Campaigns completed vs. started ratio >70%
- **Cognitive Growth**: Measurable improvement in target Bloom's level after campaign
- **Generation Time**: <5 minutes for 5-quest campaign (without images)
- **Consistency**: 0 lore contradictions per campaign
- **Goal Achievement**: Players complete 80%+ of primary goals, 50%+ of secondary goals
- **Challenge Completion**: Average 85%+ challenge success rate
- **Level-Up Rate**: Players level up within expected encounter thresholds ±20%
- **AI Evaluation Accuracy**: Player feedback agreement with AI success determination >90%

---

## 🎓 Educational Value

### **Bloom's Taxonomy Benefits**
- **Remember**: World lore mastery, location familiarity
- **Understand**: Cultural comprehension, species relationships
- **Apply**: Problem-solving with world mechanics
- **Analyze**: Mystery investigation, pattern recognition
- **Evaluate**: Ethical decision-making, judgment
- **Create**: World-shaping, innovation

### **Skill Development**
- **Empathy**: Species diplomacy, understanding motivations
- **Strategy**: Resource management, long-term planning
- **Creativity**: Problem-solving, improvisation
- **Courage**: Risk-taking, facing challenges
- **Collaboration**: Multi-species teamwork
- **Resilience**: Failure recovery, persistence

---

## 🌟 Why This Approach Works

1. **Rich World Utilization**: Every world property becomes gameplay
2. **Personalized Learning**: Adapts to individual cognitive levels
3. **Scalable Architecture**: Same pattern as World Factory (proven)
4. **Data-Driven**: Tracks and responds to player progress
5. **Inclusive Design**: Same campaign serves all skill levels (via layers)
6. **Educational Integration**: Hidden learning within engaging narrative
7. **Replayability**: Branching paths + different Bloom's focuses
8. **Long-Term Engagement**: Players return to unlock deeper layers

---

## 🔮 Future Enhancements

- **Multi-Player Campaigns**: Assign different Bloom's challenges to each player
- **Campaign Chaining**: Link multiple campaigns into sagas
- **Dynamic World Updates**: Campaign outcomes modify world state
- **Community Content**: Players create challenges for others
- **Cross-World Campaigns**: Campaigns spanning multiple worlds
- **AI Game Master**: Real-time campaign adaptation during play

---

*This architecture leverages everything we built in World Factory while adding sophisticated educational personalization and rich gameplay variety.*
