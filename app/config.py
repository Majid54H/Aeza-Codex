"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    data_dir: Path = Path("data")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure local data directories exist in development
if settings.environment == "development":
    for subdir in ("documents", "indexes", "metadata"):
        (settings.data_dir / subdir).mkdir(parents=True, exist_ok=True)
