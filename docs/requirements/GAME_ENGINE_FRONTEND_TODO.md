# Game Engine Frontend Implementation TODO
## Objective Display UI Components

**Status:** Backend Complete ✅ | Frontend Pending ⏳
**Priority:** P0 (Critical)
**Estimated Effort:** 20 hours

---

## Backend Completion Summary

All backend work is **COMPLETE** and ready for frontend integration:

✅ **Neo4j Query Service** - 5 new methods (+510 lines)
- `get_player_objective_progress()`
- `get_available_acquisition_paths()`
- `get_scene_objectives()`
- `get_dimensional_progress()`
- `record_objective_progress()`

✅ **Quest Tracker Integration** - 3 new methods (+330 lines)
- `check_objective_cascade()`
- `_check_quest_objective_conditions()`
- `_check_criterion()`

✅ **API Endpoints** - 4 new routes (+300 lines)
- `GET /session/{session_id}/objectives`
- `GET /session/{session_id}/knowledge/{knowledge_id}/paths`
- `GET /session/{session_id}/item/{item_id}/paths`
- `GET /session/{session_id}/dimensional-progress`

✅ **WebSocket Events** - 2 event types
- `objective_progress` - Quest objective updates
- `campaign_objective_progress` - Campaign objective updates

**Total Backend Lines:** ~1,140 lines

---

## Frontend Tasks Remaining

### **Task 1: Add Objectives Sidebar to session.html**

**File:** `services/django-web/templates/game/session.html`

**Location:** Add as a fixed right sidebar (similar to existing layout structure)

**HTML to Add:**

```html
<!-- Objectives Sidebar (Right Panel) -->
<div id="objectives-sidebar" class="objectives-panel" style="
    position: fixed;
    right: 20px;
    top: 120px;
    width: 350px;
    background: rgba(27, 27, 46, 0.95);
    padding: 20px;
    border-radius: 8px;
    max-height: calc(100vh - 140px);
    overflow-y: auto;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 90;
">
    <!-- Header with Toggle -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h5 style="color: var(--rpg-gold, #FFD700); margin: 0;">
            <i class="material-icons tiny" style="vertical-align: middle;">flag</i>
            Objectives
        </h5>
        <button id="toggle-objectives-btn" class="btn-flat" style="color: white; padding: 0; min-width: 36px;">
            <i class="material-icons">chevron_right</i>
        </button>
    </div>

    <!-- Campaign Objectives -->
    <div id="campaign-objectives-container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h6 style="color: var(--rpg-silver, #C0C0C0); margin: 0; font-size: 0.9rem;">
                Campaign Progress
            </h6>
            <span id="overall-progress-badge" style="
                background: rgba(106, 90, 205, 0.3);
                color: var(--rpg-purple, #6A5ACD);
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: bold;
            ">0%</span>
        </div>
        <div id="campaign-objectives-list">
            <!-- Populated via JavaScript -->
            <p style="color: #888; font-size: 0.85rem; text-align: center; padding: 20px;">
                Loading objectives...
            </p>
        </div>
    </div>

    <!-- Current Quest Objectives -->
    <div id="quest-objectives-container" style="margin-top: 20px;">
        <h6 style="color: var(--rpg-silver, #C0C0C0); margin-bottom: 8px; font-size: 0.9rem;">
            <i class="material-icons tiny" style="vertical-align: middle;">assignment</i>
            Current Quest
        </h6>
        <div id="quest-objectives-list">
            <!-- Populated via JavaScript -->
        </div>
    </div>

    <!-- Scene Objectives -->
    <div id="scene-objectives-container" style="margin-top: 20px;">
        <h6 style="color: var(--rpg-silver, #C0C0C0); margin-bottom: 8px; font-size: 0.9rem;">
            <i class="material-icons tiny" style="vertical-align: middle;">location_on</i>
            This Scene
        </h6>
        <div id="scene-objectives-list">
            <!-- Populated via JavaScript -->
        </div>
    </div>

    <!-- Scene Resources (Knowledge & Items) -->
    <div id="scene-resources-container" style="margin-top: 20px;">
        <h6 style="color: var(--rpg-gold, #FFD700); margin-bottom: 8px; font-size: 0.9rem;">
            <i class="material-icons tiny" style="vertical-align: middle;">school</i>
            Available Resources
        </h6>

        <div id="scene-knowledge-list" style="margin-bottom: 10px;">
            <!-- Knowledge items -->
        </div>

        <div id="scene-items-list">
            <!-- Item items -->
        </div>
    </div>

    <!-- Dimensional Development -->
    <div id="dimensional-progress-container" style="margin-top: 20px;">
        <h6 style="color: var(--rpg-silver, #C0C0C0); margin-bottom: 8px; font-size: 0.9rem;">
            <i class="material-icons tiny" style="vertical-align: middle;">psychology</i>
            Dimensional Development
        </h6>
        <div id="dimensions-list">
            <!-- Populated via JavaScript -->
        </div>
    </div>
</div>

<!-- Objectives Sidebar Collapsed State -->
<style>
.objectives-panel.collapsed {
    right: -330px !important;
}

.objectives-panel {
    transition: right 0.3s ease-in-out;
}
</style>
```

**Toggle Functionality (Add to session.html `<script>` section):**

```javascript
// Toggle objectives sidebar
document.getElementById('toggle-objectives-btn').addEventListener('click', function() {
    const sidebar = document.getElementById('objectives-sidebar');
    const icon = this.querySelector('i');

    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        icon.textContent = 'chevron_right';
    } else {
        sidebar.classList.add('collapsed');
        icon.textContent = 'chevron_left';
    }
});
```

---

### **Task 2: Create/Update game_session.js**

**File:** `services/django-web/static/js/game_session.js` (create if doesn't exist)

**Functions to Add:**

#### **1. Load Initial Objective Data**

```javascript
async function loadObjectiveProgress(sessionId, playerId) {
    try {
        // Use game engine port (8080) instead of Django port (8000)
        const response = await fetch(
            `http://localhost:8080/session/${sessionId}/objectives?player_id=${playerId}`
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Update overall progress badge
        document.getElementById('overall-progress-badge').textContent =
            `${data.overall_progress}%`;

        // Render campaign objectives
        const campaignList = document.getElementById('campaign-objectives-list');
        if (data.campaign_objectives && data.campaign_objectives.length > 0) {
            campaignList.innerHTML = data.campaign_objectives
                .map(renderCampaignObjective)
                .join('');
        } else {
            campaignList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center; padding: 10px;">No objectives yet</p>';
        }

        // Render current quest objectives
        const questList = document.getElementById('quest-objectives-list');
        if (data.current_quest_objectives && data.current_quest_objectives.length > 0) {
            questList.innerHTML = data.current_quest_objectives
                .map(renderQuestObjective)
                .join('');
        } else {
            questList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center;">No active quest objectives</p>';
        }

        // Render scene objectives
        const sceneList = document.getElementById('scene-objectives-list');
        if (data.scene_objectives && data.scene_objectives.length > 0) {
            sceneList.innerHTML = data.scene_objectives
                .map(obj => `
                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px;">
                        <div style="color: #b8b8d1; font-size: 0.85rem;">${obj.description}</div>
                    </div>
                `).join('');
        } else {
            sceneList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center;">No scene objectives</p>';
        }

        // Render scene knowledge
        const knowledgeList = document.getElementById('scene-knowledge-list');
        if (data.scene_knowledge && data.scene_knowledge.length > 0) {
            knowledgeList.innerHTML = data.scene_knowledge
                .map(k => renderSceneResource(k, 'knowledge'))
                .join('');
        }

        // Render scene items
        const itemsList = document.getElementById('scene-items-list');
        if (data.scene_items && data.scene_items.length > 0) {
            itemsList.innerHTML = data.scene_items
                .map(i => renderSceneResource(i, 'item'))
                .join('');
        }

        // Render dimensional progress
        const dimensionsList = document.getElementById('dimensions-list');
        if (data.dimensions && data.dimensions.length > 0) {
            dimensionsList.innerHTML = renderDimensionalProgress(data.dimensions);
        }

        console.log('Objectives loaded successfully', data);

    } catch (error) {
        console.error('Failed to load objectives:', error);
        document.getElementById('campaign-objectives-list').innerHTML =
            '<p style="color: #f44336; font-size: 0.85rem; text-align: center;">Failed to load objectives</p>';
    }
}
```

#### **2. Render Functions**

```javascript
function renderCampaignObjective(objective) {
    const percentage = objective.completion_percentage || 0;
    const color = percentage === 100 ? '#4CAF50' : percentage > 0 ? '#6A5ACD' : '#C0C0C0';

    return `
        <div class="objective-card"
             data-campaign-objective-id="${objective.id}"
             style="margin-bottom: 15px; padding: 12px; background: rgba(106, 90, 205, 0.1); border-left: 3px solid ${color}; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="color: #FFD700; font-weight: bold; flex: 1; font-size: 0.9rem;">${objective.description}</span>
                <span class="campaign-percentage" style="color: ${color}; font-size: 0.85rem; font-weight: bold;">${percentage}%</span>
            </div>

            <!-- Progress bar -->
            <div style="margin-top: 8px; height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                <div class="campaign-progress-bar" style="height: 100%; background: ${color}; width: ${percentage}%; transition: width 0.5s ease;"></div>
            </div>

            <!-- Quest objectives under this campaign objective -->
            <div class="quest-objectives" style="margin-top: 10px; padding-left: 10px;">
                ${objective.quest_objectives.map(qo => renderQuestObjective(qo)).join('')}
            </div>
        </div>
    `;
}

function renderQuestObjective(questObj) {
    const status = questObj.status || 'not_started';
    const icon = status === 'completed' ? 'check_circle' : status === 'in_progress' ? 'pending' : 'radio_button_unchecked';
    const color = status === 'completed' ? '#4CAF50' : status === 'in_progress' ? '#6A5ACD' : '#C0C0C0';

    return `
        <div data-objective-id="${questObj.id}" style="margin-bottom: 8px; display: flex; align-items: start; gap: 8px;">
            <i class="material-icons tiny status-icon" style="color: ${color}; margin-top: 2px; font-size: 16px;">${icon}</i>
            <div style="flex: 1;">
                <span style="color: #b8b8d1; font-size: 0.85rem;">${questObj.description}</span>
                ${questObj.progress ? `
                    <div class="progress-bar" style="margin-top: 4px; height: 4px; background: rgba(192, 192, 192, 0.2); border-radius: 2px; overflow: hidden;">
                        <div style="height: 100%; background: ${color}; width: ${questObj.progress}%; transition: width 0.5s ease;"></div>
                    </div>
                    <div class="percentage-text" style="margin-top: 2px; font-size: 0.75rem; color: ${color};">
                        ${questObj.progress}% complete
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function renderSceneResource(resource, type) {
    const icon = type === 'knowledge' ? 'school' : 'inventory_2';
    const color = type === 'knowledge' ? '#6A5ACD' : '#FFC107';

    // Show redundancy indicator
    const redundancyColor = {
        'high': '#4CAF50',
        'medium': '#FFC107',
        'low': '#f44336'
    }[resource.redundancy_level || 'low'];

    const acquisitionMethods = resource.acquisition_methods || [];
    const methodCount = acquisitionMethods.length;

    return `
        <div class="resource-card" style="margin-bottom: 10px; padding: 10px; background: rgba(255, 255, 255, 0.05); border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <i class="material-icons tiny" style="color: ${color}; font-size: 18px;">${icon}</i>
                <span style="color: ${color}; font-weight: bold; flex: 1; font-size: 0.85rem;">${resource.name}</span>
                <span style="font-size: 0.7rem; color: ${redundancyColor}; font-weight: bold;">
                    ${methodCount} path${methodCount !== 1 ? 's' : ''}
                </span>
            </div>

            ${resource.description ? `
                <div style="font-size: 0.8rem; color: #b8b8d1; margin-bottom: 8px;">
                    ${resource.description}
                </div>
            ` : ''}

            <!-- Acquisition methods -->
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                ${acquisitionMethods.map(method => {
                    const methodIcon = {
                        'npc': '💬',
                        'teaches': '💬',
                        'discovery': '🔍',
                        'reveals': '🔍',
                        'challenge': '⚔️',
                        'rewards': '⚔️',
                        'event': '⭐',
                        'gives': '🎁',
                        'contains': '📦',
                        'grants': '✨'
                    }[method.toLowerCase()] || '•';

                    return `
                        <span class="chip" style="background: rgba(106, 90, 205, 0.2); color: #6A5ACD; font-size: 0.7rem; padding: 2px 6px; border-radius: 12px;">
                            ${methodIcon} ${method}
                        </span>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderDimensionalProgress(dimensions) {
    return dimensions.map(dim => {
        const percentage = dim.percentage || 0;
        const color = percentage >= 75 ? '#4CAF50' : percentage >= 50 ? '#6A5ACD' : '#C0C0C0';

        return `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #b8b8d1; font-size: 0.8rem;">${dim.name}</span>
                    <span style="color: ${color}; font-size: 0.8rem; font-weight: bold;">${percentage}%</span>
                </div>
                <div style="height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                    <div style="height: 100%; background: ${color}; width: ${percentage}%; transition: width 0.5s;"></div>
                </div>
                <div style="margin-top: 2px; font-size: 0.7rem; color: #888;">
                    Knowledge: ${dim.knowledge_acquired}/${dim.knowledge_total} |
                    Challenges: ${dim.challenges_completed}/${dim.challenges_total}
                </div>
            </div>
        `;
    }).join('');
}
```

#### **3. WebSocket Event Handlers**

Add to existing WebSocket `onmessage` handler:

```javascript
// In existing websocket.onmessage function
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);

    switch(data.event) {
        case 'objective_progress':
            handleObjectiveProgress(data);
            break;
        case 'campaign_objective_progress':
            handleCampaignObjectiveProgress(data);
            break;
        // ... existing cases
    }
};

function handleObjectiveProgress(data) {
    // Update quest objective UI
    const objectiveCard = document.querySelector(`[data-objective-id="${data.objective_id}"]`);
    if (objectiveCard) {
        // Update progress bar
        const progressBar = objectiveCard.querySelector('.progress-bar div');
        if (progressBar) {
            progressBar.style.width = `${data.percentage}%`;
        }

        // Update percentage text
        const percentageText = objectiveCard.querySelector('.percentage-text');
        if (percentageText) {
            percentageText.textContent = `${data.percentage}% complete`;
        }

        // Update status icon if completed
        if (data.percentage === 100) {
            const icon = objectiveCard.querySelector('.status-icon');
            if (icon) {
                icon.textContent = 'check_circle';
                icon.style.color = '#4CAF50';
            }
        }
    }

    // Show toast notification
    if (typeof M !== 'undefined' && M.toast) {
        M.toast({
            html: `<i class="material-icons tiny">check</i> ${data.objective_description} (${data.percentage}%)`,
            classes: 'purple',
            displayLength: 3000
        });
    }

    // Trigger celebration animation if completed
    if (data.percentage === 100) {
        triggerObjectiveCompletionAnimation(data.objective_id);
    }
}

function handleCampaignObjectiveProgress(data) {
    // Update campaign objective card
    const campaignCard = document.querySelector(`[data-campaign-objective-id="${data.objective_id}"]`);
    if (campaignCard) {
        const progressBar = campaignCard.querySelector('.campaign-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${data.percentage}%`;
        }

        const percentageText = campaignCard.querySelector('.campaign-percentage');
        if (percentageText) {
            percentageText.textContent = `${data.percentage}%`;
        }
    }

    // Update overall progress
    document.getElementById('overall-progress-badge').textContent = `${data.percentage}%`;
}

function triggerObjectiveCompletionAnimation(objectiveId) {
    const card = document.querySelector(`[data-objective-id="${objectiveId}"]`);
    if (card) {
        // Add pulse animation
        card.style.animation = 'pulse 0.5s ease-in-out';

        // Optional: Add confetti effect if library available
        if (typeof confetti === 'function') {
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
        }

        // Play success sound if available
        try {
            const audio = new Audio('/static/sounds/objective_complete.mp3');
            audio.play().catch(err => console.log('Audio play failed:', err));
        } catch (e) {
            // Ignore audio errors
        }
    }
}
```

#### **4. Initialize on Page Load**

```javascript
document.addEventListener('DOMContentLoaded', function() {
    // Get session and player ID from page data attributes or URL
    const sessionId = document.body.dataset.sessionId ||
                      new URLSearchParams(window.location.search).get('session_id');
    const playerId = document.body.dataset.playerId ||
                     new URLSearchParams(window.location.search).get('player_id');

    if (sessionId && playerId) {
        // Load objective progress
        loadObjectiveProgress(sessionId, playerId);

        // Refresh every 30 seconds (optional)
        setInterval(() => {
            loadObjectiveProgress(sessionId, playerId);
        }, 30000);
    }
});
```

---

## Testing Checklist

### **1. Visual Testing**

- [ ] Objectives sidebar appears on right side of screen
- [ ] Toggle button collapses/expands sidebar
- [ ] Campaign objectives display with progress bars
- [ ] Quest objectives display with status icons
- [ ] Scene resources show acquisition methods
- [ ] Dimensional progress bars render correctly
- [ ] All colors match design (purple, gold, green, etc.)
- [ ] Responsive layout works on different screen sizes

### **2. Functional Testing**

- [ ] API call to `/session/{id}/objectives` succeeds
- [ ] Objective data populates correctly on page load
- [ ] WebSocket events update objective UI in real-time
- [ ] Progress bars animate smoothly
- [ ] Toast notifications appear on objective progress
- [ ] Celebration animation triggers on objective completion
- [ ] Overall progress badge updates correctly

### **3. Error Handling**

- [ ] Graceful error message if API fails
- [ ] Empty state displays when no objectives
- [ ] No JavaScript console errors
- [ ] Sidebar doesn't break if data missing

---

## Integration Steps

1. **Add HTML to session.html:**
   - Find existing sidebar structure
   - Add objectives sidebar HTML
   - Add toggle CSS and script

2. **Create/Update game_session.js:**
   - Add all render functions
   - Add loadObjectiveProgress function
   - Add WebSocket event handlers
   - Add page load initialization

3. **Link JavaScript to HTML:**
   - Add `<script src="{% static 'js/game_session.js' %}"></script>` to session.html
   - Ensure it loads AFTER WebSocket connection established

4. **Test:**
   - Start game session
   - Verify objectives load
   - Trigger objective progress (complete a challenge, acquire knowledge, etc.)
   - Verify WebSocket updates work

---

## CSS Variables Used

Make sure these are defined in your CSS:

```css
:root {
    --rpg-gold: #FFD700;
    --rpg-silver: #C0C0C0;
    --rpg-purple: #6A5ACD;
    --rpg-green: #4CAF50;
}
```

---

## Next Steps After Frontend Complete

1. **Test with real campaign data**
2. **Optimize Neo4j queries for performance**
3. **Add error logging and monitoring**
4. **Create player feedback survey**
5. **Document API for other developers**

---

**Status:** ⏳ **Ready for Frontend Implementation**
**Estimated Time:** 12-16 hours for complete UI implementation
