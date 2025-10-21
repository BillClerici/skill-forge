"""
Auto-Save Manager
Handles periodic game state saves and checkpoints
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from ..core.config import settings
from ..core.logging import get_logger
from ..services.redis_manager import redis_manager
from ..services.mongo_persistence import mongo_persistence
from ..models.state import GameSessionState

logger = get_logger(__name__)


class AutoSaveManager:
    """
    Manages automatic saving of game sessions
    """

    def __init__(self):
        # Track auto-save tasks
        self.autosave_tasks: Dict[str, asyncio.Task] = {}

        # Auto-save interval
        self.save_interval_seconds = settings.AUTOSAVE_INTERVAL_SECONDS

    async def start_autosave(self, session_id: str):
        """
        Start auto-save for a session

        Args:
            session_id: Session ID
        """
        try:
            # Cancel existing autosave if any
            if session_id in self.autosave_tasks:
                self.autosave_tasks[session_id].cancel()

            # Create new autosave task
            self.autosave_tasks[session_id] = asyncio.create_task(
                self._autosave_loop(session_id)
            )

            logger.info(
                "autosave_started",
                session_id=session_id,
                interval_seconds=self.save_interval_seconds
            )

        except Exception as e:
            logger.error("autosave_start_failed", error=str(e))

    async def stop_autosave(self, session_id: str):
        """
        Stop auto-save for a session

        Args:
            session_id: Session ID
        """
        try:
            if session_id in self.autosave_tasks:
                self.autosave_tasks[session_id].cancel()
                del self.autosave_tasks[session_id]

                logger.info("autosave_stopped", session_id=session_id)

        except Exception as e:
            logger.error("autosave_stop_failed", error=str(e))

    async def _autosave_loop(self, session_id: str):
        """
        Auto-save loop for a session

        Args:
            session_id: Session ID
        """
        save_count = 0

        try:
            while True:
                await asyncio.sleep(self.save_interval_seconds)

                # Perform save
                success = await self.save_checkpoint(session_id)

                if success:
                    save_count += 1
                    logger.info(
                        "autosave_completed",
                        session_id=session_id,
                        save_count=save_count
                    )
                else:
                    logger.warning(
                        "autosave_failed",
                        session_id=session_id
                    )

        except asyncio.CancelledError:
            logger.info("autosave_loop_cancelled", session_id=session_id)
            raise

        except Exception as e:
            logger.error(
                "autosave_loop_error",
                session_id=session_id,
                error=str(e)
            )

    async def save_checkpoint(self, session_id: str) -> bool:
        """
        Save checkpoint of current game state

        Args:
            session_id: Session ID

        Returns:
            Success status
        """
        try:
            # Load state from Redis
            state = await redis_manager.load_state(session_id)

            if not state:
                logger.warning("no_state_to_save", session_id=session_id)
                return False

            # Save to MongoDB
            success = await mongo_persistence.save_session(state)

            if success:
                # Save chat messages batch
                chat_messages = state.get("chat_messages", [])
                if chat_messages:
                    # Only save new messages since last save
                    # For simplicity, save all for now (could optimize with tracking)
                    await mongo_persistence.save_chat_messages_batch(
                        session_id,
                        chat_messages
                    )

                # Update checkpoint metadata in state
                state["last_checkpoint"] = datetime.utcnow().isoformat()
                state["checkpoint_count"] = state.get("checkpoint_count", 0) + 1

                # Update Redis
                await redis_manager.save_state(session_id, state)

                logger.info(
                    "checkpoint_saved",
                    session_id=session_id,
                    checkpoint_count=state["checkpoint_count"]
                )

                return True
            else:
                return False

        except Exception as e:
            logger.error(
                "checkpoint_save_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def create_manual_save(
        self,
        session_id: str,
        save_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create manual save point

        Args:
            session_id: Session ID
            save_name: Optional name for save

        Returns:
            Save information
        """
        try:
            # Load state
            state = await redis_manager.load_state(session_id)

            if not state:
                return {
                    "success": False,
                    "error": "Session not found"
                }

            # Create save
            save_id = f"save_{datetime.utcnow().timestamp()}"
            save_name = save_name or f"Manual Save {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

            save_data = {
                "save_id": save_id,
                "save_name": save_name,
                "session_id": session_id,
                "saved_at": datetime.utcnow().isoformat(),
                "state_snapshot": state,
                "metadata": {
                    "quest_progress": len(state.get("completed_quest_ids", [])),
                    "total_actions": len(state.get("action_history", [])),
                    "game_time": state.get("elapsed_game_time", 0),
                    "players": [p.get("character_name") for p in state.get("players", [])]
                }
            }

            # Save to MongoDB
            await mongo_persistence.db.save_points.insert_one(save_data)

            # Save full checkpoint
            await self.save_checkpoint(session_id)

            logger.info(
                "manual_save_created",
                session_id=session_id,
                save_id=save_id,
                save_name=save_name
            )

            return {
                "success": True,
                "save_id": save_id,
                "save_name": save_name,
                "saved_at": save_data["saved_at"]
            }

        except Exception as e:
            logger.error("manual_save_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def load_save_point(
        self,
        save_id: str
    ) -> Optional[GameSessionState]:
        """
        Load game from save point

        Args:
            save_id: Save ID

        Returns:
            Game state or None
        """
        try:
            # Load save from MongoDB
            save_data = await mongo_persistence.db.save_points.find_one({"save_id": save_id})

            if not save_data:
                logger.warning("save_point_not_found", save_id=save_id)
                return None

            state = save_data.get("state_snapshot")

            # Update state with load information
            state["loaded_from_save"] = save_id
            state["loaded_at"] = datetime.utcnow().isoformat()

            # Save to Redis
            session_id = state.get("session_id")
            await redis_manager.save_state(session_id, state)

            logger.info(
                "save_point_loaded",
                save_id=save_id,
                session_id=session_id
            )

            return state

        except Exception as e:
            logger.error("save_point_load_failed", error=str(e))
            return None

    async def list_save_points(self, session_id: str) -> List[Dict[str, Any]]:
        """List all save points for a session"""
        try:
            cursor = mongo_persistence.db.save_points.find(
                {"session_id": session_id}
            ).sort("saved_at", -1)

            saves = []
            async for doc in cursor:
                saves.append({
                    "save_id": doc["save_id"],
                    "save_name": doc["save_name"],
                    "saved_at": doc["saved_at"],
                    "metadata": doc.get("metadata", {})
                })

            return saves

        except Exception as e:
            logger.error("list_saves_failed", error=str(e))
            return []

    async def delete_save_point(self, save_id: str) -> bool:
        """Delete a save point"""
        try:
            result = await mongo_persistence.db.save_points.delete_one({"save_id": save_id})

            if result.deleted_count > 0:
                logger.info("save_point_deleted", save_id=save_id)
                return True
            else:
                logger.warning("save_point_not_found_for_delete", save_id=save_id)
                return False

        except Exception as e:
            logger.error("save_deletion_failed", error=str(e))
            return False


# Global instance
autosave_manager = AutoSaveManager()
