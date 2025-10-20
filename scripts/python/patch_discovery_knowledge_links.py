#!/usr/bin/env python3
"""
Patch existing campaign discoveries to link them to knowledge items.

This script analyzes the Neo4j graph to find which knowledge items should be
revealed by each discovery, then updates the MongoDB discovery documents.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@localhost:27017")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

CAMPAIGN_ID = "campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6"


async def patch_discoveries():
    """Patch discoveries to include knowledge_revealed field"""

    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    db = mongo_client.skillforge

    # Connect to Neo4j
    neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        print(f"🔧 Patching discoveries for campaign: {CAMPAIGN_ID}")
        print()

        # Get all discoveries for this campaign from MongoDB
        discoveries_cursor = db.discoveries.find({"campaign_id": CAMPAIGN_ID})
        discoveries = await discoveries_cursor.to_list(length=None)

        print(f"📋 Found {len(discoveries)} discoveries in MongoDB")
        print()

        patched_count = 0

        async with neo4j_driver.session() as session:
            for discovery in discoveries:
                discovery_id = discovery["_id"]
                discovery_name = discovery.get("name", "Unknown")

                # Query Neo4j to find knowledge linked to this discovery
                query = """
                MATCH (d:Discovery {id: $discovery_id})-[:PROVIDES]->(k:Knowledge)
                RETURN k.id as knowledge_id, k.name as knowledge_name
                """

                result = await session.run(query, discovery_id=discovery_id)
                records = await result.data()

                knowledge_ids = [record["knowledge_id"] for record in records if record["knowledge_id"]]

                # Update MongoDB document
                if knowledge_ids:
                    print(f"✅ {discovery_name}")
                    print(f"   ID: {discovery_id}")
                    print(f"   Linking {len(knowledge_ids)} knowledge items:")
                    for record in records:
                        print(f"      - {record['knowledge_name']} ({record['knowledge_id']})")

                    # Update the discovery document
                    await db.discoveries.update_one(
                        {"_id": discovery_id},
                        {"$set": {"knowledge_revealed": knowledge_ids}}
                    )
                    patched_count += 1
                    print()
                else:
                    print(f"⚠️  {discovery_name}")
                    print(f"   ID: {discovery_id}")
                    print(f"   No knowledge items found in Neo4j graph")
                    print(f"   Setting knowledge_revealed to empty array")

                    # Still add the field, but empty
                    await db.discoveries.update_one(
                        {"_id": discovery_id},
                        {"$set": {"knowledge_revealed": []}}
                    )
                    print()

        print("=" * 60)
        print(f"✨ Patch complete!")
        print(f"   Total discoveries: {len(discoveries)}")
        print(f"   Patched with knowledge: {patched_count}")
        print(f"   Without knowledge: {len(discoveries) - patched_count}")

    finally:
        mongo_client.close()
        await neo4j_driver.close()


if __name__ == "__main__":
    asyncio.run(patch_discoveries())
