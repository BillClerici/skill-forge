#!/usr/bin/env python3
"""Delete campaign from Redis"""
import redis

# Connect to Redis (from within Docker network)
redis_client = redis.Redis(
    host='redis',
    port=6379,
    decode_responses=True
)

campaign_id = "f9fb8164-b442-42e3-abae-6ca437c31bc2"

# Delete both keys
progress_key = f"campaign:progress:{campaign_id}"
state_key = f"campaign:state:{campaign_id}"

deleted_progress = redis_client.delete(progress_key)
deleted_state = redis_client.delete(state_key)

print(f"Deleted progress key: {deleted_progress}")
print(f"Deleted state key: {deleted_state}")
print(f"Campaign {campaign_id} removed from Redis")
