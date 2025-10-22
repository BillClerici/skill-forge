"""
Command publisher for RabbitMQ
"""
import aio_pika
import json
import logging
from typing import Dict, Any
from uuid import UUID, uuid4
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


class CommandPublisher:
    """Publisher for game commands"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
        self.channel = None
        self.commands_exchange = None
        self.events_exchange = None

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.connection_string)
            self.channel = await self.connection.channel()

            # Declare exchanges (should already exist from init)
            self.commands_exchange = await self.channel.declare_exchange(
                'game.commands',
                aio_pika.ExchangeType.DIRECT,
                durable=True,
                passive=False
            )

            self.events_exchange = await self.channel.declare_exchange(
                'game.events',
                aio_pika.ExchangeType.TOPIC,
                durable=True,
                passive=False
            )

            logger.info("✓ Command Publisher connected to RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to connect Command Publisher: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            logger.info("Command Publisher disconnected")

    async def publish_player_action(
        self,
        session_id: UUID,
        player_id: UUID,
        action: str,
        metadata: Dict[str, Any] = None
    ):
        """Publish a player action command"""
        try:
            message = {
                'message_id': str(uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'routing_key': f'game.player_action.{session_id}',
                'session_id': str(session_id),
                'campaign_id': '',  # Will be filled by orchestrator
                'event_type': 'player_action',
                'payload': {
                    'player_id': str(player_id),
                    'action': action,
                    'metadata': metadata or {}
                },
                'source_service': 'game-ui-gateway',
                'priority': 7
            }

            message_body = json.dumps(message, cls=UUIDEncoder).encode()

            aio_message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=7,
                content_type='application/json'
            )

            await self.events_exchange.publish(
                aio_message,
                routing_key=f'game.player_action.{session_id}'
            )

            logger.debug(f"Published player action: {action}")

        except Exception as e:
            logger.error(f"Error publishing player action: {e}")
            raise

    async def publish_team_chat(
        self,
        session_id: UUID,
        player_id: UUID,
        message: str,
        chat_type: str = 'team'
    ):
        """Publish a team chat message"""
        try:
            event = {
                'message_id': str(uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'routing_key': 'game.conversation.message',
                'session_id': str(session_id),
                'campaign_id': '',
                'event_type': 'conversation.message',
                'payload': {
                    'message_id': str(uuid4()),
                    'message_type': chat_type,
                    'sender': {
                        'type': 'player',
                        'id': str(player_id),
                        'name': ''  # Will be filled by orchestrator
                    },
                    'recipient': {
                        'type': 'all'
                    },
                    'content': {
                        'text': message
                    },
                    'timestamp': datetime.utcnow().isoformat()
                },
                'source_service': 'game-ui-gateway',
                'priority': 5
            }

            message_body = json.dumps(event, cls=UUIDEncoder).encode()

            aio_message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=5,
                content_type='application/json'
            )

            await self.events_exchange.publish(
                aio_message,
                routing_key='game.conversation.message'
            )

            logger.debug(f"Published team chat from player {player_id}")

        except Exception as e:
            logger.error(f"Error publishing team chat: {e}")
            raise

    async def publish_command(
        self,
        command_type: str,
        session_id: UUID,
        payload: Dict[str, Any]
    ):
        """Publish a generic command"""
        try:
            message = {
                'message_id': str(uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'command_type': command_type,
                'session_id': str(session_id),
                'payload': payload
            }

            message_body = json.dumps(message, cls=UUIDEncoder).encode()

            aio_message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type='application/json'
            )

            await self.commands_exchange.publish(
                aio_message,
                routing_key=command_type
            )

            logger.debug(f"Published command: {command_type}")

        except Exception as e:
            logger.error(f"Error publishing command: {e}")
            raise
