"""
Player Data MCP Server
Provides secure, structured context to AI agents about players
"""
import os
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Boolean, Date, Time, TIMESTAMP, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
import uuid
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient
import json

# ============================================
# Configuration
# ============================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://skillforge_user:password@postgres:5432/skillforge")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# Replace postgresql:// with postgresql+asyncpg://
if DATABASE_URL and "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Player Data MCP Server",
    description="MCP Server providing player cognitive profiles and context to AI agents",
    version="1.0.0"
)

# ============================================
# Database Models
# ============================================

Base = declarative_base()

class Member(Base):
    __tablename__ = 'members'

    member_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(PGUUID(as_uuid=True), nullable=False)
    display_name = Column(String(100), nullable=False)
    email = Column(String(255))
    date_of_birth = Column(Date)
    role = Column(String(50))
    can_manage_account = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Parental Controls
    daily_time_limit_minutes = Column(Integer)
    quiet_hours_start = Column(Time)
    quiet_hours_end = Column(Time)
    allowed_universes = Column(String)  # JSON string
    can_play_with_strangers = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP, server_default='now()')
    updated_at = Column(TIMESTAMP, server_default='now()', onupdate='now()')

class PlayerProfile(Base):
    __tablename__ = 'player_profiles'

    profile_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(PGUUID(as_uuid=True), nullable=False)
    character_name = Column(String(100), nullable=False)
    universe_id = Column(PGUUID(as_uuid=True))
    world_id = Column(PGUUID(as_uuid=True))
    archetype = Column(String(100))
    appearance_data = Column(String)  # JSON string
    portrait_url = Column(String(500))
    total_playtime_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default='now()')

class MemberCognitiveProgress(Base):
    __tablename__ = 'member_cognitive_progress'

    member_id = Column(PGUUID(as_uuid=True), primary_key=True)

    # Bloom's Taxonomy
    remember_mastered = Column(Boolean, default=False)
    understand_mastered = Column(Boolean, default=False)
    apply_mastered = Column(Boolean, default=False)
    analyze_progress = Column(Numeric(3, 2), default=0.00)
    evaluate_progress = Column(Numeric(3, 2), default=0.00)
    create_progress = Column(Numeric(3, 2), default=0.00)

    # Core Skills (1-10)
    empathy_level = Column(Integer, default=1)
    strategy_level = Column(Integer, default=1)
    creativity_level = Column(Integer, default=1)
    courage_level = Column(Integer, default=1)

    updated_at = Column(TIMESTAMP, server_default='now()', onupdate='now()')

# ============================================
# Database Setup
# ============================================

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Redis client
redis_client: Optional[Redis] = None

# MongoDB client
mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db = None

@app.on_event("startup")
async def startup():
    global redis_client, mongo_client, mongo_db
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client.skillforge

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()
    if mongo_client:
        mongo_client.close()

# ============================================
# Authentication
# ============================================

async def verify_mcp_token(authorization: str = Header(None)):
    """Verify MCP authentication token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.replace("Bearer ", "")

    if token != MCP_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid MCP token")

    return token

# ============================================
# Response Models
# ============================================

class CognitiveProfile(BaseModel):
    member_id: UUID
    display_name: str
    age: Optional[int]
    role: str

    # Bloom's Taxonomy
    remember_mastered: bool
    understand_mastered: bool
    apply_mastered: bool
    analyze_progress: float
    evaluate_progress: float
    create_progress: float
    current_bloom_tier: str

    # Core Skills
    empathy_level: int
    strategy_level: int
    creativity_level: int
    courage_level: int

    # Metadata
    total_playtime_minutes: int
    character_count: int

class CharacterInfo(BaseModel):
    profile_id: UUID
    character_name: str
    member_id: UUID
    member_display_name: str
    universe_id: Optional[UUID]
    world_id: Optional[UUID]
    archetype: Optional[str]
    total_playtime_minutes: int
    created_at: datetime

class ParentalControlsInfo(BaseModel):
    member_id: UUID
    daily_time_limit_minutes: Optional[int]
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    allowed_universes: List[str]
    can_play_with_strangers: bool
    remaining_time_today_minutes: Optional[int]

class FamilyContext(BaseModel):
    account_id: UUID
    members: List[Dict[str, Any]]
    parental_controls: List[ParentalControlsInfo]
    family_structure: Dict[str, Any]

# ============================================
# MCP Tools (Endpoints)
# ============================================

@app.get("/")
async def root():
    return {
        "service": "Player Data MCP Server",
        "version": "1.0.0",
        "description": "Provides player cognitive profiles and context to AI agents"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp/player-cognitive-profile/{player_id}", response_model=CognitiveProfile)
async def get_player_cognitive_profile(
    player_id: UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get player's cognitive profile
    Returns Bloom's taxonomy progress and core skills
    """
    # Get member
    result = await db.execute(
        select(Member).where(Member.member_id == player_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get cognitive progress
    result = await db.execute(
        select(MemberCognitiveProgress).where(MemberCognitiveProgress.member_id == player_id)
    )
    cognitive = result.scalar_one_or_none()

    # If no cognitive progress exists, create default
    if not cognitive:
        cognitive = MemberCognitiveProgress(
            member_id=player_id,
            remember_mastered=False,
            understand_mastered=False,
            apply_mastered=False,
            analyze_progress=0.0,
            evaluate_progress=0.0,
            create_progress=0.0,
            empathy_level=1,
            strategy_level=1,
            creativity_level=1,
            courage_level=1
        )
        db.add(cognitive)
        await db.commit()

    # Get character count and total playtime
    result = await db.execute(
        select(PlayerProfile).where(PlayerProfile.member_id == player_id)
    )
    characters = result.scalars().all()

    total_playtime = sum(c.total_playtime_minutes or 0 for c in characters)
    character_count = len(characters)

    # Calculate current Bloom tier
    bloom_tier = "Remember"
    if cognitive.create_progress >= 0.5:
        bloom_tier = "Create"
    elif cognitive.evaluate_progress >= 0.5:
        bloom_tier = "Evaluate"
    elif cognitive.analyze_progress >= 0.5:
        bloom_tier = "Analyze"
    elif cognitive.apply_mastered:
        bloom_tier = "Apply"
    elif cognitive.understand_mastered:
        bloom_tier = "Understand"

    # Calculate age
    age = None
    if member.date_of_birth:
        today = datetime.now().date()
        age = today.year - member.date_of_birth.year
        if today.month < member.date_of_birth.month or \
           (today.month == member.date_of_birth.month and today.day < member.date_of_birth.day):
            age -= 1

    return CognitiveProfile(
        member_id=member.member_id,
        display_name=member.display_name,
        age=age,
        role=member.role or "member",
        remember_mastered=cognitive.remember_mastered,
        understand_mastered=cognitive.understand_mastered,
        apply_mastered=cognitive.apply_mastered,
        analyze_progress=float(cognitive.analyze_progress),
        evaluate_progress=float(cognitive.evaluate_progress),
        create_progress=float(cognitive.create_progress),
        current_bloom_tier=bloom_tier,
        empathy_level=cognitive.empathy_level,
        strategy_level=cognitive.strategy_level,
        creativity_level=cognitive.creativity_level,
        courage_level=cognitive.courage_level,
        total_playtime_minutes=total_playtime,
        character_count=character_count
    )

@app.get("/mcp/character-info/{character_id}", response_model=CharacterInfo)
async def get_character_info(
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get character information
    Returns character details, archetype, universe context
    """
    result = await db.execute(
        select(PlayerProfile).where(PlayerProfile.profile_id == character_id)
    )
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    # Get member info
    result = await db.execute(
        select(Member).where(Member.member_id == character.member_id)
    )
    member = result.scalar_one_or_none()

    return CharacterInfo(
        profile_id=character.profile_id,
        character_name=character.character_name,
        member_id=character.member_id,
        member_display_name=member.display_name if member else "Unknown",
        universe_id=character.universe_id,
        world_id=character.world_id,
        archetype=character.archetype,
        total_playtime_minutes=character.total_playtime_minutes or 0,
        created_at=character.created_at
    )

@app.get("/mcp/family-context/{account_id}", response_model=FamilyContext)
async def get_family_context(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get family context
    Returns family structure, parental controls, member ages
    """
    # Get all members in account
    result = await db.execute(
        select(Member).where(Member.account_id == account_id)
    )
    members = result.scalars().all()

    if not members:
        raise HTTPException(status_code=404, detail="Account not found or has no members")

    # Build member list
    member_list = []
    parental_controls_list = []

    for member in members:
        # Calculate age
        age = None
        if member.date_of_birth:
            today = datetime.now().date()
            age = today.year - member.date_of_birth.year
            if today.month < member.date_of_birth.month or \
               (today.month == member.date_of_birth.month and today.day < member.date_of_birth.day):
                age -= 1

        member_list.append({
            "member_id": str(member.member_id),
            "display_name": member.display_name,
            "role": member.role or "member",
            "age": age,
            "can_manage_account": member.can_manage_account
        })

        # Add parental controls if they exist
        if member.daily_time_limit_minutes or member.quiet_hours_start or member.allowed_universes:
            allowed_universes = []
            if member.allowed_universes:
                try:
                    allowed_universes = json.loads(member.allowed_universes)
                except:
                    allowed_universes = []

            # Calculate remaining time (placeholder - would need session tracking)
            remaining_time = member.daily_time_limit_minutes

            parental_controls_list.append(ParentalControlsInfo(
                member_id=member.member_id,
                daily_time_limit_minutes=member.daily_time_limit_minutes,
                quiet_hours_start=str(member.quiet_hours_start) if member.quiet_hours_start else None,
                quiet_hours_end=str(member.quiet_hours_end) if member.quiet_hours_end else None,
                allowed_universes=allowed_universes,
                can_play_with_strangers=member.can_play_with_strangers or False,
                remaining_time_today_minutes=remaining_time
            ))

    # Build family structure (placeholder - would use Neo4j for relationships)
    family_structure = {
        "total_members": len(members),
        "has_parental_controls": len(parental_controls_list) > 0,
        "roles": list(set(m["role"] for m in member_list))
    }

    return FamilyContext(
        account_id=account_id,
        members=member_list,
        parental_controls=parental_controls_list,
        family_structure=family_structure
    )

@app.get("/mcp/parental-controls/{member_id}", response_model=ParentalControlsInfo)
async def get_parental_controls(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get parental controls for a member
    """
    result = await db.execute(
        select(Member).where(Member.member_id == member_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    allowed_universes = []
    if member.allowed_universes:
        try:
            allowed_universes = json.loads(member.allowed_universes)
        except:
            allowed_universes = []

    # Calculate remaining time (placeholder)
    remaining_time = member.daily_time_limit_minutes

    return ParentalControlsInfo(
        member_id=member.member_id,
        daily_time_limit_minutes=member.daily_time_limit_minutes,
        quiet_hours_start=str(member.quiet_hours_start) if member.quiet_hours_start else None,
        quiet_hours_end=str(member.quiet_hours_end) if member.quiet_hours_end else None,
        allowed_universes=allowed_universes,
        can_play_with_strangers=member.can_play_with_strangers or False,
        remaining_time_today_minutes=remaining_time
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
