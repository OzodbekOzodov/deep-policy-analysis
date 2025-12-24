import re
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Source, Document, Chunk
from app.clients.llm import EmbeddingClient

class ChunkingService:
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Returns list of:
        {
            "sequence": int,       # 0-indexed position
            "content": str,        # chunk text
            "token_count": int     # estimated tokens
        }
        """
        # Simple splitting by sentence, then grouping
        # Split by ., !, ?, or newline followed by whitespace
        # This regex looks for sentence terminators.
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk_sentences = []
        current_chunk_tokens = 0
        sequence = 0
        
        for sentence in sentences:
            if not sentence:
                continue
            
            token_count = self.estimate_tokens(sentence)
            
            # If a single sentence is bigger than chunk size, we force split it (naive)
            # For now, simplistic approach: allow it to overflow if it's one huge sentence,
            # or we could split words. Let's start with simple sentence accumulation.
            
            if current_chunk_tokens + token_count > self.chunk_size and current_chunk_sentences:
                # Close current chunk
                chunk_text = " ".join(current_chunk_sentences)
                chunks.append({
                    "sequence": sequence,
                    "content": chunk_text,
                    "token_count": self.estimate_tokens(chunk_text)
                })
                sequence += 1
                
                # Handle overlap: keep last N sentences that fit within overlap limit
                overlap_tokens = 0
                overlap_sentences = []
                for s in reversed(current_chunk_sentences):
                    s_tokens = self.estimate_tokens(s)
                    if overlap_tokens + s_tokens <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break
                
                current_chunk_sentences = overlap_sentences
                current_chunk_tokens = overlap_tokens
            
            current_chunk_sentences.append(sentence)
            current_chunk_tokens += token_count
            
        # Add last chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append({
                "sequence": sequence,
                "content": chunk_text,
                "token_count": self.estimate_tokens(chunk_text)
            })
            
        return chunks

class IngestionService:
    def __init__(self, db: AsyncSession, embedding_client: EmbeddingClient):
        self.db = db
        self.embedding_client = embedding_client
        self.chunker = ChunkingService()
    
    async def ingest_text(
        self,
        text: str,
        analysis_id: UUID,
        title: Optional[str] = None,
        source_type: str = "paste"
    ) -> Dict[str, Any]:
        """
        Full ingestion pipeline:
        1. Create source record
        2. Create document record
        3. Chunk text
        4. Generate embeddings for all chunks (batch)
        5. Store chunks with embeddings
        6. Mark chunks as indexed
        
        Returns:
        {
            "source_id": UUID,
            "document_id": UUID,
            "chunks_created": int,
            "tokens_total": int
        }
        """
        # 1. Create Source
        source = await self._create_source(source_type, title)
        
        # 2. Create Document
        document = await self._create_document(source.id, analysis_id, text, title)
        
        # 3. Chunk Text
        chunks_data = self.chunker.chunk_text(text)
        
        # 4. Generate Embeddings (Batched)
        chunk_texts = [c["content"] for c in chunks_data]
        embeddings = await self.embedding_client.embed(chunk_texts)
        
        if len(embeddings) != len(chunks_data):
            raise ValueError(f"Mismatch in embeddings count: chunks={len(chunks_data)}, embeddings={len(embeddings)}")
            
        # 5. Store Chunks
        chunks_count = await self._store_chunks_with_embeddings(document.id, analysis_id, chunks_data, embeddings)
        
        # Update document token count (Note: tokens field doesn't exist on Document model, skipping)
        total_tokens = sum(c["token_count"] for c in chunks_data)
        await self.db.flush()
        
        return {
            "source_id": source.id,
            "document_id": document.id,
            "chunks_created": chunks_count,
            "tokens_total": total_tokens
        }
    
    async def _create_source(self, source_type: str, title: Optional[str]) -> Source:
        source = Source(
            source_type=source_type,
            title=title or "Untitled Source"
        )
        self.db.add(source)
        await self.db.flush()
        await self.db.refresh(source)
        return source
    
    async def _create_document(
        self, 
        source_id: UUID, 
        analysis_id: UUID,
        content: str,
        title: Optional[str]
    ) -> Document:
        document = Document(
            source_id=source_id,
            analysis_id=analysis_id,
            raw_content=content,
            title=title or "Untitled Document"
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document
    
    async def _store_chunks_with_embeddings(
        self,
        document_id: UUID,
        analysis_id: UUID,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> int:
        
        db_chunks = []
        for i, chunk_data in enumerate(chunks):
            chunk = Chunk(
                document_id=document_id,
                analysis_id=analysis_id,
                sequence=chunk_data["sequence"],
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                embedding=embeddings[i],
                is_indexed=True # We have embeddings, so indexed
            )
            db_chunks.append(chunk)
            
        self.db.add_all(db_chunks)
        await self.db.flush()
        return len(db_chunks)
