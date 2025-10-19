"""
Gameplay Views
Handles game session creation and management
"""
import requests
import uuid
import os
import json
import redis
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.http import JsonResponse
from pymongo import MongoClient
from bson import ObjectId

from characters.models import Character
from members.models import Player

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Redis connection
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


class GameLobbyView(View):
    """Browse and select campaigns to play"""

    def get(self, request):
        # Get all campaigns from MongoDB (most don't have generation_status)
        # Filter for campaigns with quest_ids to ensure they're playable
        campaigns = list(db.campaigns.find({'quest_ids': {'$exists': True, '$ne': []}}))

        # Add campaign_id field for templates
        for campaign in campaigns:
            campaign['campaign_id'] = campaign['_id']

            # Template compatibility - add title field
            if 'title' not in campaign and 'name' in campaign:
                campaign['title'] = campaign['name']

            # Get world data for display
            world_id = campaign.get('world_id')
            if world_id:
                world = db.world_definitions.find_one({'_id': world_id})
                if world:
                    campaign['world'] = world
                else:
                    campaign['world'] = {'name': 'Unknown World'}
            else:
                campaign['world'] = {'name': 'Unknown World'}

            # Add quest count for template
            quest_ids = campaign.get('quest_ids', [])

            # Create a simple class to make .count() work in template
            class QuestCount:
                def __init__(self, ids):
                    self.ids = ids
                def count(self):
                    return len(self.ids)

            campaign['quests'] = QuestCount(quest_ids)

        # Get player's characters
        player_id = request.session.get('player_id')
        characters = []

        if player_id:
            try:
                player = Player.objects.get(player_id=player_id)
                characters = Character.objects.filter(player_id=player.player_id, is_active=True)
            except Player.DoesNotExist:
                pass
        else:
            # TODO: Remove this for production - for testing, show all characters
            characters = Character.objects.filter(is_active=True)

        # Get active game sessions from Redis
        active_sessions = []
        try:
            # Get all session keys from Redis
            session_keys = redis_client.keys('session:state:*')

            for key in session_keys:
                session_data_raw = redis_client.get(key)
                if session_data_raw:
                    session_data = json.loads(session_data_raw)
                    session_id = session_data.get('session_id', '')

                    # Get campaign info
                    campaign_id = session_data.get('campaign_id')
                    campaign_info = db.campaigns.find_one({'_id': campaign_id}) if campaign_id else None

                    # Get character info
                    players = session_data.get('players', [])
                    character_names = []
                    for player_data in players:
                        char_id = player_data.get('character_id')
                        if char_id:
                            try:
                                character = Character.objects.get(character_id=char_id)
                                character_names.append(character.name)
                            except Character.DoesNotExist:
                                character_names.append('Unknown Character')

                    active_sessions.append({
                        'session_id': session_id,
                        'campaign_name': campaign_info.get('name', 'Unknown Campaign') if campaign_info else 'Unknown Campaign',
                        'campaign_id': campaign_id,
                        'started_at': session_data.get('started_at', ''),
                        'status': session_data.get('status', 'active'),
                        'character_names': character_names,
                        'current_scene': session_data.get('scene_name', 'Unknown Location'),
                        'player_count': len(players)
                    })

            # Sort by started_at (most recent first)
            active_sessions.sort(key=lambda x: x['started_at'], reverse=True)
        except Exception as e:
            print(f"Error fetching active sessions: {e}")

        context = {
            'campaigns': campaigns,
            'characters': characters,
            'player_id': player_id,
            'active_sessions': active_sessions
        }

        return render(request, 'game/lobby.html', context)


class StartGameSessionView(View):
    """Start a new game session"""

    def post(self, request, campaign_id):
        campaign = db.campaigns.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('game_lobby')

        character_id = request.POST.get('character_id')
        session_type = request.POST.get('session_type', 'solo')  # solo or party

        if not character_id:
            messages.error(request, 'Please select a character')
            return redirect('game_lobby')

        try:
            character = Character.objects.get(character_id=character_id)
            player = Player.objects.get(player_id=character.player_id)

            # Call game-engine API to create session
            game_engine_url = 'http://game-engine:9500/api/v1'

            if session_type == 'solo':
                response = requests.post(
                    f'{game_engine_url}/session/start-solo',
                    json={
                        'campaign_id': str(campaign_id),
                        'player_id': str(player.player_id),
                        'character_id': str(character.character_id)
                    },
                    timeout=30
                )
            else:
                response = requests.post(
                    f'{game_engine_url}/session/create-party',
                    json={
                        'campaign_id': str(campaign_id),
                        'host_player_id': str(player.player_id),
                        'host_character_id': str(character.character_id),
                        'max_players': int(request.POST.get('max_players', 4)),
                        'auto_start': request.POST.get('auto_start') == 'true'
                    },
                    timeout=30
                )

            response.raise_for_status()
            result = response.json()

            session_id = result.get('session_id')

            # Store session info in Django session
            request.session['current_game_session'] = session_id
            request.session['campaign_id'] = str(campaign_id)

            messages.success(request, 'Game session created successfully!')

            if session_type == 'party':
                # Redirect to party lobby
                return redirect('party_lobby', session_id=session_id)
            else:
                # Redirect to game session
                return redirect('game_session', session_id=session_id)

        except Character.DoesNotExist:
            messages.error(request, 'Character not found')
            return redirect('game_lobby')
        except requests.RequestException as e:
            messages.error(request, f'Failed to start game session: {str(e)}')
            return redirect('game_lobby')


class GameSessionView(View):
    """Main game session interface"""

    def get(self, request, session_id):
        # Get session data from game-engine
        try:
            game_engine_url = 'http://game-engine:9500/api/v1'

            response = requests.get(
                f'{game_engine_url}/session/{session_id}/state',
                timeout=10
            )

            response.raise_for_status()
            session_data = response.json()

            # Get campaign from MongoDB
            campaign_id = session_data.get('campaign_id')
            campaign = db.campaigns.find_one({'_id': campaign_id})
            if not campaign:
                messages.error(request, 'Campaign not found')
                return redirect('game_lobby')

            # Template compatibility - add campaign_id field and title
            campaign['campaign_id'] = campaign['_id']
            if 'title' not in campaign and 'name' in campaign:
                campaign['title'] = campaign['name']

            # Prepare campaign backstory/storyline for chat display
            campaign_intro_json = json.dumps({
                'backstory': campaign.get('backstory', ''),
                'storyline': campaign.get('storyline', ''),
                'description': campaign.get('description', '')
            })

            # Get the campaign's first quest
            first_quest = None
            first_quest_json = None
            quest_ids = campaign.get('quest_ids', [])
            if quest_ids:
                first_quest_id = quest_ids[0]
                first_quest = db.quests.find_one({'_id': first_quest_id})

                # Convert to JSON-safe format
                if first_quest:
                    first_quest_json = json.dumps({
                        'title': first_quest.get('name') or first_quest.get('title', 'Quest'),
                        'description': first_quest.get('description', ''),
                        'objectives': first_quest.get('objectives', [])
                    })

            # Get player character
            players = session_data.get('players', [])
            if not players:
                messages.error(request, 'No players in session')
                return redirect('game_lobby')

            player_data = players[0]
            character = get_object_or_404(
                Character,
                character_id=player_data.get('character_id')
            )
            player = get_object_or_404(
                Player,
                player_id=character.player_id
            )

            context = {
                'session_id': session_id,
                'campaign': campaign,
                'character': character,
                'player': player,
                'session_data': session_data,
                'scene_description': session_data.get('scene_description', ''),
                'available_actions': session_data.get('available_actions', []),
                'quest_id': session_data.get('current_quest_id'),
                'first_quest_json': first_quest_json,  # Campaign's first quest as JSON string
                'campaign_intro_json': campaign_intro_json  # Campaign backstory/storyline
            }

            return render(request, 'game/session.html', context)

        except requests.RequestException as e:
            messages.error(request, f'Failed to load game session: {str(e)}')
            return redirect('game_lobby')


class PartyLobbyView(View):
    """Party lobby for multiplayer sessions"""

    def get(self, request, session_id):
        try:
            game_engine_url = 'http://game-engine:9500/api/v1'

            response = requests.get(
                f'{game_engine_url}/session/{session_id}/state',
                timeout=10
            )

            response.raise_for_status()
            session_data = response.json()

            campaign_id = session_data.get('campaign_id')
            campaign = db.campaigns.find_one({'_id': campaign_id})
            if not campaign:
                messages.error(request, 'Campaign not found')
                return redirect('game_lobby')

            context = {
                'session_id': session_id,
                'campaign': campaign,
                'session_data': session_data,
                'players': session_data.get('players', []),
                'party_settings': session_data.get('party_settings', {})
            }

            return render(request, 'game/party_lobby.html', context)

        except requests.RequestException as e:
            messages.error(request, f'Failed to load party lobby: {str(e)}')
            return redirect('game_lobby')


class JoinSessionView(View):
    """Join an existing session with invite token"""

    def get(self, request):
        invite_token = request.GET.get('token')

        if not invite_token:
            messages.error(request, 'Invalid invite token')
            return redirect('game_lobby')

        # Extract session_id from token
        # Format: invite_{session_id}
        if invite_token.startswith('invite_'):
            session_id = invite_token[7:]  # Remove 'invite_' prefix
        else:
            messages.error(request, 'Invalid invite token format')
            return redirect('game_lobby')

        context = {
            'session_id': session_id,
            'invite_token': invite_token
        }

        return render(request, 'game/join_session.html', context)

    def post(self, request):
        session_id = request.POST.get('session_id')
        invite_token = request.POST.get('invite_token')
        character_id = request.POST.get('character_id')

        if not all([session_id, invite_token, character_id]):
            messages.error(request, 'Missing required information')
            return redirect('game_lobby')

        try:
            character = Character.objects.get(character_id=character_id)
            player = Player.objects.get(player_id=character.player_id)

            # Call game-engine API to join session
            game_engine_url = 'http://game-engine:9500/api/v1'

            response = requests.post(
                f'{game_engine_url}/session/{session_id}/join',
                params={
                    'player_id': str(player.player_id),
                    'character_id': str(character.character_id),
                    'invite_token': invite_token
                },
                timeout=30
            )

            response.raise_for_status()

            messages.success(request, 'Successfully joined the party!')
            return redirect('party_lobby', session_id=session_id)

        except Character.DoesNotExist:
            messages.error(request, 'Character not found')
            return redirect('game_lobby')
        except requests.RequestException as e:
            messages.error(request, f'Failed to join session: {str(e)}')
            return redirect('game_lobby')


class SessionControlView(View):
    """Control session (pause, resume, save)"""

    def post(self, request, session_id):
        action = request.POST.get('action')

        try:
            game_engine_url = 'http://game-engine:9500/api/v1'

            if action == 'pause':
                response = requests.post(
                    f'{game_engine_url}/session/{session_id}/pause',
                    timeout=10
                )
            elif action == 'resume':
                response = requests.post(
                    f'{game_engine_url}/session/{session_id}/resume',
                    timeout=10
                )
            elif action == 'save':
                # TODO: Implement manual save
                messages.info(request, 'Auto-save is active. Manual save coming soon!')
                return redirect('game_session', session_id=session_id)
            else:
                messages.error(request, 'Invalid action')
                return redirect('game_session', session_id=session_id)

            response.raise_for_status()

            messages.success(request, f'Session {action}d successfully')
            return redirect('game_session', session_id=session_id)

        except requests.RequestException as e:
            messages.error(request, f'Failed to {action} session: {str(e)}')
            return redirect('game_session', session_id=session_id)


class CampaignImagesAPIView(View):
    """API endpoint to fetch all campaign-related images"""

    def get(self, request, campaign_id):
        try:
            campaign = db.campaigns.find_one({'_id': campaign_id})
            if not campaign:
                return JsonResponse({'error': 'Campaign not found'}, status=404)

            images = {
                'world': [],
                'campaign': [],
                'region': [],
                'place': [],
                'scene': [],
                'species': []
            }

            # 1. World images (from world definition)
            world_id = campaign.get('world_id')
            if world_id:
                world = db.world_definitions.find_one({'_id': world_id})
                if world:
                    primary_world_url = world.get('primary_image_url')
                    # Add primary world image
                    if primary_world_url:
                        images['world'].append({
                            'url': primary_world_url,
                            'title': world.get('name', 'World'),
                            'is_primary': True
                        })
                    # Add additional world images (skip if same as primary or has "Image 1")
                    for idx, img in enumerate(world.get('world_images', [])):
                        if isinstance(img, dict) and img.get('url'):
                            img_title = img.get('title', '')
                            # Skip if this URL is the same as the primary image or title contains "Image 1"
                            if img.get('url') == primary_world_url or 'Image 1' in img_title:
                                continue
                            images['world'].append({
                                'url': img['url'],
                                'title': img_title or f"World Image {idx + 1}",
                                'is_primary': False
                            })

            # 2. Campaign images
            primary_campaign_url = campaign.get('primary_image_url')
            if primary_campaign_url:
                images['campaign'].append({
                    'url': primary_campaign_url,
                    'title': campaign.get('title') or campaign.get('name', 'Campaign'),
                    'is_primary': True
                })
            # Add additional campaign images (skip if same as primary or has "Image 1")
            for idx, img in enumerate(campaign.get('campaign_images', [])):
                if isinstance(img, dict) and img.get('url'):
                    img_title = img.get('title', '')
                    # Skip if this URL is the same as the primary image or title contains "Image 1"
                    if img.get('url') == primary_campaign_url or 'Image 1' in img_title:
                        continue
                    images['campaign'].append({
                        'url': img['url'],
                        'title': img_title or f"Campaign Image {idx + 1}",
                        'is_primary': False
                    })

            # 3. Region images (from world's regions)
            if world_id:
                world = db.world_definitions.find_one({'_id': world_id})
                if world:
                    region_ids = world.get('regions', [])
                    for region_id in region_ids:
                        region = db.region_definitions.find_one({'_id': region_id})
                        if region:
                            primary_region_url = region.get('primary_image_url')
                            if primary_region_url:
                                images['region'].append({
                                    'url': primary_region_url,
                                    'title': region.get('region_name', 'Region'),
                                    'is_primary': True
                                })
                            # Check for region_images array (skip if same as primary or has "Image 1")
                            region_images = region.get('region_images', [])
                            if region_images:
                                for idx, img in enumerate(region_images):
                                    if isinstance(img, dict) and img.get('url'):
                                        img_title = img.get('title', '')
                                        # Skip if this URL is the same as the primary image or title contains "Image 1"
                                        if img.get('url') == primary_region_url or 'Image 1' in img_title:
                                            continue
                                        images['region'].append({
                                            'url': img['url'],
                                            'title': img_title or f"{region.get('region_name', 'Region')} - Image {idx + 1}",
                                            'is_primary': False
                                        })

            # 4. Place images (from quest places)
            quest_ids = campaign.get('quest_ids', [])
            for quest_id in quest_ids:
                quest = db.quests.find_one({'_id': quest_id})
                if quest:
                    place_ids = quest.get('place_ids', [])
                    for place_id in place_ids:
                        place = db.places.find_one({'_id': place_id})
                        if place:
                            primary_place_url = place.get('primary_image_url')
                            if primary_place_url:
                                images['place'].append({
                                    'url': primary_place_url,
                                    'title': place.get('name', 'Place'),
                                    'is_primary': True
                                })
                            # Check for place_images array (skip if same as primary or has "Image 1")
                            place_images = place.get('place_images', [])
                            if place_images:
                                for idx, img in enumerate(place_images):
                                    if isinstance(img, dict) and img.get('url'):
                                        img_title = img.get('title', '')
                                        # Skip if this URL is the same as the primary image or title contains "Image 1"
                                        if img.get('url') == primary_place_url or 'Image 1' in img_title:
                                            continue
                                        images['place'].append({
                                            'url': img['url'],
                                            'title': img_title or f"{place.get('name', 'Place')} - Image {idx + 1}",
                                            'is_primary': False
                                        })

            # 5. Scene images (from place scenes)
            for quest_id in quest_ids:
                quest = db.quests.find_one({'_id': quest_id})
                if quest:
                    place_ids = quest.get('place_ids', [])
                    for place_id in place_ids:
                        place = db.places.find_one({'_id': place_id})
                        if place:
                            scene_ids = place.get('scene_ids', [])
                            for scene_id in scene_ids:
                                scene = db.scenes.find_one({'_id': scene_id})
                                if scene:
                                    primary_scene_url = scene.get('primary_image_url')
                                    if primary_scene_url:
                                        images['scene'].append({
                                            'url': primary_scene_url,
                                            'title': scene.get('name', 'Scene'),
                                            'is_primary': True
                                        })
                                    # Check for scene_images array (skip if same as primary or has "Image 1")
                                    scene_images = scene.get('scene_images', [])
                                    if scene_images:
                                        for idx, img in enumerate(scene_images):
                                            if isinstance(img, dict) and img.get('url'):
                                                img_title = img.get('title', '')
                                                # Skip if this URL is the same as the primary image or title contains "Image 1"
                                                if img.get('url') == primary_scene_url or 'Image 1' in img_title:
                                                    continue
                                                images['scene'].append({
                                                    'url': img['url'],
                                                    'title': img_title or f"{scene.get('name', 'Scene')} - Image {idx + 1}",
                                                    'is_primary': False
                                                })

            # 6. Species images (from NPCs)
            npc_ids = campaign.get('npc_ids', [])
            species_seen = set()
            for npc_id in npc_ids:
                npc = db.npcs.find_one({'_id': npc_id})
                if npc:
                    species_id = npc.get('species_id')
                    if species_id and species_id not in species_seen:
                        species_seen.add(species_id)
                        species = db.species.find_one({'_id': species_id})
                        if species:
                            primary_species_url = species.get('primary_image_url')
                            if primary_species_url:
                                images['species'].append({
                                    'url': primary_species_url,
                                    'title': species.get('name', 'Species'),
                                    'is_primary': True
                                })
                            # Add additional species images (skip if same as primary or has "Image 1")
                            for idx, img in enumerate(species.get('species_images', [])):
                                if isinstance(img, dict) and img.get('url'):
                                    img_title = img.get('title', '')
                                    # Skip if this URL is the same as the primary image or title contains "Image 1"
                                    if img.get('url') == primary_species_url or 'Image 1' in img_title:
                                        continue
                                    images['species'].append({
                                        'url': img['url'],
                                        'title': img_title or f"{species.get('name', 'Species')} - Image {idx + 1}",
                                        'is_primary': False
                                    })

            # Sort each category to put primary images first
            for category in images:
                images[category].sort(key=lambda x: (not x['is_primary'], x['title']))

            return JsonResponse({'images': images})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DeleteSessionView(View):
    """Delete a game session from all storage"""

    def post(self, request):
        try:
            session_id = request.POST.get('session_id')
            if not session_id:
                return JsonResponse({'error': 'Session ID is required'}, status=400)

            # Delete from Redis (session state and cache)
            try:
                # Delete session state
                redis_client.delete(f'session:state:{session_id}')
                # Delete session lock
                redis_client.delete(f'session:lock:{session_id}')
                # Delete any cached campaign/quest data for this session
                redis_client.delete(f'campaign:{session_id}')
                redis_client.delete(f'quest:{session_id}')
            except Exception as e:
                print(f"Error deleting from Redis: {e}")

            # Delete from MongoDB (if session data is persisted there)
            try:
                db.game_sessions.delete_many({'session_id': session_id})
            except Exception as e:
                print(f"Error deleting from MongoDB: {e}")

            # Note: PostgreSQL Character data is NOT deleted since it's independent of sessions

            return JsonResponse({
                'success': True,
                'message': 'Session deleted successfully'
            })

        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
