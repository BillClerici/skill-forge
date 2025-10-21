"""
RabbitMQ Event Consumer for Game UI Gateway
Listens for game events and forwards them to WebSocket clients
"""
import json
import asyncio
import logging
from typing import Optional
import aio_pika
from aio_pika.abc import AbstractIncomingMessage

logger = logging.getLogger(__name__)


class EventConsumer:
    """
    Consumes game events from RabbitMQ and forwards to WebSocket clients
    """

    def __init__(self, connection_string: str, connection_manager):
        self.connection_string = connection_string
        self.connection_manager = connection_manager
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self.consuming = False

    async def connect(self):
        """Connect to RabbitMQ and set up queue"""
        try:
            self.connection = await aio_pika.connect_robust(
                self.connection_string
            )
            self.channel = await self.connection.channel()

            # Set prefetch count
            await self.channel.set_qos(prefetch_count=10)

            # Declare exchange (should already exist)
            exchange = await self.channel.declare_exchange(
                'game.events',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )

            # Declare queue for UI gateway
            self.queue = await self.channel.declare_queue(
                'game.ui.events',
                durable=False,  # Non-durable for UI events (ephemeral)
                auto_delete=True  # Auto-delete when gateway disconnects
            )

            # Bind to all session events
            await self.queue.bind(
                exchange,
                routing_key='session.#'
            )

            logger.info(
                f"Event consumer connected - Queue: {self.queue.name}, "
                f"Exchange: game.events, Routing key: session.#"
            )

        except Exception as e:
            logger.error(f"Event consumer connection failed: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        self.consuming = False
        if self.connection:
            await self.connection.close()
            logger.info("Event consumer disconnected")

    async def start_consuming(self):
        """Start consuming messages from the queue"""
        if not self.queue:
            raise RuntimeError("Queue not initialized. Call connect() first.")

        self.consuming = True
        logger.info("Started consuming game events")

        # Start consuming messages
        await self.queue.consume(self._process_event)

    async def _process_event(self, message: AbstractIncomingMessage):
        """
        Process incoming game event message

        Args:
            message: Incoming RabbitMQ message
        """
        async with message.process():
            try:
                # Parse message
                data = json.loads(message.body.decode())

                event_type = data.get('event_type')
                session_id = data.get('session_id')

                logger.info(
                    f"Game event received - Type: {event_type}, Session: {session_id}"
                )

                # Forward event to all players in the session
                if session_id:
                    await self.connection_manager.broadcast_to_session(
                        session_id,
                        data
                    )

            except json.JSONDecodeError as e:
                logger.error(f"Invalid event JSON: {e}")

            except Exception as e:
                logger.error(f"Event processing failed: {e}")
