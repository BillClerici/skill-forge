# SkillForge AI Agents and MCP Servers

## Table of Contents
- [Overview](#overview)
- [Architecture Diagrams](#architecture-diagrams)
- [MCP Servers](#mcp-servers)
  - [Player Data MCP](#player-data-mcp)
  - [World/Universe MCP](#worlduniverse-mcp)
- [AI Agents](#ai-agents)
  - [Agent Orchestrator](#agent-orchestrator)
  - [Game Master Agent](#game-master-agent)
- [Integration Flows](#integration-flows)
- [Deployment](#deployment)

---

## Overview

SkillForge utilizes a **Model Context Protocol (MCP)** architecture to provide AI agents with structured, secure context about players and game worlds. This architecture separates concerns between:

- **MCP Servers**: Provide read-only, structured context to AI agents
- **AI Agents**: Generate narratives, make decisions, and create content using the context
- **Orchestrator**: Manages agent lifecycle, cost tracking, and resource allocation

This design ensures that sensitive player data remains secure while enabling powerful AI-driven gameplay experiences.

---

## Architecture Diagrams

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Django Web App                          │
│                    (World/Universe Management)                   │
└────────────────────┬───────────────────────┬────────────────────┘
                     │                       │
                     ▼                       ▼
           ┌─────────────────┐     ┌─────────────────┐
           │    MongoDB      │     │     Neo4j       │
           │  (World Lore)   │     │  (Relationships)│
           └─────────────────┘     └─────────────────┘
                     │                       │
                     └───────────┬───────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  MCP: World/Universe    │
                    │   (Port 8002)           │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Agent Orchestrator     │
                    │   (Port 9000)           │
                    │  - Cost Tracking        │
                    │  - Session Management   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Game Master Agent      │
                    │   (Port 8000)           │
                    │  - LangGraph            │
                    │  - Claude Sonnet 4      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  MCP: Player Data       │
                    │   (Port 8001)           │
                    └────────────┬────────────┘
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
           ┌─────────────────┐     ┌─────────────────┐
           │   PostgreSQL    │     │      Redis      │
           │ (Player Profiles)│     │   (Caching)     │
           └─────────────────┘     └─────────────────┘
```

### Agent Interaction Flow

```
┌──────────┐         ┌─────────────────┐         ┌──────────────┐
│  Client  │────1───>│  Orchestrator   │────2───>│ MCP: Player  │
│  (User)  │         │                 │         │     Data     │
└──────────┘         └─────────────────┘         └──────────────┘
      │                      │                           │
      │                      3                           │
      │              ┌───────▼────────┐                  │
      │              │  Game Master   │◄─────4───────────┘
      │              │     Agent      │
      │              └───────┬────────┘
      │                      │
      │                      5
      │              ┌───────▼────────┐
      │              │ MCP: World/    │
      │              │   Universe     │
      │              └───────┬────────┘
      │                      │
      │◄─────────6───────────┘
      │   (Narrative Response)
```

**Flow Steps:**
1. Client sends player action to Orchestrator
2. Orchestrator fetches player cognitive profile from Player Data MCP
3. Orchestrator invokes Game Master Agent with context
4. Game Master fetches additional player context
5. Game Master fetches world/universe guidelines and lore
6. Game Master generates narrative and returns to client

---

## MCP Servers

### Player Data MCP

#### Business Description

The Player Data MCP Server provides AI agents with secure, read-only access to player cognitive profiles, learning progress, and gameplay preferences. This enables the AI to adapt narratives to each player's educational level, interests, and developmental needs while maintaining strict data privacy.

**Key Features:**
- Cognitive skill tracking (Bloom's Taxonomy)
- Learning progress monitoring
- Parental control information
- Player preferences and play style
- Character profile access

#### Technical Description

**Technology Stack:**
- **Framework**: FastAPI (Python)
- **Primary Database**: PostgreSQL (player profiles, cognitive progress)
- **Secondary Storage**: MongoDB (extended profile data)
- **Caching**: Redis (performance optimization)
- **Authentication**: Bearer token-based MCP authentication

**Core Endpoints:**
```python
GET /mcp/player-cognitive-profile/{player_id}
# Returns: Bloom's taxonomy mastery, skill levels, play style

GET /mcp/player-context/{profile_id}
# Returns: Full player context including character info and preferences

GET /mcp/player-learning-goals/{profile_id}
# Returns: Current learning objectives and progress
```

**Data Models:**
- `Member`: Account member with parental controls
- `PlayerProfile`: Character profiles and gameplay data
- `MemberCognitiveProgress`: Bloom's taxonomy and skill tracking

#### Interactions

**Consumes:**
- PostgreSQL: Member and profile data
- MongoDB: Extended profile attributes
- Redis: Cached cognitive profiles

**Provides To:**
- Game Master Agent: Player cognitive context
- Agent Orchestrator: Player subscription and usage data

#### Deployment

```yaml
Container: skillforge-mcp-player-data
Port: 8001
Dependencies:
  - postgres (PostgreSQL)
  - mongodb (MongoDB)
  - redis (Redis)
Environment:
  - DATABASE_URL: PostgreSQL connection
  - MONGODB_URL: MongoDB connection
  - REDIS_URL: Redis connection
  - MCP_AUTH_TOKEN: Authentication token
```

**Health Checks:**
- Database connectivity validation on startup
- Redis connection pool monitoring

---

### World/Universe MCP

#### Business Description

The World/Universe MCP Server provides AI agents with rich, structured world-building information including universe guidelines, world lore, regional details, and location descriptions. This ensures that AI-generated narratives remain consistent with the established game world and genre conventions.

**Key Features:**
- Universe guidelines and content ratings
- World properties (physical, biological, technological, societal, historical)
- Region and location definitions
- Graph-based relationship tracking
- Backstory and lore management

#### Technical Description

**Technology Stack:**
- **Framework**: FastAPI (Python)
- **Primary Database**: MongoDB (world definitions, lore)
- **Graph Database**: Neo4j (world/region/location relationships)
- **Caching**: Redis (world context caching)
- **Authentication**: Bearer token-based MCP authentication

**Core Endpoints:**
```python
GET /mcp/universe-guidelines/{universe_id}
# Returns: Universe type, purpose, content rating, restrictions

GET /mcp/world-lore/{world_id}
# Returns: Complete world properties, backstory, and lore

GET /mcp/location-context/{world_id}/{region_id}/{location_id}
# Returns: Specific location details and context

GET /mcp/world-relationships/{world_id}
# Returns: Neo4j graph of world -> regions -> locations
```

**Data Models:**
- `Universe`: Top-level game universe with guidelines
- `World`: Planetary/world definitions with 5 property categories
  - Physical Properties: star system, terrain, climate, resources
  - Biological Properties: habitability, flora, fauna, native species
  - Technological Properties: tech level, automation, weapons/tools
  - Societal Properties: government, culture, demographics, social issues
  - Historical Properties: major events, significant sites, timeline, myths
- `Region`: Geographic regions within worlds
- `Location`: Specific locations within regions

#### Interactions

**Consumes:**
- MongoDB: World/universe definitions
- Neo4j: Relationship graphs
- Redis: Cached world contexts

**Provides To:**
- Game Master Agent: World context and lore
- Agent Orchestrator: World metadata
- Django Web App: CRUD operations for world management

#### Deployment

```yaml
Container: skillforge-mcp-world-universe
Port: 8002
Dependencies:
  - mongodb (MongoDB)
  - neo4j (Neo4j Graph DB)
  - redis (Redis)
Environment:
  - MONGODB_URL: MongoDB connection
  - NEO4J_URL: Bolt protocol connection
  - NEO4J_USER: Neo4j username
  - NEO4J_PASSWORD: Neo4j password
  - REDIS_URL: Redis connection
  - MCP_AUTH_TOKEN: Authentication token
```

**Health Checks:**
- MongoDB connectivity
- Neo4j driver initialization
- Redis connection pool

---

## AI Agents

### Agent Orchestrator

#### Business Description

The Agent Orchestrator acts as the central coordination point for all AI agent interactions. It manages agent lifecycle, tracks AI costs per account, enforces subscription-tier budgets, and handles session state management. This ensures that families stay within budget while providing transparency into AI usage costs.

**Key Features:**
- Cost tracking and budget enforcement
- Session management (campaigns)
- Subscription tier management
- Agent invocation coordination
- Usage analytics

#### Technical Description

**Technology Stack:**
- **Framework**: FastAPI (Python)
- **Session Store**: Redis (active campaigns, cost tracking)
- **Persistent Storage**: MongoDB (campaign history, usage logs)
- **HTTP Client**: httpx (async MCP and agent calls)

**Core Endpoints:**
```python
POST /api/start-campaign
# Creates new campaign session, validates budget

POST /api/player-action
# Processes player action, invokes Game Master, tracks costs

GET /api/cost-tracking/{account_id}
# Returns current usage against daily/monthly budgets

POST /api/generate-backstory
# Generates world/character backstories via Game Master

POST /api/generate-regions
# Batch generates regions and locations for worlds
```

**Budget Management:**
```python
DAILY_BUDGET_LIMITS = {
    "free": $0.50,
    "individual": $2.00,
    "family": $5.00,
    "educational": $10.00,
    "organizational": $20.00
}
```

#### Interactions

**Consumes:**
- Redis: Session state, cost tracking
- MongoDB: Campaign history
- Player Data MCP: Player cognitive profiles
- World/Universe MCP: World context

**Invokes:**
- Game Master Agent: Narrative generation, backstory creation

**Provides To:**
- Django Web App: Campaign management endpoints
- Client Applications: Gameplay API

#### Deployment

```yaml
Container: skillforge-agent-orchestrator
Port: 9000
Dependencies:
  - redis (Session storage)
  - mongodb (Campaign persistence)
  - mcp-player-data (Player context)
  - mcp-world-universe (World context)
Environment:
  - REDIS_URL: Redis connection
  - MONGODB_URL: MongoDB connection
  - MCP_PLAYER_DATA_URL: http://mcp-player-data:8001
  - MCP_WORLD_UNIVERSE_URL: http://mcp-world-universe:8002
  - MCP_AUTH_TOKEN: MCP authentication
  - GAME_MASTER_URL: http://agent-game-master:8000
```

---

### Game Master Agent

#### Business Description

The Game Master Agent is the core narrative AI that generates immersive, educational RPG experiences. Powered by Claude Sonnet 4 and LangGraph, it creates adaptive storytelling that responds to player actions while incorporating educational objectives and maintaining world consistency.

**Key Features:**
- Dynamic narrative generation
- Educational objective integration
- Bloom's taxonomy alignment
- Character development and progression
- Image prompt generation for visual assets
- Cost calculation and token tracking

#### Technical Description

**Technology Stack:**
- **AI Model**: Claude Sonnet 4 (via Anthropic API)
- **Framework**: LangGraph (LangChain)
- **API**: FastAPI (Python)
- **Context Sources**: Player Data MCP, World/Universe MCP

**LangGraph Workflow:**
```
┌──────────────┐
│ Gather       │
│ Context      │──┐
└──────────────┘  │
                  │
┌──────────────┐  │
│ Fetch Player │◄─┘
│ Profile      │──┐
└──────────────┘  │
                  │
┌──────────────┐  │
│ Fetch World  │◄─┘
│ Lore         │──┐
└──────────────┘  │
                  │
┌──────────────┐  │
│ Generate     │◄─┘
│ Narrative    │──┐
└──────────────┘  │
                  │
┌──────────────┐  │
│ Format       │◄─┘
│ Response     │
└──────────────┘
```

**Core Endpoints:**
```python
POST /generate-narrative
# Generates narrative response to player action
# Returns: narrative text, choices, cognitive updates, cost

POST /generate-backstory
# Creates world/character backstories
# Returns: backstory text, tokens used, cost

POST /generate-npc
# Creates NPC character with personality
# Returns: NPC definition, dialogue examples

POST /generate-regions
# Batch generates world regions and locations
# Returns: region/location definitions with backstories
```

**Cost Calculation:**
```python
CLAUDE_PRICING = {
    "claude-sonnet-4": {
        "input": $3.00 per million tokens,
        "output": $15.00 per million tokens
    }
}

cost_usd = (
    (input_tokens / 1_000_000) * CLAUDE_PRICING["input"] +
    (output_tokens / 1_000_000) * CLAUDE_PRICING["output"]
)
```

#### Interactions

**Consumes:**
- Player Data MCP: Cognitive profiles, learning goals
- World/Universe MCP: World lore, universe guidelines

**Provides To:**
- Agent Orchestrator: Narrative responses with cost data
- Django Web App: Backstory generation, content creation

**External APIs:**
- Anthropic API: Claude Sonnet 4 LLM

#### Deployment

```yaml
Container: skillforge-agent-game-master
Port: 8000
Dependencies:
  - mcp-player-data (Player context)
  - mcp-world-universe (World context)
Environment:
  - ANTHROPIC_API_KEY: Claude API key
  - MCP_PLAYER_DATA_URL: http://mcp-player-data:8001
  - MCP_WORLD_UNIVERSE_URL: http://mcp-world-universe:8002
  - MCP_AUTH_TOKEN: MCP authentication
```

**Resource Requirements:**
- CPU: 1-2 cores
- Memory: 2GB minimum
- Network: Low latency to Anthropic API

---

## Integration Flows

### Campaign Gameplay Flow

```sequence
Player->Orchestrator: Send Action
Orchestrator->PlayerMCP: Get Cognitive Profile
PlayerMCP->Orchestrator: Return Profile
Orchestrator->Orchestrator: Check Budget
Orchestrator->GameMaster: Generate Narrative
GameMaster->PlayerMCP: Get Player Context
GameMaster->WorldMCP: Get World Lore
WorldMCP->GameMaster: Return Lore
GameMaster->Claude: Generate Response
Claude->GameMaster: Narrative + Tokens
GameMaster->Orchestrator: Response + Cost
Orchestrator->Orchestrator: Update Cost Tracking
Orchestrator->Player: Narrative Response
```

### World Backstory Generation Flow

```sequence
Django->Orchestrator: Generate Backstory
Orchestrator->WorldMCP: Get World Properties
WorldMCP->Orchestrator: Return Properties
Orchestrator->GameMaster: Generate Backstory
GameMaster->Claude: Create Backstory
Claude->GameMaster: Backstory Text
GameMaster->Orchestrator: Backstory + Cost
Orchestrator->Django: Return Backstory
Django->MongoDB: Save Backstory
```

### Batch Region Generation Flow

```sequence
Django->Orchestrator: Generate Regions (n=3)
Orchestrator->WorldMCP: Get World Context
WorldMCP->Orchestrator: World Properties + Backstory
Orchestrator->GameMaster: Generate 3 Regions
GameMaster->Claude: Batch Generation
Claude->GameMaster: 3 Regions + Locations
GameMaster->Orchestrator: Regions + Total Cost
Orchestrator->Django: Region Definitions
Django->MongoDB: Save Regions
Django->Neo4j: Create Graph Relationships
```

---

## Deployment

### Docker Compose Services

All MCP servers and AI agents are deployed as Docker containers managed by Docker Compose:

```bash
# Start all services
docker-compose up -d

# Start specific MCP servers
docker-compose up -d mcp-player-data mcp-world-universe

# Start AI agents
docker-compose up -d agent-orchestrator agent-game-master

# View logs
docker-compose logs -f agent-game-master
```

### Network Architecture

All services communicate over the `skillforge-network` bridge network:

- **MCP Servers**: Internal network only (8001, 8002)
- **Orchestrator**: Internal network only (9000)
- **Game Master**: Internal network only (8000)
- **Django Web**: External port 8000
- **API Gateway**: External port 4000

### Scaling Considerations

**Horizontal Scaling:**
- MCP servers can scale horizontally (stateless with Redis caching)
- Game Master agents can scale with load balancer
- Orchestrator should remain single instance (cost tracking coordination)

**Vertical Scaling:**
- Game Master: Increase memory for larger context windows
- MCP servers: Increase CPU for database query performance

### Monitoring

**Key Metrics:**
- Agent response time (p50, p95, p99)
- Token usage per request
- Cost per campaign session
- MCP cache hit rate
- Budget exhaustion events

**Health Endpoints:**
```
GET /health (all services)
GET /metrics (Prometheus format)
```

---

## Security

### Authentication

All MCP servers require bearer token authentication:
```bash
Authorization: Bearer ${MCP_AUTH_TOKEN}
```

### Data Access Patterns

- **MCP Servers**: Read-only access to data stores
- **AI Agents**: No direct database access (only via MCP)
- **Orchestrator**: Manages write access to session state

### Privacy Controls

- Player data never leaves MCP server boundaries
- AI agents receive only necessary context
- Parental controls enforced at MCP level
- Content rating filtering per universe

---

## LangGraph

### What is LangGraph?

LangGraph is a state machine framework built on top of LangChain for creating complex, multi-step AI agent workflows. It provides a structured way to define agent behavior as a directed graph where:

- **Nodes** represent discrete processing steps (functions)
- **Edges** define the flow between steps
- **State** is a typed dictionary that flows through the graph

LangGraph enables building reliable, maintainable AI agents by making the workflow explicit and traceable, rather than relying on implicit prompt chaining or unstructured decision-making.

**Key Benefits:**
- Explicit state management across agent steps
- Clear visualization of agent workflow
- Easy debugging and testing of individual nodes
- Conditional branching and complex decision flows
- Built-in error handling and retry logic

---

### LangGraph in SkillForge

In SkillForge, LangGraph powers the **Game Master Agent** by structuring the narrative generation process into a reliable, multi-step workflow. Instead of a single monolithic LLM call, the agent breaks down narrative generation into discrete, manageable steps.

**Primary Use Cases:**
1. **Campaign Gameplay**: Processing player actions and generating narrative responses
2. **Backstory Generation**: Creating world and character backstories with proper context
3. **NPC Creation**: Generating non-player characters with personalities
4. **Batch Region Generation**: Creating multiple regions and locations efficiently

**Why LangGraph for SkillForge?**
- Ensures all necessary context is gathered before generating narratives
- Separates concerns (context fetching vs. narrative generation)
- Makes the agent workflow transparent and debuggable
- Handles errors gracefully without corrupting state
- Enables easy extension with new processing steps

---

### LangGraph Structure in Game Master Agent

#### State Definition

The Game Master Agent uses a TypedDict to define the state that flows through the workflow:

```python
class AgentState(TypedDict):
    # Input Parameters
    profile_id: str                              # Player profile UUID
    character_name: str                          # Player's character name
    universe_id: str                             # Universe UUID
    world_id: str                                # World UUID
    campaign_name: Optional[str]                 # Campaign identifier
    action_type: Optional[str]                   # Type of action (move, talk, etc.)
    action_text: Optional[str]                   # Player's action description

    # Context Data (populated by gather_context node)
    player_profile: Optional[Dict[str, Any]]     # Cognitive profile from MCP
    universe_guidelines: Optional[Dict[str, Any]] # Universe rules from MCP
    world_lore: Optional[Dict[str, Any]]         # World backstory from MCP

    # Generated Output (populated by generate_narrative node)
    narrative_text: Optional[str]                # Generated narrative response
    choices: Optional[List[Dict[str, Any]]]      # Player choices
    image_prompt: Optional[str]                  # DALL-E prompt for scene
    cognitive_skill_updates: Optional[Dict[str, int]] # Skill XP changes

    # Metadata
    tokens_used: int                             # Total tokens consumed
    cost_usd: float                              # Total cost in USD
    error: Optional[str]                         # Error message if any
```

This state object is passed through each node, with each node reading from and writing to specific fields.

#### Workflow Graph

The Game Master Agent defines a two-node workflow:

```
┌─────────────────┐
│   Entry Point   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ gather_context  │◄─── Fetches player profile, universe guidelines,
└────────┬────────┘     and world lore from MCP servers
         │
         ▼
┌─────────────────┐
│generate_narrative│◄─── Uses Claude Sonnet 4 to generate narrative
└────────┬────────┘     based on gathered context
         │
         ▼
┌─────────────────┐
│      END        │
└─────────────────┘
```

**Workflow Definition Code:**
```python
from langgraph.graph import StateGraph, END

# Create the workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("gather_context", gather_context)
workflow.add_node("generate_narrative", generate_narrative)

# Define the flow
workflow.set_entry_point("gather_context")
workflow.add_edge("gather_context", "generate_narrative")
workflow.add_edge("generate_narrative", END)

# Compile into executable graph
agent_graph = workflow.compile()
```

#### Node Implementations

**1. gather_context Node**

This node fetches all necessary context from MCP servers before narrative generation:

```python
async def gather_context(state: AgentState) -> AgentState:
    """Step 1: Gather context from MCP servers"""
    try:
        # Fetch player cognitive profile
        player_profile = await mcp_client.get_player_cognitive_profile(
            UUID(state["profile_id"])
        )

        # Fetch universe guidelines
        universe_guidelines = await mcp_client.get_universe_guidelines(
            UUID(state["universe_id"])
        )

        # Fetch world lore and backstory
        world_lore = await mcp_client.get_world_lore(
            UUID(state["world_id"]),
            UUID(state["universe_id"])
        )

        # Update state with fetched context
        state["player_profile"] = player_profile
        state["universe_guidelines"] = universe_guidelines
        state["world_lore"] = world_lore

    except Exception as e:
        state["error"] = f"Error gathering context: {str(e)}"

    return state
```

**2. generate_narrative Node**

This node uses the gathered context to generate the narrative response via Claude:

```python
async def generate_narrative(state: AgentState) -> AgentState:
    """Step 2: Generate narrative using Claude"""

    # Build system prompt from gathered context
    system_prompt = build_system_prompt(state)

    # Build user prompt from player action
    user_prompt = f"""
    Player Character: {state['character_name']}
    Action Type: {state['action_type']}
    Action: {state['action_text']}

    Generate an immersive narrative response with:
    1. Vivid scene description
    2. 3-4 meaningful choices for the player
    3. Educational opportunities aligned with player's cognitive level
    4. An evocative image prompt for visual generation
    """

    # Invoke Claude Sonnet 4
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = llm.invoke(messages)

    # Parse the structured response
    parsed = parse_narrative_response(response.content)

    # Calculate costs
    input_tokens = response.usage_metadata["input_tokens"]
    output_tokens = response.usage_metadata["output_tokens"]
    cost_usd = calculate_cost(input_tokens, output_tokens)

    # Update state with generated content
    state["narrative_text"] = parsed["narrative"]
    state["choices"] = parsed["choices"]
    state["image_prompt"] = parsed["image_prompt"]
    state["cognitive_skill_updates"] = parsed["skill_updates"]
    state["tokens_used"] = input_tokens + output_tokens
    state["cost_usd"] = cost_usd

    return state
```

#### Workflow Execution

The compiled graph is executed asynchronously for each narrative generation request:

```python
@app.post("/generate-narrative")
async def generate_narrative_endpoint(request: NarrativeRequest):
    """FastAPI endpoint that executes the LangGraph workflow"""

    # Initialize state from request
    initial_state: AgentState = {
        "profile_id": str(request.profile_id),
        "character_name": request.character_name,
        "universe_id": str(request.universe_id),
        "world_id": str(request.world_id),
        "campaign_name": request.campaign_name,
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

    # Execute the workflow
    final_state = await agent_graph.ainvoke(initial_state)

    # Check for errors
    if final_state.get("error"):
        raise HTTPException(status_code=500, detail=final_state["error"])

    # Return the results
    return {
        "narrative": final_state["narrative_text"],
        "choices": final_state["choices"],
        "image_prompt": final_state["image_prompt"],
        "cognitive_updates": final_state["cognitive_skill_updates"],
        "tokens_used": final_state["tokens_used"],
        "cost_usd": final_state["cost_usd"]
    }
```

---

### Integration with Other Components

#### MCP Server Integration

LangGraph nodes directly interact with MCP servers to gather context:

```
┌──────────────┐
│  LangGraph   │
│gather_context│
└──────┬───────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│  Player     │   │  World/      │
│  Data MCP   │   │  Universe    │
│  (8001)     │   │  MCP (8002)  │
└─────────────┘   └──────────────┘
```

The `gather_context` node makes async HTTP calls to both MCP servers in parallel, fetching:
- **Player Data MCP**: Cognitive profile, learning goals, play style
- **World/Universe MCP**: World properties, backstory, universe guidelines

#### Claude API Integration

LangGraph nodes use the Claude API via LangChain's ChatAnthropic wrapper:

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=4096,
    temperature=0.7
)
```

The `generate_narrative` node constructs prompts from the gathered context and invokes Claude.

#### Orchestrator Integration

The Agent Orchestrator invokes the Game Master Agent's LangGraph workflow:

```
┌─────────────────┐
│  Orchestrator   │
│   (Port 9000)   │
└────────┬────────┘
         │
         │ POST /generate-narrative
         ▼
┌─────────────────┐
│  Game Master    │
│  LangGraph      │
│   Workflow      │
└────────┬────────┘
         │
         │ Returns: narrative + cost
         ▼
┌─────────────────┐
│  Orchestrator   │
│  Cost Tracking  │
└─────────────────┘
```

The Orchestrator:
1. Validates player budget before invoking
2. Calls the Game Master's `/generate-narrative` endpoint
3. Receives the final state with cost data
4. Updates cost tracking in Redis
5. Returns narrative to the client

---

### Error Handling in LangGraph

Each node includes error handling that updates the state's `error` field:

```python
async def gather_context(state: AgentState) -> AgentState:
    try:
        # Fetch context from MCPs
        ...
    except HTTPError as e:
        state["error"] = f"MCP connection error: {str(e)}"
    except Exception as e:
        state["error"] = f"Unexpected error: {str(e)}"

    return state
```

The workflow continues even if errors occur, allowing downstream nodes or the endpoint handler to check the `error` field and respond appropriately.

**Error Flow:**
```
gather_context (error) → generate_narrative → END
                                   │
                                   ▼
                         Check state["error"]
                                   │
                                   ▼
                         Return HTTP 500
```

---

### Future LangGraph Enhancements

1. **Conditional Branching**: Add decision nodes that route to different narrative styles based on player age or cognitive level
   ```python
   workflow.add_conditional_edges(
       "gather_context",
       lambda state: "simple_narrative" if state["player_profile"]["age"] < 10 else "complex_narrative"
   )
   ```

2. **Parallel Context Fetching**: Use LangGraph's parallel execution for independent MCP calls
   ```python
   workflow.add_node("fetch_player", fetch_player_profile)
   workflow.add_node("fetch_world", fetch_world_lore)
   # Both execute in parallel
   ```

3. **Multi-Agent Collaboration**: Connect multiple LangGraph workflows for specialized agents
   ```python
   # Game Master generates narrative
   # Quest Designer generates objectives
   # Both workflows coordinate via shared state
   ```

4. **Long-term Memory**: Add a node for retrieving relevant past campaign events from vector database
   ```python
   workflow.add_node("retrieve_memory", fetch_relevant_memories)
   workflow.add_edge("retrieve_memory", "generate_narrative")
   ```

5. **Iterative Refinement**: Add feedback loops for quality control
   ```python
   workflow.add_conditional_edges(
       "generate_narrative",
       lambda state: "refine" if quality_score(state) < 0.8 else "end"
   )
   ```

---

## Future Enhancements

1. **Additional MCP Servers:**
   - Quest/Mission MCP (story arcs and objectives)
   - NPC Personality MCP (character AI behaviors)
   - Item/Equipment MCP (game mechanics)

2. **Agent Improvements:**
   - Multi-agent collaboration (Game Master + Quest Designer)
   - Long-term memory with vector databases
   - Real-time streaming narrative generation

3. **Cost Optimization:**
   - Prompt caching for world context
   - Smaller models for simple interactions
   - Batch processing for non-interactive generation

4. **Analytics:**
   - Learning outcome tracking
   - Engagement metrics
   - Cognitive skill progression visualization
