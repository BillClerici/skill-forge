# SkillForge RPG - AI-Powered Educational Platform

A hybrid AI-powered educational RPG platform featuring multi-account systems, multi-character gameplay, and AI-driven narrative generation.

## Architecture Overview

- **Multi-Account System**: Individual, Family, Educational, and Organizational accounts
- **Multi-Character Gameplay**: Up to 10 characters per member
- **Universe/World System**: Categorical Universes containing genre-based Worlds
- **AI Agent-Driven**: Narrative generation and assessment
- **Microservices Architecture**: Traditional services + AI Agents + MCP servers
- **Docker-First**: All components containerized for local development

## Technology Stack

### Data Layer
- **PostgreSQL 16**: Relational data (accounts, members, profiles, subscriptions) with UUID primary keys
- **Neo4j 5.13**: Graph database (relationships, skill trees, campaign graphs)
- **MongoDB 7.0**: Universe definitions, event sourcing, AI conversation history
- **Redis 7.2**: Caching, sessions, rate limiting
- **RabbitMQ 3.12**: Event bus with topic exchanges

### Backend
- **Python 3.11+**: FastAPI microservices
- **Strawberry GraphQL**: Unified API endpoint
- **SQLAlchemy 2.0+**: ORM with async support
- **Pydantic 2.x**: Data validation

### AI Infrastructure (Future Phases)
- **LangGraph**: Agent orchestration
- **Claude API**: Primary LLM
- **MCP Servers**: Context provision for AI agents

## Quick Start

### Prerequisites
- Docker Desktop
- Git

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/skill-forge.git
   cd skill-forge
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your passwords and secrets
   ```

3. **Start the infrastructure**
   ```bash
   # Start databases only
   docker-compose up -d postgres neo4j mongodb redis rabbitmq

   # Wait for PostgreSQL to be ready
   docker-compose logs -f postgres
   ```

4. **Run database migrations**
   ```bash
   # Run PostgreSQL migrations
   docker-compose exec postgres psql -U skillforge_user -d skillforge -f /migrations/001_initial_schema.sql
   ```

5. **Start the services**
   ```bash
   # Start all services
   docker-compose up -d

   # View logs
   docker-compose logs -f
   ```

6. **Access the services**
   - GraphQL API: http://localhost:8000/graphql
   - Neo4j Browser: http://localhost:7474
   - RabbitMQ Management: http://localhost:15672 (user: skillforge, password: from .env)

## Project Structure

```
skill-forge/
├── docker-compose.yml          # Container orchestration
├── .env.example                # Environment template
├── docs/                       # Documentation
│   ├── requirements/           # Requirements specifications
│   └── setup/                  # Setup instructions
├── migrations/                 # Database migrations
│   └── 001_initial_schema.sql # Initial PostgreSQL schema
├── services/                   # Microservices
│   ├── api-gateway/           # GraphQL gateway
│   ├── account-service/       # Account CRUD
│   └── member-service/        # Member & family management
└── shared/                     # Shared code
    ├── models/                # Pydantic models
    └── utils/                 # Utilities
```

## Development Workflow

### Start development environment
```bash
docker-compose up -d
```

### View service logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway
```

### Rebuild a service
```bash
docker-compose up -d --build account-service
```

### Stop all services
```bash
docker-compose down
```

### Reset databases (WARNING: Deletes all data)
```bash
docker-compose down -v
docker-compose up -d
```

## Development Phases

### Phase 1: Foundation (Current - Weeks 1-2)
- ✅ Docker Compose setup with all databases
- ✅ PostgreSQL schema with UUID primary keys
- ✅ Account and Member services
- 🔄 GraphQL API Gateway
- 🔄 RabbitMQ event bus

### Phase 2: MCP Infrastructure (Weeks 3-4)
- Player Data MCP Server
- World/Universe MCP Server
- MCP authentication

### Phase 3: First AI Agent (Weeks 5-8)
- Agent Orchestrator
- AI Game Master Agent
- Claude API integration
- MCP integration

### Phase 4: Complete Services (Weeks 9-12)
- Remaining microservices
- GraphQL resolvers
- WebSocket subscriptions
- End-to-end testing

## Key Principles

1. **UUID Primary Keys**: All models use UUIDs, not integers
2. **Neo4j-First for Relationships**: Maximize graph database usage
3. **GraphQL API**: Single unified endpoint
4. **Event-Driven**: RabbitMQ for inter-service communication
5. **Docker-First**: All components in containers

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[License information]

## Support

For questions or issues, please open a GitHub issue.