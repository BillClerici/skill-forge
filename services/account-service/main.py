"""
Account Service - FastAPI Microservice
Handles CRUD operations for accounts and subscriptions
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pydantic import BaseModel, EmailStr
import os

# Database setup
# Note: Using asyncpg driver for async operations
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://skillforge_user:password@localhost:5432/skillforge")
if DATABASE_URL and "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


# SQLAlchemy Models
class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_owner_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    account_type: Mapped[str] = mapped_column(nullable=False)
    subscription_tier: Mapped[Optional[str]] = mapped_column(nullable=True)
    subscription_status: Mapped[str] = mapped_column(nullable=False, default="active")
    billing_cycle: Mapped[Optional[str]] = mapped_column(nullable=True)
    max_members: Mapped[int] = mapped_column(default=1)
    current_member_count: Mapped[int] = mapped_column(default=1)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Schemas
class AccountCreate(BaseModel):
    account_type: str
    subscription_tier: Optional[str] = None
    max_members: int = 1


class AccountUpdate(BaseModel):
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


class AccountResponse(BaseModel):
    account_id: uuid.UUID
    account_type: str
    subscription_tier: Optional[str]
    subscription_status: str
    max_members: int
    current_member_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Dependency for database session
async def get_db():
    async with async_session_maker() as session:
        yield session


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Account Service starting up...")
    yield
    # Shutdown
    print("🛑 Account Service shutting down...")
    await engine.dispose()


# FastAPI app
app = FastAPI(
    title="SkillForge Account Service",
    description="CRUD operations for accounts and subscriptions",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "Account Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "account-service"}


@app.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: AccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new account"""
    try:
        new_account = Account(
            account_type=account_data.account_type,
            subscription_tier=account_data.subscription_tier,
            max_members=account_data.max_members,
            subscription_status="active"
        )

        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        return new_account
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create account: {str(e)}"
        )


@app.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get account by ID"""
    result = await db.execute(
        select(Account).where(Account.account_id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    return account


@app.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all accounts"""
    result = await db.execute(
        select(Account).offset(skip).limit(limit)
    )
    accounts = result.scalars().all()
    return accounts


@app.patch("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    account_update: AccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update account"""
    result = await db.execute(
        select(Account).where(Account.account_id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    # Update fields
    if account_update.subscription_tier is not None:
        account.subscription_tier = account_update.subscription_tier
    if account_update.subscription_status is not None:
        account.subscription_status = account_update.subscription_status

    account.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(account)

    return account


@app.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete account"""
    result = await db.execute(
        select(Account).where(Account.account_id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    await db.delete(account)
    await db.commit()

    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
