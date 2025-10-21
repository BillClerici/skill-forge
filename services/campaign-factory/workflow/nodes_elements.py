"""
Scene Element Generation Nodes
Phase 7: Generate NPCs, discoveries, events, challenges for scenes
"""
import os
import logging
import json
import uuid
from datetime import datetime
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


async def auto_assign_orphans_to_scenes(
    state: CampaignWorkflowState,
    orphan_knowledge: List[KnowledgeData],
    orphan_items: List[ItemData],
    all_discoveries: List[DiscoveryData],
    all_challenges: List[ChallengeData]
) -> None:
    """
    Auto-assign orphan knowledge and items to scenes to ensure 100% coverage.

    Strategy:
    1. Group orphans by the objectives they support
    2. Find scenes that support those objectives
    3. Create discoveries for knowledge orphans
    4. Create challenges for item orphans
    5. Add acquisition methods to orphan entities

    Args:
        state: Campaign workflow state
        orphan_knowledge: Knowledge entities with no acquisition methods
        orphan_items: Item entities with no acquisition methods
        all_discoveries: List of existing discoveries (will be appended to)
        all_challenges: List of existing challenges (will be appended to)
    """
    try:
        logger.info(f"AUTO-ASSIGNING {len(orphan_knowledge)} orphan knowledge and {len(orphan_items)} orphan items to scenes")

        # Build a map of objective_id -> scene_id for targeted assignment
        objective_to_scenes = {}
        for assignment in state.get("scene_objective_assignments", []):
            for obj_id in assignment.get("advances_quest_objectives", []):
                if obj_id not in objective_to_scenes:
                    objective_to_scenes[obj_id] = []
                objective_to_scenes[obj_id].append({
                    "scene_id": assignment["scene_id"],
                    "scene_name": assignment.get("scene_name", "Unknown Scene")
                })

        # If no objective mappings exist, fall back to distributing across all scenes
        if not objective_to_scenes:
            logger.warning("No scene-objective assignments found - distributing orphans evenly across scenes")
            all_scene_ids = [scene.get("scene_id") for scene in state.get("scenes", [])]

        # Process orphan knowledge
        for kg_idx, kg in enumerate(orphan_knowledge):
            kg_id = kg.get("knowledge_id")
            kg_name = kg.get("name", "Unknown Knowledge")

            # Find which objectives need this knowledge
            target_objectives = []
            for obj_progress in state.get("objective_progress", []):
                for kg_spec in obj_progress.get("_knowledge_specs", []):
                    if kg_spec.get("knowledge_id") == kg_id:
                        target_objectives.append(obj_progress["objective_id"])

            # Find scenes that support these objectives
            target_scenes = []
            for obj_id in target_objectives:
                if obj_id in objective_to_scenes:
                    target_scenes.extend(objective_to_scenes[obj_id])

            # Fallback: if no scenes found, use first available scene
            if not target_scenes:
                if state.get("scenes"):
                    first_scene = state["scenes"][0]
                    target_scenes = [{
                        "scene_id": first_scene.get("scene_id"),
                        "scene_name": first_scene.get("name", "Default Scene")
                    }]
                else:
                    logger.error(f"Cannot assign orphan knowledge {kg_name} - no scenes available!")
                    continue

            # Create 2 discoveries for redundancy (or 1 if only 1 scene available)
            num_discoveries = min(2, len(target_scenes))
            for i in range(num_discoveries):
                scene_info = target_scenes[i % len(target_scenes)]
                scene = next((s for s in state["scenes"] if s.get("scene_id") == scene_info["scene_id"]), None)

                if not scene:
                    logger.warning(f"Scene {scene_info['scene_id']} not found in state - skipping")
                    continue

                # Create a discovery for this knowledge
                discovery_id = f"discovery_{uuid.uuid4().hex[:16]}"
                rubric_id = f"rubric_discovery_{uuid.uuid4().hex[:8]}"

                discovery: DiscoveryData = {
                    "discovery_id": discovery_id,
                    "name": f"{kg_name} Documentation",
                    "description": f"A source of information about {kg_name.lower()}. Study this to gain understanding.",
                    "knowledge_type": kg.get("knowledge_type", "information"),
                    "blooms_level": state["campaign_core"]["target_blooms_level"],
                    "unlocks_scenes": [],
                    "provides_knowledge_ids": [kg_id],
                    "provides_item_ids": [],
                    "rubric_id": rubric_id,
                    "scene_id": scene.get("scene_id")
                }

                # Add to discoveries list
                all_discoveries.append(discovery)

                # Add to scene's discovery IDs
                if "discovery_ids" not in scene:
                    scene["discovery_ids"] = []
                scene["discovery_ids"].append(discovery_id)

                # Add acquisition method to knowledge entity
                acquisition_method = {
                    "type": "environmental_discovery",
                    "entity_id": discovery_id,
                    "difficulty": "Medium",
                    "max_level_obtainable": 4,
                    "rubric_id": rubric_id,
                    "conditions": {}
                }

                if "acquisition_methods" not in kg:
                    kg["acquisition_methods"] = []
                kg["acquisition_methods"].append(acquisition_method)

                logger.info(f"AUTO-ASSIGNED knowledge '{kg_name}' to scene '{scene_info['scene_name']}' via discovery '{discovery['name']}'")

                # Generate rubric for this discovery
                try:
                    rubric = get_template_for_interaction(
                        "environmental_discovery",
                        kg.get("knowledge_type", "information"),
                        {"id": discovery_id, "name": discovery["name"], "discovery_type": kg.get("knowledge_type", "information")}
                    )

                    if rubric is not None:
                        if "rubrics" not in state:
                            state["rubrics"] = []

                        dedup_key = f"{rubric.get('rubric_type')}:{rubric.get('interaction_name')}"
                        existing_keys = [
                            f"{r.get('rubric_type')}:{r.get('interaction_name')}"
                            for r in state["rubrics"]
                        ]

                        if dedup_key not in existing_keys:
                            state["rubrics"].append(rubric)
                except Exception as e:
                    logger.error(f"Error generating rubric for auto-assigned discovery: {str(e)}")

        # Process orphan items
        for item_idx, item in enumerate(orphan_items):
            item_id = item.get("item_id")
            item_name = item.get("name", "Unknown Item")

            # Find which objectives need this item
            target_objectives = []
            for obj_progress in state.get("objective_progress", []):
                for item_spec in obj_progress.get("_item_specs", []):
                    if item_spec.get("item_id") == item_id:
                        target_objectives.append(obj_progress["objective_id"])

            # Find scenes that support these objectives
            target_scenes = []
            for obj_id in target_objectives:
                if obj_id in objective_to_scenes:
                    target_scenes.extend(objective_to_scenes[obj_id])

            # Fallback: if no scenes found, use first available scene
            if not target_scenes:
                if state.get("scenes"):
                    first_scene = state["scenes"][0]
                    target_scenes = [{
                        "scene_id": first_scene.get("scene_id"),
                        "scene_name": first_scene.get("name", "Default Scene")
                    }]
                else:
                    logger.error(f"Cannot assign orphan item {item_name} - no scenes available!")
                    continue

            # Create 2 challenges for redundancy (or 1 if only 1 scene available)
            num_challenges = min(2, len(target_scenes))
            for i in range(num_challenges):
                scene_info = target_scenes[i % len(target_scenes)]
                scene = next((s for s in state["scenes"] if s.get("scene_id") == scene_info["scene_id"]), None)

                if not scene:
                    logger.warning(f"Scene {scene_info['scene_id']} not found in state - skipping")
                    continue

                # Create a challenge that rewards this item
                challenge_id = f"challenge_{uuid.uuid4().hex[:16]}"
                rubric_id = f"rubric_challenge_{uuid.uuid4().hex[:8]}"

                challenge: ChallengeData = {
                    "challenge_id": challenge_id,
                    "name": f"Obtain {item_name}",
                    "description": f"Successfully acquire the {item_name.lower()} through skillful effort.",
                    "challenge_type": "skill_check",
                    "challenge_category": "general",
                    "primary_dimension": item.get("primary_dimension", "intellectual"),
                    "secondary_dimensions": [],
                    "difficulty": state["quest_difficulty"],
                    "blooms_level": state["campaign_core"]["target_blooms_level"],
                    "required_knowledge": [],
                    "required_items": [],
                    "provides_knowledge_ids": [],
                    "provides_item_ids": [item_id],
                    "rubric_id": rubric_id,
                    "success_rewards": {"item": item_name},
                    "failure_consequences": {},
                    "scene_id": scene.get("scene_id")
                }

                # Add to challenges list
                all_challenges.append(challenge)

                # Add to scene's challenge IDs
                if "challenge_ids" not in scene:
                    scene["challenge_ids"] = []
                scene["challenge_ids"].append(challenge_id)

                # Add acquisition method to item entity
                acquisition_method = {
                    "type": "challenge",
                    "entity_id": challenge_id,
                    "difficulty": state["quest_difficulty"],
                    "max_level_obtainable": 1,  # Binary for items
                    "rubric_id": rubric_id,
                    "conditions": {}
                }

                if "acquisition_methods" not in item:
                    item["acquisition_methods"] = []
                item["acquisition_methods"].append(acquisition_method)

                logger.info(f"AUTO-ASSIGNED item '{item_name}' to scene '{scene_info['scene_name']}' via challenge '{challenge['name']}'")

                # Generate rubric for this challenge
                try:
                    rubric = get_template_for_interaction(
                        "challenge",
                        "skill_check",
                        {"id": challenge_id, "name": challenge["name"], "difficulty": challenge["difficulty"]}
                    )

                    if rubric is not None:
                        if "rubrics" not in state:
                            state["rubrics"] = []

                        dedup_key = f"{rubric.get('rubric_type')}:{rubric.get('interaction_name')}"
                        existing_keys = [
                            f"{r.get('rubric_type')}:{r.get('interaction_name')}"
                            for r in state["rubrics"]
                        ]

                        if dedup_key not in existing_keys:
                            state["rubrics"].append(rubric)
                except Exception as e:
                    logger.error(f"Error generating rubric for auto-assigned challenge: {str(e)}")

        # Update state with new elements
        state["discoveries"] = all_discoveries
        state["challenges"] = all_challenges

        logger.info(f"✓ AUTO-ASSIGNMENT COMPLETE: Created {len(orphan_knowledge) * 2} discoveries and {len(orphan_items) * 2} challenges")

    except Exception as e:
        logger.error(f"Error in auto_assign_orphans_to_scenes: {str(e)}")
        # Non-critical - log but don't raise


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
        state["step_progress"] = 0  # Initialize step progress for this phase
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

            # Update step progress based on scene completion
            state["step_progress"] = int(((scene_idx + 1) / total_scenes) * 100)  # 0-100% within this phase

            state["status_message"] = f"Generating elements for scene {scene_idx + 1} of {total_scenes}..."
            await publish_progress(state, f"Scene: {scene['name']}")

            logger.info(f"Generating elements for scene {scene_idx + 1}/{total_scenes}: {scene['name']}")

            # Step 1: Determine what elements this scene needs
            elements_needed = await determine_scene_elements(scene, state)
            logger.info(f"DEBUG: elements_needed = {json.dumps(elements_needed, indent=2)[:500]}")

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

                # DEBUG: Log what we're tracking (from the generated discovery entity)
                logger.info(f"DEBUG: Discovery provides_knowledge_ids={discovery.get('provides_knowledge_ids', [])}, provides_item_ids={discovery.get('provides_item_ids', [])}")

                # Track knowledge/items from discovery entity
                _track_knowledge_from_spec(discovery, discovery_id, "environmental_discovery", scene, knowledge_tracker)
                _track_items_from_spec(discovery, discovery_id, "environmental_discovery", scene, item_tracker)

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

                # DEBUG: Log what we're tracking (from the generated challenge entity)
                logger.info(f"DEBUG: Challenge provides_knowledge_ids={challenge.get('provides_knowledge_ids', [])}, provides_item_ids={challenge.get('provides_item_ids', [])}")

                # Track knowledge/items from challenge entity
                _track_knowledge_from_spec(challenge, challenge_id, "challenge", scene, knowledge_tracker)
                _track_items_from_spec(challenge, challenge_id, "challenge", scene, item_tracker)

        # Step 6: Merge acquisition methods into existing knowledge entities using IDs
        logger.info(f"DEBUG: knowledge_tracker has {len(knowledge_tracker)} knowledge IDs")
        logger.info(f"DEBUG: item_tracker has {len(item_tracker)} item IDs")
        logger.info(f"Merging acquisition methods for {len(knowledge_tracker)} knowledge items into existing entities")

        existing_knowledge = state.get("knowledge_entities", [])

        # Build ID-based lookup for existing knowledge - NO MORE NAME MATCHING!
        existing_knowledge_map = {}  # knowledge_id -> knowledge entity
        for kg in existing_knowledge:
            kg_id = kg.get("knowledge_id", "")
            if kg_id:
                existing_knowledge_map[kg_id] = kg

        logger.info(f"DEBUG: Existing knowledge IDs: {list(existing_knowledge_map.keys())[:10]}")

        # Merge acquisition methods from tracker into existing entities by ID
        unmatched_ids = []
        for knowledge_id, tracker_data in knowledge_tracker.items():
            if knowledge_id in existing_knowledge_map:
                # Entity exists - ADD acquisition methods to it
                existing_entity = existing_knowledge_map[knowledge_id]
                existing_methods = existing_entity.get("acquisition_methods", [])
                new_methods = tracker_data.get("acquisition_methods", [])

                # Merge methods (avoid duplicates based on entity_id)
                existing_entity_ids = {m.get("entity_id") for m in existing_methods}
                for method in new_methods:
                    if method.get("entity_id") not in existing_entity_ids:
                        existing_methods.append(method)

                existing_entity["acquisition_methods"] = existing_methods
                logger.info(f"Merged {len(new_methods)} acquisition methods into knowledge ID {knowledge_id}: {existing_entity.get('name')}")
            else:
                # Entity doesn't exist - this should never happen with ID-based system!
                logger.warning(f"Knowledge ID {knowledge_id} not found in existing entities - AI may have hallucinated an ID")
                unmatched_ids.append(knowledge_id)

        if unmatched_ids:
            logger.error(f"Unmatched knowledge IDs (AI hallucinated these): {unmatched_ids}")

        # No new entities to create - all knowledge should already exist from quest generation
        state["knowledge_entities"] = existing_knowledge

        # Step 7: Merge acquisition methods into existing item entities using IDs
        logger.info(f"Merging acquisition methods for {len(item_tracker)} items into existing entities")

        existing_items = state.get("item_entities", [])

        # Build ID-based lookup for existing items - NO MORE NAME MATCHING!
        existing_items_map = {}  # item_id -> item entity
        for item in existing_items:
            item_id = item.get("item_id", "")
            if item_id:
                existing_items_map[item_id] = item

        logger.info(f"DEBUG: Existing item IDs: {list(existing_items_map.keys())[:10]}")

        # Merge acquisition methods from tracker into existing entities by ID
        unmatched_item_ids = []
        for item_id, tracker_data in item_tracker.items():
            if item_id in existing_items_map:
                # Entity exists - ADD acquisition methods to it
                existing_entity = existing_items_map[item_id]
                existing_methods = existing_entity.get("acquisition_methods", [])
                new_methods = tracker_data.get("acquisition_methods", [])

                # Merge methods (avoid duplicates based on entity_id)
                existing_entity_ids = {m.get("entity_id") for m in existing_methods}
                for method in new_methods:
                    if method.get("entity_id") not in existing_entity_ids:
                        existing_methods.append(method)

                existing_entity["acquisition_methods"] = existing_methods
                logger.info(f"Merged {len(new_methods)} acquisition methods into item ID {item_id}: {existing_entity.get('name')}")
            else:
                # Entity doesn't exist - this should never happen with ID-based system!
                logger.warning(f"Item ID {item_id} not found in existing entities - AI may have hallucinated an ID")
                unmatched_item_ids.append(item_id)

        if unmatched_item_ids:
            logger.error(f"Unmatched item IDs (AI hallucinated these): {unmatched_item_ids}")

        # No new entities to create - all items should already exist from quest generation
        state["item_entities"] = existing_items

        # Update state with all generated elements
        state["npcs"] = all_npcs
        state["discoveries"] = all_discoveries
        state["events"] = all_events
        state["challenges"] = all_challenges

        logger.info(f"Final counts: {len(state['knowledge_entities'])} knowledge entities, {len(state['item_entities'])} item entities")

        # NO CONVERSION NEEDED! The AI now returns IDs directly in provides_knowledge_ids and provides_item_ids
        # All entities (discoveries, challenges, events, NPCs) already have the correct IDs from the AI

        # Create checkpoint after element generation
        create_checkpoint(state, "elements_generated")

        # Count knowledge/items with acquisition methods for reporting
        knowledge_with_methods = sum(1 for kg in state["knowledge_entities"] if len(kg.get("acquisition_methods", [])) > 0)
        items_with_methods = sum(1 for item in state["item_entities"] if len(item.get("acquisition_methods", [])) > 0)

        add_audit_entry(
            state,
            "generate_scene_elements",
            "Generated scene elements",
            {
                "num_npcs": len(all_npcs),
                "num_discoveries": len(all_discoveries),
                "num_events": len(all_events),
                "num_challenges": len(all_challenges),
                "num_knowledge_tracked": len(knowledge_tracker),
                "num_items_tracked": len(item_tracker),
                "total_knowledge_entities": len(state["knowledge_entities"]),
                "total_items": len(state["item_entities"]),
                "knowledge_with_acquisition_methods": knowledge_with_methods,
                "items_with_acquisition_methods": items_with_methods,
                "unmatched_knowledge_ids": len(unmatched_ids) if unmatched_ids else 0,
                "unmatched_item_ids": len(unmatched_item_ids) if unmatched_item_ids else 0,
                "new_species_created": len(state["new_species_ids"])
            },
            "success"
        )

        logger.info(f"Generated {len(all_npcs)} NPCs, {len(all_discoveries)} discoveries, "
                   f"{len(all_events)} events, {len(all_challenges)} challenges")
        logger.info(f"Merged acquisition methods: {knowledge_with_methods}/{len(state['knowledge_entities'])} knowledge, "
                   f"{items_with_methods}/{len(state['item_entities'])} items have acquisition methods")

        # ORPHAN DETECTION & AUTO-ASSIGNMENT
        # Check for knowledge/items with no acquisition methods
        orphan_knowledge = [
            kg for kg in state["knowledge_entities"]
            if len(kg.get("acquisition_methods", [])) == 0
        ]
        orphan_items = [
            item for item in state["item_entities"]
            if len(item.get("acquisition_methods", [])) == 0
        ]

        if orphan_knowledge or orphan_items:
            logger.warning(f"ORPHAN RESOURCES DETECTED: {len(orphan_knowledge)} knowledge, {len(orphan_items)} items with NO acquisition methods")
            logger.warning(f"Orphan knowledge IDs: {[kg.get('knowledge_id') for kg in orphan_knowledge]}")
            logger.warning(f"Orphan item IDs: {[item.get('item_id') for item in orphan_items]}")

            # Auto-assign orphans to scenes
            await auto_assign_orphans_to_scenes(
                state,
                orphan_knowledge,
                orphan_items,
                all_discoveries,
                all_challenges
            )

            # Re-count after auto-assignment
            knowledge_with_methods_final = sum(1 for kg in state["knowledge_entities"] if len(kg.get("acquisition_methods", [])) > 0)
            items_with_methods_final = sum(1 for item in state["item_entities"] if len(item.get("acquisition_methods", [])) > 0)

            logger.info(f"AFTER AUTO-ASSIGNMENT: {knowledge_with_methods_final}/{len(state['knowledge_entities'])} knowledge, "
                       f"{items_with_methods_final}/{len(state['item_entities'])} items have acquisition methods")

        # Reset step progress for next phase
        state["step_progress"] = 0

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
    # Use objective-driven mapping from scene_objective_assignments
    scene_knowledge = []
    scene_items = []

    # Find this scene's assignment
    scene_assignment = None
    for assignment in state.get("scene_objective_assignments", []):
        if assignment["scene_id"] == scene.get("scene_id"):
            scene_assignment = assignment
            break

    if scene_assignment:
        # Get knowledge that should be provided in this scene
        knowledge_domains = [kg["domain"] for kg in scene_assignment.get("provides_knowledge", [])]

        # Match knowledge entities to domains
        for kg in state.get("knowledge_entities", []):
            kg_name = kg.get("name", "")
            kg_type = kg.get("knowledge_type", "skill")

            # Check if knowledge matches any required domain
            if kg_name in knowledge_domains or any(kg_type.lower() in domain.lower() for domain in knowledge_domains):
                scene_knowledge.append(kg)

        # Get items that should be provided in this scene
        item_categories = [item["category"] for item in scene_assignment.get("provides_items", [])]

        # Match item entities to categories
        for item in state.get("item_entities", []):
            item_name = item.get("name", "")
            item_type = item.get("item_type", "tool")

            # Check if item matches any required category
            if item_name in item_categories or any(item_type.lower() in category.lower() for category in item_categories):
                scene_items.append(item)

    # Fallback: if no assignment or no matches, use a subset for variety
    if not scene_assignment or (len(scene_knowledge) == 0 and len(state.get("knowledge_entities", [])) > 0):
        # Provide up to 3 knowledge items for variety
        scene_knowledge = state.get("knowledge_entities", [])[:3]

    if not scene_assignment or (len(scene_items) == 0 and len(state.get("item_entities", [])) > 0):
        # Provide up to 3 items for variety
        scene_items = state.get("item_entities", [])[:3]

    # Get character profile to determine which dimensions to target
    character_profile = state.get("character_profile")
    target_dimensions = []

    if character_profile:
        # Target the least developed dimensions
        target_dimensions = character_profile.get("recommended_focus", ["intellectual", "social"])
    else:
        # Default to balanced dimensions
        target_dimensions = ["intellectual", "social", "emotional"]

    # Format knowledge/items for prompt using ID-based selection
    # AI will select by ID, not by name - much more reliable!
    if len(scene_knowledge) > 0:
        knowledge_str = "AVAILABLE KNOWLEDGE (select by ID in provides_knowledge_ids):\n" + "\n".join([
            f'- ID: {kg.get("knowledge_id", "unknown")} | Name: "{kg.get("name", "Unknown")}" | Type: {kg.get("knowledge_type", "skill")} | Dimension: {kg.get("primary_dimension", "intellectual")}'
            for kg in scene_knowledge
        ])
    else:
        knowledge_str = "No knowledge entities available for this scene."

    if len(scene_items) > 0:
        items_str = "AVAILABLE ITEMS (select by ID in provides_item_ids):\n" + "\n".join([
            f'- ID: {item.get("item_id", "unknown")} | Name: "{item.get("name", "Unknown")}" | Type: {item.get("item_type", "tool")}'
            for item in scene_items
        ])
    else:
        items_str = "No item entities available for this scene."

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

CRITICAL CONSTRAINT - KNOWLEDGE/ITEM SELECTION:
You MUST select knowledge and items by their IDs from the "AVAILABLE KNOWLEDGE" and "AVAILABLE ITEMS" lists below.
- Use provides_knowledge_ids (NOT provides_knowledge) with the ID values from the list
- Use provides_item_ids (NOT provides_items) with the ID values from the list
- DO NOT invent new IDs. ONLY use IDs that appear in the available lists.
- If the available lists say "No knowledge/items available", leave the ID arrays EMPTY.
- Any ID that doesn't exist in the provided list will cause critical validation errors.

Return your response as JSON:
{{
  "npcs": ["quest_giver", "merchant", "wise_elder"],
  "discoveries": [
    {{
      "type": "lore",
      "description": "Ancient text about...",
      "provides_knowledge_ids": ["knowledge_abc123"],
      "provides_item_ids": [],
      "dimension": "intellectual"
    }}
  ],
  "events": [
    {{
      "type": "scripted",
      "description": "Unexpected event...",
      "provides_knowledge_ids": [],
      "provides_item_ids": ["item_def456"],
      "dimension": "emotional"
    }}
  ],
  "challenges": [
    {{
      "type": "riddle",
      "description": "Solve the ancient riddle...",
      "provides_knowledge_ids": ["knowledge_ghi789"],
      "provides_item_ids": [],
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

{knowledge}

{items}

Target Dimensions for Character Growth:
{target_dimensions}

Campaign Target Bloom's Level: {blooms_level}

CRITICAL REMINDER:
- In provides_knowledge_ids arrays, use ONLY IDs from the "AVAILABLE KNOWLEDGE" list above
- In provides_item_ids arrays, use ONLY IDs from the "AVAILABLE ITEMS" list above
- Copy the IDs EXACTLY as shown (like "knowledge_abc123" or "item_def456")
- If lists say "No knowledge/items available", leave the ID arrays EMPTY []
- DO NOT invent new IDs or modify existing ones

Determine what elements this scene needs. Remember to create REDUNDANCY (2-3 ways to get the same knowledge/items).""")
    ])

    # Format objectives that this scene supports
    objectives_str = ""
    if scene_assignment:
        quest_obj_ids = scene_assignment.get("advances_quest_objectives", [])
        if len(quest_obj_ids) > 0:
            objectives_str = "This scene supports the following quest objectives:\n"
            # Find the actual objectives from objective_progress
            for obj_progress in state.get("objective_progress", []):
                if obj_progress["objective_id"] in quest_obj_ids:
                    objectives_str += f"  - {obj_progress['description']}\n"
        else:
            objectives_str = "(No specific objectives assigned to this scene)"
    else:
        objectives_str = "(No scene assignment found - scene objectives unknown)"
        logger.warning(f"No scene assignment found for scene '{scene.get('name')}' - element generation may be suboptimal")

    # Format parent quest for context (legacy - keep for backward compatibility)
    parent_quest = None
    for quest in state.get("quests", []):
        for place in state.get("places", []):
            if place.get("parent_quest_id") == quest.get("quest_id") and scene.get("parent_place_id") == place.get("place_id"):
                parent_quest = quest
                break
        if parent_quest:
            break

    # If we couldn't get objectives from scene_assignment, fall back to parent quest
    if not objectives_str or objectives_str == "(No scene assignment found - scene objectives unknown)":
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
        "knowledge": knowledge_str,  # Already has fallback message
        "items": items_str,  # Already has fallback message
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
        "provides_knowledge_ids": spec.get("provides_knowledge_ids", []),  # ID-based!
        "provides_item_ids": spec.get("provides_item_ids", []),  # ID-based!
        "rubric_id": rubric_id,
        "scene_id": scene.get("scene_id")  # Link to parent scene for persistence
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
        "provides_knowledge_ids": spec.get("provides_knowledge_ids", []),  # ID-based!
        "provides_item_ids": spec.get("provides_item_ids", []),  # ID-based!
        "rubric_id": rubric_id,
        "scene_id": scene.get("scene_id")  # Link to parent scene for persistence
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

        # Rewards system - ID-based!
        "provides_knowledge_ids": spec.get("provides_knowledge_ids", []),
        "provides_item_ids": spec.get("provides_item_ids", []),
        "rubric_id": rubric_id,

        # Legacy support
        "success_rewards": enriched.get("success_rewards", {}),
        "failure_consequences": enriched.get("failure_consequences", {}),

        # Scene linking
        "scene_id": scene.get("scene_id")  # Link to parent scene for persistence
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
