"""
Character Progression System - Django Integration
Manages character development profiles in MongoDB

Phase 5: Multi-dimensional progression tracking for Django web app
"""
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pymongo import MongoClient
from django.conf import settings

logger = logging.getLogger(__name__)

# MongoDB connection
mongo_client = MongoClient(settings.MONGO_CONNECTION_STRING)
mongo_db = mongo_client[settings.MONGO_DATABASE]


class CharacterProgressionManager:
    """
    Manages character progression data in MongoDB.

    Collections:
    - characters_progression: Character development profiles
    - progression_history: Historical events (knowledge acquired, items obtained, level-ups)
    """

    def __init__(self):
        self.progression_collection = mongo_db.characters_progression
        self.history_collection = mongo_db.progression_history

    def get_or_create_profile(self, character_id: str) -> Dict[str, Any]:
        """
        Get existing profile or create new one.

        Args:
            character_id: ID of the character

        Returns:
            Character development profile
        """
        try:
            # Try to find existing profile
            profile = self.progression_collection.find_one({"character_id": character_id})

            if profile:
                # Remove MongoDB _id for cleaner data
                profile.pop("_id", None)
                return profile

            # Create new profile
            from services.campaign_factory.workflow.progression_tracker import create_character_profile
            new_profile = create_character_profile(character_id)

            # Save to MongoDB
            self.progression_collection.insert_one(new_profile)

            logger.info(f"Created new progression profile for character {character_id}")
            return new_profile

        except Exception as e:
            logger.error(f"Error getting/creating profile: {str(e)}")
            return {}

    def award_knowledge(
        self,
        character_id: str,
        knowledge_id: str,
        knowledge_name: str,
        level: int,
        source: str = "unknown"
    ) -> bool:
        """
        Award knowledge to character.

        Args:
            character_id: ID of the character
            knowledge_id: ID of the knowledge entity
            knowledge_name: Name of the knowledge
            level: Level of mastery (1-4)
            source: Source of the knowledge

        Returns:
            True if successful
        """
        try:
            profile = self.get_or_create_profile(character_id)

            # Update profile using progression tracker
            from services.campaign_factory.workflow.progression_tracker import award_knowledge as award_kg
            updated_profile = award_kg(profile, knowledge_id, knowledge_name, level, source)

            # Save to MongoDB
            self.progression_collection.update_one(
                {"character_id": character_id},
                {"$set": updated_profile},
                upsert=True
            )

            # Log to history
            self._log_progression_event(
                character_id,
                "knowledge_acquired",
                {
                    "knowledge_id": knowledge_id,
                    "knowledge_name": knowledge_name,
                    "level": level,
                    "source": source
                }
            )

            logger.info(f"Awarded knowledge to character {character_id}: {knowledge_name} (Level {level})")
            return True

        except Exception as e:
            logger.error(f"Error awarding knowledge: {str(e)}")
            return False

    def award_item(
        self,
        character_id: str,
        item_id: str,
        item_name: str,
        quantity: int = 1,
        source: str = "unknown"
    ) -> bool:
        """
        Award item to character.

        Args:
            character_id: ID of the character
            item_id: ID of the item entity
            item_name: Name of the item
            quantity: Quantity to add
            source: Source of the item

        Returns:
            True if successful
        """
        try:
            profile = self.get_or_create_profile(character_id)

            # Update profile using progression tracker
            from services.campaign_factory.workflow.progression_tracker import award_item as award_it
            updated_profile = award_it(profile, item_id, item_name, quantity, source)

            # Save to MongoDB
            self.progression_collection.update_one(
                {"character_id": character_id},
                {"$set": updated_profile},
                upsert=True
            )

            # Log to history
            self._log_progression_event(
                character_id,
                "item_acquired",
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "quantity": quantity,
                    "source": source
                }
            )

            logger.info(f"Awarded item to character {character_id}: {item_name} x{quantity}")
            return True

        except Exception as e:
            logger.error(f"Error awarding item: {str(e)}")
            return False

    def add_dimensional_experience(
        self,
        character_id: str,
        dimension: str,
        exp: int
    ) -> bool:
        """
        Add experience to a dimension.

        Args:
            character_id: ID of the character
            dimension: Dimension to add experience to
            exp: Experience points to add

        Returns:
            True if successful
        """
        try:
            profile = self.get_or_create_profile(character_id)

            # Get old level for comparison
            old_level = profile["dimensional_maturity"][dimension]["current_level"]

            # Update profile using progression tracker
            from services.campaign_factory.workflow.progression_tracker import add_dimensional_experience as add_exp
            updated_profile = add_exp(profile, dimension, exp)

            # Check for level-up
            new_level = updated_profile["dimensional_maturity"][dimension]["current_level"]
            leveled_up = new_level > old_level

            # Save to MongoDB
            self.progression_collection.update_one(
                {"character_id": character_id},
                {"$set": updated_profile},
                upsert=True
            )

            # Log to history
            event_data = {
                "dimension": dimension,
                "exp_gained": exp,
                "new_total": updated_profile["dimensional_maturity"][dimension]["experience_points"]
            }

            if leveled_up:
                event_data["leveled_up"] = True
                event_data["old_level"] = old_level
                event_data["new_level"] = new_level
                self._log_progression_event(character_id, "dimension_level_up", event_data)
            else:
                self._log_progression_event(character_id, "dimensional_experience", event_data)

            logger.info(f"Added {exp} exp to {dimension} for character {character_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding dimensional experience: {str(e)}")
            return False

    def get_progression_summary(self, character_id: str) -> Dict[str, Any]:
        """
        Get progression summary for character.

        Args:
            character_id: ID of the character

        Returns:
            Progression summary
        """
        try:
            profile = self.get_or_create_profile(character_id)

            from services.campaign_factory.workflow.progression_tracker import get_progression_summary
            summary = get_progression_summary(profile)

            return summary

        except Exception as e:
            logger.error(f"Error getting progression summary: {str(e)}")
            return {}

    def check_quest_objectives(self, character_id: str, quest_id: str) -> Dict[str, Any]:
        """
        Check if character can complete quest objectives.

        Args:
            character_id: ID of the character
            quest_id: ID of the quest

        Returns:
            Dict with objective completion status
        """
        try:
            profile = self.get_or_create_profile(character_id)

            # Get quest objectives from MongoDB
            quest = mongo_db.quests.find_one({"quest_id": quest_id})
            if not quest:
                return {"error": "Quest not found"}

            # Check each objective
            from services.campaign_factory.workflow.progression_tracker import check_objective_completion

            objectives = quest.get("structured_objectives", quest.get("objectives", []))
            results = {}

            for objective in objectives:
                obj_id = objective.get("objective_id", "")
                is_complete, reason = check_objective_completion(profile, objective)

                results[obj_id] = {
                    "description": objective.get("description", ""),
                    "complete": is_complete,
                    "reason": reason
                }

            return {
                "quest_id": quest_id,
                "quest_name": quest.get("name", ""),
                "objectives": results,
                "all_complete": all(result["complete"] for result in results.values())
            }

        except Exception as e:
            logger.error(f"Error checking quest objectives: {str(e)}")
            return {"error": str(e)}

    def get_progression_history(
        self,
        character_id: str,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get progression history for character.

        Args:
            character_id: ID of the character
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return

        Returns:
            List of progression events
        """
        try:
            query = {"character_id": character_id}
            if event_type:
                query["event_type"] = event_type

            events = list(
                self.history_collection.find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )

            # Remove MongoDB _id
            for event in events:
                event.pop("_id", None)

            return events

        except Exception as e:
            logger.error(f"Error getting progression history: {str(e)}")
            return []

    def _log_progression_event(
        self,
        character_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Log progression event to history collection.

        Args:
            character_id: ID of the character
            event_type: Type of event
            data: Event data
        """
        try:
            event = {
                "character_id": character_id,
                "event_type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }

            self.history_collection.insert_one(event)

        except Exception as e:
            logger.error(f"Error logging progression event: {str(e)}")


# Global instance
progression_manager = CharacterProgressionManager()
