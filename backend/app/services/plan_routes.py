"""Real road geometry for day itineraries, backed by OSRM with an on-disk cache.

Combines two strategies:
- On-demand: a single OSRM /route call per day (ordered stops) returns the real
  driving LineString as GeoJSON.
- Persistent cache: geometries are keyed by the ordered sequence of place ids
  and stored under data/plan_routes.json, so regenerated or identical plans
  reuse the same geometry without hitting the network again.

OSRM stays optional: any failure returns None, and the frontend falls back to
straight-line segments. Generation is never blocked by routing being down.
"""

import json
import threading
from logging import getLogger
from math import isfinite
from pathlib import Path

import httpx

from app.config import settings

logger = getLogger(__name__)
_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "plan_routes.json"
_lock = threading.Lock()
_cache: dict[str, list] = {}


def _load_cache() -> None:
    global _cache
    if not _CACHE_PATH.exists():
        return
    try:
        payload = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        _cache = payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        logger.warning("Could not load plan route cache; starting empty")


def _store_cache() -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Could not persist plan route cache")


def _day_key(slots: list[dict]) -> str:
    return "|".join(str(slot.get("dia_diem_id")) for slot in slots)


def _day_coordinates(slots: list[dict]) -> list[tuple[float, float]]:
    coordinates: list[tuple[float, float]] = []
    for slot in slots:
        point = slot.get("toa_do") or {}
        try:
            lat = float(point.get("lat"))
            lng = float(point.get("lng"))
        except (TypeError, ValueError):
            return []
        if not (isfinite(lat) and isfinite(lng)):
            return []
        coordinates.append((lng, lat))
    return coordinates


def _validated_geometry(payload: object, endpoints: list[tuple[float, float]]) -> list | None:
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        return None
    routes = payload.get("routes")
    if not isinstance(routes, list) or len(routes) != 1 or not isinstance(routes[0], dict):
        return None
    geometry = routes[0].get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        return None
    points = geometry.get("coordinates")
    if not isinstance(points, list) or not 2 <= len(points) <= 50_000:
        return None
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            return None
        lng, lat = point
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
            for value in point
        ) or not (-180 <= lng <= 180 and -90 <= lat <= 90):
            return None
    # Snap tolerance: OSRM snaps stops onto the nearest road, so endpoints may
    # differ by a few hundred meters for stops off the carriageway. 0.01deg
    # (~1.1km) still rejects an outright wrong route while accepting common
    # snapping drift.
    for actual, expected in zip((points[0], points[-1]), (endpoints[0], endpoints[-1]), strict=False):
        if abs(actual[0] - expected[0]) > 0.01 or abs(actual[1] - expected[1]) > 0.01:
            return None
    return points


def _fetch_day_route(coordinates: list[tuple[float, float]]) -> list | None:
    joined = ";".join(f"{lng},{lat}" for lng, lat in coordinates)
    url = f"{settings.osrm_base_url.strip().rstrip('/')}/route/v1/driving/{joined}"
    try:
        with httpx.Client(timeout=httpx.Timeout(12, connect=3)) as client:
            response = client.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    return _validated_geometry(payload, coordinates)


def resolve_day_route(slots: list[dict]) -> dict | None:
    """Return a GeoJSON LineString for the ordered slots of one day, or None.

    The cache is consulted first (keyed by the ordered place ids); a miss
    performs a single live OSRM request and stores the result on success.
    """
    if not settings.plan_route_geometry or len(slots) < 2:
        return None
    coordinates = _day_coordinates(slots)
    if len(coordinates) < 2:
        return None
    key = _day_key(slots)
    with _lock:
        cached = _cache.get(key)
    if isinstance(cached, list) and len(cached) >= 2:
        return {"type": "LineString", "coordinates": cached}
    points = _fetch_day_route(coordinates)
    if not points:
        return None
    with _lock:
        _cache[key] = points
        _store_cache()
    return {"type": "LineString", "coordinates": points}


def enrich_plan_routes(plan: dict) -> dict:
    """Attach a tuyen_duong LineString to every day of a plan, if available."""
    if not settings.plan_route_geometry:
        return plan
    days = plan.get("ngay")
    if not isinstance(days, list):
        return plan
    for day in days:
        if not isinstance(day, dict):
            continue
        slots = day.get("khoang_gio")
        if not isinstance(slots, list):
            continue
        geometry = resolve_day_route(slots)
        if geometry:
            day["tuyen_duong"] = geometry
    return plan


_load_cache()