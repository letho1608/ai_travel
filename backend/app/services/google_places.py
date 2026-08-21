"""Lazy Google Places enrichment for itinerary slots.

This intentionally runs only for places that already appear in a generated
plan. It never imports the whole catalog, and it caches successful lookups so a
place is not billed repeatedly across later plans.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any

from app.config import settings
from app.data import DATA_DIR
from app.services.place_images import ensure_plan_cover
from app.text_utils import ascii_fold

GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
GOOGLE_PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"
GOOGLE_LEGACY_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_LEGACY_PHOTO_URL = "https://maps.googleapis.com/maps/api/place/photo"
CACHE_PATH = DATA_DIR / "google_place_cache.json"
VIETNAM_LAT = (8.0, 24.5)
VIETNAM_LNG = (102.0, 110.5)
MAP_SEARCH_RADIUS_M = 50_000.0
MAP_SEARCH_RADIUS_KM = 55.0


def _slot_has_image(slot: dict[str, Any]) -> bool:
    url = slot.get("anh")
    return isinstance(url, str) and url.startswith("http")


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
    lookups = payload.get("lookups") if isinstance(payload.get("lookups"), dict) else {}
    return {"metadata": metadata, "places": places, "lookups": lookups}


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


def _places_http_blocked(exc: BaseException) -> bool:
    """True when Google rejected the key/method; those calls are not billed usage."""
    return isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403}


def _legacy_photo_url(photo_reference: str, api_key: str) -> str:
    return (
        GOOGLE_LEGACY_PHOTO_URL
        + "?"
        + urllib.parse.urlencode(
            {"maxwidth": 800, "photo_reference": photo_reference, "key": api_key}
        )
    )


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


def _place_id_value(place_id: str | None) -> str:
    raw = str(place_id or "").strip()
    if raw.startswith("places/"):
        raw = raw.split("/", 1)[1]
    return raw


def _named_maps_url(name: str, place_id: str | None) -> str:
    pid = _place_id_value(place_id)
    if pid:
        return f"https://www.google.com/maps/place/?q=place_id:{urllib.parse.quote(pid, safe='')}"
    query = urllib.parse.quote_plus(" ".join(str(name or "").split()))
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _coord_pin_url(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def _legacy_slot_lookup(slot: dict[str, Any], api_key: str) -> dict[str, Any] | None:
    """Find the Google place nearest the itinerary pin via the legacy Text Search API."""
    from app.pipeline.routing import haversine_km

    name = str(slot.get("ten_dia_diem") or "").strip()
    coordinates = slot.get("toa_do") if isinstance(slot.get("toa_do"), dict) else {}
    lat = coordinates.get("lat")
    lng = coordinates.get("lng")
    if not name or not isinstance(lat, int | float) or not isinstance(lng, int | float):
        return None
    city = str(slot.get("khu_vuc") or "").strip()
    query = " ".join(part for part in (name, city) if part)
    params = {
        "query": query,
        "language": "vi",
        "region": "vn",
        "location": f"{float(lat)},{float(lng)}",
        "radius": 500,
        "key": api_key,
    }
    url = GOOGLE_LEGACY_TEXT_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.load(response)
    except (OSError, TimeoutError, ValueError, TypeError, urllib.error.HTTPError):
        return None
    if str(payload.get("status") or "") not in {"OK", "ZERO_RESULTS"}:
        return None
    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        location = ((row.get("geometry") or {}).get("location") if isinstance(row.get("geometry"), dict) else {}) or {}
        try:
            hit_lat = float(location["lat"])
            hit_lng = float(location["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        ranked.append((haversine_km(float(lat), float(lng), hit_lat, hit_lng), row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    row = ranked[0][1]
    place_id = _place_id_value(row.get("place_id"))
    label = str(row.get("name") or name).strip()
    if not place_id or not label:
        return None
    return {
        "google_place_id": place_id,
        "display_name": label,
        "google_maps_url": _named_maps_url(label, place_id),
        "dia_chi_google": row.get("formatted_address"),
        "google_rating": row.get("rating"),
        "google_user_rating_count": row.get("user_ratings_total"),
        "google_updated_at": datetime.now(UTC).isoformat(),
    }


def _places_post(url: str, payload: dict[str, Any], api_key: str, field_mask: str) -> list[Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            places = json.load(response).get("places", [])
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise
        return []
    except (TimeoutError, urllib.error.URLError, json.JSONDecodeError, OSError):
        return []
    return places if isinstance(places, list) else []


def _google_place_coords(row: dict[str, Any]) -> tuple[float, float] | None:
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    try:
        return float(location["latitude"]), float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return None


def _nearest_google_place(places: list[Any], lat: float, lng: float) -> dict[str, Any] | None:
    from app.pipeline.routing import haversine_km

    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in places:
        if not isinstance(row, dict):
            continue
        coords = _google_place_coords(row)
        if coords is None:
            continue
        ranked.append((haversine_km(lat, lng, coords[0], coords[1]), row))
    if ranked:
        ranked.sort(key=lambda item: item[0])
        return ranked[0][1]
    first = places[0] if places else None
    return first if isinstance(first, dict) else None


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
    city = str(slot.get("khu_vuc") or "").strip()
    query_text = " ".join(part for part in (name, city) if part) or name
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.googleMapsUri,places.rating,places.userRatingCount"
    )
    if include_photos:
        field_mask += ",places.photos"
    if include_hours:
        field_mask += ",places.currentOpeningHours,places.regularOpeningHours,places.businessStatus"
    center = {"latitude": float(lat), "longitude": float(lng)}
    nearby_payload = {
        "languageCode": "vi",
        "regionCode": "VN",
        "maxResultCount": 5,
        "rankPreference": "DISTANCE",
        "includedTypes": [
            "restaurant", "cafe", "coffee_shop", "bakery", "bar",
            "tourist_attraction", "park", "museum", "church", "hindu_temple",
            "lodging", "market", "shopping_mall", "point_of_interest",
        ],
        "locationRestriction": {"circle": {"center": center, "radius": 150.0}},
    }
    places = _places_post(GOOGLE_NEARBY_SEARCH_URL, nearby_payload, api_key, field_mask)
    if not places:
        text_payload = {
            "textQuery": query_text,
            "languageCode": "vi",
            "regionCode": "VN",
            "pageSize": 5,
            "locationBias": {"circle": {"center": center, "radius": 800.0}},
        }
        places = _places_post(GOOGLE_TEXT_SEARCH_URL, text_payload, api_key, field_mask)
    if not places:
        return None
    google = _nearest_google_place(places, float(lat), float(lng))
    if not google:
        return None
    photos = google.get("photos") or []
    photo_name = (
        photos[0].get("name")
        if include_photos and photos and isinstance(photos[0], dict)
        else None
    )
    display = google.get("displayName") if isinstance(google.get("displayName"), dict) else {}
    label = str(display.get("text") or name).strip()
    place_id = _place_id_value(google.get("id")) or None
    enriched = {
        "google_place_id": place_id,
        "display_name": label,
        "google_maps_url": _named_maps_url(label, place_id),
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
    place_id = slot.get("google_place_id")
    label = str(slot.get("ten_dia_diem") or "").strip()
    if place_id and label:
        slot["google_maps_url"] = _named_maps_url(label, str(place_id))
        slot["google_review_url"] = slot["google_maps_url"]
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
    if photo_name and not _slot_has_image(slot):
        slot["anh"] = _photo_url(str(photo_name), api_key)
        slot["anh_nguon"] = "Google Places"


def resolve_maps_place_url(
    *,
    name: str,
    lat: float,
    lng: float,
    city: str = "",
    slot_id: str = "",
) -> str:
    """Return a Google Maps URL that opens one named place, not a search list."""
    label = " ".join(part for part in (str(name or "").strip(), str(city or "").strip()) if part)
    cache = _load_cache()
    cache_places = cache.setdefault("places", {})
    if slot_id:
        cached = cache_places.get(slot_id)
        if isinstance(cached, dict) and not cached.get("negative"):
            place_id = str(cached.get("google_place_id") or "").strip()
            if place_id:
                cached_name = str(cached.get("display_name") or name or label).strip()
                return _named_maps_url(cached_name, place_id)
    api_key = settings.google_maps_api_key
    if not api_key:
        return _coord_pin_url(lat, lng)
    text_daily_cap = max(0, settings.google_places_text_search_daily_cap)
    text_monthly_cap = max(0, settings.google_places_text_search_monthly_cap)
    if not _quota_available(cache, "text_search", text_daily_cap, text_monthly_cap):
        return _coord_pin_url(lat, lng)
    slot = {
        "ten_dia_diem": str(name or "").strip(),
        "toa_do": {"lat": float(lat), "lng": float(lng)},
        "khu_vuc": str(city or "").strip(),
    }
    try:
        enriched = _fetch_google_slot(slot, api_key)
    except Exception:
        enriched = None
    if not (isinstance(enriched, dict) and enriched.get("google_place_id")):
        enriched = _legacy_slot_lookup(slot, api_key)
    _record_request(cache, "text_search")
    if enriched and enriched.get("google_place_id"):
        if slot_id:
            cache_places[slot_id] = dict(enriched)
        _save_cache(cache)
        maps_url = str(enriched.get("google_maps_url") or "").strip()
        if maps_url.startswith("https://www.google.com/maps/place/?q=place_id:"):
            return maps_url
        return _named_maps_url(str(enriched.get("display_name") or name or label), str(enriched["google_place_id"]))
    _save_cache(cache)
    return _coord_pin_url(lat, lng)


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
    places_api_blocked = False
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
            wants_photo = not _slot_has_image(slot)
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
                places_api_blocked
                or per_plan_remaining <= 0
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
            try:
                enriched = _fetch_google_slot(
                    slot,
                    api_key,
                    include_photos=has_photo_quota,
                    include_hours=has_hours_quota,
                )
            except Exception as exc:
                if _places_http_blocked(exc):
                    places_api_blocked = True
                continue
            _record_request(cache, "text_search")
            request_count += 1
            per_plan_remaining -= 1
            cache_changed = True
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
    ensure_plan_cover(result)
    return result


_GOOGLE_KIND_BY_TYPE = {
    "museum": "bao_tang",
    "art_gallery": "bao_tang",
    "restaurant": "nha_hang",
    "cafe": "cafe",
    "coffee_shop": "cafe",
    "park": "cong_vien",
    "amusement_park": "giai_tri",
    "tourist_attraction": "dia_danh",
    "church": "den_chua",
    "hindu_temple": "den_chua",
    "mosque": "den_chua",
    "pagoda": "den_chua",
    "place_of_worship": "den_chua",
    "beach": "bai_bien",
    "natural_feature": "dia_danh",
    "market": "cho",
}


def _kind_from_google_types(types: list[str] | None) -> str:
    for google_type in types or []:
        kind = _GOOGLE_KIND_BY_TYPE.get(str(google_type))
        if kind:
            return kind
    return "dia_danh"


def _area_from_google_address(address: str, fallback: str | None) -> str:
    parts = [part.strip() for part in str(address or "").split(",") if part.strip()]
    parts = [part for part in parts if ascii_fold(part) not in {"viet nam", "vietnam"}]
    return parts[-1] if parts else (fallback or "Việt Nam")


def _google_name_rank(folded_query: str, folded_label: str) -> int:
    if not folded_query or not folded_label:
        return 2
    if folded_query == folded_label or folded_query in folded_label or folded_label in folded_query:
        return 0
    query_tokens = {token for token in folded_query.split() if len(token) >= 3}
    label_tokens = set(folded_label.split())
    if query_tokens and query_tokens <= label_tokens:
        return 0
    if query_tokens and len(query_tokens & label_tokens) >= min(2, len(query_tokens)):
        return 1
    return 2


def _search_named_place_legacy(
    query: str,
    origin: tuple[float, float],
    city: str | None,
    cache: dict[str, Any],
    include_photos: bool,
) -> Any | None:
    from app.data import Place
    from app.pipeline.routing import haversine_km

    api_key = settings.google_maps_api_key
    if not api_key:
        return None
    params = {
        "query": f"{query} {city} Việt Nam" if city else f"{query} Việt Nam",
        "language": "vi",
        "region": "vn",
        "location": f"{origin[0]},{origin[1]}",
        "radius": int(MAP_SEARCH_RADIUS_M),
        "key": api_key,
    }
    url = GOOGLE_LEGACY_TEXT_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.load(response)
    except (OSError, TimeoutError, ValueError, TypeError):
        return None
    if str(payload.get("status") or "") not in {"OK", "ZERO_RESULTS"}:
        return None
    _record_request(cache, "text_search")
    folded_query = ascii_fold(query)
    scored: list[tuple[int, float, dict]] = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        location = ((row.get("geometry") or {}).get("location") if isinstance(row.get("geometry"), dict) else {}) or {}
        try:
            lat = float(location.get("lat"))
            lng = float(location.get("lng"))
        except (TypeError, ValueError):
            continue
        if not (VIETNAM_LAT[0] <= lat <= VIETNAM_LAT[1] and VIETNAM_LNG[0] <= lng <= VIETNAM_LNG[1]):
            continue
        if haversine_km(origin[0], origin[1], lat, lng) > MAP_SEARCH_RADIUS_KM:
            continue
        label = str(row.get("name") or "").strip()
        name_rank = _google_name_rank(folded_query, ascii_fold(label))
        if name_rank > 1:
            continue
        scored.append((name_rank, haversine_km(origin[0], origin[1], lat, lng), row))
    if not scored:
        return None
    row = min(scored, key=lambda item: (item[0], item[1]))[2]
    location = ((row.get("geometry") or {}).get("location") if isinstance(row.get("geometry"), dict) else {}) or {}
    lat = float(location["lat"])
    lng = float(location["lng"])
    label = str(row.get("name") or query).strip()
    place_id = str(row.get("place_id") or "").strip()
    if not place_id or not label:
        return None
    maps_url = _named_maps_url(label, place_id)
    photos = row.get("photos") or []
    photo_ref = photos[0].get("photo_reference") if include_photos and photos and isinstance(photos[0], dict) else None
    image_url = _legacy_photo_url(str(photo_ref), api_key) if photo_ref else None
    if photo_ref:
        _record_request(cache, "photo")
    rating = row.get("rating")
    reviews = row.get("user_ratings_total")
    return Place(
        id=f"google-{place_id}",
        name=label,
        kind=_kind_from_google_types(row.get("types") if isinstance(row.get("types"), list) else None),
        area=_area_from_google_address(str(row.get("formatted_address") or ""), city),
        lat=lat,
        lng=lng,
        cost=0,
        duration_min=75,
        tags=("map_verified", "google_verified"),
        open_hour=7,
        close_hour=22,
        source="Google Places",
        source_url=maps_url,
        image_url=image_url,
        image_credit="Google Places" if image_url else None,
        rating=float(rating) if isinstance(rating, int | float) else None,
        review_count=int(reviews) if isinstance(reviews, int | float) else None,
        google_place_id=place_id,
        google_maps_url=maps_url,
    )


def search_named_place(
    name: str,
    origin: tuple[float, float],
    city: str | None = None,
) -> Any | None:
    """Look up a user-typed place on Google Maps. Returns a Place or None."""
    from app.data import Place
    from app.pipeline.routing import haversine_km

    query = " ".join(str(name or "").split())
    if not query or not settings.google_maps_api_key:
        return None
    cache = _load_cache()
    lookup_key = f"{ascii_fold(query)}|{ascii_fold(city or '')}|{origin[0]:.2f}|{origin[1]:.2f}|area"
    lookups = cache.setdefault("lookups", {})
    cached = lookups.get(lookup_key)
    if isinstance(cached, dict):
        if cached.get("negative"):
            return None
        try:
            data = {key: value for key, value in cached.items() if key in Place.__dataclass_fields__}
            if isinstance(data.get("tags"), list):
                data["tags"] = tuple(data["tags"])
            return Place(**data)
        except (TypeError, ValueError):
            pass
    if not _quota_available(
        cache,
        "text_search",
        settings.google_places_text_search_daily_cap,
        settings.google_places_text_search_monthly_cap,
    ):
        return None
    include_photos = _quota_available(
        cache,
        "photo",
        settings.google_places_photo_daily_cap,
        settings.google_places_photo_monthly_cap,
    )
    query_text = f"{query} {city} Việt Nam" if city else f"{query} Việt Nam"
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.types,places.googleMapsUri,places.rating,places.userRatingCount"
    )
    if include_photos:
        field_mask += ",places.photos"
    body = json.dumps(
        {
            "textQuery": query_text,
            "languageCode": "vi",
            "regionCode": "VN",
            "locationBias": {
                "circle": {
                    "center": {"latitude": float(origin[0]), "longitude": float(origin[1])},
                    "radius": MAP_SEARCH_RADIUS_M,
                }
            },
            "pageSize": 5,
        }
    ).encode()
    request = urllib.request.Request(
        GOOGLE_TEXT_SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_maps_api_key,
            "X-Goog-FieldMask": field_mask,
        },
    )
    rows: list[dict] = []
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            rows = json.load(response).get("places") or []
        _record_request(cache, "text_search")
    except urllib.error.HTTPError as exc:
        if not _places_http_blocked(exc):
            lookups[lookup_key] = {"negative": True}
            _save_cache(cache)
            return None
        rows = []
    except (OSError, TimeoutError, ValueError, TypeError):
        rows = []
    folded_query = ascii_fold(query)
    scored: list[tuple[int, float, dict]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        try:
            lat = float(location.get("latitude"))
            lng = float(location.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not (VIETNAM_LAT[0] <= lat <= VIETNAM_LAT[1] and VIETNAM_LNG[0] <= lng <= VIETNAM_LNG[1]):
            continue
        if haversine_km(origin[0], origin[1], lat, lng) > MAP_SEARCH_RADIUS_KM:
            continue
        display = row.get("displayName") if isinstance(row.get("displayName"), dict) else {}
        label = str(display.get("text") or "").strip()
        folded_label = ascii_fold(label)
        name_rank = _google_name_rank(folded_query, folded_label)
        if name_rank > 1:
            continue
        scored.append((name_rank, haversine_km(origin[0], origin[1], lat, lng), row))
    chosen = None
    if scored:
        row = min(scored, key=lambda item: (item[0], item[1]))[2]
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        lat = float(location["latitude"])
        lng = float(location["longitude"])
        display = row.get("displayName") if isinstance(row.get("displayName"), dict) else {}
        label = str(display.get("text") or query).strip()
        place_id = str(row.get("id") or "").strip()
        if place_id and label:
            maps_url = _named_maps_url(label, place_id)
            rating = row.get("rating")
            reviews = row.get("userRatingCount")
            photos = row.get("photos") or []
            photo_name = photos[0].get("name") if include_photos and photos and isinstance(photos[0], dict) else None
            image_url = _photo_url(str(photo_name), settings.google_maps_api_key) if photo_name else None
            if photo_name:
                _record_request(cache, "photo")
            chosen = Place(
                id=f"google-{place_id}",
                name=label,
                kind=_kind_from_google_types(row.get("types") if isinstance(row.get("types"), list) else None),
                area=_area_from_google_address(str(row.get("formattedAddress") or ""), city),
                lat=lat,
                lng=lng,
                cost=0,
                duration_min=75,
                tags=("map_verified", "google_verified"),
                open_hour=7,
                close_hour=22,
                source="Google Places",
                source_url=str(maps_url),
                image_url=image_url,
                image_credit="Google Places" if image_url else None,
                rating=float(rating) if isinstance(rating, int | float) else None,
                review_count=int(reviews) if isinstance(reviews, int | float) else None,
                google_place_id=place_id,
                google_maps_url=str(maps_url),
            )
    if chosen is None:
        chosen = _search_named_place_legacy(query, origin, city, cache, include_photos)
    if chosen:
        cached_place = {key: getattr(chosen, key) for key in chosen.__dataclass_fields__}
        cached_place["tags"] = list(chosen.tags)
        lookups[lookup_key] = cached_place
    else:
        lookups[lookup_key] = {"negative": True}
    _save_cache(cache)
    return chosen
