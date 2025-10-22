"""
WebSocket API for Game UI Gateway
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/game/{session_id}/player/{player_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: UUID, player_id: UUID):
    """WebSocket endpoint for game UI"""
    from ..main import connection_manager, command_publisher

    # Connect the WebSocket
    await connection_manager.connect(websocket, session_id, player_id)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "session_id": str(session_id),
            "player_id": str(player_id)
        })

        # Send initial scene (temporary - until game engine integration)
        await websocket.send_json({
            "type": "event",
            "event_type": "scene_update",
            "payload": {
                "scene_description": "🎮 <strong>Welcome to SkillForge!</strong><br><br>Your adventure begins here. The game engine is initializing your campaign and will start sending you narrative content soon.<br><br>For now, you can test the interface by typing actions in the input box below.",
                "available_actions": [
                    "Look around",
                    "Check inventory",
                    "Talk to NPC",
                    "Explore the area"
                ]
            }
        })

        # Send initial quest data
        await websocket.send_json({
            "type": "event",
            "event_type": "quest_progress",
            "payload": {
                "objectives": [
                    {
                        "description": "Connect to the game server",
                        "completed": True
                    },
                    {
                        "description": "Await first quest from Game Master",
                        "completed": False
                    },
                    {
                        "description": "Begin your adventure",
                        "completed": False
                    }
                ]
            }
        })

        # Main message loop
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Handle different command types
                command_type = message.get('command_type', '')

                if command_type == 'player_action':
                    action = message['payload'].get('action', '')
                    logger.info(f"Player action received - Session: {session_id}, Player: {player_id}, Action: {action}")

                    # Publish player action
                    await command_publisher.publish_player_action(
                        session_id,
                        player_id,
                        action,
                        message['payload'].get('metadata')
                    )

                    logger.info(f"Player action published to RabbitMQ - Action: {action}")

                    # Send acknowledgment
                    await websocket.send_json({
                        "type": "ack",
                        "request_id": message.get('request_id'),
                        "status": "received"
                    })

                elif command_type == 'team_chat':
                    # Publish team chat
                    await command_publisher.publish_team_chat(
                        session_id,
                        player_id,
                        message['payload'].get('message', ''),
                        message['payload'].get('chat_type', 'team')
                    )

                    # Send acknowledgment
                    await websocket.send_json({
                        "type": "ack",
                        "request_id": message.get('request_id'),
                        "status": "received"
                    })

                elif command_type == 'ping':
                    # Respond to ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get('timestamp')
                    })

                else:
                    logger.warning(f"Unknown command type: {command_type}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"Player {player_id} disconnected from session {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        # Disconnect the WebSocket
        connection_manager.disconnect(websocket)
