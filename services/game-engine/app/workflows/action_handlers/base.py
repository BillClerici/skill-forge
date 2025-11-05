"""
Base Action Handler

Defines the interface that all action handlers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ActionResult:
    """
    Result of an action execution.

    Attributes:
        success: Whether the action succeeded
        outcome: Dictionary containing action-specific results
        requires_assessment: Whether GM should assess this action
        narrative_generated: Whether narrative was added to chat
        error_message: Optional error message if action failed
    """
    success: bool
    outcome: Dict[str, Any]
    requires_assessment: bool = False
    narrative_generated: bool = False
    error_message: Optional[str] = None


class ActionHandler(ABC):
    """
    Base class for all action handlers.

    Each action handler is responsible for:
    1. Validating the action can be performed
    2. Executing the action logic
    3. Generating appropriate narrative
    4. Updating game state
    5. Returning structured results
    """

    @abstractmethod
    async def can_handle(self, action_type: str, state: Dict[str, Any]) -> bool:
        """
        Check if this handler can process the given action type.

        Args:
            action_type: The type of action to handle
            state: Current game session state

        Returns:
            True if this handler can process this action
        """
        pass

    @abstractmethod
    async def execute(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any],
        target_id: Optional[str] = None
    ) -> ActionResult:
        """
        Execute the action.

        Args:
            action_type: The specific action being performed
            parameters: Action-specific parameters
            state: Current game session state
            target_id: Optional target identifier

        Returns:
            ActionResult containing execution results
        """
        pass

    async def validate_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that the action can be performed in the current state.

        Args:
            action_type: The action type
            parameters: Action parameters
            state: Current game state

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation - can be overridden
        return True, None

    def _create_error_result(self, error_message: str) -> ActionResult:
        """Helper to create an error result."""
        return ActionResult(
            success=False,
            outcome={"error": error_message},
            error_message=error_message
        )

    def _create_success_result(
        self,
        outcome: Dict[str, Any],
        requires_assessment: bool = False,
        narrative_generated: bool = False
    ) -> ActionResult:
        """Helper to create a success result."""
        return ActionResult(
            success=True,
            outcome=outcome,
            requires_assessment=requires_assessment,
            narrative_generated=narrative_generated
        )
