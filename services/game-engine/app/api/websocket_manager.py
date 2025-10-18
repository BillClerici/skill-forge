"""
WebSocket Connection Manager
Handles real-time bidirectional communication for gameplay
"""
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import asyncio

from ..core.logging import get_logger
from ..services.redis_manager import redis_manager
from ..workflows.game_loop import game_loop
from ..models.state import GameSessionState

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for game sessions
    Handles message routing and player presence
    """

    def __init__(self):
        # Map of session_id -> set of WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # Map of websocket -> player_id
        self.websocket_to_player: Dict[WebSocket, str] = {}

        # Map of session_id -> typing players
        self.typing_players: Dict[str, Set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        player_id: str
    ):
        """
        Accept WebSocket connection and add to session

        Args:
            websocket: WebSocket connection
            session_id: Game session ID
            player_id: Player ID
        """
        await websocket.accept()

        # Add to active connections
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        self.websocket_to_player[websocket] = player_id

        logger.info(
            "websocket_connected",
            session_id=session_id,
            player_id=player_id,
            total_connections=len(self.active_connections[session_id])
        )

        # Send connection confirmation
        await self.send_personal_message(
            {
                "event": "connected",
                "session_id": session_id,
                "player_id": player_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            websocket
        )

        # Notify other players
        await self.broadcast_to_session(
            session_id,
            {
                "event": "player_joined",
                "player_id": player_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            exclude_websocket=websocket
        )

        # Send current game state on connection (for page refresh persistence)
        try:
            state = await redis_manager.load_state(session_id)
            if state:
                # Send quest progress
                from ..workflows.game_loop import calculate_complete_quest_progress
                quest_progress = await calculate_complete_quest_progress(state)
                if quest_progress:
                    logger.info(
                        "sending_quest_progress_on_connect",
                        session_id=session_id,
                        quest_progress=quest_progress
                    )
                    await self.send_personal_message(
                        {
                            "event": "quest_progress_update",
                            "quest_progress": quest_progress
                        },
                        websocket
                    )

                # Send scene data (for Investigate Scene panel)
                if state.get("scene_description"):
                    logger.info(
                        "sending_scene_data_on_connect",
                        session_id=session_id
                    )

                    # Enrich scene data with completion status
                    enriched_discoveries = self._mark_completed_discoveries(
                        state.get("available_discoveries", []),
                        state,
                        player_id
                    )

                    enriched_npcs = self._mark_encountered_npcs(
                        state.get("available_npcs", []),
                        state,
                        player_id
                    )

                    await self.send_personal_message(
                        {
                            "event": "scene_update",
                            "scene_description": state.get("scene_description", ""),
                            "available_actions": state.get("available_actions", []),
                            "available_npcs": enriched_npcs,
                            "visible_items": state.get("visible_items", []),
                            "available_discoveries": enriched_discoveries,
                            "active_challenges": state.get("active_challenges", []),
                            "active_events": state.get("active_events", [])
                        },
                        websocket
                    )
        except Exception as e:
            logger.error(
                "state_on_connect_failed",
                session_id=session_id,
                error=str(e)
            )

    def disconnect(self, websocket: WebSocket, session_id: str):
        """
        Remove WebSocket connection from session

        Args:
            websocket: WebSocket connection
            session_id: Game session ID
        """
        player_id = self.websocket_to_player.get(websocket)

        # Remove from active connections
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        # Remove from websocket mapping
        if websocket in self.websocket_to_player:
            del self.websocket_to_player[websocket]

        # Remove from typing indicators
        if session_id in self.typing_players and player_id:
            self.typing_players[session_id].discard(player_id)

        logger.info(
            "websocket_disconnected",
            session_id=session_id,
            player_id=player_id
        )

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        Send message to specific WebSocket connection

        Args:
            message: Message data
            websocket: Target WebSocket
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(
                "send_message_failed",
                error=str(e)
            )

    async def broadcast_to_session(
        self,
        session_id: str,
        message: Dict[str, Any],
        exclude_websocket: Optional[WebSocket] = None
    ):
        """
        Broadcast message to all connections in session

        Args:
            session_id: Game session ID
            message: Message data
            exclude_websocket: Optional WebSocket to exclude from broadcast
        """
        if session_id not in self.active_connections:
            return

        disconnected = []

        for websocket in self.active_connections[session_id]:
            if websocket == exclude_websocket:
                continue

            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(
                    "broadcast_failed",
                    session_id=session_id,
                    error=str(e)
                )
                disconnected.append(websocket)

        # Clean up disconnected WebSockets
        for websocket in disconnected:
            self.disconnect(websocket, session_id)

    async def handle_typing_indicator(
        self,
        session_id: str,
        player_id: str,
        is_typing: bool
    ):
        """
        Handle typing indicator updates

        Args:
            session_id: Game session ID
            player_id: Player ID
            is_typing: Whether player is typing
        """
        if session_id not in self.typing_players:
            self.typing_players[session_id] = set()

        if is_typing:
            self.typing_players[session_id].add(player_id)
        else:
            self.typing_players[session_id].discard(player_id)

        # Broadcast typing status
        await self.broadcast_to_session(
            session_id,
            {
                "event": "typing_indicator",
                "player_id": player_id,
                "is_typing": is_typing,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    async def process_player_action(
        self,
        session_id: str,
        player_id: str,
        action_content: str,
        websocket: WebSocket
    ):
        """
        Process player action and inject into game loop workflow

        Args:
            session_id: Game session ID
            player_id: Player ID
            action_content: Player's action text
            websocket: WebSocket connection
        """
        try:
            logger.info(
                "processing_player_action",
                session_id=session_id,
                player_id=player_id,
                content_length=len(action_content)
            )

            # Acquire lock for session state
            lock_acquired = await redis_manager.acquire_lock(session_id, timeout=30)

            if not lock_acquired:
                await self.send_personal_message(
                    {
                        "event": "error",
                        "message": "Session is currently being processed. Please try again.",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    websocket
                )
                return

            try:
                # Load current state from Redis
                state = await redis_manager.load_state(session_id)

                if not state:
                    await self.send_personal_message(
                        {
                            "event": "error",
                            "message": "Session not found.",
                            "timestamp": datetime.utcnow().isoformat()
                        },
                        websocket
                    )
                    return

                # Check if session is awaiting player input
                if not state.get("awaiting_player_input"):
                    await self.send_personal_message(
                        {
                            "event": "error",
                            "message": "Session is not ready for input.",
                            "timestamp": datetime.utcnow().isoformat()
                        },
                        websocket
                    )
                    return

                # Inject player action into state
                state["pending_action"] = {
                    "player_id": player_id,
                    "player_input": action_content,
                    "timestamp": datetime.utcnow().isoformat()
                }

                state["awaiting_player_input"] = False
                state["current_node"] = "interpret_action"

                # Clear scene_just_generated flag if it's set
                # This prevents the scene from being rebroadcast after actions like questions
                if state.get("scene_just_generated"):
                    state["scene_just_generated"] = False

                # Save updated state
                await redis_manager.save_state(session_id, state)

                # Send acknowledgment
                await self.send_personal_message(
                    {
                        "event": "action_received",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    websocket
                )

                # Broadcast action to other players (for multiplayer)
                await self.broadcast_to_session(
                    session_id,
                    {
                        "event": "player_action_broadcast",
                        "player_id": player_id,
                        "action_preview": action_content[:50] + "..." if len(action_content) > 50 else action_content,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    exclude_websocket=websocket
                )

                # Continue workflow execution in background
                asyncio.create_task(self._continue_workflow(session_id, state))

            finally:
                # Release lock
                await redis_manager.release_lock(session_id)

        except Exception as e:
            logger.error(
                "player_action_processing_failed",
                session_id=session_id,
                player_id=player_id,
                error=str(e)
            )

            await self.send_personal_message(
                {
                    "event": "error",
                    "message": "Failed to process action. Please try again.",
                    "timestamp": datetime.utcnow().isoformat()
                },
                websocket
            )

    async def _continue_workflow(self, session_id: str, state: GameSessionState):
        """
        Continue workflow execution after player input

        Args:
            session_id: Game session ID
            state: Current game state
        """
        try:
            logger.info(
                "continuing_workflow",
                session_id=session_id,
                current_node=state.get("current_node")
            )

            # Execute workflow from current node
            # Set recursion_limit to 50 to handle longer gameplay sequences
            result = await game_loop.ainvoke(
                state,
                {"recursion_limit": 50}
            )

            # Broadcast state updates to all players
            await self._broadcast_state_updates(session_id, result)

        except Exception as e:
            logger.error(
                "workflow_continuation_failed",
                session_id=session_id,
                error=str(e)
            )

    async def _broadcast_state_updates(
        self,
        session_id: str,
        state: GameSessionState
    ):
        """
        Broadcast state updates to all connected players

        Args:
            session_id: Game session ID
            state: Updated game state
        """
        try:
            # Send new chat messages
            chat_messages = state.get("chat_messages", [])
            if chat_messages:
                # Send only the latest messages (e.g., last 5)
                recent_messages = chat_messages[-5:]

                for message in recent_messages:
                    await self.broadcast_to_session(
                        session_id,
                        {
                            "event": "chat_message",
                            "message": message,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

            # Send scene update only if scene was just generated
            # Check if the last action was a scene generation by looking at current_node
            # Scene updates should only be sent after generate_scene node
            # DON'T send scene_update for questions, acknowledgments, or other non-scene-changing actions
            if state.get("scene_description") and state.get("scene_just_generated", False):
                await self.broadcast_to_session(
                    session_id,
                    {
                        "event": "scene_update",
                        "scene_description": state["scene_description"],
                        "available_actions": state.get("available_actions", []),
                        "available_npcs": state.get("available_npcs", []),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            # Send state status update
            await self.broadcast_to_session(
                session_id,
                {
                    "event": "state_update",
                    "status": state.get("status"),
                    "current_node": state.get("current_node"),
                    "awaiting_player_input": state.get("awaiting_player_input", False),
                    "current_scene_id": state.get("current_scene_id"),
                    "scene_name": state.get("scene_name"),
                    "place_name": state.get("place_name"),
                    "location_name": state.get("location_name"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error(
                "broadcast_state_updates_failed",
                session_id=session_id,
                error=str(e)
            )

    def _mark_completed_discoveries(
        self,
        discoveries: list,
        state: GameSessionState,
        player_id: str
    ) -> list:
        """
        Mark discoveries as investigated if player has acquired the knowledge

        Args:
            discoveries: List of discovery objects
            state: Game state
            player_id: Player ID

        Returns:
            List of discoveries with 'investigated' flag added
        """
        if not discoveries:
            return []

        player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
        enriched_discoveries = []

        for discovery in discoveries:
            discovery_copy = discovery.copy()
            knowledge_revealed = discovery.get("knowledge_revealed", [])

            # If discovery has knowledge and player has ALL of it, mark as investigated
            if knowledge_revealed:
                has_all_knowledge = all(
                    kid in player_knowledge
                    for kid in knowledge_revealed
                )
                discovery_copy["investigated"] = has_all_knowledge
            else:
                discovery_copy["investigated"] = False

            enriched_discoveries.append(discovery_copy)

        return enriched_discoveries

    def _mark_encountered_npcs(
        self,
        npcs: list,
        state: GameSessionState,
        player_id: str
    ) -> list:
        """
        Mark NPCs as encountered if player has talked to them

        Args:
            npcs: List of NPC objects
            state: Game state
            player_id: Player ID

        Returns:
            List of NPCs with 'encountered' flag added
        """
        if not npcs:
            return []

        # For now, we can check if the player has knowledge from the NPC
        # In the future, we could track encounters more explicitly
        player_knowledge = state.get("player_knowledge", {}).get(player_id, {})
        enriched_npcs = []

        for npc in npcs:
            npc_copy = npc.copy()
            # For now, mark all NPCs as not encountered
            # TODO: Implement proper NPC encounter tracking
            npc_copy["encountered"] = False
            enriched_npcs.append(npc_copy)

        return enriched_npcs

    async def handle_team_chat_message(
        self,
        session_id: str,
        player_id: str,
        channel: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Handle team chat message

        Args:
            session_id: Game session ID
            player_id: Sender player ID
            channel: Chat channel (party, whisper, ooc, strategy)
            content: Message content
            metadata: Optional metadata (mentions, reply_to, etc.)
        """
        try:
            message = {
                "event": "team_chat_message",
                "message_id": f"team_msg_{datetime.utcnow().timestamp()}",
                "session_id": session_id,
                "player_id": player_id,
                "channel": channel,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat()
            }

            # TODO: Persist to MongoDB

            # Broadcast to session
            if channel == "whisper" and metadata and metadata.get("target_player_id"):
                # Send only to sender and target
                target_player_id = metadata["target_player_id"]
                # TODO: Implement targeted send to specific players
                await self.broadcast_to_session(session_id, message)
            else:
                # Broadcast to all
                await self.broadcast_to_session(session_id, message)

            logger.info(
                "team_chat_message_sent",
                session_id=session_id,
                player_id=player_id,
                channel=channel
            )

        except Exception as e:
            logger.error(
                "team_chat_message_failed",
                session_id=session_id,
                error=str(e)
            )


# Global connection manager instance
connection_manager = ConnectionManager()
