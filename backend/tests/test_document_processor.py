"""Tests for the Document Processor module.

Tests the complete document processing pipeline:
- Upload (queue document)
- Parse (extract text from PDF/HTML/text)
- Chunk (split into overlapping pieces)
- Embed (generate vector embeddings)
- Index (mark as searchable)
"""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.models.database import Chunk, Document
from app.services.document_processor import (
    DocumentProcessor,
    KnowledgeBaseService,
    DocumentProcessingError,
    DocumentValidationError,
    DocumentParsingError,
    EmbeddingError,
    HTMLStripper,
)


# =============================================================================
# HTMLStripper Tests
# =============================================================================

class TestHTMLStripper:
    """Tests for the HTML tag stripper."""

    def test_strip_simple_html(self):
        """Test stripping simple HTML tags."""
        stripper = HTMLStripper()
        html = "<h1>Title</h1><p>This is content</p>"
        stripper.feed(html)
        result = stripper.get_text()
        assert result == "TitleThis is content"

    def test_strip_nested_html(self):
        """Test stripping nested HTML tags."""
        stripper = HTMLStripper()
        html = "<div><p>Nested <strong>bold</strong> text</p></div>"
        stripper.feed(html)
        result = stripper.get_text()
        assert "Nested" in result
        assert "bold" in result
        assert "text" in result
        assert "<" not in result  # No tags remaining

    def test_strip_empty_html(self):
        """Test stripping empty HTML."""
        stripper = HTMLStripper()
        stripper.feed("")
        result = stripper.get_text()
        assert result == ""


# =============================================================================
# DocumentProcessor Tests
# =============================================================================

class TestDocumentProcessor:
    """Tests for the DocumentProcessor class."""

    # =========================================================================
    # Validation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validate_valid_document(
        self,
        document_processor: DocumentProcessor,
        sample_document: Document
    ):
        """Test validation of a valid document."""
        # Should not raise
        document_processor._validate_document(sample_document)

    @pytest.mark.asyncio
    async def test_validate_document_no_content(
        self,
        db_session,
        mock_embedding_client: MagicMock
    ):
        """Test validation fails for document without content."""
        processor = DocumentProcessor(db_session, mock_embedding_client)

        doc = Document(
            title="Empty Document",
            raw_content=None,
            processing_status="pending"
        )

        with pytest.raises(DocumentValidationError, match="no raw content"):
            processor._validate_document(doc)

    @pytest.mark.asyncio
    async def test_validate_document_too_large(
        self,
        db_session,
        mock_embedding_client: MagicMock
    ):
        """Test validation fails for oversized document."""
        processor = DocumentProcessor(db_session, mock_embedding_client)

        # Create content larger than 50MB limit
        large_content = "x" * (51 * 1024 * 1024)
        doc = Document(
            title="Large Document",
            raw_content=large_content,
            processing_status="pending"
        )

        with pytest.raises(DocumentValidationError, match="exceeds limit"):
            processor._validate_document(doc)

    # =========================================================================
    # Parsing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_parse_plain_text(
        self,
        document_processor: DocumentProcessor,
        sample_text_document: str
    ):
        """Test parsing plain text content."""
        doc = Document(
            title="Test",
            content_type="text/plain",
            raw_content=sample_text_document
        )

        result = await document_processor._parse_content(doc)

        assert result == sample_text_document
        assert "National AI Policy Framework" in result

    @pytest.mark.asyncio
    async def test_parse_html_content(
        self,
        document_processor: DocumentProcessor,
        sample_html_document: str
    ):
        """Test parsing HTML content."""
        doc = Document(
            title="Test HTML",
            content_type="text/html",
            raw_content=sample_html_document
        )

        result = await document_processor._parse_content(doc)

        # Should extract text without tags
        assert "Artificial Intelligence Governance Framework" in result
        assert "Safety First" in result
        assert "<!DOCTYPE html>" not in result
        assert "<h1>" not in result

    @pytest.mark.asyncio
    async def test_parse_pdf_content(
        self,
        document_processor: DocumentProcessor,
        sample_pdf_base64: str
    ):
        """Test parsing PDF content."""
        doc = Document(
            title="Test PDF",
            content_type="application/pdf",
            raw_content=sample_pdf_base64
        )

        result = await document_processor._parse_content(doc)

        # Should extract text from PDF
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_parse_pdf_invalid_base64(
        self,
        document_processor: DocumentProcessor
    ):
        """Test parsing PDF with invalid base64 content."""
        doc = Document(
            title="Invalid PDF",
            content_type="application/pdf",
            raw_content="not-valid-base64!!!"
        )

        with pytest.raises(DocumentParsingError, match="Invalid base64"):
            await document_processor._parse_content(doc)

    @pytest.mark.asyncio
    async def test_parse_pdf_empty_content(
        self,
        document_processor: DocumentProcessor
    ):
        """Test parsing PDF with empty content."""
        doc = Document(
            title="Empty PDF",
            content_type="application/pdf",
            raw_content=""
        )

        with pytest.raises(DocumentParsingError, match="empty"):
            await document_processor._parse_content(doc)

    @pytest.mark.asyncio
    async def test_parse_unknown_content_type_treats_as_text(
        self,
        document_processor: DocumentProcessor
    ):
        """Test that unknown content types default to plain text."""
        content = "Unknown format content"
        doc = Document(
            title="Unknown",
            content_type="application/unknown",
            raw_content=content
        )

        result = await document_processor._parse_content(doc)
        assert result == content

    # =========================================================================
    # Chunking Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_chunks(
        self,
        document_processor: DocumentProcessor,
        sample_document: Document,
        sample_text_document: str
    ):
        """Test creating chunk records in database."""
        chunks_data = [
            {"sequence": 0, "content": "First chunk", "token_count": 2},
            {"sequence": 1, "content": "Second chunk", "token_count": 2},
        ]

        chunk_records = await document_processor._create_chunks(
            sample_document,
            chunks_data
        )

        assert len(chunk_records) == 2
        assert chunk_records[0].sequence == 0
        assert chunk_records[0].content == "First chunk"
        assert chunk_records[1].sequence == 1
        assert chunk_records[1].content == "Second chunk"

        # Chunks should have IDs assigned but not be committed yet
        assert chunk_records[0].id is not None

    # =========================================================================
    # Embedding Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_embed_chunks_batched(
        self,
        document_processor: DocumentProcessor,
        sample_document: Document
    ):
        """Test embedding chunks in batches."""
        # Create 25 chunks (more than batch size of 20)
        chunks = []
        for i in range(25):
            chunk = Chunk(
                document_id=sample_document.id,
                sequence=i,
                content=f"Chunk content {i}",
                token_count=3,
                is_indexed=False
            )
            chunks.append(chunk)

        await document_processor._embed_chunks_batched(chunks)

        # All chunks should have embeddings
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 768  # Gemini embedding dimension
            assert chunk.is_indexed is True

    @pytest.mark.asyncio
    async def test_embed_with_retry_on_transient_failure(
        self,
        document_processor: DocumentProcessor
    ):
        """Test embedding retry logic on transient failures."""
        # Mock that fails twice then succeeds
        call_count = 0

        async def side_effect(texts):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return [[0.1] * 768 for _ in texts]

        document_processor.embedding_client.embed = AsyncMock(side_effect=side_effect)

        result = await document_processor._embed_with_retry(["test text"])

        assert call_count == 3  # Failed twice, succeeded on third try
        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_embed_with_retry_exhausted(
        self,
        document_processor: DocumentProcessor
    ):
        """Test embedding retry when attempts are exhausted."""
        # Mock that always fails
        document_processor.embedding_client.embed = AsyncMock(
            side_effect=ConnectionError("Persistent error")
        )

        with pytest.raises(ConnectionError):
            await document_processor._embed_with_retry(["test text"])

    # =========================================================================
    # End-to-End Processing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_process_document_success(
        self,
        db_session,
        mock_embedding_client: MagicMock,
        sample_text_document: str
    ):
        """Test successful end-to-end document processing."""
        # Create source
        from app.models.database import Source
        source = Source(source_type="upload", title="Test")
        db_session.add(source)
        await db_session.flush()

        # Create document
        doc = Document(
            source_id=source.id,
            title="Test Document",
            content_type="text/plain",
            raw_content=sample_text_document,
            processing_status="pending",
            is_in_knowledge_base=True
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        processor = DocumentProcessor(db_session, mock_embedding_client)

        result = await processor.process_document(doc.id)

        # Verify result
        assert result["status"] == "indexed"
        assert result["chunks_created"] > 0
        assert result["error"] is None

        # Verify database state
        await db_session.refresh(doc)
        assert doc.processing_status == "indexed"
        assert doc.processed_at is not None
        assert doc.processing_error is None

        # Verify chunks were created
        chunks_result = await db_session.execute(
            select(Chunk).where(Chunk.document_id == doc.id)
        )
        chunks = chunks_result.scalars().all()

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding is not None
            assert chunk.is_indexed is True

    @pytest.mark.asyncio
    async def test_process_document_no_extractable_text(
        self,
        db_session,
        mock_embedding_client: MagicMock
    ):
        """Test processing document with no extractable text."""
        from app.models.database import Source

        source = Source(source_type="upload", title="Test")
        db_session.add(source)
        await db_session.flush()

        doc = Document(
            source_id=source.id,
            title="Empty Document",
            content_type="text/plain",
            raw_content="   ",  # Only whitespace
            processing_status="pending",
            is_in_knowledge_base=True
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)

        processor = DocumentProcessor(db_session, mock_embedding_client)

        result = await processor.process_document(doc.id)

        assert result["status"] == "failed"
        assert "no extractable text" in result["error"].lower()

        await db_session.refresh(doc)
        assert doc.processing_status == "failed"
        assert doc.processing_error is not None

    @pytest.mark.asyncio
    async def test_process_document_not_found(
        self,
        db_session,
        mock_embedding_client: MagicMock
    ):
        """Test processing a non-existent document."""
        processor = DocumentProcessor(db_session, mock_embedding_client)

        with pytest.raises(ValueError, match="not found"):
            await processor.process_document(uuid4())


# =============================================================================
# KnowledgeBaseService Tests
# =============================================================================

class TestKnowledgeBaseService:
    """Tests for the KnowledgeBaseService class."""

    @pytest.mark.asyncio
    async def test_add_document(
        self,
        knowledge_base_service: KnowledgeBaseService
    ):
        """Test adding a document to the knowledge base."""
        content = "Test document content for knowledge base."
        title = "Test KB Document"

        doc = await knowledge_base_service.add_document(
            content=content,
            title=title,
            content_type="text/plain",
            source_type="upload"
        )

        assert doc.title == title
        assert doc.processing_status == "pending"
        assert doc.is_in_knowledge_base is True
        assert doc.raw_content == content
        assert doc.source_id is not None

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        knowledge_base_service: KnowledgeBaseService,
        indexed_document: Document
    ):
        """Test getting knowledge base statistics."""
        stats = await knowledge_base_service.get_stats()

        assert "documents" in stats
        assert "chunks" in stats

        assert stats["documents"]["total"] >= 1
        assert stats["documents"]["indexed"] >= 1
        assert stats["chunks"]["total"] >= 1
        assert stats["chunks"]["indexed"] >= 1

    @pytest.mark.asyncio
    async def test_process_pending(
        self,
        db_session,
        knowledge_base_service: KnowledgeBaseService,
        mock_embedding_client: MagicMock,
        sample_text_document: str
    ):
        """Test processing all pending documents."""
        from app.models.database import Source

        # Create multiple pending documents
        for i in range(3):
            source = Source(source_type="upload", title=f"Source {i}")
            db_session.add(source)
            await db_session.flush()

            doc = Document(
                source_id=source.id,
                title=f"Document {i}",
                content_type="text/plain",
                raw_content=sample_text_document,
                processing_status="pending",
                is_in_knowledge_base=True
            )
            db_session.add(doc)
        await db_session.commit()

        # Process all pending
        results = await knowledge_base_service.process_pending(limit=10)

        assert len(results) == 3
        assert all(r["status"] == "indexed" for r in results)

    @pytest.mark.asyncio
    async def test_retry_failed(
        self,
        db_session,
        knowledge_base_service: KnowledgeBaseService,
        mock_embedding_client: MagicMock,
        sample_text_document: str
    ):
        """Test retrying failed documents."""
        from app.models.database import Source

        # Create a failed document
        source = Source(source_type="upload", title="Failed Source")
        db_session.add(source)
        await db_session.flush()

        doc = Document(
            source_id=source.id,
            title="Failed Document",
            content_type="text/plain",
            raw_content=sample_text_document,
            processing_status="failed",
            processing_error="Temporary error",
            is_in_knowledge_base=True
        )
        db_session.add(doc)
        await db_session.commit()

        # Retry failed documents
        results = await knowledge_base_service.retry_failed(limit=10)

        assert len(results) == 1
        assert results[0]["status"] == "indexed"

        await db_session.refresh(doc)
        assert doc.processing_status == "indexed"
        assert doc.processing_error is None
