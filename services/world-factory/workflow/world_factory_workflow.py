"""
World Factory LangGraph Workflow
Complete orchestration of world generation with 12 discrete steps
"""
import os
import logging
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from .state import WorldFactoryState, AuditEntry, NodeResult
from .nodes import (
    check_uniqueness_node,
    generate_world_core_node,
    generate_world_properties_node,
    generate_world_backstory_node,
)
from .nodes_images import (
    generate_world_images_node,
    generate_region_images_node,
    generate_location_images_node,
    generate_species_images_node,
)
from .nodes_entities import (
    generate_regions_node,
    generate_species_node,
    finalize_world_node,
)
from .nodes_locations_hierarchical import (
    generate_locations_hierarchical_node,
)
from .utils import publish_progress, save_audit_trail

logger = logging.getLogger(__name__)

# Initialize LLM clients
anthropic_client = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv('ANTHROPIC_API_KEY'),
    temperature=0.8,
    max_tokens=4096
)

openai_client = ChatOpenAI(
    model="gpt-4o",
    api_key=os.getenv('OPENAI_API_KEY'),
    temperature=0.7
)


def should_continue_after_error(state: WorldFactoryState) -> str:
    """Determine if workflow should continue or fail after error"""
    if state.errors and state.retry_count >= state.max_retries:
        return "failed"
    return "continue"


def route_after_uniqueness(state: WorldFactoryState) -> str:
    """Route after uniqueness check"""
    if state.errors:
        if state.retry_count < state.max_retries:
            return "retry_uniqueness"
        return "failed"
    return "generate_core"


def route_after_core(state: WorldFactoryState) -> str:
    """Route after world core generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_core"
    return "generate_properties"


def route_after_properties(state: WorldFactoryState) -> str:
    """Route after properties generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_properties"
    return "generate_backstory"


def route_after_backstory(state: WorldFactoryState) -> str:
    """Route after backstory generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_backstory"
    # Skip world images if generate_images is False
    if not state.generate_images:
        return "generate_regions"
    return "generate_world_images"


def route_after_world_images(state: WorldFactoryState) -> str:
    """Route after world images generation"""
    # Images are optional - errors are cleared in the node itself
    # Always continue to generate_regions regardless of image errors
    return "generate_regions"


def route_after_regions(state: WorldFactoryState) -> str:
    """Route after regions generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_regions"
    # Skip region images if generate_images is False
    if not state.generate_images:
        return "generate_locations"
    return "generate_region_images"


def route_after_region_images(state: WorldFactoryState) -> str:
    """Route after region images generation"""
    # Images are optional - errors are cleared in the node itself
    return "generate_locations"


def route_after_locations(state: WorldFactoryState) -> str:
    """Route after locations generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_locations"
    # Skip location images if generate_images is False
    if not state.generate_images:
        return "generate_species"
    return "generate_location_images"


def route_after_location_images(state: WorldFactoryState) -> str:
    """Route after location images generation"""
    # Images are optional - errors are cleared in the node itself
    return "generate_species"


def route_after_species(state: WorldFactoryState) -> str:
    """Route after species generation"""
    if state.errors:
        return "failed" if state.retry_count >= state.max_retries else "retry_species"
    # Skip species images if generate_images is False
    if not state.generate_images:
        return "finalize"
    return "generate_species_images"


def route_after_species_images(state: WorldFactoryState) -> str:
    """Route after species images generation"""
    # Images are optional - errors are cleared in the node itself
    return "finalize"


def create_world_factory_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for world factory

    Workflow Steps:
    1. Check Uniqueness - Ensure world is different from existing ones
    2. Generate World Core - Name, description, themes, visual style
    3. Generate World Properties - Physical, biological, tech, societal, historical
    4. Generate World Backstory - Comprehensive backstory and timeline
    5. Generate World Images - 4 DALL-E images of the world
    6. Generate Regions - 3-5 regions with backstories
    7. Generate Region Images - 4 images per region
    8. Generate Locations - Locations for each region
    9. Generate Location Images - 4 images per location
    10. Generate Species - World-appropriate species
    11. Generate Species Images - 4 images per species
    12. Finalize - Validation and final audit trail
    """

    # Create workflow graph
    workflow = StateGraph(WorldFactoryState)

    # Add nodes
    workflow.add_node("check_uniqueness", check_uniqueness_node)
    workflow.add_node("generate_core", generate_world_core_node)
    workflow.add_node("generate_properties", generate_world_properties_node)
    workflow.add_node("generate_backstory", generate_world_backstory_node)
    workflow.add_node("generate_world_images", generate_world_images_node)
    workflow.add_node("generate_regions", generate_regions_node)
    workflow.add_node("generate_region_images", generate_region_images_node)
    workflow.add_node("generate_locations", generate_locations_hierarchical_node)
    workflow.add_node("generate_location_images", generate_location_images_node)
    workflow.add_node("generate_species", generate_species_node)
    workflow.add_node("generate_species_images", generate_species_images_node)
    workflow.add_node("finalize", finalize_world_node)

    # Set entry point
    workflow.set_entry_point("check_uniqueness")

    # Add conditional edges with routing logic
    workflow.add_conditional_edges(
        "check_uniqueness",
        route_after_uniqueness,
        {
            "generate_core": "generate_core",
            "retry_uniqueness": "check_uniqueness",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_core",
        route_after_core,
        {
            "generate_properties": "generate_properties",
            "retry_core": "generate_core",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_properties",
        route_after_properties,
        {
            "generate_backstory": "generate_backstory",
            "retry_properties": "generate_properties",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_backstory",
        route_after_backstory,
        {
            "generate_world_images": "generate_world_images",
            "generate_regions": "generate_regions",  # Skip images if disabled
            "retry_backstory": "generate_backstory",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_world_images",
        route_after_world_images,
        {
            "generate_regions": "generate_regions"
        }
    )

    workflow.add_conditional_edges(
        "generate_regions",
        route_after_regions,
        {
            "generate_region_images": "generate_region_images",
            "generate_locations": "generate_locations",  # Skip images if disabled
            "retry_regions": "generate_regions",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_region_images",
        route_after_region_images,
        {
            "generate_locations": "generate_locations"
        }
    )

    workflow.add_conditional_edges(
        "generate_locations",
        route_after_locations,
        {
            "generate_location_images": "generate_location_images",
            "generate_species": "generate_species",  # Skip images if disabled
            "retry_locations": "generate_locations",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_location_images",
        route_after_location_images,
        {
            "generate_species": "generate_species"
        }
    )

    workflow.add_conditional_edges(
        "generate_species",
        route_after_species,
        {
            "generate_species_images": "generate_species_images",
            "finalize": "finalize",  # Skip images if disabled
            "retry_species": "generate_species",
            "failed": END
        }
    )

    workflow.add_conditional_edges(
        "generate_species_images",
        route_after_species_images,
        {
            "finalize": "finalize"
        }
    )

    workflow.add_edge("finalize", END)

    # Compile the workflow
    return workflow.compile()


# Export for use in main service
__all__ = ['create_world_factory_workflow', 'WorldFactoryState', 'anthropic_client', 'openai_client']
