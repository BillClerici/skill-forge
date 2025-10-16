# Campaign Wizard V2 - Implementation Status

## ✅ Completed Implementations

### Frontend (UI)
1. **✅ campaign_designer_wizard_v2.html** - Complete 11-step wizard with:
   - Universe selection
   - World selection (shows genre)
   - Region selection
   - Story idea input (optional)
   - Story selection (3 AI-generated ideas)
   - Campaign core review
   - Quest settings (difficulty, playtime, quest count)
   - Quest review
   - Place review
   - Scene review
   - Final review

2. **✅ campaign_wizard_v2.js** - Complete JavaScript with:
   - Step navigation and validation
   - API calls to backend endpoints
   - Polling for async workflow progress
   - Story idea generation and selection
   - Campaign core display
   - Quest/Place/Scene review displays
   - Bloom's Taxonomy tag display
   - Backstory toggle functionality
   - Loading overlay with phase tracking
   - Knowledge & Items display

### Features Implemented in UI
- ✅ Universe selection as first step
- ✅ Optional story idea input
- ✅ 3 AI-generated story ideas display
- ✅ Story regeneration
- ✅ Campaign core review (Plot, Storyline, Objectives)
- ✅ Bloom's Taxonomy display throughout
- ✅ Quest settings (count, difficulty, playtime)
- ✅ Quest/Place/Scene review gates
- ✅ Backstory display (expandable)
- ✅ New location tracking display
- ✅ Knowledge & Items display in scenes
- ✅ Enhanced progress tracking with phases
- ✅ Image generation options

---

## ⏳ Remaining Backend Implementation

### Phase 2.1: Django View Endpoints (CRITICAL)

**File to create:** `services/django-web/campaigns/wizard_views_v2.py`

```python
"""
Campaign Wizard V2 Views
Complete endpoint implementation for 22-step workflow
"""
import os
import json
import uuid
import httpx
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from pymongo import MongoClient

# MongoDB connection
mongo_client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://localhost:27017/'))
mongo_db = mongo_client.skillforge

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv('ORCHESTRATOR_URL', 'http://localhost:9000')


@login_required
def campaign_wizard_v2(request):
    """Main wizard view - Step 1: Universe selection"""
    # Fetch universes from MongoDB
    universes = list(mongo_db.universes.find({}))

    context = {
        'universes': universes
    }

    return render(request, 'campaigns/campaign_designer_wizard_v2.html', context)


@login_required
@require_http_methods(["GET"])
def get_worlds_for_universe_api(request, universe_id):
    """AJAX: Get worlds for a universe"""
    worlds = list(mongo_db.world_definitions.find({'universe_id': universe_id}))

    # Add primary_image_url to each world
    for world in worlds:
        world['_id'] = str(world['_id'])
        world['primary_image_url'] = None
        if world.get('world_images') and world.get('primary_image_index') is not None:
            images = world.get('world_images', [])
            primary_idx = world.get('primary_image_index')
            if 0 <= primary_idx < len(images):
                world['primary_image_url'] = images[primary_idx].get('url')

    return JsonResponse({'worlds': worlds})


@login_required
@require_http_methods(["GET"])
def get_regions_for_world_api(request, world_id):
    """AJAX: Get regions for a world"""
    regions = list(mongo_db.region_definitions.find({'world_id': world_id}))

    for region in regions:
        region['_id'] = str(region['_id'])

    return JsonResponse({'regions': regions})


@login_required
@require_http_methods(["POST"])
def generate_stories_api(request):
    """AJAX: Generate 3 story ideas"""
    try:
        data = json.loads(request.body)
        request_id = str(uuid.uuid4())

        # Call orchestrator
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/start",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id),
                    'character_id': data.get('character_id'),
                    'universe_id': data['universe_id'],
                    'universe_name': data.get('universe_name'),
                    'world_id': data['world_id'],
                    'world_name': data.get('world_name'),
                    'region_id': data.get('region_id'),
                    'region_name': data.get('region_name'),
                    'genre': data.get('genre'),
                    'user_story_idea': data.get('user_story_idea', '')
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to start workflow'}, status=500)

        return JsonResponse({'request_id': request_id, 'status': 'generating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def regenerate_stories_api(request):
    """AJAX: Regenerate story ideas"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/regenerate-stories",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to regenerate stories'}, status=500)

        return JsonResponse({'status': 'regenerating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def generate_core_api(request):
    """AJAX: Generate campaign core"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')
        selected_story_id = data.get('selected_story_id')

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/select-story",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id),
                    'selected_story_id': selected_story_id
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to generate core'}, status=500)

        return JsonResponse({'status': 'generating'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def approve_core_api(request):
    """AJAX: Approve campaign core and start quest generation"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-core",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id),
                    'user_approved_core': True,
                    'num_quests': data.get('num_quests', 5),
                    'quest_difficulty': data.get('quest_difficulty', 'Medium'),
                    'quest_playtime_minutes': data.get('quest_playtime_minutes', 90),
                    'generate_images': data.get('generate_images', True)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve core'}, status=500)

        return JsonResponse({'status': 'generating_quests'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def approve_quests_api(request):
    """AJAX: Approve quests and start place generation"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-quests",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve quests'}, status=500)

        return JsonResponse({'status': 'generating_places'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def approve_places_api(request):
    """AJAX: Approve places and start scene generation"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/approve-places",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to approve places'}, status=500)

        return JsonResponse({'status': 'generating_scenes'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_workflow_status_api(request, request_id):
    """AJAX: Get campaign workflow status"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{ORCHESTRATOR_URL}/campaign-wizard/status/{request_id}"
            )

            if response.status_code == 404:
                return JsonResponse({'error': 'Request not found'}, status=404)

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to get status'}, status=500)

            return JsonResponse(response.json())

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def finalize_campaign_api(request):
    """AJAX: Finalize campaign"""
    try:
        data = json.loads(request.body)
        request_id = data.get('request_id')

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{ORCHESTRATOR_URL}/campaign-wizard/finalize",
                json={
                    'request_id': request_id,
                    'user_id': str(request.user.id)
                }
            )

            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to finalize'}, status=500)

            result = response.json()
            return JsonResponse({
                'status': 'completed',
                'campaign_id': result.get('campaign_id')
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

### Phase 2.2: Update URL Configuration

**File:** `services/django-web/skillforge/urls.py`

Add to urlpatterns:
```python
# Campaign Wizard V2
path('campaigns/wizard/v2/', wizard_views_v2.campaign_wizard_v2, name='campaign_wizard_v2'),
path('campaigns/wizard/api/worlds/<str:universe_id>', wizard_views_v2.get_worlds_for_universe_api, name='get_worlds_for_universe_api'),
path('campaigns/wizard/api/regions/<str:world_id>', wizard_views_v2.get_regions_for_world_api, name='get_regions_for_world_api'),
path('campaigns/wizard/api/generate-stories', wizard_views_v2.generate_stories_api, name='generate_stories_api'),
path('campaigns/wizard/api/regenerate-stories', wizard_views_v2.regenerate_stories_api, name='regenerate_stories_api'),
path('campaigns/wizard/api/generate-core', wizard_views_v2.generate_core_api, name='generate_core_api'),
path('campaigns/wizard/api/approve-core', wizard_views_v2.approve_core_api, name='approve_core_api'),
path('campaigns/wizard/api/approve-quests', wizard_views_v2.approve_quests_api, name='approve_quests_api'),
path('campaigns/wizard/api/approve-places', wizard_views_v2.approve_places_api, name='approve_places_api'),
path('campaigns/wizard/api/status/<str:request_id>', wizard_views_v2.get_workflow_status_api, name='get_workflow_status_api'),
path('campaigns/wizard/api/finalize', wizard_views_v2.finalize_campaign_api, name='finalize_campaign_api'),
```

### Phase 2.3: Update Orchestrator Endpoints

**File:** `ai-agents/orchestrator/main.py`

Add these new endpoints (after existing campaign-wizard endpoints):

```python
@app.post("/campaign-wizard/approve-quests")
async def approve_quests(request: Dict[str, Any]):
    """User approves quests, trigger place generation"""
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "user_approved_quests": True,
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
                "request_id": campaign_message["request_id"]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving quests: {str(e)}")


@app.post("/campaign-wizard/approve-places")
async def approve_places(request: Dict[str, Any]):
    """User approves places, trigger scene generation"""
    import aio_pika

    try:
        rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://skillforge:password@rabbitmq:5672")
        connection = await aio_pika.connect_robust(rabbitmq_url)

        async with connection:
            channel = await connection.channel()

            campaign_message = {
                "request_id": request.get("request_id"),
                "user_id": request.get("user_id"),
                "user_approved_places": True,
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
                "request_id": campaign_message["request_id"]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving places: {str(e)}")


@app.post("/campaign-wizard/finalize")
async def finalize_campaign(request: Dict[str, Any]):
    """Finalize campaign and persist to MongoDB/Neo4j"""
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

            # Wait briefly for finalization (or implement proper wait mechanism)
            import asyncio
            await asyncio.sleep(2)

            # Get final campaign ID from Redis
            progress_key = f"campaign:progress:{request.get('request_id')}"
            progress_data = await redis_client.get(progress_key)

            if progress_data:
                data = json.loads(progress_data)
                return {
                    "status": "completed",
                    "campaign_id": data.get("final_campaign_id")
                }

            return {
                "status": "completed",
                "campaign_id": None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finalizing campaign: {str(e)}")
```

### Phase 2.4: Update Workflow State & Nodes

**File:** `services/campaign-factory/workflow/state.py`

Add to CampaignWorkflowState:
```python
# Additional approval gates
user_approved_quests: bool
user_approved_places: bool
user_approved_scenes: bool

# Backstory tracking
campaign_backstory: Optional[str]
quest_backstories: Dict[str, str]  # quest_id -> backstory

# Image generation preferences
generate_images_campaign: bool
generate_images_quests: bool
generate_images_places: bool
generate_images_scenes: bool
```

**File:** `services/campaign-factory/workflow/campaign_workflow.py`

Update routing functions and add new nodes:

```python
# Add wait nodes for new approval gates
from .nodes_quest import wait_for_quest_approval_node
from .nodes_place_scene import wait_for_place_approval_node, wait_for_scene_approval_node


def route_after_quests(state: CampaignWorkflowState) -> str:
    """Route after quest generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_quests"
    if state.get("user_approved_quests", False):
        return "generate_places"
    return "wait_for_quest_approval"


def route_after_quest_approval(state: CampaignWorkflowState) -> str:
    """Route after user approves quests"""
    if state.user_approved_quests:
        return "generate_places"
    return "wait_for_quest_approval"


def route_after_places(state: CampaignWorkflowState) -> str:
    """Route after place generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_places"
    if state.get("user_approved_places", False):
        return "generate_scenes"
    return "wait_for_place_approval"


def route_after_place_approval(state: CampaignWorkflowState) -> str:
    """Route after user approves places"""
    if state.user_approved_places:
        return "generate_scenes"
    return "wait_for_place_approval"


def route_after_scenes(state: CampaignWorkflowState) -> str:
    """Route after scene generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_scenes"
    if state.get("user_approved_scenes", False):
        return "generate_elements"
    return "wait_for_scene_approval"


# In create_campaign_workflow():
workflow.add_node("wait_for_quest_approval", wait_for_quest_approval_node)
workflow.add_node("wait_for_place_approval", wait_for_place_approval_node)
workflow.add_node("wait_for_scene_approval", wait_for_scene_approval_node)

# Update edges
workflow.add_conditional_edges(
    "generate_quests",
    route_after_quests,
    {
        "generate_places": "generate_places",
        "wait_for_quest_approval": "wait_for_quest_approval",
        "retry_quests": "generate_quests",
        "failed": END
    }
)

workflow.add_conditional_edges(
    "wait_for_quest_approval",
    route_after_quest_approval,
    {
        "generate_places": "generate_places",
        "wait_for_quest_approval": "wait_for_quest_approval"
    }
)

# Similar for places and scenes...
```

---

## 🚀 Testing & Deployment

### To Test the Full Implementation:

1. **Create Django view file**:
```bash
# Create services/django-web/campaigns/wizard_views_v2.py
# (Copy code from above)
```

2. **Update URLs**:
```bash
# Edit services/django-web/skillforge/urls.py
# Import wizard_views_v2
# Add all wizard API endpoints
```

3. **Update orchestrator**:
```bash
# Edit ai-agents/orchestrator/main.py
# Add approve-quests, approve-places, finalize endpoints
```

4. **Update workflow**:
```bash
# Edit services/campaign-factory/workflow/state.py
# Edit services/campaign-factory/workflow/campaign_workflow.py
# Add approval gate nodes and routing
```

5. **Create static JS directory** (if needed):
```bash
mkdir -p services/django-web/static/js
```

6. **Test workflow**:
- Navigate to `/campaigns/wizard/v2/`
- Select Universe → World → Region
- Enter story idea (optional)
- Generate 3 story ideas
- Select story
- Review campaign core
- Configure quests
- Review quests/places/scenes
- Finalize campaign

---

## 📋 Summary of All Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **1.1-1.3** | ✅ Complete | Universe/World/Region selection UI |
| **1.4-1.6** | ✅ Complete | Story idea generation UI with 3 options |
| **1.7-1.10** | ✅ Complete | Quest/Place/Scene review steps UI |
| **1.11-1.12** | ✅ Complete | Image generation options & enhanced progress |
| **2.1** | ⏳ Needs Implementation | Django wizard view endpoints |
| **2.2** | ⏳ Needs Implementation | URL configuration |
| **2.3** | ⏳ Needs Implementation | Orchestrator endpoint updates |
| **2.4** | ⏳ Needs Implementation | Workflow state & node updates |
| **3** | ✅ Complete | Bloom's Taxonomy integration (in UI) |
| **4** | ⚠️ Partial | Location hierarchy (needs workflow node updates) |
| **5** | ✅ Complete | Backstory display (in UI) |
| **6** | ✅ Complete | Knowledge & Items system display (in UI) |

---

## 🎯 Next Steps

1. Create `wizard_views_v2.py` with all API endpoints
2. Update `skillforge/urls.py` to include new endpoints
3. Update orchestrator with new approval gate endpoints
4. Update workflow to include approval gate nodes
5. Test end-to-end workflow
6. Update navigation to link to new wizard (`/campaigns/wizard/v2/`)

All frontend code is complete and ready. The remaining work is primarily backend integration to connect the UI to the existing LangGraph workflow.
