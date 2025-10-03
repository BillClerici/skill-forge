"""
Quest/Mission MCP Server
Provides story arcs, objectives, and quest management for AI agents
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
    title="Quest/Mission MCP Server",
    description="MCP server for quest storylines, objectives, and mission management",
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

class QuestObjective(BaseModel):
    """Individual quest objective"""
    objective_id: str
    description: str
    objective_type: str  # collect, defeat, explore, interact, escort, investigate
    target: Optional[str] = None
    quantity: int = 1
    current_progress: int = 0
    is_completed: bool = False
    bloom_level: str = "Remember"  # Bloom's taxonomy level
    cognitive_skills: List[str] = []  # empathy, strategy, creativity, courage

class Quest(BaseModel):
    """Quest/Mission definition"""
    quest_id: str
    quest_name: str
    quest_type: str  # main, side, daily, event, tutorial
    description: str
    story_arc: Optional[str] = None  # Which larger story this belongs to
    prerequisites: List[str] = []  # Quest IDs that must be completed first
    objectives: List[QuestObjective]
    rewards: Dict[str, Any] = {}  # XP, items, unlocks
    difficulty_level: int = 1  # 1-10
    estimated_duration: int = 30  # minutes
    world_id: Optional[str] = None
    region_id: Optional[str] = None
    location_id: Optional[str] = None
    npc_giver: Optional[str] = None  # NPC who gives the quest
    status: str = "not_started"  # not_started, active, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class StoryArc(BaseModel):
    """Multi-quest story arc"""
    arc_id: str
    arc_name: str
    description: str
    theme: str  # overarching theme
    quest_chain: List[str]  # Ordered list of quest IDs
    current_chapter: int = 0
    world_id: str
    difficulty_progression: str = "linear"  # linear, branching, adaptive
    educational_focus: List[str] = []  # Key learning outcomes
    created_at: datetime = Field(default_factory=datetime.now)

class ActivePlayerQuest(BaseModel):
    """Player's active quest state"""
    player_quest_id: str
    profile_id: str
    quest_id: str
    status: str  # active, completed, failed, abandoned
    objectives_progress: Dict[str, int] = {}  # objective_id -> progress
    started_at: datetime
    completed_at: Optional[datetime] = None
    turn_history: List[Dict[str, Any]] = []  # Track player decisions

# ============================================
# MCP Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "service": "Quest/Mission MCP Server",
        "version": "1.0.0",
        "description": "Story arcs, objectives, and quest management"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp/quest/{quest_id}")
async def get_quest(
    quest_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get quest details by ID"""
    # Try cache first
    cache_key = f"quest:{quest_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Query MongoDB
    quest = await mongo_db.quests.find_one({"quest_id": quest_id})

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    # Remove MongoDB _id
    quest.pop("_id", None)

    # Cache for 1 hour
    await redis_client.setex(cache_key, 3600, json.dumps(quest, default=str))

    return quest

@app.get("/mcp/player-active-quests/{profile_id}")
async def get_player_active_quests(
    profile_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get all active quests for a player"""
    active_quests = []

    cursor = mongo_db.player_quests.find({
        "profile_id": profile_id,
        "status": "active"
    })

    async for player_quest in cursor:
        # Get full quest details
        quest = await mongo_db.quests.find_one({"quest_id": player_quest["quest_id"]})

        if quest:
            quest.pop("_id", None)
            player_quest.pop("_id", None)

            active_quests.append({
                "player_quest": player_quest,
                "quest_details": quest
            })

    return {
        "profile_id": profile_id,
        "active_quests": active_quests,
        "total_active": len(active_quests)
    }

@app.get("/mcp/available-quests/{profile_id}")
async def get_available_quests(
    profile_id: str,
    world_id: Optional[str] = None,
    region_id: Optional[str] = None,
    location_id: Optional[str] = None,
    token: str = Depends(verify_mcp_token)
):
    """Get quests available to a player based on location and prerequisites"""

    # Get player's completed quests
    completed_quest_ids = []
    completed_cursor = mongo_db.player_quests.find({
        "profile_id": profile_id,
        "status": "completed"
    })

    async for pq in completed_cursor:
        completed_quest_ids.append(pq["quest_id"])

    # Get player's active quests
    active_quest_ids = []
    active_cursor = mongo_db.player_quests.find({
        "profile_id": profile_id,
        "status": "active"
    })

    async for pq in active_cursor:
        active_quest_ids.append(pq["quest_id"])

    # Build query for available quests
    query = {"status": "not_started"}

    if world_id:
        query["world_id"] = world_id
    if region_id:
        query["region_id"] = region_id
    if location_id:
        query["location_id"] = location_id

    available_quests = []
    cursor = mongo_db.quests.find(query)

    async for quest in cursor:
        quest_id = quest["quest_id"]

        # Skip if already active or completed
        if quest_id in active_quest_ids or quest_id in completed_quest_ids:
            continue

        # Check prerequisites
        prerequisites = quest.get("prerequisites", [])
        prerequisites_met = all(prereq in completed_quest_ids for prereq in prerequisites)

        if prerequisites_met:
            quest.pop("_id", None)
            available_quests.append(quest)

    return {
        "profile_id": profile_id,
        "location_context": {
            "world_id": world_id,
            "region_id": region_id,
            "location_id": location_id
        },
        "available_quests": available_quests,
        "total_available": len(available_quests)
    }

@app.get("/mcp/story-arc/{arc_id}")
async def get_story_arc(
    arc_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get story arc details"""
    arc = await mongo_db.story_arcs.find_one({"arc_id": arc_id})

    if not arc:
        raise HTTPException(status_code=404, detail="Story arc not found")

    arc.pop("_id", None)

    # Get all quests in the arc
    quest_chain = arc.get("quest_chain", [])
    quests = []

    for quest_id in quest_chain:
        quest = await mongo_db.quests.find_one({"quest_id": quest_id})
        if quest:
            quest.pop("_id", None)
            quests.append(quest)

    return {
        "story_arc": arc,
        "quests": quests
    }

@app.get("/mcp/world-quests/{world_id}")
async def get_world_quests(
    world_id: str,
    quest_type: Optional[str] = None,
    token: str = Depends(verify_mcp_token)
):
    """Get all quests for a world"""
    query = {"world_id": world_id}

    if quest_type:
        query["quest_type"] = quest_type

    quests = []
    cursor = mongo_db.quests.find(query)

    async for quest in cursor:
        quest.pop("_id", None)
        quests.append(quest)

    return {
        "world_id": world_id,
        "quest_type": quest_type,
        "quests": quests,
        "total_quests": len(quests)
    }

@app.post("/mcp/update-quest-progress")
async def update_quest_progress(
    profile_id: str,
    quest_id: str,
    objective_id: str,
    progress: int,
    token: str = Depends(verify_mcp_token)
):
    """Update progress on a quest objective"""

    # Find player's quest
    player_quest = await mongo_db.player_quests.find_one({
        "profile_id": profile_id,
        "quest_id": quest_id,
        "status": "active"
    })

    if not player_quest:
        raise HTTPException(status_code=404, detail="Active quest not found for player")

    # Update progress
    objectives_progress = player_quest.get("objectives_progress", {})
    objectives_progress[objective_id] = progress

    # Check if quest is complete
    quest = await mongo_db.quests.find_one({"quest_id": quest_id})
    all_objectives_complete = True

    for objective in quest.get("objectives", []):
        obj_id = objective["objective_id"]
        required = objective.get("quantity", 1)
        current = objectives_progress.get(obj_id, 0)

        if current < required:
            all_objectives_complete = False
            break

    # Update player quest
    update_data = {
        "objectives_progress": objectives_progress,
        "updated_at": datetime.now()
    }

    if all_objectives_complete:
        update_data["status"] = "completed"
        update_data["completed_at"] = datetime.now()

    await mongo_db.player_quests.update_one(
        {"_id": player_quest["_id"]},
        {"$set": update_data}
    )

    return {
        "profile_id": profile_id,
        "quest_id": quest_id,
        "objective_id": objective_id,
        "new_progress": progress,
        "quest_completed": all_objectives_complete
    }

@app.post("/mcp/start-quest")
async def start_quest(
    profile_id: str,
    quest_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Start a quest for a player"""

    # Check if quest exists
    quest = await mongo_db.quests.find_one({"quest_id": quest_id})
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    # Check if already active
    existing = await mongo_db.player_quests.find_one({
        "profile_id": profile_id,
        "quest_id": quest_id,
        "status": "active"
    })

    if existing:
        raise HTTPException(status_code=400, detail="Quest already active")

    # Create player quest
    player_quest = {
        "player_quest_id": f"{profile_id}_{quest_id}_{int(datetime.now().timestamp())}",
        "profile_id": profile_id,
        "quest_id": quest_id,
        "status": "active",
        "objectives_progress": {},
        "started_at": datetime.now(),
        "turn_history": []
    }

    await mongo_db.player_quests.insert_one(player_quest)
    player_quest.pop("_id", None)

    return player_quest

# ============================================
# Admin Endpoints (for creating quests)
# ============================================

@app.post("/admin/create-quest")
async def create_quest(quest: Quest, token: str = Depends(verify_mcp_token)):
    """Create a new quest"""
    quest_dict = quest.dict()
    await mongo_db.quests.insert_one(quest_dict)
    return {"status": "created", "quest_id": quest.quest_id}

@app.post("/admin/create-story-arc")
async def create_story_arc(arc: StoryArc, token: str = Depends(verify_mcp_token)):
    """Create a new story arc"""
    arc_dict = arc.dict()
    await mongo_db.story_arcs.insert_one(arc_dict)
    return {"status": "created", "arc_id": arc.arc_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
