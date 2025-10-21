"""
Game Event Manager Service
Central event processing hub for SkillForge games
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .services.rabbitmq_service import RabbitMQService
from .handlers.event_handler import (
    SessionEventHandler,
    PlayerEventHandler,
    QuestEventHandler,
    DiscoveryEventHandler,
    ConversationEventHandler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global RabbitMQ service instance
rabbitmq_service: RabbitMQService = None


async def process_game_event(event: dict):
    """Process a game event from the queue"""
    try:
        event_type = event.get('event_type', '')

        # Route to appropriate handler
        if event_type.startswith('session.'):
            handler = SessionEventHandler(rabbitmq_service)
            await handler.handle(event)
        elif event_type.startswith('player.'):
            handler = PlayerEventHandler(rabbitmq_service)
            await handler.handle(event)
        elif event_type.startswith('quest.'):
            handler = QuestEventHandler(rabbitmq_service)
            await handler.handle(event)
        elif event_type == 'discovery.found':
            handler = DiscoveryEventHandler(rabbitmq_service)
            await handler.handle(event)
        elif event_type == 'conversation.message':
            handler = ConversationEventHandler(rabbitmq_service)
            await handler.handle(event)

    except Exception as e:
        logger.error(f"Error processing event: {e}")


async def start_event_consumers():
    """Start consuming events from RabbitMQ queues"""
    try:
        # Note: In a production environment, you might want to run these in separate processes
        # For now, we'll just log that the service is ready to consume
        logger.info("Event Manager is ready to process events")

        # If you want to actively consume from a specific queue, uncomment:
        # await rabbitmq_service.consume_queue(
        #     'game.orchestrator.queue',
        #     process_game_event
        # )

    except Exception as e:
        logger.error(f"Error starting event consumers: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global rabbitmq_service

    # Startup
    logger.info("Starting Game Event Manager Service...")

    # Get RabbitMQ connection string from environment
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = os.getenv('RABBITMQ_PORT', '5672')
    rabbitmq_user = os.getenv('RABBITMQ_USER', 'admin')
    rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'admin')

    connection_string = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

    # Initialize RabbitMQ service
    rabbitmq_service = RabbitMQService(connection_string)
    await rabbitmq_service.connect()

    # Start event consumers
    asyncio.create_task(start_event_consumers())

    logger.info("✓ Game Event Manager Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Game Event Manager Service...")
    await rabbitmq_service.disconnect()
    logger.info("✓ Game Event Manager Service shut down")


# Create FastAPI app
app = FastAPI(
    title="Game Event Manager",
    description="Central event processing hub for SkillForge games",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', '9501'))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
