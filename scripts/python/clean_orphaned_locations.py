"""
Clean Orphaned Location Nodes
Removes Location nodes that have direct relationships to World (incorrect hierarchy)
Keeps Location nodes that follow proper hierarchy (Region -> L1 -> L2 -> L3)
"""
import os
import sys
from neo4j import GraphDatabase

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')

# Neo4j connection
NEO4J_URI = 'bolt://localhost:7687'


def clean_neo4j_orphaned_locations():
    """
    Delete Location nodes with direct PART_OF relationships to World
    Keep Location nodes with proper CHILD_OF relationships
    """
    print("\n=== Cleaning Neo4j Orphaned Locations ===")

    driver = GraphDatabase.driver(NEO4J_URI, auth=('neo4j', NEO4J_PASSWORD))

    with driver.session() as session:
        # First, identify locations with direct World relationships
        result = session.run("""
            MATCH (loc:Location)-[:PART_OF]->(w:World)
            RETURN count(loc) as count
        """)
        orphaned_count = result.single()['count']

        print(f"\nFound {orphaned_count} Location nodes with direct PART_OF relationships to World")

        if orphaned_count > 0:
            # Show sample of orphaned locations
            print("\nSample of orphaned locations:")
            sample_result = session.run("""
                MATCH (loc:Location)-[:PART_OF]->(w:World)
                RETURN loc.name as name, loc.id as id, w.name as world_name
                LIMIT 10
            """)
            for record in sample_result:
                print(f"  - {record['name']} (ID: {record['id']}) -> World: {record['world_name']}")

            if orphaned_count > 10:
                print(f"  ... and {orphaned_count - 10} more")

        # Count properly hierarchical locations (should be kept)
        result = session.run("""
            MATCH (loc:Location)
            WHERE NOT (loc)-[:PART_OF]->(:World)
            RETURN count(loc) as count
        """)
        valid_count = result.single()['count']

        print(f"\n{valid_count} Location nodes follow proper hierarchy (will be KEPT)")

        # Show statistics about relationship types
        print("\nLocation relationship statistics:")

        result = session.run("""
            MATCH (loc:Location)-[:CHILD_OF]->(parent)
            RETURN labels(parent) as parent_type, count(loc) as count
        """)
        for record in result:
            parent_label = record['parent_type'][0] if record['parent_type'] else 'Unknown'
            print(f"  - CHILD_OF {parent_label}: {record['count']} locations")

        result = session.run("""
            MATCH (loc:Location)-[:PART_OF]->(w:World)
            RETURN count(loc) as count
        """)
        print(f"  - PART_OF World: {result.single()['count']} locations (TO BE DELETED)")

    driver.close()

    return orphaned_count, valid_count


def delete_orphaned_locations():
    """
    Delete Location nodes with direct PART_OF relationships to World
    """
    print("\n=== Deleting Orphaned Locations ===")

    driver = GraphDatabase.driver(NEO4J_URI, auth=('neo4j', NEO4J_PASSWORD))

    with driver.session() as session:
        # Delete Location nodes with direct PART_OF relationships to World
        # DETACH DELETE removes the node and all its relationships
        result = session.run("""
            MATCH (loc:Location)-[:PART_OF]->(w:World)
            DETACH DELETE loc
            RETURN count(loc) as deleted_count
        """)
        deleted_count = result.single()['deleted_count']

        print(f"✓ Deleted {deleted_count} orphaned Location nodes")

        # Verify remaining locations
        result = session.run("""
            MATCH (loc:Location)
            RETURN count(loc) as remaining_count
        """)
        remaining_count = result.single()['remaining_count']

        print(f"✓ {remaining_count} Location nodes remain (proper hierarchy)")

        # Show breakdown of remaining locations
        print("\nRemaining locations by hierarchy level:")

        # Level 1 (children of Region)
        result = session.run("""
            MATCH (loc:Location)-[:CHILD_OF]->(r:Region)
            RETURN count(loc) as count
        """)
        l1_count = result.single()['count']
        print(f"  - Level 1 (CHILD_OF Region): {l1_count} locations")

        # Level 2 (children of Level 1 locations)
        result = session.run("""
            MATCH (loc:Location)-[:CHILD_OF]->(parent:Location)-[:CHILD_OF]->(r:Region)
            RETURN count(loc) as count
        """)
        l2_count = result.single()['count']
        print(f"  - Level 2 (CHILD_OF Level 1): {l2_count} locations")

        # Level 3 (children of Level 2 locations)
        result = session.run("""
            MATCH (loc:Location)-[:CHILD_OF]->(l2:Location)-[:CHILD_OF]->(l1:Location)-[:CHILD_OF]->(r:Region)
            RETURN count(loc) as count
        """)
        l3_count = result.single()['count']
        print(f"  - Level 3 (CHILD_OF Level 2): {l3_count} locations")

        # Locations without CHILD_OF (might be pre-existing world locations)
        result = session.run("""
            MATCH (loc:Location)
            WHERE NOT (loc)-[:CHILD_OF]->()
            RETURN count(loc) as count
        """)
        no_parent_count = result.single()['count']
        if no_parent_count > 0:
            print(f"  - No parent relationship: {no_parent_count} locations (pre-existing)")

    driver.close()

    return deleted_count, remaining_count


def main():
    """Main cleanup function"""
    print("=" * 60)
    print("  SKILL FORGE - Clean Orphaned Locations")
    print("=" * 60)
    print("\nThis script will DELETE Location nodes with direct PART_OF")
    print("relationships to World (incorrect hierarchy).")
    print("\nThis script will PRESERVE Location nodes with proper")
    print("CHILD_OF relationships (Region -> L1 -> L2 -> L3).")
    print("\n" + "=" * 60)

    # Analyze before deletion
    orphaned_count, valid_count = clean_neo4j_orphaned_locations()

    if orphaned_count == 0:
        print("\n✓ No orphaned locations found - database is clean!")
        return

    print("\n" + "=" * 60)

    # Auto-confirm deletion (for script usage)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--auto-confirm':
        print(f"\nAuto-confirming deletion of {orphaned_count} orphaned Location nodes...")
        response = 'yes'
    else:
        response = input(f"\nDelete {orphaned_count} orphaned Location nodes? (yes/no): ")

    if response.lower() != 'yes':
        print("\nAborted - no data was deleted")
        return

    try:
        deleted_count, remaining_count = delete_orphaned_locations()

        print("\n" + "=" * 60)
        print("  ✓ Orphaned Location Cleanup Complete!")
        print("=" * 60)
        print(f"\nDeleted: {deleted_count} orphaned locations")
        print(f"Remaining: {remaining_count} valid locations")
        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n✗ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
