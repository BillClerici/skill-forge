"""
Views for Universe and World management
Uses MongoDB for definitions and Neo4j for relationships
"""
import uuid
import httpx
import requests
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.http import JsonResponse
from pymongo import MongoClient
from neo4j import GraphDatabase
import os
import json


# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URL = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')


class UniverseListView(View):
    """List all universes"""

    def get(self, request):
        universes = list(db.universe_definitions.find())
        # Add universe_id field for template (Django doesn't allow _id)
        for universe in universes:
            universe['universe_id'] = universe['_id']
        return render(request, 'worlds/universe_list.html', {'universes': universes})


class UniverseCreateView(View):
    """Create a new universe"""

    def get(self, request):
        return render(request, 'worlds/universe_form.html')

    def post(self, request):
        universe_id = str(uuid.uuid4())
        universe_data = {
            '_id': universe_id,
            'universe_name': request.POST.get('universe_name'),
            'description': request.POST.get('description'),
            'purpose_category': request.POST.get('purpose_category'),
            'target_age_group': request.POST.get('target_age_group'),
            'max_content_rating': request.POST.get('max_content_rating', 'PG'),
            'narrative_tone': {
                'style': request.POST.get('narrative_style', 'friendly'),
                'humor_level': request.POST.get('humor_level', 'moderate')
            },
            'vocabulary_style': {
                'reading_level': request.POST.get('reading_level', 'middle_school'),
                'complexity': request.POST.get('complexity', 'moderate')
            },
            'features': {
                'combat_enabled': request.POST.get('combat_enabled') == 'on',
                'romance_enabled': request.POST.get('romance_enabled') == 'on',
                'character_death': request.POST.get('character_death') == 'on'
            }
        }

        # Store in MongoDB
        db.universe_definitions.insert_one(universe_data)

        # Create node in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (u:Universe {
                    id: $universe_id,
                    name: $universe_name,
                    content_rating: $content_rating
                })
            """, universe_id=universe_id,
               universe_name=universe_data['universe_name'],
               content_rating=universe_data['max_content_rating'])

        messages.success(request, f'Universe "{universe_data["universe_name"]}" created successfully!')
        return redirect('universe_list')


class UniverseDetailView(View):
    """View universe details"""

    def get(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        worlds = list(db.world_definitions.find({'universe_id': universe_id}))

        # Add world_id field for template (Django doesn't allow _id)
        for world in worlds:
            world['world_id'] = world['_id']

        # Process data for template display
        if universe:
            # Add universe_id field for template (Django doesn't allow _id)
            universe['universe_id'] = universe['_id']

            # Format reading level for display
            if universe.get('vocabulary_style', {}).get('reading_level'):
                reading_level = universe['vocabulary_style']['reading_level']
                universe['reading_level_display'] = reading_level.replace('_', ' ').title()

            # Format purpose category for display
            if universe.get('purpose_category'):
                purpose_category = universe['purpose_category']
                universe['purpose_category_display'] = purpose_category.replace('_', ' ').title()

            # Format target age group for display
            if universe.get('target_age_group'):
                age_group = universe['target_age_group']
                age_mapping = {
                    'children': 'Children (5-10)',
                    'teen': 'Teen (11-17)',
                    'adult': 'Adult (18+)',
                    'all_ages': 'All Ages'
                }
                universe['target_age_group_display'] = age_mapping.get(age_group, age_group.replace('_', ' ').title())

            # Extract nested fields for easier template access
            narrative_tone = universe.get('narrative_tone', {})
            universe['narrative_style'] = narrative_tone.get('style', '')
            universe['humor_level'] = narrative_tone.get('humor_level', '')

            vocab_style = universe.get('vocabulary_style', {})
            universe['reading_level'] = vocab_style.get('reading_level', '')
            universe['complexity'] = vocab_style.get('complexity', '')

            features = universe.get('features', {})
            universe['combat_enabled'] = features.get('combat_enabled', False)
            universe['romance_enabled'] = features.get('romance_enabled', False)
            universe['character_death'] = features.get('character_death', False)

        return render(request, 'worlds/universe_detail.html', {
            'universe': universe,
            'worlds': worlds,
            'worlds_count': len(worlds)
        })


class WorldListView(View):
    """List all worlds"""

    def get(self, request):
        worlds = list(db.world_definitions.find())
        # Add world_id field for template (Django doesn't allow _id)
        for world in worlds:
            world['world_id'] = world['_id']
        return render(request, 'worlds/world_list.html', {'worlds': worlds})


class WorldCreateView(View):
    """Create a new world"""

    def get(self, request):
        universes = list(db.universe_definitions.find())
        # Add id field for template
        for universe in universes:
            universe['id'] = universe['_id']

        # Initialize empty form data for multi-selects
        form_data = {
            'universe_ids': {'value': []},
            'themes': {'value': []},
            'visual_style': {'value': []}
        }
        return render(request, 'worlds/world_form.html', {
            'universes': universes,
            'form': form_data
        })

    def post(self, request):
        world_id = str(uuid.uuid4())

        # Get multi-select values (returns list)
        universe_ids = request.POST.getlist('universe_ids')
        themes = request.POST.getlist('themes')
        visual_styles = request.POST.getlist('visual_style')

        world_data = {
            '_id': world_id,
            'world_name': request.POST.get('world_name'),
            'universe_ids': universe_ids,
            'genre': request.POST.get('genre'),
            'themes': themes,
            'visual_style': visual_styles,
            'power_system': request.POST.get('power_system', ''),
            'physical_properties': {
                'star_system': request.POST.get('star_system', ''),
                'planetary_classification': request.POST.get('planetary_classification', ''),
                'world_features': request.POST.getlist('world_features'),
                'resources': request.POST.getlist('resources'),
                'terrain': request.POST.getlist('terrain'),
                'climate': request.POST.get('climate', '')
            },
            'biological_properties': {
                'habitability': request.POST.get('habitability', ''),
                'flora': request.POST.getlist('flora'),
                'fauna': request.POST.getlist('fauna'),
                'native_species': request.POST.getlist('native_species')
            },
            'technological_properties': {
                'technology_level': request.POST.get('technology_level', ''),
                'technology_history': request.POST.getlist('technology_history'),
                'automation': request.POST.get('automation', ''),
                'weapons_tools': request.POST.getlist('weapons_tools')
            },
            'societal_properties': {
                'government': request.POST.getlist('government'),
                'culture_traditions': request.POST.getlist('culture_traditions'),
                'inhabitants': request.POST.getlist('inhabitants'),
                'social_issues': request.POST.getlist('social_issues')
            },
            'historical_properties': {
                'major_events': request.POST.getlist('major_events'),
                'significant_sites': request.POST.getlist('significant_sites'),
                'timeline': request.POST.get('timeline', ''),
                'myths_origin': request.POST.getlist('myths_origin')
            },
            'regions': [],
            'npcs': []
        }

        # Store in MongoDB
        db.world_definitions.insert_one(world_data)

        # Create node and relationships in Neo4j for each universe
        with neo4j_driver.session() as session:
            for universe_id in universe_ids:
                session.run("""
                    MATCH (u:Universe {id: $universe_id})
                    MERGE (w:World {id: $world_id})
                    ON CREATE SET w.name = $world_name, w.genre = $genre
                    MERGE (w)-[:IN_UNIVERSE]->(u)
                """, universe_id=universe_id,
                   world_id=world_id,
                   world_name=world_data['world_name'],
                   genre=world_data['genre'])

        messages.success(request, f'World "{world_data["world_name"]}" created successfully!')
        return redirect('world_list')


class WorldDetailView(View):
    """View world details"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        universes = []
        regions = []

        if world:
            # Add world_id field for template (Django doesn't allow _id)
            world['world_id'] = world['_id']

            # Get all universes this world belongs to
            universe_ids = world.get('universe_ids', [])
            if not universe_ids and world.get('universe_id'):
                # Legacy support: convert single universe_id to array
                universe_ids = [world.get('universe_id')]

            if universe_ids:
                universes = list(db.universe_definitions.find({'_id': {'$in': universe_ids}}))
                for u in universes:
                    u['universe_id'] = u['_id']

            # Get all regions for this world
            region_ids = world.get('regions', [])
            if region_ids:
                regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))
                for r in regions:
                    r['region_id'] = r['_id']

            # Format themes and visual styles for display
            if isinstance(world.get('themes'), list):
                world['themes_display'] = ', '.join(world['themes'])
            else:
                world['themes_display'] = world.get('themes', '')

            if isinstance(world.get('visual_style'), list):
                world['visual_style_display'] = ', '.join(world['visual_style'])
            else:
                world['visual_style_display'] = world.get('visual_style', '')

        return render(request, 'worlds/world_detail.html', {
            'world': world,
            'universes': universes,
            'regions': regions
        })


class UniverseUpdateView(View):
    """Update an existing universe"""

    def get(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        if not universe:
            messages.error(request, 'Universe not found')
            return redirect('universe_list')

        # Add universe_id field for template
        universe['universe_id'] = universe['_id']

        # Extract nested fields for form
        narrative_tone = universe.get('narrative_tone', {})
        vocab_style = universe.get('vocabulary_style', {})
        features = universe.get('features', {})

        # Create form-compatible dict structure
        form_data = {
            'instance': universe,
            'universe_name': {'value': universe.get('universe_name', '')},
            'description': {'value': universe.get('description', '')},
            'purpose_category': {'value': universe.get('purpose_category', '')},
            'target_age_group': {'value': universe.get('target_age_group', '')},
            'max_content_rating': {'value': universe.get('max_content_rating', '')},
            'narrative_style': {'value': narrative_tone.get('style', '')},
            'humor_level': {'value': narrative_tone.get('humor_level', '')},
            'reading_level': {'value': vocab_style.get('reading_level', '')},
            'complexity': {'value': vocab_style.get('complexity', '')},
            'combat_enabled': {'value': features.get('combat_enabled', False)},
            'romance_enabled': {'value': features.get('romance_enabled', False)},
            'character_death': {'value': features.get('character_death', False)}
        }

        return render(request, 'worlds/universe_form.html', {
            'form': form_data,
            'universe': universe
        })

    def post(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        if not universe:
            messages.error(request, 'Universe not found')
            return redirect('universe_list')

        universe_data = {
            'universe_name': request.POST.get('universe_name'),
            'description': request.POST.get('description'),
            'purpose_category': request.POST.get('purpose_category'),
            'target_age_group': request.POST.get('target_age_group'),
            'max_content_rating': request.POST.get('max_content_rating', 'PG'),
            'narrative_tone': {
                'style': request.POST.get('narrative_style', 'friendly'),
                'humor_level': request.POST.get('humor_level', 'moderate')
            },
            'vocabulary_style': {
                'reading_level': request.POST.get('reading_level', 'middle_school'),
                'complexity': request.POST.get('complexity', 'moderate')
            },
            'features': {
                'combat_enabled': request.POST.get('combat_enabled') == 'on',
                'romance_enabled': request.POST.get('romance_enabled') == 'on',
                'character_death': request.POST.get('character_death') == 'on'
            }
        }

        # Update in MongoDB
        db.universe_definitions.update_one({'_id': universe_id}, {'$set': universe_data})

        # Update node in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (u:Universe {id: $universe_id})
                SET u.name = $universe_name,
                    u.content_rating = $content_rating
            """, universe_id=universe_id,
               universe_name=universe_data['universe_name'],
               content_rating=universe_data['max_content_rating'])

        messages.success(request, f'Universe "{universe_data["universe_name"]}" updated successfully!')
        return redirect('universe_detail', universe_id=universe_id)


class UniverseDeleteView(View):
    """Delete a universe with relationship checking"""

    def get(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        if not universe:
            messages.error(request, 'Universe not found')
            return redirect('universe_list')

        # Add universe_id field for template (Django doesn't allow _id)
        universe['universe_id'] = universe['_id']

        # Check for related worlds in Neo4j
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (w:World)-[:IN_UNIVERSE]->(u:Universe {id: $universe_id})
                RETURN w.id as world_id, w.name as world_name
            """, universe_id=universe_id)
            related_worlds = [{'world_id': record['world_id'], 'world_name': record['world_name']}
                            for record in result]

        return render(request, 'worlds/universe_confirm_delete.html', {
            'universe': universe,
            'related_worlds': related_worlds
        })

    def post(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        if not universe:
            messages.error(request, 'Universe not found')
            return redirect('universe_list')

        # Check for related worlds
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (w:World)-[:IN_UNIVERSE]->(u:Universe {id: $universe_id})
                RETURN count(w) as world_count
            """, universe_id=universe_id)
            world_count = result.single()['world_count']

            if world_count > 0:
                messages.error(request, f'Cannot delete universe "{universe["universe_name"]}". It has {world_count} related world(s). Delete those first.')
                return redirect('universe_detail', universe_id=universe_id)

            # Delete from Neo4j
            session.run("""
                MATCH (u:Universe {id: $universe_id})
                DELETE u
            """, universe_id=universe_id)

        # Delete from MongoDB
        db.universe_definitions.delete_one({'_id': universe_id})

        messages.success(request, f'Universe "{universe["universe_name"]}" deleted successfully!')
        return redirect('universe_list')


class WorldUpdateView(View):
    """Update an existing world"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        universes = list(db.universe_definitions.find())
        # Add id field for template
        for universe in universes:
            universe['id'] = universe['_id']

        # Get property groups
        physical = world.get('physical_properties', {})
        biological = world.get('biological_properties', {})
        technological = world.get('technological_properties', {})
        societal = world.get('societal_properties', {})
        historical = world.get('historical_properties', {})

        # Get arrays for multi-select fields (support both old and new format)
        universe_ids = world.get('universe_ids', [])
        if not universe_ids and world.get('universe_id'):
            universe_ids = [world.get('universe_id')]

        themes = world.get('themes', [])
        if isinstance(themes, str):
            themes = [t.strip() for t in themes.split(',') if t.strip()]

        visual_styles = world.get('visual_style', [])
        if isinstance(visual_styles, str):
            visual_styles = [visual_styles] if visual_styles else []

        world['world_id'] = world['_id']

        # Create form-compatible dict structure
        form_data = {
            'instance': world,
            'world_name': {'value': world.get('world_name', '')},
            'universe_ids': {'value': universe_ids},
            'genre': {'value': world.get('genre', '')},
            'themes': {'value': themes},
            'visual_style': {'value': visual_styles},
            'power_system': {'value': world.get('power_system', '')},
            # Physical Properties
            'star_system': {'value': physical.get('star_system', '')},
            'planetary_classification': {'value': physical.get('planetary_classification', '')},
            'world_features': {'value': physical.get('world_features', [])},
            'resources': {'value': physical.get('resources', [])},
            'terrain': {'value': physical.get('terrain', [])},
            'climate': {'value': physical.get('climate', '')},
            # Biological Properties
            'habitability': {'value': biological.get('habitability', '')},
            'flora': {'value': biological.get('flora', [])},
            'fauna': {'value': biological.get('fauna', [])},
            'native_species': {'value': biological.get('native_species', [])},
            # Technological Properties
            'technology_level': {'value': technological.get('technology_level', '')},
            'technology_history': {'value': technological.get('technology_history', [])},
            'automation': {'value': technological.get('automation', '')},
            'weapons_tools': {'value': technological.get('weapons_tools', [])},
            # Societal Properties
            'government': {'value': societal.get('government', [])},
            'culture_traditions': {'value': societal.get('culture_traditions', [])},
            'inhabitants': {'value': societal.get('inhabitants', [])},
            'social_issues': {'value': societal.get('social_issues', [])},
            # Historical Properties
            'major_events': {'value': historical.get('major_events', [])},
            'significant_sites': {'value': historical.get('significant_sites', [])},
            'timeline': {'value': historical.get('timeline', '')},
            'myths_origin': {'value': historical.get('myths_origin', [])}
        }

        return render(request, 'worlds/world_form.html', {
            'form': form_data,
            'universes': universes,
            'world': world
        })

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        # Get multi-select values
        universe_ids = request.POST.getlist('universe_ids')
        themes = request.POST.getlist('themes')
        visual_styles = request.POST.getlist('visual_style')

        world_data = {
            'world_name': request.POST.get('world_name'),
            'universe_ids': universe_ids,
            'genre': request.POST.get('genre'),
            'themes': themes,
            'visual_style': visual_styles,
            'power_system': request.POST.get('power_system', ''),
            'physical_properties': {
                'star_system': request.POST.get('star_system', ''),
                'planetary_classification': request.POST.get('planetary_classification', ''),
                'world_features': request.POST.getlist('world_features'),
                'resources': request.POST.getlist('resources'),
                'terrain': request.POST.getlist('terrain'),
                'climate': request.POST.get('climate', '')
            },
            'biological_properties': {
                'habitability': request.POST.get('habitability', ''),
                'flora': request.POST.getlist('flora'),
                'fauna': request.POST.getlist('fauna'),
                'native_species': request.POST.getlist('native_species')
            },
            'technological_properties': {
                'technology_level': request.POST.get('technology_level', ''),
                'technology_history': request.POST.getlist('technology_history'),
                'automation': request.POST.get('automation', ''),
                'weapons_tools': request.POST.getlist('weapons_tools')
            },
            'societal_properties': {
                'government': request.POST.getlist('government'),
                'culture_traditions': request.POST.getlist('culture_traditions'),
                'inhabitants': request.POST.getlist('inhabitants'),
                'social_issues': request.POST.getlist('social_issues')
            },
            'historical_properties': {
                'major_events': request.POST.getlist('major_events'),
                'significant_sites': request.POST.getlist('significant_sites'),
                'timeline': request.POST.get('timeline', ''),
                'myths_origin': request.POST.getlist('myths_origin')
            }
        }

        # Update in MongoDB
        db.world_definitions.update_one({'_id': world_id}, {'$set': world_data})

        # Update node in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (w:World {id: $world_id})
                SET w.name = $world_name,
                    w.genre = $genre
            """, world_id=world_id,
               world_name=world_data['world_name'],
               genre=world_data['genre'])

            # Update universe relationships - delete old, create new
            session.run("""
                MATCH (w:World {id: $world_id})
                OPTIONAL MATCH (w)-[r:IN_UNIVERSE]->()
                DELETE r
            """, world_id=world_id)

            # Create new relationships for each selected universe
            for universe_id in universe_ids:
                session.run("""
                    MATCH (w:World {id: $world_id})
                    MATCH (u:Universe {id: $universe_id})
                    MERGE (w)-[:IN_UNIVERSE]->(u)
                """, world_id=world_id, universe_id=universe_id)

        messages.success(request, f'World "{world_data["world_name"]}" updated successfully!')
        return redirect('world_detail', world_id=world_id)


class WorldDeleteView(View):
    """Delete a world with relationship checking"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        # Add world_id field for template (Django doesn't allow _id)
        world['world_id'] = world['_id']

        # Check for related campaigns in Neo4j
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (c:Campaign)-[:IN_WORLD]->(w:World {id: $world_id})
                RETURN c.id as campaign_id, c.name as campaign_name
            """, world_id=world_id)
            related_campaigns = [{'campaign_id': record['campaign_id'], 'campaign_name': record['campaign_name']}
                               for record in result]

        universe = db.universe_definitions.find_one({'_id': world.get('universe_id')})

        return render(request, 'worlds/world_confirm_delete.html', {
            'world': world,
            'universe': universe,
            'related_campaigns': related_campaigns
        })

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        # Check for related campaigns
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (c:Campaign)-[:IN_WORLD]->(w:World {id: $world_id})
                RETURN count(c) as campaign_count
            """, world_id=world_id)
            campaign_count = result.single()['campaign_count']

            if campaign_count > 0:
                messages.error(request, f'Cannot delete world "{world["world_name"]}". It has {campaign_count} related campaign(s). Delete those first.')
                return redirect('world_detail', world_id=world_id)

            # Delete from Neo4j
            session.run("""
                MATCH (w:World {id: $world_id})
                DETACH DELETE w
            """, world_id=world_id)

        # Delete from MongoDB
        db.world_definitions.delete_one({'_id': world_id})

        messages.success(request, f'World "{world["world_name"]}" deleted successfully!')
        return redirect('world_list')


class WorldGenerateBackstoryView(View):
    """Generate AI backstory for a world"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        # Call orchestrator to generate backstory
        try:
            with httpx.Client() as client:
                # Get property groups
                physical = world.get('physical_properties', {})
                biological = world.get('biological_properties', {})
                technological = world.get('technological_properties', {})
                societal = world.get('societal_properties', {})
                historical = world.get('historical_properties', {})

                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-backstory",
                    json={
                        'world_id': world_id,
                        'world_name': world.get('world_name', ''),
                        'genre': world.get('genre', ''),
                        'themes': world.get('themes', []),
                        'visual_style': world.get('visual_style', []),
                        'power_system': world.get('power_system', ''),
                        'physical_properties': physical,
                        'biological_properties': biological,
                        'technological_properties': technological,
                        'societal_properties': societal,
                        'historical_properties': historical
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return JsonResponse({
                        'success': True,
                        'backstory': result.get('backstory', ''),
                        'tokens_used': result.get('tokens_used', 0),
                        'cost_usd': result.get('cost_usd', 0)
                    })
                else:
                    return JsonResponse({'error': f'Agent error: {response.text}'}, status=response.status_code)

        except httpx.TimeoutException:
            return JsonResponse({'error': 'Request timed out'}, status=504)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate backstory: {str(e)}'}, status=500)


class WorldSaveBackstoryView(View):
    """Save the backstory to the world"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            backstory = request.POST.get('backstory', '')

            # Save backstory to MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': {'backstory': backstory}}
            )

            messages.success(request, 'Backstory saved successfully!')
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to save backstory: {str(e)}'}, status=500)


# ============================================
# Region Views
# ============================================

class RegionListView(View):
    """List all regions for a world"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        world['world_id'] = world['_id']

        # Get all regions for this world from MongoDB
        regions = list(db.region_definitions.find({'world_id': world_id}))
        for region in regions:
            region['region_id'] = region['_id']

        return render(request, 'worlds/region_list.html', {
            'world': world,
            'regions': regions
        })


class RegionCreateView(View):
    """Create a new region"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        world['world_id'] = world['_id']

        form_data = {
            'region_name': {'value': ''},
            'region_type': {'value': ''},
            'climate': {'value': ''},
            'terrain': {'value': []},
            'description': {'value': ''}
        }

        return render(request, 'worlds/region_form.html', {
            'world': world,
            'form': form_data
        })

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        region_id = str(uuid.uuid4())
        terrain = request.POST.getlist('terrain')

        region_data = {
            '_id': region_id,
            'region_name': request.POST.get('region_name'),
            'region_type': request.POST.get('region_type'),
            'climate': request.POST.get('climate'),
            'terrain': terrain,
            'description': request.POST.get('description', ''),
            'world_id': world_id,
            'locations': []
        }

        # Store in MongoDB
        db.region_definitions.insert_one(region_data)

        # Update world's regions array
        db.world_definitions.update_one(
            {'_id': world_id},
            {'$push': {'regions': region_id}}
        )

        # Create node in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (w:World {id: $world_id})
                MERGE (r:Region {id: $region_id})
                ON CREATE SET r.name = $region_name, r.type = $region_type
                MERGE (r)-[:IN_WORLD]->(w)
            """, world_id=world_id, region_id=region_id,
               region_name=region_data['region_name'],
               region_type=region_data['region_type'])

        messages.success(request, f'Region "{region_data["region_name"]}" created successfully!')
        return redirect('region_detail', world_id=world_id, region_id=region_id)


class RegionDetailView(View):
    """View region details"""

    def get(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('region_list', world_id=world_id)

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']

        # Get all locations for this region
        location_ids = region.get('locations', [])
        locations = list(db.location_definitions.find({'_id': {'$in': location_ids}})) if location_ids else []
        for location in locations:
            location['location_id'] = location['_id']

        return render(request, 'worlds/region_detail.html', {
            'world': world,
            'region': region,
            'locations': locations
        })


class RegionUpdateView(View):
    """Update an existing region"""

    def get(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('region_list', world_id=world_id)

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']

        form_data = {
            'region_name': {'value': region.get('region_name', '')},
            'region_type': {'value': region.get('region_type', '')},
            'climate': {'value': region.get('climate', '')},
            'terrain': {'value': region.get('terrain', [])},
            'description': {'value': region.get('description', '')}
        }

        return render(request, 'worlds/region_form.html', {
            'world': world,
            'region': region,
            'form': form_data,
            'is_edit': True
        })

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('region_list', world_id=world_id)

        terrain = request.POST.getlist('terrain')

        # Update MongoDB
        db.region_definitions.update_one(
            {'_id': region_id},
            {
                '$set': {
                    'region_name': request.POST.get('region_name'),
                    'region_type': request.POST.get('region_type'),
                    'climate': request.POST.get('climate'),
                    'terrain': terrain,
                    'description': request.POST.get('description', '')
                }
            }
        )

        # Update Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (r:Region {id: $region_id})
                SET r.name = $region_name, r.type = $region_type
            """, region_id=region_id,
               region_name=request.POST.get('region_name'),
               region_type=request.POST.get('region_type'))

        messages.success(request, f'Region "{request.POST.get("region_name")}" updated successfully!')
        return redirect('region_detail', world_id=world_id, region_id=region_id)


class RegionDeleteView(View):
    """Delete a region"""

    def get(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        if not world or not region:
            messages.error(request, 'World or region not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']

        return render(request, 'worlds/region_confirm_delete.html', {
            'world': world,
            'region': region
        })

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('region_list', world_id=world_id)

        region_name = region.get('region_name', 'Unknown')

        # Check for related locations
        location_count = len(region.get('locations', []))
        if location_count > 0:
            messages.error(request, f'Cannot delete region "{region_name}". It has {location_count} location(s). Delete those first.')
            return redirect('region_detail', world_id=world_id, region_id=region_id)

        # Remove from world's regions array
        db.world_definitions.update_one(
            {'_id': world_id},
            {'$pull': {'regions': region_id}}
        )

        # Delete from MongoDB
        db.region_definitions.delete_one({'_id': region_id})

        # Delete from Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (r:Region {id: $region_id})
                DETACH DELETE r
            """, region_id=region_id)

        messages.success(request, f'Region "{region_name}" deleted successfully!')
        return redirect('region_list', world_id=world_id)


class RegionGenerateBackstoryView(View):
    """Generate AI backstory for a region"""

    def post(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        if not world or not region:
            return JsonResponse({'error': 'World or region not found'}, status=404)

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-region-backstory",
                    json={
                        'region_id': region_id,
                        'region_name': region.get('region_name', ''),
                        'region_type': region.get('region_type', ''),
                        'climate': region.get('climate', ''),
                        'terrain': region.get('terrain', []),
                        'description': region.get('description', ''),
                        'world_name': world.get('world_name'),
                        'world_genre': world.get('genre')
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return JsonResponse({
                        'success': True,
                        'backstory': result.get('backstory', ''),
                        'tokens_used': result.get('tokens_used', 0),
                        'cost_usd': result.get('cost_usd', 0)
                    })
                else:
                    return JsonResponse({'error': f'Agent error: {response.text}'}, status=response.status_code)

        except httpx.TimeoutException:
            return JsonResponse({'error': 'Request timed out'}, status=504)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate backstory: {str(e)}'}, status=500)


class RegionSaveBackstoryView(View):
    """Save the backstory to the region"""

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            return JsonResponse({'error': 'Region not found'}, status=404)

        try:
            backstory = request.POST.get('backstory', '')

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': {'backstory': backstory}}
            )

            messages.success(request, 'Backstory saved successfully!')
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to save backstory: {str(e)}'}, status=500)


# ============================================
# LOCATION VIEWS
# ============================================

class LocationListView(View):
    """List all locations in a region"""

    def get(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        if not world or not region:
            messages.error(request, 'World or region not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']

        # Get all locations for this region
        location_ids = region.get('locations', [])
        locations = []
        if location_ids:
            locations = list(db.location_definitions.find({'_id': {'$in': location_ids}}))

        return render(request, 'worlds/location_list.html', {
            'world': world,
            'region': region,
            'locations': locations
        })


class LocationCreateView(View):
    """Create a new location"""

    def get(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        if not world or not region:
            messages.error(request, 'World or region not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']

        form_data = {
            'location_name': {'value': ''},
            'location_type': {'value': ''},
            'description': {'value': ''},
            'features': {'value': []}
        }

        return render(request, 'worlds/location_form.html', {
            'world': world,
            'region': region,
            'form': form_data
        })

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('world_list')

        location_id = str(uuid.uuid4())
        features = request.POST.getlist('features')

        location_data = {
            '_id': location_id,
            'location_name': request.POST.get('location_name'),
            'location_type': request.POST.get('location_type'),
            'description': request.POST.get('description', ''),
            'features': features,
            'region_id': region_id,
            'world_id': world_id
        }

        # Store in MongoDB
        db.location_definitions.insert_one(location_data)

        # Update region's locations array
        db.region_definitions.update_one(
            {'_id': region_id},
            {'$push': {'locations': location_id}}
        )

        # Create node in Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (r:Region {id: $region_id})
                MERGE (l:Location {id: $location_id})
                ON CREATE SET l.name = $location_name, l.type = $location_type
                MERGE (l)-[:IN_REGION]->(r)
            """, region_id=region_id, location_id=location_id,
               location_name=location_data['location_name'],
               location_type=location_data['location_type'])

        messages.success(request, f'Location "{location_data["location_name"]}" created successfully!')
        return redirect('location_detail', world_id=world_id, region_id=region_id, location_id=location_id)


class LocationDetailView(View):
    """View location details"""

    def get(self, request, world_id, region_id, location_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})
        location = db.location_definitions.find_one({'_id': location_id})

        if not world or not region or not location:
            messages.error(request, 'World, region, or location not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']
        location['location_id'] = location['_id']

        return render(request, 'worlds/location_detail.html', {
            'world': world,
            'region': region,
            'location': location
        })


class LocationUpdateView(View):
    """Update an existing location"""

    def get(self, request, world_id, region_id, location_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})
        location = db.location_definitions.find_one({'_id': location_id})

        if not world or not region or not location:
            messages.error(request, 'World, region, or location not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']
        location['location_id'] = location['_id']

        return render(request, 'worlds/location_form.html', {
            'world': world,
            'region': region,
            'location': location
        })

    def post(self, request, world_id, region_id, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            messages.error(request, 'Location not found')
            return redirect('region_detail', world_id=world_id, region_id=region_id)

        features = request.POST.getlist('features')

        updated_data = {
            'location_name': request.POST.get('location_name'),
            'location_type': request.POST.get('location_type'),
            'description': request.POST.get('description', ''),
            'features': features
        }

        db.location_definitions.update_one(
            {'_id': location_id},
            {'$set': updated_data}
        )

        # Update Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (l:Location {id: $location_id})
                SET l.name = $location_name, l.type = $location_type
            """, location_id=location_id,
               location_name=updated_data['location_name'],
               location_type=updated_data['location_type'])

        messages.success(request, 'Location updated successfully!')
        return redirect('location_detail', world_id=world_id, region_id=region_id, location_id=location_id)


class LocationDeleteView(View):
    """Delete a location"""

    def get(self, request, world_id, region_id, location_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})
        location = db.location_definitions.find_one({'_id': location_id})

        if not world or not region or not location:
            messages.error(request, 'World, region, or location not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        region['region_id'] = region['_id']
        location['location_id'] = location['_id']

        return render(request, 'worlds/location_confirm_delete.html', {
            'world': world,
            'region': region,
            'location': location
        })

    def post(self, request, world_id, region_id, location_id):
        # Remove from region's locations array
        db.region_definitions.update_one(
            {'_id': region_id},
            {'$pull': {'locations': location_id}}
        )

        # Delete from MongoDB
        db.location_definitions.delete_one({'_id': location_id})

        # Delete from Neo4j
        with neo4j_driver.session() as session:
            session.run("""
                MATCH (l:Location {id: $location_id})
                DETACH DELETE l
            """, location_id=location_id)

        messages.success(request, 'Location deleted successfully!')
        return redirect('region_detail', world_id=world_id, region_id=region_id)


class LocationGenerateBackstoryView(View):
    """Generate backstory for a location using AI"""

    def post(self, request, world_id, region_id, location_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})
        location = db.location_definitions.find_one({'_id': location_id})

        if not world or not region or not location:
            return JsonResponse({'error': 'World, region, or location not found'}, status=404)

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-location-backstory",
                    json={
                        'location_id': location_id,
                        'location_name': location.get('location_name', ''),
                        'location_type': location.get('location_type', ''),
                        'description': location.get('description', ''),
                        'features': location.get('features', []),
                        'region_name': region.get('region_name'),
                        'world_name': world.get('world_name')
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return JsonResponse({
                        'success': True,
                        'backstory': result.get('backstory', ''),
                        'tokens_used': result.get('tokens_used', 0),
                        'cost_usd': result.get('cost_usd', 0)
                    })
                else:
                    return JsonResponse({'error': f'Orchestrator error: {response.text}'}, status=response.status_code)

        except Exception as e:
            return JsonResponse({'error': f'Failed to generate backstory: {str(e)}'}, status=500)


class LocationSaveBackstoryView(View):
    """Save the backstory to the location"""

    def post(self, request, world_id, region_id, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            return JsonResponse({'error': 'Location not found'}, status=404)

        try:
            backstory = request.POST.get('backstory', '')

            db.location_definitions.update_one(
                {'_id': location_id},
                {'$set': {'backstory': backstory}}
            )

            messages.success(request, 'Backstory saved successfully!')
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to save backstory: {str(e)}'}, status=500)


class WorldGenerateRegionsView(View):
    """Generate multiple regions with backstories and locations using AI"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            data = json.loads(request.body)
            num_regions = data.get('num_regions', 3)
            num_locations_per_region = data.get('num_locations_per_region', 3)

            # Validate input
            if not isinstance(num_regions, int) or num_regions < 1 or num_regions > 10:
                return JsonResponse({'error': 'num_regions must be between 1 and 10'}, status=400)
            if not isinstance(num_locations_per_region, int) or num_locations_per_region < 1 or num_locations_per_region > 10:
                return JsonResponse({'error': 'num_locations_per_region must be between 1 and 10'}, status=400)

            # Prepare world context with new properties
            world_context = {
                'world_name': world.get('world_name'),
                'genre': world.get('genre'),
                'themes': world.get('themes', []),
                'visual_style': world.get('visual_style', []),
                'power_system': world.get('power_system', ''),
                'backstory': world.get('backstory', ''),
                'physical_properties': world.get('physical_properties', {}),
                'biological_properties': world.get('biological_properties', {}),
                'technological_properties': world.get('technological_properties', {}),
                'societal_properties': world.get('societal_properties', {}),
                'historical_properties': world.get('historical_properties', {})
            }

            # Call orchestrator to generate regions with locations
            orchestrator_url = f'{ORCHESTRATOR_URL}/api/generate-regions'
            response = requests.post(
                orchestrator_url,
                json={
                    'world_context': world_context,
                    'num_regions': num_regions,
                    'num_locations_per_region': num_locations_per_region
                },
                timeout=300  # 5 minute timeout for batch generation
            )

            if response.status_code == 200:
                result = response.json()
                regions_data = result.get('regions', [])

                regions_created = 0
                locations_created = 0

                # Create each region and its locations
                for region_data in regions_data:
                    # Create region
                    region_id = str(uuid.uuid4())
                    region_doc = {
                        '_id': region_id,
                        'region_name': region_data.get('region_name'),
                        'region_type': region_data.get('region_type'),
                        'climate': region_data.get('climate'),
                        'terrain': region_data.get('terrain', []),
                        'description': region_data.get('description', ''),
                        'backstory': region_data.get('backstory', ''),
                        'world_id': world_id,
                        'locations': []
                    }

                    # Create locations for this region
                    location_ids = []
                    for location_data in region_data.get('locations', []):
                        location_id = str(uuid.uuid4())
                        location_doc = {
                            '_id': location_id,
                            'location_name': location_data.get('location_name'),
                            'location_type': location_data.get('location_type'),
                            'description': location_data.get('description', ''),
                            'features': location_data.get('features', []),
                            'backstory': location_data.get('backstory', ''),
                            'region_id': region_id,
                            'world_id': world_id
                        }
                        db.location_definitions.insert_one(location_doc)
                        location_ids.append(location_id)
                        locations_created += 1

                    # Add location IDs to region
                    region_doc['locations'] = location_ids

                    # Insert region
                    db.region_definitions.insert_one(region_doc)
                    regions_created += 1

                    # Add region to world
                    db.world_definitions.update_one(
                        {'_id': world_id},
                        {'$push': {'regions': region_id}}
                    )

                    # Create region node in Neo4j
                    with neo4j_driver.session() as session:
                        session.run("""
                            MATCH (w:World {id: $world_id})
                            MERGE (r:Region {id: $region_id})
                            ON CREATE SET r.name = $region_name, r.type = $region_type
                            MERGE (r)-[:IN_WORLD]->(w)
                        """, world_id=world_id, region_id=region_id,
                           region_name=region_doc['region_name'],
                           region_type=region_doc['region_type'])

                    # Create location nodes in Neo4j
                    for location_id in location_ids:
                        location = db.location_definitions.find_one({'_id': location_id})
                        if location:
                            with neo4j_driver.session() as session:
                                session.run("""
                                    MATCH (r:Region {id: $region_id})
                                    MERGE (l:Location {id: $location_id})
                                    ON CREATE SET l.name = $location_name, l.type = $location_type
                                    MERGE (l)-[:IN_REGION]->(r)
                                """, region_id=region_id, location_id=location_id,
                                   location_name=location['location_name'],
                                   location_type=location['location_type'])

                return JsonResponse({
                    'success': True,
                    'regions_created': regions_created,
                    'locations_created': locations_created,
                    'tokens_used': result.get('tokens_used', 0),
                    'cost_usd': result.get('cost_usd', 0)
                })
            else:
                return JsonResponse({'error': f'Orchestrator error: {response.text}'}, status=response.status_code)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate regions: {str(e)}'}, status=500)


class RegionGenerateLocationsView(View):
    """Generate multiple locations for a region using AI"""

    def post(self, request, world_id, region_id):
        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        if not world or not region:
            return JsonResponse({'error': 'World or region not found'}, status=404)

        try:
            data = json.loads(request.body)
            num_locations = data.get('num_locations', 3)

            # Validate input
            if not isinstance(num_locations, int) or num_locations < 1 or num_locations > 10:
                return JsonResponse({'error': 'num_locations must be between 1 and 10'}, status=400)

            # Prepare context
            context = {
                'world_name': world.get('world_name'),
                'world_genre': world.get('genre'),
                'world_backstory': world.get('backstory', ''),
                'region_name': region.get('region_name'),
                'region_type': region.get('region_type'),
                'climate': region.get('climate'),
                'terrain': region.get('terrain', []),
                'region_description': region.get('description', ''),
                'region_backstory': region.get('backstory', ''),
                'num_locations': num_locations
            }

            # Call orchestrator to generate locations
            orchestrator_url = f'{ORCHESTRATOR_URL}/api/generate-locations'
            response = requests.post(
                orchestrator_url,
                json=context,
                timeout=180  # 3 minute timeout
            )

            if response.status_code == 200:
                result = response.json()
                locations_data = result.get('locations', [])

                locations_created = 0

                # Create each location
                for location_data in locations_data:
                    location_id = str(uuid.uuid4())
                    location_doc = {
                        '_id': location_id,
                        'location_name': location_data.get('location_name'),
                        'location_type': location_data.get('location_type'),
                        'description': location_data.get('description', ''),
                        'features': location_data.get('features', []),
                        'backstory': location_data.get('backstory', ''),
                        'region_id': region_id,
                        'world_id': world_id
                    }
                    db.location_definitions.insert_one(location_doc)
                    locations_created += 1

                    # Add location to region
                    db.region_definitions.update_one(
                        {'_id': region_id},
                        {'$push': {'locations': location_id}}
                    )

                    # Create location node in Neo4j
                    with neo4j_driver.session() as session:
                        session.run("""
                            MATCH (r:Region {id: $region_id})
                            MERGE (l:Location {id: $location_id})
                            ON CREATE SET l.name = $location_name, l.type = $location_type
                            MERGE (l)-[:IN_REGION]->(r)
                        """, region_id=region_id, location_id=location_id,
                           location_name=location_doc['location_name'],
                           location_type=location_doc['location_type'])

                return JsonResponse({
                    'success': True,
                    'locations_created': locations_created,
                    'tokens_used': result.get('tokens_used', 0),
                    'cost_usd': result.get('cost_usd', 0)
                })
            else:
                return JsonResponse({'error': f'Orchestrator error: {response.text}'}, status=response.status_code)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate locations: {str(e)}'}, status=500)
