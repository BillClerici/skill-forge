# Campaign Design Wizard UI Updates - Objective Cascade Integration

## Question: Does the UI need updating for the new objective cascade changes?

**Answer: YES - Several updates are needed to expose the new objective cascade functionality.**

---

## Current UI State (V2 Wizard)

### What's Currently Shown:

**Step 6: Campaign Core Review**
- ✅ Campaign name, plot, storyline
- ✅ **Primary objectives** (3-5 high-level)
- ✅ Bloom's taxonomy levels
- ❌ No objective decomposition preview
- ❌ No success criteria shown

**Step 8: Quest Review**
- ✅ Quest name, description, backstory
- ✅ **Quest objectives** (2-4 per quest)
- ✅ Difficulty, duration, order
- ❌ No linkage to campaign objectives shown
- ❌ No knowledge/item requirements shown
- ❌ No structured objectives from `objective_system.py`

**Step 10: Scene Review**
- ✅ Scene name, description
- ✅ NPCs, discoveries listed
- ❌ No objective assignments shown
- ❌ No "what this scene accomplishes" information
- ❌ No knowledge/items provided by scene

**Step 11: Final Review**
- ✅ Summary counts (quests, places, scenes, NPCs, etc.)
- ❌ No objective cascade validation results
- ❌ No coverage statistics
- ❌ No warning about missing links

---

## NEW FEATURES TO EXPOSE IN UI

### 1. **Step 6.5 (NEW): Objective Decomposition Preview** 🆕

**After** user approves campaign core, **before** narrative planning:

```
┌─────────────────────────────────────────────────────────┐
│ Step 6.5: Objective Decomposition                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Breaking down your campaign objectives into quest       │
│ objectives...                                            │
│                                                          │
│ Campaign Objective: "Discover the source of corruption" │
│   ├─ Quest 1: "Investigate abandoned mine"              │
│   │   • Success Criteria:                               │
│   │     - Find 3 clues about contamination              │
│   │     - Collect 2 water samples                       │
│   │   • Requires Knowledge: Mining Safety, Chem Analysis│
│   │   • Requires Items: Sample Collection Kit          │
│   │                                                      │
│   ├─ Quest 2: "Analyze contaminated samples"            │
│   │   • Success Criteria:                               │
│   │     - Complete lab analysis                         │
│   │     - Identify contaminant source                   │
│   │   • Requires Knowledge: Chemical Analysis (Level 3) │
│   │   • Requires Items: Lab Equipment                   │
│   │                                                      │
│   └─ Quest 3: "Confront the corrupt official"           │
│       • Success Criteria:                               │
│         - Gather evidence                               │
│         - Present case to authorities                   │
│       • Requires Knowledge: Negotiation, Legal Procedure│
│       • Requires Items: Evidence Documents              │
│                                                          │
│ [✓ Decomposition Complete] [Continue to Narrative Plan] │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
- Add new step in wizard after core approval
- Display results from `state.objective_decompositions`
- Show expandable/collapsible objective tree
- Non-editable (informational only)

---

### 2. **Step 8: Enhanced Quest Review** (UPDATE)

**Add objective linkage information:**

```
┌─────────────────────────────────────────────────────────┐
│ Quest 1: The Abandoned Mine                              │
├─────────────────────────────────────────────────────────┤
│ Description: Investigate the mysterious...               │
│                                                          │
│ 🎯 Supports Campaign Objectives:                         │
│   • "Discover source of corruption" (Primary)           │
│                                                          │
│ ✓ Quest Objectives:                                      │
│   1. Investigate the flooded shaft                      │
│      └─ Supports: Campaign Objective 1                  │
│   2. Collect contaminated samples                       │
│      └─ Supports: Campaign Objective 1                  │
│                                                          │
│ 📚 Required Knowledge Domains:                           │
│   • Mining Safety (Level 2)                             │
│   • Chemical Analysis (Level 1)                         │
│                                                          │
│ 🎒 Required Item Categories:                             │
│   • Investigation Tools                                 │
│   • Sample Collection Equipment                          │
│                                                          │
│ [View Scenes] [Approve Quest]                           │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
- Read from `state.objective_progress` to get linkages
- Display knowledge/item requirements from structured_objectives
- Add "Supports Campaign Objectives" section
- Color-code objectives by campaign objective

---

### 3. **Step 10: Enhanced Scene Review** (UPDATE)

**Add scene objective assignments:**

```
┌─────────────────────────────────────────────────────────┐
│ Scene: The Flooded Shaft                                 │
├─────────────────────────────────────────────────────────┤
│ Location: Level 3 → Abandoned Mine Entrance              │
│                                                          │
│ 🎯 This scene advances:                                  │
│   ✓ Quest Objective: "Investigate the flooded shaft"   │
│   ✓ Campaign Objective: "Discover source of corruption"│
│                                                          │
│ 📚 Knowledge Provided:                                   │
│   • Mining Safety (via 3 encounters)                    │
│     - NPC: Old Miner (Level 2)                          │
│     - Discovery: Ancient Manual (Level 3)               │
│     - Challenge: Navigate Collapse (Level 2 required)   │
│                                                          │
│ 🎒 Items Provided:                                       │
│   • Sample Collection Kit (via 2 encounters)            │
│     - NPC: Equipment Vendor                             │
│     - Challenge: Navigate Collapse (reward)             │
│                                                          │
│ ⚠️ Required to Complete: YES                             │
│                                                          │
│ NPCs: Old Miner, Equipment Vendor                       │
│ Discoveries: Ancient Manual, Warning Signs               │
│ Challenges: Navigate Collapse                           │
│                                                          │
│ [View Details] [Approve Scene]                          │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
- Read from `state.scene_objective_assignments`
- Display quest/campaign objectives this scene advances
- Show knowledge/items provided with acquisition method counts
- Highlight if scene is required for quest completion

---

### 4. **Step 11: Add Validation Results Tab** 🆕

**Add validation report to final review:**

```
┌─────────────────────────────────────────────────────────┐
│ Step 11: Final Review & Validation                       │
├─────────────────────────────────────────────────────────┤
│ [Summary] [Validation] [Resources] [Timeline]           │
│                                                          │
│ ═══════════════════════════════════════════════════════ │
│ VALIDATION TAB:                                          │
│ ═══════════════════════════════════════════════════════ │
│                                                          │
│ ✅ Objective Cascade Validation: PASSED                 │
│                                                          │
│ Coverage Statistics:                                     │
│   ✅ 3/3 campaign objectives fully covered              │
│   ✅ 8/8 quest objectives addressable in 2+ scenes      │
│   ✅ 15/15 knowledge items have acquisition methods     │
│   ⚠️  2/12 items have only 1 acquisition path           │
│                                                          │
│ ⚠️ Warnings (2):                                         │
│   • "Sample Collection Kit" has only 1 acquisition path │
│     Recommendation: Add alternative in Scene 5          │
│   • "Lab Equipment" has only 1 acquisition path         │
│     Recommendation: Add NPC vendor in Scene 8           │
│                                                          │
│ Redundancy Check:                                        │
│   ✅ 12/12 critical knowledge items have 2-3 paths      │
│   ⚠️  10/12 critical items have 2-3 paths               │
│                                                          │
│ ℹ️ All warnings are non-critical. Campaign can proceed.│
│                                                          │
│ [View Details] [Finalize Campaign]                      │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
- Read from `state.validation_report`
- Display statistics in dashboard format
- Show errors (red), warnings (yellow), success (green)
- Expandable sections for each validation category
- Block finalization if errors exist
- Allow finalization with warnings (after confirmation)

---

### 5. **Add Progress Phase: "Objective Decomposition"** 🆕

**Update progress tracking UI:**

Current phases:
```
Story Ideas → Campaign Core → Quests → Places → Scenes → NPCs → Finalization
```

New phases:
```
Story Ideas → Campaign Core → 🆕 Objectives → Narrative Plan → Quests →
Places → Scenes → 🆕 Scene Assignments → NPCs → 🆕 Validation → Finalization
```

**Implementation in `campaign_wizard_v2.js`:**
```javascript
const phaseOrder = [
    'story_gen',
    'core_gen',
    'objective_decomp',  // NEW
    'narrative_plan',    // NEW
    'quest_gen',
    'place_gen',
    'scene_gen',
    'scene_assignment',  // NEW
    'element_gen',
    'validation',        // NEW
    'finalize'
];
```

---

## UI Components Needed

### New Vue/JavaScript Components:

1. **`ObjectiveDecompositionCard.vue`** - Display objective tree
2. **`ValidationDashboard.vue`** - Display validation results
3. **`ObjectiveLinkageBadge.vue`** - Show campaign ← quest ← scene links
4. **`KnowledgeProvidersList.vue`** - Show acquisition methods
5. **`RedundancyIndicator.vue`** - Visual indicator of redundancy (1/2/3+ paths)

### Updated Components:

1. **`QuestCard.vue`** - Add objective linkage section
2. **`SceneCard.vue`** - Add scene objective assignment section
3. **`ProgressModal.vue`** - Add new phases

---

## API Endpoint Updates Needed

### Current V2 API (wizard_views_v2.py):

```python
# EXISTING:
✅ POST /campaigns/wizard/api/generate-stories
✅ POST /campaigns/wizard/api/generate-core
✅ POST /campaigns/wizard/api/approve-core  # Triggers workflow
✅ GET  /campaigns/wizard/api/status/<request_id>
✅ POST /campaigns/wizard/api/finalize
```

### NEW ENDPOINTS NEEDED:

```python
# Add to wizard_views_v2.py:

🆕 GET /campaigns/wizard/api/objective-decomposition/<request_id>
   # Returns: state.objective_decompositions
   # Use case: Step 6.5 objective decomposition preview

🆕 GET /campaigns/wizard/api/scene-assignments/<request_id>
   # Returns: state.scene_objective_assignments
   # Use case: Step 10 scene objective display

🆕 GET /campaigns/wizard/api/validation-report/<request_id>
   # Returns: state.validation_report
   # Use case: Step 11 validation tab

🆕 POST /campaigns/wizard/api/retry-validation/<request_id>
   # Triggers: Re-run validation after auto-fixes
   # Use case: If user wants to re-validate after changes
```

---

## Implementation Priority

### Phase 1 (MVP - Essential):
1. ✅ Add objective decomposition preview (Step 6.5)
2. ✅ Show validation results in final review (Step 11)
3. ✅ Add new API endpoints
4. ✅ Update progress phase tracking

### Phase 2 (Enhanced UX):
1. 🔄 Enhanced quest review with objective linkage
2. 🔄 Enhanced scene review with assignments
3. 🔄 Visual objective tree/graph

### Phase 3 (Advanced Features):
1. 🔮 Interactive objective editing
2. 🔮 Validation auto-fix UI (one-click fixes)
3. 🔮 Objective-first mode toggle in wizard

---

## Mockup: Validation Dashboard (Step 11)

```html
<div class="validation-dashboard">
  <div class="validation-header">
    <i class="material-icons green-text">check_circle</i>
    <h5>Objective Cascade Validation: PASSED</h5>
  </div>

  <div class="validation-stats row">
    <div class="col s3">
      <div class="stat-card">
        <span class="stat-number green-text">3/3</span>
        <span class="stat-label">Campaign Objectives Covered</span>
      </div>
    </div>
    <div class="col s3">
      <div class="stat-card">
        <span class="stat-number green-text">8/8</span>
        <span class="stat-label">Quest Objectives Addressable</span>
      </div>
    </div>
    <div class="col s3">
      <div class="stat-card">
        <span class="stat-number green-text">15/15</span>
        <span class="stat-label">Knowledge Acquirable</span>
      </div>
    </div>
    <div class="col s3">
      <div class="stat-card">
        <span class="stat-number yellow-text">10/12</span>
        <span class="stat-label">Items with Redundancy</span>
      </div>
    </div>
  </div>

  <div class="warnings-section" v-if="warnings.length > 0">
    <h6><i class="material-icons yellow-text">warning</i> Warnings ({{warnings.length}})</h6>
    <ul class="collection">
      <li class="collection-item" v-for="warning in warnings">
        <i class="material-icons yellow-text">warning</i>
        {{warning.message}}
        <div class="secondary-content">
          <span class="badge yellow white-text">{{warning.severity}}</span>
        </div>
        <div class="recommendation">
          <strong>Recommendation:</strong> {{warning.recommendations[0]}}
        </div>
      </li>
    </ul>
  </div>
</div>
```

---

## Summary

**YES, the UI needs significant updates to expose the new objective cascade features:**

1. ✅ Add Step 6.5 for objective decomposition preview
2. ✅ Enhance Quest Review (Step 8) with objective linkage
3. ✅ Enhance Scene Review (Step 10) with assignments
4. ✅ Add Validation tab to Final Review (Step 11)
5. ✅ Update progress tracking with new phases
6. ✅ Create 3 new API endpoints
7. ✅ Update JavaScript controller for new workflow

**Estimated Effort:**
- Backend API endpoints: 4-6 hours
- Frontend components: 8-12 hours
- JavaScript controller updates: 4-6 hours
- Testing & refinement: 4-6 hours
**Total: 20-30 hours** for full implementation

**Benefit:**
Users will be able to SEE and UNDERSTAND how objectives cascade through their campaign, validate completeness, and get actionable feedback before finalization.
