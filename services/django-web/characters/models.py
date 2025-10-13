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

    # Personal Evolution Arc (Meta-Cognitive Development & Integrated Wisdom)
    BLOOMS_LEVEL_CHOICES = [
        ('remembering', 'Novice - Developing awareness across multiple dimensions'),
        ('understanding', 'Apprentice - Understanding connections between growth areas'),
        ('applying', 'Journeyman - Applying integrated knowledge across domains'),
        ('analyzing', 'Expert - Analyzing patterns across all dimensions'),
        ('evaluating', 'Master - Evaluating holistic development with wisdom'),
        ('creating', 'Grandmaster - Creating transformative synthesis and original frameworks'),
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

    # Dimensional Maturity (7 dimensions × 6 Bloom's levels)
    dimensional_maturity = models.JSONField(
        default=dict,
        help_text="7-dimension maturity tracking: Physical, Emotional, Intellectual, Social, Spiritual, Vocational, Environmental"
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

    # Bloom's Level Mapping
    BLOOMS_FRIENDLY_NAMES = {
        1: "Novice",
        2: "Apprentice",
        3: "Journeyman",
        4: "Expert",
        5: "Master",
        6: "Grandmaster"
    }

    BLOOMS_TAXONOMY_LEVELS = {
        1: "Remember",
        2: "Understand",
        3: "Apply",
        4: "Analyze",
        5: "Evaluate",
        6: "Create"
    }

    DIMENSION_NAMES = [
        "physical",
        "emotional",
        "intellectual",
        "social",
        "spiritual",
        "vocational",
        "environmental"
    ]

    @staticmethod
    def get_default_dimensional_maturity():
        """Default dimensional maturity for new characters (all at level 1)"""
        return {
            "physical": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "emotional": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "intellectual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "social": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "spiritual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "vocational": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
            "environmental": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100}
        }

    @property
    def dimensional_profile(self):
        """Get formatted dimensional maturity profile"""
        if not self.dimensional_maturity:
            maturity = self.get_default_dimensional_maturity()
        else:
            # Ensure all dimensions exist
            default = self.get_default_dimensional_maturity()
            maturity = {**default, **self.dimensional_maturity}

        profile = {}
        for dimension, data in maturity.items():
            current_level = data.get("current_level", 1)
            exp = data.get("experience_points", 0)
            next_threshold = data.get("next_level_threshold", 100)

            profile[dimension] = {
                "current_level": current_level,
                "bloom_level": data.get("bloom_level", self.BLOOMS_TAXONOMY_LEVELS[current_level]),
                "friendly_name": self.BLOOMS_FRIENDLY_NAMES[current_level],
                "experience_points": exp,
                "next_level_threshold": next_threshold,
                "progress_percentage": int((exp / next_threshold) * 100) if next_threshold > 0 else 100,
                "color": self.get_dimension_color(current_level),
                "description": self.get_dimension_description(dimension)
            }
        return profile

    @staticmethod
    def get_dimension_color(level):
        """Return color based on Bloom's level (1-6)"""
        colors = {
            1: "#9e9e9e",  # Gray - Novice (Remember)
            2: "#2196f3",  # Blue - Apprentice (Understand)
            3: "#4caf50",  # Green - Journeyman (Apply)
            4: "#ff9800",  # Orange - Expert (Analyze)
            5: "#9c27b0",  # Purple - Master (Evaluate)
            6: "#f44336"   # Red - Grandmaster (Create)
        }
        return colors.get(level, "#9e9e9e")

    @staticmethod
    def get_dimension_description(dimension):
        """Get description for each of the 7 dimensions"""
        descriptions = {
            "physical": "Physical development, health, coordination, and bodily mastery",
            "emotional": "Emotional intelligence, self-regulation, and affective awareness",
            "intellectual": "Cognitive abilities, critical thinking, and knowledge acquisition",
            "social": "Interpersonal skills, collaboration, and community engagement",
            "spiritual": "Values, purpose, ethics, and connection to something greater",
            "vocational": "Skills, competencies, and capabilities for meaningful work",
            "environmental": "Awareness and stewardship of surroundings and nature"
        }
        return descriptions.get(dimension, "")
