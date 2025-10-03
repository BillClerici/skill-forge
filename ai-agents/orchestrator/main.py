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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
