"""
NPC Image Generation Views
Handles full-body and avatar/bust image generation for NPCs
Also handles AI-powered regeneration of NPC descriptions
"""
import json
import logging
import httpx
from django.views import View
from django.http import JsonResponse
from pymongo import MongoClient
from anthropic import Anthropic
import os

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Image generation service URL
IMAGE_GEN_URL = os.getenv('IMAGE_GEN_URL', 'http://image-gen:8002')

# Anthropic client for AI generation
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


class NPCGenerateImageView(View):
    """Generate full-body or avatar image for an NPC"""

    def post(self, request, campaign_id, npc_id):
        try:
            data = json.loads(request.body)
            image_type = data.get('image_type', 'full_body')  # 'full_body' or 'avatar'

            # Get NPC data
            npc = db.npcs.find_one({'_id': npc_id})
            if not npc:
                return JsonResponse({'error': 'NPC not found'}, status=404)

            # Build prompt from NPC data
            name = npc.get('name', 'Character')
            species = npc.get('species_name', 'humanoid')
            role = npc.get('role', 'character')
            backstory = npc.get('backstory', '')
            backstory_summary = npc.get('backstory_summary', '')
            personality_traits = npc.get('personality_traits', [])

            # Use backstory or summary for description
            description = backstory if backstory else backstory_summary
            if not description:
                description = f"A {species} who serves as a {role}"

            # Build prompt based on image type
            if image_type == 'avatar':
                prompt = f"""Portrait bust shot of {name}, a {species} {role}.
{description[:500]}

Style: Character portrait, head and shoulders, detailed facial features, professional RPG character art.
Personality: {', '.join(personality_traits[:3]) if personality_traits else 'dignified'}
Focus on facial expression and character details."""
            else:  # full_body
                prompt = f"""Full body character art of {name}, a {species} {role}.
{description[:500]}

Style: Full body RPG character illustration, dynamic pose, detailed costume and equipment.
Personality: {', '.join(personality_traits[:3]) if personality_traits else 'dignified'}
Show complete character from head to toe."""

            # Call image generation service
            timeout = httpx.Timeout(120.0, connect=10.0)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{IMAGE_GEN_URL}/generate",
                    json={
                        'prompt': prompt,
                        'entity_type': 'npc',
                        'entity_id': npc_id,
                        'image_type': image_type,
                        'width': 512 if image_type == 'avatar' else 512,
                        'height': 512 if image_type == 'avatar' else 768
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Image generation failed: {response.text}")
                    return JsonResponse({
                        'error': 'Image generation failed',
                        'details': response.text
                    }, status=500)

                result = response.json()
                image_url = result.get('url')

                if not image_url:
                    return JsonResponse({'error': 'No image URL returned'}, status=500)

                return JsonResponse({
                    'success': True,
                    'image_url': image_url,
                    'image_type': image_type,
                    'message': f'{image_type.replace("_", " ").title()} image generated successfully'
                })

        except httpx.TimeoutException:
            logger.error("Image generation timeout")
            return JsonResponse({'error': 'Image generation timed out. Please try again.'}, status=504)
        except Exception as e:
            logger.error(f"Error generating NPC image: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class NPCSaveImageView(View):
    """Save generated image to NPC document"""

    def post(self, request, campaign_id, npc_id):
        try:
            data = json.loads(request.body)
            image_url = data.get('image_url')
            image_type = data.get('image_type', 'full_body')

            if not image_url:
                return JsonResponse({'error': 'Image URL required'}, status=400)

            # Get NPC
            npc = db.npcs.find_one({'_id': npc_id})
            if not npc:
                return JsonResponse({'error': 'NPC not found'}, status=404)

            # Initialize images array if it doesn't exist
            if 'images' not in npc:
                npc['images'] = {'full_body': [], 'avatar': []}

            # Ensure the structure exists
            if image_type not in npc['images']:
                npc['images'][image_type] = []

            # Add new image
            npc['images'][image_type].append({
                'url': image_url,
                'timestamp': data.get('timestamp')
            })

            # Update MongoDB
            db.npcs.update_one(
                {'_id': npc_id},
                {'$set': {'images': npc['images']}}
            )

            return JsonResponse({
                'success': True,
                'message': f'{image_type.replace("_", " ").title()} image saved successfully'
            })

        except Exception as e:
            logger.error(f"Error saving NPC image: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class NPCDeleteImageView(View):
    """Delete an NPC image"""

    def post(self, request, campaign_id, npc_id):
        try:
            data = json.loads(request.body)
            image_url = data.get('image_url')
            image_type = data.get('image_type', 'full_body')

            if not image_url:
                return JsonResponse({'error': 'Image URL required'}, status=400)

            # Get NPC
            npc = db.npcs.find_one({'_id': npc_id})
            if not npc:
                return JsonResponse({'error': 'NPC not found'}, status=404)

            # Remove image from array
            if 'images' in npc and image_type in npc['images']:
                npc['images'][image_type] = [
                    img for img in npc['images'][image_type]
                    if img['url'] != image_url
                ]

                # Update MongoDB
                db.npcs.update_one(
                    {'_id': npc_id},
                    {'$set': {'images': npc['images']}}
                )

            return JsonResponse({
                'success': True,
                'message': f'{image_type.replace("_", " ").title()} image deleted successfully'
            })

        except Exception as e:
            logger.error(f"Error deleting NPC image: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)


class NPCRegenerateFieldsView(View):
    """Regenerate NPC description, purpose, and backstory using AI"""

    def post(self, request, campaign_id, npc_id):
        try:
            # Get NPC data
            npc = db.npcs.find_one({'_id': npc_id})
            if not npc:
                return JsonResponse({'error': 'NPC not found'}, status=404)

            # Build context from NPC data
            name = npc.get('name', 'Character')
            species = npc.get('species_name', 'humanoid')
            role = npc.get('role', 'character')
            archetype = npc.get('archetype', 'neutral')

            # Get scene/location context if available
            scene_id = npc.get('level_3_location_id') or npc.get('primary_scene_id')
            location_context = ""
            if scene_id:
                scene = db.scenes.find_one({'_id': scene_id})
                if scene:
                    location_context = f"\nLocation: {scene.get('name', 'Unknown')}\nLocation Context: {scene.get('description', '')[:200]}"

            # Create AI prompt using the same structure as campaign generation
            prompt = f"""You are a master NPC designer for RPG games.

Generate compelling narrative content for an existing NPC. Maintain consistency with their established identity while enriching their story.

NPC Identity:
Name: {name}
Species: {species}
Role: {role}
Archetype: {archetype}{location_context}

Generate the following fields as JSON:
{{
  "description": "Brief one-sentence description of the NPC's appearance and demeanor",
  "purpose": "The NPC's function in the campaign narrative (2-3 sentences)",
  "backstory_summary": "One-paragraph summary of their backstory, motivations, and current situation (3-5 sentences)"
}}

Ensure the content is:
- Consistent with their species, role, and archetype
- Appropriate for their location and context
- Rich in narrative detail and personality
- Distinct and memorable

CRITICAL: Return ONLY the JSON object, no other text."""

            # Call Anthropic API
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                temperature=0.8,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            result = json.loads(response_text)

            return JsonResponse({
                'success': True,
                'description': result.get('description', ''),
                'purpose': result.get('purpose', ''),
                'backstory_summary': result.get('backstory_summary', ''),
                'message': 'NPC fields regenerated successfully'
            })

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in NPC regeneration: {e}\nResponse: {response_text}", exc_info=True)
            return JsonResponse({'error': f'Failed to parse AI response: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"Error regenerating NPC fields: {e}", exc_info=True)
            return JsonResponse({'error': 'Internal server error'}, status=500)
