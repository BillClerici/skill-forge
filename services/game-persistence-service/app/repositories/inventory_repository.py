"""
Inventory repository for MongoDB operations
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Dict, Any
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class InventoryRepository:
    """Repository for inventory operations"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db['player_inventories']

    async def get_inventory(self, session_id: UUID, player_id: UUID) -> Optional[Dict[str, Any]]:
        """Get player inventory"""
        try:
            inventory = await self.collection.find_one({
                'session_id': str(session_id),
                'player_id': str(player_id)
            })
            return inventory
        except Exception as e:
            logger.error(f"Error getting inventory: {e}")
            return None

    async def upsert_inventory(self, inventory_data: Dict[str, Any]) -> bool:
        """Upsert player inventory"""
        try:
            # Convert UUIDs
            if 'session_id' in inventory_data:
                inventory_data['session_id'] = str(inventory_data['session_id'])
            if 'player_id' in inventory_data:
                inventory_data['player_id'] = str(inventory_data['player_id'])

            await self.collection.update_one(
                {
                    'session_id': inventory_data['session_id'],
                    'player_id': inventory_data['player_id']
                },
                {'$set': inventory_data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error upserting inventory: {e}")
            return False
