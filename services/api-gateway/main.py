"""
GraphQL API Gateway - Unified endpoint for SkillForge RPG
Aggregates data from microservices using Strawberry GraphQL
"""
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

import httpx
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info
from pymongo import MongoClient


# ============================================
# MongoDB Connection
# ============================================

MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')

def get_db():
    """Get MongoDB database instance"""
    mongo_client = MongoClient(MONGODB_URL)
    return mongo_client['skillforge']


# ============================================
# GraphQL Types
# ============================================

@strawberry.type
class Account:
    account_id: strawberry.ID
    account_type: str
    subscription_tier: Optional[str]
    subscription_status: str
    max_members: int
    current_member_count: int
    created_at: datetime
    updated_at: datetime


@strawberry.input
class CreateAccountInput:
    account_type: str
    subscription_tier: Optional[str] = None
    max_members: int = 1


@strawberry.input
class UpdateAccountInput:
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


# World Building Types
@strawberry.type
class Universe:
    universe_id: strawberry.ID
    universe_name: str
    max_content_rating: Optional[str]
    description: Optional[str]


@strawberry.type
class World:
    world_id: strawberry.ID
    world_name: str
    description: Optional[str]
    genre: Optional[str]
    themes: Optional[List[str]]
    visual_style: Optional[List[str]]


@strawberry.type
class Region:
    region_id: strawberry.ID
    region_name: str
    region_type: Optional[str]
    climate: Optional[str]
    description: Optional[str]
    world_id: strawberry.ID


@strawberry.type
class Location:
    location_id: strawberry.ID
    location_name: str
    location_type: Optional[str]
    description: Optional[str]
    region_id: strawberry.ID
    world_id: strawberry.ID


@strawberry.type
class Species:
    species_id: strawberry.ID
    species_name: str
    species_type: Optional[str]
    category: Optional[str]
    description: Optional[str]
    backstory: Optional[str]
    character_traits: Optional[List[str]]
    world_id: strawberry.ID


# ============================================
# Service Clients
# ============================================

ACCOUNT_SERVICE_URL = os.getenv("ACCOUNT_SERVICE_URL", "http://account-service:8000")


async def get_http_client() -> httpx.AsyncClient:
    """Get HTTP client for service communication"""
    return httpx.AsyncClient(timeout=10.0)


# ============================================
# GraphQL Resolvers
# ============================================

@strawberry.type
class Query:
    @strawberry.field
    async def hello(self) -> str:
        """Test query"""
        return "Hello from SkillForge GraphQL API!"

    @strawberry.field
    async def account(self, account_id: strawberry.ID) -> Optional[Account]:
        """Get account by ID"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}")
                if response.status_code == 200:
                    data = response.json()
                    return Account(
                        account_id=data["account_id"],
                        account_type=data["account_type"],
                        subscription_tier=data.get("subscription_tier"),
                        subscription_status=data["subscription_status"],
                        max_members=data["max_members"],
                        current_member_count=data["current_member_count"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        updated_at=datetime.fromisoformat(data["updated_at"])
                    )
                return None
            except Exception as e:
                print(f"Error fetching account: {e}")
                return None

    @strawberry.field
    async def accounts(self, skip: int = 0, limit: int = 100) -> List[Account]:
        """List all accounts"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{ACCOUNT_SERVICE_URL}/accounts",
                    params={"skip": skip, "limit": limit}
                )
                if response.status_code == 200:
                    data = response.json()
                    return [
                        Account(
                            account_id=item["account_id"],
                            account_type=item["account_type"],
                            subscription_tier=item.get("subscription_tier"),
                            subscription_status=item["subscription_status"],
                            max_members=item["max_members"],
                            current_member_count=item["current_member_count"],
                            created_at=datetime.fromisoformat(item["created_at"]),
                            updated_at=datetime.fromisoformat(item["updated_at"])
                        )
                        for item in data
                    ]
                return []
            except Exception as e:
                print(f"Error fetching accounts: {e}")
                return []

    # Universe queries
    @strawberry.field
    def universes(self) -> List[Universe]:
        """Get all universes"""
        db = get_db()
        universes = list(db.universe_definitions.find())
        return [
            Universe(
                universe_id=u["_id"],
                universe_name=u.get("universe_name", ""),
                max_content_rating=u.get("max_content_rating"),
                description=u.get("description")
            )
            for u in universes
        ]

    @strawberry.field
    def universe(self, universe_id: strawberry.ID) -> Optional[Universe]:
        """Get universe by ID"""
        db = get_db()
        u = db.universe_definitions.find_one({'_id': str(universe_id)})
        if u:
            return Universe(
                universe_id=u["_id"],
                universe_name=u.get("universe_name", ""),
                max_content_rating=u.get("max_content_rating"),
                description=u.get("description")
            )
        return None

    # World queries
    @strawberry.field
    def worlds(self) -> List[World]:
        """Get all worlds"""
        db = get_db()
        worlds = list(db.world_definitions.find())
        return [
            World(
                world_id=w["_id"],
                world_name=w.get("world_name", ""),
                description=w.get("description"),
                genre=w.get("genre"),
                themes=w.get("themes", []),
                visual_style=w.get("visual_style", [])
            )
            for w in worlds
        ]

    @strawberry.field
    def world(self, world_id: strawberry.ID) -> Optional[World]:
        """Get world by ID"""
        db = get_db()
        w = db.world_definitions.find_one({'_id': str(world_id)})
        if w:
            return World(
                world_id=w["_id"],
                world_name=w.get("world_name", ""),
                description=w.get("description"),
                genre=w.get("genre"),
                themes=w.get("themes", []),
                visual_style=w.get("visual_style", [])
            )
        return None

    @strawberry.field
    def worlds_by_universe(self, universe_id: strawberry.ID) -> List[World]:
        """Get all worlds in a universe"""
        db = get_db()
        worlds = list(db.world_definitions.find({'universe_ids': str(universe_id)}))
        return [
            World(
                world_id=w["_id"],
                world_name=w.get("world_name", ""),
                description=w.get("description"),
                genre=w.get("genre"),
                themes=w.get("themes", []),
                visual_style=w.get("visual_style", [])
            )
            for w in worlds
        ]

    # Region queries
    @strawberry.field
    def regions(self) -> List[Region]:
        """Get all regions"""
        db = get_db()
        regions = list(db.region_definitions.find())
        return [
            Region(
                region_id=r["_id"],
                region_name=r.get("region_name", ""),
                region_type=r.get("region_type"),
                climate=r.get("climate"),
                description=r.get("description"),
                world_id=r.get("world_id", "")
            )
            for r in regions
        ]

    @strawberry.field
    def region(self, region_id: strawberry.ID) -> Optional[Region]:
        """Get region by ID"""
        db = get_db()
        r = db.region_definitions.find_one({'_id': str(region_id)})
        if r:
            return Region(
                region_id=r["_id"],
                region_name=r.get("region_name", ""),
                region_type=r.get("region_type"),
                climate=r.get("climate"),
                description=r.get("description"),
                world_id=r.get("world_id", "")
            )
        return None

    @strawberry.field
    def regions_by_world(self, world_id: strawberry.ID) -> List[Region]:
        """Get all regions in a world"""
        db = get_db()
        regions = list(db.region_definitions.find({'world_id': str(world_id)}))
        return [
            Region(
                region_id=r["_id"],
                region_name=r.get("region_name", ""),
                region_type=r.get("region_type"),
                climate=r.get("climate"),
                description=r.get("description"),
                world_id=r.get("world_id", "")
            )
            for r in regions
        ]

    # Location queries
    @strawberry.field
    def locations(self) -> List[Location]:
        """Get all locations"""
        db = get_db()
        locations = list(db.location_definitions.find())
        return [
            Location(
                location_id=l["_id"],
                location_name=l.get("location_name", ""),
                location_type=l.get("location_type"),
                description=l.get("description"),
                region_id=l.get("region_id", ""),
                world_id=l.get("world_id", "")
            )
            for l in locations
        ]

    @strawberry.field
    def location(self, location_id: strawberry.ID) -> Optional[Location]:
        """Get location by ID"""
        db = get_db()
        l = db.location_definitions.find_one({'_id': str(location_id)})
        if l:
            return Location(
                location_id=l["_id"],
                location_name=l.get("location_name", ""),
                location_type=l.get("location_type"),
                description=l.get("description"),
                region_id=l.get("region_id", ""),
                world_id=l.get("world_id", "")
            )
        return None

    @strawberry.field
    def locations_by_region(self, region_id: strawberry.ID) -> List[Location]:
        """Get all locations in a region"""
        db = get_db()
        locations = list(db.location_definitions.find({'region_id': str(region_id)}))
        return [
            Location(
                location_id=l["_id"],
                location_name=l.get("location_name", ""),
                location_type=l.get("location_type"),
                description=l.get("description"),
                region_id=l.get("region_id", ""),
                world_id=l.get("world_id", "")
            )
            for l in locations
        ]

    @strawberry.field
    def locations_by_world(self, world_id: strawberry.ID) -> List[Location]:
        """Get all locations in a world"""
        db = get_db()
        locations = list(db.location_definitions.find({'world_id': str(world_id)}))
        return [
            Location(
                location_id=l["_id"],
                location_name=l.get("location_name", ""),
                location_type=l.get("location_type"),
                description=l.get("description"),
                region_id=l.get("region_id", ""),
                world_id=l.get("world_id", "")
            )
            for l in locations
        ]

    # Species queries
    @strawberry.field
    def all_species(self) -> List[Species]:
        """Get all species"""
        db = get_db()
        species_list = list(db.species_definitions.find())
        return [
            Species(
                species_id=s["_id"],
                species_name=s.get("species_name", ""),
                species_type=s.get("species_type"),
                category=s.get("category"),
                description=s.get("description"),
                backstory=s.get("backstory"),
                character_traits=s.get("character_traits", []),
                world_id=s.get("world_id", "")
            )
            for s in species_list
        ]

    @strawberry.field
    def species(self, species_id: strawberry.ID) -> Optional[Species]:
        """Get species by ID"""
        db = get_db()
        s = db.species_definitions.find_one({'_id': str(species_id)})
        if s:
            return Species(
                species_id=s["_id"],
                species_name=s.get("species_name", ""),
                species_type=s.get("species_type"),
                category=s.get("category"),
                description=s.get("description"),
                backstory=s.get("backstory"),
                character_traits=s.get("character_traits", []),
                world_id=s.get("world_id", "")
            )
        return None

    @strawberry.field
    def species_by_world(self, world_id: strawberry.ID) -> List[Species]:
        """Get all species in a world"""
        db = get_db()
        species_list = list(db.species_definitions.find({'world_id': str(world_id)}))
        return [
            Species(
                species_id=s["_id"],
                species_name=s.get("species_name", ""),
                species_type=s.get("species_type"),
                category=s.get("category"),
                description=s.get("description"),
                backstory=s.get("backstory"),
                character_traits=s.get("character_traits", []),
                world_id=s.get("world_id", "")
            )
            for s in species_list
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_account(self, input: CreateAccountInput) -> Account:
        """Create a new account"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ACCOUNT_SERVICE_URL}/accounts",
                json={
                    "account_type": input.account_type,
                    "subscription_tier": input.subscription_tier,
                    "max_members": input.max_members
                }
            )
            response.raise_for_status()
            data = response.json()
            return Account(
                account_id=data["account_id"],
                account_type=data["account_type"],
                subscription_tier=data.get("subscription_tier"),
                subscription_status=data["subscription_status"],
                max_members=data["max_members"],
                current_member_count=data["current_member_count"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"])
            )

    @strawberry.mutation
    async def update_account(
        self,
        account_id: strawberry.ID,
        input: UpdateAccountInput
    ) -> Optional[Account]:
        """Update an existing account"""
        async with httpx.AsyncClient() as client:
            update_data = {}
            if input.subscription_tier is not None:
                update_data["subscription_tier"] = input.subscription_tier
            if input.subscription_status is not None:
                update_data["subscription_status"] = input.subscription_status

            response = await client.patch(
                f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}",
                json=update_data
            )
            if response.status_code == 200:
                data = response.json()
                return Account(
                    account_id=data["account_id"],
                    account_type=data["account_type"],
                    subscription_tier=data.get("subscription_tier"),
                    subscription_status=data["subscription_status"],
                    max_members=data["max_members"],
                    current_member_count=data["current_member_count"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"])
                )
            return None

    @strawberry.mutation
    async def delete_account(self, account_id: strawberry.ID) -> bool:
        """Delete an account"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{ACCOUNT_SERVICE_URL}/accounts/{account_id}")
            return response.status_code == 204


# ============================================
# GraphQL Schema
# ============================================

schema = strawberry.Schema(query=Query, mutation=Mutation)


# ============================================
# FastAPI Application
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 GraphQL API Gateway starting up...")
    yield
    # Shutdown
    print("🛑 GraphQL API Gateway shutting down...")


app = FastAPI(
    title="SkillForge GraphQL API Gateway",
    description="Unified GraphQL endpoint aggregating all SkillForge services",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "service": "GraphQL API Gateway",
        "status": "running",
        "version": "1.0.0",
        "graphql_endpoint": "/graphql"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}


# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
