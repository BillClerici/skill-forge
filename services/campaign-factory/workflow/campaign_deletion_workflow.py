"""
Campaign Deletion Workflow
LangGraph workflow for comprehensive campaign deletion across MongoDB, Neo4j, and PostgreSQL
"""
import os
import logging
from typing import Dict, Any, List, TypedDict
from langgraph.graph import StateGraph, END
from pymongo import MongoClient
from neo4j import GraphDatabase
import psycopg2
from datetime import datetime

logger = logging.getLogger(__name__)

# Database connections
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['skillforge']

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'skillforge')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')


class CampaignDeletionState(TypedDict, total=False):
    """State for campaign deletion workflow"""
    campaign_id: str
    campaign_name: str
    is_new_format: bool

    # Deletion tracking
    deleted_quests: List[str]
    deleted_places: List[str]
    deleted_scenes: List[str]
    deleted_npcs: List[str]
    deleted_discoveries: List[str]
    deleted_events: List[str]
    deleted_challenges: List[str]
    deleted_knowledge: List[str]
    deleted_items: List[str]
    deleted_rubrics: List[str]

    # Status tracking
    mongodb_deleted: bool
    neo4j_deleted: bool
    postgres_deleted: bool

    # Error tracking
    errors: List[str]
    warnings: List[str]

    # Audit
    deleted_at: str
    deletion_log: List[Dict[str, Any]]


async def fetch_campaign_data_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Fetch campaign data to determine format and structure
    """
    try:
        campaign_id = state['campaign_id']
        logger.info(f"Fetching campaign data for deletion: {campaign_id}")

        # Check new format first
        campaign = db.campaigns.find_one({'_id': campaign_id})
        if campaign:
            state['is_new_format'] = True
            state['campaign_name'] = campaign.get('campaign_name', 'Unknown')
            logger.info(f"Found new format campaign: {state['campaign_name']}")
        else:
            # Check old format
            campaign = db.campaign_state.find_one({'_id': campaign_id})
            if campaign:
                state['is_new_format'] = False
                state['campaign_name'] = campaign.get('campaign_name', 'Unknown')
                logger.info(f"Found old format campaign: {state['campaign_name']}")
            else:
                error_msg = f"Campaign not found: {campaign_id}"
                logger.error(error_msg)
                state['errors'] = state.get('errors', []) + [error_msg]

        state['deleted_at'] = datetime.utcnow().isoformat()

    except Exception as e:
        logger.error(f"Error fetching campaign data: {e}")
        state['errors'] = state.get('errors', []) + [str(e)]

    return state


async def delete_mongodb_campaign_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Delete campaign and all related entities from MongoDB
    """
    try:
        campaign_id = state['campaign_id']
        is_new_format = state.get('is_new_format', False)

        logger.info(f"Starting MongoDB deletion for campaign: {campaign_id}")

        if is_new_format:
            # Delete from new format collections

            # 1. Find all quests for this campaign
            quests = list(db.quests.find({'campaign_id': campaign_id}))
            quest_ids = [q['_id'] for q in quests]
            state['deleted_quests'] = quest_ids
            logger.info(f"Found {len(quest_ids)} quests to delete")

            # 2. Find all places for these quests
            places = list(db.places.find({'quest_id': {'$in': quest_ids}})) if quest_ids else []
            place_ids = [p['_id'] for p in places]
            state['deleted_places'] = place_ids
            logger.info(f"Found {len(place_ids)} places to delete")

            # 3. Find all scenes for these places
            scenes = list(db.scenes.find({'place_id': {'$in': place_ids}})) if place_ids else []
            scene_ids = [s['_id'] for s in scenes]
            state['deleted_scenes'] = scene_ids
            logger.info(f"Found {len(scene_ids)} scenes to delete")

            # 4. Find all scene elements
            if scene_ids:
                npcs = list(db.npcs.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_npcs'] = [n['_id'] for n in npcs]
                logger.info(f"Found {len(state['deleted_npcs'])} NPCs to delete")

                discoveries = list(db.discoveries.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_discoveries'] = [d['_id'] for d in discoveries]
                logger.info(f"Found {len(state['deleted_discoveries'])} discoveries to delete")

                events = list(db.events.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_events'] = [e['_id'] for e in events]
                logger.info(f"Found {len(state['deleted_events'])} events to delete")

                challenges = list(db.challenges.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_challenges'] = [c['_id'] for c in challenges]
                logger.info(f"Found {len(state['deleted_challenges'])} challenges to delete")

                knowledge = list(db.knowledge.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_knowledge'] = [k['_id'] for k in knowledge]
                logger.info(f"Found {len(state['deleted_knowledge'])} knowledge entities to delete")

                items = list(db.items.find({'level_3_location_id': {'$in': scene_ids}}))
                state['deleted_items'] = [i['_id'] for i in items]
                logger.info(f"Found {len(state['deleted_items'])} items to delete")

            # 5. Find all rubrics for this campaign
            rubrics = list(db.rubrics.find({'campaign_id': campaign_id}))
            state['deleted_rubrics'] = [r['_id'] for r in rubrics]
            logger.info(f"Found {len(state['deleted_rubrics'])} rubrics to delete")

            # Now perform deletions in reverse order (leaf to root)

            # Delete scene elements
            if scene_ids:
                db.npcs.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_npcs', []))} NPCs")

                db.discoveries.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_discoveries', []))} discoveries")

                db.events.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_events', []))} events")

                db.challenges.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_challenges', []))} challenges")

                db.knowledge.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_knowledge', []))} knowledge entities")

                db.items.delete_many({'level_3_location_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(state.get('deleted_items', []))} items")

            # Delete rubrics
            db.rubrics.delete_many({'campaign_id': campaign_id})
            logger.info(f"Deleted {len(state.get('deleted_rubrics', []))} rubrics")

            # Delete scenes
            if scene_ids:
                db.scenes.delete_many({'_id': {'$in': scene_ids}})
                logger.info(f"Deleted {len(scene_ids)} scenes")

            # Delete places
            if place_ids:
                db.places.delete_many({'_id': {'$in': place_ids}})
                logger.info(f"Deleted {len(place_ids)} places")

            # Delete quests
            if quest_ids:
                db.quests.delete_many({'_id': {'$in': quest_ids}})
                logger.info(f"Deleted {len(quest_ids)} quests")

            # Delete campaign
            db.campaigns.delete_one({'_id': campaign_id})
            logger.info(f"Deleted campaign: {campaign_id}")

        else:
            # Delete old format campaign
            db.campaign_state.delete_one({'_id': campaign_id})
            logger.info(f"Deleted old format campaign: {campaign_id}")

        state['mongodb_deleted'] = True
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'mongodb_deletion',
            'status': 'success',
            'details': {
                'quests': len(state.get('deleted_quests', [])),
                'places': len(state.get('deleted_places', [])),
                'scenes': len(state.get('deleted_scenes', [])),
                'npcs': len(state.get('deleted_npcs', [])),
                'discoveries': len(state.get('deleted_discoveries', [])),
                'events': len(state.get('deleted_events', [])),
                'challenges': len(state.get('deleted_challenges', [])),
                'knowledge': len(state.get('deleted_knowledge', [])),
                'items': len(state.get('deleted_items', [])),
                'rubrics': len(state.get('deleted_rubrics', []))
            }
        }]

    except Exception as e:
        logger.error(f"Error deleting from MongoDB: {e}")
        state['errors'] = state.get('errors', []) + [f"MongoDB deletion failed: {str(e)}"]
        state['mongodb_deleted'] = False

    return state


async def delete_neo4j_entities_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Delete all campaign-related entities from Neo4j
    """
    try:
        campaign_id = state['campaign_id']
        logger.info(f"Starting Neo4j deletion for campaign: {campaign_id}")

        with neo4j_driver.session() as session:
            # Delete all entities associated with this campaign
            # This includes NPCs, Locations (scenes/places), Knowledge, Items, etc.

            # 1. Delete NPC nodes
            if state.get('deleted_npcs'):
                result = session.run("""
                    MATCH (n:NPC)
                    WHERE n.id IN $npc_ids
                    DETACH DELETE n
                    RETURN count(n) as deleted_count
                """, npc_ids=state['deleted_npcs'])
                npc_count = result.single()['deleted_count']
                logger.info(f"Deleted {npc_count} NPC nodes from Neo4j")

            # 2. Delete Location nodes (scenes and places)
            location_ids = state.get('deleted_scenes', []) + state.get('deleted_places', [])
            if location_ids:
                result = session.run("""
                    MATCH (l:Location)
                    WHERE l.id IN $location_ids
                    DETACH DELETE l
                    RETURN count(l) as deleted_count
                """, location_ids=location_ids)
                location_count = result.single()['deleted_count']
                logger.info(f"Deleted {location_count} Location nodes from Neo4j")

            # 3. Delete Knowledge nodes
            if state.get('deleted_knowledge'):
                result = session.run("""
                    MATCH (k:Knowledge)
                    WHERE k.id IN $knowledge_ids
                    DETACH DELETE k
                    RETURN count(k) as deleted_count
                """, knowledge_ids=state['deleted_knowledge'])
                knowledge_count = result.single()['deleted_count']
                logger.info(f"Deleted {knowledge_count} Knowledge nodes from Neo4j")

            # 4. Delete Item nodes
            if state.get('deleted_items'):
                result = session.run("""
                    MATCH (i:Item)
                    WHERE i.id IN $item_ids
                    DETACH DELETE i
                    RETURN count(i) as deleted_count
                """, item_ids=state['deleted_items'])
                item_count = result.single()['deleted_count']
                logger.info(f"Deleted {item_count} Item nodes from Neo4j")

            # 5. Delete Discovery nodes
            if state.get('deleted_discoveries'):
                result = session.run("""
                    MATCH (d:Discovery)
                    WHERE d.id IN $discovery_ids
                    DETACH DELETE d
                    RETURN count(d) as deleted_count
                """, discovery_ids=state['deleted_discoveries'])
                discovery_count = result.single()['deleted_count']
                logger.info(f"Deleted {discovery_count} Discovery nodes from Neo4j")

            # 6. Delete Event nodes
            if state.get('deleted_events'):
                result = session.run("""
                    MATCH (e:Event)
                    WHERE e.id IN $event_ids
                    DETACH DELETE e
                    RETURN count(e) as deleted_count
                """, event_ids=state['deleted_events'])
                event_count = result.single()['deleted_count']
                logger.info(f"Deleted {event_count} Event nodes from Neo4j")

            # 7. Delete Challenge nodes
            if state.get('deleted_challenges'):
                result = session.run("""
                    MATCH (c:Challenge)
                    WHERE c.id IN $challenge_ids
                    DETACH DELETE c
                    RETURN count(c) as deleted_count
                """, challenge_ids=state['deleted_challenges'])
                challenge_count = result.single()['deleted_count']
                logger.info(f"Deleted {challenge_count} Challenge nodes from Neo4j")

            # 8. Finally, delete the Campaign node and all its remaining relationships
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                DETACH DELETE c
                RETURN count(c) as deleted_count
            """, campaign_id=campaign_id)
            campaign_count = result.single()['deleted_count']
            logger.info(f"Deleted {campaign_count} Campaign node from Neo4j")

        state['neo4j_deleted'] = True
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'neo4j_deletion',
            'status': 'success',
            'details': 'All campaign entities and relationships deleted'
        }]

    except Exception as e:
        logger.error(f"Error deleting from Neo4j: {e}")
        state['errors'] = state.get('errors', []) + [f"Neo4j deletion failed: {str(e)}"]
        state['neo4j_deleted'] = False

    return state


async def delete_postgres_records_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Delete campaign-related records from PostgreSQL
    """
    try:
        campaign_id = state['campaign_id']
        logger.info(f"Starting PostgreSQL deletion for campaign: {campaign_id}")

        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )

        try:
            with conn.cursor() as cursor:
                # Delete player-campaign associations if they exist
                # This depends on your PostgreSQL schema - adjust table names as needed

                # Example: Delete from player_campaigns junction table
                cursor.execute("""
                    DELETE FROM campaigns_playercampaign
                    WHERE campaign_id = %s
                """, (campaign_id,))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} player-campaign associations from PostgreSQL")

                conn.commit()

            state['postgres_deleted'] = True
            state['deletion_log'] = state.get('deletion_log', []) + [{
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'postgres_deletion',
                'status': 'success',
                'details': f'Deleted {deleted_count} records'
            }]

        finally:
            conn.close()

    except psycopg2.Error as e:
        # PostgreSQL deletion is non-critical - campaign may not have player associations
        logger.warning(f"PostgreSQL deletion warning: {e}")
        state['warnings'] = state.get('warnings', []) + [f"PostgreSQL deletion warning: {str(e)}"]
        state['postgres_deleted'] = True  # Mark as successful even with warning

    except Exception as e:
        logger.error(f"Error deleting from PostgreSQL: {e}")
        state['errors'] = state.get('errors', []) + [f"PostgreSQL deletion failed: {str(e)}"]
        state['postgres_deleted'] = False

    return state


def route_after_fetch(state: CampaignDeletionState) -> str:
    """Route after fetching campaign data"""
    if state.get('errors'):
        return 'failed'
    return 'delete_mongodb'


def route_after_mongodb(state: CampaignDeletionState) -> str:
    """Route after MongoDB deletion"""
    if not state.get('mongodb_deleted', False):
        return 'failed'
    return 'delete_neo4j'


def route_after_neo4j(state: CampaignDeletionState) -> str:
    """Route after Neo4j deletion"""
    # Continue even if Neo4j fails - MongoDB is primary
    return 'delete_postgres'


def route_after_postgres(state: CampaignDeletionState) -> str:
    """Route after PostgreSQL deletion"""
    # Check if critical deletions succeeded
    if state.get('mongodb_deleted', False):
        return 'completed'
    return 'failed'


def create_campaign_deletion_workflow() -> StateGraph:
    """
    Create LangGraph workflow for comprehensive campaign deletion

    Workflow Steps:
    1. Fetch campaign data and determine format
    2. Delete from MongoDB (all collections, cascade)
    3. Delete from Neo4j (all entities and relationships)
    4. Delete from PostgreSQL (player associations)
    """
    workflow = StateGraph(CampaignDeletionState)

    # Add nodes
    workflow.add_node('fetch_campaign', fetch_campaign_data_node)
    workflow.add_node('delete_mongodb', delete_mongodb_campaign_node)
    workflow.add_node('delete_neo4j', delete_neo4j_entities_node)
    workflow.add_node('delete_postgres', delete_postgres_records_node)

    # Set entry point
    workflow.set_entry_point('fetch_campaign')

    # Add conditional edges
    workflow.add_conditional_edges(
        'fetch_campaign',
        route_after_fetch,
        {
            'delete_mongodb': 'delete_mongodb',
            'failed': END
        }
    )

    workflow.add_conditional_edges(
        'delete_mongodb',
        route_after_mongodb,
        {
            'delete_neo4j': 'delete_neo4j',
            'failed': END
        }
    )

    workflow.add_conditional_edges(
        'delete_neo4j',
        route_after_neo4j,
        {
            'delete_postgres': 'delete_postgres'
        }
    )

    workflow.add_conditional_edges(
        'delete_postgres',
        route_after_postgres,
        {
            'completed': END,
            'failed': END
        }
    )

    return workflow.compile()


# Export for use in Django views
__all__ = ['create_campaign_deletion_workflow', 'CampaignDeletionState']
