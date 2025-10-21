"""
RabbitMQ service for publishing and consuming events
"""
import aio_pika
import json
import logging
from typing import Callable, Optional
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder for UUID and datetime"""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RabbitMQService:
    """Service for RabbitMQ operations"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchanges = {}

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.connection_string)
            self.channel = await self.connection.channel()

            # Declare/get exchanges (should already exist from init)
            self.exchanges['game.events'] = await self.channel.declare_exchange(
                'game.events',
                aio_pika.ExchangeType.TOPIC,
                durable=True,
                passive=False  # Will create if doesn't exist
            )

            self.exchanges['game.ui'] = await self.channel.declare_exchange(
                'game.ui',
                aio_pika.ExchangeType.TOPIC,
                durable=True,
                passive=False
            )

            self.exchanges['game.commands'] = await self.channel.declare_exchange(
                'game.commands',
                aio_pika.ExchangeType.DIRECT,
                durable=True,
                passive=False
            )

            logger.info("✓ Connected to RabbitMQ and declared exchanges")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    async def publish_event(
        self,
        exchange_name: str,
        routing_key: str,
        message: dict,
        priority: int = 5
    ):
        """
        Publish an event to an exchange

        Args:
            exchange_name: Name of the exchange (without .exchange suffix)
            routing_key: Routing key for the message
            message: Message payload as dictionary
            priority: Message priority (0-9)
        """
        try:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                logger.error(f"Exchange {exchange_name} not found")
                return

            # Convert message to JSON with custom encoder
            message_body = json.dumps(message, cls=UUIDEncoder).encode()

            # Create message
            aio_message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority,
                content_type='application/json',
                timestamp=datetime.utcnow()
            )

            # Publish
            await exchange.publish(
                aio_message,
                routing_key=routing_key
            )

            logger.debug(f"Published event to {exchange_name} with key {routing_key}")

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    async def consume_queue(
        self,
        queue_name: str,
        callback: Callable,
        prefetch_count: int = 10
    ):
        """
        Consume messages from a queue

        Args:
            queue_name: Name of the queue to consume from
            callback: Async callback function to process messages
            prefetch_count: Number of messages to prefetch
        """
        try:
            await self.channel.set_qos(prefetch_count=prefetch_count)

            queue = await self.channel.declare_queue(
                queue_name,
                durable=True
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            # Parse message
                            body = json.loads(message.body.decode())

                            # Call callback
                            await callback(body)

                            logger.debug(f"Processed message from {queue_name}")

                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            # Message will be nacked and potentially sent to DLQ

        except Exception as e:
            logger.error(f"Failed to consume from queue {queue_name}: {e}")
            raise

    async def create_session_queue(self, session_id: UUID) -> str:
        """
        Create a session-specific queue for UI updates

        Args:
            session_id: Session ID

        Returns:
            Queue name
        """
        try:
            queue_name = f"game.session.{session_id}.ui"

            queue = await self.channel.declare_queue(
                queue_name,
                durable=False,
                auto_delete=True,
                arguments={
                    'x-message-ttl': 300000,  # 5 minutes
                    'x-max-length': 1000
                }
            )

            # Bind to UI exchange with session-specific routing key
            await queue.bind(
                self.exchanges['game.ui'],
                routing_key=f"ui.session.{session_id}.#"
            )

            logger.info(f"Created session queue: {queue_name}")

            return queue_name

        except Exception as e:
            logger.error(f"Failed to create session queue: {e}")
            raise

    async def delete_session_queue(self, session_id: UUID):
        """Delete a session-specific queue"""
        try:
            queue_name = f"game.session.{session_id}.ui"
            await self.channel.queue_delete(queue_name)
            logger.info(f"Deleted session queue: {queue_name}")

        except Exception as e:
            logger.error(f"Failed to delete session queue: {e}")
