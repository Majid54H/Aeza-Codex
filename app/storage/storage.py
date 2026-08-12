"""Persistent storage abstraction.

V1: LocalStorage under data/
Later: swap get_storage() to a cloud/object backend without changing callers.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings

CHUNK_MAPPING_FILE = "chunk_mapping.json"
SETTINGS_FILE = "admin_settings.json"
FAISS_INDEX_FILE = "faiss.index"
SKIP_METADATA_FILES = {CHUNK_MAPPING_FILE, SETTINGS_FILE}

DEFAULT_SETTINGS = {
    "chatbot_name": "",
    "welcome_message": "",
    "primary_color": "",
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
    async def load_document(self, document_id: str) -> bytes:
        ...

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        ...

    @abstractmethod
    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        ...

    @abstractmethod
    async def load_metadata(self, document_id: str) -> dict:
        ...

    @abstractmethod
    async def list_documents(self) -> list[dict]:
        ...

    @abstractmethod
    def save_faiss_index(self, data: bytes) -> None:
        ...

    @abstractmethod
    def load_faiss_index(self) -> bytes | None:
        ...

    @abstractmethod
    def delete_faiss_index(self) -> None:
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
        self.indexes_dir = base_dir / "indexes"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

    def _document_paths(self, document_id: str) -> list[Path]:
        prefix = f"{document_id}_"
        return sorted(
            self.documents_dir.glob(prefix + "*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        safe_filename = _sanitize_filename(filename)
        path = self.documents_dir / f"{document_id}_{safe_filename}"
        path.write_bytes(content)

    async def load_document(self, document_id: str) -> bytes:
        candidates = self._document_paths(document_id)
        if not candidates:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return candidates[0].read_bytes()

    async def delete_document(self, document_id: str) -> None:
        for path in self._document_paths(document_id):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        meta_path = self.metadata_dir / f"{document_id}.json"
        try:
            meta_path.unlink()
        except FileNotFoundError:
            pass

    async def save_metadata(self, document_id: str, metadata: dict) -> None:
        path = self.metadata_dir / f"{document_id}.json"
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    async def load_metadata(self, document_id: str) -> dict:
        path = self.metadata_dir / f"{document_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Metadata not found: {document_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    async def list_documents(self) -> list[dict]:
        docs = []
        for meta_file in self.metadata_dir.glob("*.json"):
            if meta_file.name in SKIP_METADATA_FILES:
                continue
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            docs.append({"id": meta_file.stem, **data})
        return docs

    def save_faiss_index(self, data: bytes) -> None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        path.write_bytes(data)

    def load_faiss_index(self) -> bytes | None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        if not path.exists():
            return None
        return path.read_bytes()

    def delete_faiss_index(self) -> None:
        path = self.indexes_dir / FAISS_INDEX_FILE
        try:
            path.unlink()
        except FileNotFoundError:
            pass

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
    """Return the active storage backend (LocalStorage for V1)."""
    return LocalStorage(settings.data_dir)
