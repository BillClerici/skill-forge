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
        # Query both collections: old campaign_state and new AI-generated campaigns
        old_campaigns = list(db.campaign_state.find())
        new_campaigns = list(db.campaigns.find())

        # Merge and normalize both formats
        campaigns = []

        # Process old format campaigns
        for campaign in old_campaigns:
            campaign['campaign_id'] = campaign['_id']
            campaign['campaign_name'] = campaign.get('campaign_name', 'Untitled Campaign')
            campaign['campaign_description'] = campaign.get('campaign_description', '')

            # Fetch world data for images
            world_ids = campaign.get('world_ids', [])
            if world_ids:
                worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))
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
            campaigns.append(campaign)

        # Process new AI-generated campaigns
        for campaign in new_campaigns:
            campaign['campaign_id'] = campaign['_id']
            campaign['campaign_name'] = campaign.get('name', 'Untitled Campaign')
            campaign['campaign_description'] = campaign.get('plot', '')

            # Get world data
            world_id = campaign.get('world_id')
            if world_id:
                world = db.world_definitions.find_one({'_id': world_id})
                if world:
                    world['primary_image_url'] = None
                    if world.get('world_images') and world.get('primary_image_index') is not None:
                        images = world.get('world_images', [])
                        primary_idx = world.get('primary_image_index')
                        if 0 <= primary_idx < len(images):
                            world['primary_image_url'] = images[primary_idx].get('url')
                    campaign['worlds'] = [world]
                    campaign['world_names'] = [world.get('world_name', 'Unknown World')]
                else:
                    campaign['worlds'] = []
                    campaign['world_names'] = []
            else:
                campaign['worlds'] = []
                campaign['world_names'] = []

            campaigns.append(campaign)

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
        # Try both collections: old format and new AI-generated
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        is_new_format = False
        if not campaign:
            campaign = db.campaigns.find_one({'_id': campaign_id})
            is_new_format = True
        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        # Add campaign_id field for template (Django doesn't allow _id)
        campaign['campaign_id'] = campaign['_id']

        # Normalize campaign_name field
        if 'name' in campaign and 'campaign_name' not in campaign:
            campaign['campaign_name'] = campaign['name']

        # Get all worlds for this campaign
        if is_new_format:
            world_id = campaign.get('world_id')
            worlds = [db.world_definitions.find_one({'_id': world_id})] if world_id else []
        else:
            world_ids = campaign.get('world_ids', [])
            worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}})) if world_ids else []

        # Add id field and primary_image_url for template (Django doesn't allow _id)
        for world in worlds:
            if world:
                world['id'] = world['_id']
                # Get primary image URL
                world['primary_image_url'] = None
                if world.get('world_images') and world.get('primary_image_index') is not None:
                    images = world.get('world_images', [])
                    primary_idx = world.get('primary_image_index')
                    if 0 <= primary_idx < len(images):
                        world['primary_image_url'] = images[primary_idx].get('url')

        # Get hierarchical data for new AI-generated campaigns
        quests = []
        if is_new_format:
            quest_ids = campaign.get('quest_ids', [])
            if quest_ids:
                quests_raw = list(db.quests.find({'_id': {'$in': quest_ids}}))

                for quest in quests_raw:
                    quest['quest_id'] = quest['_id']

                    # Get places for this quest
                    place_ids = quest.get('place_ids', [])
                    places_raw = list(db.places.find({'_id': {'$in': place_ids}})) if place_ids else []

                    places = []
                    for place in places_raw:
                        place['place_id'] = place['_id']

                        # Get scenes for this place
                        scene_ids = place.get('scene_ids', [])
                        scenes_raw = list(db.scenes.find({'_id': {'$in': scene_ids}})) if scene_ids else []

                        for scene in scenes_raw:
                            scene['scene_id'] = scene['_id']

                        place['scenes'] = scenes_raw
                        places.append(place)

                    quest['places'] = places
                    quests.append(quest)

        # Get all players for this campaign from PostgreSQL
        player_ids = campaign.get('player_ids', [])
        players = Player.objects.filter(
            player_id__in=player_ids,
            is_active=True
        ).values('player_id', 'display_name', 'email', 'role') if player_ids else []

        # Helper function to normalize objectives (handle both strings and objects)
        def normalize_objectives(objectives):
            if not objectives:
                return []
            normalized = []
            for obj in objectives:
                if isinstance(obj, str):
                    normalized.append(obj)
                elif isinstance(obj, dict):
                    # Try common keys for objective text
                    text = obj.get('objective') or obj.get('description') or obj.get('text') or str(obj)
                    normalized.append(text)
                else:
                    normalized.append(str(obj))
            return normalized

        # Normalize primary objectives in campaign data before passing to template
        if 'primary_objectives' in campaign and campaign['primary_objectives']:
            campaign['primary_objectives'] = normalize_objectives(campaign['primary_objectives'])

        # Prepare JSON data for JavaScript
        import json

        # Get world image URL for campaign view (fallback)
        world_image_url = None
        if worlds and worlds[0] and worlds[0].get('primary_image_url'):
            world_image_url = worlds[0]['primary_image_url']

        # Prefer campaign's own image over world image
        campaign_image_url = campaign.get('primary_image_url') or world_image_url

        campaign_json = {
            'campaign': {
                'id': str(campaign['_id']),
                'name': campaign.get('name', campaign.get('campaign_name', '')),
                'plot': campaign.get('plot', ''),
                'storyline': campaign.get('storyline', ''),
                'primary_objectives': normalize_objectives(campaign.get('primary_objectives', [])),
                'difficulty_level': campaign.get('difficulty_level', ''),
                'estimated_duration_hours': campaign.get('estimated_duration_hours', 0),
                'target_blooms_level': campaign.get('target_blooms_level', ''),
                'stats': campaign.get('stats', {}),
                'primary_image_url': campaign_image_url,
                'world_image_url': world_image_url
            },
            'quests': []
        }

        for quest in quests:
            quest_data = {
                'id': str(quest['_id']),
                'name': quest.get('name', ''),
                'description': quest.get('description', ''),
                'objectives': normalize_objectives(quest.get('objectives', [])),
                'difficulty_level': quest.get('difficulty_level', ''),
                'estimated_duration_minutes': quest.get('estimated_duration_minutes', 0),
                'backstory': quest.get('backstory', ''),
                'primary_image_url': quest.get('primary_image_url'),
                'places': []
            }

            for place in quest.get('places', []):
                place_data = {
                    'id': str(place['_id']),
                    'name': place.get('name', ''),
                    'description': place.get('description', ''),
                    'primary_image_url': place.get('primary_image_url'),
                    'scenes': []
                }

                for scene in place.get('scenes', []):
                    # Get NPCs for this scene
                    npc_ids = scene.get('npc_ids', [])
                    npcs = []
                    if npc_ids:
                        npcs_raw = list(db.npcs.find({'_id': {'$in': npc_ids}}))
                        for npc in npcs_raw:
                            npc_role = npc.get('role', '')

                            # Handle role being a complex dict (full NPC spec)
                            if isinstance(npc_role, dict):
                                # Check if it's the full NPC spec with provides_knowledge, etc.
                                if 'provides_knowledge' in npc_role or 'provides_items' in npc_role:
                                    # Extract meaningful information
                                    role_parts = []

                                    # Add dimension if available
                                    dimension = npc_role.get('dimension', '')
                                    if dimension:
                                        role_parts.append(f"{dimension.capitalize()} specialist")

                                    # Add knowledge expertise
                                    knowledge = npc_role.get('provides_knowledge', [])
                                    if knowledge:
                                        if len(knowledge) == 1:
                                            role_parts.append(f"Expert in {knowledge[0]}")
                                        else:
                                            role_parts.append(f"Knowledgeable in {len(knowledge)} areas")

                                    # Add item provider info
                                    items = npc_role.get('provides_items', [])
                                    if items:
                                        if len(items) == 1:
                                            role_parts.append(f"Provides {items[0]}")
                                        else:
                                            role_parts.append(f"Provides {len(items)} items")

                                    npc_role = " • ".join(role_parts) if role_parts else "Character"
                                else:
                                    # It's a dict with a 'type' field
                                    npc_role = npc_role.get('type', 'Character')

                            npcs.append({
                                'name': npc.get('name', 'Unknown'),
                                'role': str(npc_role) if npc_role else 'Character',
                                'species_name': npc.get('species_name', '')
                            })

                    # Get Discoveries for this scene
                    discovery_ids = scene.get('discovery_ids', [])
                    # Filter out None/null values
                    discovery_ids = [id for id in discovery_ids if id is not None and id != '']
                    discoveries = []
                    if discovery_ids:
                        discoveries_raw = list(db.discoveries.find({'_id': {'$in': discovery_ids}}))
                        for discovery in discoveries_raw:
                            discoveries.append({
                                'name': discovery.get('name', 'Unknown Discovery'),
                                'description': discovery.get('description', ''),
                                'knowledge_type': discovery.get('knowledge_type', 'information'),
                                'blooms_level': discovery.get('blooms_level', 0)
                            })

                    # Get Events for this scene
                    event_ids = scene.get('event_ids', [])
                    # Filter out None/null values
                    event_ids = [id for id in event_ids if id is not None and id != '']
                    events = []
                    if event_ids:
                        events_raw = list(db.events.find({'_id': {'$in': event_ids}}))
                        for event in events_raw:
                            events.append({
                                'name': event.get('name', 'Unknown Event'),
                                'description': event.get('description', ''),
                                'event_type': event.get('event_type', 'scripted'),
                                'outcomes': event.get('outcomes', [])
                            })

                    # Get Challenges for this scene
                    challenge_ids = scene.get('challenge_ids', [])
                    # Filter out None/null values
                    challenge_ids = [id for id in challenge_ids if id is not None and id != '']
                    challenges = []
                    if challenge_ids:
                        challenges_raw = list(db.challenges.find({'_id': {'$in': challenge_ids}}))
                        for challenge in challenges_raw:
                            challenges.append({
                                'name': challenge.get('name', 'Unknown Challenge'),
                                'description': challenge.get('description', ''),
                                'challenge_type': challenge.get('challenge_type', 'skill_check'),
                                'difficulty': challenge.get('difficulty', 'Medium'),
                                'success_rewards': challenge.get('success_rewards', {}),
                                'failure_consequences': challenge.get('failure_consequences', {})
                            })

                    # Get Knowledge Entities for this scene
                    knowledge_ids = scene.get('knowledge_ids', [])
                    # Filter out None/null values
                    knowledge_ids = [id for id in knowledge_ids if id is not None and id != '']
                    knowledge = []
                    if knowledge_ids:
                        knowledge_raw = list(db.knowledge.find({'_id': {'$in': knowledge_ids}}))
                        for kg in knowledge_raw:
                            # Format acquisition methods with entity names
                            # Group methods by type to avoid duplicates
                            methods_by_type = {}

                            for method in kg.get('acquisition_methods', []):
                                entity_id = method.get('entity_id')
                                method_type = method.get('type', 'unknown')
                                difficulty = method.get('difficulty', 'Medium')

                                # Look up entity name based on type
                                entity_name = None
                                if method_type == 'npc_conversation' and entity_id:
                                    npc = db.npcs.find_one({'_id': entity_id})
                                    if npc:
                                        entity_name = npc.get('name', None)
                                elif method_type == 'challenge' and entity_id:
                                    challenge = db.challenges.find_one({'_id': entity_id})
                                    if challenge:
                                        entity_name = challenge.get('name', None)
                                elif method_type == 'environmental_discovery' and entity_id:
                                    discovery = db.discoveries.find_one({'_id': entity_id})
                                    if discovery:
                                        entity_name = discovery.get('name', None)
                                elif method_type == 'dynamic_event' and entity_id:
                                    event = db.events.find_one({'_id': entity_id})
                                    if event:
                                        entity_name = event.get('name', None)

                                # Only add if we found a valid entity
                                if entity_name:
                                    if method_type not in methods_by_type:
                                        methods_by_type[method_type] = {}  # Use dict for deduplication

                                    # Use entity_name as key to prevent duplicates (same name = duplicate from user perspective)
                                    if entity_name not in methods_by_type[method_type]:
                                        methods_by_type[method_type][entity_name] = {
                                            'name': entity_name,
                                            'difficulty': difficulty
                                        }

                            # Create concise display for each method type
                            acquisition_methods = []
                            for method_type, entities_dict in methods_by_type.items():
                                # Convert dict values to list
                                entities = list(entities_dict.values())

                                if method_type == 'npc_conversation':
                                    # Show each NPC individually so users can see their names
                                    for entity in entities:
                                        acquisition_methods.append({
                                            'display': f"Talk to {entity['name']} ({entity['difficulty']})",
                                            'type': method_type
                                        })
                                elif method_type == 'challenge':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"Complete {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"Complete {len(entities)} challenges ({diff_str})",
                                            'type': method_type
                                        })
                                elif method_type == 'environmental_discovery':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"Discover {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"Make {len(entities)} discoveries ({diff_str})",
                                            'type': method_type
                                        })
                                elif method_type == 'dynamic_event':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"During {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"During {len(entities)} events ({diff_str})",
                                            'type': method_type
                                        })

                            knowledge.append({
                                'name': kg.get('name', 'Unknown Knowledge'),
                                'description': kg.get('description', ''),
                                'knowledge_type': kg.get('knowledge_type', 'information'),
                                'primary_dimension': kg.get('primary_dimension', ''),
                                'acquisition_methods': acquisition_methods
                            })

                    # Get Items for this scene
                    item_ids = scene.get('item_ids', [])
                    # Filter out None/null values
                    item_ids = [id for id in item_ids if id is not None and id != '']
                    items = []
                    if item_ids:
                        items_raw = list(db.items.find({'_id': {'$in': item_ids}}))
                        for item in items_raw:
                            # Format acquisition methods with entity names
                            # Group methods by type to avoid duplicates
                            methods_by_type = {}

                            for method in item.get('acquisition_methods', []):
                                entity_id = method.get('entity_id')
                                method_type = method.get('type', 'unknown')
                                difficulty = method.get('difficulty', 'Medium')

                                # Look up entity name based on type
                                entity_name = None
                                if method_type == 'npc_conversation' and entity_id:
                                    npc = db.npcs.find_one({'_id': entity_id})
                                    if npc:
                                        entity_name = npc.get('name', None)
                                elif method_type == 'challenge' and entity_id:
                                    challenge = db.challenges.find_one({'_id': entity_id})
                                    if challenge:
                                        entity_name = challenge.get('name', None)
                                elif method_type == 'environmental_discovery' and entity_id:
                                    discovery = db.discoveries.find_one({'_id': entity_id})
                                    if discovery:
                                        entity_name = discovery.get('name', None)
                                elif method_type == 'dynamic_event' and entity_id:
                                    event = db.events.find_one({'_id': entity_id})
                                    if event:
                                        entity_name = event.get('name', None)

                                # Only add if we found a valid entity
                                if entity_name:
                                    if method_type not in methods_by_type:
                                        methods_by_type[method_type] = {}  # Use dict for deduplication

                                    # Use entity_name as key to prevent duplicates (same name = duplicate from user perspective)
                                    if entity_name not in methods_by_type[method_type]:
                                        methods_by_type[method_type][entity_name] = {
                                            'name': entity_name,
                                            'difficulty': difficulty
                                        }

                            # Create concise display for each method type
                            acquisition_methods = []
                            for method_type, entities_dict in methods_by_type.items():
                                # Convert dict values to list
                                entities = list(entities_dict.values())

                                if method_type == 'npc_conversation':
                                    # Show each NPC individually so users can see their names
                                    for entity in entities:
                                        acquisition_methods.append({
                                            'display': f"Receive from {entity['name']} ({entity['difficulty']})",
                                            'type': method_type
                                        })
                                elif method_type == 'challenge':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"Earn by completing {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"Earn by completing {len(entities)} challenges ({diff_str})",
                                            'type': method_type
                                        })
                                elif method_type == 'environmental_discovery':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"Find at {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"Find at {len(entities)} discoveries ({diff_str})",
                                            'type': method_type
                                        })
                                elif method_type == 'dynamic_event':
                                    if len(entities) == 1:
                                        acquisition_methods.append({
                                            'display': f"Obtain during {entities[0]['name']} ({entities[0]['difficulty']})",
                                            'type': method_type
                                        })
                                    else:
                                        difficulties = list(set([e['difficulty'] for e in entities]))
                                        diff_str = ', '.join(difficulties)
                                        acquisition_methods.append({
                                            'display': f"Obtain during {len(entities)} events ({diff_str})",
                                            'type': method_type
                                        })

                            items.append({
                                'name': item.get('name', 'Unknown Item'),
                                'description': item.get('description', ''),
                                'item_type': item.get('item_type', 'item'),
                                'is_quest_critical': item.get('is_quest_critical', False),
                                'acquisition_methods': acquisition_methods
                            })

                    # Get Rubrics for this scene
                    rubric_ids = scene.get('rubric_ids', [])
                    # Filter out None/null values
                    rubric_ids = [id for id in rubric_ids if id is not None and id != '']
                    rubrics = []
                    if rubric_ids:
                        rubrics_raw = list(db.rubrics.find({'_id': {'$in': rubric_ids}}))
                        for rubric in rubrics_raw:
                            rubrics.append({
                                'interaction_name': rubric.get('interaction_name', 'Unknown Interaction'),
                                'rubric_type': rubric.get('rubric_type', 'evaluation'),
                                'primary_dimension': rubric.get('primary_dimension', ''),
                                'evaluation_criteria': rubric.get('evaluation_criteria', [])
                            })

                    scene_data = {
                        'id': str(scene['_id']),
                        'name': scene.get('name', ''),
                        'description': scene.get('description', ''),
                        'level_3_location_name': scene.get('level_3_location_name', ''),
                        'primary_image_url': scene.get('primary_image_url'),
                        'npcs': npcs,
                        'discoveries': discoveries,
                        'events': events,
                        'challenges': challenges,
                        'knowledge': knowledge,
                        'items': items,
                        'rubrics': rubrics
                    }
                    place_data['scenes'].append(scene_data)

                quest_data['places'].append(place_data)

            campaign_json['quests'].append(quest_data)

        return render(request, 'campaigns/campaign_detail.html', {
            'campaign': campaign,
            'worlds': worlds,
            'players': list(players),
            'quests': quests,
            'is_new_format': is_new_format,
            'members': list(players),  # For backwards compatibility
            'campaign_json': json.dumps(campaign_json)
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
    """Delete a campaign with comprehensive cleanup across all databases"""

    def post(self, request, campaign_id):
        import logging
        logger = logging.getLogger(__name__)

        # Check if campaign exists (either format)
        campaign = db.campaign_state.find_one({'_id': campaign_id})
        is_new_format = False
        if not campaign:
            campaign = db.campaigns.find_one({'_id': campaign_id})
            is_new_format = True

        if not campaign:
            messages.error(request, 'Campaign not found')
            return redirect('campaign_list')

        campaign_name = campaign.get('campaign_name') or campaign.get('name', 'Unknown')

        try:
            # Track deletion counts
            deleted_counts = {
                'quests': 0,
                'places': 0,
                'scenes': 0,
                'npcs': 0,
                'discoveries': 0,
                'events': 0,
                'challenges': 0,
                'knowledge': 0,
                'items': 0,
                'rubrics': 0
            }

            # Collect IDs for Neo4j deletion
            npc_ids = []
            location_ids = []  # scenes and places
            knowledge_ids = []
            item_ids = []
            discovery_ids = []
            event_ids = []
            challenge_ids = []

            if is_new_format:
                logger.info(f"Deleting new format campaign: {campaign_id}")

                # 1. Find all quests for this campaign
                quests = list(db.quests.find({'campaign_id': campaign_id}))
                quest_ids = [q['_id'] for q in quests]
                deleted_counts['quests'] = len(quest_ids)
                logger.info(f"Found {len(quest_ids)} quests to delete")

                # 2. Find all places for these quests
                places = list(db.places.find({'quest_id': {'$in': quest_ids}})) if quest_ids else []
                place_ids = [p['_id'] for p in places]
                deleted_counts['places'] = len(place_ids)
                location_ids.extend(place_ids)
                logger.info(f"Found {len(place_ids)} places to delete")

                # 3. Find all scenes for these places
                scenes = list(db.scenes.find({'place_id': {'$in': place_ids}})) if place_ids else []
                scene_ids = [s['_id'] for s in scenes]
                deleted_counts['scenes'] = len(scene_ids)
                location_ids.extend(scene_ids)
                logger.info(f"Found {len(scene_ids)} scenes to delete")

                # 4. Find and delete all scene elements
                if scene_ids:
                    # NPCs
                    npcs = list(db.npcs.find({'level_3_location_id': {'$in': scene_ids}}))
                    npc_ids = [n['_id'] for n in npcs]
                    deleted_counts['npcs'] = len(npc_ids)
                    db.npcs.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(npc_ids)} NPCs")

                    # Discoveries
                    discoveries = list(db.discoveries.find({'level_3_location_id': {'$in': scene_ids}}))
                    discovery_ids = [d['_id'] for d in discoveries]
                    deleted_counts['discoveries'] = len(discovery_ids)
                    db.discoveries.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(discovery_ids)} discoveries")

                    # Events
                    events = list(db.events.find({'level_3_location_id': {'$in': scene_ids}}))
                    event_ids = [e['_id'] for e in events]
                    deleted_counts['events'] = len(event_ids)
                    db.events.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(event_ids)} events")

                    # Challenges
                    challenges = list(db.challenges.find({'level_3_location_id': {'$in': scene_ids}}))
                    challenge_ids = [c['_id'] for c in challenges]
                    deleted_counts['challenges'] = len(challenge_ids)
                    db.challenges.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(challenge_ids)} challenges")

                    # Knowledge
                    knowledge = list(db.knowledge.find({'level_3_location_id': {'$in': scene_ids}}))
                    knowledge_ids = [k['_id'] for k in knowledge]
                    deleted_counts['knowledge'] = len(knowledge_ids)
                    db.knowledge.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(knowledge_ids)} knowledge entities")

                    # Items
                    items = list(db.items.find({'level_3_location_id': {'$in': scene_ids}}))
                    item_ids = [i['_id'] for i in items]
                    deleted_counts['items'] = len(item_ids)
                    db.items.delete_many({'level_3_location_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(item_ids)} items")

                # 5. Find and delete rubrics
                rubrics = list(db.rubrics.find({'campaign_id': campaign_id}))
                rubric_ids = [r['_id'] for r in rubrics]
                deleted_counts['rubrics'] = len(rubric_ids)
                db.rubrics.delete_many({'campaign_id': campaign_id})
                logger.info(f"Deleted {len(rubric_ids)} rubrics")

                # 6. Delete scenes
                if scene_ids:
                    db.scenes.delete_many({'_id': {'$in': scene_ids}})
                    logger.info(f"Deleted {len(scene_ids)} scenes")

                # 7. Delete places
                if place_ids:
                    db.places.delete_many({'_id': {'$in': place_ids}})
                    logger.info(f"Deleted {len(place_ids)} places")

                # 8. Delete quests
                if quest_ids:
                    db.quests.delete_many({'_id': {'$in': quest_ids}})
                    logger.info(f"Deleted {len(quest_ids)} quests")

                # 9. Delete campaign
                db.campaigns.delete_one({'_id': campaign_id})
                logger.info(f"Deleted campaign: {campaign_id}")

            else:
                # Old format campaign
                logger.info(f"Deleting old format campaign: {campaign_id}")
                db.campaign_state.delete_one({'_id': campaign_id})
                logger.info(f"Deleted old format campaign: {campaign_id}")

            # Delete from Neo4j
            try:
                with neo4j_driver.session() as session:
                    # Delete NPC nodes
                    if npc_ids:
                        result = session.run("""
                            MATCH (n:NPC)
                            WHERE n.id IN $npc_ids
                            DETACH DELETE n
                            RETURN count(n) as deleted_count
                        """, npc_ids=npc_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} NPC nodes")

                    # Delete Scene nodes
                    if scene_ids:
                        result = session.run("""
                            MATCH (s:Scene)
                            WHERE s.id IN $scene_ids
                            DETACH DELETE s
                            RETURN count(s) as deleted_count
                        """, scene_ids=scene_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Scene nodes")

                    # Delete Place nodes
                    if place_ids:
                        result = session.run("""
                            MATCH (p:Place)
                            WHERE p.id IN $place_ids
                            DETACH DELETE p
                            RETURN count(p) as deleted_count
                        """, place_ids=place_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Place nodes")

                    # Delete Location nodes (generic - for any that weren't caught above)
                    if location_ids:
                        result = session.run("""
                            MATCH (l:Location)
                            WHERE l.id IN $location_ids
                            DETACH DELETE l
                            RETURN count(l) as deleted_count
                        """, location_ids=location_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Location nodes")

                    # Delete Knowledge nodes
                    if knowledge_ids:
                        result = session.run("""
                            MATCH (k:Knowledge)
                            WHERE k.id IN $knowledge_ids
                            DETACH DELETE k
                            RETURN count(k) as deleted_count
                        """, knowledge_ids=knowledge_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Knowledge nodes")

                    # Delete Item nodes
                    if item_ids:
                        result = session.run("""
                            MATCH (i:Item)
                            WHERE i.id IN $item_ids
                            DETACH DELETE i
                            RETURN count(i) as deleted_count
                        """, item_ids=item_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Item nodes")

                    # Delete Discovery nodes
                    if discovery_ids:
                        result = session.run("""
                            MATCH (d:Discovery)
                            WHERE d.id IN $discovery_ids
                            DETACH DELETE d
                            RETURN count(d) as deleted_count
                        """, discovery_ids=discovery_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Discovery nodes")

                    # Delete Event nodes
                    if event_ids:
                        result = session.run("""
                            MATCH (e:Event)
                            WHERE e.id IN $event_ids
                            DETACH DELETE e
                            RETURN count(e) as deleted_count
                        """, event_ids=event_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Event nodes")

                    # Delete Challenge nodes
                    if challenge_ids:
                        result = session.run("""
                            MATCH (c:Challenge)
                            WHERE c.id IN $challenge_ids
                            DETACH DELETE c
                            RETURN count(c) as deleted_count
                        """, challenge_ids=challenge_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Challenge nodes")

                    # Delete Quest nodes
                    if quest_ids:
                        result = session.run("""
                            MATCH (q:Quest)
                            WHERE q.id IN $quest_ids
                            DETACH DELETE q
                            RETURN count(q) as deleted_count
                        """, quest_ids=quest_ids)
                        count = result.single()['deleted_count']
                        logger.warning(f"Neo4j: Deleted {count} Quest nodes")

                    # Delete Campaign node and all remaining relationships
                    result = session.run("""
                        MATCH (c:Campaign {id: $campaign_id})
                        DETACH DELETE c
                        RETURN count(c) as deleted_count
                    """, campaign_id=campaign_id)
                    count = result.single()['deleted_count']
                    logger.warning(f"Neo4j: Deleted {count} Campaign node")

            except Exception as neo4j_error:
                logger.warning(f"Neo4j deletion warning: {neo4j_error}")
                messages.warning(request, f"Neo4j cleanup warning: {str(neo4j_error)}")

            # Delete from PostgreSQL (non-critical)
            try:
                import psycopg2
                POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
                POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
                POSTGRES_DB = os.getenv('POSTGRES_DB', 'skillforge')
                POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
                POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

                conn = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD
                )

                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM campaigns_playercampaign
                            WHERE campaign_id = %s
                        """, (campaign_id,))
                        pg_deleted_count = cursor.rowcount
                        conn.commit()
                        logger.info(f"Deleted {pg_deleted_count} player-campaign associations from PostgreSQL")
                finally:
                    conn.close()

            except Exception as pg_error:
                logger.warning(f"PostgreSQL deletion warning: {pg_error}")
                # Non-critical - don't show warning to user

            # Calculate total deleted entities
            total_deleted = sum(deleted_counts.values())

            messages.success(request, f'Campaign "{campaign_name}" and {total_deleted} related entities have been permanently deleted')

        except Exception as e:
            logger.error(f"Error during campaign deletion: {e}", exc_info=True)
            messages.error(request, f'Failed to delete campaign: {str(e)}')

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
            # Remove _id to prevent template errors
            if '_id' in universe:
                del universe['_id']
            universes.append(universe)

        context = {
            'universes': universes
        }

        return render(request, 'campaigns/campaign_designer_wizard_v2.html', context)

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


from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


class CampaignGenerateImageView(View):
    """Generate AI image for a campaign using DALL-E 3 API"""

    def post(self, request, campaign_id):
        campaign = db.campaigns.find_one({'_id': campaign_id})
        if not campaign:
            return JsonResponse({'error': 'Campaign not found'}, status=404)

        try:
            # Get world context for richer prompts
            world_id = campaign.get('world_id')
            world = db.world_definitions.find_one({'_id': world_id}) if world_id else None

            # Build comprehensive prompt from campaign + world context
            plot = campaign.get('plot', '')
            storyline = campaign.get('storyline', '')

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            # Strong anti-text prefix
            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            # Strong anti-text suffix
            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO scrolls, books, or documents with visible text
- Pure visual imagery only"""

            # Build campaign prompt
            world_context = ""
            if world:
                world_context = f" Set in the world of {world.get('world_name', '')}: {world.get('description', '')[:200]}"

            campaign_prompt = f"""{no_text_prefix}
Epic campaign scene: {campaign.get('name', 'Campaign')}

Plot: {plot[:300]}

{world_context}

Create a dramatic, cinematic scene that captures the essence of this campaign. Fantasy RPG art style, high detail, atmospheric.
{no_text_suffix}"""

            logger.info(f"Generating campaign image with prompt: {campaign_prompt[:200]}...")

            # Generate image (16:9 ratio)
            response = client.images.generate(
                model="dall-e-3",
                prompt=campaign_prompt,
                size="1792x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            # Download and save image
            media_path = Path(settings.MEDIA_ROOT) / 'campaigns' / campaign_id
            media_path.mkdir(parents=True, exist_ok=True)

            image_filename = f"campaign_{uuid.uuid4().hex[:8]}.png"
            image_path = media_path / image_filename

            urllib.request.urlretrieve(image_url, str(image_path))

            # Save to MongoDB
            relative_url = f"/media/campaigns/{campaign_id}/{image_filename}"

            current_images = campaign.get('campaign_images', [])
            current_images.append({
                'url': relative_url,
                'prompt': campaign_prompt,
                'created_at': str(uuid.uuid4())
            })

            db.campaigns.update_one(
                {'_id': campaign_id},
                {'$set': {'campaign_images': current_images}}
            )

            return JsonResponse({
                'success': True,
                'image_url': relative_url,
                'images': current_images
            })

        except Exception as e:
            logger.error(f"Error generating campaign image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class QuestGenerateImageView(View):
    """Generate AI image for a quest using DALL-E 3 API"""

    def post(self, request, campaign_id, quest_id):
        quest = db.quests.find_one({'_id': quest_id})
        if not quest:
            return JsonResponse({'error': 'Quest not found'}, status=404)

        campaign = db.campaigns.find_one({'_id': campaign_id})
        if not campaign:
            return JsonResponse({'error': 'Campaign not found'}, status=404)

        try:
            # Build contextual prompt: Quest + Campaign context
            quest_desc = quest.get('description', '')
            quest_backstory = quest.get('backstory', '')
            campaign_plot = campaign.get('plot', '')

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO scrolls, books, or documents with visible text
- Pure visual imagery only"""

            quest_prompt = f"""{no_text_prefix}
Fantasy RPG Quest: {quest.get('name', 'Quest')}

Quest Description: {quest_desc[:250]}

Campaign Context: {campaign_plot[:150]}

Backstory: {quest_backstory[:150] if quest_backstory else ''}

Create an atmospheric scene depicting this quest. Fantasy RPG art style, dramatic lighting, high detail.
{no_text_suffix}"""

            logger.info(f"Generating quest image with prompt: {quest_prompt[:200]}...")

            response = client.images.generate(
                model="dall-e-3",
                prompt=quest_prompt,
                size="1792x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            # Download and save
            media_path = Path(settings.MEDIA_ROOT) / 'quests' / quest_id
            media_path.mkdir(parents=True, exist_ok=True)

            image_filename = f"quest_{uuid.uuid4().hex[:8]}.png"
            image_path = media_path / image_filename

            urllib.request.urlretrieve(image_url, str(image_path))

            relative_url = f"/media/quests/{quest_id}/{image_filename}"

            current_images = quest.get('quest_images', [])
            current_images.append({
                'url': relative_url,
                'prompt': quest_prompt,
                'created_at': str(uuid.uuid4())
            })

            db.quests.update_one(
                {'_id': quest_id},
                {'$set': {'quest_images': current_images}}
            )

            return JsonResponse({
                'success': True,
                'image_url': relative_url,
                'images': current_images
            })

        except Exception as e:
            logger.error(f"Error generating quest image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class PlaceGenerateImageView(View):
    """Generate AI image for a place using DALL-E 3 API"""

    def post(self, request, campaign_id, quest_id, place_id):
        place = db.places.find_one({'_id': place_id})
        if not place:
            return JsonResponse({'error': 'Place not found'}, status=404)

        quest = db.quests.find_one({'_id': quest_id})
        campaign = db.campaigns.find_one({'_id': campaign_id})

        try:
            # Build contextual prompt: Place + Quest + Campaign
            place_desc = place.get('description', '')
            quest_desc = quest.get('description', '') if quest else ''
            campaign_plot = campaign.get('plot', '') if campaign else ''

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO scrolls, books, or documents with visible text
- Pure visual imagery only"""

            place_prompt = f"""{no_text_prefix}
Fantasy RPG Location: {place.get('name', 'Place')}

Location Description: {place_desc[:300]}

Quest Context: {quest_desc[:150] if quest_desc else ''}

Campaign Setting: {campaign_plot[:100] if campaign_plot else ''}

Create a detailed, atmospheric view of this location. Fantasy RPG art style, immersive environment, high detail.
{no_text_suffix}"""

            logger.info(f"Generating place image with prompt: {place_prompt[:200]}...")

            response = client.images.generate(
                model="dall-e-3",
                prompt=place_prompt,
                size="1792x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            media_path = Path(settings.MEDIA_ROOT) / 'places' / place_id
            media_path.mkdir(parents=True, exist_ok=True)

            image_filename = f"place_{uuid.uuid4().hex[:8]}.png"
            image_path = media_path / image_filename

            urllib.request.urlretrieve(image_url, str(image_path))

            relative_url = f"/media/places/{place_id}/{image_filename}"

            current_images = place.get('place_images', [])
            current_images.append({
                'url': relative_url,
                'prompt': place_prompt,
                'created_at': str(uuid.uuid4())
            })

            db.places.update_one(
                {'_id': place_id},
                {'$set': {'place_images': current_images}}
            )

            return JsonResponse({
                'success': True,
                'image_url': relative_url,
                'images': current_images
            })

        except Exception as e:
            logger.error(f"Error generating place image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class SceneGenerateImageView(View):
    """Generate AI image for a scene using DALL-E 3 API"""

    def post(self, request, campaign_id, quest_id, place_id, scene_id):
        scene = db.scenes.find_one({'_id': scene_id})
        if not scene:
            return JsonResponse({'error': 'Scene not found'}, status=404)

        place = db.places.find_one({'_id': place_id})
        quest = db.quests.find_one({'_id': quest_id})
        campaign = db.campaigns.find_one({'_id': campaign_id})

        try:
            # Build contextual prompt: Scene + Place + Quest + Campaign
            scene_desc = scene.get('description', '')
            place_desc = place.get('description', '') if place else ''
            quest_desc = quest.get('description', '') if quest else ''
            campaign_plot = campaign.get('plot', '') if campaign else ''

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO scrolls, books, or documents with visible text
- Pure visual imagery only"""

            scene_prompt = f"""{no_text_prefix}
Fantasy RPG Scene: {scene.get('name', 'Scene')}

Scene Description: {scene_desc[:250]}

Location: {place.get('name', '')} - {place_desc[:100] if place_desc else ''}

Quest: {quest_desc[:100] if quest_desc else ''}

Campaign: {campaign_plot[:80] if campaign_plot else ''}

Create a cinematic moment capturing this scene. Fantasy RPG art style, dramatic composition, high detail.
{no_text_suffix}"""

            logger.info(f"Generating scene image with prompt: {scene_prompt[:200]}...")

            response = client.images.generate(
                model="dall-e-3",
                prompt=scene_prompt,
                size="1792x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            media_path = Path(settings.MEDIA_ROOT) / 'scenes' / scene_id
            media_path.mkdir(parents=True, exist_ok=True)

            image_filename = f"scene_{uuid.uuid4().hex[:8]}.png"
            image_path = media_path / image_filename

            urllib.request.urlretrieve(image_url, str(image_path))

            relative_url = f"/media/scenes/{scene_id}/{image_filename}"

            current_images = scene.get('scene_images', [])
            current_images.append({
                'url': relative_url,
                'prompt': scene_prompt,
                'created_at': str(uuid.uuid4())
            })

            db.scenes.update_one(
                {'_id': scene_id},
                {'$set': {'scene_images': current_images}}
            )

            return JsonResponse({
                'success': True,
                'image_url': relative_url,
                'images': current_images
            })

        except Exception as e:
            logger.error(f"Error generating scene image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class CampaignSetPrimaryImageView(View):
    """Set primary image for a campaign"""

    def post(self, request, campaign_id):
        try:
            import json
            data = json.loads(request.body)
            image_url = data.get('image_url')

            if not image_url:
                return JsonResponse({'error': 'image_url required'}, status=400)

            campaign = db.campaigns.find_one({'_id': campaign_id})
            if not campaign:
                return JsonResponse({'error': 'Campaign not found'}, status=404)

            # Update campaign with primary image URL
            db.campaigns.update_one(
                {'_id': campaign_id},
                {'$set': {'primary_image_url': image_url}}
            )

            return JsonResponse({'success': True, 'image_url': image_url})

        except Exception as e:
            logger.error(f"Error setting campaign primary image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class QuestSetPrimaryImageView(View):
    """Set primary image for a quest"""

    def post(self, request, campaign_id, quest_id):
        try:
            import json
            data = json.loads(request.body)
            image_url = data.get('image_url')

            if not image_url:
                return JsonResponse({'error': 'image_url required'}, status=400)

            quest = db.quests.find_one({'_id': quest_id})
            if not quest:
                return JsonResponse({'error': 'Quest not found'}, status=404)

            db.quests.update_one(
                {'_id': quest_id},
                {'$set': {'primary_image_url': image_url}}
            )

            return JsonResponse({'success': True, 'image_url': image_url})

        except Exception as e:
            logger.error(f"Error setting quest primary image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class PlaceSetPrimaryImageView(View):
    """Set primary image for a place"""

    def post(self, request, campaign_id, quest_id, place_id):
        try:
            import json
            data = json.loads(request.body)
            image_url = data.get('image_url')

            if not image_url:
                return JsonResponse({'error': 'image_url required'}, status=400)

            place = db.places.find_one({'_id': place_id})
            if not place:
                return JsonResponse({'error': 'Place not found'}, status=404)

            db.places.update_one(
                {'_id': place_id},
                {'$set': {'primary_image_url': image_url}}
            )

            return JsonResponse({'success': True, 'image_url': image_url})

        except Exception as e:
            logger.error(f"Error setting place primary image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class SceneSetPrimaryImageView(View):
    """Set primary image for a scene"""

    def post(self, request, campaign_id, quest_id, place_id, scene_id):
        try:
            import json
            data = json.loads(request.body)
            image_url = data.get('image_url')

            if not image_url:
                return JsonResponse({'error': 'image_url required'}, status=400)

            scene = db.scenes.find_one({'_id': scene_id})
            if not scene:
                return JsonResponse({'error': 'Scene not found'}, status=404)

            db.scenes.update_one(
                {'_id': scene_id},
                {'$set': {'primary_image_url': image_url}}
            )

            return JsonResponse({'success': True, 'image_url': image_url})

        except Exception as e:
            logger.error(f"Error setting scene primary image: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
