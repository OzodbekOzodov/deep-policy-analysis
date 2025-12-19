import asyncio
import os
import sys

# Add backend to path so we can import app modules
# Assumes script is run from project root or backend root
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.clients.llm import LLMClient, EmbeddingClient

async def main():
    print("Initializing clients...")
    # Test LLM completion
    llm = LLMClient()
    print("Testing LLM Completion...")
    try:
        result = await llm.complete(
            prompt="Say hello",
            task="test"
        )
        print(f"Completion: {result}")
    except Exception as e:
        print(f"Completion failed: {e}")
    
    # Test structured completion
    print("\nTesting Structured Completion...")
    try:
        result = await llm.complete(
            prompt="Return a greeting",
            task="test",
            schema={
                "type": "object",
                "properties": {
                    "greeting": {"type": "string"},
                    "language": {"type": "string"}
                },
                "required": ["greeting", "language"]
            }
        )
        print(f"Structured: {result}")
    except Exception as e:
        print(f"Structured completion failed: {e}")
    
    # Test embedding
    print("\nTesting Embeddings...")
    embed = EmbeddingClient()
    try:
        vectors = await embed.embed(["Hello world", "Test sentence"])
        if vectors:
            print(f"Embeddings: {len(vectors)} vectors, {len(vectors[0])} dimensions each")
        else:
            print("Embeddings: Received empty list")
    except Exception as e:
        print(f"Embedding failed: {e}")
    
    await llm.close()
    await embed.close()

if __name__ == "__main__":
    asyncio.run(main())
