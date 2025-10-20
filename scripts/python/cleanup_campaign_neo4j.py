#!/usr/bin/env python3
"""
Cleanup script to remove all Neo4j nodes for a specific campaign.
Uses campaign_id property instead of ID pattern matching.
"""

from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

CAMPAIGN_ID = "campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def delete_campaign_nodes():
    """Delete all nodes associated with the campaign"""

    with driver.session() as session:
        print(f"🗑️  Deleting all Neo4j nodes for campaign: {CAMPAIGN_ID}\n")

        # List of node types to delete
        node_types = [
            "Quest",
            "Scene",
            "Place",
            "Discovery",
            "Challenge",
            "Event",
            "NPC",
            "Knowledge",
            "Item",
            "Rubric",
            "CampaignObjective",
            "QuestObjective"
        ]

        total_deleted = 0

        for node_type in node_types:
            # Try deleting by campaign_id property
            result = session.run(f"""
                MATCH (n:{node_type})
                WHERE n.campaign_id = $campaign_id
                DETACH DELETE n
                RETURN count(n) as deleted_count
            """, campaign_id=CAMPAIGN_ID)

            count = result.single()['deleted_count']
            if count > 0:
                print(f"  ✅ Deleted {count} {node_type} nodes")
                total_deleted += count

        # Delete Campaign node itself
        result = session.run("""
            MATCH (c:Campaign {id: $campaign_id})
            DETACH DELETE c
            RETURN count(c) as deleted_count
        """, campaign_id=CAMPAIGN_ID)

        count = result.single()['deleted_count']
        if count > 0:
            print(f"  ✅ Deleted {count} Campaign node")
            total_deleted += count

        # Also delete any nodes connected to the campaign
        result = session.run("""
            MATCH (c:Campaign {id: $campaign_id})-[*]-(n)
            WHERE NOT n:Campaign
            DETACH DELETE n
            RETURN count(n) as deleted_count
        """, campaign_id=CAMPAIGN_ID)

        count = result.single()['deleted_count']
        if count > 0:
            print(f"  ✅ Deleted {count} connected nodes")
            total_deleted += count

        print(f"\n🎯 Total nodes deleted: {total_deleted}")

        # Verify cleanup
        result = session.run("""
            MATCH (n)
            WHERE n.campaign_id = $campaign_id OR n.id = $campaign_id
            RETURN count(n) as remaining
        """, campaign_id=CAMPAIGN_ID)

        remaining = result.single()['remaining']
        if remaining == 0:
            print("✅ Campaign completely removed from Neo4j!")
        else:
            print(f"⚠️  Warning: {remaining} nodes still remain")

if __name__ == "__main__":
    delete_campaign_nodes()
    driver.close()
