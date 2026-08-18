import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import jwt
from fastapi import APIRouter, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings
from app.schemas import (
    AccountDeleteRequest, OAuthRequest, PasswordAuthRequest, PasswordForgotRequest,
    UserPreferencesRequest,
)
from app.services.store import store

router = APIRouter(prefix="/api/auth", tags=["auth"])
LOCAL_USERS: dict[str, dict] = {}
POLICY_VERSION = "2026-08-05"
PASSWORD_ITERATIONS = 240_000


def _password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, stored: str | None) -> bool:
    try:
        algorithm, iterations, salt, expected = (stored or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    except (AttributeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def _public_user(user: dict) -> dict:
    result = {key: value for key, value in user.items() if key != "mat_khau_hash"}
    if "role" not in result:
        result["role"] = "admin" if user.get("username") in ("admin", "root", "administrator") else "user"
    return result


def _issue_token(user: dict) -> str:
    if settings.app_env == "local":
        token = f"local-jwt-{user['id']}"
        LOCAL_USERS[token] = user
        return token
    if not settings.app_jwt_secret:
        raise RuntimeError("APP_JWT_SECRET is required outside local mode")
    return jwt.encode(
        {"sub": user["id"], "email": user["email"], "name": user.get("ten"),
         "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(days=7)},
        settings.app_jwt_secret, algorithm="HS256",
    )


def resolve_user(authorization: str | None) -> dict | None:
    token = (authorization or "").removeprefix("Bearer ")
    if not token:
        return None
    if settings.app_env == "local":
        return LOCAL_USERS.get(token)
    if not settings.app_jwt_secret:
        return None
    try:
        claims = jwt.decode(token, settings.app_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return store.get_user_by_id(claims["sub"])


def _verify_google(raw_token: str) -> dict:
    if not settings.google_client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is required for Google sign-in")
    claims = id_token.verify_oauth2_token(
        raw_token, google_requests.Request(), settings.google_client_id
    )
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google account email is not verified")
    return claims


def _google_identity(raw_token: str) -> dict:
    if settings.app_env == "local" and raw_token.startswith("mock-google-"):
        slug = re.sub(r"[^a-z0-9_-]+", "", raw_token.removeprefix("mock-google-").casefold()) or "local"
        return {
            "sub": str(uuid5(NAMESPACE_URL, raw_token)),
            "email": f"{slug[:40]}@demo.local",
            "name": slug.replace("-", " ").replace("_", " ").title() or "Demo user",
        }
    return _verify_google(raw_token)


@router.post("/oauth")
def oauth(payload: OAuthRequest):
    if not payload.consent:
        raise HTTPException(400, "Bạn cần đồng ý điều khoản và chính sách bảo mật")
    try:
        identity = _google_identity(payload.token)
        user = store.upsert_user_and_claim(
            "google", identity["email"], identity.get("name"), payload.ma_phien,
            POLICY_VERSION,
        )
        token = _issue_token(user)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(401, str(exc)) from exc
    store.log(payload.ma_phien, "dang_nhap_oauth", {"id_nguoi_dung": user["id"]})
    return {"token": token, "nguoi_dung": _public_user(user)}


@router.post("/password")
def password_auth(payload: PasswordAuthRequest):
    if not payload.consent:
        raise HTTPException(400, "Bạn cần đồng ý điều khoản và chính sách bảo mật")
    existing = store.get_user_by_username(payload.username)
    try:
        if payload.hanh_dong == "dang_ky":
            if existing:
                raise HTTPException(409, "Tên đăng nhập đã tồn tại")
            user = store.create_password_user_and_claim(
                payload.username,
                _password_hash(payload.password),
                payload.ma_phien,
                POLICY_VERSION,
                payload.so_dien_thoai,
            )
        else:
            hashed = existing.get("mat_khau_hash") if existing else None
            if not existing or not hashed or not _verify_password(payload.password, hashed):
                raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng")
            user = existing
    except ValueError as exc:
        raise HTTPException(409, "Tên đăng nhập đã tồn tại") from exc
    store.claim_session(payload.ma_phien, user["id"])
    store.log(payload.ma_phien, "dang_nhap_mat_khau", {"id_nguoi_dung": user["id"]})
    token = _issue_token(user)
    return {"token": token, "nguoi_dung": _public_user(user)}


@router.post("/password/forgot")
def password_forgot(payload: PasswordForgotRequest):
    user = store.get_user_by_username(payload.username)
    store.log(
        payload.ma_phien,
        "quen_mat_khau",
        {"username": payload.username, "co_tai_khoan": bool(user)},
    )
    return {"ok": True}


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    user = resolve_user(authorization)
    if not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    return _public_user(user)


@router.get("/preferences")
def preferences(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if authorization and not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    if not x_session_id and not user:
        raise HTTPException(401, "Thiếu phiên hoặc thông tin đăng nhập")
    return store.get_preferences(x_session_id or "", user["id"] if user else None)


@router.put("/preferences")
def update_preferences(
    payload: UserPreferencesRequest,
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if authorization and not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    values = payload.model_dump(exclude={"ma_phien"})
    return store.save_preferences(payload.ma_phien, user["id"] if user else None, values)


@router.delete("/account", status_code=204)
def delete_account(
    payload: AccountDeleteRequest,
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    try:
        store.delete_user_data(user["id"])
    except ValueError as exc:
        raise HTTPException(404, "Tài khoản không còn tồn tại") from exc
    for token, local_user in list(LOCAL_USERS.items()):
        if local_user["id"] == user["id"]:
            LOCAL_USERS.pop(token, None)
