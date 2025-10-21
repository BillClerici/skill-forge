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

    # ============================================
    # Objective Cascade Tracking (Neo4j Integration)
    # ============================================

    async def check_objective_cascade(
        self,
        session_id: str,
        player_id: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Check progress on all levels of objective cascade:
        - Campaign objectives
        - Quest objectives
        - Scene objectives

        Integrates with Neo4j objective hierarchy from Campaign Design Wizard.

        Args:
            session_id: Session ID
            player_id: Player ID
            state: Game session state

        Returns:
            Progress report with UI updates
        """
        try:
            campaign_id = state.get("campaign_id")

            # Initialize PROGRESS relationships if they don't exist (self-healing)
            await neo4j_graph.initialize_player_progress(player_id, campaign_id)

            # Get current objective hierarchy progress from Neo4j
            progress = await neo4j_graph.get_player_objective_progress(
                player_id,
                campaign_id
            )

            # Check each quest objective for completion
            updates_sent = []

            for camp_obj in progress["campaign_objectives"]:
                for quest_obj in camp_obj["quest_objectives"]:
                    if quest_obj["status"] != "completed":
                        # Check if conditions are met
                        completion = await self._check_quest_objective_conditions(
                            quest_obj["id"],
                            player_id,
                            state
                        )

                        # If progress has been made, update Neo4j
                        if completion["percentage"] > quest_obj.get("progress", 0):
                            await neo4j_graph.record_objective_progress(
                                player_id,
                                quest_obj["id"],
                                "quest",
                                completion["percentage"],
                                completion["metadata"]
                            )

                            # Broadcast update to UI via WebSocket
                            await connection_manager.broadcast_to_session(
                                session_id,
                                {
                                    "event": "objective_progress",
                                    "objective_id": quest_obj["id"],
                                    "objective_description": quest_obj["description"],
                                    "percentage": completion["percentage"],
                                    "criteria_met": completion["criteria_met"],
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            )

                            updates_sent.append({
                                "objective_id": quest_obj["id"],
                                "new_percentage": completion["percentage"]
                            })

            # Check campaign objectives (calculated from quest objective progress)
            for camp_obj in progress["campaign_objectives"]:
                quest_progress = [
                    qo["progress"] for qo in camp_obj["quest_objectives"]
                ]
                campaign_percentage = (
                    sum(quest_progress) / len(quest_progress)
                    if quest_progress else 0
                )

                # If campaign objective progress changed, update
                if campaign_percentage != camp_obj.get("completion_percentage", 0):
                    await neo4j_graph.record_objective_progress(
                        player_id,
                        camp_obj["id"],
                        "campaign",
                        int(campaign_percentage)
                    )

                    # Broadcast campaign objective progress
                    await connection_manager.broadcast_to_session(
                        session_id,
                        {
                            "event": "campaign_objective_progress",
                            "objective_id": camp_obj["id"],
                            "objective_description": camp_obj["description"],
                            "percentage": campaign_percentage,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

                    updates_sent.append({
                        "objective_id": camp_obj["id"],
                        "new_percentage": int(campaign_percentage),
                        "type": "campaign"
                    })

            logger.info(
                "objective_cascade_checked",
                session_id=session_id,
                player_id=player_id,
                updates=len(updates_sent)
            )

            return {
                "progress": progress,
                "updates_sent": updates_sent
            }

        except Exception as e:
            logger.error("objective_cascade_check_failed", error=str(e))
            return {
                "progress": {"campaign_objectives": [], "overall_progress": 0},
                "updates_sent": [],
                "error": str(e)
            }

    async def _check_quest_objective_conditions(
        self,
        quest_objective_id: str,
        player_id: str,
        state: GameSessionState
    ) -> Dict[str, Any]:
        """
        Check if quest objective conditions are met based on:
        - Knowledge acquired
        - Items collected
        - Scenes visited
        - NPCs talked to
        - Challenges completed

        Args:
            quest_objective_id: Quest objective ID
            player_id: Player ID
            state: Game session state

        Returns:
            Dict with completion percentage, criteria met, and metadata
        """
        try:
            # Get objective definition from Neo4j
            async with neo4j_graph.driver.session() as session:
                result = await session.run("""
                    MATCH (qo:QuestObjective {id: $obj_id})
                    OPTIONAL MATCH (qo)-[:REQUIRES_KNOWLEDGE]->(k:Knowledge)
                    OPTIONAL MATCH (qo)-[:REQUIRES_ITEM]->(i:Item)
                    RETURN qo.success_criteria as criteria,
                           collect(DISTINCT k.id) as required_knowledge,
                           collect(DISTINCT i.id) as required_items
                """, obj_id=quest_objective_id)

                record = await result.single()

            if not record:
                logger.warning(
                    "quest_objective_not_found",
                    objective_id=quest_objective_id
                )
                return {
                    "percentage": 0,
                    "criteria_met": [],
                    "criteria_total": 0,
                    "metadata": {}
                }

            criteria = record["criteria"] or []
            required_knowledge = [k for k in record["required_knowledge"] if k]
            required_items = [i for i in record["required_items"] if i]

            criteria_met = []
            criteria_total = len(criteria)

            # Check each criterion
            for criterion in criteria:
                met = await self._check_criterion(
                    criterion,
                    player_id,
                    state,
                    required_knowledge,
                    required_items
                )
                if met:
                    criteria_met.append(criterion)

            # Calculate percentage
            percentage = (
                (len(criteria_met) / criteria_total * 100)
                if criteria_total > 0 else 0
            )

            # Check knowledge progress
            player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
            knowledge_acquired = [
                k for k in required_knowledge
                if k in player_knowledge
            ]

            # Check items progress
            player_inventories = state.get("player_inventories", {}).get(player_id, [])
            items_collected = [
                i for i in required_items
                if any(inv.get("item_id") == i for inv in player_inventories)
            ]

            return {
                "percentage": int(percentage),
                "criteria_met": criteria_met,
                "criteria_total": criteria_total,
                "metadata": {
                    "knowledge_progress": len(knowledge_acquired),
                    "knowledge_total": len(required_knowledge),
                    "items_progress": len(items_collected),
                    "items_total": len(required_items)
                }
            }

        except Exception as e:
            logger.error(
                "quest_objective_check_failed",
                objective_id=quest_objective_id,
                error=str(e)
            )
            return {
                "percentage": 0,
                "criteria_met": [],
                "criteria_total": 0,
                "metadata": {}
            }

    async def _check_criterion(
        self,
        criterion: str,
        player_id: str,
        state: GameSessionState,
        required_knowledge: List[str],
        required_items: List[str]
    ) -> bool:
        """
        Check if a specific success criterion is met.

        Examples:
        - "Find 3 clues" -> Check if 3 discoveries were made
        - "Collect 2 samples" -> Check if 2 specific items collected
        - "Talk to Old Miner" -> Check if NPC interaction occurred
        - "Complete corrupted water analysis" -> Check if challenge completed

        Args:
            criterion: Success criterion description
            player_id: Player ID
            state: Game session state
            required_knowledge: Required knowledge IDs
            required_items: Required item IDs

        Returns:
            True if criterion is met
        """
        criterion_lower = criterion.lower()

        # Pattern matching for different criterion types
        if "find" in criterion_lower or "discover" in criterion_lower:
            # Check discoveries/events in state
            completed_discoveries = state.get("completed_discoveries", [])
            # Extract number from criterion (e.g., "Find 3 clues" -> 3)
            import re
            match = re.search(r'\d+', criterion)
            target_count = int(match.group()) if match else 1
            return len(completed_discoveries) >= target_count

        elif "collect" in criterion_lower or "gather" in criterion_lower:
            # Check if required items are collected
            player_inventories = state.get("player_inventories", {}).get(player_id, [])
            items_collected = sum(
                1 for i in required_items
                if any(inv.get("item_id") == i for inv in player_inventories)
            )
            import re
            match = re.search(r'\d+', criterion)
            target_count = int(match.group()) if match else len(required_items)
            return items_collected >= target_count

        elif "talk to" in criterion_lower or "speak with" in criterion_lower:
            # Check if NPC was talked to
            conversation_history = state.get("conversation_history", [])
            # Extract NPC name from criterion
            # Simple check: if any conversation happened, consider met
            # (More sophisticated NPC name matching could be added)
            return len(conversation_history) > 0

        elif "complete" in criterion_lower or "finish" in criterion_lower:
            # Check if challenge was completed
            completed_challenges = state.get("completed_challenges", [])
            # Could check for specific challenge IDs
            return len(completed_challenges) > 0

        elif "visit" in criterion_lower or "reach" in criterion_lower:
            # Check if scene/location was visited
            completed_scene_ids = state.get("completed_scene_ids", [])
            import re
            match = re.search(r'\d+', criterion)
            target_count = int(match.group()) if match else 1
            return len(completed_scene_ids) >= target_count

        elif "acquire" in criterion_lower or "learn" in criterion_lower:
            # Check if knowledge was acquired
            player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
            knowledge_acquired = sum(
                1 for k in required_knowledge
                if k in player_knowledge
            )
            import re
            match = re.search(r'\d+', criterion)
            target_count = int(match.group()) if match else len(required_knowledge)
            return knowledge_acquired >= target_count

        else:
            # Default: consider criterion as a descriptive note, not automatically checkable
            logger.warning(
                "unknown_criterion_pattern",
                criterion=criterion
            )
            return False


# Global instance
quest_tracker = QuestProgressionTracker()
