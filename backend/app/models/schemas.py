"""DAP API Schemas - Pydantic Models"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field


# ===== Request Models =====

class CreateAnalysisRequest(BaseModel):
    """Request to create a new analysis job."""
    query: str = Field(..., description="The analysis query/question")
    scope: dict = Field(default_factory=dict, description="Scope configuration")
    depth: str = Field(default="standard", description="Analysis depth: quick, standard, deep")
    text_input: Optional[str] = Field(None, description="Direct text input for analysis")


class UploadDocumentRequest(BaseModel):
    """Request to upload a document."""
    title: Optional[str] = Field(None, description="Document title")
    content: str = Field(..., description="Document content")
    content_type: str = Field(default="text/plain", description="MIME type of content")


# ===== Response Models =====

class APORCounts(BaseModel):
    """APOR entity counts."""
    actors: int = 0
    policies: int = 0
    outcomes: int = 0
    risks: int = 0


class AnalysisProgress(BaseModel):
    """Analysis progress information."""
    stage: str
    percent: int = 0
    stats: APORCounts = Field(default_factory=APORCounts)


class AnalysisResponse(BaseModel):
    """Analysis job response."""
    id: UUID
    query: str
    status: str
    current_stage: Optional[str] = None
    progress: Optional[AnalysisProgress] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProvenanceResponse(BaseModel):
    """Source provenance for an entity."""
    chunk_id: UUID
    quote: Optional[str] = None
    confidence: int = 50


class EntityResponse(BaseModel):
    """Extracted entity response."""
    id: UUID
    type: Literal["actor", "policy", "outcome", "risk"]
    label: str
    confidence: int = 50
    impact_score: int = 50
    summary: Optional[str] = None
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class RelationshipResponse(BaseModel):
    """Entity relationship response."""
    id: UUID
    source: UUID
    target: UUID
    relationship: str
    confidence: int = 50
    
    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    """Graph data for visualization."""
    nodes: list[EntityResponse] = Field(default_factory=list)
    links: list[RelationshipResponse] = Field(default_factory=list)
    version: int = 1
    # Add simulation data
    summary: Optional[str] = None
    projected_gdp: Optional[list[int]] = None
    social_stability: Optional[list[int]] = None
    timeline_labels: Optional[list[str]] = None


class CheckpointResponse(BaseModel):
    """Pipeline checkpoint response."""
    id: UUID
    stage: str
    version: int
    stats: APORCounts
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Uploaded document response."""
    id: UUID
    title: Optional[str] = None
    content_type: str = "text/plain"
    chunks_count: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
