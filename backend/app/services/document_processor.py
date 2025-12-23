"""Document Processing Pipeline

Processes documents through: parse → chunk → embed → store.
Supports incremental processing and failure recovery.
Enterprise-grade resilience with retries, validation, and comprehensive error handling.
"""

import base64
import logging
from io import BytesIO, StringIO
from html.parser import HTMLParser
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.models.database import Source, Document, Chunk
from app.clients.llm import EmbeddingClient
from app.services.ingestion import ChunkingService

logger = logging.getLogger(__name__)

# Configuration
MAX_DOCUMENT_SIZE_MB = 50
MAX_DOCUMENT_SIZE_BYTES = MAX_DOCUMENT_SIZE_MB * 1024 * 1024
EMBEDDING_RETRY_ATTEMPTS = 3
ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "application/pdf",
    "text/html",
    "text/htm"
}


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""
    pass


class DocumentValidationError(DocumentProcessingError):
    """Document validation failed."""
    pass


class DocumentParsingError(DocumentProcessingError):
    """Document parsing failed."""
    pass


class EmbeddingError(DocumentProcessingError):
    """Embedding generation failed."""
    pass


class HTMLStripper(HTMLParser):
    """Simple HTML tag stripper."""
    def __init__(self):
        super().__init__()
        self.text = StringIO()
    
    def handle_data(self, d):
        self.text.write(d)
    
    def get_text(self) -> str:
        return self.text.getvalue()


class DocumentProcessor:
    """
    Processes documents: parse → chunk → embed → store.
    Handles failures gracefully and supports resume.
    """
    
    def __init__(self, db: AsyncSession, embedding_client: EmbeddingClient):
        self.db = db
        self.embedding_client = embedding_client
        self.chunker = ChunkingService()
        self.batch_size = 20  # Embed 20 chunks at a time
    
    async def process_document(self, document_id: UUID) -> dict:
        """
        Process a single document through the full pipeline.
        Updates status at each stage. Handles failures with comprehensive error handling.

        Returns:
        {
            "document_id": UUID,
            "status": "indexed" | "failed",
            "chunks_created": int,
            "error": str | None
        }
        """
        doc = await self.db.get(Document, document_id)
        if not doc:
            error_msg = f"Document {document_id} not found"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Starting processing for document {document_id} ({doc.title})")

        try:
            # Validation
            self._validate_document(doc)

            # Stage 1: Parse
            await self._update_status(doc, "parsing")
            text = await self._parse_content(doc)

            if not text or not text.strip():
                raise DocumentValidationError("Document has no extractable text content")

            logger.info(f"Document {document_id} parsed: {len(text)} characters")

            # Stage 2: Chunk
            await self._update_status(doc, "chunking")
            chunks = self.chunker.chunk_text(text)

            if not chunks:
                raise DocumentValidationError("Document produced no chunks")

            logger.info(f"Document {document_id} chunked: {len(chunks)} chunks")

            chunk_records = await self._create_chunks(doc, chunks)

            # Stage 3: Embed (batched with retry)
            await self._update_status(doc, "embedding")
            await self._embed_chunks_batched(chunk_records)

            logger.info(f"Document {document_id} embedded: {len(chunk_records)} chunks")

            # Stage 4: Mark indexed
            await self._update_status(doc, "indexed")
            doc.processed_at = datetime.now(timezone.utc)
            await self.db.commit()

            logger.info(f"✓ Document {document_id} successfully indexed: {len(chunk_records)} chunks")

            return {
                "document_id": str(document_id),
                "status": "indexed",
                "chunks_created": len(chunk_records),
                "error": None
            }

        except DocumentProcessingError as e:
            # Expected processing errors
            logger.error(f"Document {document_id} processing failed: {type(e).__name__}: {e}")
            await self._update_status(doc, "failed", error=f"{type(e).__name__}: {str(e)}")
            return {
                "document_id": str(document_id),
                "status": "failed",
                "chunks_created": 0,
                "error": str(e)
            }
        except Exception as e:
            # Unexpected errors
            logger.exception(f"Unexpected error processing document {document_id}")
            await self._update_status(doc, "failed", error=f"Unexpected error: {str(e)}")
            return {
                "document_id": str(document_id),
                "status": "failed",
                "chunks_created": 0,
                "error": f"Unexpected error: {str(e)}"
            }

    def _validate_document(self, doc: Document) -> None:
        """Validate document before processing."""
        if not doc.raw_content:
            raise DocumentValidationError("Document has no raw content")

        content_size = len(doc.raw_content.encode('utf-8') if isinstance(doc.raw_content, str) else doc.raw_content)
        if content_size > MAX_DOCUMENT_SIZE_BYTES:
            raise DocumentValidationError(
                f"Document size ({content_size / 1024 / 1024:.2f}MB) exceeds limit ({MAX_DOCUMENT_SIZE_MB}MB)"
            )

        if doc.content_type and doc.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Unrecognized content type {doc.content_type}, treating as text/plain")

        logger.debug(f"Document validation passed: {doc.id}")
    
    async def _parse_content(self, doc: Document) -> str:
        """Extract text from document based on content_type."""
        content_type = doc.content_type or "text/plain"
        
        if content_type == "text/plain":
            return doc.raw_content or ""
        elif content_type == "application/pdf":
            return await self._parse_pdf(doc.raw_content)
        elif content_type in ("text/html", "text/htm"):
            return self._parse_html(doc.raw_content)
        else:
            # Default: treat as plain text
            return doc.raw_content or ""
    
    async def _parse_pdf(self, content: str) -> str:
        """Parse PDF content. Content is base64 encoded."""
        try:
            from pypdf import PdfReader
        except ImportError:
            raise DocumentParsingError("pypdf not installed. Run: pip install pypdf")

        if not content:
            raise DocumentParsingError("PDF content is empty")

        try:
            pdf_bytes = base64.b64decode(content)
            reader = PdfReader(BytesIO(pdf_bytes))

            if len(reader.pages) == 0:
                raise DocumentParsingError("PDF has no pages")

            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            if not text_parts:
                raise DocumentParsingError("PDF contains no extractable text")

            return "\n\n".join(text_parts)
        except base64.binascii.Error as e:
            raise DocumentParsingError(f"Invalid base64 PDF content: {e}")
        except Exception as e:
            raise DocumentParsingError(f"Failed to parse PDF: {e}")
    
    def _parse_html(self, content: str) -> str:
        """Strip HTML tags, extract text."""
        if not content:
            return ""
        
        stripper = HTMLStripper()
        stripper.feed(content)
        return stripper.get_text()
    
    async def _create_chunks(self, doc: Document, chunks: list[dict]) -> list[Chunk]:
        """Create chunk records in database."""
        chunk_records = []
        for chunk_data in chunks:
            chunk = Chunk(
                document_id=doc.id,
                analysis_id=doc.analysis_id,  # May be None for KB-only docs
                sequence=chunk_data["sequence"],
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                is_indexed=False
            )
            self.db.add(chunk)
            chunk_records.append(chunk)
        
        await self.db.flush()  # Get IDs without committing
        return chunk_records
    
    async def _embed_chunks_batched(self, chunks: list[Chunk]) -> None:
        """Generate embeddings in batches with retry logic for resilience."""
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            texts = [c.content for c in batch]

            logger.debug(f"Embedding batch {i // self.batch_size + 1} ({len(batch)} chunks)")

            try:
                embeddings = await self._embed_with_retry(texts)

                if len(embeddings) != len(batch):
                    raise EmbeddingError(
                        f"Embedding count mismatch: expected {len(batch)}, got {len(embeddings)}"
                    )

                for chunk, embedding in zip(batch, embeddings):
                    if not embedding or len(embedding) != 768:
                        raise EmbeddingError(
                            f"Invalid embedding dimension: expected 768, got {len(embedding) if embedding else 0}"
                        )
                    chunk.embedding = embedding
                    chunk.is_indexed = True

                await self.db.flush()

            except Exception as e:
                logger.error(f"Failed to embed batch {i // self.batch_size + 1}: {e}")
                raise EmbeddingError(f"Failed to generate embeddings: {e}")

    @retry(
        stop=stop_after_attempt(EMBEDDING_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with automatic retry on transient failures."""
        try:
            return await self.embedding_client.embed(texts)
        except Exception as e:
            logger.warning(f"Embedding attempt failed: {e}")
            raise
    
    async def _update_status(self, doc: Document, status: str, error: str = None):
        """Update document processing status."""
        doc.processing_status = status
        doc.processing_error = error
        await self.db.commit()


class KnowledgeBaseService:
    """
    Manages the knowledge base: add documents, process queue, search.
    """
    
    def __init__(self, db: AsyncSession, embedding_client: EmbeddingClient):
        self.db = db
        self.embedding_client = embedding_client
        self.processor = DocumentProcessor(db, embedding_client)
    
    async def add_document(
        self,
        content: str,
        title: Optional[str] = None,
        content_type: str = "text/plain",
        source_type: str = "upload",
        source_url: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Document:
        """
        Add a document to the knowledge base.
        Creates source + document records with status='pending'.
        Does NOT process immediately - call process_pending() separately.
        """
        # Create source
        source = Source(
            source_type=source_type,
            url=source_url,
            title=title or "Untitled"
        )
        self.db.add(source)
        await self.db.flush()
        
        # Create document
        doc = Document(
            source_id=source.id,
            title=title,
            content_type=content_type,
            raw_content=content,
            meta_data=metadata or {},
            processing_status="pending",
            is_in_knowledge_base=True
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        
        logger.info(f"Document added to KB: {doc.id} ({title})")
        return doc
    
    async def process_document(self, document_id: UUID) -> dict:
        """Process a single document immediately."""
        return await self.processor.process_document(document_id)
    
    async def process_pending(self, limit: int = 100) -> list[dict]:
        """
        Process all pending documents in the knowledge base.
        Returns list of results.
        """
        # Get pending documents
        result = await self.db.execute(
            select(Document)
            .where(Document.processing_status == "pending")
            .where(Document.is_in_knowledge_base == True)
            .limit(limit)
        )
        pending_docs = result.scalars().all()
        
        logger.info(f"Processing {len(pending_docs)} pending documents")
        
        results = []
        for doc in pending_docs:
            result = await self.processor.process_document(doc.id)
            results.append(result)
        
        return results
    
    async def retry_failed(self, limit: int = 50) -> list[dict]:
        """Retry processing failed documents."""
        result = await self.db.execute(
            select(Document)
            .where(Document.processing_status == "failed")
            .where(Document.is_in_knowledge_base == True)
            .limit(limit)
        )
        failed_docs = result.scalars().all()
        
        logger.info(f"Retrying {len(failed_docs)} failed documents")
        
        results = []
        for doc in failed_docs:
            # Reset status
            doc.processing_status = "pending"
            doc.processing_error = None
            await self.db.commit()
            
            result = await self.processor.process_document(doc.id)
            results.append(result)
        
        return results
    
    async def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        # Document counts by status
        doc_stats = await self.db.execute(
            select(
                Document.processing_status,
                sql_func.count(Document.id)
            )
            .where(Document.is_in_knowledge_base == True)
            .group_by(Document.processing_status)
        )
        status_counts = {row[0]: row[1] for row in doc_stats.fetchall()}
        
        # Total chunks
        chunk_count = await self.db.scalar(
            select(sql_func.count(Chunk.id))
        )
        
        # Indexed chunks (with embeddings)
        indexed_count = await self.db.scalar(
            select(sql_func.count(Chunk.id))
            .where(Chunk.is_indexed == True)
        )
        
        return {
            "documents": {
                "total": sum(status_counts.values()),
                "pending": status_counts.get("pending", 0),
                "indexed": status_counts.get("indexed", 0),
                "failed": status_counts.get("failed", 0),
                "processing": (
                    status_counts.get("parsing", 0) + 
                    status_counts.get("chunking", 0) + 
                    status_counts.get("embedding", 0)
                )
            },
            "chunks": {
                "total": chunk_count or 0,
                "indexed": indexed_count or 0
            }
        }
