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

from .state import CampaignWorkflowState, NPCData, DiscoveryData, EventData, ChallengeData
from .utils import add_audit_entry, publish_progress, create_checkpoint, get_blooms_level_description
from .subgraph_npc import create_npc_subgraph

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

        await publish_progress(state)

        total_scenes = len(state['scenes'])
        logger.info(f"Generating elements for {total_scenes} scenes")

        all_npcs: List[NPCData] = []
        all_discoveries: List[DiscoveryData] = []
        all_events: List[EventData] = []
        all_challenges: List[ChallengeData] = []

        # Generate elements for each scene
        for scene_idx, scene in enumerate(state["scenes"]):
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
                    "errors": []
                }

                # Run NPC subgraph
                result_state = await npc_subgraph.ainvoke(npc_state)

                if "npc" in result_state:
                    npc = result_state["npc"]
                    all_npcs.append(npc)
                    scene["npc_ids"].append(npc.get("npc_id", ""))

                    # Track new species if created
                    if result_state.get("new_species_created", False):
                        species_id = result_state.get("species_id", "")
                        if species_id not in state["new_species_ids"]:
                            state["new_species_ids"].append(species_id)

            # Step 3: Generate discoveries
            for discovery_spec in elements_needed.get("discoveries", []):
                discovery = await generate_discovery(discovery_spec, scene, state)
                all_discoveries.append(discovery)
                scene["discovery_ids"].append(discovery.get("discovery_id", ""))

            # Step 4: Generate events
            for event_spec in elements_needed.get("events", []):
                event = await generate_event(event_spec, scene, state)
                all_events.append(event)
                scene["event_ids"].append(event.get("event_id", ""))

            # Step 5: Generate challenges
            for challenge_spec in elements_needed.get("challenges", []):
                challenge = await generate_challenge(challenge_spec, scene, state)
                all_challenges.append(challenge)
                scene["challenge_ids"].append(challenge.get("challenge_id", ""))

        # Update state with all generated elements
        state["npcs"] = all_npcs
        state["discoveries"] = all_discoveries
        state["events"] = all_events
        state["challenges"] = all_challenges

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
                "new_species_created": len(state["new_species_ids"])
            },
            "success"
        )

        logger.info(f"Generated {len(all_npcs)} NPCs, {len(all_discoveries)} discoveries, "
                   f"{len(all_events)} events, {len(all_challenges)} challenges")

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
    Use AI to determine what elements a scene needs
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a master scene designer for RPG games.

Your task is to determine what elements (NPCs, discoveries, events, challenges) a scene needs.

Consider:
- What NPCs would naturally be in this location?
- What knowledge or secrets could be discovered?
- What events might occur during the scene?
- What challenges or obstacles exist?

Return your response as JSON:
{{
  "npcs": ["quest_giver", "merchant", "enemy"],
  "discoveries": [
    {{"type": "lore", "description": "Ancient text about..."}},
    {{"type": "clue", "description": "Evidence of..."}}
  ],
  "events": [
    {{"type": "scripted", "description": "Guards arrive and..."}}
  ],
  "challenges": [
    {{"type": "combat", "description": "Fight with..."}},
    {{"type": "puzzle", "description": "Solve the..."}}
  ]
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
        ("user", """Scene Context:
Name: {scene_name}
Description: {scene_description}
Location: {location}

Campaign Target Bloom's Level: {blooms_level}

Determine what elements this scene needs.""")
    ])

    chain = prompt | anthropic_client
    response = await chain.ainvoke({
        "scene_name": scene["name"],
        "scene_description": scene["description"],
        "location": scene["level_3_location_name"],
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

    discovery: DiscoveryData = {
        "discovery_id": None,  # Will be set on persistence
        "name": enriched.get("name", f"Discovery in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),
        "knowledge_type": spec.get("type", "information"),
        "blooms_level": state["campaign_core"]["target_blooms_level"],
        "unlocks_scenes": []  # May be set based on narrative flow
    }
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

    event: EventData = {
        "event_id": None,  # Will be set on persistence
        "name": enriched.get("name", f"Event in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),
        "event_type": spec.get("type", "scripted"),
        "trigger_conditions": {},
        "outcomes": enriched.get("outcomes", [])
    }
    return event


async def generate_challenge(spec: dict, scene: dict, state: CampaignWorkflowState) -> ChallengeData:
    """Generate a challenge element with AI-enhanced details"""
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

    challenge: ChallengeData = {
        "challenge_id": None,  # Will be set on persistence
        "name": enriched.get("name", f"Challenge in {scene['name']}"),
        "description": enriched.get("full_description", spec.get("description", "")),
        "challenge_type": spec.get("type", "skill_check"),
        "difficulty": state["quest_difficulty"],
        "blooms_level": state["campaign_core"]["target_blooms_level"],
        "success_rewards": enriched.get("success_rewards", {}),
        "failure_consequences": enriched.get("failure_consequences", {})
    }
    return challenge
