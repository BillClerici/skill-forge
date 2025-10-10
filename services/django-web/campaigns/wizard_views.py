"""
Campaign Wizard Views
Multi-step wizard for creating campaigns using LangGraph workflow
"""
import os
import json
import uuid
import httpx
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from pymongo import MongoClient
from neo4j import GraphDatabase

# MongoDB connection
mongo_client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017/'))
mongo_db = mongo_client.skillforge

# Neo4j connection
neo4j_driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL', 'bolt://localhost:7687'),
    auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'password'))
)

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://localhost:9000')


@login_required
def campaign_wizard_start(request):
    """
    Step 1: Select Universe, World, Region
    """
    # Fetch user's characters
    from members.models import Character
    characters = Character.objects.filter(player=request.user).select_related('player')

    # Fetch universes from MongoDB
    universes = list(mongo_db.universes.find({}))

    context = {
        'characters': characters,
        'universes': universes,
        'step': 1
    }

    return render(request, 'campaigns/wizard/step1_select_world.html', context)


@login_required
@require_http_methods(["POST"])
def campaign_wizard_init(request):
    """
    Initialize campaign wizard workflow

    POST data:
    - character_id: Selected character
    - universe_id: Selected universe
    - world_id: Selected world
    - region_id: Selected region
    - user_story_idea: Optional user story direction
    """
    try:
        # Get form data
        character_id = request.POST.get('character_id')
        universe_id = request.POST.get('universe_id')
        world_id = request.POST.get('world_id')
        region_id = request.POST.get('region_id')
        user_story_idea = request.POST.get('user_story_idea', '')

        # Fetch selected entities from MongoDB
        universe = mongo_db.universes.find_one({'_id': universe_id})
        world = mongo_db.worlds.find_one({'_id': world_id})
        region = mongo_db.regions.find_one({'_id': region_id})

        if not universe or not world or not region:
            return JsonResponse({'error': 'Selected universe, world, or region not found'}, status=404)

        # Generate request ID
        request_id = str(uuid.uuid4())

        # Store request in session
        request.session['campaign_wizard'] = {
            'request_id': request_id,
            'character_id': character_id,
            'universe_id': universe_id,
            'universe_name': universe.get('name'),
            'world_id': world_id,
            'world_name': world.get('name'),
            'region_id': region_id,
            'region_name': region.get('name'),
            'genre': world.get('genre'),
            'user_story_idea': user_story_idea,
            'step': 2
        }

        # Call orchestrator to start workflow
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/start",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id),
                    'character_id': character_id,
                    'universe_id': universe_id,
                    'universe_name': universe.get('name'),
                    'world_id': world_id,
                    'world_name': world.get('name'),
                    'region_id': region_id,
                    'region_name': region.get('name'),
                    'genre': world.get('genre'),
                    'user_story_idea': user_story_idea
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to start campaign workflow'}, status=500)

        return JsonResponse({
            'status': 'success',
            'request_id': request_id,
            'redirect_url': '/campaigns/wizard/story-selection/'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def campaign_wizard_story_selection(request):
    """
    Step 2: Select story idea from 3 generated options
    """
    wizard_data = request.session.get('campaign_wizard', {})

    if not wizard_data or wizard_data.get('step') != 2:
        return redirect('campaign_wizard_start')

    context = {
        'wizard_data': wizard_data,
        'step': 2
    }

    return render(request, 'campaigns/wizard/step2_select_story.html', context)


@login_required
@require_http_methods(["POST"])
def campaign_wizard_select_story(request):
    """
    User selects a story idea

    POST data:
    - selected_story_id: ID of selected story
    """
    try:
        wizard_data = request.session.get('campaign_wizard', {})
        selected_story_id = request.POST.get('selected_story_id')

        # Call orchestrator
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/select-story",
                json={
                    'request_id': wizard_data['request_id'],
                    'user_id': str(request.user.id),
                    'selected_story_id': selected_story_id
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to select story'}, status=500)

        # Update session
        wizard_data['selected_story_id'] = selected_story_id
        wizard_data['step'] = 3
        request.session['campaign_wizard'] = wizard_data

        return JsonResponse({
            'status': 'success',
            'redirect_url': '/campaigns/wizard/core-approval/'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def campaign_wizard_regenerate_stories(request):
    """
    User requests story regeneration
    """
    try:
        wizard_data = request.session.get('campaign_wizard', {})

        # Call orchestrator
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/regenerate-stories",
                json={
                    'request_id': wizard_data['request_id'],
                    'user_id': str(request.user.id)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to regenerate stories'}, status=500)

        return JsonResponse({'status': 'regenerating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def campaign_wizard_core_approval(request):
    """
    Step 3: Review and approve campaign core (plot, storyline, objectives)
    """
    wizard_data = request.session.get('campaign_wizard', {})

    if not wizard_data or wizard_data.get('step') != 3:
        return redirect('campaign_wizard_start')

    context = {
        'wizard_data': wizard_data,
        'step': 3
    }

    return render(request, 'campaigns/wizard/step3_approve_core.html', context)


@login_required
@require_http_methods(["POST"])
def campaign_wizard_approve_core(request):
    """
    User approves campaign core and provides quest specifications

    POST data:
    - num_quests: Number of quests (default 5)
    - quest_difficulty: Easy, Medium, Hard, Expert
    - quest_playtime_minutes: Expected playtime per quest
    - generate_images: Boolean
    """
    try:
        wizard_data = request.session.get('campaign_wizard', {})

        num_quests = int(request.POST.get('num_quests', 5))
        quest_difficulty = request.POST.get('quest_difficulty', 'Medium')
        quest_playtime_minutes = int(request.POST.get('quest_playtime_minutes', 90))
        generate_images = request.POST.get('generate_images', 'true') == 'true'

        # Call orchestrator
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-core",
                json={
                    'request_id': wizard_data['request_id'],
                    'user_id': str(request.user.id),
                    'user_approved_core': True,
                    'num_quests': num_quests,
                    'quest_difficulty': quest_difficulty,
                    'quest_playtime_minutes': quest_playtime_minutes,
                    'generate_images': generate_images
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve campaign core'}, status=500)

        # Update session
        wizard_data['num_quests'] = num_quests
        wizard_data['quest_difficulty'] = quest_difficulty
        wizard_data['quest_playtime_minutes'] = quest_playtime_minutes
        wizard_data['generate_images'] = generate_images
        wizard_data['step'] = 4
        request.session['campaign_wizard'] = wizard_data

        return JsonResponse({
            'status': 'generating',
            'redirect_url': '/campaigns/wizard/progress/'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def campaign_wizard_progress(request):
    """
    Step 4: Show progress of campaign generation
    """
    wizard_data = request.session.get('campaign_wizard', {})

    if not wizard_data or wizard_data.get('step') != 4:
        return redirect('campaign_wizard_start')

    context = {
        'wizard_data': wizard_data,
        'step': 4
    }

    return render(request, 'campaigns/wizard/step4_progress.html', context)


@login_required
@require_http_methods(["GET"])
def campaign_wizard_status(request):
    """
    AJAX endpoint to get campaign generation status

    Returns JSON with progress, phase, and errors
    """
    try:
        wizard_data = request.session.get('campaign_wizard', {})
        request_id = wizard_data.get('request_id')

        if not request_id:
            return JsonResponse({'error': 'No active campaign wizard session'}, status=404)

        # Call orchestrator to get status
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{ORCHESTRATOR_URL}/campaign-wizard/status/{request_id}"
            )

            if response.status_code == 404:
                return JsonResponse({'error': 'Campaign request not found'}, status=404)

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to get campaign status'}, status=500)

            status_data = response.json()

        return JsonResponse(status_data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def campaign_wizard_complete(request):
    """
    Step 5: Campaign generation complete
    """
    wizard_data = request.session.get('campaign_wizard', {})

    if not wizard_data:
        return redirect('campaign_wizard_start')

    # Fetch completed campaign from MongoDB
    request_id = wizard_data.get('request_id')

    # TODO: Fetch campaign by request_id from MongoDB
    # For now, redirect to campaigns list

    # Clear wizard session
    del request.session['campaign_wizard']

    return redirect('campaigns')


# AJAX helper endpoints

@login_required
@require_http_methods(["GET"])
def get_worlds_for_universe(request, universe_id):
    """
    AJAX endpoint to get worlds for a universe
    """
    worlds = list(mongo_db.worlds.find({'universe_id': universe_id}))

    # Convert ObjectId to string for JSON serialization
    for world in worlds:
        world['_id'] = str(world['_id'])

    return JsonResponse({'worlds': worlds})


@login_required
@require_http_methods(["GET"])
def get_regions_for_world(request, world_id):
    """
    AJAX endpoint to get regions for a world
    """
    regions = list(mongo_db.regions.find({'world_id': world_id}))

    # Convert ObjectId to string for JSON serialization
    for region in regions:
        region['_id'] = str(region['_id'])

    return JsonResponse({'regions': regions})
