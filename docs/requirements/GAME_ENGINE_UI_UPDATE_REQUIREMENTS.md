# Game Engine & UI Update Requirements
## Integrating Objective Cascade & Neo4j Enhancements

**Status:** 🔴 **REQUIRED** - Game Engine and UI need significant updates
**Priority:** HIGH
**Estimated Effort:** 30-40 hours
**Impact:** Better player experience, objective tracking, and progression visibility

---

## **Executive Summary**

**YES - The Game Engine and Game UI absolutely need updates** to leverage the new objective cascade system and Neo4j enhancements implemented in the Campaign Design Wizard.

**Current State:**
- ✅ Game Engine tracks objectives but uses old flat structure
- ✅ Basic knowledge/item acquisition works
- ❌ No integration with new Neo4j objective hierarchy
- ❌ No UI display of objective cascade (campaign → quest → scene)
- ❌ No validation of objective achievability during gameplay
- ❌ No dimensional development visualization
- ❌ No redundancy-aware acquisition path guidance

**Required Changes:**
1. Update Game Engine to query new Neo4j objective graph
2. Add objective cascade display to Game UI
3. Show knowledge/item acquisition paths with redundancy info
4. Display dimensional development progress
5. Add scene-objective linkage visualization
6. Integrate validation system for runtime checks

---

## **Part 1: Game Engine Updates Required**

### **File: `services/game-engine/app/services/neo4j_graph.py`**

**Current Status:** Basic Neo4j integration for tracking player progress
**Required:** Enhanced queries to leverage new objective graph structure

#### **1.1 Add New Query Methods** (+200 lines)

```python
class Neo4jGraph:
    """Enhanced with objective cascade queries"""

    async def get_player_objective_progress(self, player_id: str, campaign_id: str) -> Dict:
        """
        Get player's progress on campaign and quest objectives.

        Returns:
        {
            "campaign_objectives": [
                {
                    "id": "...",
                    "description": "Discover the source of corruption",
                    "status": "in_progress",
                    "completion_percentage": 66,
                    "quest_objectives": [
                        {
                            "id": "...",
                            "description": "Investigate abandoned mine",
                            "status": "completed",
                            "completion_percentage": 100,
                            "completed_at": "2025-01-20T12:00:00Z"
                        }
                    ]
                }
            ],
            "overall_progress": 66
        }
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (camp:Campaign {id: $campaign_id})-[:HAS_OBJECTIVE]->(co:CampaignObjective)
                OPTIONAL MATCH (co)-[:DECOMPOSES_TO]->(qo:QuestObjective)
                OPTIONAL MATCH (p:Player {player_id: $player_id})-[prog:PROGRESS]->(qo)
                OPTIONAL MATCH (q:Quest)-[:ACHIEVES]->(qo)
                RETURN co,
                       collect(DISTINCT {
                           id: qo.id,
                           description: qo.description,
                           status: qo.status,
                           quest_name: q.name,
                           progress: prog.percentage,
                           completed_at: prog.completed_at
                       }) as quest_objectives
            """, campaign_id=campaign_id, player_id=player_id)

            # Process and return structured data
            # ...

    async def get_available_acquisition_paths(
        self,
        player_id: str,
        resource_id: str,
        resource_type: str  # "knowledge" or "item"
    ) -> List[Dict]:
        """
        Find all ways to acquire a knowledge/item, showing which paths
        are still available based on player's current scene.

        Returns:
        [
            {
                "method": "npc",
                "encounter_id": "npc_old_miner",
                "encounter_name": "Old Miner",
                "scene_id": "scene_flooded_shaft",
                "scene_name": "The Flooded Shaft",
                "available": True,  # Player hasn't acquired yet
                "redundancy_level": "high"  # 3+ paths exist
            },
            {
                "method": "discovery",
                "encounter_id": "disc_ancient_manual",
                "encounter_name": "Ancient Manual",
                "scene_id": "scene_flooded_shaft",
                "scene_name": "The Flooded Shaft",
                "available": True,
                "redundancy_level": "high"
            }
        ]
        """
        label = "Knowledge" if resource_type == "knowledge" else "Item"

        async with self.driver.session() as session:
            result = await session.run(f"""
                MATCH (r:{label} {{id: $resource_id}})
                MATCH (e)-[rel]->(r)
                WHERE type(rel) IN ['TEACHES', 'GIVES', 'REVEALS', 'CONTAINS', 'REWARDS', 'GRANTS']
                MATCH (s:Scene)-[:CONTAINS]->(e)

                // Check if player has already acquired this resource
                OPTIONAL MATCH (p:Player {{player_id: $player_id}})-[acq:ACQUIRED]->(r)

                // Get redundancy info
                WITH s, e, type(rel) as rel_type, acq, r.redundancy_paths as total_paths

                RETURN s.id as scene_id,
                       s.name as scene_name,
                       e.id as encounter_id,
                       e.name as encounter_name,
                       labels(e)[0] as encounter_type,
                       rel_type,
                       acq IS NULL as available,
                       CASE
                           WHEN total_paths >= 3 THEN 'high'
                           WHEN total_paths = 2 THEN 'medium'
                           ELSE 'low'
                       END as redundancy_level
                ORDER BY s.order_sequence
            """, resource_id=resource_id, player_id=player_id)

            # Process results...

    async def get_scene_objectives(self, scene_id: str) -> Dict:
        """
        Get all objectives that can be advanced in this scene.

        Returns:
        {
            "scene_id": "...",
            "scene_name": "The Flooded Shaft",
            "advances_quest_objectives": [
                {
                    "id": "...",
                    "description": "Investigate the flooded shaft",
                    "completion_criteria": ["Find 3 clues", "Collect 2 samples"]
                }
            ],
            "advances_campaign_objectives": [
                {
                    "id": "...",
                    "description": "Discover the source of corruption"
                }
            ],
            "provides_knowledge": [
                {
                    "id": "...",
                    "name": "Mining Safety",
                    "max_level": 3,
                    "acquisition_methods": ["npc", "discovery", "challenge"]
                }
            ],
            "provides_items": [
                {
                    "id": "...",
                    "name": "Sample Collection Kit",
                    "acquisition_methods": ["npc", "challenge"]
                }
            ]
        }
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (s:Scene {id: $scene_id})

                // Quest objectives
                OPTIONAL MATCH (s)-[:ADVANCES]->(qo:QuestObjective)

                // Campaign objectives
                OPTIONAL MATCH (s)-[:ADVANCES]->(co:CampaignObjective)

                // Knowledge provisions
                OPTIONAL MATCH (s)-[pk:PROVIDES]->(k:Knowledge)
                OPTIONAL MATCH (ek)-[rk]->(k)
                WHERE (s)-[:CONTAINS]->(ek)
                  AND type(rk) IN ['TEACHES', 'REVEALS', 'REWARDS', 'GRANTS']

                // Item provisions
                OPTIONAL MATCH (s)-[pi:PROVIDES]->(i:Item)
                OPTIONAL MATCH (ei)-[ri]->(i)
                WHERE (s)-[:CONTAINS]->(ei)
                  AND type(ri) IN ['GIVES', 'CONTAINS', 'REWARDS', 'GRANTS']

                RETURN s,
                       collect(DISTINCT qo) as quest_objectives,
                       collect(DISTINCT co) as campaign_objectives,
                       collect(DISTINCT {k: k, methods: collect(DISTINCT type(rk))}) as knowledge,
                       collect(DISTINCT {i: i, methods: collect(DISTINCT type(ri))}) as items
            """, scene_id=scene_id)

            # Process and return...

    async def get_dimensional_progress(self, player_id: str, campaign_id: str) -> Dict:
        """
        Get player's dimensional development progress.

        Returns:
        {
            "dimensions": [
                {
                    "name": "Physical",
                    "current_level": 3,
                    "target_level": 4,
                    "percentage": 75,
                    "knowledge_acquired": 5,
                    "knowledge_total": 7,
                    "challenges_completed": 8,
                    "challenges_total": 10
                }
            ]
        }
        """
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (d:Dimension)

                // Knowledge for this dimension in campaign
                OPTIONAL MATCH (k:Knowledge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)

                // Player's acquired knowledge
                OPTIONAL MATCH (p:Player {player_id: $player_id})-[acq:ACQUIRED]->(k)

                // Challenges for this dimension
                OPTIONAL MATCH (ch:Challenge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)
                OPTIONAL MATCH (p)-[comp:COMPLETED]->(ch)

                RETURN d.name as dimension_name,
                       count(DISTINCT k) as total_knowledge,
                       count(DISTINCT acq) as acquired_knowledge,
                       count(DISTINCT ch) as total_challenges,
                       count(DISTINCT comp) as completed_challenges
                ORDER BY d.name
            """, player_id=player_id, campaign_id=campaign_id)

            # Calculate levels and percentages...

    async def record_objective_progress(
        self,
        player_id: str,
        objective_id: str,
        objective_type: str,  # "campaign" or "quest"
        completion_percentage: int,
        metadata: Dict = None
    ):
        """
        Record player's progress on a specific objective.
        """
        async with self.driver.session() as session:
            label = "CampaignObjective" if objective_type == "campaign" else "QuestObjective"

            await session.run(f"""
                MATCH (p:Player {{player_id: $player_id}})
                MATCH (obj:{label} {{id: $objective_id}})
                MERGE (p)-[prog:PROGRESS]->(obj)
                SET prog.percentage = $percentage,
                    prog.updated_at = datetime(),
                    prog.metadata = $metadata,
                    prog.status = CASE
                        WHEN $percentage >= 100 THEN 'completed'
                        WHEN $percentage > 0 THEN 'in_progress'
                        ELSE 'not_started'
                    END
                SET obj.status = prog.status

                // If completed, set completion timestamp
                FOREACH (_ IN CASE WHEN $percentage >= 100 THEN [1] ELSE [] END |
                    SET prog.completed_at = datetime()
                )
            """,
            player_id=player_id,
            objective_id=objective_id,
            percentage=completion_percentage,
            metadata=metadata or {}
            )
```

**Estimated Effort:** 6-8 hours

---

### **File: `services/game-engine/app/managers/quest_tracker.py`**

**Current Status:** Tracks quest objectives based on simple conditions
**Required:** Integration with Neo4j objective hierarchy

#### **1.2 Enhanced Quest Tracker** (+150 lines)

```python
class QuestTracker:
    """Enhanced with objective cascade tracking"""

    async def check_objective_cascade(
        self,
        session_id: str,
        player_id: str,
        state: GameSessionState
    ) -> Dict:
        """
        Check progress on all levels of objective cascade:
        - Campaign objectives
        - Quest objectives
        - Scene objectives

        Returns progress report with UI updates.
        """
        campaign_id = state["campaign_id"]

        # Get current objective hierarchy progress
        progress = await neo4j_graph.get_player_objective_progress(
            player_id,
            campaign_id
        )

        # Check each quest objective for completion
        for camp_obj in progress["campaign_objectives"]:
            for quest_obj in camp_obj["quest_objectives"]:
                if quest_obj["status"] != "completed":
                    # Check if conditions are met
                    completion = await self._check_quest_objective_conditions(
                        quest_obj["id"],
                        player_id,
                        state
                    )

                    if completion["percentage"] > quest_obj.get("progress", 0):
                        # Progress made - record to Neo4j
                        await neo4j_graph.record_objective_progress(
                            player_id,
                            quest_obj["id"],
                            "quest",
                            completion["percentage"],
                            completion["metadata"]
                        )

                        # Broadcast update to UI
                        await connection_manager.broadcast_to_session(
                            session_id,
                            {
                                "event": "objective_progress",
                                "objective_id": quest_obj["id"],
                                "objective_description": quest_obj["description"],
                                "percentage": completion["percentage"],
                                "criteria_met": completion["criteria_met"]
                            }
                        )

        # Check campaign objectives
        for camp_obj in progress["campaign_objectives"]:
            quest_progress = [
                qo["progress"] for qo in camp_obj["quest_objectives"]
            ]
            campaign_percentage = sum(quest_progress) / len(quest_progress) if quest_progress else 0

            if campaign_percentage != camp_obj.get("completion_percentage", 0):
                await neo4j_graph.record_objective_progress(
                    player_id,
                    camp_obj["id"],
                    "campaign",
                    int(campaign_percentage)
                )

                await connection_manager.broadcast_to_session(
                    session_id,
                    {
                        "event": "campaign_objective_progress",
                        "objective_id": camp_obj["id"],
                        "objective_description": camp_obj["description"],
                        "percentage": campaign_percentage
                    }
                )

        return progress

    async def _check_quest_objective_conditions(
        self,
        quest_objective_id: str,
        player_id: str,
        state: GameSessionState
    ) -> Dict:
        """
        Check if quest objective conditions are met based on:
        - Knowledge acquired
        - Items collected
        - Scenes visited
        - NPCs talked to
        - Challenges completed
        """
        # Get objective definition from Neo4j
        async with neo4j_graph.driver.session() as session:
            result = await session.run("""
                MATCH (qo:QuestObjective {id: $obj_id})
                OPTIONAL MATCH (qo)-[:REQUIRES_KNOWLEDGE]->(k:Knowledge)
                OPTIONAL MATCH (qo)-[:REQUIRES_ITEM]->(i:Item)
                RETURN qo.success_criteria as criteria,
                       collect(DISTINCT k.id) as required_knowledge,
                       collect(DISTINCT i.id) as required_items
            """, obj_id=quest_objective_id)

            data = await result.single()

        criteria_met = []
        criteria_total = len(data["criteria"])

        # Check each criterion
        for criterion in data["criteria"]:
            # Parse criterion (e.g., "Find 3 clues", "Collect 2 samples")
            met = await self._check_criterion(
                criterion,
                player_id,
                state,
                data["required_knowledge"],
                data["required_items"]
            )
            if met:
                criteria_met.append(criterion)

        percentage = (len(criteria_met) / criteria_total * 100) if criteria_total > 0 else 0

        return {
            "percentage": percentage,
            "criteria_met": criteria_met,
            "criteria_total": criteria_total,
            "metadata": {
                "knowledge_progress": len([
                    k for k in data["required_knowledge"]
                    if k in state["player_knowledge"].get(player_id, {})
                ]),
                "items_progress": len([
                    i for i in data["required_items"]
                    if any(inv["item_id"] == i for inv in state["player_inventories"].get(player_id, []))
                ])
            }
        }
```

**Estimated Effort:** 6-8 hours

---

### **File: `services/game-engine/app/workflows/game_loop.py`**

**Current Status:** LangGraph workflow for game state management
**Required:** Add objective checking node

#### **1.3 Add Objective Check Node** (+50 lines)

```python
async def check_objectives_node(state: GameSessionState) -> GameSessionState:
    """
    Check all objective progress after player action.
    """
    session_id = state["session_id"]
    player_id = state["current_player_id"]

    # Check objective cascade
    progress = await quest_tracker.check_objective_cascade(
        session_id,
        player_id,
        state
    )

    # Update state with current objective status
    state["objective_progress"] = progress

    # Check for completed quests
    for camp_obj in progress["campaign_objectives"]:
        for quest_obj in camp_obj["quest_objectives"]:
            if quest_obj["status"] == "completed" and quest_obj["id"] not in state.get("completed_quest_ids", []):
                # Quest just completed
                await handle_quest_completion(state, quest_obj["quest_id"])

    return state

# Add to workflow
workflow.add_node("check_objectives", check_objectives_node)

# Update edges
workflow.add_edge("process_action", "check_objectives")
workflow.add_edge("check_objectives", "generate_response")
```

**Estimated Effort:** 2-3 hours

---

## **Part 2: Game UI Updates Required**

### **File: `services/django-web/templates/game/session.html`**

**Current Status:** Basic game session UI with chat and scene description
**Required:** Add objective display panels

#### **2.1 Add Objective Cascade Panel** (+300 lines HTML/CSS)

**New UI Components:**

1. **Objective Progress Sidebar**
```html
<!-- Add to session.html -->
<div class="objectives-panel" style="position: fixed; right: 20px; top: 80px; width: 350px; background: rgba(27, 27, 46, 0.95); padding: 20px; border-radius: 8px; max-height: calc(100vh - 100px); overflow-y: auto;">
    <h5 style="color: var(--rpg-gold); margin-top: 0;">
        <i class="material-icons tiny">flag</i> Campaign Objectives
    </h5>

    <div id="campaign-objectives-list">
        <!-- Populated via JavaScript -->
    </div>

    <h6 style="color: var(--rpg-silver); margin-top: 20px;">
        <i class="material-icons tiny">assignment</i> Current Quest
    </h6>

    <div id="quest-objectives-list">
        <!-- Populated via JavaScript -->
    </div>

    <h6 style="color: var(--rpg-silver); margin-top: 20px;">
        <i class="material-icons tiny">location_on</i> This Scene
    </h6>

    <div id="scene-objectives-list">
        <!-- Populated via JavaScript -->
    </div>
</div>
```

2. **Objective Card Template** (JavaScript)
```javascript
function renderCampaignObjective(objective) {
    const percentage = objective.completion_percentage || 0;
    const color = percentage === 100 ? 'var(--rpg-green)' : percentage > 0 ? 'var(--rpg-purple)' : 'var(--rpg-silver)';

    return `
        <div class="objective-card" style="margin-bottom: 15px; padding: 12px; background: rgba(106, 90, 205, 0.1); border-left: 3px solid ${color}; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: var(--rpg-gold); font-weight: bold; flex: 1;">${objective.description}</span>
                <span style="color: ${color}; font-size: 0.9rem; font-weight: bold;">${percentage}%</span>
            </div>

            <!-- Progress bar -->
            <div style="margin-top: 8px; height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                <div style="height: 100%; background: ${color}; width: ${percentage}%;"></div>
            </div>

            <!-- Quest objectives under this campaign objective -->
            <div class="quest-objectives" style="margin-top: 10px; padding-left: 15px;">
                ${objective.quest_objectives.map(qo => renderQuestObjective(qo)).join('')}
            </div>
        </div>
    `;
}

function renderQuestObjective(questObj) {
    const status = questObj.status || 'not_started';
    const icon = status === 'completed' ? 'check_circle' : status === 'in_progress' ? 'pending' : 'radio_button_unchecked';
    const color = status === 'completed' ? 'var(--rpg-green)' : status === 'in_progress' ? 'var(--rpg-purple)' : 'var(--rpg-silver)';

    return `
        <div style="margin-bottom: 8px; display: flex; align-items: start; gap: 8px;">
            <i class="material-icons tiny" style="color: ${color}; margin-top: 2px;">${icon}</i>
            <div style="flex: 1;">
                <span style="color: #b8b8d1; font-size: 0.9rem;">${questObj.description}</span>
                ${questObj.progress ? `
                    <div style="margin-top: 4px; font-size: 0.8rem; color: var(--rpg-silver);">
                        ${questObj.progress}% complete
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}
```

3. **Knowledge/Item Acquisition Panel**
```html
<div class="resources-panel" style="margin-top: 20px; padding: 15px; background: rgba(27, 27, 46, 0.6); border-radius: 8px;">
    <h6 style="color: var(--rpg-gold); margin-top: 0;">
        <i class="material-icons tiny">school</i> Available in This Scene
    </h6>

    <div id="scene-knowledge-list">
        <!-- Knowledge items that can be acquired here -->
    </div>

    <div id="scene-items-list">
        <!-- Items that can be acquired here -->
    </div>
</div>
```

4. **Resource Card with Acquisition Paths**
```javascript
function renderSceneResource(resource, type) {
    const icon = type === 'knowledge' ? 'school' : 'inventory_2';
    const color = type === 'knowledge' ? 'var(--rpg-purple)' : '#FFC107';

    // Show redundancy indicator
    const redundancyColor = {
        'high': 'var(--rpg-green)',
        'medium': '#FFC107',
        'low': '#f44336'
    }[resource.redundancy_level || 'low'];

    return `
        <div class="resource-card" style="margin-bottom: 10px; padding: 10px; background: rgba(255, 255, 255, 0.05); border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <i class="material-icons tiny" style="color: ${color};">${icon}</i>
                <span style="color: ${color}; font-weight: bold; flex: 1;">${resource.name}</span>
                <span style="font-size: 0.75rem; color: ${redundancyColor};">
                    ${resource.acquisition_methods.length} path${resource.acquisition_methods.length > 1 ? 's' : ''}
                </span>
            </div>

            <div style="font-size: 0.85rem; color: #b8b8d1; margin-bottom: 8px;">
                ${resource.description}
            </div>

            <!-- Acquisition methods -->
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                ${resource.acquisition_methods.map(method => `
                    <span class="chip" style="background: rgba(106, 90, 205, 0.2); color: var(--rpg-purple); font-size: 0.75rem; padding: 2px 8px; border-radius: 12px;">
                        ${getMethodIcon(method)} ${method}
                    </span>
                `).join('')}
            </div>
        </div>
    `;
}

function getMethodIcon(method) {
    const icons = {
        'npc': '💬',
        'discovery': '🔍',
        'challenge': '⚔️',
        'event': '⭐'
    };
    return icons[method] || '•';
}
```

5. **Dimensional Development Panel**
```html
<div class="dimensions-panel" style="margin-top: 20px; padding: 15px; background: rgba(27, 27, 46, 0.6); border-radius: 8px;">
    <h6 style="color: var(--rpg-gold); margin-top: 0;">
        <i class="material-icons tiny">psychology</i> Dimensional Development
    </h6>

    <div id="dimensions-list">
        <!-- 7 dimensions with progress bars -->
    </div>
</div>
```

```javascript
function renderDimensionalProgress(dimensions) {
    return dimensions.map(dim => {
        const percentage = dim.percentage || 0;
        const color = percentage >= 75 ? 'var(--rpg-green)' : percentage >= 50 ? 'var(--rpg-purple)' : 'var(--rpg-silver)';

        return `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #b8b8d1; font-size: 0.85rem;">${dim.name}</span>
                    <span style="color: ${color}; font-size: 0.85rem;">${percentage}%</span>
                </div>
                <div style="height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                    <div style="height: 100%; background: ${color}; width: ${percentage}%; transition: width 0.3s;"></div>
                </div>
                <div style="margin-top: 2px; font-size: 0.75rem; color: var(--rpg-silver);">
                    Knowledge: ${dim.acquired_knowledge}/${dim.total_knowledge} |
                    Challenges: ${dim.completed_challenges}/${dim.total_challenges}
                </div>
            </div>
        `;
    }).join('');
}
```

**Estimated Effort:** 8-10 hours

---

### **File: `services/django-web/static/js/game_session.js`** (New File)

**Required:** WebSocket handlers for objective updates

#### **2.2 WebSocket Event Handlers** (+200 lines)

```javascript
// Add to existing WebSocket message handler
websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);

    switch(data.event) {
        case 'objective_progress':
            handleObjectiveProgress(data);
            break;
        case 'campaign_objective_progress':
            handleCampaignObjectiveProgress(data);
            break;
        case 'quest_completed':
            handleQuestCompleted(data);
            break;
        case 'knowledge_acquired':
            handleKnowledgeAcquired(data);
            break;
        case 'item_acquired':
            handleItemAcquired(data);
            break;
        case 'dimensional_progress':
            handleDimensionalProgress(data);
            break;
        // ... existing cases
    }
};

function handleObjectiveProgress(data) {
    // Update quest objective UI
    const objectiveCard = document.querySelector(`[data-objective-id="${data.objective_id}"]`);
    if (objectiveCard) {
        // Update progress bar
        const progressBar = objectiveCard.querySelector('.progress-bar');
        progressBar.style.width = `${data.percentage}%`;

        // Update percentage text
        const percentageText = objectiveCard.querySelector('.percentage-text');
        percentageText.textContent = `${data.percentage}%`;

        // Update status icon
        if (data.percentage === 100) {
            const icon = objectiveCard.querySelector('.status-icon');
            icon.textContent = 'check_circle';
            icon.style.color = 'var(--rpg-green)';
        }
    }

    // Show toast notification
    M.toast({
        html: `<i class="material-icons tiny">check</i> Objective progress: ${data.objective_description} (${data.percentage}%)`,
        classes: 'purple'
    });

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
        progressBar.style.width = `${data.percentage}%`;

        const percentageText = campaignCard.querySelector('.campaign-percentage');
        percentageText.textContent = `${data.percentage}%`;
    }
}

function triggerObjectiveCompletionAnimation(objectiveId) {
    const card = document.querySelector(`[data-objective-id="${objectiveId}"]`);
    if (card) {
        card.classList.add('objective-completed-animation');

        // Confetti or celebration effect
        confetti({
            particleCount: 100,
            spread: 70,
            origin: { y: 0.6 }
        });

        // Play success sound
        const audio = new Audio('/static/sounds/objective_complete.mp3');
        audio.play();
    }
}

function loadObjectiveProgress(sessionId) {
    // Fetch initial objective state when page loads
    fetch(`/api/game-session/${sessionId}/objectives`)
        .then(response => response.json())
        .then(data => {
            // Render campaign objectives
            const campaignList = document.getElementById('campaign-objectives-list');
            campaignList.innerHTML = data.campaign_objectives.map(renderCampaignObjective).join('');

            // Render current quest objectives
            const questList = document.getElementById('quest-objectives-list');
            questList.innerHTML = data.current_quest_objectives.map(renderQuestObjective).join('');

            // Render scene resources
            const knowledgeList = document.getElementById('scene-knowledge-list');
            knowledgeList.innerHTML = data.scene_knowledge.map(k => renderSceneResource(k, 'knowledge')).join('');

            const itemsList = document.getElementById('scene-items-list');
            itemsList.innerHTML = data.scene_items.map(i => renderSceneResource(i, 'item')).join('');

            // Render dimensional progress
            const dimensionsList = document.getElementById('dimensions-list');
            dimensionsList.innerHTML = renderDimensionalProgress(data.dimensions);
        });
}

// Call on page load
document.addEventListener('DOMContentLoaded', function() {
    const sessionId = document.body.dataset.sessionId;
    loadObjectiveProgress(sessionId);
});
```

**Estimated Effort:** 6-8 hours

---

## **Part 3: New API Endpoints Required**

### **File: `services/game-engine/app/api/routes.py`**

#### **3.1 Add Objective Endpoints** (+100 lines)

```python
@router.get("/session/{session_id}/objectives")
async def get_session_objectives(
    session_id: str,
    player_id: str = Query(...)
):
    """
    Get all objective progress for a player in a session.

    Returns:
    - Campaign objectives with progress
    - Current quest objectives
    - Scene objectives (what can be done in current scene)
    - Knowledge/items available in scene
    - Dimensional development progress
    """
    state = await redis_manager.get_session_state(session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    campaign_id = state["campaign_id"]
    current_scene_id = state.get("current_scene_id")

    # Get objective progress from Neo4j
    progress = await neo4j_graph.get_player_objective_progress(player_id, campaign_id)

    # Get scene objectives and resources
    scene_data = await neo4j_graph.get_scene_objectives(current_scene_id) if current_scene_id else {}

    # Get dimensional progress
    dimensions = await neo4j_graph.get_dimensional_progress(player_id, campaign_id)

    # Get available acquisition paths for scene resources
    scene_knowledge = []
    for knowledge in scene_data.get("provides_knowledge", []):
        paths = await neo4j_graph.get_available_acquisition_paths(
            player_id,
            knowledge["id"],
            "knowledge"
        )
        scene_knowledge.append({
            **knowledge,
            "acquisition_paths": paths,
            "redundancy_level": paths[0]["redundancy_level"] if paths else "low"
        })

    scene_items = []
    for item in scene_data.get("provides_items", []):
        paths = await neo4j_graph.get_available_acquisition_paths(
            player_id,
            item["id"],
            "item"
        )
        scene_items.append({
            **item,
            "acquisition_paths": paths,
            "redundancy_level": paths[0]["redundancy_level"] if paths else "low"
        })

    return {
        "campaign_objectives": progress["campaign_objectives"],
        "current_quest_objectives": [
            qo for co in progress["campaign_objectives"]
            for qo in co["quest_objectives"]
            if qo["status"] in ["not_started", "in_progress"]
        ],
        "scene_objectives": scene_data.get("advances_quest_objectives", []),
        "scene_knowledge": scene_knowledge,
        "scene_items": scene_items,
        "dimensions": dimensions["dimensions"],
        "overall_progress": progress["overall_progress"]
    }

@router.get("/session/{session_id}/knowledge/{knowledge_id}/paths")
async def get_knowledge_acquisition_paths(
    session_id: str,
    knowledge_id: str,
    player_id: str = Query(...)
):
    """
    Get all ways to acquire a specific knowledge item.
    Shows which paths are still available.
    """
    paths = await neo4j_graph.get_available_acquisition_paths(
        player_id,
        knowledge_id,
        "knowledge"
    )

    return {
        "knowledge_id": knowledge_id,
        "paths": paths,
        "total_paths": len(paths),
        "available_paths": len([p for p in paths if p["available"]]),
        "redundancy_level": paths[0]["redundancy_level"] if paths else "low"
    }

@router.get("/session/{session_id}/dimensional-progress")
async def get_dimensional_development(
    session_id: str,
    player_id: str = Query(...)
):
    """
    Get player's dimensional development progress.
    """
    state = await redis_manager.get_session_state(session_id)
    if not state:
        raise HTTPException(404, "Session not found")

    campaign_id = state["campaign_id"]
    dimensions = await neo4j_graph.get_dimensional_progress(player_id, campaign_id)

    return dimensions
```

**Estimated Effort:** 4-5 hours

---

## **Part 4: Implementation Timeline**

### **Sprint 1: Backend Foundation** (2 weeks, 40 hours)

**Week 1:**
- [ ] **Day 1-2:** Enhance `neo4j_graph.py` with new query methods (8 hours)
  - `get_player_objective_progress()`
  - `get_available_acquisition_paths()`
  - `get_scene_objectives()`
  - `get_dimensional_progress()`
  - `record_objective_progress()`

- [ ] **Day 3-4:** Update `quest_tracker.py` (8 hours)
  - `check_objective_cascade()`
  - `_check_quest_objective_conditions()`
  - Integration with Neo4j queries

- [ ] **Day 5:** Add objective check node to `game_loop.py` (4 hours)
  - Workflow integration
  - State updates

**Week 2:**
- [ ] **Day 1-2:** Create new API endpoints in `routes.py` (8 hours)
  - `/session/{id}/objectives`
  - `/session/{id}/knowledge/{id}/paths`
  - `/session/{id}/dimensional-progress`

- [ ] **Day 3-5:** Testing & bug fixes (12 hours)
  - Unit tests for Neo4j queries
  - Integration tests for quest tracker
  - API endpoint testing

---

### **Sprint 2: Frontend UI** (1.5 weeks, 30 hours)

**Week 3:**
- [ ] **Day 1-2:** Create objective panel UI components (10 hours)
  - HTML structure in `session.html`
  - CSS styling for panels
  - Responsive layout

- [ ] **Day 3-4:** JavaScript WebSocket handlers (10 hours)
  - Event handlers for objective updates
  - Rendering functions
  - Animation effects

- [ ] **Day 5:** Knowledge/item acquisition UI (6 hours)
  - Resource cards
  - Acquisition path display
  - Redundancy indicators

**Week 4:**
- [ ] **Day 1:** Dimensional development panel (4 hours)
  - Progress bars
  - Statistics display

- [ ] **Day 2-3:** Testing & polish (10 hours)
  - Cross-browser testing
  - UX refinements
  - Performance optimization

---

### **Sprint 3: Polish & Deploy** (1 week, 20 hours)

- [ ] **Day 1-2:** Integration testing (8 hours)
  - End-to-end gameplay testing
  - Objective progression verification
  - Neo4j data validation

- [ ] **Day 3:** Documentation (4 hours)
  - Update player guide
  - Developer documentation
  - API documentation

- [ ] **Day 4:** Bug fixes and refinement (6 hours)
  - Address QA feedback
  - Performance tuning

- [ ] **Day 5:** Deployment (2 hours)
  - Production deployment
  - Monitoring setup

---

## **Total Effort Estimate**

| Component | Hours |
|-----------|-------|
| **Backend Updates** | 40 |
| **Frontend UI** | 30 |
| **Testing & Polish** | 20 |
| **Documentation** | 4 |
| **Deployment** | 2 |
| **Total** | **96 hours** (~2.5 weeks full-time) |

---

## **Priority Levels**

### **P0 - Critical (Must Have)** ✅

These are essential for basic functionality:

1. ✅ Enhanced Neo4j queries (`get_player_objective_progress`, `get_scene_objectives`)
2. ✅ Basic objective panel in UI (campaign and quest objectives)
3. ✅ WebSocket handlers for objective progress events
4. ✅ `/session/{id}/objectives` API endpoint
5. ✅ Update `quest_tracker.py` to use Neo4j objective hierarchy

**Estimated:** 30 hours

---

### **P1 - High (Should Have)** 📊

Nice to have for better UX:

1. 📊 Knowledge/item acquisition path display
2. 📊 Redundancy indicators
3. 📊 Dimensional development panel
4. 📊 Scene resources panel
5. 📊 Objective completion animations

**Estimated:** 25 hours

---

### **P2 - Medium (Nice to Have)** 🎨

Polish and advanced features:

1. 🎨 Interactive objective tree visualization
2. 🎨 Acquisition path recommendations ("Try talking to...")
3. 🎨 Progress analytics dashboard
4. 🎨 Achievement system based on objectives
5. 🎨 Sound effects and celebrations

**Estimated:** 20 hours

---

## **Benefits of Implementation**

### **For Players:**
- ✅ Clear visibility of what to do next
- ✅ Understanding of multiple paths to success
- ✅ Progress tracking across campaign, quest, and scene levels
- ✅ Dimensional development awareness
- ✅ Reduced confusion about objectives

### **For Developers:**
- ✅ Consistent objective tracking system
- ✅ Better game analytics
- ✅ Foundation for AI-driven recommendations
- ✅ Reduced support tickets about "what do I do?"

### **For System:**
- ✅ Full utilization of Neo4j graph capabilities
- ✅ Real-time objective validation
- ✅ Foundation for future features (achievements, leaderboards)
- ✅ Better player retention metrics

---

## **Risk Assessment**

### **Low Risk:**
- Adding new API endpoints (backward compatible)
- New UI panels (additive, doesn't break existing)
- Neo4j query methods (read-only operations)

### **Medium Risk:**
- WebSocket message handling (existing messages still work)
- Quest tracker changes (need thorough testing)

### **High Risk:**
- None identified (all changes are additive)

---

## **Rollout Strategy**

### **Phase 1: Backend Only** (Week 1-2)
- Deploy enhanced Neo4j queries
- Update quest tracker
- Add API endpoints
- **No UI changes yet** - test in isolation

### **Phase 2: UI Beta** (Week 3)
- Deploy UI panels as "beta feature"
- Toggle flag for enabling/disabling
- Gather user feedback

### **Phase 3: Full Release** (Week 4)
- Enable for all users
- Monitor analytics
- Iterate based on feedback

---

## **Success Metrics**

Track these metrics to measure success:

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Player completion rate | Baseline | +30% | Sessions where quest completed |
| "What do I do?" support tickets | Baseline | -50% | Support ticket count |
| Average session duration | Baseline | +20% | Session time analytics |
| Objective clarity rating | Unknown | 4.5/5 | Player survey |
| Redundancy utilization | 0% | 60% | Players using 2+ paths |

---

## **Next Steps**

### **Immediate Actions:**

1. **Review & Approve** this plan with stakeholders
2. **Prioritize** features (P0, P1, P2)
3. **Assign** resources (1-2 developers)
4. **Schedule** sprints (2.5 weeks estimated)
5. **Create** tickets in project management system

### **Pre-Implementation Checklist:**

- [ ] Stakeholder approval
- [ ] Neo4j indexes created (for performance)
- [ ] Testing environment set up
- [ ] UI mockups reviewed
- [ ] API contract agreed upon
- [ ] Documentation template prepared

---

## **Conclusion**

**ANSWER: YES - The Game Engine and UI definitely need updates.**

The Campaign Design Wizard now creates a rich objective cascade and Neo4j graph structure that the Game Engine is not currently leveraging. Implementing these updates will:

- ✅ Significantly improve player experience
- ✅ Reduce player confusion about objectives
- ✅ Provide clear progression visibility
- ✅ Enable future AI-driven features
- ✅ Fully utilize Neo4j capabilities (30% → 90%)

**Recommended Approach:** Start with **P0 (Critical) features** in Sprint 1 to get core functionality working, then iterate with P1 and P2 features based on user feedback.

**Total Investment:** ~96 hours (~2.5 weeks full-time)
**Expected ROI:** 30% increase in completion rate, 50% reduction in support tickets

---

**Status:** 📋 **Ready for Implementation Planning**
