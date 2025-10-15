"""
Clear Campaign Data Script
Removes all campaign-related data while preserving foundational entities

KEEPS:
- Accounts, Players, Characters
- Universes, Worlds, Regions, Locations, Species

REMOVES:
- Campaigns, Quests, Places, Scenes
- NPCs, Discoveries, Events, Challenges
- Knowledge, Items, Rubrics
- Campaign Factory state/audit data
- Redis cache, RabbitMQ queues
"""

import os
import sys
from pymongo import MongoClient
from neo4j import GraphDatabase
import psycopg2
import redis

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables
MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', 'mongo_dev_pass_2024')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'skillforge_dev_pass_2024')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'rabbitmq_dev_pass_2024')

# Database connections
MONGODB_URI = f'mongodb://admin:{MONGO_PASSWORD}@localhost:27017'
NEO4J_URI = 'bolt://localhost:7687'
POSTGRES_URI = f'postgresql://skillforge_user:{POSTGRES_PASSWORD}@localhost:5432/skillforge'
REDIS_URL = 'redis://localhost:6379'


def clear_mongodb():
    """Clear campaign-related collections from MongoDB"""
    print("\n=== Clearing MongoDB ===")

    client = MongoClient(MONGODB_URI)
    db = client.skillforge

    # Collections to DELETE (campaign-related)
    campaign_collections = [
        'campaigns',
        'quests',
        'places',
        'scenes',
        'npcs',
        'discoveries',
        'events',
        'challenges',
        'knowledge',
        'items',
        'rubrics',
        'world_factory_state',
        'world_factory_results',
        'world_factory_audit'
    ]

    # Collections to KEEP (foundational)
    keep_collections = [
        'universe_definitions',
        'world_definitions',
        'region_definitions',
        'location_definitions',
        'species_definitions'
    ]

    for collection_name in campaign_collections:
        if collection_name in db.list_collection_names():
            count = db[collection_name].count_documents({})
            result = db[collection_name].delete_many({})
            print(f"✓ Cleared {collection_name}: {result.deleted_count} documents deleted (had {count})")
        else:
            print(f"  {collection_name}: collection doesn't exist")

    # Verify keep collections are untouched
    print("\nVerifying preserved collections:")
    for collection_name in keep_collections:
        if collection_name in db.list_collection_names():
            count = db[collection_name].count_documents({})
            print(f"  {collection_name}: {count} documents preserved")

    client.close()


def clear_neo4j():
    """Clear campaign-related nodes and relationships from Neo4j"""
    print("\n=== Clearing Neo4j ===")

    driver = GraphDatabase.driver(NEO4J_URI, auth=('neo4j', NEO4J_PASSWORD))

    with driver.session() as session:
        # Delete campaign-related nodes and their relationships
        # Order matters: delete children before parents

        # 1. Delete Rubrics (linked to NPCs, Challenges, etc.)
        result = session.run("MATCH (r:Rubric) DETACH DELETE r RETURN count(r) as count")
        print(f"✓ Deleted Rubrics: {result.single()['count']} nodes")

        # 2. Delete Knowledge and Items
        result = session.run("MATCH (k:Knowledge) DETACH DELETE k RETURN count(k) as count")
        print(f"✓ Deleted Knowledge: {result.single()['count']} nodes")

        result = session.run("MATCH (i:Item) DETACH DELETE i RETURN count(i) as count")
        print(f"✓ Deleted Items: {result.single()['count']} nodes")

        # 3. Delete scene elements (NPCs, Discoveries, Events, Challenges)
        result = session.run("MATCH (n:NPC) DETACH DELETE n RETURN count(n) as count")
        print(f"✓ Deleted NPCs: {result.single()['count']} nodes")

        result = session.run("MATCH (d:Discovery) DETACH DELETE d RETURN count(d) as count")
        print(f"✓ Deleted Discoveries: {result.single()['count']} nodes")

        result = session.run("MATCH (e:Event) DETACH DELETE e RETURN count(e) as count")
        print(f"✓ Deleted Events: {result.single()['count']} nodes")

        result = session.run("MATCH (c:Challenge) DETACH DELETE c RETURN count(c) as count")
        print(f"✓ Deleted Challenges: {result.single()['count']} nodes")

        # 4. Delete Scenes
        result = session.run("MATCH (s:Scene) DETACH DELETE s RETURN count(s) as count")
        print(f"✓ Deleted Scenes: {result.single()['count']} nodes")

        # 5. Delete Places
        result = session.run("MATCH (p:Place) DETACH DELETE p RETURN count(p) as count")
        print(f"✓ Deleted Places: {result.single()['count']} nodes")

        # 6. Delete Quests
        result = session.run("MATCH (q:Quest) DETACH DELETE q RETURN count(q) as count")
        print(f"✓ Deleted Quests: {result.single()['count']} nodes")

        # 7. Delete Campaigns
        result = session.run("MATCH (c:Campaign) DETACH DELETE c RETURN count(c) as count")
        print(f"✓ Deleted Campaigns: {result.single()['count']} nodes")

        # Verify preserved nodes
        print("\nVerifying preserved nodes:")
        preserved_labels = ['World', 'Region', 'Location', 'Species', 'Character', 'Player']
        for label in preserved_labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            count = result.single()['count']
            if count > 0:
                print(f"  {label}: {count} nodes preserved")

    driver.close()


def clear_postgres():
    """Clear campaign-related tables from PostgreSQL"""
    print("\n=== Clearing PostgreSQL ===")

    conn = psycopg2.connect(POSTGRES_URI)
    cur = conn.cursor()

    # Check if campaign-related tables exist
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE '%campaign%'
        OR table_name LIKE '%quest%'
        OR table_name IN ('places', 'scenes', 'npcs', 'challenges', 'discoveries', 'events')
    """)

    campaign_tables = [row[0] for row in cur.fetchall()]

    if campaign_tables:
        for table in campaign_tables:
            cur.execute(f"SELECT count(*) FROM {table}")
            count = cur.fetchone()[0]

            cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            print(f"✓ Cleared {table}: {count} rows deleted")

        conn.commit()
    else:
        print("  No campaign-related tables found")

    # Verify preserved tables
    print("\nVerifying preserved tables:")
    preserved_tables = ['accounts', 'players', 'characters', 'universes', 'worlds', 'regions']
    for table in preserved_tables:
        cur.execute(f"""
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = '{table}'
        """)
        if cur.fetchone()[0] > 0:
            cur.execute(f"SELECT count(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table}: {count} rows preserved")

    cur.close()
    conn.close()


def clear_redis():
    """Clear Redis cache"""
    print("\n=== Clearing Redis ===")

    r = redis.from_url(REDIS_URL)

    # Get all keys
    all_keys = r.keys('*')

    if all_keys:
        # Clear campaign-related keys
        campaign_patterns = [
            'campaign:*',
            'quest:*',
            'place:*',
            'scene:*',
            'npc:*',
            'workflow:*',
            'factory:*'
        ]

        deleted_count = 0
        for pattern in campaign_patterns:
            keys = r.keys(pattern)
            if keys:
                deleted = r.delete(*keys)
                deleted_count += deleted
                print(f"✓ Cleared {pattern}: {deleted} keys deleted")

        if deleted_count == 0:
            print("  No campaign-related keys found")

        # Show remaining keys (should be non-campaign related)
        remaining = r.keys('*')
        if remaining:
            print(f"\nRemaining keys: {len(remaining)}")
            for key in remaining[:10]:  # Show first 10
                print(f"  - {key.decode('utf-8')}")
            if len(remaining) > 10:
                print(f"  ... and {len(remaining) - 10} more")
    else:
        print("  Redis is empty")

    r.close()


def clear_rabbitmq():
    """Clear RabbitMQ queues"""
    print("\n=== Clearing RabbitMQ ===")

    try:
        import pika

        credentials = pika.PlainCredentials('skillforge', RABBITMQ_PASSWORD)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters('localhost', 5672, '/', credentials)
        )
        channel = connection.channel()

        # List of queues to purge
        campaign_queues = [
            'campaign_factory',
            'world_factory',
            'quest_generation',
            'npc_generation',
            'story_generation'
        ]

        for queue_name in campaign_queues:
            try:
                result = channel.queue_purge(queue_name)
                print(f"✓ Cleared {queue_name}: {result} messages purged")
            except Exception as e:
                print(f"  {queue_name}: queue doesn't exist or error - {str(e)}")

        connection.close()

    except ImportError:
        print("  pika library not installed - skipping RabbitMQ cleanup")
        print("  You can manually purge queues via RabbitMQ Management UI at http://localhost:15672")
    except Exception as e:
        print(f"  Error connecting to RabbitMQ: {str(e)}")
        print("  You can manually purge queues via RabbitMQ Management UI at http://localhost:15672")


def main():
    """Main cleanup function"""
    import sys

    print("=" * 60)
    print("  SKILL FORGE - Campaign Data Cleanup")
    print("=" * 60)
    print("\nThis script will DELETE all campaign-related data:")
    print("  - Campaigns, Quests, Places, Scenes")
    print("  - NPCs, Discoveries, Events, Challenges")
    print("  - Knowledge, Items, Rubrics")
    print("  - Campaign Factory state/audit data")
    print("  - Redis cache, RabbitMQ queues")
    print("\nThis script will PRESERVE:")
    print("  - Accounts, Players, Characters")
    print("  - Universes, Worlds, Regions, Locations, Species")
    print("\n" + "=" * 60)

    # Auto-confirm for initial prompt too
    if len(sys.argv) > 1 and sys.argv[1] == '--auto-confirm':
        print("\nAuto-confirming cleanup...")
        response = 'yes'
    else:
        response = input("\nAre you sure you want to continue? (yes/no): ")

    if response.lower() != 'yes':
        print("\nAborted - no data was deleted")
        return

    try:
        clear_mongodb()
        clear_neo4j()
        clear_postgres()
        clear_redis()
        clear_rabbitmq()

        print("\n" + "=" * 60)
        print("  ✓ Campaign Data Cleanup Complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
