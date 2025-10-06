"""
Player models for SkillForge
Using existing PostgreSQL tables with managed=False
"""
import uuid
from django.db import models
from .models_profile import PlayerProfile


class Player(models.Model):
    """Player model - maps to existing players table"""
    player_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.UUIDField()

    # Identity
    display_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, null=True, blank=True)
    date_of_birth = models.DateField()

    # Role & Permissions
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('parent', 'Parent'),
            ('teen', 'Teen'),
            ('child', 'Child'),
            ('student', 'Student'),
            ('employee', 'Employee'),
        ]
    )
    can_manage_account = models.BooleanField(default=False)
    can_manage_players = models.BooleanField(default=False)
    can_view_billing = models.BooleanField(default=False)

    # Content Restrictions
    content_restriction_level = models.CharField(
        max_length=20,
        default='automatic',
        choices=[
            ('automatic', 'Automatic (Age-Based)'),
            ('custom', 'Custom'),
        ]
    )
    allowed_universes = models.JSONField(null=True, blank=True)
    blocked_universes = models.JSONField(null=True, blank=True)

    # Parental Controls
    daily_time_limit_minutes = models.IntegerField(null=True, blank=True)
    weekday_time_limit_minutes = models.IntegerField(null=True, blank=True)
    weekend_time_limit_minutes = models.IntegerField(null=True, blank=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    # Social Settings
    can_play_with_family = models.BooleanField(default=True)
    can_play_with_friends = models.BooleanField(default=False)
    can_play_with_strangers = models.BooleanField(default=False)
    friend_requests_require_approval = models.BooleanField(default=True)
    can_chat_in_family_campaigns = models.BooleanField(default=True)
    can_chat_with_friends = models.BooleanField(default=False)
    can_chat_with_strangers = models.BooleanField(default=False)

    # Parent Monitoring
    parent_can_view_activity = models.BooleanField(default=True)
    send_weekly_report_to_parent = models.BooleanField(default=True)
    notify_parent_on_new_campaign = models.BooleanField(default=True)
    parent_email_for_notifications = models.EmailField(max_length=255, null=True, blank=True)

    # Authentication
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    login_count = models.IntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'players'
        managed = False

    def __str__(self):
        return f"{self.display_name} ({self.role})"

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
