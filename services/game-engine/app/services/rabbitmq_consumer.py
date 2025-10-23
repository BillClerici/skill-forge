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
                payload = data.get('payload', {})
                player_id = payload.get('player_id')
                action = payload.get('action')
                metadata = payload.get('metadata', {})

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

                # Prepare action data
                pending_action = {
                    "player_id": player_id,
                    "player_input": action,  # Changed from "action" to "player_input" to match workflow expectation
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": metadata
                }

                # Process through game loop
                logger.info(
                    "processing_action_through_game_loop",
                    session_id=session_id
                )

                # Execute game loop with minimal input
                # The workflow will load full state from Redis in initialize_session node
                workflow_input = {
                    "session_id": session_id,
                    "pending_action": pending_action,
                    "awaiting_player_input": False
                }

                result = await game_loop.ainvoke(
                    workflow_input,
                    {"recursion_limit": 50}
                )

                logger.info(
                    "workflow_result_conversation_state",
                    session_id=session_id,
                    active_conversation_npc_id=result.get("active_conversation_npc_id"),
                    active_conversation_npc_name=result.get("active_conversation_npc_name"),
                    conversation_turn_count=result.get("conversation_turn_count", 0)
                )

                # Process any pending acquisitions through objective tracker
                from ..workflows.objective_tracker import process_acquisitions

                pending_acquisitions = result.get("pending_acquisitions", {
                    "knowledge": [],
                    "items": [],
                    "events": [],
                    "challenges": []
                })

                logger.info(
                    "checking_pending_acquisitions",
                    session_id=session_id,
                    pending=pending_acquisitions,
                    has_any=any(pending_acquisitions.values())
                )

                if any(pending_acquisitions.values()):
                    players = result.get("players", [])
                    if players and result.get("campaign_id"):
                        player_id = players[0].get("player_id")
                        campaign_id = result["campaign_id"]

                        logger.info(
                            "processing_acquisitions_in_consumer",
                            session_id=session_id,
                            knowledge_count=len(pending_acquisitions.get("knowledge", [])),
                            items_count=len(pending_acquisitions.get("items", []))
                        )

                        # Process acquisitions through objective tracker
                        acquisition_results = await process_acquisitions(
                            session_id,
                            player_id,
                            campaign_id,
                            pending_acquisitions
                        )

                        logger.info(
                            "acquisitions_processed_in_consumer",
                            session_id=session_id,
                            total=len(acquisition_results.get("acquisitions", [])),
                            objectives_affected=len(acquisition_results.get("affected_objectives", []))
                        )

                        # Add acquired knowledge to game state
                        if "player_knowledge" not in result:
                            result["player_knowledge"] = {}
                        if player_id not in result["player_knowledge"]:
                            result["player_knowledge"][player_id] = {}

                        for acq in acquisition_results.get("acquisitions", []):
                            if acq.get("type") == "knowledge":
                                knowledge_id = acq.get("data", {}).get("id")
                                if knowledge_id and knowledge_id not in result["player_knowledge"][player_id]:
                                    # Store as dict with metadata for compatibility with _publish_game_response
                                    result["player_knowledge"][player_id][knowledge_id] = {
                                        "level": 1,
                                        "acquired_at": acq.get("data", {}).get("acquired_at", datetime.utcnow().isoformat())
                                    }
                                    logger.info(
                                        "knowledge_added_to_state",
                                        player_id=player_id,
                                        knowledge_id=knowledge_id
                                    )

                        # Clear pending acquisitions
                        result["pending_acquisitions"] = {
                            "knowledge": [],
                            "items": [],
                            "events": [],
                            "challenges": []
                        }

                        # Save updated state
                        await redis_manager.load_state(session_id)  # Reload to get latest
                        await redis_manager.save_state(session_id, result)

                # Persist chat messages to MongoDB for permanent storage
                from ..services.mongo_persistence import mongo_persistence
                chat_messages = result.get("chat_messages", [])
                if chat_messages:
                    # Save the latest chat message to MongoDB
                    latest_message = chat_messages[-1]
                    await mongo_persistence.save_chat_message(session_id, latest_message)

                # Log conversation state before publishing
                logger.info(
                    "before_publish_conversation_state",
                    session_id=session_id,
                    active_conversation_npc_id=result.get("active_conversation_npc_id"),
                    active_conversation_npc_name=result.get("active_conversation_npc_name"),
                    conversation_turn_count=result.get("conversation_turn_count", 0)
                )

                # Publish results back to RabbitMQ for UI Gateway
                await self._publish_game_response(session_id, result)

                logger.info(
                    "player_action_processed",
                    session_id=session_id,
                    new_node=result.get("current_node"),
                    awaiting_input=result.get("awaiting_player_input"),
                    active_conversation_npc_id=result.get("active_conversation_npc_id")
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
                            "active_conversation_npc_id": state.get("active_conversation_npc_id"),
                            "active_conversation_npc_name": state.get("active_conversation_npc_name"),
                            "conversation_turn_count": state.get("conversation_turn_count", 0),
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

                        # Extract quest objectives with progress
                        objectives = []
                        campaign_objectives = []

                        for co in progress.get("campaign_objectives", []):
                            # Add campaign objective with full details
                            campaign_objectives.append({
                                "description": co.get("description", "Unknown objective"),
                                "completion_percentage": co.get("completion_percentage", 0),
                                "percent": co.get("completion_percentage", 0),
                                "completed": co.get("status") == "completed",
                                "status": co.get("status", "not_started")
                            })

                            # Add quest objectives under this campaign objective
                            for qo in co.get("quest_objectives", []):
                                if qo.get("status") in ["not_started", "in_progress", "completed"]:
                                    objectives.append({
                                        "description": qo.get("description", "Unknown objective"),
                                        "progress": qo.get("progress", 0),
                                        "percent": qo.get("progress", 0),
                                        "completed": qo.get("status") == "completed"
                                    })

                        if objectives or campaign_objectives:
                            # Get knowledge and items counts
                            player_knowledge_count = len(state.get("player_knowledge", {}).get(player_id, {}))
                            player_items_count = len(state.get("player_inventories", {}).get(player_id, []))

                            await rabbitmq_client.publish_event(
                                exchange="game.events",
                                routing_key=f"session.{session_id}.quest_progress",
                                message={
                                    "type": "event",
                                    "event_type": "quest_progress",
                                    "session_id": session_id,
                                    "payload": {
                                        "quest_name": state.get("quest_name", ""),
                                        "objectives": objectives,
                                        "campaign_objectives": campaign_objectives,
                                        "campaign_overall_progress": progress.get("campaign_overall_progress", 0),
                                        "knowledge_count": player_knowledge_count,
                                        "items_count": player_items_count,
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
                            "sender": latest_message.get("sender_name", latest_message.get("sender", "Game Master")),
                            "sender_role": latest_message.get("sender_role", ""),
                            "sender_avatar": latest_message.get("sender_avatar", ""),
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

            # Publish acquisitions updates (knowledge, items, events, challenges)
            players = state.get("players", [])
            if players:
                player_id = players[0].get("player_id")

                # Gather player acquisitions
                # Note: player_knowledge and player_inventories are stored as dicts of knowledge_id -> metadata in Redis
                player_knowledge = state.get("player_knowledge", {})
                player_inventories = state.get("player_inventories", {})

                knowledge_list = []
                if player_id in player_knowledge:
                    # Get knowledge IDs for this player
                    player_knowledge_dict = player_knowledge[player_id]
                    if isinstance(player_knowledge_dict, dict):
                        # Fetch full knowledge objects from MongoDB
                        from ..services.mongo_persistence import mongo_persistence
                        knowledge_ids = list(player_knowledge_dict.keys())
                        if knowledge_ids:
                            knowledge_objects = await mongo_persistence.get_knowledge_by_ids(knowledge_ids)
                            for k in knowledge_objects:
                                knowledge_id = k.get("knowledge_id", "")
                                # Handle both dict format (new) and int format (old state)
                                knowledge_metadata = player_knowledge_dict.get(knowledge_id, {})
                                if isinstance(knowledge_metadata, dict):
                                    acquired_at = knowledge_metadata.get("acquired_at", "")
                                else:
                                    # Old format was just integer 1
                                    acquired_at = ""

                                knowledge_list.append({
                                    "id": knowledge_id,
                                    "name": k.get("name", "Unknown Knowledge"),
                                    "description": k.get("description", ""),
                                    "purpose": k.get("purpose", ""),
                                    "source": k.get("source", ""),
                                    "acquired_at": acquired_at
                                })

                items_list = []
                if player_id in player_inventories:
                    # Items are already full objects in state
                    for item in player_inventories[player_id]:
                        items_list.append({
                            "id": item.get("item_id", ""),
                            "name": item.get("name", "Unknown Item"),
                            "description": item.get("description", ""),
                            "purpose": item.get("purpose", ""),
                            "source": item.get("source", ""),
                            "quantity": item.get("quantity", 1),
                            "acquired_at": item.get("acquired_at", "")
                        })

                events_list = state.get("completed_events", [])
                challenges_list = state.get("completed_challenges", [])

                # Publish acquisitions update
                await rabbitmq_client.publish_event(
                    exchange="game.events",
                    routing_key=f"session.{session_id}.acquisitions_update",
                    message={
                        "type": "event",
                        "event_type": "acquisitions_update",
                        "session_id": session_id,
                        "payload": {
                            "knowledge": knowledge_list,
                            "items": items_list,
                            "events": events_list,
                            "challenges": challenges_list,
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
