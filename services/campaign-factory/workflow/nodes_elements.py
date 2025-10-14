"""
Scene Element Generation Nodes
Phase 7: Generate NPCs, discoveries, events, challenges for scenes
"""
import os
import logging
import json
import uuid
from typing import List
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, NPCData, DiscoveryData, EventData, ChallengeData, KnowledgeData, ItemData
from .utils import add_audit_entry, publish_progress, create_checkpoint, get_blooms_level_description
from .subgraph_npc import create_npc_subgraph
from .objective_system import map_knowledge_to_scenes, map_items_to_scenes
from .rubric_engine import generate_rubric_for_interaction
from .rubric_templates import get_template_for_interaction
from .nodes_elements_helpers import _track_knowledge_from_spec, _track_items_from_spec, generate_knowledge_entities, generate_item_entities

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # API key read from ANTHROPIC_API_KEY env var
    temperature=0.8,
    max_tokens=4096
)

# Create NPC subgraph instance
npc_subgraph = create_npc_subgraph()


async def generate_scene_elements_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Generate all scene elements: NPCs, discoveries, events, challenges

    This node:
    1. For each scene, determines what elements are needed
    2. Generates NPCs using NPC subgraph (with species association)
    3. Generates discoveries that provide knowledge
    4. Generates events that create dynamic interactions
    5. Generates challenges that test player skills
    6. Links elements to scenes
    """
    try:
        state["current_node"] = "generate_scene_elements"
        state["current_phase"] = "element_gen"
        state["progress_percentage"] = 95
        state["status_message"] = "Generating scene elements (NPCs, discoveries, events, challenges)..."

        # Ensure state has all required list fields initialized
        if "rubrics" not in state or state["rubrics"] is None:
            state["rubrics"] = []
        if "new_species_ids" not in state or state["new_species_ids"] is None:
            state["new_species_ids"] = []
        if "errors" not in state or state["errors"] is None:
            state["errors"] = []

        await publish_progress(state)

        total_scenes = len(state['scenes'])
        logger.info(f"Generating elements for {total_scenes} scenes")

        all_npcs: List[NPCData] = []
        all_discoveries: List[DiscoveryData] = []
        all_events: List[EventData] = []
        all_challenges: List[ChallengeData] = []

        # NEW: Collect knowledge and items from all specs
        knowledge_tracker = {}  # knowledge_name -> {scenes, acquisition_methods, dimension}
        item_tracker = {}  # item_name -> {scenes, acquisition_methods}

        # Generate elements for each scene
        for scene_idx, scene in enumerate(state["scenes"]):
            # Ensure scene has all required list fields initialized (defensive programming)
            if "npc_ids" not in scene or scene["npc_ids"] is None:
                scene["npc_ids"] = []
            if "discovery_ids" not in scene or scene["discovery_ids"] is None:
                scene["discovery_ids"] = []
            if "event_ids" not in scene or scene["event_ids"] is None:
                scene["event_ids"] = []
            if "challenge_ids" not in scene or scene["challenge_ids"] is None:
                scene["challenge_ids"] = []

            # Update progress for each scene (95% to 98% range)
            scene_progress = 95 + int((scene_idx / total_scenes) * 3)  # 95% to 98%
            state["progress_percentage"] = scene_progress
            state["status_message"] = f"Generating elements for scene {scene_idx + 1} of {total_scenes}..."
            await publish_progress(state, f"Scene: {scene['name']}")

            logger.info(f"Generating elements for scene {scene_idx + 1}/{total_scenes}: {scene['name']}")

            # Step 1: Determine what elements this scene needs
            elements_needed = await determine_scene_elements(scene, state)

            # Step 2: Generate NPCs using subgraph
            for npc_role in elements_needed.get("npcs", []):
                npc_state = {
                    "npc_role": npc_role,
                    "narrative_context": scene["description"],
                    "location_name": scene["level_3_location_name"],
                    "level_3_location_id": scene["level_3_location_id"],
                    "world_id": state["world_id"],
                    "region_id": state["region_id"],
                    "region_name": state["region_name"],
                    "region_data": state.get("region_data", {}),  # Pass region inhabitants
                    "errors": [],
                    "rubrics": []  # Initialize rubrics list for subgraph
                }

                # Run NPC subgraph
                result_state = await npc_subgraph.ainvoke(npc_state)

                if "npc" in result_state:
                    npc = result_state["npc"]
                    all_npcs.append(npc)
                    npc_id = npc.get("npc_id", "")
                    scene["npc_ids"].append(npc_id)

                    # Track knowledge/items provided by this NPC
                    if isinstance(npc_role, dict):
                        _track_knowledge_from_spec(npc_role, npc_id, "npc_conversation", scene, knowledge_tracker)
                        _track_items_from_spec(npc_role, npc_id, "npc_conversation", scene, item_tracker)

                    # Add NPC rubric to main state if generated
                    if "npc_rubric" in result_state:
                        if "rubrics" not in state:
                            state["rubrics"] = []
                        state["rubrics"].append(result_state["npc_rubric"])
                        logger.info(f"Added rubric for NPC: {npc['name']}")

                    # Track new species if created
                    if result_state.get("new_species_created", False):
                        species_id = result_state.get("species_id", "")
                        if species_id not in state["new_species_ids"]:
                            state["new_species_ids"].append(species_id)

            # Step 3: Generate discoveries
            for discovery_spec in elements_needed.get("discoveries", []):
                discovery = await generate_discovery(discovery_spec, scene, state)
                all_discoveries.append(discovery)
                discovery_id = discovery.get("discovery_id", "")
                scene["discovery_ids"].append(discovery_id)

                # Track knowledge/items from discovery
                _track_knowledge_from_spec(discovery_spec, discovery_id, "environmental_discovery", scene, knowledge_tracker)
                _track_items_from_spec(discovery_spec, discovery_id, "environmental_discovery", scene, item_tracker)

            # Step 4: Generate events
            for event_spec in elements_needed.get("events", []):
                event = await generate_event(event_spec, scene, state)
                all_events.append(event)
                event_id = event.get("event_id", "")
                scene["event_ids"].append(event_id)

                # Track knowledge/items from event
                _track_knowledge_from_spec(event_spec, event_id, "dynamic_event", scene, knowledge_tracker)
                _track_items_from_spec(event_spec, event_id, "dynamic_event", scene, item_tracker)

            # Step 5: Generate challenges
            for challenge_spec in elements_needed.get("challenges", []):
                challenge = await generate_challenge(challenge_spec, scene, state)
                all_challenges.append(challenge)
                challenge_id = challenge.get("challenge_id", "")
                scene["challenge_ids"].append(challenge_id)

                # Track knowledge/items from challenge
                _track_knowledge_from_spec(challenge_spec, challenge_id, "challenge", scene, knowledge_tracker)
                _track_items_from_spec(challenge_spec, challenge_id, "challenge", scene, item_tracker)

        # Step 6: Generate Knowledge Entities from collected data
        logger.info(f"Generating knowledge entities from {len(knowledge_tracker)} unique knowledge items")
        all_knowledge_entities = await generate_knowledge_entities(knowledge_tracker, state)

        # Step 7: Generate Items from collected data
        logger.info(f"Generating items from {len(item_tracker)} unique items")
        all_items = await generate_item_entities(item_tracker, state)

        # Update state with all generated elements
        state["npcs"] = all_npcs
        state["discoveries"] = all_discoveries
        state["events"] = all_events
        state["challenges"] = all_challenges
        state["knowledge_entities"] = all_knowledge_entities
        state["item_entities"] = all_items

        # Create checkpoint after element generation
        create_checkpoint(state, "elements_generated")

        add_audit_entry(
            state,
            "generate_scene_elements",
            "Generated scene elements",
            {
                "num_npcs": len(all_npcs),
                "num_discoveries": len(all_discoveries),
                "num_events": len(all_events),
                "num_challenges": len(all_challenges),
                "num_knowledge_entities": len(all_knowledge_entities),
                "num_items": len(all_items),
                "new_species_created": len(state["new_species_ids"])
            },
            "success"
        )

        logger.info(f"Generated {len(all_npcs)} NPCs, {len(all_discoveries)} discoveries, "
                   f"{len(all_events)} events, {len(all_challenges)} challenges, "
                   f"{len(all_knowledge_entities)} knowledge entities, {len(all_items)} items")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error generating scene elements: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "generate_scene_elements",
            "Failed to generate scene elements",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


async def determine_scene_elements(scene: dict, state: CampaignWorkflowState) -> dict:
    """
    Use AI to determine what elements a scene needs.

    NEW (Phase 4):
    - Considers quest objectives and required knowledge/items
    - Targets specific dimensions for character balance
    - Creates multiple acquisition paths (redundancy)
    - Assigns knowledge/items to interactions
    """

    # Determine which knowledge/items should be available in this scene
    scene_knowledge = []
    scene_items = []

    # Get knowledge and items that should be in this scene (from objective mapping)
    for kg in state.get("knowledge_entities", []):
        # Simple check: if knowledge name appears in scene description or is generic
        # In a real system, this would use the mapping from objective_system
        scene_knowledge.append(kg)

    for item in state.get("item_entities", []):
        # Simple check: if item name appears in scene description or is generic
        scene_items.append(item)

    # Get character profile to determine which dimensions to target
    character_profile = state.get("character_profile")
    target_dimensions = []

    if character_profile:
        # Target the least developed dimensions
        target_dimensions = character_profile.get("recommended_focus", ["intellectual", "social"])
    else:
        # Default to balanced dimensions
        target_dimensions = ["intellectual", "social", "emotional"]

    # Format knowledge/items for prompt
    knowledge_str = "\n".join([
        f"- {kg.get('name', 'Unknown')} ({kg.get('knowledge_type', 'skill')}, {kg.get('primary_dimension', 'intellectual')})"
        for kg in scene_knowledge[:3]  # Limit to 3 for brevity
    ])

    items_str = "\n".join([
        f"- {item.get('name', 'Unknown')} ({item.get('item_type', 'tool')})"
        for item in scene_items[:3]  # Limit to 3 for brevity
    ])

    dimensions_str = ", ".join(target_dimensions)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a master scene designer for RPG games with expertise in educational design.

Your task is to determine what elements (NPCs, discoveries, events, challenges) a scene needs to:
1. Provide knowledge/items needed for quest objectives
2. Target specific developmental dimensions for character growth
3. Create multiple ways to acquire the same knowledge/items (REDUNDANCY)

DEVELOPMENTAL DIMENSIONS:
- Physical: Combat, endurance, precision, strength
- Emotional: Empathy, stress management, self-awareness
- Intellectual: Problem-solving, analysis, memory, logic
- Social: Communication, negotiation, leadership, teamwork
- Spiritual: Ethics, values, purpose, meaning
- Vocational: Craftsmanship, skill mastery, innovation
- Environmental: Ecology, resource management, sustainability

CHALLENGE TYPES BY DIMENSION:
- Physical: combat, obstacle_course, endurance_test, precision_task
- Intellectual: riddle, cipher, memory_game, strategy_game, mathematical_puzzle, lateral_thinking
- Social: negotiation, persuasion, deception_detection, team_coordination, leadership_test
- Emotional: stress_management, empathy_scenario, trauma_processing, temptation_resistance
- Spiritual: moral_dilemma, purpose_quest, value_conflict, sacrifice_decision
- Vocational: craft_mastery, professional_puzzle, skill_competition, innovation_challenge
- Environmental: ecosystem_management, resource_optimization, pollution_solution, wildlife_interaction

IMPORTANT: Create REDUNDANCY by providing 2-3 different ways to acquire the same knowledge/items.
For example:
- Knowledge about "Ancient Mining Techniques" could be acquired from:
  1. NPC conversation with an old miner
  2. Discovery of an ancient manual
  3. Challenge: solving a mining puzzle

Return your response as JSON:
{{
  "npcs": ["quest_giver", "merchant", "wise_elder"],
  "discoveries": [
    {{
      "type": "lore",
      "description": "Ancient text about...",
      "provides_knowledge": ["knowledge_name"],
      "provides_items": [],
      "dimension": "intellectual"
    }}
  ],
  "events": [
    {{
      "type": "scripted",
      "description": "Unexpected event...",
      "provides_knowledge": [],
      "provides_items": ["item_name"],
      "dimension": "emotional"
    }}
  ],
  "challenges": [
    {{
      "type": "riddle",
      "description": "Solve the ancient riddle...",
      "provides_knowledge": ["knowledge_name"],
      "provides_items": [],
      "dimension": "intellectual",
      "difficulty": "Medium"
    }}
  ]
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
        ("user", """Scene Context:
Name: {scene_name}
Description: {scene_description}
Location: {location}

Quest Objectives Supported by This Scene:
{objectives}

Knowledge Available in Campaign:
{knowledge}

Items Available in Campaign:
{items}

Target Dimensions for Character Growth:
{target_dimensions}

Campaign Target Bloom's Level: {blooms_level}

Determine what elements this scene needs. Remember to create REDUNDANCY (2-3 ways to get the same knowledge/items).""")
    ])

    # Format objectives (from parent quest)
    parent_quest = None
    for quest in state.get("quests", []):
        for place in state.get("places", []):
            if place.get("parent_quest_id") == quest.get("quest_id") and scene.get("parent_place_id") == place.get("place_id"):
                parent_quest = quest
                break
        if parent_quest:
            break

    objectives_str = ""
    if parent_quest:
        structured_objectives = parent_quest.get("structured_objectives", [])
        if structured_objectives:
            objectives_str = "\n".join([
                f"- {obj.get('description', 'Unnamed objective')}"
                for obj in structured_objectives[:2]  # Limit to 2 for brevity
            ])
        else:
            objectives_str = "\n".join([
                f"- {obj.get('description', 'Unnamed objective')}"
                for obj in parent_quest.get("objectives", [])[:2]
            ])

    if not objectives_str:
        objectives_str = "General exploration and discovery"

    chain = prompt | anthropic_client
    response = await chain.ainvoke({
        "scene_name": scene["name"],
        "scene_description": scene["description"],
        "location": scene["level_3_location_name"],
        "objectives": objectives_str,
        "knowledge": knowledge_str if knowledge_str else "No specific knowledge requirements",
        "items": items_str if items_str else "No specific item requirements",
        "target_dimensions": dimensions_str,
        "blooms_level": state["campaign_core"]["target_blooms_level"]
    })

    return json.loads(response.content.strip())


async def generate_discovery(spec: dict, scene: dict, state: CampaignWorkflowState) -> DiscoveryData:
    """Generate a discovery element with AI-enhanced details"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a master RPG designer creating discovery elements.

Generate a compelling name and enriched description for a discovery.

Return JSON:
{{
  "name": "Discovery name (3-5 words)",
  "full_description": "Enhanced description with sensory details and narrative context (2-3 sentences)"
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
        ("user", """Scene: {scene_name}
Scene Context: {scene_description}
Discovery Type: {discovery_type}
Discovery Base: {discovery_description}

Create a compelling discovery element.""")
    ])

    chain = prompt | anthropic_client
    response = await chain.ainvoke({
        "scene_name": scene["name"],
        "scene_description": scene["description"],
        "discovery_type": spec.get("type", "information"),
        "discovery_description": spec.get("description", "A piece of information")
    })

    enriched = json.loads(response.content.strip())

    # Generate discovery ID immediately
    discovery_id = f"discovery_{uuid.uuid4().hex[:16]}"

    # Generate rubric ID for this discovery
    rubric_id = f"rubric_discovery_{uuid.uuid4().hex[:8]}"

    discovery: DiscoveryData = {
        "discovery_id": discovery_id,
        "name": enriched.get("name", f"Discovery in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),
        "knowledge_type": spec.get("type", "information"),
        "blooms_level": state["campaign_core"]["target_blooms_level"],
        "unlocks_scenes": [],  # May be set based on narrative flow
        "provides_knowledge_ids": spec.get("provides_knowledge", []),
        "rubric_id": rubric_id
    }

    # Generate rubric for this discovery
    try:
        rubric = get_template_for_interaction(
            "environmental_discovery",
            spec.get("type", "information"),
            {"id": discovery_id, "name": discovery["name"], "discovery_type": spec.get("type", "information")}
        )

        # Only store rubric if it was successfully generated
        if rubric is not None:
            # Check for duplicate rubrics (by interaction_name + rubric_type)
            if "rubrics" not in state:
                state["rubrics"] = []

            # Create dedup key
            dedup_key = f"{rubric.get('rubric_type')}:{rubric.get('interaction_name')}"
            existing_keys = [
                f"{r.get('rubric_type')}:{r.get('interaction_name')}"
                for r in state["rubrics"]
            ]

            if dedup_key not in existing_keys:
                state["rubrics"].append(rubric)
                logger.info(f"Generated rubric for discovery: {discovery['name']}")
            else:
                logger.warning(f"Skipping duplicate rubric: {discovery['name']} (interaction already exists)")
        else:
            logger.warning(f"Rubric generation returned None for discovery: {discovery['name']}")

    except Exception as e:
        logger.error(f"Error generating rubric for discovery: {str(e)}")

    return discovery


async def generate_event(spec: dict, scene: dict, state: CampaignWorkflowState) -> EventData:
    """Generate an event element with AI-enhanced details"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a master RPG designer creating dynamic event elements.

Generate a compelling name and enriched description for an event.

Return JSON:
{{
  "name": "Event name (3-5 words)",
  "full_description": "Enhanced description with dramatic detail (2-3 sentences)",
  "outcomes": ["outcome1", "outcome2"]
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
        ("user", """Scene: {scene_name}
Scene Context: {scene_description}
Event Type: {event_type}
Event Base: {event_description}

Create a compelling event element.""")
    ])

    chain = prompt | anthropic_client
    response = await chain.ainvoke({
        "scene_name": scene["name"],
        "scene_description": scene["description"],
        "event_type": spec.get("type", "scripted"),
        "event_description": spec.get("description", "An event occurs")
    })

    enriched = json.loads(response.content.strip())

    # Generate event ID immediately
    event_id = f"event_{uuid.uuid4().hex[:16]}"

    # Generate rubric ID for this event
    rubric_id = f"rubric_event_{uuid.uuid4().hex[:8]}"

    event: EventData = {
        "event_id": event_id,
        "name": enriched.get("name", f"Event in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),
        "event_type": spec.get("type", "scripted"),
        "trigger_conditions": {},
        "outcomes": enriched.get("outcomes", []),
        "rubric_id": rubric_id
    }

    # Generate rubric for this event
    try:
        rubric = get_template_for_interaction(
            "dynamic_event",
            spec.get("type", "scripted"),
            {"id": event_id, "name": event["name"], "event_type": spec.get("type", "scripted")}
        )

        # Only store rubric if it was successfully generated
        if rubric is not None:
            # Check for duplicate rubrics (by interaction_name + rubric_type)
            if "rubrics" not in state:
                state["rubrics"] = []

            # Create dedup key
            dedup_key = f"{rubric.get('rubric_type')}:{rubric.get('interaction_name')}"
            existing_keys = [
                f"{r.get('rubric_type')}:{r.get('interaction_name')}"
                for r in state["rubrics"]
            ]

            if dedup_key not in existing_keys:
                state["rubrics"].append(rubric)
                logger.info(f"Generated rubric for event: {event['name']}")
            else:
                logger.warning(f"Skipping duplicate rubric: {event['name']} (interaction already exists)")
        else:
            logger.warning(f"Rubric generation returned None for event: {event['name']}")

    except Exception as e:
        logger.error(f"Error generating rubric for event: {str(e)}")

    return event


async def generate_challenge(spec: dict, scene: dict, state: CampaignWorkflowState) -> ChallengeData:
    """
    Generate a challenge element with AI-enhanced details.

    NEW (Phase 4):
    - Uses enhanced ChallengeData structure with dimensions
    - Generates rubric for challenge evaluation
    - Links knowledge/items that can be obtained
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a master RPG designer creating challenge elements.

Generate a compelling name and enriched description for a challenge.

Return JSON:
{{
  "name": "Challenge name (3-5 words)",
  "full_description": "Enhanced description with stakes and mechanics (2-3 sentences)",
  "success_rewards": {{"reward_type": "reward_description"}},
  "failure_consequences": {{"consequence_type": "consequence_description"}}
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
        ("user", """Scene: {scene_name}
Scene Context: {scene_description}
Challenge Type: {challenge_type}
Challenge Base: {challenge_description}
Difficulty: {difficulty}

Create a compelling challenge element.""")
    ])

    chain = prompt | anthropic_client
    response = await chain.ainvoke({
        "scene_name": scene["name"],
        "scene_description": scene["description"],
        "challenge_type": spec.get("type", "skill_check"),
        "challenge_description": spec.get("description", "A challenge to overcome"),
        "difficulty": state["quest_difficulty"]
    })

    enriched = json.loads(response.content.strip())

    # Map challenge type to category and dimension
    challenge_type = spec.get("type", "skill_check")
    challenge_category, primary_dimension, secondary_dimensions = _map_challenge_to_dimensions(challenge_type)

    # Generate challenge ID immediately
    challenge_id = f"challenge_{uuid.uuid4().hex[:16]}"

    # Generate rubric ID
    rubric_id = f"rubric_challenge_{uuid.uuid4().hex[:8]}"

    # Enhanced ChallengeData with all new fields
    challenge: ChallengeData = {
        "challenge_id": challenge_id,
        "name": enriched.get("name", f"Challenge in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),

        # Challenge classification
        "challenge_type": challenge_type,
        "challenge_category": challenge_category,
        "primary_dimension": primary_dimension,
        "secondary_dimensions": secondary_dimensions,

        # Difficulty and requirements
        "difficulty": spec.get("difficulty", state["quest_difficulty"]),
        "blooms_level": state["campaign_core"]["target_blooms_level"],
        "required_knowledge": [],  # TODO: Link to knowledge requirements from spec
        "required_items": [],  # TODO: Link to item requirements from spec

        # Rewards system
        "provides_knowledge_ids": spec.get("provides_knowledge", []),
        "provides_item_ids": spec.get("provides_items", []),
        "rubric_id": rubric_id,

        # Legacy support
        "success_rewards": enriched.get("success_rewards", {}),
        "failure_consequences": enriched.get("failure_consequences", {})
    }

    # Generate rubric for this challenge
    try:
        rubric = get_template_for_interaction(
            "challenge",
            challenge_type,
            {"id": challenge_id, "name": challenge["name"], "difficulty": challenge["difficulty"]}
        )

        # Only store rubric if it was successfully generated
        if rubric is not None:
            # Check for duplicate rubrics (by interaction_name + rubric_type)
            if "rubrics" not in state:
                state["rubrics"] = []

            # Create dedup key
            dedup_key = f"{rubric.get('rubric_type')}:{rubric.get('interaction_name')}"
            existing_keys = [
                f"{r.get('rubric_type')}:{r.get('interaction_name')}"
                for r in state["rubrics"]
            ]

            if dedup_key not in existing_keys:
                state["rubrics"].append(rubric)
                logger.info(f"Generated rubric for challenge: {challenge['name']}")
            else:
                logger.warning(f"Skipping duplicate rubric: {challenge['name']} (interaction already exists)")
        else:
            logger.warning(f"Rubric generation returned None for challenge: {challenge['name']}")

    except Exception as e:
        logger.error(f"Error generating rubric for challenge: {str(e)}")

    return challenge


def _map_challenge_to_dimensions(challenge_type: str) -> tuple:
    """
    Map challenge type to category, primary dimension, and secondary dimensions.

    Returns:
        Tuple of (category, primary_dimension, secondary_dimensions)
    """
    # Mental (Intellectual)
    mental_challenges = ["riddle", "cipher", "memory_game", "strategy_game", "mathematical_puzzle", "lateral_thinking"]
    # Physical
    physical_challenges = ["combat", "obstacle_course", "endurance_test", "precision_task", "reflex_challenge", "strength_test"]
    # Social
    social_challenges = ["negotiation", "persuasion", "deception_detection", "team_coordination", "leadership_test", "cultural_navigation"]
    # Emotional
    emotional_challenges = ["stress_management", "empathy_scenario", "trauma_processing", "temptation_resistance", "fear_confrontation", "relationship_repair"]
    # Spiritual
    spiritual_challenges = ["moral_dilemma", "purpose_quest", "value_conflict", "sacrifice_decision", "forgiveness_scenario", "faith_test"]
    # Vocational
    vocational_challenges = ["craft_mastery", "professional_puzzle", "skill_competition", "innovation_challenge", "apprenticeship_test", "quality_control"]
    # Environmental
    environmental_challenges = ["ecosystem_management", "resource_optimization", "pollution_solution", "wildlife_interaction", "climate_adaptation", "conservation_decision"]

    if challenge_type in mental_challenges:
        return "mental", "intellectual", []
    elif challenge_type in physical_challenges:
        if challenge_type == "combat":
            return "physical", "physical", ["intellectual", "emotional", "social"]
        return "physical", "physical", []
    elif challenge_type in social_challenges:
        return "social", "social", ["emotional"]
    elif challenge_type in emotional_challenges:
        return "emotional", "emotional", ["social"]
    elif challenge_type in spiritual_challenges:
        return "spiritual", "spiritual", ["emotional", "social"]
    elif challenge_type in vocational_challenges:
        return "vocational", "vocational", ["physical", "intellectual"]
    elif challenge_type in environmental_challenges:
        return "environmental", "environmental", ["intellectual"]
    else:
        # Default for unknown types
        return "general", "intellectual", []
