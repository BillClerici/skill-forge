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

        # Calculate location depth for determining available location types
        location_depth = 1  # Default to level 1
        if location.get('parent_location_id'):
            # This location has a parent, so check parent's depth
            parent = db.location_definitions.find_one({'_id': location['parent_location_id']})
            if parent:
                if parent.get('parent_location_id'):
                    location_depth = 3  # Parent has a parent, so this is level 3
                else:
                    location_depth = 2  # Parent is top-level, so this is level 2

        # Get all locations in this region for parent selection
        all_locations = list(db.location_definitions.find({'region_id': region_id}))
        for loc in all_locations:
            loc['location_id'] = loc['_id']

        return render(request, 'worlds/location_form.html', {
            'world': world,
            'region': region,
            'location': location,
            'location_depth': location_depth,
            'all_locations': all_locations,
            'parent_location_id': location.get('parent_location_id')
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
            # Get current image count
            # Admin pages can have up to 3 images (plus 1 map), but generate 1 at a time
            current_images = world.get('world_images', [])

            if len(current_images) >= 3:
                return JsonResponse({'error': 'Already have 3 images. Delete some first to generate more.'}, status=400)

            # Generate only 1 image at a time
            images_to_generate = 1

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

            # Define 4 image types for different perspectives
            description = world.get('description', '')

            # Strong anti-text prefix for ALL prompts
            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            # Strong anti-text suffix for ALL prompts
            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO book text, scrolls with writing, or inscriptions
- NO UI elements, watermarks, or captions
- Pure visual imagery only - if it looks like text, don't include it
This is mandatory and non-negotiable."""

            image_types = [
                {
                    'type': 'full_planet',
                    'name': 'Full Planet View',
                    'prompt_template': f"""{no_text_prefix}Create a cinematic full planet view of the fantasy world: {world.get('world_name')}

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

Art Direction: Full planetary view from space, highly detailed, professional space illustration, dramatic lighting, epic scale{no_text_suffix}"""
                },
                {
                    'type': 'landscape',
                    'name': 'Iconic Landscape',
                    'prompt_template': f"""{no_text_prefix}Create an epic landscape view of {world.get('world_name')}

{f"World Description: {description}" if description else ""}

Show a sweeping landscape featuring:
- {', '.join(physical.get('terrain', ['mountains', 'valleys'])[:2])}
- {physical.get('climate', 'Varied climate')} atmosphere
- {', '.join(biological.get('flora', ['exotic vegetation'])[:2])}
- Dramatic sky and lighting
{f"- Regions: {', '.join(region_summary[:2])}" if region_summary else ""}

Genre: {world.get('genre')}
Visual Style: {visual_styles if visual_styles else 'Epic high-fantasy'}
Themes: {themes if themes else 'Adventure and wonder'}

Art Direction: Wide cinematic landscape, epic scale, highly detailed, dramatic atmosphere, professional concept art{no_text_suffix}"""
                },
                {
                    'type': 'settlement',
                    'name': 'Major Settlement',
                    'prompt_template': f"""{no_text_prefix}Create a detailed view of a major settlement or city in {world.get('world_name')}

{f"World Description: {description}" if description else ""}

Show an impressive settlement with:
- Architecture reflecting the world's culture and technology
- {', '.join(world.get('societal_properties', {}).get('culture_traditions', ['unique cultural elements'])[:2])}
- Inhabitants going about their lives
- {world.get('technological_properties', {}).get('technology_level', 'Medieval technology')}
- Surrounding environment integration

Genre: {world.get('genre')}
Visual Style: {visual_styles if visual_styles else 'Epic high-fantasy'}

Art Direction: Detailed settlement view, bustling with life, architectural detail, cinematic composition, professional concept art{no_text_suffix}"""
                },
                {
                    'type': 'atmospheric',
                    'name': 'Atmospheric Scene',
                    'prompt_template': f"""{no_text_prefix}Create an atmospheric, mood-setting scene from {world.get('world_name')}

{f"World Description: {description}" if description else ""}

Capture the world's essence with:
- Dramatic lighting and weather effects
- Mysterious or awe-inspiring environment
- {', '.join(biological.get('fauna', ['unique creatures'])[:2])} presence
- Environmental storytelling elements
- Sense of scale and wonder

Genre: {world.get('genre')}
Visual Style: {visual_styles if visual_styles else 'Epic high-fantasy'}
Themes: {themes if themes else 'Mystery and discovery'}

Art Direction: Cinematic atmosphere, dramatic mood, evocative lighting, professional concept art, epic fantasy illustration{no_text_suffix}"""
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
# World Map Generation Views
# ============================================

@method_decorator(csrf_exempt, name='dispatch')
class WorldGenerateMapView(View):
    """Generate a cartographic map for a world using DALL-E 3 API"""

    def get_genre_map_style(self, genre):
        """Return map styling instructions based on genre - PLAIN TERRAIN ONLY"""
        genre_styles = {
            'Fantasy': {
                'style_name': 'medieval_fantasy',
                'description': 'Natural terrain view with slightly muted, earthy colors',
                'technical': 'Top-down terrain view, natural landscape, realistic geography'
            },
            'Western': {
                'style_name': 'western_1800s',
                'description': 'Natural terrain with warm, desert-influenced color palette',
                'technical': 'Aerial terrain view, natural landscape photography'
            },
            'Sci-Fi': {
                'style_name': 'sci_fi_holographic',
                'description': 'Clean terrain view with slightly cooler tones',
                'technical': 'Satellite imagery, clean terrain mapping, technical perspective'
            },
            'Post-Apocalyptic': {
                'style_name': 'post_apocalyptic',
                'description': 'Natural terrain with muted, desaturated colors',
                'technical': 'Aerial terrain photography, natural geography'
            },
            'Steampunk': {
                'style_name': 'steampunk_victorian',
                'description': 'Natural terrain with sepia-toned color palette',
                'technical': 'Vintage aerial photography, natural landscape'
            },
            'Cyberpunk': {
                'style_name': 'cyberpunk_neon',
                'description': 'Natural terrain with high contrast and darker tones',
                'technical': 'Satellite terrain view, high-contrast mapping'
            },
            'Historical': {
                'style_name': 'historical_authentic',
                'description': 'Natural terrain with aged, historical color tones',
                'technical': 'Period-appropriate aerial terrain view'
            }
        }

        # Default to Fantasy if genre not found
        return genre_styles.get(genre, genre_styles['Fantasy'])

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            # Check if regenerating (replace existing) or generating new
            regenerate = json.loads(request.body).get('regenerate', False) if request.body else False

            # Get genre-specific map style
            genre = world.get('genre', 'Fantasy')
            map_style = self.get_genre_map_style(genre)

            # Get regions for the map with full details
            regions = list(db.region_definitions.find({'world_id': world_id}))
            region_descriptions = []
            for region in regions[:15]:  # Get more regions for better context
                region_desc = f"{region.get('region_name')} - {region.get('region_type', 'region')}"
                details = []
                if region.get('climate'):
                    details.append(f"{region.get('climate')} climate")
                if region.get('terrain'):
                    details.append(f"{region.get('terrain')} terrain")
                if region.get('description'):
                    # Add first 100 chars of description for context
                    details.append(region.get('description')[:100])
                if details:
                    region_desc += f": {', '.join(details)}"
                region_descriptions.append(region_desc)

            # Extract all world properties for comprehensive map generation
            physical = world.get('physical_properties', {})
            biological = world.get('biological_properties', {})
            technological = world.get('technological_properties', {})
            societal = world.get('societal_properties', {})

            world_name = world.get('world_name', 'Unknown World')
            description = world.get('description', '')
            backstory = world.get('backstory', '')
            visual_style = world.get('visual_style', [])
            themes = world.get('themes', [])

            # Core map requirements - TERRAIN ONLY BACKGROUND
            terrain_only_requirement = """
ABSOLUTE CRITICAL REQUIREMENTS - READ CAREFULLY:

THIS IS A TERRAIN BACKGROUND IMAGE ONLY - NOT A MAP WITH DECORATIONS!

STRICTLY FORBIDDEN - DO NOT INCLUDE:
❌ NO text of any kind (English, symbols, runes, fictional languages, etc.)
❌ NO letters, numbers, characters, glyphs, or writing systems
❌ NO compass roses (neither with nor without letters)
❌ NO decorative borders or frames with any markings
❌ NO legends, keys, or explanatory boxes
❌ NO banners, scrolls, ribbons, or cartouches
❌ NO title blocks or name plates
❌ NO scale bars with markings
❌ NO location markers, pins, or numbered circles
❌ NO arrows, pointers, or directional indicators
❌ NO emblems, crests, or heraldic symbols
❌ NO decorative flourishes that look like text
❌ NO anything that resembles writing, even stylized
❌ NO map borders with decorative elements

WHAT TO INCLUDE - TERRAIN ONLY:
✓ Mountains, hills, and elevation changes
✓ Forests, jungles, and vegetation
✓ Deserts, plains, and barren areas
✓ Water bodies: oceans, seas, rivers, lakes
✓ Natural landmasses and continents
✓ Coastlines and shorelines
✓ Natural terrain colors and textures
✓ Realistic geographic features
✓ Elevation shading and depth

STYLE: Think NASA satellite imagery, Google Earth view, or aerial photography
- Pure, clean, UNMARKED terrain surface
- No human-made decorative elements
- Just the raw, natural geography
- This is the BASE LAYER that will have clean markers added programmatically
"""

            # Build rich contextual information from backstory and description
            world_context = description
            if backstory:
                # Extract first 500 chars of backstory for additional context
                backstory_excerpt = backstory[:500].strip()
                if backstory_excerpt and backstory_excerpt != description:
                    world_context = f"{description}\n\nKey History: {backstory_excerpt}"

            # Build detailed prompt with all world properties
            map_prompt = f"""{terrain_only_requirement}

Create a detailed, immersive cartographic map of the world: {world_name}

=== WORLD CONTEXT ===
{world_context if world_context else 'A rich and detailed world awaiting exploration'}

=== VISUAL STYLE & THEMES ===
Genre: {genre}
Visual Style: {', '.join(visual_style) if visual_style else 'Epic and detailed'}
Themes: {', '.join(themes) if themes else 'Adventure and exploration'}
Map Style: {map_style['description']}

=== PHYSICAL GEOGRAPHY (CRITICAL - DEPICT ACCURATELY) ===
Terrain Features: {', '.join(physical.get('terrain', ['diverse landscapes']))}
Climate: {physical.get('climate', 'Varied climates across regions')}
Planet Type: {physical.get('planet_type', 'Earth-like')}
Size: {physical.get('size', 'Standard planetary scale')}
{f"Gravity: {physical.get('gravity')}" if physical.get('gravity') else ""}
{f"Atmosphere: {physical.get('atmosphere')}" if physical.get('atmosphere') else ""}
{f"Water Coverage: {physical.get('water_coverage')}" if physical.get('water_coverage') else ""}

Bodies of Water: Show oceans, seas, major rivers, and lakes appropriate to the climate and terrain
Mountain Ranges: Depict using symbolic mountain icons based on terrain data
Volcanic/Seismic Activity: {f"Include volcanic regions - {physical.get('volcanic_activity')}" if physical.get('volcanic_activity') else "Standard geological features"}

=== BIOLOGICAL FEATURES ===
{f"Flora: Visually represent regions with {', '.join(biological.get('flora', [])[:5])}" if biological.get('flora') else "Vegetation appropriate to climate zones"}
{f"Fauna: Consider ecosystems supporting {', '.join(biological.get('fauna', [])[:5])}" if biological.get('fauna') else "Standard biomes and ecosystems"}
{f"Dominant Species: {', '.join(biological.get('dominant_species', []))}" if biological.get('dominant_species') else ""}

=== CIVILIZATION & SETTLEMENTS ===
Technology Level: {technological.get('technology_level', 'Varied development')}
{f"Transportation: {technological.get('transportation')} - show appropriate trade routes and pathways" if technological.get('transportation') else ""}
{f"Architecture Style: {technological.get('architecture')} - settlements should reflect this" if technological.get('architecture') else ""}
{f"Population Distribution: {societal.get('population_distribution')}" if societal.get('population_distribution') else ""}
{f"Major Governments: {', '.join(societal.get('government_type', []))[:100]}" if societal.get('government_type') else ""}

=== GEOGRAPHIC REGIONS TO REPRESENT ===
{f"This world contains {len(region_descriptions)} distinct geographic regions with varied terrain:" if region_descriptions else "Show diverse geographic variations across the world"}

{chr(10).join([f"Area {i+1}: {r}" for i, r in enumerate(region_descriptions)]) if region_descriptions else ""}

TERRAIN RENDERING REQUIREMENTS:
• Show natural geographic variation across the world
• Each region should have geographically distinct terrain matching its description
• Use natural features to differentiate areas: mountains, forests, deserts, water, vegetation
• Terrain should flow naturally with realistic geographic transitions
• Show major landmasses, continents, islands
• Depict water bodies: oceans, seas, major rivers, lakes
• Mountain ranges: Use realistic mountain textures and elevation
• Forests: Dense tree coverage in appropriate regions
• Deserts: Sandy/rocky barren areas
• Climate zones visible through terrain coloring and vegetation
• Natural boundaries: Use geographic features (mountain ranges, rivers) to separate regions
• Realistic biome distribution based on latitude and climate

TECHNICAL REQUIREMENTS:
- {map_style['technical']}
- Top-down cartographic perspective showing full world geography
- Professional quality with rich detail
- Clear visual hierarchy (major features prominent, details subtle)
- Balanced composition with good use of space
- Appropriate aging/weathering effects for the chosen style
- Colors and styling should evoke the world's themes and atmosphere

FINAL RENDERING INSTRUCTIONS:
Create a beautiful, realistic TERRAIN-ONLY view that looks like:
- A NASA satellite photograph of the planet's surface
- Google Earth / Google Maps terrain view (satellite mode)
- An aerial photograph taken from space showing pure geography

IMAGE MUST BE:
✓ Completely clean and unmarked
✓ Natural terrain colors and realistic textures
✓ Geographic features clearly visible through terrain variation
✓ Professional quality with proper shading and depth
✓ {map_style['technical']} (style only - NO text elements from this style)
✓ Top-down view showing the full world geography

IMAGE MUST NOT HAVE:
❌ Any text, letters, symbols, or markings whatsoever
❌ Decorative borders, frames, or ornamental elements
❌ Compass roses, legends, or map furniture
❌ ANYTHING except pure, natural terrain

Think: "What would this world look like from space?" - That's what you're creating.
"""

            # Use OpenAI DALL-E 3 for map generation
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings
            from datetime import datetime

            client = OpenAI(api_key=openai_api_key)

            # Generate map with DALL-E 3
            response = client.images.generate(
                model="dall-e-3",
                prompt=map_prompt[:4000],  # DALL-E has prompt limits
                size="1792x1024",  # Landscape orientation for maps
                quality="hd",  # Use HD quality for maps
                n=1,
            )

            # Download and save map locally
            dalle_url = response.data[0].url

            # Create directory structure: media/worlds/[world_id]/maps/
            world_maps_dir = Path(settings.MEDIA_ROOT) / 'worlds' / world_id / 'maps'
            world_maps_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            filename = f"map_{uuid.uuid4()}.png"
            filepath = world_maps_dir / filename

            # Download map from DALL-E URL
            urllib.request.urlretrieve(dalle_url, filepath)

            # HYBRID APPROACH: Overlay clean markers on terrain background
            from PIL import Image, ImageDraw, ImageFont

            # Load the generated terrain image
            base_image = Image.open(filepath)

            # CROP BORDERS to remove fake text decorations (typically in outer 5-8%)
            img_width, img_height = base_image.size
            crop_percent = 0.06  # Remove 6% from each edge
            crop_left = int(img_width * crop_percent)
            crop_top = int(img_height * crop_percent)
            crop_right = int(img_width * (1 - crop_percent))
            crop_bottom = int(img_height * (1 - crop_percent))

            # Crop the image to remove decorative borders
            base_image = base_image.crop((crop_left, crop_top, crop_right, crop_bottom))

            # Save the clean terrain-only image (no markers)
            # Markers will be added interactively by the user via the Map Editor
            base_image.save(filepath, 'PNG', quality=95)

            # Store relative path for URL generation
            relative_path = f"worlds/{world_id}/maps/{filename}"
            local_url = f"{settings.MEDIA_URL}{relative_path}"

            # Prepare region legend data for the map
            # Auto-assign initial coordinates in a grid pattern for user to adjust in editor
            region_legend = []
            import math
            num_regions = min(len(regions), 15)
            cols = math.ceil(math.sqrt(num_regions))

            for i, region in enumerate(regions[:15]):
                # Format terrain and climate properly (handle arrays)
                terrain = region.get('terrain', '')
                if isinstance(terrain, list):
                    terrain = ', '.join(str(t) for t in terrain[:3])  # First 3 items
                elif not terrain:
                    terrain = ''

                climate = region.get('climate', '')
                if isinstance(climate, list):
                    climate = ', '.join(str(c) for c in climate[:2])  # First 2 items
                elif not climate:
                    climate = ''

                # Calculate initial grid position for this region
                row = i // cols
                col = i % cols
                x = (col + 0.5) / cols
                y = (row + 0.5) / math.ceil(num_regions / cols)

                # Clamp to safe bounds
                x = max(0.15, min(0.85, x))
                y = max(0.15, min(0.85, y))

                region_legend.append({
                    'number': i + 1,
                    'region_id': region['_id'],
                    'name': region.get('region_name', f'Region {i+1}'),
                    'type': region.get('region_type', 'region'),
                    'climate': climate,
                    'terrain': terrain,
                    'x': x,  # Initial position - user can adjust in Map Editor
                    'y': y   # Initial position - user can adjust in Map Editor
                })

            # Prepare map data with region legend
            map_data = {
                'url': local_url,
                'prompt': map_prompt[:500],
                'style': map_style['style_name'],
                'generated_at': datetime.utcnow(),
                'filepath': str(filepath),
                'region_legend': region_legend,
                'region_count': len(region_legend)
            }

            # Save map to MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$set': {'world_map': map_data}}
            )

            return JsonResponse({
                'success': True,
                'map': map_data,
                'regenerate': regenerate
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to generate map: {str(e)}'}, status=500)

    def assign_region_coordinates(self, world_id, regions):
        """Auto-assign coordinates to regions using a simple grid distribution"""
        import math

        if not regions:
            return

        # Simple grid distribution for initial placement
        num_regions = len(regions)
        cols = math.ceil(math.sqrt(num_regions))

        region_coords = {}
        for idx, region in enumerate(regions):
            row = idx // cols
            col = idx % cols

            # Spread regions across the map with some variation
            x = (col + 0.5) / cols + (hash(region['_id']) % 20 - 10) / 100
            y = (row + 0.5) / math.ceil(num_regions / cols) + (hash(region['_id'][::-1]) % 20 - 10) / 100

            # Clamp to valid range
            x = max(0.1, min(0.9, x))
            y = max(0.1, min(0.9, y))

            region_coords[region['_id']] = {
                'x': x,
                'y': y,
                'map_icon': self.get_region_icon(region.get('region_type', 'region'))
            }

        db.world_definitions.update_one(
            {'_id': world_id},
            {'$set': {'region_coordinates': region_coords}}
        )

    def get_region_icon(self, region_type):
        """Return appropriate icon type for region"""
        icon_map = {
            'kingdom': 'kingdom',
            'province': 'province',
            'territory': 'territory',
            'wilderness': 'wilderness',
            'mountains': 'mountains',
            'forest': 'forest',
            'desert': 'desert',
            'coast': 'coast',
            'island': 'island',
        }
        return icon_map.get(region_type.lower(), 'region')


@method_decorator(csrf_exempt, name='dispatch')
class WorldDeleteMapView(View):
    """Delete the world map"""

    def post(self, request, world_id):
        try:
            world = db.world_definitions.find_one({'_id': world_id})
            if not world:
                return JsonResponse({'error': 'World not found'}, status=404)

            # Remove map from MongoDB
            db.world_definitions.update_one(
                {'_id': world_id},
                {'$unset': {'world_map': ''}}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete map: {str(e)}'}, status=500)


class WorldSaveMapCoordinatesView(View):
    """Save updated marker coordinates and regenerate map image"""

    def post(self, request, world_id):
        try:
            world = db.world_definitions.find_one({'_id': world_id})
            if not world:
                return JsonResponse({'error': 'World not found'}, status=404)

            # Check if map exists
            if 'world_map' not in world:
                return JsonResponse({'error': 'No map found to update'}, status=400)

            # Parse request body
            data = json.loads(request.body)
            markers = data.get('markers', [])

            if not markers:
                return JsonResponse({'error': 'No markers provided'}, status=400)

            # Update region legend with new coordinates
            # Fetch actual region data from database to populate legend properly
            regions = list(db.region_definitions.find({'world_id': world_id}))
            region_lookup = {str(r['_id']): r for r in regions}

            updated_legend = []
            for i, marker in enumerate(markers):
                marker_region_id = marker.get('id', '')

                # Try to find the actual region in the database
                actual_region = None
                if marker_region_id and marker_region_id in region_lookup:
                    actual_region = region_lookup[marker_region_id]
                elif i < len(regions):
                    # Fallback: match by index if no ID match
                    actual_region = regions[i]

                # Use actual region data if found, otherwise use marker data
                if actual_region:
                    # Format terrain and climate properly (handle arrays)
                    terrain = actual_region.get('terrain', '')
                    if isinstance(terrain, list):
                        terrain = ', '.join(str(t) for t in terrain[:3])

                    climate = actual_region.get('climate', '')
                    if isinstance(climate, list):
                        climate = ', '.join(str(c) for c in climate[:2])

                    updated_legend.append({
                        'region_id': str(actual_region['_id']),
                        'number': marker.get('number', i + 1),
                        'name': actual_region.get('region_name', marker.get('name', f'Region {i+1}')),
                        'x': marker.get('x', 0.5),
                        'y': marker.get('y', 0.5),
                        'type': actual_region.get('region_type', 'region'),
                        'climate': climate,
                        'terrain': terrain
                    })
                else:
                    # No matching region - use generic marker data
                    updated_legend.append({
                        'region_id': marker.get('id', ''),
                        'number': marker.get('number', i + 1),
                        'name': marker.get('name', f'Region {i+1}'),
                        'x': marker.get('x', 0.5),
                        'y': marker.get('y', 0.5),
                        'type': marker.get('type', 'region'),
                        'climate': marker.get('climate', ''),
                        'terrain': marker.get('terrain', '')
                    })

            # Get the current map data
            current_map = world.get('world_map', {})

            # Regenerate map image with new coordinates using PIL
            # Use the filesystem path directly instead of HTTP request
            map_filepath = current_map.get('filepath', '')
            map_url = current_map.get('url', '')

            if map_filepath or map_url:
                from PIL import Image, ImageDraw, ImageFont
                from io import BytesIO
                import base64
                from pathlib import Path
                from django.conf import settings

                # Load image from filesystem if we have the path
                if map_filepath and Path(map_filepath).exists():
                    base_image = Image.open(map_filepath).convert('RGBA')
                elif map_url:
                    # Fallback: construct filesystem path from URL
                    # URL format: /media/worlds/{id}/maps/{filename}
                    if map_url.startswith('/media/'):
                        relative_path = map_url.replace('/media/', '')
                        full_path = Path(settings.MEDIA_ROOT) / relative_path
                        base_image = Image.open(full_path).convert('RGBA')
                    elif map_url.startswith('data:image'):
                        # Base64 encoded image
                        import re
                        img_data = re.sub('^data:image/.+;base64,', '', map_url)
                        base_image = Image.open(BytesIO(base64.b64decode(img_data))).convert('RGBA')
                    else:
                        # Full URL - use requests
                        import requests
                        response = requests.get(map_url)
                        base_image = Image.open(BytesIO(response.content)).convert('RGBA')
                else:
                    return JsonResponse({'error': 'No valid map image found'}, status=400)

                # Note: Ideally we'd have the terrain-only version, but for now use existing
                # In a future iteration, we could store terrain_background_url separately

                # Crop borders (same as generation)
                img_width, img_height = base_image.size
                crop_percent = 0.06
                crop_left = int(img_width * crop_percent)
                crop_top = int(img_height * crop_percent)
                crop_right = int(img_width * (1 - crop_percent))
                crop_bottom = int(img_height * (1 - crop_percent))
                base_image = base_image.crop((crop_left, crop_top, crop_right, crop_bottom))

                img_width, img_height = base_image.size

                # Create overlay for markers
                draw = ImageDraw.Draw(base_image)

                # Calculate marker size
                marker_radius = int(img_height * 0.045)
                font_size = int(marker_radius * 1.3)

                # Try to load a font, fallback to default
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                # Draw each marker
                for marker in updated_legend:
                    x = int(marker['x'] * img_width)
                    y = int(marker['y'] * img_height)
                    number = marker['number']

                    # Draw shadow/glow
                    shadow_offset = 4
                    for shadow_layer in range(3):
                        shadow_radius = marker_radius + (shadow_layer + 1) * 3
                        alpha_val = 80 - (shadow_layer * 20)
                        for _ in range(2):
                            draw.ellipse(
                                [x - shadow_radius + shadow_offset, y - shadow_radius + shadow_offset,
                                 x + shadow_radius + shadow_offset, y + shadow_radius + shadow_offset],
                                fill=(0, 0, 0, alpha_val),
                                outline=None
                            )

                    # Draw outer border (black)
                    border_width = max(4, marker_radius // 6)
                    draw.ellipse(
                        [x - marker_radius - border_width, y - marker_radius - border_width,
                         x + marker_radius + border_width, y + marker_radius + border_width],
                        fill='#000000',
                        outline='#000000'
                    )

                    # Draw inner circle (gold)
                    draw.ellipse(
                        [x - marker_radius, y - marker_radius,
                         x + marker_radius, y + marker_radius],
                        fill='#FFD700',
                        outline='#FFD700'
                    )

                    # Draw number
                    # Get text bounding box for centering
                    bbox = draw.textbbox((0, 0), str(number), font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x - text_width // 2
                    text_y = y - text_height // 2 - 2

                    draw.text((text_x, text_y), str(number), fill='#000000', font=font)

                # Convert to base64 for storage
                buffered = BytesIO()
                base_image.convert('RGB').save(buffered, format='PNG')
                img_data = base64.b64encode(buffered.getvalue()).decode()
                new_map_url = f"data:image/png;base64,{img_data}"

                # Update MongoDB with new coordinates and regenerated image
                db.world_definitions.update_one(
                    {'_id': world_id},
                    {'$set': {
                        'world_map.region_legend': updated_legend,
                        'world_map.region_count': len(updated_legend),
                        'world_map.url': new_map_url
                    }}
                )

                return JsonResponse({'success': True, 'message': 'Map updated successfully'})

            else:
                # No existing map URL, just update coordinates
                db.world_definitions.update_one(
                    {'_id': world_id},
                    {'$set': {
                        'world_map.region_legend': updated_legend,
                        'world_map.region_count': len(updated_legend)
                    }}
                )

                return JsonResponse({'success': True, 'message': 'Coordinates saved'})

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to save coordinates: {str(e)}'}, status=500)


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
            # Admin pages can have up to 4 images, but generate 1 at a time
            current_images = region.get('region_images', [])

            if len(current_images) >= 4:
                return JsonResponse({'error': 'Already have 4 images. Delete some first to generate more.'}, status=400)

            # Generate only 1 image at a time
            images_to_generate = 1

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

            # Strong anti-text prefix for ALL prompts
            no_text_prefix = """CRITICAL REQUIREMENT: This image must contain ZERO text. No words, no letters, no symbols, no signs, no banners, no labels, no writing of any kind. Do not add any textual elements whatsoever.

"""

            # Strong anti-text suffix for ALL prompts
            no_text_suffix = """

ABSOLUTE REQUIREMENT - NO EXCEPTIONS:
- NO text, letters, numbers, symbols, or writing of ANY kind
- NO signs, banners, flags with text, shop signs, or labels
- NO book text, scrolls with writing, or inscriptions
- NO UI elements, watermarks, or captions
- Pure visual imagery only - if it looks like text, don't include it
This is mandatory and non-negotiable."""

            # Define 4 image types for different perspectives
            image_types = [
                {
                    'type': 'panoramic_view',
                    'name': 'Panoramic Vista',
                    'prompt_template': f"""{no_text_prefix}Create a cinematic, wide panoramic vista of the fantasy RPG region: {region.get('region_name')}

World: {world.get('world_name')} - {world.get('genre', 'Fantasy')}
Region Type: {region.get('region_type', 'Fantasy region')}
Themes: {themes if themes else 'Adventure'}

Environment:
- Climate: {physical.get('climate', 'Varied')}
- Terrain: {', '.join(physical.get('terrain_types', [])[:3])}
- Natural Features: {', '.join(physical.get('natural_features', [])[:3])}

{f"Notable Locations: {', '.join(location_summary[:3])}" if location_summary else ''}

{region.get('description', '')[:150] if region.get('description') else ''}

Art Direction: Wide establishing shot showing the full scope of the region, highly detailed digital concept art, dramatic lighting, epic scale, professional fantasy illustration{no_text_suffix}"""
                },
                {
                    'type': 'key_landmark',
                    'name': 'Key Landmark',
                    'prompt_template': f"""{no_text_prefix}Create a dramatic view of the most iconic landmark in the region: {region.get('region_name')}

World: {world.get('world_name')} - {world.get('genre', 'Fantasy')}
Region Type: {region.get('region_type', 'Fantasy region')}

Show a prominent natural or architectural feature:
- {', '.join(physical.get('natural_features', ['distinctive features'])[:2])}
- Climate: {physical.get('climate', 'Varied')}
- Surrounding terrain: {', '.join(physical.get('terrain_types', [])[:2])}

{f"Near: {location_summary[0]}" if location_summary else ''}

Art Direction: Dramatic composition focusing on iconic feature, cinematic lighting, professional concept art, detailed environment{no_text_suffix}"""
                },
                {
                    'type': 'inhabited_area',
                    'name': 'Inhabited Area',
                    'prompt_template': f"""{no_text_prefix}Create a detailed view of where people live and gather in the region: {region.get('region_name')}

World: {world.get('world_name')} - {world.get('genre', 'Fantasy')}

Show settlements or gathering places:
- Architecture style: {', '.join(cultural.get('architectural_style', ['regional architecture'])[:2])}
- Local culture: {', '.join(cultural.get('traditions', ['local traditions'])[:2])}
- {f"Locations like: {', '.join(location_summary[:2])}" if location_summary else 'Local settlements'}
- Climate influence: {physical.get('climate', 'Varied')}

Art Direction: Populated area showing daily life, architectural detail, atmospheric lighting, professional concept art{no_text_suffix}"""
                },
                {
                    'type': 'environmental_detail',
                    'name': 'Environmental Detail',
                    'prompt_template': f"""{no_text_prefix}Create an atmospheric close-up view of the unique environment in: {region.get('region_name')}

World: {world.get('world_name')} - {world.get('genre', 'Fantasy')}

Focus on environmental details:
- Climate effects: {physical.get('climate', 'Varied')}
- Natural features: {', '.join(physical.get('natural_features', ['unique elements'])[:2])}
- Flora and fauna presence
- Weather and atmospheric conditions
- Mood: {themes if themes else 'mysterious atmosphere'}

Art Direction: Detailed environmental study, cinematic atmosphere, dramatic mood lighting, professional fantasy illustration{no_text_suffix}"""
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

            # Set Panoramic View as primary by default if it was just generated and no primary exists
            update_data = {'region_images': all_images}
            if region.get('primary_image_index') is None:
                # Find the panoramic_view image index
                for idx, img in enumerate(all_images):
                    if img.get('image_type') == 'panoramic_view':
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


# ============================================
# Region Map Generation Views
# ============================================

@method_decorator(csrf_exempt, name='dispatch')
class RegionGenerateMapView(View):
    """Generate a region map by zooming into the world map at the region's location"""

    def post(self, request, world_id, region_id):
        region = db.region_definitions.find_one({'_id': region_id})
        if not region:
            return JsonResponse({'error': 'Region not found'}, status=404)

        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        try:
            regenerate = json.loads(request.body).get('regenerate', False) if request.body else False

            # Check if world has a map
            world_map = world.get('world_map')
            if not world_map or not world_map.get('filepath'):
                return JsonResponse({'error': 'World map not found. Generate a world map first.'}, status=400)

            # Find this region's coordinates in the world map legend
            region_legend = world_map.get('region_legend', [])
            region_coords = None
            for legend_entry in region_legend:
                if legend_entry.get('region_id') == region_id:
                    region_coords = {
                        'x': legend_entry.get('x', 0.5),
                        'y': legend_entry.get('y', 0.5)
                    }
                    break

            if not region_coords:
                return JsonResponse({'error': 'Region not found on world map. Edit the world map to add this region.'}, status=400)

            # Get locations in this region
            locations = list(db.location_definitions.find({'region_id': region_id}))

            # Load world map and zoom into region area
            from PIL import Image, ImageDraw, ImageFont
            from pathlib import Path
            from django.conf import settings
            from datetime import datetime
            import math

            # Load the world map from filesystem
            world_map_path = Path(world_map['filepath'])
            if not world_map_path.exists():
                return JsonResponse({'error': 'World map file not found'}, status=500)

            world_image = Image.open(world_map_path).convert('RGBA')
            world_width, world_height = world_image.size

            # Calculate zoom crop area (zoom into 25% of world map centered on region)
            zoom_factor = 0.25  # Region map shows 25% of world map
            crop_width = int(world_width * zoom_factor)
            crop_height = int(world_height * zoom_factor)

            # Center the crop on the region's coordinates
            center_x = int(region_coords['x'] * world_width)
            center_y = int(region_coords['y'] * world_height)

            # Calculate crop bounds
            left = max(0, center_x - crop_width // 2)
            top = max(0, center_y - crop_height // 2)
            right = min(world_width, left + crop_width)
            bottom = min(world_height, top + crop_height)

            # Adjust if crop goes beyond bounds
            if right - left < crop_width:
                if left == 0:
                    right = min(world_width, crop_width)
                else:
                    left = max(0, right - crop_width)

            if bottom - top < crop_height:
                if top == 0:
                    bottom = min(world_height, crop_height)
                else:
                    top = max(0, bottom - crop_height)

            # Crop the region area
            region_image = world_image.crop((left, top, right, bottom))

            # Calculate coordinate transformation for locations
            # Locations will be positioned relative to the cropped region
            coord_offset_x = left / world_width
            coord_offset_y = top / world_height
            coord_scale_x = world_width / (right - left)
            coord_scale_y = world_height / (bottom - top)

            # Auto-assign initial grid coordinates to locations (Level 1 only)
            level_1_locations = [loc for loc in locations if loc.get('level', 1) == 1]

            import math
            num_locations = len(level_1_locations)
            cols = math.ceil(math.sqrt(num_locations))

            location_legend = []
            for i, location in enumerate(level_1_locations):
                # Calculate grid position within region
                row = i // cols
                col = i % cols

                # Position in region space (0.0-1.0)
                x = (col + 0.5) / cols
                y = (row + 0.5) / math.ceil(num_locations / cols)

                # Add variation
                x = max(0.15, min(0.85, x))
                y = max(0.15, min(0.85, y))

                # Format terrain and climate
                terrain = location.get('terrain', '')
                if isinstance(terrain, list):
                    terrain = ', '.join(str(t) for t in terrain[:2])

                climate = location.get('climate', '')
                if isinstance(climate, list):
                    climate = ', '.join(str(c) for c in climate[:2])

                location_legend.append({
                    'location_id': str(location['_id']),
                    'number': i + 1,
                    'name': location.get('location_name', f'Location {i+1}'),
                    'type': location.get('location_type', 'location'),
                    'x': x,
                    'y': y,
                    'terrain': terrain,
                    'climate': climate
                })

            # Draw location markers on region map
            draw = ImageDraw.Draw(region_image)
            img_width, img_height = region_image.size

            marker_radius = int(img_height * 0.035)  # Smaller than world markers
            font_size = int(marker_radius * 1.2)

            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()

            # Draw each location marker
            for loc_marker in location_legend:
                x = int(loc_marker['x'] * img_width)
                y = int(loc_marker['y'] * img_height)
                number = loc_marker['number']

                # Draw shadow
                shadow_offset = 3
                for _ in range(2):
                    draw.ellipse(
                        [x - marker_radius + shadow_offset, y - marker_radius + shadow_offset,
                         x + marker_radius + shadow_offset, y + marker_radius + shadow_offset],
                        fill=(0, 0, 0, 100),
                        outline=None
                    )

                # Draw outer border
                draw.ellipse(
                    [x - marker_radius - 2, y - marker_radius - 2,
                     x + marker_radius + 2, y + marker_radius + 2],
                    fill='#000000',
                    outline='#000000'
                )

                # Draw inner circle (blue for locations)
                draw.ellipse(
                    [x - marker_radius, y - marker_radius,
                     x + marker_radius, y + marker_radius],
                    fill='#4A90E2',  # Blue for locations
                    outline='#4A90E2'
                )

                # Draw number
                bbox = draw.textbbox((0, 0), str(number), font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = x - text_width // 2
                text_y = y - text_height // 2 - 2

                draw.text((text_x, text_y), str(number), fill='#FFFFFF', font=font)

            # Save region map
            region_maps_dir = Path(settings.MEDIA_ROOT) / 'regions' / region_id / 'maps'
            region_maps_dir.mkdir(parents=True, exist_ok=True)

            filename = f"map_{uuid.uuid4()}.png"
            filepath = region_maps_dir / filename

            region_image.save(filepath, 'PNG', quality=95)

            relative_path = f"regions/{region_id}/maps/{filename}"
            local_url = f"{settings.MEDIA_URL}{relative_path}"

            map_data = {
                'url': local_url,
                'filepath': str(filepath),
                'generated_at': datetime.utcnow(),
                'location_legend': location_legend,
                'location_count': len(location_legend),
                'zoom_factor': zoom_factor,
                'source': 'world_map_zoom'
            }

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': {'region_map': map_data}}
            )

            return JsonResponse({
                'success': True,
                'map': map_data,
                'regenerate': regenerate
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to generate map: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RegionSaveMapCoordinatesView(View):
    """Save updated location marker coordinates and regenerate region map"""

    def post(self, request, world_id, region_id):
        try:
            region = db.region_definitions.find_one({'_id': region_id})
            if not region:
                return JsonResponse({'error': 'Region not found'}, status=404)

            # Check if map exists
            if 'region_map' not in region:
                return JsonResponse({'error': 'No map found to update'}, status=400)

            # Parse request body
            data = json.loads(request.body)
            markers = data.get('markers', [])

            if not markers:
                return JsonResponse({'error': 'No markers provided'}, status=400)

            # Fetch actual location data from database
            locations = list(db.location_definitions.find({'region_id': region_id}))
            location_lookup = {str(loc['_id']): loc for loc in locations}

            updated_legend = []
            for i, marker in enumerate(markers):
                marker_location_id = marker.get('id', '')

                # Try to find the actual location in the database
                actual_location = None
                if marker_location_id and marker_location_id in location_lookup:
                    actual_location = location_lookup[marker_location_id]
                elif i < len(locations):
                    actual_location = locations[i]

                # Use actual location data if found
                if actual_location:
                    terrain = actual_location.get('terrain', '')
                    if isinstance(terrain, list):
                        terrain = ', '.join(str(t) for t in terrain[:2])

                    climate = actual_location.get('climate', '')
                    if isinstance(climate, list):
                        climate = ', '.join(str(c) for c in climate[:2])

                    updated_legend.append({
                        'location_id': str(actual_location['_id']),
                        'number': marker.get('number', i + 1),
                        'name': actual_location.get('location_name', marker.get('name', f'Location {i+1}')),
                        'type': actual_location.get('location_type', 'location'),
                        'x': marker.get('x', 0.5),
                        'y': marker.get('y', 0.5),
                        'terrain': terrain,
                        'climate': climate
                    })
                else:
                    updated_legend.append({
                        'location_id': marker.get('id', ''),
                        'number': marker.get('number', i + 1),
                        'name': marker.get('name', f'Location {i+1}'),
                        'type': marker.get('type', 'location'),
                        'x': marker.get('x', 0.5),
                        'y': marker.get('y', 0.5),
                        'terrain': marker.get('terrain', ''),
                        'climate': marker.get('climate', '')
                    })

            # Get current map and regenerate with new markers
            current_map = region.get('region_map', {})
            map_filepath = current_map.get('filepath', '')
            map_url = current_map.get('url', '')

            if map_filepath or map_url:
                from PIL import Image, ImageDraw, ImageFont
                from io import BytesIO
                from pathlib import Path
                from django.conf import settings
                import base64

                # Load base image
                if map_filepath and Path(map_filepath).exists():
                    base_image = Image.open(map_filepath).convert('RGBA')
                elif map_url.startswith('/media/'):
                    relative_path = map_url.replace('/media/', '')
                    full_path = Path(settings.MEDIA_ROOT) / relative_path
                    base_image = Image.open(full_path).convert('RGBA')
                else:
                    return JsonResponse({'error': 'Map file not found'}, status=400)

                # Reload the original world map crop (without markers)
                # For now, just overlay new markers on existing image
                # TODO: Store original terrain-only crop for cleaner regeneration

                draw = ImageDraw.Draw(base_image)
                img_width, img_height = base_image.size

                marker_radius = int(img_height * 0.035)
                font_size = int(marker_radius * 1.2)

                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                # Draw each marker
                for loc_marker in updated_legend:
                    x = int(loc_marker['x'] * img_width)
                    y = int(loc_marker['y'] * img_height)
                    number = loc_marker['number']

                    # Draw shadow
                    for _ in range(2):
                        draw.ellipse(
                            [x - marker_radius + 3, y - marker_radius + 3,
                             x + marker_radius + 3, y + marker_radius + 3],
                            fill=(0, 0, 0, 100),
                            outline=None
                        )

                    # Draw border
                    draw.ellipse(
                        [x - marker_radius - 2, y - marker_radius - 2,
                         x + marker_radius + 2, y + marker_radius + 2],
                        fill='#000000',
                        outline='#000000'
                    )

                    # Draw inner circle
                    draw.ellipse(
                        [x - marker_radius, y - marker_radius,
                         x + marker_radius, y + marker_radius],
                        fill='#4A90E2',
                        outline='#4A90E2'
                    )

                    # Draw number
                    bbox = draw.textbbox((0, 0), str(number), font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    text_x = x - text_width // 2
                    text_y = y - text_height // 2 - 2

                    draw.text((text_x, text_y), str(number), fill='#FFFFFF', font=font)

                # Save updated map
                base_image.save(map_filepath, 'PNG', quality=95)

                # Update MongoDB
                db.region_definitions.update_one(
                    {'_id': region_id},
                    {'$set': {
                        'region_map.location_legend': updated_legend,
                        'region_map.location_count': len(updated_legend)
                    }}
                )

                return JsonResponse({'success': True, 'message': 'Map updated successfully'})

            else:
                return JsonResponse({'error': 'No map image found'}, status=400)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to save coordinates: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RegionDeleteMapView(View):
    """Delete the region map"""

    def post(self, request, world_id, region_id):
        try:
            region = db.region_definitions.find_one({'_id': region_id})
            if not region:
                return JsonResponse({'error': 'Region not found'}, status=404)

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$unset': {'region_map': ''}}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete map: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class RegionUpdateLocationCoordinatesView(View):
    """Update coordinates for a location on the region map"""

    def post(self, request, world_id, region_id):
        try:
            data = json.loads(request.body)
            location_id = data.get('location_id')
            x = data.get('x')
            y = data.get('y')

            if not location_id or x is None or y is None:
                return JsonResponse({'error': 'location_id, x, and y required'}, status=400)

            # Validate coordinates
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return JsonResponse({'error': 'Coordinates must be between 0 and 1'}, status=400)

            region = db.region_definitions.find_one({'_id': region_id})
            if not region:
                return JsonResponse({'error': 'Region not found'}, status=404)

            location_coordinates = region.get('location_coordinates', {})
            if location_id not in location_coordinates:
                location_coordinates[location_id] = {}

            location_coordinates[location_id]['x'] = x
            location_coordinates[location_id]['y'] = y

            db.region_definitions.update_one(
                {'_id': region_id},
                {'$set': {'location_coordinates': location_coordinates}}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to update coordinates: {str(e)}'}, status=500)


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


# ============================================
# Location Map Generation Views
# ============================================

@method_decorator(csrf_exempt, name='dispatch')
class LocationGenerateMapView(View):
    """Generate a cartographic map for a location using DALL-E 3 API"""

    def get_genre_map_style(self, genre):
        """Return map styling instructions based on genre"""
        genre_styles = {
            'Fantasy': {'style_name': 'medieval_fantasy', 'description': 'Medieval fantasy map style with parchment texture, hand-drawn style'},
            'Western': {'style_name': 'western_1800s', 'description': '1800s survey map style with sepia tones'},
            'Sci-Fi': {'style_name': 'sci_fi_holographic', 'description': 'Futuristic holographic HUD style'},
            'Post-Apocalyptic': {'style_name': 'post_apocalyptic', 'description': 'Weathered, salvaged map style'},
            'Steampunk': {'style_name': 'steampunk_victorian', 'description': 'Victorian steampunk cartography'},
            'Cyberpunk': {'style_name': 'cyberpunk_neon', 'description': 'Cyberpunk digital map with neon'},
            'Historical': {'style_name': 'historical_authentic', 'description': 'Authentic historical cartography'},
        }
        return genre_styles.get(genre, genre_styles['Fantasy'])

    def post(self, request, world_id, region_id, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            return JsonResponse({'error': 'Location not found'}, status=404)

        world = db.world_definitions.find_one({'_id': world_id})
        region = db.region_definitions.find_one({'_id': region_id})

        try:
            regenerate = json.loads(request.body).get('regenerate', False) if request.body else False

            genre = world.get('genre', 'Fantasy') if world else 'Fantasy'
            map_style = self.get_genre_map_style(genre)

            location_name = location.get('location_name', 'Unknown Location')
            location_type = location.get('location_type', 'location')
            description = location.get('description', '')

            # Determine map type based on location type
            if location_type.lower() in ['city', 'town', 'village']:
                map_type = 'settlement'
                focus = 'streets, buildings, districts, and key landmarks'
            elif location_type.lower() in ['dungeon', 'cave', 'ruins']:
                map_type = 'interior'
                focus = 'rooms, corridors, chambers, and hazards'
            elif location_type.lower() in ['fortress', 'castle', 'temple']:
                map_type = 'structure'
                focus = 'floors, rooms, walls, and defensive features'
            else:
                map_type = 'area'
                focus = 'layout, key features, and points of interest'

            no_text_requirement = """
CRITICAL MAP REQUIREMENTS:
- NO text, labels, names, letters, or numbers
- NO written language of any kind
- Pure visual cartography with symbols and icons only
"""

            map_prompt = f"""{no_text_requirement}

Create a detailed cartographic map of: {location_name}

LOCATION: {description if description else f'A {location_type}'}
TYPE: {location_type} ({map_type} map)

MAP STYLE: {map_style['description']}

FEATURES TO DEPICT:
- {focus}
- Entrances and exits
- Notable features and areas
- Paths and connections
- Scale appropriate details

VISUAL ELEMENTS:
- Symbolic icons for different areas
- Clear layout and structure
- Visual hierarchy
- Decorative border (period-appropriate)

TECHNICAL:
- Top-down or isometric view as appropriate
- {location_type} map style
- Clear, readable layout
- Genre: {genre}

IMPORTANT: NO TEXT - pure visual map.
"""

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings
            from datetime import datetime

            client = OpenAI(api_key=openai_api_key)

            response = client.images.generate(
                model="dall-e-3",
                prompt=map_prompt[:4000],
                size="1792x1024",
                quality="hd",
                n=1,
            )

            dalle_url = response.data[0].url

            # Create directory: media/locations/[location_id]/maps/
            location_maps_dir = Path(settings.MEDIA_ROOT) / 'locations' / location_id / 'maps'
            location_maps_dir.mkdir(parents=True, exist_ok=True)

            filename = f"map_{uuid.uuid4()}.png"
            filepath = location_maps_dir / filename

            urllib.request.urlretrieve(dalle_url, filepath)

            relative_path = f"locations/{location_id}/maps/{filename}"
            local_url = f"{settings.MEDIA_URL}{relative_path}"

            map_data = {
                'url': local_url,
                'prompt': map_prompt[:500],
                'style': map_style['style_name'],
                'generated_at': datetime.utcnow(),
                'filepath': str(filepath)
            }

            db.location_definitions.update_one(
                {'_id': location_id},
                {'$set': {'location_map': map_data}}
            )

            return JsonResponse({
                'success': True,
                'map': map_data,
                'regenerate': regenerate
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Failed to generate map: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class LocationDeleteMapView(View):
    """Delete the location map"""

    def post(self, request, world_id, region_id, location_id):
        try:
            location = db.location_definitions.find_one({'_id': location_id})
            if not location:
                return JsonResponse({'error': 'Location not found'}, status=404)

            db.location_definitions.update_one(
                {'_id': location_id},
                {'$unset': {'location_map': ''}}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete map: {str(e)}'}, status=500)


# Import Location Image Views
from .views_locations import LocationGenerateImageView, LocationDeleteImageView, LocationSetPrimaryImageView
