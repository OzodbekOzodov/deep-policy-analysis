from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    gemini_api_key: str
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    
    default_model: str = "models/gemini-2.0-flash"
    embedding_model: str = "models/text-embedding-004"
    
    class Config:
        env_file = ".env"
        extra = "ignore" # Allow extra fields in .env

settings = Settings()
