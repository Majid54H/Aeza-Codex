"""Aeza Codex — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api import chat, knowledge, admin

app = FastAPI(title="Aeza Codex", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
