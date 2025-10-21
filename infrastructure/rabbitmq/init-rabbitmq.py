#!/usr/bin/env python3
"""
RabbitMQ Initialization Script
Sets up exchanges, queues, and bindings for SkillForge game architecture
"""
import pika
import sys
import time
import os


def wait_for_rabbitmq(host, port, username, password, max_retries=30):
    """Wait for RabbitMQ to be ready"""
    for i in range(max_retries):
        try:
            credentials = pika.PlainCredentials(username, password)
            parameters = pika.ConnectionParameters(
                host=host,
                port=port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            connection = pika.BlockingConnection(parameters)
            connection.close()
            print(f"✓ RabbitMQ is ready at {host}:{port}")
            return True
        except Exception as e:
            print(f"Waiting for RabbitMQ... ({i+1}/{max_retries}): {e}")
            time.sleep(2)

    print("✗ RabbitMQ is not available")
    return False


def setup_rabbitmq(host='localhost', port=5672, username='skillforge', password='rabbitmq_dev_pass_2024'):
    """Set up RabbitMQ exchanges, queues, and bindings"""

    print("\n" + "="*60)
    print("SkillForge RabbitMQ Initialization")
    print("="*60 + "\n")

    # Wait for RabbitMQ to be ready
    if not wait_for_rabbitmq(host, port, username, password):
        sys.exit(1)

    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(username, password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    print("Connected to RabbitMQ\n")

    # ========== EXCHANGES ==========
    print("Creating exchanges...")

    # Game Events Exchange (Topic)
    channel.exchange_declare(
        exchange='game.events',
        exchange_type='topic',
        durable=True
    )
    print("  ✓ game.events (topic)")

    # Game UI Exchange (Topic)
    channel.exchange_declare(
        exchange='game.ui',
        exchange_type='topic',
        durable=True
    )
    print("  ✓ game.ui (topic)")

    # Game Commands Exchange (Direct)
    channel.exchange_declare(
        exchange='game.commands',
        exchange_type='direct',
        durable=True
    )
    print("  ✓ game.commands (direct)")

    # ========== PERSISTENT QUEUES ==========
    print("\nCreating persistent queues...")

    # Persistence Queue (receives all game events)
    channel.queue_declare(
        queue='game.persistence.queue',
        durable=True,
        arguments={
            'x-message-ttl': 86400000,  # 24 hours
            'x-max-length': 1000000  # Max 1M messages
        }
    )
    print("  ✓ game.persistence.queue")

    # Analytics Queue
    channel.queue_declare(
        queue='game.analytics.queue',
        durable=True,
        arguments={
            'x-message-ttl': 86400000,
            'x-max-length': 500000
        }
    )
    print("  ✓ game.analytics.queue")

    # Orchestrator Queue
    channel.queue_declare(
        queue='game.orchestrator.queue',
        durable=True,
        arguments={
            'x-message-ttl': 3600000,  # 1 hour
            'x-max-length': 100000
        }
    )
    print("  ✓ game.orchestrator.queue")

    # Quest Service Queue
    channel.queue_declare(
        queue='game.quest.queue',
        durable=True,
        arguments={
            'x-message-ttl': 3600000,
            'x-max-length': 100000
        }
    )
    print("  ✓ game.quest.queue")

    # Command Queues
    for command_type in ['action', 'chat', 'system']:
        queue_name = f'game.commands.{command_type}'
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                'x-message-ttl': 300000,  # 5 minutes
                'x-max-length': 50000
            }
        )
        print(f"  ✓ {queue_name}")

    # Dead Letter Queue
    channel.queue_declare(
        queue='game.dead_letter.queue',
        durable=True
    )
    print("  ✓ game.dead_letter.queue")

    # ========== BINDINGS ==========
    print("\nCreating bindings...")

    # Bind persistence queue to all game events
    channel.queue_bind(
        exchange='game.events',
        queue='game.persistence.queue',
        routing_key='game.#'
    )
    print("  ✓ game.persistence.queue → game.# (all events)")

    # Bind analytics queue to all game events
    channel.queue_bind(
        exchange='game.events',
        queue='game.analytics.queue',
        routing_key='game.#'
    )
    print("  ✓ game.analytics.queue → game.# (all events)")

    # Bind orchestrator queue to specific events
    orchestrator_events = [
        'game.session.created',
        'game.session.started',
        'game.player.action',
        'game.quest.started',
        'game.challenge.initiated'
    ]
    for routing_key in orchestrator_events:
        channel.queue_bind(
            exchange='game.events',
            queue='game.orchestrator.queue',
            routing_key=routing_key
        )
    print(f"  ✓ game.orchestrator.queue → {len(orchestrator_events)} event types")

    # Bind quest queue to relevant events
    quest_events = [
        'game.discovery.found',
        'game.challenge.completed',
        'game.npc.interaction',
        'game.item.acquired',
        'game.knowledge.gained',
        'game.player.action'
    ]
    for routing_key in quest_events:
        channel.queue_bind(
            exchange='game.events',
            queue='game.quest.queue',
            routing_key=routing_key
        )
    print(f"  ✓ game.quest.queue → {len(quest_events)} event types")

    # Bind command queues to commands exchange
    for command_type in ['action', 'chat', 'system']:
        channel.queue_bind(
            exchange='game.commands',
            queue=f'game.commands.{command_type}',
            routing_key=command_type
        )
    print("  ✓ Command queues bound")

    # ========== SUMMARY ==========
    print("\n" + "="*60)
    print("RabbitMQ Setup Complete!")
    print("="*60)
    print("\nExchanges:")
    print("  • game.events (topic)")
    print("  • game.ui (topic)")
    print("  • game.commands (direct)")
    print("\nQueues:")
    print("  • game.persistence.queue")
    print("  • game.analytics.queue")
    print("  • game.orchestrator.queue")
    print("  • game.quest.queue")
    print("  • game.commands.action")
    print("  • game.commands.chat")
    print("  • game.commands.system")
    print("  • game.dead_letter.queue")
    print("\nRouting Keys for game.events.exchange:")
    print("  • game.session.created")
    print("  • game.session.started")
    print("  • game.session.ended")
    print("  • game.player.joined")
    print("  • game.player.action")
    print("  • game.player.disconnected")
    print("  • game.conversation.message")
    print("  • game.quest.started")
    print("  • game.quest.objective_completed")
    print("  • game.quest.completed")
    print("  • game.discovery.found")
    print("  • game.challenge.initiated")
    print("  • game.challenge.completed")
    print("  • game.npc.interaction")
    print("  • game.item.acquired")
    print("  • game.knowledge.gained")
    print("  • game.scene.changed")
    print("  • game.world.modified")
    print("\n")

    connection.close()


if __name__ == '__main__':
    # Get RabbitMQ connection details from environment or use defaults
    host = os.getenv('RABBITMQ_HOST', 'localhost')
    port = int(os.getenv('RABBITMQ_PORT', '5672'))
    username = os.getenv('RABBITMQ_USER', 'skillforge')
    password = os.getenv('RABBITMQ_PASS', os.getenv('RABBITMQ_PASSWORD', 'rabbitmq_dev_pass_2024'))

    setup_rabbitmq(host, port, username, password)
