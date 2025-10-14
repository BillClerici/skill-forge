"""
Campaign Factory Utility Functions
Progress publishing, audit trail management, checkpointing
"""
import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import aio_pika
from redis.asyncio import Redis
from pymongo import MongoClient
from .state import CampaignWorkflowState, AuditEntry

logger = logging.getLogger(__name__)

# Database connections
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['skillforge']

# Redis client (will be set by main.py)
redis_client: Redis = None


def set_redis_client(client: Redis):
    """Set the global Redis client"""
    global redis_client
    redis_client = client


async def save_campaign_state(state: CampaignWorkflowState):
    """
    Save campaign workflow state to Redis for resumption

    Args:
        state: Campaign workflow state
    """
    if redis_client is None:
        logger.warning("Redis client not initialized, skipping state save")
        return

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


async def publish_progress(state: CampaignWorkflowState, message: str = None):
    """
    Publish workflow progress to RabbitMQ for real-time UI updates
    Also saves state to Redis

    Args:
        state: Current workflow state
        message: Optional custom message (uses state.status_message if None)
    """
    try:
        # Save state to Redis first
        await save_campaign_state(state)

        connection = await aio_pika.connect_robust(
            f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
            f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
        )

        async with connection:
            channel = await connection.channel()

            progress_data = {
                "request_id": state["request_id"],
                "user_id": state["user_id"],
                "phase": state["current_phase"],
                "node": state["current_node"],
                "progress": state["progress_percentage"],
                "message": message or state["status_message"],
                "timestamp": datetime.utcnow().isoformat(),
                "errors": state["errors"],
                "warnings": state["warnings"]
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(progress_data).encode(),
                    content_type="application/json"
                ),
                routing_key=f"campaign.progress.{state['request_id']}"
            )

            logger.info(f"Published progress: {state['current_phase']} - {state['progress_percentage']}%")

    except Exception as e:
        logger.error(f"Error publishing progress: {e}")
        # Don't fail workflow on progress publish errors


def add_audit_entry(state: CampaignWorkflowState, node: str, action: str,
                    details: Dict[str, Any], status: str = "success"):
    """
    Add entry to audit trail

    Args:
        state: Current workflow state
        node: Node name
        action: Action description
        details: Additional details
        status: Entry status (success, error, warning)
    """
    entry: AuditEntry = {
        "timestamp": datetime.utcnow().isoformat(),
        "node": node,
        "action": action,
        "details": details,
        "status": status
    }

    state["audit_trail"].append(entry)
    logger.info(f"Audit: [{node}] {action} - {status}")


def create_checkpoint(state: CampaignWorkflowState, phase_name: str):
    """
    Create state checkpoint for potential rollback

    Args:
        state: Current workflow state
        phase_name: Name of phase to checkpoint
    """
    checkpoint = {
        "phase": phase_name,
        "timestamp": datetime.utcnow().isoformat(),
        "campaign_core": state.get("campaign_core"),
        "quests": state.get("quests", []).copy() if state.get("quests") else [],
        "places": state.get("places", []).copy() if state.get("places") else [],
        "scenes": state.get("scenes", []).copy() if state.get("scenes") else [],
        "npcs": state.get("npcs", []).copy() if state.get("npcs") else [],
        "discoveries": state.get("discoveries", []).copy() if state.get("discoveries") else [],
        "events": state.get("events", []).copy() if state.get("events") else [],
        "challenges": state.get("challenges", []).copy() if state.get("challenges") else [],
        "new_species_ids": state.get("new_species_ids", []).copy() if state.get("new_species_ids") else [],
        "new_location_ids": state.get("new_location_ids", []).copy() if state.get("new_location_ids") else [],
        "progress_percentage": state.get("progress_percentage", 0)
    }

    state["checkpoints"][phase_name] = checkpoint
    logger.info(f"Created checkpoint: {phase_name}")


def rollback_to_checkpoint(state: CampaignWorkflowState, phase_name: str) -> bool:
    """
    Rollback state to a previous checkpoint

    Args:
        state: Current workflow state
        phase_name: Name of checkpoint to rollback to

    Returns:
        True if rollback successful, False if checkpoint not found
    """
    if phase_name not in state.get("checkpoints", {}):
        logger.error(f"Checkpoint '{phase_name}' not found")
        return False

    checkpoint = state["checkpoints"][phase_name]

    # Restore state from checkpoint
    state["campaign_core"] = checkpoint["campaign_core"]
    state["quests"] = checkpoint["quests"]
    state["places"] = checkpoint["places"]
    state["scenes"] = checkpoint["scenes"]
    state["npcs"] = checkpoint["npcs"]
    state["discoveries"] = checkpoint["discoveries"]
    state["events"] = checkpoint["events"]
    state["challenges"] = checkpoint["challenges"]
    state["new_species_ids"] = checkpoint["new_species_ids"]
    state["new_location_ids"] = checkpoint["new_location_ids"]
    state["progress_percentage"] = checkpoint["progress_percentage"]

    # Clear errors
    state["errors"] = []
    state["warnings"] = []
    state["retry_count"] = 0

    logger.info(f"Rolled back to checkpoint: {phase_name}")
    add_audit_entry(state, "rollback", f"Rolled back to {phase_name}",
                    {"checkpoint_timestamp": checkpoint["timestamp"]}, "success")

    return True


def save_audit_trail(state: CampaignWorkflowState, output_path: str = None):
    """
    Save audit trail to file for debugging and compliance

    Args:
        state: Current workflow state
        output_path: Optional custom output path
    """
    if output_path is None:
        audit_dir = os.path.join(os.getcwd(), "audit_trails")
        os.makedirs(audit_dir, exist_ok=True)
        output_path = os.path.join(audit_dir, f"campaign_{state['request_id']}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")

    audit_data = {
        "request_id": state["request_id"],
        "user_id": state["user_id"],
        "character_id": state["character_id"],
        "created_at": state["created_at"],
        "final_phase": state["current_phase"],
        "final_status": "success" if not state.get("errors", []) else "failed",
        "campaign_id": state.get("final_campaign_id"),
        "audit_trail": state["audit_trail"],
        "checkpoints": list(state.get("checkpoints", {}).keys()),
        "errors": state.get("errors", []),
        "warnings": state.get("warnings", [])
    }

    try:
        with open(output_path, 'w') as f:
            json.dump(audit_data, f, indent=2)
        logger.info(f"Saved audit trail to {output_path}")
    except Exception as e:
        logger.error(f"Error saving audit trail: {e}")


def calculate_progress(state: CampaignWorkflowState) -> int:
    """
    Calculate workflow progress percentage based on current phase

    Phase weights:
    - init: 5%
    - story_gen: 10%
    - core_gen: 15%
    - quest_gen: 20%
    - place_gen: 20%
    - scene_gen: 20%
    - element_gen: 25%
    - finalize: 100%
    """
    phase_progress = {
        "init": 5,
        "story_gen": 10,
        "core_gen": 15,
        "quest_gen": 35,  # Cumulative
        "place_gen": 55,
        "scene_gen": 75,
        "element_gen": 95,
        "finalize": 100
    }

    return phase_progress.get(state.get("current_phase", "init"), 0)


def get_blooms_level_description(level: int) -> str:
    """
    Get human-readable description of Bloom's Taxonomy level

    Args:
        level: Bloom's level (1-6)

    Returns:
        Description string
    """
    levels = {
        1: "Remembering - Recall facts and basic concepts",
        2: "Understanding - Explain ideas or concepts",
        3: "Applying - Use information in new situations",
        4: "Analyzing - Draw connections among ideas",
        5: "Evaluating - Justify a decision or course of action",
        6: "Creating - Produce new or original work"
    }

    return levels.get(level, "Unknown level")


async def publish_entity_event(entity_type: str, action: str, entity_id: str, entity_data: Dict[str, Any]):
    """
    Publish entity lifecycle event to RabbitMQ for Neo4j sync

    Args:
        entity_type: 'world', 'region', 'location', 'species', 'npc'
        action: 'created', 'updated', 'deleted'
        entity_id: Entity ID
        entity_data: Dictionary with entity details
    """
    try:
        routing_key = f'entity.{entity_type}.{action}'
        event_data = {
            'entity_type': entity_type,
            'action': action,
            'entity_id': entity_id,
            'data': entity_data
        }

        # Publish to RabbitMQ entity exchange
        connection = await aio_pika.connect_robust(
            f"amqp://{os.getenv('RABBITMQ_USER')}:{os.getenv('RABBITMQ_PASS')}@"
            f"{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/"
        )

        async with connection:
            channel = await connection.channel()

            # Declare skillforge events exchange (same as Django and world-factory)
            await channel.declare_exchange(
                'skillforge.events',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )

            exchange = await channel.get_exchange('skillforge.events')

            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(event_data).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=routing_key
            )

        logger.info(f"Published entity event: {routing_key} for {entity_id}")

    except Exception as e:
        logger.error(f"Failed to publish entity event: {e}")
