"""Documents API Routes - Real Implementation"""

from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.schemas import UploadDocumentRequest, DocumentResponse
from app.api.deps import get_db, get_embedding_client
from app.clients.llm import EmbeddingClient
from app.services.ingestion import IngestionService
from app.models.database import Document, Chunk, AnalysisJob

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    request: UploadDocumentRequest,
    analysis_id: UUID = Query(..., description="Analysis to attach document to"),
    db: AsyncSession = Depends(get_db),
    embedding_client: EmbeddingClient = Depends(get_embedding_client)
):
    """
    Upload a document for analysis.
    
    If analysis_id is provided, associates document with that analysis.
    Otherwise creates a standalone document.
    """
    # Verify analysis exists
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    service = IngestionService(db, embedding_client)
    
    try:
        result = await service.ingest_text(
            text=request.content,
            analysis_id=analysis_id,
            title=request.title,
            source_type="paste" # or map from request if available
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    
    # Fetch and return document
    document_result = await db.execute(
        select(Document).where(Document.id == result["document_id"])
    )
    document = document_result.scalar_one()
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content_type="text/plain", # Default for pasted text
        chunks_count=result["chunks_created"],
        created_at=datetime.utcnow() # Approximation or fetch from source/doc
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get document details."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Count chunks
    chunk_count_result = await db.execute(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
    )
    chunks_count = chunk_count_result.scalar() or 0
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content_type=document.content_type,
        chunks_count=chunks_count,
        created_at=document.created_at
    )
