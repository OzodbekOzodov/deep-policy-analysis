# Knowledge Base Tests

This directory contains comprehensive tests for the Knowledge Base pipeline, including document processing, API endpoints, and query expansion.

## Test Structure

```
tests/
├── __init__.py                  # Test package initialization
├── conftest.py                  # Pytest fixtures and configuration
├── test_document_processor.py   # Document processing pipeline tests
├── test_knowledge_api.py        # HTTP API endpoint tests
└── test_query_expansion.py      # Query expansion service tests
```

## Test Coverage

### test_document_processor.py
Tests the complete document processing pipeline:
- HTML tag stripping
- Document validation (size, content type)
- Content parsing (plain text, HTML, PDF)
- Chunking and embedding generation
- End-to-end processing with retry logic
- Knowledge base service operations

### test_knowledge_api.py
Tests the HTTP API endpoints:
- `POST /api/knowledge/documents` - Upload documents (text, files, PDF, HTML)
- `POST /api/knowledge/process` - Process pending documents
- `POST /api/knowledge/retry-failed` - Retry failed documents
- `GET /api/knowledge/documents` - List documents by status
- `GET /api/knowledge/stats` - Get knowledge base statistics
- `POST /api/knowledge/search` - Semantic vector search
- `POST /api/knowledge/expand` - Query expansion

### test_query_expansion.py
Tests the query expansion service:
- Query expansion generation
- Caching mechanism
- Case-insensitive cache lookup
- Error handling and fallbacks
- SHA256 hash generation for cache keys

## Setup

### 1. Install Test Dependencies

```bash
cd backend
source venv/bin/activate
pip install -r requirements-test.txt
```

### 2. Create Test Database

```bash
# Create test database
createdb dap_test

# Or with psql
psql postgres -c "CREATE DATABASE dap_test;"

# Enable pgvector extension
psql dap_test -c "CREATE EXTENSION vector;"
```

### 3. Set Environment Variables (Optional)

```bash
# Override test database URL if different
export TEST_DATABASE_URL="postgresql+asyncpg://localhost/dap_test"
```

## Running Tests

### Run All Tests

```bash
cd backend
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_document_processor.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_knowledge_api.py::TestUploadDocument -v
```

### Run Specific Test

```bash
pytest tests/test_document_processor.py::TestDocumentProcessor::test_process_document_success -v
```

### Run with Coverage

```bash
# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Run Only Tests Matching a Pattern

```bash
# Run only tests with "upload" in the name
pytest tests/ -k upload -v

# Run only tests with "expand" in the name
pytest tests/ -k expand -v
```

## Test Fixtures

The `conftest.py` file provides the following fixtures:

### Database Fixtures
- `db_session` - Fresh database session for each test
- `engine` - Test database engine

### Client Fixtures
- `http_client` - Async HTTP client for testing API endpoints
- `mock_embedding_client` - Mocked embedding client
- `mock_llm_client` - Mocked LLM client

### Content Fixtures
- `sample_text_document` - Sample plain text content
- `sample_html_document` - Sample HTML document
- `sample_pdf_bytes` - Sample PDF file bytes
- `sample_pdf_base64` - Sample PDF as base64 string

### Database Record Fixtures
- `sample_document` - Pending document in database
- `indexed_document` - Fully indexed document with chunks

### Service Fixtures
- `document_processor` - DocumentProcessor instance with mocked deps
- `knowledge_base_service` - KnowledgeBaseService instance

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: dap_test
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=app
```

## Writing New Tests

### Example: Testing a New Endpoint

```python
class TestNewEndpoint:
    """Tests for the new endpoint."""

    @pytest.mark.asyncio
    async def test_new_endpoint_success(
        self,
        http_client: AsyncClient
    ):
        """Test successful call to new endpoint."""
        response = await http_client.post("/api/new", json={"key": "value"})

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "expected"

    @pytest.mark.asyncio
    async def test_new_endpoint_validation_error(
        self,
        http_client: AsyncClient
    ):
        """Test validation error handling."""
        response = await http_client.post("/api/new", json={})

        assert response.status_code == 422
```

### Example: Testing a New Service Method

```python
class TestNewService:
    """Tests for the new service."""

    @pytest.mark.asyncio
    async def test_service_method(
        self,
        db_session: AsyncSession
    ):
        """Test service method execution."""
        # Arrange
        service = NewService(db_session)

        # Act
        result = await service.do_something()

        # Assert
        assert result is not None
        assert result.status == "success"
```

## Debugging Tests

### Run with Python Debugger

```bash
pytest tests/test_document_processor.py::TestDocumentProcessor::test_process_document_success --pdb
```

### Show Print Output

```bash
pytest tests/ -v -s
```

### Stop on First Failure

```bash
pytest tests/ -v -x
```

### Run Last Failed Tests

```bash
pytest tests/ --lf
```

## Troubleshooting

### Database Connection Error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:** Ensure PostgreSQL is running and the test database exists:
```bash
brew services start postgresql@17
createdb dap_test
psql dap_test -c "CREATE EXTENSION vector;"
```

### Import Errors

```
ModuleNotFoundError: No module named 'app'
```

**Solution:** Ensure you're running tests from the `backend` directory:
```bash
cd backend
pytest tests/
```

### Async Test Errors

```
RuntimeError: Task attached to a different loop
```

**Solution:** Tests use the `event_loop` fixture. Ensure you're using `@pytest.mark.asyncio` decorator.

### pgvector Extension Error

```
type "vector" does not exist
```

**Solution:** Enable the pgvector extension:
```bash
psql dap_test -c "CREATE EXTENSION vector;"
```

## Test Philosophy

These tests follow these principles:

1. **Isolation** - Each test is independent and can run in any order
2. **Speed** - Tests use mocked external services (LLM, embeddings)
3. **Clarity** - Test names clearly describe what is being tested
4. **Coverage** - Tests cover happy path, edge cases, and error conditions
5. **Maintainability** - Fixtures reduce duplication and make tests readable

## Contributing

When adding new features:

1. Write tests first (TDD) or alongside implementation
2. Ensure all tests pass before submitting
3. Add tests for edge cases and error conditions
4. Update this README if adding new test files or fixtures
