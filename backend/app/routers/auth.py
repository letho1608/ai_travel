from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import jwt
from fastapi import APIRouter, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings
from app.schemas import AccountDeleteRequest, OAuthRequest, UserPreferencesRequest
from app.services.store import store

router = APIRouter(prefix="/api/auth", tags=["auth"])
DEMO_USERS: dict[str, dict] = {}
POLICY_VERSION = "2026-08-05"


def _issue_token(user: dict) -> str:
    if settings.app_env == "local":
        token = f"mock-jwt-{user['id']}"
        DEMO_USERS[token] = user
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
        return DEMO_USERS.get(token)
    if not settings.app_jwt_secret:
        return None
    try:
        claims = jwt.decode(token, settings.app_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return store.get_user_by_id(claims["sub"])


def _verify_google(raw_token: str) -> dict:
    if not settings.google_client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is required outside local mode")
    claims = id_token.verify_oauth2_token(
        raw_token, google_requests.Request(), settings.google_client_id
    )
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google account email is not verified")
    return claims


@router.post("/oauth")
def oauth(payload: OAuthRequest):
    if not payload.consent:
        raise HTTPException(400, "Bạn cần đồng ý điều khoản và chính sách bảo mật")
    try:
        if settings.app_env == "local":
            if not payload.token.startswith("mock-google-"):
                raise ValueError("Mock Google token không hợp lệ")
            identity = {
                "sub": str(uuid5(NAMESPACE_URL, payload.token)),
                "email": "demo@example.com", "name": "Người dùng demo",
            }
        else:
            identity = _verify_google(payload.token)
        user = store.upsert_user_and_claim(
            "google", identity["email"], identity.get("name"), payload.ma_phien,
            POLICY_VERSION,
        )
        token = _issue_token(user)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(401, str(exc)) from exc
    store.log(payload.ma_phien, "dang_nhap_oauth", {"id_nguoi_dung": user["id"]})
    return {"token": token, "nguoi_dung": user}


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    user = resolve_user(authorization)
    if not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ")
    return user


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
    for token, demo_user in list(DEMO_USERS.items()):
        if demo_user["id"] == user["id"]:
            DEMO_USERS.pop(token, None)
