"""Persistent storage abstraction."""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


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
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            docs.append({"id": meta_file.stem, **data})
        return docs

    async def load_document(self, document_id: str) -> bytes:
        # Documents are stored as: <document_id>_<filename>
        # For re-indexing we don't depend on the original filename, we just locate by prefix.
        prefix = f"{document_id}_"
        candidates = sorted(
            self.documents_dir.glob(prefix + "*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"Document not found: {document_id}")
        return candidates[0].read_bytes()


def get_storage() -> StorageBackend:
    return LocalStorage(settings.data_dir)
