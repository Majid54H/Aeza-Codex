"""Aeza Codex — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, Response

from app.api import admin, chat, knowledge as knowledge_api
from app.config import settings
from app.rag import faiss as faiss_index
from app.services import knowledge as knowledge_service
from app.storage.storage import get_storage

logger = logging.getLogger(__name__)

_startup_error: str | None = None
_startup_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_error, _startup_ready
    _startup_error = None
    _startup_ready = False

    try:
        if settings.environment == "production" and not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when ENVIRONMENT=production")

        backend = settings.resolved_storage_backend
        logger.info("Aeza Codex starting with storage backend: %s", backend)
        get_storage()

        faiss_index.load()
        await knowledge_service.rebuild_catalogs_from_documents()
        _startup_ready = True
    except Exception as exc:
        _startup_error = str(exc)
        logger.exception("Startup initialization failed: %s", exc)

    yield


app = FastAPI(title="Aeza Codex", version="1.0.0", lifespan=lifespan)


class DevStaticFiles(StaticFiles):
    """Avoid stale CSS/JS in local development (no 304 cache)."""

    def is_not_modified(self, *args, **kwargs) -> bool:
        if settings.environment == "development":
            return False
        return super().is_not_modified(*args, **kwargs)

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        if settings.environment == "development":
            response.headers["Cache-Control"] = "no-store"
        return response


app.mount("/static", DevStaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(knowledge_api.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/")
async def root():
    return RedirectResponse(url="/chat")


@app.get("/health")
async def health():
    faiss_stats = faiss_index.stats()
    payload = {
        "status": "ok" if _startup_ready and not _startup_error else "degraded",
        "environment": settings.environment,
        "storage_backend": settings.resolved_storage_backend,
        "blob_configured": bool(settings.blob_token),
        "ready": _startup_ready,
        "faiss_vectors": faiss_stats["vectors"],
        "faiss_chunks": faiss_stats["chunks"],
    }
    if _startup_error:
        payload["startup_error"] = _startup_error
    if settings.is_vercel and not settings.blob_token:
        payload["storage_note"] = (
            "Using /tmp storage (ephemeral). Connect Vercel Blob for persistent knowledge."
        )
    elif faiss_stats["vectors"] == 0:
        payload["index_note"] = (
            "FAISS index is empty. Upload a document or use Admin → Re-index."
        )
    return payload


@app.get("/admin")
async def admin_page(request: Request):
    """Owner/admin UI landing page (custom login handled in the UI)."""
    return templates.TemplateResponse(request, "admin.html", {})


@app.get("/chat")
async def chat_page(request: Request, embed: str = ""):
    """Customer chat UI. Use ?embed=1 to fill the parent iframe size."""
    return templates.TemplateResponse(
        request,
        "chat.html",
        {"embed": embed.lower() in {"1", "true", "yes"}},
    )
