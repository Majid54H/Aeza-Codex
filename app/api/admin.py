"""Admin API routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.services import knowledge as knowledge_service
from app.storage.storage import get_storage

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class ChatbotSettings(BaseModel):
    chatbot_name: str = Field(default="Aeza Codex", max_length=80)
    welcome_message: str = Field(default="Ask a question about this business.", max_length=300)
    primary_color: str = Field(default="#6366f1", max_length=20)
    logo_url: str = Field(default="", max_length=500)


@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/settings", response_model=ChatbotSettings)
async def get_settings():
    storage = get_storage()
    return ChatbotSettings(**storage.load_settings())


@router.put("/settings", response_model=ChatbotSettings)
async def put_settings(payload: ChatbotSettings):
    storage = get_storage()
    saved = storage.save_settings(payload.model_dump())
    return ChatbotSettings(**saved)


@router.post("/reindex")
async def reindex():
    """Trigger a full re-index of the knowledge base."""
    await knowledge_service.reindex_all()
    return {"status": "reindex_complete"}
