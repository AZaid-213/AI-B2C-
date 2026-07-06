from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # GreenAPI
    greenapi_instance_id: str
    greenapi_api_token: str
    greenapi_base_url: str = "https://api.green-api.com"

    # Groq AI
    groq_api_key: str | None = None
    groq_api_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"

    # Redis queue
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_env: str = "development"
    allowed_origins: str = "http://localhost:5173"
    test_phone: str = "924224547133"  # dummy number for testing

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
