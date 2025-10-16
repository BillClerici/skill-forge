# Dimensional Maturity System
## Multi-Dimensional Character Development Using Bloom's Taxonomy

### Executive Summary
This document defines the **7 Dimensional Maturity System** that tracks player character development across seven key dimensions of human growth. Each dimension progresses through **Bloom's Taxonomy** - a proven educational framework with 6 cognitive levels. This system integrates character development with the rubric-based evaluation system to provide meaningful, measurable personal growth through gameplay.

---

## 1. The Seven Dimensions of Maturity

SkillForge tracks character development across 7 fundamental dimensions that encompass the full spectrum of human development:

### 1.1 Physical Dimension
**Definition**: Physical development, health, coordination, bodily mastery, and kinesthetic awareness.

**Includes**:
- Physical fitness and endurance
- Combat skills and coordination
- Manual dexterity and craftsmanship
- Physical resilience and recovery
- Athletic capabilities

**Measured Through**:
- Challenge interactions (physical obstacles, combat scenarios)
- Environmental discoveries (physical exploration)
- Resource management (physical stamina, health)

---

### 1.2 Emotional Dimension
**Definition**: Emotional intelligence, self-regulation, affective awareness, and emotional maturity.

**Includes**:
- Emotional self-awareness
- Emotion regulation under pressure
- Empathy and emotional connection
- Resilience and recovery from setbacks
- Mood management and composure

**Measured Through**:
- NPC conversations (emotional tone, empathy)
- Event responses (emotional reactions)
- Challenge approaches (handling frustration, stress)

---

### 1.3 Intellectual Dimension
**Definition**: Cognitive abilities, critical thinking, knowledge acquisition, and intellectual development.

**Includes**:
- Problem-solving and reasoning
- Learning and knowledge retention
- Analysis and synthesis
- Strategic thinking
- Creative problem-solving

**Measured Through**:
- Environmental discoveries (investigation, observation)
- Challenge interactions (puzzle-solving, strategy)
- NPC conversations (questioning, understanding)

---

### 1.4 Social Dimension
**Definition**: Interpersonal skills, collaboration, communication, and community engagement.

**Includes**:
- Communication effectiveness
- Relationship building
- Teamwork and collaboration
- Social responsibility
- Conflict resolution

**Measured Through**:
- NPC conversations (relationship building, active listening)
- Event responses (group decision-making)
- Challenge approaches (cooperative vs. solo strategies)

---

### 1.5 Spiritual Dimension
**Definition**: Values, purpose, ethics, meaning-making, and connection to something greater than oneself.

**Includes**:
- Ethical reasoning and moral development
- Purpose and meaning
- Values alignment
- Integrity and principles
- Connection to higher ideals

**Measured Through**:
- Event responses (moral dilemmas)
- NPC conversations (ethical discussions)
- Challenge approaches (value-based decisions)

---

### 1.6 Vocational Dimension
**Definition**: Skills, competencies, capabilities for meaningful work, and professional development.

**Includes**:
- Skill acquisition and mastery
- Craft and profession development
- Practical competencies
- Goal achievement
- Contribution and productivity

**Measured Through**:
- Challenge interactions (skill application)
- Environmental discoveries (skill use)
- Quest progression (goal accomplishment)

---

### 1.7 Environmental Dimension
**Definition**: Awareness and stewardship of surroundings, nature, and the broader ecosystem.

**Includes**:
- Environmental awareness
- Ecological understanding
- Resource stewardship
- Sustainability consciousness
- Relationship with nature

**Measured Through**:
- Environmental discoveries (ecological observation)
- Event responses (environmental impact decisions)
- Resource management (sustainability choices)

---

## 2. Bloom's Taxonomy Progression System

Each of the 7 dimensions progresses through **6 levels based on Bloom's Taxonomy**:

| Level | Bloom's Taxonomy | Friendly Name | XP Threshold | Description |
|-------|-----------------|---------------|--------------|-------------|
| 1 | **Remember** | Novice | 0 | Recall facts and basic concepts |
| 2 | **Understand** | Apprentice | 100 | Explain ideas or concepts |
| 3 | **Apply** | Journeyman | 300 | Use information in new situations |
| 4 | **Analyze** | Expert | 600 | Draw connections among ideas |
| 5 | **Evaluate** | Master | 1000 | Justify a stand or decision |
| 6 | **Create** | Grandmaster | 1500 | Produce new or original work |

### 2.1 Level Descriptions by Dimension

#### Physical Dimension
- **Novice (Remember)**: Recall basic movements and techniques
- **Apprentice (Understand)**: Explain proper form and technique
- **Journeyman (Apply)**: Use skills effectively in new contexts
- **Expert (Analyze)**: Understand body mechanics and optimize performance
- **Master (Evaluate)**: Judge and refine physical techniques
- **Grandmaster (Create)**: Invent new moves, techniques, or training methods

#### Emotional Dimension
- **Novice (Remember)**: Recognize basic emotions
- **Apprentice (Understand)**: Explain emotional patterns and triggers
- **Journeyman (Apply)**: Apply emotional regulation techniques
- **Expert (Analyze)**: Analyze complex emotional dynamics
- **Master (Evaluate)**: Judge emotional appropriateness and impact
- **Grandmaster (Create)**: Develop new emotional wisdom and insights

#### Intellectual Dimension
- **Novice (Remember)**: Recall facts and information
- **Apprentice (Understand)**: Explain concepts and ideas
- **Journeyman (Apply)**: Apply knowledge to solve problems
- **Expert (Analyze)**: Break down complex systems and patterns
- **Master (Evaluate)**: Critique theories and judge validity
- **Grandmaster (Create)**: Generate original theories and solutions

#### Social Dimension
- **Novice (Remember)**: Recall social norms and customs
- **Apprentice (Understand)**: Explain social dynamics
- **Journeyman (Apply)**: Navigate social situations effectively
- **Expert (Analyze)**: Understand complex social patterns
- **Master (Evaluate)**: Judge social appropriateness and impact
- **Grandmaster (Create)**: Build new communities and social structures

#### Spiritual Dimension
- **Novice (Remember)**: Recall moral rules and values
- **Apprentice (Understand)**: Explain ethical principles
- **Journeyman (Apply)**: Apply values in decision-making
- **Expert (Analyze)**: Analyze moral dilemmas deeply
- **Master (Evaluate)**: Judge ethical soundness of actions
- **Grandmaster (Create)**: Develop original ethical frameworks

#### Vocational Dimension
- **Novice (Remember)**: Recall procedures and steps
- **Apprentice (Understand)**: Explain how things work
- **Journeyman (Apply)**: Execute skills competently
- **Expert (Analyze)**: Optimize processes and workflows
- **Master (Evaluate)**: Judge quality and effectiveness
- **Grandmaster (Create)**: Innovate new methods and practices

#### Environmental Dimension
- **Novice (Remember)**: Recall environmental facts
- **Apprentice (Understand)**: Explain ecological relationships
- **Journeyman (Apply)**: Practice environmental stewardship
- **Expert (Analyze)**: Understand complex ecosystems
- **Master (Evaluate)**: Assess environmental impact
- **Grandmaster (Create)**: Design sustainable systems

---

## 3. Integration with Rubric System

### 3.1 Rubric-to-Dimension Mapping

Each of the 4 interaction types contributes experience points to relevant dimensions:

#### NPC Conversation Rubric → Dimensions
```python
{
    "relationship_building": ["social", "emotional"],
    "question_quality": ["intellectual", "social"],
    "active_listening": ["emotional", "social"],
    "context_understanding": ["intellectual", "social"]
}
```

#### Environmental Discovery Rubric → Dimensions
```python
{
    "observation_detail": ["intellectual", "environmental"],
    "investigation_method": ["intellectual", "vocational"],
    "pattern_recognition": ["intellectual", "environmental"],
    "knowledge_application": ["intellectual", "vocational"]
}
```

#### Challenge Rubric → Dimensions
```python
{
    "problem_solving": ["intellectual", "vocational"],
    "resource_management": ["environmental", "vocational"],
    "risk_assessment": ["intellectual", "physical"],
    "adaptability": ["emotional", "intellectual"]
}
```

#### Dynamic Event Rubric → Dimensions
```python
{
    "situation_assessment": ["intellectual", "emotional"],
    "decision_speed": ["emotional", "physical"],
    "action_effectiveness": ["physical", "vocational"],
    "ethical_considerations": ["spiritual", "social"]
}
```

### 3.2 Experience Point Awards

Rubric scores translate to dimensional experience points:

| Criterion Score | XP Award per Dimension | Description |
|-----------------|----------------------|-------------|
| 4 (Exemplary) | +50 XP | Exceptional performance |
| 3 (Proficient) | +25 XP | Solid, competent performance |
| 2 (Developing) | +10 XP | Basic attempt, needs improvement |
| 1 (Beginning) | +5 XP | Minimal engagement |

**Example**: An NPC conversation with the following scores:
- Relationship Building: 4 (Exemplary) → +50 XP to Social, +50 XP to Emotional
- Question Quality: 3 (Proficient) → +25 XP to Intellectual, +25 XP to Social
- Active Listening: 3 (Proficient) → +25 XP to Emotional, +25 XP to Social
- Context Understanding: 4 (Exemplary) → +50 XP to Intellectual, +50 XP to Social

**Result**:
- Emotional: +75 XP
- Intellectual: +75 XP
- Social: +150 XP

### 3.3 Level-Up Mechanics

When a dimension's experience points reach the threshold for the next level:
1. Current level increments by 1 (max level 6)
2. Bloom's level updates (Remember → Understand → Apply → Analyze → Evaluate → Create)
3. Next level threshold is set to the next tier
4. Excess XP carries over

**Level Thresholds**:
```python
LEVEL_THRESHOLDS = {
    1: 0,      # Novice starts at 0 XP
    2: 100,    # Apprentice requires 100 XP
    3: 300,    # Journeyman requires 300 XP
    4: 600,    # Expert requires 600 XP
    5: 1000,   # Master requires 1000 XP
    6: 1500    # Grandmaster requires 1500 XP
}
```

---

## 4. Data Model

### 4.1 Character Model (Django)

```python
# In characters/models.py

class Character(models.Model):
    # ... existing fields ...

    # Dimensional Maturity (7 dimensions × 6 Bloom's levels)
    dimensional_maturity = models.JSONField(
        default=dict,
        help_text="7-dimension maturity tracking: Physical, Emotional, Intellectual, Social, Spiritual, Vocational, Environmental"
    )

    # Bloom's Level Mapping
    BLOOMS_FRIENDLY_NAMES = {
        1: "Novice",
        2: "Apprentice",
        3: "Journeyman",
        4: "Expert",
        5: "Master",
        6: "Grandmaster"
    }

    BLOOMS_TAXONOMY_LEVELS = {
        1: "Remember",
        2: "Understand",
        3: "Apply",
        4: "Analyze",
        5: "Evaluate",
        6: "Create"
    }

    DIMENSION_NAMES = [
        "physical",
        "emotional",
        "intellectual",
        "social",
        "spiritual",
        "vocational",
        "environmental"
    ]

    @staticmethod
    def get_default_dimensional_maturity():
        """Default dimensional maturity for new characters (all at level 1)"""
        return {
            "physical": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "emotional": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "intellectual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "social": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "spiritual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "vocational": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "environmental": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100}
        }

    @property
    def dimensional_profile(self):
        """Get formatted dimensional maturity profile"""
        if not self.dimensional_maturity:
            maturity = self.get_default_dimensional_maturity()
        else:
            # Ensure all dimensions exist
            default = self.get_default_dimensional_maturity()
            maturity = {**default, **self.dimensional_maturity}

        profile = {}
        for dimension, data in maturity.items():
            current_level = data.get("current_level", 1)
            exp = data.get("experience_points", 0)
            next_threshold = data.get("next_level_threshold", 100)

            profile[dimension] = {
                "current_level": current_level,
                "bloom_level": data.get("bloom_level", self.BLOOMS_TAXONOMY_LEVELS[current_level]),
                "friendly_name": self.BLOOMS_FRIENDLY_NAMES[current_level],
                "experience_points": exp,
                "next_level_threshold": next_threshold,
                "progress_percentage": int((exp / next_threshold) * 100) if next_threshold > 0 else 100,
                "color": self.get_dimension_color(current_level),
                "description": self.get_dimension_description(dimension)
            }
        return profile
```

### 4.2 CharacterDevelopmentProfile (Campaign Factory)

```python
# In services/campaign-factory/workflow/state.py

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
    balance_score: float  # Average across all dimensions
    most_developed: List[str]  # Top 3 dimensions
    least_developed: List[str]  # Bottom 3 dimensions
    recommended_focus: List[str]  # Dimensions to work on for balance
    acquired_knowledge: Dict[str, Dict[str, Any]]
    acquired_items: Dict[str, Dict[str, Any]]
    quest_progress: Dict[str, Dict[str, Any]]
```

---

## 5. Visualization on Character Sheet & Detail View

### 5.1 Character Sheet Display

The Character Sheet displays dimensional maturity with:
- **Current Level & Friendly Name**: "Level 3: Journeyman"
- **Bloom's Taxonomy Level**: "Apply"
- **Experience Progress**: "250 / 300 XP"
- **Progress Bar**: Visual progress to next level
- **Bloom's Level Track**: 6-stage progression indicator showing Novice → Grandmaster
- **Dimension Description**: Brief explanation of each dimension

### 5.2 Character Detail View Display

The Character Detail View shows:
- Compact version of dimensional progress
- Color-coded level indicators
- Mini progression tracks for each dimension
- Integration with overall character development

### 5.3 Color Coding by Level

```python
LEVEL_COLORS = {
    1: "#9e9e9e",  # Gray - Novice (Remember)
    2: "#2196f3",  # Blue - Apprentice (Understand)
    3: "#4caf50",  # Green - Journeyman (Apply)
    4: "#ff9800",  # Orange - Expert (Analyze)
    5: "#9c27b0",  # Purple - Master (Evaluate)
    6: "#f44336"   # Red - Grandmaster (Create)
}
```

---

## 6. Benefits of the 7 Dimensional Maturity System

1. **Holistic Development**: Tracks physical, emotional, intellectual, social, spiritual, vocational, and environmental growth
2. **Bloom's Taxonomy Foundation**: Uses proven educational framework for measurable cognitive development
3. **Clear Progression**: 6 levels with defined thresholds provide clear milestones
4. **Real Skill Transfer**: Cognitive skills practiced in-game apply to real life
5. **Personalized Growth**: Each player develops unique dimensional profiles based on choices
6. **Educational Rigor**: Replaces random chance with actual skill demonstration
7. **Balanced Development**: Encourages growth across all dimensions, not just favorites

---

## 7. Connection to Scene Progression System

The Dimensional Maturity System is fully integrated with the **Scene Progression System** (Phases 1-5):

### Phase 1: Multi-Dimensional Progression
- 7 dimensions defined with Bloom's 6 levels
- CharacterDevelopmentProfile tracks all dimensions
- Integrated into CampaignWorkflowState

### Phase 3: Rubric System
- 7 rubric templates map to dimensional experience
- AI-generated rubrics customize to character's weakest dimensions
- Performance scoring awards dimensional XP

### Phase 4: Dimension-Aware Scene Generation
- Scenes target character's weakest dimensions
- 42 challenge types automatically map to relevant dimensions
- Balanced development encouraged through scene variety

### Phase 5: Progression Tracking
- `progression_tracker.py` manages level-ups and XP awards
- MongoDB stores progression history
- Django integration displays dimensional growth

---

## 8. Implementation Status

✅ **Completed**:
- Data model definition (state.py)
- Progression tracking logic (progression_tracker.py)
- Level-up mechanics and thresholds
- MongoDB storage for progression history
- Character model integration
- Character Sheet UI display
- Character Detail view display
- Documentation

🔄 **In Progress**:
- Full rubric-to-dimension integration
- Experience point award automation
- Balance score calculation refinement

📋 **Future Enhancements**:
- Dimensional growth timeline visualization
- Comparative analytics (player vs. player)
- Dimension-based character archetypes
- Achievement badges for dimension mastery

---

**Document Version**: 2.0
**Date**: 2025-01-13
**Author**: Claude Code (SkillForge Development)
**System**: 7 Dimensional Maturity with Bloom's Taxonomy
