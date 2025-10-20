"""
Helper functions for knowledge and item generation
Extracted to separate file for better organization
"""
import uuid
import logging
import json
from datetime import datetime
from typing import Dict, Any, List
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import KnowledgeData, ItemData, AcquisitionMethod, KnowledgePartialLevel

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0.7,
    max_tokens=4096
)


def _normalize_name(name: str) -> str:
    """
    Normalize knowledge/item names to prevent duplicates with different formatting.

    Examples:
        "Syndicate surveillance methods" -> "syndicate_surveillance_methods"
        "surveillance_detection" -> "surveillance_detection"
        "Formation Markers" -> "formation_markers"
        "formation_markers" -> "formation_markers"

    Returns:
        Normalized name (lowercase with underscores)
    """
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _format_friendly_name(name: str) -> str:
    """
    Convert snake_case/camelCase names to friendly Title Case display names.

    Examples:
        "settlement_geography" -> "Settlement Geography"
        "observation_journal" -> "Observation Journal"
        "Formation Markers" -> "Formation Markers"
        "ancient_rune_reading" -> "Ancient Rune Reading"
        "NPCDiplomacy" -> "NPC Diplomacy"

    Returns:
        Friendly formatted name
    """
    if not name:
        return name

    # If name has spaces and mixed case, assume it's already formatted
    if " " in name and any(c.isupper() for c in name):
        return name.strip()

    # Replace underscores and hyphens with spaces
    name = name.replace("_", " ").replace("-", " ")

    # Split camelCase (e.g., "NPCDiplomacy" -> "NPC Diplomacy")
    import re
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name)

    # Title case each word
    return name.title().strip()


def _track_knowledge_from_spec(spec: dict, entity_id: str, interaction_type: str, scene: dict, knowledge_tracker: dict):
    """
    Track knowledge from a spec (NPC, discovery, event, challenge) using IDs.

    Args:
        spec: The specification dict with provides_knowledge_ids
        entity_id: ID of the entity providing the knowledge
        interaction_type: Type of interaction (npc_conversation, environmental_discovery, etc.)
        scene: Scene dict where this knowledge is available
        knowledge_tracker: Dict to track all knowledge by ID
    """
    # Use ID-based field instead of name-based
    knowledge_ids = spec.get("provides_knowledge_ids", [])
    dimension = spec.get("dimension", "intellectual")
    difficulty = spec.get("difficulty", "Medium")

    for knowledge_id in knowledge_ids:
        if not knowledge_id or knowledge_id.strip() == "":
            continue

        # Track by ID - no normalization needed!
        # Initialize tracker for this knowledge if not exists
        if knowledge_id not in knowledge_tracker:
            knowledge_tracker[knowledge_id] = {
                "scenes": [],
                "acquisition_methods": [],
                "dimension": dimension
            }

        # Add scene if not already added
        scene_id = scene.get("scene_id", "")
        if scene_id and scene_id not in knowledge_tracker[knowledge_id]["scenes"]:
            knowledge_tracker[knowledge_id]["scenes"].append(scene_id)

        # Add acquisition method
        acquisition_method = {
            "type": interaction_type,
            "entity_id": entity_id,
            "difficulty": difficulty,
            "max_level_obtainable": 4,  # Full mastery through this method
            "rubric_id": f"rubric_{entity_id}",  # Will be linked to actual rubric
            "conditions": {}
        }

        knowledge_tracker[knowledge_id]["acquisition_methods"].append(acquisition_method)


def _track_items_from_spec(spec: dict, entity_id: str, interaction_type: str, scene: dict, item_tracker: dict):
    """
    Track items from a spec (NPC, discovery, event, challenge) using IDs.

    Args:
        spec: The specification dict with provides_item_ids
        entity_id: ID of the entity providing the item
        interaction_type: Type of interaction
        scene: Scene dict where this item is available
        item_tracker: Dict to track all items by ID
    """
    # Use ID-based field instead of name-based
    item_ids = spec.get("provides_item_ids", [])
    difficulty = spec.get("difficulty", "Medium")

    for item_id in item_ids:
        if not item_id or item_id.strip() == "":
            continue

        # Track by ID - no normalization needed!
        # Initialize tracker for this item if not exists
        if item_id not in item_tracker:
            item_tracker[item_id] = {
                "scenes": [],
                "acquisition_methods": []
            }

        # Add scene if not already added
        scene_id = scene.get("scene_id", "")
        if scene_id and scene_id not in item_tracker[item_id]["scenes"]:
            item_tracker[item_id]["scenes"].append(scene_id)

        # Add acquisition method
        acquisition_method = {
            "type": interaction_type,
            "entity_id": entity_id,
            "difficulty": difficulty,
            "max_level_obtainable": 1,  # Binary for items (have or don't have)
            "rubric_id": f"rubric_{entity_id}",
            "conditions": {}
        }

        item_tracker[item_id]["acquisition_methods"].append(acquisition_method)


async def generate_knowledge_entities(knowledge_tracker: dict, state: dict) -> List[KnowledgeData]:
    """
    Generate full KnowledgeData entities from tracked knowledge.

    Args:
        knowledge_tracker: Dict of knowledge_name -> {scenes, acquisition_methods, dimension}
        state: Campaign workflow state

    Returns:
        List of KnowledgeData entities
    """
    knowledge_entities = []

    for normalized_name, tracker_data in knowledge_tracker.items():
        try:
            # Use display_name (original formatting) for user-facing content
            display_name = tracker_data.get("display_name", normalized_name)

            # Generate knowledge ID
            knowledge_id = f"knowledge_{uuid.uuid4().hex[:16]}"

            # Use AI to generate detailed description and type
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an educational RPG designer creating knowledge entities.

Generate detailed information for a knowledge entity.

Return JSON:
{{
  "description": "Detailed description of what this knowledge represents (2-3 sentences)",
  "knowledge_type": "skill, lore, clue, secret, technique, or insight"
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
                ("user", """Knowledge Name: {knowledge_name}
Dimension: {dimension}
Campaign Context: {campaign_plot}
Bloom's Level: {blooms_level}

Generate detailed knowledge information.""")
            ])

            chain = prompt | anthropic_client
            response = await chain.ainvoke({
                "knowledge_name": display_name,
                "dimension": tracker_data["dimension"],
                "campaign_plot": state.get("campaign_core", {}).get("plot", "")[:200],
                "blooms_level": state.get("campaign_core", {}).get("target_blooms_level", 3)
            })

            enriched = json.loads(response.content.strip())

            # Generate 4 partial levels (25%, 50%, 75%, 100%)
            partial_levels: List[KnowledgePartialLevel] = [
                {
                    "level": 1,
                    "description": f"Basic understanding of {display_name}",
                    "sufficient_for": []
                },
                {
                    "level": 2,
                    "description": f"Intermediate knowledge of {display_name}",
                    "sufficient_for": []
                },
                {
                    "level": 3,
                    "description": f"Advanced mastery of {display_name}",
                    "sufficient_for": []
                },
                {
                    "level": 4,
                    "description": f"Complete mastery of {display_name}",
                    "sufficient_for": []
                }
            ]

            # Use first scene where this knowledge appears
            scene_id = tracker_data["scenes"][0] if tracker_data["scenes"] else None

            # Create KnowledgeData
            knowledge: KnowledgeData = {
                "knowledge_id": knowledge_id,
                "name": display_name,  # Use display_name for consistency
                "description": enriched.get("description", f"Knowledge about {display_name}"),
                "knowledge_type": enriched.get("knowledge_type", "skill"),
                "primary_dimension": tracker_data["dimension"],
                "bloom_level_target": state.get("campaign_core", {}).get("target_blooms_level", 3),
                "supports_objectives": [],  # TODO: Link to objectives
                "partial_levels": partial_levels,
                "acquisition_methods": tracker_data["acquisition_methods"],
                "created_at": datetime.utcnow().isoformat(),
                "scene_id": scene_id
            }

            knowledge_entities.append(knowledge)
            logger.info(f"Generated knowledge entity: {display_name} (ID: {knowledge_id})")

        except Exception as e:
            logger.error(f"Error generating knowledge entity for '{normalized_name}': {e}")
            # Continue with next knowledge

    return knowledge_entities


async def generate_item_entities(item_tracker: dict, state: dict) -> List[ItemData]:
    """
    Generate full ItemData entities from tracked items.

    Args:
        item_tracker: Dict of item_name -> {scenes, acquisition_methods}
        state: Campaign workflow state

    Returns:
        List of ItemData entities
    """
    item_entities = []

    for normalized_name, tracker_data in item_tracker.items():
        try:
            # Use display_name (original formatting) for user-facing content
            display_name = tracker_data.get("display_name", normalized_name)

            # Generate item ID
            item_id = f"item_{uuid.uuid4().hex[:16]}"

            # Use AI to generate detailed description and type
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an RPG designer creating item entities.

Generate detailed information for an item.

Return JSON:
{{
  "description": "Detailed description of the item (2-3 sentences)",
  "item_type": "tool, consumable, key_item, quest_item, equipment, or resource",
  "is_quest_critical": true or false
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
                ("user", """Item Name: {item_name}
Campaign Context: {campaign_plot}

Generate detailed item information.""")
            ])

            chain = prompt | anthropic_client
            response = await chain.ainvoke({
                "item_name": display_name,
                "campaign_plot": state.get("campaign_core", {}).get("plot", "")[:200]
            })

            enriched = json.loads(response.content.strip())

            # Use first scene where this item appears
            scene_id = tracker_data["scenes"][0] if tracker_data["scenes"] else None

            # Create ItemData
            item: ItemData = {
                "item_id": item_id,
                "name": display_name,  # Use display_name for consistency
                "description": enriched.get("description", f"A useful item: {display_name}"),
                "item_type": enriched.get("item_type", "tool"),
                "supports_objectives": [],  # TODO: Link to objectives
                "acquisition_methods": tracker_data["acquisition_methods"],
                "quantity": 1,
                "is_consumable": enriched.get("item_type") == "consumable",
                "is_quest_critical": enriched.get("is_quest_critical", False),
                "created_at": datetime.utcnow().isoformat(),
                "scene_id": scene_id
            }

            item_entities.append(item)
            logger.info(f"Generated item entity: {display_name} (ID: {item_id})")

        except Exception as e:
            logger.error(f"Error generating item entity for '{normalized_name}': {e}")
            # Continue with next item

    return item_entities
