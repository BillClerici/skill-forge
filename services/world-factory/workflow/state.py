"""
World Factory Workflow State Models
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AuditEntry(BaseModel):
    """Single audit trail entry"""
    step: str
    status: str  # started, in_progress, completed, failed
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_attempt: int = 0
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None


class WorldFactoryState(BaseModel):
    """State object for the World Factory LangGraph workflow"""

    # Workflow metadata
    workflow_id: str
    genre: str
    user_id: str
    current_step: str
    generate_images: bool = True  # Flag to control image generation

    # Generated entity IDs
    world_id: Optional[str] = None
    region_ids: List[str] = Field(default_factory=list)
    location_ids: List[str] = Field(default_factory=list)
    species_ids: List[str] = Field(default_factory=list)

    # World data (accumulated during workflow)
    world_data: Optional[Dict[str, Any]] = None
    regions_data: List[Dict[str, Any]] = Field(default_factory=list)
    locations_data: List[Dict[str, Any]] = Field(default_factory=list)
    species_data: List[Dict[str, Any]] = Field(default_factory=list)

    # Error handling
    errors: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3

    # Audit trail
    audit_trail: List[AuditEntry] = Field(default_factory=list)

    # Statistics
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True


class NodeResult(BaseModel):
    """Result from a workflow node execution"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    should_retry: bool = False
