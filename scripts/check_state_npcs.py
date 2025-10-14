#!/usr/bin/env python3
"""Check if NPCs in state have species information"""
from pymongo import MongoClient
import os
import json

mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
db = mongo_client['skill_forge']

# Check MongoDB NPCs for species info
print("MongoDB NPCs (checking species info):")
npcs = list(db.npcs.find({}, {'_id': 1, 'name': 1, 'species_id': 1, 'species_name': 1}).limit(5))
if npcs:
    for npc in npcs:
        print(f"  {npc.get('name')}")
        print(f"    species_id: {npc.get('species_id')}")
        print(f"    species_name: {npc.get('species_name')}")
else:
    print("  No NPCs found in MongoDB")

# Check recent workflow state from Redis
import redis
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True
)

# Get recent workflow state (if exists)
keys = redis_client.keys('campaign_workflow:*')
if keys:
    latest_key = sorted(keys)[-1]
    print(f"\nChecking workflow state: {latest_key}")

    state_json = redis_client.get(latest_key)
    if state_json:
        state = json.loads(state_json)
        npcs = state.get('npcs', [])[:3]
        print(f"\nWorkflow State NPCs (first 3):")
        for npc in npcs:
            print(f"  {npc.get('name')}")
            print(f"    npc_id: {npc.get('npc_id')}")
            print(f"    species_id: {npc.get('species_id')}")
            print(f"    species_name: {npc.get('species_name')}")
else:
    print("\nNo workflow state found in Redis")
