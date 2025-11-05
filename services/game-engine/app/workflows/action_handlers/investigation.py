"""
Investigation Action Handler

Handles investigation actions:
- investigate_discovery: Investigate discoveries in the scene

Extract from game_loop.py lines 2296-2450
"""

from typing import Dict, Any, Optional
from .base import ActionHandler, ActionResult
from ...core.logging import get_logger

logger = get_logger(__name__)


class InvestigationHandler(ActionHandler):
    """Handles discovery investigation actions."""

    async def can_handle(self, action_type: str, state: Dict[str, Any]) -> bool:
        """Check if this handler can process investigation actions."""
        return action_type == "investigate_discovery"

    async def execute(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str] = None
    ) -> ActionResult:
        """Execute investigation action."""
        return await self._handle_investigate_discovery(parameters, state, target_id)

    async def _handle_investigate_discovery(
        self,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str]
    ) -> ActionResult:
        """
        Handle investigating a discovery.

        TODO: Extract logic from game_loop.py lines 2296-2450

        Steps:
        1. Get discovery name from parameters
        2. Find discovery in available_discoveries
        3. If not found, return error
        4. Generate investigation narrative via GM
        5. Extract knowledge acquisitions from narrative
        6. Add to pending_acquisitions
        7. Mark discovery as investigated in state
        8. Create and broadcast chat message
        9. Return result
        """
        # TODO: Implement
        discovery_name = parameters.get("discovery_name", target_id)
        logger.info("handling_investigate_discovery", discovery_name=discovery_name)

        return self._create_success_result(
            outcome={"discovery_investigated": True},
            narrative_generated=True
        )
