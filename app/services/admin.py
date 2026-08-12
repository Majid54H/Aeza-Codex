"""Admin settings service — thin wrapper over storage."""

from app.storage.storage import get_storage


def get_chatbot_settings() -> dict:
    return get_storage().load_settings()


def update_chatbot_settings(data: dict) -> dict:
    return get_storage().save_settings(data)
