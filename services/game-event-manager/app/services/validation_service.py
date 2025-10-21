"""
Event validation service
"""
import logging
from typing import Dict, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for validating events"""

    @staticmethod
    def validate_event(event: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate an event

        Args:
            event: Event dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check required fields
            required_fields = ['session_id', 'event_type', 'payload']
            for field in required_fields:
                if field not in event:
                    return False, f"Missing required field: {field}"

            # Validate session_id is a valid UUID
            try:
                UUID(str(event['session_id']))
            except (ValueError, AttributeError):
                return False, "Invalid session_id format"

            # Validate event_type
            valid_event_types = [
                'session.created',
                'session.started',
                'session.ended',
                'player.joined',
                'player.action',
                'player.disconnected',
                'conversation.message',
                'quest.started',
                'quest.objective_completed',
                'quest.completed',
                'discovery.found',
                'challenge.initiated',
                'challenge.completed',
                'npc.interaction',
                'item.acquired',
                'knowledge.gained',
                'scene.changed',
                'world.modified'
            ]

            if event['event_type'] not in valid_event_types:
                return False, f"Invalid event_type: {event['event_type']}"

            # Validate payload is a dictionary
            if not isinstance(event['payload'], dict):
                return False, "Payload must be a dictionary"

            return True, ""

        except Exception as e:
            logger.error(f"Error validating event: {e}")
            return False, str(e)

    @staticmethod
    def enrich_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich an event with additional metadata

        Args:
            event: Event dictionary

        Returns:
            Enriched event
        """
        from datetime import datetime
        from uuid import uuid4

        # Add timestamp if not present
        if 'timestamp' not in event:
            event['timestamp'] = datetime.utcnow().isoformat()

        # Add message_id if not present
        if 'message_id' not in event:
            event['message_id'] = str(uuid4())

        # Add source_service if not present
        if 'source_service' not in event:
            event['source_service'] = 'game-event-manager'

        # Add priority if not present
        if 'priority' not in event:
            event['priority'] = 5

        # Generate routing key based on event type
        if 'routing_key' not in event:
            event['routing_key'] = f"game.{event['event_type']}"

        return event

    @staticmethod
    def get_routing_key(event_type: str) -> str:
        """
        Get the routing key for an event type

        Args:
            event_type: Event type (e.g., 'player.action')

        Returns:
            Routing key for RabbitMQ (e.g., 'game.player.action')
        """
        return f"game.{event_type}"
