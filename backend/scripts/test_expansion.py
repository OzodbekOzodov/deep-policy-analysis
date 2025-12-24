"""Test script for Query Expansion Service"""

import asyncio
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.clients.llm import LLMClient
from app.services.expansion import QueryExpansionService
from app.config import get_settings

settings = get_settings()


async def test_expansion():
    """Test query expansion with caching."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    llm = LLMClient(settings.llm_gateway_url)
    
    async with async_session() as db:
        service = QueryExpansionService(llm, db)
        
        query = "China semiconductor policy impact"
        
        print(f"Original query: {query}")
        print("Expanding...")
        
        start = time.time()
        expansions = await service.expand_query(query, num_expansions=15)
        first_elapsed = time.time() - start
        
        print(f"\nGenerated {len(expansions)} expansions in {first_elapsed:.2f}s:")
        for i, exp in enumerate(expansions, 1):
            print(f"  {i}. {exp}")
        
        # Test caching - second call should be instant
        print("\nTesting cache (second call)...")
        start = time.time()
        cached_expansions = await service.expand_query(query)
        cache_elapsed = time.time() - start
        
        print(f"Cache retrieval took {cache_elapsed:.3f}s")
        print(f"Same results: {expansions == cached_expansions}")
        
        if cache_elapsed < 0.1:
            print("✅ Caching is working correctly!")
        else:
            print("⚠️ Cache may not be working as expected")
    
    await llm.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_expansion())
