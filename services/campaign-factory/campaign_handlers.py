"""
Campaign Request Handlers
Handles campaign generation workflow requests
"""
import json
import logging
import aio_pika

from config import Config
from database import db_manager
from state_manager import state_manager
from message_publisher import message_publisher
from workflow import create_campaign_workflow

logger = logging.getLogger(__name__)

# Initialize campaign workflow
campaign_workflow = create_campaign_workflow()


class CampaignRequestHandler:
    """Handles campaign generation requests from RabbitMQ"""

    async def process_campaign_request(self, message: aio_pika.IncomingMessage):
        """
        Process campaign generation request from RabbitMQ

        Message format:
        {
            "request_id": "uuid",
            "user_id": "user_uuid",
            "character_id": "character_uuid",
            "universe_id": "universe_uuid",
            "universe_name": "Universe Name",
            "world_id": "world_uuid",
            "world_name": "World Name",
            "region_id": "region_uuid",
            "region_name": "Region Name",
            "genre": "fantasy",
            "user_story_idea": "Optional story direction",
            "workflow_action": "start|select_story|approve_core|regenerate_stories|approve_quests|approve_places|finalize",
            "selected_story_id": "story_uuid",
            "user_approved_core": true,
            "num_quests": 5,
            "quest_difficulty": "Medium",
            "quest_playtime_minutes": 90,
            "generate_images": true
        }
        """
        # Manual message acknowledgment to prevent timeout
        # This allows workflows longer than 2 minutes to complete
        await message.ack()

        try:
            # Parse message
            request_data = json.loads(message.body.decode())
            request_id = request_data.get('request_id')
            logger.info(f"Received campaign request: {request_id}")

            # Check if campaign already completed - prevent restart loop
            if request_id:
                redis = db_manager.get_redis_client()
                progress_key = f"campaign:progress:{request_id}"
                progress_data = await redis.get(progress_key)
                if progress_data:
                    progress = json.loads(progress_data)
                    if progress.get("final_campaign_id"):
                        logger.warning(f"Campaign {request_id} already completed with ID {progress['final_campaign_id']} - skipping duplicate request")
                        return

            workflow_action = request_data.get("workflow_action", "start")

            # Route to appropriate handler
            if workflow_action == "start":
                await self._handle_start(request_data)
            elif workflow_action == "select_story":
                await self._handle_select_story(request_data)
            elif workflow_action == "regenerate_stories":
                await self._handle_regenerate_stories(request_data)
            elif workflow_action == "approve_core":
                await self._handle_approve_core(request_data)
            elif workflow_action == "approve_quests":
                await self._handle_approve_quests(request_data)
            elif workflow_action == "approve_places":
                await self._handle_approve_places(request_data)
            elif workflow_action == "finalize":
                await self._handle_finalize(request_data)

            logger.info(f"Campaign request processed: {request_data.get('request_id')}")

        except Exception as e:
            logger.error(f"Error processing campaign request: {e}", exc_info=True)
            # Publish error to user
            await message_publisher.publish_campaign_error(
                request_data.get("request_id", "unknown"),
                request_data.get("user_id", "unknown"),
                str(e)
            )

    async def _handle_start(self, request_data: dict):
        """Handle 'start' workflow action"""
        # Initialize new workflow state
        state = await state_manager.initialize_campaign_state(request_data)

        # Run workflow (will pause at first human-in-the-loop gate)
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Publish story ideas to user for selection
        await message_publisher.publish_story_ideas(result_state)

    async def _handle_select_story(self, request_data: dict):
        """Handle 'select_story' workflow action"""
        # Resume workflow with user's story selection
        state = await state_manager.load_campaign_state(request_data["request_id"])
        state["selected_story_id"] = request_data["selected_story_id"]

        # Continue workflow
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Publish campaign core to user for approval
        await message_publisher.publish_campaign_core(result_state)

    async def _handle_regenerate_stories(self, request_data: dict):
        """Handle 'regenerate_stories' workflow action"""
        # Resume workflow to regenerate stories
        state = await state_manager.load_campaign_state(request_data["request_id"])
        state["regenerate_stories"] = True

        # Continue workflow
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Publish new story ideas
        await message_publisher.publish_story_ideas(result_state)

    async def _handle_approve_core(self, request_data: dict):
        """Handle 'approve_core' workflow action"""
        # Resume workflow with user's core approval
        state = await state_manager.load_campaign_state(request_data["request_id"])
        state["user_approved_core"] = request_data["user_approved_core"]
        state["num_quests"] = request_data.get("num_quests", 5)
        state["quest_difficulty"] = request_data.get("quest_difficulty", "Medium")
        state["quest_playtime_minutes"] = request_data.get("quest_playtime_minutes", 90)
        state["generate_images"] = request_data.get("generate_images", True)

        # Continue workflow (will run to completion)
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Publish final campaign result
        await message_publisher.publish_campaign_completion(result_state)

    async def _handle_approve_quests(self, request_data: dict):
        """Handle 'approve_quests' workflow action"""
        # Resume workflow with quest approval
        state = await state_manager.load_campaign_state(request_data["request_id"])
        state["user_approved_quests"] = request_data.get("user_approved_quests", True)

        # Continue workflow
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Save updated state
        await state_manager.save_campaign_state(result_state)

    async def _handle_approve_places(self, request_data: dict):
        """Handle 'approve_places' workflow action"""
        # Resume workflow with place approval
        state = await state_manager.load_campaign_state(request_data["request_id"])
        state["user_approved_places"] = request_data.get("user_approved_places", True)

        # Continue workflow
        result_state = await campaign_workflow.ainvoke(
            state,
            {"recursion_limit": Config.WORKFLOW_RECURSION_LIMIT}
        )

        # Save updated state
        await state_manager.save_campaign_state(result_state)

    async def _handle_finalize(self, request_data: dict):
        """Handle 'finalize' workflow action - manually trigger finalization"""
        # Manually trigger finalization
        state = await state_manager.load_campaign_state(request_data["request_id"])

        # Import finalization node
        from workflow.nodes_finalize import finalize_campaign_node

        # Run finalization
        result_state = await finalize_campaign_node(state)

        # Save updated state
        await state_manager.save_campaign_state(result_state)

        # Publish completion
        await message_publisher.publish_campaign_completion(result_state)


# Global campaign request handler instance
campaign_request_handler = CampaignRequestHandler()
