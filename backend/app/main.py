import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.routers import admin, auth, inventory, plans, roadtrip, support
from app.services.rate_limit import limiter
from app.services.store import store

settings.validate_production()
logger = logging.getLogger(__name__)


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        consumed = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal consumed, exceeded
            message = await receive()
            if message["type"] != "http.request":
                return message
            consumed += len(message.get("body", b""))
            if consumed > self.max_bytes:
                exceeded = True
                return {"type": "http.disconnect"}
            return message

        async def limited_send(message: Message) -> None:
            if not exceeded:
                await send(message)

        await self.app(scope, limited_receive, limited_send)
        if exceeded:
            response = JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
                headers={"Connection": "close"},
            )
            await response(scope, receive, send)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async def maintenance_loop():
        while True:
            try:
                await asyncio.to_thread(store.cleanup_expired)
                await asyncio.to_thread(store.materialize_due_reminders)
            except (psycopg.Error, RedisError, RuntimeError):
                logger.exception("Scheduled cleanup failed")
            await asyncio.sleep(3600)

    task = asyncio.create_task(maintenance_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Content-Type", "Authorization", "X-Session-Id", "X-Support-Token", "X-Admin-Token",
    ],
)
app.include_router(admin.router)
app.include_router(plans.router)
app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(roadtrip.router)
app.include_router(support.router)


@app.middleware("http")
async def security_headers(request, call_next):
    request_id = request.headers.get("X-Request-ID")
    request_id = str(uuid4()) if not request_id or len(request_id) > 100 else request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.app_env != "local":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok", "ai_mode": settings.ai_mode,
        "storage": "postgresql" if store.__class__.__name__ == "PostgresStore" else "memory",
        "rate_limiter": "redis" if limiter.__class__.__name__ == "RedisRateLimiter" else "memory",
    }


@app.get("/ready")
def readiness():
    try:
        if store.__class__.__name__ == "PostgresStore":
            with store._connect() as connection:
                connection.execute("SELECT 1")
        if limiter.__class__.__name__ == "RedisRateLimiter":
            limiter.client.ping()
    except (psycopg.Error, RedisError, RuntimeError):
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}
