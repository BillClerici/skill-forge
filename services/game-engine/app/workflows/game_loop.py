"""
LangGraph Game Loop Workflow
Orchestrates the main gameplay loop using state machine
"""
from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from datetime import datetime
import json

from ..models.state import (
    GameSessionState,
    SessionStatus,
    ActionInterpretation,
    NPCDialogueResponse,
    AssessmentResult,
    PlayerAction,
    GameEvent
)
from ..services.game_master import gm_agent
from ..services.mcp_client import mcp_client
from ..services.redis_manager import redis_manager
from ..services.rabbitmq_client import rabbitmq_client
from ..core.logging import get_logger
from .objective_tracker import process_acquisitions

logger = get_logger(__name__)


# ============================================
# Helper Functions
# ============================================

def create_encounter_metadata(state: GameSessionState, player_id: str) -> dict:
    """Create standardized encounter metadata with context"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "quest_id": state.get("current_quest_id"),
        "place_id": state.get("current_place_id"),
        "scene_id": state.get("current_scene_id"),
        "player_id": player_id,
        "session_id": state.get("session_id")
    }


async def persist_encounter(
    session_id: str,
    player_id: str,
    encounter_type: str,
    encounter_data: dict,
    metadata: dict
):
    """Persist encounter to both MongoDB and Neo4j"""
    try:
        from ..services.mongo_persistence import mongo_persistence
        from ..services.neo4j_graph import neo4j_graph

        # Save to MongoDB
        await mongo_persistence.save_encounter(
            session_id=session_id,
            player_id=player_id,
            encounter_type=encounter_type,
            encounter_data=encounter_data,
            metadata=metadata
        )

        # Save to Neo4j graph
        await neo4j_graph.record_encounter(
            player_id=player_id,
            encounter_type=encounter_type,
            encounter_id=encounter_data.get("id"),
            encounter_name=encounter_data.get("name") or encounter_data.get("title", "Unknown"),
            metadata=metadata
        )

    except Exception as e:
        logger.error("encounter_persistence_failed", error=str(e))


async def persist_knowledge_acquisition(
    session_id: str,
    player_id: str,
    knowledge_id: str,
    knowledge_data: dict,
    source_type: str,
    source_id: str,
    metadata: dict
):
    """Persist knowledge acquisition to both MongoDB and Neo4j"""
    try:
        from ..services.mongo_persistence import mongo_persistence
        from ..services.neo4j_graph import neo4j_graph

        # Save to MongoDB
        await mongo_persistence.save_knowledge_acquisition(
            session_id=session_id,
            player_id=player_id,
            knowledge_id=knowledge_id,
            knowledge_data=knowledge_data,
            source_type=source_type,
            source_id=source_id,
            metadata=metadata
        )

        # Save to Neo4j graph
        await neo4j_graph.record_knowledge_acquisition_with_source(
            player_id=player_id,
            knowledge_id=knowledge_id,
            knowledge_name=knowledge_data.get("name") or knowledge_data.get("title", "Unknown"),
            source_type=source_type,
            source_id=source_id,
            metadata=metadata
        )

    except Exception as e:
        logger.error("knowledge_acquisition_persistence_failed", error=str(e))


async def persist_item_acquisition(
    session_id: str,
    player_id: str,
    item_id: str,
    item_data: dict,
    source_type: str,
    source_id: str,
    metadata: dict
):
    """Persist item acquisition to both MongoDB and Neo4j"""
    try:
        from ..services.mongo_persistence import mongo_persistence
        from ..services.neo4j_graph import neo4j_graph

        # Save to MongoDB
        await mongo_persistence.save_item_acquisition(
            session_id=session_id,
            player_id=player_id,
            item_id=item_id,
            item_data=item_data,
            source_type=source_type,
            source_id=source_id,
            metadata=metadata
        )

        # Save to Neo4j graph
        await neo4j_graph.record_item_acquisition_with_source(
            player_id=player_id,
            item_id=item_id,
            item_name=item_data.get("name", "Unknown"),
            source_type=source_type,
            source_id=source_id,
            metadata=metadata
        )

    except Exception as e:
        logger.error("item_acquisition_persistence_failed", error=str(e))


async def get_quest_progress_for_acquisition(
    state: GameSessionState,
    acquisition_type: str,
    acquisition_id: str
) -> dict:
    """
    Check if an acquisition relates to quest objectives and return progress data

    Args:
        state: Current game session state
        acquisition_type: Type of acquisition ("knowledge", "item", etc.)
        acquisition_id: ID of the acquired entity

    Returns:
        dict with questLink and progress if related to a quest, empty dict otherwise
    """
    try:
        from ..services.mongo_persistence import mongo_persistence

        current_quest_id = state.get("current_quest_id")
        logger.info("quest_progress_check", current_quest_id=current_quest_id, acquisition_type=acquisition_type, acquisition_id=acquisition_id)
        if not current_quest_id:
            logger.info("no_current_quest_id")
            return {}

        # Load quest data
        quest_data = await mongo_persistence.get_quest(current_quest_id)
        if not quest_data:
            logger.info("quest_data_not_found", quest_id=current_quest_id)
            return {}

        # Check quest objectives for this acquisition
        objectives = quest_data.get("objectives", [])
        logger.info("checking_objectives", objective_count=len(objectives))
        for objective in objectives:
            objective_type = objective.get("type", "")
            required_ids = objective.get("required_ids", [])
            logger.info("objective_check", objective_type=objective_type, expected_type=f"learn_{acquisition_type}", required_ids=required_ids, acquisition_id=acquisition_id)

            # Check if this acquisition matches an objective
            if (objective_type == f"collect_{acquisition_type}" or
                objective_type == f"acquire_{acquisition_type}" or
                objective_type == f"learn_{acquisition_type}"):

                logger.info("type_matched", objective_type=objective_type)
                if acquisition_id in required_ids:
                    logger.info("acquisition_matched", acquisition_id=acquisition_id)
                    # This acquisition is part of a quest objective!
                    # Calculate progress
                    player_id = state.get("players", [{}])[0].get("player_id") if state.get("players") else None

                    if acquisition_type == "knowledge":
                        player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
                        acquired_count = sum(1 for rid in required_ids if rid in player_knowledge.keys())
                    elif acquisition_type == "item":
                        player_inventory = state.get("player_inventories", {}).get(player_id, [])
                        acquired_count = sum(1 for rid in required_ids if any(item.get("item_id") == rid for item in player_inventory))
                    else:
                        acquired_count = 0

                    total_required = len(required_ids)

                    result = {
                        "questLink": objective.get("description", "Quest Objective"),
                        "progress": f"{acquired_count}/{total_required}"
                    }
                    logger.info("returning_quest_progress", result=result)
                    return result

        logger.info("no_matching_objective_found")
        return {}

    except Exception as e:
        logger.error("quest_progress_check_failed", error=str(e))
        return {}


async def calculate_complete_quest_progress(state: GameSessionState) -> dict:
    """
    Calculate progress for ALL objectives in the current quest using Neo4j.

    This function now delegates to the Neo4j-based objective tracking system
    for consistent, graph-based objective progress.

    Args:
        state: Current game session state

    Returns:
        dict with quest progress data for all objectives
    """
    try:
        from ..managers.quest_tracker import quest_tracker
        from ..services.mongo_persistence import mongo_persistence
        from ..services.neo4j_graph import neo4j_graph

        current_quest_id = state.get("current_quest_id")
        campaign_id = state.get("campaign_id")
        player_id = state.get("players", [{}])[0].get("player_id") if state.get("players") else None

        logger.info("calculate_complete_quest_progress_start", current_quest_id=current_quest_id)

        if not current_quest_id or not player_id or not campaign_id:
            logger.info("missing_required_ids", quest=current_quest_id, player=player_id, campaign=campaign_id)
            return {}

        # Get quest name from MongoDB for display
        quest_data = await mongo_persistence.get_quest(current_quest_id)
        quest_name = quest_data.get("name", "Current Quest") if quest_data else "Current Quest"

        # Get Neo4j objective progress (this is the source of truth)
        progress_data = await neo4j_graph.get_player_objective_progress(player_id, campaign_id)

        if not progress_data or not progress_data.get("campaign_objectives"):
            logger.info("no_neo4j_objectives_found")
            return {
                "quest_id": current_quest_id,
                "quest_name": quest_name,
                "overall_progress": 0,
                "objectives": []
            }

        # Get quest number from Neo4j
        async with neo4j_graph.driver.session() as session:
            result = await session.run("""
                MATCH (q:Quest {id: $quest_id})
                RETURN q.order_sequence as quest_number
            """, quest_id=current_quest_id)
            record = await result.single()
            current_quest_number = record["quest_number"] if record else 1

        # Get player's acquired knowledge and items from state
        player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
        player_inventory = state.get("player_inventories", {}).get(player_id, [])
        player_knowledge_ids = set(player_knowledge.keys())
        player_item_ids = {item.get("item_id") for item in player_inventory if item.get("item_id")}

        # Collect campaign objectives for display
        campaign_objectives = []
        campaign_total_progress = 0
        campaign_obj_count = 0

        for campaign_obj in progress_data.get("campaign_objectives", []):
            # Calculate campaign objective progress
            campaign_progress = campaign_obj.get("completion_percentage", 0)
            campaign_objectives.append({
                "description": campaign_obj.get("description", "Campaign Objective"),
                "completion_percentage": campaign_progress,
                "percent": campaign_progress,
                "completed": campaign_obj.get("status") == "completed",
                "status": campaign_obj.get("status", "not_started")
            })
            campaign_total_progress += campaign_progress
            campaign_obj_count += 1

        # Calculate overall campaign progress
        campaign_overall_progress = round(campaign_total_progress / campaign_obj_count) if campaign_obj_count > 0 else 0

        # Find quest objectives for the current quest
        quest_objectives = []
        total_progress = 0
        objective_count = 0

        for campaign_obj in progress_data.get("campaign_objectives", []):
            for quest_obj in campaign_obj.get("quest_objectives", []):
                # Match objectives by quest number (order_sequence)
                if quest_obj.get("quest_number") == current_quest_number:
                    # Get required knowledge and items for this objective from Neo4j
                    async with neo4j_graph.driver.session() as session:
                        result = await session.run("""
                            MATCH (qo:QuestObjective {id: $obj_id})
                            OPTIONAL MATCH (qo)-[:REQUIRES_KNOWLEDGE]->(k:Knowledge)
                            OPTIONAL MATCH (qo)-[:REQUIRES_ITEM]->(i:Item)
                            RETURN collect(DISTINCT k.id) as required_knowledge,
                                   collect(DISTINCT i.id) as required_items,
                                   qo.success_criteria as criteria
                        """, obj_id=quest_obj["id"])
                        record = await result.single()

                    if not record:
                        continue

                    required_knowledge = [k for k in record["required_knowledge"] if k]
                    required_items = [i for i in record["required_items"] if i]
                    criteria = record["criteria"] or []

                    # Calculate progress based on knowledge/items acquired
                    knowledge_acquired = len(set(required_knowledge) & player_knowledge_ids) if required_knowledge else 0
                    items_acquired = len(set(required_items) & player_item_ids) if required_items else 0

                    total_required = len(required_knowledge) + len(required_items)
                    total_acquired = knowledge_acquired + items_acquired

                    # Calculate percentage
                    percent = int((total_acquired / total_required * 100)) if total_required > 0 else 0

                    quest_objectives.append({
                        "description": quest_obj.get("description", "Quest Objective"),
                        "type": "",  # Not used in UI, kept for compatibility
                        "current": total_acquired,
                        "total": total_required,
                        "progress": f"{total_acquired}/{total_required}",
                        "percent": percent,
                        "completed": percent >= 100
                    })

                    total_progress += percent
                    objective_count += 1

        # Calculate overall progress
        overall_progress = round(total_progress / objective_count) if objective_count > 0 else 0

        result = {
            "quest_id": current_quest_id,
            "quest_name": quest_name,
            "overall_progress": overall_progress,
            "objectives": quest_objectives,
            "campaign_objectives": campaign_objectives,
            "campaign_overall_progress": campaign_overall_progress
        }

        logger.info("calculate_complete_quest_progress_returning", result=result)
        return result

    except Exception as e:
        logger.error("complete_quest_progress_calculation_failed", error=str(e))
        return {}


async def format_player_input_for_display(
    player_input: str,
    action_interpretation: ActionInterpretation,
    state: GameSessionState
) -> str:
    """
    Format player input for display by replacing IDs with user-friendly names

    Args:
        player_input: Raw player input string
        action_interpretation: Interpreted action data
        state: Current game state

    Returns:
        Formatted string with friendly names
    """
    try:
        from ..services.mongo_persistence import mongo_persistence

        action_type = action_interpretation.get("action_type")
        target_id = action_interpretation.get("target_id")
        parameters = action_interpretation.get("parameters", {})

        # Create a mapping of IDs to friendly names
        friendly_input = player_input

        # Handle item actions
        if action_type == "take_item" and target_id:
            # Try to get item name from parameters or look it up
            item_name = parameters.get("item_name", target_id)

            # If item_name looks like an ID, try to look up the friendly name
            if "_" in item_name or item_name.islower():
                # Load scene data to get visible items
                scene_data = await mongo_persistence.get_scene(state.get("current_scene_id", ""))
                if scene_data:
                    visible_item_ids = scene_data.get("visible_item_ids", [])
                    for vid in visible_item_ids:
                        item_obj = await mongo_persistence.get_item(vid)
                        if item_obj and (item_obj.get("_id") == target_id or
                                        item_obj.get("name", "").lower() == item_name.lower()):
                            friendly_name = item_obj.get("name", item_name)
                            # Replace the ID/slug with friendly name
                            friendly_input = friendly_input.replace(item_name, friendly_name)
                            break

        # Handle investigate discovery actions
        elif action_type == "investigate_discovery" and target_id:
            discovery_name = parameters.get("discovery_name", target_id)

            # Check if discovery exists in available discoveries
            available_discoveries = state.get("available_discoveries", [])
            for d in available_discoveries:
                if (d.get("_id") == target_id or
                    d.get("discovery_id") == target_id or
                    d.get("name", "").lower() == discovery_name.lower()):
                    friendly_name = d.get("name", discovery_name)
                    # Replace with friendly name
                    friendly_input = friendly_input.replace(discovery_name, friendly_name)
                    break

        return friendly_input

    except Exception as e:
        logger.error("format_player_input_failed", error=str(e))
        return player_input  # Return original on error


async def detect_acquirable_opportunities(
    gm_response: str,
    state: GameSessionState
) -> dict:
    """
    Parse GM response to detect potential acquirable items, knowledge, and NPCs
    Returns opportunities that can be presented as action buttons to the player
    """
    opportunities = {
        "items": [],
        "knowledge": [],
        "npcs": [],
        "discoveries": [],
        "actions": []
    }

    try:
        from ..services.mongo_persistence import mongo_persistence

        # Get available entities from current scene
        available_npcs = state.get("available_npcs", [])
        available_discoveries = state.get("available_discoveries", [])
        visible_items = state.get("visible_items", [])

        # Detect NPCs mentioned in response
        for npc in available_npcs:
            npc_name = npc.get("name", "")
            if npc_name and npc_name.lower() in gm_response.lower():
                opportunities["npcs"].append({
                    "id": npc.get("npc_id") or npc.get("_id"),
                    "name": npc_name,
                    "role": npc.get("role", "Character"),
                    "action": f"Ask {npc_name} about...",
                    "context": "talk_to_npc"
                })

        # Detect discoveries mentioned
        for discovery in available_discoveries:
            discovery_name = discovery.get("name", "")
            if discovery_name and discovery_name.lower() in gm_response.lower():
                opportunities["discoveries"].append({
                    "id": discovery.get("discovery_id") or discovery.get("_id"),
                    "name": discovery_name,
                    "description": discovery.get("description", ""),
                    "action": f"Investigate {discovery_name}",
                    "context": "investigate_discovery"
                })

        # Detect items mentioned
        for item_name in visible_items:
            if item_name and item_name.lower() in gm_response.lower():
                opportunities["items"].append({
                    "name": item_name,
                    "action": f"Take {item_name}",
                    "context": "take_item"
                })

        # Detect common action patterns
        action_patterns = {
            "examine": r"(?:examine|look at|inspect|check)\s+(?:the\s+)?(\w+(?:\s+\w+)?)",
            "search": r"(?:search|look for|find)\s+(?:the\s+)?(\w+(?:\s+\w+)?)",
            "ask_about": r"(?:ask about|inquire about|learn about)\s+(?:the\s+)?(\w+(?:\s+\w+)?)"
        }

        import re
        for action_type, pattern in action_patterns.items():
            matches = re.finditer(pattern, gm_response.lower())
            for match in matches:
                target = match.group(1)
                if target:
                    # Format action text with proper capitalization
                    action_verb = action_type.replace('_', ' ').title()
                    action_text = f"{action_verb} {target.title()}"

                    opportunities["actions"].append({
                        "type": action_type,
                        "target": target,
                        "action": action_text,
                        "context": "perform_action"
                    })

                    logger.debug(
                        "opportunity_detected",
                        action_type=action_type,
                        target=target,
                        action_text=action_text
                    )

    except Exception as e:
        logger.error("opportunity_detection_failed", error=str(e))

    return opportunities


# ============================================
# Workflow Nodes
# ============================================

async def initialize_session_node(state: GameSessionState) -> GameSessionState:
    """
    Initialize game session with campaign data

    Load campaign, set starting location, initialize player states
    """
    try:
        # If there's a pending action, this is a resume - load full state from Redis
        if state.get("pending_action"):
            from ..services.redis_manager import redis_manager
            logger.info(
                "loading_session_state_from_redis",
                session_id=state["session_id"]
            )
            full_state = await redis_manager.load_state(state["session_id"])
            if full_state:
                # Sanitize state - convert None values to empty lists for list fields
                if full_state.get("completed_discoveries") is None:
                    full_state["completed_discoveries"] = []
                if full_state.get("completed_challenges") is None:
                    full_state["completed_challenges"] = []

                # Load chat history from MongoDB if missing from Redis
                if not full_state.get("chat_messages") or len(full_state.get("chat_messages", [])) == 0:
                    from ..services.mongo_persistence import mongo_persistence
                    logger.info(
                        "loading_chat_history_from_mongodb",
                        session_id=state["session_id"]
                    )
                    chat_history = await mongo_persistence.get_chat_history(state["session_id"])
                    if chat_history:
                        full_state["chat_messages"] = chat_history
                        logger.info(
                            "chat_history_loaded_from_mongodb",
                            session_id=state["session_id"],
                            message_count=len(chat_history)
                        )

                # Merge pending action into loaded state
                full_state["pending_action"] = state["pending_action"]
                full_state["awaiting_player_input"] = False
                full_state["current_node"] = "interpret_action"

                # Return as plain dict to avoid TypedDict validation issues
                return dict(full_state)

        # Check if session is already initialized (has scene_description)
        # If so, skip initialization and go directly to the current node
        if state.get("scene_description") and state.get("current_node") and state.get("current_node") != "generate_scene":
            logger.info(
                "session_already_initialized_skipping",
                session_id=state["session_id"],
                current_node=state.get("current_node")
            )
            # Session already initialized, return state as-is
            # The workflow will route based on current_node
            return state

        logger.info(
            "initializing_session",
            session_id=state["session_id"],
            campaign_id=state.get("campaign_id", "unknown")
        )

        # Load campaign data directly from MongoDB
        from ..services.mongo_persistence import mongo_persistence
        from ..services.neo4j_graph import neo4j_graph

        campaign = await mongo_persistence.get_campaign(state["campaign_id"])

        # Populate campaign metadata
        if campaign:
            state["campaign_name"] = campaign.get("name")
            state["campaign_plot"] = campaign.get("plot_summary")

        if campaign and campaign.get("quest_ids") and len(campaign["quest_ids"]) > 0:
            # Get ALL quests to sort by order_sequence (BATCH QUERY - Performance optimization)
            quest_ids = campaign["quest_ids"]
            all_quests = await mongo_persistence.get_quests_by_ids(quest_ids)

            # Sort quests by order_sequence
            all_quests.sort(key=lambda q: q.get("order_sequence", 0))

            if all_quests:
                first_quest = all_quests[0]
                first_quest_id = first_quest.get("_id") or first_quest.get("quest_id")
                state["current_quest_id"] = first_quest_id

                # Use Place/Scene structure: Get first place (by order_sequence), then first scene
                place_ids = first_quest.get("place_ids", [])
                if place_ids and len(place_ids) > 0:
                    # Load all places to sort by order_sequence (BATCH QUERY - Performance optimization)
                    all_places = await mongo_persistence.get_places_by_ids(place_ids)

                    # Sort places by order_sequence
                    all_places.sort(key=lambda p: p.get("order_sequence", 0))

                    if all_places:
                        first_place = all_places[0]
                        first_place_id = first_place.get("_id") or first_place.get("place_id")

                        # Load all scenes to sort by order_sequence (BATCH QUERY - Performance optimization)
                        scene_ids = first_place.get("scene_ids", [])
                        if scene_ids:
                            all_scenes = await mongo_persistence.get_scenes_by_ids(scene_ids)

                            # Sort scenes by order_sequence
                            all_scenes.sort(key=lambda s: s.get("order_sequence", 0))

                            if all_scenes:
                                first_scene_id = all_scenes[0].get("_id") or all_scenes[0].get("scene_id")
                                state["current_scene_id"] = first_scene_id
                                state["current_place_id"] = first_place_id
                                logger.info(
                                    "loaded_campaign_quest",
                                    quest_id=first_quest_id,
                                    quest_title=first_quest.get("name", "Unknown"),
                                    place_id=first_place_id,
                                    scene_id=first_scene_id
                                )
                            else:
                                logger.warning("place_has_no_scenes", place_id=first_place_id)
                                state["current_scene_id"] = "starting_location"
                                state["current_place_id"] = campaign.get("world_id", "")
                        else:
                            logger.warning("place_has_no_scene_ids", place_id=first_place_id)
                            state["current_scene_id"] = "starting_location"
                            state["current_place_id"] = campaign.get("world_id", "")
                    else:
                        logger.warning("quest_has_no_places", quest_id=first_quest_id)
                        state["current_scene_id"] = "starting_location"
                        state["current_place_id"] = campaign.get("world_id", "")
                else:
                    logger.warning("quest_has_no_place_ids", quest_id=first_quest_id)
                    state["current_scene_id"] = "starting_location"
                    state["current_place_id"] = campaign.get("world_id", "")
            else:
                # Quests not found
                logger.warning("quests_not_found_in_mongodb", quest_ids=quest_ids)
                state["current_scene_id"] = "starting_location"
                state["current_place_id"] = campaign.get("world_id", "")
        else:
            # No quests in campaign - ERROR condition
            logger.error(
                "no_quests_in_campaign",
                campaign_id=state["campaign_id"]
            )
            raise ValueError(f"Campaign {state['campaign_id']} has no quests configured")

        # Initialize player states
        if not state.get("player_inventories"):
            state["player_inventories"] = {}
        if not state.get("player_knowledge"):
            state["player_knowledge"] = {}
        if not state.get("player_locations"):
            state["player_locations"] = {}

        for player in state.get("players", []):
            player_id = player["player_id"]
            state["player_locations"][player_id] = state["current_scene_id"]

            # Initialize inventory from MCP (optional)
            try:
                inventory_data = await mcp_client.get_player_inventory(player_id)
                if inventory_data:
                    state["player_inventories"][player_id] = inventory_data.get("items", [])
                else:
                    state["player_inventories"][player_id] = []
            except Exception as e:
                logger.warning(
                    "inventory_load_failed",
                    player_id=player_id,
                    error=str(e)
                )
                state["player_inventories"][player_id] = []

            # Initialize PROGRESS relationships in Neo4j for all quest objectives
            try:
                await neo4j_graph.initialize_player_objective_progress(
                    player_id=player_id,
                    campaign_id=state["campaign_id"]
                )
                logger.info(
                    "player_objective_progress_initialized",
                    player_id=player_id,
                    campaign_id=state["campaign_id"]
                )
            except Exception as e:
                logger.error(
                    "player_objective_progress_init_failed",
                    player_id=player_id,
                    error=str(e)
                )

        # Initialize lists
        state["conversation_history"] = state.get("conversation_history", [])
        state["action_history"] = state.get("action_history", [])
        state["event_log"] = state.get("event_log", [])
        state["chat_messages"] = state.get("chat_messages", [])
        state["completed_quest_ids"] = state.get("completed_quest_ids", [])
        state["completed_scene_ids"] = state.get("completed_scene_ids", [])
        state["completed_discoveries"] = state.get("completed_discoveries", [])
        state["completed_challenges"] = state.get("completed_challenges", [])

        # Set game time
        state["time_of_day"] = "morning"
        state["elapsed_game_time"] = 0

        # Check if session was paused before updating status
        current_state = await redis_manager.load_state(state["session_id"])
        if current_state and current_state.get("status") == "paused":
            logger.info("session_paused_during_init", session_id=state["session_id"])
            state["status"] = "paused"
            return state

        # Load quest progress for display
        if state.get("players") and len(state["players"]) > 0:
            try:
                # Use the complete quest progress calculation for consistency
                complete_progress = await calculate_complete_quest_progress(state)
                if complete_progress:
                    state["quest_progress"] = complete_progress
            except Exception as e:
                logger.warning("quest_progress_load_failed_init", error=str(e))

        # Update status
        state["status"] = SessionStatus.ACTIVE
        state["current_node"] = "generate_scene"
        state["awaiting_player_input"] = False
        state["last_updated"] = datetime.utcnow().isoformat()

        # Save to Redis
        await redis_manager.save_state(state["session_id"], state)

        # Publish state change event
        await rabbitmq_client.publish_state_change(
            state["session_id"],
            "initializing",
            "active"
        )

        logger.info(
            "session_initialized",
            session_id=state["session_id"],
            starting_quest=state["current_quest_id"],
            starting_scene=state["current_scene_id"]
        )

        return state

    except Exception as e:
        logger.error(
            "session_initialization_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        state["status"] = SessionStatus.ERROR
        return state


async def generate_scene_node(state: GameSessionState) -> GameSessionState:
    """
    Generate immersive scene description using Game Master agent
    """
    try:
        logger.info(
            "generating_scene",
            session_id=state["session_id"],
            scene_id=state["current_scene_id"]
        )

        # Define streaming callback to publish chunks via RabbitMQ
        async def stream_chunk(chunk: str):
            """Callback to publish streaming chunks to RabbitMQ"""
            await rabbitmq_client.publish_event(
                exchange="game.events",
                routing_key=f"session.{state['session_id']}.scene_chunk",
                message={
                    "type": "event",
                    "event_type": "scene_chunk",
                    "session_id": state["session_id"],
                    "payload": {
                        "chunk": chunk,
                        "is_complete": False,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

        # Generate scene description via Game Master with streaming
        scene_description = await gm_agent.generate_scene_description(
            state,
            stream_callback=stream_chunk
        )
        state["scene_description"] = scene_description

        # Publish final completion chunk
        await rabbitmq_client.publish_event(
            exchange="game.events",
            routing_key=f"session.{state['session_id']}.scene_chunk",
            message={
                "type": "event",
                "event_type": "scene_chunk",
                "session_id": state["session_id"],
                "payload": {
                    "chunk": "",
                    "is_complete": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )

        # Load scene data from MongoDB
        from ..services.mongo_persistence import mongo_persistence
        import asyncio

        # PERFORMANCE OPTIMIZATION: Parallelize scene and place data loading
        place_data_task = None
        if state.get("current_place_id"):
            place_data_task = mongo_persistence.get_place(state["current_place_id"])

        # Load scene and place data in parallel
        if place_data_task:
            scene_data, place_data = await asyncio.gather(
                mongo_persistence.get_scene(state["current_scene_id"]),
                place_data_task
            )
        else:
            scene_data = await mongo_persistence.get_scene(state["current_scene_id"])
            place_data = None

        # Store scene name and place name in state for display
        if scene_data:
            state["scene_name"] = scene_data.get("name", "Current Location")
            state["location_name"] = scene_data.get("name", "Current Location")  # Primary location field
            if place_data:
                state["place_name"] = place_data.get("name", "")

        # PERFORMANCE OPTIMIZATION: Parallelize all scene-related content loading
        if scene_data:
            # Extract all IDs needed
            discovery_ids = scene_data.get("discovery_ids", [])
            event_ids = scene_data.get("event_ids", [])
            challenge_ids = scene_data.get("challenge_ids", [])
            visible_item_ids = scene_data.get("visible_item_ids", [])
            required_knowledge_ids = scene_data.get("required_knowledge", [])
            required_item_ids = scene_data.get("required_items", [])

            # Get the scene's level_3_location_id for NPC lookup
            # NPCs are stored with level_3_location_id, not the scene's MongoDB _id
            scene_location_id = scene_data.get("level_3_location_id", state["current_scene_id"])

            # Load all content in parallel (7 queries at once instead of sequential)
            (
                npcs_at_location,
                discoveries,
                events,
                challenges,
                visible_items,
                required_knowledge,
                required_items
            ) = await asyncio.gather(
                mongo_persistence.get_npcs_at_location(scene_location_id),
                mongo_persistence.get_discoveries_by_ids(discovery_ids) if discovery_ids else asyncio.sleep(0, result=[]),
                mongo_persistence.get_events_by_ids(event_ids) if event_ids else asyncio.sleep(0, result=[]),
                mongo_persistence.get_challenges_by_ids(challenge_ids) if challenge_ids else asyncio.sleep(0, result=[]),
                mongo_persistence.get_items_by_ids(visible_item_ids) if visible_item_ids else asyncio.sleep(0, result=[]),
                mongo_persistence.get_knowledge_by_ids(required_knowledge_ids) if required_knowledge_ids else asyncio.sleep(0, result=[]),
                mongo_persistence.get_items_by_ids(required_item_ids) if required_item_ids else asyncio.sleep(0, result=[])
            )

            # Set NPCs
            state["available_npcs"] = npcs_at_location if npcs_at_location else []
            if npcs_at_location:
                logger.info(
                    "npcs_loaded_from_mongodb",
                    session_id=state["session_id"],
                    scene_id=state["current_scene_id"],
                    npc_count=len(npcs_at_location)
                )
            else:
                logger.warning(
                    "no_npcs_found_at_location",
                    session_id=state["session_id"],
                    scene_id=state["current_scene_id"]
                )

            # Set discoveries
            state["available_discoveries"] = discoveries
            if discoveries:
                logger.info("discoveries_loaded", session_id=state["session_id"], count=len(discoveries))

            # Set events
            state["active_events"] = events
            if events:
                logger.info("events_loaded", session_id=state["session_id"], count=len(events))

            # Set challenges
            state["active_challenges"] = challenges
            if challenges:
                logger.info("challenges_loaded", session_id=state["session_id"], count=len(challenges))

            # Filter visible items to exclude already acquired
            if visible_items:
                player_id = state.get("players", [{}])[0].get("player_id") if state.get("players") else None
                player_inventory = state.get("player_inventories", {}).get(player_id, [])
                acquired_item_ids = [item.get("item_id") for item in player_inventory]

                filtered_items = [
                    item for item in visible_items
                    if item.get("_id") not in acquired_item_ids and item.get("item_id") not in acquired_item_ids
                ]

                state["visible_items"] = [item.get("name") for item in filtered_items]
                logger.info(
                    "visible_items_loaded",
                    session_id=state["session_id"],
                    count=len(filtered_items),
                    total_in_scene=len(visible_items),
                    already_acquired=len(visible_items) - len(filtered_items)
                )
            else:
                state["visible_items"] = []

            # Set required knowledge
            state["scene_required_knowledge"] = required_knowledge
            if required_knowledge:
                logger.info("scene_required_knowledge_loaded", session_id=state["session_id"], count=len(required_knowledge))

            # Set required items
            state["scene_required_items"] = required_items
            if required_items:
                logger.info("scene_required_items_loaded", session_id=state["session_id"], count=len(required_items))
        else:
            # No scene data found, initialize empty lists
            state["available_npcs"] = []
            state["available_discoveries"] = []
            state["active_events"] = []
            state["active_challenges"] = []
            state["visible_items"] = []
            state["scene_required_knowledge"] = []
            state["scene_required_items"] = []

        # Determine available actions based on scene context
        available_actions = ["look around", "examine surroundings"]

        if state["available_npcs"]:
            available_actions.append("talk to NPC")

        if state.get("active_challenges"):
            available_actions.append("attempt challenge")

        if state.get("visible_items"):
            available_actions.append("take item")

        if state.get("available_discoveries"):
            available_actions.append("investigate discovery")

        available_actions.extend(["check inventory", "view quest log"])
        state["available_actions"] = available_actions

        # Create chat message for scene description
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "DM_NARRATIVE",
            "sender_id": "game_master",
            "sender_name": "Game Master",
            "content": scene_description,
            "metadata": {
                "scene_id": state["current_scene_id"],
                "available_actions": available_actions,
                "npcs_present": [npc.get("name") for npc in state["available_npcs"]]
            }
        }

        state["chat_messages"].append(chat_message)

        # Publish scene update
        await rabbitmq_client.publish_scene_update(
            state["session_id"],
            scene_description,
            available_actions,
            state["available_npcs"]
        )

        # Broadcast complete scene data via WebSocket for Investigate Scene panel
        from ..api.websocket_manager import connection_manager
        await connection_manager.broadcast_to_session(
            state["session_id"],
            {
                "event": "scene_update",
                "scene_description": scene_description,
                "available_actions": available_actions,
                "available_npcs": state.get("available_npcs", []),
                "visible_items": state.get("visible_items", []),
                "available_discoveries": state.get("available_discoveries", []),
                "active_challenges": state.get("active_challenges", []),
                "active_events": state.get("active_events", [])
            }
        )

        # Calculate and broadcast quest progress for persistence on page refresh
        logger.info("calculating_quest_progress_for_scene_generation", session_id=state["session_id"])
        complete_progress = await calculate_complete_quest_progress(state)
        logger.info("quest_progress_calculated", session_id=state["session_id"], has_progress=bool(complete_progress), progress_data=complete_progress)
        if complete_progress:
            logger.info("publishing_quest_progress_update", session_id=state["session_id"])
            await rabbitmq_client.publish_event(
                exchange="game.events",
                routing_key=f"session.{state['session_id']}.quest_progress",
                message={
                    "type": "event",
                    "event_type": "quest_progress",
                    "session_id": state["session_id"],
                    "payload": {
                        "objectives": complete_progress.get("objectives", []),
                        "quest_name": complete_progress.get("quest_name"),
                        "overall_progress": complete_progress.get("overall_progress", 0),
                        "campaign_objectives": complete_progress.get("campaign_objectives", []),
                        "campaign_overall_progress": complete_progress.get("campaign_overall_progress", 0),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            logger.info("quest_progress_published", session_id=state["session_id"])

            # Save quest progress to state for persistence on page refresh
            state["quest_progress"] = complete_progress

        # Process acquisitions and update objectives
        # Check for pending acquisitions (set by GM agent or manual testing)
        pending_acquisitions = state.get("pending_acquisitions", {
            "knowledge": [],
            "items": [],
            "events": [],
            "challenges": []
        })

        logger.info(
            "checking_pending_acquisitions",
            session_id=state["session_id"],
            pending_acquisitions=pending_acquisitions,
            has_acquisitions=any(pending_acquisitions.values())
        )

        # If there are any acquisitions to process
        if any(pending_acquisitions.values()):
            logger.info(
                "processing_acquisitions",
                session_id=state["session_id"],
                knowledge_count=len(pending_acquisitions.get("knowledge", [])),
                items_count=len(pending_acquisitions.get("items", [])),
                events_count=len(pending_acquisitions.get("events", [])),
                challenges_count=len(pending_acquisitions.get("challenges", []))
            )

            # Get player and campaign info
            players = state.get("players", [])
            if players and state.get("campaign_id"):
                player_id = players[0].get("player_id")
                campaign_id = state["campaign_id"]

                # Process acquisitions through objective tracker
                acquisition_results = await process_acquisitions(
                    state["session_id"],
                    player_id,
                    campaign_id,
                    pending_acquisitions
                )

                logger.info(
                    "acquisitions_processed",
                    session_id=state["session_id"],
                    total_acquisitions=len(acquisition_results.get("acquisitions", [])),
                    objectives_affected=len(acquisition_results.get("affected_objectives", []))
                )

                # Clear pending acquisitions after processing
                state["pending_acquisitions"] = {
                    "knowledge": [],
                    "items": [],
                    "events": [],
                    "challenges": []
                }

        # Update workflow state
        state["current_node"] = "await_player_input"
        state["awaiting_player_input"] = True
        state["scene_just_generated"] = True  # Flag to indicate scene was just generated
        state["last_updated"] = datetime.utcnow().isoformat()

        # Save state
        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "scene_generated",
            session_id=state["session_id"],
            npcs_count=len(state["available_npcs"]),
            actions_count=len(available_actions)
        )

        return state

    except Exception as e:
        logger.error(
            "scene_generation_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def await_player_input_node(state: GameSessionState) -> GameSessionState:
    """
    Wait for player input via WebSocket

    This node marks the state as awaiting input. The actual input
    will be injected via WebSocket handler, which will reload state,
    add the pending_action, and trigger workflow continuation.
    """
    try:
        logger.info(
            "awaiting_player_input",
            session_id=state["session_id"]
        )

        # This node just marks that we're waiting
        # The WebSocket handler will:
        # 1. Receive player input
        # 2. Load state from Redis
        # 3. Set state["pending_action"] = player_input
        # 4. Set state["awaiting_player_input"] = False
        # 5. Save state back to Redis
        # 6. Trigger workflow to continue to interpret_action_node

        # Check if session was externally paused before saving
        current_state = await redis_manager.load_state(state["session_id"])
        current_status = current_state.get("status") if current_state else None
        logger.info(
            "checking_pause_status",
            session_id=state["session_id"],
            current_status=current_status,
            paused_check=current_status == "paused"
        )
        if current_status == "paused":
            # Session was paused externally, don't overwrite
            logger.info("session_paused_externally", session_id=state["session_id"])
            state["status"] = "paused"
            return state

        state["current_node"] = "await_player_input"
        state["awaiting_player_input"] = True
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        # This node will "pause" here until WebSocket provides input
        # The workflow will be retriggered when input arrives

        return state

    except Exception as e:
        logger.error(
            "await_input_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def interpret_action_node(state: GameSessionState) -> GameSessionState:
    """
    Interpret player's natural language input into structured action
    """
    try:
        logger.info(
            "interpreting_action",
            session_id=state["session_id"]
        )

        # Get pending action (set by WebSocket handler)
        pending_action = state.get("pending_action")
        if not pending_action:
            logger.warning("no_pending_action", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            return state

        player_input = pending_action.get("player_input", "")
        player_id = pending_action.get("player_id", "")

        # Find player data
        player = None
        for p in state.get("players", []):
            if p["player_id"] == player_id:
                player = p
                break

        if not player:
            logger.error("player_not_found", player_id=player_id)
            state["pending_action"] = None
            state["current_node"] = "await_player_input"
            return state

        # Check if player is in an active conversation with an NPC
        # If so, route directly to the NPC unless they're explicitly ending the conversation
        active_npc_id = state.get("active_conversation_npc_id")
        active_npc_name = state.get("active_conversation_npc_name")

        logger.info(
            "interpret_action_conversation_state_check",
            session_id=state["session_id"],
            player_input=player_input[:100],
            active_conversation_npc_id=active_npc_id,
            active_conversation_npc_name=active_npc_name,
            conversation_turn_count=state.get("conversation_turn_count", 0)
        )

        # Keywords that indicate ending a conversation
        end_conversation_keywords = ["goodbye", "bye", "leave", "stop talking", "end conversation",
                                      "that's all", "nevermind", "move on", "go", "walk away"]

        # Check if ending conversation
        is_ending_conversation = active_npc_id and any(keyword in player_input.lower() for keyword in end_conversation_keywords)

        if active_npc_id and not is_ending_conversation:
            # Player is in active conversation - route directly to talk_to_npc
            # Do NOT call GM interpreter to avoid it misclassifying the message
            logger.info(
                "routing_to_active_conversation",
                session_id=state["session_id"],
                npc_id=active_npc_id,
                npc_name=active_npc_name,
                player_input=player_input[:100]
            )

            action_interpretation = {
                "action_type": "talk_to_npc",
                "target_id": active_npc_id,
                "parameters": {"statement": player_input},
                "success_probability": 1.0,
                "player_input": player_input
            }
        else:
            # Use Game Master agent to interpret action
            action_interpretation = await gm_agent.interpret_player_action(
                player_input,
                state,
                player
            )

            # If player ended conversation, clear the active conversation state
            if is_ending_conversation:
                logger.info(
                    "ending_active_conversation",
                    session_id=state["session_id"],
                    npc_id=active_npc_id
                )
                state["active_conversation_npc_id"] = None
                state["active_conversation_npc_name"] = None
                state["conversation_turn_count"] = 0

        # Store interpreted action for execution
        state["pending_action"]["interpretation"] = action_interpretation

        # Format player input for display with friendly names
        display_input = await format_player_input_for_display(
            player_input,
            action_interpretation,
            state
        )

        # Add to chat history
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "PLAYER_ACTION",
            "sender_id": player_id,
            "sender_name": player.get("character_name", "Unknown"),
            "content": display_input,
            "metadata": {
                "action_type": action_interpretation["action_type"],
                "target_id": action_interpretation.get("target_id")
            }
        }
        state["chat_messages"].append(chat_message)

        # Update workflow state
        state["current_node"] = "execute_action"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "action_interpreted",
            session_id=state["session_id"],
            action_type=action_interpretation["action_type"],
            target_id=action_interpretation.get("target_id")
        )

        return state

    except Exception as e:
        logger.error(
            "action_interpretation_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def execute_action_node(state: GameSessionState) -> GameSessionState:
    """
    Execute the interpreted action and generate outcome
    """
    try:
        logger.info(
            "executing_action",
            session_id=state["session_id"]
        )

        pending_action = state.get("pending_action")
        if not pending_action:
            logger.warning("no_pending_action_in_execute", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            return state

        interpretation: ActionInterpretation = pending_action.get("interpretation")

        if not interpretation:
            logger.warning("no_interpretation", session_id=state["session_id"])
            state["current_node"] = "await_player_input"
            state["pending_action"] = None
            return state

        action_type = interpretation["action_type"]
        target_id = interpretation.get("target_id")
        parameters = interpretation.get("parameters", {})
        player_id = pending_action.get("player_id")

        # Execute based on action type
        outcome = None
        requires_assessment = False

        if action_type == "player_ready":
            # Player is acknowledging readiness or understanding
            # Provide encouraging response and prompt them to take action
            encouragement = "Excellent! Your adventure awaits. Take a moment to look around, speak with anyone present, or take your first action."

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": encouragement,
                "metadata": {"action_type": "acknowledgment"}
            }
            state["chat_messages"].append(chat_message)

            outcome = {"player_acknowledged": True}

        elif action_type == "ask_gm_question":
            # Player is asking the Game Master a question
            question = parameters.get("question", pending_action.get("player_input", ""))

            # Import connection manager for streaming
            from ..api.websocket_manager import connection_manager

            # Define streaming callback to broadcast chunks via WebSocket
            async def stream_answer_chunk(chunk: str):
                """Callback to broadcast streaming answer chunks"""
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "gm_answer_chunk",
                        "chunk": chunk,
                        "is_complete": False
                    }
                )

            answer = await gm_agent.answer_player_question(question, state, stream_callback=stream_answer_chunk)

            # Broadcast final completion chunk
            await connection_manager.broadcast_to_session(
                state["session_id"],
                {
                    "event": "gm_answer_chunk",
                    "chunk": "",
                    "is_complete": True
                }
            )

            # Add GM answer to chat
            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": answer,
                "metadata": {"action_type": "question_answer"}
            }
            state["chat_messages"].append(chat_message)

            # Detect opportunities in GM response
            opportunities = await detect_acquirable_opportunities(answer, state)

            # Broadcast opportunities if any found
            if any(opportunities.values()):
                from ..api.websocket_manager import connection_manager
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_opportunities",
                        "opportunities": opportunities,
                        "context": "gm_response"
                    }
                )

            outcome = {"question_answered": True}

        elif action_type == "talk_to_npc":
            # Check if there are available NPCs
            if not state.get("available_npcs"):
                # No NPCs available - GM should narrate that player needs to progress
                gm_response = f"""Looking around the chaotic marketplace, you're surrounded by hundreds of frightened, confused people from all three societies. However, in this moment of panic and darkness, identifying and approaching someone who can actually help with the investigation will be crucial.

Let me help guide you: The scene description mentions several key elements - marketplace buildings where groups are sheltering, the reservoir control room showing signs of sabotage, and emerging conflicts between groups.

Consider these actionable next steps:
• Examine the scene more carefully to identify specific NPCs or locations
• Look for the reservoir control room to investigate the sabotage
• Check on one of the marketplace buildings where groups are trapped
• Search for guards, merchants, or officials who might have information

What would you like to do?"""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": gm_response,
                    "metadata": {"action_type": "gm_guidance"}
                }
                state["chat_messages"].append(chat_message)

                outcome = {"gm_guidance_provided": True}
            else:
                # NPCs available - proceed with normal dialogue
                player_statement = parameters.get("statement", pending_action.get("player_input", ""))

                # Resolve NPC name to NPC ID
                # target_id might be the NPC's name or the actual npc_id
                actual_npc_id = target_id
                for npc in state.get("available_npcs", []):
                    if npc.get("name") == target_id or npc.get("npc_id") == target_id or npc.get("_id") == target_id:
                        actual_npc_id = npc.get("npc_id") or npc.get("_id")
                        break

                npc_response = await gm_agent.generate_npc_dialogue(
                    actual_npc_id,
                    {"quest": state.get("current_quest_id")},
                    player_statement,
                    state
                )

                # Add NPC response to chat
                npc_name = "Unknown NPC"
                for npc in state.get("available_npcs", []):
                    if npc.get("npc_id") == actual_npc_id:
                        npc_name = npc.get("name", "Unknown NPC")
                        break

                # Get NPC details for rich message
                npc_details = None
                for npc in state.get("available_npcs", []):
                    if npc.get("npc_id") == actual_npc_id or npc.get("_id") == actual_npc_id:
                        npc_details = npc
                        break

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "NPC_DIRECT",  # Direct NPC dialogue
                    "sender_id": actual_npc_id,
                    "sender_name": npc_name,
                    "sender_role": npc_details.get("role", "Character") if npc_details else "Character",
                    "sender_avatar": npc_details.get("avatar", "") if npc_details else "",
                    "content": npc_response["dialogue"],
                    "metadata": {
                        "affinity_change": npc_response["affinity_change"],
                        "knowledge_revealed": npc_response["knowledge_revealed"],
                        "emotional_state": npc_response.get("metadata", {}).get("emotional_state", "neutral")
                    }
                }
                state["chat_messages"].append(chat_message)

                # Set active conversation state to keep player engaged with this NPC
                state["active_conversation_npc_id"] = actual_npc_id
                state["active_conversation_npc_name"] = npc_name
                state["conversation_turn_count"] = state.get("conversation_turn_count", 0) + 1

                logger.info(
                    "active_conversation_set",
                    session_id=state["session_id"],
                    npc_id=actual_npc_id,
                    npc_name=npc_name,
                    turn_count=state["conversation_turn_count"],
                    state_keys=list(state.keys())  # Log all state keys to verify conversation fields are present
                )

                # Record interaction
                await mcp_client.record_npc_interaction({
                    "npc_id": actual_npc_id,
                    "player_id": player_id,
                    "session_id": state["session_id"],
                    "interaction_type": "dialogue",
                    "affinity_change": npc_response["affinity_change"],
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Publish NPC response event
                await rabbitmq_client.publish_npc_response(
                    state["session_id"],
                    npc_response
                )

                # Track NPC encounter
                from ..api.websocket_manager import connection_manager
                npc_data = None
                for npc in state.get("available_npcs", []):
                    if npc.get("npc_id") == actual_npc_id or npc.get("_id") == actual_npc_id:
                        npc_data = npc
                        break

                if npc_data:
                    # Broadcast NPC encounter event
                    encounter_metadata = create_encounter_metadata(state, player_id)
                    await connection_manager.broadcast_to_session(
                        state["session_id"],
                        {
                            "event": "npc_encountered",
                            "npc": {
                                "id": npc_data.get("npc_id") or npc_data.get("_id"),
                                "name": npc_data.get("name", "Unknown NPC"),
                                "role": npc_data.get("role", "Character"),
                                "description": npc_data.get("description", ""),
                                "metadata": encounter_metadata
                            }
                        }
                    )

                # Track knowledge gained from dialogue
                if npc_response.get("knowledge_revealed"):
                    for knowledge_id in npc_response["knowledge_revealed"]:
                        # Load knowledge details from MongoDB
                        from ..services.mongo_persistence import mongo_persistence
                        knowledge_data = await mongo_persistence.get_knowledge_by_id(knowledge_id)

                        if knowledge_data:
                            # Add to player's knowledge
                            if "player_knowledge" not in state:
                                state["player_knowledge"] = {}
                            if player_id not in state["player_knowledge"]:
                                state["player_knowledge"][player_id] = {}

                            if knowledge_id not in state["player_knowledge"][player_id]:
                                # Store as dict with metadata for compatibility with rabbitmq_consumer
                                state["player_knowledge"][player_id][knowledge_id] = {
                                    "level": 1,
                                    "acquired_at": datetime.utcnow().isoformat()
                                }

                                # Persist knowledge acquisition to MongoDB and Neo4j
                                await persist_knowledge_acquisition(
                                    session_id=state["session_id"],
                                    player_id=player_id,
                                    knowledge_id=knowledge_id,
                                    knowledge_data=knowledge_data,
                                    source_type="npc",
                                    source_id=npc_id,
                                    metadata={
                                        "session_id": state["session_id"],
                                        "quest_id": state.get("active_quest", {}).get("quest_id"),
                                        "scene_id": state.get("current_scene", {}).get("scene_id"),
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                )

                                # Get quest progress for this knowledge
                                quest_info = await get_quest_progress_for_acquisition(state, "knowledge", knowledge_id)

                                # Broadcast knowledge gained event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "knowledge_gained",
                                        "knowledge": {
                                            "id": knowledge_id,
                                            "name": knowledge_data.get("name") or knowledge_data.get("title", "Unknown Knowledge"),
                                            "description": knowledge_data.get("description", "Knowledge acquired"),
                                            "source": f"From talking with {npc_name}",
                                            **quest_info
                                        }
                                    }
                                )

                                                # Calculate and broadcast complete quest progress
                                complete_progress = await calculate_complete_quest_progress(state)
                                if complete_progress:
                                    await connection_manager.broadcast_to_session(
                                        state["session_id"],
                                        {
                                            "event": "quest_progress_update",
                                            "quest_progress": complete_progress
                                        }
                                    )

                                # Check objective cascade and broadcast progress updates
                                try:
                                    from ..managers.quest_tracker import QuestProgressionTracker
                                    quest_tracker = QuestProgressionTracker()
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade: {e}")

                # Track items given by NPC during dialogue
                if npc_response.get("items_given"):
                    for item_id in npc_response["items_given"]:
                        # Load item details from MongoDB
                        from ..services.mongo_persistence import mongo_persistence
                        item_data = await mongo_persistence.get_item(item_id)

                        if item_data:
                            # Add to player's inventory
                            if player_id not in state["player_inventories"]:
                                state["player_inventories"][player_id] = []

                            # Check if player already has this item
                            has_item = any(
                                inv_item.get("item_id") == item_id
                                for inv_item in state["player_inventories"][player_id]
                            )

                            if not has_item:
                                # Add item to inventory
                                inventory_item = {
                                    "item_id": item_id,
                                    "name": item_data.get("name", "Unknown Item"),
                                    "description": item_data.get("description", ""),
                                    "properties": item_data.get("properties", {}),
                                    "acquired_at": datetime.utcnow().isoformat(),
                                    "acquired_from": "npc",
                                    "source_npc": target_id
                                }
                                state["player_inventories"][player_id].append(inventory_item)

                                # Persist item acquisition to MongoDB and Neo4j
                                await persist_item_acquisition(
                                    session_id=state["session_id"],
                                    player_id=player_id,
                                    item_id=item_id,
                                    item_data=item_data,
                                    source_type="npc",
                                    source_id=target_id,
                                    metadata={
                                        "session_id": state["session_id"],
                                        "quest_id": state.get("active_quest", {}).get("quest_id"),
                                        "scene_id": state.get("current_scene", {}).get("scene_id"),
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                )

                                # Get quest progress for this item
                                quest_info = await get_quest_progress_for_acquisition(state, "item", item_id)

                                # Broadcast item acquired event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "item_acquired",
                                        "item": {
                                            "id": item_id,
                                            "name": item_data.get("name", "Unknown Item"),
                                            "description": item_data.get("description", f"Received from {npc_name}"),
                                            "source": f"Gift from {npc_name}",
                                            **quest_info
                                        }
                                    }
                                )

                                # Check objective cascade after item acquisition from NPC
                                try:
                                    from ..managers.quest_tracker import quest_tracker
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade after NPC item: {e}")

                outcome = npc_response
                requires_assessment = bool(npc_response.get("rubric_id"))

        elif action_type == "move_to_location":
            # Move player to new location - validate and resolve to scene
            new_location_id = target_id

            # Try multiple resolution strategies
            from .mongo_persistence import mongo_persistence

            # Strategy 1: Check if it's a valid Scene
            scene_data = await mongo_persistence.get_scene(new_location_id)

            target_scene_id = None
            if scene_data:
                # Direct scene reference
                target_scene_id = new_location_id
            else:
                # Strategy 2: Check if it's a Place - if so, navigate to first scene in that place
                place_data = await mongo_persistence.get_place(new_location_id)
                if place_data and place_data.get("scene_ids"):
                    # Load all scenes to sort by order_sequence
                    place_scenes = []
                    for sid in place_data["scene_ids"]:
                        scene = await mongo_persistence.get_scene(sid)
                        if scene:
                            place_scenes.append(scene)

                    # Sort by order_sequence
                    place_scenes.sort(key=lambda s: s.get("order_sequence", 0))

                    if place_scenes:
                        target_scene_id = place_scenes[0].get("_id") or place_scenes[0].get("scene_id")
                        logger.info(
                            "resolved_place_to_scene",
                            session_id=state["session_id"],
                            place_id=new_location_id,
                            scene_id=target_scene_id
                        )

            if not target_scene_id:
                # Location doesn't exist - provide GM guidance
                gm_response = f"""You express interest in going to "{new_location_id}", but that location isn't available or doesn't exist here.

The scene description mentions various elements you can explore. To move to a new location, you should:

1. **Examine your surroundings** more carefully to identify specific, accessible locations
2. **Ask me questions** about where you can go or what's nearby
3. **Look for clues** in the narrative about available paths or destinations

What would you like to do?"""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": gm_response,
                    "metadata": {"action_type": "invalid_movement"}
                }
                state["chat_messages"].append(chat_message)

                outcome = {"invalid_location": new_location_id, "gm_guidance_provided": True}
            else:
                # Valid location - proceed with move
                old_scene = state["current_scene_id"]
                state["player_locations"][player_id] = target_scene_id
                state["current_scene_id"] = target_scene_id

                # Update current_place_id if we resolved from a place
                if scene_data:
                    # Scene move - place stays the same or gets updated from scene metadata
                    pass
                else:
                    # Place move - update place_id
                    state["current_place_id"] = new_location_id

                # Mark previous scene as completed
                if old_scene and old_scene not in state["completed_scene_ids"]:
                    state["completed_scene_ids"].append(old_scene)

                outcome = {"moved_to": target_scene_id}

                # Will regenerate scene
                state["current_node"] = "generate_scene"

        elif action_type == "examine_object":
            # Generate examination description using Game Master
            query = parameters.get("query", pending_action.get("player_input", ""))

            # Import connection manager for streaming
            from ..api.websocket_manager import connection_manager

            # Define streaming callback to broadcast chunks via RabbitMQ
            async def stream_action_chunk(chunk: str):
                """Callback to broadcast streaming action outcome chunks"""
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{state['session_id']}.scene_chunk",
                    message={
                        "type": "event",
                        "event_type": "scene_chunk",
                        "session_id": state["session_id"],
                        "payload": {
                            "chunk": chunk,
                            "is_complete": False,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )

            # Use Game Master to generate detailed examination outcome with streaming
            examination_text = await gm_agent.generate_generic_action_outcome(
                f"look around and examine {query}" if query else "look around and observe the surroundings",
                state,
                stream_callback=stream_action_chunk
            )

            # Publish final completion chunk via RabbitMQ
            await rabbitmq_client.publish_event(
                exchange="game.events",
                routing_key=f"session.{state['session_id']}.scene_chunk",
                message={
                    "type": "event",
                    "event_type": "scene_chunk",
                    "session_id": state["session_id"],
                    "payload": {
                        "chunk": "",
                        "is_complete": True,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": examination_text,
                "metadata": {"action_type": "examine"}
            }
            state["chat_messages"].append(chat_message)

            # Extract acquisitions from the narrative
            from .objective_tracker import detect_acquisitions_from_narrative
            extracted_acquisitions = await detect_acquisitions_from_narrative(
                narrative=examination_text,
                player_action=f"look around and examine {query}" if query else "look around",
                scene_context=state.get("current_scene", {})
            )

            # Add extracted acquisitions to pending
            if "pending_acquisitions" not in state:
                state["pending_acquisitions"] = {"knowledge": [], "items": [], "events": [], "challenges": []}

            for k in extracted_acquisitions.get("knowledge", []):
                state["pending_acquisitions"]["knowledge"].append(k)
            for i in extracted_acquisitions.get("items", []):
                state["pending_acquisitions"]["items"].append(i)
            for e in extracted_acquisitions.get("events", []):
                state["pending_acquisitions"]["events"].append(e)
            for c in extracted_acquisitions.get("challenges", []):
                state["pending_acquisitions"]["challenges"].append(c)

            # Detect opportunities in examination
            opportunities = await detect_acquirable_opportunities(examination_text, state)

            # Broadcast opportunities if any found
            if any(opportunities.values()):
                from ..api.websocket_manager import connection_manager
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_opportunities",
                        "opportunities": opportunities,
                        "context": "examine"
                    }
                )

            outcome = {"examined": query}

        elif action_type == "perform_action":
            # Handle generic/creative freeform action
            action_description = parameters.get("action_description", pending_action.get("player_input", ""))

            # Import connection manager for streaming
            from ..api.websocket_manager import connection_manager

            # Define streaming callback to broadcast chunks via RabbitMQ
            async def stream_action_chunk(chunk: str):
                """Callback to broadcast streaming action outcome chunks"""
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{state['session_id']}.scene_chunk",
                    message={
                        "type": "event",
                        "event_type": "scene_chunk",
                        "session_id": state["session_id"],
                        "payload": {
                            "chunk": chunk,
                            "is_complete": False,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )

            # Use Game Master to generate narrative outcome for this creative action with streaming
            outcome_text = await gm_agent.generate_generic_action_outcome(
                action_description,
                state,
                stream_callback=stream_action_chunk
            )

            # Publish final completion chunk via RabbitMQ
            await rabbitmq_client.publish_event(
                exchange="game.events",
                routing_key=f"session.{state['session_id']}.scene_chunk",
                message={
                    "type": "event",
                    "event_type": "scene_chunk",
                    "session_id": state["session_id"],
                    "payload": {
                        "chunk": "",
                        "is_complete": True,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": outcome_text,
                "metadata": {"action_type": "generic_action"}
            }
            state["chat_messages"].append(chat_message)

            # Extract acquisitions from the narrative
            from .objective_tracker import detect_acquisitions_from_narrative
            extracted_acquisitions = await detect_acquisitions_from_narrative(
                narrative=outcome_text,
                player_action=action_description,
                scene_context=state.get("current_scene", {})
            )

            # Add extracted acquisitions to pending
            if "pending_acquisitions" not in state:
                state["pending_acquisitions"] = {"knowledge": [], "items": [], "events": [], "challenges": []}

            for k in extracted_acquisitions.get("knowledge", []):
                state["pending_acquisitions"]["knowledge"].append(k)
            for i in extracted_acquisitions.get("items", []):
                state["pending_acquisitions"]["items"].append(i)
            for e in extracted_acquisitions.get("events", []):
                state["pending_acquisitions"]["events"].append(e)
            for c in extracted_acquisitions.get("challenges", []):
                state["pending_acquisitions"]["challenges"].append(c)

            # Detect opportunities in action outcome
            opportunities = await detect_acquirable_opportunities(outcome_text, state)

            # Broadcast opportunities if any found
            if any(opportunities.values()):
                from ..api.websocket_manager import connection_manager
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_opportunities",
                        "opportunities": opportunities,
                        "context": "action_outcome"
                    }
                )

            outcome = {"action_performed": action_description}

        elif action_type == "use_item":
            # Use item from inventory
            item_id = target_id
            item_name = parameters.get("item_name", item_id)

            # Check if player has the item in inventory
            player_inventory = state.get("player_inventories", {}).get(player_id, [])
            has_item = any(item.get("item_id") == item_id or item.get("name") == item_name for item in player_inventory) if isinstance(player_inventory, list) else False

            if has_item:
                # Import connection manager for streaming
                from ..api.websocket_manager import connection_manager

                # Define streaming callback to broadcast chunks via WebSocket
                async def stream_action_chunk(chunk: str):
                    """Callback to broadcast streaming action outcome chunks"""
                    await connection_manager.broadcast_to_session(
                        state["session_id"],
                        {
                            "event": "action_outcome_chunk",
                            "chunk": chunk,
                            "is_complete": False
                        }
                    )

                # Player has the item - generate outcome narrative with streaming
                usage_context = parameters.get("usage_context", f"using {item_name}")
                outcome_text = await gm_agent.generate_generic_action_outcome(
                    f"use the {item_name} - {usage_context}",
                    state,
                    stream_callback=stream_action_chunk
                )

                # Broadcast final completion chunk
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_outcome_chunk",
                        "chunk": "",
                        "is_complete": True
                    }
                )
            else:
                # Player doesn't have the item - provide helpful guidance
                outcome_text = f"""You reach for the {item_name}, but you don't currently have that item in your inventory.

To acquire items, you can:
• **Examine your surroundings** to find items in the scene
• **Take items** that are visible and available
• **Receive items** from NPCs through dialogue or quest completion
• **Check your inventory** to see what items you currently have

Would you like to look around for items, or try something else?"""

            # Create chat message with the outcome
            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": outcome_text,
                "metadata": {
                    "action_type": "use_item",
                    "item_id": item_id,
                    "had_item": has_item
                }
            }
            state["chat_messages"].append(chat_message)

            outcome = {"used_item": item_id, "success": has_item}

        elif action_type == "take_item":
            # Take/pick up item from the scene
            item_id = target_id
            item_name = parameters.get("item_name", item_id)

            # Load visible items from scene (these are full item objects with IDs)
            from ..services.mongo_persistence import mongo_persistence
            scene_data = await mongo_persistence.get_scene(state["current_scene_id"])
            visible_item_ids = scene_data.get("visible_item_ids", []) if scene_data else []

            # Check if item is in visible items
            item_data = None
            if visible_item_ids:
                # Try to find the item by ID or name
                for vid in visible_item_ids:
                    item_obj = await mongo_persistence.get_item(vid)
                    if item_obj:
                        # Match by ID or name
                        if (item_obj.get("_id") == item_id or
                            item_obj.get("item_id") == item_id or
                            item_obj.get("name", "").lower() == item_name.lower()):
                            item_data = item_obj
                            item_id = item_obj.get("_id") or item_obj.get("item_id")
                            break

            if item_data:
                # Item found - add to player inventory
                if player_id not in state["player_inventories"]:
                    state["player_inventories"][player_id] = []

                # Add item to inventory
                inventory_item = {
                    "item_id": item_id,
                    "name": item_data.get("name", item_name),
                    "description": item_data.get("description", ""),
                    "properties": item_data.get("properties", {}),
                    "acquired_at": datetime.utcnow().isoformat()
                }
                state["player_inventories"][player_id].append(inventory_item)

                # Remove from state's visible_items list (which contains names)
                # This is session-specific and won't affect the scene template
                item_name_to_remove = item_data.get("name", item_name)
                if "visible_items" in state and item_name_to_remove in state["visible_items"]:
                    state["visible_items"].remove(item_name_to_remove)

                # Get quest progress for this item
                quest_info = await get_quest_progress_for_acquisition(state, "item", item_id)

                # Get scene name for source attribution
                scene_name = scene_data.get("name", "the scene") if scene_data else "the scene"

                # Broadcast item acquired event with source and quest data
                from ..api.websocket_manager import connection_manager
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "item_acquired",
                        "item": {
                            "id": item_id,
                            "name": item_data.get("name", item_name),
                            "description": item_data.get("description", "Item acquired from the scene"),
                            "source": f"Found in {scene_name}",
                            **quest_info
                        }
                    }
                )

                # Check objective cascade after item acquisition
                try:
                    from ..managers.quest_tracker import quest_tracker
                    await quest_tracker.check_objective_cascade(
                        state["session_id"],
                        player_id,
                        state
                    )
                except Exception as e:
                    logger.error(f"Error checking objective cascade after take_item: {e}")

                # Define streaming callback to broadcast chunks via WebSocket
                async def stream_action_chunk(chunk: str):
                    """Callback to broadcast streaming action outcome chunks"""
                    await connection_manager.broadcast_to_session(
                        state["session_id"],
                        {
                            "event": "action_outcome_chunk",
                            "chunk": chunk,
                            "is_complete": False
                        }
                    )

                # Generate narrative about taking the item with streaming
                take_text = await gm_agent.generate_generic_action_outcome(
                    f"pick up and take the {item_data.get('name', item_name)}",
                    state,
                    stream_callback=stream_action_chunk
                )

                # Broadcast final completion chunk
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_outcome_chunk",
                        "chunk": "",
                        "is_complete": True
                    }
                )

                # Create chat message
                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": take_text,
                    "metadata": {
                        "action_type": "take_item",
                        "item_acquired": item_id
                    }
                }
                state["chat_messages"].append(chat_message)

                outcome = {"item_taken": item_id, "success": True}

            else:
                # Item not found in scene - provide guidance
                take_text = f"""You look around for the {item_name}, but you don't see that item available in this location.

The items visible in this scene are:
{chr(10).join(f"• **{item}**" for item in state.get("visible_items", [])) if state.get("visible_items") else "• No items are currently visible"}

Try:
• **Examining your surroundings** more carefully to find items
• **Talking to NPCs** who might give you items
• **Searching specific locations** mentioned in the scene description

What would you like to do?"""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": take_text,
                    "metadata": {
                        "action_type": "take_item",
                        "item_not_found": item_name
                    }
                }
                state["chat_messages"].append(chat_message)

                outcome = {"item_taken": item_name, "success": False}

        elif action_type == "investigate_discovery":
            # Investigate a discovery in the scene
            discovery_id = target_id
            discovery_name = parameters.get("discovery_name", discovery_id)

            # Check if discovery exists in available discoveries
            available_discoveries = state.get("available_discoveries", [])
            discovery = None
            for d in available_discoveries:
                if d.get("_id") == discovery_id or d.get("discovery_id") == discovery_id or d.get("name", "").lower() == discovery_name.lower():
                    discovery = d
                    discovery_id = d.get("_id") or d.get("discovery_id")
                    break

            if discovery:
                # Import connection manager for streaming
                from ..api.websocket_manager import connection_manager

                # Define streaming callback to broadcast chunks via WebSocket
                async def stream_action_chunk(chunk: str):
                    """Callback to broadcast streaming action outcome chunks"""
                    await connection_manager.broadcast_to_session(
                        state["session_id"],
                        {
                            "event": "action_outcome_chunk",
                            "chunk": chunk,
                            "is_complete": False
                        }
                    )

                # Discovery found - generate investigation narrative with streaming
                investigation_text = await gm_agent.generate_generic_action_outcome(
                    f"investigate and examine the {discovery.get('name', discovery_name)}: {discovery.get('description', '')}",
                    state,
                    stream_callback=stream_action_chunk
                )

                # Broadcast final completion chunk
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_outcome_chunk",
                        "chunk": "",
                        "is_complete": True
                    }
                )

                # Extract acquisitions from the narrative (for AI-generated campaigns without pre-defined knowledge)
                from .objective_tracker import detect_acquisitions_from_narrative
                extracted_acquisitions = await detect_acquisitions_from_narrative(
                    narrative=investigation_text,
                    player_action=f"investigate {discovery.get('name', discovery_name)}",
                    scene_context=state.get("current_scene", {})
                )

                # Add extracted acquisitions to pending
                if "pending_acquisitions" not in state:
                    state["pending_acquisitions"] = {
                        "knowledge": [],
                        "items": [],
                        "events": [],
                        "challenges": []
                    }

                for k in extracted_acquisitions.get("knowledge", []):
                    state["pending_acquisitions"]["knowledge"].append(k)

                for i in extracted_acquisitions.get("items", []):
                    state["pending_acquisitions"]["items"].append(i)

                # Create chat message
                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": investigation_text,
                    "metadata": {
                        "action_type": "investigate_discovery",
                        "discovery_id": discovery_id
                    }
                }
                state["chat_messages"].append(chat_message)

                # Track discovery encounter
                from ..api.websocket_manager import connection_manager
                encounter_metadata = create_encounter_metadata(state, player_id)
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "discovery_encountered",
                        "discovery": {
                            "id": discovery_id,
                            "name": discovery.get("name", "Unknown Discovery"),
                            "description": discovery.get("description", "Discovery investigated"),
                            "metadata": encounter_metadata
                        }
                    }
                )

                # Award knowledge from discovery
                knowledge_ids = discovery.get("knowledge_revealed", [])
                if knowledge_ids:
                    from ..services.mongo_persistence import mongo_persistence
                    for knowledge_id in knowledge_ids:
                        knowledge_data = await mongo_persistence.get_knowledge_by_id(knowledge_id)
                        if knowledge_data:
                            # Add to player's knowledge
                            if "player_knowledge" not in state:
                                state["player_knowledge"] = {}
                            if player_id not in state["player_knowledge"]:
                                state["player_knowledge"][player_id] = {}

                            if knowledge_id not in state["player_knowledge"][player_id]:
                                # Store as dict with metadata for compatibility with rabbitmq_consumer
                                state["player_knowledge"][player_id][knowledge_id] = {
                                    "level": 1,
                                    "acquired_at": datetime.utcnow().isoformat()
                                }

                                # Persist knowledge acquisition to MongoDB and Neo4j
                                await persist_knowledge_acquisition(
                                    session_id=state["session_id"],
                                    player_id=player_id,
                                    knowledge_id=knowledge_id,
                                    knowledge_data=knowledge_data,
                                    source_type="discovery",
                                    source_id=discovery_id,
                                    metadata={
                                        "session_id": state["session_id"],
                                        "quest_id": state.get("active_quest", {}).get("quest_id"),
                                        "scene_id": state.get("current_scene", {}).get("scene_id"),
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                )

                                # Get quest progress for this knowledge
                                quest_info = await get_quest_progress_for_acquisition(state, "knowledge", knowledge_id)

                                # Get discovery name for source attribution
                                discovery_name = discovery.get("name", "discovery")

                                # Broadcast knowledge gained event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "knowledge_gained",
                                        "knowledge": {
                                            "id": knowledge_id,
                                            "name": knowledge_data.get("name") or knowledge_data.get("title", "Unknown Knowledge"),
                                            "description": knowledge_data.get("description", "Knowledge from discovery"),
                                            "source": f"From investigating {discovery_name}",
                                            "source_discovery": discovery_name,  # Add discovery name for tracking completion
                                            **quest_info
                                        }
                                    }
                                )

                                # Calculate and broadcast complete quest progress
                                complete_progress = await calculate_complete_quest_progress(state)
                                if complete_progress:
                                    await connection_manager.broadcast_to_session(
                                        state["session_id"],
                                        {
                                            "event": "quest_progress_update",
                                            "quest_progress": complete_progress
                                        }
                                    )

                                # Check objective cascade and broadcast progress updates
                                try:
                                    from ..managers.quest_tracker import QuestProgressionTracker
                                    quest_tracker = QuestProgressionTracker()
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade: {e}")

                # Award items from discovery
                item_ids = discovery.get("items_revealed", [])
                if item_ids:
                    from ..services.mongo_persistence import mongo_persistence
                    for item_id in item_ids:
                        item_data = await mongo_persistence.get_item(item_id)
                        if item_data:
                            # Add to player's inventory
                            if player_id not in state["player_inventories"]:
                                state["player_inventories"][player_id] = []

                            has_item = any(
                                inv_item.get("item_id") == item_id
                                for inv_item in state["player_inventories"][player_id]
                            )

                            if not has_item:
                                inventory_item = {
                                    "item_id": item_id,
                                    "name": item_data.get("name", "Unknown Item"),
                                    "description": item_data.get("description", ""),
                                    "properties": item_data.get("properties", {}),
                                    "acquired_at": datetime.utcnow().isoformat(),
                                    "acquired_from": "discovery",
                                    "source_discovery": discovery_id
                                }
                                state["player_inventories"][player_id].append(inventory_item)

                                # Get quest progress for this item
                                quest_info = await get_quest_progress_for_acquisition(state, "item", item_id)

                                # Get discovery name for source attribution
                                discovery_name = discovery.get("name", "discovery")

                                # Broadcast item acquired event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "item_acquired",
                                        "item": {
                                            "id": item_id,
                                            "name": item_data.get("name", "Unknown Item"),
                                            "description": item_data.get("description", "Discovered item"),
                                            "source": f"From investigating {discovery_name}",
                                            **quest_info
                                        }
                                    }
                                )

                                # Check objective cascade after item acquisition from discovery
                                try:
                                    from ..managers.quest_tracker import quest_tracker
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade after discovery item: {e}")

                # Mark discovery as completed
                if discovery_id not in state.get("completed_discoveries", []):
                    state["completed_discoveries"].append(discovery_id)

                outcome = {"discovery_investigated": discovery_id, "success": True}

            else:
                # Discovery not found - provide guidance
                investigation_text = f"""You search for "{discovery_name}", but you don't see that particular discovery available here.

The discoveries available in this scene are:
{chr(10).join(f"• **{d.get('name', 'Unknown')}**: {d.get('description', 'No description')}" for d in available_discoveries) if available_discoveries else "• No discoveries are currently available"}

Try examining your surroundings or asking what you can investigate."""

                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": investigation_text,
                    "metadata": {
                        "action_type": "investigate_discovery",
                        "discovery_not_found": discovery_name
                    }
                }
                state["chat_messages"].append(chat_message)

                outcome = {"discovery_investigated": discovery_name, "success": False}

        elif action_type == "attempt_challenge":
            # Attempt a challenge/puzzle
            challenge_id = target_id

            # Check if challenge exists in active challenges
            active_challenges = state.get("active_challenges", [])
            challenge = None
            for ch in active_challenges:
                if ch.get("_id") == challenge_id or ch.get("challenge_id") == challenge_id:
                    challenge = ch
                    break

            if challenge:
                # Import connection manager for streaming
                from ..api.websocket_manager import connection_manager

                # Define streaming callback to broadcast chunks via WebSocket
                async def stream_action_chunk(chunk: str):
                    """Callback to broadcast streaming action outcome chunks"""
                    await connection_manager.broadcast_to_session(
                        state["session_id"],
                        {
                            "event": "action_outcome_chunk",
                            "chunk": chunk,
                            "is_complete": False
                        }
                    )

                # Challenge exists - generate attempt narrative with streaming
                challenge_name = challenge.get("name", "challenge")
                challenge_description = challenge.get("description", "")
                attempt_text = await gm_agent.generate_generic_action_outcome(
                    f"attempt the challenge: {challenge_name}. {challenge_description}",
                    state,
                    stream_callback=stream_action_chunk
                )

                # Broadcast final completion chunk
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "action_outcome_chunk",
                        "chunk": "",
                        "is_complete": True
                    }
                )

                # Track challenge encounter
                encounter_metadata = create_encounter_metadata(state, player_id)
                await connection_manager.broadcast_to_session(
                    state["session_id"],
                    {
                        "event": "challenge_encountered",
                        "challenge": {
                            "id": challenge_id,
                            "name": challenge.get("name", "Unknown Challenge"),
                            "description": challenge.get("description", "Challenge attempted"),
                            "metadata": encounter_metadata
                        }
                    }
                )

                # Award knowledge from challenge completion
                knowledge_ids = challenge.get("knowledge_revealed", [])
                if knowledge_ids:
                    from ..services.mongo_persistence import mongo_persistence
                    for knowledge_id in knowledge_ids:
                        knowledge_data = await mongo_persistence.get_knowledge_by_id(knowledge_id)
                        if knowledge_data:
                            # Add to player's knowledge
                            if "player_knowledge" not in state:
                                state["player_knowledge"] = {}
                            if player_id not in state["player_knowledge"]:
                                state["player_knowledge"][player_id] = {}

                            if knowledge_id not in state["player_knowledge"][player_id]:
                                # Store as dict with metadata for compatibility with rabbitmq_consumer
                                state["player_knowledge"][player_id][knowledge_id] = {
                                    "level": 1,
                                    "acquired_at": datetime.utcnow().isoformat()
                                }

                                # Persist knowledge acquisition to MongoDB and Neo4j
                                await persist_knowledge_acquisition(
                                    session_id=state["session_id"],
                                    player_id=player_id,
                                    knowledge_id=knowledge_id,
                                    knowledge_data=knowledge_data,
                                    source_type="challenge",
                                    source_id=challenge_id,
                                    metadata={
                                        "session_id": state["session_id"],
                                        "quest_id": state.get("active_quest", {}).get("quest_id"),
                                        "scene_id": state.get("current_scene", {}).get("scene_id"),
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                )

                                # Get quest progress for this knowledge
                                quest_info = await get_quest_progress_for_acquisition(state, "knowledge", knowledge_id)

                                # Get challenge name for source attribution
                                challenge_name = challenge.get("name", "challenge")

                                # Broadcast knowledge gained event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "knowledge_gained",
                                        "knowledge": {
                                            "id": knowledge_id,
                                            "name": knowledge_data.get("name") or knowledge_data.get("title", "Unknown Knowledge"),
                                            "description": knowledge_data.get("description", "Knowledge from challenge"),
                                            "source": f"From completing {challenge_name}",
                                            **quest_info
                                        }
                                    }
                                )

                                # Check objective cascade after knowledge acquisition from challenge
                                try:
                                    from ..managers.quest_tracker import quest_tracker
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade after challenge knowledge: {e}")

                # Award items from challenge completion
                item_ids = challenge.get("items_rewarded", [])
                if item_ids:
                    from ..services.mongo_persistence import mongo_persistence
                    for item_id in item_ids:
                        item_data = await mongo_persistence.get_item(item_id)
                        if item_data:
                            # Add to player's inventory
                            if player_id not in state["player_inventories"]:
                                state["player_inventories"][player_id] = []

                            has_item = any(
                                inv_item.get("item_id") == item_id
                                for inv_item in state["player_inventories"][player_id]
                            )

                            if not has_item:
                                inventory_item = {
                                    "item_id": item_id,
                                    "name": item_data.get("name", "Unknown Item"),
                                    "description": item_data.get("description", ""),
                                    "properties": item_data.get("properties", {}),
                                    "acquired_at": datetime.utcnow().isoformat(),
                                    "acquired_from": "challenge",
                                    "source_challenge": challenge_id
                                }
                                state["player_inventories"][player_id].append(inventory_item)

                                # Get quest progress for this item
                                quest_info = await get_quest_progress_for_acquisition(state, "item", item_id)

                                # Get challenge name for source attribution
                                challenge_name = challenge.get("name", "challenge")

                                # Broadcast item acquired event with source and quest data
                                await connection_manager.broadcast_to_session(
                                    state["session_id"],
                                    {
                                        "event": "item_acquired",
                                        "item": {
                                            "id": item_id,
                                            "name": item_data.get("name", "Unknown Item"),
                                            "description": item_data.get("description", "Reward from challenge"),
                                            "source": f"Reward from {challenge_name}",
                                            **quest_info
                                        }
                                    }
                                )

                                # Check objective cascade after item acquisition from challenge
                                try:
                                    from ..managers.quest_tracker import quest_tracker
                                    await quest_tracker.check_objective_cascade(
                                        state["session_id"],
                                        player_id,
                                        state
                                    )
                                except Exception as e:
                                    logger.error(f"Error checking objective cascade after challenge item: {e}")

                # Mark challenge as completed
                if challenge_id not in state.get("completed_challenges", []):
                    state["completed_challenges"].append(challenge_id)

                # Check objective cascade after challenge completion
                try:
                    from ..managers.quest_tracker import quest_tracker
                    await quest_tracker.check_objective_cascade(
                        state["session_id"],
                        player_id,
                        state
                    )
                except Exception as e:
                    logger.error(f"Error checking objective cascade after challenge completion: {e}")

            else:
                # Challenge doesn't exist - provide guidance
                attempt_text = f"""You attempt to tackle a challenge, but I'm not sure which specific challenge you're referring to.

The available challenges in this scene are:
{chr(10).join(f"• **{ch.get('name', 'Unknown')}**: {ch.get('description', 'No description')}" for ch in active_challenges) if active_challenges else "• No challenges are currently available"}

Try examining your surroundings more carefully, or ask me about what challenges are available."""

            # Create chat message with the attempt outcome
            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_NARRATIVE",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": attempt_text,
                "metadata": {
                    "action_type": "attempt_challenge",
                    "challenge_id": challenge_id,
                    "challenge_found": bool(challenge)
                }
            }
            state["chat_messages"].append(chat_message)

            outcome = {"attempted_challenge": challenge_id, "success": bool(challenge)}
            requires_assessment = bool(challenge)  # Only assess if challenge was valid

        # Record action in history
        player_action: PlayerAction = {
            "action_id": f"action_{datetime.utcnow().timestamp()}",
            "player_id": player_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action_type,
            "target_id": target_id,
            "parameters": parameters,
            "outcome": outcome
        }
        state["action_history"].append(player_action)

        # Store outcome and assessment requirement
        state["pending_action"]["outcome"] = outcome
        state["requires_assessment"] = requires_assessment

        if requires_assessment:
            state["assessment_context"] = {
                "action": interpretation,
                "outcome": outcome,
                "rubric_id": outcome.get("rubric_id") if isinstance(outcome, dict) else None
            }

        # Determine next node
        if action_type == "move_to_location":
            state["current_node"] = "generate_scene"
        elif requires_assessment:
            state["current_node"] = "assess_performance"
        else:
            state["current_node"] = "update_world_state"

        state["last_updated"] = datetime.utcnow().isoformat()
        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "action_executed",
            session_id=state["session_id"],
            action_type=action_type,
            requires_assessment=requires_assessment
        )

        return state

    except Exception as e:
        logger.error(
            "action_execution_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def assess_performance_node(state: GameSessionState) -> GameSessionState:
    """
    Assess player performance using rubrics and Bloom's Taxonomy
    """
    try:
        logger.info(
            "assessing_performance",
            session_id=state["session_id"]
        )

        assessment_context = state.get("assessment_context", {})
        if not assessment_context:
            logger.warning("no_assessment_context", session_id=state["session_id"])
            state["current_node"] = "update_world_state"
            state["requires_assessment"] = False
            return state

        # TODO: Implement rubric-based assessment agent
        # For now, create a placeholder assessment

        assessment: AssessmentResult = {
            "assessment_id": f"assess_{datetime.utcnow().timestamp()}",
            "player_id": state.get("pending_action", {}).get("player_id", ""),
            "timestamp": datetime.utcnow().isoformat(),
            "rubric_id": assessment_context.get("rubric_id", ""),
            "performance_indicators": {},
            "bloom_level_demonstrated": "Understand",
            "dimensional_scores": {},
            "strengths": ["Engaged with NPC effectively"],
            "areas_for_improvement": [],
            "feedback_message": "Good interaction! You're making progress.",
            "experience_gained": 10
        }

        # Store assessment
        if "assessments" not in state:
            state["assessments"] = []
        state["assessments"].append(assessment)

        # Add assessment to chat
        chat_message = {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "session_id": state["session_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "DM_ASSESSMENT",
            "sender_id": "game_master",
            "sender_name": "Game Master",
            "content": assessment["feedback_message"],
            "metadata": {
                "bloom_level": assessment["bloom_level_demonstrated"],
                "experience_gained": assessment["experience_gained"]
            }
        }
        state["chat_messages"].append(chat_message)

        # Publish assessment event
        await rabbitmq_client.publish_assessment(
            state["session_id"],
            assessment
        )

        state["current_node"] = "update_world_state"
        state["requires_assessment"] = False
        state["assessment_context"] = None
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "performance_assessed",
            session_id=state["session_id"],
            bloom_level=assessment["bloom_level_demonstrated"]
        )

        return state

    except Exception as e:
        logger.error(
            "assessment_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        state["current_node"] = "update_world_state"
        return state


async def update_world_state_node(state: GameSessionState) -> GameSessionState:
    """
    Update world state based on action outcomes
    Apply consequences, update NPCs, persist changes
    """
    try:
        logger.info(
            "updating_world_state",
            session_id=state["session_id"]
        )

        # Get action outcome
        pending_action = state.get("pending_action")
        outcome = pending_action.get("outcome", {}) if pending_action else {}

        # Update game time
        state["elapsed_game_time"] = state.get("elapsed_game_time", 0) + 1

        # Update time of day (simple progression)
        elapsed = state["elapsed_game_time"]
        if elapsed < 10:
            state["time_of_day"] = "morning"
        elif elapsed < 20:
            state["time_of_day"] = "afternoon"
        elif elapsed < 30:
            state["time_of_day"] = "evening"
        else:
            state["time_of_day"] = "night"

        # Record world change
        # TODO: Persist to MongoDB and Neo4j
        if outcome:
            world_change = {
                "change_id": f"change_{datetime.utcnow().timestamp()}",
                "timestamp": datetime.utcnow().isoformat(),
                "change_type": "action_outcome",
                "affected_entities": [pending_action.get("player_id")],
                "description": f"Player action resulted in: {outcome}",
                "data": outcome
            }

            if "world_changes" not in state:
                state["world_changes"] = []
            state["world_changes"].append(world_change)

        # Clear pending action
        state["pending_action"] = None

        # Move to next node
        state["current_node"] = "check_quest_objectives"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "world_state_updated",
            session_id=state["session_id"],
            elapsed_time=state["elapsed_game_time"]
        )

        return state

    except Exception as e:
        logger.error(
            "world_state_update_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def check_quest_objectives_node(state: GameSessionState) -> GameSessionState:
    """
    Check if quest objectives or campaign goals are completed
    """
    try:
        logger.info(
            "checking_quest_objectives",
            session_id=state["session_id"]
        )

        # TODO: Implement quest objective checking with quest-mission MCP
        # For now, just check action count as simple progression

        quest_completed = False
        campaign_completed = False

        # Simple check: if 20 actions taken, mark quest as complete
        if len(state.get("action_history", [])) >= 20:
            current_quest_id = state.get("current_quest_id")
            if current_quest_id and current_quest_id not in state.get("completed_quest_ids", []):
                state["completed_quest_ids"].append(current_quest_id)
                quest_completed = True

                # Add completion message
                chat_message = {
                    "message_id": f"msg_{datetime.utcnow().timestamp()}",
                    "session_id": state["session_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_type": "DM_NARRATIVE",
                    "sender_id": "game_master",
                    "sender_name": "Game Master",
                    "content": "Quest completed! You've successfully finished this chapter of your adventure.",
                    "metadata": {
                        "event_type": "quest_complete",
                        "quest_id": current_quest_id
                    }
                }
                state["chat_messages"].append(chat_message)

        # Check if all quests complete (campaign done)
        # TODO: Get total quest count from MCP

        state["current_node"] = "provide_bloom_feedback"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        logger.info(
            "quest_objectives_checked",
            session_id=state["session_id"],
            quest_completed=quest_completed
        )

        return state

    except Exception as e:
        logger.error(
            "quest_check_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def provide_bloom_feedback_node(state: GameSessionState) -> GameSessionState:
    """
    Provide Bloom's Taxonomy progression feedback
    """
    try:
        logger.info(
            "providing_bloom_feedback",
            session_id=state["session_id"]
        )

        # TODO: Implement comprehensive Bloom's analysis
        # For now, provide periodic feedback every 5 actions

        action_count = len(state.get("action_history", []))

        if action_count % 5 == 0 and action_count > 0:
            # Generate feedback message
            feedback_content = f"""You're progressing well! So far, you've demonstrated skills at the 'Understand' and 'Apply' levels of Bloom's Taxonomy.

Keep exploring and engaging with NPCs to unlock higher-order thinking challenges."""

            chat_message = {
                "message_id": f"msg_{datetime.utcnow().timestamp()}",
                "session_id": state["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "DM_BLOOM_FEEDBACK",
                "sender_id": "game_master",
                "sender_name": "Game Master",
                "content": feedback_content,
                "metadata": {
                    "action_count": action_count,
                    "current_bloom_tier": "Understand"
                }
            }
            state["chat_messages"].append(chat_message)

        state["current_node"] = "check_session_end"
        state["last_updated"] = datetime.utcnow().isoformat()

        await redis_manager.save_state(state["session_id"], state)

        return state

    except Exception as e:
        logger.error(
            "bloom_feedback_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


async def check_session_end_node(state: GameSessionState) -> GameSessionState:
    """
    Check if session should end or continue
    """
    try:
        logger.info(
            "checking_session_end",
            session_id=state["session_id"]
        )

        should_end = False

        # Check end conditions
        if state.get("status") == SessionStatus.PAUSED:
            should_end = True
        elif state.get("status") == SessionStatus.COMPLETED:
            should_end = True
        elif state.get("status") == SessionStatus.ERROR:
            should_end = True

        # TODO: Check if all campaign quests completed

        if should_end:
            state["current_node"] = "END"
            logger.info("session_ending", session_id=state["session_id"])
        else:
            # Continue game loop - go back to await player input
            state["current_node"] = "await_player_input"
            state["awaiting_player_input"] = True

        state["last_updated"] = datetime.utcnow().isoformat()
        await redis_manager.save_state(state["session_id"], state)

        return state

    except Exception as e:
        logger.error(
            "session_end_check_failed",
            session_id=state.get("session_id"),
            error=str(e)
        )
        return state


# ============================================
# Conditional Edge Functions
# ============================================

def should_continue_session(state: GameSessionState) -> str:
    """Determine if session should continue or end"""
    if state.get("current_node") == "END":
        return "end"
    elif state.get("status") in [SessionStatus.PAUSED, SessionStatus.COMPLETED, SessionStatus.ERROR]:
        return "end"
    else:
        return "continue"


def route_after_execution(state: GameSessionState) -> str:
    """Route to appropriate node after action execution"""
    if state.get("current_node") == "generate_scene":
        return "generate_scene"
    elif state.get("requires_assessment"):
        return "assess_performance"
    else:
        return "update_world_state"


def route_from_await_input(state: GameSessionState) -> str:
    """Route from await_player_input based on whether there's pending action"""
    # If there's a pending action, continue to interpret it
    if state.get("pending_action"):
        return "interpret_action"
    # Otherwise, pause workflow (end for now, will be restarted by WebSocket)
    else:
        return "end"


def route_from_initialize(state: GameSessionState) -> str:
    """Route from initialize_session based on whether session was already initialized"""
    # If session already has a scene_description or current_node set to something other than
    # generate_scene, it was already initialized
    # Route to the current node instead of generate_scene
    current_node = state.get("current_node")
    has_scene = bool(state.get("scene_description"))

    if has_scene and current_node and current_node != "generate_scene":
        logger.info(
            "routing_to_current_node",
            session_id=state.get("session_id"),
            current_node=current_node
        )
        return current_node
    else:
        # New session, proceed to generate_scene
        return "generate_scene"


# ============================================
# Build Workflow Graph
# ============================================

def build_game_loop_workflow() -> StateGraph:
    """
    Build the LangGraph workflow for game loop

    Returns:
        Compiled StateGraph workflow
    """

    # Create workflow graph
    # Use Dict instead of GameSessionState to avoid validation issues with total=False
    workflow = StateGraph(dict)

    # Add all nodes
    workflow.add_node("initialize_session", initialize_session_node)
    workflow.add_node("generate_scene", generate_scene_node)
    workflow.add_node("await_player_input", await_player_input_node)
    workflow.add_node("interpret_action", interpret_action_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("assess_performance", assess_performance_node)
    workflow.add_node("update_world_state", update_world_state_node)
    workflow.add_node("check_quest_objectives", check_quest_objectives_node)
    workflow.add_node("provide_bloom_feedback", provide_bloom_feedback_node)
    workflow.add_node("check_session_end", check_session_end_node)

    # Set entry point
    workflow.set_entry_point("initialize_session")

    # Conditional routing from initialize_session
    # If already initialized, route to current_node; otherwise, route to generate_scene
    workflow.add_conditional_edges(
        "initialize_session",
        route_from_initialize,
        {
            "generate_scene": "generate_scene",
            "interpret_action": "interpret_action",
            "execute_action": "execute_action",
            "assess_performance": "assess_performance",
            "update_world_state": "update_world_state",
            "check_quest_objectives": "check_quest_objectives",
            "provide_bloom_feedback": "provide_bloom_feedback",
            "check_session_end": "check_session_end",
            "await_player_input": "await_player_input"
        }
    )

    # Add edges
    workflow.add_edge("generate_scene", "await_player_input")

    # Conditional routing from await_player_input
    workflow.add_conditional_edges(
        "await_player_input",
        route_from_await_input,
        {
            "interpret_action": "interpret_action",
            "end": END
        }
    )

    workflow.add_edge("interpret_action", "execute_action")

    # Conditional routing after action execution
    workflow.add_conditional_edges(
        "execute_action",
        route_after_execution,
        {
            "generate_scene": "generate_scene",
            "assess_performance": "assess_performance",
            "update_world_state": "update_world_state"
        }
    )

    workflow.add_edge("assess_performance", "update_world_state")
    workflow.add_edge("update_world_state", "check_quest_objectives")
    workflow.add_edge("check_quest_objectives", "provide_bloom_feedback")
    workflow.add_edge("provide_bloom_feedback", "check_session_end")

    # Conditional routing at session end check
    workflow.add_conditional_edges(
        "check_session_end",
        should_continue_session,
        {
            "continue": "await_player_input",
            "end": END
        }
    )

    # Compile workflow
    # Note: recursion_limit must be set when invoking the workflow, not during compilation
    # The default limit is 25, but the game loop can legitimately go through many nodes
    # in a single turn (initialize -> generate_scene -> await_input -> interpret -> execute ->
    # assess -> update -> check_quest -> bloom_feedback -> check_end -> await_input)
    # That's 11 nodes, so with player interactions we can easily hit 25
    compiled_workflow = workflow.compile()

    logger.info("game_loop_workflow_built")

    return compiled_workflow


# Global compiled workflow instance
game_loop = build_game_loop_workflow()
