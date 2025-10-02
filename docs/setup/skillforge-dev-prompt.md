# SkillForge RPG - Complete Development Requirements

## Project Overview

SkillForge is a hybrid AI-powered educational RPG platform featuring:
- Multi-account system (Individual, Family, Educational, Organizational)
- Multi-character gameplay (up to 10 characters per member)
- Universe/World system (categorical Universes containing genre-based Worlds)
- AI Agent-driven narrative generation and assessment
- Traditional microservices for CRUD and business logic
- MCP (Model Context Protocol) servers for AI context provision
- Full Docker containerization for local development

---

## Core Architecture Principles

1. **Hybrid Architecture**: Traditional microservices + AI Agents + MCP servers
2. **UUID Primary Keys**: All models use UUIDs (not integers) for primary and foreign keys
3. **Neo4j-First Data Modeling**: Maximize use of graph database for relationships
4. **GraphQL API**: Single unified endpoint for Django web app and Flutter mobile app
5. **Event-Driven**: RabbitMQ for inter-service communication
6. **Docker-First**: All components run in Docker containers (Docker Desktop for local dev)

---

## Technology Stack Summary

### Frontend
- **Django Web App**: Django 5.0, Tailwind CSS 3.x, HTMX 1.9, WebSockets
- **Flutter Mobile App**: Flutter 3.x, Dart 3.x, Riverpod 2.x, GraphQL client

### API Layer
- **GraphQL Gateway**: Strawberry GraphQL 0.219+, Django 5.0, Channels for WebSocket

### AI Infrastructure
- **AI Agents**: LangGraph 0.0.40+, LangChain 0.1+, Claude API (Anthropic), OpenAI GPT-4
- **MCP Servers**: FastAPI 0.104+, MCP SDK (Model Context Protocol)
- **Agent Orchestration**: Python 3.11+, Redis 7.2, Celery 5.3

### Microservices
- **Backend Services**: Python 3.11+, FastAPI 0.104+, Pydantic 2.x
- **Background Workers**: Celery 5.3, Celery Beat

### Data Layer
- **PostgreSQL 16**: Relational data (accounts, members, profiles, subscriptions)
- **Neo4j 5.13**: Graph database (relationships, skill trees, campaign graphs, family networks)
- **AWS DocumentDB 5.0** (MongoDB-compatible): Universe definitions, event sourcing, AI conversation history
- **Redis 7.2**: Caching, sessions, rate limiting, cost tracking

### Message Broker
- **RabbitMQ 3.12**: Event bus with topic exchanges

### External Services
- **Claude API**: Anthropic (primary LLM)
- **OpenAI API**: GPT-4 (secondary, fallback)
- **Stable Diffusion**: AI image generation
- **Stripe API**: Payment processing
- **Firebase**: FCM (push notifications), Analytics
- **AWS S3 + CloudFront**: Asset storage and CDN

### DevOps
- **Docker**: All services containerized
- **Docker Compose**: Local orchestration
- **Datadog/Sentry**: Monitoring and error tracking
- **LangSmith**: LLM observability

---

## Component Details

### 1. Django Web App

**Purpose**: Server-side rendered web interface for desktop browsers

**Technology**:
- Django 5.0 (Python web framework)
- Django Channels (WebSocket support)
- Tailwind CSS 3.x (styling)
- HTMX 1.9 (dynamic UI without heavy JavaScript)
- Strawberry GraphQL (GraphQL client integrated into Django)

**Key Features**:
- Account management dashboard
- Family member management
- Character creation and selection
- Universe browser
- Campaign management
- Parental control settings
- Real-time narrative updates via WebSocket

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "skillforge.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**Models** (Django ORM → PostgreSQL, with UUID primary keys):
- Account
- Member
- PlayerProfile
- Subscription
- ActivityLog

---

### 2. Flutter Mobile App

**Purpose**: Native iOS/Android application

**Technology**:
- Flutter 3.x (cross-platform framework)
- Dart 3.x
- Riverpod 2.x (state management)
- GraphQL Flutter client (graphql_flutter 5.x)
- SQLite (local storage)
- Hive (key-value store)

**Key Features**:
- Account switcher
- Character selection
- Universe browser
- Offline mode per character
- Push notifications (FCM/APNs)
- GraphQL queries/mutations

**Docker Setup** (for build environment):
```dockerfile
FROM cirrusci/flutter:3.16.0
WORKDIR /app
COPY . .
RUN flutter pub get
CMD ["flutter", "run"]
```

**Local Storage**:
- SQLite: Offline character data, cached quests
- Hive: Preferences, Universe favorites, session tokens

---

### 3. GraphQL API Gateway

**Purpose**: Unified API endpoint for both web and mobile clients

**Technology**:
- Strawberry GraphQL 0.219+ (Python GraphQL library)
- Django 5.0 (integrated with Strawberry)
- Django Channels (WebSocket subscriptions)
- JWT authentication (PyJWT 2.8+)

**Key Features**:
- Single endpoint for all queries/mutations
- Account context injection
- JWT-based authentication
- Rate limiting per account type
- WebSocket subscriptions for real-time updates
- Routes to both microservices AND AI agents

**Schema Examples**:
```graphql
type Query {
  me: Member
  myCharacters: [PlayerProfile!]!
  universes(filters: UniverseFilters): [Universe!]!
  worlds(universeId: UUID!, filters: WorldFilters): [World!]!
  campaigns(characterId: UUID!): [Campaign!]!
}

type Mutation {
  createCharacter(input: CreateCharacterInput!): PlayerProfile!
  startCampaign(input: StartCampaignInput!): Campaign!
  updateParentalControls(memberId: UUID!, input: ParentalControlsInput!): Member!
}

type Subscription {
  narrativeUpdate(campaignId: UUID!): NarrativeEvent!
  characterUpdate(characterId: UUID!): PlayerProfile!
}
```

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 4. MCP Servers (Model Context Protocol)

**Purpose**: Provide secure, structured context to AI agents

**Technology**:
- FastAPI 0.104+
- MCP SDK (Python implementation)
- Pydantic 2.x (data validation)
- Async database drivers (asyncpg, motor)

#### 4.1 Player Data MCP Server

**Provides to AI Agents**:
- Player cognitive profiles
- Character information
- Member-level permissions
- Family account structure
- Parental control settings

**Data Sources**:
- PostgreSQL: Accounts, Members, PlayerProfiles, MemberCognitiveProgress
- Redis: Active session data
- DocumentDB: Character narrative history

**MCP Endpoints**:
```python
@mcp_tool
async def get_player_cognitive_profile(player_id: UUID) -> CognitiveProfile:
    """Returns Bloom's taxonomy progress and core skills"""
    
@mcp_tool
async def get_character_info(character_id: UUID) -> CharacterInfo:
    """Returns character details, archetype, universe context"""
    
@mcp_tool
async def get_family_context(account_id: UUID) -> FamilyContext:
    """Returns family structure, parental controls, member ages"""
```

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "mcp_player.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

#### 4.2 World/Universe MCP Server

**Provides to AI Agents**:
- Universe definitions and guidelines
- World lore, geography, NPCs
- Visual style specifications
- Universe-specific narrative tone
- Previously generated content (consistency)

**Data Sources**:
- DocumentDB: universe_definitions, world_definitions, world_adaptations
- Neo4j: Universe-World relationship graph
- Redis: Cached frequently-accessed data

**MCP Endpoints**:
```python
@mcp_tool
async def get_universe_guidelines(universe_id: UUID) -> UniverseGuidelines:
    """Returns content rating, tone, features, modifications"""
    
@mcp_tool
async def get_world_lore(world_id: UUID) -> WorldLore:
    """Returns complete world lore, NPCs, regions, history"""
    
@mcp_tool
async def get_previously_generated_content(
    character_id: UUID, 
    content_type: str
) -> List[GeneratedContent]:
    """Returns past AI-generated content for consistency"""
```

#### 4.3 Educational Standards MCP Server

**Provides to AI Agents**:
- Common Core standards
- NGSS (Next Generation Science Standards)
- State-specific standards
- Curriculum alignment data
- Learning objective definitions

**Data Sources**:
- PostgreSQL: curriculum_standards table
- External APIs: State education department APIs

**MCP Endpoints**:
```python
@mcp_tool
async def get_standards_for_subject(
    subject: str, 
    grade_level: int
) -> List[Standard]:
    """Returns educational standards for validation"""
    
@mcp_tool
async def validate_learning_objective(
    objective: str, 
    subject: str
) -> ValidationResult:
    """Checks if objective aligns with standards"""
```

#### 4.4 AI Content Cache MCP Server

**Purpose**: Cache AI-generated content for consistency and cost savings

**Data Sources**:
- Redis: Hot cache (recently accessed)
- DocumentDB: Persistent cache
- PostgreSQL: Cache metadata

**MCP Endpoints**:
```python
@mcp_tool
async def get_cached_response(
    prompt_hash: str
) -> Optional[CachedResponse]:
    """Returns cached AI response if exists (30% cost savings)"""
    
@mcp_tool
async def store_ai_response(
    prompt_hash: str, 
    response: str, 
    metadata: dict
) -> bool:
    """Stores AI response for future reuse"""
```

**Docker Setup for All MCP Servers**:
```yaml
# docker-compose.yml
services:
  mcp-player-data:
    build: ./mcp-servers/player-data
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=${POSTGRES_URL}
      - REDIS_URL=${REDIS_URL}
      - DOCUMENTDB_URL=${DOCUMENTDB_URL}
    depends_on:
      - postgres
      - redis
      - documentdb
      
  mcp-world-universe:
    build: ./mcp-servers/world-universe
    ports:
      - "8002:8002"
    environment:
      - DOCUMENTDB_URL=${DOCUMENTDB_URL}
      - NEO4J_URL=${NEO4J_URL}
      - REDIS_URL=${REDIS_URL}
      
  mcp-educational-standards:
    build: ./mcp-servers/educational-standards
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=${POSTGRES_URL}
      
  mcp-content-cache:
    build: ./mcp-servers/content-cache
    ports:
      - "8004:8004"
    environment:
      - REDIS_URL=${REDIS_URL}
      - DOCUMENTDB_URL=${DOCUMENTDB_URL}
```

---

### 5. AI Agents

**Purpose**: Intelligent reasoning, creativity, complex decision-making

**Technology**:
- LangGraph 0.0.40+ (agent orchestration)
- LangChain 0.1+ (LLM integration)
- Claude API (Anthropic SDK)
- OpenAI API (OpenAI Python SDK)
- Redis (agent state persistence)
- DocumentDB (conversation history)

#### 5.1 AI Game Master Agent

**Purpose**: Core narrative generation and gameplay experience

**Technology Stack**:
```python
# requirements.txt
langgraph==0.0.40
langchain==0.1.0
anthropic==0.8.0
openai==1.0.0
redis==5.0.0
motor==3.3.0  # Async MongoDB driver for DocumentDB
```

**Key Capabilities**:
- Autonomous narrative generation
- Tool use (calls microservices as functions)
- MCP integration for context
- Conversation memory persistence
- Multi-turn reasoning
- Universe-aware content generation

**Agent Architecture**:
```python
from langgraph.graph import StateGraph
from langchain.agents import AgentExecutor
from langchain_anthropic import ChatAnthropic
from mcp_client import MCPClient

class GameMasterAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")
        self.mcp_player = MCPClient("http://mcp-player-data:8001")
        self.mcp_world = MCPClient("http://mcp-world-universe:8002")
        
        # Define tools (microservices)
        self.tools = [
            self.update_cognitive_skills,
            self.generate_visualization,
            self.save_narrative_event,
            self.check_challenge_completion
        ]
        
        # Create LangGraph workflow
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        graph = StateGraph()
        
        # States: plan → gather_context → generate → validate → execute
        graph.add_node("plan", self.plan_narrative)
        graph.add_node("gather_context", self.gather_context)
        graph.add_node("generate", self.generate_narrative)
        graph.add_node("validate", self.validate_output)
        graph.add_node("execute", self.execute_tools)
        
        # Edges
        graph.add_edge("plan", "gather_context")
        graph.add_edge("gather_context", "generate")
        graph.add_edge("generate", "validate")
        graph.add_conditional_edges(
            "validate",
            self.should_regenerate,
            {"regenerate": "generate", "execute": "execute"}
        )
        
        return graph.compile()
    
    async def gather_context(self, state):
        """Calls MCP servers to get context"""
        player_profile = await self.mcp_player.get_player_cognitive_profile(
            state["player_id"]
        )
        world_lore = await self.mcp_world.get_world_lore(
            state["world_id"]
        )
        universe_guidelines = await self.mcp_world.get_universe_guidelines(
            state["universe_id"]
        )
        
        return {
            **state,
            "player_profile": player_profile,
            "world_lore": world_lore,
            "universe_guidelines": universe_guidelines
        }
    
    async def generate_narrative(self, state):
        """Generates narrative using Claude with full context"""
        prompt = self._build_prompt(state)
        response = await self.llm.ainvoke(prompt)
        return {**state, "narrative": response.content}
    
    async def update_cognitive_skills(self, player_id: UUID, skill: str, delta: int):
        """Tool: Update player's cognitive skills (calls microservice)"""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://player-development:8000/skills/{player_id}",
                json={"skill": skill, "delta": delta}
            )
```

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "agents.game_master"]
```

**Environment Variables**:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
MCP_PLAYER_DATA_URL=http://mcp-player-data:8001
MCP_WORLD_UNIVERSE_URL=http://mcp-world-universe:8002
REDIS_URL=redis://redis:6379
DOCUMENTDB_URL=mongodb://documentdb:27017
```

#### 5.2 Content Adaptation Agent

**Purpose**: Intelligently modify Worlds for different Universe categories

**Key Capabilities**:
- Reads base World definitions via MCP
- Reasons about appropriate modifications per Universe
- Generates Universe-specific variants
- Human-in-loop approval workflow

**Agent Architecture**:
```python
class ContentAdaptationAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")
        self.mcp_world = MCPClient("http://mcp-world-universe:8002")
    
    async def adapt_world_to_universe(
        self, 
        world_id: UUID, 
        universe_id: UUID
    ) -> WorldAdaptation:
        # Get base world
        base_world = await self.mcp_world.get_world_lore(world_id)
        
        # Get universe guidelines
        universe_guidelines = await self.mcp_world.get_universe_guidelines(
            universe_id
        )
        
        # Reason about modifications
        prompt = f"""
        Base World: {base_world}
        Target Universe: {universe_guidelines}
        
        Analyze what modifications are needed to make this World 
        appropriate for this Universe. Consider:
        - Content rating adjustments
        - Tone modifications
        - Vocabulary changes
        - Thematic adaptations
        
        Provide detailed reasoning for each change.
        """
        
        analysis = await self.llm.ainvoke(prompt)
        
        # Generate adapted content
        adapted_world = await self._generate_adaptation(
            base_world, 
            universe_guidelines, 
            analysis
        )
        
        # Queue for human review
        await self._submit_for_approval(adapted_world)
        
        return adapted_world
```

#### 5.3 Educational Assessment Agent

**Purpose**: Map player actions to learning outcomes, provide pedagogical feedback

**Key Capabilities**:
- Observes player decisions in real-time
- Maps actions to Bloom's taxonomy levels
- Identifies learning gaps
- Generates scaffolded feedback
- Writes progress reports for teachers

**Agent Architecture**:
```python
class EducationalAssessmentAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="gpt-4")  # GPT-4 for structured outputs
        self.mcp_player = MCPClient("http://mcp-player-data:8001")
        self.mcp_standards = MCPClient("http://mcp-educational-standards:8003")
    
    async def assess_player_action(
        self,
        player_id: UUID,
        action: PlayerAction,
        context: ChallengeContext
    ) -> Assessment:
        # Get player's current cognitive level
        profile = await self.mcp_player.get_player_cognitive_profile(player_id)
        
        # Get relevant standards
        standards = await self.mcp_standards.get_standards_for_subject(
            context.subject,
            profile.grade_level
        )
        
        # Assess action
        prompt = f"""
        Player Action: {action}
        Challenge Context: {context}
        Player Profile: {profile}
        Relevant Standards: {standards}
        
        Assess this action:
        1. What Bloom's taxonomy level does this demonstrate?
        2. Which learning objectives were met?
        3. What cognitive skills were used?
        4. What scaffolding would help the player progress?
        
        Provide structured JSON output.
        """
        
        assessment = await self.llm.ainvoke(
            prompt,
            response_format={"type": "json_object"}
        )
        
        return Assessment.parse_obj(assessment)
```

#### 5.4 Other Agents (Brief)

**Parental Monitoring Agent**: Analyzes activity logs, generates weekly summaries, flags concerns
**Universe Recommendation Agent**: Interviews users, understands goals, explains recommendations
**NPC Conversation Agents**: Per-NPC personality with memory (major NPCs only)

#### 5.5 Agent Orchestration & Cost Control

**Purpose**: Manage agent lifecycle, track costs, enforce limits

**Key Components**:
```python
class AgentOrchestrator:
    def __init__(self):
        self.redis = Redis(host='redis', port=6379)
        self.active_agents = {}
        self.warm_pool_size = 5
    
    async def get_or_create_agent(
        self, 
        agent_type: str, 
        session_id: UUID
    ) -> Agent:
        """Cold-start agents on demand, maintain warm pool"""
        
        # Check warm pool first
        if agent_type in self.warm_pool:
            return self.warm_pool[agent_type].pop()
        
        # Create new agent
        agent = self._create_agent(agent_type)
        
        # Load context from MCP/DocumentDB
        await agent.load_context(session_id)
        
        # Track in active agents
        self.active_agents[session_id] = agent
        
        return agent
    
    async def track_cost(
        self, 
        account_id: UUID, 
        tokens_used: int, 
        cost: float
    ):
        """Track per-account AI costs in Redis"""
        
        # Increment daily cost
        key = f"ai_cost:{account_id}:{date.today()}"
        await self.redis.incrbyfloat(key, cost)
        
        # Check budget limit
        daily_cost = await self.redis.get(key)
        budget_limit = await self._get_account_budget(account_id)
        
        if float(daily_cost) >= budget_limit:
            # Throttle account
            await self._throttle_account(account_id)
            await self._notify_user(account_id, "budget_limit_reached")
    
    async def shutdown_agent(self, session_id: UUID):
        """Shutdown agent, save state, release resources"""
        
        agent = self.active_agents.get(session_id)
        if not agent:
            return
        
        # Save conversation history to DocumentDB
        await agent.save_conversation_history()
        
        # Save state to Redis
        await agent.save_state()
        
        # Return to warm pool if space available
        if len(self.warm_pool.get(agent.type, [])) < self.warm_pool_size:
            self.warm_pool[agent.type].append(agent)
        else:
            # Cleanup
            del self.active_agents[session_id]
```

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "orchestrator.main"]
```

---

### 6. Traditional Microservices

All microservices follow this pattern:
- **Technology**: Python 3.11+, FastAPI 0.104+, Pydantic 2.x
- **Database**: PostgreSQL (via SQLAlchemy 2.0+, asyncpg), Neo4j (via neo4j-driver 5.x)
- **Event Publishing**: RabbitMQ (via aio-pika 9.x)
- **Docker**: Individual Dockerfiles, orchestrated via docker-compose

#### 6.1 Account Service

**Purpose**: CRUD for accounts, subscriptions, billing

**Models** (PostgreSQL with UUIDs):
```python
from sqlalchemy import Column, String, Enum, Integer, Date, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Account(Base):
    __tablename__ = 'accounts'
    
    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_owner_member_id = Column(UUID(as_uuid=True), ForeignKey('members.member_id'))
    account_type = Column(Enum('individual', 'family', 'educational', 'organizational'))
    subscription_tier = Column(String(50))
    subscription_status = Column(Enum('active', 'past_due', 'cancelled', 'suspended'))
    max_members = Column(Integer, default=1)
    current_member_count = Column(Integer, default=1)
    stripe_customer_id = Column(String(100))
    created_at = Column(TIMESTAMP, server_default='now()')
```

**Endpoints**:
```python
@app.post("/accounts", response_model=AccountResponse)
async def create_account(account: AccountCreate):
    """Create new account"""
    
@app.get("/accounts/{account_id}")
async def get_account(account_id: UUID):
    """Get account details"""
    
@app.patch("/accounts/{account_id}/subscription")
async def update_subscription(account_id: UUID, subscription: SubscriptionUpdate):
    """Update subscription tier"""
```

**Docker Setup**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "account_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 6.2 Member & Parental Controls Service

**Purpose**: Family member CRUD, age-based restrictions, time limits

**Models** (PostgreSQL):
```python
class Member(Base):
    __tablename__ = 'members'
    
    member_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey('accounts.account_id'), nullable=False)
    display_name = Column(String(100), nullable=False)
    email = Column(String(255))  # Optional for children
    date_of_birth = Column(Date, nullable=False)
    role = Column(Enum('owner', 'parent', 'teen', 'child', 'student', 'employee'))
    can_manage_account = Column(Boolean, default=False)
    
    # Parental Controls
    daily_time_limit_minutes = Column(Integer)
    quiet_hours_start = Column(Time)
    quiet_hours_end = Column(Time)
    allowed_universes = Column(JSON)  # List of UUID strings
    can_play_with_strangers = Column(Boolean, default=False)
```

**Neo4j Models** (Family Relationships):
```cypher
// Family network graph
CREATE (m:Member {
    member_id: 'uuid-here',
    display_name: 'John Smith',
    role: 'parent'
})

CREATE (child:Member {
    member_id: 'uuid-here',
    display_name: 'Emma Smith',
    role: 'child'
})

CREATE (m)-[:PARENT_OF]->(child)
CREATE (m)-[:MANAGES]->(child)
```

#### 6.3 Character Profile Service

**Purpose**: Multi-character CRUD, character switching, cognitive tracking

**Models** (PostgreSQL):
```python
class PlayerProfile(Base):
    __tablename__ = 'player_profiles'
    
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey('members.member_id'), nullable=False)
    character_name = Column(String(100), nullable=False)
    universe_id = Column(UUID(as_uuid=True), ForeignKey('universes.universe_id'), nullable=False)
    world_id = Column(UUID(as_uuid=True), ForeignKey('worlds.world_id'), nullable=False)
    archetype = Column(String(100))
    appearance_data = Column(JSON)
    portrait_url = Column(String(500))
    total_playtime_minutes = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default='now()')

class MemberCognitiveProgress(Base):
    __tablename__ = 'member_cognitive_progress'
    
    member_id = Column(UUID(as_uuid=True), ForeignKey('members.member_id'), primary_key=True)
    
    # Bloom's Taxonomy
    remember_mastered = Column(Boolean, default=False)
    understand_mastered = Column(Boolean, default=False)
    apply_mastered = Column(Boolean, default=False)
    analyze_progress = Column(Numeric(3, 2), default=0.00)
    evaluate_progress = Column(Numeric(3, 2), default=0.00)
    create_progress = Column(Numeric(3, 2), default=0.00)
    
    # Core Skills (1-10)
    empathy_level = Column(Integer, default=1)
    strategy_level = Column(Integer, default=1)
    creativity_level = Column(Integer, default=1)
    courage_level = Column(Integer, default=1)
```

**Neo4j Models** (Character Relationships):
```cypher
// Character relationship graph
CREATE (char:PlayerProfile {
    profile_id: 'uuid-here',
    character_name: 'Seraphina',
    universe_id: 'uuid-here',
    world_id: 'uuid-here'
})

CREATE (npc:NPC {
    npc_id: 'uuid-here',
    name: 'Queen Aria',
    world_id: 'uuid-here'
})

CREATE (char)-[:TRUSTS {level: 8}]->(npc)
CREATE (char)-[:ALLIED_WITH]->(npc)
```

#### 6.4 Universe & World Services

**Purpose**: CRUD for Universes and Worlds, Universe-World mappings

**Models** (PostgreSQL):
```python
class Universe(Base):
    __tablename__ = 'universes'
    
    universe_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    universe_name = Column(String(255), nullable=False)
    universe_type = Column(Enum('content_rating', 'age_focused', 'gameplay_style', 'context_based'))
    purpose = Column(Text)
    target_age_min = Column(Integer)
    target_age_max = Column(Integer)
    max_content_rating = Column(String(10))
    features = Column(JSON)
    creator_type = Column(Enum('official', 'community'))

class World(Base):
    __tablename__ = 'worlds'
    
    world_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_name = Column(String(255), nullable=False)
    genre = Column(String(50), nullable=False)
    base_content_rating = Column(String(10))
    themes = Column(JSON)
    visual_style = Column(String(100))
    can_be_adapted_to = Column(JSON)  # List of universe_ids
    creator_id = Column(UUID(as_uuid=True))
    creator_type = Column(Enum('official', 'community'))

class UniverseWorldMapping(Base):
    __tablename__ = 'universe_world_mappings'
    
    mapping_id = Column(BigInteger, primary_key=True, autoincrement=True)
    universe_id = Column(UUID(as_uuid=True), ForeignKey('universes.universe_id'))
    world_id = Column(UUID(as_uuid=True), ForeignKey('worlds.world_id'))
    requires_adaptation = Column(Boolean, default=False)
    adapted_world_version_id = Column(UUID(as_uuid=True))
```

**Neo4j Models** (Universe-World Relationships):
```cypher
// Universe-World graph
CREATE (u:Universe {
    universe_id: 'uuid-here',
    name: 'Educational Universe',
    type: 'gameplay_style'
})

CREATE (w:World {
    world_id: 'uuid-here',
    name: 'The Shattered Kingdoms',
    genre: 'fantasy'
})

CREATE (u)-[:CONTAINS {
    requires_adaptation: true,
    adaptation_level: 'moderate'
}]->(w)
```

**DocumentDB Collections** (Universe/World Definitions):
```javascript
// universe_definitions collection
{
  "_id": "uuid-here",
  "universe_id": "uuid-here",
  "name": "Educational Universe",
  "narrative": {
    "tone_profile": {...},
    "vocabulary_style": {...}
  },
  "features": {
    "teacher_dashboard": true,
    "curriculum_aligned": true
  }
}

// world_definitions collection
{
  "_id": "uuid-here",
  "world_id": "uuid-here",
  "name": "The Shattered Kingdoms",
  "lore": {...},
  "npcs": [...],
  "regions": [...],
  "quests": [...]
}
```

#### 6.5 Campaign Management Service

**Purpose**: Multi-character campaign orchestration, state management

**Models** (PostgreSQL):
```python
class Campaign(Base):
    __tablename__ = 'campaigns'
    
    campaign_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_name = Column(String(255), nullable=False)
    universe_id = Column(UUID(as_uuid=True), ForeignKey('universes.universe_id'))
    world_id = Column(UUID(as_uuid=True), ForeignKey('worlds.world_id'))
    campaign_type = Column(Enum('solo', 'multiplayer_coop', 'family', 'competitive'))
    max_players = Column(Integer, default=1)
    current_player_count = Column(Integer, default=0)
    state_model = Column(Enum('shared', 'instanced', 'hybrid'), default='instanced')
    current_chapter = Column(Integer, default=1)

class CampaignParticipant(Base):
    __tablename__ = 'campaign_participants'
    
    participant_id = Column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey('campaigns.campaign_id'))
    profile_id = Column(UUID(as_uuid=True), ForeignKey('player_profiles.profile_id'))
    member_id = Column(UUID(as_uuid=True), ForeignKey('members.member_id'))
    role = Column(String(50))
    sessions_participated = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint('campaign_id', 'member_id', name='unique_member_campaign'),
    )
```

**Neo4j Models** (Campaign Graphs):
```cypher
// Campaign participation graph
CREATE (campaign:Campaign {
    campaign_id: 'uuid-here',
    name: 'Family Adventure',
    type: 'family'
})

CREATE (char1:PlayerProfile {profile_id: 'uuid-here'})
CREATE (char2:PlayerProfile {profile_id: 'uuid-here'})

CREATE (char1)-[:PARTICIPATES_IN {
    role: 'party_leader',
    sessions: 5
}]->(campaign)

CREATE (char2)-[:PARTICIPATES_IN {
    role: 'member',
    sessions: 5
}]->(campaign)
```

#### 6.6 Other Core Services (Brief)

**Player Development Service**: Cognitive skill updates (deterministic), Bloom's tracking
**Challenge Service**: Challenge CRUD, scoring, mapping to context
**Character Service**: Character CRUD, archetypes, NPC templates
**Visualization Service**: Image generation orchestration, asset caching
**Session Service**: Session state CRUD, Universe transitions
**Social Service**: Family features, campaign sharing, multiplayer coordination
**Analytics Service**: Data aggregation, metrics calculation
**Educational Dashboard Service**: Teacher UI, class management, progress display

---

### 7. Data Layer Setup

#### 7.1 PostgreSQL (Relational Data)

**Version**: PostgreSQL 16

**Docker Setup**:
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: skillforge
      POSTGRES_USER: skillforge_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d

volumes:
  postgres_data:
```

**Alembic Migrations** (SQLAlchemy):
```bash
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

**Key Tables**:
- accounts
- members
- player_profiles
- member_cognitive_progress
- universes
- worlds
- universe_world_mappings
- campaigns
- campaign_participants
- subscriptions
- activity_logs

#### 7.2 Neo4j (Graph Database)

**Version**: Neo4j 5.13

**Docker Setup**:
```yaml
services:
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
```

**Models in Neo4j** (Maximize graph usage):

1. **Account-Member Relationships**:
```cypher
CREATE (a:Account {account_id: $account_id})
CREATE (m1:Member {member_id: $member_id, role: 'owner'})
CREATE (m2:Member {member_id: $member_id, role: 'child'})
CREATE (a)-[:HAS_MEMBER]->(m1)
CREATE (a)-[:HAS_MEMBER]->(m2)
CREATE (m1)-[:PARENT_OF]->(m2)
```

2. **Universe-World Relationships**:
```cypher
CREATE (u:Universe {universe_id: $universe_id})
CREATE (w:World {world_id: $world_id})
CREATE (u)-[:CONTAINS {adaptation_level: 'moderate'}]->(w)
```

3. **Character Relationships**:
```cypher
CREATE (char:PlayerProfile {profile_id: $profile_id})
CREATE (npc:NPC {npc_id: $npc_id})
CREATE (char)-[:TRUSTS {level: 8}]->(npc)
CREATE (char)-[:ALLIED_WITH]->(faction:Faction)
```

4. **Campaign Participation**:
```cypher
CREATE (campaign:Campaign {campaign_id: $campaign_id})
CREATE (char1:PlayerProfile {profile_id: $profile_id1})
CREATE (char2:PlayerProfile {profile_id: $profile_id2})
CREATE (char1)-[:PARTICIPATES_IN]->(campaign)
CREATE (char2)-[:PARTICIPATES_IN]->(campaign)
```

5. **Skill Dependencies**:
```cypher
CREATE (skill1:Skill {name: 'Empathy', level: 5})
CREATE (skill2:Skill {name: 'Negotiation', level: 3})
CREATE (skill2)-[:REQUIRES {min_level: 4}]->(skill1)
```

6. **Quest Dependencies**:
```cypher
CREATE (q1:Quest {quest_id: $quest_id1})
CREATE (q2:Quest {quest_id: $quest_id2})
CREATE (q2)-[:REQUIRES_COMPLETION]->(q1)
```

**Python Driver Usage**:
```python
from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def create_character_relationship(self, char_id: UUID, npc_id: UUID, relationship: str):
        with self.driver.session() as session:
            session.run("""
                MATCH (char:PlayerProfile {profile_id: $char_id})
                MATCH (npc:NPC {npc_id: $npc_id})
                MERGE (char)-[r:RELATIONSHIP {type: $relationship}]->(npc)
                """,
                char_id=str(char_id),
                npc_id=str(npc_id),
                relationship=relationship
            )
```

#### 7.3 AWS DocumentDB (MongoDB-Compatible)

**Purpose**: Universe/World definitions, event sourcing, AI conversation history

**Docker Setup** (Local MongoDB for Development):
```yaml
services:
  mongodb:
    image: mongo:7.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

**Collections**:

1. **universe_definitions**: Complete Universe specifications
2. **world_definitions**: Complete World lore, NPCs, regions
3. **world_adaptations**: Universe-specific world modifications
4. **universe_narrative_context**: Tone profiles, vocabulary patterns
5. **challenge_events**: Event sourcing for player responses
6. **dialogue_history**: Character-specific NPC conversations
7. **narrative_content**: AI-generated storylines
8. **player_actions**: Timestamped player decisions
9. **ai_conversation_history**: Game Master agent conversation memory

**Python Driver** (Motor - Async):
```python
from motor.motor_asyncio import AsyncIOMotorClient

class DocumentDBClient:
    def __init__(self, uri):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.skillforge
    
    async def save_narrative_event(self, event: dict):
        await self.db.narrative_content.insert_one(event)
    
    async def get_universe_definition(self, universe_id: UUID):
        return await self.db.universe_definitions.find_one(
            {"universe_id": str(universe_id)}
        )
```

#### 7.4 Redis (Cache & Sessions)

**Version**: Redis 7.2

**Docker Setup**:
```yaml
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

**Usage Patterns**:
```python
from redis.asyncio import Redis

class RedisClient:
    def __init__(self, url):
        self.redis = Redis.from_url(url, decode_responses=True)
    
    async def cache_universe_data(self, universe_id: UUID, data: dict):
        key = f"universe:{universe_id}"
        await self.redis.setex(key, 3600, json.dumps(data))
    
    async def track_ai_cost(self, account_id: UUID, cost: float):
        key = f"ai_cost:{account_id}:{date.today()}"
        await self.redis.incrbyfloat(key, cost)
```

---

### 8. Message Broker (RabbitMQ)

**Version**: RabbitMQ 3.12

**Docker Setup**:
```yaml
services:
  rabbitmq:
    image: rabbitmq:3.12-management
    environment:
      RABBITMQ_DEFAULT_USER: skillforge
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

volumes:
  rabbitmq_data:
```

**Exchange Configuration**:
```python
import aio_pika

async def setup_exchanges():
    connection = await aio_pika.connect_robust("amqp://rabbitmq:5672")
    channel = await connection.channel()
    
    # Topic exchange for domain events
    exchange = await channel.declare_exchange(
        "skillforge.events",
        aio_pika.ExchangeType.TOPIC,
        durable=True
    )
    
    return exchange

# Publish event
async def publish_event(exchange, routing_key: str, message: dict):
    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            content_type="application/json"
        ),
        routing_key=routing_key
    )

# Examples:
# "account.created"
# "character.created"
# "campaign.started"
# "narrative.generated"
# "skill.updated"
```

---

### 9. External Services Integration

#### 9.1 Claude API (Anthropic)

```bash
pip install anthropic
```

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = await client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    messages=[
        {"role": "user", "content": "Generate narrative..."}
    ]
)
```

#### 9.2 OpenAI API

```bash
pip install openai
```

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = await client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Assess player action..."}
    ]
)
```

#### 9.3 Stable Diffusion (Replicate or local)

```bash
pip install replicate
```

```python
import replicate

output = replicate.run(
    "stability-ai/stable-diffusion:...",
    input={"prompt": "watercolor fantasy portrait..."}
)
```

#### 9.4 Stripe

```bash
pip install stripe
```

```python
import stripe

stripe.api_key = os.environ["STRIPE_API_KEY"]

customer = stripe.Customer.create(
    email="user@example.com",
    payment_method=payment_method_id
)

subscription = stripe.Subscription.create(
    customer=customer.id,
    items=[{"price": "price_family_tier"}]
)
```

---

### 10. Complete Docker Compose Setup

**Project Structure**:
```
skillforge/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env
├── services/
│   ├── web-app/           # Django
│   ├── mobile-app/        # Flutter
│   ├── api-gateway/       # GraphQL
│   ├── account-service/
│   ├── member-service/
│   ├── character-service/
│   ├── universe-service/
│   ├── world-service/
│   ├── campaign-service/
│   └── ...
├── mcp-servers/
│   ├── player-data/
│   ├── world-universe/
│   ├── educational-standards/
│   └── content-cache/
├── ai-agents/
│   ├── game-master/
│   ├── content-adaptation/
│   ├── educational-assessment/
│   └── orchestrator/
└── shared/
    ├── models/            # Shared Pydantic models
    ├── utils/
    └── config/
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  # ============================================
  # Data Layer
  # ============================================
  
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: skillforge
      POSTGRES_USER: skillforge_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U skillforge_user"]
      interval: 10s
      timeout: 5s
      retries: 5
  
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
  
  mongodb:
    image: mongo:7.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
  
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
  
  rabbitmq:
    image: rabbitmq:3.12-management
    environment:
      RABBITMQ_DEFAULT_USER: skillforge
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
  
  # ============================================
  # MCP Servers
  # ============================================
  
  mcp-player-data:
    build: ./mcp-servers/player-data
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - REDIS_URL=redis://redis:6379
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
  
  mcp-world-universe:
    build: ./mcp-servers/world-universe
    ports:
      - "8002:8002"
    environment:
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - mongodb
      - neo4j
      - redis
  
  mcp-educational-standards:
    build: ./mcp-servers/educational-standards
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
    depends_on:
      postgres:
        condition: service_healthy
  
  mcp-content-cache:
    build: ./mcp-servers/content-cache
    ports:
      - "8004:8004"
    environment:
      - REDIS_URL=redis://redis:6379
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
    depends_on:
      - redis
      - mongodb
  
  # ============================================
  # AI Agents
  # ============================================
  
  agent-orchestrator:
    build: ./ai-agents/orchestrator
    ports:
      - "9000:9000"
    environment:
      - REDIS_URL=redis://redis:6379
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
      - mongodb
      - mcp-player-data
      - mcp-world-universe
  
  agent-game-master:
    build: ./ai-agents/game-master
    deploy:
      replicas: 3  # Multiple instances for load balancing
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MCP_PLAYER_DATA_URL=http://mcp-player-data:8001
      - MCP_WORLD_UNIVERSE_URL=http://mcp-world-universe:8002
      - MCP_CONTENT_CACHE_URL=http://mcp-content-cache:8004
      - REDIS_URL=redis://redis:6379
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - ORCHESTRATOR_URL=http://agent-orchestrator:9000
    depends_on:
      - agent-orchestrator
      - mcp-player-data
      - mcp-world-universe
  
  agent-content-adaptation:
    build: ./ai-agents/content-adaptation
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MCP_WORLD_UNIVERSE_URL=http://mcp-world-universe:8002
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
    depends_on:
      - mcp-world-universe
  
  agent-educational-assessment:
    build: ./ai-agents/educational-assessment
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MCP_PLAYER_DATA_URL=http://mcp-player-data:8001
      - MCP_EDUCATIONAL_STANDARDS_URL=http://mcp-educational-standards:8003
    depends_on:
      - mcp-player-data
      - mcp-educational-standards
  
  # ============================================
  # Traditional Microservices
  # ============================================
  
  api-gateway:
    build: ./services/api-gateway
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
      - AGENT_ORCHESTRATOR_URL=http://agent-orchestrator:9000
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
  
  account-service:
    build: ./services/account-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
      - STRIPE_API_KEY=${STRIPE_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_started
  
  member-service:
    build: ./services/member-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      - postgres
      - neo4j
      - rabbitmq
  
  character-service:
    build: ./services/character-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      - postgres
      - neo4j
  
  universe-service:
    build: ./services/universe-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
    depends_on:
      - postgres
      - neo4j
      - mongodb
  
  world-service:
    build: ./services/world-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - NEO4J_URL=bolt://neo4j:7687
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
    depends_on:
      - postgres
      - neo4j
      - mongodb
  
  campaign-service:
    build: ./services/campaign-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - NEO4J_URL=bolt://neo4j:7687
      - MONGODB_URL=mongodb://admin:${MONGO_PASSWORD}@mongodb:27017
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      - postgres
      - neo4j
      - mongodb
  
  player-development-service:
    build: ./services/player-development-service
    environment:
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
    depends_on:
      - postgres
      - rabbitmq
  
  # ============================================
  # Frontend Applications
  # ============================================
  
  web-app:
    build: ./services/web-app
    ports:
      - "3000:3000"
    environment:
      - GRAPHQL_ENDPOINT=http://api-gateway:8000/graphql
      - WEBSOCKET_ENDPOINT=ws://api-gateway:8000/ws
    depends_on:
      - api-gateway
  
  # ============================================
  # Background Workers
  # ============================================
  
  celery-worker:
    build: ./services/celery-worker
    command: celery -A tasks worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://skillforge:${RABBITMQ_PASSWORD}@rabbitmq:5672
      - DATABASE_URL=postgresql://skillforge_user:${POSTGRES_PASSWORD}@postgres:5432/skillforge
    depends_on:
      - redis
      - rabbitmq
      - postgres
  
  celery-beat:
    build: ./services/celery-worker
    command: celery -A tasks beat --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

volumes:
  postgres_data:
  neo4j_data:
  mongodb_data:
  redis_data:
  rabbitmq_data:
```

**.env file**:
```bash
# Database Passwords
POSTGRES_PASSWORD=your_postgres_password
NEO4J_PASSWORD=your_neo4j_password
MONGO_PASSWORD=your_mongo_password
RABBITMQ_PASSWORD=your_rabbitmq_password

# API Keys
ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-your-key
STRIPE_API_KEY=sk_test_your_key

# JWT
JWT_SECRET=your_jwt_secret_key

# External Services
STABLE_DIFFUSION_API_KEY=your_key
FIREBASE_PROJECT_ID=your_project
```

**Running Locally**:
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild specific service
docker-compose up -d --build account-service

# Run migrations
docker-compose exec postgres psql -U skillforge_user -d skillforge -f /migrations/001_initial.sql

# Access Neo4j Browser
open http://localhost:7474

# Access RabbitMQ Management
open http://localhost:15672
```

---

## Development Workflow

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/yourusername/skillforge.git
cd skillforge

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Start infrastructure (databases, MCP servers)
docker-compose up -d postgres neo4j mongodb redis rabbitmq
docker-compose up -d mcp-player-data mcp-world-universe mcp-educational-standards mcp-content-cache

# Run database migrations
docker-compose exec postgres psql -U skillforge_user -d skillforge -f /migrations/001_initial.sql

# Seed Neo4j with initial data
docker-compose exec neo4j cypher-shell -u neo4j -p ${NEO4J_PASSWORD} -f /cypher/001_initial.cypher

# Start microservices
docker-compose up -d account-service member-service character-service

# Start AI agents
docker-compose up -d agent-orchestrator agent-game-master

# Start frontend
docker-compose up -d web-app api-gateway
```

### 2. Development Containers

Each service has hot-reload enabled for development:

```dockerfile
# Example: account-service/Dockerfile.dev
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Install dev dependencies
RUN pip install watchdog pytest pytest-asyncio
COPY . .
# Use watchdog for hot reload
CMD ["watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### 3. Testing

```bash
# Run tests for specific service
docker-compose exec account-service pytest

# Run all tests
docker-compose exec -T account-service pytest
docker-compose exec -T member-service pytest
docker-compose exec -T character-service pytest

# Integration tests
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### 4. Monitoring

```bash
# View logs for specific service
docker-compose logs -f agent-game-master

# View logs for all AI agents
docker-compose logs -f agent-orchestrator agent-game-master agent-content-adaptation

# View database logs
docker-compose logs -f postgres neo4j mongodb
```

---

## Critical Implementation Notes

### UUID Primary Keys

All models MUST use UUIDs:

```python
# Correct - PostgreSQL
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Account(Base):
    __tablename__ = 'accounts'
    account_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ... other columns

# Correct - Neo4j (store as string)
from neo4j import GraphDatabase

def create_account_node(tx, account_id: uuid.UUID):
    query = """
    CREATE (a:Account {account_id: $account_id})
    RETURN a
    """
    result = tx.run(query, account_id=str(account_id))
    return result.single()

# Correct - DocumentDB/MongoDB (store as string)
from motor.motor_asyncio import AsyncIOMotorClient
import uuid

async def save_universe_definition(universe_id: uuid.UUID, definition: dict):
    await db.universe_definitions.insert_one({
        "_id": str(universe_id),  # MongoDB _id as string UUID
        "universe_id": str(universe_id),
        **definition
    })

# INCORRECT - Don't use auto-incrementing integers
class Account(Base):
    account_id = Column(Integer, primary_key=True, autoincrement=True)  # ❌ WRONG
```

### Neo4j Best Practices

Maximize use of Neo4j for relationships:

**What Goes in Neo4j:**
- Family relationships (PARENT_OF, MANAGES, SIBLING_OF)
- Character relationships (TRUSTS, ALLIED_WITH, ENEMY_OF)
- Universe-World mappings (CONTAINS, ADAPTED_FROM)
- Campaign participation (PARTICIPATES_IN, PARTY_MEMBER)
- Skill dependencies (REQUIRES, UNLOCKS)
- Quest dependencies (REQUIRES_COMPLETION, LEADS_TO)
- NPC relationships (KNOWS, WORKS_FOR, BETRAYED_BY)
- Faction relationships (MEMBER_OF, AT_WAR_WITH, ALLIED_WITH)

**What Stays in PostgreSQL:**
- Core entity data (accounts, members, profiles, subscriptions)
- Billing/payment data (security-critical)
- Activity logs (time-series data)
- Cognitive progress (numerical data with frequent updates)

**Example: Character Creation Flow**

```python
# 1. Create in PostgreSQL (core data)
async def create_character_postgres(profile_data: dict):
    profile = PlayerProfile(
        profile_id=uuid.uuid4(),
        member_id=profile_data['member_id'],
        character_name=profile_data['character_name'],
        universe_id=profile_data['universe_id'],
        world_id=profile_data['world_id']
    )
    db.add(profile)
    await db.commit()
    return profile

# 2. Create relationships in Neo4j
async def create_character_neo4j(profile_id: uuid.UUID, member_id: uuid.UUID, 
                                  world_id: uuid.UUID):
    with driver.session() as session:
        session.run("""
            // Create character node
            CREATE (c:PlayerProfile {
                profile_id: $profile_id,
                created_at: datetime()
            })
            
            // Link to member
            MATCH (m:Member {member_id: $member_id})
            CREATE (m)-[:OWNS]->(c)
            
            // Link to world
            MATCH (w:World {world_id: $world_id})
            CREATE (c)-[:PLAYS_IN]->(w)
            """,
            profile_id=str(profile_id),
            member_id=str(member_id),
            world_id=str(world_id)
        )

# 3. Store character-specific data in DocumentDB
async def create_character_documentdb(profile_id: uuid.UUID):
    await db.character_world_knowledge.insert_one({
        "_id": str(profile_id),
        "profile_id": str(profile_id),
        "discovered_locations": [],
        "known_npcs": [],
        "world_lore_discovered": [],
        "conversation_history": []
    })
```

### GraphQL Schema Design

**Complete Schema Example:**

```graphql
# schema.graphql

# ============================================
# Scalars
# ============================================

scalar UUID
scalar DateTime
scalar JSON

# ============================================
# Account Types
# ============================================

enum AccountType {
  INDIVIDUAL
  FAMILY
  EDUCATIONAL
  ORGANIZATIONAL
}

enum SubscriptionStatus {
  ACTIVE
  PAST_DUE
  CANCELLED
  SUSPENDED
}

type Account {
  accountId: UUID!
  accountType: AccountType!
  subscriptionTier: String!
  subscriptionStatus: SubscriptionStatus!
  maxMembers: Int!
  currentMemberCount: Int!
  members: [Member!]!
  createdAt: DateTime!
}

# ============================================
# Member Types
# ============================================

enum MemberRole {
  OWNER
  PARENT
  TEEN
  CHILD
  STUDENT
  EMPLOYEE
}

type Member {
  memberId: UUID!
  accountId: UUID!
  displayName: String!
  email: String
  dateOfBirth: DateTime!
  age: Int!
  role: MemberRole!
  canManageAccount: Boolean!
  parentalControls: ParentalControls
  cognitiveProgress: CognitiveProgress!
  characters: [PlayerProfile!]!
}

type ParentalControls {
  dailyTimeLimitMinutes: Int
  quietHoursStart: String
  quietHoursEnd: String
  allowedUniverses: [UUID!]
  canPlayWithStrangers: Boolean!
}

type CognitiveProgress {
  memberId: UUID!
  rememberMastered: Boolean!
  understandMastered: Boolean!
  applyMastered: Boolean!
  analyzeProgress: Float!
  evaluateProgress: Float!
  createProgress: Float!
  empathyLevel: Int!
  strategyLevel: Int!
  creativityLevel: Int!
  courageLevel: Int!
}

# ============================================
# Character Types
# ============================================

type PlayerProfile {
  profileId: UUID!
  memberId: UUID!
  characterName: String!
  universe: Universe!
  world: World!
  archetype: String!
  appearanceData: JSON
  portraitUrl: String
  totalPlaytimeMinutes: Int!
  campaigns: [Campaign!]!
  relationships: [CharacterRelationship!]!
  createdAt: DateTime!
  lastPlayedAt: DateTime
}

type CharacterRelationship {
  targetId: UUID!
  targetName: String!
  targetType: String!  # NPC, Faction, etc.
  relationshipType: String!
  trustLevel: Int
}

# ============================================
# Universe/World Types
# ============================================

enum UniverseType {
  CONTENT_RATING
  AGE_FOCUSED
  GAMEPLAY_STYLE
  CONTEXT_BASED
}

type Universe {
  universeId: UUID!
  universeName: String!
  universeType: UniverseType!
  purpose: String!
  description: String!
  targetAgeMin: Int
  targetAgeMax: Int
  maxContentRating: String!
  features: JSON!
  worlds: [World!]!
  isAccessibleByMember(memberId: UUID!): Boolean!
}

type World {
  worldId: UUID!
  worldName: String!
  genre: String!
  baseContentRating: String!
  themes: [String!]!
  visualStyle: String!
  description: String!
  availableInUniverses: [Universe!]!
  archetypes: [Archetype!]!
  startingLocations: [Location!]!
}

type Archetype {
  archetypeId: String!
  name: String!
  description: String!
  startingSkills: JSON!
  portraitPrompt: String!
}

type Location {
  locationId: UUID!
  name: String!
  description: String!
  imageUrl: String
}

# ============================================
# Campaign Types
# ============================================

enum CampaignType {
  SOLO
  MULTIPLAYER_COOP
  FAMILY
  COMPETITIVE
}

type Campaign {
  campaignId: UUID!
  campaignName: String!
  universe: Universe!
  world: World!
  campaignType: CampaignType!
  maxPlayers: Int!
  currentPlayerCount: Int!
  participants: [CampaignParticipant!]!
  currentChapter: Int!
  progress: Float!
  lastSessionAt: DateTime
  createdAt: DateTime!
}

type CampaignParticipant {
  character: PlayerProfile!
  member: Member!
  role: String!
  sessionsParticipated: Int!
  joinedAt: DateTime!
}

# ============================================
# Narrative Types
# ============================================

type NarrativeEvent {
  eventId: UUID!
  campaignId: UUID!
  characterId: UUID!
  eventType: String!
  content: String!
  imageUrl: String
  choices: [NarrativeChoice!]
  timestamp: DateTime!
}

type NarrativeChoice {
  choiceId: String!
  text: String!
  bloomLevel: String!
  skillsRequired: [String!]
}

# ============================================
# Queries
# ============================================

type Query {
  # Account queries
  me: Member!
  myAccount: Account!
  
  # Character queries
  myCharacters: [PlayerProfile!]!
  character(profileId: UUID!): PlayerProfile
  
  # Universe/World queries
  universes(
    type: UniverseType
    ageRange: [Int!]
    search: String
  ): [Universe!]!
  
  universe(universeId: UUID!): Universe
  
  worldsInUniverse(
    universeId: UUID!
    genre: String
    search: String
  ): [World!]!
  
  world(worldId: UUID!, universeId: UUID): World
  
  # Campaign queries
  myCampaigns: [Campaign!]!
  campaign(campaignId: UUID!): Campaign
  
  campaignsForCharacter(profileId: UUID!): [Campaign!]!
  
  # Family queries
  familyMembers: [Member!]!
  childActivity(memberId: UUID!, dateRange: [DateTime!]): ActivityReport!
  
  # Educational queries (teachers only)
  myStudents: [Member!]!
  studentProgress(memberId: UUID!): EducationalProgress!
}

# ============================================
# Mutations
# ============================================

type Mutation {
  # Account mutations
  createAccount(input: CreateAccountInput!): Account!
  updateSubscription(tier: String!): Account!
  
  # Member mutations
  addFamilyMember(input: AddMemberInput!): Member!
  updateParentalControls(memberId: UUID!, input: ParentalControlsInput!): Member!
  
  # Character mutations
  createCharacter(input: CreateCharacterInput!): PlayerProfile!
  deleteCharacter(profileId: UUID!): Boolean!
  
  # Campaign mutations
  startCampaign(input: StartCampaignInput!): Campaign!
  joinCampaign(campaignId: UUID!, profileId: UUID!): Campaign!
  leaveCampaign(campaignId: UUID!, profileId: UUID!): Boolean!
  
  # Gameplay mutations
  submitPlayerAction(
    campaignId: UUID!
    profileId: UUID!
    action: PlayerActionInput!
  ): NarrativeEvent!
  
  makeChoice(
    eventId: UUID!
    choiceId: String!
  ): NarrativeEvent!
}

# ============================================
# Subscriptions
# ============================================

type Subscription {
  # Real-time narrative updates
  narrativeUpdate(campaignId: UUID!): NarrativeEvent!
  
  # Character updates
  characterUpdate(profileId: UUID!): PlayerProfile!
  
  # Campaign events
  campaignEvent(campaignId: UUID!): CampaignEvent!
  
  # Parental monitoring
  childActivityAlert(memberId: UUID!): ActivityAlert!
}

type CampaignEvent {
  eventType: String!
  campaignId: UUID!
  data: JSON!
  timestamp: DateTime!
}

type ActivityAlert {
  alertType: String!
  memberId: UUID!
  message: String!
  timestamp: DateTime!
}

# ============================================
# Input Types
# ============================================

input CreateAccountInput {
  accountType: AccountType!
  ownerName: String!
  ownerEmail: String!
  ownerDateOfBirth: DateTime!
  password: String!
  subscriptionTier: String!
}

input AddMemberInput {
  displayName: String!
  email: String
  dateOfBirth: DateTime!
  role: MemberRole!
  parentalControls: ParentalControlsInput
}

input ParentalControlsInput {
  dailyTimeLimitMinutes: Int
  quietHoursStart: String
  quietHoursEnd: String
  allowedUniverses: [UUID!]
  canPlayWithStrangers: Boolean
}

input CreateCharacterInput {
  characterName: String!
  universeId: UUID!
  worldId: UUID!
  archetype: String!
  appearanceData: JSON
}

input StartCampaignInput {
  campaignName: String!
  universeId: UUID!
  worldId: UUID!
  campaignType: CampaignType!
  profileId: UUID!
}

input PlayerActionInput {
  actionType: String!
  text: String
  choiceId: String
  metadata: JSON
}

type ActivityReport {
  memberId: UUID!
  totalPlaytimeMinutes: Int!
  sessionsCount: Int!
  cognitiveGrowth: CognitiveGrowth!
  campaignsPlayed: [Campaign!]!
}

type CognitiveGrowth {
  empathyDelta: Int!
  strategyDelta: Int!
  creativityDelta: Int!
}

type EducationalProgress {
  memberId: UUID!
  bloomTier: String!
  learningObjectivesMet: [String!]!
  standardsAlignment: JSON!
  recentAssessments: [Assessment!]!
}

type Assessment {
  assessmentId: UUID!
  challengeId: UUID!
  bloomLevel: String!
  skillsDemonstrated: [String!]!
  feedback: String!
  timestamp: DateTime!
}
```

**Strawberry GraphQL Implementation:**

```python
# api-gateway/schema.py

import strawberry
from strawberry.types import Info
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# Import your service clients
from services.account_service import AccountServiceClient
from services.character_service import CharacterServiceClient
from services.campaign_service import CampaignServiceClient

# ============================================
# Types
# ============================================

@strawberry.enum
class AccountType:
    INDIVIDUAL = "individual"
    FAMILY = "family"
    EDUCATIONAL = "educational"
    ORGANIZATIONAL = "organizational"

@strawberry.type
class Account:
    account_id: UUID
    account_type: AccountType
    subscription_tier: str
    subscription_status: str
    max_members: int
    current_member_count: int
    created_at: datetime
    
    @strawberry.field
    async def members(self, info: Info) -> List["Member"]:
        # Call member service
        return await info.context.member_service.get_members(self.account_id)

@strawberry.type
class Member:
    member_id: UUID
    account_id: UUID
    display_name: str
    email: Optional[str]
    date_of_birth: datetime
    age: int
    role: str
    
    @strawberry.field
    async def characters(self, info: Info) -> List["PlayerProfile"]:
        return await info.context.character_service.get_characters(self.member_id)
    
    @strawberry.field
    async def cognitive_progress(self, info: Info) -> "CognitiveProgress":
        return await info.context.player_dev_service.get_progress(self.member_id)

@strawberry.type
class PlayerProfile:
    profile_id: UUID
    member_id: UUID
    character_name: str
    universe_id: UUID
    world_id: UUID
    archetype: str
    portrait_url: Optional[str]
    total_playtime_minutes: int
    created_at: datetime
    
    @strawberry.field
    async def universe(self, info: Info) -> "Universe":
        return await info.context.universe_service.get_universe(self.universe_id)
    
    @strawberry.field
    async def world(self, info: Info) -> "World":
        return await info.context.world_service.get_world(self.world_id)
    
    @strawberry.field
    async def campaigns(self, info: Info) -> List["Campaign"]:
        return await info.context.campaign_service.get_campaigns_for_character(
            self.profile_id
        )

# ... more types ...

# ============================================
# Queries
# ============================================

@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> Member:
        """Get current authenticated member"""
        member_id = info.context.current_user.member_id
        return await info.context.member_service.get_member(member_id)
    
    @strawberry.field
    async def my_characters(self, info: Info) -> List[PlayerProfile]:
        """Get all characters for current member"""
        member_id = info.context.current_user.member_id
        return await info.context.character_service.get_characters(member_id)
    
    @strawberry.field
    async def universes(
        self,
        info: Info,
        type: Optional[str] = None,
        age_range: Optional[List[int]] = None,
        search: Optional[str] = None
    ) -> List["Universe"]:
        """Browse available universes"""
        return await info.context.universe_service.list_universes(
            universe_type=type,
            age_range=age_range,
            search=search
        )
    
    @strawberry.field
    async def worlds_in_universe(
        self,
        info: Info,
        universe_id: UUID,
        genre: Optional[str] = None,
        search: Optional[str] = None
    ) -> List["World"]:
        """Get worlds available in a specific universe"""
        return await info.context.world_service.list_worlds(
            universe_id=universe_id,
            genre=genre,
            search=search
        )

# ============================================
# Mutations
# ============================================

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_character(
        self,
        info: Info,
        input: "CreateCharacterInput"
    ) -> PlayerProfile:
        """Create a new character"""
        member_id = info.context.current_user.member_id
        
        # Call character service
        character = await info.context.character_service.create_character(
            member_id=member_id,
            character_name=input.character_name,
            universe_id=input.universe_id,
            world_id=input.world_id,
            archetype=input.archetype
        )
        
        return character
    
    @strawberry.mutation
    async def start_campaign(
        self,
        info: Info,
        input: "StartCampaignInput"
    ) -> "Campaign":
        """Start a new campaign"""
        # Verify character belongs to current member
        member_id = info.context.current_user.member_id
        character = await info.context.character_service.get_character(
            input.profile_id
        )
        
        if character.member_id != member_id:
            raise Exception("Character does not belong to you")
        
        # Call AI Game Master Agent via orchestrator
        campaign = await info.context.agent_orchestrator.start_campaign(
            profile_id=input.profile_id,
            universe_id=input.universe_id,
            world_id=input.world_id,
            campaign_name=input.campaign_name
        )
        
        return campaign
    
    @strawberry.mutation
    async def submit_player_action(
        self,
        info: Info,
        campaign_id: UUID,
        profile_id: UUID,
        action: "PlayerActionInput"
    ) -> "NarrativeEvent":
        """Submit player action and get AI response"""
        
        # Verify character belongs to current member
        member_id = info.context.current_user.member_id
        character = await info.context.character_service.get_character(profile_id)
        
        if character.member_id != member_id:
            raise Exception("Character does not belong to you")
        
        # Call AI Game Master Agent
        narrative_event = await info.context.agent_orchestrator.process_action(
            campaign_id=campaign_id,
            profile_id=profile_id,
            action_type=action.action_type,
            action_text=action.text,
            metadata=action.metadata
        )
        
        return narrative_event

# ============================================
# Subscriptions
# ============================================

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def narrative_update(
        self,
        info: Info,
        campaign_id: UUID
    ) -> "NarrativeEvent":
        """Real-time narrative updates for a campaign"""
        
        # Subscribe to Redis pub/sub or WebSocket channel
        async for event in info.context.pubsub.subscribe(f"campaign:{campaign_id}"):
            yield event
    
    @strawberry.subscription
    async def character_update(
        self,
        info: Info,
        profile_id: UUID
    ) -> PlayerProfile:
        """Real-time character updates"""
        async for update in info.context.pubsub.subscribe(f"character:{profile_id}"):
            yield update

# ============================================
# Schema
# ============================================

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)
```

**Context and Authentication:**

```python
# api-gateway/context.py

from dataclasses import dataclass
from typing import Optional
import jwt
from fastapi import HTTPException, status

@dataclass
class CurrentUser:
    member_id: UUID
    account_id: UUID
    role: str
    permissions: List[str]

@dataclass
class Context:
    current_user: Optional[CurrentUser]
    
    # Service clients
    account_service: AccountServiceClient
    member_service: MemberServiceClient
    character_service: CharacterServiceClient
    universe_service: UniverseServiceClient
    world_service: WorldServiceClient
    campaign_service: CampaignServiceClient
    player_dev_service: PlayerDevelopmentServiceClient
    
    # AI Agent orchestrator
    agent_orchestrator: AgentOrchestratorClient
    
    # Pub/sub for subscriptions
    pubsub: PubSubClient

async def get_context(request) -> Context:
    # Extract JWT token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not token:
        current_user = None
    else:
        try:
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET, 
                algorithms=["HS256"]
            )
            current_user = CurrentUser(
                member_id=UUID(payload["member_id"]),
                account_id=UUID(payload["account_id"]),
                role=payload["role"],
                permissions=payload.get("permissions", [])
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    
    # Initialize service clients
    return Context(
        current_user=current_user,
        account_service=AccountServiceClient(),
        member_service=MemberServiceClient(),
        character_service=CharacterServiceClient(),
        universe_service=UniverseServiceClient(),
        world_service=WorldServiceClient(),
        campaign_service=CampaignServiceClient(),
        player_dev_service=PlayerDevelopmentServiceClient(),
        agent_orchestrator=AgentOrchestratorClient(),
        pubsub=PubSubClient()
    )
```

**FastAPI Integration:**

```python
# api-gateway/main.py

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from context import get_context
from schema import schema

app = FastAPI(title="SkillForge GraphQL API")

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context
)

app.include_router(graphql_app, prefix="/graphql")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Next Steps for Implementation

### Phase 1: Foundation (Week 1-2)
1. Set up Docker Compose with all databases
2. Create base Django web app with GraphQL
3. Implement Account and Member services with PostgreSQL + Neo4j
4. Create initial database migrations
5. Set up RabbitMQ event bus

### Phase 2: MCP Infrastructure (Week 3-4)
1. Build Player Data MCP Server
2. Build World/Universe MCP Server
3. Implement MCP authentication
4. Test MCP endpoints

### Phase 3: First AI Agent (Week 5-8)
1. Implement Agent Orchestrator
2. Build AI Game Master Agent with LangGraph
3. Integrate Claude API
4. Connect to MCP servers
5. Test with simple narrative generation

### Phase 4: Complete Services (Week 9-12)
1. Build remaining microservices
2. Implement all GraphQL resolvers
3. Add WebSocket subscriptions
4. Build Flutter mobile app
5. End-to-end testing

This provides a complete, production-ready development plan. Start with Phase 1 and work systematically through each phase.