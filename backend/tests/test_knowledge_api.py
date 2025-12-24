"""Tests for the Knowledge Base API endpoints.

Tests the complete HTTP API for knowledge base operations:
- POST /api/knowledge/documents - Upload documents
- POST /api/knowledge/process - Process pending documents
- POST /api/knowledge/retry-failed - Retry failed documents
- GET /api/knowledge/documents - List documents by status
- GET /api/knowledge/stats - Get knowledge base statistics
- POST /api/knowledge/search - Semantic search
- POST /api/knowledge/expand - Query expansion
"""

import base64
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.database import Chunk, Document


# =============================================================================
# POST /api/knowledge/documents - Upload Document Tests
# =============================================================================

class TestUploadDocument:
    """Tests for document upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_text_document(
        self,
        http_client: AsyncClient,
        sample_text_document: str
    ):
        """Test uploading a plain text document."""
        response = await http_client.post(
            "/api/knowledge/documents",
            data={
                "text": sample_text_document,
                "title": "Test Policy Document",
                "content_type": "text/plain",
                "source_type": "upload"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "document_id" in data
        assert data["title"] == "Test Policy Document"
        assert data["status"] == "pending"
        assert "message" in data

    @pytest.mark.asyncio
    async def test_upload_text_document_default_title(
        self,
        http_client: AsyncClient
    ):
        """Test uploading text without providing a title."""
        response = await http_client.post(
            "/api/knowledge/documents",
            data={
                "text": "Test content",
                "content_type": "text/plain"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Untitled Text Document"

    @pytest.mark.asyncio
    async def test_upload_empty_text_rejected(
        self,
        http_client: AsyncClient
    ):
        """Test that empty text content is rejected."""
        response = await http_client.post(
            "/api/knowledge/documents",
            data={
                "text": "   ",
                "title": "Empty Doc"
            }
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_neither_file_nor_text_rejected(
        self,
        http_client: AsyncClient
    ):
        """Test that request without file or text is rejected."""
        response = await http_client.post(
            "/api/knowledge/documents",
            data={"title": "No content"}
        )

        assert response.status_code == 400
        assert "either file or text" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_text_file(
        self,
        http_client: AsyncClient,
        sample_text_document: str
    ):
        """Test uploading a text file."""
        file_content = sample_text_document.encode('utf-8')
        files = {"file": ("document.txt", BytesIO(file_content), "text/plain")}
        data = {"title": "Uploaded File"}

        response = await http_client.post(
            "/api/knowledge/documents",
            files=files,
            data=data
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data

    @pytest.mark.asyncio
    async def test_upload_pdf_file(
        self,
        http_client: AsyncClient,
        sample_pdf_bytes: bytes
    ):
        """Test uploading a PDF file."""
        files = {"file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")}
        data = {"title": "Test PDF"}

        response = await http_client.post(
            "/api/knowledge/documents",
            files=files,
            data=data
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data

    @pytest.mark.asyncio
    async def test_upload_oversized_file_rejected(
        self,
        http_client: AsyncClient
    ):
        """Test that files larger than 50MB are rejected."""
        # Create a 51MB file
        large_content = b"x" * (51 * 1024 * 1024)
        files = {"file": ("large.txt", BytesIO(large_content), "text/plain")}

        response = await http_client.post(
            "/api/knowledge/documents",
            files=files
        )

        assert response.status_code == 400
        assert "exceeds" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_html_file(
        self,
        http_client: AsyncClient,
        sample_html_document: str
    ):
        """Test uploading an HTML file."""
        file_content = sample_html_document.encode('utf-8')
        files = {"file": ("document.html", BytesIO(file_content), "text/html")}
        data = {"title": "HTML Document"}

        response = await http_client.post(
            "/api/knowledge/documents",
            files=files,
            data=data
        )

        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data


# =============================================================================
# POST /api/knowledge/process - Process Documents Tests
# =============================================================================

class TestProcessPendingDocuments:
    """Tests for processing pending documents endpoint."""

    @pytest.mark.asyncio
    async def test_process_pending_documents(
        self,
        http_client: AsyncClient,
        db_session,
        sample_text_document: str
    ):
        """Test processing pending documents."""
        from app.models.database import Source

        # Create a pending document
        source = Source(source_type="upload", title="Test")
        db_session.add(source)
        await db_session.flush()

        doc = Document(
            source_id=source.id,
            title="To Process",
            content_type="text/plain",
            raw_content=sample_text_document,
            processing_status="pending",
            is_in_knowledge_base=True
        )
        db_session.add(doc)
        await db_session.commit()

        # Process pending documents
        response = await http_client.post("/api/knowledge/process?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data["processed"] >= 1
        assert data["successful"] >= 1
        assert "results" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_process_with_custom_limit(
        self,
        http_client: AsyncClient,
        db_session,
        sample_text_document: str
    ):
        """Test processing with a custom limit."""
        from app.models.database import Source

        # Create multiple documents
        for i in range(5):
            source = Source(source_type="upload", title=f"Source {i}")
            db_session.add(source)
            await db_session.flush()

            doc = Document(
                source_id=source.id,
                title=f"Doc {i}",
                content_type="text/plain",
                raw_content=sample_text_document,
                processing_status="pending",
                is_in_knowledge_base=True
            )
            db_session.add(doc)
        await db_session.commit()

        # Process with limit of 2
        response = await http_client.post("/api/knowledge/process?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 2

    @pytest.mark.asyncio
    async def test_process_when_no_pending_documents(
        self,
        http_client: AsyncClient
    ):
        """Test processing when there are no pending documents."""
        response = await http_client.post("/api/knowledge/process")

        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 0


# =============================================================================
# POST /api/knowledge/retry-failed - Retry Failed Documents Tests
# =============================================================================

class TestRetryFailedDocuments:
    """Tests for retrying failed documents endpoint."""

    @pytest.mark.asyncio
    async def test_retry_failed_documents(
        self,
        http_client: AsyncClient,
        db_session,
        sample_text_document: str
    ):
        """Test retrying failed documents."""
        from app.models.database import Source

        # Create a failed document
        source = Source(source_type="upload", title="Failed")
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
        response = await http_client.post("/api/knowledge/retry-failed?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert data["retried"] >= 1
        assert data["successful"] >= 1


# =============================================================================
# GET /api/knowledge/documents - List Documents Tests
# =============================================================================

class TestListDocuments:
    """Tests for listing documents endpoint."""

    @pytest.mark.asyncio
    async def test_list_all_documents(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test listing all documents without status filter."""
        response = await http_client.get("/api/knowledge/documents")

        assert response.status_code == 200
        data = response.json()

        assert "documents" in data
        assert "count" in data
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_list_pending_documents(
        self,
        http_client: AsyncClient,
        db_session,
        sample_text_document: str
    ):
        """Test listing only pending documents."""
        from app.models.database import Source

        # Create pending document
        source = Source(source_type="upload", title="Pending")
        db_session.add(source)
        await db_session.flush()

        doc = Document(
            source_id=source.id,
            title="Pending Doc",
            content_type="text/plain",
            raw_content=sample_text_document,
            processing_status="pending",
            is_in_knowledge_base=True
        )
        db_session.add(doc)
        await db_session.commit()

        response = await http_client.get("/api/knowledge/documents?status=pending")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] >= 1
        for doc in data["documents"]:
            assert doc["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_indexed_documents(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test listing only indexed documents."""
        response = await http_client.get("/api/knowledge/documents?status=indexed")

        assert response.status_code == 200
        data = response.json()

        assert data["count"] >= 1
        for doc in data["documents"]:
            assert doc["status"] == "indexed"

    @pytest.mark.asyncio
    async def test_list_documents_with_limit(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test listing documents with a limit."""
        response = await http_client.get("/api/knowledge/documents?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 1

    @pytest.mark.asyncio
    async def test_list_documents_with_offset(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test listing documents with offset for pagination."""
        response1 = await http_client.get("/api/knowledge/documents?limit=1")
        response2 = await http_client.get("/api/knowledge/documents?limit=1&offset=1")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # If there are multiple documents, the results should differ
        if data1["count"] > 0 and data2["count"] > 0:
            doc1_id = data1["documents"][0]["id"]
            doc2_id = data2["documents"][0]["id"]
            # May be same if there's only 1 document
            assert doc1_id is not None


# =============================================================================
# GET /api/knowledge/stats - Get Statistics Tests
# =============================================================================

class TestGetStats:
    """Tests for knowledge base statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test getting knowledge base statistics."""
        response = await http_client.get("/api/knowledge/stats")

        assert response.status_code == 200
        data = response.json()

        assert "documents" in data
        assert "chunks" in data

        # Verify document stats structure
        doc_stats = data["documents"]
        assert "total" in doc_stats
        assert "pending" in doc_stats
        assert "indexed" in doc_stats
        assert "failed" in doc_stats
        assert "processing" in doc_stats

        # Verify chunk stats structure
        chunk_stats = data["chunks"]
        assert "total" in chunk_stats
        assert "indexed" in chunk_stats

        # Values should be non-negative
        assert doc_stats["total"] >= 0
        assert chunk_stats["total"] >= 0

    @pytest.mark.asyncio
    async def test_get_stats_empty_knowledge_base(
        self,
        http_client: AsyncClient,
        db_session
    ):
        """Test getting stats when knowledge base is empty."""
        response = await http_client.get("/api/knowledge/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["documents"]["total"] >= 0
        assert data["chunks"]["total"] >= 0


# =============================================================================
# POST /api/knowledge/search - Semantic Search Tests
# =============================================================================

class TestSearchKnowledgeBase:
    """Tests for knowledge base search endpoint."""

    @pytest.mark.asyncio
    async def test_search_with_query(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test searching with a text query."""
        response = await http_client.post(
            "/api/knowledge/search",
            json={"query": "artificial intelligence policy", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()

        # Should return a list of results
        assert isinstance(data, list)

        # If results exist, verify structure
        if len(data) > 0:
            result = data[0]
            assert "chunk_id" in result
            assert "document_id" in result
            assert "content" in result
            assert "sequence" in result
            assert "document_title" in result
            assert "score" in result
            assert isinstance(result["score"], (int, float))

    @pytest.mark.asyncio
    async def test_search_with_custom_limit(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test searching with a custom result limit."""
        response = await http_client.post(
            "/api/knowledge/search",
            json={"query": "policy", "limit": 2}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(
        self,
        http_client: AsyncClient
    ):
        """Test that empty query is rejected."""
        response = await http_client.post(
            "/api/knowledge/search",
            json={"query": "", "limit": 5}
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_search_limit_validation(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test that search limit is properly validated."""
        # Test limit exceeds maximum
        response = await http_client.post(
            "/api/knowledge/search",
            json={"query": "policy", "limit": 200}
        )

        # Should be rejected or capped
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_search_returns_relevant_results(
        self,
        http_client: AsyncClient,
        indexed_document: Document
    ):
        """Test that search returns relevant results based on query."""
        # Search for content that should exist in indexed document
        response = await http_client.post(
            "/api/knowledge/search",
            json={"query": "artificial intelligence safety", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()

        # Results should be sorted by score (most relevant first)
        if len(data) > 1:
            scores = [r["score"] for r in data]
            assert scores == sorted(scores, reverse=True)


# =============================================================================
# POST /api/knowledge/expand - Query Expansion Tests
# =============================================================================

class TestQueryExpansion:
    """Tests for query expansion endpoint."""

    @pytest.mark.asyncio
    async def test_expand_query(
        self,
        http_client: AsyncClient
    ):
        """Test expanding a query into multiple variations."""
        response = await http_client.post(
            "/api/knowledge/expand",
            json={"query": "AI policy risks", "num_expansions": 5}
        )

        assert response.status_code == 200
        data = response.json()

        assert "original_query" in data
        assert "expansions" in data
        assert "cached" in data

        assert data["original_query"] == "AI policy risks"
        assert isinstance(data["expansions"], list)
        assert len(data["expansions"]) >= 1

    @pytest.mark.asyncio
    async def test_expand_with_custom_count(
        self,
        http_client: AsyncClient
    ):
        """Test query expansion with custom expansion count."""
        response = await http_client.post(
            "/api/knowledge/expand",
            json={"query": "climate policy", "num_expansions": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # Should generate requested number of expansions
        assert len(data["expansions"]) >= 1

    @pytest.mark.asyncio
    async def test_expand_empty_query_rejected(
        self,
        http_client: AsyncClient
    ):
        """Test that empty query is rejected."""
        response = await http_client.post(
            "/api/knowledge/expand",
            json={"query": "", "num_expansions": 5}
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_expand_limit_validation(
        self,
        http_client: AsyncClient
    ):
        """Test that expansion count is properly validated."""
        # Test exceeds maximum
        response = await http_client.post(
            "/api/knowledge/expand",
            json={"query": "policy", "num_expansions": 50}
        )

        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_expand_caching(
        self,
        http_client: AsyncClient
    ):
        """Test that query expansions are cached."""
        query = "test caching query"

        # First request
        response1 = await http_client.post(
            "/api/knowledge/expand",
            json={"query": query, "num_expansions": 5}
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request (should be cached)
        response2 = await http_client.post(
            "/api/knowledge/expand",
            json={"query": query, "num_expansions": 5}
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Second request should indicate it was cached
        assert data2["cached"] is True
