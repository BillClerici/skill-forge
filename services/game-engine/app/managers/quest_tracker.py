"""
Quest Progression Tracker
Monitors quest objectives, triggers events, and tracks campaign progress
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..core.logging import get_logger
from ..models.state import GameSessionState
from ..services.mcp_client import mcp_client
from ..services.neo4j_graph import neo4j_graph
from ..api.websocket_manager import connection_manager

logger = get_logger(__name__)


class QuestProgressionTracker:
    """
    Tracks and manages quest progression
    """

    def __init__(self):
        # Cache quest data
        self.quest_cache: Dict[str, Dict[str, Any]] = {}

    async def check_quest_objectives(
        self,
        session_id: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Check if quest objectives are completed

        Args:
            session_id: Session ID
            state: Game session state

        Returns:
            Quest progress information
        """
        try:
            current_quest_id = state.get("current_quest_id")

            if not current_quest_id:
                return {
                    "quest_active": False,
                    "objectives_met": False
                }

            # Get quest data
            quest_data = await self._get_quest_data(current_quest_id)

            if not quest_data:
                logger.warning("quest_data_not_found", quest_id=current_quest_id)
                return {
                    "quest_active": False,
                    "objectives_met": False
                }

            # Check objectives
            objectives = quest_data.get("objectives", [])
            objectives_status = []

            for objective in objectives:
                status = await self._check_objective(objective, state)
                objectives_status.append(status)

            # Determine if quest is complete
            all_objectives_met = all(obj["completed"] for obj in objectives_status)

            # Calculate completion percentage
            completed_count = sum(1 for obj in objectives_status if obj["completed"])
            completion_percentage = int((completed_count / len(objectives)) * 100) if objectives else 0

            # Update Neo4j with progress
            player = state.get("players", [{}])[0]
            player_id = player.get("player_id", "")

            await neo4j_graph.record_quest_progress(
                player_id,
                current_quest_id,
                quest_data.get("title", "Unknown"),
                "completed" if all_objectives_met else "in_progress",
                completion_percentage
            )

            progress_info = {
                "quest_active": True,
                "quest_id": current_quest_id,
                "quest_title": quest_data.get("title"),
                "objectives": objectives_status,
                "objectives_met": all_objectives_met,
                "completion_percentage": completion_percentage
            }

            # If quest complete, trigger completion
            if all_objectives_met and current_quest_id not in state.get("completed_quest_ids", []):
                await self._complete_quest(session_id, current_quest_id, state, quest_data)

            logger.info(
                "quest_objectives_checked",
                session_id=session_id,
                quest_id=current_quest_id,
                completion=completion_percentage
            )

            return progress_info

        except Exception as e:
            logger.error(
                "quest_check_failed",
                session_id=session_id,
                error=str(e)
            )
            return {
                "quest_active": False,
                "objectives_met": False,
                "error": str(e)
            }

    async def _get_quest_data(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get quest data from cache or MCP"""
        if quest_id in self.quest_cache:
            return self.quest_cache[quest_id]

        quest_data = await mcp_client.get_quest(quest_id)

        if quest_data:
            self.quest_cache[quest_id] = quest_data

        return quest_data

    async def _check_objective(
        self,
        objective: Dict[str, Any],
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Check if a single objective is completed

        Args:
            objective: Objective data
            state: Game session state

        Returns:
            Objective status
        """
        objective_type = objective.get("type")
        objective_id = objective.get("objective_id")

        completed = False
        current_value = 0
        target_value = objective.get("target_value", 1)

        if objective_type == "talk_to_npc":
            # Check if player talked to specific NPC
            target_npc = objective.get("target_npc_id")
            conversation_history = state.get("conversation_history", [])

            talked_to_npc = any(
                conv.get("npc_id") == target_npc
                for conv in conversation_history
            )

            completed = talked_to_npc
            current_value = 1 if talked_to_npc else 0

        elif objective_type == "visit_location":
            # Check if player visited location
            target_location = objective.get("target_location_id")
            completed = target_location in state.get("completed_scene_ids", [])
            current_value = 1 if completed else 0

        elif objective_type == "collect_item":
            # Check if player has item
            target_item = objective.get("target_item_id")
            player_inventories = state.get("player_inventories", {})

            for inventory in player_inventories.values():
                if target_item in inventory:
                    current_value += 1

            completed = current_value >= target_value

        elif objective_type == "complete_challenge":
            # Check if challenge was completed
            target_challenge = objective.get("target_challenge_id")
            completed_challenges = state.get("completed_challenges", [])

            completed = target_challenge in completed_challenges
            current_value = 1 if completed else 0

        elif objective_type == "reach_bloom_level":
            # Check if player reached specific Bloom's level
            target_level = objective.get("target_bloom_level")
            player = state.get("players", [{}])[0]
            current_level = player.get("cognitive_profile", {}).get("current_bloom_tier", "Remember")

            bloom_levels = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
            current_index = bloom_levels.index(current_level) if current_level in bloom_levels else 0
            target_index = bloom_levels.index(target_level) if target_level in bloom_levels else 0

            completed = current_index >= target_index
            current_value = current_index
            target_value = target_index

        elif objective_type == "perform_actions":
            # Check if player performed N actions
            current_value = len(state.get("action_history", []))
            completed = current_value >= target_value

        return {
            "objective_id": objective_id,
            "type": objective_type,
            "description": objective.get("description", ""),
            "completed": completed,
            "current_value": current_value,
            "target_value": target_value,
            "optional": objective.get("optional", False)
        }

    async def _complete_quest(
        self,
        session_id: str,
        quest_id: str,
        state: GameSessionState,
        quest_data: Dict[str, Any]
    ):
        """
        Trigger quest completion

        Args:
            session_id: Session ID
            quest_id: Quest ID
            state: Game session state
            quest_data: Quest data
        """
        try:
            # Add to completed quests
            state["completed_quest_ids"].append(quest_id)

            # Calculate rewards
            rewards = quest_data.get("rewards", {})

            # Broadcast quest completion
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "quest_completed",
                    "quest_id": quest_id,
                    "quest_title": quest_data.get("title"),
                    "rewards": rewards,
                    "celebration_message": f"Quest Complete: {quest_data.get('title')}!",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Award rewards
            await self._award_quest_rewards(session_id, state, rewards)

            # Check for next quest
            next_quest = await self._get_next_quest(quest_id, state)

            if next_quest:
                state["current_quest_id"] = next_quest["quest_id"]

                await connection_manager.broadcast_to_session(
                    session_id,
                    {
                        "event": "new_quest_available",
                        "quest_id": next_quest["quest_id"],
                        "quest_title": next_quest.get("title"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            logger.info(
                "quest_completed",
                session_id=session_id,
                quest_id=quest_id,
                next_quest=next_quest.get("quest_id") if next_quest else None
            )

        except Exception as e:
            logger.error("quest_completion_failed", error=str(e))

    async def _award_quest_rewards(
        self,
        session_id: str,
        state: GameSessionState,
        rewards: Dict[str, Any]
    ):
        """Award quest rewards to players"""
        try:
            # Experience points
            xp = rewards.get("experience", 0)

            # Items
            items = rewards.get("items", [])

            for player in state.get("players", []):
                player_id = player["player_id"]

                # Award items
                for item_id in items:
                    await mcp_client.add_item_to_inventory(player_id, item_id, quantity=1)

                # TODO: Award XP to player (would integrate with player-data MCP)

            logger.info(
                "quest_rewards_awarded",
                session_id=session_id,
                xp=xp,
                items_count=len(items)
            )

        except Exception as e:
            logger.error("reward_awarding_failed", error=str(e))

    async def _get_next_quest(
        self,
        completed_quest_id: str,
        state: GameSessionState
    ) -> Optional[Dict[str, Any]]:
        """Get next quest in campaign"""
        try:
            campaign_id = state.get("campaign_id")

            # Get all campaign quests
            campaign_quests = await mcp_client.get_campaign_quests(campaign_id)

            if not campaign_quests:
                return None

            quests = campaign_quests.get("quests", [])
            completed_quest_ids = state.get("completed_quest_ids", [])

            # Find next uncompleted quest
            for quest in quests:
                quest_id = quest.get("quest_id")

                if quest_id not in completed_quest_ids:
                    # Check prerequisites
                    prerequisites = quest.get("prerequisites", [])

                    if all(prereq in completed_quest_ids for prereq in prerequisites):
                        return quest

            return None

        except Exception as e:
            logger.error("next_quest_lookup_failed", error=str(e))
            return None

    async def get_campaign_progress(
        self,
        session_id: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """Get overall campaign progress"""
        try:
            campaign_id = state.get("campaign_id")

            # Get all quests
            campaign_quests = await mcp_client.get_campaign_quests(campaign_id)

            if not campaign_quests:
                return {
                    "campaign_id": campaign_id,
                    "total_quests": 0,
                    "completed_quests": 0,
                    "completion_percentage": 0
                }

            total_quests = len(campaign_quests.get("quests", []))
            completed_quests = len(state.get("completed_quest_ids", []))
            completion_percentage = int((completed_quests / total_quests) * 100) if total_quests > 0 else 0

            return {
                "campaign_id": campaign_id,
                "total_quests": total_quests,
                "completed_quests": completed_quests,
                "completion_percentage": completion_percentage,
                "current_quest_id": state.get("current_quest_id"),
                "campaign_complete": completed_quests >= total_quests
            }

        except Exception as e:
            logger.error("campaign_progress_failed", error=str(e))
            return {
                "campaign_id": campaign_id,
                "error": str(e)
            }


# Global instance
quest_tracker = QuestProgressionTracker()
