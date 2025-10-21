"""
Game UI Gateway Service
WebSocket gateway for UI to backend communication
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .api.websocket import router as ws_router
from .managers.connection_manager import ConnectionManager
from .publishers.command_publisher import CommandPublisher
from .consumers.event_consumer import EventConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
connection_manager: ConnectionManager = None
command_publisher: CommandPublisher = None
event_consumer: EventConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global connection_manager, command_publisher, event_consumer
    import asyncio

    # Startup
    logger.info("Starting Game UI Gateway Service...")

    # Initialize connection manager
    connection_manager = ConnectionManager()

    # Get RabbitMQ connection details
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
    rabbitmq_port = os.getenv('RABBITMQ_PORT', '5672')
    rabbitmq_user = os.getenv('RABBITMQ_USER', 'skillforge')
    rabbitmq_pass = os.getenv('RABBITMQ_PASS', os.getenv('RABBITMQ_PASSWORD', 'rabbitmq_dev_pass_2024'))

    connection_string = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

    # Initialize command publisher
    command_publisher = CommandPublisher(connection_string)
    await command_publisher.connect()
    logger.info("✓ Command publisher connected")

    # Initialize event consumer
    event_consumer = EventConsumer(connection_string, connection_manager)
    await event_consumer.connect()
    logger.info("✓ Event consumer connected")

    # Start consuming events in background
    asyncio.create_task(event_consumer.start_consuming())
    logger.info("✓ Event consumer started")

    logger.info("✓ Game UI Gateway Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Game UI Gateway Service...")

    if event_consumer:
        await event_consumer.disconnect()
        logger.info("✓ Event consumer disconnected")

    if command_publisher:
        await command_publisher.disconnect()
        logger.info("✓ Command publisher disconnected")

    logger.info("✓ Game UI Gateway Service shut down")


# Create FastAPI app
app = FastAPI(
    title="Game UI Gateway",
    description="WebSocket gateway for SkillForge game UI",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api_router)
app.include_router(ws_router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', '9600'))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
