"""
Clean up orphaned Neo4j nodes that don't have corresponding MongoDB data
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

def cleanup_orphaned_nodes():
    """Remove Neo4j nodes that don't exist in MongoDB"""

    print("Starting Neo4j orphan cleanup...\n")

    # Get all valid IDs from MongoDB
    print("Collecting valid IDs from MongoDB...")
    valid_campaign_ids = set(str(c['_id']) for c in db.campaigns.find({}, {'_id': 1}))
    valid_campaign_ids.update(str(c['_id']) for c in db.campaign_state.find({}, {'_id': 1}))

    valid_quest_ids = set(str(q['_id']) for q in db.quests.find({}, {'_id': 1}))
    valid_npc_ids = set(str(n['_id']) for n in db.npcs.find({}, {'_id': 1}))
    valid_scene_ids = set(str(s['_id']) for s in db.scenes.find({}, {'_id': 1}))
    valid_place_ids = set(str(p['_id']) for p in db.places.find({}, {'_id': 1}))
    valid_knowledge_ids = set(str(k['_id']) for k in db.knowledge.find({}, {'_id': 1}))
    valid_item_ids = set(str(i['_id']) for i in db.items.find({}, {'_id': 1}))
    valid_discovery_ids = set(str(d['_id']) for d in db.discoveries.find({}, {'_id': 1}))
    valid_event_ids = set(str(e['_id']) for e in db.events.find({}, {'_id': 1}))
    valid_challenge_ids = set(str(c['_id']) for c in db.challenges.find({}, {'_id': 1}))
    valid_rubric_ids = set(str(r['_id']) for r in db.rubrics.find({}, {'_id': 1}))

    print(f"Found {len(valid_campaign_ids)} campaigns in MongoDB")
    print(f"Found {len(valid_quest_ids)} quests in MongoDB")
    print(f"Found {len(valid_npc_ids)} NPCs in MongoDB")
    print(f"Found {len(valid_scene_ids)} scenes in MongoDB")
    print(f"Found {len(valid_place_ids)} places in MongoDB")
    print(f"Found {len(valid_knowledge_ids)} knowledge entities in MongoDB")
    print(f"Found {len(valid_item_ids)} items in MongoDB")
    print(f"Found {len(valid_discovery_ids)} discoveries in MongoDB")
    print(f"Found {len(valid_event_ids)} events in MongoDB")
    print(f"Found {len(valid_challenge_ids)} challenges in MongoDB")
    print(f"Found {len(valid_rubric_ids)} rubrics in MongoDB\n")

    # Delete orphaned nodes from Neo4j
    with neo4j_driver.session() as session:
        # Campaign nodes
        result = session.run("""
            MATCH (c:Campaign)
            WHERE NOT c.id IN $valid_ids
            DETACH DELETE c
            RETURN count(c) as deleted_count
        """, valid_ids=list(valid_campaign_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Campaign nodes")

        # Quest nodes
        result = session.run("""
            MATCH (q:Quest)
            WHERE NOT q.id IN $valid_ids
            DETACH DELETE q
            RETURN count(q) as deleted_count
        """, valid_ids=list(valid_quest_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Quest nodes")

        # NPC nodes
        result = session.run("""
            MATCH (n:NPC)
            WHERE NOT n.id IN $valid_ids
            DETACH DELETE n
            RETURN count(n) as deleted_count
        """, valid_ids=list(valid_npc_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned NPC nodes")

        # Scene nodes (Location nodes with scene IDs)
        result = session.run("""
            MATCH (s:Scene)
            WHERE NOT s.id IN $valid_ids
            DETACH DELETE s
            RETURN count(s) as deleted_count
        """, valid_ids=list(valid_scene_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Scene nodes")

        # Place nodes (Location nodes with place IDs)
        result = session.run("""
            MATCH (p:Place)
            WHERE NOT p.id IN $valid_ids
            DETACH DELETE p
            RETURN count(p) as deleted_count
        """, valid_ids=list(valid_place_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Place nodes")

        # Location nodes (generic - scenes and places)
        valid_location_ids = valid_scene_ids.union(valid_place_ids)
        result = session.run("""
            MATCH (l:Location)
            WHERE NOT l.id IN $valid_ids
            DETACH DELETE l
            RETURN count(l) as deleted_count
        """, valid_ids=list(valid_location_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Location nodes")

        # Knowledge nodes
        result = session.run("""
            MATCH (k:Knowledge)
            WHERE NOT k.id IN $valid_ids
            DETACH DELETE k
            RETURN count(k) as deleted_count
        """, valid_ids=list(valid_knowledge_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Knowledge nodes")

        # Item nodes
        result = session.run("""
            MATCH (i:Item)
            WHERE NOT i.id IN $valid_ids
            DETACH DELETE i
            RETURN count(i) as deleted_count
        """, valid_ids=list(valid_item_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Item nodes")

        # Discovery nodes
        result = session.run("""
            MATCH (d:Discovery)
            WHERE NOT d.id IN $valid_ids
            DETACH DELETE d
            RETURN count(d) as deleted_count
        """, valid_ids=list(valid_discovery_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Discovery nodes")

        # Event nodes
        result = session.run("""
            MATCH (e:Event)
            WHERE NOT e.id IN $valid_ids
            DETACH DELETE e
            RETURN count(e) as deleted_count
        """, valid_ids=list(valid_event_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Event nodes")

        # Challenge nodes
        result = session.run("""
            MATCH (c:Challenge)
            WHERE NOT c.id IN $valid_ids
            DETACH DELETE c
            RETURN count(c) as deleted_count
        """, valid_ids=list(valid_challenge_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Challenge nodes")

        # Rubric nodes
        result = session.run("""
            MATCH (r:Rubric)
            WHERE NOT r.id IN $valid_ids
            DETACH DELETE r
            RETURN count(r) as deleted_count
        """, valid_ids=list(valid_rubric_ids))
        count = result.single()['deleted_count']
        print(f"✓ Deleted {count} orphaned Rubric nodes")

    print("\n✅ Neo4j cleanup complete!")

    # Show final counts
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as NodeType, count(n) as Count
            ORDER BY Count DESC
        """)
        print("\nFinal Neo4j node counts:")
        for record in result:
            print(f"  {record['NodeType']}: {record['Count']}")

if __name__ == '__main__':
    cleanup_orphaned_nodes()
    neo4j_driver.close()
    mongo_client.close()
