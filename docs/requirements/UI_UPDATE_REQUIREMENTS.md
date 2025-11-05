# UI Update Requirements for Hierarchical Objective System

## 🎯 Overview

The backend now supports a 3-level hierarchical objective system with 4 child objective types, rubric-based evaluation, and cascade tracking. The UI needs updates to display and interact with this new system.

---

## 📊 **1. Game UI Updates** (CRITICAL)

**File:** `services/django-web/static/js/game_session.js`

### **Current State:**
- Displays campaign objectives (flat)
- Displays quest objectives (flat)
- Shows "scene objectives" (generic placeholder)
- No rubric scores or quality ratings
- Basic WebSocket handlers

### **Required Updates:**

#### **A. Child Objectives Display (NEW)**

Add rendering for 4 child objective types with type-specific icons and metadata:

```javascript
function renderChildObjectives(childObjectives, sceneid) {
    // Group by type
    const discoveries = childObjectives.filter(o => o.objective_type === 'discovery');
    const challenges = childObjectives.filter(o => o.objective_type === 'challenge');
    const events = childObjectives.filter(o => o.objective_type === 'event');
    const conversations = childObjectives.filter(o => o.objective_type === 'conversation');

    return `
        <!-- Discovery Objectives -->
        ${discoveries.length > 0 ? `
            <div class="objective-group">
                <h6>🔍 Discoveries</h6>
                ${discoveries.map(d => renderChildObjective(d, '🔍')).join('')}
            </div>
        ` : ''}

        <!-- Challenge Objectives -->
        ${challenges.length > 0 ? `
            <div class="objective-group">
                <h6>⚔️ Challenges</h6>
                ${challenges.map(c => renderChildObjective(c, '⚔️')).join('')}
            </div>
        ` : ''}

        <!-- Event Objectives -->
        ${events.length > 0 ? `
            <div class="objective-group">
                <h6>⭐ Events</h6>
                ${events.map(e => renderChildObjective(e, '⭐')).join('')}
            </div>
        ` : ''}

        <!-- Conversation Objectives -->
        ${conversations.length > 0 ? `
            <div class="objective-group">
                <h6>💬 Conversations</h6>
                ${conversations.map(c => renderChildObjective(c, '💬')).join('')}
            </div>
        ` : ''}
    `;
}

function renderChildObjective(childObj, icon) {
    const isCompleted = childObj.status === 'completed';
    const rubricScore = childObj.rubric_score || null;
    const minScore = childObj.minimum_rubric_score || 2.5;

    return `
        <div class="child-objective-card"
             data-child-objective-id="${childObj.objective_id}"
             style="margin: 8px 0; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 4px; border-left: 3px solid ${isCompleted ? '#4CAF50' : '#6A5ACD'};">

            <div style="display: flex; align-items: start; gap: 8px;">
                <span style="font-size: 1.2rem;">${icon}</span>
                <div style="flex: 1;">
                    <div style="font-size: 0.85rem; color: ${isCompleted ? '#4CAF50' : '#b8b8d1'};">
                        ${childObj.description}
                    </div>

                    ${childObj.is_required ?
                        '<span class="chip tiny" style="background: #f44336; color: white; font-size: 0.6rem; padding: 2px 6px;">Required</span>' :
                        '<span class="chip tiny" style="background: #888; color: white; font-size: 0.6rem; padding: 2px 6px;">Optional</span>'
                    }

                    ${rubricScore !== null ? `
                        <div class="rubric-score" style="margin-top: 4px; font-size: 0.75rem; color: ${getRubricColor(rubricScore)};">
                            Quality: ${rubricScore.toFixed(1)}/4.0 ${rubricScore >= minScore ? '✓' : '✗'}
                        </div>
                    ` : ''}

                    ${renderObjectiveHints(childObj)}
                </div>
            </div>
        </div>
    `;
}

function renderObjectiveHints(childObj) {
    const type = childObj.objective_type;
    let hint = '';

    if (type === 'discovery' && childObj.scene_location_hint) {
        hint = `<div style="font-size: 0.7rem; color: #888; margin-top: 4px;">💡 ${childObj.scene_location_hint}</div>`;
    } else if (type === 'challenge' && childObj.difficulty_hint) {
        hint = `<div style="font-size: 0.7rem; color: #888; margin-top: 4px;">⚠️ ${childObj.difficulty_hint}</div>`;
    } else if (type === 'conversation' && childObj.npc_name_hint) {
        hint = `<div style="font-size: 0.7rem; color: #888; margin-top: 4px;">💬 Talk to ${childObj.npc_name_hint}</div>`;
    } else if (type === 'event' && childObj.participation_type) {
        hint = `<div style="font-size: 0.7rem; color: #888; margin-top: 4px;">📋 ${childObj.participation_type}</div>`;
    }

    return hint;
}

function getRubricColor(score) {
    if (score >= 3.5) return '#4CAF50'; // Excellent
    if (score >= 2.5) return '#6A5ACD'; // Good
    if (score >= 1.5) return '#FFC107'; // Basic
    return '#f44336'; // Minimal
}
```

#### **B. Update Quest Objective Rendering**

Modify `renderQuestObjective()` to show child objectives underneath:

```javascript
function renderQuestObjective(questObj) {
    // ... existing code ...

    return `
        <div data-objective-id="${questObj.id}" style="margin-bottom: 12px;">
            <!-- Existing quest objective display -->
            <div style="display: flex; align-items: start; gap: 8px;">
                <i class="material-icons tiny status-icon" style="color: ${color};">${icon}</i>
                <div style="flex: 1;">
                    <span style="color: #b8b8d1; font-size: 0.85rem;">${questObj.description}</span>

                    <!-- Progress bar -->
                    ${progress > 0 ? `...` : ''}
                </div>
            </div>

            <!-- NEW: Child objectives under this quest objective -->
            ${questObj.child_objectives && questObj.child_objectives.length > 0 ? `
                <div class="child-objectives-list" style="margin-top: 10px; padding-left: 20px; border-left: 2px solid rgba(106, 90, 205, 0.3);">
                    ${renderChildObjectives(questObj.child_objectives, questObj.current_scene_id)}
                </div>
            ` : ''}
        </div>
    `;
}
```

#### **C. New WebSocket Event Handlers**

Add handlers for the new event types:

```javascript
// Add to window.GameSessionObjectives
function handleChildObjectiveCompleted(data) {
    console.log('Child objective completed:', data);

    const childCard = document.querySelector(`[data-child-objective-id="${data.child_objective_id}"]`);
    if (childCard) {
        // Update card styling
        childCard.style.borderLeftColor = '#4CAF50';

        // Add rubric score display
        const scoreDiv = document.createElement('div');
        scoreDiv.className = 'rubric-score';
        scoreDiv.innerHTML = `
            <div style="margin-top: 4px; font-size: 0.75rem; color: ${getRubricColor(data.rubric_score)};">
                Quality: ${data.rubric_score.toFixed(1)}/4.0 - ${getQualityLabel(data.completion_quality)}
            </div>
        `;
        childCard.appendChild(scoreDiv);

        // Show completion animation
        triggerChildObjectiveAnimation(childCard, data.child_objective_type);
    }

    // Update parent quest objective progress
    if (data.quest_objective_progress) {
        updateQuestObjectiveProgress(data.quest_objective_id, data.quest_objective_progress);
    }

    // Show toast with rubric score
    showRubricToast(data.child_objective_type, data.description, data.rubric_score, data.completion_quality);
}

function handleQuestObjectiveCompleted(data) {
    console.log('Quest objective completed:', data);

    // Update quest objective card
    const questCard = document.querySelector(`[data-objective-id="${data.quest_objective_id}"]`);
    if (questCard) {
        const icon = questCard.querySelector('.status-icon');
        if (icon) {
            icon.textContent = 'check_circle';
            icon.style.color = '#4CAF50';
        }
    }

    // Show toast with average quality
    M.toast({
        html: `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="material-icons">emoji_events</i>
                <div>
                    Quest Objective Complete!
                    <div style="font-size: 0.8rem; opacity: 0.9;">Average Quality: ${data.overall_quality}</div>
                </div>
            </div>
        `,
        classes: 'green',
        displayLength: 5000
    });

    // Trigger celebration
    if (typeof confetti === 'function') {
        confetti({ particleCount: 150, spread: 90 });
    }
}

function handleCampaignObjectiveCompleted(data) {
    console.log('Campaign objective completed:', data);

    // Major celebration - campaign objective is huge!
    M.toast({
        html: `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="material-icons" style="font-size: 2rem;">🏆</i>
                <div>
                    <strong>Campaign Milestone Achieved!</strong>
                    <div style="font-size: 0.8rem;">${data.description}</div>
                    <div style="font-size: 0.75rem; opacity: 0.9;">Quality Score: ${data.overall_quality_score.toFixed(1)}/4.0</div>
                </div>
            </div>
        `,
        classes: 'purple',
        displayLength: 7000
    });

    // Epic celebration
    if (typeof confetti === 'function') {
        confetti({
            particleCount: 300,
            spread: 120,
            origin: { y: 0.5 }
        });
    }

    // Play fanfare sound
    try {
        const audio = new Audio('/static/sounds/campaign_milestone.mp3');
        audio.play();
    } catch (e) {
        // Ignore
    }
}

function handleObjectiveCascadeUpdate(data) {
    console.log('Cascade update:', data);

    // Update all affected objectives
    data.updated_objectives.forEach(obj => {
        if (obj.type === 'quest') {
            updateQuestObjectiveProgress(obj.id, obj.progress);
        } else if (obj.type === 'campaign') {
            updateCampaignObjectiveProgress(obj.id, obj.progress);
        }
    });
}

function showRubricToast(type, description, score, quality) {
    const typeEmoji = {
        'discovery': '🔍',
        'challenge': '⚔️',
        'event': '⭐',
        'conversation': '💬'
    }[type] || '✓';

    const qualityColor = {
        'excellent': '#4CAF50',
        'good': '#6A5ACD',
        'minimal': '#FFC107'
    }[quality] || '#888';

    M.toast({
        html: `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.5rem;">${typeEmoji}</span>
                <div>
                    <strong>${description}</strong>
                    <div style="font-size: 0.8rem; color: ${qualityColor};">
                        Score: ${score.toFixed(1)}/4.0 - ${quality.toUpperCase()}
                    </div>
                </div>
            </div>
        `,
        classes: 'purple',
        displayLength: 4000
    });
}

// Export new handlers
window.GameSessionObjectives.handleChildObjectiveCompleted = handleChildObjectiveCompleted;
window.GameSessionObjectives.handleQuestObjectiveCompleted = handleQuestObjectiveCompleted;
window.GameSessionObjectives.handleCampaignObjectiveCompleted = handleCampaignObjectiveCompleted;
window.GameSessionObjectives.handleObjectiveCascadeUpdate = handleObjectiveCascadeUpdate;
```

#### **D. Update API Call**

Modify `loadObjectiveProgress()` to fetch child objectives:

```javascript
async function loadObjectiveProgress(sessionId, playerId) {
    try {
        // Add child_objectives=true parameter
        const response = await fetch(
            `/api/session/${sessionId}/objectives/?player_id=${playerId}&child_objectives=true`
        );

        // ... rest of existing code
    } catch (error) {
        // ... error handling
    }
}
```

---

## 🏭 **2. Campaign Factory UI Updates** (OPTIONAL)

**File:** `services/django-web/static/js/campaign_wizard_v2.js`

### **Current State:**
- 11-step wizard for campaign creation
- Polls workflow status
- Shows quest/place/scene progress

### **Recommended Updates:**

#### **A. Add Child Objectives Preview Step (Optional)**

After step 7 (quest generation), add an optional preview of child objectives:

```javascript
// Update totalSteps to 12 (add 1 step)
const totalSteps = 12;

// Add new step in HTML template (services/django-web/games/templates/games/campaign_wizard_v2.html):
// Step 8: Child Objectives Preview

// Update navigation to handle new step
```

#### **B. Show Objective Decomposition in Progress**

Update the polling display to show new workflow steps:

```javascript
function displayWorkflowProgress(workflowData) {
    // ... existing code ...

    // Add new workflow steps
    const newSteps = [
        { key: 'decompose_objectives', label: '🎯 Decomposing Objectives' },
        { key: 'design_child_objectives', label: '🔍 Designing Child Objectives' },
        { key: 'assign_rubrics', label: '📊 Assigning Rubrics' },
        { key: 'plan_narrative', label: '📖 Planning Narrative' },
        { key: 'validate_cascade', label: '✓ Validating Objective Cascade' }
    ];

    // Display these steps in the progress panel
}
```

#### **C. Show Child Objectives Summary**

In the final review step, display child objectives count:

```javascript
function displayCampaignSummary(data) {
    // ... existing summary ...

    return `
        <div class="summary-section">
            <h6>Objectives Structure</h6>
            <p>Campaign Objectives: ${data.campaign_objectives?.length || 0}</p>
            <p>Quest Objectives: ${data.quest_objectives?.length || 0}</p>
            <p>Child Objectives: ${data.child_objectives?.length || 0}</p>
            <ul>
                <li>🔍 Discoveries: ${data.discovery_objectives?.length || 0}</li>
                <li>⚔️ Challenges: ${data.challenge_objectives?.length || 0}</li>
                <li>⭐ Events: ${data.event_objectives?.length || 0}</li>
                <li>💬 Conversations: ${data.conversation_objectives?.length || 0}</li>
            </ul>
        </div>
    `;
}
```

---

## 🔌 **3. Backend API Updates** (REQUIRED)

### **Game Engine API Endpoint**

**File:** `services/game-engine/app/routes/session_routes.py` (or similar)

Update the `/api/session/{session_id}/objectives/` endpoint to return child objectives:

```python
@router.get("/session/{session_id}/objectives/")
async def get_session_objectives(
    session_id: str,
    player_id: str,
    child_objectives: bool = True  # NEW parameter
):
    """
    Get objective progress for a player in a game session
    """
    # ... existing code to get campaign/quest objectives ...

    if child_objectives:
        # NEW: Query Neo4j for child objectives
        query = """
        MATCH (p:Player {player_id: $player_id})
        MATCH (co:QuestChildObjective)
        WHERE co.campaign_id = $campaign_id

        OPTIONAL MATCH (p)-[prog:PROGRESS]->(co)
        OPTIONAL MATCH (co)-[:AVAILABLE_IN]->(s:Scene)
        OPTIONAL MATCH (co)-[:EVALUATED_BY]->(r:Rubric)

        RETURN co, prog,
               collect(DISTINCT s.id) as available_scenes,
               collect(DISTINCT r.id) as rubric_ids
        ORDER BY co.objective_type, co.description
        """

        # Execute query and add to response
        child_objectives_data = await neo4j_graph.run_query(query, {
            "player_id": player_id,
            "campaign_id": campaign_id
        })

        # Group child objectives by quest objective
        response["quest_objectives"] = enrich_with_child_objectives(
            response["quest_objectives"],
            child_objectives_data
        )

    return response
```

### **WebSocket Event Registration**

**File:** `services/game-engine/app/websockets/game_session_ws.py` (or similar)

Ensure WebSocket publishes the new event types:

```python
# In your WebSocket message handler
async def handle_game_message(websocket, message):
    # ... existing message handling ...

    # NEW: Subscribe to child objective events
    await rabbitmq_client.subscribe(
        exchange="game.events",
        routing_keys=[
            f"session.{session_id}.child_objective_completed",
            f"session.{session_id}.quest_objective_completed",
            f"session.{session_id}.campaign_objective_completed",
            f"session.{session_id}.objective_cascade_update"
        ],
        callback=lambda event: websocket.send_json(event)
    )
```

---

## 📋 **Implementation Priority**

### **Phase 1: Critical (Must Have)**
1. ✅ Backend cascade system (DONE)
2. ✅ Database persistence (DONE)
3. ⚠️ **Game UI child objectives display** (THIS FILE)
4. ⚠️ **Game UI WebSocket event handlers** (THIS FILE)
5. ⚠️ **Backend API endpoint update** (Add child_objectives param)

### **Phase 2: Important (Should Have)**
6. Game UI rubric score display
7. Game UI objective hints
8. Campaign Factory progress display updates

### **Phase 3: Optional (Nice to Have)**
9. Campaign Factory child objectives preview step
10. Campaign Factory detailed summary
11. Game UI advanced animations
12. Game UI sound effects

---

## 🧪 **Testing Checklist**

### **Game UI Testing:**
- [ ] Child objectives display correctly in sidebar
- [ ] Objectives grouped by type (discovery, challenge, event, conversation)
- [ ] Required vs optional badges show correctly
- [ ] Hints display for each objective type
- [ ] Rubric scores display after completion
- [ ] Quality labels (excellent/good/minimal) show correctly
- [ ] Child objective completion triggers quest objective update
- [ ] Quest objective completion triggers campaign objective update
- [ ] Toast notifications show for all completion levels
- [ ] Animations play on completion
- [ ] WebSocket updates work in real-time

### **Campaign Factory Testing:**
- [ ] New workflow steps display during generation
- [ ] Child objectives count shows in summary
- [ ] Objective type breakdown displays correctly

---

## 📝 **Summary**

**Critical UI Updates Required:**
1. Game UI: Add child objectives display (4 types)
2. Game UI: Add rubric score display
3. Game UI: Add 4 new WebSocket event handlers
4. Backend API: Update objectives endpoint to return child objectives
5. Backend WebSocket: Publish new event types

**Estimated Effort:**
- Game UI updates: 4-6 hours
- Backend API updates: 1-2 hours
- Campaign Factory updates: 2-3 hours (optional)
- **Total Critical Path: 5-8 hours**

The backend is complete and functional. The UI updates are the final piece to make the hierarchical objective system fully operational!
