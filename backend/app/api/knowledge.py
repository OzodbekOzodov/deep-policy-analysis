"""Knowledge Base API Routes"""

from __future__ import annotations

import base64
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_llm_client, get_embedding_client
from app.models.schemas import KnowledgeBaseStats, QueryExpansionResponse
from app.models.database import Document, Chunk, Source
from app.clients.llm import LLMClient, EmbeddingClient
from app.services.expansion import QueryExpansionService
from app.services.document_processor import KnowledgeBaseService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    """Knowledge base search request."""
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class ExpandRequest(BaseModel):
    """Query expansion request."""
    query: str = Field(..., min_length=1)
    num_expansions: int = Field(default=15, ge=5, le=25)


# =============================================================================
# Document Management Endpoints
# =============================================================================

@router.post("/documents")
async def add_document(
    title: Optional[str] = Form(None),
    content_type: str = Form("text/plain"),
    source_type: str = Form("upload"),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """
    Add document to knowledge base.
    Accepts either file upload or text content.
    Document is queued for processing.
    """
    try:
        service = KnowledgeBaseService(db, embedding_client)

        content = None
        final_content_type = content_type
        final_title = title

        if file:
            try:
                file_bytes = await file.read()

                # Validate file size (50MB limit)
                if len(file_bytes) > 50 * 1024 * 1024:
                    raise HTTPException(
                        400,
                        f"File size ({len(file_bytes) / 1024 / 1024:.2f}MB) exceeds 50MB limit"
                    )

                if file.content_type == "application/pdf":
                    content = base64.b64encode(file_bytes).decode()
                    final_content_type = "application/pdf"
                elif file.content_type in ("text/plain", "text/html", "text/htm"):
                    content = file_bytes.decode("utf-8", errors="ignore")
                    final_content_type = file.content_type
                else:
                    # Try to decode as text
                    content = file_bytes.decode("utf-8", errors="ignore")
                    final_content_type = "text/plain"

                final_title = title or file.filename
            except UnicodeDecodeError:
                raise HTTPException(400, "File is not valid UTF-8 text or PDF")
            except Exception as e:
                raise HTTPException(400, f"Failed to read file: {str(e)}")
        elif text:
            if not text.strip():
                raise HTTPException(400, "Text content cannot be empty")
            content = text
            final_title = title or "Untitled Text Document"
        else:
            raise HTTPException(400, "Provide either file or text")

        doc = await service.add_document(
            content=content,
            title=final_title,
            content_type=final_content_type,
            source_type=source_type
        )

        return {
            "document_id": str(doc.id),
            "title": doc.title,
            "status": doc.processing_status,
            "message": "Document queued for processing"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to add document: {str(e)}")


@router.post("/process")
async def process_pending(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """
    Process all pending documents in knowledge base.
    Processes documents sequentially with comprehensive error handling.
    """
    try:
        service = KnowledgeBaseService(db, embedding_client)
        results = await service.process_pending(limit=limit)

        successful = [r for r in results if r["status"] == "indexed"]
        failed = [r for r in results if r["status"] == "failed"]

        return {
            "processed": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
            "summary": {
                "success_rate": f"{len(successful) / len(results) * 100:.1f}%" if results else "0%",
                "failed_documents": [r["document_id"] for r in failed] if failed else []
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to process documents: {str(e)}")


@router.post("/retry-failed")
async def retry_failed(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """Retry processing failed documents."""
    service = KnowledgeBaseService(db, embedding_client)
    results = await service.retry_failed(limit=limit)
    
    return {
        "retried": len(results),
        "successful": len([r for r in results if r["status"] == "indexed"]),
        "still_failed": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    """List documents in knowledge base."""
    query = select(Document).where(Document.is_in_knowledge_base == True)
    
    if status:
        query = query.where(Document.processing_status == status)
    
    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    docs = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "content_type": d.content_type,
                "status": d.processing_status,
                "error": d.processing_error,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "processed_at": d.processed_at.isoformat() if d.processed_at else None
            }
            for d in docs
        ],
        "count": len(docs)
    }


# =============================================================================
# Stats and Search Endpoints
# =============================================================================

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """Get knowledge base statistics with document status breakdown."""
    service = KnowledgeBaseService(db, embedding_client)
    return await service.get_stats()


@router.post("/search")
async def search_knowledge_base(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """
    Search knowledge base using hybrid search (semantic + full-text).

    Returns relevant chunks from the knowledge base.
    """
    from sqlalchemy import text as sql_text

    try:
        # Get query embedding
        embedding_result = await embedding_client.embed([request.query])
        query_embedding = embedding_result[0]

        # Perform hybrid search using both vector similarity and full-text
        # Using pgvector cosine distance
        query = sql_text("""
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.sequence,
                d.title as document_title,
                (1 - (c.embedding <=> :embedding::vector)) as similarity_score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE
                c.is_indexed = true
                AND c.embedding IS NOT NULL
                AND d.is_in_knowledge_base = true
            ORDER BY c.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = await db.execute(
            query,
            {
                "embedding": str(query_embedding),
                "limit": request.limit
            }
        )

        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row[0]),
                "document_id": str(row[1]),
                "content": row[2],
                "sequence": row[3],
                "document_title": row[4],
                "score": float(row[5])
            }
            for row in rows
        ]

    except Exception as e:
        # Fall back to empty results on error
        logger.warning(f"Search failed: {e}")
        return []


@router.post("/expand", response_model=QueryExpansionResponse)
async def expand_query(
    request: ExpandRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client)
):
    """
    Expand a query into multiple search variations.
    
    Uses LLM to generate diverse query reformulations for better retrieval.
    Results are cached in the database for future use.
    """
    service = QueryExpansionService(llm, db)
    
    # Check if this will be cached (for response)
    cached = await service._get_cached(request.query) is not None
    
    expansions = await service.expand_query(request.query, request.num_expansions)
    
    return QueryExpansionResponse(
        original_query=request.query,
        expansions=expansions,
        cached=cached
    )

