# Location Image Generation Views
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import os
from pymongo import MongoClient

# MongoDB connection
client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://admin:password@mongodb:27017'))
db = client['skillforge']


@method_decorator(csrf_exempt, name='dispatch')
class LocationGenerateImageView(View):
    """Generate AI images for a location using DALL-E 3 API"""

    def post(self, request, world_id, region_id, location_id):
        location = db.location_definitions.find_one({'_id': location_id})
        if not location:
            return JsonResponse({'error': 'Location not found'}, status=404)

        region = db.region_definitions.find_one({'_id': region_id})
        world = db.world_definitions.find_one({'_id': world_id})

        try:
            # Get current image count
            current_images = location.get('location_images', [])
            images_to_generate = 1 - len(current_images)

            if images_to_generate <= 0:
                return JsonResponse({'error': 'Already have 1 image. Delete it first.'}, status=400)

            # Build comprehensive prompt
            features = location.get('features', [])
            if isinstance(features, list):
                features_str = ', '.join(features[:3]) if features else 'Various features'
            else:
                features_str = 'Various features'

            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client_openai = OpenAI(api_key=openai_api_key)

            # Define 1 image type: Location View
            image_types = [
                {
                    'type': 'location_view',
                    'name': 'Location View',
                    'prompt_template': f"""Create a cinematic view of the fantasy RPG location: {location.get('location_name')}

World: {world.get('world_name') if world else 'Fantasy World'} - {world.get('genre', 'Fantasy') if world else 'Fantasy'}
Region: {region.get('region_name') if region else 'Unknown Region'} - {region.get('region_type') if region else ''}
Location Type: {location.get('location_type', 'Fantasy location')}

Environment:
- Purpose: {location.get('purpose', 'Mysterious location')}
- Key Features: {features_str}

{location.get('description', '')[:150] if location.get('description') else ''}

Art Direction: Detailed establishing shot, highly detailed digital concept art, dramatic lighting, epic scale, professional fantasy illustration

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

                response = client_openai.images.generate(
                    model="dall-e-3",
                    prompt=dalle_prompt[:4000],
                    size="1792x1024",
                    quality="standard",
                    n=1,
                )

                # Download and save image locally
                dalle_url = response.data[0].url

                # Create directory structure: media/locations/[location_id]/
                location_media_dir = Path(settings.MEDIA_ROOT) / 'locations' / location_id
                location_media_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique filename
                import uuid
                filename = f"{uuid.uuid4()}.png"
                filepath = location_media_dir / filename

                # Download image from DALL-E URL
                urllib.request.urlretrieve(dalle_url, filepath)

                # Store relative path for URL generation
                relative_path = f"locations/{location_id}/{filename}"
                local_url = f"{settings.MEDIA_URL}{relative_path}"

                new_images.append({
                    'url': local_url,
                    'prompt': dalle_prompt[:500],
                    'image_type': image_type_config['type'],
                    'image_name': image_type_config['name'],
                    'filepath': str(filepath)
                })

            all_images = current_images + new_images

            # Set Day as primary by default if it was just generated and no primary exists
            update_data = {'location_images': all_images}
            if location.get('primary_image_index') is None:
                # Find the day image index
                for idx, img in enumerate(all_images):
                    if img.get('image_type') == 'day':
                        update_data['primary_image_index'] = idx
                        break

            db.location_definitions.update_one(
                {'_id': location_id},
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
class LocationDeleteImageView(View):
    """Delete a specific location image by index"""

    def post(self, request, world_id, region_id, location_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            location = db.location_definitions.find_one({'_id': location_id})
            if not location:
                return JsonResponse({'error': 'Location not found'}, status=404)

            current_images = location.get('location_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            current_images.pop(image_index)

            # Adjust primary_image_index if needed
            primary_index = location.get('primary_image_index')
            update_data = {'location_images': current_images}

            if primary_index is not None:
                if primary_index == image_index:
                    update_data['primary_image_index'] = None
                elif primary_index > image_index:
                    update_data['primary_image_index'] = primary_index - 1

            db.location_definitions.update_one(
                {'_id': location_id},
                {'$set': update_data}
            )

            return JsonResponse({
                'success': True,
                'remaining_count': len(current_images)
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to delete image: {str(e)}'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class LocationSetPrimaryImageView(View):
    """Set a specific location image as the primary image"""

    def post(self, request, world_id, region_id, location_id):
        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None:
                return JsonResponse({'error': 'image_index required'}, status=400)

            location = db.location_definitions.find_one({'_id': location_id})
            if not location:
                return JsonResponse({'error': 'Location not found'}, status=404)

            current_images = location.get('location_images', [])

            if image_index < 0 or image_index >= len(current_images):
                return JsonResponse({'error': 'Invalid image index'}, status=400)

            db.location_definitions.update_one(
                {'_id': location_id},
                {'$set': {'primary_image_index': image_index}}
            )

            return JsonResponse({
                'success': True,
                'primary_image_index': image_index
            })

        except Exception as e:
            return JsonResponse({'error': f'Failed to set primary image: {str(e)}'}, status=500)
