"""Admin API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.services import admin as admin_service
from app.services import knowledge as knowledge_service

router = APIRouter()


class ChatbotSettings(BaseModel):
    chatbot_name: str = Field(default="Aeza Codex", max_length=80)
    welcome_message: str = Field(default="Ask a question about this business.", max_length=300)
    primary_color: str = Field(default="#6366f1", max_length=20)
    logo_url: str = Field(default="", max_length=500)


@router.get("/settings", response_model=ChatbotSettings)
async def get_settings():
    """Public branding settings for /chat."""
    return ChatbotSettings(**admin_service.get_chatbot_settings())


@router.put("/settings", response_model=ChatbotSettings)
async def put_settings(payload: ChatbotSettings, _: str = Depends(require_admin)):
    saved = admin_service.update_chatbot_settings(payload.model_dump())
    return ChatbotSettings(**saved)


@router.post("/reindex")
async def reindex(_: str = Depends(require_admin)):
    """Trigger a full re-index of the knowledge base."""
    await knowledge_service.reindex_all()
    return {"status": "reindex_complete"}
