"""
Conversation repository for MongoDB operations
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation operations"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db['game_conversations']
        self.sequence_collection = db['conversation_sequences']

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

    async def create_message(self, message_data: Dict[str, Any]) -> bool:
        """Create a new conversation message"""
        try:
            # Convert UUIDs
            if 'session_id' in message_data:
                message_data['session_id'] = str(message_data['session_id'])
            if 'message_id' in message_data:
                message_data['message_id'] = str(message_data['message_id'])

            # Get sequence number
            if 'sequence_number' not in message_data:
                message_data['sequence_number'] = await self.get_next_sequence_number(
                    UUID(message_data['session_id'])
                )

            await self.collection.insert_one(message_data)
            return True
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return False

    async def get_messages(
        self,
        session_id: UUID,
        message_type: str = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get conversation messages"""
        try:
            query = {'session_id': str(session_id)}
            if message_type:
                query['message_type'] = message_type

            cursor = self.collection.find(query).sort('sequence_number', 1).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
