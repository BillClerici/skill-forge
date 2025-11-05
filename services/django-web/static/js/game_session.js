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
        // Add child_objectives=true to fetch hierarchical objectives
        const response = await fetch(
            `/api/session/${sessionId}/objectives/?player_id=${playerId}&child_objectives=true`
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
// Helper Functions
// ============================================

function getRubricColor(score) {
    if (score >= 3.5) return '#4CAF50'; // Excellent
    if (score >= 2.5) return '#6A5ACD'; // Good
    if (score >= 1.5) return '#FFC107'; // Basic
    return '#f44336'; // Minimal
}

function getQualityLabel(quality) {
    const labels = {
        'excellent': 'EXCELLENT',
        'good': 'GOOD',
        'minimal': 'MINIMAL'
    };
    return labels[quality] || quality.toUpperCase();
}

function renderChildObjectives(childObjectives, sceneId) {
    if (!childObjectives || childObjectives.length === 0) {
        return '';
    }

    // Group by type
    const discoveries = childObjectives.filter(o => o.objective_type === 'discovery');
    const challenges = childObjectives.filter(o => o.objective_type === 'challenge');
    const events = childObjectives.filter(o => o.objective_type === 'event');
    const conversations = childObjectives.filter(o => o.objective_type === 'conversation');

    let html = '<div class="child-objectives-container" style="margin-top: 10px; padding-left: 20px; border-left: 2px solid rgba(106, 90, 205, 0.3);">';

    // Discovery Objectives
    if (discoveries.length > 0) {
        html += `
            <div class="objective-group" style="margin-bottom: 12px;">
                <h6 style="color: #6A5ACD; font-size: 0.8rem; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.1rem;">🔍</span> Discoveries (${discoveries.length})
                </h6>
                ${discoveries.map(d => renderChildObjective(d, '🔍')).join('')}
            </div>
        `;
    }

    // Challenge Objectives
    if (challenges.length > 0) {
        html += `
            <div class="objective-group" style="margin-bottom: 12px;">
                <h6 style="color: #6A5ACD; font-size: 0.8rem; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.1rem;">⚔️</span> Challenges (${challenges.length})
                </h6>
                ${challenges.map(c => renderChildObjective(c, '⚔️')).join('')}
            </div>
        `;
    }

    // Event Objectives
    if (events.length > 0) {
        html += `
            <div class="objective-group" style="margin-bottom: 12px;">
                <h6 style="color: #6A5ACD; font-size: 0.8rem; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.1rem;">⭐</span> Events (${events.length})
                </h6>
                ${events.map(e => renderChildObjective(e, '⭐')).join('')}
            </div>
        `;
    }

    // Conversation Objectives
    if (conversations.length > 0) {
        html += `
            <div class="objective-group" style="margin-bottom: 12px;">
                <h6 style="color: #6A5ACD; font-size: 0.8rem; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 1.1rem;">💬</span> Conversations (${conversations.length})
                </h6>
                ${conversations.map(c => renderChildObjective(c, '💬')).join('')}
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function renderChildObjective(childObj, icon) {
    const isCompleted = childObj.status === 'completed';
    const rubricScore = childObj.rubric_score || null;
    const minScore = childObj.minimum_rubric_score || 2.5;

    return `
        <div class="child-objective-card"
             data-child-objective-id="${childObj.objective_id}"
             style="margin: 6px 0; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; border-left: 3px solid ${isCompleted ? '#4CAF50' : '#6A5ACD'};">

            <div style="display: flex; align-items: start; gap: 8px;">
                <span style="font-size: 1.2rem; line-height: 1;">${icon}</span>
                <div style="flex: 1;">
                    <div style="font-size: 0.8rem; color: ${isCompleted ? '#4CAF50' : '#b8b8d1'}; line-height: 1.4;">
                        ${childObj.description || 'Objective'}
                    </div>

                    <div style="display: flex; gap: 4px; margin-top: 4px; flex-wrap: wrap;">
                        ${childObj.is_required ?
                            '<span class="chip tiny" style="background: #f44336; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 10px;">Required</span>' :
                            '<span class="chip tiny" style="background: #888; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 10px;">Optional</span>'
                        }
                        ${isCompleted ?
                            '<span class="chip tiny" style="background: #4CAF50; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 10px;">✓ Complete</span>' :
                            ''
                        }
                    </div>

                    ${rubricScore !== null ? `
                        <div class="rubric-score" style="margin-top: 4px; font-size: 0.7rem; color: ${getRubricColor(rubricScore)}; font-weight: bold;">
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
        hint = `<div style="font-size: 0.65rem; color: #888; margin-top: 4px; font-style: italic;">💡 ${childObj.scene_location_hint}</div>`;
    } else if (type === 'challenge' && childObj.difficulty_hint) {
        hint = `<div style="font-size: 0.65rem; color: #888; margin-top: 4px; font-style: italic;">⚠️ ${childObj.difficulty_hint}</div>`;
    } else if (type === 'conversation' && childObj.npc_name_hint) {
        hint = `<div style="font-size: 0.65rem; color: #888; margin-top: 4px; font-style: italic;">💬 Talk to ${childObj.npc_name_hint}</div>`;
    } else if (type === 'event' && childObj.participation_type) {
        hint = `<div style="font-size: 0.65rem; color: #888; margin-top: 4px; font-style: italic;">📋 ${childObj.participation_type}</div>`;
    }

    return hint;
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
        <div data-objective-id="${questObj.id}" style="margin-bottom: 12px;">
            <div style="display: flex; align-items: start; gap: 8px;">
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

            ${questObj.child_objectives && questObj.child_objectives.length > 0 ?
                renderChildObjectives(questObj.child_objectives, questObj.current_scene_id)
                : ''
            }
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

function handleChildObjectiveCompleted(data) {
    console.log('Child objective completed:', data);

    const childCard = document.querySelector(`[data-child-objective-id="${data.child_objective_id}"]`);
    if (childCard) {
        // Update card styling
        childCard.style.borderLeftColor = '#4CAF50';

        // Update text color
        const descDiv = childCard.querySelector('div[style*="font-size: 0.8rem"]');
        if (descDiv) {
            descDiv.style.color = '#4CAF50';
        }

        // Add/update rubric score display
        const existingScore = childCard.querySelector('.rubric-score');
        if (existingScore) {
            existingScore.remove();
        }

        const rubricScore = data.rubric_score || 0;
        const scoreHTML = `
            <div class="rubric-score" style="margin-top: 4px; font-size: 0.7rem; color: ${getRubricColor(rubricScore)}; font-weight: bold;">
                Quality: ${rubricScore.toFixed(1)}/4.0 - ${getQualityLabel(data.completion_quality)}
            </div>
        `;
        const contentDiv = childCard.querySelector('div[style*="flex: 1"]');
        if (contentDiv) {
            contentDiv.insertAdjacentHTML('beforeend', scoreHTML);
        }

        // Add completion badge
        const badgeContainer = childCard.querySelector('div[style*="flex-wrap: wrap"]');
        if (badgeContainer && !badgeContainer.querySelector('.chip.tiny[style*="#4CAF50"]')) {
            badgeContainer.insertAdjacentHTML('beforeend',
                '<span class="chip tiny" style="background: #4CAF50; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 10px;">✓ Complete</span>'
            );
        }

        // Trigger animation
        childCard.style.animation = 'pulse 0.5s ease';
        setTimeout(() => {
            childCard.style.animation = '';
        }, 500);
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
    if (typeof M !== 'undefined' && M.toast) {
        M.toast({
            html: `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i class="material-icons" style="font-size: 1.5rem;">emoji_events</i>
                    <div>
                        <strong>Quest Objective Complete!</strong>
                        <div style="font-size: 0.8rem; opacity: 0.9;">Average Quality: ${data.overall_quality}</div>
                    </div>
                </div>
            `,
            classes: 'green',
            displayLength: 5000
        });
    }

    // Trigger celebration
    if (typeof confetti === 'function') {
        confetti({ particleCount: 150, spread: 90 });
    }
}

function handleCampaignObjectiveCompleted(data) {
    console.log('Campaign objective completed:', data);

    // Update campaign objective card
    const campaignCard = document.querySelector(`[data-campaign-objective-id="${data.objective_id}"]`);
    if (campaignCard) {
        const progressBar = campaignCard.querySelector('.campaign-progress-bar');
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.style.background = '#4CAF50';
        }

        const percentageText = campaignCard.querySelector('.campaign-percentage');
        if (percentageText) {
            percentageText.textContent = '100%';
            percentageText.style.color = '#4CAF50';
        }
    }

    // Major celebration - campaign objective is huge!
    if (typeof M !== 'undefined' && M.toast) {
        M.toast({
            html: `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 2rem;">🏆</span>
                    <div>
                        <strong>Campaign Milestone Achieved!</strong>
                        <div style="font-size: 0.8rem;">${data.description}</div>
                        <div style="font-size: 0.75rem; opacity: 0.9;">Quality Score: ${(data.overall_quality_score || 0).toFixed(1)}/4.0</div>
                    </div>
                </div>
            `,
            classes: 'purple',
            displayLength: 7000
        });
    }

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
        audio.play().catch(err => console.log('Audio play failed:', err));
    } catch (e) {
        // Ignore audio errors
    }
}

function handleObjectiveCascadeUpdate(data) {
    console.log('Cascade update:', data);

    // Update all affected objectives
    if (data.updated_objectives && Array.isArray(data.updated_objectives)) {
        data.updated_objectives.forEach(obj => {
            if (obj.type === 'quest') {
                updateQuestObjectiveProgress(obj.id, obj.progress);
            } else if (obj.type === 'campaign') {
                updateCampaignObjectiveProgress(obj.id, obj.progress);
            }
        });
    }
}

function updateQuestObjectiveProgress(objectiveId, progress) {
    const questCard = document.querySelector(`[data-objective-id="${objectiveId}"]`);
    if (questCard) {
        const progressBar = questCard.querySelector('.progress-bar div');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }

        const percentageText = questCard.querySelector('.percentage-text');
        if (percentageText) {
            percentageText.textContent = `${progress}% complete`;
        }

        // Update status icon if completed
        if (progress === 100) {
            const icon = questCard.querySelector('.status-icon');
            if (icon) {
                icon.textContent = 'check_circle';
                icon.style.color = '#4CAF50';
            }
        }
    }
}

function updateCampaignObjectiveProgress(objectiveId, progress) {
    const campaignCard = document.querySelector(`[data-campaign-objective-id="${objectiveId}"]`);
    if (campaignCard) {
        const progressBar = campaignCard.querySelector('.campaign-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }

        const percentageText = campaignCard.querySelector('.campaign-percentage');
        if (percentageText) {
            percentageText.textContent = `${progress}%`;
        }
    }
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

    if (typeof M !== 'undefined' && M.toast) {
        M.toast({
            html: `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.5rem;">${typeEmoji}</span>
                    <div>
                        <strong>${description}</strong>
                        <div style="font-size: 0.8rem; color: ${qualityColor};">
                            Score: ${(score || 0).toFixed(1)}/4.0 - ${getQualityLabel(quality)}
                        </div>
                    </div>
                </div>
            `,
            classes: 'purple',
            displayLength: 4000
        });
    }
}

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
    handleChildObjectiveCompleted,
    handleQuestObjectiveCompleted,
    handleObjectiveCascadeUpdate,
    toggleObjectivesSidebar
};
