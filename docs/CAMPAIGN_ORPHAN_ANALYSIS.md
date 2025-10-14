# Campaign Entity Orphan Problem - Root Cause Analysis

## Summary
Campaign entities (Discoveries, Challenges, Events) are created as **completely orphaned nodes** in both MongoDB and Neo4j, with no relationships to Scenes, Places, Quests, or Campaign.

## Problems Identified

### 1. **Missing Entity IDs in Scenes (PRIMARY ISSUE)**

**Location:** During element generation (`nodes_elements.py`)

**Problem:**
- Scenes are populated with entity ID lists that contain only `None` values
- Example from state:
  ```python
  'npc_ids': [None, None, None, None],
  'discovery_ids': [None, None, None],
  'event_ids': [None, None, None],
  'challenge_ids': [None, None, None]
  ```

**Impact:**
- Persistence layer can't link entities to scenes because scene doesn't know which entities belong to it
- All entities become orphaned

**Root Cause:**
- Element generation creates entities but doesn't add their IDs to the parent scene's ID lists
- Likely missing code like: `scene['discovery_ids'].append(discovery['discovery_id'])`

---

### 2. **ID Regeneration During Persistence**

**Location:** `db_persistence.py` lines 304-363, 883-1012

**Problem:**
- Entities are generated with IDs like: `discovery_0a616e70bdbf4d0c`
- During persistence, NEW IDs are generated: `discovery_c78328bc-4575-4ab2-8110-308444aacebf_0`
- Code tries to match these IDs but they'll never match:
  ```python
  # Line 885 - generates NEW ID
  challenge_id = f"challenge_{state['request_id']}_{idx}"

  # Line 913 - tries to match OLD ID from scene
  if challenge_id in scene.get("challenge_ids", []):  # NEVER MATCHES!
  ```

**Impact:**
- Even if scene IDs were populated, they wouldn't match persistence IDs
- Entities created but never linked

---

### 3. **Missing Entity Data in MongoDB**

**Location:** `db_persistence.py` lines 307-321 (discoveries), 327-341 (events), 347-363 (challenges)

**Problem:**
- MongoDB documents created with minimal data
- Field names don't match entity structure:
  ```python
  # Code expects:
  discovery_doc = {"_id": discovery_id, "name": discovery["name"], ...}

  # But entity has:
  discovery["discovery_name"], not discovery["name"]
  ```

**Result:**
- MongoDB has stub documents with `"discovery_name": "N/A"` (missing field)
- No description, scene_id, campaign_id, etc.

---

### 4. **Missing campaign_id Property**

**Location:** All entity creation

**Problem:**
- Entities created in Neo4j without `campaign_id` property
- Current: `campaign_id: None`
- Should be: `campaign_id: "campaign_c78328bc-4575-4ab2-8110-308444aacebf"`

---

### 5. **Zero Relationships in Neo4j**

**Location:** `db_persistence.py` lines 883-1012

**Problem:**
- Nodes created but relationship creation code never executes
- Because: `if challenge_id in scene.get("challenge_ids", [])` fails (see Problem #1 and #2)

**Result:**
- Discovery nodes: 0 relationships
- Challenge nodes: 0 relationships
- Event nodes: 0 relationships

---

## Data State

### MongoDB
```
Campaigns: 1 ✅
Quests: 1 ✅
Places: 2 ✅
Scenes: 5 ✅
NPCs: 10 ✅
Discoveries: 15 ❌ (stub documents only)
Challenges: 15 ❌ (stub documents only)
Events: 8 ❌ (stub documents only)
Knowledge: 3 ✅
Items: 3 ✅
Rubrics: 48 ✅
```

### Neo4j
```
Campaign: 1 ✅
Quest: 1 ✅
Place: 2 ✅
Scene: 10 ✅ (includes location scenes)
NPC: 10 ✅
Discovery: 15 ❌ (0 relationships, campaign_id=None)
Challenge: 15 ❌ (0 relationships, campaign_id=None)
Event: 8 ❌ (0 relationships, campaign_id=None)
Knowledge: 3 ✅
Item: 3 ✅
Rubrics: 10 ❌ (only NPC rubrics linked)
```

---

## Fixes Required

### Fix 1: Populate Scene Entity IDs During Generation ⭐ **CRITICAL**

**File:** `services/campaign-factory/workflow/nodes_elements.py`

**Action:** When creating entities, add their IDs to parent scene:
```python
# After creating discovery:
discovery_id = f"discovery_{some_unique_id}"
discovery = {
    "discovery_id": discovery_id,
    "name": "...",
    # ... other fields
}
state["discoveries"].append(discovery)

# ADD THIS:
scene["discovery_ids"].append(discovery_id)
```

**Apply to:** Discoveries, Challenges, Events

---

### Fix 2: Use Original Entity IDs in Persistence

**File:** `services/campaign-factory/workflow/db_persistence.py`

**Action:** Don't regenerate IDs - use existing ones:
```python
# BEFORE (line 305):
discovery_id = f"discovery_{state['request_id']}_{idx}"

# AFTER:
discovery_id = discovery.get("discovery_id", f"discovery_{state['request_id']}_{idx}")
```

**Apply to:** Discoveries (line 305), Events (line 325), Challenges (line 345)

---

### Fix 3: Fix MongoDB Field Names

**File:** `services/campaign-factory/workflow/db_persistence.py`

**Action:** Match actual entity field names:
```python
# BEFORE (line 309):
"name": discovery["name"],

# AFTER:
"name": discovery.get("discovery_name") or discovery.get("name", "Unknown Discovery"),
```

**Apply to:** All entity types, check actual field names in generation code

---

### Fix 4: Add campaign_id to All Entities

**File:** `services/campaign-factory/workflow/db_persistence.py`

**Action:** Add campaign_id when creating MongoDB docs and Neo4j nodes:
```python
# MongoDB (line 307):
discovery_doc = {
    "_id": discovery_id,
    "name": discovery.get("discovery_name", "Unknown"),
    "campaign_id": campaign_id,  # ADD THIS
    "scene_id": discovery.get("scene_id"),  # ADD THIS
    # ... rest
}

# Neo4j (line 936):
session.run("""
    MERGE (d:Discovery {id: $discovery_id})
    SET d.name = $name,
        d.campaign_id = $campaign_id,  // ADD THIS
        d.description = $description
""",
    discovery_id=discovery_id,
    campaign_id=campaign_id,  # ADD THIS
    name=discovery.get("discovery_name", "Unknown"),
    # ... rest
)
```

---

### Fix 5: Simplify Scene-Entity Linking

**File:** `services/campaign-factory/workflow/db_persistence.py`

**Current approach (lines 883-927):** Loop through entire quest/place hierarchy to find matching scenes

**Better approach:**
```python
# Create scene_id to persisted_scene_id mapping once
scene_id_map = {}
scene_counter = 0
for quest in state["quests"]:
    for place in quest_places:
        for scene in place_scenes:
            scene_id_map[scene.get("scene_id")] = f"scene_{state['request_id']}_{scene_counter}"
            scene_counter += 1

# Then use simple lookup for linking:
for idx, challenge in enumerate(state.get("challenges", [])):
    challenge_id = challenge.get("challenge_id", f"challenge_{state['request_id']}_{idx}")
    scene_id = challenge.get("scene_id")

    # Create node
    session.run("""MERGE (ch:Challenge {id: $challenge_id}) ...""")

    # Link to scene if scene_id exists
    if scene_id and scene_id in scene_id_map:
        persisted_scene_id = scene_id_map[scene_id]
        session.run("""
            MATCH (sc:Scene {id: $scene_id})
            MATCH (ch:Challenge {id: $challenge_id})
            MERGE (sc)-[:CONTAINS_CHALLENGE]->(ch)
        """, scene_id=persisted_scene_id, challenge_id=challenge_id)
```

---

## Priority Order

1. **FIX 1** - Populate scene entity IDs during generation (CRITICAL)
2. **FIX 2** - Use original entity IDs in persistence
3. **FIX 3** - Fix MongoDB field names
4. **FIX 4** - Add campaign_id to all entities
5. **FIX 5** - Simplify scene-entity linking logic

---

## Testing After Fixes

1. Generate new campaign
2. Check MongoDB:
   - All entities have proper field values (not "N/A")
   - All entities have `campaign_id` field
   - All entities have `scene_id` field
3. Check Neo4j:
   - All entities have `campaign_id` property
   - All entities have relationships: `(Scene)-[:CONTAINS_X]->(Entity)`
   - No orphaned nodes: `MATCH (n) WHERE NOT (n)--() RETURN count(n)` should be 0
4. Test deletion:
   - Delete campaign
   - Verify all related entities deleted from both databases

---

## Additional Notes

- NPCs are working correctly (they have proper IDs, relationships, and data)
- Knowledge and Items are working correctly
- Rubrics only work for NPCs (same ID mismatch issue for other entity rubrics)
- The world/region/location hierarchy is working correctly
