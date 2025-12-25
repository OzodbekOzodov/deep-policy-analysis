import time
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import google.generativeai as genai
from openai import AsyncOpenAI
import google.api_core.exceptions

from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients based on provider
openai_client: Optional[AsyncOpenAI] = None
gemini_configured: bool = False

# Configure Gemini if using Gemini
if settings.is_gemini or settings.provider == "gemini":
    genai.configure(api_key=settings.api_key)
    gemini_configured = True
    logger.info(f"Configured Gemini provider with model: {settings.default_model or settings.gemini_default_model}")

# Configure OpenAI-compatible client if using OpenAI-compatible provider
if settings.is_openai_compatible:
    openai_client = AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        # Add default headers required by OpenRouter
        default_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Deep Policy Analyst"
        }
    )
    logger.info(f"Configured OpenAI-compatible provider ({settings.provider}) with model: {settings.default_model}")

app = FastAPI(title="LLM Gateway Service")

# Data Models
class CompletionRequest(BaseModel):
    task: str
    prompt: str
    schema: Optional[Dict[str, Any]] = None
    temperature: float = 0.2
    max_tokens: int = 4000
    model: Optional[str] = None

class CompletionResponse(BaseModel):
    content: Union[str, Dict[str, Any]]
    model_used: str
    tokens: Dict[str, int]
    latency_ms: int
    request_id: str

class EmbeddingRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model_used: str
    tokens: int
    latency_ms: int

# Get the default model based on provider
def get_default_model() -> str:
    if settings.default_model:
        return settings.default_model
    if settings.provider == "gemini":
        return settings.gemini_default_model
    if settings.provider == "openai":
        return settings.openai_default_model
    if settings.provider == "anthropic":
        return settings.anthropic_default_model
    if settings.provider == "openrouter":
        return "openai/gpt-oss-120b:free"
    return settings.gemini_default_model

# Gemini generation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((
        google.api_core.exceptions.GoogleAPICallError,
        ConnectionError,
        TimeoutError
    ))
)
async def generate_gemini(request: CompletionRequest, request_id: str) -> CompletionResponse:
    start_time = time.perf_counter()
    model_name = request.model or get_default_model()

    generation_config = {
        "temperature": request.temperature,
        "max_output_tokens": request.max_tokens,
    }

    if request.schema:
        generation_config["response_mime_type"] = "application/json"
        generation_config["response_schema"] = request.schema

    model = genai.GenerativeModel(model_name)

    full_prompt = f"Task: {request.task}\n\n{request.prompt}"

    try:
        response = await model.generate_content_async(
            full_prompt,
            generation_config=generation_config
        )

        latency = int((time.perf_counter() - start_time) * 1000)

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata"):
             input_tokens = response.usage_metadata.prompt_token_count
             output_tokens = response.usage_metadata.candidates_token_count

        content = response.text
        if request.schema:
             import json
             try:
                 content = json.loads(content)
             except json.JSONDecodeError:
                 logger.error(f"Failed to decode JSON from Gemini: {content}")

        return CompletionResponse(
            content=content,
            model_used=model_name,
            tokens={"input": input_tokens, "output": output_tokens},
            latency_ms=latency,
            request_id=request_id
        )

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Gemini Error: {str(e)}")

# OpenAI-compatible generation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True
)
async def generate_openai_compatible(request: CompletionRequest, request_id: str) -> CompletionResponse:
    if not openai_client:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="OpenAI-compatible provider is not configured."
         )

    start_time = time.perf_counter()
    model_name = request.model or get_default_model()

    messages = [
        {"role": "system", "content": request.task},
        {"role": "user", "content": request.prompt}
    ]

    # Build extra body for OpenRouter-specific features
    extra_body = {}
    if settings.provider == "openrouter":
        # Enable reasoning for o1 models that support it
        if "o1" in model_name.lower() or "gpt-oss" in model_name.lower():
            extra_body["reasoning"] = {"enabled": True}

    params = {
        "model": model_name,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }

    # Only use JSON mode for providers that support it (not all custom providers)
    if request.schema and settings.provider != "custom":
        params["response_format"] = {"type": "json_object"}
        messages[-1]["content"] += "\n\nPlease respond in JSON matching the schema."
    elif request.schema:
        # For custom providers, just ask for JSON in the prompt
        messages[-1]["content"] += "\n\nPlease respond in valid JSON format matching the schema."

    try:
        response = await openai_client.chat.completions.create(
            **params,
            extra_body=extra_body if extra_body else None
        )
        latency = int((time.perf_counter() - start_time) * 1000)

        resp_content = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        content = resp_content
        if request.schema:
             import json
             try:
                 # Some providers return None when JSON mode is requested but not supported
                 if content is None:
                     logger.warning("Provider returned None content for JSON request, using empty dict")
                     content = {}
                 else:
                     content = json.loads(content)
             except (json.JSONDecodeError, TypeError) as e:
                 logger.error(f"Failed to decode JSON from OpenAI provider: {e}, content was: {repr(content)[:200]}")
                 # Return empty dict instead of failing
                 content = {}

        return CompletionResponse(
            content=content,
            model_used=model_name,
            tokens={"input": input_tokens, "output": output_tokens},
            latency_ms=latency,
            request_id=request_id
        )

    except Exception as e:
        logger.error(f"OpenAI compatible generation failed: {e}")
        # Log the full error for debugging
        import traceback
        logger.error(traceback.format_exc())
        raise

# Endpoints

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": settings.provider,
        "model": get_default_model(),
        "openai_client_active": openai_client is not None
    }

@app.post("/v1/complete", response_model=CompletionResponse)
async def complete(request: CompletionRequest):
    request_id = str(uuid.uuid4())
    logger.info(f"Complete request: task='{request.task[:50]}...' model='{request.model or get_default_model()}' provider='{settings.provider}'")

    # Route based on provider
    if settings.is_gemini or (not openai_client and settings.provider == "gemini"):
        return await generate_gemini(request, request_id)
    else:
        return await generate_openai_compatible(request, request_id)

@app.post("/v1/embed", response_model=EmbeddingResponse)
async def embed(request: EmbeddingRequest):
    start_time = time.perf_counter()
    model_name = request.model or settings.embedding_model

    # Use Gemini for embeddings (can be extended to support other providers)
    try:
        # Configure Gemini for embeddings if needed
        embedding_key = settings.embedding_api_key or settings.api_key
        if not gemini_configured or (settings.embedding_api_key and settings.embedding_api_key != settings.api_key):
            genai.configure(api_key=embedding_key)

        result = genai.embed_content(
            model=model_name,
            content=request.texts,
            task_type="retrieval_document"
        )

        embeddings = result['embedding']
        latency = int((time.perf_counter() - start_time) * 1000)
        tokens = 0

        return EmbeddingResponse(
             embeddings=embeddings,
             model_used=model_name,
             tokens=tokens,
             latency_ms=latency
        )

    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
