"""
Character views for SkillForge
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import DetailView
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import os
import httpx
from .models import Character
from .forms import CharacterForm
from members.models import Player

ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://agent-orchestrator:9000')


class CharacterCreateView(View):
    """View for creating a new character"""

    def get(self, request, player_id):
        # Verify player exists
        player = get_object_or_404(Player, player_id=player_id)

        form = CharacterForm(player_id=player_id)
        context = {
            'form': form,
            'player': player,
            'page_title': 'Create Character'
        }
        return render(request, 'characters/character_form.html', context)

    def post(self, request, player_id):
        # Verify player exists
        player = get_object_or_404(Player, player_id=player_id)

        form = CharacterForm(request.POST, player_id=player_id)
        if form.is_valid():
            character = form.save()
            messages.success(request, f'Character "{character.name}" created successfully!')
            return redirect('player_detail', player_id=player_id)
        else:
            messages.error(request, 'Please correct the errors below.')

        context = {
            'form': form,
            'player': player,
            'page_title': 'Create Character'
        }
        return render(request, 'characters/character_form.html', context)


class CharacterDetailView(DetailView):
    """View for displaying character details"""
    model = Character
    template_name = 'characters/character_detail.html'
    context_object_name = 'character'
    pk_url_kwarg = 'character_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        character = self.get_object()

        # Get player
        try:
            context['player'] = Player.objects.get(player_id=character.player_id)
        except Player.DoesNotExist:
            context['player'] = None

        # Get Neo4j relationships
        from characters.neo4j_utils import get_character_relationships
        context['relationships'] = get_character_relationships(character.character_id)

        return context


class CharacterSheetView(DetailView):
    """View for displaying character sheet"""
    model = Character
    template_name = 'characters/character_sheet.html'
    context_object_name = 'character'
    pk_url_kwarg = 'character_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        character = self.get_object()

        # Get player
        try:
            context['player'] = Player.objects.get(player_id=character.player_id)
        except Player.DoesNotExist:
            context['player'] = None

        return context


class CharacterEditView(View):
    """View for editing an existing character"""

    def get(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)
        player = get_object_or_404(Player, player_id=character.player_id)

        form = CharacterForm(instance=character, player_id=character.player_id)
        context = {
            'form': form,
            'character': character,
            'player': player,
            'page_title': f'Edit {character.name}'
        }
        return render(request, 'characters/character_form.html', context)

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)
        player = get_object_or_404(Player, player_id=character.player_id)

        form = CharacterForm(request.POST, instance=character, player_id=character.player_id)
        if form.is_valid():
            character = form.save()
            messages.success(request, f'Character "{character.name}" updated successfully!')
            return redirect('character_detail', character_id=character.character_id)
        else:
            messages.error(request, 'Please correct the errors below.')

        context = {
            'form': form,
            'character': character,
            'player': player,
            'page_title': f'Edit {character.name}'
        }
        return render(request, 'characters/character_form.html', context)


class CharacterDeleteView(View):
    """View for deleting a character"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)
        player_id = character.player_id
        character_name = character.name

        # Delete from Neo4j
        from characters.neo4j_utils import delete_character_node
        delete_character_node(character_id)

        # Delete from PostgreSQL
        character.delete()

        messages.success(request, f'Character "{character_name}" deleted successfully.')
        return redirect('player_detail', player_id=player_id)


class CharacterGenerateBackstoryView(View):
    """Generate AI backstory for character"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            # Get player for context
            player = get_object_or_404(Player, player_id=character.player_id)

            print(f"DEBUG: Calling orchestrator at {ORCHESTRATOR_URL}/generate-character-backstory")

            # Get attributes, skills, and personality traits
            attributes = list(character.attributes.keys()) if isinstance(character.attributes, dict) else []
            skills = character.skills if isinstance(character.skills, list) else []
            personality_traits = character.personality_traits if isinstance(character.personality_traits, list) else []

            # Get voice profile
            voice_profile = character.voice_profile if isinstance(character.voice_profile, dict) else {}
            voice_type = voice_profile.get('voice_type', '')
            accent = voice_profile.get('accent', '')
            speaking_patterns = voice_profile.get('speaking_patterns', [])
            languages = voice_profile.get('languages', [])
            speech_quirks = voice_profile.get('speech_quirks', '')

            # Call orchestrator to generate backstory
            with httpx.Client() as client:
                response = client.post(
                    f"{ORCHESTRATOR_URL}/generate-character-backstory",
                    json={
                        'character_id': str(character.character_id),
                        'character_name': character.name,
                        'title': character.title or '',
                        'description': character.description or '',
                        'age': str(character.age) if character.age else '',
                        'height': character.height or '',
                        'appearance': character.appearance or '',
                        'blooms_level': character.blooms_level,
                        'player_name': player.display_name,
                        'attributes': attributes,
                        'skills': skills,
                        'personality_traits': personality_traits,
                        'voice_type': voice_type,
                        'accent': accent,
                        'speaking_patterns': speaking_patterns,
                        'languages': languages,
                        'speech_quirks': speech_quirks
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return JsonResponse({
                        'success': True,
                        'backstory': result.get('backstory', '')
                    })
                else:
                    error_detail = f"Orchestrator returned {response.status_code}: {response.text}"
                    print(f"ERROR: {error_detail}")
                    return JsonResponse({
                        'success': False,
                        'error': error_detail
                    }, status=500)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class CharacterSaveBackstoryView(View):
    """Save generated backstory to character"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            data = json.loads(request.body)
            backstory = data.get('backstory', '')

            character.backstory = backstory
            character.save()

            return JsonResponse({
                'success': True,
                'message': 'Backstory saved successfully'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class CharacterGenerateImageView(View):
    """Generate AI image for character using DALL-E 3"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            # Check if already at max images (4)
            current_images = character.images or []
            if len(current_images) >= 4:
                return JsonResponse({
                    'success': False,
                    'error': 'Maximum of 4 images reached. Delete an image to generate a new one.'
                }, status=400)

            # Get player and player profile for preferences
            player = get_object_or_404(Player, player_id=character.player_id)
            from members.models import PlayerProfile
            try:
                player_profile = PlayerProfile.objects.get(player_id=player.player_id)
            except PlayerProfile.DoesNotExist:
                player_profile = None

            # Use OpenAI DALL-E 3 for image generation
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return JsonResponse({
                    'success': False,
                    'error': 'OpenAI API key not configured'
                }, status=500)

            from openai import OpenAI
            import urllib.request
            from pathlib import Path
            from django.conf import settings

            client = OpenAI(api_key=openai_api_key)

            # Build simple, clean prompt focused on character artwork only
            prompt_parts = []

            # Start with basic character description
            if character.appearance:
                prompt_parts.append(character.appearance)
            else:
                prompt_parts.append(f"A fantasy character")

            if character.age:
                prompt_parts.append(f"age {character.age}")

            # Add personality traits for expression/demeanor
            if character.personality_traits and isinstance(character.personality_traits, list):
                # Take up to 3 personality traits for visual representation
                visual_traits = character.personality_traits[:3]
                if visual_traits:
                    traits_str = ", ".join([trait.replace('_', ' ') for trait in visual_traits])
                    prompt_parts.append(f"with {traits_str} demeanor")

            # Add attributes for physical representation
            if character.attributes and isinstance(character.attributes, dict):
                attr_keys = list(character.attributes.keys())
                # Highlight physical attributes
                physical_attrs = [a for a in attr_keys if a in ['strength', 'dexterity', 'agility', 'constitution', 'endurance']]
                if physical_attrs:
                    attrs_str = " and ".join([attr.replace('_', ' ') for attr in physical_attrs[:2]])
                    prompt_parts.append(f"displaying {attrs_str}")

            # Add evolution arc visual descriptor
            arc_descriptors = {
                'remembering': 'novice adventurer with eager expression',
                'understanding': 'growing wisdom in their eyes',
                'applying': 'confident and skilled warrior pose',
                'analyzing': 'wise strategist appearance',
                'evaluating': 'masterful commanding presence',
                'creating': 'legendary grandmaster aura'
            }
            arc_desc = arc_descriptors.get(character.blooms_level, '')
            if arc_desc:
                prompt_parts.append(arc_desc)

            # Add art style based on player preferences
            art_style = "fantasy art style"
            if player_profile:
                if player_profile.play_style == 'narrative':
                    art_style = "cinematic fantasy art"
                elif player_profile.play_style == 'combat':
                    art_style = "dynamic action fantasy art"
                elif player_profile.play_style == 'exploration':
                    art_style = "adventurous fantasy art"
                elif player_profile.play_style == 'puzzle':
                    art_style = "thoughtful fantasy art"

            character_description = ", ".join(prompt_parts)

            full_prompt = f"""A detailed portrait painting of a fantasy character. {character_description}. Professional {art_style}, painterly style, dramatic lighting, detailed facial features. Portrait only, plain background, no text, no UI elements, no character sheet, no stats, no labels."""

            # Generate image using DALL-E 3
            response = client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            # Get the image URL from response
            dalle_image_url = response.data[0].url

            # Download and save the image to media folder
            media_root = Path(settings.MEDIA_ROOT)
            character_images_dir = media_root / 'character_images' / str(character.character_id)
            character_images_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename
            image_count = len(current_images)
            filename = f"character_{character.character_id}_image_{image_count + 1}.png"
            file_path = character_images_dir / filename

            # Download image
            urllib.request.urlretrieve(dalle_image_url, str(file_path))

            # Create media URL
            image_url = f"{settings.MEDIA_URL}character_images/{character.character_id}/{filename}"

            # Add to images list
            images = current_images
            images.append(image_url)
            character.images = images
            character.save()

            return JsonResponse({
                'success': True,
                'image_url': image_url,
                'image_index': len(images) - 1
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class CharacterDeleteImageView(View):
    """Delete character image"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None or image_index < 0 or image_index >= len(character.images):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid image index'
                }, status=400)

            # Remove image
            images = character.images
            images.pop(image_index)
            character.images = images

            # Adjust primary image index if needed
            if character.primary_image_index >= len(images) and len(images) > 0:
                character.primary_image_index = 0
            elif len(images) == 0:
                character.primary_image_index = 0

            character.save()

            return JsonResponse({
                'success': True,
                'message': 'Image deleted successfully'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class CharacterSetPrimaryImageView(View):
    """Set primary image for character"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            data = json.loads(request.body)
            image_index = data.get('image_index')

            if image_index is None or image_index < 0 or image_index >= len(character.images):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid image index'
                }, status=400)

            character.primary_image_index = image_index
            character.save()

            return JsonResponse({
                'success': True,
                'message': 'Primary image set successfully'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
