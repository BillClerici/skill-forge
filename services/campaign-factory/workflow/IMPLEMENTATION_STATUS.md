# Objective Cascade Refactoring - Implementation Status

## Completed ✅

### 1. State Extensions (Fix #4)
- ✅ Added `ObjectiveProgress` TypedDict for tracking objective completion
- ✅ Added `ObjectiveDecomposition` TypedDict for campaign → quest mapping
- ✅ Added `SceneObjectiveAssignment` TypedDict for scene → objective linking
- ✅ Added `ValidationReport` TypedDict for cascade validation results
- ✅ Extended `CampaignWorkflowState` with new fields:
  - `objective_progress: List[ObjectiveProgress]`
  - `objective_decompositions: List[ObjectiveDecomposition]`
  - `scene_objective_assignments: List[SceneObjectiveAssignment]`
  - `validation_report: Optional[ValidationReport]`
  - `generation_mode: str` (for objective-first vs narrative-first)

### 2. Objective Decomposition Node (Fix #1)
- ✅ Created `nodes_objective_decomposition.py`
- ✅ Implements `decompose_campaign_objectives_node()`
- ✅ AI-powered decomposition of campaign objectives into quest objectives
- ✅ Creates tracking structures for all objectives
- ✅ Identifies knowledge domains and item categories needed
- ✅ Defines success criteria for each objective level

### 3. Narrative Planner Enhancement (Fix #2)
- ✅ Updated `nodes_narrative_planner.py`
- ✅ Enhanced prompt to require objective awareness for each scene
- ✅ Added quest objectives breakdown to narrative planning context
- ✅ Updated scene JSON structure to include:
  - `supports_quest_objectives: List[str]`
  - `provides_knowledge_domains: List[str]`
  - `provides_item_categories: List[str]`
  - `is_required_for_quest_completion: bool`
- ✅ Requires redundancy: every objective addressable in 2+ scenes

### 4. Validation Node (Fix #5)
- ✅ Created `nodes_validation.py`
- ✅ Implements `validate_objective_cascade_node()`
- ✅ Comprehensive validation:
  - Campaign → Quest objective coverage
  - Quest → Scene assignments
  - Scene encounters → Knowledge/Item provision
  - Redundancy requirements (2-3 paths)
  - Completion criteria existence
- ✅ Generates auto-fix suggestions
- ✅ Creates detailed ValidationReport

## In Progress 🚧

### 5. Elements Node Update (Fix #3)
**Status:** Next to implement

**Required Changes:**
1. Update `determine_scene_elements()` in `nodes_elements.py` to:
   - Use actual objective mapping from `objective_system.py`
   - Pull from `scene_objective_assignments` to know what scene should provide
   - Assign knowledge/items based on objective requirements

2. Remove the TODO comment at line 272-273:
   ```python
   # Simple check: if knowledge name appears in scene description or is generic
   # In a real system, this would use the mapping from objective_system
   ```

3. Use `map_knowledge_to_scenes()` and `map_items_to_scenes()` properly

## Remaining 📋

### 6. Objective System Enhancements
**File:** `objective_system.py`

**Required Changes:**
1. Fix `map_knowledge_to_scenes()` to actually use scene_objective_assignments
2. Fix `map_items_to_scenes()` to actually use scene_objective_assignments
3. Add function to populate `scene_objective_assignments` after scene generation

### 7. Scene Objective Assignment Generation
**New Node Needed:** `generate_scene_assignments_node()`

**Purpose:**
- Run AFTER scene generation
- Create `SceneObjectiveAssignment` for each scene
- Based on narrative blueprint's `supports_quest_objectives` field
- Assign knowledge/items to scenes based on objective decomposition

### 8. Workflow Integration
**File:** `campaign_workflow.py`

**Required Changes:**
1. Add new nodes to workflow graph:
   - `decompose_campaign_objectives_node` (after core generation)
   - `generate_scene_assignments_node` (after scene generation)
   - `validate_objective_cascade_node` (after element generation, before finalization)

2. Update workflow edges to support new flow:
   ```
   campaign_core → objective_decomp → narrative_plan → quests → places → scenes
   → scene_assignments → elements → validation → finalization
   ```

### 9. Objective-First Generation Mode
**New Workflow Variant**

**Purpose:**
- Alternative to narrative-first mode
- Starts with objectives, generates content to support them
- More structured, less creative but better aligned

**Flow:**
```
1. Core generation
2. Objective decomposition
3. Knowledge/Item definition (before narrative)
4. Scene requirement calculation
5. Narrative generation to fill requirements
6. Quest/Place/Scene generation
7. Element generation (targeted)
8. Validation
9. Finalization
```

## Integration Plan

### Phase 1: Complete Current Fixes (Next Steps)
1. ✅ Update `nodes_elements.py` (Fix #3)
2. ✅ Update `objective_system.py` mapping functions
3. ✅ Create `generate_scene_assignments_node()`

### Phase 2: Workflow Integration
1. Update `campaign_workflow.py` with new nodes
2. Test with existing campaigns
3. Verify validation catches issues

### Phase 3: Objective-First Mode
1. Create `campaign_workflow_objective_first.py`
2. Create variant nodes for objective-first approach
3. Add mode selection to wizard

## Testing Plan

### Test Cases Needed:
1. **Campaign with all objectives covered** → Should pass validation
2. **Campaign with missing scene assignments** → Should fail validation with errors
3. **Campaign with single-path knowledge** → Should warn about redundancy
4. **Objective-first mode** → Should generate complete, validated campaign

### Manual Test:
Create a small 2-quest campaign and verify:
- ✅ Objectives decompose correctly
- ✅ Narrative blueprint includes objective tags
- ✅ Scenes have objective assignments
- ✅ Elements provide required knowledge/items
- ✅ Validation passes
- ✅ Player can complete all objectives through gameplay

## Known Issues & TODOs

1. **Character Profile Integration:** Currently hardcoded target dimensions in `determine_scene_elements()` - needs MCP integration
2. **Auto-Fix Implementation:** `apply_auto_fixes_node()` is a placeholder - needs full implementation
3. **Rubric Integration:** Rubrics are generated but not fully integrated with objective completion tracking
4. **Progress Tracking:** Need runtime state management to track `ObjectiveProgress` during gameplay

## Documentation Needed

1. Developer guide for objective cascade system
2. Campaign designer guide (how to use new features)
3. API documentation for validation endpoint
4. Migration guide for existing campaigns
