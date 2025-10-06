"""
Player Profile models for SkillForge
Character profiles for specific worlds/universes
"""
import uuid
from django.db import models


class PlayerProfile(models.Model):
    """Player Profile - character instances in specific worlds"""
    profile_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_id = models.UUIDField()

    # Character Info
    character_name = models.CharField(max_length=100)
    universe_id = models.UUIDField()
    world_id = models.UUIDField()
    archetype = models.CharField(max_length=100, null=True, blank=True)

    # Appearance
    appearance_data = models.JSONField(null=True, blank=True)
    portrait_url = models.CharField(max_length=500, null=True, blank=True)

    # Progress
    world_knowledge_level = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    discovered_locations = models.JSONField(null=True, blank=True)
    known_npcs = models.JSONField(null=True, blank=True)
    completed_quests = models.JSONField(null=True, blank=True)

    # Stats
    total_playtime_minutes = models.IntegerField(default=0)
    character_level = models.IntegerField(default=1)
    character_achievements = models.JSONField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_played_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'player_profiles'
        managed = False

    def __str__(self):
        return f"{self.character_name} - {self.player_id}"
