/**
 * Campaign Design Wizard V2 - JavaScript
 * Complete implementation with all 22 workflow steps
 */

document.addEventListener('DOMContentLoaded', function() {
    let currentStep = 1;
    const totalSteps = 11;
    let requestId = null;
    let pollInterval = null;
    let timerInterval = null;
    let timerStartTime = null;

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

    // Check for in-progress campaigns on page load
    checkInProgressCampaigns();

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
        // Update sidebar navigation steps (V2)
        document.querySelectorAll('.nav-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.remove('active', 'completed');
            if (stepNum === currentStep) {
                step.classList.add('active');
            } else if (stepNum < currentStep) {
                step.classList.add('completed');
            }
        });

        // Update old progress indicators if they exist (V1 compatibility)
        document.querySelectorAll('.progress-step').forEach(step => {
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
            const campaignName = document.getElementById('campaign_name');
            if (!campaignName || !campaignName.value.trim()) {
                M.toast({html: 'Please enter a campaign name', classes: 'red'});
                return false;
            }
            wizardState.campaign_name = campaignName.value.trim();

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
            // Story data is stored directly on the element, not in dataset
            wizardState.selected_story = story.storyData;
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
                            <span class="chip" style="background-color: rgba(106, 90, 205, 0.2); color: var(--rpg-purple); font-size: 0.85rem;">
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
                                <span style="color: var(--rpg-silver); font-size: 0.85rem; display: flex; align-items: center; gap: 4px;">
                                    <i class="material-icons tiny">location_on</i>
                                    <span>${(region.locations || []).length} Locations</span>
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

            // Save request_id to localStorage for resume functionality
            localStorage.setItem('campaign_wizard_request_id', requestId);

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
        const maxAttempts = 180; // 6 minutes max (was 2 minutes)
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0) {
                updateLoadingMessage('story', 'Generating story ideas...', `Still working... (${Math.floor(attempts / 30)} minute${attempts >= 60 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Story generation timed out. The generation may still be running in the background. Please refresh the page or check back later.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                // Update loading message with progress if available
                if (data.progress_percentage) {
                    updateLoadingMessage('story', `Generating story ideas... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

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

            // Create the radio input separately to avoid HTML attribute issues
            const radioInput = document.createElement('input');
            radioInput.type = 'radio';
            radioInput.name = 'selected_story_id';
            radioInput.value = story.id;
            // Store the story object directly on the element to avoid JSON escaping issues
            radioInput.storyData = story;

            card.appendChild(radioInput);

            const contentDiv = document.createElement('div');
            contentDiv.className = 'story-idea-content';
            contentDiv.innerHTML = `
                <h6 style="color: var(--rpg-gold); margin-top: 0;">${story.title}</h6>
                <p style="color: #b8b8d1; font-size: 0.95rem; line-height: 1.6;">
                    ${story.summary}
                </p>
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                    ${story.themes.map(theme => `<span class="chip" style="background-color: rgba(106, 90, 205, 0.2); color: white; font-size: 0.8rem;">${theme}</span>`).join('')}
                </div>
                <div style="margin-top: 15px; display: flex; gap: 15px; font-size: 0.85rem; color: var(--rpg-silver);">
                    <span><i class="material-icons tiny">timer</i> ${story.estimated_length}</span>
                    <span><i class="material-icons tiny">trending_up</i> ${story.difficulty_level}</span>
                </div>
            `;

            card.appendChild(contentDiv);
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
        // Simply call generateStoryIdeas again with a fresh request
        // This ensures we get NEW story ideas instead of cached ones
        await generateStoryIdeas();
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
        const maxAttempts = 180; // 6 minutes max (was 2 minutes)
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0) {
                updateLoadingMessage('core', 'Generating campaign core...', `Still working... (${Math.floor(attempts / 30)} minute${attempts >= 60 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Campaign core generation timed out. The generation may still be running in the background. Please refresh the page or check back later.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                // Update loading message with progress if available
                if (data.progress_percentage) {
                    updateLoadingMessage('core', `Generating campaign core... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

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

        // Format plot and storyline into paragraphs
        const formatTextParagraphs = (text) => {
            if (!text) return '';
            // Split by double newlines or periods followed by newlines, create <p> tags for each paragraph
            return text.split(/\n\n+/).map(para =>
                `<p style="color: #b8b8d1; line-height: 1.6; margin-bottom: 15px;">${para.trim()}</p>`
            ).join('');
        };

        container.innerHTML = `
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Campaign Name:</strong>
                <p style="color: #b8b8d1;">${core.name || 'Untitled Campaign'}</p>
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Plot:</strong>
                ${formatTextParagraphs(core.plot)}
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Storyline:</strong>
                ${formatTextParagraphs(core.storyline)}
            </div>
            <div class="review-section">
                <strong style="color: var(--rpg-gold);">Primary Objectives:</strong>
                <ol style="color: #b8b8d1;">
                    ${core.primary_objectives.map(obj => `
                        <li style="margin-bottom: 10px;">
                            ${obj.description}
                        </li>
                    `).join('')}
                </ol>
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

        // Hide Bloom's info section (removed per user request)
        const bloomsInfo = document.getElementById('blooms-info');
        if (bloomsInfo) {
            bloomsInfo.style.display = 'none';
        }
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
        const maxAttempts = 300; // 10 minutes for quest generation (was 4 minutes)
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0 && attempts < maxAttempts - 15) {
                const minutesElapsed = Math.floor(attempts / 30);
                updateLoadingMessage('quests', 'Generating quests...', `Still working... (${minutesElapsed} minute${minutesElapsed !== 1 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Quest generation timed out. The quest generation may still be running in the background. Please check the campaign list or refresh the page.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                // Update loading message with progress
                if (data.progress_percentage) {
                    updateLoadingMessage('quests', `Generating quests... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

                // Check if campaign already finalized (auto-finalization)
                if (data.final_campaign_id) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    localStorage.removeItem('campaign_wizard_request_id');
                    M.toast({html: 'Campaign created successfully!', classes: 'green'});
                    window.location.href = `/campaigns/${data.final_campaign_id}/`;
                    return;
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
                    <ol style="color: #b8b8d1; font-size: 0.9rem; margin-top: 5px;">
                        ${quest.objectives.map(obj => `
                            <li style="margin-bottom: 8px;">
                                ${obj.description}
                            </li>
                        `).join('')}
                    </ol>
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
        const maxAttempts = 180; // 6 minutes for place generation (was 4 minutes)
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0 && attempts < maxAttempts - 15) {
                const minutesElapsed = Math.floor(attempts / 30);
                updateLoadingMessage('places', 'Generating places...', `Still working... (${minutesElapsed} minute${minutesElapsed !== 1 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Place generation timed out. The generation may still be running in the background. Please check back later.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.progress_percentage) {
                    updateLoadingMessage('places', `Generating places... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

                // Check if campaign already finalized (auto-finalization)
                if (data.final_campaign_id) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    localStorage.removeItem('campaign_wizard_request_id');
                    M.toast({html: 'Campaign created successfully!', classes: 'green'});
                    window.location.href = `/campaigns/${data.final_campaign_id}/`;
                    return;
                }

                if (data.places && data.places.length > 0) {
                    clearInterval(pollInterval);
                    wizardState.places = data.places;
                    wizardState.new_locations = wizardState.new_locations.concat(data.new_locations || []);
                    displayPlaces(data.places, data.new_locations || []);
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
    function displayPlaces(places, newLocations) {
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
                        <strong style="color: var(--rpg-purple); display: flex; align-items: center; gap: 8px;">
                            <i class="material-icons" style="font-size: 1.2rem;">map</i>
                            <span>${place.name}</span>
                        </strong>
                        <p style="color: #b8b8d1; font-size: 0.9rem; margin-top: 8px;">
                            ${place.description}
                        </p>
                    </div>
                `).join('')}
            `;
            container.appendChild(card);
        });

        // Show new locations if any were created
        const level2NewLocations = newLocations.filter(loc => loc.level === 2);
        if (level2NewLocations.length > 0) {
            document.getElementById('new-locations-created-l2').style.display = 'block';
            const locationList = document.getElementById('new-locations-list-l2');
            locationList.innerHTML = level2NewLocations.map((loc, idx) => `
                <li style="margin-bottom: 12px;"><strong>${loc.name}</strong> (${loc.type}) - ${loc.description || 'New location added to world'}</li>
            `).join('');
            // Change to ordered list
            locationList.parentElement.querySelector('#new-locations-list-l2').style.listStyleType = 'decimal';
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
        const maxAttempts = 300; // 10 minutes for scene + element generation (was 6 minutes)
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0 && attempts < maxAttempts - 15) {
                const minutesElapsed = Math.floor(attempts / 30);
                updateLoadingMessage('scenes', 'Generating scenes...', `Still working... (${minutesElapsed} minute${minutesElapsed !== 1 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Scene generation timed out. The generation may still be running in the background. Please check back later.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.progress_percentage) {
                    updateLoadingMessage('scenes', `Generating scenes... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

                // Check if campaign already finalized (auto-finalization)
                if (data.final_campaign_id) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    localStorage.removeItem('campaign_wizard_request_id');
                    M.toast({html: 'Campaign created successfully!', classes: 'green'});
                    window.location.href = `/campaigns/${data.final_campaign_id}/`;
                    return;
                }

                if (data.scenes && data.scenes.length > 0) {
                    clearInterval(pollInterval);
                    wizardState.scenes = data.scenes;
                    wizardState.new_locations = wizardState.new_locations.concat(data.new_locations || []);
                    displayScenes(data.scenes, data.new_locations || [], data.npcs || [], data.discoveries || []);
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
    function displayScenes(scenes, newLocations, npcs, discoveries) {
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
                        <div style="margin-top: 10px; font-size: 0.85rem; color: var(--rpg-silver); display: flex; align-items: center; gap: 4px;">
                            <i class="material-icons tiny">movie</i>
                            <span>${scene.level_3_location_name}</span>
                        </div>

                        ${(scene.npc_ids && scene.npc_ids.length > 0) || (npcs && npcs.length > 0) ? `
                            <div style="margin-top: 10px;">
                                <strong style="color: var(--rpg-gold); font-size: 0.85rem;">NPCs:</strong>
                                <div style="margin-top: 5px;">
                                    ${scene.npc_ids ? scene.npc_ids.map(npcId => {
                                        const npc = npcs ? npcs.find(n => n.npc_id === npcId) : null;
                                        return npc ? `<span class="chip" style="background-color: rgba(212, 175, 55, 0.2); font-size: 0.75rem;">${npc.name} (${npc.role})</span>` : '';
                                    }).filter(html => html).join('') : ''}
                                </div>
                            </div>
                        ` : ''}

                        ${(scene.discovery_ids && scene.discovery_ids.length > 0) || (discoveries && discoveries.length > 0) ? `
                            <div style="margin-top: 10px;">
                                <strong style="color: var(--rpg-gold); font-size: 0.85rem;">Knowledge & Discoveries:</strong>
                                <div style="margin-top: 5px;">
                                    ${scene.discovery_ids ? scene.discovery_ids.map(discId => {
                                        const disc = discoveries ? discoveries.find(d => d.discovery_id === discId) : null;
                                        return disc ? `<span class="knowledge-item">${disc.name}</span>` : '';
                                    }).filter(html => html).join('') : ''}
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
        const level3NewLocations = newLocations.filter(loc => loc.level === 3);
        if (level3NewLocations.length > 0) {
            document.getElementById('new-locations-created-l3').style.display = 'block';
            const locationList = document.getElementById('new-locations-list-l3');
            locationList.innerHTML = level3NewLocations.map(loc => `
                <li style="margin-bottom: 12px;"><strong>${loc.name}</strong> (${loc.type}) - ${loc.description || 'New location added to world'}</li>
            `).join('');
        }
    }

    /**
     * Populate final review
     */
    async function populateFinalReview() {
        // Show campaign name in final review if the element exists
        const campaignNameElement = document.getElementById('final-review-campaign-name');
        if (campaignNameElement) {
            campaignNameElement.textContent = wizardState.campaign_name || 'Untitled Campaign';
        }

        document.getElementById('final-review-universe').textContent = wizardState.universe_name;
        document.getElementById('final-review-world').textContent = `${wizardState.world_name} (${wizardState.world_genre})`;
        document.getElementById('final-review-region').textContent = wizardState.region_name || 'Entire World';
        document.getElementById('final-review-story').textContent = wizardState.selected_story ? wizardState.selected_story.title : 'N/A';
        document.getElementById('final-review-quests').textContent = `${wizardState.quests.length} Quests (${wizardState.quest_difficulty} difficulty, ~${wizardState.quest_playtime_minutes} min each)`;
        document.getElementById('final-review-summary').textContent = `Campaign "${wizardState.campaign_name}" includes ${wizardState.quests.length} quests, ${wizardState.places.length} places, ${wizardState.scenes.length} scenes. ${wizardState.new_locations.length} new locations were created.`;

        // NEW: Load and display validation report
        await loadValidationReport();
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

            // Start polling for completion instead of expecting immediate response
            await pollFinalization();
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

        // Reset progress bar
        const progressBar = document.getElementById('progress-bar-fill');
        if (progressBar) {
            progressBar.style.width = '10%';
        }

        // Reset progress displays
        const overallProgress = document.getElementById('overall-progress-percentage');
        const stepProgress = document.getElementById('step-progress-percentage');
        if (overallProgress) overallProgress.textContent = '0';
        if (stepProgress) stepProgress.textContent = '0';

        // Start timer
        startTimer();

        // Hide error notifications initially
        const errorDiv = document.getElementById('progress-errors');
        const warningDiv = document.getElementById('progress-warnings');
        if (errorDiv) errorDiv.style.display = 'none';
        if (warningDiv) warningDiv.style.display = 'none';

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
        } else {
            document.getElementById('loading-detail-message').textContent = 'This may take a few minutes.';
        }
    }

    /**
     * Calculate step progress within current phase
     * Phase ranges based on backend: story(0-10), core(10-15), quests(15-35), places(35-55), scenes(55-98), finalize(98-100)
     * Note: Backend has element generation at 95-98%, but frontend treats it as part of scenes phase
     */
    function calculateStepProgress(phase, overallProgress) {
        const phaseRanges = {
            'story': { start: 0, end: 10 },
            'core': { start: 10, end: 15 },
            'quests': { start: 15, end: 35 },
            'places': { start: 35, end: 55 },
            'scenes': { start: 55, end: 98 },  // Includes element generation (95-98%)
            'finalize': { start: 98, end: 100 }
        };

        const range = phaseRanges[phase];
        if (!range) return 0;

        const phaseWidth = range.end - range.start;
        const progressWithinPhase = overallProgress - range.start;
        const stepPercentage = (progressWithinPhase / phaseWidth) * 100;

        // Clamp between 0 and 100
        return Math.max(0, Math.min(100, stepPercentage));
    }

    function updateLoadingMessage(phase, statusMessage, detailMessage = null, progressPercentage = null, stepProgressPercentage = null, errors = null) {
        document.getElementById('loading-status-message').textContent = statusMessage;
        if (detailMessage) {
            document.getElementById('loading-detail-message').textContent = detailMessage;
        }

        // FIX: Update progress bar based on BACKEND progress_percentage instead of phase calculation
        const progressBar = document.getElementById('progress-bar-fill');
        if (progressBar && progressPercentage !== null) {
            // Use backend progress percentage to keep status text and progress bar in sync
            progressBar.style.width = progressPercentage + '%';
        } else if (progressBar) {
            // Fallback: Calculate based on phase if no percentage provided
            // NEW: Added objective hierarchy steps (decompose, design, assign_rubrics, plan_narrative)
            const phases = ['story', 'core', 'decompose_objectives', 'design_child_objectives', 'assign_rubrics', 'plan_narrative', 'quests', 'places', 'scenes', 'finalize'];
            const currentIndex = phases.indexOf(phase);
            const calculatedPercentage = ((currentIndex + 1) / phases.length) * 100;
            progressBar.style.width = calculatedPercentage + '%';
        }

        // Update Overall Progress display
        const overallProgress = document.getElementById('overall-progress-percentage');
        if (overallProgress && progressPercentage !== null) {
            overallProgress.textContent = Math.floor(progressPercentage);
        }

        // Update Step Progress display - use backend value if available, otherwise calculate
        const stepProgress = document.getElementById('step-progress-percentage');
        if (stepProgress) {
            // Use backend step_progress if available (during element generation), otherwise calculate from phase
            const stepProgressValue = (stepProgressPercentage !== null) ? stepProgressPercentage :
                                     (progressPercentage !== null) ? calculateStepProgress(phase, progressPercentage) : 0;
            stepProgress.textContent = Math.floor(stepProgressValue);
        }

        // Display errors if present
        if (errors && errors.length > 0) {
            displayErrors(errors);
        }

        // Mark completed phases
        // NEW: Added objective hierarchy steps
        const phases = ['story', 'core', 'decompose_objectives', 'design_child_objectives', 'assign_rubrics', 'plan_narrative', 'quests', 'places', 'scenes', 'finalize'];
        const currentIndex = phases.indexOf(phase);
        phases.forEach((p, idx) => {
            const stepEl = document.querySelector(`.phase-step[data-phase="${p}"]`);
            if (stepEl) {
                if (idx < currentIndex) {
                    stepEl.classList.add('completed');
                    stepEl.classList.remove('active');
                } else if (idx === currentIndex) {
                    stepEl.classList.add('active');
                    stepEl.classList.remove('completed');
                }
            }
        });

        // Update status message with user-friendly labels for new phases
        const phaseLabels = {
            'story': 'Generating Story Ideas',
            'core': 'Generating Campaign Core',
            'decompose_objectives': '🎯 Decomposing Objectives',
            'design_child_objectives': '🔍 Designing Child Objectives',
            'assign_rubrics': '📊 Assigning Rubrics',
            'plan_narrative': '📖 Planning Narrative',
            'quests': 'Generating Quests',
            'places': 'Generating Places',
            'scenes': 'Generating Scenes',
            'finalize': 'Finalizing Campaign'
        };

        // If the status message contains a phase label, update it
        if (phaseLabels[phase] && !statusMessage.includes('%')) {
            document.getElementById('loading-status-message').textContent = phaseLabels[phase];
        }
    }

    function hideLoadingOverlay() {
        // Mark current phase as completed before hiding
        const activePhase = document.querySelector('.phase-step.active');
        if (activePhase) {
            activePhase.classList.add('completed');
            activePhase.classList.remove('active');
        }

        // Set progress bar to 100%
        const progressBar = document.getElementById('progress-bar-fill');
        if (progressBar) {
            progressBar.style.width = '100%';
        }

        // Update progress displays to 100%
        const overallProgress = document.getElementById('overall-progress-percentage');
        const stepProgress = document.getElementById('step-progress-percentage');
        if (overallProgress) overallProgress.textContent = '100';
        if (stepProgress) stepProgress.textContent = '100';

        // Stop timer
        stopTimer();

        // Hide overlay after a brief delay to show completion
        setTimeout(() => {
            document.getElementById('loading-overlay').style.display = 'none';
            // Reset for next use
            if (progressBar) {
                progressBar.style.width = '0%';
            }
        }, 500);

        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    /**
     * Timer functions
     */
    function startTimer() {
        // Clear any existing timer
        if (timerInterval) {
            clearInterval(timerInterval);
        }

        // Set start time
        timerStartTime = Date.now();

        // Update timer display immediately
        updateTimerDisplay();

        // Update timer every second
        timerInterval = setInterval(updateTimerDisplay, 1000);
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        timerStartTime = null;
    }

    function updateTimerDisplay() {
        if (!timerStartTime) return;

        const elapsed = Math.floor((Date.now() - timerStartTime) / 1000); // seconds
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;

        const timerEl = document.getElementById('elapsed-timer');
        if (timerEl) {
            timerEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
    }

    /**
     * Error display function
     */
    function displayErrors(errors) {
        const errorDiv = document.getElementById('progress-errors');
        const errorList = document.getElementById('progress-error-list');

        if (!errorDiv || !errorList) return;

        // Clear existing errors
        errorList.innerHTML = '';

        // Add each error as a list item
        errors.forEach(error => {
            const li = document.createElement('li');
            li.textContent = error;
            errorList.appendChild(li);
        });

        // Show error div
        errorDiv.style.display = 'block';
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

    /**
     * Check for in-progress campaigns
     */
    async function checkInProgressCampaigns() {
        try {
            const response = await fetch('/campaigns/wizard/api/in-progress');
            if (!response.ok) return;

            const data = await response.json();

            if (data.success && data.campaigns && data.campaigns.length > 0) {
                // Show banner with the most recent campaign
                const campaign = data.campaigns[0];
                displayInProgressBanner(campaign);
            }
        } catch (error) {
            console.error('Error checking in-progress campaigns:', error);
        }
    }

    /**
     * Display in-progress banner
     */
    function displayInProgressBanner(campaign) {
        const banner = document.getElementById('in-progress-banner');

        // Update banner content
        document.getElementById('in-progress-campaign-name').textContent = campaign.campaign_name || 'Untitled Campaign';
        document.getElementById('in-progress-universe').textContent = campaign.universe_name || 'Unknown Universe';
        document.getElementById('in-progress-world').textContent = campaign.world_name || 'Unknown World';
        document.getElementById('in-progress-percentage').textContent = (campaign.progress_percentage || 0) + '%';
        document.getElementById('in-progress-status').textContent = campaign.status_message || 'Processing...';
        document.getElementById('in-progress-bar').style.width = (campaign.progress_percentage || 0) + '%';

        // Show banner
        banner.style.display = 'block';

        // Setup resume button handler
        document.getElementById('resume-campaign-btn').onclick = function() {
            reopenProgressModal(campaign.request_id);
        };
    }

    /**
     * Close loading overlay manually
     */
    function closeLoadingOverlay() {
        // Stop any active polling
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }

        // Stop timer
        stopTimer();

        // Hide overlay
        document.getElementById('loading-overlay').style.display = 'none';

        M.toast({html: 'Progress overlay closed. Generation continues in background.', classes: 'blue'});
    }

    /**
     * Reopen progress modal for existing campaign
     */
    async function reopenProgressModal(existingRequestId) {
        // Set the request ID
        requestId = existingRequestId;

        // Save to localStorage
        localStorage.setItem('campaign_wizard_request_id', requestId);

        // Fetch current status to determine which phase to show
        try {
            const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
            if (!response.ok) {
                M.toast({html: 'Unable to resume campaign', classes: 'red'});
                return;
            }

            const data = await response.json();

            // Populate wizard state with what's been generated
            if (data.campaign_name) wizardState.campaign_name = data.campaign_name;
            if (data.universe_id) wizardState.universe_id = data.universe_id;
            if (data.universe_name) wizardState.universe_name = data.universe_name;
            if (data.world_id) wizardState.world_id = data.world_id;
            if (data.world_name) wizardState.world_name = data.world_name;
            if (data.world_genre) wizardState.world_genre = data.world_genre;
            if (data.region_id) wizardState.region_id = data.region_id;
            if (data.region_name) wizardState.region_name = data.region_name;
            if (data.selected_story_id) wizardState.selected_story_id = data.selected_story_id;
            if (data.selected_story) wizardState.selected_story = data.selected_story;
            if (data.campaign_core) wizardState.campaign_core = data.campaign_core;
            if (data.quests) wizardState.quests = data.quests;
            if (data.places) wizardState.places = data.places;
            if (data.scenes) wizardState.scenes = data.scenes;

            // Determine which step to navigate to and what phase to show
            let targetStep = 1;
            let phase = 'story';
            let statusMsg = 'Generating story ideas...';

            if (data.scenes && data.scenes.length > 0) {
                targetStep = 10;
                phase = 'finalize';
                statusMsg = 'Finalizing campaign...';
                // Display scenes
                displayScenes(data.scenes, data.new_locations || [], data.npcs || [], data.discoveries || []);
            } else if (data.places && data.places.length > 0) {
                targetStep = 9;
                phase = 'scenes';
                statusMsg = 'Generating scenes with NPCs, challenges, events, and discoveries...';
                // Display places
                displayPlaces(data.places, data.new_locations || []);
            } else if (data.quests && data.quests.length > 0) {
                targetStep = 8;
                phase = 'places';
                statusMsg = 'Generating places...';
                // Display quests
                displayQuests(data.quests);
            } else if (data.campaign_core) {
                targetStep = 6;
                phase = 'quests';
                statusMsg = 'Generating quests...';
                // Display campaign core
                displayCampaignCore(data.campaign_core);
            } else if (data.story_ideas && data.story_ideas.length > 0) {
                targetStep = 5;
                phase = 'core';
                statusMsg = 'Generating campaign core...';
                // Display story ideas
                displayStoryIdeas(data.story_ideas);
            }

            // Navigate to the appropriate wizard step
            currentStep = targetStep;
            updateProgress();

            // Show loading overlay with current phase
            showLoadingOverlay(phase, statusMsg);

            // Start polling based on current phase
            if (phase === 'finalize') {
                // Already finalized, just poll to check completion
                await pollFinalization();
            } else if (phase === 'scenes') {
                await pollScenes();
            } else if (phase === 'places') {
                await pollPlaces();
            } else if (phase === 'quests') {
                await pollQuests();
            } else if (phase === 'core') {
                await pollCampaignCore();
            } else {
                await pollStoryIdeas();
            }
        } catch (error) {
            console.error('Error resuming campaign:', error);
            M.toast({html: 'Error resuming campaign', classes: 'red'});
        }
    }

    // Setup close button handler for loading overlay
    const closeOverlayBtn = document.getElementById('close-loading-overlay-btn');
    if (closeOverlayBtn) {
        closeOverlayBtn.addEventListener('click', closeLoadingOverlay);
    }

    /**
     * Poll for finalization completion
     */
    async function pollFinalization() {
        const maxAttempts = 600; // 20 minutes max
        let attempts = 0;

        pollInterval = setInterval(async () => {
            attempts++;

            // Show "Still working..." message every 30 seconds
            if (attempts % 15 === 0 && attempts < maxAttempts - 15) {
                const minutesElapsed = Math.floor(attempts / 30);
                updateLoadingMessage('finalize', 'Finalizing campaign...', `Still working... (${minutesElapsed} minute${minutesElapsed !== 1 ? 's' : ''} elapsed)`);
            }

            if (attempts > maxAttempts) {
                clearInterval(pollInterval);
                hideLoadingOverlay();
                M.toast({html: 'Finalization timed out. The finalization may still be running in the background. Please check back later.', classes: 'orange', displayLength: 8000});
                return;
            }

            try {
                const response = await fetch(`/campaigns/wizard/api/status/${requestId}`);
                if (!response.ok) return;

                const data = await response.json();

                if (data.progress_percentage) {
                    updateLoadingMessage('finalize', `Finalizing campaign... ${data.progress_percentage}%`, data.status_message, data.progress_percentage, data.step_progress, data.errors);
                }

                if (data.final_campaign_id) {
                    clearInterval(pollInterval);
                    hideLoadingOverlay();
                    // Clear localStorage since campaign is complete
                    localStorage.removeItem('campaign_wizard_request_id');
                    M.toast({html: 'Campaign created successfully!', classes: 'green'});
                    window.location.href = `/campaigns/${data.final_campaign_id}/`;
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
     * Load and display validation report
     */
    async function loadValidationReport() {
        if (!requestId) return;

        const validationContainer = document.getElementById('validation-report-container');
        if (!validationContainer) return;

        validationContainer.innerHTML = '<div class="center-align" style="padding: 20px;"><div class="preloader-wrapper small active"><div class="spinner-layer spinner-blue-only"><div class="circle-clipper left"><div class="circle"></div></div><div class="gap-patch"><div class="circle"></div></div><div class="circle-clipper right"><div class="circle"></div></div></div></div><p style="color: var(--rpg-silver); margin-top: 15px;">Loading validation report...</p></div>';

        try {
            const response = await fetch(`/campaigns/wizard/api/validation-report/${requestId}`);
            if (!response.ok) {
                validationContainer.innerHTML = '<p style="color: var(--rpg-silver);">Validation report not available yet.</p>';
                return;
            }

            const data = await response.json();
            const report = data.validation_report;

            if (!report) {
                validationContainer.innerHTML = '<p style="color: var(--rpg-silver);">No validation report found.</p>';
                return;
            }

            displayValidationReport(report);
        } catch (error) {
            console.error('Error loading validation report:', error);
            validationContainer.innerHTML = '<p style="color: #f44336;">Error loading validation report.</p>';
        }
    }

    /**
     * Display validation report
     */
    function displayValidationReport(report) {
        const container = document.getElementById('validation-report-container');

        const passed = report.validation_passed;
        const stats = report.stats || {};
        const errors = report.errors || [];
        const warnings = report.warnings || [];

        const statusColor = passed ? 'var(--rpg-green)' : '#f44336';
        const statusIcon = passed ? 'check_circle' : 'error';
        const statusText = passed ? 'PASSED' : 'FAILED';

        let html = `
            <div style="margin-bottom: 25px;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
                    <i class="material-icons" style="color: ${statusColor}; font-size: 32px;">${statusIcon}</i>
                    <h5 style="color: ${statusColor}; margin: 0;">Objective Cascade Validation: ${statusText}</h5>
                </div>

                <!-- Statistics Dashboard -->
                <div class="row" style="margin-bottom: 20px;">
                    <div class="col s6 m3">
                        <div style="padding: 15px; background: rgba(76, 175, 80, 0.1); border-radius: 8px; text-align: center;">
                            <div style="font-size: 28px; color: var(--rpg-green); font-weight: bold;">${stats.campaign_objectives_covered || 0}/${stats.total_campaign_objectives || 0}</div>
                            <div style="color: #b8b8d1; font-size: 0.85rem; margin-top: 5px;">Campaign Objectives</div>
                        </div>
                    </div>
                    <div class="col s6 m3">
                        <div style="padding: 15px; background: rgba(76, 175, 80, 0.1); border-radius: 8px; text-align: center;">
                            <div style="font-size: 28px; color: var(--rpg-green); font-weight: bold;">${stats.quest_objectives_addressable || 0}/${stats.total_quest_objectives || 0}</div>
                            <div style="color: #b8b8d1; font-size: 0.85rem; margin-top: 5px;">Quest Objectives</div>
                        </div>
                    </div>
                    <div class="col s6 m3">
                        <div style="padding: 15px; background: rgba(76, 175, 80, 0.1); border-radius: 8px; text-align: center;">
                            <div style="font-size: 28px; color: var(--rpg-green); font-weight: bold;">${stats.knowledge_acquirable || 0}/${stats.total_knowledge || 0}</div>
                            <div style="color: #b8b8d1; font-size: 0.85rem; margin-top: 5px;">Knowledge Items</div>
                        </div>
                    </div>
                    <div class="col s6 m3">
                        <div style="padding: 15px; background: ${stats.items_with_redundancy < stats.total_items ? 'rgba(255, 193, 7, 0.1)' : 'rgba(76, 175, 80, 0.1)'}; border-radius: 8px; text-align: center;">
                            <div style="font-size: 28px; color: ${stats.items_with_redundancy < stats.total_items ? '#FFC107' : 'var(--rpg-green)'}; font-weight: bold;">${stats.items_with_redundancy || 0}/${stats.total_items || 0}</div>
                            <div style="color: #b8b8d1; font-size: 0.85rem; margin-top: 5px;">Items with Redundancy</div>
                        </div>
                    </div>
                </div>
        `;

        // Display errors if any
        if (errors.length > 0) {
            html += `
                <div style="margin-top: 20px; padding: 15px; background: rgba(244, 67, 54, 0.1); border-left: 3px solid #f44336; border-radius: 4px;">
                    <h6 style="color: #f44336; margin-top: 0;"><i class="material-icons tiny" style="vertical-align: middle;">error</i> Errors (${errors.length})</h6>
                    <ul style="margin-bottom: 0;">
            `;
            errors.forEach(error => {
                html += `
                    <li style="color: #b8b8d1; margin-bottom: 10px;">
                        <strong style="color: #f44336;">${error.check}:</strong> ${error.message}
                        ${error.recommendations && error.recommendations.length > 0 ? `
                            <div style="margin-top: 5px; padding-left: 15px; color: #90caf9;">
                                <strong>Recommendation:</strong> ${error.recommendations[0]}
                            </div>
                        ` : ''}
                    </li>
                `;
            });
            html += `
                    </ul>
                </div>
            `;
        }

        // Display warnings if any
        if (warnings.length > 0) {
            html += `
                <div style="margin-top: 20px; padding: 15px; background: rgba(255, 193, 7, 0.1); border-left: 3px solid #FFC107; border-radius: 4px;">
                    <h6 style="color: #FFC107; margin-top: 0;"><i class="material-icons tiny" style="vertical-align: middle;">warning</i> Warnings (${warnings.length})</h6>
                    <ul style="margin-bottom: 0;">
            `;
            warnings.forEach(warning => {
                html += `
                    <li style="color: #b8b8d1; margin-bottom: 10px;">
                        <strong style="color: #FFC107;">${warning.check}:</strong> ${warning.message}
                        ${warning.recommendations && warning.recommendations.length > 0 ? `
                            <div style="margin-top: 5px; padding-left: 15px; color: #90caf9;">
                                <strong>Recommendation:</strong> ${warning.recommendations[0]}
                            </div>
                        ` : ''}
                    </li>
                `;
            });
            html += `
                    </ul>
                </div>
            `;
        }

        // Success message
        if (passed && errors.length === 0) {
            html += `
                <div style="margin-top: 20px; padding: 15px; background: rgba(76, 175, 80, 0.1); border-left: 3px solid var(--rpg-green); border-radius: 4px;">
                    <p style="color: var(--rpg-green); margin: 0;">
                        <i class="material-icons tiny" style="vertical-align: middle;">check_circle</i>
                        <strong>All validation checks passed!</strong> ${warnings.length > 0 ? 'There are some warnings, but they are non-critical and the campaign can proceed.' : 'Your campaign is ready for finalization.'}
                    </p>
                </div>
            `;
        }

        html += `</div>`;
        container.innerHTML = html;
    }

    /**
     * Load and display objective decomposition
     */
    async function loadObjectiveDecomposition() {
        if (!requestId) return;

        const objectiveContainer = document.getElementById('objective-decomposition-container');
        if (!objectiveContainer) return;

        objectiveContainer.innerHTML = '<div class="center-align" style="padding: 20px;"><div class="preloader-wrapper small active"><div class="spinner-layer spinner-blue-only"><div class="circle-clipper left"><div class="circle"></div></div><div class="gap-patch"><div class="circle"></div></div><div class="circle-clipper right"><div class="circle"></div></div></div></div><p style="color: var(--rpg-silver); margin-top: 15px;">Loading objective decomposition...</p></div>';

        try {
            const response = await fetch(`/campaigns/wizard/api/objective-decomposition/${requestId}`);
            if (!response.ok) {
                objectiveContainer.innerHTML = '<p style="color: var(--rpg-silver);">Objective decomposition not available yet.</p>';
                return;
            }

            const data = await response.json();
            const decompositions = data.objective_decompositions || [];

            if (decompositions.length === 0) {
                objectiveContainer.innerHTML = '<p style="color: var(--rpg-silver);">No objective decompositions found.</p>';
                return;
            }

            displayObjectiveDecomposition(decompositions);
        } catch (error) {
            console.error('Error loading objective decomposition:', error);
            objectiveContainer.innerHTML = '<p style="color: #f44336;">Error loading objective decomposition.</p>';
        }
    }

    /**
     * Display objective decomposition tree
     */
    function displayObjectiveDecomposition(decompositions) {
        const container = document.getElementById('objective-decomposition-container');

        let html = '<div style="padding: 15px; background: rgba(27, 27, 46, 0.4); border-radius: 8px;">';

        decompositions.forEach((decomp, index) => {
            html += `
                <div style="margin-bottom: ${index < decompositions.length - 1 ? '30px' : '0'}; padding: 15px; background: rgba(106, 90, 205, 0.1); border-left: 3px solid var(--rpg-purple); border-radius: 4px;">
                    <h6 style="color: var(--rpg-gold); margin-top: 0;">
                        <i class="material-icons tiny" style="vertical-align: middle;">flag</i>
                        Campaign Objective: ${decomp.campaign_objective_description}
                    </h6>

                    ${decomp.completion_criteria && decomp.completion_criteria.length > 0 ? `
                        <div style="margin: 10px 0; padding-left: 25px;">
                            <strong style="color: var(--rpg-silver); font-size: 0.9rem;">Completion Criteria:</strong>
                            <ul style="margin: 5px 0 10px 0;">
                                ${decomp.completion_criteria.map(criteria => `<li style="color: #b8b8d1; font-size: 0.85rem;">${criteria}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    <div style="padding-left: 25px; margin-top: 15px;">
                        <strong style="color: var(--rpg-silver);">Quest Objectives (${decomp.minimum_quests_required || 1} required):</strong>
                        ${(decomp.quest_objectives || []).map((qobj, qIndex) => `
                            <div style="margin-top: 12px; padding: 12px; background: rgba(27, 27, 46, 0.6); border-radius: 4px;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="display: inline-block; width: 24px; height: 24px; background: var(--rpg-purple); color: white; border-radius: 50%; text-align: center; line-height: 24px; font-size: 0.8rem; font-weight: bold;">${qobj.quest_number || qIndex + 1}</span>
                                    <span style="color: var(--rpg-gold); font-weight: bold;">Quest ${qobj.quest_number || qIndex + 1}: ${qobj.description}</span>
                                </div>

                                ${qobj.success_criteria && qobj.success_criteria.length > 0 ? `
                                    <div style="margin-top: 8px; padding-left: 32px;">
                                        <span style="color: var(--rpg-silver); font-size: 0.85rem;">Success Criteria:</span>
                                        <ul style="margin: 3px 0;">
                                            ${qobj.success_criteria.map(criteria => `<li style="color: #b8b8d1; font-size: 0.8rem;">${criteria}</li>`).join('')}
                                        </ul>
                                    </div>
                                ` : ''}

                                ${qobj.required_knowledge_domains && qobj.required_knowledge_domains.length > 0 ? `
                                    <div style="margin-top: 8px; padding-left: 32px;">
                                        <span style="color: var(--rpg-silver); font-size: 0.85rem;">Required Knowledge:</span>
                                        <div style="margin-top: 3px;">
                                            ${qobj.required_knowledge_domains.map(domain => `
                                                <span class="chip" style="background-color: rgba(106, 90, 205, 0.2); color: var(--rpg-purple); font-size: 0.75rem; height: 24px; line-height: 24px; margin: 2px;">
                                                    <i class="material-icons tiny" style="vertical-align: middle;">school</i> ${domain}
                                                </span>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}

                                ${qobj.required_item_categories && qobj.required_item_categories.length > 0 ? `
                                    <div style="margin-top: 8px; padding-left: 32px;">
                                        <span style="color: var(--rpg-silver); font-size: 0.85rem;">Required Items:</span>
                                        <div style="margin-top: 3px;">
                                            ${qobj.required_item_categories.map(category => `
                                                <span class="chip" style="background-color: rgba(255, 193, 7, 0.2); color: #FFC107; font-size: 0.75rem; height: 24px; line-height: 24px; margin: 2px;">
                                                    <i class="material-icons tiny" style="vertical-align: middle;">inventory_2</i> ${category}
                                                </span>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}

                                ${qobj.blooms_level ? `
                                    <div style="margin-top: 8px; padding-left: 32px;">
                                        <span class="chip" style="background-color: rgba(76, 175, 80, 0.2); color: var(--rpg-green); font-size: 0.75rem; height: 24px; line-height: 24px;">
                                            Bloom's Level ${qobj.blooms_level}
                                        </span>
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    // Initialize
    updateProgress();
});
