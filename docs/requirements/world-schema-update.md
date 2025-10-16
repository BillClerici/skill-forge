# World Schema Update - Multi-Select Fields

## Overview
Updated the World data model to support multi-select fields for universes, themes, and visual styles, enabling richer categorization and purpose-driven world assignment.

## Changes Summary

### 1. **Universe Assignment** - Single → Multiple
**Old**: A world belonged to one universe
**New**: A world can belong to multiple universes

#### MongoDB Schema Change
```json
// OLD
{
  "_id": "uuid",
  "world_name": "The Shattered Kingdoms",
  "universe_id": "550e8400-e29b-41d4-a716-446655440001",  // Single ID
  "genre": "fantasy",
  "themes": "magic,dragons,war",  // Comma-separated string
  "visual_style": "watercolor fantasy"  // Single string
}

// NEW
{
  "_id": "uuid",
  "world_name": "The Shattered Kingdoms",
  "universe_ids": [  // Array of universe IDs
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ],
  "genre": "Fantasy",  // Single dropdown selection
  "themes": [  // Array from multi-select
    "Magic",
    "Dragons",
    "War"
  ],
  "visual_style": [  // Array from multi-select
    "Dark-and-Gritty",
    "Detailed"
  ],
  "setting": "...",
  "lore": { ... }
}
```

### 2. **Genre** - Freeform → Dropdown
**Old**: Text input allowing any value
**New**: Dropdown with predefined options

#### Available Genres
- Fantasy
- Sci-Fi
- Horror
- Cyberpunk
- Steampunk
- Post-Apocalyptic
- Historical
- Modern
- Mystery
- Adventure
- Western
- Superhero

### 3. **Themes** - Comma-Separated String → Multi-Select
**Old**: Single text field with comma-separated values
**New**: Multi-select dropdown

#### Available Themes
- Magic
- Dragons
- War
- Politics
- Exploration
- Technology
- Religion
- Mystery
- Romance
- Survival
- Trade
- Prophecy
- Rebellion
- Ancient Civilizations

### 4. **Visual Style** - Single String → Multi-Select
**Old**: Single text field for visual description
**New**: Multi-select dropdown allowing multiple aesthetic choices

#### Available Visual Styles
- Dark and Gritty
- Bright and Colorful
- Realistic
- Stylized
- Noir
- Minimalist
- Detailed
- Gothic
- Whimsical
- Retro

## Neo4j Relationship Changes

### Old: Single Universe Relationship
```cypher
(:World {id: "world-id"})-[:IN_UNIVERSE]->(:Universe {id: "universe-id"})
```

### New: Multiple Universe Relationships
```cypher
(:World {id: "world-id"})-[:IN_UNIVERSE]->(:Universe {id: "universe-1"})
(:World {id: "world-id"})-[:IN_UNIVERSE]->(:Universe {id: "universe-2"})
(:World {id: "world-id"})-[:IN_UNIVERSE]->(:Universe {id: "universe-3"})
```

## Benefits

### 1. Purpose-Driven Universe Assignment
A world can now belong to multiple universes based on different purposes:

**Example**: "The Shattered Kingdoms" (Fantasy world)
- **Family-Friendly Universe** - PG-rated version
- **Teen Universe** - Age-appropriate challenges
- **Educational Universe** - History and civics focus
- **Narrative-Driven Universe** - Story-focused gameplay

### 2. Richer Categorization
Multiple themes and visual styles allow for nuanced world discovery:

**Example**: A world with themes `["Technology", "Politics", "Rebellion"]` and visual styles `["Dark-and-Gritty", "Noir"]` clearly signals a cyberpunk dystopian setting.

### 3. Improved Filtering & Discovery
Users can find worlds by:
- **Multiple universes**: See all worlds in their selected universes
- **Theme combinations**: Filter by specific theme combinations
- **Visual preferences**: Match their aesthetic preferences

## Implementation Details

### Form Handling
- **Materialize CSS**: Using `multiple` attribute on `<select>` elements
- **Django**: Using `request.POST.getlist()` to capture multi-select values
- **Template**: Checking `if value in array` for selected state

### Backwards Compatibility
The update views include legacy support:

```python
# Convert old single universe_id to new array format
universe_ids = world.get('universe_ids', [])
if not universe_ids and world.get('universe_id'):
    universe_ids = [world.get('universe_id')]

# Convert old comma-separated themes to array
themes = world.get('themes', [])
if isinstance(themes, str):
    themes = [t.strip() for t in themes.split(',') if t.strip()]
```

### Display Formatting
```python
# In views.py
world['themes_display'] = ', '.join(world['themes'])
world['visual_style_display'] = ', '.join(world['visual_style'])
```

```django
<!-- In templates -->
{% for theme in world.themes %}
    <span class="chip">{{ theme }}</span>
{% endfor %}
```

## Migration Notes

### Existing Data
- Worlds with `universe_id` (string) will be automatically converted to `universe_ids` (array) in the update view
- Worlds with `themes` (comma-separated string) will be converted to array format
- Worlds with `visual_style` (string) will be converted to array format

### No Data Loss
The conversion is non-destructive. Old data is preserved and reformatted on next edit.

## Testing Checklist

- [x] Create new world with multiple universes
- [x] Create new world with multiple themes
- [x] Create new world with multiple visual styles
- [x] Edit existing world to add/remove universes
- [x] Edit existing world to change themes
- [x] Edit existing world to change visual styles
- [x] View world detail page showing all selected values
- [x] Verify Neo4j relationships created for all selected universes
- [x] Verify backwards compatibility with existing data
- [x] Test deletion warnings when world belongs to multiple universes

## Future Enhancements

1. **Validation Rules**: Ensure theme/style combinations make sense for selected genre
2. **Universe Constraints**: Validate that world content matches all selected universe requirements
3. **Automatic Suggestions**: Suggest additional universes based on world attributes
4. **Advanced Filtering**: UI for complex multi-criteria world discovery
