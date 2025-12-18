"""Documents API Routes - Real Implementation"""

from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db
from app.models.schemas import UploadDocumentRequest, DocumentResponse
from app.models.database import Document, Chunk, AnalysisJob
from app.services.ingestion import ChunkingService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    request: UploadDocumentRequest,
    analysis_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document for analysis.
    
    If analysis_id is provided, associates document with that analysis.
    Otherwise creates a standalone document.
    """
    # Create analysis if not provided
    if analysis_id is None:
        analysis = AnalysisJob(
            query=request.title or "Document Analysis",
            status="created"
        )
        db.add(analysis)
        await db.flush()
        analysis_id = analysis.id
    else:
        # Verify analysis exists
        result = await db.execute(
            select(AnalysisJob).where(AnalysisJob.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Create document
    document = Document(
        analysis_id=analysis_id,
        title=request.title or "Untitled Document",
        content_type=request.content_type,
        raw_content=request.content,
        meta_data=request.metadata or {}
    )
    db.add(document)
    await db.flush()
    
    # Chunk the content
    chunker = ChunkingService()
    chunk_data = chunker.chunk_text(request.content)
    
    # Store chunks
    for chunk_info in chunk_data:
        chunk = Chunk(
            document_id=document.id,
            analysis_id=analysis_id,
            sequence=chunk_info["sequence"],
            content=chunk_info["content"],
            token_count=chunk_info["token_count"],
            extraction_status="pending"
        )
        db.add(chunk)
    
    await db.commit()
    
    return DocumentResponse(
        id=document.id,
        title=document.title,
        content_type=document.content_type,
        chunks_count=len(chunk_data),
        created_at=document.created_at
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
