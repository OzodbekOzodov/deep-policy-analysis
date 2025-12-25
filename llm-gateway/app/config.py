from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Provider selection: openrouter, gemini, openai, anthropic, custom
    provider: str = "gemini"

    # LLM API credentials
    api_key: str
    base_url: Optional[str] = None
    default_model: Optional[str] = None

    # Embedding API (can use same or different provider)
    embedding_api_key: Optional[str] = None

    # Model defaults (fallbacks if not specified)
    gemini_default_model: str = "gemini-2.0-flash-exp"
    openai_default_model: str = "gpt-4o-mini"
    anthropic_default_model: str = "claude-3-5-sonnet-20241022"
    embedding_model: str = "models/text-embedding-004"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def is_gemini(self) -> bool:
        return self.provider in ("gemini", "custom") and bool(self.base_url) and "generativelanguage" in self.base_url

    @property
    def is_openai_compatible(self) -> bool:
        return self.provider in ("openrouter", "openai", "anthropic", "custom") and bool(self.api_key)

settings = Settings()
