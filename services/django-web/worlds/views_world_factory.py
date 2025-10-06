"""
World Factory Views
Endpoints for initiating and monitoring world factory workflows
"""
import os
import uuid
import json
import logging
import pika
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from pymongo import MongoClient
from redis import Redis

logger = logging.getLogger(__name__)

# Database connections
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:mongo_dev_pass_2024@mongodb:27017')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://skillforge:rabbitmq_pass@rabbitmq:5672')

mongo_client = MongoClient(MONGODB_URL)
db = mongo_client['skillforge']
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryInitiateView(View):
    """Initiate a new world factory workflow"""

    def post(self, request):
        """
        Initiate world factory generation
        Expected JSON: {"genre": "Fantasy", "user_id": "user_uuid"}
        """
        try:
            data = json.loads(request.body)
            genre = data.get('genre')
            user_id = data.get('user_id', 'anonymous')

            if not genre:
                return JsonResponse({
                    'success': False,
                    'error': 'Genre is required'
                }, status=400)

            # Generate workflow ID
            workflow_id = str(uuid.uuid4())

            # Create job message
            job_data = {
                'workflow_id': workflow_id,
                'genre': genre,
                'user_id': user_id,
                'initiated_at': datetime.utcnow().isoformat()
            }

            # Publish to RabbitMQ world_factory_jobs queue
            try:
                parameters = pika.URLParameters(RABBITMQ_URL)
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()

                # Ensure queue exists
                channel.queue_declare(
                    queue='world_factory_jobs',
                    durable=True,
                    arguments={
                        'x-message-ttl': 3600000,  # 1 hour TTL
                        'x-dead-letter-exchange': 'world_factory_dlx'
                    }
                )

                # Publish job
                channel.basic_publish(
                    exchange='',
                    routing_key='world_factory_jobs',
                    body=json.dumps(job_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistent
                        content_type='application/json'
                    )
                )

                connection.close()

                logger.info(f"Initiated world factory workflow: {workflow_id} for genre: {genre}")

                # Store initial audit record in MongoDB
                db.world_factory_audit.insert_one({
                    'workflow_id': workflow_id,
                    'genre': genre,
                    'user_id': user_id,
                    'status': 'initiated',
                    'audit_trail': [{
                        'step': 'initiate',
                        'status': 'started',
                        'message': f'World factory workflow initiated for genre: {genre}',
                        'timestamp': datetime.utcnow()
                    }],
                    'created_at': datetime.utcnow()
                })

                # Store in Redis for quick access
                redis_client.setex(
                    f"world_factory:{workflow_id}:status",
                    3600,  # 1 hour
                    json.dumps({'status': 'queued', 'genre': genre})
                )

                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_id,
                    'genre': genre,
                    'message': 'World factory workflow initiated successfully'
                })

            except Exception as e:
                logger.error(f"Failed to publish to RabbitMQ: {e}")
                return JsonResponse({
                    'success': False,
                    'error': f'Failed to queue job: {str(e)}'
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            logger.error(f"Error initiating world factory: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryStatusView(View):
    """Get status of a world factory workflow"""

    def get(self, request, workflow_id):
        """Get current status and progress of workflow"""
        try:
            # Try Redis first for latest status
            redis_key = f"world_factory:{workflow_id}:latest"
            latest_status = redis_client.get(redis_key)

            if latest_status:
                status_data = json.loads(latest_status)

                # Also get progress history from Redis
                progress_key = f"world_factory:{workflow_id}:progress"
                progress_events = redis_client.lrange(progress_key, 0, -1)
                progress_history = [json.loads(event) for event in progress_events]

                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_id,
                    'latest_status': status_data,
                    'progress_history': progress_history
                })

            # Fall back to MongoDB if not in Redis
            audit_record = db.world_factory_audit.find_one({'workflow_id': workflow_id})

            if audit_record:
                # Remove MongoDB _id for JSON serialization
                audit_record.pop('_id', None)

                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_id,
                    'audit_record': audit_record
                })

            # Not found
            return JsonResponse({
                'success': False,
                'error': 'Workflow not found'
            }, status=404)

        except Exception as e:
            logger.error(f"Error getting workflow status: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryResultView(View):
    """Get final result of a completed world factory workflow"""

    def get(self, request, workflow_id):
        """Get final result including world_id and summary"""
        try:
            result = db.world_factory_results.find_one({'workflow_id': workflow_id})

            if result:
                # Remove MongoDB _id
                result.pop('_id', None)

                # Get the generated world data
                world_id = result.get('world_id')
                if world_id:
                    world = db.world_definitions.find_one({'_id': world_id})
                    if world:
                        world.pop('_id', None)
                        result['world'] = world

                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_id,
                    'result': result
                })

            return JsonResponse({
                'success': False,
                'error': 'Result not found - workflow may still be running'
            }, status=404)

        except Exception as e:
            logger.error(f"Error getting workflow result: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryCancelView(View):
    """Cancel a running workflow and rollback all changes"""

    def post(self, request, workflow_id):
        """Cancel workflow and delete any partially created data"""
        try:
            # Get workflow state to find world_id if it exists
            state = db.world_factory_state.find_one({'workflow_id': workflow_id})

            if not state:
                return JsonResponse({
                    'success': False,
                    'error': 'Workflow not found'
                }, status=404)

            world_id = state.get('world_id')

            # Rollback: Delete all created data
            deleted_counts = {}

            if world_id:
                # Delete species
                species_result = db.species_definitions.delete_many({'world_id': world_id})
                deleted_counts['species'] = species_result.deleted_count

                # Delete locations
                locations_result = db.location_definitions.delete_many({'world_id': world_id})
                deleted_counts['locations'] = locations_result.deleted_count

                # Delete regions
                regions_result = db.region_definitions.delete_many({'world_id': world_id})
                deleted_counts['regions'] = regions_result.deleted_count

                # Delete world
                world_result = db.world_definitions.delete_one({'_id': world_id})
                deleted_counts['world'] = world_result.deleted_count

                # Delete from Neo4j via event
                from ..utils.event_publisher import publish_entity_event
                publish_entity_event('world', 'deleted', world_id, {})

            # Mark workflow as cancelled in state
            db.world_factory_state.update_one(
                {'workflow_id': workflow_id},
                {
                    '$set': {
                        'status': 'cancelled',
                        'cancelled_at': datetime.utcnow()
                    }
                }
            )

            # Add cancellation to audit trail
            db.world_factory_audit.update_one(
                {'workflow_id': workflow_id},
                {
                    '$push': {
                        'audit_trail': {
                            'step': 'cancel',
                            'status': 'completed',
                            'message': 'Workflow cancelled by user',
                            'timestamp': datetime.utcnow().isoformat(),
                            'data': deleted_counts
                        }
                    }
                },
                upsert=True
            )

            # Clear Redis progress data
            redis_client.delete(f"world_factory:{workflow_id}:progress")
            redis_client.delete(f"world_factory:{workflow_id}:latest")

            return JsonResponse({
                'success': True,
                'message': 'Workflow cancelled and data rolled back',
                'deleted': deleted_counts
            })

        except Exception as e:
            logger.error(f"Error cancelling workflow: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryAuditTrailView(View):
    """Get detailed audit trail for a workflow"""

    def get(self, request, workflow_id):
        """Get complete audit trail with all steps and events"""
        try:
            audit = db.world_factory_audit.find_one({'workflow_id': workflow_id})

            if audit:
                audit.pop('_id', None)

                return JsonResponse({
                    'success': True,
                    'workflow_id': workflow_id,
                    'audit_trail': audit.get('audit_trail', []),
                    'genre': audit.get('genre'),
                    'status': audit.get('status'),
                    'created_at': audit.get('created_at').isoformat() if audit.get('created_at') else None
                })

            return JsonResponse({
                'success': False,
                'error': 'Audit trail not found'
            }, status=404)

        except Exception as e:
            logger.error(f"Error getting audit trail: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorldFactoryListWorkflowsView(View):
    """List all world factory workflows for a user"""

    def get(self, request):
        """List workflows with optional filtering - includes both completed and in-progress"""
        try:
            user_id = request.GET.get('user_id')
            status = request.GET.get('status')
            limit = int(request.GET.get('limit', 20))

            # Check for in-progress workflows in state collection
            state_query = {}
            if user_id:
                state_query['user_id'] = user_id

            in_progress_workflows = list(db.world_factory_state.find(
                state_query,
                {
                    'workflow_id': 1,
                    'world_id': 1,
                    'genre': 1,
                    'status': 1,
                    'created_at': 1,
                    'updated_at': 1
                }
            ).sort('created_at', -1).limit(limit))

            # Check completed workflows in results collection
            result_query = {}
            if user_id:
                result_query['user_id'] = user_id
            if status:
                result_query['status'] = status

            completed_workflows = list(db.world_factory_results.find(
                result_query,
                {
                    'workflow_id': 1,
                    'world_id': 1,
                    'genre': 1,
                    'status': 1,
                    'summary': 1,
                    'completed_at': 1,
                    'created_at': 1
                }
            ).sort('completed_at', -1).limit(limit))

            # Combine and deduplicate (in-progress takes precedence)
            workflow_map = {}
            for workflow in in_progress_workflows:
                workflow.pop('_id', None)
                if workflow.get('created_at'):
                    workflow['created_at'] = workflow['created_at'].isoformat() + 'Z'
                if workflow.get('updated_at'):
                    workflow['updated_at'] = workflow['updated_at'].isoformat() + 'Z'
                workflow_map[workflow['workflow_id']] = workflow

            for workflow in completed_workflows:
                workflow.pop('_id', None)
                if workflow.get('completed_at'):
                    workflow['completed_at'] = workflow['completed_at'].isoformat() + 'Z'
                if workflow.get('created_at'):
                    workflow['created_at'] = workflow['created_at'].isoformat() + 'Z'
                # Only add if not already in map (completed)
                if workflow['workflow_id'] not in workflow_map:
                    workflow_map[workflow['workflow_id']] = workflow

            workflows = list(workflow_map.values())
            # Sort by created_at or completed_at
            workflows.sort(key=lambda w: w.get('created_at') or w.get('completed_at', ''), reverse=True)

            return JsonResponse({
                'success': True,
                'workflows': workflows[:limit],
                'count': len(workflows[:limit])
            })

        except Exception as e:
            logger.error(f"Error listing workflows: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
