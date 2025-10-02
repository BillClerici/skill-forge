"""
Account-related Pydantic models
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .base import AccountTypeEnum, SubscriptionStatusEnum


class AccountBase(BaseModel):
    """Base Account schema"""
    account_type: str = Field(..., description="Type of account")
    subscription_tier: Optional[str] = None
    subscription_status: str = Field(default=SubscriptionStatusEnum.ACTIVE)
    max_members: int = Field(default=1, description="Maximum number of members allowed")


class AccountCreate(AccountBase):
    """Schema for creating a new account"""
    owner_name: str
    owner_email: EmailStr
    owner_date_of_birth: date
    owner_password: str


class AccountUpdate(BaseModel):
    """Schema for updating an account"""
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


class AccountResponse(AccountBase):
    """Schema for account response"""
    account_id: UUID
    account_owner_member_id: Optional[UUID] = None
    current_member_count: int
    stripe_customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountWithMembers(AccountResponse):
    """Account with member details"""
    members: list = Field(default_factory=list)
