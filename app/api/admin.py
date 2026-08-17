"""Admin API routes (custom auth + branding)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import (
    apply_creds_cookie,
    apply_session_cookie,
    clear_session_cookie,
    credential_candidates,
    env_credentials_match,
    get_admin_username_optional,
    hash_password,
    match_login,
    password_matches,
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


async def _verify_recovery_password(request: Request, recovery_password: str) -> bool:
    for creds in await credential_candidates(request):
        if password_matches(recovery_password, creds):
            return True
    env_password = settings.admin_password or ""
    return bool(env_password) and secrets.compare_digest(recovery_password, env_password)


def _build_credentials(username: str, password: str) -> dict:
    salt = secrets.token_hex(16)
    iterations = 200_000
    return {
        "username": username.strip(),
        "password_hash": hash_password(password, salt=salt, iterations=iterations),
        "salt": salt,
        "iterations": iterations,
        "source": "user",
    }


async def _save_new_credentials(
    response: Response,
    new_username: str,
    new_password: str,
    set_session: bool = True,
) -> dict:
    creds = _build_credentials(new_username, new_password)
    try:
        await get_storage().save_admin_credentials(creds)
    except Exception:
        # Cookie still keeps the new login working on this browser (e.g. ephemeral /tmp).
        pass
    apply_creds_cookie(response, creds)
    if set_session:
        apply_session_cookie(response, creds["username"], creds["password_hash"])
    return creds


@router.get("/auth-status")
async def auth_status(request: Request):
    user = await get_admin_username_optional(request)
    return {"authenticated": bool(user), "username": user or ""}


@router.post("/login")
async def login(payload: AdminLoginRequest, request: Request, response: Response):
    try:
        candidates = await credential_candidates(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    matched = match_login(payload.username, payload.password, candidates)
    if matched is None:
        has_user_creds = any(item.get("source") == "user" for item in candidates)
        if not has_user_creds and env_credentials_match(payload.username, payload.password):
            matched = next((item for item in candidates if item.get("source") != "user"), None)
            if matched is None and candidates:
                matched = candidates[0]

    if matched is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    username = matched["username"]
    apply_session_cookie(response, username, matched["password_hash"])
    if matched.get("source") == "user":
        apply_creds_cookie(response, matched)
    return {"status": "logged_in", "username": username}


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"status": "logged_out"}


@router.put("/credentials")
async def update_credentials(
    payload: AdminCredentialsUpdateRequest,
    request: Request,
    response: Response,
    _username: str = Depends(require_admin),
):
    current_ok = False
    for creds in await credential_candidates(request):
        if password_matches(payload.current_password, creds):
            current_ok = True
            break
    if not current_ok:
        env_password = settings.admin_password or ""
        if not env_password or not secrets.compare_digest(payload.current_password, env_password):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

    creds = await _save_new_credentials(
        response,
        payload.new_username,
        payload.new_password,
        set_session=False,
    )
    clear_session_cookie(response)
    return {"status": "credentials_updated", "username": creds["username"]}


@router.post("/recover-credentials")
async def recover_credentials(
    payload: AdminRecoverCredentialsRequest,
    request: Request,
    response: Response,
):
    try:
        if not await _verify_recovery_password(request, payload.recovery_password):
            raise HTTPException(status_code=401, detail="Recovery password is incorrect")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    creds = await _save_new_credentials(response, payload.new_username, payload.new_password)
    return {"status": "credentials_recovered", "username": creds["username"]}


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
