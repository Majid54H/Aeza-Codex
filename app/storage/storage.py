"""Persistent storage abstraction."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import settings


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


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path):
        self.documents_dir = base_dir / "documents"
        self.metadata_dir = base_dir / "metadata"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    async def save_document(self, document_id: str, filename: str, content: bytes) -> None:
        path = self.documents_dir / f"{document_id}_{filename}"
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


def get_storage() -> StorageBackend:
    return LocalStorage(settings.data_dir)
