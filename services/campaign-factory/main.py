"""
Campaign Factory Service - RabbitMQ Consumer
Orchestrates campaign generation using LangGraph workflow
"""
import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import aio_pika
from pymongo import MongoClient
from neo4j import GraphDatabase
import uuid
from redis.asyncio import Redis

from workflow import create_campaign_workflow, CampaignWorkflowState
from workflow.utils import set_redis_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize workflow
campaign_workflow = create_campaign_workflow()

# Database connections
mongo_client = None
neo4j_driver = None
redis_client = None


async def init_database_connections():
    """Initialize database connections"""
    global mongo_client, neo4j_driver, redis_client

    try:
        # MongoDB
        mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        mongo_client = MongoClient(mongo_uri)
        logger.info("Connected to MongoDB")

        # Neo4j
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
        neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        logger.info("Connected to Neo4j")

        # Redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_client = Redis.from_url(redis_url, decode_responses=True)
        set_redis_client(redis_client)  # Set global Redis client for workflow utils
        logger.info("Connected to Redis")

    except Exception as e:
        logger.error(f"Error initializing database connections: {e}")
        raise


async def process_campaign_request(message: aio_pika.IncomingMessage):
    """
    Process campaign generation request from RabbitMQ

    Message format:
    {
        "request_id": "uuid",
        "user_id": "user_uuid",
        "character_id": "character_uuid",
        "universe_id": "universe_uuid",
        "universe_name": "Universe Name",
        "world_id": "world_uuid",
        "world_name": "World Name",
        "region_id": "region_uuid",
        "region_name": "Region Name",
        "genre": "fantasy",
        "user_story_idea": "Optional story direction",
        "workflow_action": "start|select_story|approve_core|regenerate_stories|approve_quests|approve_places|finalize",
        "selected_story_id": "story_uuid",  # For select_story action
        "user_approved_core": true,  # For approve_core action
        "num_quests": 5,
        "quest_difficulty": "Medium",
        "quest_playtime_minutes": 90,
        "generate_images": true
    }
    """
    async with message.process():
        try:
            # Parse message
            request_data = json.loads(message.body.decode())
            logger.info(f"Received campaign request: {request_data.get('request_id')}")

            workflow_action = request_data.get("workflow_action", "start")

            if workflow_action == "start":
                # Initialize new workflow state
                state = await initialize_campaign_state(request_data)

                # Run workflow (will pause at first human-in-the-loop gate)
                result_state = await campaign_workflow.ainvoke(state)

                # Publish story ideas to user for selection
                await publish_story_ideas_to_user(result_state)

            elif workflow_action == "select_story":
                # Resume workflow with user's story selection
                state = await load_campaign_state(request_data["request_id"])
                state["selected_story_id"] = request_data["selected_story_id"]

                # Continue workflow
                result_state = await campaign_workflow.ainvoke(state)

                # Publish campaign core to user for approval
                await publish_campaign_core_to_user(result_state)

            elif workflow_action == "regenerate_stories":
                # Resume workflow to regenerate stories
                state = await load_campaign_state(request_data["request_id"])
                state["regenerate_stories"] = True

                # Continue workflow
                result_state = await campaign_workflow.ainvoke(state)

                # Publish new story ideas
                await publish_story_ideas_to_user(result_state)

            elif workflow_action == "approve_core":
                # Resume workflow with user's core approval
                state = await load_campaign_state(request_data["request_id"])
                state["user_approved_core"] = request_data["user_approved_core"]
                state["num_quests"] = request_data.get("num_quests", 5)
                state["quest_difficulty"] = request_data.get("quest_difficulty", "Medium")
                state["quest_playtime_minutes"] = request_data.get("quest_playtime_minutes", 90)
                state["generate_images"] = request_data.get("generate_images", True)

                # Continue workflow (will run to completion)
                result_state = await campaign_workflow.ainvoke(state)

                # Publish final campaign result
                await publish_campaign_completion(result_state)

            elif workflow_action == "approve_quests":
                # Resume workflow with quest approval
                state = await load_campaign_state(request_data["request_id"])
                state["user_approved_quests"] = request_data.get("user_approved_quests", True)

                # Continue workflow
                result_state = await campaign_workflow.ainvoke(state)

                # Save updated state
                await save_campaign_state(result_state)

            elif workflow_action == "approve_places":
                # Resume workflow with place approval
                state = await load_campaign_state(request_data["request_id"])
                state["user_approved_places"] = request_data.get("user_approved_places", True)

                # Continue workflow
                result_state = await campaign_workflow.ainvoke(state)

                # Save updated state
                await save_campaign_state(result_state)

            elif workflow_action == "finalize":
                # Manually trigger finalization
                state = await load_campaign_state(request_data["request_id"])

                # Import finalization node
                from workflow.nodes_finalize import finalize_campaign_node

                # Run finalization
                result_state = await finalize_campaign_node(state)

                # Save updated state
                await save_campaign_state(result_state)

                # Publish completion
                await publish_campaign_completion(result_state)

            logger.info(f"Campaign request processed: {request_data.get('request_id')}")

        except Exception as e:
            logger.error(f"Error processing campaign request: {e}")
            # Publish error to user
            await publish_error_to_user(request_data.get("request_id"), str(e))


async def initialize_campaign_state(request_data: dict) -> CampaignWorkflowState:
    """
    Initialize campaign workflow state from request

    Args:
        request_data: Request data from RabbitMQ

    Returns:
        Initialized CampaignWorkflowState
    """
    # Fetch region details from MongoDB if region_id is provided
    region_data = {}
    if request_data.get("region_id"):
        try:
            mongo_db = mongo_client['skillforge']
            region = mongo_db.region_definitions.find_one({"_id": request_data["region_id"]})
            if region:
                region_data = {
                    "description": region.get("description", ""),
                    "backstory": region.get("backstory", ""),
                    "climate": region.get("climate", ""),
                    "terrain": region.get("terrain", ""),
                    "key_features": region.get("key_features", []),
                    "notable_locations": region.get("notable_locations", []),
                    "inhabitants": region.get("inhabitants", [])
                }
                logger.info(f"Loaded region data for {request_data['region_name']}")
        except Exception as e:
            logger.warning(f"Could not fetch region details: {e}")

    state: CampaignWorkflowState = {
        "request_id": request_data.get("request_id", str(uuid.uuid4())),
        "user_id": request_data["user_id"],
        "character_id": request_data["character_id"],
        "created_at": datetime.utcnow().isoformat(),

        # User selections
        "universe_id": request_data["universe_id"],
        "universe_name": request_data["universe_name"],
        "world_id": request_data["world_id"],
        "world_name": request_data["world_name"],
        "region_id": request_data["region_id"],
        "region_name": request_data["region_name"],
        "region_data": region_data,  # Full region details for story generation
        "genre": request_data["genre"],
        "user_story_idea": request_data.get("user_story_idea"),

        # Story generation
        "story_ideas": [],
        "selected_story_id": None,
        "story_regeneration_count": 0,
        "regenerate_stories": False,

        # Campaign core
        "campaign_core": None,
        "user_approved_core": False,

        # Quest specifications (will be set after core approval)
        "num_quests": 5,
        "quest_difficulty": "Medium",
        "quest_playtime_minutes": 90,
        "generate_images": True,

        # User approval flags for workflow gates
        "user_approved_quests": None,
        "user_approved_places": None,

        # Generated content
        "quests": [],
        "places": [],
        "scenes": [],
        "npcs": [],
        "discoveries": [],
        "events": [],
        "challenges": [],

        # World enrichment tracking
        "new_species_ids": [],
        "new_location_ids": [],  # DEPRECATED
        "new_locations": [],  # Full location details
        "new_npc_ids": [],

        # Workflow state management
        "current_phase": "init",
        "current_node": "",
        "errors": [],
        "warnings": [],
        "retry_count": 0,
        "max_retries": 3,

        # Audit trail
        "audit_trail": [],

        # Checkpoints
        "checkpoints": {},

        # Progress tracking
        "progress_percentage": 0,
        "status_message": "Initializing campaign generation...",

        # Results
        "final_campaign_id": None,
        "mongodb_campaign_id": None,
        "neo4j_relationships_created": 0,
        "postgres_records_created": 0
    }

    # Save initial state
    await save_campaign_state(state)

    return state


async def save_campaign_state(state: CampaignWorkflowState):
    """
    Save campaign workflow state to Redis for resumption

    Args:
        state: Campaign workflow state
    """
    try:
        request_id = state['request_id']

        # Save full state to Redis with 24 hour expiry
        state_key = f"campaign:state:{request_id}"
        await redis_client.setex(state_key, 86400, json.dumps(state, default=str))

        # Save progress data for status API
        progress_key = f"campaign:progress:{request_id}"
        progress_data = {
            "request_id": request_id,
            "progress_percentage": state.get("progress_percentage", 0),
            "status_message": state.get("status_message", "Processing..."),
            "current_phase": state.get("current_phase", "init"),
            "current_node": state.get("current_node", ""),
            "story_ideas": state.get("story_ideas", []),
            "campaign_core": state.get("campaign_core"),
            "quests": state.get("quests", []),
            "places": state.get("places", []),
            "scenes": state.get("scenes", []),
            "npcs": state.get("npcs", []),
            "discoveries": state.get("discoveries", []),
            "events": state.get("events", []),
            "challenges": state.get("challenges", []),
            "new_location_ids": state.get("new_location_ids", []),  # DEPRECATED
            "new_locations": state.get("new_locations", []),  # Full location details
            "final_campaign_id": state.get("final_campaign_id"),
            "errors": state.get("errors", []),
            "warnings": state.get("warnings", [])
        }
        await redis_client.setex(progress_key, 86400, json.dumps(progress_data, default=str))

        logger.info(f"Saved campaign state to Redis: {request_id}")

    except Exception as e:
        logger.error(f"Error saving campaign state to Redis: {e}")


async def load_campaign_state(request_id: str) -> CampaignWorkflowState:
    """
    Load campaign workflow state from Redis

    Args:
        request_id: Request ID

    Returns:
        Campaign workflow state
    """
    try:
        state_key = f"campaign:state:{request_id}"
        state_json = await redis_client.get(state_key)

        if not state_json:
            raise ValueError(f"Campaign state not found for request_id: {request_id}")

        state = json.loads(state_json)
        logger.info(f"Loaded campaign state from Redis: {request_id}")
        return state

    except Exception as e:
        logger.error(f"Error loading campaign state from Redis: {e}")
        raise


async def publish_story_ideas_to_user(state: CampaignWorkflowState):
    """
    Publish story ideas to user via RabbitMQ

    Args:
        state: Campaign workflow state with story ideas
    """
    connection = await aio_pika.connect_robust(
        f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
        f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
    )

    async with connection:
        channel = await connection.channel()

        message_data = {
            "request_id": state["request_id"],
            "workflow_phase": "story_selection",
            "story_ideas": state["story_ideas"],
            "regeneration_count": state["story_regeneration_count"]
        }

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_data).encode(),
                content_type="application/json"
            ),
            routing_key=f"campaign.story_ideas.{state['user_id']}"
        )

        logger.info(f"Published story ideas to user: {state['user_id']}")


async def publish_campaign_core_to_user(state: CampaignWorkflowState):
    """
    Publish campaign core to user for approval

    Args:
        state: Campaign workflow state with campaign core
    """
    connection = await aio_pika.connect_robust(
        f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
        f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
    )

    async with connection:
        channel = await connection.channel()

        message_data = {
            "request_id": state["request_id"],
            "workflow_phase": "core_approval",
            "campaign_core": state["campaign_core"]
        }

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_data).encode(),
                content_type="application/json"
            ),
            routing_key=f"campaign.core_approval.{state['user_id']}"
        )

        logger.info(f"Published campaign core to user: {state['user_id']}")


async def publish_campaign_completion(state: CampaignWorkflowState):
    """
    Publish campaign completion notification

    Args:
        state: Final campaign workflow state
    """
    connection = await aio_pika.connect_robust(
        f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
        f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
    )

    async with connection:
        channel = await connection.channel()

        message_data = {
            "request_id": state["request_id"],
            "workflow_phase": "completed",
            "campaign_id": state["final_campaign_id"],
            "status": "success" if not state["errors"] else "failed",
            "errors": state["errors"],
            "stats": {
                "num_quests": len(state["quests"]),
                "num_places": len(state["places"]),
                "num_scenes": len(state["scenes"]),
                "num_npcs": len(state["npcs"]),
                "new_species_created": len(state["new_species_ids"]),
                "new_locations_created": len(state["new_location_ids"])
            }
        }

        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_data).encode(),
                content_type="application/json"
            ),
            routing_key=f"campaign.completed.{state['user_id']}"
        )

        logger.info(f"Published campaign completion: {state['final_campaign_id']}")


async def publish_error_to_user(request_id: str, error: str):
    """
    Publish error notification to user

    Args:
        request_id: Request ID
        error: Error message
    """
    try:
        connection = await aio_pika.connect_robust(
            f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
            f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
        )

        async with connection:
            channel = await connection.channel()

            message_data = {
                "request_id": request_id,
                "workflow_phase": "error",
                "error": error
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message_data).encode(),
                    content_type="application/json"
                ),
                routing_key=f"campaign.error.{request_id}"
            )

            logger.info(f"Published error notification: {request_id}")

    except Exception as e:
        logger.error(f"Error publishing error notification: {e}")


async def main():
    """
    Main entry point - Start RabbitMQ consumer
    """
    logger.info("Starting Campaign Factory service...")

    # Initialize database connections
    await init_database_connections()

    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(
        f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
        f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
    )

    async with connection:
        # Create channel
        channel = await connection.channel()

        # Set QoS
        await channel.set_qos(prefetch_count=1)

        # Declare queue
        queue = await channel.declare_queue(
            "campaign_generation_queue",
            durable=True
        )

        logger.info("Campaign Factory service ready. Waiting for campaign requests...")

        # Start consuming
        await queue.consume(process_campaign_request)

        # Keep running
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down Campaign Factory service...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Campaign Factory service stopped")
        sys.exit(0)
