"""
Views for Universe and World management
Uses MongoDB for definitions and Neo4j for relationships
"""
import uuid
import httpx
import requests
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import JsonResponse
from pymongo import MongoClient
from neo4j import GraphDatabase
import os
import json
from utils.rabbitmq import publish_entity_event


# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection (for READ operations only - writes go through RabbitMQ)
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

            # Extract nested fields for easier template access
            narrative_tone = universe.get('narrative_tone', {})
            universe['narrative_style'] = narrative_tone.get('style', '')
            universe['humor_level'] = narrative_tone.get('humor_level', '')

            vocab_style = universe.get('vocabulary_style', {})
            universe['reading_level'] = vocab_style.get('reading_level', '').replace('_', ' ').title()

            features = universe.get('features', {})
            universe['combat_enabled'] = features.get('combat_enabled', False)
            universe['romance_enabled'] = features.get('romance_enabled', False)

            # Get world count for this universe
            universe['world_count'] = db.world_definitions.count_documents({'universe_ids': universe['_id']})

            # Format purpose category
            if universe.get('purpose_category'):
                universe['purpose_display'] = universe['purpose_category'].replace('_', ' ').title()

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

        # Publish event to sync to Neo4j
        publish_entity_event('universe', 'created', universe_id, {
            'universe_name': universe_data['universe_name'],
            'max_content_rating': universe_data['max_content_rating']
        })

        messages.success(request, f'Universe "{universe_data["universe_name"]}" created successfully!')
        return redirect('universe_list')


class UniverseDetailView(View):
    """View universe details"""

    def get(self, request, universe_id):
        universe = db.universe_definitions.find_one({'_id': universe_id})
        worlds = list(db.world_definitions.find({'universe_ids': universe_id}))

        # Add world_id field for template (Django doesn't allow _id)
        for world in worlds:
            world['world_id'] = world['_id']

            # Get primary image URL
            world['primary_image_url'] = None
            if world.get('world_images') and world.get('primary_image_index') is not None:
                images = world.get('world_images', [])
                primary_idx = world.get('primary_image_index')
                if 0 <= primary_idx < len(images):
                    world['primary_image_url'] = images[primary_idx].get('url')

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

        # Enrich world data for template
        for world in worlds:
            world['world_id'] = world['_id']

            # Get universe data
            if world.get('universe_ids'):
                universe_id = world['universe_ids'][0]
                universe = db.universe_definitions.find_one({'_id': universe_id})
                if universe:
                    world['universe'] = universe

            # Get primary image URL
            world['primary_image_url'] = None
            if world.get('world_images') and world.get('primary_image_index') is not None:
                images = world.get('world_images', [])
                primary_idx = world.get('primary_image_index')
                if 0 <= primary_idx < len(images):
                    world['primary_image_url'] = images[primary_idx].get('url')

            # Get region count
            world['region_count'] = db.region_definitions.count_documents({'world_id': world['_id']})

        response = render(request, 'worlds/world_list.html', {'worlds': worlds})
        # Prevent browser caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


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
            'description': request.POST.get('description', ''),
            'universe_ids': universe_ids,
            'genre': request.POST.get('genre'),
            'themes': themes,
            'visual_style': visual_styles,
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

        # Publish event to sync to Neo4j
        publish_entity_event('world', 'created', world_id, {
            'universe_ids': universe_ids,
            'world_name': world_data['world_name'],
            'genre': world_data['genre']
        })

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
            regions_dict = {}
            if region_ids:
                regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))
                for r in regions:
                    r['region_id'] = r['_id']
                    regions_dict[r['_id']] = r

                    # Get primary image URL
                    r['primary_image_url'] = None
                    if r.get('region_images') and r.get('primary_image_index') is not None:
                        images = r.get('region_images', [])
                        primary_idx = r.get('primary_image_index')
                        if 0 <= primary_idx < len(images):
                            r['primary_image_url'] = images[primary_idx].get('url')

            # Get all species for this world
            species_ids = world.get('species', [])
            species = []
            if species_ids:
                species = list(db.species_definitions.find({'_id': {'$in': species_ids}}))
                for s in species:
                    s['species_id'] = s['_id']

                    # Get region names
                    s['region_names'] = []
                    if s.get('regions'):
                        for region_id in s['regions']:
                            if region_id in regions_dict:
                                s['region_names'].append(regions_dict[region_id].get('region_name', ''))

                    # Get primary image URL
                    s['primary_image_url'] = None
                    if s.get('species_images') and s.get('primary_image_index') is not None:
                        images = s.get('species_images', [])
                        primary_idx = s.get('primary_image_index')
                        if 0 <= primary_idx < len(images):
                            s['primary_image_url'] = images[primary_idx].get('url')
                    # Fallback to old species_image field
                    elif s.get('species_image'):
                        s['primary_image_url'] = s.get('species_image')

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
            'regions': regions,
            'species': species
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

        # Publish event to sync to Neo4j
        publish_entity_event('universe', 'updated', universe_id, {
            'universe_name': universe_data['universe_name'],
            'max_content_rating': universe_data['max_content_rating']
        })

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

        # Delete from MongoDB
        db.universe_definitions.delete_one({'_id': universe_id})

        # Publish event to sync deletion to Neo4j
        publish_entity_event('universe', 'deleted', universe_id, {})

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
            'description': {'value': world.get('description', '')},
            'universe_ids': {'value': universe_ids},
            'genre': {'value': world.get('genre', '')},
            'themes': {'value': themes},
            'visual_style': {'value': visual_styles},
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
            'description': request.POST.get('description', ''),
            'universe_ids': universe_ids,
            'genre': request.POST.get('genre'),
            'themes': themes,
            'visual_style': visual_styles,
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

        # Publish event to sync to Neo4j
        publish_entity_event('world', 'updated', world_id, {
            'universe_ids': universe_ids,
            'world_name': world_data['world_name'],
            'genre': world_data['genre']
        })

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

        # Delete from MongoDB
        db.world_definitions.delete_one({'_id': world_id})

        # Publish event to sync deletion to Neo4j
        publish_entity_event('world', 'deleted', world_id, {})

        messages.success(request, f'World "{world["world_name"]}" deleted successfully!')
        return redirect('world_list')


@method_decorator(csrf_exempt, name='dispatch')
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
                        'description': world.get('description', ''),
                        'genre': world.get('genre', ''),
                        'themes': world.get('themes', []),
                        'visual_style': world.get('visual_style', []),
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
                    backstory = result.get('backstory', '')
                    tokens_used = result.get('tokens_used', 0)
                    cost_usd = result.get('cost_usd', 0)

                    # Generate timeline after backstory is created
                    timeline = []
                    try:
                        timeline_response = client.post(
                            f"{ORCHESTRATOR_URL}/generate-timeline",
                            json={
                                'world_id': world_id,
                                'world_name': world.get('world_name', ''),
                                'genre': world.get('genre', ''),
                                'backstory': backstory,
                                'historical_properties': historical
                            },
                            timeout=60.0
                        )

                        if timeline_response.status_code == 200:
                            timeline_result = timeline_response.json()
                            timeline = timeline_result.get('timeline', [])
                            tokens_used += timeline_result.get('tokens_used', 0)
                            cost_usd += timeline_result.get('cost_usd', 0)
                    except Exception as timeline_error:
                        print(f"Timeline generation failed: {timeline_error}")
                        # Continue without timeline if it fails

                    return JsonResponse({
                        'success': True,
                        'backstory': backstory,
                        'timeline': timeline,
                        'tokens_used': tokens_used,
                        'cost_usd': cost_usd
                    })
                else:
                    return JsonResponse({'error': f'Agent error: {response.text}'}, status=response.status_code)

        except httpx.TimeoutException:
            return JsonResponse({'error': 'Request timed out'}, status=504)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate backstory: {str(e)}'}, status=500)


class WorldSaveBackstoryView(View):
    """Save the backstory and timeline to the world"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            import json
            backstory = request.POST.get('backstory', '')
            timeline_json = request.POST.get('timeline', '[]')

            # Parse timeline JSON
            try:
                timeline = json.loads(timeline_json)
            except:
                timeline = []

            # Save backstory and timeline to MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': {
                    'backstory': backstory,
                    'timeline': timeline
                }}
            )

            messages.success(request, 'Backstory and timeline saved successfully!')
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

            # Get primary image URL
            region['primary_image_url'] = None
            if region.get('region_images') and region.get('primary_image_index') is not None:
                images = region.get('region_images', [])
                primary_idx = region.get('primary_image_index')
                if 0 <= primary_idx < len(images):
                    region['primary_image_url'] = images[primary_idx].get('url')

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

        # Publish event to sync to Neo4j
        publish_entity_event('region', 'created', region_id, {
            'world_id': world_id,
            'region_name': region_data['region_name'],
            'region_type': region_data['region_type'],
            'climate': region_data.get('climate', '')
        })

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

        # Get world primary image URL
        world['primary_image_url'] = None
        if world.get('world_images') and world.get('primary_image_index') is not None:
            images = world.get('world_images', [])
            primary_idx = world.get('primary_image_index')
            if 0 <= primary_idx < len(images):
                world['primary_image_url'] = images[primary_idx].get('url')

        # Get region count for world
        world['region_count'] = db.region_definitions.count_documents({'world_id': world_id})

        # Get universe info for world
        if world.get('universe_id'):
            universe = db.universe_definitions.find_one({'_id': world.get('universe_id')})
            world['universe'] = universe

        # Get all locations for this region (top-level only for tree)
        location_ids = region.get('locations', [])
        locations = list(db.location_definitions.find({'_id': {'$in': location_ids}})) if location_ids else []
        for location in locations:
            location['location_id'] = location['_id']

            # Get primary image URL
            location['primary_image_url'] = None
            if location.get('location_images') and location.get('primary_image_index') is not None:
                images = location.get('location_images', [])
                primary_idx = location.get('primary_image_index')
                if 0 <= primary_idx < len(images):
                    location['primary_image_url'] = images[primary_idx].get('url')

        # Build hierarchical tree structure for location tree view
        def build_location_tree(location):
            """Recursively build location tree with children"""
            loc_data = {
                'id': location['_id'],
                'name': location.get('location_name'),
                'type': location.get('location_type'),
                'depth': location.get('depth', 1),
                'children': []
            }

            child_ids = location.get('child_locations', [])
            if child_ids:
                children = list(db.location_definitions.find({'_id': {'$in': child_ids}}))
                for child in children:
                    loc_data['children'].append(build_location_tree(child))

            return loc_data

        location_tree = [build_location_tree(loc) for loc in locations]

        return render(request, 'worlds/region_detail.html', {
            'world': world,
            'region': region,
            'locations': locations,
            'location_tree': location_tree
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

        # Publish event to sync deletion to Neo4j
        publish_entity_event('region', 'deleted', region_id, {})

        messages.success(request, f'Region "{region_name}" deleted successfully!')
        return redirect('region_list', world_id=world_id)


@method_decorator(csrf_exempt, name='dispatch')
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

        # Get all locations in this region for parent selection
        all_locations = list(db.location_definitions.find({'region_id': region_id}))
        for loc in all_locations:
            loc['location_id'] = loc['_id']

        # Check if creating child location (parent_location_id in query params)
        parent_location_id = request.GET.get('parent_location_id')
        parent_location = None
        location_depth = 1  # Default: Primary
        if parent_location_id:
            parent_location = db.location_definitions.find_one({'_id': parent_location_id})
            if parent_location:
                parent_location['location_id'] = parent_location['_id']
                location_depth = parent_location.get('depth', 1) + 1

        form_data = {
            'location_name': {'value': ''},
            'location_type': {'value': ''},
            'description': {'value': ''},
            'features': {'value': []}
        }

        return render(request, 'worlds/location_form.html', {
            'world': world,
            'region': region,
            'form': form_data,
            'all_locations': all_locations,
            'parent_location_id': parent_location_id,
            'parent_location': parent_location,
            'location_depth': location_depth
        })

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            messages.error(request, 'Region not found')
            return redirect('world_list')

        location_id = str(uuid.uuid4())
        features = request.POST.getlist('features')
        parent_location_id = request.POST.get('parent_location_id', None)

        # Calculate depth based on parent
        depth = 1  # Default: Primary location
        if parent_location_id:
            parent = db.location_definitions.find_one({'_id': parent_location_id})
            if parent:
                depth = parent.get('depth', 1) + 1
                # Enforce max depth of 3
                if depth > 3:
                    messages.error(request, 'Maximum location depth of 3 levels reached')
                    return redirect('location_detail', world_id=world_id, region_id=region_id, location_id=parent_location_id)

        location_data = {
            '_id': location_id,
            'location_name': request.POST.get('location_name'),
            'location_type': request.POST.get('location_type'),
            'description': request.POST.get('description', ''),
            'features': features,
            'region_id': region_id,
            'world_id': world_id,
            'parent_location_id': parent_location_id,
            'child_locations': [],
            'depth': depth
        }

        # Store in MongoDB
        db.location_definitions.insert_one(location_data)

        # Update parent location's child_locations array if this is a child location
        parent_location_id = location_data.get('parent_location_id')
        if parent_location_id:
            db.location_definitions.update_one(
                {'_id': parent_location_id},
                {'$push': {'child_locations': location_id}}
            )

        # Update region's locations array (only add top-level locations)
        if not parent_location_id:
            db.region_definitions.update_one(
                {'_id': region_id},
                {'$push': {'locations': location_id}}
            )

        # Publish event to sync to Neo4j
        publish_entity_event('location', 'created', location_id, {
            'region_id': region_id,
            'parent_location_id': parent_location_id,
            'location_name': location_data['location_name'],
            'location_type': location_data['location_type']
        })

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

        # Get region primary image URL
        region['primary_image_url'] = None
        if region.get('region_images') and region.get('primary_image_index') is not None:
            images = region.get('region_images', [])
            primary_idx = region.get('primary_image_index')
            if 0 <= primary_idx < len(images):
                region['primary_image_url'] = images[primary_idx].get('url')

        # Get location count for region
        region['location_count'] = len(region.get('locations', []))

        # Load child locations if any
        child_location_ids = location.get('child_locations', [])
        child_locations = []
        if child_location_ids:
            child_locations = list(db.location_definitions.find({'_id': {'$in': child_location_ids}}))
            for child in child_locations:
                child['location_id'] = child['_id']

        # Load parent location if any
        parent_location = None
        parent_location_id = location.get('parent_location_id')
        if parent_location_id:
            parent_location = db.location_definitions.find_one({'_id': parent_location_id})
            if parent_location:
                parent_location['location_id'] = parent_location['_id']

        return render(request, 'worlds/location_detail.html', {
            'world': world,
            'region': region,
            'location': location,
            'child_locations': child_locations,
            'parent_location': parent_location
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

        # Count all child locations recursively
        def count_children(loc_id):
            loc = db.location_definitions.find_one({'_id': loc_id})
            if not loc:
                return 0
            count = 0
            child_ids = loc.get('child_locations', [])
            for child_id in child_ids:
                count += 1 + count_children(child_id)
            return count

        child_count = count_children(location_id)

        return render(request, 'worlds/location_confirm_delete.html', {
            'world': world,
            'region': region,
            'location': location,
            'child_count': child_count
        })

    def post(self, request, world_id, region_id, location_id):
        # Get the location to check for children
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            messages.error(request, 'Location not found')
            return redirect('region_detail', world_id=world_id, region_id=region_id)

        # Recursive function to delete location and all its children
        def delete_location_recursively(loc_id):
            """Delete a location and all its children recursively"""
            loc = db.location_definitions.find_one({'_id': loc_id})
            if not loc:
                return 0

            deleted_count = 0

            # First, recursively delete all children
            child_ids = loc.get('child_locations', [])
            for child_id in child_ids:
                deleted_count += delete_location_recursively(child_id)

            # Remove from parent's child_locations array if has parent
            parent_id = loc.get('parent_location_id')
            if parent_id:
                db.location_definitions.update_one(
                    {'_id': parent_id},
                    {'$pull': {'child_locations': loc_id}}
                )

            # Delete the location from MongoDB
            db.location_definitions.delete_one({'_id': loc_id})

            # Publish event to sync deletion to Neo4j
            publish_entity_event('location', 'deleted', loc_id, {})

            return deleted_count + 1

        # Remove from region's locations array (only if top-level)
        if not location.get('parent_location_id'):
            db.region_definitions.update_one(
                {'_id': region_id},
                {'$pull': {'locations': location_id}}
            )

        # Delete this location and all children recursively
        total_deleted = delete_location_recursively(location_id)

        if total_deleted > 1:
            messages.success(request, f'Location and {total_deleted - 1} child location(s) deleted successfully!')
        else:
            messages.success(request, 'Location deleted successfully!')

        return redirect('region_detail', world_id=world_id, region_id=region_id)


@method_decorator(csrf_exempt, name='dispatch')
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


@method_decorator(csrf_exempt, name='dispatch')
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
                'description': world.get('description', ''),
                'genre': world.get('genre'),
                'themes': world.get('themes', []),
                'visual_style': world.get('visual_style', []),
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


@method_decorator(csrf_exempt, name='dispatch')
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

@method_decorator(csrf_exempt, name='dispatch')
class WorldGenerateImageView(View):
    """Generate AI images for a world using DALL-E 3 API"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            # Get current image count to determine how many to generate
            current_images = world.get('world_images', [])
            images_to_generate = 1 - len(current_images)

            if images_to_generate <= 0:
                return JsonResponse({'error': 'Already have 1 image. Delete it first.'}, status=400)

            # Get regions and locations for richer context
            regions = list(db.region_definitions.find({'world_id': world_id}))
            region_summary = []
            for region in regions[:5]:  # Limit to top 5 regions for prompt
                locations = list(db.location_definitions.find({'region_id': region['_id']}).limit(2))
                region_info = f"{region.get('region_name')} ({region.get('region_type')})"
                if locations:
                    loc_names = ', '.join([loc.get('location_name', '') for loc in locations])
                    region_info += f' with {loc_names}'
                region_summary.append(region_info)

            # Build comprehensive image prompt base
            physical = world.get('physical_properties', {})
            biological = world.get('biological_properties', {})
            visual_styles = ', '.join(world.get('visual_style', []))
            themes = ', '.join(world.get('themes', []))

            # Use OpenAI DALL-E 3 for image generation
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            # Define 1 image type: Full Planet View
            description = world.get('description', '')
            image_types = [
                {
                    'type': 'full_planet',
                    'name': 'Full Planet View',
                    'prompt_template': f"""Create a cinematic full planet view of the fantasy world: {world.get('world_name')}

{f"World Description: {description}" if description else ""}

Show the entire planet from space with:
- Visible continents and oceans
- Cloud formations
- Terrain: {', '.join(physical.get('terrain', [])[:3])}
- Climate patterns: {physical.get('climate', 'Varied')}
- Any moons in orbit
- Atmospheric effects

Genre: {world.get('genre')}
Visual Style: {visual_styles if visual_styles else 'Epic high-fantasy'}

Art Direction: Full planetary view from space, highly detailed, professional space illustration, dramatic lighting, epic scale"""
                }
            ]

            # Determine which images to generate based on what's missing
            new_images = []
            existing_types = [img.get('image_type') for img in current_images]

            for i in range(images_to_generate):
                # Find the first missing image type
                image_type_config = None
                for img_type in image_types:
                    if img_type['type'] not in existing_types:
                        image_type_config = img_type
                        existing_types.append(img_type['type'])  # Mark as being generated
                        break

                if not image_type_config:
                    # All types exist, shouldn't happen but fallback to first type
                    image_type_config = image_types[0]

                dalle_prompt = f"{image_type_config['prompt_template']}. IMPORTANT: No text, letters, words, or symbols of any kind in the image."

                # Generate image with DALL-E 3
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=dalle_prompt[:4000],
                    size="1792x1024",
                    quality="standard",
                    n=1,
                )

                # Download and save image locally
                dalle_url = response.data[0].url

                # Create directory structure: media/worlds/[world_id]/
                world_media_dir = Path(settings.MEDIA_ROOT) / 'worlds' / world_id
                world_media_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique filename
                import uuid
                filename = f"{uuid.uuid4()}.png"
                filepath = world_media_dir / filename

                # Download image from DALL-E URL
                urllib.request.urlretrieve(dalle_url, filepath)

                # Store relative path for URL generation
                relative_path = f"worlds/{world_id}/{filename}"
                local_url = f"{settings.MEDIA_URL}{relative_path}"

                new_images.append({
                    'url': local_url,
                    'prompt': dalle_prompt[:500],
                    'image_type': image_type_config['type'],
                    'image_name': image_type_config['name'],
                    'filepath': str(filepath)
                })

            # Add new images to existing array
            all_images = current_images + new_images

            # Set Full Planet as primary by default if it was just generated and no primary exists
            update_data = {'world_images': all_images}
            if world.get('primary_image_index') is None:
                # Find the full_planet image index
                for idx, img in enumerate(all_images):
                    if img.get('image_type') == 'full_planet':
                        update_data['primary_image_index'] = idx
                        break

            # Save images array to MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': update_data}
            )

            return JsonResponse({
                'success': True,
                'images': new_images,
                'total_count': len(all_images)
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to generate images: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldDeleteImageView(View):
    """Delete a specific world image by index"""

    def post(self, request, world_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            world = db.world_definitions.find_one({'_id': world_id})
            if not world:
                return JsonResponse({'error': 'World not found'}, status=404)

            current_images = world.get('world_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            # Remove image at index
            current_images.pop(image_index)

            # Adjust primary_image_index if needed
            primary_index = world.get('primary_image_index')
            update_data = {'world_images': current_images}

            if primary_index is not None:
                if primary_index == image_index:
                    # Deleted the primary image, reset to None
                    update_data['primary_image_index'] = None
                elif primary_index > image_index:
                    # Primary image shifted down by 1
                    update_data['primary_image_index'] = primary_index - 1

            # Update MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': update_data}
            )

            return JsonResponse({
                'success': True,
                'remaining_count': len(current_images)
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete image: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldSetPrimaryImageView(View):
    """Set a specific world image as the primary image"""

    def post(self, request, world_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            world = db.world_definitions.find_one({'_id': world_id})
            if not world:
                return JsonResponse({'error': 'World not found'}, status=404)

            current_images = world.get('world_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            # Update MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': {'primary_image_index': image_index}}
            )

            return JsonResponse({
                'success': True,
                'primary_image_index': image_index
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to set primary image: {str(e)}'}, status=500)


# ============================================
# Region Image Generation Views
# ============================================

@method_decorator(csrf_exempt, name='dispatch')
class RegionGenerateImageView(View):
    """Generate AI images for a region using DALL-E 3 API"""

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            return JsonResponse({'error': 'Region not found'}, status=404)

        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            # Get current image count
            current_images = region.get('region_images', [])
            images_to_generate = 1 - len(current_images)

            if images_to_generate <= 0:
                return JsonResponse({'error': 'Already have 1 image. Delete it first.'}, status=400)

            # Get locations for context
            locations = list(db.location_definitions.find({'region_id': region_id}).limit(5))
            location_summary = [loc.get('location_name', '') for loc in locations]

            # Build comprehensive prompt
            physical = region.get('physical_properties', {})
            cultural = region.get('cultural_properties', {})
            themes = ', '.join(region.get('themes', []))

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            # Define 1 image type: Region View
            image_types = [
                {
                    'type': 'region_view',
                    'name': 'Region View',
                    'prompt_template': f"""Create a cinematic, wide panoramic vista of the fantasy RPG region: {region.get('region_name')}

World: {world.get('world_name')} - {world.get('genre', 'Fantasy')}
Region Type: {region.get('region_type', 'Fantasy region')}
Themes: {themes if themes else 'Adventure'}

Environment:
- Climate: {physical.get('climate', 'Varied')}
- Terrain: {', '.join(physical.get('terrain_types', [])[:3])}
- Natural Features: {', '.join(physical.get('natural_features', [])[:3])}

{f"Notable Locations: {', '.join(location_summary[:3])}" if location_summary else ''}

{region.get('description', '')[:150] if region.get('description') else ''}

Art Direction: Wide establishing shot showing the full scope of the region, highly detailed digital concept art, dramatic lighting, epic scale, professional fantasy illustration

IMPORTANT: No text, letters, words, or symbols of any kind in the image."""
                }
            ]

            # Determine which images to generate based on what's missing
            new_images = []
            existing_types = [img.get('image_type') for img in current_images]

            for i in range(images_to_generate):
                # Find the first missing image type
                image_type_config = None
                for img_type in image_types:
                    if img_type['type'] not in existing_types:
                        image_type_config = img_type
                        existing_types.append(img_type['type'])  # Mark as being generated
                        break

                if not image_type_config:
                    # All types exist, shouldn't happen but fallback to first type
                    image_type_config = image_types[0]

                dalle_prompt = image_type_config['prompt_template']

                response = client.images.generate(
                    model="dall-e-3",
                    prompt=dalle_prompt[:4000],
                    size="1792x1024",
                    quality="standard",
                    n=1,
                )

                # Download and save image locally
                dalle_url = response.data[0].url

                # Create directory structure: media/regions/[region_id]/
                region_media_dir = Path(settings.MEDIA_ROOT) / 'regions' / region_id
                region_media_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique filename
                import uuid
                filename = f"{uuid.uuid4()}.png"
                filepath = region_media_dir / filename

                # Download image from DALL-E URL
                urllib.request.urlretrieve(dalle_url, filepath)

                # Store relative path for URL generation
                relative_path = f"regions/{region_id}/{filename}"
                local_url = f"{settings.MEDIA_URL}{relative_path}"

                new_images.append({
                    'url': local_url,
                    'prompt': dalle_prompt[:500],
                    'image_type': image_type_config['type'],
                    'image_name': image_type_config['name'],
                    'filepath': str(filepath)
                })

            all_images = current_images + new_images

            # Set Far Away as primary by default if it was just generated and no primary exists
            update_data = {'region_images': all_images}
            if region.get('primary_image_index') is None:
                # Find the far_away image index
                for idx, img in enumerate(all_images):
                    if img.get('image_type') == 'far_away':
                        update_data['primary_image_index'] = idx
                        break

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': update_data}
            )

            return JsonResponse({
                'success': True,
                'images': new_images,
                'total_count': len(all_images)
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to generate images: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RegionDeleteImageView(View):
    """Delete a specific region image by index"""

    def post(self, request, world_id, region_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            region = db.region_definitions.find_one({'_id': region_id})
            if not region:
                return JsonResponse({'error': 'Region not found'}, status=404)

            current_images = region.get('region_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            current_images.pop(image_index)

            # Adjust primary_image_index if needed
            primary_index = region.get('primary_image_index')
            update_data = {'region_images': current_images}

            if primary_index is not None:
                if primary_index == image_index:
                    update_data['primary_image_index'] = None
                elif primary_index > image_index:
                    update_data['primary_image_index'] = primary_index - 1

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': update_data}
            )

            return JsonResponse({
                'success': True,
                'remaining_count': len(current_images)
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete image: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RegionSetPrimaryImageView(View):
    """Set a specific region image as the primary image"""

    def post(self, request, world_id, region_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            region = db.region_definitions.find_one({'_id': region_id})
            if not region:
                return JsonResponse({'error': 'Region not found'}, status=404)

            current_images = region.get('region_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': {'primary_image_index': image_index}}
            )

            return JsonResponse({
                'success': True,
                'primary_image_index': image_index
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to set primary image: {str(e)}'}, status=500)


class WorldTextToSpeechView(View):
    """Generate TTS audio for world backstory using ElevenLabs"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({
                'success': False,
                'error': 'World not found'
            }, status=404)

        try:
            from elevenlabs import ElevenLabs
            from django.http import HttpResponse

            elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
            if not elevenlabs_api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'ElevenLabs API key not configured'
                }, status=500)

            backstory = world.get('backstory', '')
            if not backstory:
                return JsonResponse({
                    'success': False,
                    'error': 'No backstory to read'
                }, status=400)

            client = ElevenLabs(api_key=elevenlabs_api_key)

            # Use Old British Male voice for world backstories
            voice_id = "iOVaF08dLdP3q4lSrs5M"

            # Generate audio
            audio_generator = client.text_to_speech.convert(
                text=backstory,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )

            # Stream audio as response
            audio_data = b''.join(audio_generator)

            response = HttpResponse(audio_data, content_type='audio/mpeg')
            response['Content-Disposition'] = f'inline; filename="world_{world_id}_backstory.mp3"'
            return response

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error generating audio: {str(e)}'
            }, status=500)


class RegionTextToSpeechView(View):
    """Generate TTS audio for region backstory using ElevenLabs"""

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            return JsonResponse({
                'success': False,
                'error': 'Region not found'
            }, status=404)

        try:
            from elevenlabs import ElevenLabs
            from django.http import HttpResponse

            elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
            if not elevenlabs_api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'ElevenLabs API key not configured'
                }, status=500)

            backstory = region.get('backstory', '')
            if not backstory:
                return JsonResponse({
                    'success': False,
                    'error': 'No backstory to read'
                }, status=400)

            client = ElevenLabs(api_key=elevenlabs_api_key)

            # Use Old British Male voice for region backstories
            voice_id = "iOVaF08dLdP3q4lSrs5M"

            # Generate audio
            audio_generator = client.text_to_speech.convert(
                text=backstory,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )

            # Stream audio as response
            audio_data = b''.join(audio_generator)

            response = HttpResponse(audio_data, content_type='audio/mpeg')
            response['Content-Disposition'] = f'inline; filename="region_{region_id}_backstory.mp3"'
            return response

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error generating audio: {str(e)}'
            }, status=500)


class LocationTextToSpeechView(View):
    """Generate TTS audio for location backstory using ElevenLabs"""

    def post(self, request, world_id, region_id, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            return JsonResponse({
                'success': False,
                'error': 'Location not found'
            }, status=404)

        try:
            from elevenlabs import ElevenLabs
            from django.http import HttpResponse

            elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
            if not elevenlabs_api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'ElevenLabs API key not configured'
                }, status=500)

            backstory = location.get('backstory', '')
            if not backstory:
                return JsonResponse({
                    'success': False,
                    'error': 'No backstory to read'
                }, status=400)

            client = ElevenLabs(api_key=elevenlabs_api_key)

            # Use Old British Male voice for location backstories
            voice_id = "iOVaF08dLdP3q4lSrs5M"

            # Generate audio
            audio_generator = client.text_to_speech.convert(
                text=backstory,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )

            # Stream audio as response
            audio_data = b''.join(audio_generator)

            response = HttpResponse(audio_data, content_type='audio/mpeg')
            response['Content-Disposition'] = f'inline; filename="location_{location_id}_backstory.mp3"'
            return response

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error generating audio: {str(e)}'
            }, status=500)


# Import Location Image Views
from .views_locations import LocationGenerateImageView, LocationDeleteImageView, LocationSetPrimaryImageView
