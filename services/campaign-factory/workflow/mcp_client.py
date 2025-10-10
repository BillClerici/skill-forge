"""
MCP Client for Campaign Factory
Fetches data from MCP servers for world context
"""
import os
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MCP_WORLD_UNIVERSE_URL = os.getenv("MCP_WORLD_UNIVERSE_URL", "http://mcp-world-universe:8002")
MCP_NPC_PERSONALITY_URL = os.getenv("MCP_NPC_PERSONALITY_URL", "http://mcp-npc-personality:8004")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "mcp_dev_token_2024")


async def fetch_world_context(world_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch complete world context from MCP

    Args:
        world_id: World ID

    Returns:
        World data dict or None if not found
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/worlds/{world_id}",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch world {world_id}: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error fetching world context: {e}")
        return None


async def fetch_region_context(region_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch region context from MCP

    Args:
        region_id: Region ID

    Returns:
        Region data dict or None if not found
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/regions/{region_id}",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch region {region_id}: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error fetching region context: {e}")
        return None


async def fetch_world_species(world_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all species for a world from MCP

    Args:
        world_id: World ID

    Returns:
        List of species dicts
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/worlds/{world_id}/species",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json().get("species", [])
            else:
                logger.error(f"Failed to fetch species for world {world_id}: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Error fetching world species: {e}")
        return []


async def fetch_level1_locations(region_id: str) -> List[Dict[str, Any]]:
    """
    Fetch Level 1 locations for a region from MCP

    Args:
        region_id: Region ID

    Returns:
        List of Level 1 location dicts
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/regions/{region_id}/locations?level=1",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json().get("locations", [])
            else:
                logger.warning(f"Failed to fetch Level 1 locations for region {region_id}: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Error fetching Level 1 locations: {e}")
        return []


async def fetch_level2_locations(parent_location_id: str) -> List[Dict[str, Any]]:
    """
    Fetch Level 2 locations under a parent location from MCP

    Args:
        parent_location_id: Parent location ID

    Returns:
        List of Level 2 location dicts
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/locations/{parent_location_id}/children?level=2",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json().get("locations", [])
            else:
                logger.warning(f"Failed to fetch Level 2 locations for {parent_location_id}: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Error fetching Level 2 locations: {e}")
        return []


async def fetch_level3_locations(parent_location_id: str) -> List[Dict[str, Any]]:
    """
    Fetch Level 3 locations under a parent location from MCP

    Args:
        parent_location_id: Parent location ID

    Returns:
        List of Level 3 location dicts
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MCP_WORLD_UNIVERSE_URL}/locations/{parent_location_id}/children?level=3",
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                return response.json().get("locations", [])
            else:
                logger.warning(f"Failed to fetch Level 3 locations for {parent_location_id}: {response.status_code}")
                return []

    except Exception as e:
        logger.error(f"Error fetching Level 3 locations: {e}")
        return []


async def create_species_via_game_master(
    world_id: str,
    world_context: Dict[str, Any],
    species_data: Dict[str, Any]
) -> Optional[str]:
    """
    Create new species via orchestrator/game-master

    Args:
        world_id: World ID
        world_context: World context dict
        species_data: Species data to create

    Returns:
        Species ID if created, None otherwise
    """
    try:
        orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://agent-orchestrator:9000")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{orchestrator_url}/generate-species",
                json={
                    "world_id": world_id,
                    "world_name": world_context.get("name", ""),
                    "world_genre": world_context.get("genre", ""),
                    "species_data": species_data
                },
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("species_id")
            else:
                logger.error(f"Failed to create species: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating species via game master: {e}")
        return None


async def create_location_via_game_master(
    location_data: Dict[str, Any],
    parent_location_id: Optional[str] = None
) -> Optional[str]:
    """
    Create new location via orchestrator/game-master

    Args:
        location_data: Location data to create
        parent_location_id: Optional parent location ID

    Returns:
        Location ID if created, None otherwise
    """
    try:
        orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://agent-orchestrator:9000")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MCP_WORLD_UNIVERSE_URL}/locations",
                json={
                    **location_data,
                    "parent_location_id": parent_location_id
                },
                headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"}
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return result.get("location_id")
            else:
                logger.error(f"Failed to create location: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error creating location via MCP: {e}")
        return None
