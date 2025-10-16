# Personal Evolution Arc vs. Dimensional Maturity Profile
## Understanding SkillForge's Dual Progression System

### Executive Summary

SkillForge uses **two interconnected but distinct progression systems**:

1. **Dimensional Maturity Profile** (Tactical) - 7 specific skill areas that grow through gameplay
2. **Personal Evolution Arc** (Strategic) - Overall meta-cognitive development that requires balanced growth

They are **NOT redundant** - each serves a different purpose in character development and game design.

---

## The Two Systems

### 🎯 Dimensional Maturity Profile (The "Skills")

**What It Tracks**: 7 specific areas of development
- Physical, Emotional, Intellectual, Social, Spiritual, Vocational, Environmental

**How It Updates**: Automatically after every rubric-evaluated interaction
- NPC conversation → +XP to Social, Emotional, Intellectual
- Combat challenge → +XP to Physical, Intellectual, Emotional
- Moral dilemma → +XP to Spiritual, Emotional, Social

**Progression**: Each dimension progresses independently through Bloom's 6 levels
- Player can be Expert (4) in Physical but Novice (1) in Social

**Purpose**:
- ✅ Granular skill tracking
- ✅ Creates diverse character builds
- ✅ Shows player strengths and weaknesses
- ✅ Guides scene generation to target weak areas

**Frequency**: Updates every interaction (high frequency)

---

### 🌟 Personal Evolution Arc (The "Wisdom")

**What It Tracks**: Meta-cognitive integration across all dimensions
- Character's ability to reflect, integrate, and synthesize learning
- Represents **wisdom**, **self-awareness**, and **balanced development**

**How It Updates**: Calculated based on dimensional maturity requirements
- NOT an average, but requires **minimum thresholds** in multiple dimensions
- Only updates when dimensional level-ups cause requirements to be met

**Progression Requirements**:

| Level | Name | Bloom's | Requirements | Meaning |
|-------|------|---------|--------------|---------|
| 1 | Novice | Remember | All dimensions at 1+ | Beginning journey |
| 2 | Apprentice | Understand | 5+ dimensions at 2+ | Developing understanding in multiple areas |
| 3 | Journeyman | Apply | 4+ at 3+, all at 2+ | Practically applying knowledge across domains |
| 4 | Expert | Analyze | 3+ at 4+, 6+ at 3+ | Analyzing patterns across dimensions |
| 5 | Master | Evaluate | 2+ at 5+, 5+ at 4+ | Evaluating with integrated judgment |
| 6 | Grandmaster | Create | 1+ at 6, 4+ at 5+, all at 4+ | Creating transformative synthesis |

**Purpose**:
- ✅ Represents hero's journey / main story arc
- ✅ Gates major campaign milestones
- ✅ Encourages balanced development (prevents min-maxing)
- ✅ Reflects true character maturity

**Frequency**: Updates rarely (only on dimensional level-ups)

---

## Why Both Systems Are Necessary

### Example Character Comparison

**Character A: "The Balanced Hero"**
```
Dimensional Maturity:
- Physical: Level 4 (Expert)
- Emotional: Level 4 (Expert)
- Intellectual: Level 3 (Journeyman)
- Social: Level 3 (Journeyman)
- Spiritual: Level 3 (Journeyman)
- Vocational: Level 3 (Journeyman)
- Environmental: Level 3 (Journeyman)

Personal Evolution Arc: Level 4 (Expert/Analyze)
✅ Meets requirement: 3+ at level 4+, 6+ at level 3+
```
**Narrative**: A well-rounded adventurer with deep understanding across multiple areas. Wise enough to lead others.

---

**Character B: "The Min-Maxed Fighter"**
```
Dimensional Maturity:
- Physical: Level 6 (Grandmaster)
- Emotional: Level 5 (Master)
- Intellectual: Level 2 (Apprentice)
- Social: Level 1 (Novice)
- Spiritual: Level 1 (Novice)
- Vocational: Level 2 (Apprentice)
- Environmental: Level 1 (Novice)

Personal Evolution Arc: Level 2 (Apprentice/Understand)
❌ Does NOT meet Level 3 requirement: needs 4+ at level 3+, all at 2+
```
**Narrative**: An incredibly skilled warrior, but lacks the balanced development for true wisdom. Cannot yet lead or face complex challenges that require integration.

---

### Gameplay Implications

**Campaign Gating**:
```
Quest: "Unite the Five Kingdoms"
Requirements:
- Personal Evolution Arc: Level 5 (Master) - You need wisdom to unite kingdoms
- Social Dimension: Level 4+ - You need diplomatic skills
- Spiritual Dimension: Level 3+ - You need ethical grounding
```

**Character A** ✅ Can attempt this quest (has Level 4 Personal Evolution)
**Character B** ❌ Cannot attempt (only Level 2 Personal Evolution despite high combat skills)

---

## Educational Rationale

### Bloom's Taxonomy Alignment

**Dimensional Maturity** = Domain-Specific Cognitive Skills
- "I can analyze combat tactics" (Physical/Intellectual dimension at Analyze level)
- "I can evaluate moral dilemmas" (Spiritual dimension at Evaluate level)

**Personal Evolution Arc** = Meta-Cognitive Development
- "I can integrate learning from multiple domains"
- "I can reflect on my growth holistically"
- "I have wisdom, not just skills"

This mirrors real education:
- You can be excellent at math but struggle with writing
- True expertise requires breadth AND depth
- Meta-cognition (thinking about thinking) is a separate skill

---

## Implementation Details

### Automatic Calculation

When a dimensional level-up occurs:

```python
# 1. Rubric awards XP to dimensions
dimensional_exp = calculate_dimensional_experience(rubric, scores)
# Result: {"social": 155, "emotional": 105, "intellectual": 50}

# 2. Progression tracker adds XP and checks for dimensional level-ups
profile = add_dimensional_experience(profile, "social", 155)
# Result: Social dimension levels up from 2 → 3

# 3. Personal Evolution Arc is automatically recalculated
pe_level, pe_blooms, pe_friendly = calculate_personal_evolution_level(profile["dimensional_maturity"])
# Result: Checks if new dimensional levels meet next Personal Evolution threshold

# 4. If requirements are met, Personal Evolution Arc levels up
if pe_level > old_pe_level:
    logger.info(f"PERSONAL EVOLUTION ARC LEVEL UP! {old_pe_level} -> {pe_level}")
    # Character's blooms_level field gets updated
```

### Storage

**Campaign Factory (MongoDB)**:
- `CharacterDevelopmentProfile.dimensional_maturity` - 7 dimensions with full tracking
- `CharacterDevelopmentProfile.personal_evolution` - Calculated Personal Evolution data

**Django Web (PostgreSQL)**:
- `Character.dimensional_maturity` (JSONB) - 7 dimensions for display
- `Character.blooms_level` (CharField) - Personal Evolution Arc level
- Synced from MongoDB profile periodically

---

## Player-Facing Communication

### Character Sheet Display

**Section 1: Personal Evolution Arc** (Top section - prominent)
```
🌟 Personal Evolution Arc: Level 3 - Journeyman (Apply)

Progress: ●✓●✓●●○○○○
         Novice → Apprentice → Journeyman → Expert → Master → Grandmaster

You're applying knowledge practically across multiple domains.

Next Level (Expert): Reach level 4+ in 3 dimensions, level 3+ in 6 dimensions
```

**Section 2: Dimensional Maturity Profile** (Detailed breakdown)
```
🎯 Dimensional Maturity Profile

Physical:      Level 3 ██████████░░░░ 250/300 XP (Journeyman)
Emotional:     Level 4 ██████████████░░ 150/600 XP (Expert)
Intellectual:  Level 3 ██████████░░░░ 200/300 XP (Journeyman)
...
```

### In-Game Messaging

When Personal Evolution Arc levels up:
```
╔═══════════════════════════════════════════════╗
║  🌟 PERSONAL EVOLUTION ARC ADVANCEMENT! 🌟    ║
╠═══════════════════════════════════════════════╣
║                                               ║
║  Through balanced growth across multiple      ║
║  dimensions, you have achieved:               ║
║                                               ║
║     JOURNEYMAN LEVEL (Apply)                  ║
║                                               ║
║  You now demonstrate the ability to apply     ║
║  knowledge practically across all domains.    ║
║  New quests and challenges await!             ║
║                                               ║
╚═══════════════════════════════════════════════╝
```

---

## Summary: Key Differences

| Aspect | Dimensional Maturity | Personal Evolution Arc |
|--------|---------------------|----------------------|
| **Purpose** | Track specific skills | Track integrated wisdom |
| **Granularity** | 7 independent dimensions | Single holistic level |
| **Update Frequency** | Every interaction | On dimensional level-ups |
| **Allows Specialization** | Yes (can max one dimension) | No (requires balance) |
| **Gates Content** | Specific dimensional requirements | Overall maturity requirements |
| **Represents** | What you CAN do | What you UNDERSTAND |
| **Bloom's Application** | Per-dimension cognitive skills | Meta-cognitive integration |
| **Player Control** | Direct (play to your strengths) | Indirect (must develop broadly) |

---

## Design Philosophy

> "In SkillForge, you can become a **Grandmaster warrior** (Physical dimension at level 6) while remaining an **Apprentice** in your Personal Evolution Arc (level 2) if you neglect other areas.
>
> This reflects real life: technical expertise ≠ wisdom.
>
> To face the greatest challenges and lead others, you must develop **balanced mastery** across multiple dimensions. The Personal Evolution Arc ensures that true character growth requires both **skill AND wisdom**."

---

**Version**: 1.0
**Date**: 2025-01-13
**System**: Personal Evolution Arc + 7 Dimensional Maturity System
