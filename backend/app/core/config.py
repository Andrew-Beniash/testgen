"""
Configuration settings for the Test Generation Agent.

This module handles all configuration through environment variables
with sensible defaults for development.
"""

import os
from typing import Optional, List
from pydantic import BaseSettings, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings


class Settings(PydanticBaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    APP_NAME: str = "Test Generation Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # API settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/testgen"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_ECHO: bool = False
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TEMPERATURE: float = 0.1
    
    # Azure DevOps settings
    AZURE_DEVOPS_ORGANIZATION: Optional[str] = None
    AZURE_DEVOPS_PROJECT: Optional[str] = None
    AZURE_DEVOPS_PAT: Optional[str] = None
    AZURE_DEVOPS_WEBHOOK_SECRET: Optional[str] = None
    
    # Vector database settings
    VECTOR_DB_TYPE: str = "qdrant"  # Options: "qdrant", "weaviate"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    
    # Quality settings
    QUALITY_THRESHOLD_MIN: float = 0.75
    QUALITY_THRESHOLD_HIGH: float = 0.85
    VALIDATION_TIMEOUT_SECONDS: int = 30
    MAX_RETRIES_GENERATION: int = 3
    
    # Performance settings
    MAX_CONCURRENT_GENERATIONS: int = 10
    GENERATION_TIMEOUT_SECONDS: int = 120
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    
    # CORS settings
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000"
    ]
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted."""
        if v and not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    @validator("LOG_LEVEL", pre=True)
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @validator("ENVIRONMENT", pre=True)
    def validate_environment(cls, v):
        """Ensure environment is valid."""
        valid_envs = ["development", "testing", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v.lower()
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
