"""
Fix quest objectives by adding tracking data (type and required_ids)
based on the knowledge/items available in scenes for each quest.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase

MONGODB_URL = "mongodb://skillforge:skillforge2024@localhost:27017/"
NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "skillforge2024"

async def fix_objectives():
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    db = mongo_client['skillforge']

    # Connect to Neo4j
    neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASS))

    campaign_id = "campaign_9e716d42-a9c3-4ab4-8642-667a015d62eb"

    # Get all quests for this campaign
    quests = await db.quests.find({"campaign_id": campaign_id}).to_list(length=100)

    print(f"Found {len(quests)} quests to fix")

    for quest in quests:
        quest_id = quest["_id"]
        quest_name = quest["name"]
        order_seq = quest.get("order_sequence", 1)

        print(f"\nFixing quest: {quest_name} (order {order_seq})")

        # Get knowledge and items for this quest from Neo4j
        async with neo4j_driver.session() as session:
            result = await session.run("""
                // Get quest objectives for this quest
                MATCH (q:Quest {campaign_id: $campaign_id})
                WHERE q.order_sequence = $order_seq
                MATCH (q)-[:ACHIEVES]->(qo:QuestObjective)

                // Get scenes that advance these objectives
                OPTIONAL MATCH (s:Scene)-[:ADVANCES]->(qo)

                // Get knowledge from those scenes
                OPTIONAL MATCH (s)-[:CONTAINS_DISCOVERY]->(d:Discovery)-[:REVEALS]->(k:Knowledge)
                OPTIONAL MATCH (s)-[:CONTAINS_CHALLENGE]->(c:Challenge)-[:REWARDS]->(k2:Knowledge)
                OPTIONAL MATCH (s)-[:FEATURES]->(n:NPC)-[:TEACHES]->(k3:Knowledge)

                // Get items from those scenes
                OPTIONAL MATCH (s)-[:CONTAINS_DISCOVERY]->(d2:Discovery)-[:CONTAINS]->(i:Item)
                OPTIONAL MATCH (s)-[:CONTAINS_CHALLENGE]->(c2:Challenge)-[:REWARDS]->(i2:Item)
                OPTIONAL MATCH (s)-[:FEATURES]->(n2:NPC)-[:GIVES]->(i3:Item)

                WITH qo,
                     collect(DISTINCT k.id) + collect(DISTINCT k2.id) + collect(DISTINCT k3.id) as knowledge_ids,
                     collect(DISTINCT i.id) + collect(DISTINCT i2.id) + collect(DISTINCT i3.id) as item_ids

                RETURN qo.description as description,
                       [kid IN knowledge_ids WHERE kid IS NOT NULL] as knowledge_ids,
                       [iid IN item_ids WHERE iid IS NOT NULL] as item_ids
                ORDER BY qo.quest_number
            """, campaign_id=campaign_id, order_seq=order_seq)

            records = await result.values()

        # Update quest objectives
        updated_objectives = []
        for idx, obj_data in enumerate(quest.get("objectives", [])):
            updated_obj = obj_data.copy()

            # Try to match with Neo4j data
            if idx < len(records):
                record = records[idx]
                knowledge_ids = record[1]
                item_ids = record[2]

                # Determine type based on what's available
                if knowledge_ids and item_ids:
                    # Has both - prefer knowledge
                    updated_obj["type"] = "learn_knowledge"
                    updated_obj["required_ids"] = knowledge_ids
                    print(f"  Objective {idx+1}: learn_knowledge ({len(knowledge_ids)} knowledge items)")
                elif knowledge_ids:
                    updated_obj["type"] = "learn_knowledge"
                    updated_obj["required_ids"] = knowledge_ids
                    print(f"  Objective {idx+1}: learn_knowledge ({len(knowledge_ids)} knowledge items)")
                elif item_ids:
                    updated_obj["type"] = "collect_item"
                    updated_obj["required_ids"] = item_ids
                    print(f"  Objective {idx+1}: collect_item ({len(item_ids)} items)")
                else:
                    # No tracking data available - leave as description only
                    updated_obj["type"] = ""
                    updated_obj["required_ids"] = []
                    print(f"  Objective {idx+1}: no tracking data (description only)")
            else:
                # No Neo4j data - leave as description only
                updated_obj["type"] = ""
                updated_obj["required_ids"] = []
                print(f"  Objective {idx+1}: no Neo4j match (description only)")

            updated_objectives.append(updated_obj)

        # Update MongoDB
        await db.quests.update_one(
            {"_id": quest_id},
            {"$set": {"objectives": updated_objectives}}
        )
        print(f"  ✓ Updated {len(updated_objectives)} objectives")

    await neo4j_driver.close()
    mongo_client.close()
    print("\n✅ All quests updated!")

if __name__ == "__main__":
    asyncio.run(fix_objectives())
