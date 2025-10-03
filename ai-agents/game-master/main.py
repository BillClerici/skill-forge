"""
AI Game Master Agent
Core narrative generation and gameplay experience using LangGraph
"""
import os
from typing import Optional, Dict, Any, List, TypedDict, Annotated
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import httpx
import json

# LangChain imports
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain.schema import HumanMessage, SystemMessage
from fastapi.responses import StreamingResponse

# Local imports
from memory_manager import MemoryManager
from analytics_tracker import AnalyticsTracker

# ============================================
# Configuration
# ============================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MCP_PLAYER_DATA_URL = os.getenv("MCP_PLAYER_DATA_URL", "http://mcp-player-data:8001")
MCP_WORLD_UNIVERSE_URL = os.getenv("MCP_WORLD_UNIVERSE_URL", "http://mcp-world-universe:8002")
MCP_QUEST_MISSION_URL = os.getenv("MCP_QUEST_MISSION_URL", "http://mcp-quest-mission:8003")
MCP_NPC_PERSONALITY_URL = os.getenv("MCP_NPC_PERSONALITY_URL", "http://mcp-npc-personality:8004")
MCP_ITEM_EQUIPMENT_URL = os.getenv("MCP_ITEM_EQUIPMENT_URL", "http://mcp-item-equipment:8005")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# Initialize memory and analytics
memory_manager = MemoryManager()
analytics_tracker = AnalyticsTracker()

# Claude pricing (input/output per million tokens)
CLAUDE_PRICING = {
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-sonnet-3-5": {"input": 3.00, "output": 15.00}
}

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="AI Game Master Agent",
    description="LangGraph-powered narrative generation agent",
    version="1.0.0"
)

# ============================================
# State Definition for LangGraph
# ============================================

class AgentState(TypedDict):
    # Input
    profile_id: str
    character_name: str
    universe_id: str
    world_id: str
    campaign_name: Optional[str]
    action_type: Optional[str]
    action_text: Optional[str]

    # Context from MCP
    player_profile: Optional[Dict[str, Any]]
    universe_guidelines: Optional[Dict[str, Any]]
    world_lore: Optional[Dict[str, Any]]

    # Generated content
    narrative_text: Optional[str]
    choices: Optional[List[Dict[str, Any]]]
    image_prompt: Optional[str]
    cognitive_skill_updates: Optional[Dict[str, int]]

    # Metadata
    tokens_used: int
    cost_usd: float
    error: Optional[str]

# ============================================
# MCP Client
# ============================================

class MCPClient:
    """Client for calling MCP servers"""

    def __init__(self):
        self.player_data_url = MCP_PLAYER_DATA_URL
        self.world_universe_url = MCP_WORLD_UNIVERSE_URL
        self.headers = {"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}

    async def get_player_cognitive_profile(self, player_id: UUID):
        """Get player's cognitive profile from MCP"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.player_data_url}/mcp/player-cognitive-profile/{player_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_universe_guidelines(self, universe_id: UUID):
        """Get universe guidelines from MCP"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.world_universe_url}/mcp/universe-guidelines/{universe_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_world_lore(self, world_id: UUID, universe_id: Optional[UUID] = None):
        """Get world lore from MCP"""
        url = f"{self.world_universe_url}/mcp/world-lore/{world_id}"
        if universe_id:
            url += f"?universe_id={universe_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None

mcp_client = MCPClient()

# ============================================
# LangGraph Agent Implementation
# ============================================

# Initialize Claude models
llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    anthropic_api_key=ANTHROPIC_API_KEY if ANTHROPIC_API_KEY else None,
    temperature=0.7,
    max_tokens=4096
)

# Smaller model for simple interactions (cost optimization)
llm_haiku = ChatAnthropic(
    model="claude-3-5-haiku-20241022",
    anthropic_api_key=ANTHROPIC_API_KEY if ANTHROPIC_API_KEY else None,
    temperature=0.7,
    max_tokens=2048
)

# Streaming model
llm_streaming = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    anthropic_api_key=ANTHROPIC_API_KEY if ANTHROPIC_API_KEY else None,
    temperature=0.7,
    max_tokens=4096,
    streaming=True
)

async def gather_context(state: AgentState) -> AgentState:
    """Step 1: Gather context from MCP servers"""
    try:
        # Get player profile
        player_profile = await mcp_client.get_player_cognitive_profile(
            UUID(state["profile_id"])
        )

        # Get universe guidelines
        universe_guidelines = await mcp_client.get_universe_guidelines(
            UUID(state["universe_id"])
        )

        # Get world lore
        world_lore = await mcp_client.get_world_lore(
            UUID(state["world_id"]),
            UUID(state["universe_id"])
        )

        state["player_profile"] = player_profile
        state["universe_guidelines"] = universe_guidelines
        state["world_lore"] = world_lore

    except Exception as e:
        state["error"] = f"Error gathering context: {str(e)}"

    return state

async def generate_narrative(state: AgentState) -> AgentState:
    """Step 2: Generate narrative using Claude"""
    try:
        if state.get("error"):
            return state

        # Build system prompt
        system_prompt = build_system_prompt(state)

        # Build user prompt
        if state.get("action_text"):
            # Processing a player action
            user_prompt = f"""
            The player "{state['character_name']}" has taken the following action:
            Action Type: {state.get('action_type', 'unknown')}
            Action: {state.get('action_text')}

            Please respond with:
            1. A vivid, engaging narrative describing what happens as a result of this action
            2. 2-3 meaningful choices for what the player can do next
            3. A brief image description that could be used to generate a scene illustration
            4. Any cognitive skill updates this action demonstrates (empathy, strategy, creativity, courage)
            """
        else:
            # Starting a new campaign
            user_prompt = f"""
            Begin a new adventure for {state['character_name']} in the world of {state['world_lore'].get('world_name', 'unknown')}.

            Campaign: {state.get('campaign_name', 'Untitled Adventure')}

            Please create:
            1. An engaging opening scene that introduces the character to the world
            2. 2-3 initial choices that set the tone for the adventure
            3. A vivid image description for the opening scene
            4. Set initial cognitive engagement (which skills this opening highlights)
            """

        # Call Claude
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = llm.invoke(messages)

        # Parse response
        narrative_result = parse_narrative_response(response.content)

        state["narrative_text"] = narrative_result["narrative"]
        state["choices"] = narrative_result["choices"]
        state["image_prompt"] = narrative_result["image_prompt"]
        state["cognitive_skill_updates"] = narrative_result["skill_updates"]

        # Calculate cost
        tokens_used = response.response_metadata.get("usage", {})
        input_tokens = tokens_used.get("input_tokens", 0)
        output_tokens = tokens_used.get("output_tokens", 0)

        cost = (input_tokens / 1_000_000 * CLAUDE_PRICING["claude-sonnet-4"]["input"]) + \
               (output_tokens / 1_000_000 * CLAUDE_PRICING["claude-sonnet-4"]["output"])

        state["tokens_used"] = input_tokens + output_tokens
        state["cost_usd"] = cost

    except Exception as e:
        state["error"] = f"Error generating narrative: {str(e)}"
        state["tokens_used"] = 0
        state["cost_usd"] = 0.0

    return state

def build_system_prompt(state: AgentState) -> str:
    """Build comprehensive system prompt for Claude"""
    player = state.get("player_profile", {})
    universe = state.get("universe_guidelines", {})
    world = state.get("world_lore", {})

    return f"""You are an expert AI Game Master for an educational RPG called SkillForge.

PLAYER CONTEXT:
- Name: {state.get('character_name')}
- Age: {player.get('age', 'unknown')}
- Current Bloom's Tier: {player.get('current_bloom_tier', 'Remember')}
- Empathy Level: {player.get('empathy_level', 1)}/10
- Strategy Level: {player.get('strategy_level', 1)}/10
- Creativity Level: {player.get('creativity_level', 1)}/10
- Courage Level: {player.get('courage_level', 1)}/10

UNIVERSE GUIDELINES:
- Universe: {universe.get('universe_name', 'Default Universe')}
- Content Rating: {universe.get('max_content_rating', 'PG')}
- Tone: {universe.get('narrative_tone', {}).get('style', 'friendly')}
- Reading Level: {universe.get('vocabulary_style', {}).get('reading_level', 'middle_school')}

WORLD SETTING:
- World: {world.get('world_name', 'Default World')}
- Genre: {world.get('genre', 'fantasy')}
- Themes: {', '.join(world.get('themes', ['adventure']))}
- Visual Style: {world.get('visual_style', 'watercolor fantasy')}

INSTRUCTIONS:
1. Generate engaging narratives that match the content rating and reading level
2. Create choices that challenge the player at their current cognitive level
3. Encourage development of cognitive skills (empathy, strategy, creativity, courage)
4. Keep descriptions vivid but age-appropriate
5. Return your response in the following JSON format:

{{
  "narrative": "The narrative text describing what happens...",
  "choices": [
    {{"id": "choice_1", "text": "Choice description", "bloom_level": "Understand", "skills": ["empathy"]}},
    {{"id": "choice_2", "text": "Choice description", "bloom_level": "Apply", "skills": ["strategy"]}}
  ],
  "image_prompt": "A description for an image generator...",
  "skill_updates": {{"empathy": 1, "strategy": 0, "creativity": 1, "courage": 0}}
}}

IMPORTANT: Your entire response must be valid JSON. Do not include any text outside the JSON structure.
"""

def parse_narrative_response(response_text: str) -> Dict[str, Any]:
    """Parse Claude's response into structured format"""
    try:
        # Try to parse as JSON
        result = json.loads(response_text)
        return {
            "narrative": result.get("narrative", ""),
            "choices": result.get("choices", []),
            "image_prompt": result.get("image_prompt", ""),
            "skill_updates": result.get("skill_updates", {})
        }
    except json.JSONDecodeError:
        # Fallback: extract what we can
        return {
            "narrative": response_text[:1000] if response_text else "An error occurred generating the narrative.",
            "choices": [
                {"id": "choice_1", "text": "Continue the adventure", "bloom_level": "Remember", "skills": []},
                {"id": "choice_2", "text": "Explore the area", "bloom_level": "Understand", "skills": ["strategy"]}
            ],
            "image_prompt": "A fantasy scene",
            "skill_updates": {}
        }

# Build LangGraph workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("gather_context", gather_context)
workflow.add_node("generate_narrative", generate_narrative)

# Add edges
workflow.set_entry_point("gather_context")
workflow.add_edge("gather_context", "generate_narrative")
workflow.add_edge("generate_narrative", END)

# Compile the graph
agent_graph = workflow.compile()

# ============================================
# FastAPI Endpoints
# ============================================

class StartCampaignRequest(BaseModel):
    profile_id: str
    character_name: str
    universe_id: str
    world_id: str
    campaign_name: str

class ProcessActionRequest(BaseModel):
    campaign_id: str
    profile_id: str
    action_type: str
    action_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    session: Optional[Dict[str, Any]] = None

class GenerateWorldBackstoryRequest(BaseModel):
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

@app.get("/")
async def root():
    return {
        "service": "AI Game Master Agent",
        "version": "1.0.0",
        "description": "LangGraph-powered narrative generation"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/start-campaign")
async def start_campaign(request: StartCampaignRequest):
    """Start a new campaign"""

    # Initialize state
    initial_state: AgentState = {
        "profile_id": request.profile_id,
        "character_name": request.character_name,
        "universe_id": request.universe_id,
        "world_id": request.world_id,
        "campaign_name": request.campaign_name,
        "action_type": None,
        "action_text": None,
        "player_profile": None,
        "universe_guidelines": None,
        "world_lore": None,
        "narrative_text": None,
        "choices": None,
        "image_prompt": None,
        "cognitive_skill_updates": None,
        "tokens_used": 0,
        "cost_usd": 0.0,
        "error": None
    }

    # Run the agent
    result = await agent_graph.ainvoke(initial_state)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "campaign_id": request.profile_id,  # Would generate proper campaign ID in production
        "profile_id": request.profile_id,
        "narrative_text": result["narrative_text"],
        "choices": result["choices"],
        "image_prompt": result["image_prompt"],
        "cognitive_skill_updates": result["cognitive_skill_updates"],
        "tokens_used": result["tokens_used"],
        "cost_usd": result["cost_usd"]
    }

@app.post("/process-action")
async def process_action(request: ProcessActionRequest):
    """Process a player action"""

    # Initialize state
    initial_state: AgentState = {
        "profile_id": request.profile_id,
        "character_name": "Player",  # Would fetch from database
        "universe_id": "default",  # Would fetch from campaign
        "world_id": "default",  # Would fetch from campaign
        "campaign_name": None,
        "action_type": request.action_type,
        "action_text": request.action_text,
        "player_profile": None,
        "universe_guidelines": None,
        "world_lore": None,
        "narrative_text": None,
        "choices": None,
        "image_prompt": None,
        "cognitive_skill_updates": None,
        "tokens_used": 0,
        "cost_usd": 0.0,
        "error": None
    }

    # Run the agent
    result = await agent_graph.ainvoke(initial_state)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "campaign_id": request.campaign_id,
        "profile_id": request.profile_id,
        "narrative_text": result["narrative_text"],
        "choices": result["choices"],
        "image_prompt": result["image_prompt"],
        "cognitive_skill_updates": result["cognitive_skill_updates"],
        "tokens_used": result["tokens_used"],
        "cost_usd": result["cost_usd"]
    }

@app.post("/generate-world-backstory")
async def generate_world_backstory(request: GenerateWorldBackstoryRequest):
    """Generate creative backstory for a world using Claude with full MCP context"""

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # Build context from ALL world properties
    themes_str = ", ".join(request.themes) if request.themes else "adventure"
    styles_str = ", ".join(request.visual_style) if request.visual_style else "classic fantasy"

    # Build comprehensive prompt using all new properties
    prompt = f"""You are a creative world-building assistant for a tabletop RPG system. Generate an engaging, comprehensive backstory for a world based on ALL the following properties:

BASIC INFORMATION:
- World Name: {request.world_name}
- Genre: {request.genre}
- Setting: {request.setting}
- Themes: {themes_str}
- Visual Style: {styles_str}
- Power System: {request.power_system if hasattr(request, 'power_system') else 'N/A'}

PHYSICAL PROPERTIES:
- Star System: {request.physical_properties.get('star_system', 'N/A') if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}
- Planetary Classification: {request.physical_properties.get('planetary_classification', 'N/A') if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}
- World Features: {', '.join(request.physical_properties.get('world_features', [])) if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}
- Resources: {', '.join(request.physical_properties.get('resources', [])) if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}
- Terrain: {', '.join(request.physical_properties.get('terrain', [])) if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}
- Climate: {request.physical_properties.get('climate', 'N/A') if hasattr(request, 'physical_properties') and request.physical_properties else 'N/A'}

BIOLOGICAL PROPERTIES:
- Habitability: {request.biological_properties.get('habitability', 'N/A') if hasattr(request, 'biological_properties') and request.biological_properties else 'N/A'}
- Flora: {', '.join(request.biological_properties.get('flora', [])) if hasattr(request, 'biological_properties') and request.biological_properties else 'N/A'}
- Fauna: {', '.join(request.biological_properties.get('fauna', [])) if hasattr(request, 'biological_properties') and request.biological_properties else 'N/A'}
- Native Species: {', '.join(request.biological_properties.get('native_species', [])) if hasattr(request, 'biological_properties') and request.biological_properties else 'N/A'}

TECHNOLOGICAL PROPERTIES:
- Technology Level: {request.technological_properties.get('technology_level', 'N/A') if hasattr(request, 'technological_properties') and request.technological_properties else 'N/A'}
- Technology History: {request.technological_properties.get('technology_history', 'N/A') if hasattr(request, 'technological_properties') and request.technological_properties else 'N/A'}
- Automation: {request.technological_properties.get('automation', 'N/A') if hasattr(request, 'technological_properties') and request.technological_properties else 'N/A'}
- Weapons & Tools: {', '.join(request.technological_properties.get('weapons_tools', [])) if hasattr(request, 'technological_properties') and request.technological_properties else 'N/A'}

SOCIETAL & CULTURAL PROPERTIES:
- Government: {request.societal_properties.get('government', 'N/A') if hasattr(request, 'societal_properties') and request.societal_properties else 'N/A'}
- Culture & Traditions: {', '.join(request.societal_properties.get('culture_traditions', [])) if hasattr(request, 'societal_properties') and request.societal_properties else 'N/A'}
- Inhabitants: {', '.join(request.societal_properties.get('inhabitants', [])) if hasattr(request, 'societal_properties') and request.societal_properties else 'N/A'}
- Social Issues: {', '.join(request.societal_properties.get('social_issues', [])) if hasattr(request, 'societal_properties') and request.societal_properties else 'N/A'}

HISTORICAL PROPERTIES:
- Major Events: {', '.join(request.historical_properties.get('major_events', [])) if hasattr(request, 'historical_properties') and request.historical_properties else 'N/A'}
- Significant Sites: {', '.join(request.historical_properties.get('significant_sites', [])) if hasattr(request, 'historical_properties') and request.historical_properties else 'N/A'}
- Timeline: {request.historical_properties.get('timeline', 'N/A') if hasattr(request, 'historical_properties') and request.historical_properties else 'N/A'}
- Myths & Origin Stories: {request.historical_properties.get('myths_origin', 'N/A') if hasattr(request, 'historical_properties') and request.historical_properties else 'N/A'}

INSTRUCTIONS:
1. Write a creative and immersive backstory that weaves together ALL these world properties
2. Create a rich narrative of 3-4 compelling paragraphs (250-400 words)
3. Incorporate physical, biological, technological, societal, and historical elements naturally
4. Address the native species, technological development, cultural traditions, and major historical events
5. Reference the world's resources, terrain, climate, and how they shaped civilization
6. Include hints about the power system and how it influenced society
7. Make the world feel alive, complex, and ready for adventure
8. Use vivid, evocative language that matches the genre and visual style
9. Return ONLY the backstory text, no preamble or explanation

Write the comprehensive backstory now:"""

    try:
        # Use Claude via LangChain
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,  # More creative for backstory
            max_tokens=600
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)

        # Calculate cost
        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        # Cost calculation (per million tokens)
        cost_usd = (input_tokens * 3.00 / 1_000_000) + (output_tokens * 15.00 / 1_000_000)

        return {
            "backstory": response.content,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating backstory: {str(e)}")

@app.post("/generate-region-backstory")
async def generate_region_backstory(request: GenerateRegionBackstoryRequest):
    """Generate creative backstory for a region using Claude"""

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    terrain_str = ", ".join(request.terrain) if request.terrain else "varied"

    prompt = f"""You are a creative world-building assistant for a tabletop RPG system. Generate an engaging backstory for a region based on the following properties:

REGION NAME: {request.region_name}
REGION TYPE: {request.region_type}
CLIMATE: {request.climate}
TERRAIN: {terrain_str}
DESCRIPTION: {request.description}"""

    if request.world_name:
        prompt += f"\nWORLD: {request.world_name}"
    if request.world_genre:
        prompt += f"\nGENRE: {request.world_genre}"

    prompt += """

INSTRUCTIONS:
1. Write a creative and immersive backstory that brings this region to life
2. Keep it to 2-3 compelling paragraphs (150-250 words)
3. Incorporate the climate, terrain, and region type naturally
4. Include hints of history, conflicts, or mysteries
5. Make it feel alive and inspire adventure
6. Use vivid, evocative language that matches the genre
7. Return ONLY the backstory text, no preamble or explanation

Write the backstory now:"""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,
            max_tokens=600
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)

        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (input_tokens * 3.00 / 1_000_000) + (output_tokens * 15.00 / 1_000_000)

        return {
            "backstory": response.content,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating backstory: {str(e)}")

@app.post("/generate-location-backstory")
async def generate_location_backstory(request: GenerateLocationBackstoryRequest):
    """Generate creative backstory for a location using Claude"""

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    features_str = ", ".join(request.features) if request.features else "unique characteristics"

    prompt = f"""You are a creative world-building assistant for a tabletop RPG system. Generate an engaging backstory for a location based on the following properties:

LOCATION NAME: {request.location_name}
LOCATION TYPE: {request.location_type}
DESCRIPTION: {request.description}
FEATURES: {features_str}"""

    if request.region_name:
        prompt += f"\nREGION: {request.region_name}"
    if request.world_name:
        prompt += f"\nWORLD: {request.world_name}"

    prompt += """

INSTRUCTIONS:
1. Write a creative and immersive backstory that brings this location to life
2. Keep it to 2-3 compelling paragraphs (150-250 words)
3. Incorporate the location type and features naturally
4. Include specific details that make it memorable
5. Hint at potential adventures or encounters
6. Make it feel lived-in and authentic
7. Return ONLY the backstory text, no preamble or explanation

Write the backstory now:"""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,
            max_tokens=600
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)

        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (input_tokens * 3.00 / 1_000_000) + (output_tokens * 15.00 / 1_000_000)

        return {
            "backstory": response.content,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating backstory: {str(e)}")

@app.post("/generate-regions")
async def generate_regions(request: GenerateRegionsRequest):
    """Generate multiple regions with locations and backstories"""

    world_context = request.world_context
    num_regions = request.num_regions
    num_locations_per_region = request.num_locations_per_region

    # Build comprehensive prompt with ALL world properties
    physical = world_context.get('physical_properties', {})
    biological = world_context.get('biological_properties', {})
    technological = world_context.get('technological_properties', {})
    societal = world_context.get('societal_properties', {})
    historical = world_context.get('historical_properties', {})

    prompt = f"""You are a creative world-builder for an RPG game. Generate {num_regions} unique and diverse regions for this world that align with ALL of its established properties.

WORLD CONTEXT:
Basic Information:
- Name: {world_context.get('world_name')}
- Genre: {world_context.get('genre')}
- Themes: {', '.join(world_context.get('themes', []))}
- Visual Style: {', '.join(world_context.get('visual_style', []))}
- Power System: {world_context.get('power_system')}

Physical Properties:
- Star System: {physical.get('star_system', 'N/A')}
- Planetary Classification: {physical.get('planetary_classification', 'N/A')}
- World Features: {', '.join(physical.get('world_features', []))}
- Resources: {', '.join(physical.get('resources', []))}
- Terrain Types: {', '.join(physical.get('terrain', []))}
- Climate: {physical.get('climate', 'N/A')}

Biological Properties:
- Habitability: {biological.get('habitability', 'N/A')}
- Flora: {', '.join(biological.get('flora', []))}
- Fauna: {', '.join(biological.get('fauna', []))}
- Native Species: {', '.join(biological.get('native_species', []))}

Technological Properties:
- Technology Level: {technological.get('technology_level', 'N/A')}
- Automation: {technological.get('automation', 'N/A')}
- Weapons & Tools: {', '.join(technological.get('weapons_tools', []))}

Societal & Cultural Properties:
- Government: {societal.get('government', 'N/A')}
- Culture & Traditions: {', '.join(societal.get('culture_traditions', []))}
- Inhabitants: {', '.join(societal.get('inhabitants', []))}
- Social Issues: {', '.join(societal.get('social_issues', []))}

Historical Context:
- Major Events: {', '.join(historical.get('major_events', []))}
- Significant Sites: {', '.join(historical.get('significant_sites', []))}
- Myths & Origin: {historical.get('myths_origin', 'N/A')}

World Backstory:
{world_context.get('backstory', 'No backstory provided')}

GENERATION REQUIREMENTS:
For each region, generate:
1. A unique region_name (creative, evocative, fits the world's genre and themes)
2. A region_type from: Mountain, Forest, Desert, Coastal, Urban, Rural, Wasteland, Tundra, Swamp, Underground, Island, Volcanic, Mystical
3. A climate that aligns with the world's climate and planetary classification
4. An array of terrain features consistent with the world's terrain types and world features
5. A 1-2 sentence description highlighting how the region reflects the world's properties
6. A compelling 2-3 paragraph backstory (150-250 words) that:
   - Incorporates the world's backstory and major historical events
   - References the native species, flora, or fauna found in the region
   - Reflects the technological level and societal structure
   - Connects to the power system and cultural traditions
   - Addresses any relevant social issues or significant sites
7. {num_locations_per_region} locations within the region, each with:
   - location_name (creative, specific to the region and world's inhabitants)
   - location_type from: City, Town, Village, Fortress, Castle, Temple, Dungeon, Cave, Ruins, Market, Port, Inn/Tavern, Guild Hall, Academy, Library, Landmark, Wilderness
   - description (1-2 sentences) that incorporates world resources, technology, or culture
   - features array from: Trading Post, Blacksmith, Magic Shop, Quest Board, Safe Haven, Dangerous, Hidden, Magical, Ancient, Cursed, Sacred, Abandoned, Thriving, Under Siege, Mysterious, Fortified, Underground, Floating
   - backstory (2-3 paragraphs, 150-250 words) that:
     * Ties into the region, world backstory, and historical events
     * Features the native species or inhabitants
     * Reflects the technological level and weapons/tools
     * Incorporates the power system if relevant
     * References cultural traditions or government structure

CRITICAL: Make each region and location feel distinct, memorable, and deeply interconnected with ALL the world's established properties, backstory, and lore. The regions should feel like natural extensions of the world, not generic fantasy locations.

Return the result as a JSON array of regions. Each region should have this structure:
{{
  "region_name": "string",
  "region_type": "string",
  "climate": "string",
  "terrain": ["string"],
  "description": "string",
  "backstory": "string",
  "locations": [
    {{
      "location_name": "string",
      "location_type": "string",
      "description": "string",
      "features": ["string"],
      "backstory": "string"
    }}
  ]
}}

Return ONLY the JSON array, no preamble or explanation."""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,
            max_tokens=8000  # Large token limit for batch generation
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)

        # Parse JSON from response
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        regions_data = json.loads(content)

        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (input_tokens * 3.00 / 1_000_000) + (output_tokens * 15.00 / 1_000_000)

        return {
            "regions": regions_data,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating regions: {str(e)}")

@app.post("/generate-locations")
async def generate_locations(request: GenerateLocationsRequest):
    """Generate multiple locations for a region"""

    # Build the prompt
    prompt = f"""You are a creative world-builder for an RPG game. Generate {request.num_locations} unique and diverse locations for this region.

World Context:
- World Name: {request.world_name}
- Genre: {request.world_genre}
- World Backstory: {request.world_backstory}

Region Context:
- Region Name: {request.region_name}
- Region Type: {request.region_type}
- Climate: {request.climate}
- Terrain: {', '.join(request.terrain)}
- Description: {request.region_description}
- Backstory: {request.region_backstory}

For each location, generate:
1. A unique location_name (creative, evocative, fits the region and world)
2. A location_type from: City, Town, Village, Fortress, Castle, Temple, Dungeon, Cave, Ruins, Market, Port, Inn/Tavern, Guild Hall, Academy, Library, Landmark, Wilderness
3. A 1-2 sentence description
4. An array of features from: Trading Post, Blacksmith, Magic Shop, Quest Board, Safe Haven, Dangerous, Hidden, Magical, Ancient, Cursed, Sacred, Abandoned, Thriving, Under Siege, Mysterious, Fortified, Underground, Floating
5. A compelling 2-3 paragraph backstory (150-250 words) that:
   - Ties into the region's characteristics and backstory
   - Connects to the world's lore and genre
   - Makes the location feel distinct and memorable
   - Hints at potential adventures or encounters

Make each location feel unique and interconnected with both the region and world.

Return the result as a JSON array of locations. Each location should have this structure:
{{
  "location_name": "string",
  "location_type": "string",
  "description": "string",
  "features": ["string"],
  "backstory": "string"
}}

Return ONLY the JSON array, no preamble or explanation."""

    try:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,
            max_tokens=6000  # Large token limit for multiple locations
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm.ainvoke(messages)

        # Parse JSON from response
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        locations_data = json.loads(content)

        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (input_tokens * 3.00 / 1_000_000) + (output_tokens * 15.00 / 1_000_000)

        return {
            "locations": locations_data,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating locations: {str(e)}")

@app.post("/start-campaign-stream")
async def start_campaign_stream(request: StartCampaignRequest):
    """Start a campaign with streaming narrative generation"""

    async def generate_stream():
        # Build context
        system_prompt = f"You are an AI Game Master for SkillForge. Generate an engaging opening for a campaign."

        user_prompt = f"""Begin a new adventure for {request.character_name} in world {request.world_id}.
Campaign: {request.campaign_name}

Generate an immersive opening scene."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Stream response
        async for chunk in llm_streaming.astream(messages):
            if hasattr(chunk, 'content'):
                yield f"data: {json.dumps({'text': chunk.content})}\n\n"

        # Signal completion
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.get("/analytics/cognitive-progression/{profile_id}")
async def get_cognitive_progression(profile_id: str):
    """Get cognitive skill progression data"""
    progression = await analytics_tracker.get_cognitive_progression(profile_id)
    return progression

@app.get("/analytics/engagement/{profile_id}")
async def get_engagement_metrics(profile_id: str, days: int = 30):
    """Get engagement metrics"""
    metrics = await analytics_tracker.get_engagement_metrics(profile_id, days)
    return metrics

@app.get("/analytics/learning-outcomes/{profile_id}")
async def get_learning_outcomes(profile_id: str, days: int = 30):
    """Get learning outcome summary"""
    outcomes = await analytics_tracker.get_learning_outcome_summary(profile_id, days)
    return outcomes

@app.post("/memory/store-event")
async def store_campaign_event(
    campaign_id: str,
    profile_id: str,
    event_type: str,
    event_description: str
):
    """Store a campaign event in long-term memory"""
    await memory_manager.store_campaign_event(
        campaign_id=campaign_id,
        profile_id=profile_id,
        event_type=event_type,
        event_description=event_description
    )
    return {"status": "stored"}

@app.get("/memory/retrieve/{campaign_id}")
async def retrieve_campaign_memories(
    campaign_id: str,
    query: str,
    n_results: int = 5
):
    """Retrieve relevant campaign memories"""
    memories = await memory_manager.retrieve_relevant_memories(
        campaign_id=campaign_id,
        query=query,
        n_results=n_results
    )
    return {"memories": memories}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
