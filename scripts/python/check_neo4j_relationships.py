#!/usr/bin/env python3
"""Check Neo4j relationship structure"""
from neo4j import GraphDatabase
import os

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
username = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD', '')

driver = GraphDatabase.driver(uri, auth=(username, password))

with driver.session() as session:
    # Get most recent campaign by any identifier
    result = session.run("""
        MATCH (c:Campaign)
        RETURN c.id AS id, c.name AS name, c.campaign_id AS campaign_id
        ORDER BY c.id DESC
        LIMIT 1
    """)
    campaign = result.single()

    if campaign:
        print(f"Most recent campaign:")
        print(f"  Name: {campaign['name']}")
        print(f"  id property: {campaign['id']}")
        print(f"  campaign_id property: {campaign['campaign_id']}")

        # Use the id property to find NPCs
        campaign_node_id = campaign['id']

        print(f"\nLooking for NPCs using id: {campaign_node_id}")

        # Try to find NPCs without filtering by campaign
        result = session.run("""
            MATCH (n:NPC)
            RETURN n.id AS id, n.name AS name, n.species_id AS species_id, n.species_name AS species_name, n.campaign_id AS campaign_id
            LIMIT 10
        """)
        npcs = list(result)

        print(f"\nAll NPCs (first 10):")
        for npc in npcs:
            print(f"  {npc['name']}")
            print(f"    id: {npc['id']}")
            print(f"    species_id: {npc['species_id']}")
            print(f"    species_name: {npc['species_name']}")
            print(f"    campaign_id: {npc['campaign_id']}")

        # Check relationships FROM Campaign
        print(f"\nRelationships from Campaign node:")
        result = session.run("""
            MATCH (c:Campaign {id: $campaign_id})-[r]->(target)
            RETURN type(r) AS rel_type, labels(target) AS target_labels, count(*) AS count
        """, campaign_id=campaign_node_id)
        rels = list(result)

        for rel in rels:
            print(f"  {rel['rel_type']} -> {rel['target_labels']}: {rel['count']}")

        # Check if NPCs have relationship TO Campaign
        print(f"\nRelationships TO Campaign node:")
        result = session.run("""
            MATCH (source)-[r]->(c:Campaign {id: $campaign_id})
            RETURN type(r) AS rel_type, labels(source) AS source_labels, count(*) AS count
        """, campaign_id=campaign_node_id)
        rels = list(result)

        for rel in rels:
            print(f"  {rel['source_labels']} -{rel['rel_type']}-> Campaign: {rel['count']}")

        # Check unique species IDs from NPCs
        print(f"\nUnique species referenced by NPCs:")
        result = session.run("""
            MATCH (n:NPC)
            WITH DISTINCT n.species_id AS species_id, n.species_name AS species_name
            RETURN species_id, species_name
            LIMIT 10
        """)
        species_refs = list(result)

        for ref in species_refs:
            # Check if this species exists
            result2 = session.run("""
                MATCH (s:Species {id: $species_id})
                RETURN s.name AS name
            """, species_id=ref['species_id'])
            species = result2.single()

            if species:
                print(f"  {ref['species_id']} ({ref['species_name']}) - EXISTS in Neo4j")
            else:
                print(f"  {ref['species_id']} ({ref['species_name']}) - MISSING in Neo4j")

driver.close()
