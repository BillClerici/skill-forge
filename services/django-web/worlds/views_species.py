"""
Views for Species management
Uses MongoDB for definitions and Neo4j for relationships
"""
import uuid
import httpx
import requests
import sys
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import JsonResponse
from pymongo import MongoClient
import os
import json
from openai import OpenAI
from utils.rabbitmq import publish_entity_event


# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection removed - now using RabbitMQ events
# NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
# NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
# NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
# neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')

# OpenAI client for DALL-E
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Media directory for saving images
from django.conf import settings
MEDIA_ROOT = settings.MEDIA_ROOT
MEDIA_URL = settings.MEDIA_URL


class SpeciesCreateView(View):
    """Create a new species for a world"""

    def get(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            messages.error(request, 'World not found')
            return redirect('world_list')

        # Get all regions for this world
        region_ids = world.get('regions', [])
        regions = []
        if region_ids:
            regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))
            for r in regions:
                r['region_id'] = r['_id']

        # Get all unique character traits from existing species in this world
        all_species = list(db.species_definitions.find({'world_id': world_id}))
        custom_traits = set()
        for species in all_species:
            for trait in species.get('character_traits', []):
                custom_traits.add(trait)

        world['world_id'] = world['_id']
        return render(request, 'worlds/species_form.html', {
            'world': world,
            'regions': regions,
            'custom_traits': sorted(list(custom_traits)),
            'action': 'create'
        })

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        # Generate unique ID
        species_id = str(uuid.uuid4())

        # Get form data
        species_name = request.POST.get('species_name', '')
        species_type = request.POST.get('species_type', '')
        category = request.POST.get('category', '')
        description = request.POST.get('description', '')
        backstory = request.POST.get('backstory', '')
        character_traits = request.POST.getlist('character_traits')
        region_ids = request.POST.getlist('regions')

        # Create species document
        species = {
            '_id': species_id,
            'world_id': world_id,
            'species_name': species_name,
            'species_type': species_type,
            'category': category,
            'description': description,
            'backstory': backstory,
            'character_traits': character_traits,
            'regions': region_ids,
            'relationships': [],
            'species_image': None
        }

        # Insert into MongoDB
        db.species_definitions.insert_one(species)

        # Update world's species list
        db.world_definitions.update_one(
            {'_id': world_id},
            {'$addToSet': {'species': species_id}}
        )

        # Publish event to sync to Neo4j
        publish_entity_event('species', 'created', species_id, {
            'world_id': world_id,
            'species_name': species_name,
            'species_type': species_type,
            'category': category,
            'regions': region_ids
        })

        messages.success(request, f'Species "{species_name}" created successfully!')
        return redirect('world_detail', world_id=world_id)


class SpeciesDetailView(View):
    """View species details"""

    def get(self, request, world_id, species_id):
        world = db.world_definitions.find_one({'_id': world_id})
        species = db.species_definitions.find_one({'_id': species_id})

        if not world or not species:
            messages.error(request, 'World or Species not found')
            return redirect('world_list')

        # Get all regions for this world to show which ones this species inhabits
        region_ids = world.get('regions', [])
        all_regions = []
        species_regions = []
        if region_ids:
            all_regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))
            for r in all_regions:
                r['region_id'] = r['_id']
                if r['_id'] in species.get('regions', []):
                    species_regions.append(r)

        world['world_id'] = world['_id']
        species['species_id'] = species['_id']

        # Get primary image for display
        primary_image = None
        if species.get('species_images') and species.get('primary_image_index') is not None:
            images = species.get('species_images', [])
            primary_idx = species.get('primary_image_index')
            if 0 <= primary_idx < len(images):
                primary_image = images[primary_idx]

        return render(request, 'worlds/species_detail.html', {
            'world': world,
            'species': species,
            'species_regions': species_regions,
            'primary_image': primary_image
        })


class SpeciesEditView(View):
    """Edit an existing species"""

    def get(self, request, world_id, species_id):
        world = db.world_definitions.find_one({'_id': world_id})
        species = db.species_definitions.find_one({'_id': species_id})

        if not world or not species:
            messages.error(request, 'World or Species not found')
            return redirect('world_list')

        # Get all regions for this world
        region_ids = world.get('regions', [])
        regions = []
        if region_ids:
            regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))
            for r in regions:
                r['region_id'] = r['_id']
                # Mark regions that this species inhabits
                r['is_selected'] = r['_id'] in species.get('regions', [])

        # Get all unique character traits from existing species in this world
        all_species = list(db.species_definitions.find({'world_id': world_id}))
        custom_traits = set()
        for sp in all_species:
            for trait in sp.get('character_traits', []):
                custom_traits.add(trait)

        world['world_id'] = world['_id']
        species['species_id'] = species['_id']

        return render(request, 'worlds/species_form.html', {
            'world': world,
            'species': species,
            'regions': regions,
            'custom_traits': sorted(list(custom_traits)),
            'action': 'edit'
        })

    def post(self, request, world_id, species_id):
        species = db.species_definitions.find_one({'_id': species_id})
        if not species:
            return JsonResponse({'error': 'Species not found'}, status=404)

        # Get form data
        species_name = request.POST.get('species_name', '')
        species_type = request.POST.get('species_type', '')
        category = request.POST.get('category', '')
        description = request.POST.get('description', '')
        backstory = request.POST.get('backstory', '')
        character_traits = request.POST.getlist('character_traits')
        region_ids = request.POST.getlist('regions')

        # Update species document
        db.species_definitions.update_one(
            {'_id': species_id},
            {'$set': {
                'species_name': species_name,
                'species_type': species_type,
                'category': category,
                'description': description,
                'backstory': backstory,
                'character_traits': character_traits,
                'regions': region_ids
            }}
        )

        # Publish event to sync to Neo4j
        publish_entity_event('species', 'updated', species_id, {
            'species_name': species_name,
            'species_type': species_type,
            'category': category,
            'regions': region_ids
        })

        messages.success(request, f'Species "{species_name}" updated successfully!')
        return redirect('species_detail', world_id=world_id, species_id=species_id)


class SpeciesDeleteView(View):
    """Delete a species"""

    def get(self, request, world_id, species_id):
        world = db.world_definitions.find_one({'_id': world_id})
        species = db.species_definitions.find_one({'_id': species_id})

        if not world or not species:
            messages.error(request, 'World or Species not found')
            return redirect('world_list')

        world['world_id'] = world['_id']
        species['species_id'] = species['_id']

        return render(request, 'worlds/species_confirm_delete.html', {
            'world': world,
            'species': species
        })

    def post(self, request, world_id, species_id):
        # Delete species from MongoDB
        db.species_definitions.delete_one({'_id': species_id})

        # Remove from world's species list
        db.world_definitions.update_one(
            {'_id': world_id},
            {'$pull': {'species': species_id}}
        )

        # Publish event to sync deletion to Neo4j
        publish_entity_event('species', 'deleted', species_id, {})

        messages.success(request, 'Species deleted successfully!')
        return redirect('world_detail', world_id=world_id)


@method_decorator(csrf_exempt, name='dispatch')
class SpeciesGenerateAIView(View):
    """Generate species for a world using AI"""

    def post(self, request, world_id):
        world = db.world_definitions.find_one({'_id': world_id})
        if not world:
            return JsonResponse({'error': 'World not found'}, status=404)

        # Get all regions for context
        region_ids = world.get('regions', [])
        regions = []
        if region_ids:
            regions = list(db.region_definitions.find({'_id': {'$in': region_ids}}))

        # Prepare world context for AI
        world_context = {
            'world_id': world_id,
            'world_name': world.get('world_name', ''),
            'genre': world.get('genre', ''),
            'description': world.get('description', ''),
            'backstory': world.get('backstory', ''),
            'themes': world.get('themes', []),
            'visual_style': world.get('visual_style', []),
            'timeline': world.get('timeline', []),
            'physical_properties': world.get('physical_properties', {}),
            'biological_properties': world.get('biological_properties', {}),
            'technological_properties': world.get('technological_properties', {}),
            'societal_properties': world.get('societal_properties', {}),
            'historical_properties': world.get('historical_properties', {}),
            'regions': [
                {
                    'region_id': str(r['_id']),
                    'region_name': r.get('region_name', ''),
                    'region_type': r.get('region_type', ''),
                    'climate': r.get('climate', ''),
                    'terrain': r.get('terrain', []),
                    'description': r.get('description', ''),
                    'backstory': r.get('backstory', '')
                }
                for r in regions
            ]
        }

        try:
            # Call orchestrator to generate species
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-species",
                    json=world_context
                )

                if response.status_code == 200:
                    result = response.json()
                    species_list = result.get('species', [])

                    # Save each species to MongoDB and generate images
                    created_species_ids = []
                    for species_data in species_list:
                        species_id = str(uuid.uuid4())

                        species = {
                            '_id': species_id,
                            'world_id': world_id,
                            'species_name': species_data.get('name', ''),
                            'species_type': species_data.get('species_type', ''),
                            'category': species_data.get('category', ''),
                            'description': species_data.get('description', ''),
                            'backstory': species_data.get('backstory', ''),
                            'character_traits': species_data.get('character_traits', []),
                            'regions': species_data.get('region_ids', []),
                            'relationships': [],
                            'species_images': [],
                            'primary_image_index': None
                        }

                        db.species_definitions.insert_one(species)
                        created_species_ids.append(species_id)

                        # Generate image for this species
                        if openai_client:
                            try:
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

                                traits_str = ', '.join(species_data.get('character_traits', [])[:5]) if species_data.get('character_traits') else 'unique characteristics'

                                dalle_prompt = f"""{no_text_prefix}Create a detailed character portrait of the {species['species_name']} species from the fantasy world: {world.get('world_name')}

World Genre: {world.get('genre', 'Fantasy')}
Species: {species['species_name']}
Type: {species['species_type']}
Key Traits: {traits_str}

{species['description'][:200] if species['description'] else ''}

Art Direction: Full body or portrait view, highly detailed fantasy character art, dramatic lighting, professional digital illustration, showing distinctive species features and characteristics{no_text_suffix}"""

                                # Generate image with DALL-E 3
                                dalle_response = openai_client.images.generate(
                                    model="dall-e-3",
                                    prompt=dalle_prompt,
                                    size="1024x1024",
                                    quality="standard",
                                    n=1
                                )

                                image_url = dalle_response.data[0].url

                                # Download and save image locally
                                img_response = requests.get(image_url)
                                if img_response.status_code == 200:
                                    # Create species images directory
                                    species_dir = os.path.join(MEDIA_ROOT, 'species', world_id)
                                    os.makedirs(species_dir, exist_ok=True)

                                    # Save image with timestamp
                                    import time
                                    timestamp = int(time.time() * 1000)
                                    image_filename = f"{species_id}_{timestamp}_0.png"
                                    image_path = os.path.join(species_dir, image_filename)

                                    with open(image_path, 'wb') as f:
                                        f.write(img_response.content)

                                    # Update species with new multi-image system
                                    local_image_url = f"{MEDIA_URL}species/{world_id}/{image_filename}"

                                    # Add to species_images array as portrait type
                                    image_data = {
                                        'url': local_image_url,
                                        'image_type': 'portrait',
                                        'image_name': 'Portrait',
                                        'perspective': 'close-up portrait showing face and upper body details'
                                    }

                                    db.species_definitions.update_one(
                                        {'_id': species_id},
                                        {
                                            '$push': {'species_images': image_data},
                                            '$set': {'primary_image_index': 0}
                                        }
                                    )
                            except Exception as img_error:
                                # Log error but continue - image generation is optional
                                print(f"Failed to generate image for species {species['species_name']}: {str(img_error)}")

                    # Add new species to world's species list (append, don't replace)
                    db.world_definitions.update_one(
                        {'_id': world_id},
                        {'$push': {'species': {'$each': created_species_ids}}}
                    )

                    return JsonResponse({
                        'success': True,
                        'species_count': len(created_species_ids),
                        'tokens_used': result.get('tokens_used', 0),
                        'cost_usd': result.get('cost_usd', 0)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f'AI generation failed: {response.text}'
                    }, status=500)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SpeciesDeleteImageView(View):
    """Delete a species image"""

    def post(self, request, world_id, species_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            species = db.species_definitions.find_one({'_id': species_id})
            if not species:
                return JsonResponse({'error': 'Species not found'}, status=404)

            species_images = species.get('species_images', [])

            if image_index is None or image_index < 0 or image_index >= len(species_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            # Remove the image from the list
            deleted_image = species_images.pop(image_index)

            # Delete the physical file
            if deleted_image.get('url'):
                image_path = deleted_image['url'].replace(MEDIA_URL, '')
                full_path = os.path.join(MEDIA_ROOT, image_path)
                if os.path.exists(full_path):
                    os.remove(full_path)

            # Adjust primary index if needed
            primary_index = species.get('primary_image_index')
            if primary_index is not None:
                if primary_index == image_index:
                    # Deleted image was primary, set first image as primary
                    primary_index = 0 if species_images else None
                elif primary_index > image_index:
                    # Adjust primary index
                    primary_index -= 1

            # Update database
            db.species_definitions.update_one(
                {'_id': species_id},
                {'$set': {
                    'species_images': species_images,
                    'primary_image_index': primary_index
                }}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SpeciesSetPrimaryImageView(View):
    """Set primary image for a species"""

    def post(self, request, world_id, species_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            species = db.species_definitions.find_one({'_id': species_id})
            if not species:
                return JsonResponse({'error': 'Species not found'}, status=404)

            species_images = species.get('species_images', [])

            if image_index is None or image_index < 0 or image_index >= len(species_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            # Update primary index
            db.species_definitions.update_one(
                {'_id': species_id},
                {'$set': {'primary_image_index': image_index}}
            )

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SpeciesGenerateImageView(View):
    """Generate images for a species using DALL-E (up to 4 total)"""

    def post(self, request, world_id, species_id):
        if not openai_client:
            return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

        world = db.world_definitions.find_one({'_id': world_id})
        species = db.species_definitions.find_one({'_id': species_id})

        if not world or not species:
            return JsonResponse({'error': 'World or Species not found'}, status=404)

        # Check how many images already exist
        # Admin pages can have up to 4 images, but generate 1 at a time
        current_images = species.get('species_images', [])
        if len(current_images) >= 4:
            return JsonResponse({'error': 'Already have 4 images. Delete some first to generate more.'}, status=400)

        try:
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
                    'type': 'full_body',
                    'name': 'Full Body View',
                    'perspective': 'full body standing pose showing complete form from head to toe'
                },
                {
                    'type': 'portrait',
                    'name': 'Portrait',
                    'perspective': 'close-up portrait showing face and upper body details'
                },
                {
                    'type': 'action_pose',
                    'name': 'Action Pose',
                    'perspective': 'dynamic action pose showing movement and agility'
                },
                {
                    'type': 'habitat',
                    'name': 'In Natural Habitat',
                    'perspective': 'shown in natural environment or habitat, environmental context'
                }
            ]

            # Generate only 1 image at a time
            images_to_generate = 1
            generated_images = []
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

                perspective = image_type_config['perspective']

                # Build safe prompt focusing on visual aspects only
                # Avoid backstory, lore, or anything that might trigger content filters
                species_name = species.get('species_name', 'Fantasy Creature')
                species_type = species.get('species_type', 'Creature')

                # Get description but remove potentially problematic content
                original_desc = species.get('description', '')

                # Comprehensive list of potentially problematic words for OpenAI's content policy
                problem_phrases = [
                    'war', 'War', 'battle', 'Battle', 'killed', 'kill', 'death', 'Death',
                    'scorched', 'spawned', 'Spawned', 'blood', 'corpse', 'dead', 'dying',
                    'destroyed', 'attacking', 'aggressive', 'Aggressive',
                    'predatory', 'Predatory', 'prey', 'Prey', 'hunt', 'Hunt', 'hunting', 'Hunting',
                    'paralyze', 'Paralyze', 'apex predator', 'Apex predator', 'apex Predator',
                    'violence', 'violent', 'weapon', 'weapons', 'massacre', 'slaughter',
                    'torture', 'terror', 'fear', 'Fear', 'victim', 'victims'
                ]

                # Split description into sentences and keep only physical/visual descriptions
                sentences = [s.strip() for s in original_desc.split('.') if s.strip()]
                safe_sentences = []
                for sentence in sentences:
                    # Check if sentence contains problematic words
                    has_problem = any(word.lower() in sentence.lower() for word in problem_phrases)
                    if not has_problem and len(sentence) > 10:
                        safe_sentences.append(sentence)

                # If we have safe sentences, use them, otherwise create a generic visual description
                if safe_sentences:
                    visual_desc = '. '.join(safe_sentences[:2])  # Use first 2 safe sentences
                else:
                    # Create a neutral description focusing on visual aspects only
                    visual_desc = f"A {species_type.lower()} with distinctive fur patterns and unique physical features"

                # Add traits if they're safe
                traits = species.get('character_traits', [])[:3]
                safe_traits = []
                trait_replacements = {
                    'aggressive': 'bold', 'violent': 'intense', 'deadly': 'formidable',
                    'killer': 'skilled', 'murderous': 'mysterious', 'evil': 'dark',
                    'predatory': 'focused', 'territorial': 'protective', 'cunning': 'clever',
                    'savage': 'wild', 'brutal': 'strong', 'vicious': 'fierce'
                }
                for trait in traits:
                    trait_lower = trait.lower()
                    replaced = False
                    for bad, good in trait_replacements.items():
                        if bad in trait_lower:
                            safe_traits.append(good.capitalize())
                            replaced = True
                            break
                    if not replaced:
                        safe_traits.append(trait)

                traits_str = ', '.join(safe_traits) if safe_traits else ''

                # Build the prompt with conditional full_body instruction
                if image_type_config['type'] == 'full_body':
                    dalle_prompt = f"""{no_text_prefix}A {species_type.lower()} called {species_name}.

{visual_desc}

{f'Characteristics: {traits_str}' if traits_str else ''}

Perspective: {perspective}

Style: Detailed fantasy art, dramatic lighting, professional digital illustration, epic scale

IMPORTANT: Full body view must include the complete character from head to toe. Show the entire head, face, torso, arms, legs, and feet in the frame.{no_text_suffix}"""
                else:
                    dalle_prompt = f"""{no_text_prefix}A {species_type.lower()} called {species_name}.

{visual_desc}

{f'Characteristics: {traits_str}' if traits_str else ''}

Perspective: {perspective}

Style: Detailed fantasy art, dramatic lighting, professional digital illustration, epic scale{no_text_suffix}"""

                # Log the prompt for debugging
                print(f"=== DALL-E PROMPT FOR {species.get('species_name')} ===", file=sys.stderr)
                print(dalle_prompt, file=sys.stderr)
                print("=" * 60, file=sys.stderr)
                sys.stderr.flush()

                # Generate image with DALL-E 3
                response = openai_client.images.generate(
                    model="dall-e-3",
                    prompt=dalle_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1
                )

                image_url = response.data[0].url

                # Download and save image locally
                img_response = requests.get(image_url)

                if img_response.status_code == 200:
                    # Create species images directory
                    species_dir = os.path.join(MEDIA_ROOT, 'species', world_id)
                    os.makedirs(species_dir, exist_ok=True)

                    # Save image with unique filename
                    import time
                    timestamp = int(time.time() * 1000)
                    image_filename = f"{species_id}_{timestamp}_{i}.png"
                    image_path = os.path.join(species_dir, image_filename)

                    with open(image_path, 'wb') as f:
                        f.write(img_response.content)

                    # Store image info
                    local_image_url = f"{MEDIA_URL}species/{world_id}/{image_filename}"
                    generated_images.append({
                        'url': local_image_url,
                        'image_type': image_type_config['type'],
                        'image_name': image_type_config['name'],
                        'perspective': perspective
                    })

            # Update species with new images
            updated_images = current_images + generated_images

            # Set Portrait as primary by default if it was just generated and no primary exists
            primary_index = species.get('primary_image_index')
            if primary_index is None:
                # Find the portrait image index
                for idx, img in enumerate(updated_images):
                    if img.get('image_type') == 'portrait':
                        primary_index = idx
                        break
                # If no portrait found, use first image
                if primary_index is None and updated_images:
                    primary_index = 0

            db.species_definitions.update_one(
                {'_id': species_id},
                {'$set': {
                    'species_images': updated_images,
                    'primary_image_index': primary_index
                }}
            )

            return JsonResponse({
                'success': True,
                'images_generated': len(generated_images)
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR generating species image: {str(e)}", file=sys.stderr)
            print(f"Full traceback:\n{error_details}", file=sys.stderr)
            sys.stderr.flush()

            # Check if it's a content policy violation
            error_message = str(e)
            if 'content_policy_violation' in error_message or 'safety system' in error_message:
                error_message = "The species description contains content that violates OpenAI's safety policies. Please try editing the species description, traits, or backstory to use less explicit or sensitive language."

            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=500)
