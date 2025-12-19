from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    GEMINI_API_KEY: str = Field(..., description="API Key for Gemini")
    DEFAULT_MODEL: str = Field("gemini-2.5-flash", alias="LLM_MODEL")
    EMBEDDING_MODEL: str = "text-embedding-004"
    
    # LLM_BASE_URL might be used if we need to point to a specific endpoint, 
    # but the SDK handles it. We'll keep it available just in case.
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    class Config:
        env_file = [".env", "../.env", "../../.env"]
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
