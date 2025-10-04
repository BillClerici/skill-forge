"""
Forms for Player Profile configuration
"""
from django import forms
from .models_profile import PlayerProfile


class PlayerProfileForm(forms.ModelForm):
    """Form for configuring player profile preferences"""

    # Genre choices as multiple checkboxes
    GENRE_CHOICES = [
        ('fantasy', 'Fantasy'),
        ('scifi', 'Sci-Fi'),
        ('horror', 'Horror'),
        ('mystery', 'Mystery'),
        ('adventure', 'Adventure'),
        ('historical', 'Historical'),
        ('cyberpunk', 'Cyberpunk'),
        ('steampunk', 'Steampunk'),
        ('post_apocalyptic', 'Post-Apocalyptic'),
        ('superhero', 'Superhero'),
    ]

    favorite_genres_field = forms.MultipleChoiceField(
        choices=GENRE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Favorite Genres",
        help_text="Select all genres you enjoy"
    )

    class Meta:
        model = PlayerProfile
        fields = [
            'session_duration',
            'play_style',
            'difficulty_preference',
            'content_maturity',
            'ai_guidance_level',
            'narrative_depth',
            'enable_voice_narration',
            'enable_background_music',
            'enable_sound_effects',
            'enable_auto_save',
            'text_size',
            'high_contrast_mode',
            'reduce_motion',
        ]
        widgets = {
            'session_duration': forms.RadioSelect(),
            'play_style': forms.RadioSelect(),
            'difficulty_preference': forms.RadioSelect(),
            'content_maturity': forms.Select(),
            'ai_guidance_level': forms.RadioSelect(),
            'narrative_depth': forms.RadioSelect(),
            'text_size': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing existing profile, populate genres
        if self.instance and self.instance.pk:
            self.initial['favorite_genres_field'] = self.instance.favorite_genres

        # Add help text
        self.fields['session_duration'].help_text = "How long do you typically play in one session?"
        self.fields['play_style'].help_text = "What type of gameplay do you prefer?"
        self.fields['difficulty_preference'].help_text = "How challenging should the game be?"
        self.fields['content_maturity'].help_text = "Age-appropriate content filtering"
        self.fields['ai_guidance_level'].help_text = "How much help do you want from the AI?"
        self.fields['narrative_depth'].help_text = "How deep should the story be?"

    def clean(self):
        cleaned_data = super().clean()
        # Convert favorite_genres_field to JSON array
        genres = self.cleaned_data.get('favorite_genres_field', [])
        self.instance.favorite_genres = list(genres)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Save the genres from the checkbox field
        instance.favorite_genres = list(self.cleaned_data.get('favorite_genres_field', []))
        if commit:
            instance.save()
        return instance
