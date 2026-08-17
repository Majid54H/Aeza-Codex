"""Admin API routes (custom auth + branding)."""

from __future__ import annotations

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import (
    ADMIN_SESSION_COOKIE,
    _make_session_cookie,
    get_admin_username_optional,
    require_admin,
)
from app.config import settings
from app.services import admin as admin_service
from app.services import knowledge as knowledge_service
from app.storage.storage import get_storage

router = APIRouter()


class ChatbotSettings(BaseModel):
    chatbot_name: str = Field(default="", max_length=80)
    welcome_message: str = Field(default="", max_length=300)
    primary_color: str = Field(default="", max_length=20)
    logo_url: str = Field(default="", max_length=500)


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class AdminCredentialsUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_username: str = Field(min_length=1, max_length=80)
    new_password: str = Field(min_length=1, max_length=200)


class AdminRecoverCredentialsRequest(BaseModel):
    recovery_password: str = Field(min_length=1, max_length=200)
    new_username: str = Field(min_length=1, max_length=80)
    new_password: str = Field(min_length=1, max_length=200)


def _hash_password(password: str, salt: str, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        (salt or "").encode("utf-8"),
        int(iterations),
    )
    return dk.hex()


def _set_session_cookie(response: Response, username: str, password_hash: str) -> None:
    cookie_value = _make_session_cookie(username, password_hash)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=cookie_value,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


async def _verify_recovery_password(recovery_password: str, creds: dict) -> bool:
    salt = str(creds.get("salt") or "")
    iterations = int(creds.get("iterations") or 200_000)
    expected_hash = creds.get("password_hash") or ""
    actual_hash = _hash_password(recovery_password, salt=salt, iterations=iterations)
    if actual_hash == expected_hash:
        return True
    env_password = settings.admin_password or ""
    return bool(env_password) and secrets.compare_digest(recovery_password, env_password)


async def _save_new_credentials(
    response: Response,
    new_username: str,
    new_password: str,
) -> None:
    new_salt = secrets.token_hex(16)
    new_iterations = 200_000
    new_hash = _hash_password(new_password, salt=new_salt, iterations=new_iterations)
    storage = get_storage()
    await storage.save_admin_credentials(
        {
            "username": new_username,
            "password_hash": new_hash,
            "salt": new_salt,
            "iterations": new_iterations,
        }
    )
    _set_session_cookie(response, new_username, new_hash)


@router.get("/auth-status")
async def auth_status(request: Request):
    user = await get_admin_username_optional(request)
    return {"authenticated": bool(user), "username": user or ""}


@router.post("/login")
async def login(payload: AdminLoginRequest, response: Response):
    storage = get_storage()
    try:
        creds = await storage.load_admin_credentials()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if (payload.username or "") != (creds.get("username") or ""):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    salt = str(creds.get("salt") or "")
    iterations = int(creds.get("iterations") or 200_000)
    expected_hash = creds.get("password_hash") or ""
    actual_hash = _hash_password(payload.password, salt=salt, iterations=iterations)
    if actual_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _set_session_cookie(response, payload.username, expected_hash)
    return {"status": "logged_in", "username": payload.username}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/")
    return {"status": "logged_out"}


@router.put("/credentials")
async def update_credentials(
    payload: AdminCredentialsUpdateRequest,
    response: Response,
    _: str = Depends(require_admin),
):
    storage = get_storage()
    creds = await storage.load_admin_credentials()

    salt = str(creds.get("salt") or "")
    iterations = int(creds.get("iterations") or 200_000)
    expected_hash = creds.get("password_hash") or ""
    actual_hash = _hash_password(payload.current_password, salt=salt, iterations=iterations)
    if actual_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    new_salt = secrets.token_hex(16)
    new_iterations = 200_000
    new_hash = _hash_password(payload.new_password, salt=new_salt, iterations=new_iterations)
    await storage.save_admin_credentials(
        {
            "username": payload.new_username,
            "password_hash": new_hash,
            "salt": new_salt,
            "iterations": new_iterations,
        }
    )

    response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/")
    return {"status": "credentials_updated"}


@router.post("/recover-credentials")
async def recover_credentials(payload: AdminRecoverCredentialsRequest, response: Response):
    storage = get_storage()
    try:
        creds = await storage.load_admin_credentials()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not await _verify_recovery_password(payload.recovery_password, creds):
        raise HTTPException(status_code=401, detail="Recovery password is incorrect")

    await _save_new_credentials(response, payload.new_username, payload.new_password)
    return {"status": "credentials_recovered", "username": payload.new_username}


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
