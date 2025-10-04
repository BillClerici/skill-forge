"""
Background Worker Service
Consumes events from RabbitMQ and processes them asynchronously
"""
import os
import sys
import json
import time
import logging
import pika
from pymongo import MongoClient
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://skillforge:rabbitmq_pass@rabbitmq:5672')
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_dev_pass_2024')

# Database connections
mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ============================================
# Neo4j Sync Handlers (with retry logic)
# ============================================

def sync_species_to_neo4j(entity_id, entity_data, action, max_retries=3):
    """Sync species to Neo4j with retry logic"""
    for attempt in range(max_retries):
        try:
            with neo4j_driver.session() as session:
                if action == 'created':
                    # Create Species node and relationships
                    session.run("""
                        MATCH (w:World {id: $world_id})
                        MERGE (s:Species {id: $species_id})
                        ON CREATE SET s.name = $species_name,
                                     s.type = $species_type,
                                     s.category = $category
                        MERGE (s)-[:IN_WORLD]->(w)
                    """, world_id=entity_data.get('world_id'),
                       species_id=entity_id,
                       species_name=entity_data.get('species_name', ''),
                       species_type=entity_data.get('species_type', ''),
                       category=entity_data.get('category', ''))

                    # Link to regions
                    for region_id in entity_data.get('regions', []):
                        session.run("""
                            MATCH (s:Species {id: $species_id})
                            MATCH (r:Region {id: $region_id})
                            MERGE (s)-[:INHABITS]->(r)
                        """, species_id=entity_id, region_id=region_id)

                    logger.info(f"Created Species in Neo4j: {entity_id}")

                elif action == 'updated':
                    # Update Species node
                    session.run("""
                        MATCH (s:Species {id: $species_id})
                        SET s.name = $species_name,
                            s.type = $species_type,
                            s.category = $category
                    """, species_id=entity_id,
                       species_name=entity_data.get('species_name', ''),
                       species_type=entity_data.get('species_type', ''),
                       category=entity_data.get('category', ''))

                    # Update region relationships
                    session.run("""
                        MATCH (s:Species {id: $species_id})-[r:INHABITS]->()
                        DELETE r
                    """, species_id=entity_id)

                    for region_id in entity_data.get('regions', []):
                        session.run("""
                            MATCH (s:Species {id: $species_id})
                            MATCH (r:Region {id: $region_id})
                            MERGE (s)-[:INHABITS]->(r)
                        """, species_id=entity_id, region_id=region_id)

                    logger.info(f"Updated Species in Neo4j: {entity_id}")

                elif action == 'deleted':
                    # Delete Species node
                    session.run("""
                        MATCH (s:Species {id: $species_id})
                        DETACH DELETE s
                    """, species_id=entity_id)

                    logger.info(f"Deleted Species from Neo4j: {entity_id}")

            return True  # Success

        except Exception as e:
            logger.error(f"Neo4j sync attempt {attempt + 1}/{max_retries} failed for Species {entity_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to sync Species {entity_id} to Neo4j after {max_retries} attempts")
                return False


def sync_universe_to_neo4j(entity_id, entity_data, action, max_retries=3):
    """Sync universe to Neo4j with retry logic"""
    for attempt in range(max_retries):
        try:
            with neo4j_driver.session() as session:
                if action == 'created':
                    session.run("""
                        CREATE (u:Universe {
                            id: $universe_id,
                            name: $universe_name,
                            content_rating: $content_rating
                        })
                    """, universe_id=entity_id,
                       universe_name=entity_data.get('universe_name', ''),
                       content_rating=entity_data.get('max_content_rating', 'PG'))
                    logger.info(f"Created Universe in Neo4j: {entity_id}")

                elif action == 'updated':
                    session.run("""
                        MATCH (u:Universe {id: $universe_id})
                        SET u.name = $universe_name,
                            u.content_rating = $content_rating
                    """, universe_id=entity_id,
                       universe_name=entity_data.get('universe_name', ''),
                       content_rating=entity_data.get('max_content_rating', 'PG'))
                    logger.info(f"Updated Universe in Neo4j: {entity_id}")

                elif action == 'deleted':
                    session.run("""
                        MATCH (u:Universe {id: $universe_id})
                        DETACH DELETE u
                    """, universe_id=entity_id)
                    logger.info(f"Deleted Universe from Neo4j: {entity_id}")

            return True

        except Exception as e:
            logger.error(f"Neo4j sync attempt {attempt + 1}/{max_retries} failed for Universe {entity_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to sync Universe {entity_id} to Neo4j after {max_retries} attempts")
                return False


def sync_world_to_neo4j(entity_id, entity_data, action, max_retries=3):
    """Sync world to Neo4j with retry logic"""
    for attempt in range(max_retries):
        try:
            with neo4j_driver.session() as session:
                if action == 'created':
                    for universe_id in entity_data.get('universe_ids', []):
                        session.run("""
                            MATCH (u:Universe {id: $universe_id})
                            MERGE (w:World {id: $world_id})
                            ON CREATE SET w.name = $world_name, w.genre = $genre
                            MERGE (w)-[:IN_UNIVERSE]->(u)
                        """, universe_id=universe_id,
                           world_id=entity_id,
                           world_name=entity_data.get('world_name', ''),
                           genre=entity_data.get('genre', ''))
                    logger.info(f"Created World in Neo4j: {entity_id}")

                elif action == 'updated':
                    session.run("""
                        MATCH (w:World {id: $world_id})
                        SET w.name = $world_name,
                            w.genre = $genre
                    """, world_id=entity_id,
                       world_name=entity_data.get('world_name', ''),
                       genre=entity_data.get('genre', ''))

                    # Update universe relationships
                    session.run("""
                        MATCH (w:World {id: $world_id})
                        OPTIONAL MATCH (w)-[r:IN_UNIVERSE]->()
                        DELETE r
                    """, world_id=entity_id)

                    for universe_id in entity_data.get('universe_ids', []):
                        session.run("""
                            MATCH (w:World {id: $world_id})
                            MATCH (u:Universe {id: $universe_id})
                            MERGE (w)-[:IN_UNIVERSE]->(u)
                        """, world_id=entity_id, universe_id=universe_id)

                    logger.info(f"Updated World in Neo4j: {entity_id}")

                elif action == 'deleted':
                    session.run("""
                        MATCH (w:World {id: $world_id})
                        DETACH DELETE w
                    """, world_id=entity_id)
                    logger.info(f"Deleted World from Neo4j: {entity_id}")

            return True

        except Exception as e:
            logger.error(f"Neo4j sync attempt {attempt + 1}/{max_retries} failed for World {entity_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to sync World {entity_id} to Neo4j after {max_retries} attempts")
                return False


def sync_region_to_neo4j(entity_id, entity_data, action, max_retries=3):
    """Sync region to Neo4j with retry logic"""
    for attempt in range(max_retries):
        try:
            with neo4j_driver.session() as session:
                if action == 'created':
                    session.run("""
                        MATCH (w:World {id: $world_id})
                        MERGE (r:Region {id: $region_id})
                        ON CREATE SET r.name = $region_name,
                                     r.type = $region_type,
                                     r.climate = $climate
                        MERGE (r)-[:IN_WORLD]->(w)
                    """, world_id=entity_data.get('world_id'),
                       region_id=entity_id,
                       region_name=entity_data.get('region_name', ''),
                       region_type=entity_data.get('region_type', ''),
                       climate=entity_data.get('climate', ''))
                    logger.info(f"Created Region in Neo4j: {entity_id}")

                elif action == 'updated':
                    session.run("""
                        MATCH (r:Region {id: $region_id})
                        SET r.name = $region_name,
                            r.type = $region_type,
                            r.climate = $climate
                    """, region_id=entity_id,
                       region_name=entity_data.get('region_name', ''),
                       region_type=entity_data.get('region_type', ''),
                       climate=entity_data.get('climate', ''))
                    logger.info(f"Updated Region in Neo4j: {entity_id}")

                elif action == 'deleted':
                    session.run("""
                        MATCH (r:Region {id: $region_id})
                        DETACH DELETE r
                    """, region_id=entity_id)
                    logger.info(f"Deleted Region from Neo4j: {entity_id}")

            return True

        except Exception as e:
            logger.error(f"Neo4j sync attempt {attempt + 1}/{max_retries} failed for Region {entity_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to sync Region {entity_id} to Neo4j after {max_retries} attempts")
                return False


def sync_location_to_neo4j(entity_id, entity_data, action, max_retries=3):
    """Sync location to Neo4j with retry logic"""
    for attempt in range(max_retries):
        try:
            with neo4j_driver.session() as session:
                if action == 'created':
                    session.run("""
                        MATCH (r:Region {id: $region_id})
                        MERGE (l:Location {id: $location_id})
                        ON CREATE SET l.name = $location_name,
                                     l.type = $location_type
                        MERGE (l)-[:IN_REGION]->(r)
                    """, region_id=entity_data.get('region_id'),
                       location_id=entity_id,
                       location_name=entity_data.get('location_name', ''),
                       location_type=entity_data.get('location_type', ''))
                    logger.info(f"Created Location in Neo4j: {entity_id}")

                elif action == 'updated':
                    session.run("""
                        MATCH (l:Location {id: $location_id})
                        SET l.name = $location_name,
                            l.type = $location_type
                    """, location_id=entity_id,
                       location_name=entity_data.get('location_name', ''),
                       location_type=entity_data.get('location_type', ''))
                    logger.info(f"Updated Location in Neo4j: {entity_id}")

                elif action == 'deleted':
                    session.run("""
                        MATCH (l:Location {id: $location_id})
                        DETACH DELETE l
                    """, location_id=entity_id)
                    logger.info(f"Deleted Location from Neo4j: {entity_id}")

            return True

        except Exception as e:
            logger.error(f"Neo4j sync attempt {attempt + 1}/{max_retries} failed for Location {entity_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to sync Location {entity_id} to Neo4j after {max_retries} attempts")
                return False


# ============================================
# Event Handlers
# ============================================

def handle_entity_event(ch, method, properties, body):
    """Handle entity lifecycle events"""
    try:
        event = json.loads(body)
        entity_type = event.get('entity_type')
        action = event.get('action')
        entity_id = event.get('entity_id')
        entity_data = event.get('data', {})

        logger.info(f"Processing {action} event for {entity_type}: {entity_id}")

        # Route to appropriate handler
        if entity_type == 'universe':
            success = sync_universe_to_neo4j(entity_id, entity_data, action)
        elif entity_type == 'species':
            success = sync_species_to_neo4j(entity_id, entity_data, action)
        elif entity_type == 'world':
            success = sync_world_to_neo4j(entity_id, entity_data, action)
        elif entity_type == 'region':
            success = sync_region_to_neo4j(entity_id, entity_data, action)
        elif entity_type == 'location':
            success = sync_location_to_neo4j(entity_id, entity_data, action)
        else:
            logger.warning(f"Unknown entity type: {entity_type}")
            success = True  # Ack anyway

        if success:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Reject and requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except Exception as e:
        logger.error(f"Error processing entity event: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def handle_ai_task(ch, method, properties, body):
    """Handle AI generation tasks"""
    try:
        task = json.loads(body)
        logger.info(f"Processing AI task: {task}")

        # TODO: Implement AI task handlers
        # For now, just acknowledge
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Error processing AI task: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# ============================================
# Worker Main Loop
# ============================================

def start_worker():
    """Start the background worker"""
    logger.info("Starting Background Worker...")

    while True:
        try:
            # Connect to RabbitMQ
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Declare exchange
            channel.exchange_declare(
                exchange='skillforge.events',
                exchange_type='topic',
                durable=True
            )

            # Declare queues
            channel.queue_declare(queue='neo4j.sync', durable=True)
            channel.queue_declare(queue='ai.generation', durable=True)

            # Bind queues to exchange
            channel.queue_bind(
                exchange='skillforge.events',
                queue='neo4j.sync',
                routing_key='entity.#'
            )
            channel.queue_bind(
                exchange='skillforge.events',
                queue='ai.generation',
                routing_key='ai.*'
            )

            logger.info("Queues and bindings configured")

            # Set QoS - process one message at a time
            channel.basic_qos(prefetch_count=1)

            # Consume from neo4j.sync queue
            channel.basic_consume(
                queue='neo4j.sync',
                on_message_callback=handle_entity_event,
                auto_ack=False
            )

            # Consume from ai.generation queue
            channel.basic_consume(
                queue='ai.generation',
                on_message_callback=handle_ai_task,
                auto_ack=False
            )

            logger.info("Worker ready. Waiting for messages...")
            channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Worker error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == '__main__':
    start_worker()
