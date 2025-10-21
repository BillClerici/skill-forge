"""
RabbitMQ Consumer for Game Engine
Listens for player actions and processes them through the game loop
"""
import json
import asyncio
from typing import Optional
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from datetime import datetime

from ..core.config import settings
from ..core.logging import get_logger
from ..services.redis_manager import redis_manager
from ..services.rabbitmq_client import rabbitmq_client
from ..workflows.game_loop import game_loop
from ..models.state import GameSessionState

logger = get_logger(__name__)


class RabbitMQConsumer:
    """
    Consumes player actions from RabbitMQ and processes them through game loop
    """

    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self.consuming = False

    async def connect(self):
        """Connect to RabbitMQ and set up queue"""
        try:
            self.connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL
            )
            self.channel = await self.connection.channel()

            # Set prefetch count to process one message at a time
            await self.channel.set_qos(prefetch_count=1)

            # Declare exchange (should already exist from init-rabbitmq)
            exchange = await self.channel.declare_exchange(
                'game.events',
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )

            # Declare queue for game engine
            self.queue = await self.channel.declare_queue(
                'game.engine.actions',
                durable=True
            )

            # Bind to player action events
            await self.queue.bind(
                exchange,
                routing_key='game.player_action.#'
            )

            logger.info(
                "rabbitmq_consumer_connected",
                queue=self.queue.name,
                exchange='game.events',
                routing_key='game.player_action.#'
            )

        except Exception as e:
            logger.error("rabbitmq_consumer_connection_failed", error=str(e))
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        self.consuming = False
        if self.connection:
            await self.connection.close()
            logger.info("rabbitmq_consumer_disconnected")

    async def start_consuming(self):
        """Start consuming messages from the queue"""
        if not self.queue:
            raise RuntimeError("Queue not initialized. Call connect() first.")

        self.consuming = True
        logger.info("started_consuming_player_actions")

        # Start consuming messages
        await self.queue.consume(self._process_message)

    async def _process_message(self, message: AbstractIncomingMessage):
        """
        Process incoming player action message

        Args:
            message: Incoming RabbitMQ message
        """
        async with message.process():
            try:
                # Parse message
                data = json.loads(message.body.decode())

                session_id = data.get('session_id')
                player_id = data.get('player_id')
                action = data.get('action')
                metadata = data.get('metadata', {})

                logger.info(
                    "player_action_received",
                    session_id=session_id,
                    player_id=player_id,
                    action=action[:100] if action else None
                )

                # Load current game state from Redis
                state = await redis_manager.load_state(session_id)

                if not state:
                    logger.error(
                        "session_not_found",
                        session_id=session_id
                    )
                    return

                # Add player action to state
                state["pending_action"] = {
                    "player_id": player_id,
                    "action": action,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": metadata
                }
                state["awaiting_player_input"] = False
                state["current_node"] = "process_player_action"
                state["last_updated"] = datetime.utcnow().isoformat()

                # Save updated state
                await redis_manager.save_state(session_id, state)

                # Process through game loop
                logger.info(
                    "processing_action_through_game_loop",
                    session_id=session_id,
                    current_node=state.get("current_node")
                )

                # Execute game loop with the action
                result = await game_loop.ainvoke(
                    state,
                    {"recursion_limit": 50}
                )

                # Publish results back to RabbitMQ for UI Gateway
                await self._publish_game_response(session_id, result)

                logger.info(
                    "player_action_processed",
                    session_id=session_id,
                    new_node=result.get("current_node"),
                    awaiting_input=result.get("awaiting_player_input")
                )

            except json.JSONDecodeError as e:
                logger.error("invalid_message_json", error=str(e))

            except Exception as e:
                logger.error(
                    "player_action_processing_failed",
                    error=str(e),
                    message_id=message.message_id
                )

    async def _publish_game_response(self, session_id: str, state: GameSessionState):
        """
        Publish game response events back to RabbitMQ

        Args:
            session_id: Session ID
            state: Updated game state
        """
        try:
            # Publish scene update if scene changed
            scene_description = state.get("scene_description")
            if scene_description:
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{session_id}.scene_update",
                    message={
                        "type": "event",
                        "event_type": "scene_update",
                        "session_id": session_id,
                        "payload": {
                            "scene_description": scene_description,
                            "scene_name": state.get("scene_name", ""),
                            "location_name": state.get("location_name", ""),
                            "available_actions": state.get("available_actions", []),
                            "available_npcs": state.get("available_npcs", []),
                            "time_of_day": state.get("time_of_day", ""),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )

            # Publish quest progress if quests updated
            current_quest_id = state.get("current_quest_id")
            if current_quest_id:
                # Get quest objectives from Neo4j
                from ..services.neo4j_graph import neo4j_graph

                try:
                    # Get player from state
                    players = state.get("players", [])
                    if players:
                        player_id = players[0].get("player_id")
                        campaign_id = state.get("campaign_id")

                        # Get objective progress
                        progress = await neo4j_graph.get_player_objective_progress(
                            player_id,
                            campaign_id
                        )

                        # Extract current quest objectives
                        objectives = []
                        for co in progress.get("campaign_objectives", []):
                            for qo in co.get("quest_objectives", []):
                                if qo.get("status") in ["not_started", "in_progress"]:
                                    objectives.append({
                                        "description": qo.get("name", "Unknown objective"),
                                        "completed": qo.get("status") == "completed"
                                    })

                        if objectives:
                            await rabbitmq_client.publish_event(
                                exchange="game.events",
                                routing_key=f"session.{session_id}.quest_progress",
                                message={
                                    "type": "event",
                                    "event_type": "quest_progress",
                                    "session_id": session_id,
                                    "payload": {
                                        "objectives": objectives,
                                        "timestamp": datetime.utcnow().isoformat()
                                    }
                                }
                            )
                except Exception as e:
                    logger.warning("quest_progress_publish_failed", error=str(e))

            # Publish chat messages (GM narrative, NPC dialogue, etc.)
            chat_messages = state.get("chat_messages", [])
            if chat_messages:
                # Get the latest message
                latest_message = chat_messages[-1]
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{session_id}.chat_message",
                    message={
                        "type": "event",
                        "event_type": "chat_message",
                        "session_id": session_id,
                        "payload": {
                            "sender": latest_message.get("sender", "Game Master"),
                            "content": latest_message.get("content", ""),
                            "message_type": latest_message.get("message_type", "gm"),
                            "timestamp": latest_message.get("timestamp", datetime.utcnow().isoformat())
                        }
                    }
                )

            # Publish party updates
            players = state.get("players", [])
            if players:
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{session_id}.party_update",
                    message={
                        "type": "event",
                        "event_type": "party_update",
                        "session_id": session_id,
                        "payload": {
                            "players": [
                                {
                                    "player_id": p.get("player_id"),
                                    "character_name": p.get("character_name", "Unknown"),
                                    "status": "online"
                                }
                                for p in players
                            ],
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )

        except Exception as e:
            logger.error(
                "game_response_publish_failed",
                session_id=session_id,
                error=str(e)
            )


# Global instance
rabbitmq_consumer = RabbitMQConsumer()
