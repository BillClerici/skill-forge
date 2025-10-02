"""
Base models and schemas for SkillForge RPG
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TimestampMixin(BaseModel):
    """Mixin for created_at and updated_at timestamps"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UUIDMixin(BaseModel):
    """Mixin for UUID primary key"""
    id: UUID = Field(description="UUID primary key")


class AccountTypeEnum:
    INDIVIDUAL = "individual"
    FAMILY = "family"
    EDUCATIONAL = "educational"
    ORGANIZATIONAL = "organizational"


class SubscriptionStatusEnum:
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class MemberRoleEnum:
    OWNER = "owner"
    PARENT = "parent"
    TEEN = "teen"
    CHILD = "child"
    STUDENT = "student"
    EMPLOYEE = "employee"


class UniverseTypeEnum:
    CONTENT_RATING = "content_rating"
    AGE_FOCUSED = "age_focused"
    GAMEPLAY_STYLE = "gameplay_style"
    CONTEXT_BASED = "context_based"


class CampaignTypeEnum:
    SOLO = "solo"
    MULTIPLAYER_COOP = "multiplayer_coop"
    FAMILY = "family"
    COMPETITIVE = "competitive"
