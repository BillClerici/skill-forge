"""
Check MongoDB state after deletion
"""
import os
from pymongo import MongoClient

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client['skillforge']

print("MongoDB Collection Counts:\n")

collections_to_check = [
    'campaigns',
    'campaign_state',
    'quests',
    'places',
    'scenes',
    'npcs',
    'discoveries',
    'challenges',
    'events',
    'knowledge',
    'items',
    'rubrics',
    'world_definitions',
    'region_definitions',
    'location_definitions',
    'species_definitions',
    'universe_definitions'
]

for collection_name in collections_to_check:
    count = db[collection_name].count_documents({})
    status = "✓" if count > 0 else " "
    print(f"  {status} {collection_name:25} {count:5}")

mongo_client.close()
