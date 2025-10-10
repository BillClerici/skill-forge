"""
Views for Campaign management
Campaigns link Players, Worlds, and AI-generated narratives
"""
import uuid
import httpx
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from pymongo import MongoClient
from neo4j import GraphDatabase
import os
from members.models import Player


# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URL = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Agent endpoints
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:3000')


class CampaignListView(View):
    """List all campaigns"""

    def get(self, request):
        campaigns = list(db.campaign_state.find())
        # Add campaign_id field for template (Django doesn't allow _id)
        for campaign in campaigns:
            campaign['campaign_id'] = campaign['_id']

            # Fetch world data for images
            world_ids = campaign.get('world_ids', [])
            if world_ids:
                worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))

                # Add primary_image_url for each world
                for world in worlds:
                    world['primary_image_url'] = None
                    if world.get('world_images') and world.get('primary_image_index') is not None:
                        images = world.get('world_images', [])
                        primary_idx = world.get('primary_image_index')
                        if 0 <= primary_idx < len(images):
                            world['primary_image_url'] = images[primary_idx].get('url')

                campaign['worlds'] = worlds
            else:
                campaign['worlds'] = []

        return render(request, 'campaigns/campaign_list.html', {'campaigns': campaigns})


class CampaignCreateView(View):
    """Create a new campaign"""

    def get(self, request):
        worlds = list(db.world_definitions.find())

        # Get players from PostgreSQL instead of MongoDB
        players = Player.objects.filter(is_active=True).values(
            'player_id', 'display_name', 'email', 'role'
        )

        # Add id field for template (Django doesn't allow _id)
        for world in worlds:
            world['id'] = world['_id']

        # Convert players to list and add id field
        players_list = []
        for player in players:
            players_list.append({
                'id': str(player['player_id']),
                'player_name': player['display_name'],
                'email': player.get('email', ''),
                'role': player['role']
            })

        # Initialize empty form data for multi-selects
        form_data = {
            'world_ids': {'value': []},
            'player_ids': {'value': []}
        }

        return render(request, 'campaigns/campaign_form.html', {
            'worlds': worlds,
            'players': players_list,
            'form': form_data
        })

    def post(self, request):
        campaign_id = str(uuid.uuid4())

        # Get multi-select values
        world_ids = request.POST.getlist('world_ids')
        player_ids = request.POST.getlist('player_ids')

        if not world_ids or not player_ids:
            messages.error(request, 'Please select at least one world and one player')
            return redirect('campaign_create')

        # Get world data from MongoDB
        worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))

        # Get player data from PostgreSQL
        players = Player.objects.filter(
            player_id__in=player_ids,
            is_active=True
        ).values('player_id', 'display_name', 'email')

        if len(worlds) != len(world_ids) or len(players) != len(player_ids):
            messages.error(request, 'Invalid world or player selected')
            return redirect('campaign_create')

        # Build world and player names
        world_names = [w.get('world_name') for w in worlds]
        player_names = [p['display_name'] for p in players]

        # Convert player_ids to strings for consistency
        player_ids = [str(p['player_id']) for p in players]

        campaign_data = {
            '_id': campaign_id,
            'campaign_name': request.POST.get('campaign_name'),
            'world_ids': world_ids,
            'world_names': world_names,
            'player_ids': player_ids,
            'player_names': player_names,
            'status': 'active',
            'current_scene': None,
            'scene_history': [],
            'player_state': {
                'location': 'starting_area',
                'inventory': [],
                'quests': []
            }
        }

        # Store in MongoDB
        db.campaign_state.insert_one(campaign_data)

        # Create nodes and relationships in Neo4j
        with neo4j_driver.session() as session:
            # Create campaign node
            session.run("""
                CREATE (c:Campaign {
                    id: $campaign_id,
                    name: $campaign_name,
                    status: 'active'
                })
            """, campaign_id=campaign_id,
               campaign_name=campaign_data['campaign_name'])

            # Link to all selected worlds
            for world_id in world_ids:
                session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    MATCH (w:World {id: $world_id})
                    MERGE (c)-[:IN_WORLD]->(w)
                """, campaign_id=campaign_id, world_id=world_id)

            # Link to all selected players
            for player_id in player_ids:
                session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    MATCH (p:Player {id: $player_id})
                    MERGE (c)-[:HAS_PLAYER]->(p)
                """, campaign_id=campaign_id, player_id=player_id)

        messages.success(request, f'Campaign "{campaign_data["campaign_name"]}" created successfully with {len(world_ids)} world(s) and {len(player_ids)} player(s)!')
        return redirect('campaign_detail', campaign_id=campaign_id)


class CampaignDetailView(View):
    """View campaign details and interact with Game Master"""

    def get(self, request, campaign_id):
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        # Add campaign_id field for template (Django doesn't allow _id)
        campaign['campaign_id'] = campaign['_id']

        # Get all worlds for this campaign
        world_ids = campaign.get('world_ids', [])
        worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}})) if world_ids else []

        # Add id field and primary_image_url for template (Django doesn't allow _id)
        for world in worlds:
            world['id'] = world['_id']

            # Get primary image URL
            world['primary_image_url'] = None
            if world.get('world_images') and world.get('primary_image_index') is not None:
                images = world.get('world_images', [])
                primary_idx = world.get('primary_image_index')
                if 0 <= primary_idx < len(images):
                    world['primary_image_url'] = images[primary_idx].get('url')

        # Get all players for this campaign from PostgreSQL
        player_ids = campaign.get('player_ids', [])
        players = Player.objects.filter(
            player_id__in=player_ids,
            is_active=True
        ).values('player_id', 'display_name', 'email', 'role') if player_ids else []

        return render(request, 'campaigns/campaign_detail.html', {
            'campaign': campaign,
            'worlds': worlds,
            'players': list(players)
        })

    def post(self, request, campaign_id):
        """Handle player action through Game Master agent"""
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        player_action = request.POST.get('player_action')

        # Call orchestrator to process action through Game Master
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/process",
                    json={
                        'campaign_id': campaign_id,
                        'action': player_action,
                        'agent': 'game_master'
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()

                    # Update campaign state with new scene
                    db.campaign_state.update_one(
                        {'_id': campaign_id},
                        {
                            '$set': {'current_scene': result.get('scene')},
                            '$push': {'scene_history': result.get('scene')}
                        }
                    )

                    messages.success(request, 'Action processed!')
                else:
                    messages.error(request, f'Agent error: {response.text}')

        except Exception as e:
            messages.error(request, f'Failed to process action: {str(e)}')

        return redirect('campaign_detail', campaign_id=campaign_id)


class CampaignStartView(View):
    """Start a campaign and generate opening scene"""

    def post(self, request, campaign_id):
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        # Get required data for start-campaign endpoint
        world_ids = campaign.get('world_ids', [])
        player_ids = campaign.get('player_ids', [])

        if not world_ids or not player_ids:
            messages.error(request, 'Campaign is missing world or player information')
            return redirect('campaign_detail', campaign_id=campaign_id)

        # Get first world and player (for now)
        world_id = world_ids[0]
        player_id = player_ids[0]

        # Get character for this player (if exists)
        from characters.models import Character
        character = Character.objects.filter(player_id=player_id).first()

        if not character:
            messages.error(request, 'No character found for this player. Please create a character first.')
            return redirect('campaign_detail', campaign_id=campaign_id)

        # Get universe from world
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('campaign_detail', campaign_id=campaign_id)

        universe_id = world.get('universe_id')
        if not universe_id:
            messages.error(request, 'World is not associated with a universe')
            return redirect('campaign_detail', campaign_id=campaign_id)

        # Call orchestrator to generate opening scene
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/start-campaign",
                    json={
                        'profile_id': player_id,
                        'character_name': character.name,
                        'universe_id': universe_id,
                        'world_id': world_id,
                        'campaign_name': campaign.get('campaign_name', 'Untitled Campaign')
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()

                    # Update campaign with opening scene
                    db.campaign_state.update_one(
                        {'_id': campaign_id},
                        {
                            '$set': {
                                'current_scene': result.get('opening_scene'),
                                'status': 'in_progress'
                            },
                            '$push': {'scene_history': result.get('opening_scene')}
                        }
                    )

                    messages.success(request, 'Campaign started! The adventure begins...')
                else:
                    messages.error(request, f'Failed to start campaign: {response.text}')

        except Exception as e:
            messages.error(request, f'Failed to start campaign: {str(e)}')

        return redirect('campaign_detail', campaign_id=campaign_id)


class CampaignUpdateView(View):
    """Update an existing campaign"""

    def get(self, request, campaign_id):
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        # Add campaign_id field for template (Django doesn't allow _id)
        campaign['campaign_id'] = campaign['_id']

        worlds = list(db.world_definitions.find())

        # Get players from PostgreSQL
        players = Player.objects.filter(is_active=True).values(
            'player_id', 'display_name', 'email', 'role'
        )

        # Add id field for template
        for world in worlds:
            world['id'] = world['_id']

        # Convert players to list and add id field
        players_list = []
        for player in players:
            players_list.append({
                'id': str(player['player_id']),
                'player_name': player['display_name'],
                'email': player.get('email', ''),
                'role': player['role']
            })

        # Prepare form data with current values
        form_data = {
            'campaign_name': {'value': campaign.get('campaign_name', '')},
            'world_ids': {'value': campaign.get('world_ids', [])},
            'player_ids': {'value': campaign.get('player_ids', [])}
        }

        return render(request, 'campaigns/campaign_form.html', {
            'worlds': worlds,
            'players': players_list,
            'form': form_data,
            'campaign': campaign,
            'is_edit': True
        })

    def post(self, request, campaign_id):
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        # Get multi-select values
        world_ids = request.POST.getlist('world_ids')
        player_ids = request.POST.getlist('player_ids')

        if not world_ids or not player_ids:
            messages.error(request, 'Please select at least one world and one player')
            return redirect('campaign_update', campaign_id=campaign_id)

        # Get world data from MongoDB
        worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))

        # Get player data from PostgreSQL
        players = Player.objects.filter(
            player_id__in=player_ids,
            is_active=True
        ).values('player_id', 'display_name', 'email')

        if len(worlds) != len(world_ids) or len(players) != len(player_ids):
            messages.error(request, 'Invalid world or player selected')
            return redirect('campaign_update', campaign_id=campaign_id)

        # Build world and player names
        world_names = [w.get('world_name') for w in worlds]
        player_names = [p['display_name'] for p in players]

        # Convert player_ids to strings for consistency
        player_ids = [str(p['player_id']) for p in players]

        # Get old world and player IDs for Neo4j cleanup
        old_world_ids = campaign.get('world_ids', [])
        old_player_ids = campaign.get('player_ids', [])

        # Update MongoDB
        db.campaign_state.update_one(
            {'_id': campaign_id},
            {
                '$set': {
                    'campaign_name': request.POST.get('campaign_name'),
                    'world_ids': world_ids,
                    'world_names': world_names,
                    'player_ids': player_ids,
                    'player_names': player_names
                }
            }
        )

        # Update Neo4j relationships
        with neo4j_driver.session() as session:
            # Update campaign node name
            session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                SET c.name = $campaign_name
            """, campaign_id=campaign_id, campaign_name=request.POST.get('campaign_name'))

            # Remove old world relationships
            for old_world_id in old_world_ids:
                if old_world_id not in world_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})-[r:IN_WORLD]->(w:World {id: $world_id})
                        DELETE r
                    """, campaign_id=campaign_id, world_id=old_world_id)

            # Add new world relationships
            for world_id in world_ids:
                if world_id not in old_world_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})
                        MATCH (w:World {id: $world_id})
                        MERGE (c)-[:IN_WORLD]->(w)
                    """, campaign_id=campaign_id, world_id=world_id)

            # Remove old player relationships
            for old_player_id in old_player_ids:
                if old_player_id not in player_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})-[r:HAS_PLAYER]->(p:Player {id: $player_id})
                        DELETE r
                    """, campaign_id=campaign_id, player_id=old_player_id)

            # Add new player relationships
            for player_id in player_ids:
                if player_id not in old_player_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})
                        MATCH (p:Player {id: $player_id})
                        MERGE (c)-[:HAS_PLAYER]->(p)
                    """, campaign_id=campaign_id, player_id=player_id)

        messages.success(request, f'Campaign "{request.POST.get("campaign_name")}" updated successfully!')
        return redirect('campaign_detail', campaign_id=campaign_id)


class CampaignDeleteView(View):
    """Delete a campaign"""

    def post(self, request, campaign_id):
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        campaign_name = campaign.get('campaign_name', 'Unknown')

        # Delete from MongoDB
        db.campaign_state.delete_one({'_id': campaign_id})

        # Delete from Neo4j (including all relationships)
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                DETACH DELETE c
            """, campaign_id=campaign_id)

        messages.success(request, f'Campaign "{campaign_name}" has been permanently deleted')
        return redirect('campaign_list')


class CampaignDesignerWizardView(View):
    """Multi-step wizard for designing a complete campaign with quests and tasks - NEW V2"""

    def get(self, request):
        # Fetch universes from MongoDB
        universes_raw = list(db.universe_definitions.find({}))

        # Convert _id to id for Django template compatibility
        universes = []
        for universe in universes_raw:
            universe['id'] = str(universe['_id'])
            universes.append(universe)

        context = {
            'universes': universes
        }

        return render(request, 'campaigns/campaign_designer_wizard.html', context)

    def post(self, request):
        """Generate campaign with AI-powered quest and task generation"""
        import json
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get wizard data
            genre = request.POST.get('genre')
            world_id = request.POST.get('world_id')
            region_id = request.POST.get('region_id')
            story_outline = request.POST.get('story_outline')
            campaign_name = request.POST.get('campaign_name')

            logger.info(f"Campaign wizard submission: genre={genre}, world_id={world_id}, story={story_outline[:50] if story_outline else None}, name={campaign_name}")

            if not genre:
                messages.error(request, 'Please select a genre')
                logger.warning("Missing genre")
                return redirect('campaign_designer_wizard')
            if not world_id:
                messages.error(request, 'Please select a world')
                logger.warning("Missing world_id")
                return redirect('campaign_designer_wizard')
            if not story_outline:
                messages.error(request, 'Please provide a story outline')
                logger.warning("Missing story_outline")
                return redirect('campaign_designer_wizard')
            if not campaign_name:
                messages.error(request, 'Please provide a campaign name')
                logger.warning("Missing campaign_name")
                return redirect('campaign_designer_wizard')

            # Get world and region data
            world = db.world_definitions.find_one({'_id': world_id})
            region = db.region_definitions.find_one({'_id': region_id}) if region_id else None

            # Get locations for quest generation
            if region:
                location_ids = region.get('locations', [])
                locations = list(db.location_definitions.find({'_id': {'$in': location_ids}})) if location_ids else []
            else:
                # Get all regions and locations for the world
                region_ids = world.get('regions', [])
                regions = list(db.region_definitions.find({'_id': {'$in': region_ids}})) if region_ids else []
                locations = []
                for r in regions:
                    loc_ids = r.get('locations', [])
                    if loc_ids:
                        locations.extend(list(db.location_definitions.find({'_id': {'$in': loc_ids}})))

            # Get species for the world
            species_ids = world.get('species', [])
            species_list = list(db.species_definitions.find({'_id': {'$in': species_ids}})) if species_ids else []

            # Call AI agent to generate campaign structure
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-campaign",
                    json={
                        'genre': genre,
                        'world': {
                            'id': world_id,
                            'name': world.get('world_name'),
                            'setting': world.get('setting'),
                            'genre': world.get('genre'),
                            'backstory': world.get('backstory', '')
                        },
                        'region': {
                            'id': region_id,
                            'name': region.get('region_name') if region else None,
                            'description': region.get('description') if region else None
                        } if region else None,
                        'locations': [{'id': str(loc['_id']), 'name': loc.get('location_name'), 'description': loc.get('description')} for loc in locations[:10]],
                        'species': [{'id': str(sp['_id']), 'name': sp.get('species_name'), 'traits': sp.get('traits')} for sp in species_list[:5]],
                        'story_outline': story_outline,
                        'num_quests': int(request.POST.get('num_quests', 5))
                    },
                    timeout=120.0
                )

                if response.status_code != 200:
                    messages.error(request, f'AI generation failed: {response.text}')
                    return redirect('campaign_designer_wizard')

                ai_campaign = response.json()

            # Create campaign in MongoDB
            campaign_id = str(uuid.uuid4())

            campaign_data = {
                '_id': campaign_id,
                'campaign_name': campaign_name,
                'campaign_description': ai_campaign.get('campaign_description', ''),
                'campaign_backstory': ai_campaign.get('campaign_backstory', ''),
                'primary_locations': ai_campaign.get('primary_locations', []),
                'key_npcs': ai_campaign.get('key_npcs', []),
                'main_goals': ai_campaign.get('main_goals', []),
                'genre': genre,
                'world_ids': [world_id],
                'world_names': [world.get('world_name')],
                'region_id': region_id,
                'region_name': region.get('region_name') if region else None,
                'player_ids': [],
                'player_names': [],
                'story_outline': story_outline,
                'status': 'active',
                'scenes': ai_campaign.get('quests', []),  # Quests are scenes
                'current_scene_index': 0,
                'completed_scenes': [],
                'created_at': str(uuid.uuid4())  # Using UUID as timestamp placeholder
            }

            db.campaign_state.insert_one(campaign_data)

            # Create Neo4j relationships
            with neo4j_driver.session() as session:
                session.run("""
                    CREATE (c:Campaign {
                        id: $campaign_id,
                        name: $campaign_name,
                        genre: $genre,
                        status: 'active'
                    })
                """, campaign_id=campaign_id, campaign_name=campaign_name, genre=genre)

                # Link to world
                session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    MATCH (w:World {id: $world_id})
                    MERGE (c)-[:IN_WORLD]->(w)
                """, campaign_id=campaign_id, world_id=world_id)

            messages.success(request, f'Campaign "{campaign_name}" created successfully with {len(ai_campaign.get("quests", []))} quests!')
            return redirect('campaign_detail', campaign_id=campaign_id)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"ERROR creating campaign: {error_details}")
            messages.error(request, f'Error creating campaign: {str(e)}')
            return redirect('campaign_designer_wizard')
