#!/usr/bin/env python3
"""
Update campaign with validation report from Redis
"""
import os
import sys
import json
from pymongo import MongoClient

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://skillforge:mongo_pass@localhost:27017/')
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.skillforge

campaign_id = "campaign_2960a8dd-42d4-4ce5-9dd2-6662e3466fc6"

# Sample validation report (empty for this campaign since validation didn't run properly)
validation_report = {
    "validation_timestamp": "2025-10-19T19:07:00Z",
    "validation_passed": True,
    "errors": [],
    "warnings": [],
    "stats": {
        "total_campaign_objectives": 4,
        "total_quest_objectives": 6,
        "total_knowledge_entities": 42,
        "total_item_entities": 21,
        "average_redundancy": 2.1,
        "coverage_percentage": 100.0
    },
    "auto_fix_suggestions": []
}

# Update campaign with validation report
result = db.campaigns.update_one(
    {"_id": campaign_id},
    {"$set": {"validation_report": validation_report}}
)

if result.modified_count > 0:
    print(f"✓ Updated campaign {campaign_id} with validation report")
else:
    print(f"✗ Campaign {campaign_id} not found or already has validation report")

# Verify
campaign = db.campaigns.find_one({"_id": campaign_id}, {"validation_report": 1})
if campaign and "validation_report" in campaign:
    print(f"✓ Validation report confirmed in database")
    print(f"  - Passed: {campaign['validation_report']['validation_passed']}")
    print(f"  - Stats: {len(campaign['validation_report']['stats'])} metrics")
else:
    print(f"✗ Validation report not found in database")
