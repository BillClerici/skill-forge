"""
Member Service - FastAPI Microservice with Neo4j
Handles CRUD operations for members and family relationships
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


class Member(Base):
    __tablename__ = "members"

    member_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Identity
    display_name: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[Optional[str]] = mapped_column(nullable=True)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)

    # Role & Permissions
    role: Mapped[str] = mapped_column(nullable=False)
    can_manage_account: Mapped[bool] = mapped_column(default=False)
    can_manage_members: Mapped[bool] = mapped_column(default=False)
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

class MemberCreate(BaseModel):
    account_id: uuid.UUID
    display_name: str
    email: Optional[EmailStr] = None
    date_of_birth: date
    role: str


class MemberUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None


class MemberResponse(BaseModel):
    member_id: uuid.UUID
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
    parent_member_id: uuid.UUID
    child_member_id: uuid.UUID
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
    print("🚀 Member Service starting up...")

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
    print("🛑 Member Service shutting down...")
    if neo4j_driver:
        await neo4j_driver.close()


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="SkillForge Member Service",
    description="Member management with Neo4j relationships",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "Member Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "member-service"}


# ============================================
# Member CRUD Endpoints
# ============================================

@app.post("/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    member_data: MemberCreate,
    db: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Create a new member in PostgreSQL and Neo4j"""
    try:
        # Create in PostgreSQL
        new_member = Member(
            account_id=member_data.account_id,
            display_name=member_data.display_name,
            email=member_data.email,
            date_of_birth=member_data.date_of_birth,
            role=member_data.role
        )

        db.add(new_member)
        await db.commit()
        await db.refresh(new_member)

        # Create node in Neo4j
        async with driver.session() as neo4j_session:
            await neo4j_session.run(
                """
                CREATE (m:Member {
                    member_id: $member_id,
                    account_id: $account_id,
                    display_name: $display_name,
                    role: $role,
                    created_at: datetime()
                })
                """,
                member_id=str(new_member.member_id),
                account_id=str(new_member.account_id),
                display_name=new_member.display_name,
                role=new_member.role
            )

        return new_member

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create member: {str(e)}"
        )


@app.get("/members/{member_id}", response_model=MemberResponse)
async def get_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get member by ID"""
    result = await db.execute(
        select(Member).where(Member.member_id == member_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member {member_id} not found"
        )

    return member


@app.get("/members", response_model=List[MemberResponse])
async def list_members(
    account_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List members, optionally filtered by account"""
    query = select(Member)

    if account_id:
        query = query.where(Member.account_id == account_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    members = result.scalars().all()

    return members


@app.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Delete member from PostgreSQL and Neo4j"""
    result = await db.execute(
        select(Member).where(Member.member_id == member_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member {member_id} not found"
        )

    # Delete from PostgreSQL
    await db.delete(member)
    await db.commit()

    # Delete from Neo4j
    async with driver.session() as neo4j_session:
        await neo4j_session.run(
            "MATCH (m:Member {member_id: $member_id}) DETACH DELETE m",
            member_id=str(member_id)
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
            MATCH (parent:Member {member_id: $parent_id})
            MATCH (child:Member {member_id: $child_id})
            CREATE (parent)-[r:PARENT_OF {created_at: datetime()}]->(child)
            CREATE (parent)-[:MANAGES]->(child)
            RETURN parent, child, r
            """,
            parent_id=str(relationship.parent_member_id),
            child_id=str(relationship.child_member_id)
        )

        record = await result.single()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both members not found in graph"
            )

        return {
            "message": "Family relationship created",
            "parent_id": str(relationship.parent_member_id),
            "child_id": str(relationship.child_member_id)
        }


@app.get("/members/{member_id}/children")
async def get_member_children(
    member_id: uuid.UUID,
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Get all children of a member"""
    async with driver.session() as neo4j_session:
        result = await neo4j_session.run(
            """
            MATCH (parent:Member {member_id: $member_id})-[:PARENT_OF]->(child:Member)
            RETURN child.member_id as member_id, child.display_name as display_name, child.role as role
            """,
            member_id=str(member_id)
        )

        children = []
        async for record in result:
            children.append({
                "member_id": record["member_id"],
                "display_name": record["display_name"],
                "role": record["role"]
            })

        return {"children": children}


@app.get("/members/{member_id}/family-tree")
async def get_family_tree(
    member_id: uuid.UUID,
    driver: AsyncDriver = Depends(get_neo4j_driver)
):
    """Get the complete family tree for a member"""
    async with driver.session() as neo4j_session:
        result = await neo4j_session.run(
            """
            MATCH path = (m:Member {member_id: $member_id})-[:PARENT_OF*0..3]-(family:Member)
            RETURN DISTINCT family.member_id as member_id,
                   family.display_name as display_name,
                   family.role as role
            """,
            member_id=str(member_id)
        )

        family_members = []
        async for record in result:
            family_members.append({
                "member_id": record["member_id"],
                "display_name": record["display_name"],
                "role": record["role"]
            })

        return {"family_tree": family_members}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
