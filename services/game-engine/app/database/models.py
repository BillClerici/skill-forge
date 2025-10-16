"""
SQLAlchemy Models for PostgreSQL Database Access
Direct access to player and character data
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class Player(Base):
    """Player model - maps to PostgreSQL players table"""
    __tablename__ = 'players'

    player_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), nullable=False)
    display_name = Column(String(100), nullable=False)
    email = Column(String(255))
    role = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_login = Column(DateTime)

    # Relationships
    characters = relationship("Character", back_populates="player")


class Character(Base):
    """Character model - maps to PostgreSQL characters table"""
    __tablename__ = 'characters'

    character_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID(as_uuid=True), ForeignKey('players.player_id'), nullable=False)
    name = Column(String(100), nullable=False)
    title = Column(String(200))
    description = Column(Text)
    backstory = Column(Text)
    personality_traits = Column(JSONB, nullable=False, default=dict)
    blooms_level = Column(String(20), nullable=False)
    age = Column(Integer)
    height = Column(String(50))
    appearance = Column(Text)
    level = Column(Integer, nullable=False, default=1)
    experience_points = Column(Integer, nullable=False, default=0)
    attributes = Column(JSONB, nullable=False, default=dict)
    skills = Column(JSONB, nullable=False, default=dict)
    inventory = Column(JSONB, nullable=False, default=dict)
    voice_profile = Column(JSONB, nullable=False, default=dict)
    images = Column(JSONB, nullable=False, default=dict)
    primary_image_index = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    is_alive = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_played = Column(DateTime)
    dimensional_maturity = Column(JSONB, default={
        "physical": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "emotional": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "intellectual": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "social": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "spiritual": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "vocational": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100},
        "environmental": {"bloom_level": "Remember", "current_level": 1, "experience_points": 0, "next_level_threshold": 100}
    })

    # Relationships
    player = relationship("Player", back_populates="characters")

    def to_dict(self):
        """Convert character to dictionary for game state"""
        return {
            "character_id": str(self.character_id),
            "player_id": str(self.player_id),
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "backstory": self.backstory,
            "personality_traits": self.personality_traits,
            "blooms_level": self.blooms_level,
            "level": self.level,
            "experience_points": self.experience_points,
            "attributes": self.attributes,
            "skills": self.skills,
            "inventory": self.inventory,
            "dimensional_maturity": self.dimensional_maturity,
            "is_active": self.is_active,
            "is_alive": self.is_alive
        }
