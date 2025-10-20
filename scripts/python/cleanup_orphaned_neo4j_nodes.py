"""
Cleanup Script for Orphaned Neo4j Nodes
Removes CampaignObjective and QuestObjective nodes for campaigns that no longer exist in MongoDB
"""

import os
from neo4j import GraphDatabase
from pymongo import MongoClient

# Configuration
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_pass')

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://skillforge:mongo_pass@localhost:27017/')
MONGO_DB = os.getenv('MONGO_DB', 'skillforge_campaigns')

def get_existing_campaign_ids():
    """Get all campaign IDs that exist in MongoDB"""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    # Check both campaign collections
    campaign_ids = set()

    # Old format
    for campaign in db.campaign_state.find({}, {'_id': 1}):
        campaign_ids.add(campaign['_id'])

    # New format
    for campaign in db.campaigns.find({}, {'_id': 1}):
        campaign_ids.add(campaign['_id'])

    client.close()
    return campaign_ids

def cleanup_orphaned_nodes():
    """Remove Neo4j nodes for campaigns that don't exist in MongoDB"""

    print("=" * 80)
    print("CLEANUP ORPHANED NEO4J NODES")
    print("=" * 80)

    # Get existing campaign IDs from MongoDB
    print("\n1. Fetching existing campaign IDs from MongoDB...")
    existing_campaign_ids = get_existing_campaign_ids()
    print(f"   Found {len(existing_campaign_ids)} campaigns in MongoDB")

    # Connect to Neo4j
    print("\n2. Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Get all campaign IDs in Neo4j
        print("\n3. Fetching campaign IDs from Neo4j...")
        result = session.run("MATCH (c:Campaign) RETURN c.id as id")
        neo4j_campaign_ids = {record['id'] for record in result if record['id']}
        print(f"   Found {len(neo4j_campaign_ids)} campaigns in Neo4j")

        # Find orphaned campaigns (in Neo4j but not in MongoDB)
        orphaned_campaign_ids = neo4j_campaign_ids - existing_campaign_ids

        if not orphaned_campaign_ids:
            print("\n✅ No orphaned campaigns found. Neo4j is clean!")
            driver.close()
            return

        print(f"\n⚠️  Found {len(orphaned_campaign_ids)} orphaned campaigns:")
        for campaign_id in orphaned_campaign_ids:
            print(f"   - {campaign_id}")

        # Ask for confirmation
        print("\n" + "=" * 80)
        response = input("Delete all orphaned nodes for these campaigns? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            driver.close()
            return

        # Delete orphaned nodes for each campaign
        print("\n4. Deleting orphaned nodes...")
        total_deleted = 0

        for campaign_id in orphaned_campaign_ids:
            print(f"\n   Processing campaign: {campaign_id}")
            campaign_deleted = 0

            # Delete CampaignObjective nodes
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})-[:HAS_OBJECTIVE]->(co:CampaignObjective)
                DETACH DELETE co
                RETURN count(co) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - CampaignObjective: {count}")

            # Delete QuestObjective nodes
            result = session.run("""
                MATCH (qo:QuestObjective)
                WHERE qo.campaign_id = $campaign_id OR qo.id CONTAINS $campaign_id
                DETACH DELETE qo
                RETURN count(qo) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - QuestObjective: {count}")

            # Delete Quest nodes
            result = session.run("""
                MATCH (q:Quest)
                WHERE q.id STARTS WITH 'quest_' AND q.id CONTAINS $campaign_id
                DETACH DELETE q
                RETURN count(q) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Quest: {count}")

            # Delete Place nodes
            result = session.run("""
                MATCH (p:Place)
                WHERE p.id STARTS WITH 'place_' AND p.id CONTAINS $campaign_id
                DETACH DELETE p
                RETURN count(p) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Place: {count}")

            # Delete Scene nodes
            result = session.run("""
                MATCH (s:Scene)
                WHERE s.id STARTS WITH 'scene_' AND s.id CONTAINS $campaign_id
                DETACH DELETE s
                RETURN count(s) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Scene: {count}")

            # Delete NPC nodes
            result = session.run("""
                MATCH (n:NPC)
                WHERE n.id STARTS WITH 'npc_' AND n.id CONTAINS $campaign_id
                DETACH DELETE n
                RETURN count(n) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - NPC: {count}")

            # Delete Challenge nodes
            result = session.run("""
                MATCH (c:Challenge)
                WHERE c.id STARTS WITH 'challenge_' AND c.id CONTAINS $campaign_id
                DETACH DELETE c
                RETURN count(c) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Challenge: {count}")

            # Delete Discovery nodes
            result = session.run("""
                MATCH (d:Discovery)
                WHERE d.id STARTS WITH 'discovery_' AND d.id CONTAINS $campaign_id
                DETACH DELETE d
                RETURN count(d) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Discovery: {count}")

            # Delete Event nodes
            result = session.run("""
                MATCH (e:Event)
                WHERE e.id STARTS WITH 'event_' AND e.id CONTAINS $campaign_id
                DETACH DELETE e
                RETURN count(e) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Event: {count}")

            # Delete Knowledge nodes
            result = session.run("""
                MATCH (k:Knowledge)
                WHERE k.id STARTS WITH 'knowledge_' AND k.id CONTAINS $campaign_id
                DETACH DELETE k
                RETURN count(k) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Knowledge: {count}")

            # Delete Item nodes
            result = session.run("""
                MATCH (i:Item)
                WHERE i.id STARTS WITH 'item_' AND i.id CONTAINS $campaign_id
                DETACH DELETE i
                RETURN count(i) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Item: {count}")

            # Delete Rubric nodes
            result = session.run("""
                MATCH (r:Rubric)
                WHERE r.id STARTS WITH 'rubric_' AND r.id CONTAINS $campaign_id
                DETACH DELETE r
                RETURN count(r) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Rubric: {count}")

            # Delete Campaign node
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                DETACH DELETE c
                RETURN count(c) as deleted_count
            """, campaign_id=campaign_id)
            count = result.single()['deleted_count']
            campaign_deleted += count
            print(f"      - Campaign: {count}")

            print(f"      Total for campaign: {campaign_deleted} nodes")
            total_deleted += campaign_deleted

        print(f"\n{'=' * 80}")
        print(f"✅ CLEANUP COMPLETE")
        print(f"{'=' * 80}")
        print(f"Total nodes deleted: {total_deleted}")
        print(f"Campaigns cleaned: {len(orphaned_campaign_ids)}")

    driver.close()

if __name__ == '__main__':
    try:
        cleanup_orphaned_nodes()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
