"""
RabbitMQ connection manager and event publisher
"""
import pika
import json
import os
import logging

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://skillforge:rabbitmq_pass@rabbitmq:5672')


class RabbitMQPublisher:
    """Singleton RabbitMQ publisher for Django"""

    _instance = None
    _connection = None
    _channel = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RabbitMQPublisher, cls).__new__(cls)
        return cls._instance

    def _ensure_connection(self):
        """Ensure RabbitMQ connection is active"""
        if self._connection is None or self._connection.is_closed:
            try:
                # Parse RABBITMQ_URL
                params = pika.URLParameters(RABBITMQ_URL)
                self._connection = pika.BlockingConnection(params)
                self._channel = self._connection.channel()

                # Declare exchanges
                self._channel.exchange_declare(
                    exchange='skillforge.events',
                    exchange_type='topic',
                    durable=True
                )

                # Declare queues
                self._channel.queue_declare(queue='neo4j.sync', durable=True)
                self._channel.queue_declare(queue='ai.generation', durable=True)

                # Bind queues to exchange
                self._channel.queue_bind(
                    exchange='skillforge.events',
                    queue='neo4j.sync',
                    routing_key='entity.*'
                )
                self._channel.queue_bind(
                    exchange='skillforge.events',
                    queue='ai.generation',
                    routing_key='ai.*'
                )

                logger.info("RabbitMQ connection established")
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                self._connection = None
                self._channel = None

    def publish_event(self, routing_key, event_data):
        """
        Publish an event to RabbitMQ with automatic retry

        Args:
            routing_key: Event routing key (e.g., 'entity.species.created', 'ai.backstory.generate')
            event_data: Dictionary of event data
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._ensure_connection()

                if self._channel is None:
                    logger.warning(f"RabbitMQ not available, skipping event: {routing_key}")
                    return False

                message = json.dumps(event_data)

                self._channel.basic_publish(
                    exchange='skillforge.events',
                    routing_key=routing_key,
                    body=message,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type='application/json'
                    )
                )

                logger.info(f"Published event: {routing_key}")
                return True

            except Exception as e:
                logger.error(f"Failed to publish event {routing_key} (attempt {attempt + 1}/{max_retries}): {e}")
                # Reset connection for retry
                self._connection = None
                self._channel = None

                if attempt == max_retries - 1:
                    logger.error(f"Failed to publish event {routing_key} after {max_retries} attempts")
                    return False

        return False

    def close(self):
        """Close RabbitMQ connection"""
        if self._connection and not self._connection.is_closed:
            self._connection.close()


# Singleton instance
publisher = RabbitMQPublisher()


def publish_entity_event(entity_type, action, entity_id, entity_data):
    """
    Publish entity lifecycle event

    Args:
        entity_type: 'species', 'world', 'region', 'location', 'universe'
        action: 'created', 'updated', 'deleted'
        entity_id: Entity ID
        entity_data: Dictionary with entity details
    """
    routing_key = f'entity.{entity_type}.{action}'
    event_data = {
        'entity_type': entity_type,
        'action': action,
        'entity_id': entity_id,
        'data': entity_data
    }
    return publisher.publish_event(routing_key, event_data)


def publish_ai_task(task_type, task_data):
    """
    Publish AI generation task

    Args:
        task_type: 'backstory', 'image', 'region', 'species'
        task_data: Dictionary with task details (includes entity_id, world_id, etc.)
    """
    routing_key = f'ai.{task_type}.generate'
    return publisher.publish_event(routing_key, task_data)
