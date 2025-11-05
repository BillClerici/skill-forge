"""
Simple data cleanup script using direct connections
"""
import asyncio
import os
from pymongo import MongoClient
from neo4j import GraphDatabase
from redis.asyncio import Redis


async def clear_all_data():
    """Clear all campaign and game data from all databases"""

    print("🗑️  Starting data cleanup...")

    try:
        # MongoDB connection with authentication
        mongo_password = os.getenv("MONGO_PASSWORD", "mongo_dev_pass_2024")
        mongo_url = f"mongodb://admin:{mongo_password}@mongodb:27017"
        mongo_client = MongoClient(mongo_url)
        db = mongo_client["skillforge"]

        # Clear MongoDB
        print("\n📦 Clearing MongoDB collections...")
        collections_to_clear = [
            "campaigns", "quests", "places", "scenes", "npcs",
            "discoveries", "events", "challenges", "knowledge_entities",
            "item_entities", "rubrics", "game_sessions",
            "campaign_objectives", "quest_objectives", "child_objectives"
        ]

        total_docs = 0
        for collection_name in collections_to_clear:
            result = db[collection_name].delete_many({})
            total_docs += result.deleted_count
            if result.deleted_count > 0:
                print(f"  ✓ Cleared {collection_name}: {result.deleted_count} documents")

        # Clear Neo4j
        print("\n🔗 Clearing Neo4j campaign data...")
        neo4j_url = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_pass = os.getenv("NEO4J_PASSWORD", "password")

        neo4j_driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_pass))

        with neo4j_driver.session() as session:
            # Delete all campaign-related nodes
            result = session.run("MATCH (n) WHERE n.campaign_id IS NOT NULL DETACH DELETE n RETURN count(n) as deleted")
            deleted = result.single()["deleted"]
            print(f"  ✓ Cleared campaign nodes: {deleted} nodes")

        neo4j_driver.close()

        # Clear Redis
        print("\n⚡ Clearing Redis keys...")
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        redis = Redis.from_url(redis_url, decode_responses=True)

        patterns = ["campaign:*", "session:*", "progress:*", "game:*"]
        total_deleted = 0
        for pattern in patterns:
            keys = await redis.keys(pattern)
            if keys:
                deleted = await redis.delete(*keys)
                total_deleted += deleted
                print(f"  ✓ Cleared {pattern}: {deleted} keys")

        await redis.close()

        print(f"\n✅ Data cleanup complete!")
        print(f"   - MongoDB: {total_docs} documents deleted")
        print(f"   - Neo4j: Campaign data cleared")
        print(f"   - Redis: {total_deleted} keys cleared")

    except Exception as e:
        print(f"\n❌ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(clear_all_data())
