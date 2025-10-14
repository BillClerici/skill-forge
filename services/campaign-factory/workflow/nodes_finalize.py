"""
Campaign Finalization Node
Phase 8: Validate, persist, and finalize campaign
"""
import os
import logging
import json

from .state import CampaignWorkflowState
from .utils import add_audit_entry, publish_progress, save_audit_trail
from .db_persistence import (
    persist_campaign_to_mongodb,
    create_neo4j_relationships,
    update_postgres_analytics
)

logger = logging.getLogger(__name__)


async def finalize_campaign_node(state: CampaignWorkflowState) -> CampaignWorkflowState:
    """
    Finalize campaign: validate, persist to databases, create relationships

    This node:
    1. Validates all campaign data
    2. Persists campaign to MongoDB
    3. Creates Neo4j relationships
    4. Updates PostgreSQL for analytics
    5. Saves final audit trail
    6. Publishes completion event
    """
    try:
        state["current_node"] = "finalize_campaign"
        state["current_phase"] = "finalize"
        state["progress_percentage"] = 100
        state["status_message"] = "Finalizing campaign..."

        await publish_progress(state)

        logger.info(f"Finalizing campaign: {state['campaign_core']['name']}")

        # Step 1: Validate campaign data (100% - 0% step progress)
        state["step_progress"] = 0
        state["status_message"] = "Validating campaign data..."
        await publish_progress(state)

        validation_errors = validate_campaign(state)
        if validation_errors:
            state["errors"].extend(validation_errors)
            raise ValueError(f"Campaign validation failed: {', '.join(validation_errors)}")

        # Step 2: Persist to MongoDB (100% - 10-40% step progress)
        state["step_progress"] = 10
        state["status_message"] = "Saving campaign to MongoDB..."
        await publish_progress(state)

        campaign_id = await persist_campaign_to_mongodb(state)
        state["final_campaign_id"] = campaign_id
        state["mongodb_campaign_id"] = campaign_id

        # Step 3: Create Neo4j relationships (100% - 50-90% step progress)
        state["step_progress"] = 50
        state["status_message"] = "Creating Neo4j relationships..."
        await publish_progress(state)

        relationships_created = await create_neo4j_relationships(state, campaign_id)
        state["neo4j_relationships_created"] = relationships_created

        # Step 4: Update PostgreSQL for analytics (100% - 95% step progress)
        state["step_progress"] = 95
        state["status_message"] = "Updating analytics..."
        await publish_progress(state)

        postgres_records = await update_postgres_analytics(state, campaign_id)
        state["postgres_records_created"] = postgres_records

        # Step 5: Save audit trail (100% - 100% step progress)
        state["step_progress"] = 100
        state["status_message"] = "Saving audit trail..."
        await publish_progress(state)

        save_audit_trail(state)

        add_audit_entry(
            state,
            "finalize_campaign",
            "Campaign finalized successfully",
            {
                "campaign_id": campaign_id,
                "mongodb_records": 1,
                "neo4j_relationships": relationships_created,
                "postgres_records": postgres_records,
                "new_species_created": len(state["new_species_ids"]),
                "new_locations_created": len(state["new_location_ids"])
            },
            "success"
        )

        logger.info(f"Campaign finalized successfully: {campaign_id}")

        # Clear errors on success
        state["errors"] = []
        state["retry_count"] = 0

    except Exception as e:
        error_msg = f"Error finalizing campaign: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
        state["retry_count"] += 1

        add_audit_entry(
            state,
            "finalize_campaign",
            "Failed to finalize campaign",
            {"error": str(e), "retry_count": state["retry_count"]},
            "error"
        )

    return state


def validate_campaign(state: CampaignWorkflowState) -> list:
    """
    Validate all campaign data for completeness and consistency
    """
    errors = []

    # Validate campaign core
    if not state["campaign_core"]:
        errors.append("Campaign core is missing")
    else:
        if not state["campaign_core"].get("name"):
            errors.append("Campaign name is missing")
        if not state["campaign_core"].get("primary_objectives"):
            errors.append("Campaign primary objectives are missing")

    # Validate quests
    if not state["quests"]:
        errors.append("No quests generated")
    else:
        for idx, quest in enumerate(state["quests"]):
            if not quest.get("name"):
                errors.append(f"Quest {idx + 1} is missing name")
            if not quest.get("objectives"):
                errors.append(f"Quest {idx + 1} has no objectives")

    # Validate places
    if not state["places"]:
        errors.append("No places generated")

    # Validate scenes
    if not state["scenes"]:
        errors.append("No scenes generated")

    # Validate at least some scene elements
    if not state["npcs"] and not state["discoveries"] and not state["events"] and not state["challenges"]:
        errors.append("No scene elements generated (NPCs, discoveries, events, or challenges)")

    return errors


