"""
Event repository for MongoDB operations
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class EventRepository:
    """Repository for event operations"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db['game_events']
        self.sequence_collection = db['event_sequences']

    async def get_next_sequence_number(self, session_id: UUID) -> int:
        """Get the next sequence number for a session"""
        try:
            result = await self.sequence_collection.find_one_and_update(
                {'session_id': str(session_id)},
                {'$inc': {'sequence': 1}},
                upsert=True,
                return_document=True
            )

            return result['sequence']

        except Exception as e:
            logger.error(f"Error getting sequence number: {e}")
            return 1

    async def create_event(self, event_data: Dict[str, Any]) -> bool:
        """Create a new event"""
        try:
            # Convert UUIDs to strings
            if 'session_id' in event_data:
                event_data['session_id'] = str(event_data['session_id'])
            if 'event_id' in event_data:
                event_data['event_id'] = str(event_data['event_id'])

            # Get sequence number if not provided
            if 'sequence_number' not in event_data:
                event_data['sequence_number'] = await self.get_next_sequence_number(
                    UUID(event_data['session_id'])
                )

            # Insert
            await self.collection.insert_one(event_data)

            logger.debug(f"Created event: {event_data.get('event_id')}")
            return True

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return False

    async def get_events(
        self,
        session_id: UUID,
        event_type: Optional[str] = None,
        player_id: Optional[UUID] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get events for a session"""
        try:
            # Build query
            query = {'session_id': str(session_id)}

            if event_type:
                query['event_type'] = event_type

            if player_id:
                query['source.player_id'] = str(player_id)

            # Execute query
            cursor = self.collection.find(query).sort('sequence_number', 1).skip(skip).limit(limit)

            events = await cursor.to_list(length=limit)
            return events

        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []

    async def get_events_by_sequence_range(
        self,
        session_id: UUID,
        start_sequence: int,
        end_sequence: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get events in a sequence range"""
        try:
            query = {
                'session_id': str(session_id),
                'sequence_number': {'$gte': start_sequence}
            }

            if end_sequence:
                query['sequence_number']['$lte'] = end_sequence

            cursor = self.collection.find(query).sort('sequence_number', 1)

            events = await cursor.to_list(length=None)
            return events

        except Exception as e:
            logger.error(f"Error getting events by sequence: {e}")
            return []

    async def get_event_count(self, session_id: UUID, event_type: Optional[str] = None) -> int:
        """Get count of events"""
        try:
            query = {'session_id': str(session_id)}

            if event_type:
                query['event_type'] = event_type

            count = await self.collection.count_documents(query)
            return count

        except Exception as e:
            logger.error(f"Error getting event count: {e}")
            return 0

    async def get_latest_events(
        self,
        session_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get the latest events for a session"""
        try:
            cursor = self.collection.find(
                {'session_id': str(session_id)}
            ).sort('sequence_number', -1).limit(limit)

            events = await cursor.to_list(length=limit)

            # Reverse to get chronological order
            return list(reversed(events))

        except Exception as e:
            logger.error(f"Error getting latest events: {e}")
            return []
