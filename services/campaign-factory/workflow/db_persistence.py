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
    if not mongo_db:
        init_db_connections()

    campaign_id = f"campaign_{state.request_id}"

    try:
        # Create campaign document
        campaign_doc = {
            "_id": campaign_id,
            "name": state.campaign_core["name"],
            "plot": state.campaign_core["plot"],
            "storyline": state.campaign_core["storyline"],
            "primary_objectives": state.campaign_core["primary_objectives"],
            "universe_id": state.universe_id,
            "world_id": state.world_id,
            "region_id": state.region_id,
            "genre": state.genre,
            "character_id": state.character_id,
            "user_id": state.user_id,
            "difficulty_level": state.campaign_core["difficulty_level"],
            "estimated_duration_hours": state.campaign_core["estimated_duration_hours"],
            "target_blooms_level": state.campaign_core["target_blooms_level"],
            "status": "active",
            "created_at": state.created_at,
            "quest_ids": [],
            "stats": {
                "num_quests": len(state.quests),
                "num_places": len(state.places),
                "num_scenes": len(state.scenes),
                "num_npcs": len(state.npcs),
                "new_species_created": len(state.new_species_ids),
                "new_locations_created": len(state.new_location_ids)
            }
        }

        mongo_db.campaigns.insert_one(campaign_doc)
        logger.info(f"Created campaign document: {campaign_id}")

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

    for quest_idx, quest in enumerate(state.quests):
        quest_id = f"quest_{state.request_id}_{quest_idx}"

        # Find places for this quest
        quest_places = [p for p in state.places if p.get("parent_quest_id") == quest.get("quest_id", "")]

        place_ids = []
        for place in quest_places:
            place_id = f"place_{state.request_id}_{len(place_ids)}"

            # Find scenes for this place
            place_scenes = [s for s in state.scenes if s.get("parent_place_id") == place.get("place_id", "")]

            scene_ids = []
            for scene in place_scenes:
                scene_id = f"scene_{state.request_id}_{len(scene_ids)}"

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
                    "required_knowledge": scene.get("required_knowledge", []),
                    "required_items": scene.get("required_items", []),
                    "order_sequence": scene.get("order_sequence", 0),
                    "created_at": datetime.utcnow().isoformat()
                }

                mongo_db.scenes.insert_one(scene_doc)
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
                "created_at": datetime.utcnow().isoformat()
            }

            mongo_db.places.insert_one(place_doc)
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

        mongo_db.quests.insert_one(quest_doc)
        quest_ids.append(quest_id)

        logger.info(f"Persisted quest: {quest_id} with {len(place_ids)} places")

    return quest_ids


async def persist_npcs(state: CampaignWorkflowState):
    """
    Persist NPCs to world's NPC pool (world-permanent)
    """
    for npc in state.npcs:
        npc_id = f"npc_{state.request_id}_{npc['name'].replace(' ', '_').lower()}"

        npc_doc = {
            "_id": npc_id,
            "name": npc["name"],
            "species_id": npc["species_id"],
            "species_name": npc["species_name"],
            "personality_traits": npc["personality_traits"],
            "role": npc["role"],
            "dialogue_style": npc["dialogue_style"],
            "backstory": npc["backstory"],
            "world_id": state.world_id,
            "level_3_location_id": npc["level_3_location_id"],
            "is_world_permanent": npc.get("is_world_permanent", True),
            "origin_campaign_id": f"campaign_{state.request_id}",
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.npcs.insert_one(npc_doc)

    logger.info(f"Persisted {len(state.npcs)} NPCs to world pool")


async def persist_scene_elements(state: CampaignWorkflowState):
    """
    Persist discoveries, events, challenges
    """
    # Discoveries
    for idx, discovery in enumerate(state.discoveries):
        discovery_id = f"discovery_{state.request_id}_{idx}"

        discovery_doc = {
            "_id": discovery_id,
            "name": discovery["name"],
            "description": discovery["description"],
            "knowledge_type": discovery["knowledge_type"],
            "blooms_level": discovery["blooms_level"],
            "unlocks_scenes": discovery.get("unlocks_scenes", []),
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.discoveries.insert_one(discovery_doc)

    # Events
    for idx, event in enumerate(state.events):
        event_id = f"event_{state.request_id}_{idx}"

        event_doc = {
            "_id": event_id,
            "name": event["name"],
            "description": event["description"],
            "event_type": event["event_type"],
            "trigger_conditions": event.get("trigger_conditions", {}),
            "outcomes": event.get("outcomes", []),
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.events.insert_one(event_doc)

    # Challenges
    for idx, challenge in enumerate(state.challenges):
        challenge_id = f"challenge_{state.request_id}_{idx}"

        challenge_doc = {
            "_id": challenge_id,
            "name": challenge["name"],
            "description": challenge["description"],
            "challenge_type": challenge["challenge_type"],
            "difficulty": challenge["difficulty"],
            "blooms_level": challenge["blooms_level"],
            "success_rewards": challenge.get("success_rewards", {}),
            "failure_consequences": challenge.get("failure_consequences", {}),
            "created_at": datetime.utcnow().isoformat()
        }

        mongo_db.challenges.insert_one(challenge_doc)

    logger.info(f"Persisted {len(state.discoveries)} discoveries, {len(state.events)} events, {len(state.challenges)} challenges")


async def create_neo4j_relationships(state: CampaignWorkflowState, campaign_id: str) -> int:
    """
    Create Neo4j relationships for campaign structure

    Returns:
        Number of relationships created
    """
    if not neo4j_driver:
        init_db_connections()

    relationships_created = 0

    with neo4j_driver.session() as session:
        # Character participates in Campaign
        session.run(
            """
            MATCH (c:Character {id: $character_id})
            MATCH (camp:Campaign {id: $campaign_id})
            MERGE (c)-[:PARTICIPATES_IN]->(camp)
            """,
            character_id=state.character_id,
            campaign_id=campaign_id
        )
        relationships_created += 1

        # Campaign takes place in World and Region
        session.run(
            """
            MATCH (camp:Campaign {id: $campaign_id})
            MATCH (w:World {id: $world_id})
            MATCH (r:Region {id: $region_id})
            MERGE (camp)-[:TAKES_PLACE_IN]->(w)
            MERGE (camp)-[:LOCATED_IN]->(r)
            """,
            campaign_id=campaign_id,
            world_id=state.world_id,
            region_id=state.region_id
        )
        relationships_created += 2

        # Campaign contains Quests
        for quest_idx, quest in enumerate(state.quests):
            quest_id = f"quest_{state.request_id}_{quest_idx}"

            session.run(
                """
                MATCH (camp:Campaign {id: $campaign_id})
                MERGE (q:Quest {id: $quest_id})
                SET q.name = $quest_name, q.order_sequence = $order_sequence
                MERGE (camp)-[:CONTAINS]->(q)
                MERGE (q)-[:LOCATED_AT]->(loc:Location {id: $location_id})
                """,
                campaign_id=campaign_id,
                quest_id=quest_id,
                quest_name=quest["name"],
                order_sequence=quest["order_sequence"],
                location_id=quest["level_1_location_id"]
            )
            relationships_created += 3

        # NPCs relationships with species and locations
        for npc in state.npcs:
            npc_id = f"npc_{state.request_id}_{npc['name'].replace(' ', '_').lower()}"

            session.run(
                """
                MERGE (npc:NPC {id: $npc_id})
                SET npc.name = $npc_name, npc.role = $role
                MERGE (s:Species {id: $species_id})
                MERGE (loc:Location {id: $location_id})
                MERGE (npc)-[:IS_SPECIES]->(s)
                MERGE (npc)-[:LOCATED_AT]->(loc)
                """,
                npc_id=npc_id,
                npc_name=npc["name"],
                role=npc["role"],
                species_id=npc["species_id"],
                location_id=npc["level_3_location_id"]
            )
            relationships_created += 3

    logger.info(f"Created {relationships_created} Neo4j relationships")

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
