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


def _track_knowledge_from_spec(spec: dict, entity_id: str, interaction_type: str, scene: dict, knowledge_tracker: dict):
    """
    Track knowledge from a spec (NPC, discovery, event, challenge).

    Args:
        spec: The specification dict with provides_knowledge
        entity_id: ID of the entity providing the knowledge
        interaction_type: Type of interaction (npc_conversation, environmental_discovery, etc.)
        scene: Scene dict where this knowledge is available
        knowledge_tracker: Dict to track all knowledge
    """
    knowledge_names = spec.get("provides_knowledge", [])
    dimension = spec.get("dimension", "intellectual")
    difficulty = spec.get("difficulty", "Medium")

    for knowledge_name in knowledge_names:
        if not knowledge_name or knowledge_name.strip() == "":
            continue

        # Initialize tracker for this knowledge if not exists
        if knowledge_name not in knowledge_tracker:
            knowledge_tracker[knowledge_name] = {
                "scenes": [],
                "acquisition_methods": [],
                "dimension": dimension
            }

        # Add scene if not already added
        scene_id = scene.get("scene_id", "")
        if scene_id and scene_id not in knowledge_tracker[knowledge_name]["scenes"]:
            knowledge_tracker[knowledge_name]["scenes"].append(scene_id)

        # Add acquisition method
        acquisition_method = {
            "type": interaction_type,
            "entity_id": entity_id,
            "difficulty": difficulty,
            "max_level_obtainable": 4,  # Full mastery through this method
            "rubric_id": f"rubric_{entity_id}",  # Will be linked to actual rubric
            "conditions": {}
        }

        knowledge_tracker[knowledge_name]["acquisition_methods"].append(acquisition_method)


def _track_items_from_spec(spec: dict, entity_id: str, interaction_type: str, scene: dict, item_tracker: dict):
    """
    Track items from a spec (NPC, discovery, event, challenge).

    Args:
        spec: The specification dict with provides_items
        entity_id: ID of the entity providing the item
        interaction_type: Type of interaction
        scene: Scene dict where this item is available
        item_tracker: Dict to track all items
    """
    item_names = spec.get("provides_items", [])
    difficulty = spec.get("difficulty", "Medium")

    for item_name in item_names:
        if not item_name or item_name.strip() == "":
            continue

        # Initialize tracker for this item if not exists
        if item_name not in item_tracker:
            item_tracker[item_name] = {
                "scenes": [],
                "acquisition_methods": []
            }

        # Add scene if not already added
        scene_id = scene.get("scene_id", "")
        if scene_id and scene_id not in item_tracker[item_name]["scenes"]:
            item_tracker[item_name]["scenes"].append(scene_id)

        # Add acquisition method
        acquisition_method = {
            "type": interaction_type,
            "entity_id": entity_id,
            "difficulty": difficulty,
            "max_level_obtainable": 1,  # Binary for items (have or don't have)
            "rubric_id": f"rubric_{entity_id}",
            "conditions": {}
        }

        item_tracker[item_name]["acquisition_methods"].append(acquisition_method)


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

    for knowledge_name, tracker_data in knowledge_tracker.items():
        try:
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
                "knowledge_name": knowledge_name,
                "dimension": tracker_data["dimension"],
                "campaign_plot": state.get("campaign_core", {}).get("plot", "")[:200],
                "blooms_level": state.get("campaign_core", {}).get("target_blooms_level", 3)
            })

            enriched = json.loads(response.content.strip())

            # Generate 4 partial levels (25%, 50%, 75%, 100%)
            partial_levels: List[KnowledgePartialLevel] = [
                {
                    "level": 1,
                    "description": f"Basic understanding of {knowledge_name}",
                    "sufficient_for": []
                },
                {
                    "level": 2,
                    "description": f"Intermediate knowledge of {knowledge_name}",
                    "sufficient_for": []
                },
                {
                    "level": 3,
                    "description": f"Advanced mastery of {knowledge_name}",
                    "sufficient_for": []
                },
                {
                    "level": 4,
                    "description": f"Complete mastery of {knowledge_name}",
                    "sufficient_for": []
                }
            ]

            # Use first scene where this knowledge appears
            scene_id = tracker_data["scenes"][0] if tracker_data["scenes"] else None

            # Create KnowledgeData
            knowledge: KnowledgeData = {
                "knowledge_id": knowledge_id,
                "name": knowledge_name,
                "description": enriched.get("description", f"Knowledge about {knowledge_name}"),
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
            logger.info(f"Generated knowledge entity: {knowledge_name} (ID: {knowledge_id})")

        except Exception as e:
            logger.error(f"Error generating knowledge entity for '{knowledge_name}': {e}")
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

    for item_name, tracker_data in item_tracker.items():
        try:
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
                "item_name": item_name,
                "campaign_plot": state.get("campaign_core", {}).get("plot", "")[:200]
            })

            enriched = json.loads(response.content.strip())

            # Use first scene where this item appears
            scene_id = tracker_data["scenes"][0] if tracker_data["scenes"] else None

            # Create ItemData
            item: ItemData = {
                "item_id": item_id,
                "name": item_name,
                "description": enriched.get("description", f"A useful item: {item_name}"),
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
            logger.info(f"Generated item entity: {item_name} (ID: {item_id})")

        except Exception as e:
            logger.error(f"Error generating item entity for '{item_name}': {e}")
            # Continue with next item

    return item_entities
