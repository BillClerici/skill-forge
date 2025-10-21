"""
RabbitMQ Event Publisher for Game Engine
Publishes game events to the event-driven architecture
"""
import aio_pika
import json
import logging
from typing import Dict, Any, Optional
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


class GameEventPublisher:
    """Publisher for game events to RabbitMQ"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.events_exchange: Optional[aio_pika.Exchange] = None
        self.is_connected = False

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.connection_string)
            self.channel = await self.connection.channel()

            # Declare events exchange
            self.events_exchange = await self.channel.declare_exchange(
                'game.events.exchange',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )

            self.is_connected = True
            logger.info("✓ Game Event Publisher connected to RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to connect Game Event Publisher: {e}")
            self.is_connected = False
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            self.is_connected = False
            logger.info("Game Event Publisher disconnected")

    async def publish_event(
        self,
        event_type: str,
        session_id: UUID,
        campaign_id: UUID,
        payload: Dict[str, Any],
        source: Dict[str, Any] = None,
        priority: int = 5
    ):
        """
        Publish a game event

        Args:
            event_type: Type of event (e.g., 'player.action', 'quest.completed')
            session_id: Game session ID
            campaign_id: Campaign ID
            payload: Event payload data
            source: Event source information
            priority: Message priority (0-9)
        """
        if not self.is_connected:
            logger.warning("Not connected to RabbitMQ, attempting to publish event offline")
            return

        try:
            # Construct event message
            message = {
                'message_id': str(uuid4()),
                'timestamp': datetime.utcnow().isoformat(),
                'routing_key': f'game.{event_type}',
                'session_id': str(session_id),
                'campaign_id': str(campaign_id),
                'event_type': event_type,
                'payload': payload,
                'source': source or {'type': 'system'},
                'source_service': 'game-engine',
                'priority': priority
            }

            # Convert to JSON
            message_body = json.dumps(message, cls=UUIDEncoder).encode()

            # Create AMQP message
            aio_message = aio_pika.Message(
                body=message_body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                priority=priority,
                content_type='application/json',
                timestamp=datetime.utcnow()
            )

            # Publish to exchange
            await self.events_exchange.publish(
                aio_message,
                routing_key=f'game.{event_type}'
            )

            logger.debug(f"Published event: {event_type} for session {session_id}")

        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            # Don't raise - we don't want to break game flow if event publishing fails

    # Convenience methods for specific event types

    async def publish_session_created(self, session_id: UUID, campaign_id: UUID, players: list):
        """Publish session created event"""
        await self.publish_event(
            'session.created',
            session_id,
            campaign_id,
            {
                'session_id': str(session_id),
                'campaign_id': str(campaign_id),
                'players': players,
                'created_at': datetime.utcnow().isoformat()
            },
            priority=8
        )

    async def publish_session_started(self, session_id: UUID, campaign_id: UUID):
        """Publish session started event"""
        await self.publish_event(
            'session.started',
            session_id,
            campaign_id,
            {
                'session_id': str(session_id),
                'started_at': datetime.utcnow().isoformat()
            },
            priority=7
        )

    async def publish_session_ended(self, session_id: UUID, campaign_id: UUID):
        """Publish session ended event"""
        await self.publish_event(
            'session.ended',
            session_id,
            campaign_id,
            {
                'session_id': str(session_id),
                'ended_at': datetime.utcnow().isoformat()
            },
            priority=6
        )

    async def publish_player_action(
        self,
        session_id: UUID,
        campaign_id: UUID,
        player_id: UUID,
        action: str,
        result: str = None
    ):
        """Publish player action event"""
        await self.publish_event(
            'player.action',
            session_id,
            campaign_id,
            {
                'player_id': str(player_id),
                'action': action,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            },
            source={'type': 'player', 'player_id': str(player_id)},
            priority=7
        )

    async def publish_conversation_message(
        self,
        session_id: UUID,
        campaign_id: UUID,
        message_id: UUID,
        message_type: str,
        sender: Dict[str, Any],
        content: Dict[str, Any]
    ):
        """Publish conversation message event"""
        await self.publish_event(
            'conversation.message',
            session_id,
            campaign_id,
            {
                'message_id': str(message_id),
                'message_type': message_type,
                'sender': sender,
                'recipient': {'type': 'all'},
                'content': content,
                'timestamp': datetime.utcnow().isoformat()
            },
            source=sender,
            priority=6
        )

    async def publish_quest_started(
        self,
        session_id: UUID,
        campaign_id: UUID,
        quest_id: UUID,
        quest_name: str
    ):
        """Publish quest started event"""
        await self.publish_event(
            'quest.started',
            session_id,
            campaign_id,
            {
                'quest_id': str(quest_id),
                'quest_name': quest_name,
                'started_at': datetime.utcnow().isoformat()
            },
            priority=7
        )

    async def publish_quest_objective_completed(
        self,
        session_id: UUID,
        campaign_id: UUID,
        quest_id: UUID,
        objective_id: str,
        progress: float
    ):
        """Publish quest objective completed event"""
        await self.publish_event(
            'quest.objective_completed',
            session_id,
            campaign_id,
            {
                'quest_id': str(quest_id),
                'objective_id': objective_id,
                'progress': progress,
                'completed_at': datetime.utcnow().isoformat()
            },
            priority=7
        )

    async def publish_quest_completed(
        self,
        session_id: UUID,
        campaign_id: UUID,
        quest_id: UUID,
        rewards: Dict[str, Any]
    ):
        """Publish quest completed event"""
        await self.publish_event(
            'quest.completed',
            session_id,
            campaign_id,
            {
                'quest_id': str(quest_id),
                'rewards': rewards,
                'completed_at': datetime.utcnow().isoformat()
            },
            priority=8
        )

    async def publish_discovery_found(
        self,
        session_id: UUID,
        campaign_id: UUID,
        player_id: UUID,
        discovery_id: UUID,
        discovery_name: str,
        knowledge_gained: list
    ):
        """Publish discovery found event"""
        await self.publish_event(
            'discovery.found',
            session_id,
            campaign_id,
            {
                'player_id': str(player_id),
                'discovery_id': str(discovery_id),
                'discovery_name': discovery_name,
                'knowledge_gained': knowledge_gained,
                'timestamp': datetime.utcnow().isoformat()
            },
            source={'type': 'player', 'player_id': str(player_id)},
            priority=7
        )

    async def publish_scene_changed(
        self,
        session_id: UUID,
        campaign_id: UUID,
        old_scene_id: Optional[UUID],
        new_scene_id: UUID,
        scene_description: str,
        available_npcs: list,
        available_actions: list
    ):
        """Publish scene changed event"""
        await self.publish_event(
            'scene.changed',
            session_id,
            campaign_id,
            {
                'old_scene_id': str(old_scene_id) if old_scene_id else None,
                'new_scene_id': str(new_scene_id),
                'scene_description': scene_description,
                'available_npcs': available_npcs,
                'available_actions': available_actions,
                'timestamp': datetime.utcnow().isoformat()
            },
            priority=6
        )

    async def publish_npc_interaction(
        self,
        session_id: UUID,
        campaign_id: UUID,
        player_id: UUID,
        npc_id: UUID,
        interaction_type: str,
        outcome: str
    ):
        """Publish NPC interaction event"""
        await self.publish_event(
            'npc.interaction',
            session_id,
            campaign_id,
            {
                'player_id': str(player_id),
                'npc_id': str(npc_id),
                'interaction_type': interaction_type,
                'outcome': outcome,
                'timestamp': datetime.utcnow().isoformat()
            },
            source={'type': 'player', 'player_id': str(player_id)},
            priority=6
        )
