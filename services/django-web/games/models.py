"""
Models for Games app
Most data comes from external services (MongoDB, PostgreSQL)
These are minimal models for Django admin if needed
"""
from django.db import models

# No local models - all data is external
# This app primarily serves views and connects to:
# - Game Engine API (game sessions, workflows)
# - Game UI Gateway via WebSocket (real-time events)
# - MongoDB directly (campaigns, worlds, characters)
