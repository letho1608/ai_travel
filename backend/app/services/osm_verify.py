import json
import re

import httpx

from app.data import DATA_DIR, PLACES, Place
from app.pipeline.routing import haversine_km
from app.text_utils import ascii_fold

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CACHE_PATH = DATA_DIR / "osm_verify_cache.json"
USER_AGENT = "MinhDiDauTheLocalTest/1.0"
ALLOWED_NOMINATIM_CLASSES = {
    "amenity",
    "tourism",
    "leisure",
    "historic",
    "natural",
    "place",
    "boundary",
}
ALLOWED_NOMINATIM_TYPES = {
    "attraction",
    "archipelago",
    "bay",
    "beach",
    "cafe",
    "cape",
    "fast_food",
    "food_court",
    "island",
    "islet",
    "marketplace",
    "memorial",
    "monument",
    "museum",
    "park",
    "peak",
    "place_of_worship",
    "protected_area",
    "restaurant",
    "theme_park",
    "viewpoint",
    "water",
}
NON_TRAVEL_NAME_HINTS = {
    "san go",
    "noi that",
    "vat lieu",
    "dien may",
    "dien lanh",
    "sua chua",
    "phu tung",
    "gara",
    "garage",
    "bat dong san",
    "van phong",
}
NON_TRAVEL_RAW_HINTS = {
    "sàn gỗ",
    "nội thất",
    "vật liệu",
    "điện máy",
    "điện lạnh",
    "sửa chữa",
    "phụ tùng",
    "bất động sản",
    "văn phòng",
}
VERIFY_RADIUS_KM = 70.0
VIETNAM_LAT = (8.0, 24.5)
VIETNAM_LNG = (102.0, 110.5)


def _fold(value: str) -> str:
    return ascii_fold(value).casefold()


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _fold(value)) if len(token) >= 3}


def _looks_like_non_travel_business(value: str) -> bool:
    raw = value.casefold()
    folded = _fold(value)
    return any(hint in raw for hint in NON_TRAVEL_RAW_HINTS) or any(
        hint in folded for hint in NON_TRAVEL_NAME_HINTS
    )


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict[str, dict]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _catalog_match(name: str, origin: tuple[float, float]) -> Place | None:
    needle = _fold(name)
    if not needle or _looks_like_non_travel_business(name):
        return None
    needle_tokens = _tokens(name)
    matches = [
        place
        for place in PLACES
        if (place_needle := _fold(place.name))
        and (
            needle == place_needle
            or (
                len(needle_tokens.intersection(_tokens(place.name)))
                >= max(2, min(len(needle_tokens), 3))
            )
        )
    ]
    if not matches:
        return None
    exact = [place for place in matches if _fold(place.name) == needle]
    if len(exact) > 1 or (not exact and len(matches) > 1):
        return None
    matches = exact or matches
    return min(matches, key=lambda place: haversine_km(origin[0], origin[1], place.lat, place.lng))


def _nominatim_class(row: dict) -> str:
    return str(row.get("category") or row.get("class") or "").casefold()


def _nominatim_type(row: dict) -> str:
    return str(row.get("type") or "").casefold()


def _nominatim_search(query: str, origin: tuple[float, float], *, bounded: bool) -> list[dict]:
    params: dict[str, object] = {
        "q": query,
        "format": "jsonv2",
        "limit": 8,
        "addressdetails": 1,
    }
    if bounded:
        delta = 0.85
        params["viewbox"] = f"{origin[1] - delta},{origin[0] + delta},{origin[1] + delta},{origin[0] - delta}"
        params["bounded"] = 1
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(8, connect=2),
        )
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return []
    return rows if isinstance(rows, list) else []


def _place_from_nominatim(name: str, origin: tuple[float, float], city: str | None, rows: list[dict]) -> Place | None:
    valid_rows = [
        row
        for row in rows
        if _nominatim_class(row) in ALLOWED_NOMINATIM_CLASSES
        and _nominatim_type(row) in ALLOWED_NOMINATIM_TYPES
    ]
    needle_tokens = _tokens(name)
    named_rows = [
        row
        for row in valid_rows
        if needle_tokens.intersection(_tokens(str(row.get("name") or row.get("display_name") or "")))
    ]
    candidates = named_rows or valid_rows
    if not candidates:
        return None
    scored: list[tuple[float, dict]] = []
    for row in candidates:
        try:
            lat = float(row["lat"])
            lng = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        scored.append((haversine_km(origin[0], origin[1], lat, lng), row))
    if not scored:
        return None
    row = min(scored, key=lambda item: item[0])[1]
    if _nominatim_class(row) not in ALLOWED_NOMINATIM_CLASSES or _nominatim_type(row) not in ALLOWED_NOMINATIM_TYPES:
        return None
    display_name = str(row.get("display_name", ""))
    folded_display_name = _fold(display_name)
    if "viet nam" not in folded_display_name and "vietnam" not in folded_display_name:
        return None
    try:
        lat = float(row["lat"])
        lng = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (VIETNAM_LAT[0] <= lat <= VIETNAM_LAT[1] and VIETNAM_LNG[0] <= lng <= VIETNAM_LNG[1]):
        return None
    if haversine_km(origin[0], origin[1], lat, lng) > VERIFY_RADIUS_KM:
        return None
    osm_id, osm_type = row.get("osm_id"), str(row.get("osm_type", "")).casefold()
    if not isinstance(osm_id, int) or osm_type not in {"node", "way", "relation"}:
        return None
    return Place(
        id=f"osm-verified-{osm_type}-{osm_id}",
        name=str(row.get("name") or name),
        kind="dia_danh",
        area=city or "Việt Nam",
        lat=lat,
        lng=lng,
        cost=0,
        duration_min=60,
        tags=("osm_verified", "map_verified"),
        open_hour=7,
        close_hour=22,
        source="Nominatim",
        source_url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
    )


def verify_place_name(name: str, origin: tuple[float, float], city: str | None = None) -> Place | None:
    catalog = _catalog_match(name, origin)
    if catalog:
        return catalog
    city_key = _fold(city or "")
    cache_keys = [_fold(f"{city_key}:{origin[0]:.2f}:{origin[1]:.2f}:{name}")]
    if city_key in {"", "ha noi", "hanoi"} or haversine_km(origin[0], origin[1], 21.0285, 105.8542) <= 20:
        cache_keys.append(_fold(f"hanoi:{name}"))
    cache = _load_cache()
    for cache_key in cache_keys:
        cached = cache.get(cache_key)
        if not cached:
            continue
        try:
            cached_place = Place(**cached)
            if (
                cached_place.id.startswith("osm-verified-")
                and cached_place.source == "Nominatim"
                and cached_place.source_url
                and VIETNAM_LAT[0] <= cached_place.lat <= VIETNAM_LAT[1]
                and VIETNAM_LNG[0] <= cached_place.lng <= VIETNAM_LNG[1]
                and haversine_km(origin[0], origin[1], cached_place.lat, cached_place.lng) <= VERIFY_RADIUS_KM
            ):
                return cached_place
        except (TypeError, ValueError):
            pass
    query = f"{name}, {city}, Vietnam" if city else f"{name}, Vietnam"
    rows = _nominatim_search(query, origin, bounded=True)
    place = _place_from_nominatim(name, origin, city, rows)
    if place is None:
        place = _place_from_nominatim(name, origin, city, _nominatim_search(query, origin, bounded=False))
    if place is None:
        return None
    cache[cache_keys[0]] = place.__dict__
    _save_cache(cache)
    return place
