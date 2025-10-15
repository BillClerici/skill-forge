#!/usr/bin/env python3
"""Check Campaign NPCs and Species"""
from pymongo import MongoClient
import os
from datetime import datetime

mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
db = mongo_client['skill_forge']

# Get the most recent campaign
campaigns = list(db.campaigns.find({}, {'_id': 1, 'name': 1, 'created_at': 1}).sort('created_at', -1).limit(1))
if campaigns:
    campaign = campaigns[0]
    print(f"Most recent campaign: {campaign.get('name')} - ID: {campaign.get('_id')}")
    campaign_id = campaign.get('_id')

    # Get NPCs for this campaign
    print(f"\nNPCs in campaign {campaign_id}:")
    npcs = list(db.npcs.find({'campaign_id': campaign_id}, {'_id': 1, 'name': 1, 'species_id': 1, 'species_name': 1}))
    for npc in npcs[:10]:  # Show first 10
        print(f"  {npc.get('name')} - species_id: {npc.get('species_id')} - species_name: {npc.get('species_name')}")

    if len(npcs) > 10:
        print(f"  ... and {len(npcs) - 10} more NPCs")

    # Get unique species IDs from NPCs
    print(f"\nUnique species referenced by NPCs:")
    species_ids = db.npcs.distinct('species_id', {'campaign_id': campaign_id})
    for species_id in species_ids:
        # Check if species exists
        species = db.species.find_one({'_id': species_id})
        if species:
            print(f"  {species_id} - EXISTS: {species.get('name')}")
        else:
            print(f"  {species_id} - MISSING!")
            # Count NPCs with this missing species
            count = db.npcs.count_documents({'campaign_id': campaign_id, 'species_id': species_id})
            print(f"    ({count} NPCs reference this missing species)")
else:
    print("No campaigns found")

print(f"\nTotal species in database: {db.species.count_documents({})}")
print(f"Total NPCs in database: {db.npcs.count_documents({})}")
