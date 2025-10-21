"""
Session repository for MongoDB operations
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import logging

from ..models.session import GameSessionV2

logger = logging.getLogger(__name__)


class SessionRepository:
    """Repository for session operations"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db['game_sessions_v2']

    async def create_session(self, session: GameSessionV2) -> bool:
        """Create a new session"""
        try:
            # Convert to dict
            session_dict = session.dict()

            # Convert UUIDs to strings for MongoDB
            session_dict['session_id'] = str(session_dict['session_id'])
            session_dict['campaign_id'] = str(session_dict['campaign_id'])

            # Convert player IDs
            for player in session_dict.get('players', []):
                player['player_id'] = str(player['player_id'])
                player['character_id'] = str(player['character_id'])

            # Insert
            await self.collection.insert_one(session_dict)

            logger.info(f"Created session: {session.session_id}")
            return True

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False

    async def get_session(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a session by ID"""
        try:
            session = await self.collection.find_one(
                {'session_id': str(session_id)},
                {'_id': 0}  # Exclude MongoDB _id field
            )
            return session

        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None

    async def update_session(self, session_id: UUID, update_data: Dict[str, Any]) -> bool:
        """Update a session"""
        try:
            # Add updated_at timestamp
            update_data['updated_at'] = datetime.utcnow()

            # Update
            result = await self.collection.update_one(
                {'session_id': str(session_id)},
                {'$set': update_data}
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False

    async def update_session_status(self, session_id: UUID, status: str) -> bool:
        """Update session status"""
        return await self.update_session(session_id, {'status': status})

    async def increment_index(self, session_id: UUID, index_name: str) -> bool:
        """Increment an index counter"""
        try:
            result = await self.collection.update_one(
                {'session_id': str(session_id)},
                {
                    '$inc': {f'indices.{index_name}': 1},
                    '$set': {'updated_at': datetime.utcnow()}
                }
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error incrementing index: {e}")
            return False

    async def get_active_sessions_for_player(self, player_id: UUID) -> List[Dict[str, Any]]:
        """Get all active sessions for a player"""
        try:
            cursor = self.collection.find(
                {
                    'players.player_id': str(player_id),
                    'status': 'active'
                },
                {'_id': 0}  # Exclude MongoDB _id field
            ).sort('updated_at', -1)

            sessions = await cursor.to_list(length=100)
            return sessions

        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    async def get_completed_sessions_for_player(self, player_id: UUID) -> List[Dict[str, Any]]:
        """Get all completed sessions for a player"""
        try:
            cursor = self.collection.find(
                {
                    'players.player_id': str(player_id),
                    'status': 'completed'
                },
                {'_id': 0}  # Exclude MongoDB _id field
            ).sort('ended_at', -1)

            sessions = await cursor.to_list(length=100)
            return sessions

        except Exception as e:
            logger.error(f"Error getting completed sessions: {e}")
            return []

    async def update_progress(self, session_id: UUID, progress_data: Dict[str, Any]) -> bool:
        """Update session progress"""
        try:
            result = await self.collection.update_one(
                {'session_id': str(session_id)},
                {
                    '$set': {
                        'progress': progress_data,
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating progress: {e}")
            return False

    async def update_current_state(self, session_id: UUID, state_data: Dict[str, Any]) -> bool:
        """Update current game state"""
        try:
            result = await self.collection.update_one(
                {'session_id': str(session_id)},
                {
                    '$set': {
                        'current_state': state_data,
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating current state: {e}")
            return False
