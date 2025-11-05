"""
Database Connection Manager
Handles MongoDB, Neo4j, and Redis connections
"""
import logging
from typing import Optional
from pymongo import MongoClient
from neo4j import GraphDatabase
from redis.asyncio import Redis

from config import Config
from workflow.utils import set_redis_client

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections for Campaign Factory Service"""

    def __init__(self):
        self.mongo_client: Optional[MongoClient] = None
        self.neo4j_driver: Optional[GraphDatabase.driver] = None
        self.redis_client: Optional[Redis] = None

    async def initialize(self):
        """Initialize all database connections"""
        try:
            await self._init_mongodb()
            await self._init_neo4j()
            await self._init_redis()
            logger.info("All database connections initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database connections: {e}")
            raise

    async def _init_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = MongoClient(Config.MONGODB_URI)
            # Test connection
            self.mongo_client.server_info()
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def _init_neo4j(self):
        """Initialize Neo4j connection"""
        try:
            self.neo4j_driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
            )
            # Test connection
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = Redis.from_url(Config.REDIS_URL, decode_responses=True)
            # Test connection
            await self.redis_client.ping()
            # Set global Redis client for workflow utils
            set_redis_client(self.redis_client)
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        """Close all database connections"""
        try:
            if self.mongo_client:
                self.mongo_client.close()
                logger.info("MongoDB connection closed")

            if self.neo4j_driver:
                self.neo4j_driver.close()
                logger.info("Neo4j connection closed")

            if self.redis_client:
                await self.redis_client.close()
                logger.info("Redis connection closed")

        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

    def get_mongo_db(self, database: str = None):
        """Get MongoDB database instance"""
        if not self.mongo_client:
            raise RuntimeError("MongoDB client not initialized")
        return self.mongo_client[database or Config.MONGODB_DATABASE]

    def get_neo4j_session(self):
        """Get Neo4j session"""
        if not self.neo4j_driver:
            raise RuntimeError("Neo4j driver not initialized")
        return self.neo4j_driver.session()

    def get_redis_client(self) -> Redis:
        """Get Redis client"""
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized")
        return self.redis_client


# Global database manager instance
db_manager = DatabaseManager()
