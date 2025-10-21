"""
Game Persistence Service
Handles all MongoDB read/write operations for SkillForge games
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import aio_pika

from .api.routes import router
from .repositories.session_repository import SessionRepository
from .repositories.event_repository import EventRepository
from .repositories.conversation_repository import ConversationRepository
from .repositories.inventory_repository import InventoryRepository
from .consumers.persistence_consumer import PersistenceConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
mongo_client: AsyncIOMotorClient = None
rabbitmq_connection = None
rabbitmq_channel = None
session_repository = None
event_repository = None
conversation_repository = None
inventory_repository = None
persistence_consumer = None


async def start_rabbitmq_consumer():
    """Start consuming events from RabbitMQ"""
    global rabbitmq_connection, rabbitmq_channel, persistence_consumer

    try:
        # Get RabbitMQ connection details
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        rabbitmq_port = os.getenv('RABBITMQ_PORT', '5672')
        rabbitmq_user = os.getenv('RABBITMQ_USER', 'admin')
        rabbitmq_pass = os.getenv('RABBITMQ_PASS', 'admin')

        connection_string = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

        # Connect to RabbitMQ
        rabbitmq_connection = await aio_pika.connect_robust(connection_string)
        rabbitmq_channel = await rabbitmq_connection.channel()

        # Set QoS
        await rabbitmq_channel.set_qos(prefetch_count=10)

        # Get the queue (it should already exist from init)
        queue = await rabbitmq_channel.get_queue(
            'game.persistence.queue',
            ensure=False
        )

        logger.info("✓ Connected to RabbitMQ, starting to consume events...")

        # Consume messages
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        import json
                        event = json.loads(message.body.decode())

                        # Process event
                        await persistence_consumer.process_event(event)

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

    except Exception as e:
        logger.error(f"Error in RabbitMQ consumer: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global mongo_client, session_repository, event_repository
    global conversation_repository, inventory_repository, persistence_consumer

    # Startup
    logger.info("Starting Game Persistence Service...")

    # Get MongoDB connection details
    mongo_host = os.getenv('MONGODB_HOST', 'localhost')
    mongo_port = os.getenv('MONGODB_PORT', '27017')
    mongo_user = os.getenv('MONGODB_USERNAME', 'admin')
    mongo_pass = os.getenv('MONGODB_PASSWORD', 'admin')
    mongo_db = os.getenv('MONGODB_DATABASE', 'skillforge')

    connection_string = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:{mongo_port}/"

    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(connection_string)
    db = mongo_client[mongo_db]

    # Initialize repositories
    session_repository = SessionRepository(db)
    event_repository = EventRepository(db)
    conversation_repository = ConversationRepository(db)
    inventory_repository = InventoryRepository(db)

    logger.info("✓ Connected to MongoDB")

    # Initialize persistence consumer
    persistence_consumer = PersistenceConsumer(
        session_repository,
        event_repository,
        conversation_repository,
        inventory_repository
    )

    # Start RabbitMQ consumer in background
    asyncio.create_task(start_rabbitmq_consumer())

    logger.info("✓ Game Persistence Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Game Persistence Service...")

    if rabbitmq_connection:
        await rabbitmq_connection.close()

    if mongo_client:
        mongo_client.close()

    logger.info("✓ Game Persistence Service shut down")


# Create FastAPI app
app = FastAPI(
    title="Game Persistence Service",
    description="Persistence layer for SkillForge game data",
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
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', '9502'))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
