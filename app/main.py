"""Aeza Codex — FastAPI application entry point."""

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import admin, chat, knowledge
from app.api.deps import require_admin
from app.config import settings
from app.rag import faiss as faiss_index

app = FastAPI(title="Aeza Codex", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/admin")
async def admin_page(request: Request, _: str = Depends(require_admin)):
    """Owner/admin UI landing page (HTTP Basic auth required)."""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/chat")
async def chat_page(request: Request):
    """Customer chat UI landing page."""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.on_event("startup")
async def startup():
    if settings.environment == "production" and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when ENVIRONMENT=production")
    faiss_index.load()
