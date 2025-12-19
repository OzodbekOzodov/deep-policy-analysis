"""API Dependencies"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import Settings, get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(settings.database_url, echo=settings.debug)

# Create async session factory
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session_maker() as session:
        yield session


def get_current_settings() -> Settings:
    """Get current settings instance."""
    return get_settings()

# Client dependencies
from app.clients.llm import LLMClient, EmbeddingClient

def get_llm_client() -> LLMClient:
    return LLMClient(settings.llm_gateway_url)

def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient(settings.llm_gateway_url)

