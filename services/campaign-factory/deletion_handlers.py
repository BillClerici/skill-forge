"""
Campaign Deletion Request Handlers
Handles campaign deletion workflow requests
"""
import json
import logging
import uuid
import aio_pika

from config import Config
from state_manager import state_manager
from message_publisher import message_publisher
from workflow.campaign_deletion_workflow import create_campaign_deletion_workflow, CampaignDeletionState

logger = logging.getLogger(__name__)

# Initialize deletion workflow
deletion_workflow = create_campaign_deletion_workflow()


class CampaignDeletionHandler:
    """Handles campaign deletion requests from RabbitMQ"""

    async def process_deletion_request(self, message: aio_pika.IncomingMessage):
        """
        Process campaign deletion request from RabbitMQ

        Message format:
        {
            "request_id": "uuid",
            "campaign_id": "campaign_uuid",
            "user_id": "user_uuid"
        }
        """
        # Manual message acknowledgment to prevent timeout
        await message.ack()

        try:
            # Parse message
            request_data = json.loads(message.body.decode())
            request_id = request_data.get('request_id', str(uuid.uuid4()))
            campaign_id = request_data.get('campaign_id')
            user_id = request_data.get('user_id')

            logger.info(f"Received campaign deletion request: {request_id} for campaign: {campaign_id}")

            if not campaign_id:
                error_msg = "campaign_id is required"
                logger.error(error_msg)
                await message_publisher.publish_deletion_error(request_id, user_id, error_msg)
                return

            # Initialize deletion state
            state = self._initialize_deletion_state(request_id, campaign_id, user_id)

            # Save initial state to Redis
            await state_manager.save_deletion_state(state)

            # Publish initial progress
            await message_publisher.publish_deletion_progress(state)

            # Run deletion workflow
            result_state = await self._run_deletion_with_progress(state)

            # Publish completion
            await message_publisher.publish_deletion_completion(result_state)

            logger.info(f"Campaign deletion completed: {campaign_id}")

        except Exception as e:
            logger.error(f"Error processing campaign deletion request: {e}", exc_info=True)
            await message_publisher.publish_deletion_error(
                request_data.get("request_id", "unknown"),
                request_data.get("user_id", "unknown"),
                str(e)
            )

    def _initialize_deletion_state(
        self,
        request_id: str,
        campaign_id: str,
        user_id: str
    ) -> CampaignDeletionState:
        """
        Initialize deletion workflow state

        Args:
            request_id: Request ID
            campaign_id: Campaign ID to delete
            user_id: User ID

        Returns:
            Initialized CampaignDeletionState
        """
        return {
            "request_id": request_id,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "campaign_name": "",
            "is_new_format": False,
            "world_id": "",

            # Deletion tracking
            "deleted_quests": [],
            "deleted_places": [],
            "deleted_scenes": [],
            "deleted_npcs": [],
            "deleted_discoveries": [],
            "deleted_events": [],
            "deleted_challenges": [],
            "deleted_knowledge": [],
            "deleted_items": [],
            "deleted_rubrics": [],

            # Species and Location cleanup
            "campaign_created_species": [],
            "campaign_created_locations": [],
            "species_to_remove": [],
            "locations_to_remove": [],
            "species_dependencies": {},
            "location_dependencies": {},

            # Status tracking
            "mongodb_deleted": False,
            "neo4j_deleted": False,
            "postgres_deleted": False,
            "species_cleaned": False,
            "locations_cleaned": False,

            # Error tracking
            "errors": [],
            "warnings": [],

            # Progress tracking
            "current_phase": "init",
            "progress_percentage": 0,
            "step_progress": 0,
            "status_message": "Initializing campaign deletion...",

            # Audit
            "deleted_at": "",
            "deletion_log": []
        }

    async def _run_deletion_with_progress(self, state: CampaignDeletionState) -> CampaignDeletionState:
        """
        Run deletion workflow with progress updates published to RabbitMQ

        Args:
            state: Initial deletion state

        Returns:
            Final deletion state
        """
        try:
            # Stream the workflow and publish progress after each node
            async for event in deletion_workflow.astream(state):
                # event is a dict with node names as keys
                for node_name, node_state in event.items():
                    logger.info(f"Deletion workflow - Completed node: {node_name}")

                    # Update state
                    state.update(node_state)

                    # Save state to Redis
                    await state_manager.save_deletion_state(state)

                    # Publish progress update
                    await message_publisher.publish_deletion_progress(state)

            return state

        except Exception as e:
            logger.error(f"Error in deletion workflow: {e}", exc_info=True)
            state['errors'] = state.get('errors', []) + [str(e)]
            await state_manager.save_deletion_state(state)
            await message_publisher.publish_deletion_progress(state)
            return state


# Global deletion request handler instance
deletion_request_handler = CampaignDeletionHandler()
