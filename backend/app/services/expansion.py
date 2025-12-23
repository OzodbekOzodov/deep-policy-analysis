"""Query Expansion Service

Expands short user queries into multiple search variations for better retrieval coverage.
Uses LLM to generate expansions with caching in the database.
"""

import hashlib
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.clients.llm import LLMClient
from app.models.database import QueryExpansion
from app.prompts.expansion import EXPANSION_PROMPT, EXPANSION_SCHEMA

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """Service for expanding user queries into multiple search variations."""
    
    def __init__(self, llm_client: LLMClient, db: AsyncSession):
        self.llm = llm_client
        self.db = db
    
    async def expand_query(self, query: str, num_expansions: int = 15) -> list[str]:
        """
        Expand a user query into multiple search variations.
        
        1. Check cache (query_expansions table) for existing expansion
        2. If cached, return cached expansions
        3. If not cached:
           a. Call LLM to generate expansions
           b. Cache result in database
           c. Return expansions
        
        Returns list of query strings including the original.
        """
        # Check cache first
        cached = await self._get_cached(query)
        if cached is not None:
            logger.info(f"Query expansion cache hit for: {query[:50]}...")
            return cached
        
        # Generate new expansions
        logger.info(f"Generating expansions for: {query[:50]}...")
        expansions = await self._generate_expansions(query, num_expansions)
        
        # Always include original query
        if query not in expansions:
            expansions = [query] + expansions
        
        # Cache for future use
        await self._cache_expansions(query, expansions)
        
        return expansions
    
    async def _get_cached(self, query: str) -> Optional[list[str]]:
        """Check query_expansions table for cached result."""
        query_hash = self._hash_query(query)
        
        result = await self.db.execute(
            select(QueryExpansion).where(QueryExpansion.query_hash == query_hash)
        )
        cached = result.scalar_one_or_none()
        
        if cached:
            return cached.expansions
        return None
    
    async def _cache_expansions(self, query: str, expansions: list[str]) -> None:
        """Store expansions in query_expansions table."""
        query_hash = self._hash_query(query)
        
        expansion_record = QueryExpansion(
            original_query=query,
            query_hash=query_hash,
            expansions=expansions
        )
        
        self.db.add(expansion_record)
        await self.db.commit()
        logger.info(f"Cached {len(expansions)} expansions for query hash: {query_hash[:16]}...")
    
    def _hash_query(self, query: str) -> str:
        """SHA256 hash of normalized query for cache lookup."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    async def _generate_expansions(self, query: str, num_expansions: int) -> list[str]:
        """Call LLM to generate query expansions."""
        prompt = EXPANSION_PROMPT.format(
            query=query,
            num_expansions=num_expansions
        )
        
        try:
            result = await self.llm.complete(
                prompt=prompt,
                task="expansion",
                schema=EXPANSION_SCHEMA,
                temperature=0.7  # Higher for creativity
            )
            
            expansions = result.get("expansions", [])
            logger.info(f"LLM generated {len(expansions)} expansions")
            return expansions
            
        except Exception as e:
            logger.error(f"Failed to generate expansions: {e}")
            # Return just the original query on failure
            return [query]
