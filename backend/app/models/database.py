"""DAP Database Models - SQLAlchemy"""

import uuid
from typing import List, Optional
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index, Date, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func, text
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class AnalysisJob(Base):
    """Analysis job tracking table."""
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    query = Column(Text, nullable=False)
    scope = Column(JSONB, server_default="{}")
    depth = Column(String(20), server_default="standard")
    status = Column(String(20), server_default="created", index=True)
    current_stage = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    entities_count = Column(JSONB, server_default="{}")
    tokens_used = Column(Integer, server_default="0")

    # Visualization data
    summary = Column(Text, nullable=True)
    projected_gdp = Column(ARRAY(Integer), nullable=True)
    social_stability = Column(ARRAY(Integer), nullable=True)
    timeline_labels = Column(ARRAY(String(50)), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_analysis_jobs_analysis_status", "id", "status"),
    )

    # Relationships
    documents = relationship("Document", back_populates="analysis", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="analysis", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="analysis", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="analysis", cascade="all, delete-orphan")
    checkpoints = relationship("Checkpoint", back_populates="analysis", cascade="all, delete-orphan")
    progress_events = relationship("ProgressEvent", back_populates="analysis", cascade="all, delete-orphan")
    merge_logs = relationship("EntityMergeLog", cascade="all, delete-orphan")


class Source(Base):
    """Data sources (web search, upload, etc)."""
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    source_type = Column(String(50), nullable=False)  # 'upload', 'paste', 'web_search'
    url = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    author = Column(String(255), nullable=True)
    publish_date = Column(Date, nullable=True)
    fetch_date = Column(DateTime(timezone=True), server_default=func.now())
    meta_data = Column("metadata", JSONB, server_default="{}")

    # Relationships
    documents = relationship("Document", back_populates="source")


class Document(Base):
    """Uploaded document storage."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=True, index=True)  # nullable for KB-only docs
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    content_type = Column(String(50), nullable=True)
    raw_content = Column(Text, nullable=True)
    meta_data = Column("metadata", JSONB, server_default="{}")
    is_in_knowledge_base = Column(Boolean, server_default="true")

    # Processing status for document pipeline
    processing_status = Column(String(20), server_default="pending", index=True)  # pending, parsing, chunking, embedding, indexed, failed
    processing_error = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="documents")
    source = relationship("Source", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")



class Chunk(Base):
    """Text chunks for processing."""
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=True, index=True)  # nullable for KB-only docs
    sequence = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(768), nullable=True)  # Gemini embeddings (768)
    is_indexed = Column(Boolean, server_default="false")
    extraction_status = Column(String(20), server_default="pending")
    extraction_result = Column(JSONB, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_chunks_embedding", embedding, postgresql_using="ivfflat", postgresql_with={"lists": 100}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_chunks_search_vector", search_vector, postgresql_using="gin"),
        Index("ix_chunks_document_sequence", "document_id", "sequence"),
    )

    # Relationships
    analysis = relationship("AnalysisJob", back_populates="chunks")
    document = relationship("Document", back_populates="chunks")
    provenance = relationship("EntityProvenance", back_populates="chunk", cascade="all, delete-orphan")


class Entity(Base):
    """Extracted APOR entities."""
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False, index=True)
    label = Column(String(500), nullable=False)
    aliases = Column(ARRAY(Text), server_default="{}")
    confidence = Column(Integer, nullable=True)
    impact_score = Column(Integer, server_default="50")
    summary = Column(Text, nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    is_resolved = Column(Boolean, server_default="false")
    merged_into = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint("entity_type IN ('actor', 'policy', 'outcome', 'risk')", name="check_entity_type"),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="check_confidence_range"),
        CheckConstraint("impact_score >= 0 AND impact_score <= 100", name="check_impact_score_range"),
        Index("ix_entities_is_resolved", is_resolved),
        Index("ix_entities_analysis_type", "analysis_id", "entity_type"),
    )
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="entities")
    provenance = relationship("EntityProvenance", back_populates="entity", cascade="all, delete-orphan")
    merged_entity = relationship("Entity", remote_side=[id], backref="merged_from")


class EntityProvenance(Base):
    """Source attribution for entities."""
    __tablename__ = "entity_provenance"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(Text, nullable=False)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    entity = relationship("Entity", back_populates="provenance")
    chunk = relationship("Chunk", back_populates="provenance")


class Relationship(Base):
    """Relationships between entities."""
    __tablename__ = "relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)
    confidence = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("analysis_id", "source_entity_id", "target_entity_id", "relationship_type", name="relationships_analysis_id_source_entity_id_target_entity_id_key"),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="check_rel_confidence_range"),
    )
    
    # Relationships
    analysis = relationship("AnalysisJob", back_populates="relationships")
    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])


class Checkpoint(Base):
    """Pipeline state snapshots."""
    __tablename__ = "checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    stats = Column(JSONB, nullable=False)
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
    data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_progress_events_analysis_created", "analysis_id", created_at.desc()),
    )

    # Relationships
    analysis = relationship("AnalysisJob", back_populates="progress_events")


class QueryExpansion(Base):
    """Query expansion cache."""
    __tablename__ = "query_expansions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    original_query = Column(Text, nullable=False)
    query_hash = Column(String(64), nullable=False, unique=True)
    expansions = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EntityMergeLog(Base):
    """Audit trail for entity merge operations."""
    __tablename__ = "entity_merge_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_entity_id = Column(UUID(as_uuid=True), nullable=True)
    merged_entity_ids = Column(JSONB, nullable=False)  # Array of merged entity UUIDs
    merge_method = Column(String(50), nullable=False)  # 'alias_dict', 'exact_match', 'llm_batch'
    confidence = Column(Integer, nullable=True)  # Merge confidence 0-100
    canonical_label = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SummaryCache(Base):
    """Cache for generated entity analysis summaries."""
    __tablename__ = "summary_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    cache_key = Column(String(64), nullable=False, unique=True, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    config_hash = Column(String(64), nullable=False, index=True)  # Hash of selected_types
    summary = Column(Text, nullable=False)
    citations = Column(JSONB, nullable=False)  # List of citation objects
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Index for looking up by entity + config
    __table_args__ = (
        Index("ix_summary_cache_entity_config", "entity_id", "config_hash"),
    )
