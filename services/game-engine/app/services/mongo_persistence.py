"""
MongoDB Persistence Layer
Handles long-term storage of game sessions, chat history, and assessments
"""
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from datetime import datetime
import json

from ..core.config import settings
from ..core.logging import get_logger
from ..models.state import GameSessionState, AssessmentResult

logger = get_logger(__name__)


class MongoPersistence:
    """
    MongoDB persistence manager for game engine
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client["skillforge"]

            # Test connection
            await self.client.admin.command('ping')

            logger.info("mongodb_connected", database="skillforge")

            # Create indexes
            await self._create_indexes()

        except Exception as e:
            logger.error("mongodb_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("mongodb_disconnected")

    async def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            # Game sessions indexes
            await self.db.game_sessions.create_index("session_id", unique=True)
            await self.db.game_sessions.create_index("campaign_id")
            await self.db.game_sessions.create_index("status")
            await self.db.game_sessions.create_index([("started_at", -1)])

            # Chat messages indexes
            await self.db.chat_messages.create_index("session_id")
            await self.db.chat_messages.create_index("message_id", unique=True)
            await self.db.chat_messages.create_index([("timestamp", -1)])
            await self.db.chat_messages.create_index("sender_id")

            # Assessments indexes
            await self.db.assessments.create_index("assessment_id", unique=True)
            await self.db.assessments.create_index("player_id")
            await self.db.assessments.create_index("session_id")
            await self.db.assessments.create_index([("timestamp", -1)])

            # Player progression indexes
            await self.db.player_progression.create_index("player_id", unique=True)
            await self.db.player_progression.create_index([("last_updated", -1)])

            # Encounters indexes
            await self.db.encounters.create_index("session_id")
            await self.db.encounters.create_index("player_id")
            await self.db.encounters.create_index("encounter_type")
            await self.db.encounters.create_index([("timestamp", -1)])
            await self.db.encounters.create_index([("player_id", 1), ("encounter_type", 1)])

            # Knowledge acquisitions indexes
            await self.db.knowledge_acquisitions.create_index("session_id")
            await self.db.knowledge_acquisitions.create_index("player_id")
            await self.db.knowledge_acquisitions.create_index("knowledge_id")
            await self.db.knowledge_acquisitions.create_index("source_type")
            await self.db.knowledge_acquisitions.create_index([("timestamp", -1)])
            await self.db.knowledge_acquisitions.create_index([("player_id", 1), ("knowledge_id", 1)])

            # Item acquisitions indexes
            await self.db.item_acquisitions.create_index("session_id")
            await self.db.item_acquisitions.create_index("player_id")
            await self.db.item_acquisitions.create_index("item_id")
            await self.db.item_acquisitions.create_index("source_type")
            await self.db.item_acquisitions.create_index([("timestamp", -1)])
            await self.db.item_acquisitions.create_index([("player_id", 1), ("item_id", 1)])

            logger.info("mongodb_indexes_created")

        except Exception as e:
            logger.error("index_creation_failed", error=str(e))

    # ============================================
    # Game Session Persistence
    # ============================================

    async def save_session(self, state: GameSessionState) -> bool:
        """
        Save complete game session to MongoDB

        Args:
            state: Game session state

        Returns:
            Success status
        """
        try:
            session_id = state.get("session_id")

            # Prepare document
            session_doc = {
                "session_id": session_id,
                "campaign_id": state.get("campaign_id"),
                "status": state.get("status"),
                "started_at": state.get("started_at"),
                "last_updated": datetime.utcnow().isoformat(),
                "players": state.get("players", []),
                "current_quest_id": state.get("current_quest_id"),
                "current_scene_id": state.get("current_scene_id"),
                "completed_quest_ids": state.get("completed_quest_ids", []),
                "completed_scene_ids": state.get("completed_scene_ids", []),
                "action_history": state.get("action_history", []),
                "conversation_history": state.get("conversation_history", []),
                "event_log": state.get("event_log", []),
                "world_changes": state.get("world_changes", []),
                "elapsed_game_time": state.get("elapsed_game_time", 0),
                "time_of_day": state.get("time_of_day"),
                "party_settings": state.get("party_settings"),
                "metadata": {
                    "action_count": len(state.get("action_history", [])),
                    "quest_count": len(state.get("completed_quest_ids", [])),
                    "total_chat_messages": len(state.get("chat_messages", [])),
                    "conversation_turns": len(state.get("conversation_history", []))
                }
            }

            # Upsert session
            await self.db.game_sessions.update_one(
                {"session_id": session_id},
                {"$set": session_doc},
                upsert=True
            )

            logger.info(
                "session_saved_to_mongodb",
                session_id=session_id,
                action_count=len(state.get("action_history", []))
            )

            return True

        except Exception as e:
            logger.error(
                "session_save_failed",
                session_id=state.get("session_id"),
                error=str(e)
            )
            return False

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load game session from MongoDB

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        try:
            session_doc = await self.db.game_sessions.find_one({"session_id": session_id})

            if session_doc:
                # Remove MongoDB _id
                session_doc.pop("_id", None)

                logger.info("session_loaded_from_mongodb", session_id=session_id)
                return session_doc
            else:
                logger.warning("session_not_found_in_mongodb", session_id=session_id)
                return None

        except Exception as e:
            logger.error("session_load_failed", session_id=session_id, error=str(e))
            return None

    async def get_player_sessions(
        self,
        player_id: str,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get all sessions for a player"""
        try:
            query = {"players.player_id": player_id}

            if status:
                query["status"] = status

            cursor = self.db.game_sessions.find(query).sort("started_at", -1).limit(limit)

            sessions = []
            async for doc in cursor:
                doc.pop("_id", None)
                sessions.append(doc)

            logger.info(
                "player_sessions_retrieved",
                player_id=player_id,
                count=len(sessions)
            )

            return sessions

        except Exception as e:
            logger.error("get_player_sessions_failed", error=str(e))
            return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete a game session and all related data"""
        try:
            # Delete session document
            result = await self.db.game_sessions.delete_one({"session_id": session_id})

            # Delete related chat messages
            await self.db.chat_messages.delete_many({"session_id": session_id})

            # Delete related conversation history
            await self.db.conversations.delete_many({"session_id": session_id})

            # Delete related player state
            await self.db.player_state.delete_one({"session_id": session_id})

            logger.info("session_deleted", session_id=session_id, deleted_count=result.deleted_count)

            return result.deleted_count > 0

        except Exception as e:
            logger.error("delete_session_failed", session_id=session_id, error=str(e))
            return False

    # ============================================
    # Chat Message Persistence
    # ============================================

    async def save_chat_message(
        self,
        session_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """
        Save chat message to MongoDB

        Args:
            session_id: Session ID
            message: Chat message

        Returns:
            Success status
        """
        try:
            message_doc = {
                **message,
                "session_id": session_id,
                "stored_at": datetime.utcnow().isoformat()
            }

            await self.db.chat_messages.insert_one(message_doc)

            logger.debug(
                "chat_message_saved",
                session_id=session_id,
                message_id=message.get("message_id")
            )

            return True

        except Exception as e:
            logger.error("chat_message_save_failed", error=str(e))
            return False

    async def save_chat_messages_batch(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """Save multiple chat messages in batch"""
        try:
            if not messages:
                return True

            message_docs = [
                {
                    **msg,
                    "session_id": session_id,
                    "stored_at": datetime.utcnow().isoformat()
                }
                for msg in messages
            ]

            await self.db.chat_messages.insert_many(message_docs, ordered=False)

            logger.info(
                "chat_messages_batch_saved",
                session_id=session_id,
                count=len(messages)
            )

            return True

        except Exception as e:
            logger.error("chat_batch_save_failed", error=str(e))
            return False

    async def get_chat_history(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get chat history for session"""
        try:
            cursor = self.db.chat_messages.find(
                {"session_id": session_id}
            ).sort("timestamp", 1).skip(offset).limit(limit)

            messages = []
            async for doc in cursor:
                doc.pop("_id", None)
                messages.append(doc)

            logger.info(
                "chat_history_retrieved",
                session_id=session_id,
                count=len(messages)
            )

            return messages

        except Exception as e:
            logger.error("chat_history_retrieval_failed", error=str(e))
            return []

    # ============================================
    # Assessment Persistence
    # ============================================

    async def save_assessment(
        self,
        session_id: str,
        assessment: AssessmentResult
    ) -> bool:
        """
        Save assessment to MongoDB

        Args:
            session_id: Session ID
            assessment: Assessment result

        Returns:
            Success status
        """
        try:
            assessment_doc = {
                **assessment,
                "session_id": session_id,
                "stored_at": datetime.utcnow().isoformat()
            }

            await self.db.assessments.insert_one(assessment_doc)

            logger.info(
                "assessment_saved",
                session_id=session_id,
                assessment_id=assessment.get("assessment_id"),
                bloom_level=assessment.get("bloom_level_demonstrated")
            )

            return True

        except Exception as e:
            logger.error("assessment_save_failed", error=str(e))
            return False

    async def get_player_assessments(
        self,
        player_id: str,
        limit: int = 50
    ) -> List[AssessmentResult]:
        """Get all assessments for a player"""
        try:
            cursor = self.db.assessments.find(
                {"player_id": player_id}
            ).sort("timestamp", -1).limit(limit)

            assessments = []
            async for doc in cursor:
                doc.pop("_id", None)
                assessments.append(doc)

            logger.info(
                "player_assessments_retrieved",
                player_id=player_id,
                count=len(assessments)
            )

            return assessments

        except Exception as e:
            logger.error("assessment_retrieval_failed", error=str(e))
            return []

    # ============================================
    # Player Progression Tracking
    # ============================================

    async def update_player_progression(
        self,
        player_id: str,
        dimensional_progression: Dict[str, Any],
        bloom_history: List[str]
    ) -> bool:
        """
        Update player's progression data

        Args:
            player_id: Player ID
            dimensional_progression: Dimensional scores and trends
            bloom_history: History of Bloom's levels demonstrated

        Returns:
            Success status
        """
        try:
            progression_doc = {
                "player_id": player_id,
                "dimensional_progression": dimensional_progression,
                "bloom_history": bloom_history,
                "last_updated": datetime.utcnow().isoformat(),
                "metadata": {
                    "total_assessments": len(bloom_history),
                    "highest_bloom_level": max(bloom_history, key=lambda x: self._bloom_level_value(x)) if bloom_history else "Remember"
                }
            }

            await self.db.player_progression.update_one(
                {"player_id": player_id},
                {"$set": progression_doc},
                upsert=True
            )

            logger.info(
                "player_progression_updated",
                player_id=player_id,
                total_assessments=len(bloom_history)
            )

            return True

        except Exception as e:
            logger.error("progression_update_failed", error=str(e))
            return False

    def _bloom_level_value(self, level: str) -> int:
        """Get numeric value for Bloom's level"""
        levels = {
            "Remember": 1,
            "Understand": 2,
            "Apply": 3,
            "Analyze": 4,
            "Evaluate": 5,
            "Create": 6
        }
        return levels.get(level, 1)

    async def get_player_progression(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Get player's progression data"""
        try:
            progression = await self.db.player_progression.find_one({"player_id": player_id})

            if progression:
                progression.pop("_id", None)
                return progression
            else:
                return None

        except Exception as e:
            logger.error("progression_retrieval_failed", error=str(e))
            return None

    # ============================================
    # Campaign and Quest Data
    # ============================================

    async def get_all_campaigns(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all available campaigns from MongoDB

        Args:
            limit: Maximum number of campaigns to return

        Returns:
            List of campaign data
        """
        try:
            # Get campaigns that have quests (are playable)
            cursor = self.db.campaigns.find(
                {'quest_ids': {'$exists': True, '$ne': []}}
            ).sort("created_at", -1).limit(limit)

            campaigns = []
            async for campaign in cursor:
                campaign_id = str(campaign.get('_id'))
                campaign.pop("_id", None)
                campaign["campaign_id"] = campaign_id
                campaigns.append(campaign)

            logger.info("campaigns_loaded", count=len(campaigns))
            return campaigns

        except Exception as e:
            logger.error("campaigns_load_failed", error=str(e))
            return []

    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Get campaign data from MongoDB with Redis caching

        Args:
            campaign_id: Campaign ID

        Returns:
            Campaign data or None
        """
        try:
            # PERFORMANCE OPTIMIZATION: Check Redis cache first
            from .redis_manager import redis_manager
            cached = await redis_manager.cache_get_campaign(campaign_id)
            if cached:
                logger.info("campaign_loaded_from_cache", campaign_id=campaign_id)
                return cached

            # Cache miss - load from MongoDB
            campaign = await self.db.campaigns.find_one({"_id": campaign_id})

            if campaign:
                # Convert MongoDB _id to campaign_id for consistency
                campaign.pop("_id", None)
                campaign["campaign_id"] = campaign_id

                # Cache for future requests
                await redis_manager.cache_set_campaign(campaign_id, campaign)

                logger.info("campaign_loaded_from_mongodb", campaign_id=campaign_id)
                return campaign
            else:
                logger.warning("campaign_not_found", campaign_id=campaign_id)
                return None

        except Exception as e:
            logger.error("campaign_load_failed", campaign_id=campaign_id, error=str(e))
            return None

    async def get_quest(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """
        Get quest data from MongoDB with Redis caching

        Args:
            quest_id: Quest ID

        Returns:
            Quest data or None
        """
        try:
            # PERFORMANCE OPTIMIZATION: Check Redis cache first
            from .redis_manager import redis_manager
            cached = await redis_manager.cache_get_quest(quest_id)
            if cached:
                logger.info("quest_loaded_from_cache", quest_id=quest_id)
                return cached

            # Cache miss - load from MongoDB
            quest = await self.db.quests.find_one({"_id": quest_id})

            if quest:
                # Convert MongoDB _id to quest_id for consistency
                quest.pop("_id", None)
                quest["quest_id"] = quest_id

                # Cache for future requests
                await redis_manager.cache_set_quest(quest_id, quest)

                logger.info("quest_loaded_from_mongodb", quest_id=quest_id, title=quest.get("title", "Unknown"))
                return quest
            else:
                logger.warning("quest_not_found", quest_id=quest_id)
                return None

        except Exception as e:
            logger.error("quest_load_failed", quest_id=quest_id, error=str(e))
            return None

    async def get_place(self, place_id: str) -> Optional[Dict[str, Any]]:
        """
        Get place data from MongoDB

        Args:
            place_id: Place ID

        Returns:
            Place data or None
        """
        try:
            place = await self.db.places.find_one({"_id": place_id})

            if place:
                # Convert MongoDB _id to place_id for consistency
                place.pop("_id", None)
                place["place_id"] = place_id

                logger.info("place_loaded", place_id=place_id, name=place.get("name", "Unknown"))
                return place
            else:
                logger.warning("place_not_found", place_id=place_id)
                return None

        except Exception as e:
            logger.error("place_load_failed", place_id=place_id, error=str(e))
            return None

    async def get_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """
        Get scene data from MongoDB

        Args:
            scene_id: Scene ID

        Returns:
            Scene data or None
        """
        try:
            scene = await self.db.scenes.find_one({"_id": scene_id})

            if scene:
                # Convert MongoDB _id to scene_id for consistency
                scene.pop("_id", None)
                scene["scene_id"] = scene_id

                logger.info("scene_loaded", scene_id=scene_id, name=scene.get("name", "Unknown"))
                return scene
            else:
                logger.warning("scene_not_found", scene_id=scene_id)
                return None

        except Exception as e:
            logger.error("scene_load_failed", scene_id=scene_id, error=str(e))
            return None

    async def get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """
        Get world data from MongoDB

        Args:
            world_id: World ID

        Returns:
            World data or None
        """
        try:
            # Try to find the world in world_definitions collection
            world = await self.db.world_definitions.find_one({"_id": world_id})

            if world:
                # Convert MongoDB _id to world_id for consistency
                world.pop("_id", None)
                world["world_id"] = world_id

                logger.info("world_loaded", world_id=world_id, world_name=world.get("world_name", "Unknown"))
                return world
            else:
                logger.warning("world_not_found", world_id=world_id)
                return None

        except Exception as e:
            logger.error("world_load_failed", world_id=world_id, error=str(e))
            return None

    async def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """
        Get region data from MongoDB

        Args:
            region_id: Region ID

        Returns:
            Region data or None
        """
        try:
            region = await self.db.region_definitions.find_one({"_id": region_id})

            if region:
                # Convert MongoDB _id to region_id for consistency
                region.pop("_id", None)
                region["region_id"] = region_id

                logger.info("region_loaded", region_id=region_id, region_name=region.get("region_name", "Unknown"))
                return region
            else:
                logger.warning("region_not_found", region_id=region_id)
                return None

        except Exception as e:
            logger.error("region_load_failed", region_id=region_id, error=str(e))
            return None

    async def get_location(self, location_id: str) -> Optional[Dict[str, Any]]:
        """
        Get location data from MongoDB

        Args:
            location_id: Location ID

        Returns:
            Location data or None
        """
        try:
            location = await self.db.location_definitions.find_one({"_id": location_id})

            if location:
                # Convert MongoDB _id to location_id for consistency
                location.pop("_id", None)
                location["location_id"] = location_id

                logger.info("location_loaded", location_id=location_id, location_name=location.get("location_name", "Unknown"))
                return location
            else:
                logger.warning("location_not_found", location_id=location_id)
                return None

        except Exception as e:
            logger.error("location_load_failed", location_id=location_id, error=str(e))
            return None

    async def get_species(self, species_id: str) -> Optional[Dict[str, Any]]:
        """
        Get species data from MongoDB

        Args:
            species_id: Species ID

        Returns:
            Species data or None
        """
        try:
            species = await self.db.species_definitions.find_one({"_id": species_id})

            if species:
                # Convert MongoDB _id to species_id for consistency
                species.pop("_id", None)
                species["species_id"] = species_id

                logger.info("species_loaded", species_id=species_id, species_name=species.get("species_name", "Unknown"))
                return species
            else:
                logger.warning("species_not_found", species_id=species_id)
                return None

        except Exception as e:
            logger.error("species_load_failed", species_id=species_id, error=str(e))
            return None

    async def get_npcs_at_location(self, scene_id: str) -> List[Dict[str, Any]]:
        """
        Get all NPCs at a specific scene/location

        Args:
            scene_id: Scene ID (level_3_location_id)

        Returns:
            List of NPC data
        """
        try:
            # Query NPCs collection for NPCs at this location
            cursor = self.db.npcs.find({"level_3_location_id": scene_id})

            npcs = []
            async for npc in cursor:
                # Convert MongoDB _id to npc_id for consistency
                npc_id = npc.pop("_id", None)
                npc["npc_id"] = npc_id

                # Extract key fields for game loop
                npc_data = {
                    "npc_id": npc_id,
                    "name": npc.get("name", "Unknown"),
                    "species_name": npc.get("species_name"),
                    "role": npc.get("role", {}),
                    "personality_traits": npc.get("personality_traits", {}),
                    "dialogue_style": npc.get("dialogue_style", ""),
                    "backstory": npc.get("backstory", "")
                }
                npcs.append(npc_data)

            logger.info(
                "npcs_loaded_at_location",
                scene_id=scene_id,
                npc_count=len(npcs),
                npc_names=[n["name"] for n in npcs]
            )

            return npcs

        except Exception as e:
            logger.error("npcs_load_failed", scene_id=scene_id, error=str(e))
            return []

    async def get_discoveries_by_ids(self, discovery_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get discoveries by their IDs

        Args:
            discovery_ids: List of discovery IDs

        Returns:
            List of discovery data
        """
        try:
            if not discovery_ids:
                return []

            # Query discoveries collection
            cursor = self.db.discoveries.find({"_id": {"$in": discovery_ids}})

            discoveries = []
            async for discovery in cursor:
                discovery_id = discovery.pop("_id", None)
                discovery["discovery_id"] = discovery_id
                discoveries.append(discovery)

            logger.info(
                "discoveries_loaded",
                count=len(discoveries)
            )

            return discoveries

        except Exception as e:
            logger.error("discoveries_load_failed", error=str(e))
            return []

    async def get_events_by_ids(self, event_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get events by their IDs

        Args:
            event_ids: List of event IDs

        Returns:
            List of event data
        """
        try:
            if not event_ids:
                return []

            # Query events collection
            cursor = self.db.events.find({"_id": {"$in": event_ids}})

            events = []
            async for event in cursor:
                event_id = event.pop("_id", None)
                event["event_id"] = event_id
                events.append(event)

            logger.info(
                "events_loaded",
                count=len(events)
            )

            return events

        except Exception as e:
            logger.error("events_load_failed", error=str(e))
            return []

    async def get_challenges_by_ids(self, challenge_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get challenges by their IDs

        Args:
            challenge_ids: List of challenge IDs

        Returns:
            List of challenge data
        """
        try:
            if not challenge_ids:
                return []

            # Query challenges collection
            cursor = self.db.challenges.find({"_id": {"$in": challenge_ids}})

            challenges = []
            async for challenge in cursor:
                challenge_id = challenge.pop("_id", None)
                challenge["challenge_id"] = challenge_id
                challenges.append(challenge)

            logger.info(
                "challenges_loaded",
                count=len(challenges)
            )

            return challenges

        except Exception as e:
            logger.error("challenges_load_failed", error=str(e))
            return []

    async def get_items_by_ids(self, item_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get items by their IDs

        Args:
            item_ids: List of item IDs

        Returns:
            List of item data
        """
        try:
            if not item_ids:
                return []

            # Query items collection
            cursor = self.db.items.find({"_id": {"$in": item_ids}})

            items = []
            async for item in cursor:
                item_id = item.pop("_id", None)
                item["item_id"] = item_id
                items.append(item)

            logger.info(
                "items_loaded",
                count=len(items)
            )

            return items

        except Exception as e:
            logger.error("items_load_failed", error=str(e))
            return []

    async def get_knowledge_by_ids(self, knowledge_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get knowledge by their IDs

        Args:
            knowledge_ids: List of knowledge IDs

        Returns:
            List of knowledge data
        """
        try:
            if not knowledge_ids:
                return []

            # Query knowledge collection
            cursor = self.db.knowledge.find({"_id": {"$in": knowledge_ids}})

            knowledge_list = []
            async for knowledge in cursor:
                knowledge_id = knowledge.pop("_id", None)
                knowledge["knowledge_id"] = knowledge_id
                knowledge_list.append(knowledge)

            logger.info(
                "knowledge_loaded",
                count=len(knowledge_list)
            )

            return knowledge_list

        except Exception as e:
            logger.error("knowledge_load_failed", error=str(e))
            return []

    async def get_quests_by_ids(self, quest_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get quests by their IDs (batch query)

        Args:
            quest_ids: List of quest IDs

        Returns:
            List of quest data
        """
        try:
            if not quest_ids:
                return []

            cursor = self.db.quests.find({"_id": {"$in": quest_ids}})

            quests_list = []
            async for quest in cursor:
                quest_id = quest.pop("_id", None)
                quest["quest_id"] = quest_id
                quests_list.append(quest)

            logger.info("quests_batch_loaded", count=len(quests_list), requested=len(quest_ids))

            return quests_list

        except Exception as e:
            logger.error("quests_batch_load_failed", error=str(e))
            return []

    async def get_places_by_ids(self, place_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get places by their IDs (batch query)

        Args:
            place_ids: List of place IDs

        Returns:
            List of place data
        """
        try:
            if not place_ids:
                return []

            cursor = self.db.places.find({"_id": {"$in": place_ids}})

            places_list = []
            async for place in cursor:
                place_id = place.pop("_id", None)
                place["place_id"] = place_id
                places_list.append(place)

            logger.info("places_batch_loaded", count=len(places_list), requested=len(place_ids))

            return places_list

        except Exception as e:
            logger.error("places_batch_load_failed", error=str(e))
            return []

    async def get_scenes_by_ids(self, scene_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get scenes by their IDs (batch query)

        Args:
            scene_ids: List of scene IDs

        Returns:
            List of scene data
        """
        try:
            if not scene_ids:
                return []

            cursor = self.db.scenes.find({"_id": {"$in": scene_ids}})

            scenes_list = []
            async for scene in cursor:
                scene_id = scene.pop("_id", None)
                scene["scene_id"] = scene_id
                scenes_list.append(scene)

            logger.info("scenes_batch_loaded", count=len(scenes_list), requested=len(scene_ids))

            return scenes_list

        except Exception as e:
            logger.error("scenes_batch_load_failed", error=str(e))
            return []

    async def get_regions_by_ids(self, region_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get regions by their IDs (batch query)

        Args:
            region_ids: List of region IDs

        Returns:
            List of region data
        """
        try:
            if not region_ids:
                return []

            cursor = self.db.regions.find({"_id": {"$in": region_ids}})

            regions_list = []
            async for region in cursor:
                region_id = region.pop("_id", None)
                region["region_id"] = region_id
                regions_list.append(region)

            logger.info("regions_batch_loaded", count=len(regions_list), requested=len(region_ids))

            return regions_list

        except Exception as e:
            logger.error("regions_batch_load_failed", error=str(e))
            return []

    async def get_species_by_ids(self, species_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get species by their IDs (batch query)

        Args:
            species_ids: List of species IDs

        Returns:
            List of species data
        """
        try:
            if not species_ids:
                return []

            cursor = self.db.species.find({"_id": {"$in": species_ids}})

            species_list = []
            async for spec in cursor:
                species_id = spec.pop("_id", None)
                spec["species_id"] = species_id
                species_list.append(spec)

            logger.info("species_batch_loaded", count=len(species_list), requested=len(species_ids))

            return species_list

        except Exception as e:
            logger.error("species_batch_load_failed", error=str(e))
            return []

    async def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get single item by ID"""
        try:
            item = await self.db.items.find_one({"_id": item_id})
            if item:
                item.pop("_id", None)
                item["item_id"] = item_id
                return item
            return None
        except Exception as e:
            logger.error("item_load_failed", item_id=item_id, error=str(e))
            return None

    async def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Get single knowledge by ID"""
        try:
            knowledge = await self.db.knowledge.find_one({"_id": knowledge_id})
            if knowledge:
                knowledge.pop("_id", None)
                knowledge["knowledge_id"] = knowledge_id
                return knowledge
            return None
        except Exception as e:
            logger.error("knowledge_load_failed", knowledge_id=knowledge_id, error=str(e))
            return None

    # ============================================
    # Encounter Persistence
    # ============================================

    async def save_encounter(
        self,
        session_id: str,
        player_id: str,
        encounter_type: str,
        encounter_data: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Save encounter to MongoDB

        Args:
            session_id: Session ID
            player_id: Player ID
            encounter_type: Type of encounter (npc, event, discovery, challenge)
            encounter_data: Encounter details
            metadata: Context metadata (quest, place, scene, timestamp)

        Returns:
            Success status
        """
        try:
            encounter_doc = {
                "session_id": session_id,
                "player_id": player_id,
                "encounter_type": encounter_type,
                "encounter_id": encounter_data.get("id"),
                "encounter_name": encounter_data.get("name") or encounter_data.get("title"),
                "encounter_description": encounter_data.get("description"),
                "metadata": metadata,
                "timestamp": metadata.get("timestamp") or datetime.utcnow().isoformat(),
                "quest_id": metadata.get("quest_id"),
                "place_id": metadata.get("place_id"),
                "scene_id": metadata.get("scene_id"),
                "stored_at": datetime.utcnow().isoformat()
            }

            await self.db.encounters.insert_one(encounter_doc)

            logger.info(
                "encounter_saved",
                session_id=session_id,
                player_id=player_id,
                encounter_type=encounter_type,
                encounter_name=encounter_doc["encounter_name"]
            )

            return True

        except Exception as e:
            logger.error("encounter_save_failed", error=str(e))
            return False

    async def save_knowledge_acquisition(
        self,
        session_id: str,
        player_id: str,
        knowledge_id: str,
        knowledge_data: Dict[str, Any],
        source_type: str,
        source_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Save knowledge acquisition to MongoDB

        Args:
            session_id: Session ID
            player_id: Player ID
            knowledge_id: Knowledge ID
            knowledge_data: Knowledge details
            source_type: Source type (npc, discovery, challenge, event)
            source_id: Source entity ID
            metadata: Context metadata

        Returns:
            Success status
        """
        try:
            acquisition_doc = {
                "session_id": session_id,
                "player_id": player_id,
                "knowledge_id": knowledge_id,
                "knowledge_name": knowledge_data.get("name") or knowledge_data.get("title"),
                "knowledge_description": knowledge_data.get("description"),
                "source_type": source_type,
                "source_id": source_id,
                "metadata": metadata,
                "timestamp": metadata.get("timestamp") or datetime.utcnow().isoformat(),
                "quest_id": metadata.get("quest_id"),
                "place_id": metadata.get("place_id"),
                "scene_id": metadata.get("scene_id"),
                "stored_at": datetime.utcnow().isoformat()
            }

            await self.db.knowledge_acquisitions.insert_one(acquisition_doc)

            logger.info(
                "knowledge_acquisition_saved",
                session_id=session_id,
                player_id=player_id,
                knowledge_name=acquisition_doc["knowledge_name"],
                source_type=source_type
            )

            return True

        except Exception as e:
            logger.error("knowledge_acquisition_save_failed", error=str(e))
            return False

    async def save_item_acquisition(
        self,
        session_id: str,
        player_id: str,
        item_id: str,
        item_data: Dict[str, Any],
        source_type: str,
        source_id: Optional[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Save item acquisition to MongoDB

        Args:
            session_id: Session ID
            player_id: Player ID
            item_id: Item ID
            item_data: Item details
            source_type: Source type (npc, discovery, challenge, scene)
            source_id: Source entity ID (optional for scene items)
            metadata: Context metadata

        Returns:
            Success status
        """
        try:
            acquisition_doc = {
                "session_id": session_id,
                "player_id": player_id,
                "item_id": item_id,
                "item_name": item_data.get("name"),
                "item_description": item_data.get("description"),
                "source_type": source_type,
                "source_id": source_id,
                "metadata": metadata,
                "timestamp": metadata.get("timestamp") or datetime.utcnow().isoformat(),
                "quest_id": metadata.get("quest_id"),
                "place_id": metadata.get("place_id"),
                "scene_id": metadata.get("scene_id"),
                "stored_at": datetime.utcnow().isoformat()
            }

            await self.db.item_acquisitions.insert_one(acquisition_doc)

            logger.info(
                "item_acquisition_saved",
                session_id=session_id,
                player_id=player_id,
                item_name=acquisition_doc["item_name"],
                source_type=source_type
            )

            return True

        except Exception as e:
            logger.error("item_acquisition_save_failed", error=str(e))
            return False

    async def get_player_encounters(
        self,
        player_id: str,
        session_id: Optional[str] = None,
        encounter_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get encounter history for a player"""
        try:
            query = {"player_id": player_id}

            if session_id:
                query["session_id"] = session_id

            if encounter_type:
                query["encounter_type"] = encounter_type

            cursor = self.db.encounters.find(query).sort("timestamp", -1).limit(limit)

            encounters = []
            async for doc in cursor:
                doc.pop("_id", None)
                encounters.append(doc)

            logger.info(
                "player_encounters_retrieved",
                player_id=player_id,
                count=len(encounters)
            )

            return encounters

        except Exception as e:
            logger.error("encounters_retrieval_failed", error=str(e))
            return []

    async def get_player_knowledge_acquisitions(
        self,
        player_id: str,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get knowledge acquisition history for a player"""
        try:
            query = {"player_id": player_id}

            if session_id:
                query["session_id"] = session_id

            cursor = self.db.knowledge_acquisitions.find(query).sort("timestamp", -1).limit(limit)

            acquisitions = []
            async for doc in cursor:
                doc.pop("_id", None)
                acquisitions.append(doc)

            logger.info(
                "knowledge_acquisitions_retrieved",
                player_id=player_id,
                count=len(acquisitions)
            )

            return acquisitions

        except Exception as e:
            logger.error("knowledge_acquisitions_retrieval_failed", error=str(e))
            return []

    async def get_player_item_acquisitions(
        self,
        player_id: str,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get item acquisition history for a player"""
        try:
            query = {"player_id": player_id}

            if session_id:
                query["session_id"] = session_id

            cursor = self.db.item_acquisitions.find(query).sort("timestamp", -1).limit(limit)

            acquisitions = []
            async for doc in cursor:
                doc.pop("_id", None)
                acquisitions.append(doc)

            logger.info(
                "item_acquisitions_retrieved",
                player_id=player_id,
                count=len(acquisitions)
            )

            return acquisitions

        except Exception as e:
            logger.error("item_acquisitions_retrieval_failed", error=str(e))
            return []

    # ============================================
    # Session Analytics
    # ============================================

    async def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session statistics"""
        try:
            # Get session
            session = await self.load_session(session_id)

            if not session:
                return {}

            # Count chat messages
            chat_count = await self.db.chat_messages.count_documents({"session_id": session_id})

            # Count assessments
            assessment_count = await self.db.assessments.count_documents({"session_id": session_id})

            # Get average scores
            assessment_pipeline = [
                {"$match": {"session_id": session_id}},
                {"$group": {
                    "_id": None,
                    "avg_experience": {"$avg": "$experience_gained"},
                    "bloom_levels": {"$push": "$bloom_level_demonstrated"}
                }}
            ]

            assessment_stats = await self.db.assessments.aggregate(assessment_pipeline).to_list(1)

            stats = {
                "session_id": session_id,
                "status": session.get("status"),
                "total_actions": len(session.get("action_history", [])),
                "total_chat_messages": chat_count,
                "total_assessments": assessment_count,
                "quests_completed": len(session.get("completed_quest_ids", [])),
                "game_time_elapsed": session.get("elapsed_game_time", 0),
                "player_count": len(session.get("players", []))
            }

            if assessment_stats:
                stats["avg_experience_per_action"] = assessment_stats[0].get("avg_experience", 0)
                stats["bloom_levels_used"] = list(set(assessment_stats[0].get("bloom_levels", [])))

            return stats

        except Exception as e:
            logger.error("statistics_retrieval_failed", error=str(e))
            return {}


# Global instance
mongo_persistence = MongoPersistence()
