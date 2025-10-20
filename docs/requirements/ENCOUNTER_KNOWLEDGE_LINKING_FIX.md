# Encounter Knowledge/Item Linking Fix

## Summary

Fixed a critical issue where encounters (Discoveries, Challenges, Events, NPCs) were not properly linked to knowledge and items, preventing quest objective tracking from working correctly.

---

## Problem

When players interacted with encounters in the game:
- ✅ Encounter notifications appeared (toast popups)
- ✅ Encounters were marked as completed
- ❌ **NO knowledge was awarded**
- ❌ **NO items were given**
- ❌ **Quest objectives did NOT update**
- ❌ **Campaign progress did NOT update**

### Root Cause

**Field Name Mismatch + Missing Fields**

1. **Campaign Factory** created entities with `provides_knowledge_ids` and `provides_item_ids`
2. **MongoDB Persistence** did NOT save these fields
3. **Game Engine** looked for `knowledge_revealed` and `items_revealed` fields
4. Result: Empty arrays, no knowledge/items awarded

---

## Entities Fixed

### 1. Discoveries ✅
**Before:** Missing `knowledge_revealed` field
**After:** Saves `knowledge_revealed` from `provides_knowledge_ids`

### 2. Challenges ✅
**Before:** Missing `knowledge_revealed` and `items_revealed` fields
**After:** Saves both fields for success rewards

### 3. Events ✅ **NEW**
**Before:** No knowledge/item support at all
**After:** Full support for `knowledge_revealed` and `items_revealed`

### 4. NPCs ✅ **NEW**
**Before:** No knowledge/item support at all
**After:** Full support for `knowledge_revealed` and `items_revealed`

---

## Files Modified

### 1. Type Definitions
**File:** `services/campaign-factory/workflow/state.py`

**EventData** (lines 152-163):
```python
class EventData(TypedDict):
    # ... existing fields ...
    provides_knowledge_ids: List[str]  # NEW: Knowledge from event
    provides_item_ids: List[str]       # NEW: Items from event
    scene_id: Optional[str]            # NEW: Link to parent scene
```

**NPCData** (lines 86-101):
```python
class NPCData(TypedDict):
    # ... existing fields ...
    provides_knowledge_ids: List[str]  # NEW: Knowledge NPC can teach
    provides_item_ids: List[str]       # NEW: Items NPC can give/sell
```

### 2. Entity Generation
**File:** `services/campaign-factory/workflow/nodes_elements.py`

**Events** (line 607-618):
```python
event: EventData = {
    # ... existing fields ...
    "provides_knowledge_ids": spec.get("provides_knowledge", []),
    "provides_item_ids": spec.get("provides_items", []),
}
```

**File:** `services/campaign-factory/workflow/subgraph_npc.py`

**NPCs** (lines 358-381):
```python
# Extract knowledge/items from npc_role spec if it's a dict
npc_role_data = state.get("npc_role", "neutral")
provides_knowledge = []
provides_items = []
if isinstance(npc_role_data, dict):
    provides_knowledge = npc_role_data.get("provides_knowledge", [])
    provides_items = npc_role_data.get("provides_items", [])

npc: NPCData = {
    # ... existing fields ...
    "provides_knowledge_ids": provides_knowledge,
    "provides_item_ids": provides_items,
}
```

### 3. Database Persistence
**File:** `services/campaign-factory/workflow/db_persistence.py`

**Discoveries** (line 332):
```python
discovery_doc = {
    # ... existing fields ...
    "knowledge_revealed": discovery.get("provides_knowledge_ids", []),
}
```

**Challenges** (lines 385-386):
```python
challenge_doc = {
    # ... existing fields ...
    "knowledge_revealed": challenge.get("provides_knowledge_ids", []),
    "items_revealed": challenge.get("provides_item_ids", []),
}
```

**Events** (lines 358-359):
```python
event_doc = {
    # ... existing fields ...
    "knowledge_revealed": event.get("provides_knowledge_ids", []),
    "items_revealed": event.get("provides_item_ids", []),
}
```

**NPCs** (lines 300-301):
```python
npc_doc = {
    # ... existing fields ...
    "knowledge_revealed": npc.get("provides_knowledge_ids", []),
    "items_revealed": npc.get("provides_item_ids", []),
}
```

---

## How It Works Now

### Discovery Investigation Flow
1. Player: "Investigate Discovery"
2. Game Engine: Loads discovery from MongoDB
3. Game Engine: Reads `knowledge_revealed` field
4. Game Engine: Awards knowledge to player
5. Game Engine: Broadcasts `knowledge_gained` event
6. Frontend: Shows knowledge in Game Information
7. Game Engine: Recalculates quest progress
8. Frontend: Updates Campaign Progress & Quest Progress

### Challenge Completion Flow
1. Player: Attempts challenge
2. Game Engine: Evaluates success/failure
3. On Success: Reads `knowledge_revealed` and `items_revealed`
4. Game Engine: Awards knowledge/items to player
5. Game Engine: Broadcasts events
6. Frontend: Updates all progress tracking

### Event Participation Flow (NEW)
1. Player: Participates in event
2. Game Engine: Reads `knowledge_revealed` and `items_revealed`
3. Game Engine: Awards knowledge/items
4. Quest objectives update accordingly

### NPC Conversation Flow (NEW)
1. Player: Talks to NPC
2. Game Engine: Checks NPC's `knowledge_revealed` and `items_revealed`
3. Based on conversation: Awards knowledge/items
4. Quest objectives update accordingly

---

## Testing

### IMPORTANT: You MUST Create a New Campaign

**This fix applies to NEW campaigns only!**

Existing campaigns were created before the fix and have empty `knowledge_revealed` fields in the database.

**Steps to Test:**
1. Go to http://localhost:8000/campaigns/
2. Click **"+ Create New Campaign"** button
3. Complete the Campaign Wizard
4. Wait for campaign generation to finish
5. Start a game with the NEW campaign
6. Interact with encounters (investigate discoveries, attempt challenges, talk to NPCs, participate in events)
7. Verify:
   - ✅ Knowledge appears in Game Information
   - ✅ Items appear in inventory
   - ✅ Quest Progress updates
   - ✅ Campaign Progress updates

### Test Cases

**Test 1: Discovery Investigation**
- Action: Investigate a discovery
- Expected: Knowledge gained, quest objective updates
- Verify in: Game Information panel, Quest Progress sidebar

**Test 2: Challenge Completion**
- Action: Successfully complete a challenge
- Expected: Knowledge/items gained, objectives update
- Verify in: Game Information, Inventory, Quest Progress

**Test 3: NPC Conversation**
- Action: Talk to an NPC who teaches knowledge
- Expected: Knowledge gained after conversation
- Verify in: Game Information panel

**Test 4: Event Participation**
- Action: Participate in a dynamic event
- Expected: Knowledge/items from event outcome
- Verify in: Game Information, Inventory

---

## Benefits

1. **Quest Objective Tracking Works** - All encounter types can now contribute to objectives
2. **Campaign Progress Accurate** - Progress bars update when encounters are completed
3. **Complete Experience** - Every encounter type (NPC, Discovery, Challenge, Event) can provide rewards
4. **Scalable** - System can track progress from any source

---

## Migration Notes

**For Existing Campaigns:**

Option 1: **Create a new campaign** (Recommended)

Option 2: **Run patch script** to fix existing campaign:
```bash
cd D:\Dev\skill-forge
python patch_discovery_knowledge_links.py
```

Note: The patch script only fixes Discoveries. Challenges, Events, and NPCs in existing campaigns will still need the knowledge links added manually or via a similar script.

---

## Architecture Improvement

**Before:**
```
Campaign Factory ──> MongoDB
  creates with:        saves as:
  provides_knowledge_ids  (MISSING - not saved!)

Game Engine ──> MongoDB
  looks for:      finds:
  knowledge_revealed  (EMPTY - doesn't exist!)
```

**After:**
```
Campaign Factory ──> MongoDB
  creates with:        saves as:
  provides_knowledge_ids  knowledge_revealed ✓
  provides_item_ids       items_revealed ✓

Game Engine ──> MongoDB
  looks for:      finds:
  knowledge_revealed  [knowledge_ids] ✓
  items_revealed      [item_ids] ✓
```

---

## Service Restarted

✅ `skillforge-campaign-factory` - Restarted with all fixes

---

## Status

✅ **COMPLETE - Ready for Testing**

Create a new campaign to test the fixes!
