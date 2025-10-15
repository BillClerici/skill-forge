"""
Check if Neo4j nodes are connected to valid campaigns
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

print("Checking campaign connections in Neo4j...\n")

# Get valid campaign IDs from MongoDB
valid_campaign_ids = set(str(c['_id']) for c in db.campaigns.find({}, {'_id': 1}))
valid_campaign_ids.update(str(c['_id']) for c in db.campaign_state.find({}, {'_id': 1}))

print(f"Valid campaigns in MongoDB: {len(valid_campaign_ids)}")
for cid in valid_campaign_ids:
    print(f"  - {cid}")

print()

with neo4j_driver.session() as session:
    # Check campaigns in Neo4j
    result = session.run("MATCH (c:Campaign) RETURN c.id as id, c.name as name")
    neo4j_campaigns = list(result)

    print(f"Campaigns in Neo4j: {len(neo4j_campaigns)}")
    for record in neo4j_campaigns:
        status = "✓ VALID" if record['id'] in valid_campaign_ids else "✗ ORPHAN"
        print(f"  {status} - {record['id']} ({record['name']})")

    print()

    # Check if Discoveries are connected to campaigns
    result = session.run("""
        MATCH (d:Discovery)
        OPTIONAL MATCH (d)-[*]-(c:Campaign)
        RETURN d.id as discovery_id, collect(DISTINCT c.id) as campaign_ids
        LIMIT 25
    """)

    discoveries = list(result)
    disconnected_discoveries = []
    orphan_campaign_discoveries = []

    for record in discoveries:
        campaign_ids = [cid for cid in record['campaign_ids'] if cid is not None]

        if not campaign_ids:
            disconnected_discoveries.append(record['discovery_id'])
        elif not any(cid in valid_campaign_ids for cid in campaign_ids):
            orphan_campaign_discoveries.append({
                'id': record['discovery_id'],
                'campaigns': campaign_ids
            })

    print(f"Checked {len(discoveries)} Discovery nodes:")
    print(f"  - {len(disconnected_discoveries)} are completely disconnected from any campaign")
    print(f"  - {len(orphan_campaign_discoveries)} are connected to orphaned campaigns")

    if disconnected_discoveries:
        print("\nDisconnected Discovery nodes:")
        for disc_id in disconnected_discoveries[:10]:
            print(f"    {disc_id}")

    if orphan_campaign_discoveries:
        print("\nDiscoveries connected to deleted campaigns:")
        for disc in orphan_campaign_discoveries[:10]:
            print(f"    {disc['id']} -> campaigns: {disc['campaigns']}")

    print()

    # Check if Challenges are connected to campaigns
    result = session.run("""
        MATCH (ch:Challenge)
        OPTIONAL MATCH (ch)-[*]-(c:Campaign)
        RETURN ch.id as challenge_id, collect(DISTINCT c.id) as campaign_ids
        LIMIT 25
    """)

    challenges = list(result)
    disconnected_challenges = []
    orphan_campaign_challenges = []

    for record in challenges:
        campaign_ids = [cid for cid in record['campaign_ids'] if cid is not None]

        if not campaign_ids:
            disconnected_challenges.append(record['challenge_id'])
        elif not any(cid in valid_campaign_ids for cid in campaign_ids):
            orphan_campaign_challenges.append({
                'id': record['challenge_id'],
                'campaigns': campaign_ids
            })

    print(f"Checked {len(challenges)} Challenge nodes:")
    print(f"  - {len(disconnected_challenges)} are completely disconnected from any campaign")
    print(f"  - {len(orphan_campaign_challenges)} are connected to orphaned campaigns")

    if disconnected_challenges:
        print("\nDisconnected Challenge nodes:")
        for chal_id in disconnected_challenges[:10]:
            print(f"    {chal_id}")

    if orphan_campaign_challenges:
        print("\nChallenges connected to deleted campaigns:")
        for chal in orphan_campaign_challenges[:10]:
            print(f"    {chal['id']} -> campaigns: {chal['campaigns']}")

    print()

    # Check if Places are connected to campaigns
    result = session.run("""
        MATCH (p:Place)
        OPTIONAL MATCH (p)-[*]-(c:Campaign)
        RETURN p.id as place_id, collect(DISTINCT c.id) as campaign_ids
    """)

    places = list(result)
    disconnected_places = []
    orphan_campaign_places = []

    for record in places:
        campaign_ids = [cid for cid in record['campaign_ids'] if cid is not None]

        if not campaign_ids:
            disconnected_places.append(record['place_id'])
        elif not any(cid in valid_campaign_ids for cid in campaign_ids):
            orphan_campaign_places.append({
                'id': record['place_id'],
                'campaigns': campaign_ids
            })

    print(f"Checked {len(places)} Place nodes:")
    print(f"  - {len(disconnected_places)} are completely disconnected from any campaign")
    print(f"  - {len(orphan_campaign_places)} are connected to orphaned campaigns")

    if disconnected_places:
        print("\nDisconnected Place nodes:")
        for place_id in disconnected_places[:10]:
            print(f"    {place_id}")

    if orphan_campaign_places:
        print("\nPlaces connected to deleted campaigns:")
        for place in orphan_campaign_places[:10]:
            print(f"    {place['id']} -> campaigns: {place['campaigns']}")

neo4j_driver.close()
mongo_client.close()

print("\n✅ Check complete!")
