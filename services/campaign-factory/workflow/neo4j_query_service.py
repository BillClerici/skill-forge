"""
Neo4j Query Service
Provides read operations for querying campaign graph structures
"""
import logging
from typing import Dict, Any, List, Optional
from neo4j import Driver

logger = logging.getLogger(__name__)


class Neo4jQueryService:
    """Service for querying campaign graph data from Neo4j"""

    def __init__(self, driver: Driver):
        self.driver = driver

    def get_objective_hierarchy(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get complete objective hierarchy for a campaign.

        Returns:
            {
                "campaign_objectives": [
                    {
                        "id": "...",
                        "description": "...",
                        "status": "...",
                        "quest_objectives": [...]
                    }
                ]
            }
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (camp:Campaign {id: $campaign_id})-[:HAS_OBJECTIVE]->(co:CampaignObjective)
                    OPTIONAL MATCH (co)-[:DECOMPOSES_TO]->(qo:QuestObjective)
                    OPTIONAL MATCH (q:Quest)-[:ACHIEVES]->(qo)
                    RETURN co,
                           collect(DISTINCT {
                               id: qo.id,
                               description: qo.description,
                               blooms_level: qo.blooms_level,
                               quest_number: qo.quest_number,
                               status: qo.status,
                               is_required: qo.is_required,
                               quest_id: q.id,
                               quest_name: q.name
                           }) as quest_objectives
                    ORDER BY co.id
                """, {"campaign_id": campaign_id})

                campaign_objectives = []
                for record in result:
                    co = record["co"]
                    campaign_objectives.append({
                        "id": co["id"],
                        "description": co["description"],
                        "status": co.get("status", "not_started"),
                        "completion_criteria": co.get("completion_criteria", []),
                        "minimum_quests_required": co.get("minimum_quests_required", 1),
                        "quest_objectives": [qo for qo in record["quest_objectives"] if qo["id"] is not None]
                    })

                return {
                    "campaign_id": campaign_id,
                    "campaign_objectives": campaign_objectives
                }

        except Exception as e:
            logger.error(f"Error getting objective hierarchy: {str(e)}")
            return {"campaign_id": campaign_id, "campaign_objectives": []}

    def get_scene_objective_assignments(self, scene_id: str) -> Dict[str, Any]:
        """
        Get all objective assignments and resource provisions for a scene.

        Returns:
            {
                "scene_id": "...",
                "advances_quest_objectives": [...],
                "advances_campaign_objectives": [...],
                "provides_knowledge": [...],
                "provides_items": [...]
            }
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (s:Scene {id: $scene_id})

                    // Quest objectives
                    OPTIONAL MATCH (s)-[:ADVANCES]->(qo:QuestObjective)

                    // Campaign objectives
                    OPTIONAL MATCH (s)-[:ADVANCES]->(co:CampaignObjective)

                    // Knowledge provisions
                    OPTIONAL MATCH (s)-[pk:PROVIDES]->(k:Knowledge)

                    // Item provisions
                    OPTIONAL MATCH (s)-[pi:PROVIDES]->(i:Item)

                    RETURN s,
                           collect(DISTINCT {id: qo.id, description: qo.description}) as quest_objectives,
                           collect(DISTINCT {id: co.id, description: co.description}) as campaign_objectives,
                           collect(DISTINCT {
                               id: k.id,
                               name: k.name,
                               domain: pk.domain,
                               max_level: pk.max_level
                           }) as knowledge,
                           collect(DISTINCT {
                               id: i.id,
                               name: i.name,
                               category: pi.category,
                               quantity: pi.quantity
                           }) as items
                """, {"scene_id": scene_id})

                record = result.single()
                if not record:
                    return {"scene_id": scene_id, "error": "Scene not found"}

                s = record["s"]
                return {
                    "scene_id": scene_id,
                    "scene_name": s.get("name", "Unknown"),
                    "is_required": s.get("is_required", False),
                    "is_redundant": s.get("is_redundant", False),
                    "advances_quest_objectives": [qo for qo in record["quest_objectives"] if qo["id"] is not None],
                    "advances_campaign_objectives": [co for co in record["campaign_objectives"] if co["id"] is not None],
                    "provides_knowledge": [k for k in record["knowledge"] if k["id"] is not None],
                    "provides_items": [i for i in record["items"] if i["id"] is not None]
                }

        except Exception as e:
            logger.error(f"Error getting scene assignments: {str(e)}")
            return {"scene_id": scene_id, "error": str(e)}

    def get_knowledge_acquisition_paths(self, knowledge_id: str) -> List[Dict[str, Any]]:
        """
        Find all ways to acquire a specific knowledge item.

        Returns:
            [
                {
                    "method": "npc",
                    "encounter_id": "...",
                    "encounter_name": "...",
                    "scene_id": "...",
                    "scene_name": "..."
                }
            ]
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (k:Knowledge {id: $knowledge_id})
                    MATCH (e)-[rel]->(k)
                    WHERE type(rel) IN ['TEACHES', 'REVEALS', 'REWARDS', 'GRANTS']
                    MATCH (s:Scene)-[:CONTAINS]->(e)
                    RETURN type(rel) as rel_type,
                           e.id as encounter_id,
                           e.name as encounter_name,
                           labels(e)[0] as encounter_type,
                           s.id as scene_id,
                           s.name as scene_name,
                           rel.scene_id as rel_scene_id
                    ORDER BY s.order_sequence
                """, {"knowledge_id": knowledge_id})

                paths = []
                for record in result:
                    method_map = {
                        "TEACHES": "npc",
                        "REVEALS": "discovery",
                        "REWARDS": "challenge",
                        "GRANTS": "event"
                    }
                    paths.append({
                        "method": method_map.get(record["rel_type"], "unknown"),
                        "encounter_id": record["encounter_id"],
                        "encounter_name": record["encounter_name"],
                        "encounter_type": record["encounter_type"],
                        "scene_id": record["scene_id"],
                        "scene_name": record["scene_name"]
                    })

                return paths

        except Exception as e:
            logger.error(f"Error getting knowledge acquisition paths: {str(e)}")
            return []

    def get_item_acquisition_paths(self, item_id: str) -> List[Dict[str, Any]]:
        """
        Find all ways to acquire a specific item.

        Returns same structure as get_knowledge_acquisition_paths
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (i:Item {id: $item_id})
                    MATCH (e)-[rel]->(i)
                    WHERE type(rel) IN ['GIVES', 'CONTAINS', 'REWARDS', 'GRANTS']
                    MATCH (s:Scene)-[:CONTAINS]->(e)
                    RETURN type(rel) as rel_type,
                           e.id as encounter_id,
                           e.name as encounter_name,
                           labels(e)[0] as encounter_type,
                           s.id as scene_id,
                           s.name as scene_name
                    ORDER BY s.order_sequence
                """, {"item_id": item_id})

                paths = []
                for record in result:
                    method_map = {
                        "GIVES": "npc",
                        "CONTAINS": "discovery",
                        "REWARDS": "challenge",
                        "GRANTS": "event"
                    }
                    paths.append({
                        "method": method_map.get(record["rel_type"], "unknown"),
                        "encounter_id": record["encounter_id"],
                        "encounter_name": record["encounter_name"],
                        "encounter_type": record["encounter_type"],
                        "scene_id": record["scene_id"],
                        "scene_name": record["scene_name"]
                    })

                return paths

        except Exception as e:
            logger.error(f"Error getting item acquisition paths: {str(e)}")
            return []

    def get_campaign_validation_stats(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get validation statistics for a campaign.

        Returns:
            {
                "campaign_objectives_count": 3,
                "quest_objectives_count": 8,
                "scenes_with_assignments": 15,
                "knowledge_items": 12,
                "knowledge_with_redundancy": 10,
                "items": 8,
                "items_with_redundancy": 6,
                "single_path_warnings": [...]
            }
        """
        try:
            with self.driver.session() as session:
                # Count campaign objectives
                co_result = session.run("""
                    MATCH (camp:Campaign {id: $campaign_id})-[:HAS_OBJECTIVE]->(co:CampaignObjective)
                    RETURN count(co) as count
                """, {"campaign_id": campaign_id})
                co_count = co_result.single()["count"]

                # Count quest objectives
                qo_result = session.run("""
                    MATCH (qo:QuestObjective {campaign_id: $campaign_id})
                    RETURN count(qo) as count
                """, {"campaign_id": campaign_id})
                qo_count = qo_result.single()["count"]

                # Count scenes with assignments
                scene_result = session.run("""
                    MATCH (s:Scene {campaign_id: $campaign_id})-[:ADVANCES]->()
                    RETURN count(DISTINCT s) as count
                """, {"campaign_id": campaign_id})
                scene_count = scene_result.single()["count"]

                # Knowledge stats
                kg_result = session.run("""
                    MATCH (k:Knowledge {campaign_id: $campaign_id})
                    RETURN count(k) as total,
                           sum(CASE WHEN k.has_redundancy = true THEN 1 ELSE 0 END) as with_redundancy
                """, {"campaign_id": campaign_id})
                kg_stats = kg_result.single()

                # Item stats
                item_result = session.run("""
                    MATCH (i:Item {campaign_id: $campaign_id})
                    RETURN count(i) as total,
                           sum(CASE WHEN i.has_redundancy = true THEN 1 ELSE 0 END) as with_redundancy
                """, {"campaign_id": campaign_id})
                item_stats = item_result.single()

                # Single path warnings
                warnings_result = session.run("""
                    MATCH (r)
                    WHERE r.campaign_id = $campaign_id
                      AND (r:Knowledge OR r:Item)
                      AND r.single_path_warning = true
                    RETURN r.id as resource_id,
                           r.name as resource_name,
                           labels(r)[0] as resource_type,
                           r.redundancy_paths as path_count
                """, {"campaign_id": campaign_id})

                warnings = []
                for record in warnings_result:
                    warnings.append({
                        "resource_id": record["resource_id"],
                        "resource_name": record["resource_name"],
                        "resource_type": record["resource_type"],
                        "path_count": record["path_count"]
                    })

                return {
                    "campaign_id": campaign_id,
                    "campaign_objectives_count": co_count,
                    "quest_objectives_count": qo_count,
                    "scenes_with_assignments": scene_count,
                    "knowledge_items": kg_stats["total"],
                    "knowledge_with_redundancy": kg_stats["with_redundancy"],
                    "items": item_stats["total"],
                    "items_with_redundancy": item_stats["with_redundancy"],
                    "single_path_warnings": warnings
                }

        except Exception as e:
            logger.error(f"Error getting validation stats: {str(e)}")
            return {"campaign_id": campaign_id, "error": str(e)}

    def find_unachievable_objectives(self, campaign_id: str) -> List[Dict[str, Any]]:
        """
        Find objectives that have no scenes advancing them.

        Returns:
            [
                {
                    "objective_id": "...",
                    "objective_type": "quest" or "campaign",
                    "description": "...",
                    "reason": "No scenes advance this objective"
                }
            ]
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    // Quest objectives with no scenes
                    MATCH (qo:QuestObjective {campaign_id: $campaign_id})
                    WHERE NOT (()-[:ADVANCES]->(qo))
                    RETURN qo.id as obj_id,
                           'quest' as obj_type,
                           qo.description as description,
                           'No scenes advance this objective' as reason

                    UNION

                    // Campaign objectives with no scenes or quest objectives
                    MATCH (co:CampaignObjective {campaign_id: $campaign_id})
                    WHERE NOT (()-[:ADVANCES]->(co))
                      AND NOT (co)-[:DECOMPOSES_TO]->()
                    RETURN co.id as obj_id,
                           'campaign' as obj_type,
                           co.description as description,
                           'No quest objectives or scenes' as reason
                """, {"campaign_id": campaign_id})

                unachievable = []
                for record in result:
                    unachievable.append({
                        "objective_id": record["obj_id"],
                        "objective_type": record["obj_type"],
                        "description": record["description"],
                        "reason": record["reason"]
                    })

                return unachievable

        except Exception as e:
            logger.error(f"Error finding unachievable objectives: {str(e)}")
            return []

    def get_quest_scenes_with_objectives(self, quest_id: str) -> List[Dict[str, Any]]:
        """
        Get all scenes for a quest with their objective assignments.

        Returns:
            [
                {
                    "scene_id": "...",
                    "scene_name": "...",
                    "order_sequence": 1,
                    "advances_objectives": [...],
                    "is_required": true
                }
            ]
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (q:Quest {id: $quest_id})-[:TAKES_PLACE_AT]->()-[:CONTAINS]->(s:Scene)
                    OPTIONAL MATCH (s)-[:ADVANCES]->(obj)
                    WHERE obj:QuestObjective OR obj:CampaignObjective
                    RETURN s.id as scene_id,
                           s.name as scene_name,
                           s.order_sequence as order_sequence,
                           s.is_required as is_required,
                           collect(DISTINCT {
                               id: obj.id,
                               description: obj.description,
                               type: labels(obj)[0]
                           }) as objectives
                    ORDER BY s.order_sequence
                """, {"quest_id": quest_id})

                scenes = []
                for record in result:
                    scenes.append({
                        "scene_id": record["scene_id"],
                        "scene_name": record["scene_name"],
                        "order_sequence": record["order_sequence"],
                        "is_required": record["is_required"],
                        "advances_objectives": [obj for obj in record["objectives"] if obj["id"] is not None]
                    })

                return scenes

        except Exception as e:
            logger.error(f"Error getting quest scenes: {str(e)}")
            return []

    def get_dimensional_development(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get dimensional development analysis for a campaign.

        Returns:
            {
                "dimensions": [
                    {
                        "name": "Physical",
                        "knowledge_count": 5,
                        "challenge_count": 8,
                        "coverage": "high"
                    }
                ]
            }
        """
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (d:Dimension)
                    OPTIONAL MATCH (k:Knowledge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)
                    OPTIONAL MATCH (c:Challenge {campaign_id: $campaign_id})-[:DEVELOPS]->(d)
                    RETURN d.name as dimension_name,
                           d.description as description,
                           count(DISTINCT k) as knowledge_count,
                           count(DISTINCT c) as challenge_count
                    ORDER BY d.name
                """, {"campaign_id": campaign_id})

                dimensions = []
                for record in result:
                    total = record["knowledge_count"] + record["challenge_count"]
                    coverage = "high" if total >= 3 else "medium" if total >= 1 else "low"

                    dimensions.append({
                        "name": record["dimension_name"],
                        "description": record["description"],
                        "knowledge_count": record["knowledge_count"],
                        "challenge_count": record["challenge_count"],
                        "total_coverage": total,
                        "coverage_level": coverage
                    })

                return {
                    "campaign_id": campaign_id,
                    "dimensions": dimensions
                }

        except Exception as e:
            logger.error(f"Error getting dimensional development: {str(e)}")
            return {"campaign_id": campaign_id, "error": str(e)}


# Convenience functions for direct use

async def query_objective_hierarchy(campaign_id: str, driver: Driver) -> Dict[str, Any]:
    """Convenience wrapper for getting objective hierarchy"""
    service = Neo4jQueryService(driver)
    return service.get_objective_hierarchy(campaign_id)


async def query_validation_stats(campaign_id: str, driver: Driver) -> Dict[str, Any]:
    """Convenience wrapper for getting validation statistics"""
    service = Neo4jQueryService(driver)
    return service.get_campaign_validation_stats(campaign_id)


async def query_unachievable_objectives(campaign_id: str, driver: Driver) -> List[Dict[str, Any]]:
    """Convenience wrapper for finding unachievable objectives"""
    service = Neo4jQueryService(driver)
    return service.find_unachievable_objectives(campaign_id)
