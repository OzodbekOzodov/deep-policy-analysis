"""DAP Backend Configuration"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://localhost/dap"
    
    # LLM Configuration (Generic - works with any OpenAI-compatible API)
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    
    # LLM Gateway
    llm_gateway_url: str = "http://localhost:8001"
    
    # App settings
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
