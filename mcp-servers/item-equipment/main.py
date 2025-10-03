"""
Item/Equipment MCP Server
Provides game mechanics for items, equipment, inventory, and crafting
"""
import os
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
import json

# ============================================
# Configuration
# ============================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:password@mongodb:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Item/Equipment MCP Server",
    description="MCP server for items, equipment, inventory, and crafting",
    version="1.0.0"
)

# ============================================
# Database Clients
# ============================================

mongo_client: Optional[AsyncIOMotorClient] = None
mongo_db = None
redis_client: Optional[Redis] = None

@app.on_event("startup")
async def startup():
    global mongo_client, mongo_db, redis_client
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client.skillforge
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()

# ============================================
# Authentication
# ============================================

async def verify_mcp_token(authorization: str = Header(...)):
    """Verify MCP authentication token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split("Bearer ")[1]
    if token != MCP_AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid MCP token")

    return token

# ============================================
# Data Models
# ============================================

class ItemStats(BaseModel):
    """Item statistics and attributes"""
    attack: int = 0
    defense: int = 0
    magic: int = 0
    speed: int = 0
    durability: int = 100
    weight: float = 1.0

class ItemRequirements(BaseModel):
    """Requirements to use an item"""
    min_level: int = 1
    required_skills: List[str] = []
    required_quests: List[str] = []
    character_class: Optional[str] = None

class ItemEffect(BaseModel):
    """Effect when using an item"""
    effect_type: str  # heal, damage, buff, debuff, transform, teleport
    target: str  # self, enemy, ally, area
    magnitude: int = 0
    duration: int = 0  # seconds, 0 for instant
    description: str

class Item(BaseModel):
    """Item definition"""
    item_id: str
    name: str
    item_type: str  # weapon, armor, consumable, quest, crafting, treasure, misc
    subtype: Optional[str] = None  # sword, potion, scroll, etc.
    rarity: str = "common"  # common, uncommon, rare, epic, legendary, mythic
    description: str
    lore: Optional[str] = None

    # Stats
    stats: ItemStats = Field(default_factory=ItemStats)
    requirements: ItemRequirements = Field(default_factory=ItemRequirements)
    effects: List[ItemEffect] = []

    # Economic
    base_value: int = 10  # Currency value
    is_tradeable: bool = True
    is_sellable: bool = True
    is_craftable: bool = False

    # Equipment specific
    equipment_slot: Optional[str] = None  # head, chest, hands, legs, feet, weapon, shield
    is_stackable: bool = False
    max_stack: int = 1

    # Visual
    icon: Optional[str] = None
    model: Optional[str] = None

    # World context
    world_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

class CraftingRecipe(BaseModel):
    """Recipe for crafting items"""
    recipe_id: str
    output_item_id: str
    output_quantity: int = 1
    required_items: Dict[str, int]  # item_id -> quantity
    required_skill: Optional[str] = None
    required_skill_level: int = 1
    crafting_time: int = 60  # seconds
    success_rate: float = 1.0
    world_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

class PlayerInventory(BaseModel):
    """Player's inventory"""
    inventory_id: str
    profile_id: str
    items: Dict[str, int] = {}  # item_id -> quantity
    equipped: Dict[str, str] = {}  # slot -> item_id
    max_capacity: int = 100
    currency: int = 0
    updated_at: datetime = Field(default_factory=datetime.now)

class ItemInstance(BaseModel):
    """Unique instance of an item with specific properties"""
    instance_id: str
    item_id: str
    owner_id: Optional[str] = None  # Player profile ID
    current_durability: int = 100
    enhancements: List[str] = []  # Enhancement IDs applied
    is_equipped: bool = False
    acquired_at: datetime = Field(default_factory=datetime.now)

# ============================================
# MCP Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "service": "Item/Equipment MCP Server",
        "version": "1.0.0",
        "description": "Items, equipment, inventory, and crafting systems"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/mcp/item/{item_id}")
async def get_item(
    item_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get item definition by ID"""
    # Try cache first
    cache_key = f"item:{item_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Query MongoDB
    item = await mongo_db.items.find_one({"item_id": item_id})

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.pop("_id", None)

    # Cache for 1 hour
    await redis_client.setex(cache_key, 3600, json.dumps(item, default=str))

    return item

@app.get("/mcp/player-inventory/{profile_id}")
async def get_player_inventory(
    profile_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get player's inventory"""
    # Check cache
    cache_key = f"inventory:{profile_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        inventory_data = json.loads(cached)
    else:
        # Query MongoDB
        inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

        if not inventory:
            # Create new inventory
            inventory = {
                "inventory_id": f"inv_{profile_id}",
                "profile_id": profile_id,
                "items": {},
                "equipped": {},
                "max_capacity": 100,
                "currency": 0,
                "updated_at": datetime.now()
            }
            await mongo_db.inventories.insert_one(inventory)

        inventory.pop("_id", None)
        inventory_data = inventory

        # Cache for 5 minutes
        await redis_client.setex(cache_key, 300, json.dumps(inventory_data, default=str))

    # Fetch item details
    items_detailed = []
    for item_id, quantity in inventory_data.get("items", {}).items():
        item = await mongo_db.items.find_one({"item_id": item_id})
        if item:
            item.pop("_id", None)
            items_detailed.append({
                "item": item,
                "quantity": quantity
            })

    # Fetch equipped items
    equipped_detailed = {}
    for slot, item_id in inventory_data.get("equipped", {}).items():
        item = await mongo_db.items.find_one({"item_id": item_id})
        if item:
            item.pop("_id", None)
            equipped_detailed[slot] = item

    return {
        "inventory_id": inventory_data["inventory_id"],
        "profile_id": profile_id,
        "items": items_detailed,
        "equipped": equipped_detailed,
        "total_items": len(inventory_data.get("items", {})),
        "max_capacity": inventory_data.get("max_capacity", 100),
        "currency": inventory_data.get("currency", 0)
    }

@app.get("/mcp/craftable-items/{profile_id}")
async def get_craftable_items(
    profile_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get items the player can craft based on their inventory"""
    # Get player inventory
    inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

    if not inventory:
        return {"craftable_recipes": [], "total_craftable": 0}

    player_items = inventory.get("items", {})

    # Get all recipes
    craftable = []
    cursor = mongo_db.crafting_recipes.find({})

    async for recipe in cursor:
        recipe.pop("_id", None)

        # Check if player has all required items
        can_craft = True
        for req_item_id, req_quantity in recipe["required_items"].items():
            if player_items.get(req_item_id, 0) < req_quantity:
                can_craft = False
                break

        if can_craft:
            # Get output item details
            output_item = await mongo_db.items.find_one({"item_id": recipe["output_item_id"]})
            if output_item:
                output_item.pop("_id", None)
                recipe["output_item"] = output_item

            craftable.append(recipe)

    return {
        "profile_id": profile_id,
        "craftable_recipes": craftable,
        "total_craftable": len(craftable)
    }

@app.get("/mcp/world-items/{world_id}")
async def get_world_items(
    world_id: str,
    item_type: Optional[str] = None,
    rarity: Optional[str] = None,
    token: str = Depends(verify_mcp_token)
):
    """Get all items for a world"""
    query = {"world_id": world_id}

    if item_type:
        query["item_type"] = item_type
    if rarity:
        query["rarity"] = rarity

    items = []
    cursor = mongo_db.items.find(query)

    async for item in cursor:
        item.pop("_id", None)
        items.append(item)

    return {
        "world_id": world_id,
        "filters": {"item_type": item_type, "rarity": rarity},
        "items": items,
        "total_items": len(items)
    }

@app.get("/mcp/quest-items/{quest_id}")
async def get_quest_items(
    quest_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Get items related to a quest"""
    # Find items where this quest is in requirements
    items = []
    cursor = mongo_db.items.find({"requirements.required_quests": quest_id})

    async for item in cursor:
        item.pop("_id", None)
        items.append(item)

    return {
        "quest_id": quest_id,
        "items": items,
        "total_items": len(items)
    }

@app.post("/mcp/add-item-to-inventory")
async def add_item_to_inventory(
    profile_id: str,
    item_id: str,
    quantity: int = 1,
    token: str = Depends(verify_mcp_token)
):
    """Add item to player's inventory"""
    # Get or create inventory
    inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

    if not inventory:
        inventory = {
            "inventory_id": f"inv_{profile_id}",
            "profile_id": profile_id,
            "items": {},
            "equipped": {},
            "max_capacity": 100,
            "currency": 0,
            "updated_at": datetime.now()
        }
        await mongo_db.inventories.insert_one(inventory)

    # Update items
    items = inventory.get("items", {})
    items[item_id] = items.get(item_id, 0) + quantity

    # Update database
    await mongo_db.inventories.update_one(
        {"profile_id": profile_id},
        {"$set": {"items": items, "updated_at": datetime.now()}}
    )

    # Invalidate cache
    cache_key = f"inventory:{profile_id}"
    await redis_client.delete(cache_key)

    return {
        "status": "added",
        "profile_id": profile_id,
        "item_id": item_id,
        "quantity_added": quantity,
        "new_total": items[item_id]
    }

@app.post("/mcp/remove-item-from-inventory")
async def remove_item_from_inventory(
    profile_id: str,
    item_id: str,
    quantity: int = 1,
    token: str = Depends(verify_mcp_token)
):
    """Remove item from player's inventory"""
    inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    items = inventory.get("items", {})

    if item_id not in items or items[item_id] < quantity:
        raise HTTPException(status_code=400, detail="Insufficient items")

    items[item_id] -= quantity

    if items[item_id] <= 0:
        del items[item_id]

    await mongo_db.inventories.update_one(
        {"profile_id": profile_id},
        {"$set": {"items": items, "updated_at": datetime.now()}}
    )

    # Invalidate cache
    cache_key = f"inventory:{profile_id}"
    await redis_client.delete(cache_key)

    return {
        "status": "removed",
        "profile_id": profile_id,
        "item_id": item_id,
        "quantity_removed": quantity,
        "remaining": items.get(item_id, 0)
    }

@app.post("/mcp/equip-item")
async def equip_item(
    profile_id: str,
    item_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Equip an item"""
    # Get item details
    item = await mongo_db.items.find_one({"item_id": item_id})

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item.get("equipment_slot"):
        raise HTTPException(status_code=400, detail="Item is not equippable")

    # Get inventory
    inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # Check if player has the item
    if item_id not in inventory.get("items", {}):
        raise HTTPException(status_code=400, detail="Item not in inventory")

    # Equip
    equipped = inventory.get("equipped", {})
    slot = item["equipment_slot"]

    # Unequip current item in slot if any
    old_item_id = equipped.get(slot)

    equipped[slot] = item_id

    await mongo_db.inventories.update_one(
        {"profile_id": profile_id},
        {"$set": {"equipped": equipped, "updated_at": datetime.now()}}
    )

    # Invalidate cache
    cache_key = f"inventory:{profile_id}"
    await redis_client.delete(cache_key)

    return {
        "status": "equipped",
        "profile_id": profile_id,
        "item_id": item_id,
        "slot": slot,
        "previous_item": old_item_id
    }

@app.post("/mcp/craft-item")
async def craft_item(
    profile_id: str,
    recipe_id: str,
    token: str = Depends(verify_mcp_token)
):
    """Craft an item using a recipe"""
    # Get recipe
    recipe = await mongo_db.crafting_recipes.find_one({"recipe_id": recipe_id})

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Get inventory
    inventory = await mongo_db.inventories.find_one({"profile_id": profile_id})

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    items = inventory.get("items", {})

    # Check materials
    for req_item_id, req_quantity in recipe["required_items"].items():
        if items.get(req_item_id, 0) < req_quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient {req_item_id}")

    # Remove materials
    for req_item_id, req_quantity in recipe["required_items"].items():
        items[req_item_id] -= req_quantity
        if items[req_item_id] <= 0:
            del items[req_item_id]

    # Add crafted item
    output_item_id = recipe["output_item_id"]
    output_quantity = recipe.get("output_quantity", 1)
    items[output_item_id] = items.get(output_item_id, 0) + output_quantity

    # Update inventory
    await mongo_db.inventories.update_one(
        {"profile_id": profile_id},
        {"$set": {"items": items, "updated_at": datetime.now()}}
    )

    # Invalidate cache
    cache_key = f"inventory:{profile_id}"
    await redis_client.delete(cache_key)

    return {
        "status": "crafted",
        "profile_id": profile_id,
        "recipe_id": recipe_id,
        "output_item_id": output_item_id,
        "quantity_crafted": output_quantity
    }

# ============================================
# Admin Endpoints
# ============================================

@app.post("/admin/create-item")
async def create_item(item: Item, token: str = Depends(verify_mcp_token)):
    """Create a new item"""
    item_dict = item.dict()
    await mongo_db.items.insert_one(item_dict)

    # Invalidate cache
    cache_key = f"item:{item.item_id}"
    await redis_client.delete(cache_key)

    return {"status": "created", "item_id": item.item_id}

@app.post("/admin/create-recipe")
async def create_recipe(recipe: CraftingRecipe, token: str = Depends(verify_mcp_token)):
    """Create a crafting recipe"""
    recipe_dict = recipe.dict()
    await mongo_db.crafting_recipes.insert_one(recipe_dict)
    return {"status": "created", "recipe_id": recipe.recipe_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
