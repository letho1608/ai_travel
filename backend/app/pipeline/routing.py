import json
import os
from itertools import pairwise
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import psycopg

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


def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    dlat = radians(b_lat - a_lat)
    dlng = radians(b_lng - a_lng)
    value = sin(dlat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def travel_minutes(a: Place, b: Place) -> int:
    if TRAVEL_MINUTES:
        value = TRAVEL_MINUTES.get((a.id, b.id))
        if value is not None:
            return value
    return max(5, round(haversine_km(a.lat, a.lng, b.lat, b.lng) * 1.4 / 22 * 60))


def is_routable(place: Place) -> bool:
    return (
        not ROUTABLE_PLACE_IDS
        or place.id in ROUTABLE_PLACE_IDS
        or place.source in {"curated", "Nominatim"}
    )


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
