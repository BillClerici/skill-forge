"""
Redis Session State Manager
Handles session state caching and persistence
"""
import json
from typing import Optional, Dict, Any
from redis.asyncio import Redis
from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import GameSessionState

logger = get_logger(__name__)


class RedisSessionManager:
    """
    Manages game session state in Redis for fast access
    """

    def __init__(self):
        self.redis: Optional[Redis] = None
        self.ttl_seconds = settings.SESSION_STATE_TTL_SECONDS

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                encoding="utf-8"
            )
            await self.redis.ping()
            logger.info("redis_connected", url=settings.REDIS_URL)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("redis_disconnected")

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"session:state:{session_id}"

    def _session_lock_key(self, session_id: str) -> str:
        """Generate Redis lock key for session"""
        return f"session:lock:{session_id}"

    async def save_state(
        self,
        session_id: str,
        state: GameSessionState
    ) -> bool:
        """
        Save session state to Redis

        Args:
            session_id: Session ID
            state: Complete session state

        Returns:
            True if saved successfully
        """
        try:
            key = self._session_key(session_id)
            state_json = json.dumps(state, default=str)

            await self.redis.setex(
                key,
                self.ttl_seconds,
                state_json
            )

            logger.info(
                "session_state_saved",
                session_id=session_id,
                state_size_bytes=len(state_json)
            )
            return True

        except Exception as e:
            logger.error(
                "session_state_save_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def load_state(
        self,
        session_id: str
    ) -> Optional[GameSessionState]:
        """
        Load session state from Redis

        Args:
            session_id: Session ID

        Returns:
            Session state or None if not found
        """
        try:
            key = self._session_key(session_id)
            state_json = await self.redis.get(key)

            if not state_json:
                logger.warning(
                    "session_state_not_found",
                    session_id=session_id
                )
                return None

            state = json.loads(state_json)
            logger.info(
                "session_state_loaded",
                session_id=session_id
            )
            return state

        except Exception as e:
            logger.error(
                "session_state_load_failed",
                session_id=session_id,
                error=str(e)
            )
            return None

    async def delete_state(self, session_id: str) -> bool:
        """Delete session state from Redis"""
        try:
            key = self._session_key(session_id)
            await self.redis.delete(key)
            logger.info("session_state_deleted", session_id=session_id)
            return True
        except Exception as e:
            logger.error(
                "session_state_delete_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def acquire_lock(
        self,
        session_id: str,
        timeout: int = 30
    ) -> bool:
        """
        Acquire distributed lock for session

        Args:
            session_id: Session ID
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired
        """
        try:
            lock_key = self._session_lock_key(session_id)
            acquired = await self.redis.set(
                lock_key,
                "1",
                ex=timeout,
                nx=True  # Only set if not exists
            )
            return bool(acquired)
        except Exception as e:
            logger.error(
                "lock_acquire_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def release_lock(self, session_id: str) -> bool:
        """Release distributed lock for session"""
        try:
            lock_key = self._session_lock_key(session_id)
            await self.redis.delete(lock_key)
            return True
        except Exception as e:
            logger.error(
                "lock_release_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def extend_ttl(self, session_id: str) -> bool:
        """Extend session state TTL"""
        try:
            key = self._session_key(session_id)
            await self.redis.expire(key, self.ttl_seconds)
            return True
        except Exception as e:
            logger.error(
                "ttl_extend_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def get_active_sessions(self) -> list[str]:
        """Get list of all active session IDs"""
        try:
            pattern = "session:state:*"
            keys = await self.redis.keys(pattern)
            session_ids = [key.replace("session:state:", "") for key in keys]
            return session_ids
        except Exception as e:
            logger.error("get_active_sessions_failed", error=str(e))
            return []


# Global instance
redis_manager = RedisSessionManager()
