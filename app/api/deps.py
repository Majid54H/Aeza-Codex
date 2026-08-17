"""Shared FastAPI dependencies for admin authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException, Request, Response, status

from app.config import settings
from app.storage.storage import get_storage

ADMIN_SESSION_COOKIE = "admin_session"
ADMIN_CREDS_COOKIE = "admin_creds"
ADMIN_SESSION_TTL_SECONDS = 60 * 60 * 6  # 6 hours
ADMIN_CREDS_TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year


def cookie_secure() -> bool:
    return settings.is_vercel or (settings.environment or "").strip().lower() == "production"


def hash_password(password: str, salt: str, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        (salt or "").encode("utf-8"),
        int(iterations or 200_000),
    )
    return dk.hex()


def _encode_cookie_value(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_cookie_value(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8")).decode("utf-8")


def _creds_signing_key() -> bytes:
    return (settings.admin_password or "aeza-codex-admin").encode("utf-8")


def _valid_creds(data: object) -> dict | None:
    if not isinstance(data, dict):
        return None
    username = str(data.get("username") or "").strip()
    password_hash = str(data.get("password_hash") or "")
    salt = str(data.get("salt") or "")
    try:
        iterations = int(data.get("iterations") or 0)
    except (TypeError, ValueError):
        return None
    if not username or not password_hash or not salt or iterations < 1:
        return None
    return {
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
        "iterations": iterations,
        "source": str(data.get("source") or ""),
    }


def make_creds_cookie(creds: dict) -> str:
    payload = json.dumps(
        {
            "username": creds["username"],
            "password_hash": creds["password_hash"],
            "salt": creds["salt"],
            "iterations": creds["iterations"],
            "source": "user",
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    sig = hmac.new(_creds_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return _encode_cookie_value(f"{payload}|{sig}")


def parse_creds_cookie(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        raw = _decode_cookie_value(value)
        payload, sig = raw.rsplit("|", 1)
        expected = hmac.new(_creds_signing_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(sig, expected):
            return None
        return _valid_creds(json.loads(payload))
    except Exception:
        return None


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


def apply_session_cookie(response: Response, username: str, password_hash: str) -> None:
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=_make_session_cookie(username, password_hash),
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
        max_age=ADMIN_SESSION_TTL_SECONDS,
    )


def apply_creds_cookie(response: Response, creds: dict) -> None:
    response.set_cookie(
        key=ADMIN_CREDS_COOKIE,
        value=make_creds_cookie(creds),
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
        max_age=ADMIN_CREDS_TTL_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE,
        path="/",
        samesite="lax",
        secure=cookie_secure(),
    )


def password_matches(password: str, creds: dict) -> bool:
    expected = str(creds.get("password_hash") or "")
    actual = hash_password(
        password,
        salt=str(creds.get("salt") or ""),
        iterations=int(creds.get("iterations") or 200_000),
    )
    return bool(expected) and secrets.compare_digest(actual, expected)


def env_credentials_match(username: str, password: str) -> bool:
    expected_user = (settings.admin_username or "").strip()
    expected_password = settings.admin_password or ""
    if not expected_user or not expected_password:
        return False
    return secrets.compare_digest(username.strip(), expected_user) and secrets.compare_digest(
        password, expected_password
    )


async def credential_candidates(request: Request) -> list[dict]:
    storage = get_storage()
    stored = _valid_creds(await storage.load_admin_credentials())
    cookie = parse_creds_cookie(request.cookies.get(ADMIN_CREDS_COOKIE))

    ordered: list[dict] = []
    if stored and stored.get("source") == "user":
        ordered.append(stored)
    if cookie:
        ordered.append(cookie)
    if stored and stored.get("source") != "user":
        ordered.append(stored)

    unique: list[dict] = []
    seen: set[str] = set()
    for creds in ordered:
        key = f"{creds['username']}|{creds['password_hash']}|{creds['salt']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(creds)
    return unique


def match_login(username: str, password: str, candidates: list[dict]) -> dict | None:
    wanted = (username or "").strip()
    for creds in candidates:
        if not secrets.compare_digest(wanted, creds["username"]):
            continue
        if password_matches(password, creds):
            return creds
    return None


async def _get_admin_username_from_request(request: Request) -> str | None:
    cookie_value = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not cookie_value:
        return None

    parsed = _parse_session_cookie(cookie_value)
    if not parsed:
        return None

    username, exp, sig = parsed
    if exp < int(time.time()):
        return None

    for creds in await credential_candidates(request):
        secret = creds.get("password_hash") or ""
        msg = f"{username}|{exp}".encode("utf-8")
        expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        if not secrets.compare_digest(sig, expected):
            continue
        if not secrets.compare_digest(username, creds["username"]):
            continue
        return username

    return None


async def require_admin(request: Request) -> str:
    """Require admin session cookie for protected routes."""
    username = await _get_admin_username_from_request(request)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return username


async def get_admin_username_optional(request: Request) -> str | None:
    return await _get_admin_username_from_request(request)
