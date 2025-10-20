"""
Database Persistence for Campaign Factory
MongoDB, Neo4j, and PostgreSQL operations
"""
import os
import logging
from typing import Dict, Any, List
from pymongo import MongoClient
from neo4j import GraphDatabase
import psycopg2
from datetime import datetime

from .state import CampaignWorkflowState
from .neo4j_objective_persistence import (
    persist_objective_hierarchy_to_neo4j,
    persist_dimensional_objectives_to_neo4j
)
from .neo4j_scene_assignment_persistence import (
    persist_scene_assignments_to_neo4j,
    persist_acquisition_paths_to_neo4j,
    persist_redundancy_analysis_to_neo4j
)

logger = logging.getLogger(__name__)

# MongoDB connection
mongo_client = None
mongo_db = None

# Neo4j connection
neo4j_driver = None


def init_db_connections():
    """Initialize database connections"""
    global mongo_client, mongo_db, neo4j_driver

    # MongoDB
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    mongo_client = MongoClient(mongo_uri)
    mongo_db = mongo_client.skillforge

    # Neo4j
    neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    logger.info("Database connections initialized")


async def persist_campaign_to_mongodb(state: CampaignWorkflowState) -> str:
    """
    Persist complete campaign to MongoDB

    Creates documents for:
    - Campaign
    - Quests
    - Places
    - Scenes
    - NPCs
    - Discoveries
    - Events
    - Challenges

    Returns:
        Campaign ID
    """
    if mongo_db is None:
        init_db_connections()

    campaign_id = f"campaign_{state['request_id']}"

    try:
        # Create campaign document
        campaign_doc = {
            "_id": campaign_id,
            "name": state["campaign_core"]["name"],
            "plot": state["campaign_core"]["plot"],
            "storyline": state["campaign_core"]["storyline"],
            "primary_objectives": state["campaign_core"]["primary_objectives"],
            "universe_id": state["universe_id"],
            "world_id": state["world_id"],
            "region_id": state["region_id"],
            "genre": state["genre"],
            "character_id": state["character_id"],
            "user_id": state["user_id"],
            "difficulty_level": state["campaign_core"]["difficulty_level"],
            "estimated_duration_hours": state["campaign_core"]["estimated_duration_hours"],
            "target_blooms_level": state["campaign_core"]["target_blooms_level"],
            "status": "active",
            "created_at": state["created_at"],
            "quest_ids": [],
            "stats": {
                "num_quests": len(state["quests"]),
                "num_places": len(state["places"]),
                "num_scenes": len(state["scenes"]),
                "num_npcs": len(state["npcs"]),
                "new_species_created": len(state["new_species_ids"]),
                "new_locations_created": len(state["new_location_ids"])
            },
            "validation_report": state.get("validation_report")  # Include validation report if available
        }

        # Use replace_one with upsert to handle retries gracefully
        mongo_db.campaigns.replace_one(
            {"_id": campaign_id},
            campaign_doc,
            upsert=True
        )
        logger.info(f"Created/updated campaign document: {campaign_id}")

        # Persist quests
        quest_ids = await persist_quests(state, campaign_id)
        campaign_doc["quest_ids"] = quest_ids

        # Update campaign with quest IDs
        mongo_db.campaigns.update_one(
            {"_id": campaign_id},
            {"$set": {"quest_ids": quest_ids}}
        )

        # Persist NPCs (add to world's NPC pool)
        await persist_npcs(state)

        # Persist discoveries, events, challenges
        await persist_scene_elements(state)

        logger.info(f"Successfully persisted campaign {campaign_id} to MongoDB")

        return campaign_id

    except Exception as e:
        logger.error(f"Error persisting campaign to MongoDB: {e}")
        raise


async def persist_quests(state: CampaignWorkflowState, campaign_id: str) -> List[str]:
    """
    Persist quests and their sub-entities

    Returns:
        List of quest IDs
    """
    quest_ids = []

    for quest_idx, quest in enumerate(state["quests"]):
        # Use the quest ID that was generated during workflow execution
        quest_id = quest.get("quest_id", f"quest_{state['request_id']}_{quest_idx}")

        # Find places for this quest
        quest_places = [p for p in state["places"] if p.get("parent_quest_id") == quest.get("quest_id", "")]

        place_ids = []
        for place in quest_places:
            # Use the place ID that was generated during workflow execution
            place_id = place.get("place_id", f"place_{state['request_id']}_{len(place_ids)}")

            # Find scenes for this place
            place_scenes = [s for s in state["scenes"] if s.get("parent_place_id") == place.get("place_id", "")]

            scene_ids = []
            for scene in place_scenes:
                # Use the scene ID that was generated during workflow execution
                scene_id = scene.get("scene_id", f"scene_{state['request_id']}_{len(scene_ids)}")

                # Collect knowledge, item, and rubric IDs for this scene
                knowledge_ids = []
                item_ids = []
                rubric_ids = []

                # Get scene ID for filtering
                scene_internal_id = scene.get("scene_id", "")

                # Collect knowledge IDs for this scene
                for kg in state.get("knowledge_entities", []):
                    if kg.get("scene_id") == scene_internal_id:
                        knowledge_ids.append(kg.get("knowledge_id", ""))

                # Collect item IDs for this scene
                for item in state.get("item_entities", []):
                    if item.get("scene_id") == scene_internal_id:
                        item_ids.append(item.get("item_id", ""))

                # Collect rubric IDs for this scene
                for rubric in state.get("rubrics", []):
                    # Rubrics are linked via entity IDs (NPCs, challenges, etc.)
                    entity_id = rubric.get("entity_id", "")
                    # Check if this rubric's entity is in this scene
                    if entity_id in scene.get("npc_ids", []) or \
                       entity_id in scene.get("challenge_ids", []) or \
                       entity_id in scene.get("discovery_ids", []) or \
                       entity_id in scene.get("event_ids", []):
                        rubric_ids.append(rubric.get("rubric_id", ""))

                # Create scene document
                scene_doc = {
                    "_id": scene_id,
                    "name": scene["name"],
                    "description": scene["description"],
                    "level_3_location_id": scene["level_3_location_id"],
                    "level_3_location_name": scene["level_3_location_name"],
                    "parent_place_id": place_id,
                    "campaign_id": campaign_id,
                    "npc_ids": scene.get("npc_ids", []),
                    "discovery_ids": scene.get("discovery_ids", []),
                    "event_ids": scene.get("event_ids", []),
                    "challenge_ids": scene.get("challenge_ids", []),
                    "knowledge_ids": knowledge_ids,
                    "item_ids": item_ids,
                    "rubric_ids": rubric_ids,
                    "required_knowledge": scene.get("required_knowledge", []),
                    "required_items": scene.get("required_items", []),
                    "order_sequence": scene.get("order_sequence", 0),
                    "created_at": datetime.utcnow().isoformat()
                }

                mongo_db.scenes.replace_one(
                    {"_id": scene_id},
                    scene_doc,
                    upsert=True
                )
                scene_ids.append(scene_id)

            # Create place document
            place_doc = {
                "_id": place_id,
                "name": place["name"],
                "description": place["description"],
                "level_2_location_id": place["level_2_location_id"],
                "level_2_location_name": place["level_2_location_name"],
                "parent_quest_id": quest_id,
                "campaign_id": campaign_id,
                "scene_ids": scene_ids,
                "order_sequence": place.get("order_sequence", 0),
                "created_at": datetime.utcnow().isoformat()
            }

            mongo_db.places.replace_one(
                {"_id": place_id},
                place_doc,
                upsert=True
            )
            place_ids.append(place_id)

        # Create quest document
        quest_doc = {
            "_id": quest_id,
            "name": quest["name"],
            "description": quest["description"],
            "objectives": quest["objectives"],
            "level_1_location_id": quest["level_1_location_id"],
            "level_1_location_name": quest["level_1_location_name"],
            "difficulty_level": quest["difficulty_level"],
            "estimated_duration_minutes": quest["estimated_duration_minutes"],
            "order_sequence": quest["order_sequence"],
            "backstory": quest.get("backstory", ""),
            "campaign_id": campaign_id,
            "place_ids": place_ids,
            "status": "not_started",
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.quests.replace_one(
            {"_id": quest_id},
            quest_doc,
            upsert=True
        )
        quest_ids.append(quest_id)

        logger.info(f"Persisted quest: {quest_id} with {len(place_ids)} places")

    return quest_ids


async def persist_npcs(state: CampaignWorkflowState):
    """
    Persist NPCs to world's NPC pool (world-permanent)
    """
    for npc in state["npcs"]:
        # Use existing npc_id from the NPC data (generated in subgraph)
        npc_id = npc.get("npc_id")
        if not npc_id:
            # Fallback: generate ID if somehow missing
            npc_id = f"npc_{state['request_id']}_{npc['name'].replace(' ', '_').lower()}"
            logger.warning(f"NPC missing ID, generated: {npc_id}")

        npc_doc = {
            "_id": npc_id,
            "name": npc["name"],
            "species_id": npc["species_id"],
            "species_name": npc["species_name"],
            "personality_traits": npc["personality_traits"],
            "role": npc["role"],
            "dialogue_style": npc["dialogue_style"],
            "backstory": npc["backstory"],
            "world_id": state["world_id"],
            "level_3_location_id": npc["level_3_location_id"],
            "is_world_permanent": npc.get("is_world_permanent", True),
            "knowledge_revealed": npc.get("provides_knowledge_ids", []),  # Knowledge NPC can teach
            "items_revealed": npc.get("provides_item_ids", []),  # Items NPC can give/sell
            "origin_campaign_id": f"campaign_{state['request_id']}",
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.npcs.replace_one(
            {"_id": npc_id},
            npc_doc,
            upsert=True
        )

    logger.info(f"Persisted {len(state['npcs'])} NPCs to world pool")


async def persist_scene_elements(state: CampaignWorkflowState):
    """
    Persist discoveries, events, challenges, knowledge entities, items, and rubrics
    """
    # Discoveries
    campaign_id = f"campaign_{state['request_id']}"
    for idx, discovery in enumerate(state["discoveries"]):
        # FIX 2: Use original entity ID, don't regenerate
        discovery_id = discovery.get("discovery_id", f"discovery_{state['request_id']}_{idx}")

        # FIX 3 & 4: Fix field names and add campaign_id
        discovery_doc = {
            "_id": discovery_id,
            "discovery_name": discovery.get("name", "Unknown Discovery"),
            "name": discovery.get("name", "Unknown Discovery"),  # Duplicate for compatibility
            "description": discovery.get("description", ""),
            "knowledge_type": discovery.get("knowledge_type", "lore"),
            "blooms_level": discovery.get("blooms_level", 2),
            "unlocks_scenes": discovery.get("unlocks_scenes", []),
            "knowledge_revealed": discovery.get("provides_knowledge_ids", []),  # Link to knowledge items
            "campaign_id": campaign_id,  # FIX 4: Add campaign_id
            "scene_id": discovery.get("scene_id"),  # FIX 4: Add scene_id for tracking
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.discoveries.replace_one(
            {"_id": discovery_id},
            discovery_doc,
            upsert=True
        )

    # Events
    for idx, event in enumerate(state["events"]):
        # FIX 2: Use original entity ID, don't regenerate
        event_id = event.get("event_id", f"event_{state['request_id']}_{idx}")

        # FIX 3 & 4: Fix field names and add campaign_id
        event_doc = {
            "_id": event_id,
            "event_name": event.get("name", "Unknown Event"),
            "name": event.get("name", "Unknown Event"),  # Duplicate for compatibility
            "description": event.get("description", ""),
            "event_type": event.get("event_type", "scripted"),
            "trigger_conditions": event.get("trigger_conditions", {}),
            "outcomes": event.get("outcomes", []),
            "knowledge_revealed": event.get("provides_knowledge_ids", []),  # Knowledge gained from event
            "items_revealed": event.get("provides_item_ids", []),  # Items obtained from event
            "campaign_id": campaign_id,  # FIX 4: Add campaign_id
            "scene_id": event.get("scene_id"),  # FIX 4: Add scene_id for tracking
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.events.replace_one(
            {"_id": event_id},
            event_doc,
            upsert=True
        )

    # Challenges
    for idx, challenge in enumerate(state["challenges"]):
        # FIX 2: Use original entity ID, don't regenerate
        challenge_id = challenge.get("challenge_id", f"challenge_{state['request_id']}_{idx}")

        # FIX 3 & 4: Fix field names and add campaign_id
        challenge_doc = {
            "_id": challenge_id,
            "challenge_name": challenge.get("name", "Unknown Challenge"),
            "name": challenge.get("name", "Unknown Challenge"),  # Duplicate for compatibility
            "description": challenge.get("description", ""),
            "challenge_type": challenge.get("challenge_type", "skill_check"),
            "difficulty": challenge.get("difficulty", "Medium"),
            "blooms_level": challenge.get("blooms_level", 3),
            "success_rewards": challenge.get("success_rewards", {}),
            "failure_consequences": challenge.get("failure_consequences", {}),
            "knowledge_revealed": challenge.get("provides_knowledge_ids", []),  # Link to knowledge items (on success)
            "items_revealed": challenge.get("provides_item_ids", []),  # Link to item rewards (on success)
            "campaign_id": campaign_id,  # FIX 4: Add campaign_id
            "scene_id": challenge.get("scene_id"),  # FIX 4: Add scene_id for tracking
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.challenges.replace_one(
            {"_id": challenge_id},
            challenge_doc,
            upsert=True
        )

    # Knowledge Entities
    for knowledge in state.get("knowledge_entities", []):
        knowledge_id = knowledge.get("knowledge_id")
        if not knowledge_id:
            continue

        knowledge_doc = {
            "_id": knowledge_id,
            "knowledge_id": knowledge_id,  # Also save as field for game engine
            "name": knowledge["name"],
            "description": knowledge["description"],
            "knowledge_type": knowledge["knowledge_type"],
            "primary_dimension": knowledge["primary_dimension"],
            "bloom_level_target": knowledge["bloom_level_target"],
            "supports_objectives": knowledge.get("supports_objectives", []),
            "partial_levels": knowledge.get("partial_levels", []),
            "acquisition_methods": knowledge.get("acquisition_methods", []),
            "campaign_id": campaign_id,  # Add campaign_id for filtering
            "scene_id": knowledge.get("scene_id"),
            "created_at": knowledge.get("created_at", datetime.utcnow().isoformat())
        }

        mongo_db.knowledge.replace_one(
            {"_id": knowledge_id},
            knowledge_doc,
            upsert=True
        )

    # Items
    for item in state.get("item_entities", []):
        item_id = item.get("item_id")
        if not item_id:
            continue

        item_doc = {
            "_id": item_id,
            "item_id": item_id,  # Also save as field for game engine
            "name": item["name"],
            "description": item["description"],
            "item_type": item["item_type"],
            "supports_objectives": item.get("supports_objectives", []),
            "acquisition_methods": item.get("acquisition_methods", []),
            "quantity": item.get("quantity", 1),
            "is_consumable": item.get("is_consumable", False),
            "is_quest_critical": item.get("is_quest_critical", False),
            "campaign_id": campaign_id,  # Add campaign_id for filtering
            "scene_id": item.get("scene_id"),
            "created_at": item.get("created_at", datetime.utcnow().isoformat())
        }

        mongo_db.items.replace_one(
            {"_id": item_id},
            item_doc,
            upsert=True
        )

    # Rubrics
    for rubric in state.get("rubrics", []):
        rubric_id = rubric.get("rubric_id")
        if not rubric_id:
            continue

        rubric_doc = {
            "_id": rubric_id,
            "rubric_type": rubric["rubric_type"],
            "interaction_name": rubric["interaction_name"],
            "entity_id": rubric["entity_id"],
            "primary_dimension": rubric["primary_dimension"],
            "secondary_dimensions": rubric.get("secondary_dimensions", []),
            "evaluation_criteria": rubric.get("evaluation_criteria", []),
            "knowledge_level_mapping": rubric.get("knowledge_level_mapping", {}),
            "rewards_by_performance": rubric.get("rewards_by_performance", {}),
            "dimensional_rewards": rubric.get("dimensional_rewards", {}),
            "consequences_by_performance": rubric.get("consequences_by_performance", {}),
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.rubrics.replace_one(
            {"_id": rubric_id},
            rubric_doc,
            upsert=True
        )

    logger.info(f"Persisted {len(state['discoveries'])} discoveries, {len(state['events'])} events, {len(state['challenges'])} challenges")
    logger.info(f"Persisted {len(state.get('knowledge_entities', []))} knowledge entities, {len(state.get('item_entities', []))} items, {len(state.get('rubrics', []))} rubrics")


async def create_neo4j_relationships(state: CampaignWorkflowState, campaign_id: str) -> int:
    """
    Create Neo4j relationships for campaign structure

    Returns:
        Number of relationships created
    """
    if neo4j_driver is None:
        init_db_connections()

    relationships_created = 0

    logger.info(f"Starting Neo4j relationship creation for campaign: {campaign_id}")

    with neo4j_driver.session() as session:
        # Create Campaign node first
        try:
            logger.info(f"Creating Campaign node with id: {campaign_id}, name: {state['campaign_core']['name']}")
            session.run(
                """
                MERGE (camp:Campaign {id: $campaign_id})
                SET camp.name = $campaign_name,
                    camp.campaign_id = $campaign_id,
                    camp.status = $status,
                    camp.created_at = $created_at
                """,
                campaign_id=campaign_id,
                campaign_name=state["campaign_core"]["name"],
                status="active",
                created_at=state["created_at"]
            )
            logger.info(f"✓ Campaign node created successfully")
        except Exception as e:
            logger.error(f"Failed to create Campaign node: {str(e)}")
            logger.error(f"Campaign ID: {campaign_id}, Type: {type(campaign_id)}")
            raise

        # Character participates in Campaign (optional - only if character_id exists)
        if state.get("character_id"):
            try:
                logger.info(f"Linking Character to Campaign - character_id: {state.get('character_id')}, campaign_id: {campaign_id}")
                session.run(
                    """
                    MATCH (camp:Campaign {id: $campaign_id})
                    MERGE (c:Character {id: $character_id})
                    MERGE (c)-[:PARTICIPATES_IN]->(camp)
                    """,
                    character_id=state["character_id"],
                    campaign_id=campaign_id
                )
                relationships_created += 1
                logger.info("✓ Character linked to Campaign successfully")
            except Exception as e:
                logger.error(f"Failed to link Character to Campaign: {str(e)}")
                logger.error(f"Parameters: character_id={state.get('character_id')}, campaign_id={campaign_id}")
                raise

        # Campaign takes place in World and Region
        try:
            logger.info(f"Linking Campaign to World and Region - campaign_id: {campaign_id}, world_id: {state.get('world_id')}, region_id: {state.get('region_id')}")
            session.run(
                """
                MATCH (camp:Campaign {id: $campaign_id})
                MATCH (w:World {id: $world_id})
                MATCH (r:Region {id: $region_id})
                MERGE (camp)-[:TAKES_PLACE_IN]->(w)
                MERGE (camp)-[:LOCATED_IN]->(r)
                """,
                campaign_id=campaign_id,
                world_id=state["world_id"],
                region_id=state["region_id"]
            )
            relationships_created += 2
            logger.info("✓ Campaign linked to World and Region successfully")
        except Exception as e:
            logger.error(f"Failed to link Campaign to World and Region: {str(e)}")
            logger.error(f"Parameters: campaign_id={campaign_id}, world_id={state.get('world_id')}, region_id={state.get('region_id')}")
            raise

        # Campaign contains Quests, and create full hierarchy
        # Use same ID generation as MongoDB (flat counters, not nested indices)
        global_place_counter = 0
        global_scene_counter = 0

        logger.info(f"Creating Quest nodes for {len(state['quests'])} quests")

        for quest_idx, quest in enumerate(state["quests"]):
            # Use the quest ID that was generated during workflow execution
            quest_id = quest.get("quest_id", f"quest_{state['request_id']}_{quest_idx}")

            logger.info(f"Creating Quest {quest_idx + 1}/{len(state['quests'])}: {quest_id}")

            # Create Quest node and link to Campaign
            try:
                session.run(
                """
                MATCH (camp:Campaign {id: $campaign_id})
                MATCH (r:Region {id: $region_id})
                MERGE (q:Quest {id: $quest_id})
                SET q.name = $quest_name,
                    q.campaign_id = $campaign_id,
                    q.order_sequence = $order_sequence,
                    q.difficulty_level = $difficulty,
                    q.estimated_duration_minutes = $duration
                MERGE (camp)-[:CONTAINS]->(q)

                // MERGE Level 1 Location by name + world to avoid duplicates
                MERGE (loc:Location {name: $location_name, world_id: $world_id})
                ON CREATE SET loc.id = $location_id
                ON MATCH SET loc.id = COALESCE(loc.id, $location_id)
                // Level 1 locations are children of the Region, not directly connected to World
                MERGE (loc)-[:CHILD_OF]->(r)
                MERGE (q)-[:LOCATED_AT]->(loc)
                """,
                campaign_id=campaign_id,
                region_id=state["region_id"],
                world_id=state["world_id"],
                quest_id=quest_id,
                quest_name=quest["name"],
                order_sequence=quest["order_sequence"],
                difficulty=quest.get("difficulty_level", "Medium"),
                duration=quest.get("estimated_duration_minutes", 0),
                location_id=quest["level_1_location_id"],
                location_name=quest.get("level_1_location_name", "Unknown Location")
                )
                relationships_created += 4
                logger.info(f"✓ Quest {quest_id} created successfully")
            except Exception as e:
                logger.error(f"Failed to create Quest {quest_id}: {str(e)}")
                logger.error(f"Quest data: {quest.get('name')}, campaign_id={campaign_id}")
                raise

            # Find places for this quest and create Place nodes
            quest_places = [p for p in state["places"] if p.get("parent_quest_id") == quest.get("quest_id", "")]
            for place in quest_places:
                # Use the place ID that was generated during workflow execution
                place_id = place.get("place_id", f"place_{state['request_id']}_{global_place_counter}")
                global_place_counter += 1

                session.run(
                    """
                    MATCH (q:Quest {id: $quest_id})
                    MERGE (p:Place {id: $place_id})
                    SET p.name = $place_name,
                        p.campaign_id = $campaign_id,
                        p.order_sequence = $order_sequence
                    MERGE (q)-[:CONTAINS]->(p)

                    // MERGE Level 2 Location by name + world to avoid duplicates
                    MERGE (loc:Location {name: $location_name, world_id: $world_id})
                    ON CREATE SET loc.id = $location_id
                    ON MATCH SET loc.id = COALESCE(loc.id, $location_id)
                    MERGE (p)-[:LOCATED_AT]->(loc)

                    // Link Level 2 Location to parent Level 1 Location (NOT to World)
                    WITH loc
                    MERGE (parent:Location {name: $parent_location_name, world_id: $world_id})
                    ON CREATE SET parent.id = $parent_location_id
                    MERGE (loc)-[:CHILD_OF]->(parent)
                    """,
                    quest_id=quest_id,
                    world_id=state["world_id"],
                    campaign_id=campaign_id,
                    place_id=place_id,
                    place_name=place["name"],
                    order_sequence=place.get("order_sequence", 0),
                    location_id=place["level_2_location_id"],
                    location_name=place.get("level_2_location_name", "Unknown Location"),
                    parent_location_id=quest["level_1_location_id"],
                    parent_location_name=quest.get("level_1_location_name", "Unknown Location")
                )
                relationships_created += 4

                # Find scenes for this place and create Scene nodes
                place_scenes = [s for s in state["scenes"] if s.get("parent_place_id") == place.get("place_id", "")]
                for scene in place_scenes:
                    # Use the scene ID that was generated during workflow execution
                    scene_id = scene.get("scene_id", f"scene_{state['request_id']}_{global_scene_counter}")
                    global_scene_counter += 1

                    session.run(
                        """
                        MATCH (p:Place {id: $place_id})
                        MERGE (sc:Scene {id: $scene_id})
                        SET sc.name = $scene_name,
                            sc.campaign_id = $campaign_id,
                            sc.order_sequence = $order_sequence
                        MERGE (p)-[:CONTAINS]->(sc)

                        // MERGE Level 3 Location by name + world to avoid duplicates
                        MERGE (loc:Location {name: $location_name, world_id: $world_id})
                        ON CREATE SET loc.id = $location_id
                        ON MATCH SET loc.id = COALESCE(loc.id, $location_id)
                        MERGE (sc)-[:LOCATED_AT]->(loc)

                        // Link Level 3 Location to parent Level 2 Location (NOT to World)
                        WITH loc
                        MERGE (parent:Location {name: $parent_location_name, world_id: $world_id})
                        ON CREATE SET parent.id = $parent_location_id
                        MERGE (loc)-[:CHILD_OF]->(parent)
                        """,
                        place_id=place_id,
                        world_id=state["world_id"],
                        campaign_id=campaign_id,
                        scene_id=scene_id,
                        scene_name=scene["name"],
                        order_sequence=scene.get("order_sequence", 0),
                        location_id=scene["level_3_location_id"],
                        location_name=scene.get("level_3_location_name", "Unknown Location"),
                        parent_location_id=place["level_2_location_id"],
                        parent_location_name=place.get("level_2_location_name", "Unknown Location")
                    )
                    relationships_created += 5

                    # Link NPCs to this scene with full NPC data
                    for npc_id in scene.get("npc_ids", []):
                        if npc_id and npc_id != "None":  # Skip None values
                            # Find the NPC data from state to create node with full properties
                            npc_data = None
                            for npc in state.get("npcs", []):
                                if npc.get("npc_id") == npc_id:
                                    npc_data = npc
                                    break

                            if npc_data:
                                # Extract role as string
                                npc_role = npc_data["role"]
                                if isinstance(npc_role, dict):
                                    role_str = npc_role.get("type", str(npc_role))
                                else:
                                    role_str = str(npc_role)

                                # Create NPC with full properties including species and campaign
                                session.run(
                                    """
                                    MATCH (sc:Scene {id: $scene_id})
                                    MERGE (npc:NPC {id: $npc_id})
                                    SET npc.name = $npc_name,
                                        npc.role = $role,
                                        npc.description = $description,
                                        npc.species_id = $species_id,
                                        npc.species_name = $species_name,
                                        npc.campaign_id = $campaign_id
                                    MERGE (sc)-[:FEATURES]->(npc)
                                    """,
                                    scene_id=scene_id,
                                    npc_id=npc_id,
                                    npc_name=npc_data.get("name", "Unknown NPC"),
                                    role=role_str,
                                    description=npc_data.get("backstory", f"A {npc_data.get('species_name', 'character')} in this location."),
                                    species_id=npc_data.get("species_id", ""),
                                    species_name=npc_data.get("species_name", ""),
                                    campaign_id=campaign_id
                                )
                            else:
                                # Fallback: create NPC node with just ID (should not happen)
                                logger.warning(f"NPC {npc_id} not found in state, creating with minimal data")
                                session.run(
                                    """
                                    MATCH (sc:Scene {id: $scene_id})
                                    MERGE (npc:NPC {id: $npc_id})
                                    SET npc.name = 'Unknown NPC',
                                        npc.role = 'unknown',
                                        npc.description = 'An NPC whose details are yet to be discovered.'
                                    MERGE (sc)-[:FEATURES]->(npc)
                                    """,
                                    scene_id=scene_id,
                                    npc_id=npc_id
                                )
                            relationships_created += 1

        # NPCs relationships with species and locations
        for npc in state["npcs"]:
            # Use the NPC ID that was generated in the subgraph
            npc_id = npc.get("npc_id")
            if not npc_id:
                # Fallback if somehow missing
                npc_id = f"npc_{state['request_id']}_{npc['name'].replace(' ', '_').lower()}"

            # Extract role as string (handle both dict and string formats)
            npc_role = npc["role"]
            if isinstance(npc_role, dict):
                role_str = npc_role.get("type", str(npc_role))
            else:
                role_str = str(npc_role)

            # Skip if species_id or location_id is empty
            if not npc["species_id"] or npc["species_id"] == "" or not npc["level_3_location_id"]:
                logger.warning(f"Skipping Neo4j relationships for NPC {npc_id} - missing species_id or location_id")
                continue

            # Ensure backstory/description is not empty
            backstory = npc.get("backstory", "").strip()
            if not backstory:
                backstory = f"A {npc.get('species_name', 'character')} {role_str} whose story is connected to {npc.get('level_3_location_name', 'this location')}."

            session.run(
                """
                MATCH (w:World {id: $world_id})
                MERGE (npc:NPC {id: $npc_id})
                SET npc.name = $npc_name,
                    npc.role = $role,
                    npc.description = $description,
                    npc.species_id = $species_id,
                    npc.species_name = $species_name,
                    npc.campaign_id = $campaign_id

                // MERGE Species by name to avoid duplicates
                MERGE (s:Species {name: $species_name, world_id: $world_id})
                ON CREATE SET s.id = $species_id
                ON MATCH SET s.id = COALESCE(s.id, $species_id)
                MERGE (s)-[:IN_WORLD]->(w)

                // NPC location is Level 3 (Scene location) - should already exist from scene creation
                // Just link NPC to existing location, don't create PART_OF relationship to World
                MERGE (loc:Location {name: $location_name, world_id: $world_id})
                ON CREATE SET loc.id = $location_id
                ON MATCH SET loc.id = COALESCE(loc.id, $location_id)

                MERGE (npc)-[:IS_SPECIES]->(s)
                MERGE (npc)-[:LOCATED_AT]->(loc)
                """,
                world_id=state["world_id"],
                npc_id=npc_id,
                npc_name=npc["name"],
                role=role_str,
                description=backstory,
                campaign_id=campaign_id,
                species_id=npc["species_id"],
                species_name=npc.get("species_name", "Unknown Species"),
                location_id=npc["level_3_location_id"],
                location_name=npc.get("level_3_location_name", "Unknown Location")
            )
            relationships_created += 5

        # FIX: Create scene_id mapping for efficient lookups (moved before Knowledge/Items)
        # Map internal scene_id to the ID generated during workflow execution
        scene_id_map = {}  # internal scene_id -> persisted scene_id
        for quest in state["quests"]:
            quest_places = [p for p in state["places"] if p.get("parent_quest_id") == quest.get("quest_id", "")]
            for place in quest_places:
                place_scenes = [s for s in state["scenes"] if s.get("parent_place_id") == place.get("place_id", "")]
                for scene in place_scenes:
                    scene_internal_id = scene.get("scene_id", "")
                    if scene_internal_id:
                        # Use the scene ID that was generated during workflow execution
                        persisted_scene_id = scene.get("scene_id", f"scene_{state['request_id']}")
                        scene_id_map[scene_internal_id] = persisted_scene_id

        logger.info(f"Created scene_id_map with {len(scene_id_map)} mappings")

        # Knowledge Entities - create nodes and link to scenes
        for knowledge in state.get("knowledge_entities", []):
            knowledge_id = knowledge.get("knowledge_id")
            if not knowledge_id:
                continue

            # Create Knowledge node
            session.run(
                """
                MERGE (k:Knowledge {id: $knowledge_id})
                SET k.name = $name,
                    k.knowledge_type = $knowledge_type,
                    k.primary_dimension = $primary_dimension,
                    k.bloom_level_target = $bloom_level_target,
                    k.description = $description,
                    k.campaign_id = $campaign_id
                """,
                knowledge_id=knowledge_id,
                campaign_id=campaign_id,
                name=knowledge.get("name", "Unknown Knowledge"),
                knowledge_type=knowledge.get("knowledge_type", "skill"),
                primary_dimension=knowledge.get("primary_dimension", "intellectual"),
                bloom_level_target=knowledge.get("bloom_level_target", 3),
                description=knowledge.get("description", "")[:500]  # Truncate for Neo4j
            )

            # Link Knowledge to Scene using scene_id_map
            knowledge_scene_id = knowledge.get("scene_id")
            if knowledge_scene_id and knowledge_scene_id in scene_id_map:
                persisted_scene_id = scene_id_map[knowledge_scene_id]
                session.run(
                    """
                    MATCH (sc:Scene {id: $scene_id})
                    MATCH (k:Knowledge {id: $knowledge_id})
                    MERGE (sc)-[:PROVIDES]->(k)
                    """,
                    scene_id=persisted_scene_id,
                    knowledge_id=knowledge_id
                )
                relationships_created += 1
                logger.info(f"Linked Knowledge {knowledge_id} to Scene {persisted_scene_id}")

            # Link Knowledge acquisition methods to entities (NPCs, Challenges, Events)
            for acq_method in knowledge.get("acquisition_methods", []):
                entity_id = acq_method.get("entity_id")
                if entity_id:
                    session.run(
                        """
                        MATCH (k:Knowledge {id: $knowledge_id})
                        OPTIONAL MATCH (npc:NPC {id: $entity_id})
                        OPTIONAL MATCH (ch:Challenge {id: $entity_id})
                        OPTIONAL MATCH (e:Event {id: $entity_id})
                        FOREACH (_ IN CASE WHEN npc IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (npc)-[:TEACHES]->(k)
                        )
                        FOREACH (_ IN CASE WHEN ch IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (ch)-[:GRANTS]->(k)
                        )
                        FOREACH (_ IN CASE WHEN e IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (e)-[:GRANTS]->(k)
                        )
                        """,
                        knowledge_id=knowledge_id,
                        entity_id=entity_id
                    )
                    relationships_created += 1

        # Items - create nodes and link to scenes
        # FIX: Improved robustness - skip items without scene_id or ensure proper linking
        for item in state.get("item_entities", []):
            item_id = item.get("item_id")
            if not item_id:
                logger.warning("Item missing item_id, skipping")
                continue

            # FIX: Skip items without names (incomplete data)
            if not item.get("name"):
                logger.warning(f"Item {item_id} missing name - SKIPPING to prevent orphaned item")
                continue

            # Create Item node
            session.run(
                """
                MERGE (i:Item {id: $item_id})
                SET i.name = $name,
                    i.item_type = $item_type,
                    i.is_quest_critical = $is_quest_critical,
                    i.description = $description,
                    i.campaign_id = $campaign_id
                """,
                item_id=item_id,
                campaign_id=campaign_id,
                name=item.get("name", "Unknown Item"),
                item_type=item.get("item_type", "tool"),
                is_quest_critical=item.get("is_quest_critical", False),
                description=item.get("description", "")[:500]  # Truncate for Neo4j
            )

            # Link Item to Scene using scene_id_map
            item_scene_id = item.get("scene_id")
            if item_scene_id and item_scene_id in scene_id_map:
                persisted_scene_id = scene_id_map[item_scene_id]
                session.run(
                    """
                    MATCH (sc:Scene {id: $scene_id})
                    MATCH (i:Item {id: $item_id})
                    MERGE (sc)-[:CONTAINS_ITEM]->(i)
                    """,
                    scene_id=persisted_scene_id,
                    item_id=item_id
                )
                relationships_created += 1
                logger.info(f"Linked Item {item_id} to Scene {persisted_scene_id}")

            # Link Item acquisition methods to entities
            for acq_method in item.get("acquisition_methods", []):
                entity_id = acq_method.get("entity_id")
                if entity_id:
                    session.run(
                        """
                        MATCH (i:Item {id: $item_id})
                        OPTIONAL MATCH (npc:NPC {id: $entity_id})
                        OPTIONAL MATCH (ch:Challenge {id: $entity_id})
                        FOREACH (_ IN CASE WHEN npc IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (npc)-[:GIVES]->(i)
                        )
                        FOREACH (_ IN CASE WHEN ch IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (ch)-[:REWARDS]->(i)
                        )
                        """,
                        item_id=item_id,
                        entity_id=entity_id
                    )
                    relationships_created += 1

        # Challenges - create nodes and link to scenes
        for idx, challenge in enumerate(state.get("challenges", [])):
            # FIX 2: Use original entity ID
            challenge_id = challenge.get("challenge_id", f"challenge_{state['request_id']}_{idx}")

            # FIX 4: Create Challenge node with campaign_id
            session.run(
                """
                MERGE (ch:Challenge {id: $challenge_id})
                SET ch.name = $name,
                    ch.challenge_type = $challenge_type,
                    ch.difficulty = $difficulty,
                    ch.blooms_level = $blooms_level,
                    ch.description = $description,
                    ch.campaign_id = $campaign_id
                """,
                challenge_id=challenge_id,
                campaign_id=campaign_id,
                name=challenge.get("name", "Unknown Challenge"),
                challenge_type=challenge.get("challenge_type", "combat"),
                difficulty=challenge.get("difficulty", "Medium"),
                blooms_level=challenge.get("blooms_level", 3),
                description=challenge.get("description", "")[:500]
            )

            # FIX 5: Link Challenge to Scene using scene_id from entity
            challenge_scene_id = challenge.get("scene_id")
            if challenge_scene_id and challenge_scene_id in scene_id_map:
                persisted_scene_id = scene_id_map[challenge_scene_id]
                session.run(
                    """
                    MATCH (sc:Scene {id: $scene_id})
                    MATCH (ch:Challenge {id: $challenge_id})
                    MERGE (sc)-[:CONTAINS_CHALLENGE]->(ch)
                    """,
                    scene_id=persisted_scene_id,
                    challenge_id=challenge_id
                )
                relationships_created += 1
                logger.info(f"Linked Challenge {challenge_id} to Scene {persisted_scene_id}")

        # Discoveries - create nodes and link to scenes
        for idx, discovery in enumerate(state.get("discoveries", [])):
            # FIX 2: Use original entity ID
            discovery_id = discovery.get("discovery_id", f"discovery_{state['request_id']}_{idx}")

            # FIX 4: Create Discovery node with campaign_id
            session.run(
                """
                MERGE (d:Discovery {id: $discovery_id})
                SET d.name = $name,
                    d.knowledge_type = $knowledge_type,
                    d.blooms_level = $blooms_level,
                    d.description = $description,
                    d.campaign_id = $campaign_id
                """,
                discovery_id=discovery_id,
                campaign_id=campaign_id,
                name=discovery.get("name", "Unknown Discovery"),
                knowledge_type=discovery.get("knowledge_type", "lore"),
                blooms_level=discovery.get("blooms_level", 2),
                description=discovery.get("description", "")[:500]
            )

            # FIX 5: Link Discovery to Scene using scene_id from entity
            discovery_scene_id = discovery.get("scene_id")
            if discovery_scene_id and discovery_scene_id in scene_id_map:
                persisted_scene_id = scene_id_map[discovery_scene_id]
                session.run(
                    """
                    MATCH (sc:Scene {id: $scene_id})
                    MATCH (d:Discovery {id: $discovery_id})
                    MERGE (sc)-[:CONTAINS_DISCOVERY]->(d)
                    """,
                    scene_id=persisted_scene_id,
                    discovery_id=discovery_id
                )
                relationships_created += 1
                logger.info(f"Linked Discovery {discovery_id} to Scene {persisted_scene_id}")

        # Events - create nodes and link to scenes
        for idx, event in enumerate(state.get("events", [])):
            # FIX 2: Use original entity ID
            event_id = event.get("event_id", f"event_{state['request_id']}_{idx}")

            # FIX 4: Create Event node with campaign_id
            session.run(
                """
                MERGE (e:Event {id: $event_id})
                SET e.name = $name,
                    e.event_type = $event_type,
                    e.description = $description,
                    e.campaign_id = $campaign_id
                """,
                event_id=event_id,
                campaign_id=campaign_id,
                name=event.get("name", "Unknown Event"),
                event_type=event.get("event_type", "story"),
                description=event.get("description", "")[:500]
            )

            # FIX 5: Link Event to Scene using scene_id from entity
            event_scene_id = event.get("scene_id")
            if event_scene_id and event_scene_id in scene_id_map:
                persisted_scene_id = scene_id_map[event_scene_id]
                session.run(
                    """
                    MATCH (sc:Scene {id: $scene_id})
                    MATCH (e:Event {id: $event_id})
                    MERGE (sc)-[:CONTAINS_EVENT]->(e)
                    """,
                    scene_id=persisted_scene_id,
                    event_id=event_id
                )
                relationships_created += 1
                logger.info(f"Linked Event {event_id} to Scene {persisted_scene_id}")

        logger.info(f"Created {len(state.get('challenges', []))} Challenges, {len(state.get('discoveries', []))} Discoveries, {len(state.get('events', []))} Events in Neo4j")

        # Rubrics - create nodes and link to entities
        # IMPORTANT: Process rubrics AFTER all entities (NPCs, Challenges, Discoveries, Events) are created
        # FIX: Skip rubrics with missing entity_id or entities not found in Neo4j to prevent orphaned rubrics
        for rubric in state.get("rubrics", []):
            rubric_id = rubric.get("rubric_id")
            entity_id = rubric.get("entity_id")

            if not rubric_id:
                logger.warning("Rubric missing rubric_id, skipping")
                continue

            if not entity_id:
                logger.warning(f"Rubric {rubric_id} ({rubric.get('interaction_name', 'unknown')}) missing entity_id - SKIPPING to prevent orphaned rubric")
                continue  # FIX: Skip instead of creating orphaned rubric

            # First, check if the entity exists in Neo4j before creating the rubric
            # This prevents orphaned rubrics
            entity_check = session.run(
                """
                OPTIONAL MATCH (npc:NPC {id: $entity_id})
                OPTIONAL MATCH (ch:Challenge {id: $entity_id})
                OPTIONAL MATCH (d:Discovery {id: $entity_id})
                OPTIONAL MATCH (e:Event {id: $entity_id})

                RETURN
                    CASE WHEN npc IS NOT NULL THEN 'npc'
                         WHEN ch IS NOT NULL THEN 'challenge'
                         WHEN d IS NOT NULL THEN 'discovery'
                         WHEN e IS NOT NULL THEN 'event'
                         ELSE NULL
                    END as entity_type
                """,
                entity_id=entity_id
            )

            # Check if entity was found
            entity_record = entity_check.single()
            if not entity_record or not entity_record["entity_type"]:
                logger.warning(f"Rubric {rubric_id} ({rubric.get('interaction_name', 'unknown')}) - entity {entity_id} not found in Neo4j - SKIPPING to prevent orphaned rubric")
                continue  # FIX: Skip instead of creating orphaned rubric

            # Entity exists, safe to create rubric and link it
            # Create Rubric node
            session.run(
                """
                MERGE (r:Rubric {id: $rubric_id})
                SET r.rubric_type = $rubric_type,
                    r.campaign_id = $campaign_id,
                    r.interaction_name = $interaction_name,
                    r.primary_dimension = $primary_dimension
                """,
                rubric_id=rubric_id,
                campaign_id=campaign_id,
                rubric_type=rubric.get("rubric_type", "evaluation"),
                interaction_name=rubric.get("interaction_name", "Unknown Interaction"),
                primary_dimension=rubric.get("primary_dimension", "intellectual")
            )

            # Link Rubric to its entity (NPC, Challenge, Discovery, Event)
            session.run(
                """
                MATCH (r:Rubric {id: $rubric_id})
                OPTIONAL MATCH (npc:NPC {id: $entity_id})
                OPTIONAL MATCH (ch:Challenge {id: $entity_id})
                OPTIONAL MATCH (d:Discovery {id: $entity_id})
                OPTIONAL MATCH (e:Event {id: $entity_id})

                FOREACH (_ IN CASE WHEN npc IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (npc)-[:EVALUATED_BY]->(r)
                )
                FOREACH (_ IN CASE WHEN ch IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (ch)-[:EVALUATED_BY]->(r)
                )
                FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (d)-[:EVALUATED_BY]->(r)
                )
                FOREACH (_ IN CASE WHEN e IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (e)-[:EVALUATED_BY]->(r)
                )
                """,
                rubric_id=rubric_id,
                entity_id=entity_id
            )
            relationships_created += 1
            logger.info(f"Created rubric {rubric_id} and linked to {entity_record['entity_type']} {entity_id}")

        logger.info(f"Created {relationships_created} Neo4j relationships (including Knowledge, Items, and Rubrics)")

        # NEW: Persist objective hierarchy and assignments
        logger.info(f"Persisting objective hierarchy to Neo4j for campaign: {campaign_id}...")
        logger.info(f"State has final_campaign_id: {state.get('final_campaign_id')}")
        try:
            await persist_objective_hierarchy_to_neo4j(state, neo4j_driver)
            logger.info("✓ Objective hierarchy persisted")
        except Exception as e:
            logger.error(f"Failed to persist objective hierarchy: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Non-critical, continue

        # NEW: Persist dimensional development
        logger.info("Persisting dimensional development to Neo4j...")
        try:
            await persist_dimensional_objectives_to_neo4j(state, neo4j_driver)
            logger.info("✓ Dimensional development persisted")
        except Exception as e:
            logger.error(f"Failed to persist dimensional development: {str(e)}")
            # Non-critical, continue

        # NEW: Persist scene-objective assignments
        logger.info("Persisting scene-objective assignments to Neo4j...")
        try:
            await persist_scene_assignments_to_neo4j(state, neo4j_driver)
            logger.info("✓ Scene assignments persisted")
        except Exception as e:
            logger.error(f"Failed to persist scene assignments: {str(e)}")
            # Non-critical, continue

        # NEW: Persist detailed acquisition paths
        logger.info("Persisting acquisition paths to Neo4j...")
        try:
            await persist_acquisition_paths_to_neo4j(state, neo4j_driver)
            logger.info("✓ Acquisition paths persisted")
        except Exception as e:
            logger.error(f"Failed to persist acquisition paths: {str(e)}")
            # Non-critical, continue

        # NEW: Analyze and persist redundancy information
        logger.info("Analyzing redundancy in Neo4j...")
        try:
            await persist_redundancy_analysis_to_neo4j(state, neo4j_driver)
            logger.info("✓ Redundancy analysis complete")
        except Exception as e:
            logger.error(f"Failed to analyze redundancy: {str(e)}")
            # Non-critical, continue

    return relationships_created


async def update_postgres_analytics(state: CampaignWorkflowState, campaign_id: str) -> int:
    """
    Update PostgreSQL with campaign analytics data

    Returns:
        Number of records created
    """
    # TODO: Implement PostgreSQL analytics tables and updates
    # For now, return placeholder count
    records_count = 0

    logger.info(f"Created {records_count} PostgreSQL analytics records")

    return records_count
