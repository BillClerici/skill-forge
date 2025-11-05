"""
Message Publisher
Handles publishing messages to RabbitMQ for various campaign events
"""
import json
import logging
import aio_pika

from config import Config
from workflow.state import CampaignWorkflowState
from workflow.campaign_deletion_workflow import CampaignDeletionState

logger = logging.getLogger(__name__)


class MessagePublisher:
    """Handles publishing messages to RabbitMQ"""

    @staticmethod
    async def _get_connection():
        """Get RabbitMQ connection"""
        return await aio_pika.connect_robust(Config.get_rabbitmq_url())

    async def publish_story_ideas(self, state: CampaignWorkflowState):
        """
        Publish story ideas to user via RabbitMQ

        Args:
            state: Campaign workflow state with story ideas
        """
        connection = await self._get_connection()

        async with connection:
            channel = await connection.channel()

            message_data = {
                "request_id": state["request_id"],
                "workflow_phase": "story_selection",
                "story_ideas": state["story_ideas"],
                "regeneration_count": state["story_regeneration_count"]
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message_data).encode(),
                    content_type="application/json"
                ),
                routing_key=f"campaign.story_ideas.{state['user_id']}"
            )

            logger.info(f"Published story ideas to user: {state['user_id']}")

    async def publish_campaign_core(self, state: CampaignWorkflowState):
        """
        Publish campaign core to user for approval

        Args:
            state: Campaign workflow state with campaign core
        """
        connection = await self._get_connection()

        async with connection:
            channel = await connection.channel()

            message_data = {
                "request_id": state["request_id"],
                "workflow_phase": "core_approval",
                "campaign_core": state["campaign_core"]
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message_data).encode(),
                    content_type="application/json"
                ),
                routing_key=f"campaign.core_approval.{state['user_id']}"
            )

            logger.info(f"Published campaign core to user: {state['user_id']}")

    async def publish_campaign_completion(self, state: CampaignWorkflowState):
        """
        Publish campaign completion notification

        Args:
            state: Final campaign workflow state
        """
        connection = await self._get_connection()

        async with connection:
            channel = await connection.channel()

            message_data = {
                "request_id": state["request_id"],
                "workflow_phase": "completed",
                "campaign_id": state["final_campaign_id"],
                "status": "success" if not state["errors"] else "failed",
                "errors": state["errors"],
                "stats": {
                    "num_quests": len(state["quests"]),
                    "num_places": len(state["places"]),
                    "num_scenes": len(state["scenes"]),
                    "num_npcs": len(state["npcs"]),
                    "new_species_created": len(state["new_species_ids"]),
                    "new_locations_created": len(state["new_location_ids"])
                }
            }

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message_data).encode(),
                    content_type="application/json"
                ),
                routing_key=f"campaign.completed.{state['user_id']}"
            )

            logger.info(f"Published campaign completion: {state['final_campaign_id']}")

    async def publish_campaign_error(self, request_id: str, user_id: str, error: str):
        """
        Publish error notification to user

        Args:
            request_id: Request ID
            user_id: User ID
            error: Error message
        """
        try:
            connection = await self._get_connection()

            async with connection:
                channel = await connection.channel()

                message_data = {
                    "request_id": request_id,
                    "workflow_phase": "error",
                    "error": error
                }

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_data).encode(),
                        content_type="application/json"
                    ),
                    routing_key=f"campaign.error.{user_id}"
                )

                logger.info(f"Published error notification: {request_id}")

        except Exception as e:
            logger.error(f"Error publishing error notification: {e}")

    async def publish_deletion_progress(self, state: CampaignDeletionState):
        """
        Publish deletion progress update via RabbitMQ

        Args:
            state: Deletion workflow state
        """
        try:
            connection = await self._get_connection()

            async with connection:
                channel = await connection.channel()

                message_data = {
                    "request_id": state["request_id"],
                    "campaign_id": state.get("campaign_id"),
                    "workflow_phase": "deletion_progress",
                    "current_phase": state.get("current_phase"),
                    "progress_percentage": state.get("progress_percentage", 0),
                    "status_message": state.get("status_message", "Processing..."),
                    "errors": state.get("errors", []),
                    "warnings": state.get("warnings", [])
                }

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_data).encode(),
                        content_type="application/json"
                    ),
                    routing_key=f"campaign.deletion.progress.{state.get('user_id')}"
                )

                logger.info(f"Published deletion progress: {state.get('progress_percentage')}%")

        except Exception as e:
            logger.error(f"Error publishing deletion progress: {e}")

    async def publish_deletion_completion(self, state: CampaignDeletionState):
        """
        Publish deletion completion notification

        Args:
            state: Final deletion workflow state
        """
        try:
            connection = await self._get_connection()

            async with connection:
                channel = await connection.channel()

                message_data = {
                    "request_id": state["request_id"],
                    "campaign_id": state.get("campaign_id"),
                    "campaign_name": state.get("campaign_name"),
                    "workflow_phase": "deletion_completed",
                    "status": "success" if not state.get("errors") else "failed",
                    "errors": state.get("errors", []),
                    "warnings": state.get("warnings", []),
                    "deletion_log": state.get("deletion_log", []),
                    "stats": {
                        "deleted_counts": {
                            "quests": len(state.get("deleted_quests", [])),
                            "places": len(state.get("deleted_places", [])),
                            "scenes": len(state.get("deleted_scenes", [])),
                            "npcs": len(state.get("deleted_npcs", [])),
                            "total_entities": (
                                len(state.get("deleted_quests", [])) +
                                len(state.get("deleted_places", [])) +
                                len(state.get("deleted_scenes", [])) +
                                len(state.get("deleted_npcs", [])) +
                                len(state.get("deleted_discoveries", [])) +
                                len(state.get("deleted_events", [])) +
                                len(state.get("deleted_challenges", [])) +
                                len(state.get("deleted_knowledge", [])) +
                                len(state.get("deleted_items", [])) +
                                len(state.get("deleted_rubrics", []))
                            )
                        },
                        "cleanup": {
                            "species_removed": len(state.get("species_to_remove", [])),
                            "locations_removed": len(state.get("locations_to_remove", []))
                        }
                    }
                }

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_data).encode(),
                        content_type="application/json"
                    ),
                    routing_key=f"campaign.deletion.completed.{state.get('user_id')}"
                )

                logger.info(f"Published deletion completion for campaign: {state.get('campaign_id')}")

        except Exception as e:
            logger.error(f"Error publishing deletion completion: {e}")

    async def publish_deletion_error(self, request_id: str, user_id: str, error: str):
        """
        Publish deletion error notification

        Args:
            request_id: Request ID
            user_id: User ID
            error: Error message
        """
        try:
            connection = await self._get_connection()

            async with connection:
                channel = await connection.channel()

                message_data = {
                    "request_id": request_id,
                    "workflow_phase": "deletion_error",
                    "error": error
                }

                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(message_data).encode(),
                        content_type="application/json"
                    ),
                    routing_key=f"campaign.deletion.error.{user_id}"
                )

                logger.info(f"Published deletion error notification: {request_id}")

        except Exception as e:
            logger.error(f"Error publishing deletion error: {e}")


# Global message publisher instance
message_publisher = MessagePublisher()
