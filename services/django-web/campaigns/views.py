"""
Views for Campaign management
Campaigns link Members, Worlds, and AI-generated narratives
"""
import uuid
import httpx
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from pymongo import MongoClient
from neo4j import GraphDatabase
import os
from members.models import Member


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
        return render(request, 'campaigns/campaign_list.html', {'campaigns': campaigns})


class CampaignCreateView(View):
    """Create a new campaign"""

    def get(self, request):
        worlds = list(db.world_definitions.find())

        # Get members from PostgreSQL instead of MongoDB
        members = Member.objects.filter(is_active=True).values(
            'member_id', 'display_name', 'email', 'role'
        )

        # Add id field for template (Django doesn't allow _id)
        for world in worlds:
            world['id'] = world['_id']

        # Convert members to list and add id field
        members_list = []
        for member in members:
            members_list.append({
                'id': str(member['member_id']),
                'member_name': member['display_name'],
                'email': member.get('email', ''),
                'role': member['role']
            })

        # Initialize empty form data for multi-selects
        form_data = {
            'world_ids': {'value': []},
            'member_ids': {'value': []}
        }

        return render(request, 'campaigns/campaign_form.html', {
            'worlds': worlds,
            'members': members_list,
            'form': form_data
        })

    def post(self, request):
        campaign_id = str(uuid.uuid4())

        # Get multi-select values
        world_ids = request.POST.getlist('world_ids')
        member_ids = request.POST.getlist('member_ids')

        if not world_ids or not member_ids:
            messages.error(request, 'Please select at least one world and one player')
            return redirect('campaign_create')

        # Get world data from MongoDB
        worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))

        # Get member data from PostgreSQL
        members = Member.objects.filter(
            member_id__in=member_ids,
            is_active=True
        ).values('member_id', 'display_name', 'email')

        if len(worlds) != len(world_ids) or len(members) != len(member_ids):
            messages.error(request, 'Invalid world or member selected')
            return redirect('campaign_create')

        # Build world and member names
        world_names = [w.get('world_name') for w in worlds]
        member_names = [m['display_name'] for m in members]

        # Convert member_ids to strings for consistency
        member_ids = [str(m['member_id']) for m in members]

        campaign_data = {
            '_id': campaign_id,
            'campaign_name': request.POST.get('campaign_name'),
            'world_ids': world_ids,
            'world_names': world_names,
            'member_ids': member_ids,
            'member_names': member_names,
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

            # Link to all selected members
            for member_id in member_ids:
                session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    MATCH (m:Member {id: $member_id})
                    MERGE (c)-[:HAS_PLAYER]->(m)
                """, campaign_id=campaign_id, member_id=member_id)

        messages.success(request, f'Campaign "{campaign_data["campaign_name"]}" created successfully with {len(world_ids)} world(s) and {len(member_ids)} player(s)!')
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

        # Add id field for template (Django doesn't allow _id)
        for world in worlds:
            world['id'] = world['_id']

        # Get all members for this campaign from PostgreSQL
        member_ids = campaign.get('member_ids', [])
        members = Member.objects.filter(
            member_id__in=member_ids,
            is_active=True
        ).values('member_id', 'display_name', 'email', 'role') if member_ids else []

        return render(request, 'campaigns/campaign_detail.html', {
            'campaign': campaign,
            'worlds': worlds,
            'members': list(members)
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

        # Call orchestrator to generate opening scene
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/start-campaign",
                    json={
                        'campaign_id': campaign_id,
                        'world_id': campaign.get('world_id'),
                        'member_id': campaign.get('member_id')
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

        # Get members from PostgreSQL
        members = Member.objects.filter(is_active=True).values(
            'member_id', 'display_name', 'email', 'role'
        )

        # Add id field for template
        for world in worlds:
            world['id'] = world['_id']

        # Convert members to list and add id field
        members_list = []
        for member in members:
            members_list.append({
                'id': str(member['member_id']),
                'member_name': member['display_name'],
                'email': member.get('email', ''),
                'role': member['role']
            })

        # Prepare form data with current values
        form_data = {
            'campaign_name': {'value': campaign.get('campaign_name', '')},
            'world_ids': {'value': campaign.get('world_ids', [])},
            'member_ids': {'value': campaign.get('member_ids', [])}
        }

        return render(request, 'campaigns/campaign_form.html', {
            'worlds': worlds,
            'members': members_list,
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
        member_ids = request.POST.getlist('member_ids')

        if not world_ids or not member_ids:
            messages.error(request, 'Please select at least one world and one player')
            return redirect('campaign_update', campaign_id=campaign_id)

        # Get world data from MongoDB
        worlds = list(db.world_definitions.find({'_id': {'$in': world_ids}}))

        # Get member data from PostgreSQL
        members = Member.objects.filter(
            member_id__in=member_ids,
            is_active=True
        ).values('member_id', 'display_name', 'email')

        if len(worlds) != len(world_ids) or len(members) != len(member_ids):
            messages.error(request, 'Invalid world or member selected')
            return redirect('campaign_update', campaign_id=campaign_id)

        # Build world and member names
        world_names = [w.get('world_name') for w in worlds]
        member_names = [m['display_name'] for m in members]

        # Convert member_ids to strings for consistency
        member_ids = [str(m['member_id']) for m in members]

        # Get old world and member IDs for Neo4j cleanup
        old_world_ids = campaign.get('world_ids', [])
        old_member_ids = campaign.get('member_ids', [])

        # Update MongoDB
        db.campaign_state.update_one(
            {'_id': campaign_id},
            {
                '$set': {
                    'campaign_name': request.POST.get('campaign_name'),
                    'world_ids': world_ids,
                    'world_names': world_names,
                    'member_ids': member_ids,
                    'member_names': member_names
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

            # Remove old member relationships
            for old_member_id in old_member_ids:
                if old_member_id not in member_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})-[r:HAS_PLAYER]->(m:Member {id: $member_id})
                        DELETE r
                    """, campaign_id=campaign_id, member_id=old_member_id)

            # Add new member relationships
            for member_id in member_ids:
                if member_id not in old_member_ids:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})
                        MATCH (m:Member {id: $member_id})
                        MERGE (c)-[:HAS_PLAYER]->(m)
                    """, campaign_id=campaign_id, member_id=member_id)

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
