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
    user_id: str
    request_id: str
    is_new_format: bool
    world_id: str

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

    # Species and Location cleanup tracking
    campaign_created_species: List[str]  # Species IDs created by this campaign
    campaign_created_locations: List[Dict[str, Any]]  # Locations created by this campaign
    species_to_remove: List[str]  # Species with no other campaign dependencies
    locations_to_remove: List[str]  # Locations with no other campaign dependencies
    species_dependencies: Dict[str, List[str]]  # Species ID -> List of campaign IDs using it
    location_dependencies: Dict[str, List[str]]  # Location ID -> List of campaign IDs using it

    # Status tracking
    mongodb_deleted: bool
    neo4j_deleted: bool
    postgres_deleted: bool
    species_cleaned: bool
    locations_cleaned: bool

    # Error tracking
    errors: List[str]
    warnings: List[str]

    # Progress tracking
    current_phase: str  # fetch, delete_entities, cleanup_species, cleanup_locations, finalize
    progress_percentage: int
    step_progress: int
    status_message: str

    # Audit trail
    deleted_at: str
    deletion_log: List[Dict[str, Any]]


async def fetch_campaign_data_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Fetch campaign data to determine format and structure
    """
    try:
        campaign_id = state['campaign_id']
        logger.info(f"Fetching campaign data for deletion: {campaign_id}")

        # Update progress
        state['current_phase'] = 'fetch'
        state['progress_percentage'] = 5
        state['step_progress'] = 0
        state['status_message'] = 'Analyzing campaign structure...'

        # Check new format first
        campaign = db.campaigns.find_one({'_id': campaign_id})
        if campaign:
            state['is_new_format'] = True
            state['campaign_name'] = campaign.get('name', 'Unknown')
            state['world_id'] = campaign.get('world_id', '')

            # Track species and locations created by this campaign
            state['campaign_created_species'] = campaign.get('new_species_ids', [])
            state['campaign_created_locations'] = campaign.get('new_locations', [])

            logger.info(f"Found new format campaign: {state['campaign_name']}")
            logger.info(f"Campaign created {len(state['campaign_created_species'])} species and {len(state['campaign_created_locations'])} locations")
        else:
            # Check old format
            campaign = db.campaign_state.find_one({'_id': campaign_id})
            if campaign:
                state['is_new_format'] = False
                state['campaign_name'] = campaign.get('campaign_name', 'Unknown')
                state['world_id'] = campaign.get('world_ids', [''])[0] if campaign.get('world_ids') else ''
                state['campaign_created_species'] = []
                state['campaign_created_locations'] = []
                logger.info(f"Found old format campaign: {state['campaign_name']}")
            else:
                error_msg = f"Campaign not found: {campaign_id}"
                logger.error(error_msg)
                state['errors'] = state.get('errors', []) + [error_msg]

        state['deleted_at'] = datetime.utcnow().isoformat()

        # Add audit log entry
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'fetch_campaign_data',
            'status': 'success' if not state.get('errors') else 'failed',
            'details': {
                'campaign_name': state.get('campaign_name'),
                'is_new_format': state.get('is_new_format'),
                'created_species_count': len(state.get('campaign_created_species', [])),
                'created_locations_count': len(state.get('campaign_created_locations', []))
            }
        }]

    except Exception as e:
        logger.error(f"Error fetching campaign data: {e}")
        state['errors'] = state.get('errors', []) + [str(e)]
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'fetch_campaign_data',
            'status': 'error',
            'details': {'error': str(e)}
        }]

    return state


async def delete_mongodb_campaign_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Delete campaign and all related entities from MongoDB
    """
    try:
        campaign_id = state['campaign_id']
        is_new_format = state.get('is_new_format', False)

        # Update progress
        state['current_phase'] = 'delete_entities'
        state['progress_percentage'] = 15
        state['step_progress'] = 0
        state['status_message'] = 'Removing campaign data from MongoDB...'

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
    Delete all campaign-related entities from Neo4j by traversing relationships from Campaign node
    """
    try:
        campaign_id = state['campaign_id']
        logger.info(f"Starting Neo4j deletion for campaign: {campaign_id}")

        with neo4j_driver.session() as session:
            # Delete all entities by traversing from Campaign node
            # This is more reliable than trying to match MongoDB IDs

            # 1. Delete all Quests and their connected entities
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})-[:HAS_QUEST]->(q:Quest)
                OPTIONAL MATCH (q)-[r]->(connected)
                WHERE NOT connected:Campaign
                WITH q, collect(DISTINCT connected) as connected_nodes
                FOREACH (node IN connected_nodes | DETACH DELETE node)
                DETACH DELETE q
                RETURN count(DISTINCT q) as deleted_count
            """, campaign_id=campaign_id)
            quest_count = result.single()['deleted_count']
            logger.info(f"Deleted {quest_count} Quest nodes and their connections from Neo4j")

            # 2. Delete all Places (Level 2 Locations) and their connected entities
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})-[:HAS_QUEST]->(:Quest)-[:HAS_PLACE]->(p:Place)
                OPTIONAL MATCH (p)-[r]->(connected)
                WHERE NOT connected:Quest AND NOT connected:Campaign
                WITH p, collect(DISTINCT connected) as connected_nodes
                FOREACH (node IN connected_nodes | DETACH DELETE node)
                DETACH DELETE p
                RETURN count(DISTINCT p) as deleted_count
            """, campaign_id=campaign_id)
            place_count = result.single()['deleted_count']
            logger.info(f"Deleted {place_count} Place nodes and their connections from Neo4j")

            # 3. Delete all Scenes (Level 3 Locations) and their entities (NPCs, Challenges, etc.)
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})-[:HAS_QUEST]->(:Quest)-[:HAS_PLACE]->(:Place)-[:HAS_SCENE]->(s:Scene)
                OPTIONAL MATCH (s)-[r]->(entity)
                WHERE NOT entity:Place AND NOT entity:Quest AND NOT entity:Campaign
                WITH s, collect(DISTINCT entity) as scene_entities
                FOREACH (entity IN scene_entities | DETACH DELETE entity)
                DETACH DELETE s
                RETURN count(DISTINCT s) as deleted_count
            """, campaign_id=campaign_id)
            scene_count = result.single()['deleted_count']
            logger.info(f"Deleted {scene_count} Scene nodes and their entities from Neo4j")

            # 4. Delete any remaining orphaned NPCs that belonged to this campaign
            result = session.run("""
                MATCH (n:NPC)
                WHERE n.id STARTS WITH 'npc_' AND n.id CONTAINS $campaign_id
                DETACH DELETE n
                RETURN count(n) as deleted_count
            """, campaign_id=campaign_id)
            orphan_npc_count = result.single()['deleted_count']
            if orphan_npc_count > 0:
                logger.info(f"Deleted {orphan_npc_count} orphaned NPC nodes from Neo4j")

            # 5. Delete any remaining orphaned Knowledge nodes for this campaign
            result = session.run("""
                MATCH (k:Knowledge)
                WHERE k.id STARTS WITH 'knowledge_' AND k.id CONTAINS $campaign_id
                DETACH DELETE k
                RETURN count(k) as deleted_count
            """, campaign_id=campaign_id)
            orphan_knowledge_count = result.single()['deleted_count']
            if orphan_knowledge_count > 0:
                logger.info(f"Deleted {orphan_knowledge_count} orphaned Knowledge nodes from Neo4j")

            # 6. Delete any remaining orphaned Items for this campaign
            result = session.run("""
                MATCH (i:Item)
                WHERE i.id STARTS WITH 'item_' AND i.id CONTAINS $campaign_id
                DETACH DELETE i
                RETURN count(i) as deleted_count
            """, campaign_id=campaign_id)
            orphan_item_count = result.single()['deleted_count']
            if orphan_item_count > 0:
                logger.info(f"Deleted {orphan_item_count} orphaned Item nodes from Neo4j")

            # 7. Delete Rubric nodes for this campaign (they're linked to various entities)
            result = session.run("""
                MATCH (r:Rubric)
                WHERE r.id STARTS WITH 'rubric_' AND r.id CONTAINS $campaign_id
                DETACH DELETE r
                RETURN count(r) as deleted_count
            """, campaign_id=campaign_id)
            rubric_count = result.single()['deleted_count']
            if rubric_count > 0:
                logger.info(f"Deleted {rubric_count} Rubric nodes from Neo4j")

            # 8. Finally, delete the Campaign node itself
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


async def cleanup_species_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Cleanup species created by campaign if they're not used by other campaigns
    """
    try:
        # Update progress
        state['current_phase'] = 'cleanup_species'
        state['progress_percentage'] = 70
        state['step_progress'] = 0
        state['status_message'] = 'Checking species dependencies...'

        species_ids = state.get('campaign_created_species', [])
        world_id = state.get('world_id')

        if not species_ids:
            logger.info("No species created by this campaign to clean up")
            state['species_cleaned'] = True
            state['species_to_remove'] = []
            state['species_dependencies'] = {}
            return state

        logger.info(f"Checking {len(species_ids)} species for cleanup")

        # Check which species are used by other campaigns
        species_to_remove = []
        species_dependencies = {}

        for species_id in species_ids:
            # Find all campaigns that reference this species
            campaigns_using_species = list(db.campaigns.find({
                '_id': {'$ne': state['campaign_id']},  # Exclude current campaign
                'new_species_ids': species_id
            }))

            # Also check if NPCs in other campaigns use this species
            npcs_in_other_campaigns = list(db.npcs.find({
                'species_id': species_id,
                'campaign_id': {'$ne': state['campaign_id']}
            }))

            dependent_campaigns = [c['_id'] for c in campaigns_using_species]
            npc_campaign_ids = list(set([n.get('campaign_id') for n in npcs_in_other_campaigns if n.get('campaign_id')]))
            all_dependencies = list(set(dependent_campaigns + npc_campaign_ids))

            species_dependencies[species_id] = all_dependencies

            if not all_dependencies:
                # No other campaigns use this species, safe to remove
                species_to_remove.append(species_id)
                logger.info(f"Species {species_id} has no dependencies, will be removed")
            else:
                logger.info(f"Species {species_id} is used by {len(all_dependencies)} other campaign(s), keeping it")
                state['warnings'] = state.get('warnings', []) + [
                    f"Species {species_id} is used by other campaigns and will not be removed"
                ]

        state['species_to_remove'] = species_to_remove
        state['species_dependencies'] = species_dependencies

        # Remove species from world and MongoDB
        if species_to_remove:
            # Remove from world's species list
            if world_id:
                db.world_definitions.update_one(
                    {'_id': world_id},
                    {'$pull': {'species': {'$in': species_to_remove}}}
                )
                logger.info(f"Removed {len(species_to_remove)} species from world {world_id}")

            # Delete species documents
            result = db.species_definitions.delete_many({'_id': {'$in': species_to_remove}})
            logger.info(f"Deleted {result.deleted_count} species from MongoDB")

            # Delete from Neo4j
            with neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (s:Species)
                    WHERE s.id IN $species_ids
                    DETACH DELETE s
                    RETURN count(s) as deleted_count
                """, species_ids=species_to_remove)
                count = result.single()['deleted_count']
                logger.info(f"Deleted {count} Species nodes from Neo4j")

        state['species_cleaned'] = True
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'cleanup_species',
            'status': 'success',
            'details': {
                'total_species_created': len(species_ids),
                'species_removed': len(species_to_remove),
                'species_kept': len(species_ids) - len(species_to_remove),
                'removed_ids': species_to_remove,
                'dependencies': species_dependencies
            }
        }]

    except Exception as e:
        logger.error(f"Error cleaning up species: {e}")
        state['errors'] = state.get('errors', []) + [f"Species cleanup failed: {str(e)}"]
        state['species_cleaned'] = False
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'cleanup_species',
            'status': 'error',
            'details': {'error': str(e)}
        }]

    return state


async def cleanup_locations_node(state: CampaignDeletionState) -> CampaignDeletionState:
    """
    Cleanup locations (Level 1-3) created by campaign if they're not used by other campaigns
    """
    try:
        # Update progress
        state['current_phase'] = 'cleanup_locations'
        state['progress_percentage'] = 85
        state['step_progress'] = 0
        state['status_message'] = 'Checking location dependencies...'

        created_locations = state.get('campaign_created_locations', [])
        world_id = state.get('world_id')

        if not created_locations:
            logger.info("No locations created by this campaign to clean up")
            state['locations_cleaned'] = True
            state['locations_to_remove'] = []
            state['location_dependencies'] = {}
            return state

        logger.info(f"Checking {len(created_locations)} locations for cleanup")

        # Organize locations by level
        locations_by_level = {1: [], 2: [], 3: []}
        for loc in created_locations:
            level = loc.get('level', 3)  # Default to level 3 if not specified
            locations_by_level[level].append(loc)

        locations_to_remove = []
        location_dependencies = {}

        # Check Level 1 locations (regions)
        for loc in locations_by_level[1]:
            loc_id = loc.get('id')
            if not loc_id:
                continue

            # Check if used by other campaigns' quests
            quests_in_other_campaigns = list(db.quests.find({
                'level_1_location_id': loc_id,
                'campaign_id': {'$ne': state['campaign_id']}
            }))

            dependent_campaigns = list(set([q.get('campaign_id') for q in quests_in_other_campaigns if q.get('campaign_id')]))
            location_dependencies[loc_id] = dependent_campaigns

            if not dependent_campaigns:
                locations_to_remove.append(loc)
                logger.info(f"Level 1 location {loc_id} ({loc.get('name')}) has no dependencies, will be removed")
            else:
                logger.info(f"Level 1 location {loc_id} is used by {len(dependent_campaigns)} other campaign(s), keeping it")

        # Check Level 2 locations (places)
        for loc in locations_by_level[2]:
            loc_id = loc.get('id')
            if not loc_id:
                continue

            # Check if used by other campaigns' places
            places_in_other_campaigns = list(db.places.find({
                'level_2_location_id': loc_id,
                'quest_id': {'$exists': True}
            }))

            # Filter to only places from other campaigns
            dependent_places = []
            for place in places_in_other_campaigns:
                quest = db.quests.find_one({'_id': place.get('quest_id')})
                if quest and quest.get('campaign_id') != state['campaign_id']:
                    dependent_places.append(place)

            dependent_campaigns = list(set([
                db.quests.find_one({'_id': p.get('quest_id')}).get('campaign_id')
                for p in dependent_places
                if db.quests.find_one({'_id': p.get('quest_id')})
            ]))

            location_dependencies[loc_id] = dependent_campaigns

            if not dependent_campaigns:
                locations_to_remove.append(loc)
                logger.info(f"Level 2 location {loc_id} ({loc.get('name')}) has no dependencies, will be removed")
            else:
                logger.info(f"Level 2 location {loc_id} is used by {len(dependent_campaigns)} other campaign(s), keeping it")

        # Check Level 3 locations (scenes)
        for loc in locations_by_level[3]:
            loc_id = loc.get('id')
            if not loc_id:
                continue

            # Check if used by other campaigns' scenes
            scenes_in_other_campaigns = list(db.scenes.find({
                'level_3_location_id': loc_id,
                'place_id': {'$exists': True}
            }))

            # Filter to only scenes from other campaigns
            dependent_scenes = []
            for scene in scenes_in_other_campaigns:
                place = db.places.find_one({'_id': scene.get('place_id')})
                if place:
                    quest = db.quests.find_one({'_id': place.get('quest_id')})
                    if quest and quest.get('campaign_id') != state['campaign_id']:
                        dependent_scenes.append(scene)

            dependent_campaigns = []
            for scene in dependent_scenes:
                place = db.places.find_one({'_id': scene.get('place_id')})
                if place:
                    quest = db.quests.find_one({'_id': place.get('quest_id')})
                    if quest:
                        dependent_campaigns.append(quest.get('campaign_id'))

            dependent_campaigns = list(set([c for c in dependent_campaigns if c]))
            location_dependencies[loc_id] = dependent_campaigns

            if not dependent_campaigns:
                locations_to_remove.append(loc)
                logger.info(f"Level 3 location {loc_id} ({loc.get('name')}) has no dependencies, will be removed")
            else:
                logger.info(f"Level 3 location {loc_id} is used by {len(dependent_campaigns)} other campaign(s), keeping it")

        state['locations_to_remove'] = [loc.get('id') for loc in locations_to_remove]
        state['location_dependencies'] = location_dependencies

        # Remove locations from world and MongoDB
        if locations_to_remove:
            for loc in locations_to_remove:
                loc_id = loc.get('id')
                level = loc.get('level', 3)

                # Delete from MongoDB based on level
                if level == 1:
                    # Remove from world's regions list
                    if world_id:
                        db.world_definitions.update_one(
                            {'_id': world_id},
                            {'$pull': {'regions': loc_id}}
                        )
                    # Delete region document
                    db.region_definitions.delete_one({'_id': loc_id})
                    logger.info(f"Deleted Level 1 location {loc_id} from world and MongoDB")

                elif level == 2:
                    # Delete location document
                    db.location_definitions.delete_one({'_id': loc_id})
                    logger.info(f"Deleted Level 2 location {loc_id} from MongoDB")

                elif level == 3:
                    # Delete location document
                    db.location_definitions.delete_one({'_id': loc_id})
                    logger.info(f"Deleted Level 3 location {loc_id} from MongoDB")

                # Delete from Neo4j
                with neo4j_driver.session() as session:
                    result = session.run("""
                        MATCH (l:Location {id: $location_id})
                        DETACH DELETE l
                        RETURN count(l) as deleted_count
                    """, location_id=loc_id)
                    count = result.single()['deleted_count']
                    if count > 0:
                        logger.info(f"Deleted Location node {loc_id} from Neo4j")

        state['locations_cleaned'] = True
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'cleanup_locations',
            'status': 'success',
            'details': {
                'total_locations_created': len(created_locations),
                'locations_removed': len(locations_to_remove),
                'locations_kept': len(created_locations) - len(locations_to_remove),
                'removed_by_level': {
                    'level_1': len([l for l in locations_to_remove if l.get('level') == 1]),
                    'level_2': len([l for l in locations_to_remove if l.get('level') == 2]),
                    'level_3': len([l for l in locations_to_remove if l.get('level') == 3])
                },
                'removed_locations': [{'id': l.get('id'), 'name': l.get('name'), 'level': l.get('level')} for l in locations_to_remove],
                'dependencies': location_dependencies
            }
        }]

    except Exception as e:
        logger.error(f"Error cleaning up locations: {e}")
        state['errors'] = state.get('errors', []) + [f"Location cleanup failed: {str(e)}"]
        state['locations_cleaned'] = False
        state['deletion_log'] = state.get('deletion_log', []) + [{
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'cleanup_locations',
            'status': 'error',
            'details': {'error': str(e)}
        }]

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
    # Continue to cleanup even if postgres fails - it's non-critical
    return 'cleanup_species'


def route_after_species_cleanup(state: CampaignDeletionState) -> str:
    """Route after species cleanup"""
    # Continue to location cleanup regardless of species cleanup result
    return 'cleanup_locations'


def route_after_location_cleanup(state: CampaignDeletionState) -> str:
    """Route after location cleanup - finalize deletion"""
    # Update final progress
    state['progress_percentage'] = 100
    state['status_message'] = 'Campaign deletion completed'
    state['current_phase'] = 'completed'

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
    5. Cleanup Species (remove species created by campaign if not used elsewhere)
    6. Cleanup Locations (remove locations created by campaign if not used elsewhere)
    """
    workflow = StateGraph(CampaignDeletionState)

    # Add nodes
    workflow.add_node('fetch_campaign', fetch_campaign_data_node)
    workflow.add_node('delete_mongodb', delete_mongodb_campaign_node)
    workflow.add_node('delete_neo4j', delete_neo4j_entities_node)
    workflow.add_node('delete_postgres', delete_postgres_records_node)
    workflow.add_node('cleanup_species', cleanup_species_node)
    workflow.add_node('cleanup_locations', cleanup_locations_node)

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
            'cleanup_species': 'cleanup_species'
        }
    )

    workflow.add_conditional_edges(
        'cleanup_species',
        route_after_species_cleanup,
        {
            'cleanup_locations': 'cleanup_locations'
        }
    )

    workflow.add_conditional_edges(
        'cleanup_locations',
        route_after_location_cleanup,
        {
            'completed': END,
            'failed': END
        }
    )

    return workflow.compile()


# Export for use in Django views
__all__ = ['create_campaign_deletion_workflow', 'CampaignDeletionState']
