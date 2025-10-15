import os
from pymongo import MongoClient

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']

# Check a scene
scene = db.scenes.find_one({}, {'name': 1, 'npc_ids': 1, '_id': 1})
print("Scene sample:")
print(f"  _id: {scene.get('_id')}")
print(f"  name: {scene.get('name')}")
print(f"  npc_ids: {scene.get('npc_ids')}")

# Check if there are any NPCs
npc_count = db.npcs.count_documents({})
print(f"\nTotal NPCs in database: {npc_count}")

if npc_count > 0:
    npc_sample = db.npcs.find_one({}, {'name': 1, 'role': 1, '_id': 1})
    print(f"\nNPC sample:")
    print(f"  _id: {npc_sample.get('_id')}")
    print(f"  name: {npc_sample.get('name')}")
    print(f"  role: {npc_sample.get('role')}")

# Check campaign
campaign_id = "campaign_57fdeb6f-1de7-411e-bebc-e839876fb56c"
campaign = db.campaigns.find_one({'_id': campaign_id})
if campaign:
    print(f"\nCampaign stats:")
    print(f"  num_npcs: {campaign.get('stats', {}).get('num_npcs', 0)}")
