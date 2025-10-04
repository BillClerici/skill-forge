"""
Main views for SkillForge
"""
from django.shortcuts import render
from accounts.models import Account
from members.models import Player
from pymongo import MongoClient
import os


def dashboard(request):
    """Dashboard homepage"""
    # MongoDB connection for universe and world counts
    MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
    try:
        mongo_client = MongoClient(MONGODB_URL)
        db = mongo_client['skillforge']
        total_universes = db.universe_definitions.count_documents({})
        total_worlds = db.world_definitions.count_documents({})
    except Exception:
        total_universes = 0
        total_worlds = 0

    context = {
        'total_accounts': Account.objects.count(),
        'total_players': Player.objects.count(),
        'total_universes': total_universes,
        'total_worlds': total_worlds,
        'recent_accounts': Account.objects.order_by('-created_at')[:5],
        'recent_players': Player.objects.order_by('-created_at')[:5],
    }
    return render(request, 'dashboard.html', context)
