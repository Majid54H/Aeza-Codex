"""Persistent storage abstraction."""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings

CHUNK_MAPPING_FILE = "chunk_mapping.json"
SETTINGS_FILE = "admin_settings.json"
SKIP_METADATA_FILES = {CHUNK_MAPPING_FILE, SETTINGS_FILE}

DEFAULT_SETTINGS = {
    "chatbot_name": "Aeza Codex",
    "welcome_message": "Ask a question about this business.",
    "primary_color": "#6366f1",
    "logo_url": "",
}


def _sanitize_filename(filename: str) -> str:
    # Avoid directory traversal / invalid filenames on Windows.
    name = Path(filename).name
    name = name.replace("/", "_").replace("\\", "_")
    # Replace characters Windows doesn't allow in filenames.
    name = re.sub(r'[<>:"|?*\x00-\x1F]+', "_", name)
    # Collapse whitespace for cleaner paths.
    name = re.sub(r"\s+", "_", name).strip("._ ")
    return name or "document"


class StorageBackend(ABC):
    @abstractmethod
    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        ...

    @abstractmethod
    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        ...

    @abstractmethod
    async def list_documents(self) -> list[dict]:
        ...

    @abstractmethod
    async def load_document(self, document_id: str) -> bytes:
        ...

    @abstractmethod
    def save_chunk_mapping(self, mapping: list[dict]) -> None:
        ...

    @abstractmethod
    def load_chunk_mapping(self) -> list[dict]:
        ...

    @abstractmethod
    def load_settings(self) -> dict:
        ...

    @abstractmethod
    def save_settings(self, data: dict) -> dict:
        ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path):
        self.documents_dir = base_dir / "documents"
        self.metadata_dir = base_dir / "metadata"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        safe_filename = _sanitize_filename(filename)
        path = self.documents_dir / f"{document_id}_{safe_filename}"
        path.write_bytes(content)

    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        path = self.metadata_dir / f"{document_id}.json"
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    async def list_documents(self) -> list[dict]:
        docs = []
        for meta_file in self.metadata_dir.glob("*.json"):
            if meta_file.name in SKIP_METADATA_FILES:
                continue
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            docs.append({"id": meta_file.stem, **data})
        return docs

    async def load_document(self, document_id: str) -> bytes:
        prefix = f"{document_id}_"
        candidates = sorted(
            self.documents_dir.glob(prefix + "*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return candidates[0].read_bytes()

    def save_chunk_mapping(self, mapping: list[dict]) -> None:
        path = self.metadata_dir / CHUNK_MAPPING_FILE
        path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_chunk_mapping(self) -> list[dict]:
        path = self.metadata_dir / CHUNK_MAPPING_FILE
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8")) or []
        except (json.JSONDecodeError, OSError):
            return []

    def load_settings(self) -> dict:
        path = self.metadata_dir / SETTINGS_FILE
        if not path.exists():
            return dict(DEFAULT_SETTINGS)
        try:
            data = json.loads(path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_SETTINGS)
        merged = dict(DEFAULT_SETTINGS)
        merged.update({k: data[k] for k in DEFAULT_SETTINGS if k in data})
        return merged

    def save_settings(self, data: dict) -> dict:
        merged = self.load_settings()
        for key in DEFAULT_SETTINGS:
            if key in data and data[key] is not None:
                merged[key] = data[key]
        path = self.metadata_dir / SETTINGS_FILE
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return merged


def get_storage() -> StorageBackend:
    return LocalStorage(settings.data_dir)
