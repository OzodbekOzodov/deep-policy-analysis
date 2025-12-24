"""APOR Entity Extraction Service"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Any
from uuid import uuid4

from app.clients.llm import LLMClient, get_llm_client
from app.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    ENTITY_TYPE_PROMPTS,
    EXTRACT_RELATIONSHIPS_PROMPT,
    ENTITY_SCHEMA,
    RELATIONSHIP_SCHEMA,
)

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Multi-pass APOR entity extraction service.
    
    Extracts Actors, Policies, Outcomes, and Risks from text chunks
    using parallel LLM calls, then extracts relationships between entities.
    """
    
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or get_llm_client()
    
    async def extract_from_chunk(self, chunk_text: str, chunk_id: str) -> Dict[str, Any]:
        """
        Multi-pass extraction from a single chunk.
        
        Steps:
        1. Extract actors, policies, outcomes, risks in parallel
        2. Extract relationships using all found entities
        
        Args:
            chunk_text: Text content of the chunk
            chunk_id: Unique identifier for the chunk
            
        Returns:
            {
                "chunk_id": str,
                "entities": [{"temp_id": str, "type": str, "label": str, "confidence": int, "quote": str, "aliases": list}],
                "relationships": [{"source": str, "target": str, "relationship": str, "confidence": int}]
            }
        """
        # Step 1: Extract entities in parallel
        entity_tasks = [
            self._extract_type(chunk_text, entity_type, prompt)
            for entity_type, prompt in ENTITY_TYPE_PROMPTS.items()
        ]
        
        results = await asyncio.gather(*entity_tasks, return_exceptions=True)
        
        # Collect all entities
        all_entities = []
        type_counters = {"actor": 0, "policy": 0, "outcome": 0, "risk": 0}
        
        for entity_type, result in zip(ENTITY_TYPE_PROMPTS.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Extraction failed for {entity_type}: {result}")
                continue
            
            for entity in result:
                temp_id = f"{entity_type}_{type_counters[entity_type]}"
                type_counters[entity_type] += 1
                
                all_entities.append({
                    "temp_id": temp_id,
                    "type": entity_type,
                    "label": entity.get("label", "Unknown"),
                    "confidence": entity.get("confidence", 50),
                    "quote": entity.get("quote", ""),
                    "aliases": entity.get("aliases", [])
                })
        
        # Step 2: Extract relationships if we have entities
        relationships = []
        if len(all_entities) >= 2:
            try:
                relationships = await self._extract_relationships(chunk_text, all_entities)
            except Exception as e:
                logger.error(f"Relationship extraction failed: {e}")
        
        return {
            "chunk_id": chunk_id,
            "entities": all_entities,
            "relationships": relationships
        }
    
    async def _extract_type(self, text: str, entity_type: str, prompt: str) -> List[Dict]:
        """Extract entities of one type from text."""
        formatted_prompt = prompt.format(text=text)
        
        try:
            # Prepend system prompt to the user prompt since complete() doesn't accept system_prompt
            full_prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{formatted_prompt}"
            result = await self.llm.complete(
                prompt=full_prompt,
                schema=ENTITY_SCHEMA,
                temperature=0.1  # Low temperature for extraction
            )
            
            if isinstance(result, dict) and "entities" in result:
                return result["entities"]
            return []
            
        except Exception as e:
            logger.error(f"Failed to extract {entity_type}: {e}")
            return []
    
    async def _extract_relationships(self, text: str, entities: List[Dict]) -> List[Dict]:
        """Extract relationships between found entities."""
        # Format entities for prompt
        entities_text = "\n".join([
            f"- {e['label']} ({e['type']})"
            for e in entities
        ])
        
        formatted_prompt = EXTRACT_RELATIONSHIPS_PROMPT.format(
            text=text,
            entities=entities_text
        )
        
        try:
            # Prepend system prompt to the user prompt since complete() doesn't accept system_prompt
            full_prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\n{formatted_prompt}"
            result = await self.llm.complete(
                prompt=full_prompt,
                schema=RELATIONSHIP_SCHEMA,
                temperature=0.1
            )
            
            if isinstance(result, dict) and "relationships" in result:
                return result["relationships"]
            return []
            
        except Exception as e:
            logger.error(f"Failed to extract relationships: {e}")
            return []


# Convenience function
async def extract_from_chunk(chunk_text: str, chunk_id: str) -> Dict[str, Any]:
    """Convenience function for chunk extraction."""
    service = ExtractionService()
    return await service.extract_from_chunk(chunk_text, chunk_id)
