"""
Character forms for SkillForge
"""
from django import forms
from .models import Character


class CharacterForm(forms.ModelForm):
    """Form for creating and editing characters"""

    class Meta:
        model = Character
        fields = [
            'name',
            'title',
            'description',
            'age',
            'height',
            'appearance',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter character name',
                'required': True
            }),
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g., The Brave, Shadow Walker'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Brief description of your character (used for AI backstory generation)...',
                'class': 'materialize-textarea',
                'rows': 3
            }),
            'age': forms.NumberInput(attrs={
                'placeholder': 'Character age',
                'min': 0
            }),
            'height': forms.TextInput(attrs={
                'placeholder': 'e.g., 6 feet, 1.8 meters'
            }),
            'appearance': forms.Textarea(attrs={
                'placeholder': 'Describe your character\'s physical appearance...',
                'class': 'materialize-textarea',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        player_id = kwargs.pop('player_id', None)
        super().__init__(*args, **kwargs)
        self.player_id = player_id

    def save(self, commit=True):
        character = super().save(commit=False)
        if self.player_id:
            character.player_id = self.player_id

        if commit:
            character.save()

            # Create Neo4j relationships
            from characters.neo4j_utils import (
                create_character_node,
                create_character_player_relationship
            )

            create_character_node(
                character.character_id,
                character.name,
                character.player_id
            )

            create_character_player_relationship(character.character_id, character.player_id)

        return character
