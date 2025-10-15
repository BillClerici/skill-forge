"""
Check location data in MongoDB vs Neo4j
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

print("Checking Locations...\n")

# Check MongoDB locations
mongo_locations = list(db.location_definitions.find({}, {'_id': 1, 'location_name': 1, 'region_id': 1}))
print(f"MongoDB has {len(mongo_locations)} location_definitions")
for loc in mongo_locations[:10]:
    print(f"  - {loc['_id']}: {loc.get('location_name', 'Unknown')} (region: {loc.get('region_id', 'N/A')})")

print()

# Check campaign places
campaign_places = list(db.places.find({}, {'_id': 1, 'name': 1, 'quest_id': 1}))
print(f"MongoDB has {len(campaign_places)} campaign places")
for place in campaign_places[:5]:
    print(f"  - {place['_id']}: {place.get('name', 'Unknown')}")

print()

# Check Neo4j
with neo4j_driver.session() as session:
    # Check Location nodes
    result = session.run("MATCH (l:Location) RETURN l.id as id, l.name as name")
    neo4j_locations = list(result)
    print(f"Neo4j has {len(neo4j_locations)} Location nodes")
    for loc in neo4j_locations[:10]:
        print(f"  - {loc['id']}: {loc['name']}")

    print()

    # Check Place nodes
    result = session.run("MATCH (p:Place) RETURN p.id as id, p.name as name")
    neo4j_places = list(result)
    print(f"Neo4j has {len(neo4j_places)} Place nodes")
    for place in neo4j_places[:5]:
        print(f"  - {place['id']}: {place['name']}")

    print()

    # Check what locations are connected to regions
    result = session.run("""
        MATCH (r:Region)-[:HAS_LOCATION]->(l:Location)
        RETURN r.name as region_name, count(l) as location_count
    """)
    region_locs = list(result)
    print(f"Region-Location connections:")
    for record in region_locs:
        print(f"  Region '{record['region_name']}': {record['location_count']} locations")

neo4j_driver.close()
mongo_client.close()
