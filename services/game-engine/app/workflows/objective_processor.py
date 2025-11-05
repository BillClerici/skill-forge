"""
Objective Processing Module
Clean integration point for child objective cascade system into game loop
"""
from typing import Dict, Any, Optional
from ..core.logging import get_logger
from .objective_tracker import process_player_action_and_narrative

logger = get_logger(__name__)


async def process_objectives_after_action(
    state: Dict[str, Any],
    pending_action: Dict[str, Any],
    action_type: str,
    target_id: Optional[str],
    parameters: Dict[str, Any],
    outcome: Any
) -> Dict[str, Any]:
    """
    Process child objectives after a player action is executed.

    This is a clean integration point that can be called from the game loop
    without cluttering it with complex objective processing logic.

    Args:
        state: Game session state
        pending_action: The action that was just executed
        action_type: Type of action (talk_to_npc, examine, investigate_discovery, etc.)
        target_id: ID of the target entity (NPC, discovery, etc.)
        parameters: Action parameters
        outcome: Result of the action execution

    Returns:
        Dict with processing results (summary of completed objectives)
    """
    try:
        # Extract required data
        player_id = pending_action.get("player_id")
        campaign_id = state.get("campaign_id")

        # Quick exit if missing required data
        if not player_id or not campaign_id or not outcome:
            return {"processed": False, "reason": "missing_required_data"}

        # Get player's action text
        player_action_text = pending_action.get("player_input", "")

        # Get GM's narrative response from chat messages
        gm_narrative = _extract_gm_narrative(state)

        # Build scene context
        scene_context = {
            "discoveries": state.get("available_discoveries", []),
            "items": state.get("available_items", []),
            "events": state.get("active_events", []),
            "challenges": state.get("available_challenges", []),
            "npcs": state.get("available_npcs", [])
        }

        # Map game loop action types to cascade system action types
        cascade_action_type = _map_action_type(action_type)

        # Build action data structure
        action_data = _build_action_data(
            action_type=action_type,
            target_id=target_id,
            parameters=parameters,
            outcome=outcome,
            player_action_text=player_action_text,
            state=state
        )

        # Log processing start
        logger.info(
            "processing_objectives_after_action",
            session_id=state.get("session_id"),
            player_id=player_id,
            action_type=cascade_action_type,
            has_narrative=bool(gm_narrative)
        )

        # Call the comprehensive objective processing function
        results = await process_player_action_and_narrative(
            session_id=state["session_id"],
            player_id=player_id,
            campaign_id=campaign_id,
            player_action=player_action_text,
            action_type=cascade_action_type,
            action_data=action_data,
            gm_narrative=gm_narrative,
            scene_context=scene_context
        )

        # Log summary
        summary = results.get("summary", {})
        logger.info(
            "objectives_processed_successfully",
            session_id=state.get("session_id"),
            child_completed=summary.get("child_objectives_completed", 0),
            quest_completed=summary.get("quest_objectives_completed", 0),
            campaign_completed=summary.get("campaign_objectives_completed", 0),
            total_updates=summary.get("total_progress_updates", 0)
        )

        return {
            "processed": True,
            "summary": summary,
            "results": results
        }

    except Exception as e:
        # Don't fail the action if objective processing fails
        # Just log the error and continue
        logger.error(
            "objective_processing_failed",
            session_id=state.get("session_id"),
            error=str(e),
            error_type=type(e).__name__
        )

        return {
            "processed": False,
            "error": str(e)
        }


def _extract_gm_narrative(state: Dict[str, Any]) -> str:
    """
    Extract the GM's narrative response from chat messages.

    Args:
        state: Game session state

    Returns:
        GM's narrative text, or empty string if not found
    """
    chat_messages = state.get("chat_messages", [])

    if not chat_messages:
        return ""

    # Get the last message from the game master
    last_message = chat_messages[-1]

    if last_message.get("sender_id") == "game_master":
        return last_message.get("content", "")

    return ""


def _map_action_type(game_loop_action_type: str) -> str:
    """
    Map game loop action types to cascade system action types.

    Args:
        game_loop_action_type: Action type from game loop

    Returns:
        Action type for cascade system
    """
    action_type_map = {
        "talk_to_npc": "conversation",
        "examine": "exploration",
        "investigate_discovery": "exploration",
        "take_item": "exploration",
        "attempt_challenge": "challenge",
        "participate_in_event": "event",
        "look_around": "exploration",
        "ask_gm_question": "exploration"
    }

    return action_type_map.get(game_loop_action_type, "exploration")


def _build_action_data(
    action_type: str,
    target_id: Optional[str],
    parameters: Dict[str, Any],
    outcome: Any,
    player_action_text: str,
    state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build action data structure for cascade system.

    Args:
        action_type: Type of action
        target_id: Target entity ID
        parameters: Action parameters
        outcome: Action outcome
        player_action_text: Player's action text
        state: Game session state

    Returns:
        Action data dict
    """
    action_data = {
        "action_type": action_type,
        "target_id": target_id,
        "parameters": parameters,
        "outcome": outcome
    }

    # Add NPC-specific data for conversations
    if action_type == "talk_to_npc" and target_id:
        npc = next(
            (n for n in state.get("available_npcs", []) if n.get("npc_id") == target_id),
            None
        )
        if npc:
            action_data["npc_id"] = target_id
            action_data["npc_name"] = npc.get("name", "Unknown")
            action_data["message"] = player_action_text

    # Add discovery-specific data
    elif action_type == "investigate_discovery" and target_id:
        discovery = next(
            (d for d in state.get("available_discoveries", []) if d.get("discovery_id") == target_id),
            None
        )
        if discovery:
            action_data["discovery_id"] = target_id
            action_data["discovery_name"] = discovery.get("name", "Unknown")

    # Add challenge-specific data
    elif action_type == "attempt_challenge" and target_id:
        challenge = next(
            (c for c in state.get("available_challenges", []) if c.get("challenge_id") == target_id),
            None
        )
        if challenge:
            action_data["challenge_id"] = target_id
            action_data["challenge_name"] = challenge.get("name", "Unknown")

    # Add event-specific data
    elif action_type == "participate_in_event" and target_id:
        event = next(
            (e for e in state.get("active_events", []) if e.get("event_id") == target_id),
            None
        )
        if event:
            action_data["event_id"] = target_id
            action_data["event_name"] = event.get("name", "Unknown")

    return action_data


# Export main function
__all__ = ['process_objectives_after_action']
