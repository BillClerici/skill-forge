"""
Count all nodes in Neo4j
"""
import os
from neo4j import GraphDatabase

# Neo4j connection
NEO4J_URI = os.getenv('NEO4J_URL', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("Neo4j Node Counts:\n")

with neo4j_driver.session() as session:
    result = session.run("""
        MATCH (n)
        RETURN labels(n)[0] as NodeType, count(n) as Count
        ORDER BY Count DESC
    """)

    total = 0
    for record in result:
        node_type = record['NodeType']
        count = record['Count']
        total += count
        print(f"  {node_type:15} {count:5}")

    print(f"\n  {'TOTAL':15} {total:5}")

neo4j_driver.close()
