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
    email = models.EmailField(null=True, blank=True)
    date_of_birth = models.DateField()

    # Primary player flag
    is_primary = models.BooleanField(default=False, help_text="Primary players can manage account and other players")

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
    content_restriction_level = models.CharField(max_length=20, default='automatic')
    allowed_universes = models.JSONField(null=True, blank=True)
    blocked_universes = models.JSONField(null=True, blank=True)

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
