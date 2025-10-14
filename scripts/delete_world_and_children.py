"""
Delete the world and ALL its children from MongoDB and Neo4j
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

print("=" * 70)
print("DELETING WORLD AND ALL CHILDREN - COMPLETE CLEANUP")
print("=" * 70)
print()

# Get world info
world = db.world_definitions.find_one()
if world:
    world_id = world['_id']
    world_name = world.get('world_name', 'Unknown')
    print(f"Found world: {world_name} (ID: {world_id})\n")
else:
    print("No world found in MongoDB")
    world_id = None

# MongoDB Deletions
print("🗑️  MONGODB DELETIONS:")
print("-" * 70)

# Delete campaigns (both old and new format)
count = db.campaigns.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} campaigns")

count = db.campaign_state.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} old format campaigns")

# Delete campaign hierarchy
count = db.quests.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} quests")

count = db.places.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} places")

count = db.scenes.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} scenes")

# Delete campaign entities
count = db.npcs.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} NPCs")

count = db.discoveries.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} discoveries")

count = db.challenges.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} challenges")

count = db.events.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} events")

count = db.knowledge.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} knowledge entities")

count = db.items.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} items")

count = db.rubrics.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} rubrics")

# Delete world hierarchy
count = db.location_definitions.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} locations")

count = db.region_definitions.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} regions")

count = db.species_definitions.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} species")

count = db.world_definitions.delete_many({}).deleted_count
print(f"  ✓ Deleted {count} worlds")

print()

# Neo4j Deletions
print("🗑️  NEO4J DELETIONS:")
print("-" * 70)

with neo4j_driver.session() as session:
    # Delete all campaign-related nodes
    result = session.run("MATCH (c:Campaign) DETACH DELETE c RETURN count(c) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Campaign nodes")

    result = session.run("MATCH (q:Quest) DETACH DELETE q RETURN count(q) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Quest nodes")

    result = session.run("MATCH (p:Place) DETACH DELETE p RETURN count(p) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Place nodes")

    result = session.run("MATCH (s:Scene) DETACH DELETE s RETURN count(s) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Scene nodes")

    result = session.run("MATCH (n:NPC) DETACH DELETE n RETURN count(n) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} NPC nodes")

    result = session.run("MATCH (d:Discovery) DETACH DELETE d RETURN count(d) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Discovery nodes")

    result = session.run("MATCH (c:Challenge) DETACH DELETE c RETURN count(c) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Challenge nodes")

    result = session.run("MATCH (e:Event) DETACH DELETE e RETURN count(e) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Event nodes")

    result = session.run("MATCH (k:Knowledge) DETACH DELETE k RETURN count(k) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Knowledge nodes")

    result = session.run("MATCH (i:Item) DETACH DELETE i RETURN count(i) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Item nodes")

    result = session.run("MATCH (r:Rubric) DETACH DELETE r RETURN count(r) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Rubric nodes")

    # Delete world hierarchy
    result = session.run("MATCH (l:Location) DETACH DELETE l RETURN count(l) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Location nodes")

    result = session.run("MATCH (r:Region) DETACH DELETE r RETURN count(r) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Region nodes")

    result = session.run("MATCH (s:Species) DETACH DELETE s RETURN count(s) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} Species nodes")

    result = session.run("MATCH (w:World) DETACH DELETE w RETURN count(w) as deleted")
    count = result.single()['deleted']
    print(f"  ✓ Deleted {count} World nodes")

    # Keep Universe node (can be reused)
    print(f"  ℹ️  Kept Universe nodes (can be reused)")

print()
print("=" * 70)
print("✅ COMPLETE CLEANUP FINISHED")
print("=" * 70)
print()

# Show what's left
print("Remaining in Neo4j:")
with neo4j_driver.session() as session:
    result = session.run("""
        MATCH (n)
        RETURN labels(n)[0] as NodeType, count(n) as Count
        ORDER BY Count DESC
    """)
    for record in result:
        print(f"  {record['NodeType']:15} {record['Count']:5}")

neo4j_driver.close()
mongo_client.close()

print("\n✅ System is now clean and ready for a new world!")
