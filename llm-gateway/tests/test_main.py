import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import os
import sys

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.main import app, is_gemini_model
from app.config import settings

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["provider"] == "gemini"
    # openai_compatible might be false if no key is set in .env
    assert "openai_compatible" in response.json()

def test_is_gemini_model():
    assert is_gemini_model("gemini-1.5-flash")
    assert is_gemini_model("GEMINI-something")
    assert not is_gemini_model("gpt-4")
    assert not is_gemini_model("claude-3")

@patch("app.main.genai.GenerativeModel")
def test_complete_gemini_no_schema(mock_model_cls):
    # Mock
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hello there"
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    
    # Async mock for generate_content_async
    async_mock = AsyncMock(return_value=mock_response)
    mock_model.generate_content_async = async_mock
    mock_model_cls.return_value = mock_model

    payload = {
        "task": "Greeting",
        "prompt": "Say hello",
        "model": "gemini-1.5-flash"
    }
    
    response = client.post("/v1/complete", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello there"
    assert data["model_used"] == "gemini-1.5-flash"
    assert data["tokens"]["input"] == 10
    assert data["tokens"]["output"] == 5

@patch("app.main.genai.GenerativeModel")
def test_complete_gemini_with_schema(mock_model_cls):
    # Mock
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"greeting": "Hello"}'
    
    async_mock = AsyncMock(return_value=mock_response)
    mock_model.generate_content_async = async_mock
    mock_model_cls.return_value = mock_model

    payload = {
        "task": "Greeting",
        "prompt": "Say hello in JSON",
        "model": "gemini-1.5-flash",
        "schema": {"type": "object", "properties": {"greeting": {"type": "string"}}}
    }
    
    response = client.post("/v1/complete", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == {"greeting": "Hello"}

@patch("app.main.genai.embed_content")
def test_embed_gemini(mock_embed):
    # Mock
    mock_embed.return_value = {'embedding': [[0.1, 0.2, 0.3]]}
    
    payload = {
        "texts": ["Hello world"],
        "model": "text-embedding-004"
    }
    
    response = client.post("/v1/embed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["embeddings"]) == 1
    assert data["embeddings"][0] == [0.1, 0.2, 0.3]

def test_openai_missing_key():
    # Attempt to use openai model without key configured (assuming test env doesn't have it)
    # Ideally checking how main.py handles it
    
    # Force settings to have no openai key for this test
    with patch("app.main.openai_client", None):
        payload = {
            "task": "test",
            "prompt": "test",
            "model": "gpt-4"
        }
        response = client.post("/v1/complete", json=payload)
        # Should return 503 as per logic
        assert response.status_code == 503

@patch("app.main.openai_client")
def test_complete_openai_compatible(mock_openai_client):
    # Setup the mock client
    if mock_openai_client is None:
         pytest.skip("Skipping openai test structure if client not init (patched out)")
    
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="OpenAI Hello"))]
    mock_completion.usage.prompt_tokens = 20
    mock_completion.usage.completion_tokens = 10
    
    mock_create = AsyncMock(return_value=mock_completion)
    mock_openai_client.chat.completions.create = mock_create
    
    # We need to forcefully set openai_client in app.main to our mock for this request
    # Since app.main initializes it at module level, we might need to patch 'app.main.openai_client'
    # which we are doing via decoration. But wait, if it was None at import time, 
    # patching it might be tricky if not done carefully.
    
    # A better way is to rely on dependency injection or re-import, but for simple script 
    # checking logic:
    
    payload = {
        "task": "test",
        "prompt": "test",
        "model": "gpt-4"
    }
    
    # If the app initialized with None, the endpoint checks 'if not openai_client'. 
    # So we must ensure it is NOT None during this test.
    with patch("app.main.openai_client", mock_openai_client):
        response = client.post("/v1/complete", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "OpenAI Hello"
        assert data["model_used"] == "gpt-4"
