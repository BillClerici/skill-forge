#!/usr/bin/env python3
"""Mark campaign as completed to prevent restart loop"""
import redis
import json

# Connect to Redis (from within Docker network)
redis_client = redis.Redis(
    host='redis',
    port=6379,
    decode_responses=True
)

campaign_id = "4573ac6c-2e3c-4524-8b1e-2b3982352810"

# Get current progress
progress_key = f"campaign:progress:{campaign_id}"
progress_data = redis_client.get(progress_key)

if progress_data:
    progress = json.loads(progress_data)
    # Mark as completed
    progress["final_campaign_id"] = "CANCELLED_BY_USER"
    progress["status_message"] = "Campaign generation cancelled"

    # Save back
    redis_client.setex(progress_key, 86400, json.dumps(progress))
    print(f"Marked campaign {campaign_id} as completed")
else:
    print(f"Campaign {campaign_id} not found in Redis")
