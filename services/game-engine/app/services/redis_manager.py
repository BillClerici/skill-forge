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

    # ===================================
    # PERFORMANCE OPTIMIZATION: Generic Data Caching
    # ===================================

    async def cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data from Redis

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found
        """
        try:
            cached = await self.redis.get(key)
            if cached:
                logger.debug("cache_hit", key=key)
                return json.loads(cached)
            logger.debug("cache_miss", key=key)
            return None
        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
            return None

    async def cache_set(self, key: str, data: Dict[str, Any], ttl_seconds: int = 3600) -> bool:
        """
        Set cached data in Redis

        Args:
            key: Cache key
            data: Data to cache
            ttl_seconds: Time to live in seconds (default 1 hour)

        Returns:
            True if cached successfully
        """
        try:
            data_json = json.dumps(data, default=str)
            await self.redis.setex(key, ttl_seconds, data_json)
            logger.debug("cache_set", key=key, ttl_seconds=ttl_seconds, size_bytes=len(data_json))
            return True
        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False

    async def cache_delete(self, key: str) -> bool:
        """
        Delete cached data from Redis

        Args:
            key: Cache key

        Returns:
            True if deleted successfully
        """
        try:
            await self.redis.delete(key)
            logger.debug("cache_deleted", key=key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False

    async def cache_get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get cached campaign data"""
        return await self.cache_get(f"campaign:{campaign_id}")

    async def cache_set_campaign(self, campaign_id: str, data: Dict[str, Any]) -> bool:
        """Cache campaign data (1 hour TTL)"""
        return await self.cache_set(f"campaign:{campaign_id}", data, ttl_seconds=3600)

    async def cache_get_quest(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get cached quest data"""
        return await self.cache_get(f"quest:{quest_id}")

    async def cache_set_quest(self, quest_id: str, data: Dict[str, Any]) -> bool:
        """Cache quest data (1 hour TTL)"""
        return await self.cache_set(f"quest:{quest_id}", data, ttl_seconds=3600)

    async def cache_get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """Get cached world data"""
        return await self.cache_get(f"world:{world_id}")

    async def cache_set_world(self, world_id: str, data: Dict[str, Any]) -> bool:
        """Cache world data (1 hour TTL)"""
        return await self.cache_set(f"world:{world_id}", data, ttl_seconds=3600)


# Global instance
redis_manager = RedisSessionManager()
