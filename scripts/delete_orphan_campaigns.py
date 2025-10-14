"""
Delete orphaned Campaign nodes from Neo4j
"""
import os
from pymongo import MongoClient
from neo4j import GraphDatabase

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URI = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("Checking for orphaned Campaign nodes...\n")

# Get valid campaign IDs from MongoDB
valid_campaign_ids = set(str(c['_id']) for c in db.campaigns.find({}, {'_id': 1}))
valid_campaign_ids.update(str(c['_id']) for c in db.campaign_state.find({}, {'_id': 1}))

print(f"Valid campaigns in MongoDB: {len(valid_campaign_ids)}")
for cid in list(valid_campaign_ids):
    print(f"  ✓ {cid}")

print()

with neo4j_driver.session() as session:
    # Get all campaigns from Neo4j
    result = session.run("MATCH (c:Campaign) RETURN c.id as id, c.name as name")
    neo4j_campaigns = list(result)

    print(f"Campaigns in Neo4j: {len(neo4j_campaigns)}")

    orphaned = []
    valid = []

    for record in neo4j_campaigns:
        if record['id'] in valid_campaign_ids:
            valid.append(record)
            print(f"  ✓ VALID - {record['id']} ({record['name']})")
        else:
            orphaned.append(record)
            print(f"  ✗ ORPHAN - {record['id']} ({record['name']})")

    if orphaned:
        print(f"\n🗑️  Found {len(orphaned)} orphaned Campaign nodes")
        print("Deleting orphaned campaigns and their subgraphs...")

        for campaign in orphaned:
            campaign_id = campaign['id']
            campaign_name = campaign['name']

            print(f"\n  Deleting campaign: {campaign_name} ({campaign_id})")

            # Delete the campaign and everything connected to it
            # This uses DETACH DELETE which removes all relationships
            result = session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                OPTIONAL MATCH (c)-[*]-(connected)
                WITH c, collect(DISTINCT connected) as connected_nodes
                DETACH DELETE c
                WITH connected_nodes
                UNWIND connected_nodes as node
                WHERE node IS NOT NULL
                DETACH DELETE node
                RETURN count(node) as deleted_connected
            """, campaign_id=campaign_id)

            deleted_connected = result.single()['deleted_connected']
            print(f"    ✓ Deleted campaign node")
            print(f"    ✓ Deleted {deleted_connected} connected nodes")

        print(f"\n✅ Deleted {len(orphaned)} orphaned campaigns")

    else:
        print("\n✅ No orphaned Campaign nodes found!")

neo4j_driver.close()
mongo_client.close()
