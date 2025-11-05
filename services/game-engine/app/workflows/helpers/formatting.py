"""
Formatting Helpers

Handles display formatting and opportunity detection.

Extract from game_loop.py lines 406-570
"""

from typing import Dict, Any, List


async def format_player_input_for_display(
    player_input: str,
    action_interpretation: Dict[str, Any],
    state: Dict[str, Any]
) -> str:
    """
    Format player input for display with friendly names.

    TODO: Extract from game_loop.py lines 406-472

    Args:
        player_input: Raw player input
        action_interpretation: Interpreted action
        state: Game session state

    Returns:
        Formatted display string
    """
    # TODO: Implement - extract from game_loop.py:406-472
    return player_input


async def detect_acquirable_opportunities(
    narrative_text: str,
    state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Detect acquirable opportunities in narrative text.

    TODO: Extract from game_loop.py lines 474-570

    Args:
        narrative_text: Narrative text to analyze
        state: Game session state

    Returns:
        List of detected opportunities
    """
    # TODO: Implement - extract from game_loop.py:474-570
    return []
