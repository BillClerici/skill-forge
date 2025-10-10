"""
Hierarchical Location Taxonomy System
Defines valid location types at each level and their parent-child relationships
"""
from typing import List, Dict, Optional, Tuple
from enum import Enum


class LocationLevel(Enum):
    REGION = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


# =============================================================================
# REGION TYPES (Level 0)
# =============================================================================

REGION_TYPES = {
    "geographic_features": [
        "Continent",
        "Country",
        "Island",
        "Archipelago",
        "Mountain Range",
        "Mountain System",
        "Ocean",
        "Sea",
        "Forest",
        "Jungle",
        "Desert",
        "Tundra",
        "Plains",
        "Grasslands",
        "Swamp",
        "Wetlands",
        "Valley",
        "Canyon",
        "Peninsula",
        "Plateau",
        "Coastal Region",
        "Underground Expanse",
        "Volcanic Region",
        "Ice Shelf",
        "Savanna"
    ],
    "descriptions": {
        "Continent": "A massive landmass containing multiple countries, biomes, and civilizations",
        "Country": "A large defined territory with borders, governance, and culture",
        "Island": "Land surrounded by water, isolated ecosystem",
        "Mountain Range": "Chain of connected peaks and high-altitude terrain",
        "Ocean": "Vast body of saltwater covering large areas",
        "Forest": "Dense woodland area with tree canopy and undergrowth",
        "Desert": "Arid landscape with little precipitation, extreme temperatures",
        "Tundra": "Cold, treeless region with permafrost",
        "Plains": "Flat or gently rolling grasslands",
        "Swamp": "Wetland area with standing water and vegetation"
    }
}

# =============================================================================
# LEVEL 1 LOCATION TYPES (Settlements & Major Features)
# =============================================================================

LEVEL_1_LOCATION_TYPES = {
    "settlements": [
        "City",
        "Metropolis",
        "Megacity",
        "Town",
        "Village",
        "Hamlet",
        "Colony",
        "Outpost",
        "Settlement",
        "District",
        "Borough",
        "Neighborhood",
        "Fortress City",
        "Port City",
        "Trading Post",
        "Mining Town",
        "Orbital City",
        "Underwater City",
        "Sky City"
    ],
    "natural_features": [
        "Cave System",
        "Cavern Network",
        "Tunnel System",
        "Underground City",
        "Lake",
        "River System",
        "Mountain",
        "Hill",
        "Grove",
        "Clearing",
        "Ruins (Large)",
        "Ancient Structure",
        "Crater",
        "Volcano",
        "Glacier",
        "Canyon Section"
    ],
    "constructed_features": [
        "Military Base",
        "Castle",
        "Fortress",
        "Temple Complex",
        "University Campus",
        "Space Station",
        "Orbital Platform",
        "Research Facility",
        "Prison Complex",
        "Palace Complex"
    ],
    "parent_compatibility": {
        # Geographic features
        "Continent": ["City", "Metropolis", "Town", "Village", "District", "Castle", "Temple Complex", "Ruins (Large)"],
        "Country": ["City", "Town", "Village", "Military Base", "Capital City", "Fortress", "Port City"],
        "Island": ["City", "Town", "Village", "Port City", "Fortress", "Colony", "Outpost"],
        "Archipelago": ["Port City", "Town", "Village", "Naval Base", "Trading Post"],
        "Mountain Range": ["Cave System", "Mountain", "Fortress", "Village", "Mining Town", "Monastery"],
        "Mountain System": ["Cave System", "Fortress", "Village", "Mining Town", "Temple Complex"],
        "Ocean": ["Underwater City", "Shipwreck Site", "Coral Reef System", "Deep Sea Trench"],
        "Sea": ["Port City", "Underwater City", "Naval Base", "Island Settlement"],
        "Forest": ["Village", "Grove", "Ruins (Large)", "Cave System", "Outpost", "Hamlet"],
        "Jungle": ["Village", "Ancient Structure", "Ruins (Large)", "Outpost", "Temple Complex"],
        "Desert": ["Outpost", "Cave System", "Ruins (Large)", "Town", "Oasis Settlement", "Mining Town"],
        "Tundra": ["Outpost", "Village", "Research Facility", "Ice Cave System"],
        "Plains": ["Town", "Village", "City", "Fortress", "Trading Post"],
        "Grasslands": ["Village", "Town", "Settlement", "Outpost"],
        "Swamp": ["Village", "Outpost", "Ruins (Large)", "Fortress"],
        "Wetlands": ["Village", "Settlement", "Ancient Structure"],
        "Valley": ["Town", "Village", "Settlement", "Monastery", "Fortress"],
        "Canyon": ["Cave System", "Outpost", "Settlement", "Ruins (Large)"],
        "Peninsula": ["Port City", "Town", "Fortress", "Trading Post"],
        "Plateau": ["City", "Town", "Fortress", "Temple Complex"],
        "Coastal Region": ["Port City", "Town", "Village", "Trading Post", "Naval Base"],
        "Underground Expanse": ["Underground City", "Cave System", "Mining Town"],
        "Volcanic Region": ["Outpost", "Mining Town", "Research Facility", "Fortress"],
        "Ice Shelf": ["Research Facility", "Outpost", "Ice Cave System"],
        "Savanna": ["Village", "Town", "Outpost", "Trading Post"]
    }
}

# =============================================================================
# LEVEL 2 LOCATION TYPES (Buildings & Sub-Areas)
# =============================================================================

LEVEL_2_LOCATION_TYPES = {
    "buildings": [
        "Tavern",
        "Inn",
        "Shop",
        "Store",
        "Market",
        "Bazaar",
        "Warehouse",
        "Mansion",
        "House",
        "Dwelling",
        "Apartment Building",
        "Tower",
        "Chapel",
        "Temple",
        "Church",
        "Cathedral",
        "Library",
        "School",
        "Academy",
        "Barracks",
        "Guard Post",
        "Workshop",
        "Smithy",
        "Forge",
        "Stable",
        "Arena",
        "Coliseum",
        "Theater",
        "Guildhall",
        "Bank",
        "Town Hall",
        "City Hall",
        "Government Building",
        "Hospital",
        "Clinic",
        "Laboratory",
        "Observatory"
    ],
    "outdoor_spaces": [
        "Park",
        "Garden",
        "Plaza",
        "Square",
        "Courtyard",
        "Cemetery",
        "Graveyard",
        "Training Grounds",
        "Marketplace",
        "Fountain Area",
        "Statue Gardens"
    ],
    "natural_features": [
        "Cave",
        "Grotto",
        "Chamber",
        "Passage",
        "Tunnel",
        "Lake (Small)",
        "Pond",
        "Spring",
        "Waterfall",
        "Pool"
    ],
    "landmarks": [
        "Monument",
        "Statue",
        "Fountain",
        "Gate",
        "Bridge",
        "Wall Section",
        "Obelisk",
        "Arch"
    ],
    "parent_compatibility": {
        # Settlements
        "City": ["Tavern", "Shop", "Market", "Park", "Temple", "Guard Post", "Arena", "Library", "Bank", "City Hall", "Cathedral"],
        "Metropolis": ["Tavern", "Shop", "Market", "Tower", "Arena", "Bank", "Library", "Hospital", "Plaza", "Monument"],
        "Town": ["Inn", "Shop", "House", "Chapel", "Cemetery", "Smithy", "Market", "Town Hall", "Stable"],
        "Village": ["Dwelling", "Shop", "Chapel", "Stable", "Well", "Smithy", "Inn", "Cemetery"],
        "Hamlet": ["Dwelling", "Well", "Small Chapel", "Storage Building"],
        "Colony": ["House", "Warehouse", "Guard Post", "Workshop", "Market"],
        "Outpost": ["Guard Post", "Barracks", "Storage Building", "Workshop"],
        "Fortress City": ["Barracks", "Guard Post", "Tower", "Chapel", "Armory", "Training Grounds"],
        "Port City": ["Tavern", "Warehouse", "Market", "Dock", "Lighthouse", "Customs House"],
        "Trading Post": ["Shop", "Warehouse", "Inn", "Stable", "Market Stall"],

        # Natural features
        "Cave System": ["Cave", "Chamber", "Passage", "Grotto", "Underground Lake"],
        "Cavern Network": ["Cave", "Chamber", "Grotto", "Pool"],
        "Underground City": ["House", "Market", "Temple", "Guard Post", "Plaza"],
        "Lake": ["Dock", "Boathouse", "Fishing Hut"],
        "Grove": ["Shrine", "Clearing", "Sacred Tree"],
        "Ruins (Large)": ["Temple", "Tower", "Chamber", "Courtyard"],

        # Constructed features
        "Castle": ["Tower", "Barracks", "Chapel", "Courtyard", "Stable", "Great Hall", "Throne Room", "Armory"],
        "Fortress": ["Barracks", "Tower", "Armory", "Training Grounds", "Guard Post", "Gate"],
        "Temple Complex": ["Temple", "Chapel", "Garden", "Library", "Dormitory", "Meditation Hall"],
        "University Campus": ["Library", "Laboratory", "Dormitory", "Lecture Hall", "Observatory"],
        "Military Base": ["Barracks", "Armory", "Training Grounds", "Command Center", "Hangar"],
        "Palace Complex": ["Throne Room", "Garden", "Chapel", "Tower", "Courtyard", "Ballroom"]
    }
}

# =============================================================================
# LEVEL 3 LOCATION TYPES (Rooms & Specific Spaces)
# =============================================================================

LEVEL_3_LOCATION_TYPES = {
    "residential_rooms": [
        "Living Room",
        "Bedroom",
        "Master Bedroom",
        "Kitchen",
        "Dining Room",
        "Study",
        "Library Room",
        "Bathroom",
        "Parlor",
        "Nursery",
        "Servants Quarters",
        "Guest Room",
        "Foyer",
        "Hallway"
    ],
    "commercial_spaces": [
        "Shop Floor",
        "Storage Room",
        "Back Room",
        "Display Area",
        "Counter Area",
        "Workshop Floor",
        "Vault",
        "Office",
        "Reception Area"
    ],
    "tavern_inn_rooms": [
        "The Bar",
        "Bar Area",
        "Common Room",
        "Private Room",
        "Guest Room",
        "Cellar",
        "Kitchen",
        "Storage Room",
        "Owner's Quarters"
    ],
    "religious_spaces": [
        "Sanctuary",
        "Prayer Room",
        "Altar Room",
        "Confessional",
        "Sacristy",
        "Bell Tower",
        "Meditation Chamber",
        "Scripture Hall",
        "Reliquary"
    ],
    "civic_government": [
        "Court Room",
        "Council Chamber",
        "Office",
        "Throne Room",
        "Records Room",
        "Prison Cell",
        "Audience Hall",
        "Treasury",
        "War Room"
    ],
    "military_spaces": [
        "Armory",
        "Training Hall",
        "Barracks Room",
        "War Room",
        "Guard Room",
        "Stables",
        "Weapons Storage",
        "Command Center",
        "Mess Hall",
        "Interrogation Room"
    ],
    "utility_spaces": [
        "Hallway",
        "Corridor",
        "Stairwell",
        "Attic",
        "Basement",
        "Storage Room",
        "Closet",
        "Pantry",
        "Cellar",
        "Shaft"
    ],
    "natural_spaces": [
        "Crystal Cavern",
        "Underground Pool",
        "Lava Chamber",
        "Ice Room",
        "Crystal Formation",
        "Stalactite Chamber",
        "Underground River",
        "Mineral Vein"
    ],
    "special_spaces": [
        "Throne Alcove",
        "Altar Platform",
        "Stage",
        "Arena Floor",
        "Pit",
        "Gallery",
        "Balcony",
        "Observatory Deck"
    ],
    "parent_compatibility": {
        # Buildings
        "Tavern": ["The Bar", "Bar Area", "Common Room", "Private Room", "Kitchen", "Cellar", "Storage Room"],
        "Inn": ["Guest Room", "Common Room", "Kitchen", "Cellar", "Reception Area", "Owner's Quarters"],
        "House": ["Living Room", "Bedroom", "Kitchen", "Dining Room", "Study", "Bathroom"],
        "Mansion": ["Living Room", "Master Bedroom", "Dining Room", "Study", "Library Room", "Ballroom", "Kitchen"],
        "Shop": ["Shop Floor", "Storage Room", "Back Room", "Display Area", "Counter Area"],
        "Temple": ["Sanctuary", "Prayer Room", "Altar Room", "Sacristy", "Bell Tower"],
        "Chapel": ["Prayer Room", "Altar Room", "Confessional"],
        "Library": ["Reading Room", "Archives", "Study Room", "Scripture Hall"],
        "Barracks": ["Barracks Room", "Armory", "Training Hall", "Common Room", "Mess Hall"],
        "Tower": ["Guard Room", "Observation Deck", "Stairwell", "Top Chamber"],
        "Workshop": ["Workshop Floor", "Storage Room", "Office", "Tool Room"],
        "Smithy": ["Forge Area", "Anvil Room", "Storage Room", "Display Area"],
        "Arena": ["Arena Floor", "Pit", "Gallery", "Fighter's Room"],
        "Guildhall": ["Meeting Room", "Office", "Storage Room", "Common Room"],
        "Bank": ["Vault", "Teller Area", "Office", "Records Room"],
        "Town Hall": ["Council Chamber", "Office", "Records Room", "Court Room"],
        "City Hall": ["Council Chamber", "Office", "Court Room", "Treasury"],
        "Hospital": ["Ward", "Surgery", "Laboratory", "Office", "Storage Room"],
        "Laboratory": ["Experiment Room", "Storage Room", "Office", "Clean Room"],

        # Natural features
        "Cave": ["Chamber", "Passage", "Pool", "Crystal Cavern", "Stalactite Chamber"],
        "Grotto": ["Pool", "Crystal Formation", "Chamber"],
        "Chamber": ["Passage", "Pool", "Alcove"],

        # Castle/Fortress
        "Great Hall": ["Throne Room", "Dining Area", "Stage"],
        "Throne Room": ["Throne Alcove", "Audience Area", "Guard Post"],
        "Courtyard": ["Garden Area", "Training Ground", "Well"],

        # Outdoor spaces
        "Park": ["Garden", "Path", "Fountain Area", "Clearing"],
        "Garden": ["Greenhouse", "Tool Shed", "Meditation Spot"],
        "Plaza": ["Fountain Area", "Market Stalls", "Monument Area"],
        "Cemetery": ["Crypt", "Mausoleum", "Chapel"],

        # Training/Military
        "Training Grounds": ["Training Hall", "Armory Access", "Practice Field"],
        "Armory": ["Weapons Storage", "Armor Room", "Guard Room"]
    }
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_location_type(
    location_type: str,
    level: LocationLevel,
    parent_type: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Validate if a location type is valid for its level and parent

    Args:
        location_type: The type to validate
        level: The location level (REGION, LEVEL_1, LEVEL_2, LEVEL_3)
        parent_type: Optional parent location type for compatibility check

    Returns:
        (is_valid: bool, error_message: str)
    """
    if level == LocationLevel.REGION:
        if location_type not in REGION_TYPES["geographic_features"]:
            valid_types = ", ".join(REGION_TYPES["geographic_features"][:10]) + "..."
            return False, f"Invalid region type '{location_type}'. Must be one of: {valid_types}"

    elif level == LocationLevel.LEVEL_1:
        all_level1_types = (
            LEVEL_1_LOCATION_TYPES["settlements"] +
            LEVEL_1_LOCATION_TYPES["natural_features"] +
            LEVEL_1_LOCATION_TYPES["constructed_features"]
        )
        if location_type not in all_level1_types:
            return False, f"Invalid Level 1 location type: '{location_type}'"

        # Check parent compatibility
        if parent_type:
            compatible = LEVEL_1_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
            if location_type not in compatible:
                return False, f"Location type '{location_type}' cannot be a child of region type '{parent_type}'. Valid types: {', '.join(compatible[:5])}..."

    elif level == LocationLevel.LEVEL_2:
        all_level2_types = (
            LEVEL_2_LOCATION_TYPES["buildings"] +
            LEVEL_2_LOCATION_TYPES["outdoor_spaces"] +
            LEVEL_2_LOCATION_TYPES["natural_features"] +
            LEVEL_2_LOCATION_TYPES["landmarks"]
        )
        if location_type not in all_level2_types:
            return False, f"Invalid Level 2 location type: '{location_type}'"

        if parent_type:
            compatible = LEVEL_2_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
            if location_type not in compatible:
                return False, f"Location type '{location_type}' cannot be a child of '{parent_type}'. Valid types: {', '.join(compatible[:5])}..."

    elif level == LocationLevel.LEVEL_3:
        all_level3_types = (
            LEVEL_3_LOCATION_TYPES["residential_rooms"] +
            LEVEL_3_LOCATION_TYPES["commercial_spaces"] +
            LEVEL_3_LOCATION_TYPES["tavern_inn_rooms"] +
            LEVEL_3_LOCATION_TYPES["religious_spaces"] +
            LEVEL_3_LOCATION_TYPES["civic_government"] +
            LEVEL_3_LOCATION_TYPES["military_spaces"] +
            LEVEL_3_LOCATION_TYPES["utility_spaces"] +
            LEVEL_3_LOCATION_TYPES["natural_spaces"] +
            LEVEL_3_LOCATION_TYPES["special_spaces"]
        )
        if location_type not in all_level3_types:
            return False, f"Invalid Level 3 location type: '{location_type}'"

        if parent_type:
            compatible = LEVEL_3_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
            if location_type not in compatible:
                return False, f"Location type '{location_type}' cannot be a child of '{parent_type}'. Valid types: {', '.join(compatible[:5])}..."

    return True, ""


def get_valid_child_types(parent_type: str, parent_level: LocationLevel) -> List[str]:
    """
    Get list of valid child location types for a parent

    Args:
        parent_type: The type of the parent location
        parent_level: The level of the parent (REGION, LEVEL_1, LEVEL_2)

    Returns:
        List of valid child location types
    """
    if parent_level == LocationLevel.REGION:
        return LEVEL_1_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
    elif parent_level == LocationLevel.LEVEL_1:
        return LEVEL_2_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
    elif parent_level == LocationLevel.LEVEL_2:
        return LEVEL_3_LOCATION_TYPES["parent_compatibility"].get(parent_type, [])
    return []


def get_location_type_description(location_type: str, level: LocationLevel) -> str:
    """
    Get description/guidance for a location type

    Args:
        location_type: The location type
        level: The location level

    Returns:
        Description string
    """
    if level == LocationLevel.REGION:
        return REGION_TYPES["descriptions"].get(location_type, f"A {location_type} region")

    # Generic descriptions for other levels
    descriptions = {
        # Level 1
        "City": "A large urban settlement with multiple buildings, districts, and infrastructure",
        "Town": "A medium-sized settlement with shops, houses, and civic buildings",
        "Village": "A small rural settlement with basic amenities",
        "Cave System": "A network of interconnected caves and passages",

        # Level 2
        "Tavern": "A building serving food and drink, with a bar area, common room, and possibly guest rooms",
        "Shop": "A commercial building for selling goods",
        "Temple": "A religious building for worship and ceremonies",
        "House": "A residential building for living",
        "Cave": "A natural underground chamber",

        # Level 3
        "The Bar": "The main serving area of a tavern where drinks are poured and patrons gather",
        "Kitchen": "A room for food preparation",
        "Bedroom": "A room for sleeping",
        "Chamber": "A room or enclosed space within a cave or structure"
    }

    return descriptions.get(location_type, f"A {location_type}")


def get_all_types_by_level(level: LocationLevel) -> List[str]:
    """
    Get all valid location types for a given level

    Args:
        level: The location level

    Returns:
        List of all valid types for that level
    """
    if level == LocationLevel.REGION:
        return REGION_TYPES["geographic_features"]
    elif level == LocationLevel.LEVEL_1:
        return (
            LEVEL_1_LOCATION_TYPES["settlements"] +
            LEVEL_1_LOCATION_TYPES["natural_features"] +
            LEVEL_1_LOCATION_TYPES["constructed_features"]
        )
    elif level == LocationLevel.LEVEL_2:
        return (
            LEVEL_2_LOCATION_TYPES["buildings"] +
            LEVEL_2_LOCATION_TYPES["outdoor_spaces"] +
            LEVEL_2_LOCATION_TYPES["natural_features"] +
            LEVEL_2_LOCATION_TYPES["landmarks"]
        )
    elif level == LocationLevel.LEVEL_3:
        return (
            LEVEL_3_LOCATION_TYPES["residential_rooms"] +
            LEVEL_3_LOCATION_TYPES["commercial_spaces"] +
            LEVEL_3_LOCATION_TYPES["tavern_inn_rooms"] +
            LEVEL_3_LOCATION_TYPES["religious_spaces"] +
            LEVEL_3_LOCATION_TYPES["civic_government"] +
            LEVEL_3_LOCATION_TYPES["military_spaces"] +
            LEVEL_3_LOCATION_TYPES["utility_spaces"] +
            LEVEL_3_LOCATION_TYPES["natural_spaces"] +
            LEVEL_3_LOCATION_TYPES["special_spaces"]
        )
    return []
