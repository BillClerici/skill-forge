"""
Forms for Player Profile (Character) configuration
"""
from django import forms
from .models_profile import PlayerProfile


class PlayerProfileForm(forms.ModelForm):
    """Form for creating/editing player character profiles"""

    class Meta:
        model = PlayerProfile
        fields = [
            'player_id',
            'character_name',
            'universe_id',
            'world_id',
            'archetype',
            'appearance_data',
            'portrait_url',
        ]
        widgets = {
            'character_name': forms.TextInput(attrs={'placeholder': 'Enter character name'}),
            'archetype': forms.TextInput(attrs={'placeholder': 'e.g., Warrior, Mage, Rogue'}),
            'portrait_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'appearance_data': forms.Textarea(attrs={'rows': 4, 'placeholder': 'JSON appearance data'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.URLInput, forms.Textarea)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' validate'
