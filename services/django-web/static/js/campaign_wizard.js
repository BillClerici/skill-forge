/**
 * Campaign Designer Wizard V2 - JavaScript
 * Complete implementation with all 22 workflow steps
 */

document.addEventListener('DOMContentLoaded', function() {
    let currentStep = 1;
    const totalSteps = 11;
    let requestId = null;
    let pollInterval = null;

    // Wizard state
    const wizardState = {
        campaign_name: null,
        universe_id: null,
        universe_name: null,
        world_id: null,
        world_name: null,
        world_genre: null,
        region_id: null,
        region_name: null,
        user_story_idea: null,
        selected_story_id: null,
        selected_story: null,
        campaign_core: null,
        num_quests: 5,
        quest_difficulty: 'Medium',
        quest_playtime_minutes: 90,
        generate_images_quests: true,
        quests: [],
        places: [],
        scenes: [],
        new_locations: []
    };

    // Initialize Materialize components
    M.updateTextFields();
    M.FormSelect.init(document.querySelectorAll('select'));

    // Navigation buttons
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const generateStoriesBtn = document.getElementById('generate-stories-btn');
    const finalizeBtn = document.getElementById('finalize-btn');

    // Quest count slider
    const questSlider = document.getElementById('num_quests');
    const questDisplay = document.getElementById('quest-count-display');
    if (questSlider) {
        questSlider.addEventListener('input', function() {
            questDisplay.textContent = this.value;
            wizardState.num_quests = parseInt(this.value);
        });
    }

    // Quest difficulty
    const questDifficulty = document.getElementById('quest_difficulty');
    if (questDifficulty) {
        questDifficulty.addEventListener('change', function() {
            wizardState.quest_difficulty = this.value;
        });
    }

    // Quest playtime
    const questPlaytime = document.getElementById('quest_playtime_minutes');
    if (questPlaytime) {
        questPlaytime.addEventListener('change', function() {
            wizardState.quest_playtime_minutes = parseInt(this.value);
        });
    }

    // Image generation checkbox
    const generateImagesCheckbox = document.getElementById('generate_images_quests');
    if (generateImagesCheckbox) {
        generateImagesCheckbox.addEventListener('change', function() {
            wizardState.generate_images_quests = this.checked;
        });
    }

    /**
     * Update progress indicator
     */
    function updateProgress() {
        // Update left sidebar navigation
        document.querySelectorAll('.nav-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.remove('active', 'completed');
            if (stepNum === currentStep) {
                step.classList.add('active');
            } else if (stepNum < currentStep) {
                step.classList.add('completed');
            }
        });

        // Show/hide steps
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.style.display = parseInt(step.dataset.step) === currentStep ? 'block' : 'none';
        });

        // Update buttons
        prevBtn.style.display = currentStep > 1 ? 'inline-block' : 'none';
        nextBtn.style.display = (currentStep < totalSteps && currentStep !== 4) ? 'inline-block' : 'none';
        generateStoriesBtn.style.display = currentStep === 4 ? 'inline-block' : 'none';
        finalizeBtn.style.display = currentStep === totalSteps ? 'inline-block' : 'none';

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    /**
     * Validate current step
     */
    function validateStep(step) {
        if (step === 1) {
            // Validate campaign name
            const campaignName = document.getElementById('campaign_name');
            if (!campaignName || !campaignName.value.trim()) {
                M.toast({html: 'Please enter a campaign name', classes: 'red'});
                return false;
            }
            wizardState.campaign_name = campaignName.value.trim();

            // Validate universe selection
            const universe = document.querySelector('input[name="universe_id"]:checked');
            if (!universe) {
                M.toast({html: 'Please select a universe', classes: 'red'});
                return false;
            }
            wizardState.universe_id = universe.value;
            wizardState.universe_name = universe.dataset.name;
        } else if (step === 2) {
            const world = document.querySelector('input[name="world_id"]:checked');
            if (!world) {
                M.toast({html: 'Please select a world', classes: 'red'});
                return false;
            }
            wizardState.world_id = world.value;
            wizardState.world_name = world.dataset.name;
            wizardState.world_genre = world.dataset.genre;
        } else if (step === 5) {
            const story = document.querySelector('input[name="selected_story_id"]:checked');
            if (!story) {
                M.toast({html: 'Please select a story idea', classes: 'red'});
                return false;
            }
            wizardState.selected_story_id = story.value;
            wizardState.selected_story = JSON.parse(story.dataset.story);
        }
        return true;
    }

    /**
     * Navigation handlers
     */
    nextBtn.addEventListener('click', async function() {
        if (validateStep(currentStep)) {
            // Special handling for step transitions
            if (currentStep === 1) {
                await loadWorldsForUniverse();
            } else if (currentStep === 2) {
                populateRegions();
            } else if (currentStep === 4) {
                // Skip to story generation (handled by Generate button)
                return;
            } else if (currentStep === 5) {
                // Generate campaign core
                await generateCampaignCore();
                return; // Don't increment step yet
            } else if (currentStep === 6) {
                // User approved core, continue
                currentStep++;
                updateProgress();
                return;
            } else if (currentStep === 7) {
                // Generate quests
                await generateQuests();
                return; // Don't increment step yet
            } else if (currentStep === 8) {
                // Generate places
                await generatePlaces();
                return;
            } else if (currentStep === 9) {
                // Generate scenes
                await generateScenes();
                return;
            } else if (currentStep === 10) {
                // Populate final review
                populateFinalReview();
            }

            currentStep++;
            updateProgress();
        }
    });

    prevBtn.addEventListener('click', function() {
        currentStep--;
        updateProgress();
    });

    /**
     * Generate Campaign Ideas button handler
     */
    generateStoriesBtn.addEventListener('click', async function() {
        wizardState.user_story_idea = document.getElementById('user_story_idea').value.trim();
        await generateStoryIdeas();
    });

    /**
     * Finalize Campaign button handler
     */
    finalizeBtn.addEventListener('click', async function() {
        await finalizeCampaign();
    });

    /**
     * Load worlds for selected universe
     */
    async function loadWorldsForUniverse() {
        const worldList = document.getElementById('world-list');
        worldList.innerHTML = '<div class="center-align" style="padding: 40px;"><div class="preloader-wrapper active"><div class="spinner-layer spinner-blue-only"><div class="circle-clipper left"><div class="circle"></div></div><div class="gap-patch"><div class="circle"></div></div><div class="circle-clipper right"><div class="circle"></div></div></div></div><p style="color: var(--rpg-silver); margin-top: 20px;">Loading worlds...</p></div>';

        // Update universe name display
        document.getElementById('selected-universe-name').textContent = wizardState.universe_name;

        try {
            const response = await fetch(`/campaigns/wizard/api/worlds/${wizardState.universe_id}`);
            if (!response.ok) throw new Error('Failed to load worlds');

            const data = await response.json();
            const worlds = data.worlds || [];

            if (worlds.length === 0) {
                worldList.innerHTML = '<p style="color: var(--rpg-silver);">No worlds found in this universe.</p>';
                return;
            }

            worldList.innerHTML = '';
            worlds.forEach(world => {
                const worldCard = createWorldCard(world);
                worldList.appendChild(worldCard);
            });

            // Setup search
            setupWorldSearch();
        } catch (error) {
            console.error('Error loading worlds:', error);
            M.toast({html: 'Error loading worlds', classes: 'red'});
            worldList.innerHTML = '<p style="color: var(--rpg-silver);">Error loading worlds. Please try again.</p>';
        }
    }

    /**
     * Create world card element
     */
    function createWorldCard(world) {
        const label = document.createElement('label');
        label.className = 'world-card';
        label.dataset.name = world.world_name.toLowerCase();
        label.dataset.genre = (world.genre || '').toLowerCase();

        const imageHtml = world.primary_image_url
            ? `<img src="${world.primary_image_url}" alt="${world.world_name}" class="world-image">`
            : `<div class="world-image-placeholder"><i class="material-icons" style="font-size: 48px; color: var(--rpg-gold); opacity: 0.5;">public</i></div>`;

        label.innerHTML = `
            <input type="radio" name="world_id" value="${world._id}" data-name="${world.world_name}" data-genre="${world.genre || ''}">
            <div class="world-content">
                <div style="display: flex; gap: 15px;">
                    <div class="world-image-container">
                        ${imageHtml}
                    </div>
                    <div style="flex: 1;">
                        <div class="world-header">
                            <h6 style="color: var(--rpg-gold); margin: 0; font-size: 1.2rem; font-weight: bold;">${world.world_name}</h6>
                        </div>
                        <div style="margin-top: 10px;">
                            <span class="chip" style="background-color: rgba(106, 90, 205, 0.2); color: #ffffff; font-size: 0.85rem;">
                                <i class="material-icons tiny" style="vertical-align: middle;">category</i> ${world.genre || 'Unknown'}
                            </span>
                        </div>
                        <p style="color: #b8b8d1; font-size: 0.95rem; margin-top: 12px; line-height: 1.5;">
                            ${(world.description || 'No description').substring(0, 150)}...
                        </p>
                        <div style="margin-top: 12px; display: flex; align-items: center; gap: 15px;">
                            <span style="color: var(--rpg-silver); font-size: 0.85rem; display: flex; align-items: center; gap: 4px;">
                                <i class="material-icons" style="font-size: 1.1rem;">map</i>
                                <span>${(world.regions || []).length} Regions</span>
                            </span>
                            <span style="color: var(--rpg-silver); font-size: 0.85rem; display: flex; align-items: center; gap: 4px;">
                                <i class="material-icons" style="font-size: 1.1rem;">diversity_3</i>
                                <span>${(world.species || []).length} Species</span>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        return label;
    }

    /**
     * Setup world search
     */
    function setupWorldSearch() {
        const worldSearch = document.getElementById('world-search');
        if (worldSearch) {
            worldSearch.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                document.querySelectorAll('.world-card').forEach(card => {
                    const name = card.dataset.name;
                    const genre = card.dataset.genre;
                    if (name.includes(searchTerm) || genre.includes(searchTerm)) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
            });
        }
    }

    /**
     * Populate regions for selected world
     */
    function populateRegions() {
        const regionList = document.getElementById('region-list');
        document.getElementById('selected-world-name').textContent = wizardState.world_name;

        // Keep "Entire World" option
        const entireWorldOption = regionList.querySelector('label');
        regionList.innerHTML = '';
        regionList.appendChild(entireWorldOption);

        // Fetch regions from backend
        fetch(`/campaigns/wizard/api/regions/${wizardState.world_id}`)
            .then(response => response.json())
            .then(data => {
                const regions = data.regions || [];
                regions.forEach(region => {
                    const label = document.createElement('label');
                    label.className = 'region-card';
                    label.innerHTML = `
                        <input type="radio" name="region_id" value="${region._id}" data-name="${region.region_name}">
                        <div class="region-content">
                            <strong style="color: var(--rpg-gold);">${region.region_name}</strong>
                            <p style="color: #b8b8d1; font-size: 0.9rem; margin-top: 5px;">
                                ${region.description || 'No description available'}
                            </p>
                            <div style="margin-top: 10px;">
                                <span style="color: var(--rpg-silver); font-size: 0.85rem;">
                                    <i class="material-icons tiny">location_on</i> ${(region.locations || []).length} Locations
                                </span>
                            </div>
                        </div>
                    `;
                    regionList.appendChild(label);
                });

                // Add change listener for region selection
                regionList.addEventListener('change', function(e) {
                    if (e.target.name === 'region_id' && e.target.value) {
                        wizardState.region_id = e.target.value;
                        wizardState.region_name = e.target.dataset.name;
                    } else {
                        wizardState.region_id = null;
                        wizardState.region_name = null;
                    }
                });
            })
            .catch(error => {
                console.error('Error loading regions:', error);
                M.toast({html: 'Error loading regions', classes: 'red'});
            });
    }

    /**
     * Generate Story Ideas (Step 4 -> Step 5)
     */
    async function generateStoryIdeas() {
        showLoadingOverlay('story', 'Generating story ideas...');

        try {
            const response = await fetch('/campaigns/wizard/api/generate-stories', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    campaign_name: wizardState.campaign_name,
                    universe_id: wizardState.universe_id,
                    world_id: wizardState.world_id,
                    region_id: wizardState.region_id,
                    genre: wizardState.world_genre,
                    user_story_idea: wizardState.user_story_idea
                })
            });

            if (!response.ok) throw new Error('Failed to generate stories');

            const data = await response.json();
            requestId = data.request_id;

            // Poll for story ideas
            await pollStoryIdeas();
        } catch (error) {
            console.error('Error generating stories:', error);
            M.toast({html: 'Error generating stories', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Poll for story ideas
     */
    async function pollStoryIdeas() {
        const maxAttempts = 60; // 2 minutes max
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Story generation timed out', classes: 'red'});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.story_ideas && data.story_ideas.length > 0) {
                    clearInterval(pollInterval);
                    displayStoryIdeas(data.story_ideas);
                    hideLoadingOverlay();
                    currentStep = 5;
                    updateProgress();
                } else if (data.errors && data.errors.length > 0) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    M.toast({html: 'Error: ' + data.errors[0], classes: 'red'});
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    /**
     * Display story ideas
     */
    function displayStoryIdeas(storyIdeas) {
        const container = document.getElementById('story-ideas-container');
        container.innerHTML = '';

        storyIdeas.forEach((story, index) => {
            const card = document.createElement('label');
            card.className = 'story-idea-card';

            // Create the input element separately to avoid JSON escaping issues
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = 'selected_story_id';
            input.value = story.id;
            input.dataset.story = JSON.stringify(story);

            const content = document.createElement('div');
            content.className = 'story-idea-content';
            content.innerHTML = `
                <h6 style="color: var(--rpg-gold); margin-top: 0;">${story.title}</h6>
                <p style="color: #b8b8d1; font-size: 0.95rem; line-height: 1.6;">
                    ${story.summary}
                </p>
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                    ${story.themes.map(theme => `<span class="chip" style="background-color: rgba(106, 90, 205, 0.2); color: #ffffff; font-size: 0.8rem;">${theme}</span>`).join('')}
                </div>
                <div style="margin-top: 15px; display: flex; gap: 15px; font-size: 0.85rem; color: var(--rpg-silver);">
                    <span><i class="material-icons tiny">timer</i> ${story.estimated_length}</span>
                    <span><i class="material-icons tiny">trending_up</i> ${story.difficulty_level}</span>
                </div>
            `;

            card.appendChild(input);
            card.appendChild(content);
            container.appendChild(card);
        });

        // Show action buttons
        document.getElementById('modify-story-btn').style.display = 'inline-block';
        document.getElementById('regenerate-stories-btn').style.display = 'inline-block';

        // Modify story button handler
        document.getElementById('modify-story-btn').onclick = function() {
            currentStep = 4;
            updateProgress();
        };

        // Regenerate stories button handler
        document.getElementById('regenerate-stories-btn').onclick = async function() {
            await regenerateStories();
        };
    }

    /**
     * Regenerate stories
     */
    async function regenerateStories() {
        showLoadingOverlay('story', 'Regenerating story ideas...');

        try {
            const response = await fetch('/campaigns/wizard/api/regenerate-stories', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId
                })
            });

            if (!response.ok) throw new Error('Failed to regenerate stories');

            await pollStoryIdeas();
        } catch (error) {
            console.error('Error regenerating stories:', error);
            M.toast({html: 'Error regenerating stories', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Generate Campaign Core (Step 5 -> Step 6)
     */
    async function generateCampaignCore() {
        showLoadingOverlay('core', 'Generating campaign core...');

        try {
            const response = await fetch('/campaigns/wizard/api/generate-core', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId,
                    selected_story_id: wizardState.selected_story_id
                })
            });

            if (!response.ok) throw new Error('Failed to generate campaign core');

            await pollCampaignCore();
        } catch (error) {
            console.error('Error generating core:', error);
            M.toast({html: 'Error generating campaign core', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Poll for campaign core
     */
    async function pollCampaignCore() {
        const maxAttempts = 60;
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Campaign core generation timed out', classes: 'red'});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.campaign_core) {
                    clearInterval(pollInterval);
                    wizardState.campaign_core = data.campaign_core;
                    displayCampaignCore(data.campaign_core);
                    hideLoadingOverlay();
                    currentStep = 6;
                    updateProgress();
                } else if (data.errors && data.errors.length > 0) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    M.toast({html: 'Error: ' + data.errors[0], classes: 'red'});
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    /**
     * Display campaign core
     */
    function displayCampaignCore(core) {
        const container = document.getElementById('campaign-core-container');
        container.innerHTML = `
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Campaign Name:</strong>
                <p style="color: #b8b8d1;">${core.name || 'Untitled Campaign'}</p>
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Plot:</strong>
                <p style="color: #b8b8d1; line-height: 1.6;">${core.plot}</p>
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Storyline:</strong>
                <p style="color: #b8b8d1; line-height: 1.6;">${core.storyline}</p>
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Primary Objectives:</strong>
                <ul style="color: #b8b8d1;">
                    ${core.primary_objectives.map(obj => `
                        <li style="margin-bottom: 10px;">
                            ${obj.description}
                            <span class="blooms-tag blooms-${obj.blooms_level}">${getBloomsLabel(obj.blooms_level)}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
            ${core.backstory ? `
                <div class="review-section">
                    <strong style="color: var(--rpg-gold);">Backstory:</strong>
                    <span class="backstory-toggle" onclick="toggleBackstory('campaign-backstory')">View Backstory</span>
                    <div id="campaign-backstory" class="backstory-content">
                        <p>${core.backstory}</p>
                    </div>
                </div>
            ` : ''}
        `;

        // Show Bloom's info
        document.getElementById('blooms-info').style.display = 'block';
    }

    /**
     * Generate Quests (Step 7 -> Step 8)
     */
    async function generateQuests() {
        showLoadingOverlay('quests', 'Generating quests...');

        try {
            const response = await fetch('/campaigns/wizard/api/approve-core', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId,
                    num_quests: wizardState.num_quests,
                    quest_difficulty: wizardState.quest_difficulty,
                    quest_playtime_minutes: wizardState.quest_playtime_minutes,
                    generate_images: wizardState.generate_images_quests
                })
            });

            if (!response.ok) throw new Error('Failed to generate quests');

            await pollQuests();
        } catch (error) {
            console.error('Error generating quests:', error);
            M.toast({html: 'Error generating quests', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Poll for quests
     */
    async function pollQuests() {
        const maxAttempts = 120; // 4 minutes for quest generation
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Quest generation timed out', classes: 'red'});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                // Update loading message with progress
                if (data.progress_percentage) {
                    updateLoadingMessage('quests', `Generating quests... ${data.progress_percentage}%`, data.status_message);
                }

                if (data.quests && data.quests.length > 0) {
                    clearInterval(pollInterval);
                    wizardState.quests = data.quests;
                    displayQuests(data.quests);
                    hideLoadingOverlay();
                    currentStep = 8;
                    updateProgress();
                } else if (data.errors && data.errors.length > 0) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    M.toast({html: 'Error: ' + data.errors[0], classes: 'red'});
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    /**
     * Display quests
     */
    function displayQuests(quests) {
        const container = document.getElementById('quests-review-container');
        container.innerHTML = '';

        quests.forEach((quest, index) => {
            const card = document.createElement('div');
            card.className = 'quest-review-card';
            card.innerHTML = `
                <h6>Quest ${index + 1}: ${quest.name}</h6>
                <p style="color: #b8b8d1; font-size: 0.95rem; line-height: 1.6;">
                    ${quest.description}
                </p>
                <div style="margin-top: 15px;">
                    <strong style="color: var(--rpg-gold); font-size: 0.9rem;">Location:</strong>
                    <span style="color: #b8b8d1; font-size: 0.9rem;">${quest.level_1_location_name}</span>
                </div>
                <div style="margin-top: 10px;">
                    <strong style="color: var(--rpg-gold); font-size: 0.9rem;">Objectives:</strong>
                    <ul style="color: #b8b8d1; font-size: 0.9rem; margin-top: 5px;">
                        ${quest.objectives.map(obj => `
                            <li style="margin-bottom: 5px;">
                                ${obj.description}
                                <span class="blooms-tag blooms-${obj.blooms_level}">${getBloomsLabel(obj.blooms_level)}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                <div style="margin-top: 10px; display: flex; gap: 15px; font-size: 0.85rem; color: var(--rpg-silver);">
                    <span><i class="material-icons tiny">timer</i> ~${quest.estimated_duration_minutes} min</span>
                    <span><i class="material-icons tiny">trending_up</i> ${quest.difficulty_level}</span>
                </div>
                ${quest.backstory ? `
                    <div style="margin-top: 15px;">
                        <span class="backstory-toggle" onclick="toggleBackstory('quest-${index}-backstory')">View Backstory</span>
                        <div id="quest-${index}-backstory" class="backstory-content">
                            <p>${quest.backstory}</p>
                        </div>
                    </div>
                ` : ''}
            `;
            container.appendChild(card);
        });

        // Show regenerate button (optional)
        document.getElementById('regenerate-quests-btn').style.display = 'inline-block';
    }

    /**
     * Generate Places (Step 8 -> Step 9)
     */
    async function generatePlaces() {
        showLoadingOverlay('places', 'Generating places...');

        try {
            const response = await fetch('/campaigns/wizard/api/approve-quests', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId
                })
            });

            if (!response.ok) throw new Error('Failed to generate places');

            await pollPlaces();
        } catch (error) {
            console.error('Error generating places:', error);
            M.toast({html: 'Error generating places', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Poll for places
     */
    async function pollPlaces() {
        const maxAttempts = 120;
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Place generation timed out', classes: 'red'});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.progress_percentage) {
                    updateLoadingMessage('places', `Generating places... ${data.progress_percentage}%`, data.status_message);
                }

                if (data.places && data.places.length > 0) {
                    clearInterval(pollInterval);
                    wizardState.places = data.places;
                    wizardState.new_locations = wizardState.new_locations.concat(data.new_location_ids || []);
                    displayPlaces(data.places, data.new_location_ids || []);
                    hideLoadingOverlay();
                    currentStep = 9;
                    updateProgress();
                } else if (data.errors && data.errors.length > 0) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    M.toast({html: 'Error: ' + data.errors[0], classes: 'red'});
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    /**
     * Display places
     */
    function displayPlaces(places, newLocationIds) {
        const container = document.getElementById('places-review-container');
        container.innerHTML = '';

        // Group places by quest
        const placesByQuest = {};
        places.forEach(place => {
            if (!placesByQuest[place.parent_quest_id]) {
                placesByQuest[place.parent_quest_id] = [];
            }
            placesByQuest[place.parent_quest_id].push(place);
        });

        Object.entries(placesByQuest).forEach(([questId, questPlaces]) => {
            const quest = wizardState.quests.find(q => q.quest_id === questId);
            const card = document.createElement('div');
            card.className = 'place-review-card';
            card.innerHTML = `
                <h6>${quest ? quest.name : 'Quest'} - Places</h6>
                ${questPlaces.map(place => `
                    <div style="margin-top: 15px; padding: 10px; background: rgba(27, 27, 46, 0.4); border-radius: 4px;">
                        <strong style="color: var(--rpg-purple);">${place.name}</strong>
                        <p style="color: #b8b8d1; font-size: 0.9rem; margin-top: 5px;">
                            ${place.description}
                        </p>
                        <div style="margin-top: 5px; font-size: 0.85rem; color: var(--rpg-silver);">
                            <i class="material-icons tiny">place</i> ${place.level_2_location_name}
                        </div>
                    </div>
                `).join('')}
            `;
            container.appendChild(card);
        });

        // Show new locations if any were created
        if (newLocationIds.length > 0) {
            document.getElementById('new-locations-created-l2').style.display = 'block';
            const locationList = document.getElementById('new-locations-list-l2');
            locationList.innerHTML = newLocationIds.map(locId => `
                <li>Level 2 Location created (ID: ${locId})</li>
            `).join('');
        }
    }

    /**
     * Generate Scenes (Step 9 -> Step 10)
     */
    async function generateScenes() {
        showLoadingOverlay('scenes', 'Generating scenes with NPCs, challenges, events, and discoveries...');

        try {
            const response = await fetch('/campaigns/wizard/api/approve-places', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId
                })
            });

            if (!response.ok) throw new Error('Failed to generate scenes');

            await pollScenes();
        } catch (error) {
            console.error('Error generating scenes:', error);
            M.toast({html: 'Error generating scenes', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Poll for scenes
     */
    async function pollScenes() {
        const maxAttempts = 180; // 6 minutes for scene + element generation
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Scene generation timed out', classes: 'red'});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.progress_percentage) {
                    updateLoadingMessage('scenes', `Generating scenes... ${data.progress_percentage}%`, data.status_message);
                }

                if (data.scenes && data.scenes.length > 0) {
                    clearInterval(pollInterval);
                    wizardState.scenes = data.scenes;
                    wizardState.new_locations = wizardState.new_locations.concat(data.new_location_ids || []);
                    displayScenes(data.scenes, data.new_location_ids || [], data.npcs || [], data.discoveries || []);
                    hideLoadingOverlay();
                    currentStep = 10;
                    updateProgress();
                } else if (data.errors && data.errors.length > 0) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    M.toast({html: 'Error: ' + data.errors[0], classes: 'red'});
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    /**
     * Display scenes
     */
    function displayScenes(scenes, newLocationIds, npcs, discoveries) {
        const container = document.getElementById('scenes-review-container');
        container.innerHTML = '';

        // Group scenes by place
        const scenesByPlace = {};
        scenes.forEach(scene => {
            if (!scenesByPlace[scene.parent_place_id]) {
                scenesByPlace[scene.parent_place_id] = [];
            }
            scenesByPlace[scene.parent_place_id].push(scene);
        });

        Object.entries(scenesByPlace).forEach(([placeId, placeScenes]) => {
            const place = wizardState.places.find(p => p.place_id === placeId);
            const card = document.createElement('div');
            card.className = 'scene-review-card';
            card.innerHTML = `
                <h6>${place ? place.name : 'Place'} - Scenes</h6>
                <p style="color: var(--rpg-silver); font-size: 0.85rem; margin-bottom: 15px;">
                    <i class="material-icons tiny">info</i> Scenes can be experienced in any order
                </p>
                ${placeScenes.map((scene, idx) => `
                    <div style="margin-top: 15px; padding: 15px; background: rgba(27, 27, 46, 0.4); border-radius: 4px;">
                        <strong style="color: var(--rpg-purple);">Scene ${idx + 1}: ${scene.name}</strong>
                        <p style="color: #b8b8d1; font-size: 0.9rem; margin-top: 5px;">
                            ${scene.description}
                        </p>
                        <div style="margin-top: 10px; font-size: 0.85rem; color: var(--rpg-silver);">
                            <i class="material-icons tiny">movie</i> ${scene.level_3_location_name}
                        </div>

                        ${scene.npc_ids && scene.npc_ids.length > 0 ? `
                            <div style="margin-top: 10px;">
                                <strong style="color: var(--rpg-gold); font-size: 0.85rem;">NPCs:</strong>
                                <div style="margin-top: 5px;">
                                    ${scene.npc_ids.map(npcId => {
                                        const npc = npcs.find(n => n.npc_id === npcId);
                                        return npc ? `<span class="chip" style="background-color: rgba(212, 175, 55, 0.2); font-size: 0.75rem;">${npc.name} (${npc.role})</span>` : '';
                                    }).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${scene.discovery_ids && scene.discovery_ids.length > 0 ? `
                            <div style="margin-top: 10px;">
                                <strong style="color: var(--rpg-gold); font-size: 0.85rem;">Knowledge & Discoveries:</strong>
                                <div style="margin-top: 5px;">
                                    ${scene.discovery_ids.map(discId => {
                                        const disc = discoveries.find(d => d.discovery_id === discId);
                                        return disc ? `<span class="knowledge-item">${disc.name}</span>` : '';
                                    }).join('')}
                                </div>
                            </div>
                        ` : ''}

                        ${scene.required_knowledge && scene.required_knowledge.length > 0 ? `
                            <div style="margin-top: 10px; padding: 10px; background: rgba(106, 90, 205, 0.1); border-left: 3px solid var(--rpg-purple); border-radius: 4px;">
                                <strong style="color: var(--rpg-purple); font-size: 0.85rem;">
                                    <i class="material-icons tiny">lock</i> Requires:
                                </strong>
                                <p style="color: #b8b8d1; font-size: 0.85rem; margin-top: 5px;">
                                    Knowledge: ${scene.required_knowledge.join(', ')}
                                </p>
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
            `;
            container.appendChild(card);
        });

        // Show new locations if any were created
        if (newLocationIds.length > 0) {
            document.getElementById('new-locations-created-l3').style.display = 'block';
            const locationList = document.getElementById('new-locations-list-l3');
            locationList.innerHTML = newLocationIds.map(locId => `
                <li>Level 3 Location created (ID: ${locId})</li>
            `).join('');
        }
    }

    /**
     * Populate final review
     */
    function populateFinalReview() {
        document.getElementById('final-review-campaign-name').textContent = wizardState.campaign_name || 'Untitled Campaign';
        document.getElementById('final-review-universe').textContent = wizardState.universe_name;
        document.getElementById('final-review-world').textContent = `${wizardState.world_name} (${wizardState.world_genre})`;
        document.getElementById('final-review-region').textContent = wizardState.region_name || 'Entire World';
        document.getElementById('final-review-story').textContent = wizardState.selected_story ? wizardState.selected_story.title : 'N/A';
        document.getElementById('final-review-quests').textContent = `${wizardState.quests.length} Quests (${wizardState.quest_difficulty} difficulty, ~${wizardState.quest_playtime_minutes} min each)`;
        document.getElementById('final-review-summary').textContent = `Campaign includes ${wizardState.quests.length} quests, ${wizardState.places.length} places, ${wizardState.scenes.length} scenes. ${wizardState.new_locations.length} new locations were created.`;
    }

    /**
     * Finalize Campaign
     */
    async function finalizeCampaign() {
        showLoadingOverlay('finalize', 'Finalizing campaign...');

        try {
            const response = await fetch('/campaigns/wizard/api/finalize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    request_id: requestId
                })
            });

            if (!response.ok) throw new Error('Failed to finalize campaign');

            const data = await response.json();
            hideLoadingOverlay();

            M.toast({html: 'Campaign created successfully!', classes: 'green'});

            // Redirect to campaign detail
            if (data.campaign_id) {
                window.location.href = `/campaigns/${data.campaign_id}/`;
            } else {
                window.location.href = '/campaigns/';
            }
        } catch (error) {
            console.error('Error finalizing campaign:', error);
            M.toast({html: 'Error finalizing campaign', classes: 'red'});
            hideLoadingOverlay();
        }
    }

    /**
     * Loading overlay helpers
     */
    function showLoadingOverlay(phase, statusMessage, detailMessage = null) {
        const overlay = document.getElementById('loading-overlay');
        overlay.style.display = 'flex';

        // Update phases
        document.querySelectorAll('.phase-step').forEach(step => {
            step.classList.remove('active');
            if (step.dataset.phase === phase) {
                step.classList.add('active');
            }
        });

        // Update messages
        document.getElementById('loading-status-message').textContent = statusMessage;
        if (detailMessage) {
            document.getElementById('loading-detail-message').textContent = detailMessage;
        }
    }

    function updateLoadingMessage(phase, statusMessage, detailMessage = null) {
        document.getElementById('loading-status-message').textContent = statusMessage;
        if (detailMessage) {
            document.getElementById('loading-detail-message').textContent = detailMessage;
        }

        // Mark completed phases
        const phases = ['story', 'core', 'quests', 'places', 'scenes', 'finalize'];
        const currentIndex = phases.indexOf(phase);
        phases.forEach((p, idx) => {
            const stepEl = document.querySelector(`.phase-step[data-phase="${p}"]`);
            if (idx < currentIndex) {
                stepEl.classList.add('completed');
                stepEl.classList.remove('active');
            } else if (idx === currentIndex) {
                stepEl.classList.add('active');
                stepEl.classList.remove('completed');
            }
        });
    }

    function hideLoadingOverlay() {
        document.getElementById('loading-overlay').style.display = 'none';
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    /**
     * Utility functions
     */
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    function getBloomsLabel(level) {
        const labels = {
            1: 'Remembering',
            2: 'Understanding',
            3: 'Applying',
            4: 'Analyzing',
            5: 'Evaluating',
            6: 'Creating'
        };
        return labels[level] || `Level ${level}`;
    }

    window.toggleBackstory = function(id) {
        const backstory = document.getElementById(id);
        if (backstory) {
            backstory.style.display = backstory.style.display === 'none' ? 'block' : 'none';
        }
    };

    // Initialize
    updateProgress();
});
