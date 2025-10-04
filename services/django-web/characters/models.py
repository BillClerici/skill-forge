"""
Character models for SkillForge
Characters are created by Players and interact with the game world
"""
import uuid
from django.db import models


class Character(models.Model):
    """Character model - player-created characters for gameplay"""
    character_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_id = models.UUIDField()  # Player who created this character

    # Basic Identity
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=200, null=True, blank=True, help_text="e.g., 'The Brave', 'Shadow Walker'")

    # Character Profile/Backstory
    description = models.TextField(null=True, blank=True, help_text="Brief description used for AI backstory generation")
    backstory = models.TextField(null=True, blank=True)
    personality_traits = models.JSONField(
        default=list,
        help_text="List of personality traits: brave, cunning, wise, etc."
    )

    # Personal Evolution Arc (Bloom's Taxonomy Skill Level)
    BLOOMS_LEVEL_CHOICES = [
        ('remembering', 'Novice - Recall facts and basic concepts'),
        ('understanding', 'Apprentice - Explain ideas or concepts'),
        ('applying', 'Journeyman - Use information in new situations'),
        ('analyzing', 'Expert - Draw connections among ideas'),
        ('evaluating', 'Master - Justify a stand or decision'),
        ('creating', 'Grandmaster - Produce new or original work'),
    ]
    blooms_level = models.CharField(
        max_length=20,
        choices=BLOOMS_LEVEL_CHOICES,
        default='remembering',
        help_text="Character's Personal Evolution Arc level"
    )

    # Physical Characteristics
    age = models.IntegerField(null=True, blank=True)
    height = models.CharField(max_length=50, null=True, blank=True, help_text="e.g., '6 feet', '1.8 meters'")
    appearance = models.TextField(null=True, blank=True, help_text="Physical description")

    # Game Mechanics
    level = models.IntegerField(default=1)
    experience_points = models.IntegerField(default=0)

    # Stats (stored as JSON for flexibility)
    attributes = models.JSONField(
        default=dict,
        help_text="Character attributes: strength, dexterity, intelligence, wisdom, etc."
    )

    skills = models.JSONField(
        default=list,
        help_text="List of character skills"
    )

    inventory = models.JSONField(
        default=list,
        help_text="Character's inventory items"
    )

    # Voice and Speech Profile (for TTS/STT)
    voice_profile = models.JSONField(
        default=dict,
        help_text="Voice characteristics, accent, speaking patterns, and language proficiencies"
    )

    # Character Images (up to 4 AI-generated images)
    images = models.JSONField(
        default=list,
        help_text="List of image URLs for this character (max 4)"
    )
    primary_image_index = models.IntegerField(
        default=0,
        help_text="Index of the primary image in the images list"
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_alive = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_played = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'characters'
        managed = False  # Don't let Django manage this table

    def __str__(self):
        if self.title:
            return f"{self.name} {self.title}"
        return self.name

    @property
    def full_name(self):
        """Get character's full name with title"""
        if self.title:
            return f"{self.name} {self.title}"
        return self.name
