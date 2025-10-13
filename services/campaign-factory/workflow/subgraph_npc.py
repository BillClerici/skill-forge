"""
NPC Generation Subgraph
Reusable subgraph for generating NPCs with species association
"""
import os
import logging
import json
import uuid
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate

from .state import CampaignWorkflowState, NPCData
from .utils import add_audit_entry

logger = logging.getLogger(__name__)

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    # API key read from ANTHROPIC_API_KEY env var
    temperature=0.8,
    max_tokens=4096
)


async def evaluate_existing_species_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate if existing world species fit the NPC requirements

    This node:
    1. Fetches available species for the world
    2. Uses AI to evaluate if existing species are appropriate
    3. Decides whether to use existing or create new species
    """
    try:
        logger.info(f"Evaluating existing species for NPC: {state.get('npc_role', 'unknown role')}")

        # Fetch world species via MCP
        from .mcp_client import fetch_world_species
        world_species = await fetch_world_species(state.get("world_id", ""))

        if not world_species:
            logger.warning(f"No existing species found for world {state.get('world_id')}")
            # Fallback to basic species if world has none yet
            world_species = [
                {"id": "species_human_default", "name": "Human", "description": "Standard human species"},
                {"id": "species_elf_default", "name": "Elf", "description": "Graceful forest-dwelling species"},
            ]

        # Prioritize species from region inhabitants
        region_data = state.get("region_data", {})
        region_inhabitants = region_data.get("inhabitants", [])

        # Separate species into region inhabitants and others
        region_species = []
        other_species = []

        for sp in world_species:
            # Check if species name or ID is in region inhabitants
            if any(inhabitant.lower() in sp['name'].lower() or
                   inhabitant.lower() in str(sp.get('id', '')).lower()
                   for inhabitant in region_inhabitants):
                region_species.append(sp)
            else:
                other_species.append(sp)

        logger.info(f"Found {len(region_species)} species native to region '{state.get('region_name', 'unknown')}'")

        # Create evaluation prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert in narrative consistency and world-building.

Your task is to evaluate if existing species are appropriate for an NPC role.

CRITICAL: Strongly prefer species that are known inhabitants of the region. Only choose non-native species if there's a compelling narrative reason (e.g., traveler, invader, refugee).

Consider:
- Does the species fit the narrative context?
- Does it make sense for this species to have this role?
- Is this species native to the region?
- Would using an existing species maintain world consistency?

Return your response as JSON:
{{
  "use_existing": true,
  "species_id": "species1",
  "species_name": "Human",
  "reasoning": "Explanation of why this species is appropriate (mention if native to region)",
  "or_create_new": false,
  "new_species_suggestion": {{
    "name": "",
    "description": ""
  }}
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """NPC Context:
Role: {role}
Narrative Context: {context}
Location: {location}
Region: {region}

SPECIES NATIVE TO THIS REGION (strongly prefer these):
{native_species}

Other Species in World:
{other_species}

Evaluate species appropriateness. Strongly prefer region-native species unless narrative requires otherwise.""")
        ])

        # Format species lists
        native_species_str = "\n".join([
            f"- {sp['name']}: {sp['description']} [ID: {sp['id']}] ⭐ NATIVE TO REGION"
            for sp in region_species
        ]) if region_species else "No species specifically marked as native to this region"

        other_species_str = "\n".join([
            f"- {sp['name']}: {sp['description']} [ID: {sp['id']}]"
            for sp in other_species
        ]) if other_species else "No other species available"

        # Evaluate
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "role": state.get("npc_role", "Unknown"),
            "context": state.get("narrative_context", ""),
            "location": state.get("location_name", ""),
            "region": state.get("region_name", "Unknown Region"),
            "native_species": native_species_str,
            "other_species": other_species_str
        })

        # Parse response with error handling
        try:
            evaluation = json.loads(response.content.strip())
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON parsing failed for species evaluation: {json_err}")
            logger.error(f"Raw response: {response.content[:500]}")
            # Use fallback with default species (Human)
            logger.warning("Using fallback: defaulting to Human species")
            evaluation = {
                "use_existing": True,
                "species_id": "species1",
                "species_name": "Human",
                "reasoning": "Defaulted due to JSON parsing error",
                "or_create_new": False
            }

        state["species_evaluation"] = evaluation

        logger.info(f"Species evaluation: use_existing={evaluation.get('use_existing', False)}")

    except Exception as e:
        logger.error(f"Error evaluating species: {e}")
        state["errors"] = state.get("errors", []) + [str(e)]

    return state


async def create_new_species_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create new species for the world (if evaluation suggests it)

    This node:
    1. Takes species suggestion from evaluation
    2. Generates full species details
    3. Creates species in world via orchestrator
    4. Adds to world permanently (enriches world)
    """
    try:
        evaluation = state.get("species_evaluation", {})

        if not evaluation.get("or_create_new", False):
            logger.info("Skipping species creation - using existing")
            return state

        logger.info("Creating new species for world")

        suggestion = evaluation.get("new_species_suggestion", {})

        # TODO: Call orchestrator to create full species via game-master
        # For now, generate placeholder ID
        new_species_id = f"new_species_{uuid.uuid4().hex[:8]}"

        state["species_id"] = new_species_id
        state["species_name"] = suggestion.get("name", "New Species")
        state["new_species_created"] = True

        logger.info(f"Created new species: {state['species_name']} (ID: {new_species_id})")

    except Exception as e:
        logger.error(f"Error creating species: {e}")
        state["errors"] = state.get("errors", []) + [str(e)]

    return state


async def generate_npc_details_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate complete NPC details

    This node:
    1. Takes species assignment
    2. Generates NPC personality, backstory, dialogue style
    3. Creates NPC with world persistence flag
    """
    try:
        logger.info(f"Generating NPC details for role: {state.get('npc_role', 'unknown')}")

        # Create NPC generation prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a master NPC designer for RPG games.

Your task is to create a compelling, memorable NPC with distinct personality and backstory.

The NPC should:
- Have a unique personality that fits their role
- Have a backstory that connects to the world and narrative
- Have a distinct dialogue style
- Be appropriate for their species

Return your response as JSON:
{{
  "npc_name": "NPC name",
  "personality_traits": ["trait1", "trait2", "trait3"],
  "backstory": "NPC backstory (2-3 paragraphs)",
  "dialogue_style": "Description of how this NPC speaks and interacts",
  "quirks": ["quirk1", "quirk2"]
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """NPC Context:
Role: {role}
Species: {species}
Location: {location}
Narrative Context: {context}

Generate a complete NPC with personality and backstory.""")
        ])

        # Generate NPC
        chain = prompt | anthropic_client
        response = await chain.ainvoke({
            "role": state.get("npc_role", "Unknown"),
            "species": state.get("species_name", "Unknown"),
            "location": state.get("location_name", ""),
            "context": state.get("narrative_context", "")
        })

        # Parse response with error handling
        try:
            npc_data = json.loads(response.content.strip())
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON parsing failed for NPC generation: {json_err}")
            logger.error(f"Raw response: {response.content[:500]}")
            # Use fallback with minimal NPC data
            logger.warning("Using fallback: creating minimal NPC")
            npc_data = {
                "npc_name": f"{state.get('npc_role', 'Character').title()} NPC",
                "personality_traits": ["mysterious", "reserved"],
                "backstory": "A character whose full story remains to be told.",
                "dialogue_style": "Speaks with measured words.",
                "quirks": []
            }

        # Generate NPC ID immediately (same format as persistence layer expects)
        npc_name = npc_data.get("npc_name", "Unnamed NPC")
        npc_id = f"npc_{uuid.uuid4().hex[:16]}_{npc_name.replace(' ', '_').lower()}"

        # Create NPCData
        npc: NPCData = {
            "npc_id": npc_id,  # Set immediately so scenes can reference it
            "name": npc_name,
            "species_id": state.get("species_id", ""),
            "species_name": state.get("species_name", ""),
            "personality_traits": npc_data.get("personality_traits", []),
            "role": state.get("npc_role", "neutral"),
            "dialogue_style": npc_data.get("dialogue_style", ""),
            "backstory": npc_data.get("backstory", ""),
            "level_3_location_id": state.get("level_3_location_id", ""),
            "level_3_location_name": state.get("location_name", "Unknown Location"),
            "is_world_permanent": True  # All campaign NPCs are added to world
        }

        state["npc"] = npc

        logger.info(f"Generated NPC: {npc['name']} ({npc['species_name']} {npc['role']})")

    except Exception as e:
        logger.error(f"Error generating NPC: {e}")
        state["errors"] = state.get("errors", []) + [str(e)]

    return state


def create_npc_subgraph() -> StateGraph:
    """
    Create reusable NPC generation subgraph

    Input state requirements:
    - npc_role: Role of NPC (quest_giver, merchant, enemy, ally, neutral)
    - narrative_context: Context for NPC generation
    - location_name: Where NPC is located
    - level_3_location_id: Scene location ID

    Output state:
    - npc: Complete NPCData
    - species_id: Species used (existing or new)
    - new_species_created: Boolean flag
    """
    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("evaluate_species", evaluate_existing_species_node)
    workflow.add_node("create_species", create_new_species_node)
    workflow.add_node("generate_npc", generate_npc_details_node)

    # Set entry point
    workflow.set_entry_point("evaluate_species")

    # Add edges
    workflow.add_edge("evaluate_species", "create_species")
    workflow.add_edge("create_species", "generate_npc")
    workflow.add_edge("generate_npc", END)

    return workflow.compile()
