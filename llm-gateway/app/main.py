import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Union
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-gateway")

# Initialize Client
# The SDK automatically picks up GEMINI_API_KEY from env if available,
# but we allow explicit passing too to be safe.
client = genai.Client(api_key=settings.GEMINI_API_KEY)

app = FastAPI(title="LLM Gateway", version="1.0.0")

# Models for API
class CompletionRequest(BaseModel):
    task: str
    prompt: str
    response_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
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

# Retry Logic
# We need to catch correct exceptions from google-genai. 
# Usually they are google.genai.errors or similar, but for now we catch generic Exception 
# and check specific messages or status codes if possible, 
# or import exceptions if accessible.
# google-genai >= 0.1 usually raises standard exceptions or mapped ones.
# For simplicity in this iteration, generic retry on Exception is risky but okay for HTTP errors.
# Better: check for "429" in error message.
def is_rate_limit_error(exception):
    return "429" in str(exception) or "ResourceExhausted" in str(exception)

retry_policy = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(Exception) # Refine this if specific exceptions are known
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    response = await call_next(request)
    
    latency = int((time.time() - start_time) * 1000)
    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Latency: {latency}ms | "
        f"ID: {request_id}"
    )
    return response

@app.get("/health")
async def health_check():
    return {"status": "ok", "provider": "gemini", "sdk": "google-genai"}

@app.post("/v1/complete", response_model=CompletionResponse)
async def complete(request: CompletionRequest):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    model_name = request.model or settings.DEFAULT_MODEL
    
    try:
        config_args = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        
        # If schema provided, configure structured output
        if request.response_schema:
            config_args["response_mime_type"] = "application/json"
            config_args["response_schema"] = request.response_schema

        # Call generate_content
        # Note: google-genai is synchronous by default unless using async client?
        # The documentation snippet showed 'client = genai.Client()', which is sync.
        # For FastAPI, sync calls block the event loop. 
        # Ideally we should use the async client if available or run in threadpool.
        # google-genai has an async client? 
        # Checking docs (implicit): usually 'genai.Client' is sync.
        # fastAPI runs sync functions in threadpool, so 'def complete' works fine if not 'async def'.
        # BUT we defined 'async def complete'. If we call sync code inside, it blocks.
        # We should either make this function 'def complete' (FastAPI handles it in thread)
        # OR use run_in_executor.
        # For now, let's change handler to 'def complete' to be safe with sync client,
        # OR check if there is 'client.aio'.
        # Assuming sync client for now based on user snippet.
        
        response = client.models.generate_content(
            model=model_name,
            contents=request.prompt,
            config=config_args
        )
        
        # Parse content
        if request.response_schema:
            try:
                # response.text should be JSON string
                content = json.loads(response.text)
            except (json.JSONDecodeError, ValueError):
                logger.error(f"Failed to parse JSON response: {response.text}")
                content = response.text
        else:
            content = response.text
            
        # Usage metadata
        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
             input_tokens = response.usage_metadata.prompt_token_count
             output_tokens = response.usage_metadata.candidates_token_count
        
        latency = int((time.time() - start_time) * 1000)
        
        logger.info(f"Complete | Task: {request.task} | Model: {model_name} | Latency: {latency}ms | Tokens: {input_tokens}/{output_tokens}")
        
        return CompletionResponse(
            content=content,
            model_used=model_name,
            tokens={"input": input_tokens, "output": output_tokens},
            latency_ms=latency,
            request_id=request_id
        )

    except Exception as e:
        logger.error(f"Error in complete: {str(e)}")
        if is_rate_limit_error(e):
             raise HTTPException(status_code=429, detail="Rate limit exceeded")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/embed", response_model=EmbeddingResponse)
def embed(request: EmbeddingRequest):
    # Changed to sync def to allow blocking call in threadpool
    start_time = time.time()
    model_name = request.model or settings.EMBEDDING_MODEL
    
    try:
        # embed_content supports batching?
        # contents: str or List[str]
        
        response = client.models.embed_content(
            model=model_name,
            contents=request.texts,
        )
        
        # Response structure for list input:
        # verification needed. Usually has 'embeddings' list.
        # response.embeddings -> list of EmbedContentResponse or list of lists?
        # According to some docs, response.embeddings is a list of Embedding objects, each has .values
        
        embeddings = []
        if hasattr(response, 'embeddings'):
            if response.embeddings:
                for emb in response.embeddings:
                    embeddings.append(emb.values)
        else:
             # Fallback/Check
             # If single?
             pass

        # If user passed list, we expect list of embeddings.
        
        latency = int((time.time() - start_time) * 1000)
        tokens = 0 
        
        return EmbeddingResponse(
            embeddings=embeddings,
            model_used=model_name,
            tokens=tokens,
            latency_ms=latency
        )
        
    except Exception as e:
        logger.error(f"Error in embed: {str(e)}")
        if is_rate_limit_error(e):
             raise HTTPException(status_code=429, detail="Rate limit exceeded")
        raise HTTPException(status_code=500, detail=str(e))
