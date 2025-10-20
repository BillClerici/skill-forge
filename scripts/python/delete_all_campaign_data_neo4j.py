"""
Delete ALL Campaign-Related Data from Neo4j
Keeps: Accounts, Players, Characters, Universes, Worlds, Regions, Locations, Species
Deletes: Everything related to campaigns and gameplay
"""

import os
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_pass')

def delete_all_campaign_data():
    """Delete ALL campaign-related nodes from Neo4j"""

    print("=" * 80)
    print("DELETE ALL CAMPAIGN DATA FROM NEO4J")
    print("=" * 80)
    print("\nThis will DELETE all campaign-related nodes:")
    print("  ❌ Campaigns")
    print("  ❌ CampaignObjectives")
    print("  ❌ QuestObjectives")
    print("  ❌ Quests")
    print("  ❌ Places")
    print("  ❌ Scenes")
    print("  ❌ NPCs")
    print("  ❌ Challenges")
    print("  ❌ Discoveries")
    print("  ❌ Events")
    print("  ❌ Knowledge")
    print("  ❌ Items")
    print("  ❌ Rubrics")
    print("\nThis will KEEP:")
    print("  ✅ Accounts")
    print("  ✅ Players")
    print("  ✅ Characters")
    print("  ✅ Universes")
    print("  ✅ Worlds")
    print("  ✅ Regions")
    print("  ✅ Locations")
    print("  ✅ Species")
    print("  ✅ Dimensions")
    print("\n" + "=" * 80)

    response = input("Are you SURE you want to delete ALL campaign data? (type 'DELETE ALL' to confirm): ")
    if response != 'DELETE ALL':
        print("❌ Aborted.")
        return

    # Connect to Neo4j
    print("\n🔌 Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    deletion_summary = {}
    total_deleted = 0

    with driver.session() as session:
        print("\n🗑️  Deleting campaign-related nodes...")

        # 1. Delete CampaignObjective nodes
        print("\n   [1/13] Deleting CampaignObjective nodes...")
        result = session.run("""
            MATCH (co:CampaignObjective)
            DETACH DELETE co
            RETURN count(co) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['CampaignObjective'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} CampaignObjective nodes")

        # 2. Delete QuestObjective nodes
        print("   [2/13] Deleting QuestObjective nodes...")
        result = session.run("""
            MATCH (qo:QuestObjective)
            DETACH DELETE qo
            RETURN count(qo) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['QuestObjective'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} QuestObjective nodes")

        # 3. Delete Quest nodes
        print("   [3/13] Deleting Quest nodes...")
        result = session.run("""
            MATCH (q:Quest)
            DETACH DELETE q
            RETURN count(q) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Quest'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Quest nodes")

        # 4. Delete Place nodes
        print("   [4/13] Deleting Place nodes...")
        result = session.run("""
            MATCH (p:Place)
            DETACH DELETE p
            RETURN count(p) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Place'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Place nodes")

        # 5. Delete Scene nodes
        print("   [5/13] Deleting Scene nodes...")
        result = session.run("""
            MATCH (s:Scene)
            DETACH DELETE s
            RETURN count(s) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Scene'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Scene nodes")

        # 6. Delete NPC nodes
        print("   [6/13] Deleting NPC nodes...")
        result = session.run("""
            MATCH (n:NPC)
            DETACH DELETE n
            RETURN count(n) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['NPC'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} NPC nodes")

        # 7. Delete Challenge nodes
        print("   [7/13] Deleting Challenge nodes...")
        result = session.run("""
            MATCH (c:Challenge)
            DETACH DELETE c
            RETURN count(c) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Challenge'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Challenge nodes")

        # 8. Delete Discovery nodes
        print("   [8/13] Deleting Discovery nodes...")
        result = session.run("""
            MATCH (d:Discovery)
            DETACH DELETE d
            RETURN count(d) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Discovery'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Discovery nodes")

        # 9. Delete Event nodes
        print("   [9/13] Deleting Event nodes...")
        result = session.run("""
            MATCH (e:Event)
            DETACH DELETE e
            RETURN count(e) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Event'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Event nodes")

        # 10. Delete Knowledge nodes
        print("   [10/13] Deleting Knowledge nodes...")
        result = session.run("""
            MATCH (k:Knowledge)
            DETACH DELETE k
            RETURN count(k) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Knowledge'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Knowledge nodes")

        # 11. Delete Item nodes
        print("   [11/13] Deleting Item nodes...")
        result = session.run("""
            MATCH (i:Item)
            DETACH DELETE i
            RETURN count(i) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Item'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Item nodes")

        # 12. Delete Rubric nodes
        print("   [12/13] Deleting Rubric nodes...")
        result = session.run("""
            MATCH (r:Rubric)
            DETACH DELETE r
            RETURN count(r) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Rubric'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Rubric nodes")

        # 13. Delete Campaign nodes (last)
        print("   [13/13] Deleting Campaign nodes...")
        result = session.run("""
            MATCH (c:Campaign)
            DETACH DELETE c
            RETURN count(c) as deleted_count
        """)
        count = result.single()['deleted_count']
        deletion_summary['Campaign'] = count
        total_deleted += count
        print(f"          ✓ Deleted {count} Campaign nodes")

        print("\n" + "=" * 80)
        print("✅ DELETION COMPLETE")
        print("=" * 80)

        print("\n📊 Deletion Summary:")
        for node_type, count in deletion_summary.items():
            print(f"   {node_type:25} {count:>6} nodes")

        print(f"\n   {'TOTAL':25} {total_deleted:>6} nodes deleted")

        # Verify preserved nodes
        print("\n" + "=" * 80)
        print("✅ PRESERVED NODE COUNTS")
        print("=" * 80)

        preserved_types = [
            'Account', 'Player', 'Character',
            'Universe', 'World', 'Region', 'Location', 'Species',
            'Dimension'
        ]

        for node_type in preserved_types:
            result = session.run(f"MATCH (n:{node_type}) RETURN count(n) as count")
            count = result.single()['count']
            print(f"   {node_type:25} {count:>6} nodes")

    driver.close()
    print("\n✅ All campaign data has been deleted from Neo4j!")
    print("   Your world-building data (Universes, Worlds, Regions, etc.) is intact.\n")

if __name__ == '__main__':
    try:
        delete_all_campaign_data()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
