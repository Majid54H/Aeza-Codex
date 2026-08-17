"""Application configuration."""

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    openai_api_key: str = ""
    openai_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    chat_max_tokens: int = 4096
    data_dir: Path = Path("data")
    max_upload_size_mb: int = 10
    rag_top_k: int = 5
    rag_catalog_top_k: int = 8
    rag_min_score: float = 0.25
    excel_category_sample_products: int = 15
    web_fetch_timeout_seconds: int = 15
    web_fetch_max_bytes: int = 2_000_000
    admin_username: str = "admin"
    admin_password: str = ""
    storage_backend: str = ""
    blob_prefix: str = "aeza-codex"

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> str:
        text = str(value or "development").strip().lower()
        return text or "development"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def resolved_storage_backend(self) -> str:
        # Vercel has a read-only filesystem — always use Blob there.
        if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
            return "blob"
        explicit = (self.storage_backend or "").strip().lower()
        if explicit in {"local", "blob"}:
            return explicit
        return "local"


settings = Settings()

# Ensure local data directories exist in development (local disk only)
if settings.environment == "development" and settings.resolved_storage_backend == "local":
    for subdir in ("documents", "indexes", "metadata"):
        (settings.data_dir / subdir).mkdir(parents=True, exist_ok=True)
