"""
Character forms for SkillForge
"""
from django import forms
from .models import Character


# Character trait choices
ATTRIBUTE_CHOICES = [
    ('strength', 'Strength'),
    ('dexterity', 'Dexterity'),
    ('constitution', 'Constitution'),
    ('intelligence', 'Intelligence'),
    ('wisdom', 'Wisdom'),
    ('charisma', 'Charisma'),
    ('perception', 'Perception'),
    ('endurance', 'Endurance'),
    ('agility', 'Agility'),
    ('luck', 'Luck'),
]

SKILL_CHOICES = [
    ('archery', 'Archery'),
    ('swordsmanship', 'Swordsmanship'),
    ('magic', 'Magic'),
    ('stealth', 'Stealth'),
    ('lockpicking', 'Lockpicking'),
    ('persuasion', 'Persuasion'),
    ('intimidation', 'Intimidation'),
    ('medicine', 'Medicine'),
    ('survival', 'Survival'),
    ('tracking', 'Tracking'),
    ('crafting', 'Crafting'),
    ('alchemy', 'Alchemy'),
    ('enchanting', 'Enchanting'),
    ('athletics', 'Athletics'),
    ('acrobatics', 'Acrobatics'),
    ('investigation', 'Investigation'),
    ('history', 'History'),
    ('nature', 'Nature'),
    ('religion', 'Religion'),
    ('performance', 'Performance'),
]

PERSONALITY_TRAIT_CHOICES = [
    ('brave', 'Brave'),
    ('cautious', 'Cautious'),
    ('cunning', 'Cunning'),
    ('honorable', 'Honorable'),
    ('compassionate', 'Compassionate'),
    ('ruthless', 'Ruthless'),
    ('wise', 'Wise'),
    ('impulsive', 'Impulsive'),
    ('loyal', 'Loyal'),
    ('ambitious', 'Ambitious'),
    ('humble', 'Humble'),
    ('arrogant', 'Arrogant'),
    ('optimistic', 'Optimistic'),
    ('pessimistic', 'Pessimistic'),
    ('disciplined', 'Disciplined'),
    ('creative', 'Creative'),
    ('analytical', 'Analytical'),
    ('empathetic', 'Empathetic'),
    ('stoic', 'Stoic'),
    ('charismatic', 'Charismatic'),
]

# Voice and Speech choices for TTS/STT
VOICE_TYPE_CHOICES = [
    ('deep', 'Deep'),
    ('high', 'High'),
    ('raspy', 'Raspy'),
    ('smooth', 'Smooth'),
    ('gravelly', 'Gravelly'),
    ('melodic', 'Melodic'),
    ('nasal', 'Nasal'),
    ('booming', 'Booming'),
    ('soft', 'Soft'),
    ('commanding', 'Commanding'),
]

ACCENT_CHOICES = [
    ('none', 'No Accent'),
    # Real World Accents
    ('british', 'British'),
    ('scottish', 'Scottish'),
    ('irish', 'Irish'),
    ('french', 'French'),
    ('german', 'German'),
    ('italian', 'Italian'),
    ('spanish', 'Spanish'),
    ('russian', 'Russian'),
    ('australian', 'Australian'),
    ('southern_us', 'Southern US'),
    ('new_york', 'New York'),
    ('texan', 'Texan'),
    ('caribbean', 'Caribbean'),
    ('indian', 'Indian'),
    ('south_african', 'South African'),
    # Fantasy Accents
    ('fantasy_elvish', 'Elvish'),
    ('fantasy_dwarven', 'Dwarven'),
    ('fantasy_orcish', 'Orcish'),
    ('fantasy_fae', 'Fae/Sylvan'),
    # Sci-Fi Accents
    ('scifi_synthetic', 'Synthetic/Robotic'),
    ('scifi_alien', 'Alien/Xenomorph'),
    ('scifi_cyborg', 'Cyborg/Augmented'),
    ('scifi_space_station', 'Space Station Dialect'),
]

SPEAKING_PATTERN_CHOICES = [
    ('formal', 'Formal/Eloquent'),
    ('casual', 'Casual'),
    ('stutters', 'Stutters'),
    ('slow_deliberate', 'Slow and Deliberate'),
    ('fast_excited', 'Fast and Excited'),
    ('whispers', 'Whispers Often'),
    ('loud_boisterous', 'Loud and Boisterous'),
    ('sarcastic', 'Sarcastic'),
    ('poetic', 'Poetic/Flowery'),
    ('blunt_direct', 'Blunt and Direct'),
    ('uses_slang', 'Uses Slang'),
    ('archaic_speech', 'Archaic/Old-fashioned'),
]

LANGUAGE_CHOICES = [
    # Fantasy Languages
    ('common', 'Common'),
    ('elvish', 'Elvish'),
    ('dwarvish', 'Dwarvish'),
    ('orcish', 'Orcish'),
    ('draconic', 'Draconic'),
    ('infernal', 'Infernal'),
    ('celestial', 'Celestial'),
    ('sylvan', 'Sylvan'),
    ('undercommon', 'Undercommon'),
    ('giant', 'Giant'),
    ('gnomish', 'Gnomish'),
    ('halfling', 'Halfling'),
    # Sci-Fi Languages
    ('galactic_standard', 'Galactic Standard'),
    ('binary', 'Binary/Machine Code'),
    ('alien_xenomorph', 'Xenomorph'),
    ('android_protocol', 'Android Protocol'),
    ('telepathic', 'Telepathic'),
    # Real World Languages
    ('english', 'English'),
    ('spanish', 'Spanish'),
    ('mandarin', 'Mandarin'),
    ('french', 'French'),
    ('german', 'German'),
    ('japanese', 'Japanese'),
    ('russian', 'Russian'),
    ('arabic', 'Arabic'),
]


class CharacterForm(forms.ModelForm):
    """Form for creating and editing characters"""

    # Multi-select fields for traits
    attributes = forms.MultipleChoiceField(
        choices=ATTRIBUTE_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Select character attributes"
    )

    skills = forms.MultipleChoiceField(
        choices=SKILL_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Select character skills"
    )

    personality_traits = forms.MultipleChoiceField(
        choices=PERSONALITY_TRAIT_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Select personality traits"
    )

    # Voice and Speech fields
    voice_type = forms.ChoiceField(
        choices=[('', '-- Select Voice Type --')] + VOICE_TYPE_CHOICES,
        required=False,
        help_text="Character's voice quality"
    )

    accent = forms.ChoiceField(
        choices=[('', '-- Select Accent --')] + ACCENT_CHOICES,
        required=False,
        help_text="Character's accent"
    )

    speaking_patterns = forms.MultipleChoiceField(
        choices=SPEAKING_PATTERN_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="How the character speaks"
    )

    languages = forms.MultipleChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        help_text="Languages the character can speak"
    )

    speech_quirks = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'materialize-textarea', 'rows': 2}),
        required=False,
        help_text="Unique phrases, catchphrases, or speech mannerisms"
    )

    class Meta:
        model = Character
        fields = [
            'name',
            'title',
            'description',
            'age',
            'height',
            'appearance',
            'attributes',
            'skills',
            'personality_traits',
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

        # Populate multi-select fields from model JSON data
        if self.instance and self.instance.pk:
            # Convert attributes dict keys to list for multi-select
            if isinstance(self.instance.attributes, dict):
                self.initial['attributes'] = list(self.instance.attributes.keys())

            # Skills is already a list
            if isinstance(self.instance.skills, list):
                self.initial['skills'] = self.instance.skills

            # Personality traits is already a list
            if isinstance(self.instance.personality_traits, list):
                self.initial['personality_traits'] = self.instance.personality_traits

            # Voice profile fields
            if isinstance(self.instance.voice_profile, dict):
                self.initial['voice_type'] = self.instance.voice_profile.get('voice_type', '')
                self.initial['accent'] = self.instance.voice_profile.get('accent', '')
                self.initial['speaking_patterns'] = self.instance.voice_profile.get('speaking_patterns', [])
                self.initial['languages'] = self.instance.voice_profile.get('languages', [])
                self.initial['speech_quirks'] = self.instance.voice_profile.get('speech_quirks', '')

    def save(self, commit=True):
        character = super().save(commit=False)
        if self.player_id:
            character.player_id = self.player_id

        # Save multi-select fields to JSON
        # Attributes: store as dict with selected attributes as keys
        selected_attributes = self.cleaned_data.get('attributes', [])
        character.attributes = {attr: {} for attr in selected_attributes}

        # Skills: store as list
        character.skills = self.cleaned_data.get('skills', [])

        # Personality traits: store as list
        character.personality_traits = self.cleaned_data.get('personality_traits', [])

        # Save voice profile to JSON
        character.voice_profile = {
            'voice_type': self.cleaned_data.get('voice_type', ''),
            'accent': self.cleaned_data.get('accent', ''),
            'speaking_patterns': self.cleaned_data.get('speaking_patterns', []),
            'languages': self.cleaned_data.get('languages', []),
            'speech_quirks': self.cleaned_data.get('speech_quirks', '')
        }

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
