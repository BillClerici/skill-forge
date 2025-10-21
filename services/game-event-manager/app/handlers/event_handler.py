"""
Event handlers for processing different event types
"""
import logging
from typing import Dict, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class EventHandler:
    """Base event handler"""

    def __init__(self, rabbitmq_service):
        self.rabbitmq = rabbitmq_service

    async def handle(self, event: Dict[str, Any]):
        """Handle an event - to be overridden by subclasses"""
        raise NotImplementedError


class SessionEventHandler(EventHandler):
    """Handler for session events"""

    async def handle(self, event: Dict[str, Any]):
        """Handle session events"""
        event_type = event['event_type']

        if event_type == 'session.created':
            await self._handle_session_created(event)
        elif event_type == 'session.started':
            await self._handle_session_started(event)
        elif event_type == 'session.ended':
            await self._handle_session_ended(event)

    async def _handle_session_created(self, event: Dict[str, Any]):
        """Handle session created event"""
        session_id = UUID(event['session_id'])

        # Create session-specific UI queue
        await self.rabbitmq.create_session_queue(session_id)

        logger.info(f"Session created: {session_id}")

    async def _handle_session_started(self, event: Dict[str, Any]):
        """Handle session started event"""
        logger.info(f"Session started: {event['session_id']}")

    async def _handle_session_ended(self, event: Dict[str, Any]):
        """Handle session ended event"""
        session_id = UUID(event['session_id'])

        # Clean up session queue after a delay
        # In production, you might want to keep it for a bit longer
        # await self.rabbitmq.delete_session_queue(session_id)

        logger.info(f"Session ended: {session_id}")


class PlayerEventHandler(EventHandler):
    """Handler for player events"""

    async def handle(self, event: Dict[str, Any]):
        """Handle player events"""
        event_type = event['event_type']

        if event_type == 'player.action':
            await self._handle_player_action(event)
        elif event_type == 'player.joined':
            await self._handle_player_joined(event)
        elif event_type == 'player.disconnected':
            await self._handle_player_disconnected(event)

    async def _handle_player_action(self, event: Dict[str, Any]):
        """Handle player action event"""
        logger.info(f"Player action: {event['payload'].get('action', 'unknown')}")

    async def _handle_player_joined(self, event: Dict[str, Any]):
        """Handle player joined event"""
        logger.info(f"Player joined: {event['payload'].get('player_id', 'unknown')}")

    async def _handle_player_disconnected(self, event: Dict[str, Any]):
        """Handle player disconnected event"""
        logger.info(f"Player disconnected: {event['payload'].get('player_id', 'unknown')}")


class QuestEventHandler(EventHandler):
    """Handler for quest events"""

    async def handle(self, event: Dict[str, Any]):
        """Handle quest events"""
        event_type = event['event_type']

        if event_type == 'quest.started':
            await self._handle_quest_started(event)
        elif event_type == 'quest.objective_completed':
            await self._handle_objective_completed(event)
        elif event_type == 'quest.completed':
            await self._handle_quest_completed(event)

    async def _handle_quest_started(self, event: Dict[str, Any]):
        """Handle quest started event"""
        logger.info(f"Quest started: {event['payload'].get('quest_id', 'unknown')}")

    async def _handle_objective_completed(self, event: Dict[str, Any]):
        """Handle objective completed event"""
        logger.info(f"Objective completed: {event['payload'].get('objective_id', 'unknown')}")

    async def _handle_quest_completed(self, event: Dict[str, Any]):
        """Handle quest completed event"""
        logger.info(f"Quest completed: {event['payload'].get('quest_id', 'unknown')}")

        # Publish UI update
        await self.rabbitmq.publish_event(
            'game.ui',
            f"ui.session.{event['session_id']}.quest_completed",
            event
        )


class DiscoveryEventHandler(EventHandler):
    """Handler for discovery events"""

    async def handle(self, event: Dict[str, Any]):
        """Handle discovery events"""
        logger.info(f"Discovery found: {event['payload'].get('discovery_name', 'unknown')}")

        # Publish UI notification
        await self.rabbitmq.publish_event(
            'game.ui',
            f"ui.session.{event['session_id']}.notification",
            {
                'type': 'discovery',
                'message': f"Discovery: {event['payload'].get('discovery_name', 'Unknown')}",
                'data': event['payload']
            }
        )


class ConversationEventHandler(EventHandler):
    """Handler for conversation events"""

    async def handle(self, event: Dict[str, Any]):
        """Handle conversation events"""
        message_type = event['payload'].get('message_type', 'unknown')
        logger.debug(f"Conversation message: {message_type}")

        # Publish to UI
        await self.rabbitmq.publish_event(
            'game.ui',
            f"ui.session.{event['session_id']}.chat_message",
            event['payload']
        )
