"""
Player Profile models for SkillForge
Player preferences and gaming configuration
"""
import uuid
from django.db import models


class PlayerProfile(models.Model):
    """Player Profile - captures gaming preferences and play style"""
    profile_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_id = models.UUIDField(unique=True)  # One profile per player

    # Favorite Genres (multi-select stored as JSON)
    favorite_genres = models.JSONField(
        default=list,
        help_text="Preferred game genres: Fantasy, Sci-Fi, Horror, Mystery, Adventure, Historical"
    )

    # Session Duration Preference
    SESSION_DURATION_CHOICES = [
        ('quick', 'Quick (15-30 minutes)'),
        ('standard', 'Standard (30-60 minutes)'),
        ('extended', 'Extended (60+ minutes)'),
    ]
    session_duration = models.CharField(
        max_length=20,
        choices=SESSION_DURATION_CHOICES,
        default='standard'
    )

    # Universe Preferences (stored as JSON array of universe IDs)
    preferred_universes = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="List of preferred universe IDs"
    )

    # Play Style
    PLAY_STYLE_CHOICES = [
        ('combat', 'Combat-focused'),
        ('story', 'Story-driven'),
        ('puzzle', 'Puzzle-solving'),
        ('social', 'Social interaction'),
        ('exploration', 'Exploration'),
        ('balanced', 'Balanced'),
    ]
    play_style = models.CharField(
        max_length=20,
        choices=PLAY_STYLE_CHOICES,
        default='balanced'
    )

    # Difficulty Preference
    DIFFICULTY_CHOICES = [
        ('casual', 'Casual'),
        ('balanced', 'Balanced'),
        ('challenging', 'Challenging'),
        ('expert', 'Expert'),
    ]
    difficulty_preference = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='balanced'
    )

    # Content Maturity (auto-calculated from player age but can be overridden)
    CONTENT_MATURITY_CHOICES = [
        ('everyone', 'Everyone (E)'),
        ('everyone_10', 'Everyone 10+ (E10+)'),
        ('teen', 'Teen (T)'),
        ('mature', 'Mature 17+ (M)'),
        ('adults_only', 'Adults Only 18+ (AO)'),
    ]
    content_maturity = models.CharField(
        max_length=20,
        choices=CONTENT_MATURITY_CHOICES,
        default='everyone'
    )

    # AI Guidance Level
    AI_GUIDANCE_CHOICES = [
        ('minimal', 'Minimal hints'),
        ('moderate', 'Moderate guidance'),
        ('full', 'Full assistance'),
    ]
    ai_guidance_level = models.CharField(
        max_length=20,
        choices=AI_GUIDANCE_CHOICES,
        default='moderate'
    )

    # Narrative Depth
    NARRATIVE_DEPTH_CHOICES = [
        ('light', 'Light storytelling'),
        ('rich', 'Rich narrative'),
        ('deep', 'Deep lore exploration'),
    ]
    narrative_depth = models.CharField(
        max_length=20,
        choices=NARRATIVE_DEPTH_CHOICES,
        default='rich'
    )

    # Additional Preferences
    enable_voice_narration = models.BooleanField(default=False)
    enable_background_music = models.BooleanField(default=True)
    enable_sound_effects = models.BooleanField(default=True)
    enable_auto_save = models.BooleanField(default=True)

    # Accessibility Options
    text_size = models.CharField(
        max_length=20,
        choices=[
            ('small', 'Small'),
            ('medium', 'Medium'),
            ('large', 'Large'),
            ('extra_large', 'Extra Large'),
        ],
        default='medium'
    )
    high_contrast_mode = models.BooleanField(default=False)
    reduce_motion = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'player_profiles'
        managed = False  # Don't let Django manage this table

    def __str__(self):
        return f"Profile for Player {self.player_id}"
