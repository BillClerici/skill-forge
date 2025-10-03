"""
Analytics Tracker for Learning Outcomes and Engagement Metrics
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")

class AnalyticsTracker:
    """Tracks learning outcomes, engagement, and cognitive progression"""

    def __init__(self):
        self.mongo_client = AsyncIOMotorClient(MONGODB_URL)
        self.db = self.mongo_client.skillforge_analytics

    async def track_learning_outcome(
        self,
        profile_id: str,
        session_id: str,
        outcome_type: str,  # bloom_level_achieved, skill_practiced, concept_mastered
        details: Dict[str, Any]
    ):
        """Track a learning outcome"""
        outcome = {
            "profile_id": profile_id,
            "session_id": session_id,
            "outcome_type": outcome_type,
            "details": details,
            "timestamp": datetime.now()
        }

        await self.db.learning_outcomes.insert_one(outcome)

    async def track_engagement_event(
        self,
        profile_id: str,
        session_id: str,
        event_type: str,  # session_start, session_end, choice_made, quest_completed
        duration_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track an engagement event"""
        event = {
            "profile_id": profile_id,
            "session_id": session_id,
            "event_type": event_type,
            "duration_seconds": duration_seconds,
            "metadata": metadata or {},
            "timestamp": datetime.now()
        }

        await self.db.engagement_events.insert_one(event)

    async def update_cognitive_skill(
        self,
        profile_id: str,
        skill_name: str,  # empathy, strategy, creativity, courage
        xp_gained: int,
        context: str
    ):
        """Update cognitive skill progression"""
        # Get current skill level
        skill_record = await self.db.cognitive_skills.find_one({
            "profile_id": profile_id,
            "skill_name": skill_name
        })

        if not skill_record:
            # Create new skill record
            skill_record = {
                "profile_id": profile_id,
                "skill_name": skill_name,
                "total_xp": 0,
                "current_level": 1,
                "history": []
            }

        # Update XP
        skill_record["total_xp"] += xp_gained

        # Calculate new level (100 XP per level)
        new_level = 1 + (skill_record["total_xp"] // 100)
        skill_record["current_level"] = new_level

        # Add to history
        skill_record["history"].append({
            "xp_gained": xp_gained,
            "context": context,
            "timestamp": datetime.now()
        })

        skill_record["updated_at"] = datetime.now()

        # Upsert
        await self.db.cognitive_skills.update_one(
            {"profile_id": profile_id, "skill_name": skill_name},
            {"$set": skill_record},
            upsert=True
        )

    async def get_cognitive_progression(
        self,
        profile_id: str
    ) -> Dict[str, Any]:
        """Get cognitive skill progression for visualization"""
        skills = []

        async for skill in self.db.cognitive_skills.find({"profile_id": profile_id}):
            skill.pop("_id", None)
            skills.append(skill)

        # Calculate overall progression
        total_level = sum(s["current_level"] for s in skills)
        avg_level = total_level / len(skills) if skills else 0

        return {
            "profile_id": profile_id,
            "skills": skills,
            "total_level": total_level,
            "average_level": avg_level,
            "skills_count": len(skills)
        }

    async def get_engagement_metrics(
        self,
        profile_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get engagement metrics for the last N days"""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        # Count sessions
        session_count = await self.db.engagement_events.count_documents({
            "profile_id": profile_id,
            "event_type": "session_start",
            "timestamp": {"$gte": cutoff_date}
        })

        # Calculate total playtime
        pipeline = [
            {
                "$match": {
                    "profile_id": profile_id,
                    "event_type": "session_end",
                    "timestamp": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_duration": {"$sum": "$duration_seconds"}
                }
            }
        ]

        duration_result = await self.db.engagement_events.aggregate(pipeline).to_list(1)
        total_duration = duration_result[0]["total_duration"] if duration_result else 0

        # Count quests completed
        quests_completed = await self.db.engagement_events.count_documents({
            "profile_id": profile_id,
            "event_type": "quest_completed",
            "timestamp": {"$gte": cutoff_date}
        })

        # Count choices made
        choices_made = await self.db.engagement_events.count_documents({
            "profile_id": profile_id,
            "event_type": "choice_made",
            "timestamp": {"$gte": cutoff_date}
        })

        return {
            "profile_id": profile_id,
            "period_days": days,
            "session_count": session_count,
            "total_playtime_minutes": total_duration / 60 if total_duration else 0,
            "avg_session_duration_minutes": (total_duration / session_count / 60) if session_count > 0 else 0,
            "quests_completed": quests_completed,
            "choices_made": choices_made,
            "engagement_score": self._calculate_engagement_score(
                session_count, total_duration, quests_completed, choices_made
            )
        }

    def _calculate_engagement_score(
        self,
        sessions: int,
        duration: int,
        quests: int,
        choices: int
    ) -> float:
        """Calculate engagement score (0-100)"""
        # Weighted formula
        score = (
            (sessions * 5) +  # 5 points per session
            (duration / 60) +  # 1 point per minute
            (quests * 10) +  # 10 points per quest
            (choices * 2)  # 2 points per choice
        )

        # Normalize to 0-100
        return min(100, score / 10)

    async def get_learning_outcome_summary(
        self,
        profile_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get learning outcome summary"""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        # Count outcomes by type
        pipeline = [
            {
                "$match": {
                    "profile_id": profile_id,
                    "timestamp": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": "$outcome_type",
                    "count": {"$sum": 1}
                }
            }
        ]

        outcomes = {}
        async for result in self.db.learning_outcomes.aggregate(pipeline):
            outcomes[result["_id"]] = result["count"]

        return {
            "profile_id": profile_id,
            "period_days": days,
            "outcomes_by_type": outcomes,
            "total_outcomes": sum(outcomes.values())
        }
