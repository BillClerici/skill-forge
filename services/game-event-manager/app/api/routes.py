"""
API routes for Game Event Manager
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import logging

from ..services.rabbitmq_service import RabbitMQService
from ..services.validation_service import ValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


# Dependency to get RabbitMQ service
async def get_rabbitmq_service():
    """Get RabbitMQ service instance"""
    from ..main import rabbitmq_service
    return rabbitmq_service


@router.post("/events/publish")
async def publish_event(
    event: Dict[str, Any],
    rabbitmq: RabbitMQService = Depends(get_rabbitmq_service)
):
    """
    Publish an event to the event system

    Args:
        event: Event data including session_id, event_type, and payload
    """
    try:
        # Validate event
        is_valid, error_message = ValidationService.validate_event(event)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Enrich event
        enriched_event = ValidationService.enrich_event(event)

        # Get routing key
        routing_key = enriched_event['routing_key']

        # Publish to game events exchange
        await rabbitmq.publish_event(
            'game.events',
            routing_key,
            enriched_event,
            priority=enriched_event.get('priority', 5)
        )

        return {
            "status": "success",
            "message_id": enriched_event['message_id'],
            "routing_key": routing_key
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/publish-batch")
async def publish_batch_events(
    events: List[Dict[str, Any]],
    rabbitmq: RabbitMQService = Depends(get_rabbitmq_service)
):
    """
    Publish multiple events in batch

    Args:
        events: List of event data
    """
    try:
        results = []

        for event in events:
            # Validate event
            is_valid, error_message = ValidationService.validate_event(event)
            if not is_valid:
                results.append({
                    "status": "error",
                    "error": error_message
                })
                continue

            # Enrich event
            enriched_event = ValidationService.enrich_event(event)

            # Get routing key
            routing_key = enriched_event['routing_key']

            # Publish
            await rabbitmq.publish_event(
                'game.events',
                routing_key,
                enriched_event,
                priority=enriched_event.get('priority', 5)
            )

            results.append({
                "status": "success",
                "message_id": enriched_event['message_id'],
                "routing_key": routing_key
            })

        return {
            "total": len(events),
            "successful": sum(1 for r in results if r['status'] == 'success'),
            "failed": sum(1 for r in results if r['status'] == 'error'),
            "results": results
        }

    except Exception as e:
        logger.error(f"Error publishing batch events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/queue/create")
async def create_session_queue(
    session_id: UUID,
    rabbitmq: RabbitMQService = Depends(get_rabbitmq_service)
):
    """
    Create a session-specific queue for UI updates

    Args:
        session_id: Session ID
    """
    try:
        queue_name = await rabbitmq.create_session_queue(session_id)

        return {
            "status": "success",
            "queue_name": queue_name,
            "session_id": str(session_id)
        }

    except Exception as e:
        logger.error(f"Error creating session queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}/queue")
async def delete_session_queue(
    session_id: UUID,
    rabbitmq: RabbitMQService = Depends(get_rabbitmq_service)
):
    """
    Delete a session-specific queue

    Args:
        session_id: Session ID
    """
    try:
        await rabbitmq.delete_session_queue(session_id)

        return {
            "status": "success",
            "session_id": str(session_id)
        }

    except Exception as e:
        logger.error(f"Error deleting session queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "game-event-manager",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "game-event-manager",
        "version": "1.0.0",
        "description": "Central event processing hub for SkillForge games"
    }
