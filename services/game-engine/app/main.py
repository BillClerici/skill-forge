"""
Game Engine FastAPI Application
Main entry point for the game engine service
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.logging import setup_logging, get_logger
from .services.redis_manager import redis_manager
from .services.rabbitmq_client import rabbitmq_client
from .services.rabbitmq_consumer import rabbitmq_consumer
from .services.mongo_persistence import mongo_persistence
from .services.neo4j_graph import neo4j_graph
from .api.routes import router

# Setup logging
setup_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info(
        "game_engine_starting",
        service_name=settings.SERVICE_NAME,
        environment=settings.ENVIRONMENT
    )

    try:
        # Connect to Redis
        await redis_manager.connect()
        logger.info("redis_connected")

        # Connect to RabbitMQ
        await rabbitmq_client.connect()
        logger.info("rabbitmq_connected")

        # Connect to MongoDB
        await mongo_persistence.connect()
        logger.info("mongodb_connected")

        # Connect to Neo4j
        await neo4j_graph.connect()
        logger.info("neo4j_connected")

        # Connect RabbitMQ consumer and start consuming
        await rabbitmq_consumer.connect()
        logger.info("rabbitmq_consumer_connected")

        # Start consuming player actions in background
        import asyncio
        asyncio.create_task(rabbitmq_consumer.start_consuming())
        logger.info("rabbitmq_consumer_started")

        logger.info("game_engine_started_successfully")

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("game_engine_shutting_down")

    try:
        # Disconnect from Redis
        await redis_manager.disconnect()
        logger.info("redis_disconnected")

        # Disconnect from RabbitMQ consumer
        await rabbitmq_consumer.disconnect()
        logger.info("rabbitmq_consumer_disconnected")

        # Disconnect from RabbitMQ publisher
        await rabbitmq_client.disconnect()
        logger.info("rabbitmq_disconnected")

        # Disconnect from MongoDB
        await mongo_persistence.disconnect()
        logger.info("mongodb_disconnected")

        # Disconnect from Neo4j
        await neo4j_graph.disconnect()
        logger.info("neo4j_disconnected")

        logger.info("game_engine_shutdown_complete")

    except Exception as e:
        logger.error("shutdown_failed", error=str(e))


# Create FastAPI application
app = FastAPI(
    title="SkillForge Game Engine",
    description="AI-powered game engine using LangGraph and Claude",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow all origins for development (including WebSockets)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1", tags=["game-engine"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "SkillForge Game Engine",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_healthy = redis_manager.redis is not None

        # Check RabbitMQ connection
        rabbitmq_healthy = rabbitmq_client.connection is not None

        # Check MongoDB connection
        mongodb_healthy = mongo_persistence.client is not None

        # Check Neo4j connection
        neo4j_healthy = neo4j_graph.driver is not None

        overall_healthy = redis_healthy and rabbitmq_healthy and mongodb_healthy and neo4j_healthy

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "redis": "connected" if redis_healthy else "disconnected",
            "rabbitmq": "connected" if rabbitmq_healthy else "disconnected",
            "mongodb": "connected" if mongodb_healthy else "disconnected",
            "neo4j": "connected" if neo4j_healthy else "disconnected"
        }

    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9500,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
