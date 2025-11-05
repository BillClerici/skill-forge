"""
NPC Generation Subgraph
Reusable subgraph for generating NPCs with species association
"""
import os
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .state import CampaignWorkflowState, NPCData
from .utils import add_audit_entry, publish_entity_event, db, extract_json_from_llm_response
from .rubric_templates import get_template_for_interaction

logger = logging.getLogger(__name__)

# Pydantic models for structured output
class NewSpeciesSuggestion(BaseModel):
    """Suggestion for a new species"""
    name: str = Field(default="", description="Suggested species name")
    description: str = Field(default="", description="Suggested species description")

class SpeciesEvaluationResponse(BaseModel):
    """Structured response for species evaluation"""
    use_existing: bool = Field(description="Whether to use an existing species")
    species_id: str = Field(description="ID of the species to use")
    species_name: str = Field(description="Name of the species")
    reasoning: str = Field(description="Explanation of species choice")
    or_create_new: bool = Field(description="Whether to create a new species")
    new_species_suggestion: Optional[NewSpeciesSuggestion] = Field(default=None, description="New species suggestion")

class NPCDetailsResponse(BaseModel):
    """Structured response for NPC generation"""
    npc_name: str = Field(description="NPC name")
    description: str = Field(description="Brief one-sentence description of the NPC")
    purpose: str = Field(description="The NPC's function in the campaign narrative")
    archetype: str = Field(description="Character archetype: mentor, trickster, guardian, herald, or shadow")
    personality_traits: List[str] = Field(description="List of 5-7 personality traits")
    backstory: str = Field(description="NPC backstory (2-3 paragraphs)")
    backstory_summary: str = Field(description="One-paragraph summary of the backstory")
    dialogue_style: str = Field(description="Dialogue style: formal, casual, cryptic, warm, stern, or eloquent")
    quirks: List[str] = Field(default_factory=list, description="List of quirks")

# Initialize Claude client
anthropic_client = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
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

        # Evaluate with structured output for guaranteed valid JSON
        structured_llm = anthropic_client.with_structured_output(SpeciesEvaluationResponse, include_raw=False)
        chain = prompt | structured_llm
        try:
            eval_response: SpeciesEvaluationResponse = await chain.ainvoke({
                "role": state.get("npc_role", "Unknown"),
                "context": state.get("narrative_context", ""),
                "location": state.get("location_name", ""),
                "region": state.get("region_name", "Unknown Region"),
                "native_species": native_species_str,
                "other_species": other_species_str
            })
            evaluation = eval_response.model_dump()
        except Exception as parse_err:
            logger.error(f"Structured output failed for species evaluation: {parse_err}")
            # Use fallback with default species (Human)
            logger.warning("Using fallback: defaulting to Human species")
            evaluation = {
                "use_existing": True,
                "species_id": "species1",
                "species_name": "Human",
                "reasoning": "Defaulted due to parsing error",
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
    Create new species for the world (if evaluation suggests it) OR extract existing species info

    This node:
    1. Takes species suggestion from evaluation
    2. If using existing: Extract species_id and species_name from evaluation
    3. If creating new: Generates full species details and creates species in world
    4. Adds to world permanently (enriches world)
    """
    try:
        evaluation = state.get("species_evaluation", {})

        if not evaluation.get("or_create_new", False):
            # FIX: Extract existing species info from evaluation result
            logger.info("Using existing species - extracting from evaluation")
            state["species_id"] = evaluation.get("species_id", "")
            state["species_name"] = evaluation.get("species_name", "")
            state["new_species_created"] = False

            logger.info(f"Selected existing species: {state['species_name']} (ID: {state['species_id']})")
            return state

        logger.info("Creating new species for world")

        suggestion = evaluation.get("new_species_suggestion", {})
        world_id = state.get("world_id", "")

        if not world_id:
            error_msg = "Cannot create species without world_id"
            logger.error(error_msg)
            state["errors"] = state.get("errors", []) + [error_msg]
            return state

        # Generate proper UUID for species
        new_species_id = str(uuid.uuid4())

        # Create full species document (following same pattern as Django views)
        species_name = suggestion.get("name", "New Species")
        species_description = suggestion.get("description", "")

        species_document = {
            "_id": new_species_id,
            "world_id": world_id,
            "species_name": species_name,
            "species_type": suggestion.get("species_type", "Humanoid"),
            "category": suggestion.get("category", "Sentient"),
            "description": species_description,
            "backstory": suggestion.get("backstory", ""),
            "character_traits": suggestion.get("character_traits", []),
            "regions": [],  # Can be populated later if region data is available
            "relationships": [],
            "species_image": None
        }

        # Insert species into MongoDB
        try:
            db.species_definitions.insert_one(species_document)
            logger.info(f"Inserted species into MongoDB: {new_species_id}")
        except Exception as db_err:
            error_msg = f"Failed to insert species into MongoDB: {db_err}"
            logger.error(error_msg)
            state["errors"] = state.get("errors", []) + [error_msg]
            return state

        # Update world's species list
        try:
            db.world_definitions.update_one(
                {"_id": world_id},
                {"$addToSet": {"species": new_species_id}}
            )
            logger.info(f"Added species {new_species_id} to world {world_id}")
        except Exception as db_err:
            error_msg = f"Failed to update world species list: {db_err}"
            logger.error(error_msg)
            state["errors"] = state.get("errors", []) + [error_msg]
            # Don't return - species is created, just log the warning

        # Publish RabbitMQ event to sync to Neo4j
        try:
            await publish_entity_event('species', 'created', new_species_id, {
                'world_id': world_id,
                'species_name': species_name,
                'species_type': species_document['species_type'],
                'category': species_document['category']
            })
            logger.info(f"Published species creation event for {new_species_id}")
        except Exception as event_err:
            logger.warning(f"Failed to publish species event (Neo4j sync may be delayed): {event_err}")
            # Don't fail - species is created in MongoDB

        state["species_id"] = new_species_id
        state["species_name"] = species_name
        state["new_species_created"] = True

        logger.info(f"Created new species: {species_name} (ID: {new_species_id})")

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
- Have a clear archetype (mentor, trickster, guardian, herald, or shadow)
- Have a clear purpose in the campaign narrative

Return your response as JSON with ALL these fields:
{{
  "npc_name": "NPC name",
  "description": "Brief one-sentence description",
  "purpose": "Their function in the campaign narrative",
  "archetype": "mentor|trickster|guardian|herald|shadow",
  "personality_traits": ["trait1", "trait2", "trait3", "trait4", "trait5"],
  "backstory": "Full NPC backstory (2-3 paragraphs)",
  "backstory_summary": "One-paragraph summary of the backstory",
  "dialogue_style": "formal|casual|cryptic|warm|stern|eloquent",
  "quirks": ["quirk1", "quirk2"]
}}

CRITICAL: Return ONLY the JSON object, no other text."""),
            ("user", """NPC Context:
Role: {role}
Species: {species}
Location: {location}
Narrative Context: {context}

Generate a complete NPC with personality, backstory, purpose, archetype, and all required fields.""")
        ])

        # Generate NPC with structured output for guaranteed valid JSON
        structured_llm = anthropic_client.with_structured_output(NPCDetailsResponse, include_raw=False)
        chain = prompt | structured_llm
        try:
            npc_response: NPCDetailsResponse = await chain.ainvoke({
                "role": state.get("npc_role", "Unknown"),
                "species": state.get("species_name", "Unknown"),
                "location": state.get("location_name", ""),
                "context": state.get("narrative_context", "")
            })
            npc_data = npc_response.model_dump()
            # Ensure required fields are always present
            if not npc_data.get("backstory") or npc_data.get("backstory").strip() == "":
                logger.warning(f"NPC {npc_data.get('npc_name', 'unknown')} has no backstory, generating default")
                npc_data["backstory"] = f"A {state.get('species_name', 'character')} {state.get('npc_role', 'individual')} whose story is intertwined with the events at {state.get('location_name', 'this location')}."
            if not npc_data.get("backstory_summary"):
                npc_data["backstory_summary"] = npc_data.get("backstory", "")[:200] + "..."
            if not npc_data.get("description"):
                npc_data["description"] = f"A {state.get('species_name', 'character')} {state.get('npc_role', 'character')}."
            if not npc_data.get("purpose"):
                npc_data["purpose"] = f"Serves as a {state.get('npc_role', 'character')} in the narrative."
            if not npc_data.get("archetype"):
                npc_data["archetype"] = "neutral"
        except Exception as parse_err:
            logger.error(f"Structured output failed for NPC generation: {parse_err}")
            # Use fallback with minimal NPC data
            logger.warning("Using fallback: creating minimal NPC")
            default_backstory = f"A {state.get('species_name', 'character')} {state.get('npc_role', 'individual')} whose story is intertwined with the events at {state.get('location_name', 'this location')}."
            npc_data = {
                "npc_name": f"{state.get('npc_role', 'Character').title()} NPC",
                "description": f"A {state.get('species_name', 'character')} {state.get('npc_role', 'character')}.",
                "purpose": f"Serves as a {state.get('npc_role', 'character')} in the narrative.",
                "archetype": "neutral",
                "personality_traits": ["mysterious", "reserved"],
                "backstory": default_backstory,
                "backstory_summary": default_backstory,
                "dialogue_style": "formal",
                "quirks": []
            }

        # Generate NPC ID immediately (same format as persistence layer expects)
        npc_name = npc_data.get("npc_name", "Unnamed NPC")
        npc_id = f"npc_{uuid.uuid4().hex[:16]}_{npc_name.replace(' ', '_').lower()}"

        # Generate rubric ID for this NPC
        rubric_id = f"rubric_npc_{uuid.uuid4().hex[:8]}"

        # CRITICAL VALIDATION: Ensure species is ALWAYS assigned
        species_id = state.get("species_id", "")
        species_name = state.get("species_name", "")

        if not species_id or not species_name:
            error_msg = f"CRITICAL ERROR: NPC '{npc_name}' cannot be created without species! species_id='{species_id}', species_name='{species_name}'"
            logger.error(error_msg)
            state["errors"] = state.get("errors", []) + [error_msg]
            raise ValueError(error_msg)

        # Create NPCData
        # Extract knowledge/items from npc_role spec if it's a dict
        npc_role_data = state.get("npc_role", "neutral")
        provides_knowledge = []
        provides_items = []
        if isinstance(npc_role_data, dict):
            provides_knowledge = npc_role_data.get("provides_knowledge", [])
            provides_items = npc_role_data.get("provides_items", [])

        npc: NPCData = {
            "npc_id": npc_id,  # Set immediately so scenes can reference it
            "name": npc_name,
            "species_id": species_id,
            "species_name": species_name,

            # Core identity (NEW FIELDS)
            "role": state.get("npc_role", "neutral") if not isinstance(npc_role_data, dict) else npc_role_data.get("type", "neutral"),
            "purpose": npc_data.get("purpose", ""),
            "archetype": npc_data.get("archetype", "neutral"),

            # Personality & backstory
            "personality_traits": npc_data.get("personality_traits", []),
            "dialogue_style": npc_data.get("dialogue_style", ""),
            "backstory": npc_data.get("backstory", ""),
            "backstory_summary": npc_data.get("backstory_summary", ""),

            # Location
            "level_3_location_id": state.get("level_3_location_id", ""),
            "level_3_location_name": state.get("location_name", "Unknown Location"),

            # World & items
            "is_world_permanent": True,  # All campaign NPCs are added to world
            "provides_knowledge_ids": provides_knowledge,  # Knowledge NPC can teach
            "provides_item_ids": provides_items,  # Items NPC can give/sell
            "rubric_id": rubric_id
        }

        state["npc"] = npc

        # Generate rubric for NPC conversation
        try:
            # Extract role string (handle both string and dict formats)
            npc_role = state.get("npc_role", "neutral")
            if isinstance(npc_role, dict):
                npc_role_str = npc_role.get("type", "neutral")
            else:
                npc_role_str = str(npc_role)

            rubric = get_template_for_interaction(
                "npc_conversation",
                npc_role_str,
                {"id": npc_id, "name": npc["name"], "role": npc["role"]}
            )

            # Only store rubric if it was successfully generated
            if rubric is not None:
                # Store rubric in parent state (if available)
                if "rubrics" in state:
                    state["rubrics"].append(rubric)
                else:
                    # Initialize rubrics list if not present (shouldn't happen, but defensive)
                    state["rubrics"] = [rubric]

                # Also store rubric in a way the subgraph can return it
                state["npc_rubric"] = rubric

                logger.info(f"Generated rubric for NPC: {npc['name']}")
            else:
                logger.warning(f"Rubric generation returned None for NPC: {npc['name']}")

        except Exception as e:
            logger.error(f"Error generating rubric for NPC: {str(e)}")
            # Don't fail NPC generation if rubric fails

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
