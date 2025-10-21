"""
Consumer for UI events from RabbitMQ
"""
import aio_pika
import json
import logging
from typing import Dict, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class UIEventsConsumer:
    """Consumer for UI update events"""

    def __init__(self, connection_string: str, connection_manager):
        self.connection_string = connection_string
        self.connection_manager = connection_manager
        self.connection = None
        self.channel = None

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.connection_string)
            self.channel = await self.connection.channel()

            logger.info("✓ UI Events Consumer connected to RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to connect UI Events Consumer: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            logger.info("UI Events Consumer disconnected")

    async def subscribe_to_session(self, session_id: UUID):
        """Subscribe to UI events for a specific session"""
        try:
            # Declare session-specific queue
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

            # Bind to UI exchange (should already exist from init)
            ui_exchange = await self.channel.declare_exchange(
                'game.ui',
                aio_pika.ExchangeType.TOPIC,
                durable=True,
                passive=False
            )

            await queue.bind(
                ui_exchange,
                routing_key=f"ui.session.{session_id}.#"
            )

            logger.info(f"Subscribed to UI events for session {session_id}")

            # Start consuming
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            event = json.loads(message.body.decode())
                            await self._handle_ui_event(session_id, event)

                        except Exception as e:
                            logger.error(f"Error processing UI event: {e}")

        except Exception as e:
            logger.error(f"Error subscribing to session: {e}")

    async def _handle_ui_event(self, session_id: UUID, event: Dict[str, Any]):
        """Handle a UI event and broadcast to connected clients"""
        try:
            # Broadcast event to all connected clients in the session
            await self.connection_manager.send_to_session(session_id, event)

            logger.debug(f"Broadcasted UI event to session {session_id}")

        except Exception as e:
            logger.error(f"Error handling UI event: {e}")
