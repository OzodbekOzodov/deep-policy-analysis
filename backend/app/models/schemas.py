"""DAP API Schemas - Pydantic Models"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ===== Request Models =====

class CreateAnalysisRequest(BaseModel):
    """Request to create a new analysis job."""
    query: str = Field(..., description="The analysis query/question", min_length=1)
    text_input: Optional[str] = Field(None, description="Direct text input for analysis")
    scope: dict = Field(default_factory=dict, description="Scope configuration")
    depth: Literal["quick", "standard", "deep"] = Field(
        default="standard",
        description="Analysis depth: quick, standard, or deep"
    )
    apor_focus: list[Literal["actor", "policy", "outcome", "risk"]] = Field(
        default_factory=lambda: ["actor", "policy", "outcome", "risk"],
        description="Focus areas for APOR extraction"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "What are the impacts of the new climate policy?",
                "text_input": None,
                "scope": {},
                "depth": "standard",
                "apor_focus": ["actor", "policy", "outcome", "risk"]
            }
        }
    )

    @field_validator("apor_focus")
    @classmethod
    def validate_apor_focus(cls, v: list) -> list:
        """Ensure at least one APOR focus area is selected."""
        if not v or len(v) == 0:
            raise ValueError("At least one APOR focus area must be selected")
        return v


class UploadDocumentRequest(BaseModel):
    """Request to upload a document."""
    title: Optional[str] = Field(None, description="Document title")
    content: str = Field(..., description="Document content", min_length=1)
    content_type: str = Field(default="text/plain", description="MIME type of content")
    metadata: dict = Field(default_factory=dict, description="Additional document metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Climate Policy Document 2024",
                "content": "This policy aims to reduce carbon emissions...",
                "content_type": "text/plain",
                "metadata": {"source": "government", "year": 2024}
            }
        }
    )


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
    percent: int = Field(default=0, ge=0, le=100)
    stats: APORCounts = Field(default_factory=APORCounts)
    chunks_processed: int = Field(default=0, ge=0)
    chunks_total: int = Field(default=0, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stage": "extracting_entities",
                "percent": 45,
                "stats": {"actors": 5, "policies": 3, "outcomes": 2, "risks": 4},
                "chunks_processed": 45,
                "chunks_total": 100
            }
        }
    )


class AnalysisResponse(BaseModel):
    """Analysis job response."""
    id: UUID
    query: str
    status: str
    depth: str
    current_stage: Optional[str] = None
    progress: Optional[AnalysisProgress] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProvenanceItem(BaseModel):
    """Source provenance for an entity."""
    chunk_id: UUID
    quote: str
    confidence: int = Field(default=50, ge=0, le=100)
    document_title: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "chunk_id": "123e4567-e89b-12d3-a456-426614174000",
                "quote": "The government announced new climate measures",
                "confidence": 85,
                "document_title": "Climate Policy 2024"
            }
        }
    )


class EntityResponse(BaseModel):
    """Extracted entity response."""
    id: UUID
    type: Literal["actor", "policy", "outcome", "risk"]
    label: str
    confidence: int = Field(default=50, ge=0, le=100)
    impact_score: int = Field(default=50, ge=0, le=100)
    summary: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    provenance: list[ProvenanceItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RelationshipResponse(BaseModel):
    """Entity relationship response."""
    id: UUID
    source: UUID
    target: UUID
    relationship: str
    confidence: int = Field(default=50, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)


class GraphResponse(BaseModel):
    """Graph data for visualization."""
    nodes: list[EntityResponse] = Field(default_factory=list)
    links: list[RelationshipResponse] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    analysis_id: UUID

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [],
                "links": [],
                "version": 1,
                "analysis_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class CheckpointResponse(BaseModel):
    """Pipeline checkpoint response."""
    id: UUID
    stage: str
    version: int = Field(ge=1)
    stats: APORCounts
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """Uploaded document response."""
    id: UUID
    title: Optional[str] = None
    content_type: str = "text/plain"
    chunks_count: int = Field(default=0, ge=0)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseStats(BaseModel):
    """Knowledge base statistics."""
    total_documents: int = Field(default=0, ge=0)
    total_chunks: int = Field(default=0, ge=0)
    indexed_chunks: int = Field(default=0, ge=0)
    total_sources: int = Field(default=0, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_documents": 42,
                "total_chunks": 1250,
                "indexed_chunks": 1200,
                "total_sources": 15
            }
        }
    )


class QueryExpansionResponse(BaseModel):
    """Query expansion response."""
    original_query: str
    expansions: list[str] = Field(default_factory=list)
    cached: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_query": "climate policy impacts",
                "expansions": [
                    "climate change policy effects",
                    "environmental policy consequences",
                    "climate legislation outcomes"
                ],
                "cached": True
            }
        }
    )


class ProgressEvent(BaseModel):
    """SSE progress event for real-time updates."""
    type: Literal["stage_change", "entity_extracted", "chunk_processed", "stats_update", "complete", "error"]
    timestamp: datetime
    data: dict

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "entity_extracted",
                "timestamp": "2024-12-18T13:30:00Z",
                "data": {
                    "entity_id": "123e4567-e89b-12d3-a456-426614174000",
                    "entity_type": "actor",
                    "label": "Environmental Protection Agency"
                }
            }
        }
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
