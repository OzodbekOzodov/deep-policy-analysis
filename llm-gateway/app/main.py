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

# Configure Gemini
genai.configure(api_key=settings.gemini_api_key)

# Configure OpenAI (lazy initialization potential, but client is lightweight)
openai_client = None
if settings.openai_api_key:
    openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )

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

# Helpers
def is_gemini_model(model_name: str) -> bool:
    return "gemini" in model_name.lower()

# Logic
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
    model_name = request.model or settings.default_model
    
    generation_config = {
        "temperature": request.temperature,
        "max_output_tokens": request.max_tokens,
    }
    
    if request.schema:
        generation_config["response_mime_type"] = "application/json"
        generation_config["response_schema"] = request.schema
        
    model = genai.GenerativeModel(model_name)
    
    # Construct prompt. Task + Prompt usually.
    full_prompt = f"Task: {request.task}\n\n{request.prompt}"
    
    try:
        response = await model.generate_content_async(
            full_prompt,
            generation_config=generation_config
        )
        
        latency = int((time.perf_counter() - start_time) * 1000)
        
        # Token usage estimation (Gemini API provides usage_metadata access)
        # Note: python client 0.8.0 access might vary, usually response.usage_metadata
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
                 # Fallback to string if parsing fails, or could raise error
                 pass

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

# Logic
async def generate_openai_compatible(request: CompletionRequest, request_id: str) -> CompletionResponse:
    if not openai_client:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="OpenAI/Compatible provider is not configured (missing API key)."
         )
    return await _generate_openai_compatible_impl(request, request_id)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True
)
async def _generate_openai_compatible_impl(request: CompletionRequest, request_id: str) -> CompletionResponse:
    start_time = time.perf_counter()
    model_name = request.model 
    if not model_name:
         raise HTTPException(status_code=400, detail="Model name required for non-Gemini providers")

    messages = [
        {"role": "system", "content": request.task},
        {"role": "user", "content": request.prompt}
    ]
    
    params = {
        "model": model_name,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    
    if request.schema:
        params["response_format"] = {"type": "json_object"}
        messages[-1]["content"] += "\n\nPlease respond in JSON matching the schema."
    
    try:
        response = await openai_client.chat.completions.create(**params)
        latency = int((time.perf_counter() - start_time) * 1000)
        
        resp_content = response.choices[0].message.content
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        content = resp_content
        if request.schema:
             import json
             try:
                 content = json.loads(content)
             except json.JSONDecodeError:
                 logger.error("Failed to decode JSON from OpenAI provider")
                 pass

        return CompletionResponse(
            content=content,
            model_used=model_name,
            tokens={"input": input_tokens, "output": output_tokens},
            latency_ms=latency,
            request_id=request_id
        )

    except Exception as e:
        logger.error(f"OpenAI compatible generation failed: {e}")
        # Re-raise generic exceptions to trigger retry
        raise

# Endpoints

@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "provider": "gemini", 
        "openai_compatible": bool(openai_client)
    }

@app.post("/v1/complete", response_model=CompletionResponse)
async def complete(request: CompletionRequest):
    request_id = str(uuid.uuid4())
    model = request.model or settings.default_model
    
    if is_gemini_model(model):
        return await generate_gemini(request, request_id)
    else:
        return await generate_openai_compatible(request, request_id)

@app.post("/v1/embed", response_model=EmbeddingResponse)
async def embed(request: EmbeddingRequest):
    # Only supporting Gemini embeddings as per spec for now
    # Could expand later
    start_time = time.perf_counter()
    model_name = request.model or settings.embedding_model
    
    # Gemini embedding
    try:
        # batch processing
        result = genai.embed_content(
            model=model_name,
            content=request.texts,
            task_type="retrieval_document" # Defaulting for general use
        )
        
        # Result dict usually has 'embedding' key which is list of list if input is list
        embeddings = result['embedding']
        
        latency = int((time.perf_counter() - start_time) * 1000)
        
        # Token counting for embeddings is not always strictly returned in the same way
        # Rough estimate or 0 if unavailable
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
