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
}
ALLOWED_NOMINATIM_TYPES = {
    "attraction",
    "cafe",
    "fast_food",
    "food_court",
    "marketplace",
    "memorial",
    "monument",
    "museum",
    "park",
    "place_of_worship",
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
    delta = 0.65
    viewbox = f"{origin[1] - delta},{origin[0] + delta},{origin[1] + delta},{origin[0] - delta}"
    query = f"{name}, {city}, Vietnam" if city else f"{name}, Vietnam"
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 5,
                "addressdetails": 1,
                "viewbox": viewbox,
                "bounded": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(6, connect=2),
        )
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    if not isinstance(rows, list) or not rows:
        return None
    valid_rows = [row for row in rows if str(row.get("class", "")).casefold() in ALLOWED_NOMINATIM_CLASSES and str(row.get("type", "")).casefold() in ALLOWED_NOMINATIM_TYPES]
    exact_rows = [row for row in valid_rows if _fold(str(row.get("name", ""))) == _fold(name)]
    candidates = exact_rows or valid_rows
    if len(candidates) != 1:
        return None
    row = candidates[0]
    place_class = str(row.get("class", "")).casefold()
    place_type = str(row.get("type", "")).casefold()
    if place_class not in ALLOWED_NOMINATIM_CLASSES or place_type not in ALLOWED_NOMINATIM_TYPES:
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
    place = Place(
        id=f"osm-verified-{osm_type}-{osm_id}",
        name=str(row.get("name") or name),
        kind="dia_danh",
        area=city or "Việt Nam",
        lat=lat,
        lng=lng,
        cost=0,
        duration_min=60,
        tags=("osm_verified", "llm_suggested"),
        open_hour=7,
        close_hour=22,
        source="Nominatim",
        source_url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
    )
    cache[cache_keys[0]] = place.__dict__
    _save_cache(cache)
    return place
