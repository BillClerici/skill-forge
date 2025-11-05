"""
Utility functions for World Factory workflow
"""
import os
import json
import logging
import pika
from datetime import datetime
from pymongo import MongoClient
from redis import Redis
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Database connections
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://skillforge:rabbitmq_pass@rabbitmq:5672')

mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def publish_progress(workflow_id: str, step: str, status: str, message: str, data: Dict[str, Any] = None):
    """Publish progress event to RabbitMQ and Redis"""
    try:
        event = {
            'workflow_id': workflow_id,
            'step': step,
            'status': status,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data or {}
        }

        # Publish to RabbitMQ for persistence
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.basic_publish(
                exchange='world_factory_progress',
                routing_key='',
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2)
            )

            connection.close()
        except Exception as e:
            logger.error(f"Failed to publish to RabbitMQ: {e}")

        # Also store in Redis for real-time access
        redis_key = f"world_factory:{workflow_id}:progress"
        redis_client.rpush(redis_key, json.dumps(event))
        redis_client.expire(redis_key, 86400)  # 24 hour TTL

        # Store latest status in Redis
        redis_client.setex(
            f"world_factory:{workflow_id}:latest",
            3600,  # 1 hour
            json.dumps(event)
        )

    except Exception as e:
        logger.error(f"Failed to publish progress: {e}")


def save_audit_trail(workflow_id: str, audit_entry: Dict[str, Any]):
    """Save audit trail entry to MongoDB"""
    try:
        db.world_factory_audit.update_one(
            {'workflow_id': workflow_id},
            {
                '$push': {'audit_trail': audit_entry},
                '$set': {'updated_at': datetime.utcnow()}
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Failed to save audit trail: {e}")


def get_existing_worlds_for_genre(genre: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get existing worlds for the specified genre"""
    try:
        worlds = list(db.world_definitions.find(
            {'genre': {'$regex': genre, '$options': 'i'}},
            {'world_name': 1, 'description': 1, 'themes': 1, 'genre': 1}
        ).limit(limit))
        return worlds
    except Exception as e:
        logger.error(f"Failed to get existing worlds: {e}")
        return []


def calculate_tokens_and_cost(model: str, input_tokens: int, output_tokens: int) -> tuple:
    """Calculate token usage and cost"""
    total_tokens = input_tokens + output_tokens

    # Pricing (as of 2024)
    pricing = {
        'claude-sonnet-4-5-20250929': {'input': 0.003, 'output': 0.015},  # per 1K tokens
        'gpt-4o': {'input': 0.0025, 'output': 0.010},
        'dall-e-3': {'per_image': 0.040}  # $0.04 per 1024x1024 image
    }

    if model in pricing:
        input_cost = (input_tokens / 1000) * pricing[model]['input']
        output_cost = (output_tokens / 1000) * pricing[model]['output']
        total_cost = input_cost + output_cost
    elif model == 'dall-e-3':
        total_cost = pricing[model]['per_image']
    else:
        total_cost = 0.0

    return total_tokens, total_cost


def store_workflow_state(workflow_id: str, state_data: Dict[str, Any]):
    """Store workflow state in MongoDB for recovery"""
    try:
        db.world_factory_state.update_one(
            {'workflow_id': workflow_id},
            {
                '$set': {
                    **state_data,
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Failed to store workflow state: {e}")


def get_workflow_state(workflow_id: str) -> Dict[str, Any]:
    """Retrieve workflow state from MongoDB"""
    try:
        state = db.world_factory_state.find_one({'workflow_id': workflow_id})
        return state if state else {}
    except Exception as e:
        logger.error(f"Failed to get workflow state: {e}")
        return {}


def publish_entity_event(entity_type: str, action: str, entity_id: str, entity_data: Dict[str, Any]):
    """
    Publish entity lifecycle event to RabbitMQ for Neo4j sync

    Args:
        entity_type: 'world', 'region', 'location', 'species'
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
        parameters = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Declare skillforge events exchange (same as Django)
        channel.exchange_declare(
            exchange='skillforge.events',
            exchange_type='topic',
            durable=True
        )

        channel.basic_publish(
            exchange='skillforge.events',
            routing_key=routing_key,
            body=json.dumps(event_data),
            properties=pika.BasicProperties(delivery_mode=2)
        )

        connection.close()
        logger.info(f"Published entity event: {routing_key} for {entity_id}")

    except Exception as e:
        logger.error(f"Failed to publish entity event: {e}")
