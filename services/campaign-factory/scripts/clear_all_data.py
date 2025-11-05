"""
Data Cleanup Script for Campaign Refactoring
Clears all campaign and game-related data from MongoDB, Neo4j, and Redis
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase
import redis.asyncio as redis
from datetime import datetime
import json

# Import config
from workflow.utils import get_mongo_client, get_neo4j_driver


class DataCleaner:
    """Handles cleanup of all campaign and game data"""

    def __init__(self):
        self.mongo_client = None
        self.neo4j_driver = None
        self.redis_client = None
        self.cleanup_summary = {
            "mongodb": {},
            "neo4j": {},
            "redis": {},
            "timestamp": None,
            "success": False
        }

    async def initialize(self):
        """Initialize database connections"""
        print("🔌 Initializing database connections...")

        # MongoDB
        self.mongo_client = get_mongo_client()
        self.db = self.mongo_client["skill_forge"]

        # Neo4j
        self.neo4j_driver = get_neo4j_driver()

        # Redis
        self.redis_client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True
        )

        print("✅ Connections established\n")

    async def backup_data(self, backup_dir: str = "./backups") -> bool:
        """Create backup before clearing (optional)"""
        print("💾 Creating backup (optional step)...")

        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"campaign_backup_{timestamp}.json"

        try:
            backup_data = {
                "timestamp": timestamp,
                "mongodb": {},
                "neo4j": {}
            }

            # Backup MongoDB collections
            collections = [
                "campaigns", "quests", "places", "scenes", "npcs",
                "discoveries", "events", "challenges", "knowledge_entities",
                "item_entities", "rubrics", "game_sessions"
            ]

            for collection_name in collections:
                collection = self.db[collection_name]
                docs = await collection.find({}).to_list(length=None)
                backup_data["mongodb"][collection_name] = docs
                print(f"  📦 Backed up {len(docs)} documents from {collection_name}")

            # Save backup
            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            print(f"✅ Backup saved to {backup_file}\n")
            return True

        except Exception as e:
            print(f"⚠️  Backup failed: {e}")
            print("Continuing without backup...\n")
            return False

    async def clear_mongodb(self):
        """Clear all MongoDB collections"""
        print("🗑️  Clearing MongoDB collections...")

        collections_to_clear = [
            "campaigns",
            "quests",
            "places",
            "scenes",
            "npcs",
            "discoveries",
            "events",
            "challenges",
            "knowledge_entities",
            "item_entities",
            "rubrics",
            "game_sessions"
        ]

        cleared_counts = {}

        for collection_name in collections_to_clear:
            try:
                collection = self.db[collection_name]

                # Count before delete
                count = await collection.count_documents({})

                # Delete all documents
                result = await collection.delete_many({})

                cleared_counts[collection_name] = {
                    "before": count,
                    "deleted": result.deleted_count
                }

                print(f"  ✅ {collection_name}: Deleted {result.deleted_count} documents")

            except Exception as e:
                print(f"  ❌ {collection_name}: Error - {e}")
                cleared_counts[collection_name] = {"error": str(e)}

        self.cleanup_summary["mongodb"] = cleared_counts
        print(f"\n✅ MongoDB cleanup complete\n")

    async def clear_neo4j(self):
        """Clear all Neo4j nodes and relationships"""
        print("🗑️  Clearing Neo4j graph database...")

        queries = [
            # Clear all campaign-related nodes
            {
                "name": "Campaign nodes",
                "query": "MATCH (n:Campaign) DETACH DELETE n"
            },
            {
                "name": "Quest nodes",
                "query": "MATCH (n:Quest) DETACH DELETE n"
            },
            {
                "name": "CampaignObjective nodes",
                "query": "MATCH (n:CampaignObjective) DETACH DELETE n"
            },
            {
                "name": "QuestObjective nodes",
                "query": "MATCH (n:QuestObjective) DETACH DELETE n"
            },
            {
                "name": "QuestChildObjective nodes",
                "query": "MATCH (n:QuestChildObjective) DETACH DELETE n"
            },
            {
                "name": "Scene nodes",
                "query": "MATCH (n:Scene) DETACH DELETE n"
            },
            {
                "name": "Place nodes",
                "query": "MATCH (n:Place) DETACH DELETE n"
            },
            {
                "name": "NPC nodes",
                "query": "MATCH (n:NPC) DETACH DELETE n"
            },
            {
                "name": "Knowledge nodes",
                "query": "MATCH (n:Knowledge) DETACH DELETE n"
            },
            {
                "name": "Item nodes",
                "query": "MATCH (n:Item) DETACH DELETE n"
            },
            {
                "name": "Discovery nodes",
                "query": "MATCH (n:Discovery) DETACH DELETE n"
            },
            {
                "name": "Challenge nodes",
                "query": "MATCH (n:Challenge) DETACH DELETE n"
            },
            {
                "name": "Event nodes",
                "query": "MATCH (n:Event) DETACH DELETE n"
            },
            {
                "name": "Rubric nodes",
                "query": "MATCH (n:Rubric) DETACH DELETE n"
            },
            {
                "name": "Player nodes",
                "query": "MATCH (n:Player) DETACH DELETE n"
            },
            {
                "name": "Session nodes",
                "query": "MATCH (n:Session) DETACH DELETE n"
            }
        ]

        deleted_counts = {}

        async with self.neo4j_driver.session() as session:
            for query_info in queries:
                try:
                    # First count
                    count_query = query_info["query"].replace("DETACH DELETE n", "RETURN count(n) as count")
                    count_result = await session.run(count_query)
                    count_record = await count_result.single()
                    count = count_record["count"] if count_record else 0

                    # Then delete
                    result = await session.run(query_info["query"])
                    await result.consume()

                    deleted_counts[query_info["name"]] = count
                    print(f"  ✅ {query_info['name']}: Deleted {count} nodes")

                except Exception as e:
                    print(f"  ❌ {query_info['name']}: Error - {e}")
                    deleted_counts[query_info["name"]] = {"error": str(e)}

        self.cleanup_summary["neo4j"] = deleted_counts
        print(f"\n✅ Neo4j cleanup complete\n")

    async def clear_redis(self):
        """Clear all Redis keys for campaigns and sessions"""
        print("🗑️  Clearing Redis cache...")

        patterns = [
            "campaign:*",
            "session:*",
            "progress:*",
            "game:*"
        ]

        cleared_counts = {}

        for pattern in patterns:
            try:
                # Get all keys matching pattern
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)

                # Delete keys
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    cleared_counts[pattern] = deleted
                    print(f"  ✅ {pattern}: Deleted {deleted} keys")
                else:
                    cleared_counts[pattern] = 0
                    print(f"  ℹ️  {pattern}: No keys found")

            except Exception as e:
                print(f"  ❌ {pattern}: Error - {e}")
                cleared_counts[pattern] = {"error": str(e)}

        self.cleanup_summary["redis"] = cleared_counts
        print(f"\n✅ Redis cleanup complete\n")

    async def verify_cleanup(self) -> bool:
        """Verify all data has been cleared"""
        print("🔍 Verifying cleanup...")

        issues = []

        # Check MongoDB
        collections_to_check = [
            "campaigns", "quests", "places", "scenes", "npcs",
            "discoveries", "events", "challenges", "knowledge_entities",
            "item_entities", "rubrics", "game_sessions"
        ]

        for collection_name in collections_to_check:
            count = await self.db[collection_name].count_documents({})
            if count > 0:
                issues.append(f"MongoDB {collection_name} still has {count} documents")

        # Check Neo4j
        async with self.neo4j_driver.session() as session:
            result = await session.run("""
                MATCH (n)
                WHERE n:Campaign OR n:Quest OR n:CampaignObjective
                   OR n:QuestObjective OR n:QuestChildObjective
                   OR n:Scene OR n:Place OR n:NPC OR n:Knowledge
                   OR n:Item OR n:Player OR n:Session
                RETURN count(n) as count
            """)
            record = await result.single()
            if record and record["count"] > 0:
                issues.append(f"Neo4j still has {record['count']} campaign-related nodes")

        # Check Redis
        for pattern in ["campaign:*", "session:*", "progress:*", "game:*"]:
            count = 0
            async for _ in self.redis_client.scan_iter(match=pattern):
                count += 1
            if count > 0:
                issues.append(f"Redis still has {count} keys matching {pattern}")

        if issues:
            print("⚠️  Verification found issues:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ Verification passed - all data cleared\n")
            return True

    async def close(self):
        """Close all connections"""
        print("🔌 Closing connections...")

        if self.mongo_client:
            self.mongo_client.close()

        if self.neo4j_driver:
            await self.neo4j_driver.close()

        if self.redis_client:
            await self.redis_client.close()

        print("✅ Connections closed\n")

    async def run(self, create_backup: bool = False):
        """Run the complete cleanup process"""
        print("=" * 60)
        print("🚨 CAMPAIGN DATA CLEANUP SCRIPT")
        print("=" * 60)
        print("\nThis will DELETE all campaign and game data from:")
        print("  - MongoDB (campaigns, quests, scenes, NPCs, etc.)")
        print("  - Neo4j (all campaign-related nodes)")
        print("  - Redis (all cache keys)")
        print("\n⚠️  This operation CANNOT be undone!\n")

        # Confirmation
        response = input("Type 'DELETE ALL DATA' to proceed: ")
        if response != "DELETE ALL DATA":
            print("\n❌ Cleanup cancelled\n")
            return

        print("\n🚀 Starting cleanup process...\n")

        try:
            await self.initialize()

            # Optional backup
            if create_backup:
                await self.backup_data()

            # Clear databases
            await self.clear_mongodb()
            await self.clear_neo4j()
            await self.clear_redis()

            # Verify
            verification_passed = await self.verify_cleanup()

            # Summary
            self.cleanup_summary["timestamp"] = datetime.now().isoformat()
            self.cleanup_summary["success"] = verification_passed

            print("=" * 60)
            print("📊 CLEANUP SUMMARY")
            print("=" * 60)

            # MongoDB summary
            print("\nMongoDB:")
            for collection, stats in self.cleanup_summary["mongodb"].items():
                if isinstance(stats, dict) and "deleted" in stats:
                    print(f"  {collection}: {stats['deleted']} deleted")

            # Neo4j summary
            print("\nNeo4j:")
            total_nodes = sum(
                count for count in self.cleanup_summary["neo4j"].values()
                if isinstance(count, int)
            )
            print(f"  Total nodes deleted: {total_nodes}")

            # Redis summary
            print("\nRedis:")
            total_keys = sum(
                count for count in self.cleanup_summary["redis"].values()
                if isinstance(count, int)
            )
            print(f"  Total keys deleted: {total_keys}")

            if verification_passed:
                print("\n✅ Cleanup completed successfully!\n")
            else:
                print("\n⚠️  Cleanup completed with warnings (see verification above)\n")

        except Exception as e:
            print(f"\n❌ Cleanup failed: {e}\n")
            self.cleanup_summary["error"] = str(e)

        finally:
            await self.close()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Clear all campaign and game data")
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create backup before clearing"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (dangerous!)"
    )

    args = parser.parse_args()

    cleaner = DataCleaner()

    if args.yes:
        # Auto-confirm (dangerous - only for testing)
        print("⚠️  Auto-confirm enabled - skipping prompt")
        await cleaner.initialize()
        if args.backup:
            await cleaner.backup_data()
        await cleaner.clear_mongodb()
        await cleaner.clear_neo4j()
        await cleaner.clear_redis()
        await cleaner.verify_cleanup()
        await cleaner.close()
    else:
        await cleaner.run(create_backup=args.backup)


if __name__ == "__main__":
    asyncio.run(main())
