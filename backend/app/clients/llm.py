import httpx
import logging
from typing import List, Dict, Any, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.clients.exceptions import LLMConnectionError, LLMResponseError

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, LLMConnectionError))
    )
    async def complete(
        self,
        prompt: str,
        task: str = "general",
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        model: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Call LLM Gateway for completion.
        Returns parsed content (dict if schema provided, str otherwise).
        Raises on failure after retries exhausted.
        """
        url = f"{self.base_url}/v1/complete"
        payload = {
            "task": task,
            "prompt": prompt,
            "schema": schema,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "model": model
        }
        
        try:
            logger.info(f"LLM Request: task='{task}' model='{model}' schema={bool(schema)}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"LLM Response: success model_used='{data.get('model_used')}' latency={data.get('latency_ms')}ms")
            return data["content"]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM Client Response Error: {e.response.text}")
            raise LLMResponseError(f"Gateway returned {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM Client Connection Error: {e}")
            raise LLMConnectionError(f"Failed to connect to Gateway: {e}") from e
    
    async def close(self):
        await self.client.aclose()

class EmbeddingClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, LLMConnectionError))
    )
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for list of texts.
        Returns list of vectors (1536 dimensions each or whatever the model returns).
        """
        url = f"{self.base_url}/v1/embed"
        payload = {
            "texts": texts
        }
        
        try:
            # logger.debug(f"Embedding Request: count={len(texts)}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            # logger.debug(f"Embedding Response: success latency={data.get('latency_ms')}ms")
            return data["embeddings"]
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Embedding Client Response Error: {e.response.text}")
            raise LLMResponseError(f"Gateway returned {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Embedding Client Connection Error: {e}")
            raise LLMConnectionError(f"Failed to connect to Gateway: {e}") from e

    async def embed_single(self, text: str) -> List[float]:
        """Convenience method for single text."""
        result = await self.embed([text])
        return result[0]

    async def close(self):
        await self.client.aclose()


# Helper functions for dependency injection
def get_llm_client() -> LLMClient:
    """Get LLM client instance."""
    return LLMClient()


def get_embedding_client() -> EmbeddingClient:
    """Get embedding client instance."""
    return EmbeddingClient()
