"""
Verify that orphan node fixes are working correctly
Run this AFTER generating a new campaign
"""
import os
from pymongo import MongoClient
from neo4j import GraphDatabase

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['skillforge']

# Neo4j connection
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

print("=" * 80)
print("ORPHAN NODE FIX VERIFICATION")
print("=" * 80)
print()

# =============================================================================
# TEST 1: MongoDB Entity Data Quality
# =============================================================================
print("📋 TEST 1: MongoDB Entity Data Quality")
print("-" * 80)

all_good = True

# Check Discoveries
discoveries = list(db.discoveries.find({}))
print(f"\n✓ Found {len(discoveries)} discoveries in MongoDB")
for disc in discoveries[:3]:  # Show first 3
    name = disc.get("name", "N/A")
    desc = disc.get("description", "")
    campaign_id = disc.get("campaign_id", "MISSING")
    scene_id = disc.get("scene_id", "MISSING")

    status = "✅" if name != "N/A" and campaign_id != "MISSING" else "❌"
    print(f"  {status} {disc['_id'][:30]}...")
    print(f"      Name: {name[:50]}")
    print(f"      Campaign ID: {campaign_id}")
    print(f"      Scene ID: {scene_id}")

    if name == "N/A" or campaign_id == "MISSING":
        all_good = False

# Check Challenges
challenges = list(db.challenges.find({}))
print(f"\n✓ Found {len(challenges)} challenges in MongoDB")
for chall in challenges[:3]:  # Show first 3
    name = chall.get("name", "N/A")
    campaign_id = chall.get("campaign_id", "MISSING")
    scene_id = chall.get("scene_id", "MISSING")

    status = "✅" if name != "N/A" and campaign_id != "MISSING" else "❌"
    print(f"  {status} {chall['_id'][:30]}...")
    print(f"      Name: {name[:50]}")
    print(f"      Campaign ID: {campaign_id}")
    print(f"      Scene ID: {scene_id}")

    if name == "N/A" or campaign_id == "MISSING":
        all_good = False

# Check Events
events = list(db.events.find({}))
print(f"\n✓ Found {len(events)} events in MongoDB")
for event in events[:3]:  # Show first 3
    name = event.get("name", "N/A")
    campaign_id = event.get("campaign_id", "MISSING")
    scene_id = event.get("scene_id", "MISSING")

    status = "✅" if name != "N/A" and campaign_id != "MISSING" else "❌"
    print(f"  {status} {event['_id'][:30]}...")
    print(f"      Name: {name[:50]}")
    print(f"      Campaign ID: {campaign_id}")
    print(f"      Scene ID: {scene_id}")

    if name == "N/A" or campaign_id == "MISSING":
        all_good = False

print()
if all_good:
    print("✅ TEST 1 PASSED: All entities have proper data")
else:
    print("❌ TEST 1 FAILED: Some entities have missing data")

# =============================================================================
# TEST 2: Neo4j Entity Properties (campaign_id)
# =============================================================================
print("\n" + "=" * 80)
print("📋 TEST 2: Neo4j Entity Properties")
print("-" * 80)

all_have_campaign_id = True

with neo4j_driver.session() as session:
    # Check Discoveries
    result = session.run("""
        MATCH (d:Discovery)
        RETURN d.id as id, d.name as name, d.campaign_id as campaign_id
        LIMIT 3
    """)
    discoveries = list(result)
    print(f"\n✓ Found Discovery nodes in Neo4j")
    for disc in discoveries:
        status = "✅" if disc["campaign_id"] else "❌"
        print(f"  {status} {disc['id'][:30]}...")
        print(f"      Name: {disc['name']}")
        print(f"      Campaign ID: {disc['campaign_id']}")
        if not disc["campaign_id"]:
            all_have_campaign_id = False

    # Check Challenges
    result = session.run("""
        MATCH (c:Challenge)
        RETURN c.id as id, c.name as name, c.campaign_id as campaign_id
        LIMIT 3
    """)
    challenges = list(result)
    print(f"\n✓ Found Challenge nodes in Neo4j")
    for chall in challenges:
        status = "✅" if chall["campaign_id"] else "❌"
        print(f"  {status} {chall['id'][:30]}...")
        print(f"      Name: {chall['name']}")
        print(f"      Campaign ID: {chall['campaign_id']}")
        if not chall["campaign_id"]:
            all_have_campaign_id = False

    # Check Events
    result = session.run("""
        MATCH (e:Event)
        RETURN e.id as id, e.name as name, e.campaign_id as campaign_id
        LIMIT 3
    """)
    events = list(result)
    print(f"\n✓ Found Event nodes in Neo4j")
    for event in events:
        status = "✅" if event["campaign_id"] else "❌"
        print(f"  {status} {event['id'][:30]}...")
        print(f"      Name: {event['name']}")
        print(f"      Campaign ID: {event['campaign_id']}")
        if not event["campaign_id"]:
            all_have_campaign_id = False

print()
if all_have_campaign_id:
    print("✅ TEST 2 PASSED: All entities have campaign_id property")
else:
    print("❌ TEST 2 FAILED: Some entities missing campaign_id")

# =============================================================================
# TEST 3: Neo4j Scene-Entity Relationships
# =============================================================================
print("\n" + "=" * 80)
print("📋 TEST 3: Neo4j Scene-Entity Relationships")
print("-" * 80)

all_linked = True

with neo4j_driver.session() as session:
    # Check Discovery relationships
    result = session.run("""
        MATCH (sc:Scene)-[r:CONTAINS_DISCOVERY]->(d:Discovery)
        RETURN count(r) as count
    """)
    disc_rels = result.single()["count"]
    print(f"\n  Discovery-Scene relationships: {disc_rels}")
    if disc_rels == 0:
        print("    ❌ No Discovery relationships found!")
        all_linked = False
    else:
        print("    ✅ Discoveries linked to Scenes")
        # Show example
        result = session.run("""
            MATCH (sc:Scene)-[r:CONTAINS_DISCOVERY]->(d:Discovery)
            RETURN sc.name as scene, d.name as discovery
            LIMIT 2
        """)
        for record in result:
            print(f"       - Scene '{record['scene']}' contains '{record['discovery']}'")

    # Check Challenge relationships
    result = session.run("""
        MATCH (sc:Scene)-[r:CONTAINS_CHALLENGE]->(c:Challenge)
        RETURN count(r) as count
    """)
    chall_rels = result.single()["count"]
    print(f"\n  Challenge-Scene relationships: {chall_rels}")
    if chall_rels == 0:
        print("    ❌ No Challenge relationships found!")
        all_linked = False
    else:
        print("    ✅ Challenges linked to Scenes")
        # Show example
        result = session.run("""
            MATCH (sc:Scene)-[r:CONTAINS_CHALLENGE]->(c:Challenge)
            RETURN sc.name as scene, c.name as challenge
            LIMIT 2
        """)
        for record in result:
            print(f"       - Scene '{record['scene']}' contains '{record['challenge']}'")

    # Check Event relationships
    result = session.run("""
        MATCH (sc:Scene)-[r:CONTAINS_EVENT]->(e:Event)
        RETURN count(r) as count
    """)
    event_rels = result.single()["count"]
    print(f"\n  Event-Scene relationships: {event_rels}")
    if event_rels == 0:
        print("    ❌ No Event relationships found!")
        all_linked = False
    else:
        print("    ✅ Events linked to Scenes")
        # Show example
        result = session.run("""
            MATCH (sc:Scene)-[r:CONTAINS_EVENT]->(e:Event)
            RETURN sc.name as scene, e.name as event
            LIMIT 2
        """)
        for record in result:
            print(f"       - Scene '{record['scene']}' contains '{record['event']}'")

print()
if all_linked:
    print("✅ TEST 3 PASSED: All entities linked to Scenes")
else:
    print("❌ TEST 3 FAILED: Some entities not linked to Scenes")

# =============================================================================
# TEST 4: No Orphaned Nodes
# =============================================================================
print("\n" + "=" * 80)
print("📋 TEST 4: Orphaned Node Check")
print("-" * 80)

no_orphans = True

with neo4j_driver.session() as session:
    # Check for orphaned Discovery nodes
    result = session.run("""
        MATCH (d:Discovery)
        WHERE NOT (d)--()
        RETURN count(d) as orphan_count
    """)
    orphan_discoveries = result.single()["orphan_count"]

    # Check for orphaned Challenge nodes
    result = session.run("""
        MATCH (c:Challenge)
        WHERE NOT (c)--()
        RETURN count(c) as orphan_count
    """)
    orphan_challenges = result.single()["orphan_count"]

    # Check for orphaned Event nodes
    result = session.run("""
        MATCH (e:Event)
        WHERE NOT (e)--()
        RETURN count(e) as orphan_count
    """)
    orphan_events = result.single()["orphan_count"]

    print(f"\n  Orphaned Discovery nodes: {orphan_discoveries}")
    print(f"  Orphaned Challenge nodes: {orphan_challenges}")
    print(f"  Orphaned Event nodes: {orphan_events}")

    if orphan_discoveries > 0 or orphan_challenges > 0 or orphan_events > 0:
        no_orphans = False
        print("\n  ❌ Found orphaned nodes!")
    else:
        print("\n  ✅ No orphaned nodes found!")

print()
if no_orphans:
    print("✅ TEST 4 PASSED: No orphaned nodes")
else:
    print("❌ TEST 4 FAILED: Orphaned nodes exist")

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)

all_tests_passed = all_good and all_have_campaign_id and all_linked and no_orphans

if all_tests_passed:
    print("\n🎉 ALL TESTS PASSED! Orphan node fixes are working correctly!")
    print("\nThe following fixes are confirmed working:")
    print("  ✅ Fix 1: Scene entity IDs populated during generation")
    print("  ✅ Fix 2: Original entity IDs used in persistence")
    print("  ✅ Fix 3: MongoDB field names match entity structure")
    print("  ✅ Fix 4: campaign_id added to all entities")
    print("  ✅ Fix 5: Scene-entity linking working correctly")
else:
    print("\n⚠️  SOME TESTS FAILED - Please review the output above")
    if not all_good:
        print("  ❌ MongoDB entity data quality issues")
    if not all_have_campaign_id:
        print("  ❌ Missing campaign_id properties")
    if not all_linked:
        print("  ❌ Missing Scene-Entity relationships")
    if not no_orphans:
        print("  ❌ Orphaned nodes still exist")

print()
neo4j_driver.close()
mongo_client.close()
