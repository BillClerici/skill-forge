"""
Campaign Factory Service Configuration
Centralized configuration and environment variables
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for Campaign Factory Service"""

    # RabbitMQ Configuration
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = os.getenv('RABBITMQ_PORT', '5672')

    # RabbitMQ Timeout Configuration (30 minutes for long-running workflows)
    RABBITMQ_MESSAGE_TIMEOUT = int(os.getenv('RABBITMQ_MESSAGE_TIMEOUT', '1800'))  # 30 minutes in seconds

    # Queue names
    CAMPAIGN_GENERATION_QUEUE = 'campaign_generation_queue'
    CAMPAIGN_DELETION_QUEUE = 'campaign_deletion_queue'

    # Database Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DATABASE = 'skillforge'

    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    REDIS_STATE_EXPIRY = 86400  # 24 hours

    # Workflow Configuration
    WORKFLOW_RECURSION_LIMIT = 100
    MAX_RETRIES = 3

    @classmethod
    def get_rabbitmq_url(cls) -> str:
        """Get formatted RabbitMQ connection URL"""
        return f"amqp://{cls.RABBITMQ_USER}:{cls.RABBITMQ_PASS}@{cls.RABBITMQ_HOST}:{cls.RABBITMQ_PORT}/"

    @classmethod
    def get_redis_key_prefixes(cls) -> dict:
        """Get Redis key prefixes for different data types"""
        return {
            'state': 'campaign:state:',
            'progress': 'campaign:progress:',
            'deletion_state': 'campaign:deletion:state:',
            'deletion_progress': 'campaign:deletion:progress:'
        }
