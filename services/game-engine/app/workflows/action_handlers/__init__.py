"""
Action Handlers Package

Provides modular, extensible action handling for the game loop.
Each action type has its own handler module implementing the ActionHandler interface.
"""

from .base import ActionHandler, ActionResult
from .conversation import ConversationHandler
from .exploration import ExplorationHandler
from .interaction import InteractionHandler
from .investigation import InvestigationHandler
from .challenge import ChallengeHandler
from .navigation import NavigationHandler
from .gm_query import GMQueryHandler

# Action handler registry
ACTION_HANDLERS = {
    # Conversation actions
    "talk_to_npc": ConversationHandler(),
    "end_conversation": ConversationHandler(),

    # Exploration actions
    "examine": ExplorationHandler(),
    "perform_action": ExplorationHandler(),

    # Interaction actions
    "use_item": InteractionHandler(),
    "take_item": InteractionHandler(),

    # Investigation actions
    "investigate_discovery": InvestigationHandler(),

    # Challenge actions
    "attempt_challenge": ChallengeHandler(),

    # Navigation actions
    "move_to_location": NavigationHandler(),

    # GM query actions
    "ask_gm_question": GMQueryHandler(),
}


def get_action_handler(action_type: str) -> ActionHandler:
    """Get the appropriate action handler for the given action type."""
    handler = ACTION_HANDLERS.get(action_type)
    if not handler:
        raise ValueError(f"No handler registered for action type: {action_type}")
    return handler


__all__ = [
    "ActionHandler",
    "ActionResult",
    "get_action_handler",
    "ACTION_HANDLERS",
]
