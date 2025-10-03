"""
NPC Personality MCP Server
Provides character AI behaviors, personalities, and dialogue management
"""
import os
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
import json

# ============================================
# Configuration
# ============================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="NPC Personality MCP Server",
    description="MCP server for NPC personalities, behaviors, and dialogue",
    version="1.0.0"
)

# ============================================
# Database Clients
# ============================================

mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db = None
redis_client: Optional[Redis] = None

@app.on_event("startup")
async def startup():
    global mongo_client, mongo_db, redis_client
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client.skillforge
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()

# ============================================
# Authentication
# ============================================

async def verify_mcp_token(authorization: str = Header(...)):
    """Verify MCP authentication token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split("Bearer ")[1]
    if token != MCP_AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid MCP token")

    return token

# ============================================
# Data Models
# ============================================

class PersonalityTraits(BaseModel):
    """Core personality traits"""
    openness: int = 5  # 1-10: Curious vs Traditional
    conscientiousness: int = 5  # 1-10: Organized vs Spontaneous
    extraversion: int = 5  # 1-10: Outgoing vs Reserved
    agreeableness: int = 5  # 1-10: Cooperative vs Competitive
    neuroticism: int = 5  # 1-10: Sensitive vs Secure

class Motivation(BaseModel):
    """NPC motivation"""
    motivation_type: str  # power, knowledge, wealth, justice, revenge, love, survival
    description: str
    intensity: int = 5  # 1-10

class Relationship(BaseModel):
    """Relationship with another character"""
    character_id: str
    relationship_type: str  # ally, enemy, neutral, romantic, family, mentor
    affinity: int = 0  # -100 to 100
    history: str = ""

class DialogueStyle(BaseModel):
    """How the NPC speaks"""
    formality: str = "neutral"  # formal, neutral, casual, vulgar
    verbosity: str = "moderate"  # terse, moderate, verbose
    humor: str = "none"  # none, dry, witty, slapstick
    accent: Optional[str] = None
    catchphrases: List[str] = []

class NPC(BaseModel):
    """Non-Player Character definition"""
    npc_id: str
    name: str
    title: Optional[str] = None
    species: str = "human"
    age: Optional[int] = None
    gender: Optional[str] = None

    # Personality
    personality_traits: PersonalityTraits
    motivations: List[Motivation] = []
    values: List[str] = []  # honesty, loyalty, freedom, tradition, etc.
    fears: List[str] = []

    # Behavior
    alignment: str = "neutral"  # lawful_good, neutral_good, chaotic_good, etc.
    occupation: Optional[str] = None
    skills: List[str] = []
    combat_style: Optional[str] = None

    # Dialogue
    dialogue_style: DialogueStyle
    backstory: str = ""
    secrets: List[str] = []  # Hidden information

    # Relationships
    relationships: List[Relationship] = []
    faction: Optional[str] = None

    # Location
    world_id: Optional[str] = None
    region_id: Optional[str] = None
    location_id: Optional[str] = None
    home_location: Optional[str] = None

    # Quest Integration
    quests_given: List[str] = []  # Quest IDs this NPC offers
    quest_roles: Dict[str, str] = {}  # quest_id -> role (giver, target, ally, enemy)

    # State
    is_alive: bool = True
    current_mood: str = "neutral"  # happy, sad, angry, fearful, surprised, disgusted

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class NPCInteraction(BaseModel):
    """Record of player-NPC interaction"""
    interaction_id: str
    profile_id: str
    npc_id: str
    interaction_type: str  # dialogue, trade, combat, quest
    context: Dict[str, Any] = {}
    player_action: str
    npc_response: str
    affinity_change: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

class DialogueTemplate(BaseModel):
    """Template for NPC dialogue"""
    template_id: str
    npc_id: str
    situation: str  # greeting, farewell, quest_offer, shop, combat, etc.
    mood: str = "neutral"
    templates: List[str]  # Multiple variations
    conditions: Dict[str, Any] = {}  # When this template applies

# ============================================
# MCP Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "service": "NPC Personality MCP Server",
        "version": "1.0.0",
        "description": "Character AI behaviors, personalities, and dialogue"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp/npc/{npc_id}")
async def get_npc(
    npc_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get NPC details by ID"""
    # Try cache first
    cache_key = f"npc:{npc_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Query MongoDB
    npc = await mongo_db.npcs.find_one({"npc_id": npc_id})

    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    npc.pop("_id", None)

    # Cache for 30 minutes
    await redis_client.setex(cache_key, 1800, json.dumps(npc, default=str))

    return npc

@app.get("/mcp/location-npcs")
async def get_location_npcs(
    world_id: Optional[str] = None,
    region_id: Optional[str] = None,
    location_id: Optional[str] = None,
    token: str = Depends(verify_mcp_token)
):
    """Get all NPCs at a specific location"""
    query = {"is_alive": True}

    if world_id:
        query["world_id"] = world_id
    if region_id:
        query["region_id"] = region_id
    if location_id:
        query["location_id"] = location_id

    npcs = []
    cursor = mongo_db.npcs.find(query)

    async for npc in cursor:
        npc.pop("_id", None)
        # Don't include secrets in location listing
        npc.pop("secrets", None)
        npcs.append(npc)

    return {
        "location": {
            "world_id": world_id,
            "region_id": region_id,
            "location_id": location_id
        },
        "npcs": npcs,
        "total_npcs": len(npcs)
    }

@app.get("/mcp/npc-context/{npc_id}/{profile_id}")
async def get_npc_context(
    npc_id: str,
    profile_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get NPC context including relationship with player"""
    # Get NPC
    npc = await mongo_db.npcs.find_one({"npc_id": npc_id})

    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    npc.pop("_id", None)

    # Get interaction history
    interactions = []
    cursor = mongo_db.npc_interactions.find({
        "profile_id": profile_id,
        "npc_id": npc_id
    }).sort("timestamp", -1).limit(10)

    async for interaction in cursor:
        interaction.pop("_id", None)
        interactions.append(interaction)

    # Calculate relationship affinity
    total_affinity = sum(i.get("affinity_change", 0) for i in interactions)

    return {
        "npc": npc,
        "relationship": {
            "profile_id": profile_id,
            "total_affinity": total_affinity,
            "interaction_count": len(interactions),
            "recent_interactions": interactions
        }
    }

@app.get("/mcp/npc-dialogue/{npc_id}")
async def get_npc_dialogue(
    npc_id: str,
    situation: str = "greeting",
    mood: Optional[str] = None,
    token: str = Depends(verify_mcp_token)
):
    """Get dialogue templates for an NPC"""
    # Get NPC for mood if not specified
    if not mood:
        npc = await mongo_db.npcs.find_one({"npc_id": npc_id})
        if npc:
            mood = npc.get("current_mood", "neutral")
        else:
            mood = "neutral"

    # Find matching templates
    templates = []
    cursor = mongo_db.dialogue_templates.find({
        "npc_id": npc_id,
        "situation": situation,
        "mood": mood
    })

    async for template in cursor:
        template.pop("_id", None)
        templates.append(template)

    # If no exact match, try neutral mood
    if not templates and mood != "neutral":
        cursor = mongo_db.dialogue_templates.find({
            "npc_id": npc_id,
            "situation": situation,
            "mood": "neutral"
        })

        async for template in cursor:
            template.pop("_id", None)
            templates.append(template)

    return {
        "npc_id": npc_id,
        "situation": situation,
        "mood": mood,
        "templates": templates
    }

@app.get("/mcp/quest-npcs/{quest_id}")
async def get_quest_npcs(
    quest_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get all NPCs involved in a quest"""
    npcs = []

    # Find NPCs who give this quest
    cursor = mongo_db.npcs.find({"quests_given": quest_id})

    async for npc in cursor:
        npc.pop("_id", None)
        npc["role_in_quest"] = "giver"
        npcs.append(npc)

    # Find NPCs with roles in this quest
    cursor = mongo_db.npcs.find({f"quest_roles.{quest_id}": {"$exists": True}})

    async for npc in cursor:
        # Skip if already added as giver
        if any(n["npc_id"] == npc["npc_id"] for n in npcs):
            continue

        npc.pop("_id", None)
        npc["role_in_quest"] = npc["quest_roles"][quest_id]
        npcs.append(npc)

    return {
        "quest_id": quest_id,
        "npcs": npcs,
        "total_npcs": len(npcs)
    }

@app.post("/mcp/record-interaction")
async def record_interaction(
    interaction: NPCInteraction,
    token: str = Depends(verify_mcp_token)
):
    """Record a player-NPC interaction"""
    interaction_dict = interaction.dict()
    await mongo_db.npc_interactions.insert_one(interaction_dict)

    # Update NPC affinity if relationship exists
    if interaction.affinity_change != 0:
        npc = await mongo_db.npcs.find_one({"npc_id": interaction.npc_id})

        if npc:
            # Update or create relationship
            relationships = npc.get("relationships", [])
            found = False

            for rel in relationships:
                if rel.get("character_id") == interaction.profile_id:
                    rel["affinity"] = max(-100, min(100, rel["affinity"] + interaction.affinity_change))
                    found = True
                    break

            if not found:
                relationships.append({
                    "character_id": interaction.profile_id,
                    "relationship_type": "neutral",
                    "affinity": interaction.affinity_change,
                    "history": f"First met: {datetime.now().isoformat()}"
                })

            await mongo_db.npcs.update_one(
                {"npc_id": interaction.npc_id},
                {"$set": {"relationships": relationships, "updated_at": datetime.now()}}
            )

    interaction_dict.pop("_id", None)
    return {"status": "recorded", "interaction": interaction_dict}

@app.post("/mcp/update-npc-mood")
async def update_npc_mood(
    npc_id: str,
    mood: str,
    token: str = Depends(verify_mcp_token)
):
    """Update NPC's current mood"""
    result = await mongo_db.npcs.update_one(
        {"npc_id": npc_id},
        {"$set": {"current_mood": mood, "updated_at": datetime.now()}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="NPC not found")

    return {"status": "updated", "npc_id": npc_id, "new_mood": mood}

# ============================================
# Admin Endpoints
# ============================================

@app.post("/admin/create-npc")
async def create_npc(npc: NPC, token: str = Depends(verify_mcp_token)):
    """Create a new NPC"""
    npc_dict = npc.dict()
    await mongo_db.npcs.insert_one(npc_dict)

    # Invalidate cache
    cache_key = f"npc:{npc.npc_id}"
    await redis_client.delete(cache_key)

    return {"status": "created", "npc_id": npc.npc_id}

@app.post("/admin/create-dialogue-template")
async def create_dialogue_template(
    template: DialogueTemplate,
    token: str = Depends(verify_mcp_token)
):
    """Create a dialogue template"""
    template_dict = template.dict()
    await mongo_db.dialogue_templates.insert_one(template_dict)
    return {"status": "created", "template_id": template.template_id}

@app.put("/admin/update-npc/{npc_id}")
async def update_npc(
    npc_id: str,
    updates: Dict[str, Any],
    token: str = Depends(verify_mcp_token)
):
    """Update NPC data"""
    updates["updated_at"] = datetime.now()

    result = await mongo_db.npcs.update_one(
        {"npc_id": npc_id},
        {"$set": updates}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="NPC not found")

    # Invalidate cache
    cache_key = f"npc:{npc_id}"
    await redis_client.delete(cache_key)

    return {"status": "updated", "npc_id": npc_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
