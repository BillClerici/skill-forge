"""
Check for orphaned nodes in Neo4j
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

print("Checking for orphaned nodes in Neo4j...\n")

# Get valid IDs from MongoDB
valid_discovery_ids = set(str(d['_id']) for d in db.discoveries.find({}, {'_id': 1}))
valid_challenge_ids = set(str(c['_id']) for c in db.challenges.find({}, {'_id': 1}))
valid_place_ids = set(str(p['_id']) for p in db.places.find({}, {'_id': 1}))

print(f"MongoDB has {len(valid_discovery_ids)} discoveries")
print(f"MongoDB has {len(valid_challenge_ids)} challenges")
print(f"MongoDB has {len(valid_place_ids)} places\n")

# Get IDs from Neo4j
with neo4j_driver.session() as session:
    # Check Discovery nodes
    result = session.run("MATCH (d:Discovery) RETURN d.id as id")
    neo4j_discovery_ids = set(record['id'] for record in result if record['id'])

    print(f"Neo4j has {len(neo4j_discovery_ids)} Discovery nodes")

    orphaned_discoveries = neo4j_discovery_ids - valid_discovery_ids
    if orphaned_discoveries:
        print(f"Found {len(orphaned_discoveries)} orphaned Discovery nodes:")
        for disc_id in list(orphaned_discoveries)[:10]:  # Show first 10
            print(f"  - {disc_id}")
        if len(orphaned_discoveries) > 10:
            print(f"  ... and {len(orphaned_discoveries) - 10} more")
    else:
        print("No orphaned Discovery nodes found")

    print()

    # Check Challenge nodes
    result = session.run("MATCH (c:Challenge) RETURN c.id as id")
    neo4j_challenge_ids = set(record['id'] for record in result if record['id'])

    print(f"Neo4j has {len(neo4j_challenge_ids)} Challenge nodes")

    orphaned_challenges = neo4j_challenge_ids - valid_challenge_ids
    if orphaned_challenges:
        print(f"Found {len(orphaned_challenges)} orphaned Challenge nodes:")
        for chal_id in list(orphaned_challenges)[:10]:  # Show first 10
            print(f"  - {chal_id}")
        if len(orphaned_challenges) > 10:
            print(f"  ... and {len(orphaned_challenges) - 10} more")
    else:
        print("No orphaned Challenge nodes found")

    print()

    # Check Place nodes
    result = session.run("MATCH (p:Place) RETURN p.id as id")
    neo4j_place_ids = set(record['id'] for record in result if record['id'])

    print(f"Neo4j has {len(neo4j_place_ids)} Place nodes")

    orphaned_places = neo4j_place_ids - valid_place_ids
    if orphaned_places:
        print(f"Found {len(orphaned_places)} orphaned Place nodes:")
        for place_id in list(orphaned_places)[:10]:  # Show first 10
            print(f"  - {place_id}")
        if len(orphaned_places) > 10:
            print(f"  ... and {len(orphaned_places) - 10} more")

        # Delete orphaned places
        print(f"\nDeleting {len(orphaned_places)} orphaned Place nodes...")
        result = session.run("""
            MATCH (p:Place)
            WHERE p.id IN $orphan_ids
            DETACH DELETE p
            RETURN count(p) as deleted
        """, orphan_ids=list(orphaned_places))
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} orphaned Place nodes")
    else:
        print("No orphaned Place nodes found")

    # Delete orphaned discoveries
    if orphaned_discoveries:
        print(f"\nDeleting {len(orphaned_discoveries)} orphaned Discovery nodes...")
        result = session.run("""
            MATCH (d:Discovery)
            WHERE d.id IN $orphan_ids
            DETACH DELETE d
            RETURN count(d) as deleted
        """, orphan_ids=list(orphaned_discoveries))
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} orphaned Discovery nodes")

    # Delete orphaned challenges
    if orphaned_challenges:
        print(f"\nDeleting {len(orphaned_challenges)} orphaned Challenge nodes...")
        result = session.run("""
            MATCH (c:Challenge)
            WHERE c.id IN $orphan_ids
            DETACH DELETE c
            RETURN count(c) as deleted
        """, orphan_ids=list(orphaned_challenges))
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} orphaned Challenge nodes")

neo4j_driver.close()
mongo_client.close()

print("\n✅ Orphan cleanup complete!")
