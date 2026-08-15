import json
import os
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path

import httpx
import psycopg

from app.config import settings
from app.data import Place

_MATRIX_PATH = Path(__file__).resolve().parents[2] / "data" / "distance_matrix.json"


def _load_matrix() -> tuple[dict[tuple[str, str], int], set[str]]:
    if os.getenv("APP_ENV", "local") != "local":
        database_url = os.getenv("URL_CSDL_POSTGRES")
        if not database_url:
            raise RuntimeError("URL_CSDL_POSTGRES is required outside local mode")
        with psycopg.connect(database_url, connect_timeout=3) as connection:
            rows = connection.execute(
                "SELECT a.ma_nguon,b.ma_nguon,k.thoi_gian_giay "
                "FROM bang_khoang_cach k JOIN dia_diem a ON a.id=k.diem_a_id "
                "JOIN dia_diem b ON b.id=k.diem_b_id "
                "WHERE k.phuong_tien='driving'"
            ).fetchall()
        if not rows:
            raise RuntimeError("PostgreSQL route matrix is empty")
        ids = {row[0] for row in rows} | {row[1] for row in rows}
        return {(row[0], row[1]): max(1, round(row[2] / 60)) for row in rows}, ids
    if not _MATRIX_PATH.exists():
        return {}, set()
    payload = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))
    ids = payload.get("place_ids", [])
    rows = payload.get("durations_seconds", [])
    matrix = {
        (source, target): max(1, round(rows[i][j] / 60))
        for i, source in enumerate(ids)
        for j, target in enumerate(ids)
        if rows[i][j] is not None
    }
    return matrix, set(ids)


TRAVEL_MINUTES, ROUTABLE_PLACE_IDS = _load_matrix()


def public_transit_policy_status(today: date | None = None) -> dict:
    current = today or date.today()
    if not settings.public_transit_enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "max_feed_age_days": 90,
            "feed_date": settings.gtfs_feed_date,
            "note": "Public transit routing is disabled unless a fresh official GTFS feed is configured.",
        }
    if not settings.gtfs_feed_date:
        return {
            "enabled": True,
            "status": "blocked_missing_gtfs_feed_date",
            "max_feed_age_days": 90,
            "feed_date": None,
            "note": "Transit routing is blocked because no GTFS feed date is configured.",
        }
    try:
        feed_date = date.fromisoformat(settings.gtfs_feed_date)
    except ValueError:
        return {
            "enabled": True,
            "status": "blocked_invalid_gtfs_feed_date",
            "max_feed_age_days": 90,
            "feed_date": settings.gtfs_feed_date,
            "note": "Transit routing is blocked because GTFS_FEED_DATE is not YYYY-MM-DD.",
        }
    age_days = (current - feed_date).days
    if age_days < 0 or age_days > 90:
        return {
            "enabled": True,
            "status": "blocked_stale_gtfs_feed",
            "max_feed_age_days": 90,
            "feed_date": settings.gtfs_feed_date,
            "feed_age_days": age_days,
            "note": "Transit routing is blocked unless GTFS data is no older than 90 days.",
        }
    return {
        "enabled": True,
        "status": "ready",
        "max_feed_age_days": 90,
        "feed_date": settings.gtfs_feed_date,
        "feed_age_days": age_days,
        "note": "Transit routing may be used with the configured fresh GTFS feed.",
    }


def route_calibration_status() -> dict:
    path_value = settings.route_calibration_file
    if not path_value:
        return {
            "status": "missing_calibration_file",
            "required": True,
            "min_samples": settings.route_calibration_min_samples,
            "max_mape_percent": settings.route_calibration_max_mape_percent,
            "note": "Production routing must be calibrated against observed Vietnam travel-time samples.",
        }
    path = Path(path_value)
    if not path.exists():
        return {
            "status": "missing_calibration_file",
            "required": True,
            "path": str(path),
            "min_samples": settings.route_calibration_min_samples,
            "max_mape_percent": settings.route_calibration_max_mape_percent,
            "note": "Configured route calibration file does not exist.",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid_calibration_file",
            "required": True,
            "path": str(path),
            "error": str(exc)[:160],
        }
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return {"status": "invalid_calibration_file", "required": True, "path": str(path), "error": "missing summary"}
    sample_count = int(summary.get("sample_count") or 0)
    mape = summary.get("mape_percent")
    if not isinstance(mape, (int, float)):
        return {"status": "invalid_calibration_file", "required": True, "path": str(path), "error": "missing mape_percent"}
    if sample_count < settings.route_calibration_min_samples:
        return {
            "status": "insufficient_samples",
            "required": True,
            "path": str(path),
            "sample_count": sample_count,
            "min_samples": settings.route_calibration_min_samples,
            "mape_percent": round(float(mape), 2),
        }
    if float(mape) > settings.route_calibration_max_mape_percent:
        return {
            "status": "failed_error_threshold",
            "required": True,
            "path": str(path),
            "sample_count": sample_count,
            "min_samples": settings.route_calibration_min_samples,
            "mape_percent": round(float(mape), 2),
            "max_mape_percent": settings.route_calibration_max_mape_percent,
        }
    return {
        "status": "ready",
        "required": True,
        "path": str(path),
        "sample_count": sample_count,
        "min_samples": settings.route_calibration_min_samples,
        "mape_percent": round(float(mape), 2),
        "max_mape_percent": settings.route_calibration_max_mape_percent,
        "source": payload.get("source") or "route_calibration_report",
    }


TRAVEL_ESTIMATE_POLICY = {
    "status": "matrix_or_offline_estimate",
    "formula": "haversine_km * he_so_duong / toc_do_km_h * 60",
    "note": "Uu tien ma tran OSRM/PostgreSQL da build; chi fallback sang uoc tinh duong thang khi cap diem chua co trong ma tran.",
    "speeds_kmh": {"walk": 4.5, "motorbike": 22.0, "car": 25.0},
    "detour_factors": {"walk": 1.25, "motorbike": 1.4, "car": 1.5},
    "live_provider": {
        "enabled": settings.plan_live_travel_matrix,
        "provider": "OSRM table",
        "base_url": settings.osrm_base_url,
        "max_places": settings.plan_live_travel_matrix_max_places,
        "note": "Runtime matrix is opt-in; production must use a private routing endpoint. Public OSRM is local/dev only.",
    },
    "public_transit": public_transit_policy_status(),
    "calibration": route_calibration_status(),
}


@dataclass(frozen=True)
class TravelEstimate:
    distance_km: float
    minutes: int
    mode: str
    source: str
    formula: str
    status: str


@dataclass(frozen=True)
class LiveMatrixResult:
    matrix: dict[tuple[str, str], TravelEstimate]
    provider: str
    status: str
    error: str | None = None


def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    dlat = radians(b_lat - a_lat)
    dlng = radians(b_lng - a_lng)
    value = sin(dlat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def estimate_straight_line_travel(a: Place, b: Place, mode: str = "motorbike") -> TravelEstimate:
    speeds = TRAVEL_ESTIMATE_POLICY["speeds_kmh"]
    factors = TRAVEL_ESTIMATE_POLICY["detour_factors"]
    if mode not in speeds:
        mode = "motorbike"
    distance = haversine_km(a.lat, a.lng, b.lat, b.lng)
    minutes = max(5, round(distance * factors[mode] / speeds[mode] * 60))
    return TravelEstimate(
        distance_km=round(distance, 2),
        minutes=minutes,
        mode=mode,
        source="offline_straight_line_fallback",
        formula=TRAVEL_ESTIMATE_POLICY["formula"],
        status="fallback_missing_route_matrix_pair",
    )


def estimate_travel(a: Place, b: Place, mode: str = "motorbike") -> TravelEstimate:
    if TRAVEL_MINUTES:
        value = TRAVEL_MINUTES.get((a.id, b.id))
        if value is not None:
            return TravelEstimate(
                distance_km=round(haversine_km(a.lat, a.lng, b.lat, b.lng), 2),
                minutes=value,
                mode=mode,
                source="route_matrix",
                formula="precomputed_osrm_or_postgres_duration_seconds",
                status="matrix_available",
            )
    return estimate_straight_line_travel(a, b, mode)


def travel_minutes(a: Place, b: Place) -> int:
    return estimate_travel(a, b).minutes


def travel_matrix(places: list[Place], mode: str = "motorbike") -> dict[str, dict[str, dict]]:
    live = fetch_live_travel_matrix(places, mode)
    live_matrix = live.matrix if live.status == "live" else {}
    result = {
        source.id: {
            target.id: (
                live_matrix.get((source.id, target.id))
                or estimate_travel(source, target, mode)
            ).__dict__
            for target in places
            if target.id != source.id
        }
        for source in places
    }
    result["_metadata"] = {
        "live_provider_status": live.status,
        "provider": live.provider,
        "error": live.error,
        "policy": TRAVEL_ESTIMATE_POLICY["live_provider"],
        "public_transit_policy": public_transit_policy_status(),
        "route_calibration": route_calibration_status(),
    }
    return result


def _valid_table_coordinates(places: list[Place]) -> list[tuple[float, float]]:
    coordinates = []
    for place in places:
        if not (
            isinstance(place.lat, (int, float))
            and isinstance(place.lng, (int, float))
            and isfinite(place.lat)
            and isfinite(place.lng)
            and -90 <= place.lat <= 90
            and -180 <= place.lng <= 180
        ):
            return []
        coordinates.append((place.lng, place.lat))
    return coordinates


def _parse_osrm_table(payload: object, places: list[Place], mode: str) -> dict[tuple[str, str], TravelEstimate] | None:
    if not isinstance(payload, dict) or payload.get("code") != "Ok":
        return None
    durations = payload.get("durations")
    if not isinstance(durations, list) or len(durations) != len(places):
        return None
    parsed: dict[tuple[str, str], TravelEstimate] = {}
    for i, row in enumerate(durations):
        if not isinstance(row, list) or len(row) != len(places):
            return None
        for j, seconds in enumerate(row):
            if i == j:
                continue
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not isfinite(seconds):
                return None
            if seconds < 0 or seconds > 24 * 3600:
                return None
            source, target = places[i], places[j]
            parsed[(source.id, target.id)] = TravelEstimate(
                distance_km=round(haversine_km(source.lat, source.lng, target.lat, target.lng), 2),
                minutes=max(1, round(seconds / 60)),
                mode=mode,
                source="live_osrm_table",
                formula="osrm_table_duration_seconds",
                status="live_provider_available",
            )
    return parsed


def fetch_live_travel_matrix(places: list[Place], mode: str = "motorbike") -> LiveMatrixResult:
    policy = TRAVEL_ESTIMATE_POLICY["live_provider"]
    provider = str(policy["provider"])
    if not settings.plan_live_travel_matrix:
        return LiveMatrixResult({}, provider, "disabled")
    if len(places) < 2:
        return LiveMatrixResult({}, provider, "too_few_places")
    if len(places) > settings.plan_live_travel_matrix_max_places:
        return LiveMatrixResult({}, provider, "too_many_places")
    coordinates = _valid_table_coordinates(places)
    if len(coordinates) != len(places):
        return LiveMatrixResult({}, provider, "invalid_coordinates")
    joined = ";".join(f"{lng},{lat}" for lng, lat in coordinates)
    url = f"{settings.osrm_base_url.strip().rstrip('/')}/table/v1/driving/{joined}"
    try:
        with httpx.Client(timeout=httpx.Timeout(12, connect=3)) as client:
            response = client.get(url, params={"annotations": "duration"})
            response.raise_for_status()
            parsed = _parse_osrm_table(response.json(), places, mode)
    except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return LiveMatrixResult({}, provider, "provider_error", str(exc)[:160])
    if parsed is None:
        return LiveMatrixResult({}, provider, "invalid_provider_payload")
    return LiveMatrixResult(parsed, provider, "live")


def is_routable(place: Place) -> bool:
    if not (-90 <= place.lat <= 90 and -180 <= place.lng <= 180):
        return False
    return True


def nearest_neighbor(places: list[Place], origin: tuple[float, float]) -> list[Place]:
    remaining = list(places)
    result: list[Place] = []
    lat, lng = origin
    while remaining:
        nxt = min(remaining, key=lambda p: haversine_km(lat, lng, p.lat, p.lng))
        result.append(nxt)
        remaining.remove(nxt)
        lat, lng = nxt.lat, nxt.lng
    return result


def route_cost(route: list[Place]) -> int:
    return sum(travel_minutes(a, b) for a, b in pairwise(route))


def two_opt(route: list[Place]) -> list[Place]:
    best = route[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j][::-1] + best[j:]
                if route_cost(candidate) < route_cost(best):
                    best, improved = candidate, True
    return best
