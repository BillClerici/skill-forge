"""
Agent Orchestrator
Manages agent lifecycle, cost tracking, and resource allocation
"""
import os
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient
import httpx
import json

# ============================================
# Configuration
# ============================================

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
MCP_PLAYER_DATA_URL = os.getenv("MCP_PLAYER_DATA_URL", "http://mcp-player-data:8001")
MCP_WORLD_UNIVERSE_URL = os.getenv("MCP_WORLD_UNIVERSE_URL", "http://mcp-world-universe:8002")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")
GAME_MASTER_URL = os.getenv("GAME_MASTER_URL", "http://agent-game-master:8000")

# Cost tracking limits (in USD)
DAILY_BUDGET_LIMITS = {
    "free": 0.50,
    "individual": 2.00,
    "family": 5.00,
    "educational": 10.00,
    "organizational": 20.00
}

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Agent Orchestrator",
    description="Manages AI agent lifecycle, cost tracking, and resource allocation",
    version="1.0.0"
)

# ============================================
# Database Clients
# ============================================

redis_client: Optional[Redis] = None
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
# Request/Response Models
# ============================================

class StartCampaignRequest(BaseModel):
    profile_id: UUID
    character_name: str
    universe_id: UUID
    world_id: UUID
    campaign_name: str

class PlayerActionRequest(BaseModel):
    campaign_id: UUID
    profile_id: UUID
    action_type: str
    action_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class NarrativeResponse(BaseModel):
    campaign_id: str
    profile_id: str
    narrative_text: str
    choices: List[Dict[str, Any]]
    image_prompt: Optional[str] = None
    cognitive_skill_updates: Dict[str, int]
    cost_usd: float
    tokens_used: int

class CostTrackingResponse(BaseModel):
    account_id: str
    subscription_tier: str
    daily_cost: float
    daily_limit: float
    remaining_budget: float
    is_throttled: bool

class GenerateBackstoryRequest(BaseModel):
    world_id: str
    world_name: str
    genre: str
    setting: str = ""
    themes: List[str]
    visual_style: List[str]
    power_system: Optional[str] = None
    physical_properties: Optional[dict] = None
    biological_properties: Optional[dict] = None
    technological_properties: Optional[dict] = None
    societal_properties: Optional[dict] = None
    historical_properties: Optional[dict] = None
    # Legacy fields for backward compatibility
    history: Optional[str] = None
    geography: Optional[str] = None
    culture: Optional[str] = None

class GenerateBackstoryResponse(BaseModel):
    backstory: str
    tokens_used: int
    cost_usd: float

class GenerateRegionBackstoryRequest(BaseModel):
    region_id: str
    region_name: str
    region_type: str
    climate: str
    terrain: List[str]
    description: str
    world_name: Optional[str] = None
    world_genre: Optional[str] = None

class GenerateLocationBackstoryRequest(BaseModel):
    location_id: str
    location_name: str
    location_type: str
    description: str
    features: List[str]
    region_name: Optional[str] = None
    world_name: Optional[str] = None

class GenerateCharacterBackstoryRequest(BaseModel):
    character_id: str
    character_name: str
    title: Optional[str] = ""
    description: Optional[str] = ""
    age: Optional[str] = ""
    height: Optional[str] = ""
    appearance: Optional[str] = ""
    blooms_level: str
    player_name: str
    attributes: Optional[List[str]] = []
    skills: Optional[List[str]] = []
    personality_traits: Optional[List[str]] = []
    voice_type: Optional[str] = ""
    accent: Optional[str] = ""
    speaking_patterns: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    speech_quirks: Optional[str] = ""

class GenerateCampaignRequest(BaseModel):
    genre: str
    world: Dict[str, Any]
    region: Optional[Dict[str, Any]] = None
    locations: List[Dict[str, Any]]
    species: List[Dict[str, Any]]
    story_outline: str
    num_quests: int = 5

class GenerateCampaignResponse(BaseModel):
    campaign_description: str
    campaign_backstory: str
    primary_locations: List[str]
    key_npcs: List[str]
    main_goals: List[str]
    quests: List[Dict[str, Any]]
    tokens_used: int
    cost_usd: float

class GenerateRegionsRequest(BaseModel):
    world_context: Dict[str, Any]
    num_regions: int
    num_locations_per_region: int

class GenerateRegionsResponse(BaseModel):
    regions: List[Dict[str, Any]]
    tokens_used: int
    cost_usd: float

class GenerateLocationsRequest(BaseModel):
    world_name: str
    world_genre: str
    world_backstory: str
    region_name: str
    region_type: str
    climate: str
    terrain: List[str]
    region_description: str
    region_backstory: str
    num_locations: int

class GenerateLocationsResponse(BaseModel):
    locations: List[Dict[str, Any]]
    tokens_used: int
    cost_usd: float

# ============================================
# Cost Tracking
# ============================================

async def track_cost(account_id: UUID, subscription_tier: str, tokens_used: int, cost: float):
    """Track AI costs and enforce budget limits"""
    # Increment daily cost
    key = f"ai_cost:{account_id}:{date.today()}"
    await redis_client.incrbyfloat(key, cost)
    await redis_client.expire(key, 86400 * 2)  # Keep for 2 days

    # Get daily budget limit
    budget_limit = DAILY_BUDGET_LIMITS.get(subscription_tier.lower(), DAILY_BUDGET_LIMITS["free"])

    # Check if over budget
    daily_cost = float(await redis_client.get(key) or 0)

    if daily_cost >= budget_limit:
        # Throttle account
        throttle_key = f"throttled:{account_id}"
        await redis_client.setex(throttle_key, 86400, "1")

        return {
            "throttled": True,
            "daily_cost": daily_cost,
            "budget_limit": budget_limit
        }

    return {
        "throttled": False,
        "daily_cost": daily_cost,
        "budget_limit": budget_limit
    }

async def is_account_throttled(account_id: UUID) -> bool:
    """Check if account is throttled"""
    throttle_key = f"throttled:{account_id}"
    return await redis_client.exists(throttle_key) > 0

async def get_cost_tracking(account_id: UUID, subscription_tier: str) -> CostTrackingResponse:
    """Get cost tracking info for an account"""
    key = f"ai_cost:{account_id}:{date.today()}"
    daily_cost = float(await redis_client.get(key) or 0)
    daily_limit = DAILY_BUDGET_LIMITS.get(subscription_tier.lower(), DAILY_BUDGET_LIMITS["free"])

    is_throttled = await is_account_throttled(account_id)

    return CostTrackingResponse(
        account_id=str(account_id),
        subscription_tier=subscription_tier,
        daily_cost=daily_cost,
        daily_limit=daily_limit,
        remaining_budget=max(0, daily_limit - daily_cost),
        is_throttled=is_throttled
    )

# ============================================
# Session Management
# ============================================

async def get_or_create_campaign_session(campaign_id: UUID, profile_id: UUID) -> Dict[str, Any]:
    """Get or create a campaign session"""
    session_key = f"campaign_session:{campaign_id}"

    # Try to get existing session from Redis
    session_data = await redis_client.get(session_key)

    if session_data:
        return json.loads(session_data)

    # Create new session
    session = {
        "campaign_id": str(campaign_id),
        "profile_id": str(profile_id),
        "turn_count": 0,
        "created_at": datetime.now().isoformat(),
        "last_action_at": datetime.now().isoformat()
    }

    await redis_client.setex(session_key, 3600 * 24, json.dumps(session))

    return session

async def save_campaign_session(campaign_id: UUID, session_data: Dict[str, Any]):
    """Save campaign session to Redis"""
    session_key = f"campaign_session:{campaign_id}"
    await redis_client.setex(session_key, 3600 * 24, json.dumps(session_data))

# ============================================
# Agent Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "service": "Agent Orchestrator",
        "version": "1.0.0",
        "description": "Manages AI agent lifecycle and cost tracking"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/start-campaign", response_model=NarrativeResponse)
async def start_campaign(request: StartCampaignRequest):
    """Start a new campaign with AI Game Master"""

    # Get account info (would normally come from auth context)
    # For now, using placeholder
    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    # Check if throttled
    if await is_account_throttled(account_id):
        raise HTTPException(
            status_code=429,
            detail="Daily AI budget limit reached. Please upgrade your subscription or try again tomorrow."
        )

    # Forward to Game Master Agent
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/start-campaign",
                json={
                    "profile_id": str(request.profile_id),
                    "character_name": request.character_name,
                    "universe_id": str(request.universe_id),
                    "world_id": str(request.world_id),
                    "campaign_name": request.campaign_name
                },
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()

            # Track cost
            await track_cost(
                account_id,
                subscription_tier,
                result.get("tokens_used", 0),
                result.get("cost_usd", 0)
            )

            return NarrativeResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/process-action", response_model=NarrativeResponse)
async def process_action(request: PlayerActionRequest):
    """Process player action and get AI response"""

    # Get account info (would normally come from auth context)
    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    # Check if throttled
    if await is_account_throttled(account_id):
        raise HTTPException(
            status_code=429,
            detail="Daily AI budget limit reached. Please upgrade your subscription or try again tomorrow."
        )

    # Get or create session
    session = await get_or_create_campaign_session(request.campaign_id, request.profile_id)

    # Forward to Game Master Agent
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/process-action",
                json={
                    "campaign_id": str(request.campaign_id),
                    "profile_id": str(request.profile_id),
                    "action_type": request.action_type,
                    "action_text": request.action_text,
                    "metadata": request.metadata or {},
                    "session": session
                },
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()

            # Track cost
            await track_cost(
                account_id,
                subscription_tier,
                result.get("tokens_used", 0),
                result.get("cost_usd", 0)
            )

            # Update session
            session["turn_count"] += 1
            session["last_action_at"] = datetime.now().isoformat()
            await save_campaign_session(request.campaign_id, session)

            return NarrativeResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.get("/cost-tracking/{account_id}")
async def cost_tracking(account_id: UUID, subscription_tier: str = "family"):
    """Get cost tracking information for an account"""
    return await get_cost_tracking(account_id, subscription_tier)

@app.post("/reset-throttle/{account_id}")
async def reset_throttle(account_id: UUID):
    """Reset throttle for an account (admin only)"""
    throttle_key = f"throttled:{account_id}"
    await redis_client.delete(throttle_key)
    return {"status": "success", "message": "Throttle reset"}

@app.post("/generate-backstory", response_model=GenerateBackstoryResponse)
async def generate_backstory(request: GenerateBackstoryRequest):
    """Generate creative backstory for a world using AI"""

    # Get account info (would normally come from auth context)
    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    # Check if throttled
    if await is_account_throttled(account_id):
        raise HTTPException(
            status_code=429,
            detail="Daily AI budget limit reached. Please upgrade your subscription or try again tomorrow."
        )

    # Forward to Game Master Agent
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-world-backstory",
                json={
                    "world_id": request.world_id,
                    "world_name": request.world_name,
                    "genre": request.genre,
                    "setting": request.setting,
                    "themes": request.themes,
                    "visual_style": request.visual_style,
                    "power_system": request.power_system,
                    "physical_properties": request.physical_properties,
                    "biological_properties": request.biological_properties,
                    "technological_properties": request.technological_properties,
                    "societal_properties": request.societal_properties,
                    "historical_properties": request.historical_properties,
                    # Legacy fields
                    "history": request.history,
                    "geography": request.geography,
                    "culture": request.culture
                },
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()

            # Track cost
            await track_cost(
                account_id,
                subscription_tier,
                result.get("tokens_used", 0),
                result.get("cost_usd", 0)
            )

            return GenerateBackstoryResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/generate-timeline")
async def generate_timeline(request: Dict[str, Any]):
    """Generate historical timeline for a world based on its backstory"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-world-timeline",
                json=request,
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()

            # Track cost
            await track_cost(
                account_id,
                subscription_tier,
                result.get("tokens_used", 0),
                result.get("cost_usd", 0)
            )

            return result

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating timeline: {str(e)}")

@app.post("/generate-species")
async def generate_species(request: Dict[str, Any]):
    """Generate species for a world using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-world-species",
                json=request,
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()

            # Track cost
            await track_cost(
                account_id,
                subscription_tier,
                result.get("tokens_used", 0),
                result.get("cost_usd", 0)
            )

            return result

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating species: {str(e)}")

@app.post("/generate-region-backstory", response_model=GenerateBackstoryResponse)
async def generate_region_backstory(request: GenerateRegionBackstoryRequest):
    """Generate creative backstory for a region using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-region-backstory",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateBackstoryResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/generate-location-backstory", response_model=GenerateBackstoryResponse)
async def generate_location_backstory(request: GenerateLocationBackstoryRequest):
    """Generate creative backstory for a location using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-location-backstory",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateBackstoryResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/api/generate-regions", response_model=GenerateRegionsResponse)
async def generate_regions(request: GenerateRegionsRequest):
    """Generate multiple regions with backstories and locations using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for batch generation
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-regions",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateRegionsResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/api/generate-locations", response_model=GenerateLocationsResponse)
async def generate_locations(request: GenerateLocationsRequest):
    """Generate multiple locations for a region using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=180.0) as client:  # 3 minute timeout
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-locations",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateLocationsResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/api/generate-locations-hierarchical", response_model=GenerateLocationsResponse)
async def generate_locations_hierarchical(request: Dict[str, Any]):
    """Generate locations with hierarchical type constraints using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=180.0) as client:  # 3 minute timeout
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-locations-hierarchical",
                json=request,
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateLocationsResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/generate-character-backstory", response_model=GenerateBackstoryResponse)
async def generate_character_backstory(request: GenerateCharacterBackstoryRequest):
    """Generate creative backstory for a character using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-character-backstory",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateBackstoryResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

@app.post("/generate-campaign", response_model=GenerateCampaignResponse)
async def generate_campaign(request: GenerateCampaignRequest):
    """Generate complete campaign with quests and Bloom's Taxonomy tasks using AI"""

    account_id = UUID("b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f")
    subscription_tier = "family"

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for campaign generation
        try:
            response = await client.post(
                f"{GAME_MASTER_URL}/generate-campaign",
                json=request.dict(),
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            result = response.json()
            await track_cost(account_id, subscription_tier, result.get("tokens_used", 0), result.get("cost_usd", 0))
            return GenerateCampaignResponse(**result)

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="AI agent request timed out after 5 minutes")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with Game Master: {str(e)}")

# ============================================
# Campaign Wizard Endpoints
# ============================================

@app.post("/campaign-wizard/start")
async def start_campaign_wizard(request: Dict[str, Any]):
    """
    Start campaign wizard workflow

    Publishes message to RabbitMQ campaign_generation_queue
    """
    import aio_pika

    account_id = UUID(request.get("user_id", "b1fbc0c6-7a49-40ba-9ec4-d4b69ae5387f"))
    subscription_tier = request.get("subscription_tier", "family")

    if await is_account_throttled(account_id):
        raise HTTPException(status_code=429, detail="Daily AI budget limit reached")

    try:
        request_id = request.get("request_id", str(UUID(int=0)))

        # Create initial Redis progress entry BEFORE publishing to RabbitMQ
        # This prevents 404 errors when frontend starts polling immediately
        progress_key = f"campaign:progress:{request_id}"
        initial_progress = {
            "request_id": request_id,
            "user_id": str(account_id),
            "campaign_name": request.get("campaign_name", "Untitled Campaign"),
            "universe_name": request.get("universe_name"),
            "world_name": request.get("world_name"),
            "region_name": request.get("region_name"),
            "progress_percentage": 0,
            "status_message": "Initializing campaign generation...",
            "current_phase": "init",
            "current_node": "",
            "story_ideas": [],
            "campaign_core": None,
            "quests": [],
            "places": [],
            "scenes": [],
            "npcs": [],
            "discoveries": [],
            "events": [],
            "challenges": [],
            "new_location_ids": [],
            "new_locations": [],
            "final_campaign_id": None,
            "errors": [],
            "warnings": [],
            "created_at": datetime.now().isoformat()
        }
        await redis_client.setex(progress_key, 86400, json.dumps(initial_progress))

        # Connect to RabbitMQ
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            # Prepare campaign request message
            campaign_message = {
                "request_id": request_id,
                "user_id": str(account_id),
                "character_id": request.get("character_id"),
                "universe_id": request.get("universe_id"),
                "universe_name": request.get("universe_name"),
                "world_id": request.get("world_id"),
                "world_name": request.get("world_name"),
                "region_id": request.get("region_id"),
                "region_name": request.get("region_name"),
                "genre": request.get("genre"),
                "user_story_idea": request.get("user_story_idea"),
                "workflow_action": "start"
            }

            # Publish to campaign generation queue
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "started",
                "request_id": campaign_message["request_id"],
                "message": "Campaign generation workflow started"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting campaign workflow: {str(e)}")

@app.post("/campaign-wizard/select-story")
async def select_story(request: Dict[str, Any]):
    """
    User selects a story idea

    Publishes message to resume workflow
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "selected_story_id": request.get("selected_story_id"),
                "workflow_action": "select_story"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "story_selected",
                "request_id": campaign_message["request_id"]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error selecting story: {str(e)}")

@app.post("/campaign-wizard/regenerate-stories")
async def regenerate_stories(request: Dict[str, Any]):
    """
    User requests story regeneration
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "workflow_action": "regenerate_stories"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "regenerating",
                "request_id": campaign_message["request_id"]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error regenerating stories: {str(e)}")

@app.post("/campaign-wizard/approve-core")
async def approve_campaign_core(request: Dict[str, Any]):
    """
    User approves campaign core and provides quest specifications

    This triggers the full campaign generation
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "user_approved_core": request.get("user_approved_core", True),
                "num_quests": request.get("num_quests", 5),
                "quest_difficulty": request.get("quest_difficulty", "Medium"),
                "quest_playtime_minutes": request.get("quest_playtime_minutes", 90),
                "generate_images": request.get("generate_images", True),
                "workflow_action": "approve_core"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "generating",
                "request_id": campaign_message["request_id"],
                "message": "Full campaign generation started"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving campaign core: {str(e)}")

@app.post("/campaign-wizard/approve-quests")
async def approve_quests(request: Dict[str, Any]):
    """
    User approves quests and triggers place generation

    This resumes the workflow to generate places (Level 2 locations)
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "user_approved_quests": request.get("user_approved_quests", True),
                "workflow_action": "approve_quests"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "generating_places",
                "request_id": campaign_message["request_id"],
                "message": "Place generation started"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving quests: {str(e)}")

@app.post("/campaign-wizard/approve-places")
async def approve_places(request: Dict[str, Any]):
    """
    User approves places and triggers scene generation

    This resumes the workflow to generate scenes (Level 3 locations) and elements
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "user_approved_places": request.get("user_approved_places", True),
                "workflow_action": "approve_places"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            return {
                "status": "generating_scenes",
                "request_id": campaign_message["request_id"],
                "message": "Scene and element generation started"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving places: {str(e)}")

@app.post("/campaign-wizard/finalize")
async def finalize_campaign(request: Dict[str, Any]):
    """
    Finalize campaign and persist to database

    This triggers the final workflow step to save everything to MongoDB/Neo4j
    """
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "workflow_action": "finalize"
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(campaign_message).encode(),
                    content_type="application/json"
                ),
                routing_key="campaign_generation_queue"
            )

            # Wait briefly for the workflow to process
            # Then check Redis for the campaign ID
            import asyncio
            await asyncio.sleep(2)  # Give workflow time to start finalization

            # Check Redis for completion (poll up to 30 seconds)
            for _ in range(15):
                progress_key = f"campaign:progress:{request.get('request_id')}"
                progress_data = await redis_client.get(progress_key)

                if progress_data:
                    data = json.loads(progress_data)
                    campaign_id = data.get("final_campaign_id")

                    if campaign_id:
                        return {
                            "status": "completed",
                            "campaign_id": campaign_id,
                            "message": "Campaign finalized successfully"
                        }

                await asyncio.sleep(2)

            # If we get here, finalization is still in progress
            return {
                "status": "finalizing",
                "request_id": request.get("request_id"),
                "message": "Finalization in progress"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finalizing campaign: {str(e)}")

@app.get("/campaign-wizard/status/{request_id}")
async def get_campaign_status(request_id: str):
    """
    Get campaign generation status

    Checks Redis for workflow progress
    """
    try:
        # Get progress from Redis
        progress_key = f"campaign:progress:{request_id}"
        progress_data = await redis_client.get(progress_key)

        if not progress_data:
            raise HTTPException(status_code=404, detail="Campaign request not found")

        return json.loads(progress_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting campaign status: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
