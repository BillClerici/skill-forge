"""
World Factory Service
Uses LangGraph to orchestrate multi-step world generation with retry logic and audit trails
"""
import os
import sys
import json
import logging
import asyncio
import pika
from pymongo import MongoClient
from redis import Redis
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://skillforge:rabbitmq_pass@rabbitmq:5672')
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Database connections
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

# Import workflow
from workflow.world_factory_workflow import create_world_factory_workflow, WorldFactoryState


class WorldFactoryService:
    """Main service for consuming world factory jobs from RabbitMQ"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self.workflow_graph = create_world_factory_workflow()

    def connect_rabbitmq(self):
        """Connect to RabbitMQ and set up queues"""
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare queue for world factory jobs
            self.channel.queue_declare(
                queue='world_factory_jobs',
                durable=True,
                arguments={
                    'x-message-ttl': 3600000,  # 1 hour TTL
                    'x-dead-letter-exchange': 'world_factory_dlx'
                }
            )

            # Declare dead letter queue
            self.channel.exchange_declare(
                exchange='world_factory_dlx',
                exchange_type='direct',
                durable=True
            )
            self.channel.queue_declare(queue='world_factory_failed', durable=True)
            self.channel.queue_bind(
                queue='world_factory_failed',
                exchange='world_factory_dlx',
                routing_key='world_factory_jobs'
            )

            # Declare progress events exchange
            self.channel.exchange_declare(
                exchange='world_factory_progress',
                exchange_type='fanout',
                durable=True
            )

            logger.info("Connected to RabbitMQ and queues declared")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def callback(self, ch, method, properties, body):
        """Process world factory job"""
        try:
            job_data = json.loads(body)
            workflow_id = job_data.get('workflow_id')
            genre = job_data.get('genre')
            user_id = job_data.get('user_id')
            generate_images = job_data.get('generate_images', True)  # Default to True

            logger.info(f"Processing world factory job: {workflow_id} for genre: {genre} (Images: {'enabled' if generate_images else 'disabled'})")

            # Check if this workflow is already running or completed to prevent duplicates
            from datetime import datetime
            existing_workflow = db.world_factory_state.find_one({'workflow_id': workflow_id})

            if existing_workflow:
                status = existing_workflow.get('status')
                if status in ['running', 'completed']:
                    logger.warning(f"Workflow {workflow_id} is already {status}, skipping duplicate processing")
                    # Acknowledge message immediately to prevent reprocessing
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return

            # Create initial state
            initial_state = WorldFactoryState(
                workflow_id=workflow_id,
                genre=genre,
                user_id=user_id,
                generate_images=generate_images,
                current_step="start",
                world_id=None,
                region_ids=[],
                location_ids=[],
                species_ids=[],
                errors=[],
                retry_count=0,
                audit_trail=[]
            )

            # Store initial workflow state in MongoDB
            if not existing_workflow:
                db.world_factory_state.insert_one({
                    'workflow_id': workflow_id,
                    'user_id': user_id,
                    'genre': genre,
                    'generate_images': generate_images,
                    'status': 'running',
                    'current_step': 'start',
                    'world_id': None,
                    'region_ids': [],
                    'location_ids': [],
                    'species_ids': [],
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                })
            else:
                # Update existing failed workflow to running
                db.world_factory_state.update_one(
                    {'workflow_id': workflow_id},
                    {
                        '$set': {
                            'status': 'running',
                            'current_step': 'start',
                            'updated_at': datetime.utcnow()
                        }
                    }
                )

            # CRITICAL: Acknowledge message BEFORE running workflow to prevent requeue
            ch.basic_ack(delivery_tag=method.delivery_tag)

            # Run workflow (this can take 10-20 minutes)
            asyncio.run(self.run_workflow(initial_state))

        except Exception as e:
            logger.error(f"Error processing job: {e}", exc_info=True)
            # Acknowledge the message even on error - workflow state is already tracked in MongoDB
            ch.basic_ack(delivery_tag=method.delivery_tag)

    async def run_workflow(self, initial_state: WorldFactoryState):
        """Execute the LangGraph workflow"""
        try:
            from datetime import datetime

            # Convert Pydantic model to dict for LangGraph
            state_dict = initial_state.model_dump()

            # Run the workflow
            final_state = await self.workflow_graph.ainvoke(state_dict)

            logger.info(f"Workflow completed: {final_state['workflow_id']}")

            # Update workflow state in MongoDB
            workflow_status = 'completed' if not final_state.get('errors') else 'failed'
            db.world_factory_state.update_one(
                {'workflow_id': final_state['workflow_id']},
                {
                    '$set': {
                        'status': workflow_status,
                        'world_id': final_state.get('world_id'),
                        'region_ids': final_state.get('region_ids', []),
                        'location_ids': final_state.get('location_ids', []),
                        'species_ids': final_state.get('species_ids', []),
                        'updated_at': datetime.utcnow(),
                        'completed_at': datetime.utcnow()
                    }
                }
            )

            # Publish completion event
            self.publish_progress_event({
                'workflow_id': final_state['workflow_id'],
                'status': workflow_status,
                'world_id': final_state.get('world_id'),
                'errors': final_state.get('errors', []),
                'audit_trail': [entry.dict() if hasattr(entry, 'dict') else entry for entry in final_state.get('audit_trail', [])]
            })

        except Exception as e:
            logger.error(f"Workflow error: {e}", exc_info=True)

            # Update workflow state to failed
            from datetime import datetime
            db.world_factory_state.update_one(
                {'workflow_id': initial_state.workflow_id},
                {
                    '$set': {
                        'status': 'failed',
                        'error': str(e),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            self.publish_progress_event({
                'workflow_id': initial_state.workflow_id,
                'status': 'failed',
                'error': str(e)
            })

    def publish_progress_event(self, event_data: dict):
        """Publish progress event to RabbitMQ"""
        try:
            # Create a separate connection for publishing to avoid channel conflicts
            parameters = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.basic_publish(
                exchange='world_factory_progress',
                routing_key='',
                body=json.dumps(event_data),
                properties=pika.BasicProperties(delivery_mode=2)
            )

            connection.close()
        except Exception as e:
            logger.error(f"Failed to publish progress event: {e}")

    def start_consuming(self):
        """Start consuming messages from RabbitMQ"""
        try:
            self.channel.basic_qos(prefetch_count=1)  # Process one job at a time
            self.channel.basic_consume(
                queue='world_factory_jobs',
                on_message_callback=self.callback
            )

            logger.info("Waiting for world factory jobs...")
            self.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()


if __name__ == "__main__":
    service = WorldFactoryService()
    service.connect_rabbitmq()
    service.start_consuming()
