#!/usr/bin/env python3
"""Check Neo4j for Campaign and NPC data"""
from neo4j import GraphDatabase
import os

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
username = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD', '')

driver = GraphDatabase.driver(uri, auth=(username, password))

with driver.session() as session:
    # Check for campaigns
    result = session.run("""
        MATCH (c:Campaign)
        RETURN c.id AS id, c.name AS name, c.campaign_id AS campaign_id
        ORDER BY c.created_at DESC
        LIMIT 1
    """)
    campaigns = list(result)

    if campaigns:
        campaign = campaigns[0]
        print(f"Most recent campaign in Neo4j:")
        print(f"  Name: {campaign['name']}")
        print(f"  ID: {campaign['id']}")
        print(f"  campaign_id: {campaign['campaign_id']}")

        campaign_id = campaign['campaign_id'] or campaign['id']

        # Get NPCs for this campaign
        print(f"\nNPCs in campaign:")
        result = session.run("""
            MATCH (c:Campaign {campaign_id: $campaign_id})-[:HAS_NPC]->(n:NPC)
            RETURN n.id AS id, n.name AS name, n.species_id AS species_id, n.species_name AS species_name
            LIMIT 10
        """, campaign_id=campaign_id)
        npcs = list(result)

        for npc in npcs:
            print(f"  {npc['name']} - species_id: {npc['species_id']} - species_name: {npc['species_name']}")

        # Check unique species referenced by NPCs
        print(f"\nChecking if referenced species exist:")
        result = session.run("""
            MATCH (c:Campaign {campaign_id: $campaign_id})-[:HAS_NPC]->(n:NPC)
            WITH DISTINCT n.species_id AS species_id
            OPTIONAL MATCH (s:Species {id: species_id})
            RETURN species_id, s.name AS species_name, s IS NOT NULL AS exists
        """, campaign_id=campaign_id)
        species_refs = list(result)

        for ref in species_refs:
            status = "EXISTS" if ref['exists'] else "MISSING"
            print(f"  {ref['species_id']} - {status}")
            if ref['species_name']:
                print(f"    Name: {ref['species_name']}")
    else:
        print("No campaigns found in Neo4j")

    # Check total counts
    result = session.run("MATCH (c:Campaign) RETURN count(c) AS count")
    campaign_count = result.single()['count']

    result = session.run("MATCH (n:NPC) RETURN count(n) AS count")
    npc_count = result.single()['count']

    result = session.run("MATCH (s:Species) RETURN count(s) AS count")
    species_count = result.single()['count']

    print(f"\nTotal counts in Neo4j:")
    print(f"  Campaigns: {campaign_count}")
    print(f"  NPCs: {npc_count}")
    print(f"  Species: {species_count}")

driver.close()
