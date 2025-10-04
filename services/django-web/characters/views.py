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
from .models import Character
from .forms import CharacterForm
from members.models import Player


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
            # Use description to generate backstory
            description = character.description or character.name

            # Call Claude API
            from anthropic import Anthropic
            client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

            prompt = f"""Generate a compelling character backstory for an RPG character with the following details:

Name: {character.name}
{f'Title: {character.title}' if character.title else ''}
Description: {description}
{f'Age: {character.age}' if character.age else ''}
{f'Height: {character.height}' if character.height else ''}
{f'Appearance: {character.appearance}' if character.appearance else ''}

Create a rich, detailed backstory (2-3 paragraphs) that:
1. Explores their origins and early life
2. Explains how they became who they are today
3. Hints at their motivations and goals
4. Includes interesting personality traits and quirks
5. Is appropriate for a fantasy/RPG setting

Make it engaging and memorable."""

            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            backstory = message.content[0].text

            return JsonResponse({
                'success': True,
                'backstory': backstory
            })

        except Exception as e:
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
    """Generate AI image for character"""

    def post(self, request, character_id):
        character = get_object_or_404(Character, character_id=character_id)

        try:
            # Check if already at max images (4)
            if len(character.images) >= 4:
                return JsonResponse({
                    'success': False,
                    'error': 'Maximum of 4 images reached. Delete an image to generate a new one.'
                }, status=400)

            # Build image prompt from character details
            prompt_parts = [f"A fantasy RPG character portrait of {character.name}"]
            if character.title:
                prompt_parts.append(f"known as '{character.title}'")
            if character.appearance:
                prompt_parts.append(f"Physical appearance: {character.appearance}")
            if character.age:
                prompt_parts.append(f"Age: {character.age}")

            prompt = ". ".join(prompt_parts) + ". High quality, detailed fantasy art style."

            # Generate image using Anthropic (placeholder - would use actual image generation service)
            # For now, return a placeholder
            image_url = f"https://via.placeholder.com/512x512.png?text={character.name}"

            # Add to images list
            images = character.images or []
            images.append(image_url)
            character.images = images
            character.save()

            return JsonResponse({
                'success': True,
                'image_url': image_url,
                'image_index': len(images) - 1
            })

        except Exception as e:
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
