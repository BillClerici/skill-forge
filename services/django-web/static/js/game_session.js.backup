/**
 * Game Session Objectives UI
 * Handles objective progress display and WebSocket updates
 */

// Global variables
let currentSessionId = null;
let currentPlayerId = null;
let objectivesLoaded = false;

// ============================================
// Initialization
// ============================================

function initializeObjectivesPanel() {
    console.log('Initializing objectives panel...');

    // Get session and player ID from global variables defined in session.html
    // or fallback to data attributes/URL
    currentSessionId = (typeof SESSION_ID !== 'undefined' && SESSION_ID) ? SESSION_ID :
                      (document.body.dataset.sessionId ||
                       new URLSearchParams(window.location.search).get('session_id'));
    currentPlayerId = (typeof PLAYER_ID !== 'undefined' && PLAYER_ID) ? PLAYER_ID :
                     (document.body.dataset.playerId ||
                      new URLSearchParams(window.location.search).get('player_id'));

    console.log('Session ID:', currentSessionId, 'Player ID:', currentPlayerId);

    if (currentSessionId && currentPlayerId) {
        // Load objective progress
        loadObjectiveProgress(currentSessionId, currentPlayerId);

        // Refresh every 30 seconds
        setInterval(() => {
            loadObjectiveProgress(currentSessionId, currentPlayerId);
        }, 30000);
    } else {
        console.warn('Session ID or Player ID not found. Objectives will not load.');
        document.getElementById('campaign-objectives-list').innerHTML =
            '<p style="color: #f44336; font-size: 0.85rem; text-align: center;">Session or player data missing</p>';
    }

    // Setup toggle button
    const toggleBtn = document.getElementById('toggle-objectives-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleObjectivesSidebar);
    }
}

function toggleObjectivesSidebar() {
    const sidebar = document.getElementById('objectives-sidebar');
    const icon = document.querySelector('#toggle-objectives-btn i');

    if (!sidebar || !icon) return;

    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        icon.textContent = 'chevron_right';
    } else {
        sidebar.classList.add('collapsed');
        icon.textContent = 'chevron_left';
    }
}

// ============================================
// API Calls
// ============================================

async function loadObjectiveProgress(sessionId, playerId) {
    try {
        // Call Django proxy (which connects to game engine internally)
        const response = await fetch(
            `/api/session/${sessionId}/objectives/?player_id=${playerId}`
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Objectives data loaded:', data);

        objectivesLoaded = true;
        renderObjectivesData(data);

    } catch (error) {
        console.error('Failed to load objectives:', error);
        document.getElementById('campaign-objectives-list').innerHTML =
            `<p style="color: #f44336; font-size: 0.85rem; text-align: center; padding: 10px;">
                Failed to load objectives<br>
                <span style="font-size: 0.75rem; opacity: 0.8;">${error.message}</span>
            </p>`;
    }
}

// ============================================
// Render Functions
// ============================================

function renderObjectivesData(data) {
    // Update overall progress badge
    const progressBadge = document.getElementById('overall-progress-badge');
    if (progressBadge) {
        progressBadge.textContent = `${data.overall_progress || 0}%`;
    }

    // Render campaign objectives
    const campaignList = document.getElementById('campaign-objectives-list');
    if (campaignList) {
        if (data.campaign_objectives && data.campaign_objectives.length > 0) {
            campaignList.innerHTML = data.campaign_objectives
                .map(renderCampaignObjective)
                .join('');
        } else {
            campaignList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center; padding: 10px;">No objectives yet</p>';
        }
    }

    // Render current quest objectives
    const questList = document.getElementById('quest-objectives-list');
    if (questList) {
        if (data.current_quest_objectives && data.current_quest_objectives.length > 0) {
            questList.innerHTML = data.current_quest_objectives
                .map(renderQuestObjective)
                .join('');
        } else {
            questList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center;">No active quest objectives</p>';
        }
    }

    // Render scene objectives
    const sceneList = document.getElementById('scene-objectives-list');
    if (sceneList) {
        if (data.scene_objectives && data.scene_objectives.length > 0) {
            sceneList.innerHTML = data.scene_objectives
                .map(obj => `
                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px;">
                        <div style="color: #b8b8d1; font-size: 0.85rem;">${obj.description || 'Objective'}</div>
                    </div>
                `).join('');
        } else {
            sceneList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center;">No scene objectives</p>';
        }
    }

    // Render scene knowledge
    const knowledgeList = document.getElementById('scene-knowledge-list');
    if (knowledgeList) {
        if (data.scene_knowledge && data.scene_knowledge.length > 0) {
            knowledgeList.innerHTML = data.scene_knowledge
                .map(k => renderSceneResource(k, 'knowledge'))
                .join('');
        } else {
            knowledgeList.innerHTML = '';
        }
    }

    // Render scene items
    const itemsList = document.getElementById('scene-items-list');
    if (itemsList) {
        if (data.scene_items && data.scene_items.length > 0) {
            itemsList.innerHTML = data.scene_items
                .map(i => renderSceneResource(i, 'item'))
                .join('');
        } else {
            itemsList.innerHTML = '';
        }
    }

    // Render dimensional progress
    const dimensionsList = document.getElementById('dimensions-list');
    if (dimensionsList) {
        if (data.dimensions && data.dimensions.length > 0) {
            dimensionsList.innerHTML = renderDimensionalProgress(data.dimensions);
        } else {
            dimensionsList.innerHTML = '<p style="color: #888; font-size: 0.85rem; text-align: center;">No dimensional data</p>';
        }
    }
}

function renderCampaignObjective(objective) {
    const percentage = objective.completion_percentage || 0;
    const color = percentage === 100 ? '#4CAF50' : percentage > 0 ? '#6A5ACD' : '#C0C0C0';

    return `
        <div class="objective-card"
             data-campaign-objective-id="${objective.id}"
             style="margin-bottom: 15px; padding: 12px; background: rgba(106, 90, 205, 0.1); border-left: 3px solid ${color}; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="color: #FFD700; font-weight: bold; flex: 1; font-size: 0.9rem;">${objective.description || 'Campaign Objective'}</span>
                <span class="campaign-percentage" style="color: ${color}; font-size: 0.85rem; font-weight: bold;">${percentage}%</span>
            </div>

            <!-- Progress bar -->
            <div style="margin-top: 8px; height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                <div class="campaign-progress-bar" style="height: 100%; background: ${color}; width: ${percentage}%; transition: width 0.5s ease;"></div>
            </div>

            <!-- Quest objectives under this campaign objective -->
            <div class="quest-objectives" style="margin-top: 10px; padding-left: 10px;">
                ${(objective.quest_objectives || []).map(qo => renderQuestObjective(qo)).join('')}
            </div>
        </div>
    `;
}

function renderQuestObjective(questObj) {
    const status = questObj.status || 'not_started';
    const icon = status === 'completed' ? 'check_circle' : status === 'in_progress' ? 'pending' : 'radio_button_unchecked';
    const color = status === 'completed' ? '#4CAF50' : status === 'in_progress' ? '#6A5ACD' : '#C0C0C0';
    const progress = questObj.progress || 0;

    return `
        <div data-objective-id="${questObj.id}" style="margin-bottom: 8px; display: flex; align-items: start; gap: 8px;">
            <i class="material-icons tiny status-icon" style="color: ${color}; margin-top: 2px; font-size: 16px;">${icon}</i>
            <div style="flex: 1;">
                <span style="color: #b8b8d1; font-size: 0.85rem;">${questObj.description || 'Quest Objective'}</span>
                ${progress > 0 ? `
                    <div class="progress-bar" style="margin-top: 4px; height: 4px; background: rgba(192, 192, 192, 0.2); border-radius: 2px; overflow: hidden;">
                        <div style="height: 100%; background: ${color}; width: ${progress}%; transition: width 0.5s ease;"></div>
                    </div>
                    <div class="percentage-text" style="margin-top: 2px; font-size: 0.75rem; color: ${color};">
                        ${progress}% complete
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
                <span style="color: ${color}; font-weight: bold; flex: 1; font-size: 0.85rem;">${resource.name || 'Resource'}</span>
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
    if (!dimensions || dimensions.length === 0) {
        return '<p style="color: #888; font-size: 0.85rem; text-align: center;">No dimensional data</p>';
    }

    return dimensions.map(dim => {
        const percentage = dim.percentage || 0;
        const color = percentage >= 75 ? '#4CAF50' : percentage >= 50 ? '#6A5ACD' : '#C0C0C0';

        return `
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #b8b8d1; font-size: 0.8rem;">${dim.name || 'Dimension'}</span>
                    <span style="color: ${color}; font-size: 0.8rem; font-weight: bold;">${percentage}%</span>
                </div>
                <div style="height: 6px; background: rgba(192, 192, 192, 0.2); border-radius: 3px; overflow: hidden;">
                    <div style="height: 100%; background: ${color}; width: ${percentage}%; transition: width 0.5s;"></div>
                </div>
                <div style="margin-top: 2px; font-size: 0.7rem; color: #888;">
                    Knowledge: ${dim.knowledge_acquired || 0}/${dim.knowledge_total || 0} |
                    Challenges: ${dim.challenges_completed || 0}/${dim.challenges_total || 0}
                </div>
            </div>
        `;
    }).join('');
}

// ============================================
// WebSocket Event Handlers
// ============================================

function handleObjectiveProgress(data) {
    console.log('Objective progress update:', data);

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
    showObjectiveToast(data.objective_description, data.percentage);

    // Trigger celebration animation if completed
    if (data.percentage === 100) {
        triggerObjectiveCompletionAnimation(data.objective_id);
    }
}

function handleCampaignObjectiveProgress(data) {
    console.log('Campaign objective progress update:', data);

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

    // Update overall progress badge
    const overallBadge = document.getElementById('overall-progress-badge');
    if (overallBadge) {
        overallBadge.textContent = `${data.percentage}%`;
    }

    // Show toast notification
    showObjectiveToast(`Campaign: ${data.objective_description}`, data.percentage);
}

function showObjectiveToast(description, percentage) {
    // Check if Materialize toast is available
    if (typeof M !== 'undefined' && M.toast) {
        M.toast({
            html: `<i class="material-icons tiny">check</i> ${description} (${percentage}%)`,
            classes: 'purple',
            displayLength: 3000
        });
    } else {
        console.log(`Objective update: ${description} - ${percentage}%`);
    }
}

function triggerObjectiveCompletionAnimation(objectiveId) {
    const card = document.querySelector(`[data-objective-id="${objectiveId}"]`);
    if (card) {
        // Add pulse animation
        card.classList.add('objective-completed-animation');
        setTimeout(() => {
            card.classList.remove('objective-completed-animation');
        }, 500);

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

// ============================================
// Initialize on DOM Ready
// ============================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeObjectivesPanel);
} else {
    // DOM already loaded
    initializeObjectivesPanel();
}

// Export functions for use in other scripts
window.GameSessionObjectives = {
    loadObjectiveProgress,
    handleObjectiveProgress,
    handleCampaignObjectiveProgress,
    toggleObjectivesSidebar
};
