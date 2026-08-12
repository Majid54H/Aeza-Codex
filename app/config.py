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
    max_upload_size_mb: int = 10

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure local data directories exist in development
if settings.environment == "development":
    for subdir in ("documents", "indexes", "metadata"):
        (settings.data_dir / subdir).mkdir(parents=True, exist_ok=True)
