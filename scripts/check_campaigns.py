#!/usr/bin/env python3
import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Get all campaign keys
keys = r.keys('campaign:progress:*')

print(f"Found {len(keys)} campaigns in Redis\n")

stuck_at_100 = []
in_progress = []

for key in keys:
    data = r.get(key)
    if data:
        campaign = json.loads(data)
        request_id = campaign.get('request_id', 'unknown')
        progress = campaign.get('progress_percentage', 0)
        final_id = campaign.get('final_campaign_id')
        errors = campaign.get('errors', [])

        print(f"Campaign: {request_id}")
        print(f"  Progress: {progress}%")
        print(f"  Final ID: {final_id}")
        print(f"  Errors: {len(errors)}")
        print()

        # Categorize
        if progress == 100 and not final_id:
            stuck_at_100.append(request_id)
        elif progress < 100:
            in_progress.append(request_id)

print("\n" + "="*50)
print(f"Stuck at 100% (no final ID): {len(stuck_at_100)}")
for req_id in stuck_at_100:
    print(f"  - {req_id}")

print(f"\nIn Progress (<100%): {len(in_progress)}")
for req_id in in_progress:
    print(f"  - {req_id}")
