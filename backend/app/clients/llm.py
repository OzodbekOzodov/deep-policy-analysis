"""Generic LLM Client - Works with Gemini, Claude, OpenAI via env configuration"""

from __future__ import annotations

import json
import time
import logging
from typing import Optional, Union
import httpx
import google.generativeai as genai
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Generic LLM client that supports multiple providers.
    
    Configure via environment variables:
    - LLM_BASE_URL: API endpoint (used for OpenAI-compatible APIs)
    - LLM_API_KEY: API key for the provider
    - LLM_MODEL: Model name (e.g., gemini-2.5-flash, gpt-4, claude-opus)
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.base_url = base_url or settings.llm_base_url
        
        # Configure Gemini if using Google's API
        if "generativelanguage.googleapis.com" in self.base_url or "gemini" in self.model.lower():
            genai.configure(api_key=self.api_key)
            self._use_gemini = True
        else:
            self._use_gemini = False
            self._http_client = httpx.AsyncClient(timeout=60.0)
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
        max_retries: int = 3
    ) -> dict | str:
        """
        Generate completion from LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System instruction
            schema: JSON schema for structured output
            temperature: Sampling temperature
            max_tokens: Max output tokens
            max_retries: Number of retry attempts
            
        Returns:
            Parsed JSON if schema provided, otherwise raw text
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                if self._use_gemini:
                    result = await self._gemini_complete(
                        prompt, system_prompt, schema, temperature, max_tokens
                    )
                else:
                    result = await self._openai_compatible_complete(
                        prompt, system_prompt, schema, temperature, max_tokens
                    )
                
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"LLM call completed in {latency_ms}ms")
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await self._backoff(attempt)
        
        raise last_error
    
    async def _gemini_complete(
        self,
        prompt: str,
        system_prompt: Optional[str],
        schema: Optional[dict],
        temperature: float,
        max_tokens: int
    ) -> dict | str:
        """Use Google's Generative AI SDK."""
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt
        )
        
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        # Use structured output if schema provided
        if schema:
            generation_config.response_mime_type = "application/json"
            generation_config.response_schema = schema
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        text = response.text
        
        if schema:
            return json.loads(text)
        return text
    
    async def _openai_compatible_complete(
        self,
        prompt: str,
        system_prompt: Optional[str],
        schema: Optional[dict],
        temperature: float,
        max_tokens: int
    ) -> dict | str:
        """Use OpenAI-compatible API (works with OpenAI, Claude, etc.)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"schema": schema}
            }
        
        response = await self._http_client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        if schema:
            return json.loads(content)
        return content
    
    async def _backoff(self, attempt: int):
        """Exponential backoff between retries."""
        import asyncio
        delay = 2 ** attempt
        await asyncio.sleep(delay)


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
