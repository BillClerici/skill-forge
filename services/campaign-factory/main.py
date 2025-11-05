"""
Campaign Factory Service - RabbitMQ Consumer
Orchestrates campaign generation using LangGraph workflow

Refactored for better maintainability and separation of concerns
"""
import sys
import asyncio
import logging
import aio_pika

from config import Config
from database import db_manager
from state_manager import state_manager
from campaign_handlers import campaign_request_handler
from deletion_handlers import deletion_request_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Main entry point - Start RabbitMQ consumer for both generation and deletion
    """
    logger.info("Starting Campaign Factory service...")

    try:
        # Initialize database connections
        await db_manager.initialize()

        # Set Redis client for state manager
        state_manager.set_redis_client(db_manager.get_redis_client())

        # Connect to RabbitMQ with robust connection
        connection = await aio_pika.connect_robust(
            Config.get_rabbitmq_url(),
            timeout=Config.RABBITMQ_MESSAGE_TIMEOUT
        )

        async with connection:
            # Create channel
            channel = await connection.channel()

            # Set QoS - process one message at a time
            await channel.set_qos(prefetch_count=1)

            # Declare campaign generation queue
            generation_queue = await channel.declare_queue(
                Config.CAMPAIGN_GENERATION_QUEUE,
                durable=True
            )

            # Declare campaign deletion queue
            deletion_queue = await channel.declare_queue(
                Config.CAMPAIGN_DELETION_QUEUE,
                durable=True
            )

            logger.info(f"Campaign Factory service ready. Waiting for campaign requests...")
            logger.info(f"RabbitMQ timeout configured: {Config.RABBITMQ_MESSAGE_TIMEOUT} seconds")

            # Start consuming from both queues
            # Note: Using manual acknowledgment in handlers to prevent 2-minute timeout
            await generation_queue.consume(campaign_request_handler.process_campaign_request)
            await deletion_queue.consume(deletion_request_handler.process_deletion_request)

            logger.info(f"Listening on queues: {Config.CAMPAIGN_GENERATION_QUEUE}, {Config.CAMPAIGN_DELETION_QUEUE}")

            # Keep running
            try:
                await asyncio.Future()
            except KeyboardInterrupt:
                logger.info("Shutting down Campaign Factory service...")

    except Exception as e:
        logger.error(f"Fatal error in Campaign Factory service: {e}", exc_info=True)
        raise

    finally:
        # Cleanup database connections
        await db_manager.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Campaign Factory service stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Campaign Factory service crashed: {e}", exc_info=True)
        sys.exit(1)
