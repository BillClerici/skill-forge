"""
Gameplay Views
Handles game session creation and management
"""
import requests
import uuid
import os
import json
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

        context = {
            'campaigns': campaigns,
            'characters': characters,
            'player_id': player_id
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

            # Template compatibility - ensure title field exists
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
