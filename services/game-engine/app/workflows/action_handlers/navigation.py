"""
Navigation Action Handler

Handles navigation actions:
- move_to_location: Move to a different location/scene

Extracted from game_loop.py lines 1861-1945
"""

from typing import Dict, Any, Optional
from .base import ActionHandler, ActionResult
from ...core.logging import get_logger
from datetime import datetime

logger = get_logger(__name__)


class NavigationHandler(ActionHandler):
    """Handles movement and navigation actions."""

    async def can_handle(self, action_type: str, state: Dict[str, Any]) -> bool:
        """Check if this handler can process navigation actions."""
        return action_type == "move_to_location"

    async def execute(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str] = None
    ) -> ActionResult:
        """Execute navigation action."""
        return await self._handle_move_to_location(parameters, state, target_id)

    async def _handle_move_to_location(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str]
    ) -> ActionResult:
        """
        Handle moving to a new location.

        Extracted from game_loop.py lines 1861-1945

        Steps:
        1. Get new location ID from target_id
        2. Try multiple resolution strategies (Scene or Place)
        3. Validate location exists
        4. If invalid, provide GM guidance
        5. If valid, update state and trigger scene regeneration
        6. Return result
        """
        try:
            # Move player to new location - validate and resolve to scene
            new_location_id = target_id
            pending_action = state.get("pending_action", {})
            player_id = pending_action.get("player_id")

            logger.info("handling_move_to_location", location_id=new_location_id, player_id=player_id)

            # Try multiple resolution strategies
            from ..mongo_persistence import mongo_persistence

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

                return self._create_success_result(
                    outcome={"invalid_location": new_location_id, "gm_guidance_provided": True},
                    narrative_generated=True
                )
            else:
                # Valid location - proceed with move
                old_scene = state.get("current_scene_id")
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
                if old_scene and old_scene not in state.get("completed_scene_ids", []):
                    if "completed_scene_ids" not in state:
                        state["completed_scene_ids"] = []
                    state["completed_scene_ids"].append(old_scene)

                # Will regenerate scene (trigger in game loop routing)
                state["current_node"] = "generate_scene"

                return self._create_success_result(
                    outcome={"moved_to": target_scene_id},
                    narrative_generated=False  # Scene will be generated in generate_scene node
                )

        except Exception as e:
            logger.error(f"Error handling move_to_location: {e}", exc_info=True)
            return self._create_error_result(str(e))
