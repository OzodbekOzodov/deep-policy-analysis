"""Text Chunking Service for Document Ingestion"""

from __future__ import annotations

import re
from typing import List


def estimate_tokens(text: str) -> int:
    """
    Rough token count estimation.
    
    Uses the approximation of ~4 characters per token.
    """
    return len(text) // 4


class ChunkingService:
    """
    Split text into overlapping chunks for processing.
    
    Features:
    - Sentence-aware splitting (doesn't break mid-sentence)
    - Configurable chunk size and overlap
    - Token count estimation per chunk
    """
    
    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        """
        Initialize chunking service.
        
        Args:
            chunk_size: Target tokens per chunk (estimated)
            overlap: Overlap tokens between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        # Convert token target to character target (rough: 1 token ≈ 4 chars)
        self.char_size = chunk_size * 4
        self.char_overlap = overlap * 4
    
    def chunk_text(self, text: str) -> List[dict]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of chunk dictionaries with:
            - sequence: int (0-indexed)
            - content: str
            - token_count: int (estimated)
        """
        if not text or not text.strip():
            return []
        
        text = text.strip()
        
        # If text is small enough, return as single chunk
        if len(text) <= self.char_size:
            return [{
                "sequence": 0,
                "content": text,
                "token_count": estimate_tokens(text)
            }]
        
        chunks = []
        start = 0
        sequence = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.char_size
            
            if end >= len(text):
                # Last chunk
                chunk_text = text[start:]
            else:
                # Find a good break point (sentence boundary)
                chunk_text = text[start:end]
                break_point = self._find_break_point(chunk_text)
                
                if break_point > 0:
                    chunk_text = chunk_text[:break_point]
                    end = start + break_point
            
            chunk_text = chunk_text.strip()
            
            if chunk_text:
                chunks.append({
                    "sequence": sequence,
                    "content": chunk_text,
                    "token_count": estimate_tokens(chunk_text)
                })
                sequence += 1
            
            # Move start position, accounting for overlap
            if end >= len(text):
                break
            
            start = end - self.char_overlap
            # Ensure we don't go backwards
            if start <= (end - self.char_size):
                start = end - self.char_overlap // 2
        
        return chunks
    
    def _find_break_point(self, text: str) -> int:
        """
        Find the best break point in text (sentence or paragraph boundary).
        
        Looks backwards from the end of the text.
        """
        # Look for paragraph break first (double newline)
        last_para = text.rfind('\n\n')
        if last_para > len(text) * 0.5:  # Must be in second half
            return last_para + 2
        
        # Look for sentence ending (. ? ! followed by space or newline)
        sentence_pattern = r'[.!?][\s\n]'
        matches = list(re.finditer(sentence_pattern, text))
        
        # Find the last match in the second half of the text
        for match in reversed(matches):
            if match.end() > len(text) * 0.5:
                return match.end()
        
        # Look for any newline
        last_newline = text.rfind('\n')
        if last_newline > len(text) * 0.5:
            return last_newline + 1
        
        # No good break point found, just use the full length
        return 0
