"""
Child Objective Cascade System
Handles detection, evaluation, and cascade of child objectives (discovery, challenge, event, conversation)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID

from ..core.logging import get_logger
from ..services.neo4j_graph import neo4j_graph
from ..services.rabbitmq_client import rabbitmq_client

logger = get_logger(__name__)


# ==============================================================================
# CHILD OBJECTIVE DETECTION
# ==============================================================================

async def detect_child_objective_completion(
    session_id: str,
    player_id: str,
    action_type: str,  # "conversation", "discovery", "challenge", "event"
    action_data: Dict[str, Any],
    gm_narrative: str
) -> List[Dict[str, Any]]:
    """
    Detect which child objectives were completed based on player action.

    Args:
        session_id: Game session ID
        player_id: Player ID
        action_type: Type of action (conversation, discovery, challenge, event)
        action_data: Data about the action (NPC ID, discovery ID, etc.)
        gm_narrative: GM's narrative response

    Returns:
        List of completed child objectives with evaluation data
    """
    try:
        completed_objectives = []

        if action_type == "conversation":
            completed_objectives = await _detect_conversation_objective(
                player_id, action_data, gm_narrative
            )
        elif action_type == "discovery":
            completed_objectives = await _detect_discovery_objective(
                player_id, action_data, gm_narrative
            )
        elif action_type == "challenge":
            completed_objectives = await _detect_challenge_objective(
                player_id, action_data, gm_narrative
            )
        elif action_type == "event":
            completed_objectives = await _detect_event_objective(
                player_id, action_data, gm_narrative
            )

        logger.info(
            "child_objectives_detected",
            action_type=action_type,
            detected_count=len(completed_objectives)
        )

        return completed_objectives

    except Exception as e:
        logger.error("child_objective_detection_failed", error=str(e))
        return []


async def _detect_conversation_objective(
    player_id: str,
    action_data: Dict[str, Any],
    gm_narrative: str
) -> List[Dict[str, Any]]:
    """Detect conversation objectives completed"""
    try:
        npc_id = action_data.get("npc_id")
        if not npc_id:
            return []

        # Query Neo4j for conversation objectives involving this NPC
        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (child:QuestChildObjective {objective_type: 'conversation', npc_id: $npc_id})
                MATCH (player:Player {player_id: $player_id})
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(child)
                WHERE prog.status IS NULL OR prog.status <> 'completed'
                RETURN child.objective_id as objective_id,
                       child.description as description,
                       child.required_topics as required_topics,
                       child.conversation_goal as conversation_goal,
                       child.minimum_rubric_score as min_score,
                       child.rubric_ids as rubric_ids
                """,
                npc_id=npc_id,
                player_id=player_id
            )

            objectives = []
            async for record in result:
                objectives.append({
                    "objective_id": record["objective_id"],
                    "description": record["description"],
                    "required_topics": record.get("required_topics", []),
                    "conversation_goal": record.get("conversation_goal", "gather_information"),
                    "min_score": record.get("min_score", 2.0),
                    "rubric_ids": record.get("rubric_ids", []),
                    "type": "conversation"
                })

            return objectives

    except Exception as e:
        logger.error("detect_conversation_objective_failed", error=str(e))
        return []


async def _detect_discovery_objective(
    player_id: str,
    action_data: Dict[str, Any],
    gm_narrative: str
) -> List[Dict[str, Any]]:
    """Detect discovery objectives completed"""
    try:
        discovery_id = action_data.get("discovery_id")
        scene_id = action_data.get("scene_id")

        if not discovery_id and not scene_id:
            return []

        # Query for discovery objectives in this scene
        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (child:QuestChildObjective {objective_type: 'discovery'})
                WHERE (child.discovery_entity_id = $discovery_id OR $discovery_id IS NULL)
                  AND (child.primary_scene_id = $scene_id OR $scene_id IN child.available_in_scenes)
                MATCH (player:Player {player_id: $player_id})
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(child)
                WHERE prog.status IS NULL OR prog.status <> 'completed'
                RETURN child.objective_id as objective_id,
                       child.description as description,
                       child.minimum_rubric_score as min_score,
                       child.rubric_ids as rubric_ids
                """,
                discovery_id=discovery_id,
                scene_id=scene_id,
                player_id=player_id
            )

            objectives = []
            async for record in result:
                objectives.append({
                    "objective_id": record["objective_id"],
                    "description": record["description"],
                    "min_score": record.get("min_score", 2.0),
                    "rubric_ids": record.get("rubric_ids", []),
                    "type": "discovery"
                })

            return objectives

    except Exception as e:
        logger.error("detect_discovery_objective_failed", error=str(e))
        return []


async def _detect_challenge_objective(
    player_id: str,
    action_data: Dict[str, Any],
    gm_narrative: str
) -> List[Dict[str, Any]]:
    """Detect challenge objectives completed"""
    try:
        challenge_id = action_data.get("challenge_id")
        scene_id = action_data.get("scene_id")

        if not challenge_id and not scene_id:
            return []

        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (child:QuestChildObjective {objective_type: 'challenge'})
                WHERE (child.challenge_entity_id = $challenge_id OR $challenge_id IS NULL)
                  AND (child.primary_scene_id = $scene_id OR $scene_id IN child.available_in_scenes)
                MATCH (player:Player {player_id: $player_id})
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(child)
                WHERE prog.status IS NULL OR prog.status <> 'completed'
                RETURN child.objective_id as objective_id,
                       child.description as description,
                       child.minimum_rubric_score as min_score,
                       child.rubric_ids as rubric_ids
                """,
                challenge_id=challenge_id,
                scene_id=scene_id,
                player_id=player_id
            )

            objectives = []
            async for record in result:
                objectives.append({
                    "objective_id": record["objective_id"],
                    "description": record["description"],
                    "min_score": record.get("min_score", 2.0),
                    "rubric_ids": record.get("rubric_ids", []),
                    "type": "challenge"
                })

            return objectives

    except Exception as e:
        logger.error("detect_challenge_objective_failed", error=str(e))
        return []


async def _detect_event_objective(
    player_id: str,
    action_data: Dict[str, Any],
    gm_narrative: str
) -> List[Dict[str, Any]]:
    """Detect event objectives completed"""
    try:
        event_id = action_data.get("event_id")
        scene_id = action_data.get("scene_id")

        if not event_id and not scene_id:
            return []

        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (child:QuestChildObjective {objective_type: 'event'})
                WHERE (child.event_entity_id = $event_id OR $event_id IS NULL)
                  AND (child.primary_scene_id = $scene_id OR $scene_id IN child.available_in_scenes)
                MATCH (player:Player {player_id: $player_id})
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(child)
                WHERE prog.status IS NULL OR prog.status <> 'completed'
                RETURN child.objective_id as objective_id,
                       child.description as description,
                       child.minimum_rubric_score as min_score,
                       child.rubric_ids as rubric_ids
                """,
                event_id=event_id,
                scene_id=scene_id,
                player_id=player_id
            )

            objectives = []
            async for record in result:
                objectives.append({
                    "objective_id": record["objective_id"],
                    "description": record["description"],
                    "min_score": record.get("min_score", 2.0),
                    "rubric_ids": record.get("rubric_ids", []),
                    "type": "event"
                })

            return objectives

    except Exception as e:
        logger.error("detect_event_objective_failed", error=str(e))
        return []


# ==============================================================================
# RUBRIC EVALUATION
# ==============================================================================

async def evaluate_child_objective_with_rubric(
    child_objective: Dict[str, Any],
    action_data: Dict[str, Any],
    gm_narrative: str
) -> float:
    """
    Evaluate player performance using rubric.

    Uses AI to evaluate based on rubric criteria.
    Returns score (1.0-4.0)

    Args:
        child_objective: Child objective data with rubric IDs
        action_data: Player action data (conversation history, discovery details, etc.)
        gm_narrative: GM's narrative response

    Returns:
        Rubric score (1.0-4.0)
    """
    try:
        from anthropic import AsyncAnthropic
        import os

        # Get rubric from MongoDB
        from ..services.mongo_persistence import mongo_persistence
        rubric_ids = child_objective.get("rubric_ids", [])
        if not rubric_ids:
            logger.warning("no_rubric_ids_for_objective", objective_id=child_objective["objective_id"])
            return 2.5  # Default pass score

        rubric_id = rubric_ids[0]  # Use first rubric
        rubric = await mongo_persistence.get_rubric_by_id(rubric_id)

        if not rubric:
            logger.warning("rubric_not_found", rubric_id=rubric_id)
            return 2.5

        # Build evaluation prompt
        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        criteria_text = "\n".join([
            f"{i+1}. {crit['criterion']} (weight: {crit['weight']})\n" +
            "\n".join([f"   Level {level['level']}: {level['description']}" for level in crit['levels']])
            for i, crit in enumerate(rubric['evaluation_criteria'])
        ])

        evaluation_prompt = f"""Evaluate player performance using this rubric:

OBJECTIVE: {child_objective['description']}

RUBRIC CRITERIA:
{criteria_text}

PLAYER ACTION:
{action_data.get('action', 'Not specified')}

GM NARRATIVE:
{gm_narrative}

For each criterion, assign a score from 1-4 based on the player's performance.
Return ONLY a JSON object with this format:
{{
  "scores": {{"Criterion Name": 1-4, ...}},
  "overall_assessment": "brief explanation"
}}"""

        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": evaluation_prompt}]
        )

        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        import json
        evaluation = json.loads(content)
        scores = evaluation.get("scores", {})

        # Calculate weighted average
        total_score = 0.0
        total_weight = 0.0

        for criterion in rubric['evaluation_criteria']:
            criterion_name = criterion['criterion']
            weight = criterion['weight']
            score = scores.get(criterion_name, 2)  # Default to 2 if not found

            total_score += score * weight
            total_weight += weight

        final_score = total_score / total_weight if total_weight > 0 else 2.5

        logger.info(
            "child_objective_evaluated",
            objective_id=child_objective["objective_id"],
            rubric_score=final_score,
            criterion_scores=scores
        )

        return final_score

    except Exception as e:
        logger.error("rubric_evaluation_failed", error=str(e))
        return 2.5  # Default pass score on error


# ==============================================================================
# CASCADE LOGIC
# ==============================================================================

async def mark_child_objective_complete(
    player_id: str,
    child_objective_id: str,
    rubric_score: float
) -> Dict[str, Any]:
    """
    Mark child objective as complete and initiate cascade check.

    Returns:
        Dict with cascade results (quest objectives affected, campaign objectives affected)
    """
    try:
        # Update Neo4j
        async with neo4j_graph.driver.session() as session:
            await session.run(
                """
                MATCH (player:Player {player_id: $player_id})
                MATCH (child:QuestChildObjective {objective_id: $child_id})
                MERGE (player)-[prog:PROGRESS]->(child)
                SET prog.status = 'completed',
                    prog.rubric_score = $score,
                    prog.completed_at = datetime(),
                    prog.completion_percentage = 100,
                    child.status = 'completed'
                """,
                player_id=player_id,
                child_id=child_objective_id,
                score=rubric_score
            )

        logger.info(
            "child_objective_marked_complete",
            player_id=player_id,
            objective_id=child_objective_id,
            rubric_score=rubric_score
        )

        # Check quest objective cascade
        cascade_updates = await check_quest_objective_cascade(player_id, child_objective_id)

        return cascade_updates

    except Exception as e:
        logger.error("mark_child_objective_complete_failed", error=str(e))
        return {"quest_objectives": [], "campaign_objectives": []}


async def check_quest_objective_cascade(
    player_id: str,
    child_objective_id: str
) -> Dict[str, Any]:
    """
    Check if completing this child objective completes any quest objectives.

    Returns:
        Dict with completed quest and campaign objectives
    """
    try:
        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (child:QuestChildObjective {objective_id: $child_id})
                MATCH (child)-[:SUPPORTS]->(quest_obj:QuestObjective)
                MATCH (player:Player {player_id: $player_id})

                // Get all children of this quest objective
                MATCH (quest_obj)<-[:SUPPORTS]-(all_children:QuestChildObjective)

                // Get player progress on all children
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(all_children)

                WITH quest_obj,
                     collect({
                         child_id: all_children.objective_id,
                         is_required: all_children.is_required,
                         status: COALESCE(prog.status, 'not_started'),
                         rubric_score: prog.rubric_score
                     }) as children_status,
                     quest_obj.completion_type as completion_type

                RETURN quest_obj.objective_id as quest_obj_id,
                       quest_obj.description as quest_obj_desc,
                       completion_type,
                       children_status
                """,
                child_id=child_objective_id,
                player_id=player_id
            )

            completed_quest_objectives = []
            async for record in result:
                quest_obj_id = record["quest_obj_id"]
                completion_type = record.get("completion_type", "all")
                children = record["children_status"]

                # Check if quest objective should complete
                required_children = [c for c in children if c["is_required"]]
                completed_required = [c for c in required_children if c["status"] == "completed"]

                is_complete = False
                if completion_type == "all":
                    is_complete = len(completed_required) == len(required_children) and len(required_children) > 0
                elif completion_type == "any":
                    is_complete = len(completed_required) > 0
                elif completion_type == "threshold":
                    threshold = 0.8  # 80% default
                    is_complete = len(required_children) > 0 and (len(completed_required) / len(required_children)) >= threshold

                if is_complete:
                    # Calculate average rubric score
                    rubric_scores = [c["rubric_score"] for c in completed_required if c.get("rubric_score")]
                    avg_score = sum(rubric_scores) / len(rubric_scores) if rubric_scores else 2.5

                    # Mark quest objective complete
                    await mark_quest_objective_complete(player_id, quest_obj_id, avg_score)

                    completed_quest_objectives.append({
                        "objective_id": quest_obj_id,
                        "description": record["quest_obj_desc"],
                        "avg_rubric_score": avg_score
                    })

            # Check campaign objective cascade
            completed_campaign_objectives = []
            for quest_obj in completed_quest_objectives:
                campaign_updates = await check_campaign_objective_cascade(
                    player_id, quest_obj["objective_id"]
                )
                completed_campaign_objectives.extend(campaign_updates)

            return {
                "quest_objectives": completed_quest_objectives,
                "campaign_objectives": completed_campaign_objectives
            }

    except Exception as e:
        logger.error("quest_objective_cascade_failed", error=str(e))
        return {"quest_objectives": [], "campaign_objectives": []}


async def mark_quest_objective_complete(
    player_id: str,
    quest_objective_id: str,
    avg_rubric_score: float
):
    """Mark quest objective as complete"""
    try:
        async with neo4j_graph.driver.session() as session:
            await session.run(
                """
                MATCH (player:Player {player_id: $player_id})
                MATCH (quest_obj:QuestObjective {objective_id: $quest_obj_id})
                MERGE (player)-[prog:PROGRESS]->(quest_obj)
                SET prog.status = 'completed',
                    prog.avg_rubric_score = $score,
                    prog.completed_at = datetime(),
                    prog.completion_percentage = 100,
                    quest_obj.status = 'completed'
                """,
                player_id=player_id,
                quest_obj_id=quest_objective_id,
                score=avg_rubric_score
            )

        logger.info(
            "quest_objective_marked_complete",
            player_id=player_id,
            objective_id=quest_objective_id
        )

    except Exception as e:
        logger.error("mark_quest_objective_complete_failed", error=str(e))


async def check_campaign_objective_cascade(
    player_id: str,
    quest_objective_id: str
) -> List[Dict[str, Any]]:
    """
    Check if completing this quest objective completes any campaign objectives.

    Returns:
        List of completed campaign objectives
    """
    try:
        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (quest_obj:QuestObjective {objective_id: $quest_obj_id})
                MATCH (quest_obj)-[:SUPPORTS]->(campaign_obj:CampaignObjective)
                MATCH (player:Player {player_id: $player_id})

                // Get all quest objectives supporting this campaign objective
                MATCH (campaign_obj)<-[:SUPPORTS]-(all_quest_objs:QuestObjective)

                // Get player progress
                OPTIONAL MATCH (player)-[prog:PROGRESS]->(all_quest_objs)

                WITH campaign_obj,
                     collect({
                         quest_obj_id: all_quest_objs.objective_id,
                         status: COALESCE(prog.status, 'not_started'),
                         avg_rubric_score: prog.avg_rubric_score
                     }) as quest_objectives_status,
                     campaign_obj.completion_type as completion_type,
                     campaign_obj.required_quest_count as required_count

                RETURN campaign_obj.objective_id as campaign_obj_id,
                       campaign_obj.description as campaign_obj_desc,
                       completion_type,
                       required_count,
                       quest_objectives_status
                """,
                quest_obj_id=quest_objective_id,
                player_id=player_id
            )

            completed_campaign_objectives = []
            async for record in result:
                campaign_obj_id = record["campaign_obj_id"]
                completion_type = record.get("completion_type", "threshold")
                required_count = record.get("required_count", 2)
                quest_objs = record["quest_objectives_status"]

                completed_quest_objs = [q for q in quest_objs if q["status"] == "completed"]

                is_complete = False
                if completion_type == "all_quests":
                    is_complete = len(completed_quest_objs) == len(quest_objs) and len(quest_objs) > 0
                elif completion_type == "any_quests":
                    is_complete = len(completed_quest_objs) > 0
                elif completion_type == "threshold":
                    is_complete = len(completed_quest_objs) >= required_count

                if is_complete:
                    # Calculate overall quality score
                    rubric_scores = [q["avg_rubric_score"] for q in completed_quest_objs if q.get("avg_rubric_score")]
                    overall_score = sum(rubric_scores) / len(rubric_scores) if rubric_scores else 2.5

                    # Mark campaign objective complete
                    await mark_campaign_objective_complete(player_id, campaign_obj_id, overall_score)

                    completed_campaign_objectives.append({
                        "objective_id": campaign_obj_id,
                        "description": record["campaign_obj_desc"],
                        "overall_quality_score": overall_score
                    })

            return completed_campaign_objectives

    except Exception as e:
        logger.error("campaign_objective_cascade_failed", error=str(e))
        return []


async def mark_campaign_objective_complete(
    player_id: str,
    campaign_objective_id: str,
    overall_quality_score: float
):
    """Mark campaign objective as complete"""
    try:
        async with neo4j_graph.driver.session() as session:
            await session.run(
                """
                MATCH (player:Player {player_id: $player_id})
                MATCH (campaign_obj:CampaignObjective {objective_id: $campaign_obj_id})
                MERGE (player)-[prog:PROGRESS]->(campaign_obj)
                SET prog.status = 'completed',
                    prog.overall_quality_score = $score,
                    prog.completed_at = datetime(),
                    prog.completion_percentage = 100,
                    campaign_obj.status = 'completed'
                """,
                player_id=player_id,
                campaign_obj_id=campaign_objective_id,
                score=overall_quality_score
            )

        logger.info(
            "campaign_objective_marked_complete",
            player_id=player_id,
            objective_id=campaign_objective_id
        )

    except Exception as e:
        logger.error("mark_campaign_objective_complete_failed", error=str(e))


# ==============================================================================
# EVENT PUBLISHING
# ==============================================================================

async def publish_child_objective_completed_event(
    session_id: str,
    player_id: str,
    child_objective: Dict[str, Any],
    rubric_score: float,
    cascade_updates: Dict[str, Any]
):
    """Publish ChildObjectiveCompletedEvent to RabbitMQ"""
    try:
        quality = "minimal" if rubric_score < 2.0 else "good" if rubric_score < 3.0 else "excellent"

        await rabbitmq_client.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.child_objective_completed",
            message={
                "type": "event",
                "event_type": "child_objective_completed",
                "session_id": session_id,
                "payload": {
                    "player_id": player_id,
                    "child_objective_id": child_objective["objective_id"],
                    "child_objective_type": child_objective["type"],
                    "description": child_objective["description"],
                    "rubric_score": rubric_score,
                    "completion_quality": quality,
                    "cascade_updates": cascade_updates,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        logger.info(
            "child_objective_completed_event_published",
            objective_id=child_objective["objective_id"],
            quality=quality
        )

    except Exception as e:
        logger.error("publish_child_objective_event_failed", error=str(e))


async def publish_quest_objective_completed_event(
    session_id: str,
    player_id: str,
    quest_objective: Dict[str, Any]
):
    """Publish QuestObjectiveCompletedEvent to RabbitMQ"""
    try:
        await rabbitmq_client.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.quest_objective_completed",
            message={
                "type": "event",
                "event_type": "quest_objective_completed",
                "session_id": session_id,
                "payload": {
                    "player_id": player_id,
                    "quest_objective_id": quest_objective["objective_id"],
                    "description": quest_objective["description"],
                    "avg_rubric_score": quest_objective["avg_rubric_score"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        logger.info(
            "quest_objective_completed_event_published",
            objective_id=quest_objective["objective_id"]
        )

    except Exception as e:
        logger.error("publish_quest_objective_event_failed", error=str(e))


async def publish_campaign_objective_completed_event(
    session_id: str,
    player_id: str,
    campaign_objective: Dict[str, Any]
):
    """Publish CampaignObjectiveCompletedEvent to RabbitMQ"""
    try:
        await rabbitmq_client.publish_event(
            exchange="game.events",
            routing_key=f"session.{session_id}.campaign_objective_completed",
            message={
                "type": "event",
                "event_type": "campaign_objective_completed",
                "session_id": session_id,
                "payload": {
                    "player_id": player_id,
                    "campaign_objective_id": campaign_objective["objective_id"],
                    "description": campaign_objective["description"],
                    "overall_quality_score": campaign_objective["overall_quality_score"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        logger.info(
            "campaign_objective_completed_event_published",
            objective_id=campaign_objective["objective_id"]
        )

    except Exception as e:
        logger.error("publish_campaign_objective_event_failed", error=str(e))


# ==============================================================================
# MAIN ORCHESTRATION
# ==============================================================================

async def process_player_action_for_objectives(
    session_id: str,
    player_id: str,
    action_type: str,
    action_data: Dict[str, Any],
    gm_narrative: str
) -> Dict[str, Any]:
    """
    Main entry point: Process player action and handle all objective updates.

    Args:
        session_id: Game session ID
        player_id: Player ID
        action_type: Type of action (conversation, discovery, challenge, event)
        action_data: Action details
        gm_narrative: GM's response

    Returns:
        Dict with summary of completed objectives and cascade updates
    """
    try:
        # 1. Detect completed child objectives
        detected_objectives = await detect_child_objective_completion(
            session_id, player_id, action_type, action_data, gm_narrative
        )

        if not detected_objectives:
            logger.info("no_child_objectives_detected", action_type=action_type)
            return {"completed_objectives": [], "cascade_updates": []}

        all_cascade_updates = []

        # 2. Evaluate and complete each objective
        for child_obj in detected_objectives:
            # Evaluate with rubric
            rubric_score = await evaluate_child_objective_with_rubric(
                child_obj, action_data, gm_narrative
            )

            # Check if meets minimum score
            if rubric_score >= child_obj.get("min_score", 2.0):
                # Mark complete and cascade
                cascade_updates = await mark_child_objective_complete(
                    player_id, child_obj["objective_id"], rubric_score
                )

                all_cascade_updates.append({
                    "child_objective": child_obj,
                    "rubric_score": rubric_score,
                    "cascade": cascade_updates
                })

                # Publish events
                await publish_child_objective_completed_event(
                    session_id, player_id, child_obj, rubric_score, cascade_updates
                )

                # Publish quest objective events
                for quest_obj in cascade_updates.get("quest_objectives", []):
                    await publish_quest_objective_completed_event(
                        session_id, player_id, quest_obj
                    )

                # Publish campaign objective events
                for campaign_obj in cascade_updates.get("campaign_objectives", []):
                    await publish_campaign_objective_completed_event(
                        session_id, player_id, campaign_obj
                    )
            else:
                logger.info(
                    "child_objective_not_complete",
                    objective_id=child_obj["objective_id"],
                    rubric_score=rubric_score,
                    min_required=child_obj.get("min_score", 2.0)
                )

        logger.info(
            "player_action_processed_for_objectives",
            session_id=session_id,
            detected=len(detected_objectives),
            completed=len(all_cascade_updates)
        )

        return {
            "completed_objectives": all_cascade_updates,
            "total_detected": len(detected_objectives),
            "total_completed": len(all_cascade_updates)
        }

    except Exception as e:
        logger.error("process_player_action_for_objectives_failed", error=str(e))
        return {"completed_objectives": [], "cascade_updates": []}
