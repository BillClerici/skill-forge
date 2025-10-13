# Bloom's Taxonomy Descriptions Comparison
## Personal Evolution Arc vs. Dimensional Maturity

### Date: 2025-01-13

---

## The Problem

Originally, both **Personal Evolution Arc** and **Dimensional Maturity** used the same basic Bloom's Taxonomy descriptions:

- Level 1: "Recall facts and basic concepts"
- Level 2: "Explain ideas or concepts"
- Level 3: "Use information in new situations"
- etc.

This was **incorrect** because:
- Personal Evolution Arc represents **meta-cognitive development and integrated wisdom**
- Using basic skill descriptions like "recall facts" doesn't capture wisdom/integration
- The two systems serve different purposes and need different language

---

## The Solution

### Two Different Description Sets

#### 1. Personal Evolution Arc (Meta-Cognitive & Integration)

**Used for**: Overall character wisdom, requires balanced growth

| Level | Name | Old Description ❌ | New Description ✅ |
|-------|------|-------------------|-------------------|
| 1 | Novice | Recall facts and basic concepts | **Developing awareness across multiple dimensions** |
| 2 | Apprentice | Explain ideas or concepts | **Understanding connections between growth areas** |
| 3 | Journeyman | Use information in new situations | **Applying integrated knowledge across domains** |
| 4 | Expert | Draw connections among ideas | **Analyzing patterns across all dimensions** |
| 5 | Master | Justify a stand or decision | **Evaluating holistic development with wisdom** |
| 6 | Grandmaster | Produce new or original work | **Creating transformative synthesis and original frameworks** |

**Key Differences**:
- Emphasizes **integration** across dimensions
- Focuses on **holistic** understanding
- Uses **meta-cognitive** language
- Reflects **wisdom**, not just skills

---

#### 2. Dimensional Maturity (Skill-Specific)

**Used for**: Individual dimension capabilities (Physical, Emotional, Intellectual, Social, Spiritual, Vocational, Environmental)

| Level | Name | Bloom's Term | Context-Dependent Meaning |
|-------|------|-------------|---------------------------|
| 1 | Novice | Remember | Recall basic techniques/concepts in this dimension |
| 2 | Apprentice | Understand | Explain how things work in this dimension |
| 3 | Journeyman | Apply | Use skills effectively in this dimension |
| 4 | Expert | Analyze | Break down complex patterns in this dimension |
| 5 | Master | Evaluate | Judge and refine techniques in this dimension |
| 6 | Grandmaster | Create | Innovate and create new approaches in this dimension |

**Key Differences**:
- Standard Bloom's terms work because **dimension name provides context**
- Example: "Physical - Remember" = Recall basic physical movements
- Example: "Spiritual - Evaluate" = Judge ethical soundness of actions
- Focuses on **domain-specific** capabilities

---

## Examples in Context

### Physical Dimension Progression

| Level | What It Means |
|-------|---------------|
| 1 - Remember | Recall basic movements and techniques |
| 2 - Understand | Explain proper form and technique |
| 3 - Apply | Use skills effectively in new contexts |
| 4 - Analyze | Understand body mechanics and optimize performance |
| 5 - Evaluate | Judge and refine physical techniques |
| 6 - Create | Invent new moves, techniques, or training methods |

### Spiritual Dimension Progression

| Level | What It Means |
|-------|---------------|
| 1 - Remember | Recall moral rules and values |
| 2 - Understand | Explain ethical principles |
| 3 - Apply | Apply values in decision-making |
| 4 - Analyze | Analyze moral dilemmas deeply |
| 5 - Evaluate | Judge ethical soundness of actions |
| 6 - Create | Develop original ethical frameworks |

### Personal Evolution Arc Progression

| Level | What It Means |
|-------|---------------|
| 1 - Novice | Developing awareness that there are multiple dimensions of growth |
| 2 - Apprentice | Understanding how Physical growth relates to Emotional growth, etc. |
| 3 - Journeyman | Applying lessons from one dimension to improve in another |
| 4 - Expert | Analyzing patterns: "My Physical training improved my Emotional resilience" |
| 5 - Master | Evaluating entire developmental journey with wisdom and balance |
| 6 - Grandmaster | Creating new frameworks for personal growth that transcend individual skills |

---

## Educational Rationale

### Bloom's Taxonomy Applied Correctly

**Domain-Specific Cognitive Skills** (Dimensional Maturity):
- "I can **analyze** combat tactics" → Physical/Intellectual dimensions at Analyze level
- "I can **evaluate** moral dilemmas" → Spiritual dimension at Evaluate level
- Skill-focused, domain-specific

**Meta-Cognitive Development** (Personal Evolution Arc):
- "I can **analyze patterns** across all my dimensional growth"
- "I understand how my **spiritual** development enhances my **social** skills"
- "I'm **creating** new ways to integrate learning from multiple areas"
- Wisdom-focused, integration-focused

This mirrors real education:
- **Subject mastery** = knowing math, writing, science separately (Dimensions)
- **Meta-learning** = understanding how to learn, connecting subjects, study strategies (Personal Evolution)

---

## Player-Facing Impact

### Character Sheet Now Shows

**Personal Evolution Arc Section**:
```
Level 3: Journeyman
"Applying integrated knowledge across domains"
```

**Dimensional Maturity Section**:
```
Physical Dimension: Level 4 - Expert (Analyze)
"Understand body mechanics and optimize performance"

Spiritual Dimension: Level 3 - Journeyman (Apply)
"Apply values in decision-making"
```

### Player Understanding

**Before**:
- ❓ "Both say 'recall facts' - what's the difference?"
- ❓ "Why is my Personal Evolution Arc at 'recall facts' when I'm wise?"

**After**:
- ✅ "Personal Evolution Arc = integration across dimensions"
- ✅ "Dimensional Maturity = specific skills in each area"
- ✅ "They represent different types of development"

---

## Implementation Changes

### Files Updated

1. **`characters/models.py`** (lines 26-34)
   - `BLOOMS_LEVEL_CHOICES` updated with meta-cognitive descriptions
   - Comment changed from "Bloom's Taxonomy Skill Level" to "Meta-Cognitive Development & Integrated Wisdom"

2. **`workflow/personal_evolution.py`** (lines 15-23)
   - `PERSONAL_EVOLUTION_LEVELS` updated with meta-cognitive descriptions
   - Added third tuple element for full description

### Backward Compatibility

- Database values unchanged (`remembering`, `understanding`, etc.)
- Display descriptions updated
- No migration needed

---

## Summary

| Aspect | Personal Evolution Arc | Dimensional Maturity |
|--------|----------------------|---------------------|
| **Level 1 Description** | "Developing awareness across multiple dimensions" | "Remember [domain-specific]" |
| **Focus** | Integration & wisdom | Domain expertise |
| **Language** | Meta-cognitive | Skill-based |
| **Example** | "Understanding connections between growth areas" | "Recall basic physical movements" |
| **Requires** | Balanced development | Specialized development OK |
| **Represents** | What you UNDERSTAND holistically | What you CAN DO specifically |

---

**The key insight**: Personal Evolution Arc is not just "Level 3 of a skill" - it's **Level 3 of WISDOM about how all your skills integrate**. The descriptions now reflect this crucial distinction.

---

**Version**: 1.0
**Date**: 2025-01-13
**Updated By**: User feedback + Claude Code
