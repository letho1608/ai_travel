"""Lazy Google Places enrichment for itinerary slots.

This intentionally runs only for places that already appear in a generated
plan. It never imports the whole catalog, and it caches successful lookups so a
place is not billed repeatedly across later plans.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any

from app.config import settings
from app.data import DATA_DIR

GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"
CACHE_PATH = DATA_DIR / "google_place_cache.json"


def google_places_readiness() -> dict[str, Any]:
    blockers: list[str] = []
    if not settings.google_maps_api_key:
        blockers.append("GOOGLE_MAPS_API_KEY is not configured.")
    if settings.google_places_runtime_per_plan_cap <= 0:
        blockers.append("GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP must be > 0.")
    if settings.google_places_text_search_daily_cap <= 0 or settings.google_places_text_search_monthly_cap <= 0:
        blockers.append("Google Places text-search daily/monthly caps must be > 0.")
    if settings.google_places_runtime_photos and (
        settings.google_places_photo_daily_cap <= 0 or settings.google_places_photo_monthly_cap <= 0
    ):
        blockers.append("Google Places photo caps must be > 0 when runtime photos are enabled.")
    if settings.google_places_runtime_hours and (
        settings.google_places_hours_daily_cap <= 0 or settings.google_places_hours_monthly_cap <= 0
    ):
        blockers.append("Google Places hours caps must be > 0 when runtime hours are enabled.")
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "missing_or_invalid_configuration",
        "api_key_configured": bool(settings.google_maps_api_key),
        "api_key_length": len(settings.google_maps_api_key or ""),
        "runtime_per_plan_cap": settings.google_places_runtime_per_plan_cap,
        "text_search_daily_cap": settings.google_places_text_search_daily_cap,
        "text_search_monthly_cap": settings.google_places_text_search_monthly_cap,
        "runtime_photos": settings.google_places_runtime_photos,
        "photo_daily_cap": settings.google_places_photo_daily_cap,
        "photo_monthly_cap": settings.google_places_photo_monthly_cap,
        "runtime_hours": settings.google_places_runtime_hours,
        "hours_daily_cap": settings.google_places_hours_daily_cap,
        "hours_monthly_cap": settings.google_places_hours_monthly_cap,
        "blockers": blockers,
    }


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"metadata": {}, "places": {}}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"metadata": {}, "places": {}}
    if not isinstance(payload, dict):
        return {"metadata": {}, "places": {}}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    places = payload.get("places") if isinstance(payload.get("places"), dict) else {}
    return {"metadata": metadata, "places": places}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _usage_bucket(cache: dict[str, Any], sku: str, period: str, value: str) -> dict[str, Any]:
    usage_root = cache.setdefault("metadata", {}).setdefault("usage", {})
    usage = usage_root.setdefault(sku, {}).setdefault(period, {})
    if usage.get("value") != value:
        usage["value"] = value
        usage["requests"] = 0
    return usage


def _today_usage(cache: dict[str, Any], sku: str) -> int:
    today = date.today().isoformat()
    usage = _usage_bucket(cache, sku, "daily", today)
    return int(usage.get("requests", 0))


def _month_usage(cache: dict[str, Any], sku: str) -> int:
    month = date.today().strftime("%Y-%m")
    usage = _usage_bucket(cache, sku, "monthly", month)
    return int(usage.get("requests", 0))


def _record_request(cache: dict[str, Any], sku: str) -> None:
    _today_usage(cache, sku)
    _month_usage(cache, sku)
    usage = cache["metadata"]["usage"][sku]
    daily = usage["daily"]
    monthly = usage["monthly"]
    daily["requests"] = int(daily.get("requests", 0)) + 1
    monthly["requests"] = int(monthly.get("requests", 0)) + 1


def _quota_available(cache: dict[str, Any], sku: str, daily_cap: int, monthly_cap: int) -> bool:
    return _today_usage(cache, sku) < daily_cap and _month_usage(cache, sku) < monthly_cap


def _photo_url(photo_name: str, api_key: str) -> str:
    return (
        GOOGLE_PHOTO_MEDIA_URL.format(photo_name=photo_name)
        + "?"
        + urllib.parse.urlencode({"maxWidthPx": 800, "key": api_key})
    )


def _opening_hours_fields(google: dict[str, Any]) -> dict[str, Any]:
    regular = google.get("regularOpeningHours")
    current = google.get("currentOpeningHours")
    enriched: dict[str, Any] = {}
    if isinstance(regular, dict):
        enriched["google_regular_opening_hours"] = regular
    if isinstance(current, dict):
        enriched["google_current_opening_hours"] = current
    if isinstance(current, dict) and "openNow" in current:
        enriched["google_open_now"] = current.get("openNow")
    elif isinstance(regular, dict) and "openNow" in regular:
        enriched["google_open_now"] = regular.get("openNow")
    descriptions = None
    if isinstance(current, dict):
        descriptions = current.get("weekdayDescriptions")
    if not descriptions and isinstance(regular, dict):
        descriptions = regular.get("weekdayDescriptions")
    if isinstance(descriptions, list):
        enriched["google_weekday_descriptions"] = [
            item for item in descriptions if isinstance(item, str)
        ]
    if google.get("businessStatus"):
        enriched["google_business_status"] = google.get("businessStatus")
    return enriched


def _fetch_google_slot(
    slot: dict[str, Any],
    api_key: str,
    *,
    include_photos: bool = False,
    include_hours: bool = False,
) -> dict[str, Any] | None:
    coordinates = slot.get("toa_do") if isinstance(slot.get("toa_do"), dict) else {}
    lat = coordinates.get("lat")
    lng = coordinates.get("lng")
    name = str(slot.get("ten_dia_diem") or "").strip()
    if not name or not isinstance(lat, int | float) or not isinstance(lng, int | float):
        return None
    query_text = f"{name} Việt Nam"
    body = json.dumps(
        {
            "textQuery": query_text,
            "languageCode": "vi",
            "regionCode": "VN",
            "locationBias": {
                "circle": {
                    "center": {"latitude": float(lat), "longitude": float(lng)},
                    "radius": 1200.0,
                }
            },
            "pageSize": 1,
        }
    ).encode()
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,"
        "places.googleMapsUri,places.rating,places.userRatingCount"
    )
    if include_photos:
        field_mask += ",places.photos"
    if include_hours:
        field_mask += ",places.currentOpeningHours,places.regularOpeningHours,places.businessStatus"
    request = urllib.request.Request(
        GOOGLE_TEXT_SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        places = json.load(response).get("places", [])
    if not places:
        return None
    google = places[0]
    photos = google.get("photos") or []
    photo_name = (
        photos[0].get("name")
        if include_photos and photos and isinstance(photos[0], dict)
        else None
    )
    enriched = {
        "google_place_id": google.get("id"),
        "google_maps_url": google.get("googleMapsUri"),
        "google_rating": google.get("rating"),
        "google_user_rating_count": google.get("userRatingCount"),
        "dia_chi_google": google.get("formattedAddress"),
        "google_photo_name": photo_name,
        "google_updated_at": datetime.now(UTC).isoformat(),
    }
    if include_hours:
        enriched.update(_opening_hours_fields(google))
    return {key: value for key, value in enriched.items() if value is not None}


def _apply_enrichment(slot: dict[str, Any], enriched: dict[str, Any], api_key: str) -> None:
    if enriched.get("negative"):
        return
    for key, value in enriched.items():
        if value is not None:
            slot[key] = value
    if enriched.get("google_maps_url"):
        slot["google_review_url"] = enriched["google_maps_url"]
    rating = enriched.get("google_rating")
    review_count = enriched.get("google_user_rating_count")
    if rating is not None or review_count is not None:
        slot["thong_tin_danh_gia"] = {
            "rating": rating,
            "so_nhan_xet": review_count,
            "nguon": "Google Places API",
            "nguon_url": enriched.get("google_maps_url"),
            "lay_luc": enriched.get("google_updated_at"),
        }
        evidence = slot.get("bang_chung") if isinstance(slot.get("bang_chung"), dict) else None
        if evidence is not None:
            google_evidence = {
                "rating": rating,
                "so_nhan_xet": review_count,
                "nguon": "Google Places API",
                "nguon_url": enriched.get("google_maps_url"),
                "lay_luc": enriched.get("google_updated_at"),
            }
            evidence["thong_tin_danh_gia"] = google_evidence
            ranking = evidence.get("xep_hang")
            if isinstance(ranking, dict):
                facts = ranking.setdefault("du_lieu_thuc_te", {})
                if isinstance(facts, dict):
                    facts["rating"] = rating
                    facts["so_nhan_xet"] = review_count
                missing = ranking.get("du_lieu_thieu")
                if isinstance(missing, list):
                    ranking["du_lieu_thieu"] = [
                        item for item in missing if item not in {"rating", "so_review"}
                    ]
    photo_name = enriched.get("google_photo_name")
    if settings.google_places_runtime_photos and photo_name:
        slot["anh"] = _photo_url(str(photo_name), api_key)
        slot["anh_nguon"] = "Google Places"


def enrich_plan_with_google(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a plan enriched with Google data for only scheduled slots."""
    api_key = settings.google_maps_api_key
    if not api_key:
        return plan
    result = deepcopy(plan)
    cache = _load_cache()
    cache_places = cache.setdefault("places", {})
    per_plan_remaining = max(0, settings.google_places_runtime_per_plan_cap)
    text_daily_cap = max(0, settings.google_places_text_search_daily_cap)
    text_monthly_cap = max(0, settings.google_places_text_search_monthly_cap)
    photo_daily_cap = max(0, settings.google_places_photo_daily_cap)
    photo_monthly_cap = max(0, settings.google_places_photo_monthly_cap)
    hours_daily_cap = max(0, settings.google_places_hours_daily_cap)
    hours_monthly_cap = max(0, settings.google_places_hours_monthly_cap)
    request_count = 0
    photo_count = 0
    hours_count = 0
    cache_hits = 0
    quota_blocked = 0
    photo_quota_blocked = 0
    hours_quota_blocked = 0
    cache_changed = False
    for day in result.get("ngay", []):
        slots = day.get("khoang_gio") if isinstance(day, dict) else None
        if not isinstance(slots, list):
            continue
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            slot_id = str(slot.get("dia_diem_id") or "")
            if not slot_id:
                continue
            wants_photo = settings.google_places_runtime_photos
            wants_hours = settings.google_places_runtime_hours
            cached = cache_places.get(slot_id)
            if isinstance(cached, dict):
                _apply_enrichment(slot, cached, api_key)
                cache_hits += 1
                has_cached_photo = bool(cached.get("google_photo_name"))
                has_cached_hours = bool(
                    cached.get("google_regular_opening_hours")
                    or cached.get("google_current_opening_hours")
                    or cached.get("google_business_status")
                )
                if cached.get("negative") or (
                    (not wants_photo or has_cached_photo)
                    and (not wants_hours or has_cached_hours)
                ):
                    continue
            if (
                per_plan_remaining <= 0
                or text_daily_cap <= 0
                or text_monthly_cap <= 0
                or not _quota_available(
                    cache, "text_search", text_daily_cap, text_monthly_cap
                )
            ):
                quota_blocked += 1
                continue
            has_photo_quota = wants_photo and _quota_available(
                cache, "photo", photo_daily_cap, photo_monthly_cap
            )
            if wants_photo and not has_photo_quota:
                photo_quota_blocked += 1
            has_hours_quota = wants_hours and _quota_available(
                cache, "hours", hours_daily_cap, hours_monthly_cap
            )
            if wants_hours and not has_hours_quota:
                hours_quota_blocked += 1
            _record_request(cache, "text_search")
            request_count += 1
            per_plan_remaining -= 1
            cache_changed = True
            try:
                enriched = _fetch_google_slot(
                    slot,
                    api_key,
                    include_photos=has_photo_quota,
                    include_hours=has_hours_quota,
                )
            except Exception:
                continue
            if not enriched:
                cache_places[slot_id] = {
                    "negative": True,
                    "google_updated_at": datetime.now(UTC).isoformat(),
                }
                continue
            if enriched.get("google_photo_name") and has_photo_quota:
                _record_request(cache, "photo")
                photo_count += 1
            elif enriched.get("google_photo_name"):
                enriched.pop("google_photo_name", None)
            if (
                has_hours_quota
                and (
                    enriched.get("google_regular_opening_hours")
                    or enriched.get("google_current_opening_hours")
                    or enriched.get("google_business_status")
                )
            ):
                _record_request(cache, "hours")
                hours_count += 1
            cache_places[slot_id] = enriched
            _apply_enrichment(slot, enriched, api_key)
    if cache_changed:
        _save_cache(cache)
    result["google_places"] = {
        "enabled": True,
        "cache_hits": cache_hits,
        "text_search_requests_this_plan": request_count,
        "photo_requests_this_plan": photo_count,
        "text_search_daily_cap": text_daily_cap,
        "text_search_daily_used": _today_usage(cache, "text_search"),
        "text_search_monthly_cap": text_monthly_cap,
        "text_search_monthly_used": _month_usage(cache, "text_search"),
        "photo_daily_cap": photo_daily_cap,
        "photo_daily_used": _today_usage(cache, "photo"),
        "photo_monthly_cap": photo_monthly_cap,
        "photo_monthly_used": _month_usage(cache, "photo"),
        "hours_daily_cap": hours_daily_cap,
        "hours_daily_used": _today_usage(cache, "hours"),
        "hours_monthly_cap": hours_monthly_cap,
        "hours_monthly_used": _month_usage(cache, "hours"),
        "hours_requests_this_plan": hours_count,
        "per_plan_cap": settings.google_places_runtime_per_plan_cap,
        "quota_blocked": quota_blocked,
        "photo_quota_blocked": photo_quota_blocked,
        "hours_quota_blocked": hours_quota_blocked,
    }
    return result
