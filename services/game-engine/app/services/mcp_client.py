"""
MCP (Model Context Protocol) Client
Integrates with MCP servers for player data, NPCs, world info, etc.
"""
import httpx
from typing import Dict, Any, Optional, List
from ..core.config import settings
from ..core.logging import get_logger
from ..core.error_handling import (
    async_with_retry,
    with_circuit_breaker,
    ErrorRecovery,
    GracefulDegradation,
    circuit_breakers
)

logger = get_logger(__name__)


class MCPClient:
    """
    Client for communicating with MCP servers
    """

    def __init__(self):
        self.urls = {
            "player_data": settings.MCP_PLAYER_DATA_URL,
            "npc_personality": settings.MCP_NPC_PERSONALITY_URL,
            "world_universe": settings.MCP_WORLD_UNIVERSE_URL,
            "quest_mission": settings.MCP_QUEST_MISSION_URL,
            "item_equipment": settings.MCP_ITEM_EQUIPMENT_URL,
        }
        self.auth_token = settings.MCP_AUTH_TOKEN
        self.timeout = httpx.Timeout(30.0)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

    @async_with_retry(max_attempts=3, delay=0.5, exceptions=(httpx.TimeoutException, httpx.ConnectError))
    async def _get(self, server: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make GET request to MCP server with retry logic"""
        try:
            url = f"{self.urls[server]}{endpoint}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "mcp_get_http_error",
                server=server,
                endpoint=endpoint,
                status=e.response.status_code,
                error=str(e)
            )
            # Use graceful degradation for known endpoints
            return ErrorRecovery.recover_from_mcp_error(
                service_name=server,
                error=e,
                fallback_data=self._get_fallback_data(server, endpoint)
            )
        except Exception as e:
            logger.error(
                "mcp_get_failed",
                server=server,
                endpoint=endpoint,
                error=str(e)
            )
            return ErrorRecovery.recover_from_mcp_error(
                service_name=server,
                error=e,
                fallback_data=self._get_fallback_data(server, endpoint)
            )

    @async_with_retry(max_attempts=3, delay=0.5, exceptions=(httpx.TimeoutException, httpx.ConnectError))
    async def _post(
        self,
        server: str,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Make POST request to MCP server with retry logic"""
        try:
            url = f"{self.urls[server]}{endpoint}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "mcp_post_http_error",
                server=server,
                endpoint=endpoint,
                status=e.response.status_code,
                error=str(e)
            )
            return ErrorRecovery.recover_from_mcp_error(
                service_name=server,
                error=e,
                fallback_data=None  # POST operations typically don't have fallback data
            )
        except Exception as e:
            logger.error(
                "mcp_post_failed",
                server=server,
                endpoint=endpoint,
                error=str(e)
            )
            return ErrorRecovery.recover_from_mcp_error(
                service_name=server,
                error=e,
                fallback_data=None
            )

    def _get_fallback_data(self, server: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Provide fallback data for graceful degradation when MCP servers are unavailable
        """
        # Character info fallback
        if "character-info" in endpoint:
            return GracefulDegradation.get_default_character_data()

        # Quest fallback
        if "quest" in endpoint:
            return GracefulDegradation.get_default_quest_data()

        # No specific fallback available
        return None

    # ============================================
    # Player Data MCP
    # ============================================

    async def get_player_cognitive_profile(
        self,
        player_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get player's cognitive profile"""
        return await self._get(
            "player_data",
            f"/mcp/player-cognitive-profile/{player_id}"
        )

    async def get_character_info(
        self,
        character_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get character information"""
        return await self._get(
            "player_data",
            f"/mcp/character-info/{character_id}"
        )

    # ============================================
    # NPC Personality MCP
    # ============================================

    async def get_npc(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """Get NPC details"""
        return await self._get(
            "npc_personality",
            f"/mcp/npc/{npc_id}"
        )

    async def get_npc_context(
        self,
        npc_id: str,
        profile_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get NPC context including relationship with player"""
        return await self._get(
            "npc_personality",
            f"/mcp/npc-context/{npc_id}/{profile_id}"
        )

    async def get_location_npcs(
        self,
        world_id: Optional[str] = None,
        region_id: Optional[str] = None,
        location_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get all NPCs at a location"""
        params = []
        if world_id:
            params.append(f"world_id={world_id}")
        if region_id:
            params.append(f"region_id={region_id}")
        if location_id:
            params.append(f"location_id={location_id}")

        query = "?" + "&".join(params) if params else ""
        return await self._get(
            "npc_personality",
            f"/mcp/location-npcs{query}"
        )

    async def record_npc_interaction(
        self,
        interaction_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Record player-NPC interaction"""
        return await self._post(
            "npc_personality",
            "/mcp/record-interaction",
            interaction_data
        )

    # ============================================
    # World/Universe MCP
    # ============================================

    async def get_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """Get world details"""
        return await self._get(
            "world_universe",
            f"/mcp/world/{world_id}"
        )

    async def get_region(
        self,
        world_id: str,
        region_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get region details"""
        return await self._get(
            "world_universe",
            f"/mcp/world/{world_id}/region/{region_id}"
        )

    async def get_location(
        self,
        world_id: str,
        location_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get location/scene details"""
        return await self._get(
            "world_universe",
            f"/mcp/world/{world_id}/location/{location_id}"
        )

    # ============================================
    # Quest/Mission MCP
    # ============================================

    async def get_quest(self, quest_id: str) -> Optional[Dict[str, Any]]:
        """Get quest details"""
        return await self._get(
            "quest_mission",
            f"/mcp/quest/{quest_id}"
        )

    async def get_campaign_quests(
        self,
        campaign_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get all quests in a campaign"""
        return await self._get(
            "quest_mission",
            f"/mcp/campaign/{campaign_id}/quests"
        )

    async def update_quest_progress(
        self,
        quest_id: str,
        player_id: str,
        progress_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update player's quest progress"""
        return await self._post(
            "quest_mission",
            f"/mcp/quest/{quest_id}/progress",
            {"player_id": player_id, **progress_data}
        )

    # ============================================
    # Item/Equipment MCP
    # ============================================

    async def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get item details"""
        return await self._get(
            "item_equipment",
            f"/mcp/item/{item_id}"
        )

    async def get_player_inventory(
        self,
        player_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get player's inventory"""
        return await self._get(
            "item_equipment",
            f"/mcp/player/{player_id}/inventory"
        )

    async def add_item_to_inventory(
        self,
        player_id: str,
        item_id: str,
        quantity: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Add item to player inventory"""
        return await self._post(
            "item_equipment",
            f"/mcp/player/{player_id}/inventory/add",
            {"item_id": item_id, "quantity": quantity}
        )


# Global instance
mcp_client = MCPClient()
