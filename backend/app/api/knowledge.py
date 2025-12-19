"""Knowledge Base API Routes"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.models.schemas import KnowledgeBaseStats
from app.models.database import Document, Chunk, Source

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class SearchRequest(BaseModel):
    """Knowledge base search request."""
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get knowledge base statistics.

    Returns counts of documents, chunks, indexed chunks, and sources.
    """
    # Count total documents
    doc_count_result = await db.execute(
        select(func.count()).select_from(Document)
    )
    total_documents = doc_count_result.scalar() or 0

    # Count total chunks
    chunk_count_result = await db.execute(
        select(func.count()).select_from(Chunk)
    )
    total_chunks = chunk_count_result.scalar() or 0

    # Count indexed chunks (with embeddings)
    indexed_count_result = await db.execute(
        select(func.count())
        .select_from(Chunk)
        .where(Chunk.is_indexed == True)
    )
    indexed_chunks = indexed_count_result.scalar() or 0

    # Count sources
    source_count_result = await db.execute(
        select(func.count()).select_from(Source)
    )
    total_sources = source_count_result.scalar() or 0

    return KnowledgeBaseStats(
        total_documents=total_documents,
        total_chunks=total_chunks,
        indexed_chunks=indexed_chunks,
        total_sources=total_sources
    )


@router.post("/search")
async def search_knowledge_base(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search knowledge base (stub).

    In production, this would perform semantic search using embeddings
    or full-text search using search_vector.
    """
    # Stub: Return empty list
    # TODO: Implement semantic search with pgvector or full-text search
    return []
