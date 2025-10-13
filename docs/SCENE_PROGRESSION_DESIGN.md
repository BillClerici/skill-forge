# Scene Progression System Design
## Objective-Driven Knowledge & Item Acquisition

### Executive Summary
This document outlines a comprehensive redesign of the Scene generation system to create an objective-driven progression where players acquire knowledge and items through multiple interaction types, with rubrics to measure partial understanding and skill acquisition.

---

## 1. Current System Analysis

### Current Workflow
```
Campaign → Quests → Places → Scenes → Elements (NPCs, Discoveries, Events, Challenges)
```

### Current Issues
1. **No Objective Linking**: Scene elements aren't explicitly tied to quest/campaign objectives
2. **No Knowledge/Item Tracking**: Rewards are generic dictionaries, not tracked entities
3. **No Progression System**: No way to track if players have acquired required knowledge/items
4. **No Redundancy**: Single path to acquire each piece of knowledge/item
5. **No Partial Knowledge**: Binary success/failure, no gradual learning
6. **No Rubrics**: No standardized way to evaluate player performance

---

## 2. Proposed System Architecture

### 2.1 Objective Hierarchy
```
Campaign Objectives
    ↓
Quest Objectives (support Campaign Objectives)
    ↓
Required Knowledge & Items (achieve Quest Objectives)
    ↓
Scene Elements (provide Knowledge & Items)
    ↓
Interaction Methods (4 types)
```

### 2.2 Core Entities

#### Knowledge Entity
```python
{
    "knowledge_id": "kg_ancient_mining_001",
    "name": "Ancient Mining Techniques",
    "description": "Understanding of safe mineral extraction methods",
    "knowledge_type": "skill|lore|clue|secret",
    "blooms_level": 3,  # Bloom's Taxonomy level
    "supports_objectives": ["quest_obj_1", "campaign_obj_2"],

    # Progression tracking
    "partial_levels": [
        {
            "level": 1,  # 25% understanding
            "description": "Basic awareness of mining dangers",
            "sufficient_for": []  # No objectives can be completed yet
        },
        {
            "level": 2,  # 50% understanding
            "description": "Understanding of tool usage",
            "sufficient_for": ["quest_obj_1_partial"]
        },
        {
            "level": 3,  # 75% understanding
            "description": "Knowledge of safety protocols",
            "sufficient_for": ["quest_obj_1"]
        },
        {
            "level": 4,  # 100% mastery
            "description": "Expert-level extraction techniques",
            "sufficient_for": ["quest_obj_1", "campaign_obj_2"]
        }
    ],

    # Acquisition methods (redundancy)
    "acquisition_methods": [
        {
            "type": "npc_conversation",
            "npc_id": "npc_miner_001",
            "difficulty": "Medium",
            "max_level_obtainable": 3,
            "rubric_id": "conversation_rubric_001"
        },
        {
            "type": "discovery",
            "discovery_id": "disc_mining_notes_001",
            "difficulty": "Easy",
            "max_level_obtainable": 2,
            "rubric_id": "discovery_rubric_001"
        },
        {
            "type": "challenge",
            "challenge_id": "chal_navigate_mine_001",
            "difficulty": "Hard",
            "max_level_obtainable": 4,
            "rubric_id": "challenge_rubric_001"
        },
        {
            "type": "event",
            "event_id": "evt_mine_collapse_001",
            "difficulty": "Medium",
            "max_level_obtainable": 3,
            "rubric_id": "event_rubric_001"
        }
    ]
}
```

#### Item Entity
```python
{
    "item_id": "item_climbing_rope_001",
    "name": "Sturdy Climbing Rope",
    "description": "A well-maintained rope suitable for scaling walls",
    "item_type": "tool|consumable|key_item|quest_item",
    "supports_objectives": ["quest_obj_2"],

    # Acquisition methods (redundancy)
    "acquisition_methods": [
        {
            "type": "npc_conversation",
            "npc_id": "npc_merchant_001",
            "conditions": {
                "requires_knowledge": ["kg_ancient_mining_001"],
                "requires_reputation": 5
            },
            "method": "purchase|gift|trade",
            "rubric_id": "conversation_rubric_002"
        },
        {
            "type": "discovery",
            "discovery_id": "disc_debris_pile_001",
            "conditions": {},
            "rubric_id": "discovery_rubric_002"
        },
        {
            "type": "challenge",
            "challenge_id": "chal_rescue_miner_001",
            "conditions": {
                "requires_knowledge": []
            },
            "rubric_id": "challenge_rubric_002"
        }
    ],

    "quantity": 1,
    "is_consumable": false,
    "is_quest_critical": true
}
```

---

## 3. Multi-Dimensional Bloom's Taxonomy

### 3.1 Seven Developmental Dimensions

Each character develops across 7 dimensions, each using Bloom's 6 levels:
1. **Remember** (Level 1) - Recall facts, basic recognition
2. **Understand** (Level 2) - Comprehend concepts, explain ideas
3. **Apply** (Level 3) - Use knowledge in new situations
4. **Analyze** (Level 4) - Break down information, find patterns
5. **Evaluate** (Level 5) - Make judgments, critique, assess
6. **Create** (Level 6) - Synthesize new ideas, innovate

#### Dimension 1: Physical (Body)
- Combat prowess, reflexes, endurance, coordination
- Physical skill mastery, athletic ability
- Body awareness and control

#### Dimension 2: Emotional (Heart)
- Emotional intelligence, empathy, self-awareness
- Stress management, emotional regulation
- Relationship depth and intimacy

#### Dimension 3: Intellectual (Mind)
- Reasoning, logic, problem-solving
- Learning capacity, knowledge acquisition
- Critical thinking, creativity

#### Dimension 4: Social (Community)
- Communication skills, collaboration
- Leadership, conflict resolution
- Cultural awareness, teamwork

#### Dimension 5: Spiritual (Soul)
- Purpose, meaning, values alignment
- Inner strength, resilience
- Ethical reasoning, moral development

#### Dimension 6: Vocational (Craft)
- Professional skills, expertise
- Practical application, craftsmanship
- Career development, mastery

#### Dimension 7: Environmental (World)
- Ecological awareness, sustainability
- Resource management, stewardship
- Systems thinking, interconnection

### 3.2 Character Development Profile
```python
{
    "character_id": "char_001",
    "dimensional_maturity": {
        "physical": {
            "current_level": 3,  # Apply level
            "bloom_level": "Apply",
            "experience_points": 450,
            "next_level_threshold": 500,
            "strengths": ["Combat reflexes", "Endurance"],
            "growth_areas": ["Fine motor control"]
        },
        "emotional": {
            "current_level": 4,  # Analyze level
            "bloom_level": "Analyze",
            "experience_points": 720,
            "next_level_threshold": 1000,
            "strengths": ["Empathy", "Self-awareness"],
            "growth_areas": ["Stress management under pressure"]
        },
        "intellectual": {
            "current_level": 5,  # Evaluate level
            "bloom_level": "Evaluate",
            "experience_points": 1150,
            "next_level_threshold": 1500,
            "strengths": ["Critical thinking", "Pattern recognition"],
            "growth_areas": ["Creative synthesis"]
        },
        "social": {
            "current_level": 2,  # Understand level
            "bloom_level": "Understand",
            "experience_points": 180,
            "next_level_threshold": 300,
            "strengths": ["Basic communication"],
            "growth_areas": ["Leadership", "Conflict resolution"]
        },
        "spiritual": {
            "current_level": 3,  # Apply level
            "bloom_level": "Apply",
            "experience_points": 380,
            "next_level_threshold": 500,
            "strengths": ["Strong values", "Purpose clarity"],
            "growth_areas": ["Ethical complexity navigation"]
        },
        "vocational": {
            "current_level": 4,  # Analyze level
            "bloom_level": "Analyze",
            "experience_points": 650,
            "next_level_threshold": 1000,
            "strengths": ["Mining expertise", "Tool mastery"],
            "growth_areas": ["Innovation in techniques"]
        },
        "environmental": {
            "current_level": 2,  # Understand level
            "bloom_level": "Understand",
            "experience_points": 210,
            "next_level_threshold": 300,
            "strengths": ["Basic ecology awareness"],
            "growth_areas": ["Systems thinking", "Sustainability practices"]
        }
    },

    # Dimensional balance tracking
    "balance_score": 3.3,  # Average across all dimensions
    "most_developed": ["intellectual", "emotional", "vocational"],
    "least_developed": ["social", "environmental"],
    "recommended_focus": ["social", "environmental"]  # For well-rounded growth
}
```

## 4. Expanded Challenge Types & Combat System

### 4.1 Challenge Categories

#### A. Mental Challenges (Intellectual Dimension)
1. **Riddles** - Logic puzzles requiring deduction
2. **Ciphers** - Code-breaking and pattern recognition
3. **Memory Games** - Recall and sequence challenges
4. **Strategy Games** - Chess-like tactical thinking
5. **Mathematical Puzzles** - Numerical problem-solving
6. **Lateral Thinking** - Creative problem-solving

#### B. Physical Challenges (Physical Dimension)
1. **Combat** - Direct confrontation (see Combat System below)
2. **Obstacle Courses** - Navigation and agility
3. **Endurance Tests** - Stamina and persistence
4. **Precision Tasks** - Fine motor control
5. **Reflex Challenges** - Quick reaction time
6. **Strength Tests** - Raw power application

#### C. Social Challenges (Social Dimension)
1. **Negotiation** - Conflict resolution through dialogue
2. **Persuasion** - Influence and convince others
3. **Deception Detection** - Identify lies and truth
4. **Team Coordination** - Group synchronization
5. **Leadership Tests** - Guide and inspire others
6. **Cultural Navigation** - Adapt to social norms

#### D. Emotional Challenges (Emotional Dimension)
1. **Stress Management** - Remain calm under pressure
2. **Empathy Scenarios** - Understand others' feelings
3. **Trauma Processing** - Handle difficult emotions
4. **Temptation Resistance** - Self-control and discipline
5. **Fear Confrontation** - Face phobias and anxiety
6. **Relationship Repair** - Mend broken connections

#### E. Spiritual Challenges (Spiritual Dimension)
1. **Moral Dilemmas** - Ethical decision-making
2. **Purpose Quests** - Find meaning in adversity
3. **Value Conflicts** - Resolve competing priorities
4. **Sacrifice Decisions** - Choose what matters most
5. **Forgiveness Scenarios** - Let go of grudges
6. **Faith Tests** - Trust in the face of uncertainty

#### F. Vocational Challenges (Vocational Dimension)
1. **Craft Mastery** - Create high-quality items
2. **Professional Puzzles** - Job-specific problems
3. **Skill Competitions** - Demonstrate expertise
4. **Innovation Challenges** - Improve existing methods
5. **Apprenticeship Tests** - Prove readiness to advance
6. **Quality Control** - Identify flaws and fix them

#### G. Environmental Challenges (Environmental Dimension)
1. **Ecosystem Management** - Balance natural systems
2. **Resource Optimization** - Sustainable use of materials
3. **Pollution Solutions** - Clean up environmental damage
4. **Wildlife Interaction** - Coexist with nature
5. **Climate Adaptation** - Respond to environmental changes
6. **Conservation Decisions** - Protect vs. exploit resources

### 4.2 Combat System with Dimensional Integration

Combat is a **Physical** challenge but can engage **all dimensions**:

```python
{
    "challenge_type": "combat",
    "combat_subtype": "tactical_battle|duel|skirmish|siege",
    "primary_dimension": "physical",
    "secondary_dimensions": ["emotional", "intellectual", "social"],

    "combat_rubric": {
        "physical_component": {
            "weight": 0.40,
            "criteria": [
                {
                    "criterion": "Combat Technique",
                    "bloom_level_target": 3,  # Apply level
                    "scoring": [
                        {"score": 1, "description": "Poor form, wasted movements"},
                        {"score": 2, "description": "Basic competence"},
                        {"score": 3, "description": "Skilled technique"},
                        {"score": 4, "description": "Master-level execution"}
                    ]
                },
                {
                    "criterion": "Physical Conditioning",
                    "bloom_level_target": 2,  # Understand
                    "scoring": [
                        {"score": 1, "description": "Exhausted quickly"},
                        {"score": 2, "description": "Adequate stamina"},
                        {"score": 3, "description": "Strong endurance"},
                        {"score": 4, "description": "Peak physical condition"}
                    ]
                }
            ]
        },

        "intellectual_component": {
            "weight": 0.25,
            "criteria": [
                {
                    "criterion": "Tactical Thinking",
                    "bloom_level_target": 4,  # Analyze
                    "scoring": [
                        {"score": 1, "description": "No strategy, reactive only"},
                        {"score": 2, "description": "Basic tactics"},
                        {"score": 3, "description": "Strategic planning"},
                        {"score": 4, "description": "Master tactician"}
                    ]
                },
                {
                    "criterion": "Environment Usage",
                    "bloom_level_target": 3,  # Apply
                    "scoring": [
                        {"score": 1, "description": "Ignores surroundings"},
                        {"score": 2, "description": "Basic awareness"},
                        {"score": 3, "description": "Tactical positioning"},
                        {"score": 4, "description": "Perfect terrain exploitation"}
                    ]
                }
            ]
        },

        "emotional_component": {
            "weight": 0.20,
            "criteria": [
                {
                    "criterion": "Stress Management",
                    "bloom_level_target": 3,  # Apply
                    "scoring": [
                        {"score": 1, "description": "Panic, poor decisions"},
                        {"score": 2, "description": "Somewhat composed"},
                        {"score": 3, "description": "Calm under pressure"},
                        {"score": 4, "description": "Ice-cold composure"}
                    ]
                },
                {
                    "criterion": "Combat Mercy",
                    "bloom_level_target": 5,  # Evaluate
                    "scoring": [
                        {"score": 1, "description": "Unnecessary brutality"},
                        {"score": 2, "description": "Standard force"},
                        {"score": 3, "description": "Measured response"},
                        {"score": 4, "description": "Minimal harm, maximum effect"}
                    ]
                }
            ]
        },

        "social_component": {
            "weight": 0.15,
            "criteria": [
                {
                    "criterion": "Team Coordination",
                    "bloom_level_target": 3,  # Apply
                    "scoring": [
                        {"score": 1, "description": "No teamwork, hinders allies"},
                        {"score": 2, "description": "Stays out of the way"},
                        {"score": 3, "description": "Good coordination"},
                        {"score": 4, "description": "Perfect synchronization"}
                    ]
                }
            ]
        }
    },

    "dimensional_rewards": {
        "physical": {
            "bloom_target": 3,
            "experience_by_score": {
                "1": 10,
                "2": 25,
                "3": 50,
                "4": 100
            }
        },
        "intellectual": {
            "bloom_target": 4,
            "experience_by_score": {
                "1": 5,
                "2": 15,
                "3": 35,
                "4": 75
            }
        },
        "emotional": {
            "bloom_target": 3,
            "experience_by_score": {
                "1": 5,
                "2": 15,
                "3": 30,
                "4": 60
            }
        },
        "social": {
            "bloom_target": 3,
            "experience_by_score": {
                "1": 3,
                "2": 10,
                "3": 20,
                "4": 40
            }
        }
    },

    "knowledge_gained": {
        "4": ["kg_combat_mastery_001:level_4", "kg_tactical_thinking_001:level_3"],
        "3": ["kg_combat_mastery_001:level_3", "kg_tactical_thinking_001:level_2"],
        "2": ["kg_combat_mastery_001:level_2"],
        "1": ["kg_combat_mastery_001:level_1"]
    }
}
```

## 5. Four Interaction Types & Rubrics

### 5.1 NPC Conversation

#### Purpose
Players gain knowledge/items through dialogue, persuasion, and relationship building.

#### Rubric Structure
```python
{
    "rubric_id": "conversation_rubric_001",
    "rubric_type": "npc_conversation",
    "interaction_name": "Learn Mining Techniques from Elder Miner",
    "npc_id": "npc_miner_001",

    "evaluation_criteria": [
        {
            "criterion": "Relationship Building",
            "weight": 0.25,
            "levels": [
                {"score": 1, "description": "Hostile or dismissive approach"},
                {"score": 2, "description": "Neutral but respectful"},
                {"score": 3, "description": "Friendly and engaging"},
                {"score": 4, "description": "Deep rapport established"}
            ]
        },
        {
            "criterion": "Question Quality",
            "weight": 0.35,
            "levels": [
                {"score": 1, "description": "Generic or irrelevant questions"},
                {"score": 2, "description": "Surface-level relevant questions"},
                {"score": 3, "description": "Thoughtful, targeted questions"},
                {"score": 4, "description": "Expert-level probing questions"}
            ]
        },
        {
            "criterion": "Active Listening",
            "weight": 0.20,
            "levels": [
                {"score": 1, "description": "Ignores NPC cues and hints"},
                {"score": 2, "description": "Acknowledges some information"},
                {"score": 3, "description": "Builds on NPC responses"},
                {"score": 4, "description": "Demonstrates full comprehension"}
            ]
        },
        {
            "criterion": "Context Understanding",
            "weight": 0.20,
            "levels": [
                {"score": 1, "description": "No connection to quest context"},
                {"score": 2, "description": "Basic context awareness"},
                {"score": 3, "description": "Good situational understanding"},
                {"score": 4, "description": "Masterful context integration"}
            ]
        }
    ],

    "knowledge_level_mapping": {
        "1.0-1.75": 1,  # Partial level 1 (25%)
        "1.76-2.5": 2,  # Partial level 2 (50%)
        "2.51-3.25": 3, # Partial level 3 (75%)
        "3.26-4.0": 4   # Full mastery (100%)
    },

    "rewards_by_performance": {
        "knowledge": {
            "1": ["kg_ancient_mining_001:level_1"],
            "2": ["kg_ancient_mining_001:level_2"],
            "3": ["kg_ancient_mining_001:level_3"],
            "4": ["kg_ancient_mining_001:level_4"]
        },
        "items": {
            "3": ["item_mining_guide_001"],  # Bonus item at level 3+
            "4": ["item_mining_guide_001", "item_master_tools_001"]
        }
    }
}
```

### 3.2 Environmental Discovery

#### Purpose
Players gain knowledge/items by observing, investigating, and interpreting their surroundings.

#### Rubric Structure
```python
{
    "rubric_id": "discovery_rubric_001",
    "rubric_type": "environmental_discovery",
    "interaction_name": "Investigate Ancient Mining Equipment",
    "discovery_id": "disc_mining_tools_001",

    "evaluation_criteria": [
        {
            "criterion": "Observation Detail",
            "weight": 0.30,
            "levels": [
                {"score": 1, "description": "Superficial glance, misses key details"},
                {"score": 2, "description": "Notices obvious features"},
                {"score": 3, "description": "Thorough examination, finds hidden details"},
                {"score": 4, "description": "Expert analysis, connects all clues"}
            ]
        },
        {
            "criterion": "Investigation Method",
            "weight": 0.25,
            "levels": [
                {"score": 1, "description": "Random or destructive approach"},
                {"score": 2, "description": "Systematic but basic search"},
                {"score": 3, "description": "Methodical and careful investigation"},
                {"score": 4, "description": "Professional forensic-level examination"}
            ]
        },
        {
            "criterion": "Pattern Recognition",
            "weight": 0.25,
            "levels": [
                {"score": 1, "description": "No connections made"},
                {"score": 2, "description": "Identifies some patterns"},
                {"score": 3, "description": "Recognizes most relationships"},
                {"score": 4, "description": "Complete pattern comprehension"}
            ]
        },
        {
            "criterion": "Knowledge Application",
            "weight": 0.20,
            "levels": [
                {"score": 1, "description": "No use of existing knowledge"},
                {"score": 2, "description": "Basic knowledge application"},
                {"score": 3, "description": "Effective integration of knowledge"},
                {"score": 4, "description": "Expert synthesis of all knowledge"}
            ]
        }
    ],

    "knowledge_level_mapping": {
        "1.0-1.75": 1,
        "1.76-2.5": 2,
        "2.51-3.25": 3,
        "3.26-4.0": 4
    },

    "rewards_by_performance": {
        "knowledge": {
            "1": ["kg_ancient_mining_001:level_1"],
            "2": ["kg_ancient_mining_001:level_2"],
            "3": ["kg_ancient_mining_001:level_2", "kg_safety_protocols_001:level_1"],
            "4": ["kg_ancient_mining_001:level_3", "kg_safety_protocols_001:level_2"]
        },
        "items": {
            "2": ["item_mining_notes_001"],
            "4": ["item_mining_notes_001", "item_ancient_tools_001"]
        }
    }
}
```

### 3.3 Challenges (Puzzles & Combat)

#### Purpose
Players gain knowledge/items by overcoming obstacles that test their skills and problem-solving.

#### Rubric Structure
```python
{
    "rubric_id": "challenge_rubric_001",
    "rubric_type": "challenge",
    "challenge_subtype": "puzzle|combat|skill_check|social",
    "interaction_name": "Navigate Unstable Mine Shaft",
    "challenge_id": "chal_navigate_mine_001",

    "evaluation_criteria": [
        {
            "criterion": "Problem Solving",
            "weight": 0.35,
            "levels": [
                {"score": 1, "description": "Brute force or random attempts"},
                {"score": 2, "description": "Trial and error with learning"},
                {"score": 3, "description": "Logical deduction and planning"},
                {"score": 4, "description": "Elegant, optimal solution"}
            ]
        },
        {
            "criterion": "Resource Management",
            "weight": 0.25,
            "levels": [
                {"score": 1, "description": "Wasteful use of resources"},
                {"score": 2, "description": "Adequate resource usage"},
                {"score": 3, "description": "Efficient resource allocation"},
                {"score": 4, "description": "Masterful optimization"}
            ]
        },
        {
            "criterion": "Risk Assessment",
            "weight": 0.20,
            "levels": [
                {"score": 1, "description": "Reckless or overly cautious"},
                {"score": 2, "description": "Basic risk awareness"},
                {"score": 3, "description": "Calculated risk-taking"},
                {"score": 4, "description": "Expert risk management"}
            ]
        },
        {
            "criterion": "Adaptability",
            "weight": 0.20,
            "levels": [
                {"score": 1, "description": "Rigid, cannot adjust approach"},
                {"score": 2, "description": "Adjusts after multiple failures"},
                {"score": 3, "description": "Quick adaptation to changes"},
                {"score": 4, "description": "Proactive strategy modification"}
            ]
        }
    ],

    "knowledge_level_mapping": {
        "1.0-1.75": 1,
        "1.76-2.5": 2,
        "2.51-3.25": 3,
        "3.26-4.0": 4
    },

    "rewards_by_performance": {
        "knowledge": {
            "1": ["kg_ancient_mining_001:level_1"],
            "2": ["kg_ancient_mining_001:level_2", "kg_navigation_skills_001:level_1"],
            "3": ["kg_ancient_mining_001:level_3", "kg_navigation_skills_001:level_2"],
            "4": ["kg_ancient_mining_001:level_4", "kg_navigation_skills_001:level_3"]
        },
        "items": {
            "2": ["item_climbing_rope_001"],
            "3": ["item_climbing_rope_001", "item_safety_harness_001"],
            "4": ["item_climbing_rope_001", "item_safety_harness_001", "item_master_gear_001"]
        }
    },

    "failure_consequences": {
        "1": {
            "injury": "Severe injury from collapse (-2 HP)",
            "time_loss": "3 hours lost",
            "equipment_damage": "Rope damaged beyond repair"
        },
        "2": {
            "injury": "Moderate injury (-1 HP)",
            "time_loss": "1 hour lost",
            "equipment_damage": "Minor damage to gear"
        }
    }
}
```

### 3.4 Dynamic Events

#### Purpose
Players gain knowledge/items by responding appropriately to unexpected situations.

#### Rubric Structure
```python
{
    "rubric_id": "event_rubric_001",
    "rubric_type": "dynamic_event",
    "interaction_name": "Respond to Mine Tremor",
    "event_id": "evt_mine_tremor_001",

    "evaluation_criteria": [
        {
            "criterion": "Situation Assessment",
            "weight": 0.30,
            "levels": [
                {"score": 1, "description": "Panic or freeze, no assessment"},
                {"score": 2, "description": "Delayed recognition of danger"},
                {"score": 3, "description": "Quick, accurate threat evaluation"},
                {"score": 4, "description": "Instant comprehensive analysis"}
            ]
        },
        {
            "criterion": "Decision Speed",
            "weight": 0.25,
            "levels": [
                {"score": 1, "description": "Indecisive or too slow"},
                {"score": 2, "description": "Adequate response time"},
                {"score": 3, "description": "Quick, confident decisions"},
                {"score": 4, "description": "Lightning-fast optimal choices"}
            ]
        },
        {
            "criterion": "Action Effectiveness",
            "weight": 0.30,
            "levels": [
                {"score": 1, "description": "Counterproductive actions"},
                {"score": 2, "description": "Partially effective response"},
                {"score": 3, "description": "Effective problem mitigation"},
                {"score": 4, "description": "Optimal outcome achieved"}
            ]
        },
        {
            "criterion": "Learning from Event",
            "weight": 0.15,
            "levels": [
                {"score": 1, "description": "No insights gained"},
                {"score": 2, "description": "Basic lesson learned"},
                {"score": 3, "description": "Deep understanding acquired"},
                {"score": 4, "description": "Expert-level insights"}
            ]
        }
    ],

    "knowledge_level_mapping": {
        "1.0-1.75": 1,
        "1.76-2.5": 2,
        "2.51-3.25": 3,
        "3.26-4.0": 4
    },

    "rewards_by_performance": {
        "knowledge": {
            "1": ["kg_danger_awareness_001:level_1"],
            "2": ["kg_danger_awareness_001:level_2", "kg_ancient_mining_001:level_1"],
            "3": ["kg_danger_awareness_001:level_3", "kg_ancient_mining_001:level_2", "kg_emergency_response_001:level_1"],
            "4": ["kg_danger_awareness_001:level_4", "kg_ancient_mining_001:level_3", "kg_emergency_response_001:level_2"]
        },
        "items": {
            "3": ["item_revealed_passage_map_001"],  # New path discovered
            "4": ["item_revealed_passage_map_001", "item_mineral_sample_001"]
        }
    },

    "consequences_by_performance": {
        "1": {
            "injury": "Struck by falling debris (-2 HP)",
            "status": "Shaken (disadvantage on next challenge)"
        },
        "2": {
            "injury": "Minor scrapes (-1 HP)",
            "time_loss": "30 minutes delay"
        }
    }
}
```

---

## 4. Progression Tracking System

### 4.1 Player State Enhancement
```python
{
    "player_id": "player_001",
    "campaign_id": "campaign_001",

    # Knowledge progression
    "acquired_knowledge": {
        "kg_ancient_mining_001": {
            "current_level": 2,  # 50% understanding
            "max_level": 4,
            "acquisition_history": [
                {
                    "timestamp": "2025-01-13T10:30:00Z",
                    "source_type": "npc_conversation",
                    "source_id": "npc_miner_001",
                    "level_gained": 1,
                    "rubric_score": 1.5
                },
                {
                    "timestamp": "2025-01-13T11:15:00Z",
                    "source_type": "discovery",
                    "source_id": "disc_mining_notes_001",
                    "level_gained": 2,
                    "rubric_score": 2.3
                }
            ]
        }
    },

    # Item inventory
    "acquired_items": {
        "item_climbing_rope_001": {
            "quantity": 1,
            "acquisition_source": "challenge",
            "acquisition_source_id": "chal_navigate_mine_001",
            "acquisition_timestamp": "2025-01-13T12:00:00Z",
            "condition": "good"
        }
    },

    # Quest progression
    "quest_progress": {
        "quest_001": {
            "status": "in_progress",
            "objectives_completed": [],
            "objectives_in_progress": ["quest_obj_1"],
            "required_knowledge_met": {
                "kg_ancient_mining_001": {
                    "required_level": 3,
                    "current_level": 2,
                    "met": false
                }
            },
            "required_items_met": {
                "item_climbing_rope_001": {
                    "required": true,
                    "acquired": true,
                    "met": true
                }
            }
        }
    }
}
```

### 4.2 Objective Completion Logic
```python
def can_complete_objective(player_state, objective_id):
    """
    Check if player has sufficient knowledge/items to complete objective
    """
    objective = get_objective(objective_id)

    # Check required knowledge levels
    for kg_req in objective["required_knowledge"]:
        player_kg = player_state["acquired_knowledge"].get(kg_req["knowledge_id"])
        if not player_kg or player_kg["current_level"] < kg_req["min_level"]:
            return False, f"Insufficient knowledge: {kg_req['knowledge_id']}"

    # Check required items
    for item_req in objective["required_items"]:
        player_item = player_state["acquired_items"].get(item_req["item_id"])
        if not player_item or player_item["quantity"] < item_req["quantity"]:
            return False, f"Missing item: {item_req['item_id']}"

    return True, "All requirements met"
```

---

## 5. Implementation Phases

### Phase 1: Data Model Updates (Week 1-2)
- [ ] Update `state.py` with new Knowledge and Item structures
- [ ] Add rubric data structures
- [ ] Update scene/quest/campaign models with objective links
- [ ] Add player progression tracking models

### Phase 2: Objective Linking System (Week 2-3)
- [ ] Modify quest generation to define required knowledge/items
- [ ] Create objective decomposition logic
- [ ] Build knowledge/item requirement calculator

### Phase 3: Rubric System (Week 3-4)
- [ ] Implement rubric templates for each interaction type
- [ ] Create scoring engine
- [ ] Build reward distribution system based on scores

### Phase 4: Scene Generation Updates (Week 4-5)
- [ ] Update scene element generation to reference quest objectives
- [ ] Implement redundancy logic (multiple acquisition paths)
- [ ] Generate knowledge/items with partial level definitions

### Phase 5: Progression Tracking (Week 5-6)
- [ ] Implement player state tracking
- [ ] Build objective completion checker
- [ ] Create progression visualization for UI

### Phase 6: Testing & Refinement (Week 6-8)
- [ ] Generate test campaigns with full progression
- [ ] Validate rubric fairness and balance
- [ ] Tune difficulty curves
- [ ] User testing and feedback

---

## 6. Example: Complete Scene Flow

### Scene: "The Impact Zone"
**Quest Objective**: Learn about the rockslide cause and find a safe path forward

#### Required Knowledge & Items
```python
{
    "quest_obj_1": "Understand what caused the rockslide",
    "required_knowledge": [
        {"knowledge_id": "kg_ancient_mining_001", "min_level": 2},
        {"knowledge_id": "kg_geological_analysis_001", "min_level": 1}
    ],
    "required_items": []
}

{
    "quest_obj_2": "Find equipment to traverse unstable terrain",
    "required_knowledge": [
        {"knowledge_id": "kg_ancient_mining_001", "min_level": 1}
    ],
    "required_items": [
        {"item_id": "item_climbing_rope_001", "quantity": 1}
    ]
}
```

#### Knowledge Acquisition Paths
**kg_ancient_mining_001** (Target: Level 2+)
1. **NPC Conversation** with Elder Miner (Max Level 3)
2. **Discovery** of Mining Equipment (Max Level 2) ✓ Sufficient
3. **Challenge** Navigate Unstable Crater (Max Level 4)
4. **Event** Mine Tremor Response (Max Level 3)

**kg_geological_analysis_001** (Target: Level 1+)
1. **Discovery** of Survey Notes (Max Level 2) ✓ Sufficient
2. **NPC Conversation** with Geologist NPC (Max Level 3)

#### Item Acquisition Paths
**item_climbing_rope_001**
1. **Discovery** in debris pile (Easy)
2. **Challenge** Rescue Trapped Miner (Hard, requires knowledge)
3. **NPC Conversation** Purchase from merchant (requires reputation)

#### Player Experience
- Player discovers mining equipment → Gains kg_ancient_mining_001:Level_2 ✓
- Player discovers survey notes → Gains kg_geological_analysis_001:Level_1 ✓
- Player talks to Elder Miner → Gains kg_ancient_mining_001:Level_3 (bonus)
- Player finds rope in debris → Gains item_climbing_rope_001 ✓
- **Result**: Can complete both objectives!

---

## 7. Benefits of New System

1. **Clear Progression Path**: Players always know what they need
2. **Multiple Routes**: No single failure blocks progress
3. **Skill Recognition**: Rubrics reward good play with better rewards
4. **Partial Credit**: Players gain something from every attempt
5. **Replayability**: Different paths each playthrough
6. **Educational Alignment**: Bloom's Taxonomy integration
7. **Narrative Coherence**: Everything ties to objectives

---

## 8. Next Steps

1. Review and approve this design document
2. Update TypedDict definitions in `state.py`
3. Create rubric template library
4. Modify quest generation to output knowledge/item requirements
5. Update scene generation to create acquisition methods
6. Build progression tracking system
7. Update UI to display requirements and progress

---

**Document Version**: 1.0
**Date**: 2025-01-13
**Author**: Claude Code (SkillForge Development)
