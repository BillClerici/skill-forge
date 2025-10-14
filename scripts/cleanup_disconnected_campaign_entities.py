"""
Delete all campaign-related entities that are disconnected from any Campaign node
"""
import os
from neo4j import GraphDatabase

# Neo4j connection
NEO4J_URI = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("Cleaning up disconnected campaign entities from Neo4j...\n")

with neo4j_driver.session() as session:
    # First, check if there are any Campaign nodes
    result = session.run("MATCH (c:Campaign) RETURN count(c) as campaign_count")
    campaign_count = result.single()['campaign_count']

    print(f"Found {campaign_count} Campaign nodes in Neo4j\n")

    if campaign_count == 0:
        print("No campaigns found - deleting all campaign-related entities...\n")

        # Delete all Quest nodes
        result = session.run("MATCH (q:Quest) DETACH DELETE q RETURN count(q) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Quest nodes")

        # Delete all Place nodes
        result = session.run("MATCH (p:Place) DETACH DELETE p RETURN count(p) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Place nodes")

        # Delete all Scene nodes
        result = session.run("MATCH (s:Scene) DETACH DELETE s RETURN count(s) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Scene nodes")

        # Delete all NPC nodes
        result = session.run("MATCH (n:NPC) DETACH DELETE n RETURN count(n) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} NPC nodes")

        # Delete all Discovery nodes
        result = session.run("MATCH (d:Discovery) DETACH DELETE d RETURN count(d) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Discovery nodes")

        # Delete all Challenge nodes
        result = session.run("MATCH (c:Challenge) DETACH DELETE c RETURN count(c) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Challenge nodes")

        # Delete all Event nodes
        result = session.run("MATCH (e:Event) DETACH DELETE e RETURN count(e) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Event nodes")

        # Delete all Knowledge nodes
        result = session.run("MATCH (k:Knowledge) DETACH DELETE k RETURN count(k) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Knowledge nodes")

        # Delete all Item nodes
        result = session.run("MATCH (i:Item) DETACH DELETE i RETURN count(i) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Item nodes")

        # Delete all Rubric nodes
        result = session.run("MATCH (r:Rubric) DETACH DELETE r RETURN count(r) as deleted")
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} Rubric nodes")

    else:
        print("Campaign nodes exist - cleaning up only disconnected entities...\n")

        # Delete Quest nodes not connected to any Campaign
        result = session.run("""
            MATCH (q:Quest)
            WHERE NOT (q)-[*]-(c:Campaign)
            DETACH DELETE q
            RETURN count(q) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Quest nodes")

        # Delete Place nodes not connected to any Campaign
        result = session.run("""
            MATCH (p:Place)
            WHERE NOT (p)-[*]-(c:Campaign)
            DETACH DELETE p
            RETURN count(p) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Place nodes")

        # Delete Scene nodes not connected to any Campaign
        result = session.run("""
            MATCH (s:Scene)
            WHERE NOT (s)-[*]-(c:Campaign)
            DETACH DELETE s
            RETURN count(s) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Scene nodes")

        # Delete NPC nodes not connected to any Campaign
        result = session.run("""
            MATCH (n:NPC)
            WHERE NOT (n)-[*]-(c:Campaign)
            DETACH DELETE n
            RETURN count(n) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected NPC nodes")

        # Delete Discovery nodes not connected to any Campaign
        result = session.run("""
            MATCH (d:Discovery)
            WHERE NOT (d)-[*]-(c:Campaign)
            DETACH DELETE d
            RETURN count(d) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Discovery nodes")

        # Delete Challenge nodes not connected to any Campaign
        result = session.run("""
            MATCH (c:Challenge)
            WHERE NOT (c)-[*]-(camp:Campaign)
            DETACH DELETE c
            RETURN count(c) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Challenge nodes")

        # Delete Event nodes not connected to any Campaign
        result = session.run("""
            MATCH (e:Event)
            WHERE NOT (e)-[*]-(c:Campaign)
            DETACH DELETE e
            RETURN count(e) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Event nodes")

        # Delete Knowledge nodes not connected to any Campaign
        result = session.run("""
            MATCH (k:Knowledge)
            WHERE NOT (k)-[*]-(c:Campaign)
            DETACH DELETE k
            RETURN count(k) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Knowledge nodes")

        # Delete Item nodes not connected to any Campaign
        result = session.run("""
            MATCH (i:Item)
            WHERE NOT (i)-[*]-(c:Campaign)
            DETACH DELETE i
            RETURN count(i) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Item nodes")

        # Delete Rubric nodes not connected to any Campaign
        result = session.run("""
            MATCH (r:Rubric)
            WHERE NOT (r)-[*]-(c:Campaign)
            DETACH DELETE r
            RETURN count(r) as deleted
        """)
        deleted = result.single()['deleted']
        print(f"✓ Deleted {deleted} disconnected Rubric nodes")

print("\n✅ Cleanup complete!")

# Show final counts
print("\nFinal Neo4j node counts:")
result = session.run("""
    MATCH (n)
    RETURN labels(n)[0] as NodeType, count(n) as Count
    ORDER BY Count DESC
""")

for record in result:
    print(f"  {record['NodeType']:15} {record['Count']:5}")

neo4j_driver.close()
