# Campaign Designer Wizard - Gap Analysis & Implementation Plan

## Current Implementation vs Requirements

### ✅ What's Already Implemented

#### Current Wizard Flow (campaign_designer_wizard.html):
1. **Step 1: Campaign Name & Genre** - User enters name and selects genre
2. **Step 2: World Selection** - User selects from available worlds (filtered by genre)
3. **Step 3: Region Selection** - User selects region (optional)
4. **Step 4: Story Outline** - User provides story description
5. **Step 5: Quest Configuration** - User selects number of quests (3-10)
6. **Step 6: Review & Generate** - Review and submit

#### Current Workflow (campaign_workflow.py):
- Story idea generation (3 options)
- Story selection with regeneration support
- Campaign core generation (plot, storyline, objectives)
- Core approval gate
- Quest generation
- Place generation (Level 2 locations)
- Scene generation (Level 3 locations)
- Element generation (NPCs, discoveries, events, challenges)
- Finalization and persistence

### ❌ Gaps Between Current Implementation and Requirements

#### Major Gaps:

| Requirement | Current Implementation | Gap |
|------------|------------------------|-----|
| **1. Universe Selection** | Starts with Genre selection | Missing Universe selection as first step |
| **2. World Display with Genre** | Shows worlds filtered by genre | Should show all worlds in selected Universe with their genre |
| **3. Story Idea Input** | Single text field for story outline (required) | Should be **optional** multi-row text box for campaign story idea |
| **4. Generate Campaign Ideas Button** | Auto-generates on submit | Missing dedicated "Generate Campaign Ideas" button |
| **5. Show 3 Story Ideas** | Backend workflow supports this | Frontend doesn't display 3 AI-generated story ideas for selection |
| **6. Story Selection UI** | Missing in wizard | User should see 3 stories, select one, modify idea, or regenerate |
| **7. Campaign Core Display** | Missing in wizard | After story selection, should display Plot, Storyline, Primary Objectives |
| **8. Campaign Settings Modification** | No modification UI | User should be able to modify campaign settings before continuing |
| **9. Quest Settings UI** | Basic slider for quest count | Missing difficulty level selector, estimated play time per quest |
| **10. Quest Review Gate** | No review step | User should review quests before generating Places |
| **11. Place Review Gate** | No review step | User should review places/scenes before generating next level |
| **12. Scene Review Gate** | No review step | User should review scenes before generating elements |
| **13. Backstory Generation** | Not in wizard flow | Should generate backstory at each level (Campaign, Quest, Location, Place, Scene) |
| **14. Image Generation Option** | Simple boolean | Should ask at each level: "Generate images now or later?" |
| **15. Bloom's Taxonomy Display** | Mentioned in info text | Should prominently show Bloom's capabilities at campaign level |
| **16. Location Hierarchy Management** | Backend creates locations | If suitable Level 1/2/3 location doesn't exist, should create new one via World Factory |
| **17. Knowledge & Items** | Backend has discovery system | Should explicitly show Knowledge and Items being generated |
| **18. Sequential Quest Building** | Not explicitly shown | Quests should build on each other in UI |
| **19. Non-sequential Scenes** | Not shown | UI should indicate scenes can be done in any order |
| **20. Multi-step Generation Progress** | Generic loading overlay | Should show which level is being generated (Campaign → Quest → Place → Scene) |

---

## Implementation Plan

### Phase 1: Update Wizard UI Flow (HIGH PRIORITY)

#### 1.1 Restructure Wizard Steps

**New Step Flow:**
1. **Universe Selection** (NEW)
2. **World Selection** (Display with Genre)
3. **Region Selection** (Keep existing)
4. **Story Idea Input** (Make optional, add multi-row text box)
5. **Generate & Select Story** (NEW - Show 3 AI ideas)
6. **Campaign Core Review** (NEW - Show Plot, Storyline, Objectives)
7. **Quest Settings** (Enhance with difficulty, playtime)
8. **Quest Review** (NEW)
9. **Place Review** (NEW)
10. **Scene Review** (NEW)
11. **Image Generation Options** (NEW - Per level)
12. **Final Review & Generate**

**Files to modify:**
- `services/django-web/templates/campaigns/campaign_designer_wizard.html`
- `services/django-web/campaigns/views.py` (CampaignDesignerWizardView)

#### 1.2 Add Universe Selection Step

```html
<!-- Step 1: Universe Selection -->
<div class="wizard-step" data-step="1">
    <span class="card-title">Select Universe</span>
    <div id="universe-list">
        {% for universe in universes %}
        <label class="universe-card">
            <input type="radio" name="universe_id" value="{{ universe.id }}" required>
            <div class="universe-content">
                <h6>{{ universe.name }}</h6>
                <p>{{ universe.description }}</p>
            </div>
        </label>
        {% endfor %}
    </div>
</div>
```

**Backend changes:**
- `views.py`: Fetch universes from MongoDB
- Add AJAX endpoint to fetch worlds for selected universe

#### 1.3 Update World Selection Step

**Change from:**
- Filter by genre

**Change to:**
- Show all worlds in selected universe
- Display genre as metadata for each world

```html
<!-- Display genre chip for each world -->
<span class="chip">{{ world.genre }}</span>
```

#### 1.4 Make Story Idea Optional & Multi-row

**Current:**
```html
<textarea id="story_outline" name="story_outline" required></textarea>
```

**New:**
```html
<textarea id="story_outline" name="story_outline"
    rows="6"
    placeholder="Optional: Describe your campaign story idea. The AI will generate ideas based on your world and genre context if you leave this blank.">
</textarea>
```

Remove `required` attribute.

#### 1.5 Add "Generate Campaign Ideas" Step

**New Step 4a: Story Idea Generation**

```html
<div class="wizard-step" data-step="4a">
    <h5>Your Story Ideas</h5>
    <p>Review these AI-generated story ideas or modify your input to regenerate.</p>

    <div id="story-ideas-container">
        <!-- Populated via JavaScript from backend -->
    </div>

    <div class="action-buttons">
        <button type="button" id="modify-story-btn">Modify Story Idea & Regenerate</button>
        <button type="button" id="regenerate-btn">Regenerate 3 New Ideas</button>
    </div>
</div>
```

**JavaScript to handle:**
- Call backend API to generate 3 story ideas
- Display ideas in cards
- Handle selection
- Handle regeneration

#### 1.6 Add Campaign Core Review Step

**New Step 5: Campaign Core Review**

```html
<div class="wizard-step" data-step="5">
    <h5>Campaign Core</h5>

    <div class="campaign-core-display">
        <div class="section">
            <strong>Plot:</strong>
            <p id="core-plot"></p>
            <button type="button" class="btn-small edit-plot">Edit</button>
        </div>

        <div class="section">
            <strong>Storyline:</strong>
            <p id="core-storyline"></p>
            <button type="button" class="btn-small edit-storyline">Edit</button>
        </div>

        <div class="section">
            <strong>Primary Objectives:</strong>
            <ul id="core-objectives"></ul>
            <button type="button" class="btn-small edit-objectives">Edit</button>
        </div>
    </div>

    <p class="info">Review and modify campaign settings before continuing to quest generation.</p>
</div>
```

#### 1.7 Enhance Quest Settings

**Update Step to include:**

```html
<div class="input-field">
    <label for="num_quests">Number of Quests</label>
    <input type="range" id="num_quests" name="num_quests" min="3" max="10" value="5">
    <span id="quest-count-display">5</span>
</div>

<div class="input-field">
    <label for="quest_difficulty">Difficulty Level</label>
    <select id="quest_difficulty" name="quest_difficulty">
        <option value="Easy">Easy</option>
        <option value="Medium" selected>Medium</option>
        <option value="Hard">Hard</option>
        <option value="Expert">Expert</option>
    </select>
</div>

<div class="input-field">
    <label for="quest_playtime_minutes">Estimated Play Time (per quest, in minutes)</label>
    <input type="number" id="quest_playtime_minutes" name="quest_playtime_minutes" value="90" min="15" max="480" step="15">
</div>
```

#### 1.8 Add Quest Review Step

**New Step 7: Quest Review**

```html
<div class="wizard-step" data-step="7">
    <h5>Quest Review</h5>
    <p>Review generated quests before continuing to Place and Scene generation.</p>

    <div id="quest-list-review">
        <!-- Populated dynamically -->
    </div>

    <div class="action-buttons">
        <button type="button" id="regenerate-quests">Regenerate Quests</button>
        <button type="button" id="continue-to-places">Continue to Places</button>
    </div>
</div>
```

#### 1.9 Add Place Review Step

**New Step 8: Place Review**

```html
<div class="wizard-step" data-step="8">
    <h5>Place Review</h5>
    <p>Review Places (Level 2 Locations) associated with each Quest.</p>

    <div id="place-list-review">
        <!-- Populated dynamically -->
    </div>

    <div class="action-buttons">
        <button type="button" id="continue-to-scenes">Continue to Scenes</button>
    </div>
</div>
```

#### 1.10 Add Scene Review Step

**New Step 9: Scene Review**

```html
<div class="wizard-step" data-step="9">
    <h5>Scene Review</h5>
    <p>Review Scenes (Level 3 Locations) associated with each Place.</p>

    <div id="scene-list-review">
        <!-- Populated dynamically -->
    </div>

    <div class="action-buttons">
        <button type="button" id="continue-to-elements">Continue to Elements & Finalize</button>
    </div>
</div>
```

#### 1.11 Add Image Generation Options

**At each review step, add:**

```html
<div class="image-generation-option">
    <p>
        <label>
            <input type="checkbox" name="generate_images_campaign" checked>
            <span>Generate images for this campaign level</span>
        </label>
    </p>
    <p class="info">You can always generate images later from the campaign detail page.</p>
</div>
```

#### 1.12 Enhanced Progress Tracking

**Update loading overlay to show granular progress:**

```html
<div id="loading-overlay">
    <div class="progress-steps">
        <div class="step" data-phase="campaign_core">
            <i class="material-icons">check_circle</i>
            <span>Campaign Core</span>
        </div>
        <div class="step active" data-phase="quests">
            <div class="spinner"></div>
            <span>Generating Quests</span>
        </div>
        <div class="step pending" data-phase="places">
            <i class="material-icons">radio_button_unchecked</i>
            <span>Places</span>
        </div>
        <div class="step pending" data-phase="scenes">
            <i class="material-icons">radio_button_unchecked</i>
            <span>Scenes</span>
        </div>
        <div class="step pending" data-phase="elements">
            <i class="material-icons">radio_button_unchecked</i>
            <span>Elements</span>
        </div>
    </div>
    <p id="status-message">Generating Quest 2 of 5...</p>
</div>
```

---

### Phase 2: Update Backend Workflow Integration (HIGH PRIORITY)

#### 2.1 Create New Wizard Views

**Files to create/modify:**

**File:** `services/django-web/campaigns/wizard_views.py`

**New endpoints:**
- `GET /campaigns/wizard/start` - Step 1: Universe selection
- `GET /campaigns/wizard/api/universes` - AJAX: Fetch universes
- `GET /campaigns/wizard/api/worlds/<universe_id>` - AJAX: Fetch worlds for universe
- `POST /campaigns/wizard/generate-stories` - Generate 3 story ideas
- `GET /campaigns/wizard/api/stories/<request_id>` - Poll for story ideas
- `POST /campaigns/wizard/select-story` - User selects story
- `POST /campaigns/wizard/regenerate-stories` - Regenerate stories
- `GET /campaigns/wizard/api/campaign-core/<request_id>` - Get generated core
- `POST /campaigns/wizard/approve-core` - Approve campaign core with modifications
- `GET /campaigns/wizard/api/quests/<request_id>` - Get generated quests
- `POST /campaigns/wizard/approve-quests` - Approve quests, continue to places
- `GET /campaigns/wizard/api/places/<request_id>` - Get generated places
- `POST /campaigns/wizard/approve-places` - Approve places, continue to scenes
- `GET /campaigns/wizard/api/scenes/<request_id>` - Get generated scenes
- `POST /campaigns/wizard/approve-scenes` - Approve scenes, continue to elements
- `GET /campaigns/wizard/api/progress/<request_id>` - Get workflow progress

#### 2.2 Update Orchestrator Endpoints

**File:** `ai-agents/orchestrator/main.py`

**Add/Update endpoints:**
- `POST /campaign-wizard/start` ✅ (Already exists)
- `POST /campaign-wizard/select-story` ✅ (Already exists)
- `POST /campaign-wizard/regenerate-stories` ✅ (Already exists)
- `POST /campaign-wizard/approve-core` ✅ (Already exists)
- `GET /campaign-wizard/status/<request_id>` ✅ (Already exists)
- `POST /campaign-wizard/approve-quests` ❌ (NEW)
- `POST /campaign-wizard/approve-places` ❌ (NEW)
- `POST /campaign-wizard/approve-scenes` ❌ (NEW)

#### 2.3 Update Campaign Workflow

**File:** `services/campaign-factory/workflow/campaign_workflow.py`

**Add new approval gates:**

```python
def route_after_quests(state: CampaignWorkflowState) -> str:
    """Route after quest generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_quests"
    if state.user_approved_quests:  # NEW
        return "generate_places"
    return "wait_for_quest_approval"  # NEW

def route_after_places(state: CampaignWorkflowState) -> str:
    """Route after place generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_places"
    if state.user_approved_places:  # NEW
        return "generate_scenes"
    return "wait_for_place_approval"  # NEW

def route_after_scenes(state: CampaignWorkflowState) -> str:
    """Route after scene generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_scenes"
    if state.user_approved_scenes:  # NEW
        return "generate_elements"
    return "wait_for_scene_approval"  # NEW
```

**Add new nodes:**
```python
workflow.add_node("wait_for_quest_approval", wait_for_quest_approval_node)
workflow.add_node("wait_for_place_approval", wait_for_place_approval_node)
workflow.add_node("wait_for_scene_approval", wait_for_scene_approval_node)
```

#### 2.4 Update Workflow State

**File:** `services/campaign-factory/workflow/state.py`

**Add new fields:**

```python
class CampaignWorkflowState(TypedDict):
    # ... existing fields ...

    # NEW: Additional approval gates
    user_approved_quests: bool
    user_approved_places: bool
    user_approved_scenes: bool

    # NEW: Backstory tracking
    campaign_backstory: Optional[str]
    quest_backstories: Dict[str, str]  # quest_id -> backstory

    # NEW: Image generation preferences
    generate_images_campaign: bool
    generate_images_quests: bool
    generate_images_places: bool
    generate_images_scenes: bool
```

---

### Phase 3: Bloom's Taxonomy Integration (MEDIUM PRIORITY)

#### 3.1 Display Bloom's Levels Throughout Wizard

**At Campaign Core Review:**
```html
<div class="blooms-section">
    <h6>Bloom's Taxonomy Integration</h6>
    <p>This campaign will challenge players at multiple cognitive levels:</p>
    <ul>
        <li><strong>Remembering:</strong> Recall world lore and NPC information</li>
        <li><strong>Understanding:</strong> Comprehend quest objectives and storylines</li>
        <li><strong>Applying:</strong> Use knowledge to solve puzzles and challenges</li>
        <li><strong>Analyzing:</strong> Break down complex problems and relationships</li>
        <li><strong>Evaluating:</strong> Make judgment calls on quest outcomes</li>
        <li><strong>Creating:</strong> Develop strategies and solutions</li>
    </ul>
    <p class="info">During gameplay, the AI will adjust challenge difficulty based on player maturity level.</p>
</div>
```

#### 3.2 Tag Each Quest/Task with Bloom's Level

**In Quest Review:**
```html
<div class="quest-card">
    <h6>{{ quest.name }}</h6>
    <p>{{ quest.description }}</p>
    <div class="blooms-tags">
        {% for objective in quest.objectives %}
        <span class="chip blooms-{{ objective.blooms_level }}">
            {{ objective.blooms_label }}
        </span>
        {% endfor %}
    </div>
</div>
```

---

### Phase 4: Location Hierarchy & World Factory Integration (MEDIUM PRIORITY)

#### 4.1 Automatic Location Creation

**When generating Quests:**
- Check if suitable Level 1 Location exists in Region
- If not, call World Factory to create new Level 1 Location
- Store `new_location_ids` in workflow state

**When generating Places:**
- Check if suitable Level 2 Location exists as child of Quest's Level 1 Location
- If not, create new Level 2 Location via World Factory

**When generating Scenes:**
- Check if suitable Level 3 Location exists as child of Place's Level 2 Location
- If not, create new Level 3 Location via World Factory

**Update workflow nodes:**
- `nodes_quest.py`: Add location hierarchy check
- `nodes_place_scene.py`: Add location creation logic

#### 4.2 Display New Locations Created

**In Review steps:**
```html
<div class="new-locations-section">
    <h6>New Locations Created</h6>
    <p>The following locations were automatically generated for this campaign:</p>
    <ul>
        {% for location in new_locations %}
        <li>{{ location.name }} ({{ location.type }})</li>
        {% endfor %}
    </ul>
    <p class="info">These locations are now part of your world and can be reused in future campaigns.</p>
</div>
```

---

### Phase 5: Backstory Generation at Each Level (MEDIUM PRIORITY)

#### 5.1 Generate Backstories

**Update nodes to generate backstories:**

**Campaign Level:**
- `nodes_core.py`: Add backstory generation to campaign core

**Quest Level:**
- `nodes_quest.py`: Generate backstory for each quest

**Location/Place/Scene Level:**
- When creating new locations, generate backstory via Game Master agent

#### 5.2 Display Backstories in UI

**Add expandable backstory sections:**
```html
<div class="backstory-section">
    <button class="btn-small" onclick="toggleBackstory('quest-1')">
        <i class="material-icons">book</i> View Backstory
    </button>
    <div id="backstory-quest-1" class="backstory-content" style="display: none;">
        <p>{{ quest.backstory }}</p>
    </div>
</div>
```

---

### Phase 6: Knowledge & Items System (LOW PRIORITY)

#### 6.1 Explicit Knowledge & Items Display

**In Scene Review:**
```html
<div class="scene-elements">
    <h6>Knowledge to Acquire:</h6>
    <ul>
        {% for knowledge in scene.knowledge %}
        <li>{{ knowledge.name }} - {{ knowledge.description }}</li>
        {% endfor %}
    </ul>

    <h6>Items to Find:</h6>
    <ul>
        {% for item in scene.items %}
        <li>{{ item.name }} - {{ item.description }}</li>
        {% endfor %}
    </ul>
</div>
```

#### 6.2 Show Knowledge/Items Unlocking

**Display dependency graph:**
```html
<div class="dependency-graph">
    <p>This scene requires:</p>
    <ul>
        <li>Knowledge: "Ancient Rune Meaning" (acquired in Quest 2, Scene 3)</li>
        <li>Item: "Crystal Key" (acquired in Quest 1, Scene 5)</li>
    </ul>
</div>
```

---

## Summary of Changes

### Frontend Changes:
1. ✅ Add Universe selection step
2. ✅ Update World selection to show genre
3. ✅ Make story idea optional & multi-row
4. ✅ Add "Generate Campaign Ideas" step with 3 story options
5. ✅ Add Campaign Core review step
6. ✅ Enhance Quest settings (difficulty, playtime)
7. ✅ Add Quest review step
8. ✅ Add Place review step
9. ✅ Add Scene review step
10. ✅ Add image generation options per level
11. ✅ Enhanced progress tracking UI
12. ✅ Bloom's Taxonomy display at each level

### Backend Changes:
1. ✅ Create new wizard view endpoints
2. ✅ Add approval gates for Quest, Place, Scene levels
3. ✅ Update workflow state with new fields
4. ✅ Integrate World Factory for location creation
5. ✅ Add backstory generation at each level
6. ✅ Enhance progress tracking in Redis
7. ✅ Add Knowledge & Items system

### Priority Order:
1. **HIGH**: Phase 1 (UI Flow) + Phase 2 (Backend Integration)
2. **MEDIUM**: Phase 3 (Bloom's) + Phase 4 (Location Hierarchy) + Phase 5 (Backstories)
3. **LOW**: Phase 6 (Knowledge & Items Display)

---

## Next Steps

1. Start with Phase 1.1-1.3: Update wizard to include Universe selection
2. Implement Phase 1.4-1.6: Story idea generation and selection
3. Build Phase 1.7-1.10: Add review steps
4. Integrate Phase 2: Backend workflow updates
5. Polish with Phase 3-6: Advanced features

Would you like me to start implementing any of these phases?
