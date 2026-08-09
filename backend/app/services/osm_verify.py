import json
import re
from pathlib import Path

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
    return min(matches, key=lambda place: haversine_km(origin[0], origin[1], place.lat, place.lng))


def verify_place_name(name: str, origin: tuple[float, float]) -> Place | None:
    catalog = _catalog_match(name, origin)
    if catalog:
        return catalog
    cache_key = _fold(f"hanoi:{name}")
    cache = _load_cache()
    cached = cache.get(cache_key)
    if cached:
        return Place(**cached)
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={
                "q": f"{name}, Hanoi, Vietnam",
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(6, connect=2),
        )
        response.raise_for_status()
        rows = response.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    if not rows:
        return None
    row = rows[0]
    place_class = str(row.get("class", "")).casefold()
    place_type = str(row.get("type", "")).casefold()
    if place_class not in ALLOWED_NOMINATIM_CLASSES or place_type not in ALLOWED_NOMINATIM_TYPES:
        return None
    display_name = str(row.get("display_name", ""))
    if "Việt Nam" not in display_name and "Vietnam" not in display_name:
        return None
    if "Hà Nội" not in display_name and "Hanoi" not in display_name:
        return None
    try:
        lat = float(row["lat"])
        lng = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    place = Place(
        id=f"osm-verified-{row.get('osm_type', 'place')}-{row.get('osm_id')}",
        name=str(row.get("name") or name),
        kind="dia_danh",
        area="Hà Nội",
        lat=lat,
        lng=lng,
        cost=0,
        duration_min=60,
        tags=("osm_verified", "llm_suggested"),
        open_hour=7,
        close_hour=22,
        source="Nominatim",
        source_url=f"https://www.openstreetmap.org/{row.get('osm_type')}/{row.get('osm_id')}",
    )
    cache[cache_key] = place.__dict__
    _save_cache(cache)
    return place
