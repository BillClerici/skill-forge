import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
key = "campaign:progress:57fdeb6f-1de7-411e-bebc-e839876fb56c"

data = json.loads(redis_client.get(key))
data['progress_percentage'] = 100
data['status_message'] = 'Campaign finalized successfully!'
data['final_campaign_id'] = 'campaign_57fdeb6f-1de7-411e-bebc-e839876fb56c'

redis_client.set(key, json.dumps(data))
print("Updated Redis to 100% completion")
print(f"Campaign ID: {data['final_campaign_id']}")
print(f"Campaign Name: {data.get('campaign_name', 'Unknown')}")
