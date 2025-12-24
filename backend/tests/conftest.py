"""Test configuration and fixtures for the DAP backend test suite."""

import asyncio
import base64
import os
import sys
import uuid
from io import BytesIO
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.models.database import Base, Document, Chunk, Source
from app.services.document_processor import DocumentProcessor, KnowledgeBaseService
from app.clients.llm import LLMClient, EmbeddingClient


# Test database URL (can be overridden via environment)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://localhost/dap_test"
)

# Test engine - use NullPool to avoid connection issues during testing
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Drop all tables and recreate them
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def http_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an HTTP client for testing API endpoints."""

    async def override_get_db():
        yield db_session

    from app.api.deps import get_db
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_embedding_client() -> MagicMock:
    """Create a mock embedding client."""
    client = MagicMock(spec=EmbeddingClient)

    async def mock_embed(texts: list[str]) -> list[list[float]]:
        # Return 768-dimensional embeddings (matching Gemini text-embedding-004)
        return [[0.1] * 768 for _ in texts]

    client.embed = AsyncMock(side_effect=mock_embed)
    return client


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create a mock LLM client."""
    client = MagicMock(spec=LLMClient)

    async def mock_complete(prompt: str, **kwargs) -> str:
        return """{"expansions": [
            "artificial intelligence policy",
            "AI governance frameworks",
            "machine learning regulations",
            "algorithmic accountability",
            "automated decision making oversight"
        ]}"""

    client.complete = AsyncMock(side_effect=mock_complete)
    return client


@pytest.fixture
def sample_text_document() -> str:
    """Sample text document for testing."""
    return """
    National AI Policy Framework

    The rapid advancement of artificial intelligence (AI) technologies presents both
    opportunities and challenges for policymakers. This framework outlines key
    considerations for effective AI governance.

    Key Principles:
    1. Safety: AI systems must be safe, secure, and aligned with human values.
    2. Transparency: AI decision-making processes should be explainable and auditable.
    3. Accountability: Clear liability frameworks for AI-caused harms must be established.
    4. Innovation: Regulations should promote research while managing risks.

    Risks identified include:
    - Algorithmic bias and discrimination in automated systems
    - Privacy violations through surveillance capabilities
    - Economic displacement due to automation
    - Dual-use military applications

    Recommended actions:
    - Create an AI Safety Board with regulatory authority
    - Establish pre-deployment risk assessment requirements
    - Invest in AI safety research and development
    - Develop international treaties on autonomous weapons
    """


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Create a sample PDF file for testing."""
    pdf_buffer = BytesIO()
    pdf_writer = PdfWriter()

    # Create a simple blank page (in real tests, you'd add actual content)
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    # Try to create with reportlab if available, otherwise use simple approach
    try:
        temp_pdf = BytesIO()
        c = canvas.Canvas(temp_pdf, pagesize=letter)
        c.drawString(100, 750, "Test PDF Document")
        c.drawString(100, 730, "This is a test document for processing.")
        c.drawString(100, 710, "Content includes policy information.")
        c.save()

        pdf_buffer.write(temp_pdf.getvalue())
    except ImportError:
        # Fallback: create minimal PDF
        pdf_buffer.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")

    pdf_buffer.seek(0)
    return pdf_buffer.read()


@pytest.fixture
def sample_pdf_base64(sample_pdf_bytes: bytes) -> str:
    """Sample PDF content as base64 encoded string."""
    return base64.b64encode(sample_pdf_bytes).decode('utf-8')


@pytest.fixture
def sample_html_document() -> str:
    """Sample HTML document for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Policy Document</title>
    </head>
    <body>
        <h1>Artificial Intelligence Governance Framework</h1>
        <p>This document outlines the key principles for AI regulation.</p>
        <h2>Core Principles</h2>
        <ul>
            <li><strong>Safety First:</strong> AI systems must prioritize human safety.</li>
            <li><strong>Transparency:</strong> Decision processes must be explainable.</li>
            <li><strong>Accountability:</strong> Clear liability for AI-caused harms.</li>
        </ul>
        <h2>Implementation Strategy</h2>
        <p>The framework will be implemented through a multi-stakeholder approach
        involving government, industry, and civil society.</p>
    </body>
    </html>
    """


@pytest.fixture
async def sample_document(db_session: AsyncSession, sample_text_document: str) -> Document:
    """Create a sample document in the database."""
    source = Source(
        source_type="upload",
        title="Test Source"
    )
    db_session.add(source)
    await db_session.flush()

    doc = Document(
        source_id=source.id,
        title="Test AI Policy Document",
        content_type="text/plain",
        raw_content=sample_text_document,
        processing_status="pending",
        is_in_knowledge_base=True
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def indexed_document(
    db_session: AsyncSession,
    sample_text_document: str,
    mock_embedding_client: MagicMock
) -> AsyncGenerator[Document, None]:
    """Create a fully indexed document with chunks and embeddings."""
    # Create source
    source = Source(
        source_type="upload",
        title="Test Source"
    )
    db_session.add(source)
    await db_session.flush()

    # Create document
    doc = Document(
        source_id=source.id,
        title="Indexed Test Document",
        content_type="text/plain",
        raw_content=sample_text_document,
        processing_status="indexed",
        is_in_knowledge_base=True
    )
    db_session.add(doc)
    await db_session.flush()

    # Create chunks with embeddings
    embedding = [0.1] * 768
    for i, text_part in enumerate([sample_text_document[i:i+500] for i in range(0, len(sample_text_document), 500)]):
        chunk = Chunk(
            document_id=doc.id,
            sequence=i,
            content=text_part,
            token_count=len(text_part.split()),
            embedding=embedding,
            is_indexed=True
        )
        db_session.add(chunk)

    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def document_processor(db_session: AsyncSession, mock_embedding_client: MagicMock) -> AsyncGenerator[DocumentProcessor, None]:
    """Create a DocumentProcessor instance with mocked dependencies."""
    yield DocumentProcessor(db_session, mock_embedding_client)


@pytest.fixture
async def knowledge_base_service(
    db_session: AsyncSession,
    mock_embedding_client: MagicMock
) -> AsyncGenerator[KnowledgeBaseService, None]:
    """Create a KnowledgeBaseService instance with mocked dependencies."""
    yield KnowledgeBaseService(db_session, mock_embedding_client)
