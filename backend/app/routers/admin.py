import csv
import secrets
from io import StringIO

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response
from redis.exceptions import RedisError

from app.config import settings
from app.data import DISTANCE_METADATA, PLACE_METADATA, PLACES, source_for
from app.pipeline.planner import (
    AI_FALLBACK_NOTE,
    DESTINATION_RADIUS_KM,
    FOCUS_DESTINATIONS,
    build_plan,
    haversine_km,
)
from app.pipeline.routing import public_transit_policy_status, route_calibration_status
from app.services.event_calendar import official_event_calendar_status
from app.services.google_places import google_places_readiness
from app.services.quality_benchmarks import audit_release_spec, run_release_readiness_benchmark
from app.services.ai import breaker_status
from app.services.catalog_quality import catalogue_field_coverage
from app.services.rate_limit import limiter
from app.services.store import store

router = APIRouter(prefix="/api/admin", tags=["admin"])


def authorize_admin(token: str | None = None, authorization: str | None = None) -> None:
    from app.routers.auth import resolve_user
    if token and settings.support_admin_token and secrets.compare_digest(token, settings.support_admin_token):
        return
    if authorization:
        user = resolve_user(authorization)
        if user and (user.get("role") == "admin" or user.get("username") in ("admin", "root", "administrator")):
            return
        if user:
            raise HTTPException(403, "Tài khoản của bạn không có quyền Quản trị viên (Role: User)")
    if not settings.support_admin_token:
        raise HTTPException(503, "Admin token is not configured")
    raise HTTPException(401, "Yêu cầu quyền Quản trị viên (Admin)")


def _dependency_statuses() -> dict:
    storage_ok = True
    rate_limiter_ok = True
    try:
        if store.__class__.__name__ == "PostgresStore":
            with store._connect() as connection:
                connection.execute("SELECT 1")
    except (psycopg.Error, RuntimeError):
        storage_ok = False
    try:
        if limiter.__class__.__name__ == "RedisRateLimiter":
            limiter.client.ping()
        elif hasattr(limiter, "available"):
            rate_limiter_ok = bool(limiter.available)
    except (RedisError, RuntimeError):
        rate_limiter_ok = False
    return {
        "storage": {
            "name": "postgresql" if store.__class__.__name__ == "PostgresStore" else "memory",
            "status": "ok" if storage_ok else "down",
        },
        "rate_limiter": {
            "name": "redis" if limiter.__class__.__name__ == "RedisRateLimiter" else "memory",
            "status": "ok" if rate_limiter_ok else "down",
        },
    }


def _provider_statuses() -> list[dict]:
    return [
        {
            "name": "AI",
            "mode": settings.ai_mode,
            "status": "offline" if settings.ai_mode == "offline" else (
                "ready" if settings.ai_api_key else "missing_credentials"
            ),
            "detail": (
                "Local deterministic offline adapter. No paid AI call is made."
                if settings.ai_mode == "offline"
                else settings.ai_model
            ),
        },
        {
            "name": "Weather",
            "mode": "open-meteo",
            "status": "ready" if settings.weather_enabled else "disabled",
            "detail": "Forecasts include fetched-at/provider metadata when enabled.",
        },
        {
            "name": "Amadeus",
            "mode": settings.amadeus_base_url,
            "status": (
                "ready" if settings.amadeus_client_id and settings.amadeus_client_secret
                else "missing_credentials"
            ),
            "detail": "Flights, hotels, activities and transfers fail closed without credentials.",
        },
        {
            "name": "OSRM",
            "mode": settings.osrm_base_url,
            "status": "ready" if settings.osrm_base_url else "missing_configuration",
            "detail": "Road-trip routing provider.",
        },
    ]


def _provider_diagnostics() -> dict:
    ai_ready = settings.ai_mode != "offline" and bool(settings.ai_api_key)
    preferred_ai_mode = settings.ai_mode if settings.ai_mode in {"groq", "deepseek"} else "groq"
    ai_key_env = "API_KEY_GROQ" if preferred_ai_mode == "groq" else "API_KEY_DEEPSEEK"
    ai_model_env = "TEN_MODEL_GROQ" if preferred_ai_mode == "groq" else "TEN_MODEL_DEEPSEEK"
    amadeus_ready = bool(settings.amadeus_client_id and settings.amadeus_client_secret)
    return {
        "ai": {
            "ready": ai_ready,
            "mode": settings.ai_mode,
            "model": settings.ai_model,
            "chat_model": settings.ai_chat_model,
            "base_url": settings.ai_base_url,
            "api_key_configured": bool(settings.ai_api_key),
            "api_key_length": len(settings.ai_api_key or ""),
            "circuit_breaker": breaker_status(),
            "required_env": ["AI_MODE", ai_key_env, ai_model_env],
            "next_action": (
                "AI provider is ready for paid calls."
                if ai_ready
                else f"Set AI_MODE to groq or deepseek and provide {ai_key_env}, then restart backend."
            ),
        },
        "weather": {
            "ready": settings.weather_enabled,
            "mode": "open-meteo",
            "required_env": ["WEATHER_ENABLED=true"],
            "next_action": (
                "Weather provider is enabled."
                if settings.weather_enabled
                else "Set WEATHER_ENABLED=true to fetch Open-Meteo forecast data."
            ),
        },
        "amadeus": {
            "ready": amadeus_ready,
            "base_url": settings.amadeus_base_url,
            "client_id_configured": bool(settings.amadeus_client_id),
            "client_secret_configured": bool(settings.amadeus_client_secret),
            "required_env": ["AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET", "AMADEUS_BASE_URL"],
            "next_action": (
                "Amadeus inventory provider is ready."
                if amadeus_ready
                else "Add Amadeus client id/secret to enable live flights, hotels, activities and transfers."
            ),
        },
        "google_places": google_places_readiness(),
        "osrm": {
            "ready": bool(settings.osrm_base_url),
            "base_url": settings.osrm_base_url,
            "required_env": ["OSRM_BASE_URL"],
            "next_action": "Use a private OSRM endpoint for production load." if settings.app_env != "local" else "Local/dev routing can use the public OSRM endpoint.",
        },
        "public_transit": public_transit_policy_status(),
        "route_calibration": route_calibration_status(),
        "official_event_calendar": official_event_calendar_status(),
    }


def _catalog_quality() -> dict:
    by_kind: dict[str, int] = {}
    by_source: dict[str, int] = {}
    tags: dict[str, int] = {}
    missing_source_url = 0
    unusual_hours = 0
    for place in PLACES:
        by_kind[place.kind] = by_kind.get(place.kind, 0) + 1
        by_source[place.source] = by_source.get(place.source, 0) + 1
        missing_source_url += 0 if source_for(place)[0] else 1
        if place.open_hour < 0 or place.open_hour > 23 or place.close_hour < 0 or place.close_hour > 24 or place.open_hour >= place.close_hour:
            unusual_hours += 1
        for tag in place.tags:
            tags[tag] = tags.get(tag, 0) + 1
    focus_city_counts = {
        key: sum(
            1
            for place in PLACES
            if haversine_km(
                float(destination["lat"]),
                float(destination["lng"]),
                place.lat,
                place.lng,
            )
            <= DESTINATION_RADIUS_KM
        )
        for key, destination in FOCUS_DESTINATIONS.items()
    }
    coverage = PLACE_METADATA.get("coverage", [])
    failing_coverage = [
        item for item in coverage
        if isinstance(item, dict) and item.get("passes_minimum") is False
    ][:10]
    return {
        "metadata": PLACE_METADATA,
        "distance_matrix": DISTANCE_METADATA,
        "place_count": len(PLACES),
        "source_url_coverage_percent": round(
            ((len(PLACES) - missing_source_url) / len(PLACES) * 100) if PLACES else 0, 2
        ),
        "missing_source_url": missing_source_url,
        "unusual_hours": unusual_hours,
        "kind_counts": dict(sorted(by_kind.items(), key=lambda item: item[1], reverse=True)[:12]),
        "source_counts": dict(sorted(by_source.items(), key=lambda item: item[1], reverse=True)[:8]),
        "focus_city_radius_km": DESTINATION_RADIUS_KM,
        "focus_city_counts": focus_city_counts,
        "top_tags": dict(sorted(tags.items(), key=lambda item: item[1], reverse=True)[:12]),
        "failing_coverage": failing_coverage,
        "field_coverage": catalogue_field_coverage(
            focus_destinations=FOCUS_DESTINATIONS,
            radius_km=DESTINATION_RADIUS_KM,
        ),
        "sample_places": [
            {
                "id": place.id,
                "name": place.name,
                "kind": place.kind,
                "area": place.area,
                "source": place.source,
                "source_url": source_for(place)[0],
                "open_hour": place.open_hour,
                "close_hour": place.close_hour,
            }
            for place in PLACES[:12]
        ],
    }


def _ai_quality() -> dict:
    items = store.list_all()
    fallback_notes = set(AI_FALLBACK_NOTE.values())
    fallback_count = 0
    for item in items:
        notes = item.plan.get("luu_y", [])
        if isinstance(notes, list) and any(note in fallback_notes for note in notes):
            fallback_count += 1
    total = len(items)
    deterministic_count = total if settings.ai_mode == "offline" else fallback_count
    return {
        "mode": settings.ai_mode,
        "model": settings.ai_model,
        "live_provider_ready": settings.ai_mode != "offline" and bool(settings.ai_api_key),
        "total_plans": total,
        "fallback_plan_count": fallback_count,
        "fallback_rate_percent": round((fallback_count / total * 100) if total else 0, 2),
        "deterministic_mode": settings.ai_mode == "offline",
        "deterministic_plan_count": deterministic_count,
        "deterministic_rate_percent": round((deterministic_count / total * 100) if total else 0, 2),
        "next_action": (
            "Set AI_MODE=groq and API_KEY_GROQ to enable paid AI assembly."
            if settings.ai_mode == "offline" or not settings.ai_api_key
            else "Monitor fallback rate and circuit breaker before increasing traffic."
        ),
    }


def _catalog_matches(q: str | None, kind: str | None, area: str | None, tag: str | None):
    query = (q or "").casefold().strip()
    kind_filter = (kind or "").casefold().strip()
    area_filter = (area or "").casefold().strip()
    tag_filter = (tag or "").casefold().strip()
    matches = []
    for place in PLACES:
        haystack = " ".join([place.name, place.kind, place.area, place.source, *place.tags]).casefold()
        if query and query not in haystack:
            continue
        if kind_filter and kind_filter != place.kind.casefold():
            continue
        if area_filter and area_filter not in place.area.casefold():
            continue
        if tag_filter and tag_filter not in {item.casefold() for item in place.tags}:
            continue
        matches.append(place)
    return matches


@router.get("/dashboard")
def dashboard(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    dependencies = _dependency_statuses()
    summary = store.admin_summary()
    return {
        "environment": settings.app_env,
        "ready": all(item["status"] == "ok" for item in dependencies.values()),
        "dependencies": dependencies,
        "providers": _provider_statuses(),
        "provider_diagnostics": _provider_diagnostics(),
        "limits": {
            "plan_per_session_hour": settings.max_generate_per_hour,
            "plan_per_ip_hour": settings.max_generate_ip_per_hour,
            "daily_ai_budget_usd": settings.daily_ai_budget_usd,
            "monthly_ai_budget_usd": settings.monthly_ai_budget_usd,
            "max_request_body_bytes": settings.max_request_body_bytes,
        },
        "ai_quality": _ai_quality(),
        "catalog_quality": _catalog_quality(),
        "summary": summary,
        "recent_events": store.recent_events(20),
        "booking_requests": store.list_booking_requests(),
        "user_reviews": store.list_user_reviews(limit=50),
    }


@router.get("/providers/diagnostics")
def provider_diagnostics(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    return _provider_diagnostics()


@router.get("/ai-quality")
def ai_quality(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    return _ai_quality()


@router.get("/release-readiness")
def release_readiness(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    benchmark = run_release_readiness_benchmark(build_plan)
    spec = audit_release_spec(build_plan)
    return {
        "benchmark": benchmark,
        "spec_audit": spec,
        "release_gate": {
            "pass": benchmark["summary"]["release_pass"] and spec["release_gate"]["pass"],
            "blockers": [
                *[
                    blocker
                    for result in benchmark["results"]
                    for blocker in result["release_gate"]["blockers"]
                ],
                *spec["release_gate"]["blockers"],
            ],
        },
    }


@router.get("/catalog/export.csv")
def catalog_export_csv(
    q: str | None = Query(default=None, max_length=120),
    kind: str | None = Query(default=None, max_length=80),
    area: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=80),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "kind", "area", "lat", "lng", "cost", "duration_min",
        "tags", "open_hour", "close_hour", "source", "source_url",
    ])
    for place in _catalog_matches(q, kind, area, tag):
        writer.writerow([
            place.id, place.name, place.kind, place.area, place.lat, place.lng,
            place.cost, place.duration_min, "|".join(place.tags), place.open_hour,
            place.close_hour, place.source, source_for(place)[0] or "",
        ])
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="catalog-export.csv"'},
    )


@router.get("/catalog/quality")
def catalog_quality(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    return _catalog_quality()


@router.get("/catalog")
def catalog(
    q: str | None = Query(default=None, max_length=120),
    kind: str | None = Query(default=None, max_length=80),
    area: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=30, ge=1, le=100),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    matches = _catalog_matches(q, kind, area, tag)
    items = [
        {
            "id": place.id,
            "name": place.name,
            "kind": place.kind,
            "area": place.area,
            "lat": place.lat,
            "lng": place.lng,
            "cost": place.cost,
            "duration_min": place.duration_min,
            "tags": list(place.tags),
            "open_hour": place.open_hour,
            "close_hour": place.close_hour,
            "source": place.source,
            "source_url": source_for(place)[0],
        }
        for place in matches[:limit]
    ]
    return {"total": len(matches), "limit": limit, "items": items}


@router.get("/plans")
def plans(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    query = (q or "").casefold().strip()
    rows = []
    for item in store.list_all():
        title = str(item.plan.get("tieu_de", ""))
        summary = str(item.plan.get("tom_tat", ""))
        haystack = " ".join([item.token, item.session_id, item.user_id or "", title, summary]).casefold()
        if query and query not in haystack:
            continue
        rows.append({
            "token": item.token,
            "session_id": item.session_id,
            "user_id": item.user_id,
            "version": item.version,
            "title": title,
            "summary": summary,
            "departure_date": item.request.get("ngay_di"),
            "duration": item.request.get("thoi_luong"),
            "people": item.request.get("so_nguoi"),
            "language": item.request.get("ngon_ngu", "vi"),
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        })
    rows.sort(key=lambda value: value["expires_at"] or "", reverse=True)
    return {"total": len(rows), "limit": limit, "items": rows[:limit]}


@router.get("/users")
def users(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    matches = store.admin_users((q or "").strip(), 1000)
    return {"total": len(matches), "limit": limit, "items": matches[:limit]}


@router.get("/ai-usage")
def ai_usage(
    limit: int = Query(default=30, ge=1, le=100),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    items = store.admin_ai_usage(limit)
    return {"total": len(items), "limit": limit, "items": items}


@router.get("/events")
def events(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    items = store.admin_events((q or "").strip(), limit)
    return {"total": len(items), "limit": limit, "items": items}


@router.post("/maintenance/cleanup-expired")
def cleanup_expired(
    x_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    authorize_admin(x_admin_token, authorization)
    removed = store.cleanup_expired()
    store.log("admin-maintenance", "admin_cleanup_expired", {"removed_plans": removed})
    return {"removed_plans": removed}
