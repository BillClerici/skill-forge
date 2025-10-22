"""
Objective Tracking System
Handles acquisition detection, objective linking, and progress calculation
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..core.logging import get_logger
from ..services.neo4j_graph import neo4j_graph
from ..services.rabbitmq_client import rabbitmq_client

logger = get_logger(__name__)


async def detect_acquisitions_from_narrative(
    narrative: str,
    player_action: str,
    scene_context: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Analyze GM narrative to detect what the player acquired or completed.

    Uses LLM to extract:
    - Knowledge gained
    - Items obtained
    - Events participated in
    - Challenges completed

    Args:
        narrative: The GM's narrative response
        player_action: What the player did
        scene_context: Available discoveries, items, events, challenges in scene

    Returns:
        Dict with keys: knowledge, items, events, challenges
        Each containing list of acquisition dicts with name, description, etc.
    """
    # TODO: Implement LLM-based extraction
    # For now, return empty to build infrastructure
    return {
        "knowledge": [],
        "items": [],
        "events": [],
        "challenges": []
    }


async def link_acquisition_to_objectives(
    player_id: str,
    campaign_id: str,
    acquisition_type: str,  # "knowledge", "item", "event", "challenge"
    acquisition_id: str
) -> List[Dict[str, Any]]:
    """
    Query Neo4j to find which objectives this acquisition contributes to.

    Returns list of affected objectives with:
    - objective_id
    - objective_description
    - objective_type (quest/campaign)
    - contribution_type (required/advances/optional)
    - new_progress_percentage

    Args:
        player_id: Player ID
        campaign_id: Campaign ID
        acquisition_type: Type of acquisition
        acquisition_id: ID of the acquired thing

    Returns:
        List of affected objectives with progress updates
    """
    try:
        affected_objectives = []

        # Query based on acquisition type
        if acquisition_type == "knowledge":
            # Find objectives that this knowledge advances
            query = """
            MATCH (k:Knowledge {id: $acquisition_id})
            MATCH (qo:QuestObjective)-[:REQUIRES_KNOWLEDGE]->(k)
            MATCH (p:Player {player_id: $player_id})-[prog:PROGRESS]->(qo)
            MATCH (q:Quest)-[:ACHIEVES]->(qo)
            OPTIONAL MATCH (co:CampaignObjective)-[:DECOMPOSES_TO]->(qo)
            RETURN qo.id as objective_id,
                   qo.description as objective_description,
                   'quest' as objective_type,
                   q.name as quest_name,
                   co.id as campaign_objective_id,
                   co.description as campaign_objective_description,
                   COALESCE(prog.percentage, 0) as current_progress
            """

            async with neo4j_graph.driver.session() as session:
                result = await session.run(
                    query,
                    acquisition_id=acquisition_id,
                    player_id=player_id
                )

                async for record in result:
                    affected_objectives.append({
                        "objective_id": record["objective_id"],
                        "objective_description": record["objective_description"],
                        "objective_type": record["objective_type"],
                        "quest_name": record["quest_name"],
                        "campaign_objective_id": record.get("campaign_objective_id"),
                        "campaign_objective_description": record.get("campaign_objective_description"),
                        "current_progress": record["current_progress"],
                        "contribution_type": "required"
                    })

        elif acquisition_type == "item":
            # Similar query for items
            query = """
            MATCH (i:Item {id: $acquisition_id})
            MATCH (qo:QuestObjective)-[:REQUIRES_ITEM]->(i)
            MATCH (p:Player {player_id: $player_id})-[prog:PROGRESS]->(qo)
            MATCH (q:Quest)-[:ACHIEVES]->(qo)
            OPTIONAL MATCH (co:CampaignObjective)-[:DECOMPOSES_TO]->(qo)
            RETURN qo.id as objective_id,
                   qo.description as objective_description,
                   'quest' as objective_type,
                   q.name as quest_name,
                   co.id as campaign_objective_id,
                   co.description as campaign_objective_description,
                   COALESCE(prog.percentage, 0) as current_progress
            """

            async with neo4j_graph.driver.session() as session:
                result = await session.run(
                    query,
                    acquisition_id=acquisition_id,
                    player_id=player_id
                )

                async for record in result:
                    affected_objectives.append({
                        "objective_id": record["objective_id"],
                        "objective_description": record["objective_description"],
                        "objective_type": record["objective_type"],
                        "quest_name": record["quest_name"],
                        "campaign_objective_id": record.get("campaign_objective_id"),
                        "campaign_objective_description": record.get("campaign_objective_description"),
                        "current_progress": record["current_progress"],
                        "contribution_type": "required"
                    })

        logger.info(
            "acquisition_linked_to_objectives",
            acquisition_type=acquisition_type,
            acquisition_id=acquisition_id,
            affected_count=len(affected_objectives)
        )

        return affected_objectives

    except Exception as e:
        logger.error("link_acquisition_failed", error=str(e))
        return []


async def calculate_objective_progress(
    player_id: str,
    objective_id: str
) -> int:
    """
    Calculate completion percentage for a specific objective.

    Checks:
    - Required knowledge (player has it?)
    - Required items (player has it?)
    - Required events (player completed it?)
    - Required challenges (player completed it?)

    Returns percentage 0-100
    """
    try:
        query = """
        MATCH (qo:QuestObjective {id: $objective_id})
        OPTIONAL MATCH (qo)-[:REQUIRES_KNOWLEDGE]->(k:Knowledge)
        OPTIONAL MATCH (qo)-[:REQUIRES_ITEM]->(i:Item)
        OPTIONAL MATCH (p:Player {player_id: $player_id})

        // Count total requirements
        WITH qo, p,
             count(DISTINCT k) as total_knowledge,
             count(DISTINCT i) as total_items

        // Count what player has
        OPTIONAL MATCH (p)-[:HAS_KNOWLEDGE]->(k2:Knowledge)<-[:REQUIRES_KNOWLEDGE]-(qo)
        OPTIONAL MATCH (p)-[:HAS_ITEM]->(i2:Item)<-[:REQUIRES_ITEM]-(qo)

        WITH qo, p, total_knowledge, total_items,
             count(DISTINCT k2) as acquired_knowledge,
             count(DISTINCT i2) as acquired_items

        // Calculate percentage
        WITH qo,
             (total_knowledge + total_items) as total_required,
             (acquired_knowledge + acquired_items) as total_acquired

        RETURN CASE
            WHEN total_required = 0 THEN 0
            ELSE toInteger((toFloat(total_acquired) / toFloat(total_required)) * 100)
        END as percentage
        """

        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                query,
                objective_id=objective_id,
                player_id=player_id
            )

            record = await result.single()
            if record:
                percentage = record.get("percentage", 0)
                logger.info(
                    "objective_progress_calculated",
                    objective_id=objective_id,
                    percentage=percentage
                )
                return percentage

            return 0

    except Exception as e:
        logger.error("calculate_progress_failed", error=str(e))
        return 0


async def update_objective_progress(
    player_id: str,
    objective_id: str,
    new_percentage: int
) -> bool:
    """
    Update the progress relationship between player and objective.

    Creates or updates PROGRESS relationship with new percentage.
    Marks as completed if percentage reaches 100.
    """
    try:
        query = """
        MATCH (p:Player {player_id: $player_id})
        MATCH (qo:QuestObjective {id: $objective_id})

        MERGE (p)-[prog:PROGRESS]->(qo)
        SET prog.percentage = $percentage,
            prog.updated_at = datetime(),
            prog.status = CASE
                WHEN $percentage >= 100 THEN 'completed'
                WHEN $percentage > 0 THEN 'in_progress'
                ELSE 'not_started'
            END

        WITH qo, prog
        WHERE prog.status = 'completed' AND prog.completed_at IS NULL
        SET prog.completed_at = datetime(),
            qo.status = 'completed'

        RETURN prog.status as status, prog.percentage as percentage
        """

        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                query,
                player_id=player_id,
                objective_id=objective_id,
                percentage=new_percentage
            )

            record = await result.single()
            if record:
                logger.info(
                    "objective_progress_updated",
                    objective_id=objective_id,
                    percentage=new_percentage,
                    status=record.get("status")
                )
                return True

            return False

    except Exception as e:
        logger.error("update_progress_failed", error=str(e))
        return False


async def publish_acquisition_event(
    session_id: str,
    player_id: str,
    acquisition_type: str,
    acquisition_data: Dict[str, Any],
    affected_objectives: List[Dict[str, Any]]
):
    """
    Publish event for a single acquisition with objective impacts.

    This triggers toast notifications in the UI showing:
    - What was acquired
    - Which objectives were affected
    - New progress percentages
    """
    try:
        event_type = f"{acquisition_type}_acquired"

        await rabbitmq_client.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.{event_type}",
            message={
                "type": "event",
                "event_type": event_type,
                "session_id": session_id,
                "payload": {
                    "acquisition": acquisition_data,
                    "affected_objectives": affected_objectives,
                    "player_id": player_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        logger.info(
            "acquisition_event_published",
            session_id=session_id,
            acquisition_type=acquisition_type,
            affected_objectives_count=len(affected_objectives)
        )

    except Exception as e:
        logger.error("publish_acquisition_event_failed", error=str(e))


async def process_acquisitions(
    session_id: str,
    player_id: str,
    campaign_id: str,
    acquisitions: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Main orchestration function to process all acquisitions.

    For each acquisition:
    1. Link to objectives
    2. Calculate new progress
    3. Update progress in Neo4j
    4. Publish individual events
    5. Return summary of all changes

    Returns:
        Dict with acquisition summaries and objective updates
    """
    try:
        all_affected_objectives = []
        acquisition_summary = []

        # Process knowledge
        for knowledge in acquisitions.get("knowledge", []):
            knowledge_id = knowledge.get("id")

            # Fetch full knowledge details from MongoDB
            from ..services.mongo_persistence import mongo_persistence
            knowledge_full = await mongo_persistence.get_knowledge_by_id(knowledge_id)

            logger.info(
                "mongodb_knowledge_fetch",
                knowledge_id=knowledge_id,
                knowledge_full=knowledge_full,
                has_data=bool(knowledge_full)
            )

            if knowledge_full:
                # Merge full details with acquisition data
                knowledge_data = {
                    "id": knowledge_id,
                    "name": knowledge_full.get("name", "Unknown Knowledge"),
                    "description": knowledge_full.get("description", ""),
                    "purpose": knowledge_full.get("purpose", ""),
                    "acquired_at": knowledge.get("acquired_at", datetime.utcnow().isoformat())
                }
            else:
                knowledge_data = knowledge

            logger.info(
                "knowledge_data_prepared",
                knowledge_data=knowledge_data
            )

            affected = await link_acquisition_to_objectives(
                player_id, campaign_id, "knowledge", knowledge_id
            )

            # Calculate and update progress for each affected objective
            for obj in affected:
                new_progress = await calculate_objective_progress(
                    player_id, obj["objective_id"]
                )
                obj["new_progress"] = new_progress

                await update_objective_progress(
                    player_id, obj["objective_id"], new_progress
                )

            # Publish event with full knowledge details
            await publish_acquisition_event(
                session_id, player_id, "knowledge", knowledge_data, affected
            )

            acquisition_summary.append({
                "type": "knowledge",
                "data": knowledge_data,
                "objectives_affected": len(affected)
            })
            all_affected_objectives.extend(affected)

        # Process items (similar pattern)
        for item in acquisitions.get("items", []):
            affected = await link_acquisition_to_objectives(
                player_id, campaign_id, "item", item.get("id")
            )

            for obj in affected:
                new_progress = await calculate_objective_progress(
                    player_id, obj["objective_id"]
                )
                obj["new_progress"] = new_progress

                await update_objective_progress(
                    player_id, obj["objective_id"], new_progress
                )

            await publish_acquisition_event(
                session_id, player_id, "item", item, affected
            )

            acquisition_summary.append({
                "type": "item",
                "data": item,
                "objectives_affected": len(affected)
            })
            all_affected_objectives.extend(affected)

        # TODO: Process events and challenges similarly

        logger.info(
            "acquisitions_processed",
            session_id=session_id,
            total_acquisitions=len(acquisition_summary),
            total_objectives_affected=len(all_affected_objectives)
        )

        return {
            "acquisitions": acquisition_summary,
            "affected_objectives": all_affected_objectives
        }

    except Exception as e:
        logger.error("process_acquisitions_failed", error=str(e))
        return {
            "acquisitions": [],
            "affected_objectives": []
        }
