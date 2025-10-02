# Universe Purpose-Driven Model

## Overview
Universes are **purpose-driven categories** that group worlds by **why** players want to play, not just **what genre** they prefer. This allows worlds of any genre to coexist within the same universe based on shared purpose, age-appropriateness, content rating, or educational goals.

## Key Concept
**Universe = Purpose/Category** (Age, Rating, Style, Context)
- Worlds of ANY genre that fit that purpose

## Benefits

### 1. Genre Flexibility Within Categories
A parent can choose the "Family-Friendly Universe" and find:
- Fantasy worlds appropriate for children
- Sci-Fi worlds appropriate for children
- Historical worlds appropriate for children
- ALL in one place, curated for safety

### 2. Purpose-Driven Discovery
A teacher can choose the "Educational Universe" and find:
- Historical worlds for teaching history
- Sci-Fi worlds for teaching science
- Fantasy worlds for teaching ethics
- Mystery worlds for teaching critical thinking

### 3. Multiple Categorization
The same world can exist in multiple Universes:

**Example: "The Shattered Kingdoms" (Fantasy world)**
- Standard RPG Universe (general play)
- Teen Universe (age-appropriate version)
- Educational Universe (history/civics focus)
- PG-13 Universe (content rating)

### 4. Clearer User Intent
Players choose based on **why** they're playing:
- "I want something safe for my kids" → Family Universe
- "I want to learn while playing" → Educational Universe
- "I want mature, complex narratives" → Adult Universe
- "I want competitive challenges" → Competitive Universe

## Universe Categories/Purposes

### By Age
- **Children's Universe** - Ages 5-10
- **Teen Universe** - Ages 11-17
- **Adult Universe** - Ages 18+

### By Educational Goal
- **STEM Learning Universe** - Science, Technology, Engineering, Math
- **History & Culture Universe** - Historical accuracy, cultural exploration
- **Literature & Arts Universe** - Creative writing, storytelling
- **Critical Thinking Universe** - Logic puzzles, problem-solving

### By Content Rating
- **G-Rated Universe** - General audiences
- **PG Universe** - Parental guidance suggested
- **PG-13 Universe** - Parents strongly cautioned
- **R-Rated Universe** - Restricted, mature content

### By Play Style
- **Cooperative Universe** - Team-based, collaborative
- **Competitive Universe** - PvP, rankings, leaderboards
- **Sandbox Universe** - Open-ended, creative freedom
- **Narrative-Driven Universe** - Story-focused, character development

### By Accessibility
- **Beginner-Friendly Universe** - Simple rules, guided play
- **Intermediate Universe** - Moderate complexity
- **Advanced Universe** - Complex mechanics, deep strategy

## Data Model

### Universe Definition (MongoDB)
```json
{
  "_id": "uuid",
  "universe_name": "Family-Friendly Adventure Universe",
  "purpose_category": "family_friendly",  // NEW FIELD
  "description": "Safe, age-appropriate adventures for families",
  "target_age_group": "children",  // NEW FIELD
  "educational_focus": [],  // NEW FIELD - array of focus areas
  "max_content_rating": "PG",
  "narrative_tone": {
    "style": "friendly",
    "humor_level": "moderate"
  },
  "vocabulary_style": {
    "reading_level": "middle_school",
    "complexity": "moderate"
  },
  "features": {
    "combat_enabled": false,
    "romance_enabled": false,
    "character_death": false
  }
}
```

### World Assignment (Many-to-Many via Neo4j)
Worlds can belong to multiple universes:
```cypher
(:World {id: "world-id", name: "The Shattered Kingdoms", genre: "fantasy"})
  -[:AVAILABLE_IN]-> (:Universe {id: "rpg-universe"})
  -[:AVAILABLE_IN]-> (:Universe {id: "teen-universe"})
  -[:AVAILABLE_IN]-> (:Universe {id: "educational-universe"})
```

## Implementation Impact

### UI Changes Needed
1. Universe creation form adds:
   - Purpose/Category dropdown
   - Target age group selection
   - Educational focus multi-select (optional)

2. World assignment interface:
   - Allow worlds to be added to multiple universes
   - Show which universes a world belongs to
   - Validate world fits universe constraints

3. Universe browsing:
   - Filter by purpose category
   - Show world count per universe
   - Display purpose-specific metadata

### Validation Rules
- World content must not exceed universe's max_content_rating
- World reading level should match universe's target age group
- Educational worlds must align with universe's educational_focus (if specified)
