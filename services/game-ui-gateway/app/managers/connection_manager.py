"""
WebSocket Connection Manager
"""
import logging
from typing import Dict, Set
from uuid import UUID
from fastapi import WebSocket
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for game sessions"""

    def __init__(self):
        # session_id -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # websocket -> (session_id, player_id)
        self.connection_info: Dict[WebSocket, tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, session_id: UUID, player_id: UUID):
        """Connect a WebSocket to a session"""
        await websocket.accept()

        session_key = str(session_id)
        player_key = str(player_id)

        # Add to active connections
        if session_key not in self.active_connections:
            self.active_connections[session_key] = set()

        self.active_connections[session_key].add(websocket)

        # Store connection info
        self.connection_info[websocket] = (session_key, player_key)

        logger.info(f"Player {player_id} connected to session {session_id}")

    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket"""
        if websocket not in self.connection_info:
            return

        session_key, player_key = self.connection_info[websocket]

        # Remove from active connections
        if session_key in self.active_connections:
            self.active_connections[session_key].discard(websocket)

            # Remove session if no more connections
            if not self.active_connections[session_key]:
                del self.active_connections[session_key]

        # Remove connection info
        del self.connection_info[websocket]

        logger.info(f"Player {player_key} disconnected from session {session_key}")

    async def send_to_session(self, session_id: UUID, message: dict):
        """Send a message to all connections in a session"""
        session_key = str(session_id)

        if session_key not in self.active_connections:
            return

        # Convert message to JSON
        message_json = json.dumps(message)

        # Send to all connections
        disconnected = []

        for connection in self.active_connections[session_key]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected
        for connection in disconnected:
            self.disconnect(connection)

    async def send_to_player(self, session_id: UUID, player_id: UUID, message: dict):
        """Send a message to a specific player"""
        session_key = str(session_id)
        player_key = str(player_id)

        if session_key not in self.active_connections:
            return

        # Convert message to JSON
        message_json = json.dumps(message)

        # Find player's connection
        for connection in self.active_connections[session_key]:
            if connection in self.connection_info:
                conn_session, conn_player = self.connection_info[connection]
                if conn_player == player_key:
                    try:
                        await connection.send_text(message_json)
                    except Exception as e:
                        logger.error(f"Error sending to player: {e}")
                        self.disconnect(connection)

    def get_connected_players(self, session_id: UUID) -> Set[str]:
        """Get set of connected player IDs for a session"""
        session_key = str(session_id)

        if session_key not in self.active_connections:
            return set()

        players = set()

        for connection in self.active_connections[session_key]:
            if connection in self.connection_info:
                _, player_id = self.connection_info[connection]
                players.add(player_id)

        return players

    def get_session_count(self) -> int:
        """Get count of active sessions"""
        return len(self.active_connections)

    def get_connection_count(self) -> int:
        """Get total count of active connections"""
        return sum(len(conns) for conns in self.active_connections.values())

    async def broadcast_to_session(self, session_id: str, message: dict):
        """
        Broadcast a message to all connections in a session (accepts string session_id)
        This is used by the event consumer which receives string session IDs from RabbitMQ
        """
        if session_id not in self.active_connections:
            logger.debug(f"No active connections for session {session_id}")
            return

        # Convert message to JSON
        message_json = json.dumps(message)

        # Send to all connections
        disconnected = []

        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected
        for connection in disconnected:
            self.disconnect(connection)
