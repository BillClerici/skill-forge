"""
Views for Games app
"""
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
import requests
import os
import logging
from uuid import uuid4
from pymongo import MongoClient
from characters.models import Character
from members.models import Player

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:admin@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']


class GamesLobbyView(View):
    """Game lobby - start new games or continue existing ones"""

    def get(self, request):
        """Display the games lobby"""
        try:
            # Get player ID from session or create a temp one
            if request.user.is_authenticated:
                player_id = request.user.id
            else:
                # For non-authenticated users, use session-based player ID
                if 'temp_player_id' not in request.session:
                    request.session['temp_player_id'] = str(uuid4())
                player_id = request.session['temp_player_id']

            # NOTE: Active sessions are NOT shown in lobby currently
            # Sessions are managed entirely by the game engine (Redis + MongoDB)
            # If we need to show active sessions, we'll add an endpoint to game engine
            active_sessions = []

            # Fetch real campaigns from MongoDB
            available_campaigns = self._get_available_campaigns()

            # Fetch player's characters
            characters = []
            try:
                # For now, show all active characters (in production, filter by player_id)
                characters = list(Character.objects.filter(is_active=True).order_by('name')[:50])
                print(f"=== CHARACTERS LOADED: {len(characters)} ===")
                for char in characters:
                    print(f"  - {char.name} (ID: {char.character_id})")
                logger.info(f"Found {len(characters)} active characters")
            except Exception as e:
                print(f"=== ERROR LOADING CHARACTERS: {e} ===")
                logger.error(f"Error fetching characters: {e}")

            context = {
                'active_sessions': active_sessions,
                'available_campaigns': available_campaigns,
                'characters': characters,
                'player_id': player_id
            }

            return render(request, 'games/lobby.html', context)

        except Exception as e:
            logger.error(f"Error loading games lobby: {e}")
            return HttpResponse(f"Error loading games lobby: {e}", status=500)

    def _get_available_campaigns(self):
        """Get available campaigns from MongoDB"""
        try:
            # Get all campaigns from MongoDB that have quests (are playable)
            campaigns = list(db.campaigns.find({'quest_ids': {'$exists': True, '$ne': []}}))

            # Process campaigns for display
            processed_campaigns = []
            for campaign in campaigns:
                # Get campaign ID
                campaign_id = str(campaign['_id'])

                # Get world data for display
                world_name = 'Unknown World'
                world_id = campaign.get('world_id')
                if world_id:
                    world = db.world_definitions.find_one({'_id': world_id})
                    if world:
                        world_name = world.get('name', 'Unknown World')

                # Get quest count
                quest_ids = campaign.get('quest_ids', [])
                quest_count = len(quest_ids)

                # Determine difficulty based on quest count or other factors
                if quest_count <= 3:
                    difficulty = 'Easy'
                elif quest_count <= 6:
                    difficulty = 'Medium'
                else:
                    difficulty = 'Hard'

                # Estimate duration based on quest count
                estimated_hours = quest_count * 0.5
                if estimated_hours < 2:
                    duration = f"{int(estimated_hours * 60)} minutes"
                else:
                    duration = f"{int(estimated_hours)}-{int(estimated_hours) + 1} hours"

                # Get primary image
                images = campaign.get('images', [])
                primary_image = None
                for img in images:
                    if img.get('is_primary'):
                        primary_image = img.get('url')
                        break
                if not primary_image and images:
                    primary_image = images[0].get('url')

                processed_campaigns.append({
                    'id': campaign_id,
                    'name': campaign.get('name', campaign.get('title', 'Untitled Campaign')),
                    'description': campaign.get('description', 'An exciting adventure awaits...'),
                    'difficulty': difficulty,
                    'estimated_duration': duration,
                    'image_url': primary_image,
                    'world_name': world_name,
                    'quest_count': quest_count
                })

            return processed_campaigns

        except Exception as e:
            logger.error(f"Error fetching campaigns from MongoDB: {e}")
            # Return empty list on error
            return []


class GamePlayView(View):
    """Game play view - the main game UI"""

    def get(self, request, game_id):
        """Display the game play UI"""
        try:
            # Get player ID from session
            if request.user.is_authenticated:
                player_id = request.user.id
            else:
                if 'temp_player_id' not in request.session:
                    request.session['temp_player_id'] = str(uuid4())
                player_id = request.session['temp_player_id']

            # Get game engine URL
            game_engine_url = os.getenv('GAME_ENGINE_URL', 'http://game-engine:9500')

            # Fetch session data from game engine (with retries for initialization)
            session_data = None
            max_retries = 5
            retry_delay = 0.5  # seconds

            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        f'{game_engine_url}/api/v1/session/{game_id}/state',
                        timeout=5
                    )
                    if response.status_code == 200:
                        session_data = response.json()
                        break
                    elif attempt < max_retries - 1:
                        # Wait before retrying (session might still be initializing)
                        import time
                        time.sleep(retry_delay)
                except Exception as e:
                    logger.error(f"Error fetching session data (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)

            if not session_data:
                return HttpResponse("Session not found", status=404)

            # Get WebSocket gateway URL
            ws_gateway_url = os.getenv('GAME_UI_GATEWAY_WS_URL', 'ws://localhost:9600')

            context = {
                'session_id': game_id,
                'player_id': player_id,
                'session_data': session_data,
                'ws_gateway_url': ws_gateway_url
            }

            return render(request, 'games/game.html', context)

        except Exception as e:
            logger.error(f"Error loading game: {e}")
            return HttpResponse(f"Error loading game: {e}", status=500)


class CreateGameView(View):
    """Create a new game session"""

    def post(self, request):
        """Create a new game session"""
        try:
            import json as json_lib
            from uuid import uuid4

            # Get player ID from session
            if request.user.is_authenticated:
                player_id = request.user.id
            else:
                if 'temp_player_id' not in request.session:
                    request.session['temp_player_id'] = str(uuid4())
                player_id = request.session['temp_player_id']

            campaign_id = request.POST.get('campaign_id')
            character_id = request.POST.get('character_id')
            character_name = request.POST.get('character_name', '')

            # If character_id is provided and not 'new', get character name from DB
            if character_id and character_id != 'new':
                try:
                    character = Character.objects.get(character_id=character_id)
                    character_name = character.name
                    character_id = str(character.character_id)
                except Character.DoesNotExist:
                    character_id = str(player_id)
                    if not character_name:
                        character_name = f'Player_{player_id}'
            else:
                # New character or no selection
                character_id = str(player_id)
                if not character_name:
                    character_name = f'Player_{player_id}'

            # Get game engine URL
            game_engine_url = os.getenv('GAME_ENGINE_URL', 'http://game-engine:9500')

            # Create session via game engine - this will trigger the GM introduction workflow
            session_request = {
                'campaign_id': campaign_id,
                'player_id': str(player_id),
                'character_id': character_id
            }

            try:
                response = requests.post(
                    f'{game_engine_url}/api/v1/session/start-solo',
                    json=session_request,
                    timeout=10
                )

                if response.status_code == 200:
                    result = response.json()
                    session_id = result.get('session_id')

                    # Redirect to game play
                    return redirect('games:play', game_id=session_id)
                else:
                    logger.error(f"Error creating session: {response.text}")
                    return HttpResponse("Error creating session", status=500)

            except Exception as e:
                logger.error(f"Error creating session: {e}")
                return HttpResponse(f"Error creating session: {e}", status=500)

        except Exception as e:
            logger.error(f"Error in create game: {e}")
            return HttpResponse(f"Error: {e}", status=500)


class GameSessionsAPIView(View):
    """API endpoint for game sessions"""

    def get(self, request):
        """Get sessions for current player"""
        # NOTE: Sessions are now managed entirely by game engine (Redis + MongoDB)
        # If needed, add session listing endpoint to game engine API
        # For now, return empty list
        return JsonResponse({'sessions': []})
