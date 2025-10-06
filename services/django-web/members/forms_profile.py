"""
Forms for Player Profile configuration
This form is for player preferences, not character profiles
"""
from django import forms
from .models import Player


class PlayerProfileForm(forms.ModelForm):
    """Form for configuring player preferences and settings"""

    # Custom fields for universe management
    allowed_universes_list = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Allowed Universes',
        help_text='Select universes this player can access (if Custom is selected)'
    )

    blocked_universes_list = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Blocked Universes',
        help_text='Select universes this player cannot access (if Custom is selected)'
    )

    class Meta:
        model = Player
        fields = [
            'content_restriction_level',
            'daily_time_limit_minutes',
            'weekday_time_limit_minutes',
            'weekend_time_limit_minutes',
            'quiet_hours_start',
            'quiet_hours_end',
            'can_play_with_family',
            'can_play_with_friends',
            'can_play_with_strangers',
            'friend_requests_require_approval',
            'can_chat_in_family_campaigns',
            'can_chat_with_friends',
            'can_chat_with_strangers',
            'parent_email_for_notifications',
        ]
        widgets = {
            'content_restriction_level': forms.Select(),
            'daily_time_limit_minutes': forms.NumberInput(attrs={'min': '0', 'step': '15'}),
            'weekday_time_limit_minutes': forms.NumberInput(attrs={'min': '0', 'step': '15'}),
            'weekend_time_limit_minutes': forms.NumberInput(attrs={'min': '0', 'step': '15'}),
            'quiet_hours_start': forms.TimeInput(attrs={'type': 'time'}),
            'quiet_hours_end': forms.TimeInput(attrs={'type': 'time'}),
            'parent_email_for_notifications': forms.EmailInput(),
        }
        labels = {
            'content_restriction_level': 'Content Restriction Level',
            'daily_time_limit_minutes': 'Daily Time Limit (minutes)',
            'weekday_time_limit_minutes': 'Weekday Time Limit (minutes)',
            'weekend_time_limit_minutes': 'Weekend Time Limit (minutes)',
            'quiet_hours_start': 'Quiet Hours Start',
            'quiet_hours_end': 'Quiet Hours End',
            'can_play_with_family': 'Can Play with Family',
            'can_play_with_friends': 'Can Play with Friends',
            'can_play_with_strangers': 'Can Play with Strangers',
            'friend_requests_require_approval': 'Friend Requests Require Approval',
            'can_chat_in_family_campaigns': 'Can Chat in Family Campaigns',
            'can_chat_with_friends': 'Can Chat with Friends',
            'can_chat_with_strangers': 'Can Chat with Strangers',
            'parent_email_for_notifications': 'Parent Email for Notifications',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add help text
        self.fields['content_restriction_level'].help_text = 'Automatic uses age-based content filtering. Custom allows manual universe selection.'
        self.fields['daily_time_limit_minutes'].help_text = 'Leave blank for no limit'
        self.fields['quiet_hours_start'].help_text = 'Time when player cannot log in (optional)'
        self.fields['quiet_hours_end'].help_text = 'Time when quiet hours end (optional)'

        # Get universes from MongoDB
        from pymongo import MongoClient
        import os

        MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
        mongo_client = MongoClient(MONGODB_URL)
        db = mongo_client['skillforge']

        universe_docs = db.universe_definitions.find({}, {'_id': 1, 'universe_name': 1}).sort('universe_name', 1)
        universes = [(str(doc['_id']), doc['universe_name']) for doc in universe_docs]

        mongo_client.close()

        self.fields['allowed_universes_list'].choices = universes
        self.fields['blocked_universes_list'].choices = universes

        # Pre-populate with existing values
        if self.instance and self.instance.pk:
            if self.instance.allowed_universes:
                self.fields['allowed_universes_list'].initial = [str(uid) for uid in self.instance.allowed_universes]
            if self.instance.blocked_universes:
                self.fields['blocked_universes_list'].initial = [str(uid) for uid in self.instance.blocked_universes]

    def clean(self):
        cleaned_data = super().clean()
        allowed = set(cleaned_data.get('allowed_universes_list', []))
        blocked = set(cleaned_data.get('blocked_universes_list', []))

        # Check for overlap between allowed and blocked
        overlap = allowed & blocked
        if overlap:
            # Get universe names for error message
            from pymongo import MongoClient
            import os

            MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
            mongo_client = MongoClient(MONGODB_URL)
            db = mongo_client['skillforge']

            overlapping_names = []
            for universe_id in overlap:
                universe = db.universe_definitions.find_one({'_id': universe_id})
                if universe:
                    overlapping_names.append(universe['universe_name'])

            mongo_client.close()

            error_msg = f"The following universe(s) cannot be in both Allowed and Blocked lists: {', '.join(overlapping_names)}"
            raise forms.ValidationError(error_msg)

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Convert universe lists to JSON arrays
        allowed = self.cleaned_data.get('allowed_universes_list', [])
        blocked = self.cleaned_data.get('blocked_universes_list', [])

        instance.allowed_universes = allowed if allowed else None
        instance.blocked_universes = blocked if blocked else None

        if commit:
            instance.save()
        return instance
