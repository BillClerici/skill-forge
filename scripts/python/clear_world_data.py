#!/usr/bin/env python3
"""
Clear all Worlds, Regions, and Locations from MongoDB and Neo4j
"""
import os
from pymongo import MongoClient
from neo4j import GraphDatabase

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@localhost:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URL = os.getenv('NEO4J_URL', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))

def clear_all_world_data():
    """Delete all Worlds, Regions, and Locations from MongoDB and Neo4j"""

    print("🗑️  Starting cleanup of all World data...")

    # Get counts before deletion
    world_count = db.world_definitions.count_documents({})
    region_count = db.region_definitions.count_documents({})
    location_count = db.location_definitions.count_documents({})

    print(f"\n📊 Current counts:")
    print(f"   - Worlds: {world_count}")
    print(f"   - Regions: {region_count}")
    print(f"   - Locations: {location_count}")

    if world_count == 0 and region_count == 0 and location_count == 0:
        print("\n✅ No data to delete!")
        return

    # Confirm deletion
    response = input("\n⚠️  Are you sure you want to delete ALL world data? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Deletion cancelled.")
        return

    print("\n🔄 Deleting from MongoDB...")

    # Delete from MongoDB
    location_result = db.location_definitions.delete_many({})
    print(f"   ✓ Deleted {location_result.deleted_count} locations")

    region_result = db.region_definitions.delete_many({})
    print(f"   ✓ Deleted {region_result.deleted_count} regions")

    world_result = db.world_definitions.delete_many({})
    print(f"   ✓ Deleted {world_result.deleted_count} worlds")

    # Also clear regions array from universes
    universe_result = db.universe_definitions.update_many(
        {},
        {'$set': {'worlds': []}}
    )
    print(f"   ✓ Cleared worlds from {universe_result.modified_count} universes")

    print("\n🔄 Deleting from Neo4j...")

    # Delete from Neo4j
    with neo4j_driver.session() as session:
        # Delete all Location nodes and their relationships
        location_neo_result = session.run("""
            MATCH (l:Location)
            DETACH DELETE l
            RETURN count(l) as count
        """)
        location_neo_count = location_neo_result.single()['count']
        print(f"   ✓ Deleted {location_neo_count} Location nodes")

        # Delete all Region nodes and their relationships
        region_neo_result = session.run("""
            MATCH (r:Region)
            DETACH DELETE r
            RETURN count(r) as count
        """)
        region_neo_count = region_neo_result.single()['count']
        print(f"   ✓ Deleted {region_neo_count} Region nodes")

        # Delete all World nodes and their relationships
        world_neo_result = session.run("""
            MATCH (w:World)
            DETACH DELETE w
            RETURN count(w) as count
        """)
        world_neo_count = world_neo_result.single()['count']
        print(f"   ✓ Deleted {world_neo_count} World nodes")

    print("\n✅ Cleanup complete!")
    print("\n📊 Final verification:")
    print(f"   - Worlds: {db.world_definitions.count_documents({})}")
    print(f"   - Regions: {db.region_definitions.count_documents({})}")
    print(f"   - Locations: {db.location_definitions.count_documents({})}")

if __name__ == '__main__':
    try:
        clear_all_world_data()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        mongo_client.close()
        neo4j_driver.close()
