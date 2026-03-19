from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os


def parse_cors_origins(v: str) -> List[str]:
    """Parse comma-separated CORS origins"""
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",")]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_parse_enums=True,
    )

    # Database
    database_url: str = "postgresql+asyncpg://quizuser:quizpass@localhost:5432/quizdb"
    database_replica_url: Optional[str] = None  # Read replica URL

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: Optional[str] = None
    ollama_model: str = "kimi-k2.5:cloud"

    # CORS - comma-separated string will be parsed
    cors_origins: str = "http://localhost:3000"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default: int = 100  # requests per minute
    rate_limit_generate: int = 10  # requests per minute for expensive operations

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        return parse_cors_origins(self.cors_origins)


settings = Settings()