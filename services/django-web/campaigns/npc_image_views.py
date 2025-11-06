"""
NPC Image Generation Views
Handles full-body and avatar/bust image generation for NPCs
Also handles AI-powered regeneration of NPC descriptions
"""
import json
import logging
import os
import uuid
import urllib.request
from pathlib import Path
from django.views import View
from django.http import JsonResponse
from django.conf import settings
from pymongo import MongoClient
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# OpenAI client for DALL-E 3 image generation
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = None
if openai_api_key:
    from openai import OpenAI
    openai_client = OpenAI(api_key=openai_api_key)

# Anthropic client for AI generation
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))


class NPCGenerateImageView(View):
    """Generate full-body or avatar image for an NPC using DALL-E 3"""

    def post(self, request, campaign_id, npc_id):
        if not openai_client:
            return JsonResponse({'error': 'OpenAI API key not configured'}, status=500)

        try:
            data = json.loads(request.body)
            image_type = data.get('image_type', 'full_body')  # 'full_body' or 'avatar'

            # Get NPC data
            npc = db.npcs.find_one({'_id': npc_id})
            if not npc:
                return JsonResponse({'error': 'NPC not found'}, status=404)

            # Check existing images count
            current_images = npc.get('images', {}).get(image_type, [])
            if len(current_images) >= 4:
                return JsonResponse({'error': f'Already have 4 {image_type} images. Delete some first to generate more.'}, status=400)

            # Build prompt from NPC data
            name = npc.get('name', 'Character')
            species = npc.get('species_name', 'humanoid')
            role = npc.get('role', 'character')
            description = npc.get('description', '')
            personality_traits = npc.get('personality_traits', [])
            archetype = npc.get('archetype', 'neutral')

            # Use only safe, descriptive fields - avoid backstory which may contain policy-violating content
            # Focus on visual appearance and role
            char_description = description if description else f"A {species} character with a {role} role"

            # Check for existing image of the opposite type to use as reference
            reference_image_description = ""
            opposite_type = 'full_body' if image_type == 'avatar' else 'avatar'
            existing_opposite_images = npc.get('images', {}).get(opposite_type, [])

            if existing_opposite_images:
                # We have an existing image of the opposite type - use it as reference
                reference_image_url = existing_opposite_images[0]['url']

                # Convert relative path to absolute local path for Vision API
                if reference_image_url.startswith('/media/'):
                    reference_image_path = Path(settings.MEDIA_ROOT) / reference_image_url.replace('/media/', '')

                    if reference_image_path.exists():
                        try:
                            # Use GPT-4 Vision to analyze the existing image
                            import base64
                            with open(reference_image_path, 'rb') as img_file:
                                base64_image = base64.b64encode(img_file.read()).decode('utf-8')

                            vision_response = openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "Describe this character's visual appearance in detail for the purpose of generating a consistent matching image. Focus ONLY on: facial features (eyes, nose, mouth, face shape, skin tone), hair (color, style, length), distinctive features (scars, tattoos, markings), clothing style and colors, overall aesthetic. Be specific and concise. Maximum 150 words."
                                            },
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": f"data:image/png;base64,{base64_image}"
                                                }
                                            }
                                        ]
                                    }
                                ],
                                max_tokens=300
                            )

                            reference_image_description = vision_response.choices[0].message.content
                            logger.info(f"Extracted visual reference from existing {opposite_type} image: {reference_image_description[:100]}...")

                        except Exception as e:
                            logger.warning(f"Could not analyze reference image: {e}")
                            reference_image_description = ""

            # CRITICAL: No text requirements - must be extremely explicit
            no_text_requirements = """
CRITICAL REQUIREMENT - ABSOLUTELY NO TEXT OR SYMBOLS:
- ZERO text of any kind - no words, letters, numbers, runes, glyphs, or writing systems
- NO symbols, signs, emblems, crests, or heraldic marks
- NO banners, flags, shop signs, labels, or inscriptions
- NO book text, scroll writing, tattoos with text, or magical symbols
- NO UI elements, watermarks, signatures, or captions
- If it looks like it could be text or a symbol, DO NOT include it
- Pure visual imagery ONLY - this is mandatory and non-negotiable
"""

            # Build safe, generic prompt based on image type
            # Keep prompts simple to avoid content policy violations
            personality_str = ', '.join(personality_traits[:3]) if personality_traits else 'confident and capable'

            # Add reference consistency instruction if we have a reference image
            consistency_instruction = ""
            if reference_image_description:
                consistency_instruction = f"""

CRITICAL - VISUAL CONSISTENCY REQUIREMENT:
This character MUST match the following existing appearance exactly:
{reference_image_description}

Maintain perfect consistency with these visual details - same face, same hair, same features, same clothing style and colors."""

            if image_type == 'avatar':
                base_prompt = f"""Fantasy RPG character portrait: a {species} {role} character.
{char_description[:200]}{consistency_instruction}
{no_text_requirements}

FRAMING REQUIREMENTS:
- Professional character portrait, head and shoulders view
- Detailed facial features and expressions
- Clear, focused composition
- NO text, symbols, or writing anywhere in the image

Art style: Clean fantasy character portrait with detailed facial features.
Character traits: {personality_str}
Archetype: {archetype}

Fantasy character illustration with clear facial details and distinctive appearance. REMEMBER: Absolutely no text or symbols of any kind."""
            else:  # full_body
                base_prompt = f"""CRITICAL: Generate EXACTLY ONE character. NOT two, NOT three, NOT multiple figures. ONLY ONE SINGLE CHARACTER.

Fantasy RPG character art: A SINGLE {species} {role} character.
{char_description[:200]}{consistency_instruction}
{no_text_requirements}

ABSOLUTE REQUIREMENTS - THESE ARE MANDATORY:
1. EXACTLY ONE CHARACTER: Show only ONE person/figure in the entire image. Do NOT include multiple copies, versions, or instances of the character.
2. NOT A CHARACTER SHEET: This is NOT a character turnaround or reference sheet. Do NOT show front/side/back views.
3. NOT A LINEUP: Do NOT show multiple figures standing side by side.
4. SINGLE FIGURE ONLY: If you see more than one character appearing, STOP and generate only one.
5. FRONTAL VIEW: One character facing forward toward the viewer
6. FULL BODY VIEW: Show the ENTIRE character from head to toe - head, torso, arms, legs, and feet must ALL be visible
7. STANDING POSE: Character must be standing upright (not sitting, crouching, or lying down)
8. COMPLETE FIGURE: Do NOT crop any part of the body - the full figure must fit in frame
9. VERTICAL COMPOSITION: Use the full vertical space to show the complete standing character
10. NO TEXT OR SYMBOLS: Absolutely no text, writing, symbols, or emblems anywhere in the image

Art style: Single solo character portrait, full body, frontal standing pose, detailed costume and equipment. ONE character ONLY.
Character traits: {personality_str}
Archetype: {archetype}

Generate ONE individual character in frontal standing view, showing their entire body from head to toe. CRITICAL: Only ONE character must appear in the image - not two, not three, ONLY ONE. This is a portrait of a SINGLE individual."""

            full_prompt = base_prompt

            # Generate image with DALL-E 3
            logger.info(f"Generating {image_type} image for NPC: {name}")
            response = openai_client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size="1024x1792" if image_type == 'full_body' else "1024x1024",
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            # Download and save image locally
            media_root = Path(settings.MEDIA_ROOT)
            npc_images_dir = media_root / 'npc_images' / npc_id
            npc_images_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            image_filename = f"{image_type}_{uuid.uuid4().hex[:8]}.png"
            image_path = npc_images_dir / image_filename

            # Download image
            urllib.request.urlretrieve(image_url, str(image_path))

            # Generate relative URL path
            relative_path = f"/media/npc_images/{npc_id}/{image_filename}"

            # Initialize images structure if needed
            if 'images' not in npc:
                npc['images'] = {'full_body': [], 'avatar': []}
            if image_type not in npc['images']:
                npc['images'][image_type] = []

            # Add new image to NPC
            from datetime import datetime
            npc['images'][image_type].append({
                'url': relative_path,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Update MongoDB
            db.npcs.update_one(
                {'_id': npc_id},
                {'$set': {'images': npc['images']}}
            )

            logger.info(f"Successfully generated {image_type} image for NPC {name}: {relative_path}")

            return JsonResponse({
                'success': True,
                'image_url': relative_path,
                'image_type': image_type,
                'message': f'{image_type.replace("_", " ").title()} image generated successfully'
            })

        except Exception as e:
            logger.error(f"Error generating NPC image: {e}", exc_info=True)
            return JsonResponse({'error': f'Image generation failed: {str(e)}'}, status=500)


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
