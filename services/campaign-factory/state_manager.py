"""
State Manager
Handles saving and loading campaign and deletion workflow state to/from Redis
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from config import Config
from database import db_manager
from workflow.state import CampaignWorkflowState
from workflow.campaign_deletion_workflow import CampaignDeletionState

logger = logging.getLogger(__name__)


class StateManager:
    """Manages workflow state persistence in Redis"""

    def __init__(self):
        self.redis = None
        self.key_prefixes = Config.get_redis_key_prefixes()

    def set_redis_client(self, redis_client):
        """Set the Redis client instance"""
        self.redis = redis_client

    async def initialize_campaign_state(self, request_data: dict) -> CampaignWorkflowState:
        """
        Initialize campaign workflow state from request

        Args:
            request_data: Request data from RabbitMQ

        Returns:
            Initialized CampaignWorkflowState
        """
        # Fetch region details from MongoDB if region_id is provided
        region_data = {}
        if request_data.get("region_id"):
            try:
                mongo_db = db_manager.get_mongo_db()
                region = mongo_db.region_definitions.find_one({"_id": request_data["region_id"]})
                if region:
                    region_data = {
                        "description": region.get("description", ""),
                        "backstory": region.get("backstory", ""),
                        "climate": region.get("climate", ""),
                        "terrain": region.get("terrain", ""),
                        "key_features": region.get("key_features", []),
                        "notable_locations": region.get("notable_locations", []),
                        "inhabitants": region.get("inhabitants", [])
                    }
                    logger.info(f"Loaded region data for {request_data['region_name']}")
            except Exception as e:
                logger.warning(f"Could not fetch region details: {e}")

        state: CampaignWorkflowState = {
            "request_id": request_data.get("request_id", str(uuid.uuid4())),
            "user_id": request_data["user_id"],
            "character_id": request_data["character_id"],
            "created_at": datetime.utcnow().isoformat(),

            # User selections
            "universe_id": request_data["universe_id"],
            "universe_name": request_data["universe_name"],
            "world_id": request_data["world_id"],
            "world_name": request_data["world_name"],
            "region_id": request_data["region_id"],
            "region_name": request_data["region_name"],
            "region_data": region_data,
            "genre": request_data["genre"],
            "user_story_idea": request_data.get("user_story_idea"),

            # Story generation
            "story_ideas": [],
            "selected_story_id": None,
            "story_regeneration_count": 0,
            "regenerate_stories": False,

            # Campaign core
            "campaign_core": None,
            "user_approved_core": False,

            # Quest specifications
            "num_quests": 5,
            "quest_difficulty": "Medium",
            "quest_playtime_minutes": 90,
            "generate_images": True,

            # User approval flags
            "user_approved_quests": None,
            "user_approved_places": None,

            # Generated content
            "quests": [],
            "places": [],
            "scenes": [],
            "npcs": [],
            "discoveries": [],
            "events": [],
            "challenges": [],

            # World enrichment tracking
            "new_species_ids": [],
            "new_location_ids": [],  # DEPRECATED
            "new_locations": [],
            "new_npc_ids": [],

            # Workflow state management
            "current_phase": "init",
            "current_node": "",
            "errors": [],
            "warnings": [],
            "retry_count": 0,
            "max_retries": Config.MAX_RETRIES,

            # Audit trail
            "audit_trail": [],

            # Checkpoints
            "checkpoints": {},

            # Progress tracking
            "progress_percentage": 0,
            "step_progress": 0,
            "status_message": "Initializing campaign generation...",

            # Results
            "final_campaign_id": None,
            "mongodb_campaign_id": None,
            "neo4j_relationships_created": 0,
            "postgres_records_created": 0
        }

        # Save initial state
        await self.save_campaign_state(state)

        return state

    async def save_campaign_state(self, state: CampaignWorkflowState):
        """
        Save campaign workflow state to Redis

        Args:
            state: Campaign workflow state
        """
        try:
            request_id = state['request_id']

            # Save full state
            state_key = f"{self.key_prefixes['state']}{request_id}"
            await self.redis.setex(state_key, Config.REDIS_STATE_EXPIRY, json.dumps(state, default=str))

            # Save progress data for status API
            progress_key = f"{self.key_prefixes['progress']}{request_id}"
            progress_data = {
                "request_id": request_id,
                "progress_percentage": state.get("progress_percentage", 0),
                "step_progress": state.get("step_progress", 0),
                "status_message": state.get("status_message", "Processing..."),
                "current_phase": state.get("current_phase", "init"),
                "current_node": state.get("current_node", ""),
                "story_ideas": state.get("story_ideas", []),
                "campaign_core": state.get("campaign_core"),
                "quests": state.get("quests", []),
                "places": state.get("places", []),
                "scenes": state.get("scenes", []),
                "npcs": state.get("npcs", []),
                "discoveries": state.get("discoveries", []),
                "events": state.get("events", []),
                "challenges": state.get("challenges", []),
                "new_location_ids": state.get("new_location_ids", []),
                "new_locations": state.get("new_locations", []),
                "final_campaign_id": state.get("final_campaign_id"),
                "errors": state.get("errors", []),
                "warnings": state.get("warnings", [])
            }
            await self.redis.setex(progress_key, Config.REDIS_STATE_EXPIRY, json.dumps(progress_data, default=str))

            logger.info(f"Saved campaign state to Redis: {request_id}")

        except Exception as e:
            logger.error(f"Error saving campaign state to Redis: {e}")

    async def load_campaign_state(self, request_id: str) -> CampaignWorkflowState:
        """
        Load campaign workflow state from Redis

        Args:
            request_id: Request ID

        Returns:
            Campaign workflow state
        """
        try:
            state_key = f"{self.key_prefixes['state']}{request_id}"
            state_json = await self.redis.get(state_key)

            if not state_json:
                raise ValueError(f"Campaign state not found for request_id: {request_id}")

            state = json.loads(state_json)
            logger.info(f"Loaded campaign state from Redis: {request_id}")
            return state

        except Exception as e:
            logger.error(f"Error loading campaign state from Redis: {e}")
            raise

    async def save_deletion_state(self, state: CampaignDeletionState):
        """
        Save deletion workflow state to Redis

        Args:
            state: Deletion workflow state
        """
        try:
            request_id = state['request_id']

            # Save full state
            state_key = f"{self.key_prefixes['deletion_state']}{request_id}"
            await self.redis.setex(state_key, Config.REDIS_STATE_EXPIRY, json.dumps(state, default=str))

            # Save progress data for status API
            progress_key = f"{self.key_prefixes['deletion_progress']}{request_id}"
            progress_data = {
                "request_id": request_id,
                "campaign_id": state.get("campaign_id"),
                "campaign_name": state.get("campaign_name"),
                "current_phase": state.get("current_phase"),
                "progress_percentage": state.get("progress_percentage", 0),
                "step_progress": state.get("step_progress", 0),
                "status_message": state.get("status_message", "Processing..."),
                "deletion_log": state.get("deletion_log", []),
                "errors": state.get("errors", []),
                "warnings": state.get("warnings", []),
                "deleted_counts": {
                    "quests": len(state.get("deleted_quests", [])),
                    "places": len(state.get("deleted_places", [])),
                    "scenes": len(state.get("deleted_scenes", [])),
                    "npcs": len(state.get("deleted_npcs", [])),
                    "discoveries": len(state.get("deleted_discoveries", [])),
                    "events": len(state.get("deleted_events", [])),
                    "challenges": len(state.get("deleted_challenges", [])),
                    "knowledge": len(state.get("deleted_knowledge", [])),
                    "items": len(state.get("deleted_items", [])),
                    "rubrics": len(state.get("deleted_rubrics", []))
                },
                "cleanup_stats": {
                    "species_removed": len(state.get("species_to_remove", [])),
                    "locations_removed": len(state.get("locations_to_remove", []))
                }
            }
            await self.redis.setex(progress_key, Config.REDIS_STATE_EXPIRY, json.dumps(progress_data, default=str))

            logger.info(f"Saved deletion state to Redis: {request_id}")

        except Exception as e:
            logger.error(f"Error saving deletion state: {e}")


# Global state manager instance
state_manager = StateManager()
