"""
RabbitMQ consumer for persistence
"""
import logging
from typing import Dict, Any
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


class PersistenceConsumer:
    """Consumer for persisting game events to MongoDB"""

    def __init__(self, session_repo, event_repo, conversation_repo, inventory_repo):
        self.session_repo = session_repo
        self.event_repo = event_repo
        self.conversation_repo = conversation_repo
        self.inventory_repo = inventory_repo

    async def process_event(self, event: Dict[str, Any]):
        """Process an event from RabbitMQ"""
        try:
            event_type = event.get('event_type', '')

            # Always save the event
            await self._save_event(event)

            # Handle specific event types
            if event_type == 'session.created':
                await self._handle_session_created(event)
            elif event_type == 'session.started':
                await self._handle_session_started(event)
            elif event_type == 'session.ended':
                await self._handle_session_ended(event)
            elif event_type == 'conversation.message':
                await self._handle_conversation_message(event)
            elif event_type == 'item.acquired':
                await self._handle_item_acquired(event)
            elif event_type == 'knowledge.gained':
                await self._handle_knowledge_gained(event)
            elif event_type == 'quest.objective_completed':
                await self._handle_quest_objective(event)
            elif event_type == 'scene.changed':
                await self._handle_scene_changed(event)

            # Increment event counter
            await self.session_repo.increment_index(
                UUID(event['session_id']),
                'event_count'
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    async def _save_event(self, event: Dict[str, Any]):
        """Save event to game_events collection"""
        try:
            event_data = {
                'session_id': event['session_id'],
                'event_id': event.get('message_id', event.get('event_id')),
                'timestamp': event.get('timestamp', datetime.utcnow()),
                'event_type': event['event_type'],
                'source': event.get('source', {'type': 'system'}),
                'data': event.get('payload', {}),
                'state_changes': event.get('state_changes'),
                'ai_context': event.get('ai_context')
            }

            await self.event_repo.create_event(event_data)

        except Exception as e:
            logger.error(f"Error saving event: {e}")

    async def _handle_session_created(self, event: Dict[str, Any]):
        """Handle session created event"""
        try:
            payload = event['payload']

            from ..models.session import GameSessionV2, PlayerSessionData

            # Process players and set default timestamps
            players = []
            for p in payload.get('players', []):
                player_data = p.copy()
                # Set timestamps if not provided
                if not player_data.get('joined_at'):
                    player_data['joined_at'] = datetime.utcnow()
                if not player_data.get('last_seen_at'):
                    player_data['last_seen_at'] = datetime.utcnow()
                players.append(PlayerSessionData(**player_data))

            # Create session document
            session = GameSessionV2(
                session_id=UUID(event['session_id']),
                campaign_id=str(payload['campaign_id']),  # Keep as string (MongoDB ObjectId)
                players=players,
                status='active'
            )

            await self.session_repo.create_session(session)
            logger.info(f"✓ Created session {event['session_id']} for campaign {payload['campaign_id']}")

        except Exception as e:
            logger.error(f"Error handling session created: {e}", exc_info=True)

    async def _handle_session_started(self, event: Dict[str, Any]):
        """Handle session started event"""
        try:
            await self.session_repo.update_session(
                UUID(event['session_id']),
                {'started_at': datetime.utcnow()}
            )
        except Exception as e:
            logger.error(f"Error handling session started: {e}")

    async def _handle_session_ended(self, event: Dict[str, Any]):
        """Handle session ended event"""
        try:
            await self.session_repo.update_session(
                UUID(event['session_id']),
                {
                    'ended_at': datetime.utcnow(),
                    'status': 'completed'
                }
            )
        except Exception as e:
            logger.error(f"Error handling session ended: {e}")

    async def _handle_conversation_message(self, event: Dict[str, Any]):
        """Handle conversation message event"""
        try:
            payload = event['payload']

            message_data = {
                'session_id': event['session_id'],
                'message_id': payload.get('message_id'),
                'timestamp': payload.get('timestamp', datetime.utcnow()),
                'message_type': payload.get('message_type'),
                'sender': payload.get('sender'),
                'recipient': payload.get('recipient'),
                'content': payload.get('content'),
                'related_event_id': payload.get('related_event_id'),
                'scene_id': payload.get('scene_id'),
                'quest_id': payload.get('quest_id')
            }

            await self.conversation_repo.create_message(message_data)
            await self.session_repo.increment_index(
                UUID(event['session_id']),
                'conversation_count'
            )

        except Exception as e:
            logger.error(f"Error handling conversation message: {e}")

    async def _handle_item_acquired(self, event: Dict[str, Any]):
        """Handle item acquired event"""
        # This would update the player inventory
        # Implementation depends on your specific needs
        pass

    async def _handle_knowledge_gained(self, event: Dict[str, Any]):
        """Handle knowledge gained event"""
        # This would update the player inventory/knowledge
        pass

    async def _handle_quest_objective(self, event: Dict[str, Any]):
        """Handle quest objective completed"""
        try:
            payload = event['payload']

            # Update session progress
            # This is simplified - you'd want to merge with existing progress
            progress_data = {
                'quest_objectives_status': payload.get('quest_objectives_status', {})
            }

            # Note: In production, you'd want to do a more sophisticated merge
            # await self.session_repo.update_progress(
            #     UUID(event['session_id']),
            #     progress_data
            # )

        except Exception as e:
            logger.error(f"Error handling quest objective: {e}")

    async def _handle_scene_changed(self, event: Dict[str, Any]):
        """Handle scene changed event"""
        try:
            payload = event['payload']

            state_data = {
                'scene_description': payload.get('scene_description'),
                'available_npcs': payload.get('available_npcs', []),
                'available_actions': payload.get('available_actions', [])
            }

            await self.session_repo.update_current_state(
                UUID(event['session_id']),
                state_data
            )

        except Exception as e:
            logger.error(f"Error handling scene changed: {e}")
