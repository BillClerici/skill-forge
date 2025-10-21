"""
Inventory models for MongoDB
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class InventoryItem(BaseModel):
    """Item in player inventory"""
    item_id: UUID
    name: str
    category: str
    quantity: int = 1
    acquired_at: datetime
    acquired_from: str
    properties: Optional[Dict[str, Any]] = None


class KnowledgeItem(BaseModel):
    """Knowledge in player inventory"""
    knowledge_id: UUID
    name: str
    category: str
    level: int = 1
    acquired_at: datetime
    source: str
    xp_gained: int = 0


class DimensionalProgress(BaseModel):
    """Progress in a dimension"""
    level: int = 1
    xp: int = 0
    maturity: str = "novice"
    blooms_progress: Optional[Dict[str, Any]] = None


class PlayerInventoryDocument(BaseModel):
    """Player inventory document for MongoDB"""

    session_id: UUID
    player_id: UUID
    updated_at: datetime

    items: List[InventoryItem] = []
    knowledge: List[KnowledgeItem] = []
    dimensional_progress: Dict[str, DimensionalProgress] = {}

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }
