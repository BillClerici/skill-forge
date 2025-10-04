"""
Forms for Account management
"""
from django import forms
from .models import Account
from members.models import Player


class AccountCreateForm(forms.ModelForm):
    """Form for creating a new account with primary player"""

    # Primary Player fields
    primary_player_name = forms.CharField(
        max_length=100,
        required=True,
        label="Primary Player Name",
        help_text="The primary player can manage the account and add/remove other players"
    )
    primary_player_email = forms.EmailField(
        required=False,
        label="Primary Player Email"
    )
    primary_player_dob = forms.DateField(
        required=True,
        label="Primary Player Date of Birth",
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Account
        fields = ['name', 'account_type']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Smith Family Account'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for Materialize
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select, forms.DateInput)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' validate'


class AccountEditForm(forms.ModelForm):
    """Form for editing account details"""

    class Meta:
        model = Account
        fields = ['name', 'account_type', 'max_players']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Smith Family Account'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for Materialize
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' validate'


class PlayerCreateForm(forms.ModelForm):
    """Form for creating a new player on an account"""

    class Meta:
        model = Player
        fields = [
            'display_name', 'email', 'date_of_birth', 'role',
            'is_primary', 'can_manage_account', 'can_manage_players', 'can_view_billing',
            'content_restriction_level'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'display_name': forms.TextInput(attrs={'placeholder': 'Enter player name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'player@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes and help text
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select, forms.DateInput)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' validate'

        # Add help text
        self.fields['is_primary'].help_text = "Primary players can manage the account and add/remove other players"
        self.fields['role'].help_text = "Select the player's role in the account"


class PlayerEditForm(forms.ModelForm):
    """Form for editing an existing player"""

    class Meta:
        model = Player
        fields = [
            'display_name', 'email', 'date_of_birth', 'role',
            'is_primary', 'can_manage_account', 'can_manage_players', 'can_view_billing',
            'content_restriction_level', 'is_active'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'display_name': forms.TextInput(attrs={'placeholder': 'Enter player name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'player@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.Select, forms.DateInput)):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' validate'
