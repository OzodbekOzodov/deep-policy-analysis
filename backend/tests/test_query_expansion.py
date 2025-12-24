"""Tests for the Query Expansion Service.

Tests the query expansion module which:
- Expands short user queries into multiple search variations
- Uses LLM to generate expansions
- Caches results in the database
- Improves retrieval coverage
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.models.database import QueryExpansion
from app.services.expansion import QueryExpansionService


# =============================================================================
# QueryExpansionService Tests
# =============================================================================

class TestQueryExpansionService:
    """Tests for the QueryExpansionService class."""

    # =========================================================================
    # Basic Expansion Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_expand_query_generates_expansions(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that query expansion generates multiple variations."""
        service = QueryExpansionService(mock_llm_client, db_session)

        expansions = await service.expand_query("AI policy", num_expansions=5)

        # Should return at least the original query
        assert len(expansions) >= 1
        assert "AI policy" in expansions

    @pytest.mark.asyncio
    async def test_expand_query_includes_original(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that the original query is always included."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Mock that returns expansions without the original
        async def mock_complete(prompt, **kwargs):
            return """{"expansions": [
                "artificial intelligence policy",
                "machine learning governance",
                "algorithmic regulation"
            ]}"""

        mock_llm_client.complete = AsyncMock(side_effect=mock_complete)

        expansions = await service.expand_query("AI policy", num_expansions=3)

        # Original should be prepended
        assert "AI policy" in expansions
        assert expansions[0] == "AI policy"

    @pytest.mark.asyncio
    async def test_expand_query_with_custom_count(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test expansion with custom number of variations."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Mock to return exact count
        async def mock_complete(prompt, **kwargs):
            num = kwargs.get("num_expansions", 5)
            expansions = [f"expansion_{i}" for i in range(num)]
            return f'{{"expansions": {expansions}}}'

        mock_llm_client.complete = AsyncMock(side_effect=mock_complete)

        expansions = await service.expand_query("test", num_expansions=10)

        # Should have at least the requested number (plus original)
        assert len(expansions) >= 10

    # =========================================================================
    # Caching Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_expand_query_caches_result(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that expansions are cached in the database."""
        service = QueryExpansionService(mock_llm_client, db_session)

        query = "climate change policy"
        await service.expand_query(query, num_expansions=5)

        # Check database for cached entry
        result = await db_session.execute(
            select(QueryExpansion).where(
                QueryExpansion.original_query == query
            )
        )
        cached = result.scalar_one_or_none()

        assert cached is not None
        assert cached.original_query == query
        assert len(cached.expansions) > 0

    @pytest.mark.asyncio
    async def test_expand_query_returns_cached(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that cached expansions are returned without LLM call."""
        service = QueryExpansionService(mock_llm_client, db_session)

        query = "economic sanctions"
        first_expansions = await service.expand_query(query, num_expansions=5)

        # Reset mock to track new calls
        mock_llm_client.complete.reset_mock()

        # Second call should use cache
        second_expansions = await service.expand_query(query, num_expansions=5)

        # LLM should not be called again
        mock_llm_client.complete.assert_not_called()

        # Should return same expansions
        assert first_expansions == second_expansions

    @pytest.mark.asyncio
    async def test_expand_query_case_insensitive_cache(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that cache is case-insensitive."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # First call with lowercase
        await service.expand_query("AI policy", num_expansions=3)
        mock_llm_client.complete.reset_mock()

        # Second call with different case should hit cache
        await service.expand_query("ai POLICY", num_expansions=3)

        # Should not call LLM again
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_stores_query_hash(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that cache stores SHA256 hash of normalized query."""
        service = QueryExpansionService(mock_llm_client, db_session)

        query = "Test Query"
        await service.expand_query(query, num_expansions=3)

        # Calculate expected hash
        expected_hash = hashlib.sha256(
            query.lower().strip().encode()
        ).hexdigest()

        # Verify hash in database
        result = await db_session.execute(
            select(QueryExpansion).where(
                QueryExpansion.query_hash == expected_hash
            )
        )
        cached = result.scalar_one_or_none()

        assert cached is not None
        assert cached.query_hash == expected_hash

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_expand_query_llm_failure_fallback(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that LLM failure falls back to original query."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Mock LLM failure
        mock_llm_client.complete = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        expansions = await service.expand_query("test query", num_expansions=5)

        # Should return just the original query
        assert expansions == ["test query"]

    @pytest.mark.asyncio
    async def test_expand_query_malformed_llm_response(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test handling of malformed LLM response."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Mock returns invalid JSON
        mock_llm_client.complete = AsyncMock(return_value="not valid json")

        expansions = await service.expand_query("test", num_expansions=5)

        # Should gracefully handle and return original
        assert "test" in expansions

    @pytest.mark.asyncio
    async def test_expand_query_empty_llm_expansions(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test handling when LLM returns empty expansions."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Mock returns empty list
        async def mock_complete(prompt, **kwargs):
            return '{"expansions": []}'

        mock_llm_client.complete = AsyncMock(side_effect=mock_complete)

        expansions = await service.expand_query("test", num_expansions=5)

        # Should still include original query
        assert "test" in expansions

    # =========================================================================
    # Hash Function Tests
    # =========================================================================

    def test_hash_query_normalizes_input(self):
        """Test that query hashing normalizes the input."""
        service = QueryExpansionService(MagicMock(), MagicMock())

        query1 = "  Test Query  "
        query2 = "test query"
        query3 = "TEST QUERY"

        hash1 = service._hash_query(query1)
        hash2 = service._hash_query(query2)
        hash3 = service._hash_query(query3)

        # All should produce same hash
        assert hash1 == hash2 == hash3

    def test_hash_query_different_queries_produce_different_hashes(self):
        """Test that different queries produce different hashes."""
        service = QueryExpansionService(MagicMock(), MagicMock())

        hash1 = service._hash_query("query one")
        hash2 = service._hash_query("query two")

        assert hash1 != hash2

    def test_hash_query_uses_sha256(self):
        """Test that hash is SHA256 (64 hex characters)."""
        service = QueryExpansionService(MagicMock(), MagicMock())

        hash_value = service._hash_query("test query")

        # SHA256 produces 64 hex characters
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    # =========================================================================
    # Integration Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_multiple_queries_cached_independently(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that different queries are cached independently."""
        service = QueryExpansionService(mock_llm_client, db_session)

        queries = ["query one", "query two", "query three"]

        for query in queries:
            await service.expand_query(query, num_expansions=3)

        # Check all are cached
        result = await db_session.execute(select(QueryExpansion))
        all_cached = result.scalars().all()

        assert len(all_cached) == len(queries)

    @pytest.mark.asyncio
    async def test_cache_survives_service_recreation(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that cache persists across service instances."""
        # First service instance
        service1 = QueryExpansionService(mock_llm_client, db_session)
        query = "persistent query"
        expansions1 = await service1.expand_query(query, num_expansions=3)

        # Create new service instance
        service2 = QueryExpansionService(mock_llm_client, db_session)
        mock_llm_client.complete.reset_mock()

        # Should use cache from previous instance
        expansions2 = await service2.expand_query(query, num_expansions=3)

        mock_llm_client.complete.assert_not_called()
        assert expansions1 == expansions2

    @pytest.mark.asyncio
    async def test_expansion_with_varied_query_types(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test expansion with different query types."""
        service = QueryExpansionService(mock_llm_client, db_session)

        # Test various query types
        queries = [
            "short",           # Single word
            "two words",       # Simple phrase
            "complex policy question about AI and machine learning",  # Long
            "COVID-19",        # With special characters
            "US-China trade",  # With hyphen
        ]

        for query in queries:
            expansions = await service.expand_query(query, num_expansions=3)
            assert query in expansions
            assert len(expansions) >= 1


# =============================================================================
# Query Expansion LLM Prompt Tests
# =============================================================================

class TestExpansionPrompt:
    """Tests for the expansion prompt and schema."""

    @pytest.mark.asyncio
    async def test_expansion_prompt_formatting(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that the expansion prompt is properly formatted."""
        service = QueryExpansionService(mock_llm_client, db_session)

        query = "climate policy"
        num = 10

        # Track what prompt is sent
        captured_prompt = None

        async def capture_prompt(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return '{"expansions": ["test"]}'

        mock_llm_client.complete = AsyncMock(side_effect=capture_prompt)

        await service.expand_query(query, num_expansions=num)

        # Verify prompt contains key elements
        assert captured_prompt is not None
        assert query.lower() in captured_prompt.lower()

    @pytest.mark.asyncio
    async def test_llm_called_with_correct_parameters(
        self,
        db_session,
        mock_llm_client: MagicMock
    ):
        """Test that LLM is called with expected parameters."""
        service = QueryExpansionService(mock_llm_client, db_session)

        await service.expand_query("test query", num_expansions=7)

        # Verify LLM was called
        assert mock_llm_client.complete.called

        # Check call arguments
        call_kwargs = mock_llm_client.complete.call_args[1]

        # Should have schema parameter
        assert "schema" in call_kwargs

        # Temperature should be set for creativity
        assert call_kwargs.get("temperature") == 0.7
