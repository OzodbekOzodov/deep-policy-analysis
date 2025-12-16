"""DAP Database Models - SQLAlchemy"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class AnalysisJob(Base):
    """Analysis job tracking table."""
    __tablename__ = "analysis_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(Text, nullable=False)
    scope = Column(JSONB, default=dict)
    depth = Column(String(20), default="standard")
    status = Column(String(20), default="created", index=True)
    current_stage = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    entities_count = Column(JSONB, default=lambda: {"actors": 0, "policies": 0, "outcomes": 0, "risks": 0})
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Simulation data for UI charts
    summary = Column(Text, nullable=True)
    projected_gdp = Column(ARRAY(Integer), nullable=True)
    social_stability = Column(ARRAY(Integer), nullable=True)
    timeline_labels = Column(ARRAY(String), nullable=True)
    
    # Relationships
    documents = relationship("Document", back_populates="analysis", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="analysis", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="analysis", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="analysis", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="analysis", cascade="all, delete-orphan")
    progress_events = relationship("ProgressEvent", back_populates="analysis", cascade="all, delete-orphan")


class Document(Base):
    """Uploaded document storage."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    content_type = Column(String(50), default="text/plain")
    raw_content = Column(Text, nullable=True)
    doc_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Text chunks for processing."""
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    extraction_status = Column(String(20), default="pending", index=True)
    extraction_result = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")
    provenance = relationship("EntityProvenance", back_populates="chunk", cascade="all, delete-orphan")


class Entity(Base):
    """Extracted APOR entities."""
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False, index=True)
    label = Column(String(500), nullable=False)
    aliases = Column(ARRAY(Text), default=list)
    confidence = Column(Integer, default=50)
    impact_score = Column(Integer, default=50)
    summary = Column(Text, nullable=True)
    is_resolved = Column(Boolean, default=False, index=True)
    merged_into = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint("entity_type IN ('actor', 'policy', 'outcome', 'risk')", name="check_entity_type"),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="check_confidence_range"),
    )
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="entities")
    provenance = relationship("EntityProvenance", back_populates="entity", cascade="all, delete-orphan")
    merged_entity = relationship("Entity", remote_side=[id], backref="merged_from")


class EntityProvenance(Base):
    """Source attribution for entities."""
    __tablename__ = "entity_provenance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(Text, nullable=True)
    confidence = Column(Integer, default=50)
    
    # Relationships
    entity = relationship("Entity", back_populates="provenance")
    chunk = relationship("Chunk", back_populates="provenance")


class Relationship(Base):
    """Relationships between entities."""
    __tablename__ = "relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)
    confidence = Column(Integer, default=50)
    
    __table_args__ = (
        UniqueConstraint("analysis_id", "source_entity_id", "target_entity_id", "relationship_type", name="unique_relationship"),
    )
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="relationships")
    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])


class Checkpoint(Base):
    """Pipeline state snapshots."""
    __tablename__ = "checkpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    stats = Column(JSONB, default=dict)
    graph_snapshot = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="checkpoints")


class ProgressEvent(Base):
    """SSE progress events."""
    __tablename__ = "progress_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="progress_events")
