"""
World/Universe MCP Server
Provides universe definitions and world lore to AI agents
"""
import os
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase
from redis.asyncio import Redis
import json

# ============================================
# Configuration
# ============================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
NEO4J_URL = os.getenv("NEO4J_URL", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_dev_pass_2024")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="World/Universe MCP Server",
    description="MCP Server providing universe definitions and world lore to AI agents",
    version="1.0.0"
)

# ============================================
# Database Clients
# ============================================

mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db = None
neo4j_driver = None
redis_client: Optional[Redis] = None

@app.on_event("startup")
async def startup():
    global mongo_client, mongo_db, neo4j_driver, redis_client

    # MongoDB
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client.skillforge

    # Neo4j
    neo4j_driver = AsyncGraphDatabase.driver(
        NEO4J_URL,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )

    # Redis
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
    if neo4j_driver:
        await neo4j_driver.close()
    if redis_client:
        await redis_client.close()

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

class UniverseGuidelines(BaseModel):
    universe_id: str
    universe_name: str
    universe_type: str
    purpose: str
    description: str
    target_age_min: Optional[int]
    target_age_max: Optional[int]
    max_content_rating: str
    features: Dict[str, Any]
    narrative_tone: Optional[Dict[str, Any]]
    vocabulary_style: Optional[Dict[str, Any]]
    modifications: Optional[List[str]]

class WorldLore(BaseModel):
    world_id: str
    world_name: str
    genre: str
    base_content_rating: str
    themes: List[str]
    visual_style: str
    description: str
    lore: Optional[Dict[str, Any]]
    regions: Optional[List[Dict[str, Any]]]
    npcs: Optional[List[Dict[str, Any]]]
    factions: Optional[List[Dict[str, Any]]]
    starting_locations: Optional[List[Dict[str, Any]]]

class GeneratedContent(BaseModel):
    content_id: str
    content_type: str
    character_id: str
    world_id: str
    universe_id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime

class UniverseWorldMapping(BaseModel):
    universe_id: str
    world_id: str
    requires_adaptation: bool
    adaptation_level: Optional[str]
    adapted_version_id: Optional[str]

# ============================================
# MCP Tools (Endpoints)
# ============================================

@app.get("/")
async def root():
    return {
        "service": "World/Universe MCP Server",
        "version": "1.0.0",
        "description": "Provides universe definitions and world lore to AI agents"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp/universe-guidelines/{universe_id}", response_model=UniverseGuidelines)
async def get_universe_guidelines(
    universe_id: UUID,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get universe guidelines
    Returns content rating, tone, features, modifications
    """
    # Try cache first
    cache_key = f"universe:{universe_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return UniverseGuidelines(**json.loads(cached))

    # Get from MongoDB
    universe_def = await mongo_db.universe_definitions.find_one(
        {"universe_id": str(universe_id)}
    )

    if not universe_def:
        # Return a default universe for demo purposes
        universe_def = {
            "universe_id": str(universe_id),
            "universe_name": "Default Universe",
            "universe_type": "content_rating",
            "purpose": "General purpose universe",
            "description": "A default universe for testing",
            "target_age_min": 10,
            "target_age_max": 18,
            "max_content_rating": "PG",
            "features": {
                "educational": True,
                "family_friendly": True
            },
            "narrative_tone": {
                "style": "friendly",
                "formality": "casual",
                "complexity": "moderate"
            },
            "vocabulary_style": {
                "reading_level": "middle_school",
                "technical_terms": False
            },
            "modifications": []
        }

    result = UniverseGuidelines(
        universe_id=universe_def.get("universe_id", str(universe_id)),
        universe_name=universe_def.get("universe_name", "Unknown Universe"),
        universe_type=universe_def.get("universe_type", "content_rating"),
        purpose=universe_def.get("purpose", ""),
        description=universe_def.get("description", ""),
        target_age_min=universe_def.get("target_age_min"),
        target_age_max=universe_def.get("target_age_max"),
        max_content_rating=universe_def.get("max_content_rating", "PG"),
        features=universe_def.get("features", {}),
        narrative_tone=universe_def.get("narrative_tone"),
        vocabulary_style=universe_def.get("vocabulary_style"),
        modifications=universe_def.get("modifications", [])
    )

    # Cache for 1 hour
    await redis_client.setex(cache_key, 3600, result.model_dump_json())

    return result

@app.get("/mcp/world-lore/{world_id}", response_model=WorldLore)
async def get_world_lore(
    world_id: UUID,
    universe_id: Optional[UUID] = None,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get world lore
    Returns complete world lore, NPCs, regions, history
    """
    # Try cache first
    cache_key = f"world:{world_id}:{universe_id}" if universe_id else f"world:{world_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return WorldLore(**json.loads(cached))

    # Get from MongoDB
    world_def = await mongo_db.world_definitions.find_one(
        {"world_id": str(world_id)}
    )

    if not world_def:
        # Return a default world for demo purposes
        world_def = {
            "world_id": str(world_id),
            "world_name": "Default World",
            "genre": "fantasy",
            "base_content_rating": "PG",
            "themes": ["adventure", "friendship"],
            "visual_style": "watercolor fantasy",
            "description": "A default fantasy world for testing",
            "lore": {
                "history": "An ancient world with rich history",
                "geography": "Diverse landscapes including mountains, forests, and seas",
                "magic_system": "Elemental magic based on natural forces"
            },
            "regions": [
                {
                    "name": "The Starting Village",
                    "description": "A peaceful village where adventures begin",
                    "type": "settlement"
                }
            ],
            "npcs": [
                {
                    "name": "Elder Wisdom",
                    "role": "Village Elder",
                    "personality": "Wise and kind mentor",
                    "location": "The Starting Village"
                }
            ],
            "factions": [],
            "starting_locations": [
                {
                    "name": "Village Square",
                    "description": "The heart of the starting village"
                }
            ]
        }

    # If universe_id provided, check for adapted version
    if universe_id:
        adapted = await mongo_db.world_adaptations.find_one({
            "world_id": str(world_id),
            "universe_id": str(universe_id)
        })

        if adapted:
            # Merge adapted content
            world_def.update(adapted.get("adaptations", {}))

    result = WorldLore(
        world_id=world_def.get("world_id", str(world_id)),
        world_name=world_def.get("world_name", "Unknown World"),
        genre=world_def.get("genre", "fantasy"),
        base_content_rating=world_def.get("base_content_rating", "PG"),
        themes=world_def.get("themes", []),
        visual_style=world_def.get("visual_style", "fantasy"),
        description=world_def.get("description", ""),
        lore=world_def.get("lore"),
        regions=world_def.get("regions", []),
        npcs=world_def.get("npcs", []),
        factions=world_def.get("factions", []),
        starting_locations=world_def.get("starting_locations", [])
    )

    # Cache for 1 hour
    await redis_client.setex(cache_key, 3600, result.model_dump_json())

    return result

@app.get("/mcp/previously-generated-content", response_model=List[GeneratedContent])
async def get_previously_generated_content(
    character_id: UUID,
    content_type: str,
    limit: int = 10,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get previously generated content
    Returns past AI-generated content for consistency
    """
    # Query MongoDB for narrative content
    cursor = mongo_db.narrative_content.find({
        "character_id": str(character_id),
        "content_type": content_type
    }).sort("created_at", -1).limit(limit)

    results = []
    async for doc in cursor:
        results.append(GeneratedContent(
            content_id=doc.get("_id", str(doc.get("content_id", ""))),
            content_type=doc.get("content_type", content_type),
            character_id=doc.get("character_id", str(character_id)),
            world_id=doc.get("world_id", ""),
            universe_id=doc.get("universe_id", ""),
            content=doc.get("content", ""),
            metadata=doc.get("metadata", {}),
            created_at=doc.get("created_at", datetime.now())
        ))

    return results

@app.get("/mcp/universe-world-mapping/{universe_id}/{world_id}", response_model=UniverseWorldMapping)
async def get_universe_world_mapping(
    universe_id: UUID,
    world_id: UUID,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get universe-world mapping
    Returns adaptation requirements and adapted version info
    """
    # Query Neo4j for relationship
    async with neo4j_driver.session() as session:
        result = await session.run("""
            MATCH (u:Universe {universe_id: $universe_id})
                  -[r:CONTAINS]->(w:World {world_id: $world_id})
            RETURN r.requires_adaptation as requires_adaptation,
                   r.adaptation_level as adaptation_level,
                   r.adapted_version_id as adapted_version_id
        """, universe_id=str(universe_id), world_id=str(world_id))

        record = await result.single()

        if record:
            return UniverseWorldMapping(
                universe_id=str(universe_id),
                world_id=str(world_id),
                requires_adaptation=record.get("requires_adaptation", False),
                adaptation_level=record.get("adaptation_level"),
                adapted_version_id=record.get("adapted_version_id")
            )
        else:
            # Default mapping
            return UniverseWorldMapping(
                universe_id=str(universe_id),
                world_id=str(world_id),
                requires_adaptation=False,
                adaptation_level=None,
                adapted_version_id=None
            )

@app.post("/mcp/store-generated-content")
async def store_generated_content(
    content: GeneratedContent,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Store AI-generated content
    Stores content for future consistency checks
    """
    doc = content.model_dump()
    doc["created_at"] = datetime.now()

    result = await mongo_db.narrative_content.insert_one(doc)

    return {
        "status": "success",
        "content_id": str(result.inserted_id)
    }

@app.get("/worlds/{world_id}/species")
async def get_world_species(
    world_id: UUID,
    token: str = Depends(verify_mcp_token)
):
    """
    Get all species for a world
    Returns species information for campaign generation
    """
    # Query MongoDB for species in this world using the correct collection
    cursor = mongo_db.species_definitions.find({"world_id": str(world_id)})

    species_list = []
    async for doc in cursor:
        # Convert MongoDB document to dict matching Django structure
        species_id_str = str(doc.get("_id", ""))
        species_dict = {
            "id": species_id_str,  # For backward compatibility with campaign factory
            "species_id": species_id_str,
            "name": doc.get("species_name", ""),
            "species_name": doc.get("species_name", ""),
            "species_type": doc.get("species_type", ""),
            "category": doc.get("category", ""),
            "description": doc.get("description", ""),
            "backstory": doc.get("backstory", ""),
            "character_traits": doc.get("character_traits", []),
            "world_id": doc.get("world_id", str(world_id)),
            "regions": doc.get("regions", []),
            "relationships": doc.get("relationships", []),
            "species_images": doc.get("species_images", []),
            "primary_image_index": doc.get("primary_image_index")
        }
        species_list.append(species_dict)

    return {"species": species_list}

@app.get("/mcp/world-npcs/{world_id}")
async def get_world_npcs(
    world_id: UUID,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get NPCs for a world
    Returns NPC information for AI agent interactions
    """
    world_def = await mongo_db.world_definitions.find_one(
        {"world_id": str(world_id)}
    )

    if not world_def:
        return {"npcs": []}

    return {"npcs": world_def.get("npcs", [])}

@app.get("/mcp/universe-features/{universe_id}")
async def get_universe_features(
    universe_id: UUID,
    token: str = Depends(verify_mcp_token)
):
    """
    MCP Tool: Get universe-specific features
    Returns feature flags and settings for the universe
    """
    universe_def = await mongo_db.universe_definitions.find_one(
        {"universe_id": str(universe_id)}
    )

    if not universe_def:
        return {"features": {}}

    return {
        "features": universe_def.get("features", {}),
        "narrative_tone": universe_def.get("narrative_tone", {}),
        "vocabulary_style": universe_def.get("vocabulary_style", {})
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
