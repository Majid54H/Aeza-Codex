"""Shared FastAPI dependencies for admin authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request, status

from app.storage.storage import get_storage

ADMIN_SESSION_COOKIE = "admin_session"
ADMIN_SESSION_TTL_SECONDS = 60 * 60 * 6  # 6 hours


def _encode_cookie_value(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_cookie_value(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8")).decode("utf-8")


def _make_session_cookie(username: str, password_hash_secret: str) -> str:
    exp = int(time.time()) + ADMIN_SESSION_TTL_SECONDS
    msg = f"{username}|{exp}".encode("utf-8")
    sig = hmac.new(password_hash_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    raw = f"{username}|{exp}|{sig}"
    return _encode_cookie_value(raw)


def _parse_session_cookie(cookie_value: str) -> tuple[str, int, str] | None:
    try:
        raw = _decode_cookie_value(cookie_value)
        parts = raw.split("|")
        if len(parts) != 3:
            return None
        username, exp_s, sig = parts
        exp = int(exp_s)
        return username, exp, sig
    except Exception:
        return None


async def _get_admin_username_from_request(request: Request) -> str | None:
    storage = get_storage()
    creds = await storage.load_admin_credentials()
    cookie_value = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not cookie_value:
        return None

    parsed = _parse_session_cookie(cookie_value)
    if not parsed:
        return None

    username, exp, sig = parsed
    if exp < int(time.time()):
        return None

    secret = creds.get("password_hash") or ""
    msg = f"{username}|{exp}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not secrets.compare_digest(sig, expected):
        return None

    configured_username = (creds.get("username") or "").strip()
    if not configured_username or not secrets.compare_digest(username, configured_username):
        return None

    return username


async def require_admin(request: Request) -> str:
    """Require admin session cookie for protected routes."""
    username = await _get_admin_username_from_request(request)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return username


async def get_admin_username_optional(request: Request) -> str | None:
    return await _get_admin_username_from_request(request)
