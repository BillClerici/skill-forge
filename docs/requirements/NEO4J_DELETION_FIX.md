# Neo4j Campaign Deletion Fix

## Summary

Fixed the Neo4j campaign deletion bug that was leaving orphaned nodes in the database after campaign deletion.

---

## Problem

When deleting a campaign from http://localhost:8000/campaigns/, the Neo4j deletion was NOT working:
- Campaign deletion completed in MongoDB
- But dozens of nodes remained in Neo4j
- Neo4j browser showed orphaned Quest, Discovery, Challenge, Event, NPC, Knowledge, Item nodes

### Root Cause

**ID Pattern Matching Bug**

The deletion code was trying to find nodes using ID pattern matching:
```cypher
MATCH (d:Discovery)
WHERE d.id STARTS WITH 'discovery_' AND d.id CONTAINS $campaign_id
DETACH DELETE d
```

**Problem:** Entity IDs are UUIDs that DON'T contain the campaign ID!
- Example entity ID: `discovery_c884a6c9519c455c`
- Campaign ID: `campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6`
- The UUID doesn't contain the campaign ID, so the query found 0 nodes

---

## Solution

**Property-Based Matching**

Changed all Neo4j deletion queries to use the `campaign_id` property:
```cypher
MATCH (d:Discovery)
WHERE d.campaign_id = $campaign_id
DETACH DELETE d
```

This works because every entity node has a `campaign_id` property linking it to its campaign.

---

## Files Modified

### D:\Dev\skill-forge\services\campaign-factory\workflow\campaign_deletion_workflow.py

Updated `delete_neo4j_entities_node()` function (lines 299-485)

**Changed deletion queries for ALL entity types:**
1. Quest nodes (line 317)
2. Place nodes (line 328)
3. Scene nodes (line 339)
4. NPC nodes (line 350)
5. Challenge nodes (line 361)
6. Discovery nodes (line 372)
7. Event nodes (line 383)
8. Knowledge nodes (line 394)
9. Item nodes (line 405)
10. Rubric nodes (line 416)

**Before (BROKEN):**
```cypher
WHERE d.id STARTS WITH 'discovery_' AND d.id CONTAINS $campaign_id
```

**After (FIXED):**
```cypher
WHERE d.campaign_id = $campaign_id
```

---

## Service Restarted

Campaign Factory service has been restarted with the fix applied.

The service is now listening and ready to process campaign deletions correctly.

---

## Testing Instructions

### Step 1: Delete the Old Campaign

Go to http://localhost:8000/campaigns/campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6/

Click the "Delete Campaign" button.

The Neo4j deletion should now work correctly and remove ALL nodes.

### Step 2: Verify Neo4j Cleanup

Open Neo4j Browser: http://localhost:7474

Run this query to verify no orphaned nodes remain:
```cypher
MATCH (n)
WHERE n.campaign_id = 'campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6'
RETURN count(n) as remaining_nodes
```

Expected result: `remaining_nodes = 0`

### Step 3: Create New Campaign

Go to http://localhost:8000/campaigns/

Click "+ Create New Campaign" button

Complete the Campaign Wizard

Wait for generation to complete

### Step 4: Test Knowledge/Item Linking

Start a new game with the new campaign

Test these interactions:
1. **Discovery Investigation** - Investigate a discovery, verify knowledge appears in Game Information
2. **Challenge Completion** - Complete a challenge, verify knowledge/items awarded
3. **NPC Conversation** - Talk to an NPC, check for knowledge rewards
4. **Event Participation** - Participate in an event, check for knowledge/items

**Verify:**
- Knowledge appears in Game Information panel
- Items appear in inventory
- Quest Progress updates
- Campaign Progress updates

---

## Benefits

1. **Complete Deletion** - Campaign deletion now removes ALL nodes from Neo4j
2. **No Orphaned Data** - Database stays clean, no leftover campaign data
3. **Proper Testing** - Can now create fresh campaigns to test knowledge/item linking fixes

---

## Related Fixes

This Neo4j deletion fix works together with the knowledge/item linking fixes:
- See ENCOUNTER_KNOWLEDGE_LINKING_FIX.md for details on the knowledge linking fixes
- Both fixes require creating a NEW campaign to take effect

---

## Status

COMPLETE - Ready for testing

Delete the old campaign, create a new one, and test all the fixes together!
