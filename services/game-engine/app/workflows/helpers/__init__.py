"""
Helper Functions Package

Provides reusable helper functions for the game loop:
- persistence: Database persistence functions
- progress: Progress tracking and calculation
- formatting: Display formatting and utilities
"""

from .persistence import (
    persist_encounter,
    persist_knowledge_acquisition,
    persist_item_acquisition
)

from .progress import (
    get_quest_progress_for_acquisition,
    calculate_complete_quest_progress,
    create_encounter_metadata
)

from .formatting import (
    format_player_input_for_display,
    detect_acquirable_opportunities
)

__all__ = [
    # Persistence
    "persist_encounter",
    "persist_knowledge_acquisition",
    "persist_item_acquisition",

    # Progress tracking
    "get_quest_progress_for_acquisition",
    "calculate_complete_quest_progress",
    "create_encounter_metadata",

    # Formatting
    "format_player_input_for_display",
    "detect_acquirable_opportunities",
]
