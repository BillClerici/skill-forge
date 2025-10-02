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

# ============================================
# Configuration
# ============================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MCP_PLAYER_DATA_URL = os.getenv("MCP_PLAYER_DATA_URL", "http://mcp-player-data:8001")
MCP_WORLD_UNIVERSE_URL = os.getenv("MCP_WORLD_UNIVERSE_URL", "http://mcp-world-universe:8002")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

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

# Initialize Claude
llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    anthropic_api_key=ANTHROPIC_API_KEY if ANTHROPIC_API_KEY else None,
    temperature=0.7,
    max_tokens=4096
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
    setting: str
    themes: List[str]
    visual_style: List[str]
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
    """Generate creative backstory for a world using Claude"""

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # Build context from world properties
    themes_str = ", ".join(request.themes) if request.themes else "adventure"
    styles_str = ", ".join(request.visual_style) if request.visual_style else "classic fantasy"

    # Build prompt for Claude
    prompt = f"""You are a creative world-building assistant for a tabletop RPG system. Generate an engaging backstory for a world based on the following properties:

WORLD NAME: {request.world_name}
GENRE: {request.genre}
SETTING: {request.setting}
THEMES: {themes_str}
VISUAL STYLE: {styles_str}"""

    if request.history:
        prompt += f"\nEXISTING HISTORY: {request.history}"
    if request.geography:
        prompt += f"\nEXISTING GEOGRAPHY: {request.geography}"
    if request.culture:
        prompt += f"\nEXISTING CULTURE: {request.culture}"

    prompt += """

INSTRUCTIONS:
1. Write a creative and immersive backstory that brings this world to life
2. Keep it to 2-3 compelling paragraphs (150-250 words)
3. Incorporate the genre, themes, and visual style naturally
4. Make it feel alive and inspire adventure
5. If existing lore exists, build upon it and enhance it
6. Use vivid, evocative language that matches the genre
7. Return ONLY the backstory text, no preamble or explanation

Write the backstory now:"""

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
