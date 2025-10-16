"""
Multiplayer Session Manager
Handles turn management, player synchronization, and party coordination
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from ..core.logging import get_logger
from ..models.state import GameSessionState, SessionStatus
from ..services.redis_manager import redis_manager
from ..services.rabbitmq_client import rabbitmq_client
from ..api.websocket_manager import connection_manager

logger = get_logger(__name__)


class MultiplayerSessionManager:
    """
    Manages multiplayer game sessions with turn management and synchronization
    """

    def __init__(self):
        # Track active party sessions
        self.active_parties: Dict[str, Dict[str, Any]] = {}

        # Turn timers
        self.turn_timers: Dict[str, asyncio.Task] = {}

    async def initialize_party_session(
        self,
        session_id: str,
        state: GameSessionState
    ) -> bool:
        """
        Initialize multiplayer party session

        Args:
            session_id: Session ID
            state: Game session state

        Returns:
            Success status
        """
        try:
            logger.info(
                "initializing_party_session",
                session_id=session_id,
                player_count=len(state.get("players", []))
            )

            party_settings = state.get("party_settings", {})

            # Create party tracking data
            self.active_parties[session_id] = {
                "session_id": session_id,
                "host_player_id": party_settings.get("host_player_id"),
                "max_players": party_settings.get("max_players", 4),
                "current_players": len(state.get("players", [])),
                "turn_mode": party_settings.get("turn_mode", "open"),  # open, sequential, initiative
                "turn_timeout_seconds": party_settings.get("turn_timeout", 120),
                "status": "active",
                "created_at": datetime.utcnow().isoformat()
            }

            # If sequential turn mode, set first player
            if party_settings.get("turn_mode") == "sequential":
                await self._start_next_turn(session_id, state)

            # Broadcast party initialized
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "party_initialized",
                    "party_info": self.active_parties[session_id],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "party_session_initialized",
                session_id=session_id
            )

            return True

        except Exception as e:
            logger.error(
                "party_initialization_failed",
                session_id=session_id,
                error=str(e)
            )
            return False

    async def add_player_to_party(
        self,
        session_id: str,
        player_id: str,
        character_name: str
    ) -> bool:
        """
        Add player to active party

        Args:
            session_id: Session ID
            player_id: Player ID
            character_name: Character name

        Returns:
            Success status
        """
        try:
            if session_id not in self.active_parties:
                logger.warning("party_not_found", session_id=session_id)
                return False

            party = self.active_parties[session_id]

            # Check if party is full
            if party["current_players"] >= party["max_players"]:
                logger.warning("party_full", session_id=session_id)
                return False

            # Update player count
            party["current_players"] += 1

            # Broadcast player joined
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "player_joined_party",
                    "player_id": player_id,
                    "character_name": character_name,
                    "current_players": party["current_players"],
                    "max_players": party["max_players"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(
                "player_added_to_party",
                session_id=session_id,
                player_id=player_id,
                current_players=party["current_players"]
            )

            return True

        except Exception as e:
            logger.error("player_add_failed", error=str(e))
            return False

    async def remove_player_from_party(
        self,
        session_id: str,
        player_id: str
    ) -> bool:
        """Remove player from party"""
        try:
            if session_id not in self.active_parties:
                return False

            party = self.active_parties[session_id]
            party["current_players"] = max(0, party["current_players"] - 1)

            # If host leaves, transfer to another player
            if party["host_player_id"] == player_id:
                await self._transfer_host(session_id)

            # Broadcast player left
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "player_left_party",
                    "player_id": player_id,
                    "current_players": party["current_players"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # If party empty, clean up
            if party["current_players"] == 0:
                del self.active_parties[session_id]

            logger.info(
                "player_removed_from_party",
                session_id=session_id,
                player_id=player_id
            )

            return True

        except Exception as e:
            logger.error("player_removal_failed", error=str(e))
            return False

    async def _transfer_host(self, session_id: str):
        """Transfer host to another player"""
        try:
            # Load state to get other players
            state = await redis_manager.load_state(session_id)

            if state and state.get("players"):
                new_host = state["players"][0]["player_id"]
                self.active_parties[session_id]["host_player_id"] = new_host

                await connection_manager.broadcast_to_session(
                    session_id,
                    {
                        "event": "host_transferred",
                        "new_host_id": new_host,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

        except Exception as e:
            logger.error("host_transfer_failed", error=str(e))

    async def _start_next_turn(
        self,
        session_id: str,
        state: GameSessionState
    ):
        """Start next player's turn in sequential mode"""
        try:
            players = state.get("players", [])
            if not players:
                return

            current_turn_player_id = state.get("current_turn_player_id")

            # Find next player
            if not current_turn_player_id:
                next_player = players[0]
            else:
                current_index = next(
                    (i for i, p in enumerate(players) if p["player_id"] == current_turn_player_id),
                    -1
                )
                next_index = (current_index + 1) % len(players)
                next_player = players[next_index]

            # Update state
            state["current_turn_player_id"] = next_player["player_id"]
            state["turn_started_at"] = datetime.utcnow().isoformat()

            await redis_manager.save_state(session_id, state)

            # Broadcast turn start
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "turn_started",
                    "player_id": next_player["player_id"],
                    "character_name": next_player.get("character_name"),
                    "turn_timeout_seconds": self.active_parties[session_id]["turn_timeout_seconds"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Start turn timer
            await self._start_turn_timer(session_id, next_player["player_id"])

        except Exception as e:
            logger.error("turn_start_failed", error=str(e))

    async def _start_turn_timer(self, session_id: str, player_id: str):
        """Start countdown timer for player's turn"""
        try:
            # Cancel existing timer
            if session_id in self.turn_timers:
                self.turn_timers[session_id].cancel()

            # Create new timer
            timeout = self.active_parties[session_id]["turn_timeout_seconds"]

            async def turn_timeout():
                await asyncio.sleep(timeout)

                # Load state
                state = await redis_manager.load_state(session_id)

                if state and state.get("current_turn_player_id") == player_id:
                    # Timeout - skip to next player
                    await connection_manager.broadcast_to_session(
                        session_id,
                        {
                            "event": "turn_timeout",
                            "player_id": player_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

                    # Move to next player
                    await self._start_next_turn(session_id, state)

            self.turn_timers[session_id] = asyncio.create_task(turn_timeout())

        except Exception as e:
            logger.error("turn_timer_failed", error=str(e))

    async def end_turn(
        self,
        session_id: str,
        player_id: str
    ) -> bool:
        """
        End current player's turn

        Args:
            session_id: Session ID
            player_id: Player ID ending turn

        Returns:
            Success status
        """
        try:
            state = await redis_manager.load_state(session_id)

            if not state:
                return False

            # Verify it's this player's turn
            if state.get("current_turn_player_id") != player_id:
                logger.warning(
                    "not_players_turn",
                    session_id=session_id,
                    player_id=player_id
                )
                return False

            # Cancel turn timer
            if session_id in self.turn_timers:
                self.turn_timers[session_id].cancel()

            # Broadcast turn ended
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "turn_ended",
                    "player_id": player_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # Start next turn
            await self._start_next_turn(session_id, state)

            return True

        except Exception as e:
            logger.error("turn_end_failed", error=str(e))
            return False

    async def coordinate_party_action(
        self,
        session_id: str,
        action_type: str,
        initiating_player_id: str,
        required_participants: int = 2
    ) -> Dict[str, Any]:
        """
        Coordinate multi-player action (e.g., group puzzle, combined attack)

        Args:
            session_id: Session ID
            action_type: Type of coordinated action
            initiating_player_id: Player who initiated
            required_participants: Number of players required

        Returns:
            Coordination result
        """
        try:
            logger.info(
                "coordinating_party_action",
                session_id=session_id,
                action_type=action_type,
                required=required_participants
            )

            # Create coordination request
            coordination_id = f"coord_{datetime.utcnow().timestamp()}"

            coordination_data = {
                "coordination_id": coordination_id,
                "action_type": action_type,
                "initiating_player": initiating_player_id,
                "required_participants": required_participants,
                "confirmed_participants": [initiating_player_id],
                "timeout_seconds": 60,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            }

            # Broadcast coordination request
            await connection_manager.broadcast_to_session(
                session_id,
                {
                    "event": "coordination_request",
                    "coordination": coordination_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            # TODO: Implement coordination timeout and confirmation tracking
            # For now, return pending status

            return coordination_data

        except Exception as e:
            logger.error("party_coordination_failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e)
            }

    async def get_party_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current party status"""
        if session_id in self.active_parties:
            return self.active_parties[session_id]
        return None


# Global instance
multiplayer_manager = MultiplayerSessionManager()
