"""
RabbitMQ Client for Game Engine
Handles publishing game events and managing message queues
"""
import json
from typing import Dict, Any, Optional
import aio_pika
from aio_pika import ExchangeType
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class RabbitMQClient:
    """
    Manages RabbitMQ connections and message publishing
    """

    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchanges: Dict[str, aio_pika.Exchange] = {}

    async def connect(self):
        """Connect to RabbitMQ and set up exchanges"""
        try:
            self.connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL
            )
            self.channel = await self.connection.channel()

            # Declare exchanges
            await self._setup_exchanges()

            logger.info("rabbitmq_connected", url=settings.RABBITMQ_URL)

        except Exception as e:
            logger.error("rabbitmq_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            logger.info("rabbitmq_disconnected")

    async def _setup_exchanges(self):
        """Set up required exchanges"""
        exchange_configs = [
            ("game.events", ExchangeType.TOPIC),
            ("multiplayer.sync", ExchangeType.TOPIC),
            ("session.state", ExchangeType.TOPIC),
        ]

        for exchange_name, exchange_type in exchange_configs:
            exchange = await self.channel.declare_exchange(
                exchange_name,
                exchange_type,
                durable=True
            )
            self.exchanges[exchange_name] = exchange
            logger.info(
                "exchange_declared",
                exchange=exchange_name,
                type=exchange_type
            )

    async def publish_event(
        self,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Publish event to RabbitMQ

        Args:
            exchange: Exchange name
            routing_key: Routing key
            message: Message payload

        Returns:
            True if published successfully
        """
        try:
            if exchange not in self.exchanges:
                logger.error("exchange_not_found", exchange=exchange)
                return False

            message_body = json.dumps(message, default=str).encode()

            await self.exchanges[exchange].publish(
                aio_pika.Message(
                    body=message_body,
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=routing_key
            )

            logger.debug(
                "event_published",
                exchange=exchange,
                routing_key=routing_key,
                message_size=len(message_body)
            )
            return True

        except Exception as e:
            logger.error(
                "event_publish_failed",
                exchange=exchange,
                routing_key=routing_key,
                error=str(e)
            )
            return False

    async def publish_scene_update(
        self,
        session_id: str,
        scene_description: str,
        available_actions: list,
        available_npcs: list
    ):
        """Publish scene update event"""
        await self.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.scene_update",
            message={
                "event": "scene_update",
                "session_id": session_id,
                "scene_description": scene_description,
                "available_actions": available_actions,
                "available_npcs": available_npcs
            }
        )

    async def publish_scene_chunk(
        self,
        session_id: str,
        chunk: str,
        is_complete: bool = False
    ):
        """
        Publish streaming chunk for scene description

        Args:
            session_id: Session ID
            chunk: Text chunk to stream
            is_complete: Whether this is the final chunk
        """
        await self.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.scene_chunk",
            message={
                "event": "scene_chunk",
                "session_id": session_id,
                "chunk": chunk,
                "is_complete": is_complete
            }
        )

    async def publish_npc_response(
        self,
        session_id: str,
        npc_response: Dict[str, Any]
    ):
        """Publish NPC dialogue response"""
        await self.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.npc_response",
            message={
                "event": "npc_response",
                "session_id": session_id,
                **npc_response
            }
        )

    async def publish_assessment(
        self,
        session_id: str,
        assessment: Dict[str, Any]
    ):
        """Publish performance assessment"""
        await self.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.assessment",
            message={
                "event": "assessment",
                "session_id": session_id,
                **assessment
            }
        )

    async def publish_state_change(
        self,
        session_id: str,
        old_status: str,
        new_status: str
    ):
        """Publish session state change"""
        await self.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.state_change",
            message={
                "event": "session_state_changed",
                "session_id": session_id,
                "old_status": old_status,
                "new_status": new_status
            }
        )


# Global instance
rabbitmq_client = RabbitMQClient()
