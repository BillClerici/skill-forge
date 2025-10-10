"""
Campaign Wizard V2 Views
Complete endpoint implementation for 22-step workflow with all requirements
"""
import os
import json
import uuid
import httpx
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
mongo_db = mongo_client['skillforge']

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')


def campaign_wizard_v2(request):
    """
    Main wizard view - Step 1: Universe selection
    Implements requirements 1-22 from Campaign AI Workflow
    """
    # Fetch universes from MongoDB
    universes = list(mongo_db.universes.find({}))

    context = {
        'universes': universes
    }

    return render(request, 'campaigns/campaign_designer_wizard_v2.html', context)


@require_http_methods(["GET"])
def get_worlds_for_universe_api(request, universe_id):
    """
    AJAX: Get worlds for a universe
    Requirement 4: Display list of Worlds in selected Universe and their Genre
    """
    # Check both universe_id (singular) and universe_ids (plural array) for compatibility
    worlds = list(mongo_db.world_definitions.find({
        '$or': [
            {'universe_id': universe_id},
            {'universe_ids': universe_id}
        ]
    }))

    # Add primary_image_url to each world
    for world in worlds:
        world['_id'] = str(world['_id'])
        world['primary_image_url'] = None
        if world.get('world_images') and world.get('primary_image_index') is not None:
            images = world.get('world_images', [])
            primary_idx = world.get('primary_image_index')
            if 0 <= primary_idx < len(images):
                world['primary_image_url'] = images[primary_idx].get('url')

        # Ensure genre is present
        if 'genre' not in world:
            world['genre'] = 'Unknown'

    return JsonResponse({'worlds': worlds})


@require_http_methods(["GET"])
def get_regions_for_world_api(request, world_id):
    """
    AJAX: Get regions for a world
    Requirement 5: User selects World, then selects the Region for the Campaign
    """
    regions = list(mongo_db.region_definitions.find({'world_id': world_id}))

    for region in regions:
        region['_id'] = str(region['_id'])

        # Get location count for region
        location_ids = region.get('locations', [])
        region['location_count'] = len(location_ids)

    return JsonResponse({'regions': regions})


@csrf_exempt
@require_http_methods(["POST"])
def generate_stories_api(request):
    """
    AJAX: Generate 3 story ideas
    Requirement 7-8: Generate Campaign Ideas button
    The Campaign AI Workflow uses MNCP & Agents to gather World Content
    plus Region content plus Campaign story idea to generate 3 Story ideas
    """
    try:
        data = json.loads(request.body)
        request_id = str(uuid.uuid4())

        # Call orchestrator to start workflow
        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/start",
                json={
                    'request_id': request_id,
                    'user_id': user_id,
                    'character_id': data.get('character_id'),
                    'universe_id': data['universe_id'],
                    'universe_name': data.get('universe_name'),
                    'world_id': data['world_id'],
                    'world_name': data.get('world_name'),
                    'region_id': data.get('region_id'),
                    'region_name': data.get('region_name'),
                    'genre': data.get('genre'),
                    'user_story_idea': data.get('user_story_idea', '')  # Requirement 6: Optional
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to start workflow'}, status=500)

        return JsonResponse({'request_id': request_id, 'status': 'generating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerate_stories_api(request):
    """
    AJAX: Regenerate story ideas
    Requirement 9: User modifies their story idea and regenerates 3 new ideas,
    or just asks for 3 new ideas based on current world and genre context
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/regenerate-stories",
                json={
                    'request_id': request_id,
                    'user_id': user_id
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to regenerate stories'}, status=500)

        return JsonResponse({'status': 'regenerating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_core_api(request):
    """
    AJAX: Generate campaign core
    Requirement 10: Once user selects their story idea, the Campaign AI Workflow
    generates all the core components of the Campaign, including the Plot,
    detailed storyline, and Primary Objectives
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')
        selected_story_id = data.get('selected_story_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/select-story",
                json={
                    'request_id': request_id,
                    'user_id': user_id,
                    'selected_story_id': selected_story_id
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to generate core'}, status=500)

        return JsonResponse({'status': 'generating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_core_api(request):
    """
    AJAX: Approve campaign core and start quest generation
    Requirement 11: Display the Campaign level settings to the user and allow
    them to modify if they wish, otherwise continue to setting up Quests
    Requirement 12: Allow user to specify the number of Quests, difficulty level,
    and estimated play time
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-core",
                json={
                    'request_id': request_id,
                    'user_id': user_id,
                    'user_approved_core': True,
                    'num_quests': data.get('num_quests', 5),
                    'quest_difficulty': data.get('quest_difficulty', 'Medium'),
                    'quest_playtime_minutes': data.get('quest_playtime_minutes', 90),
                    'generate_images': data.get('generate_images', True)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve core'}, status=500)

        return JsonResponse({'status': 'generating_quests'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_quests_api(request):
    """
    AJAX: Approve quests and start place generation
    Requirement 13-14: Generate Quests and associate with Level 1 Locations,
    then generate Places (Level 2 Locations)
    Requirement 19: Make each level a generation step so user can review before continuing
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-quests",
                json={
                    'request_id': request_id,
                    'user_id': user_id,
                    'user_approved_quests': True
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve quests'}, status=500)

        return JsonResponse({'status': 'generating_places'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_places_api(request):
    """
    AJAX: Approve places and start scene generation
    Requirement 15-16: Generate Scenes (Level 3 Locations) and create story
    supporting Challenges, Events, Discovery Elements, and NPCs
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-places",
                json={
                    'request_id': request_id,
                    'user_id': user_id,
                    'user_approved_places': True
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve places'}, status=500)

        return JsonResponse({'status': 'generating_scenes'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_workflow_status_api(request, request_id):
    """
    AJAX: Get campaign workflow status
    Used for polling during async workflow execution
    Returns progress_percentage, status_message, and generated content
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{ORCHESTRATOR_URL}/campaign-wizard/status/{request_id}"
            )

            if response.status_code == 404:
                return JsonResponse({'error': 'Request not found'}, status=404)

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to get status'}, status=500)

            return JsonResponse(response.json())

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def finalize_campaign_api(request):
    """
    AJAX: Finalize campaign
    Requirement 20-22: Generate Backstory and supporting content,
    incorporate Bloom's Taxonomy capabilities, allow user to decide on image generation
    """
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        # Use default UUID if user is not authenticated
        user_id = str(request.user.id) if request.user.is_authenticated else "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/finalize",
                json={
                    'request_id': request_id,
                    'user_id': user_id
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to finalize'}, status=500)

            result = response.json()

            # Get the final campaign ID
            campaign_id = result.get('campaign_id')

            return JsonResponse({
                'status': 'completed',
                'campaign_id': campaign_id,
                'message': 'Campaign created successfully!'
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
