# Campaign Deletion Service Architecture

## Overview
Microservice for orchestrated campaign deletion across MongoDB, Neo4j, and PostgreSQL using LangGraph workflows, MCP tools, and RabbitMQ event-driven architecture.

## Architecture Components

### 1. **Campaign Deletion Service** (New Microservice)
- **Technology**: Python FastAPI + LangGraph
- **Purpose**: Orchestrate comprehensive campaign deletion
- **Port**: 8004
- **Docker**: `campaign-deletion-service` container

### 2. **LangGraph Workflow** (`deletion_workflow.py`)
Orchestrates multi-step deletion process:

```
┌─────────────────────────────────────────────────────────┐
│                  Deletion Workflow                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. validate_campaign_node                              │
│     └─> Check campaign exists in MongoDB               │
│                                                          │
│  2. collect_entity_ids_node                            │
│     └─> Gather all related entity IDs                  │
│         (quests, places, scenes, NPCs, etc.)           │
│                                                          │
│  3. delete_mongodb_node                                │
│     └─> Cascading deletion from MongoDB                │
│         (via MongoDB MCP tool)                          │
│                                                          │
│  4. delete_neo4j_node                                  │
│     └─> Graph deletion from Neo4j                      │
│         (via Neo4j MCP tool)                            │
│                                                          │
│  5. delete_postgres_node                               │
│     └─> Remove player associations                     │
│         (via PostgreSQL MCP tool)                       │
│                                                          │
│  6. publish_completion_node                            │
│     └─> Publish completion event to RabbitMQ           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3. **MCP (Model Context Protocol) Tools**
Reusable tools for database operations:

#### MongoDB MCP Tool (`mcp_mongodb.py`)
```python
@mcp_tool
async def delete_campaign_cascade(campaign_id: str) -> dict:
    """Delete campaign and all related entities from MongoDB"""
    # Returns: {deleted_counts: {...}, entity_ids: {...}}
```

#### Neo4j MCP Tool (`mcp_neo4j.py`)
```python
@mcp_tool
async def delete_campaign_graph(entity_ids: dict) -> dict:
    """Delete nodes and relationships from Neo4j graph"""
    # Returns: {deleted_counts: {...}}
```

#### PostgreSQL MCP Tool (`mcp_postgres.py`)
```python
@mcp_tool
async def delete_player_associations(campaign_id: str) -> dict:
    """Remove player-campaign associations"""
    # Returns: {deleted_count: int}
```

### 4. **RabbitMQ Event Flow**

```
┌──────────────┐
│ Django UI    │
│ (User clicks │
│  Delete btn) │
└──────┬───────┘
       │
       │ POST /campaigns/{id}/delete/
       ↓
┌──────────────────┐
│ Django Backend   │
│                  │
│ Publishes:       │
│ ├─ Exchange:     │
│ │  campaign.ops  │
│ │                │
│ └─ Routing Key:  │
│    campaign.     │
│    delete.       │
│    requested     │
└──────┬───────────┘
       │
       │ RabbitMQ Message:
       │ {
       │   "campaign_id": "...",
       │   "request_id": "...",
       │   "user_id": "...",
       │   "timestamp": "..."
       │ }
       ↓
┌────────────────────────┐
│ Campaign Deletion Svc  │
│                        │
│ Consumes:              │
│ ├─ Queue:              │
│ │  campaign.deletion   │
│ │                      │
│ ├─ Binding:            │
│ │  campaign.delete.*   │
│ │                      │
│ └─ Handler:            │
│    process_deletion()  │
│    └─> Invokes        │
│        LangGraph       │
│        workflow        │
└────────┬───────────────┘
         │
         │ Throughout execution:
         │ Publishes progress updates
         ↓
┌────────────────────────┐
│ RabbitMQ Progress      │
│                        │
│ Exchange:              │
│ ├─ campaign.progress   │
│ │                      │
│ Routing Keys:          │
│ ├─ deletion.validated  │
│ ├─ deletion.mongodb    │
│ ├─ deletion.neo4j      │
│ ├─ deletion.postgres   │
│ ├─ deletion.completed  │
│ └─ deletion.failed     │
└────────┬───────────────┘
         │
         │ Frontend listens via WebSocket
         ↓
┌────────────────────────┐
│ UI Progress Display    │
│                        │
│ Shows real-time:       │
│ ├─ Current step        │
│ ├─ Progress %          │
│ ├─ Deleted counts      │
│ └─ Completion status   │
└────────────────────────┘
```

### 5. **Redis State Management**
Track deletion progress and state:

```python
# State stored in Redis
deletion:state:{request_id} = {
    "campaign_id": "...",
    "status": "in_progress|completed|failed",
    "current_step": "mongodb|neo4j|postgres",
    "progress_percentage": 60,
    "deleted_counts": {
        "mongodb": {...},
        "neo4j": {...},
        "postgres": {...}
    },
    "errors": [],
    "started_at": "...",
    "completed_at": "..."
}
```

### 6. **API Endpoints**

#### Campaign Deletion Service (`/api/v1/delete`)
```
POST /api/v1/delete/campaign/{campaign_id}
- Initiates deletion workflow
- Returns request_id for tracking

GET /api/v1/delete/status/{request_id}
- Get deletion progress
- Returns current state from Redis

DELETE /api/v1/delete/cancel/{request_id}
- Cancel in-progress deletion (if possible)
```

#### Django Integration
```
POST /campaigns/{campaign_id}/delete/
- Publishes deletion request to RabbitMQ
- Redirects to progress page

GET /campaigns/deletion/{request_id}/status/
- Shows deletion progress page
- Connects to WebSocket for real-time updates
```

### 7. **Workflow State Management**

```python
class DeletionState(TypedDict):
    """LangGraph workflow state"""
    # Input
    campaign_id: str
    request_id: str
    user_id: str

    # Collected data
    campaign_name: str
    is_new_format: bool
    entity_ids: Dict[str, List[str]]  # quests, places, scenes, npcs, etc.

    # Deletion results
    mongodb_deleted: bool
    mongodb_counts: Dict[str, int]

    neo4j_deleted: bool
    neo4j_counts: Dict[str, int]

    postgres_deleted: bool
    postgres_count: int

    # Progress tracking
    current_phase: str
    progress_percentage: int
    status_message: str

    # Error handling
    errors: List[str]
    warnings: List[str]

    # Audit
    audit_trail: List[Dict]
    started_at: str
    completed_at: str
```

## Data Flow Example

### Happy Path: Successful Deletion
```
1. User clicks "Delete Campaign" in UI
   └─> Django POST /campaigns/{id}/delete/

2. Django publishes RabbitMQ message
   └─> campaign.ops exchange
       └─> routing key: campaign.delete.requested

3. Deletion Service receives message
   └─> Creates workflow instance
       └─> Initializes state with request_id

4. validate_campaign_node
   └─> Checks MongoDB for campaign
       └─> Updates Redis: status="validating"
           └─> Publishes: deletion.validated

5. collect_entity_ids_node
   └─> Queries MongoDB for all related IDs
       └─> Updates Redis: entity_ids={...}
           └─> Publishes: deletion.collecting

6. delete_mongodb_node
   └─> Calls MongoDB MCP tool
       └─> Cascading deletion
           └─> Updates Redis: mongodb_deleted=true
               └─> Publishes: deletion.mongodb (progress=33%)

7. delete_neo4j_node
   └─> Calls Neo4j MCP tool
       └─> Graph deletion
           └─> Updates Redis: neo4j_deleted=true
               └─> Publishes: deletion.neo4j (progress=66%)

8. delete_postgres_node
   └─> Calls PostgreSQL MCP tool
       └─> Association deletion
           └─> Updates Redis: postgres_deleted=true
               └─> Publishes: deletion.postgres (progress=90%)

9. publish_completion_node
   └─> Finalizes audit trail
       └─> Updates Redis: status="completed"
           └─> Publishes: deletion.completed (progress=100%)

10. UI receives completion event
    └─> Shows success message
        └─> Redirects to campaign list
```

## Error Handling

### Retry Logic
- Each node has 3 retry attempts
- Exponential backoff: 1s, 2s, 4s
- If all retries fail → mark as failed

### Rollback Strategy
- MongoDB: Not rolled back (data already deleted)
- Neo4j: Orphan cleanup runs separately
- PostgreSQL: Non-critical, warnings only

### Failure Recovery
```python
if state['mongodb_deleted'] and not state['neo4j_deleted']:
    # MongoDB deleted but Neo4j failed
    # Mark for manual cleanup
    state['warnings'].append('Neo4j deletion failed - orphan cleanup required')
    # Continue to completion with warning
```

## Monitoring & Observability

### Metrics
- Deletion request rate
- Average deletion time
- Success/failure rate
- Database-specific deletion times

### Logging
- Structured JSON logs
- Request ID tracing
- Audit trail persisted to MongoDB

### Health Checks
```
GET /health
- Service health
- Database connections
- RabbitMQ connection
```

## Deployment

### Docker Compose
```yaml
campaign-deletion-service:
  build: ./services/campaign-deletion-service
  ports:
    - "8004:8000"
  environment:
    - MONGODB_URL=mongodb://admin:mongo_dev_pass_2024@mongodb:27017
    - NEO4J_URL=bolt://neo4j:7687
    - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    - REDIS_URL=redis://redis:6379
  depends_on:
    - mongodb
    - neo4j
    - rabbitmq
    - redis
```

## Benefits of This Architecture

1. **Decoupled** - Django doesn't directly delete, just publishes events
2. **Scalable** - Multiple deletion workers can consume queue
3. **Observable** - Real-time progress updates via WebSocket
4. **Reliable** - Retry logic and error handling
5. **Traceable** - Full audit trail and logging
6. **Reusable** - MCP tools can be used by other services
7. **Testable** - Each component can be tested independently

## Next Steps

1. ✅ Create campaign-deletion-service skeleton
2. Implement LangGraph workflow
3. Create MCP tools for each database
4. Set up RabbitMQ message handling
5. Add Redis state management
6. Update Django to publish deletion requests
7. Create progress UI with WebSocket
8. Add comprehensive tests
9. Deploy and monitor
