"""
Player Service - FastAPI Microservice with Neo4j
Handles CRUD operations for players and family relationships
"""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from pydantic import BaseModel, EmailStr
from neo4j import AsyncGraphDatabase, AsyncDriver


# ============================================
# Database Setup
# ============================================

# PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://skillforge_user:password@localhost:5432/skillforge")
if DATABASE_URL and "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

# Neo4j
NEO4J_URL = os.getenv("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

neo4j_driver: Optional[AsyncDriver] = None


# ============================================
# SQLAlchemy Models
# ============================================

class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Identity
    display_name: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[Optional[str]] = mapped_column(nullable=True)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)

    # Role & Permissions
    role: Mapped[str] = mapped_column(nullable=False)
    can_manage_account: Mapped[bool] = mapped_column(default=False)
    can_manage_players: Mapped[bool] = mapped_column(default=False)
    can_view_billing: Mapped[bool] = mapped_column(default=False)

    # Content Restrictions
    content_restriction_level: Mapped[str] = mapped_column(default="automatic")
    allowed_universes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    blocked_universes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================
# Pydantic Schemas
# ============================================

class PlayerCreate(BaseModel):
    account_id: uuid.UUID
    display_name: str
    email: Optional[EmailStr] = None
    date_of_birth: date
    role: str


class PlayerUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None


class PlayerResponse(BaseModel):
    player_id: uuid.UUID
    account_id: uuid.UUID
    display_name: str
    email: Optional[str]
    date_of_birth: date
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FamilyRelationshipCreate(BaseModel):
    parent_player_id: uuid.UUID
    child_player_id: uuid.UUID
    relationship_type: str = "PARENT_OF"


# ============================================
# Dependencies
# ============================================

async def get_db():
    async with async_session_maker() as session:
        yield session


def get_neo4j_driver():
    global neo4j_driver
    if not neo4j_driver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j driver not initialized"
        )
    return neo4j_driver


# ============================================
# Application Lifecycle
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global neo4j_driver

    # Startup
    print("🚀 Player Service starting up...")

    # Initialize Neo4j driver
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            NEO4J_URL,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        # Test connection
        async with neo4j_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        print("✅ Connected to Neo4j")
    except Exception as e:
        print(f"⚠️  Neo4j connection failed: {e}")

    yield

    # Shutdown
    print("🛑 Player Service shutting down...")
    if neo4j_driver:
        await neo4j_driver.close()


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="SkillForge Player Service",
    description="Player management with Neo4j relationships",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "Player Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "player-service"}


# ============================================
# Player CRUD Endpoints
# ============================================

@app.post("/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(
    player_data: PlayerCreate,
    db: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Create a new player in PostgreSQL and Neo4j"""
    try:
        # Create in PostgreSQL
        new_player = Player(
            account_id=player_data.account_id,
            display_name=player_data.display_name,
            email=player_data.email,
            date_of_birth=player_data.date_of_birth,
            role=player_data.role
        )

        db.add(new_player)
        await db.commit()
        await db.refresh(new_player)

        # Create node in Neo4j
        async with driver.session() as neo4j_session:
            await neo4j_session.run(
                """
                CREATE (p:Player {
                    player_id: $player_id,
                    account_id: $account_id,
                    display_name: $display_name,
                    role: $role,
                    created_at: datetime()
                })
                """,
                player_id=str(new_player.player_id),
                account_id=str(new_player.account_id),
                display_name=new_player.display_name,
                role=new_player.role
            )

        return new_player

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create player: {str(e)}"
        )


@app.get("/players/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get player by ID"""
    result = await db.execute(
        select(Player).where(Player.player_id == player_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} not found"
        )

    return player


@app.get("/players", response_model=List[PlayerResponse])
async def list_players(
    account_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List players, optionally filtered by account"""
    query = select(Player)

    if account_id:
        query = query.where(Player.account_id == account_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    players = result.scalars().all()

    return players


@app.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_player(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Delete player from PostgreSQL and Neo4j"""
    result = await db.execute(
        select(Player).where(Player.player_id == player_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player {player_id} not found"
        )

    # Delete from PostgreSQL
    await db.delete(player)
    await db.commit()

    # Delete from Neo4j
    async with driver.session() as neo4j_session:
        await neo4j_session.run(
            "MATCH (p:Player {player_id: $player_id}) DETACH DELETE p",
            player_id=str(player_id)
        )

    return None


# ============================================
# Neo4j Relationship Endpoints
# ============================================

@app.post("/relationships/family", status_code=status.HTTP_201_CREATED)
async def create_family_relationship(
    relationship: FamilyRelationshipCreate,
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Create a family relationship in Neo4j graph"""
    async with driver.session() as neo4j_session:
        result = await neo4j_session.run(
            """
            MATCH (parent:Player {player_id: $parent_id})
            MATCH (child:Player {player_id: $child_id})
            CREATE (parent)-[r:PARENT_OF {created_at: datetime()}]->(child)
            CREATE (parent)-[:MANAGES]->(child)
            RETURN parent, child, r
            """,
            parent_id=str(relationship.parent_player_id),
            child_id=str(relationship.child_player_id)
        )

        record = await result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both players not found in graph"
            )

        return {
            "message": "Family relationship created",
            "parent_id": str(relationship.parent_player_id),
            "child_id": str(relationship.child_player_id)
        }


@app.get("/players/{player_id}/children")
async def get_player_children(
    player_id: uuid.UUID,
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Get all children of a player"""
    async with driver.session() as neo4j_session:
        result = await neo4j_session.run(
            """
            MATCH (parent:Player {player_id: $player_id})-[:PARENT_OF]->(child:Player)
            RETURN child.player_id as player_id, child.display_name as display_name, child.role as role
            """,
            player_id=str(player_id)
        )

        children = []
        async for record in result:
            children.append({
                "player_id": record["player_id"],
                "display_name": record["display_name"],
                "role": record["role"]
            })

        return {"children": children}


@app.get("/players/{player_id}/family-tree")
async def get_family_tree(
    player_id: uuid.UUID,
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Get the complete family tree for a player"""
    async with driver.session() as neo4j_session:
        result = await neo4j_session.run(
            """
            MATCH path = (p:Player {player_id: $player_id})-[:PARENT_OF*0..3]-(family:Player)
            RETURN DISTINCT family.player_id as player_id,
                   family.display_name as display_name,
                   family.role as role
            """,
            player_id=str(player_id)
        )

        family_players = []
        async for record in result:
            family_players.append({
                "player_id": record["player_id"],
                "display_name": record["display_name"],
                "role": record["role"]
            })

        return {"family_tree": family_players}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
