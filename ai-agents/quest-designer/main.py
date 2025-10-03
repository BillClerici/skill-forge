"""
AI Quest Designer Agent
Generates quests, story arcs, and mission objectives using LangGraph
Collaborates with Game Master for integrated storytelling
"""
import os
from typing import Optional, Dict, Any, List, TypedDict
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import json

# LangChain imports
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langchain.schema import HumanMessage, SystemMessage

# ============================================
# Configuration
# ============================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MCP_QUEST_MISSION_URL = os.getenv("MCP_QUEST_MISSION_URL", "http://mcp-quest-mission:8003")
MCP_WORLD_UNIVERSE_URL = os.getenv("MCP_WORLD_UNIVERSE_URL", "http://mcp-world-universe:8002")
MCP_NPC_PERSONALITY_URL = os.getenv("MCP_NPC_PERSONALITY_URL", "http://mcp-npc-personality:8004")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# Claude pricing
CLAUDE_PRICING = {
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00}
}

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="AI Quest Designer Agent",
    description="LangGraph-powered quest and story arc generation",
    version="1.0.0"
)

# ============================================
# State Definition
# ============================================

class QuestDesignerState(TypedDict):
    # Input
    world_id: str
    quest_type: str  # main, side, daily
    difficulty_level: int
    educational_focus: List[str]

    # Context from MCPs
    world_lore: Optional[Dict[str, Any]]
    existing_quests: Optional[List[Dict[str, Any]]]
    available_npcs: Optional[List[Dict[str, Any]]]

    # Generated content
    quest_definition: Optional[Dict[str, Any]]
    story_arc: Optional[Dict[str, Any]]

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
        self.quest_url = MCP_QUEST_MISSION_URL
        self.world_url = MCP_WORLD_UNIVERSE_URL
        self.npc_url = MCP_NPC_PERSONALITY_URL
        self.headers = {"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}

    async def get_world_lore(self, world_id: str):
        """Get world lore from MCP"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.world_url}/mcp/world-lore/{world_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_world_quests(self, world_id: str):
        """Get existing quests for a world"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.quest_url}/mcp/world-quests/{world_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get("quests", [])
            return []

    async def get_location_npcs(self, world_id: str):
        """Get NPCs in a world"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.npc_url}/mcp/location-npcs",
                params={"world_id": world_id},
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get("npcs", [])
            return []

mcp_client = MCPClient()

# ============================================
# LangGraph Agent Implementation
# ============================================

# Initialize Claude - Using Haiku for quest generation (cheaper)
llm = ChatAnthropic(
    model="claude-3-5-haiku-20241022",
    anthropic_api_key=ANTHROPIC_API_KEY if ANTHROPIC_API_KEY else None,
    temperature=0.8,
    max_tokens=4096
)

async def gather_context(state: QuestDesignerState) -> QuestDesignerState:
    """Step 1: Gather context from MCP servers"""
    try:
        # Get world lore
        world_lore = await mcp_client.get_world_lore(state["world_id"])

        # Get existing quests
        existing_quests = await mcp_client.get_world_quests(state["world_id"])

        # Get available NPCs
        available_npcs = await mcp_client.get_location_npcs(state["world_id"])

        state["world_lore"] = world_lore
        state["existing_quests"] = existing_quests
        state["available_npcs"] = available_npcs

    except Exception as e:
        state["error"] = f"Error gathering context: {str(e)}"

    return state

async def design_quest(state: QuestDesignerState) -> QuestDesignerState:
    """Step 2: Design quest using Claude"""
    try:
        if state.get("error"):
            return state

        # Build system prompt
        system_prompt = build_quest_design_prompt(state)

        # Build user prompt
        user_prompt = f"""Design a {state['quest_type']} quest for this world.

Quest Requirements:
- Difficulty Level: {state['difficulty_level']}/10
- Educational Focus: {', '.join(state.get('educational_focus', ['general']))}

Please create a quest that:
1. Fits naturally into the world's lore and existing quests
2. Involves appropriate NPCs as quest givers or targets
3. Has clear, engaging objectives that align with the educational focus
4. Includes meaningful rewards
5. Challenges the player at the specified difficulty level

Return your response as JSON with this structure:
{{
  "quest_name": "string",
  "description": "string",
  "quest_type": "{state['quest_type']}",
  "difficulty_level": {state['difficulty_level']},
  "objectives": [
    {{
      "objective_id": "obj_1",
      "description": "string",
      "objective_type": "collect|defeat|explore|interact",
      "target": "string",
      "quantity": 1,
      "bloom_level": "Remember|Understand|Apply|Analyze|Evaluate|Create",
      "cognitive_skills": ["empathy", "strategy", "creativity", "courage"]
    }}
  ],
  "npc_giver": "npc_id or name",
  "rewards": {{
    "xp": 100,
    "currency": 50,
    "items": []
  }},
  "estimated_duration": 30,
  "prerequisites": []
}}"""

        # Call Claude
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = llm.invoke(messages)

        # Parse response
        quest_definition = parse_quest_response(response.content)

        # Add IDs
        quest_definition["quest_id"] = f"quest_{uuid4().hex[:12]}"
        quest_definition["world_id"] = state["world_id"]
        quest_definition["status"] = "not_started"
        quest_definition["created_at"] = datetime.now().isoformat()

        state["quest_definition"] = quest_definition

        # Calculate cost
        tokens_used = response.response_metadata.get("usage", {})
        input_tokens = tokens_used.get("input_tokens", 0)
        output_tokens = tokens_used.get("output_tokens", 0)

        cost = (input_tokens / 1_000_000 * CLAUDE_PRICING["claude-haiku-3-5"]["input"]) + \
               (output_tokens / 1_000_000 * CLAUDE_PRICING["claude-haiku-3-5"]["output"])

        state["tokens_used"] = input_tokens + output_tokens
        state["cost_usd"] = cost

    except Exception as e:
        state["error"] = f"Error designing quest: {str(e)}"
        state["tokens_used"] = 0
        state["cost_usd"] = 0.0

    return state

def build_quest_design_prompt(state: QuestDesignerState) -> str:
    """Build system prompt for quest design"""
    world = state.get("world_lore", {})
    existing_quests = state.get("existing_quests", [])
    npcs = state.get("available_npcs", [])

    quest_names = [q.get("quest_name", "") for q in existing_quests[:5]]
    npc_names = [n.get("name", "") for n in npcs[:10]]

    return f"""You are an expert Quest Designer for an educational RPG called SkillForge.

WORLD CONTEXT:
- World: {world.get('world_name', 'Unknown')}
- Genre: {world.get('genre', 'fantasy')}
- Themes: {', '.join(world.get('themes', []))}
- Backstory: {world.get('backstory', '')[:500]}

EXISTING QUESTS:
{', '.join(quest_names) if quest_names else 'None yet'}

AVAILABLE NPCs:
{', '.join(npc_names) if npc_names else 'None yet'}

INSTRUCTIONS:
1. Create quests that feel organic to the world
2. Ensure objectives teach the specified educational focus
3. Use Bloom's Taxonomy levels appropriately for difficulty
4. Reference existing NPCs when possible
5. Make objectives clear and achievable
6. Ensure rewards are balanced for the difficulty level
7. Return ONLY valid JSON, no markdown or explanation

BLOOM'S TAXONOMY LEVELS:
- Remember: Recall facts and basic concepts
- Understand: Explain ideas or concepts
- Apply: Use information in new situations
- Analyze: Draw connections among ideas
- Evaluate: Justify a decision or course of action
- Create: Produce new or original work

Your entire response must be valid JSON."""

def parse_quest_response(response_text: str) -> Dict[str, Any]:
    """Parse Claude's response into quest definition"""
    try:
        # Remove markdown code blocks if present
        content = response_text.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        result = json.loads(content)
        return result

    except json.JSONDecodeError:
        # Fallback
        return {
            "quest_name": "Generated Quest",
            "description": "A new adventure awaits.",
            "quest_type": "side",
            "difficulty_level": 1,
            "objectives": [
                {
                    "objective_id": "obj_1",
                    "description": "Complete the quest",
                    "objective_type": "explore",
                    "target": "location",
                    "quantity": 1,
                    "bloom_level": "Remember",
                    "cognitive_skills": []
                }
            ],
            "rewards": {"xp": 100, "currency": 50, "items": []},
            "estimated_duration": 30,
            "prerequisites": []
        }

# Build LangGraph workflow
workflow = StateGraph(QuestDesignerState)

# Add nodes
workflow.add_node("gather_context", gather_context)
workflow.add_node("design_quest", design_quest)

# Add edges
workflow.set_entry_point("gather_context")
workflow.add_edge("gather_context", "design_quest")
workflow.add_edge("design_quest", END)

# Compile the graph
quest_designer_graph = workflow.compile()

# ============================================
# FastAPI Endpoints
# ============================================

class DesignQuestRequest(BaseModel):
    world_id: str
    quest_type: str = "side"
    difficulty_level: int = 1
    educational_focus: List[str] = ["general"]

class DesignStoryArcRequest(BaseModel):
    world_id: str
    arc_name: str
    num_quests: int = 3
    difficulty_progression: str = "linear"
    educational_focus: List[str] = []

@app.get("/")
async def root():
    return {
        "service": "AI Quest Designer Agent",
        "version": "1.0.0",
        "description": "LangGraph-powered quest and story arc generation"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/design-quest")
async def design_quest_endpoint(request: DesignQuestRequest):
    """Design a new quest"""

    # Initialize state
    initial_state: QuestDesignerState = {
        "world_id": request.world_id,
        "quest_type": request.quest_type,
        "difficulty_level": request.difficulty_level,
        "educational_focus": request.educational_focus,
        "world_lore": None,
        "existing_quests": None,
        "available_npcs": None,
        "quest_definition": None,
        "story_arc": None,
        "tokens_used": 0,
        "cost_usd": 0.0,
        "error": None
    }

    # Run the agent
    result = await quest_designer_graph.ainvoke(initial_state)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "quest": result["quest_definition"],
        "tokens_used": result["tokens_used"],
        "cost_usd": result["cost_usd"]
    }

@app.post("/design-story-arc")
async def design_story_arc(request: DesignStoryArcRequest):
    """Design a multi-quest story arc"""

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # Get world context
    world_lore = await mcp_client.get_world_lore(request.world_id)

    # Build prompt for story arc
    prompt = f"""You are designing a story arc for an educational RPG.

World: {world_lore.get('world_name', 'Unknown')}
Genre: {world_lore.get('genre', 'fantasy')}
Backstory: {world_lore.get('backstory', '')[:500]}

Story Arc Name: {request.arc_name}
Number of Quests: {request.num_quests}
Difficulty Progression: {request.difficulty_progression}
Educational Focus: {', '.join(request.educational_focus)}

Create a cohesive story arc with {request.num_quests} interconnected quests.
Each quest should build on the previous one and contribute to an overarching narrative.

Return as JSON:
{{
  "arc_id": "arc_xxx",
  "arc_name": "{request.arc_name}",
  "description": "Overall arc description",
  "theme": "main theme",
  "quest_chain": [
    {{
      "quest_name": "string",
      "description": "string",
      "difficulty_level": 1,
      "prerequisites": [],
      "objectives": [...],
      "educational_focus": [...]
    }}
  ]
}}

Return ONLY valid JSON."""

    try:
        llm_arc = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.8,
            max_tokens=6000
        )

        messages = [HumanMessage(content=prompt)]
        response = await llm_arc.ainvoke(messages)

        # Parse
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        arc_data = json.loads(content)

        # Add metadata
        arc_data["world_id"] = request.world_id
        arc_data["created_at"] = datetime.now().isoformat()

        # Calculate cost
        input_tokens = response.response_metadata.get("usage", {}).get("input_tokens", 0)
        output_tokens = response.response_metadata.get("usage", {}).get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = (input_tokens * 0.80 / 1_000_000) + (output_tokens * 4.00 / 1_000_000)

        return {
            "story_arc": arc_data,
            "tokens_used": total_tokens,
            "cost_usd": round(cost_usd, 6)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating story arc: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
