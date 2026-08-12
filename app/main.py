"""Aeza Codex — FastAPI application entry point."""

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from app.api import admin, chat, knowledge as knowledge_api
from app.api.deps import require_admin
from app.config import settings
from app.rag import faiss as faiss_index
from app.services import knowledge as knowledge_service

app = FastAPI(title="Aeza Codex", version="1.0.0")


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


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/admin")
async def admin_page(request: Request, _: str = Depends(require_admin)):
    """Owner/admin UI landing page (HTTP Basic auth required)."""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/chat")
async def chat_page(request: Request, embed: str = ""):
    """Customer chat UI. Use ?embed=1 to fill the parent iframe size."""
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "embed": embed.lower() in {"1", "true", "yes"},
        },
    )


@app.on_event("startup")
async def startup():
    if settings.environment == "production" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when ENVIRONMENT=production")
    faiss_index.load()
    await knowledge_service.rebuild_catalogs_from_documents()
