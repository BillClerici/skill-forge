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
    try:
        from anthropic import AsyncAnthropic
        import os

        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        extraction_prompt = f"""Analyze this game narrative and extract what the player learned, obtained, or accomplished.

Player Action: {player_action}

GM Narrative Response:
{narrative}

Extract and return a JSON object with these categories:

1. "knowledge" - Facts, clues, information, or insights the player learned
   - Each should have: name (brief title), description (what they learned), type ("clue", "fact", "insight")

2. "items" - Physical objects the player obtained
   - Each should have: name, description, properties (if any)

3. "events" - Significant events that occurred or were completed
   - Each should have: name, description

4. "challenges" - Tasks or challenges the player completed
   - Each should have: name, description

Return ONLY valid JSON in this exact format:
{{
  "knowledge": [
    {{"name": "...", "description": "...", "type": "clue"}}
  ],
  "items": [],
  "events": [],
  "challenges": []
}}

If nothing was acquired in a category, use an empty array []."""

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": extraction_prompt
            }]
        )

        # Parse JSON from response
        import json
        content = response.content[0].text.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        acquisitions = json.loads(content)

        logger.info(
            "acquisitions_extracted",
            knowledge_count=len(acquisitions.get("knowledge", [])),
            items_count=len(acquisitions.get("items", [])),
            events_count=len(acquisitions.get("events", [])),
            challenges_count=len(acquisitions.get("challenges", []))
        )

        return acquisitions

    except Exception as e:
        logger.error("acquisition_extraction_failed", error=str(e))
        return {
            "knowledge": [],
            "items": [],
            "events": [],
            "challenges": []
        }


async def match_extracted_knowledge_to_existing(
    campaign_id: str,
    extracted_name: str,
    extracted_description: str,
    extracted_type: str
) -> Optional[str]:
    """
    Use LLM to semantically match extracted knowledge to existing Knowledge nodes.

    Args:
        campaign_id: Campaign ID to search within
        extracted_name: Name of extracted knowledge (e.g., "Multiple Footprint Sets")
        extracted_description: Description of what was learned
        extracted_type: Type of knowledge (clue, fact, insight)

    Returns:
        Knowledge ID if match found, None otherwise
    """
    try:
        from anthropic import AsyncAnthropic
        import os
        import json

        # Get knowledge nodes for this campaign, prioritizing those linked to objectives
        async with neo4j_graph.driver.session() as session:
            result = await session.run(
                """
                MATCH (k:Knowledge {campaign_id: $campaign_id})
                OPTIONAL MATCH (qo:QuestObjective)-[:REQUIRES_KNOWLEDGE]->(k)
                WITH k, COUNT(qo) as objective_count
                RETURN k.id as id,
                       k.name as name,
                       k.description as description,
                       objective_count,
                       CASE WHEN objective_count > 0 THEN true ELSE false END as is_required
                ORDER BY is_required DESC, objective_count DESC
                LIMIT 50
                """,
                campaign_id=campaign_id
            )

            available_knowledge = []
            required_knowledge = []
            async for record in result:
                knowledge_entry = {
                    "id": record["id"],
                    "name": record["name"],
                    "description": record.get("description", ""),
                    "is_required": record.get("is_required", False)
                }
                available_knowledge.append(knowledge_entry)
                if record.get("is_required"):
                    required_knowledge.append(knowledge_entry)

        if not available_knowledge:
            logger.warning("no_knowledge_nodes_in_campaign", campaign_id=campaign_id)
            return None

        # Use LLM to find best match
        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Build matching prompt with priority for required knowledge
        priority_section = ""
        if required_knowledge:
            priority_section = f"""
PRIORITY - These knowledge items are required for active quest objectives (try to match to these first):
{json.dumps(required_knowledge, indent=2)}
"""

        matching_prompt = f"""You are matching extracted game knowledge to pre-defined knowledge categories.

Extracted Knowledge:
- Name: {extracted_name}
- Description: {extracted_description}
- Type: {extracted_type}

{priority_section}

All Available Knowledge Categories:
{json.dumps(available_knowledge, indent=2)}

IMPORTANT: Prioritize matching to knowledge items marked with "is_required": true as these are needed for quest objectives.

Find the BEST matching knowledge category. Examples:
- "Crystal Fragment Analysis" matches "Sonic Artifact Analysis" (analyzing sonic artifacts)
- "Evidence Documentation" matches "Crime Scene Investigation" (investigating crime scenes)
- "Tribal Greeting Customs" matches "Tribal Communication Protocols" (tribal interaction)

Return ONLY a JSON object with the matching knowledge ID, or null if no good match:
{{"matched_id": "knowledge_xxx" OR null, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": matching_prompt}]
        )

        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        match_result = json.loads(content)
        matched_id = match_result.get("matched_id")
        confidence = match_result.get("confidence", 0)

        if matched_id and confidence > 0.5:
            logger.info(
                "knowledge_matched",
                extracted=extracted_name,
                matched_to=matched_id,
                confidence=confidence,
                reasoning=match_result.get("reasoning")
            )
            return matched_id
        else:
            logger.info(
                "knowledge_no_match",
                extracted=extracted_name,
                confidence=confidence
            )
            return None

    except Exception as e:
        logger.error("knowledge_matching_failed", error=str(e))
        return None


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
            MATCH (p:Player {player_id: $player_id})
            OPTIONAL MATCH (p)-[prog:PROGRESS]->(qo)
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
            MATCH (i:Item {item_id: $acquisition_id})
            MATCH (qo:QuestObjective)-[:REQUIRES_ITEM]->(i)
            MATCH (p:Player {player_id: $player_id})
            OPTIONAL MATCH (p)-[prog:PROGRESS]->(qo)
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
    if not player_id or not objective_id:
        logger.error(
            "CRITICAL_ERROR_calculate_progress_invalid_params",
            player_id=player_id,
            objective_id=objective_id
        )
        return 0

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
        OPTIONAL MATCH (p)-[:ACQUIRED_KNOWLEDGE]->(k2:Knowledge)<-[:REQUIRES_KNOWLEDGE]-(qo)
        OPTIONAL MATCH (p)-[:ACQUIRED_ITEM]->(i2:Item)<-[:REQUIRES_ITEM]-(qo)

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
        END as percentage,
        total_required,
        total_acquired
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
                total_required = record.get("total_required", 0)
                total_acquired = record.get("total_acquired", 0)
                logger.info(
                    "objective_progress_calculated_detailed",
                    objective_id=objective_id,
                    player_id=player_id,
                    percentage=percentage,
                    total_required=total_required,
                    total_acquired=total_acquired
                )
                return percentage
            else:
                logger.warning(
                    "calculate_progress_no_record_returned",
                    objective_id=objective_id,
                    player_id=player_id
                )
                return 0

    except Exception as e:
        logger.error(
            "CRITICAL_ERROR_calculate_progress_exception",
            objective_id=objective_id,
            player_id=player_id,
            error=str(e),
            error_type=type(e).__name__
        )
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
    if not player_id or not objective_id:
        logger.error(
            "CRITICAL_ERROR_update_progress_invalid_params",
            player_id=player_id,
            objective_id=objective_id,
            percentage=new_percentage
        )
        return False

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
                    "objective_progress_updated_neo4j",
                    player_id=player_id,
                    objective_id=objective_id,
                    percentage=new_percentage,
                    status=record.get("status")
                )
                return True
            else:
                logger.error(
                    "CRITICAL_ERROR_update_progress_no_record",
                    player_id=player_id,
                    objective_id=objective_id,
                    percentage=new_percentage,
                    reason="Query returned no record - Player or Objective may not exist"
                )
                return False

    except Exception as e:
        logger.error(
            "CRITICAL_ERROR_update_progress_exception",
            player_id=player_id,
            objective_id=objective_id,
            percentage=new_percentage,
            error=str(e),
            error_type=type(e).__name__
        )
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

            # If no ID, try to match to existing knowledge in campaign
            if not knowledge_id:
                knowledge_id = await match_extracted_knowledge_to_existing(
                    campaign_id=campaign_id,
                    extracted_name=knowledge.get("name", ""),
                    extracted_description=knowledge.get("description", ""),
                    extracted_type=knowledge.get("type", "")
                )
                logger.info(
                    "knowledge_matching_attempted",
                    extracted_name=knowledge.get("name"),
                    matched_id=knowledge_id
                )

            if knowledge_id:
                # Fetch full knowledge details from MongoDB
                from ..services.mongo_persistence import mongo_persistence
                try:
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
                        logger.warning(
                            "knowledge_not_found_in_mongodb",
                            knowledge_id=knowledge_id,
                            extracted_name=knowledge.get("name")
                        )
                        knowledge_data = knowledge
                        knowledge_data["id"] = knowledge_id

                    logger.info(
                        "knowledge_data_prepared",
                        knowledge_data=knowledge_data
                    )

                    # Persist knowledge acquisition to Neo4j
                    from ..services.neo4j_graph import neo4j_graph
                    try:
                        await neo4j_graph.record_knowledge_acquisition_with_source(
                            player_id=player_id,
                            knowledge_id=knowledge_id,
                            knowledge_name=knowledge_data.get("name", "Unknown"),
                            source_type="narrative_extraction",
                            source_id=session_id,
                            metadata={
                                "session_id": session_id,
                                "timestamp": datetime.utcnow().isoformat(),
                                "extracted_from": "narrative"
                            }
                        )
                        logger.info(
                            "knowledge_persisted_to_neo4j",
                            player_id=player_id,
                            knowledge_id=knowledge_id
                        )
                    except Exception as neo4j_error:
                        logger.error(
                            "CRITICAL_ERROR_persisting_knowledge_to_neo4j",
                            player_id=player_id,
                            knowledge_id=knowledge_id,
                            error=str(neo4j_error),
                            error_type=type(neo4j_error).__name__
                        )
                        # Continue processing other acquisitions even if one fails
                        continue

                    # Link to objectives
                    try:
                        affected = await link_acquisition_to_objectives(
                            player_id, campaign_id, "knowledge", knowledge_id
                        )
                        logger.info(
                            "knowledge_linked_to_objectives",
                            knowledge_id=knowledge_id,
                            affected_count=len(affected),
                            affected_objectives=[obj["objective_id"] for obj in affected]
                        )
                    except Exception as link_error:
                        logger.error(
                            "CRITICAL_ERROR_linking_knowledge_to_objectives",
                            knowledge_id=knowledge_id,
                            error=str(link_error),
                            error_type=type(link_error).__name__
                        )
                        # Continue without linking
                        affected = []

                except Exception as e:
                    logger.error(
                        "CRITICAL_ERROR_processing_knowledge_acquisition",
                        knowledge_id=knowledge_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    continue
            else:
                # No match found - skip this knowledge
                logger.warning(
                    "knowledge_not_matched",
                    extracted_name=knowledge.get("name"),
                    extracted_description=knowledge.get("description")
                )
                continue

            # Calculate and update progress for each affected objective
            for obj in affected:
                try:
                    new_progress = await calculate_objective_progress(
                        player_id, obj["objective_id"]
                    )
                    obj["new_progress"] = new_progress
                    logger.info(
                        "objective_progress_calculated",
                        objective_id=obj["objective_id"],
                        old_progress=obj.get("current_progress", 0),
                        new_progress=new_progress
                    )

                    success = await update_objective_progress(
                        player_id, obj["objective_id"], new_progress
                    )
                    if success:
                        logger.info(
                            "objective_progress_updated_successfully",
                            objective_id=obj["objective_id"],
                            progress=new_progress
                        )

                        # Update parent campaign objective progress
                        campaign_obj_id = obj.get("campaign_objective_id")
                        if campaign_obj_id:
                            try:
                                await neo4j_graph.update_campaign_objective_progress(
                                    player_id, campaign_obj_id
                                )
                                logger.info(
                                    "campaign_objective_updated_after_quest_objective",
                                    quest_objective_id=obj["objective_id"],
                                    campaign_objective_id=campaign_obj_id
                                )
                            except Exception as campaign_error:
                                logger.error(
                                    "campaign_objective_update_failed",
                                    campaign_objective_id=campaign_obj_id,
                                    error=str(campaign_error)
                                )
                    else:
                        logger.error(
                            "CRITICAL_ERROR_objective_progress_update_failed",
                            objective_id=obj["objective_id"],
                            progress=new_progress,
                            reason="update_objective_progress returned False"
                        )
                except Exception as progress_error:
                    logger.error(
                        "CRITICAL_ERROR_calculating_or_updating_progress",
                        objective_id=obj["objective_id"],
                        error=str(progress_error),
                        error_type=type(progress_error).__name__
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

                success = await update_objective_progress(
                    player_id, obj["objective_id"], new_progress
                )

                # Update parent campaign objective progress
                if success:
                    campaign_obj_id = obj.get("campaign_objective_id")
                    if campaign_obj_id:
                        try:
                            await neo4j_graph.update_campaign_objective_progress(
                                player_id, campaign_obj_id
                            )
                        except Exception as e:
                            logger.error("campaign_objective_update_failed_for_item", error=str(e))

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
