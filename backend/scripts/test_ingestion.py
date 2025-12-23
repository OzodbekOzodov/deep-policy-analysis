import asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.clients.llm import EmbeddingClient
from app.services.ingestion import IngestionService, ChunkingService
from app.config import get_settings
from app.models.database import Base

settings = get_settings()

SAMPLE_TEXT = """
The Ministry of Defense announced a new cybersecurity policy yesterday. 
This policy aims to protect critical infrastructure from foreign threats.
The initiative comes after several high-profile breaches last year.

Officials stated that the policy will require all government contractors 
to implement enhanced security measures within 90 days. Failure to comply 
could result in contract termination.

The opposition party criticized the policy as too expensive and potentially 
harmful to small businesses. They called for a longer implementation period.

Analysts believe this could increase defense spending by 15% over the next 
fiscal year, creating risks for the budget deficit.
"""

async def test_chunking():
    chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_text(SAMPLE_TEXT)
    print(f"Created {len(chunks)} chunks:")
    for c in chunks:
        print(f"  [{c['sequence']}] {c['token_count']} tokens: {c['content'][:50]}...")

async def test_full_ingestion():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        embedding_client = EmbeddingClient(base_url=settings.llm_gateway_url)
        service = IngestionService(db, embedding_client)
        
        # Create a dummy analysis first
        from app.models.database import AnalysisJob
        job = AnalysisJob(query="Test query", status="created")
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        try:
            # Ingest
            result = await service.ingest_text(
                text=SAMPLE_TEXT,
                analysis_id=job.id,
                title="Test Document"
            )
            
            print(f"Ingestion result: {result}")
            await db.commit() # Commit transaction
            
            # Verify chunks have embeddings
            from sqlalchemy import select, func
            from app.models.database import Chunk
            
            count = await db.scalar(
                select(func.count()).where(
                    Chunk.analysis_id == job.id,
                    Chunk.embedding.isnot(None)
                )
            )
            print(f"Chunks with embeddings: {count}")
            
        finally:
            await embedding_client.close()

if __name__ == "__main__":
    print("=== Testing Chunking ===")
    asyncio.run(test_chunking())
    print("\n=== Testing Full Ingestion ===")
    asyncio.run(test_full_ingestion())
