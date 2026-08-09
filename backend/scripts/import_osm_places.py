"""Import verified Hanoi POIs from OpenStreetMap Overpass with provenance.

Usage: python scripts/import_osm_places.py --output data/places.json
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import Counter

import datetime as _dt

if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc
from datetime import UTC, datetime
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HANOI_BBOX = "20.90,105.70,21.16,106.02"
CATEGORY_MAP = {
    "cafe": "cafe",
    "restaurant": "nha_hang",
    "fast_food": "quan_an",
    "food_court": "quan_an",
    "marketplace": "cho",
    "museum": "bao_tang",
    "attraction": "dia_danh",
    "viewpoint": "dia_danh",
    "park": "cong_vien",
    "theme_park": "giai_tri",
}


def query() -> str:
    return f"""
[out:json][timeout:120];
(
  nwr[amenity~"^(cafe|restaurant|fast_food|food_court|marketplace)$"]({HANOI_BBOX});
  nwr[tourism~"^(museum|attraction|viewpoint)$"]({HANOI_BBOX});
  nwr[leisure~"^(park|theme_park)$"]({HANOI_BBOX});
);
out center tags;
""".strip()


def fetch_overpass(endpoint: str) -> dict:
    body = urllib.parse.urlencode({"data": query()}).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"User-Agent": "minh-di-dau-the/0.1 (data import; contact project owner)"},
    )
    with urllib.request.urlopen(request, timeout=150) as response:
        return json.load(response)


def category(tags: dict[str, str]) -> str | None:
    raw = tags.get("amenity") or tags.get("tourism") or tags.get("leisure")
    return CATEGORY_MAP.get(raw or "")


def coordinates(element: dict) -> tuple[float, float] | None:
    lat = element.get("lat", element.get("center", {}).get("lat"))
    lng = element.get("lon", element.get("center", {}).get("lon"))
    return (float(lat), float(lng)) if lat is not None and lng is not None else None


def normalize(element: dict, fetched_at: str) -> dict | None:
    tags = element.get("tags", {})
    name = tags.get("name:vi") or tags.get("name")
    coords = coordinates(element)
    kind = category(tags)
    if not name or not coords or not kind:
        return None
    osm_type, osm_id = element["type"], element["id"]
    address = ", ".join(
        value
        for value in (
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:district") or tags.get("addr:suburb"),
            tags.get("addr:city"),
        )
        if value
    )
    feature_tags = [
        value
        for value in (
            tags.get("cuisine"), tags.get("outdoor_seating"), tags.get("wheelchair"),
            tags.get("tourism"), tags.get("leisure"), tags.get("historic"),
        )
        if value and value not in {"yes", "no"}
    ]
    return {
        "id": f"osm-{osm_type}-{osm_id}",
        "name": name,
        "kind": kind,
        "area": tags.get("addr:district") or tags.get("addr:suburb") or "Hà Nội",
        "address": address,
        "lat": coords[0],
        "lng": coords[1],
        "cost": 0,
        "duration_min": 60,
        "tags": sorted(set(feature_tags)),
        "open_hour": 7,
        "close_hour": 22,
        "opening_hours_raw": tags.get("opening_hours"),
        "website": tags.get("website") or tags.get("contact:website"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "source": "OpenStreetMap",
        "source_id": f"{osm_type}/{osm_id}",
        "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "fetched_at": fetched_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=OVERPASS_URL)
    parser.add_argument("--output", type=Path, default=Path("data/places.json"))
    args = parser.parse_args()
    fetched_at = datetime.now(UTC).isoformat()
    payload = fetch_overpass(args.endpoint)
    places = [place for element in payload.get("elements", []) if (place := normalize(element, fetched_at))]
    places.sort(key=lambda item: (item["kind"], item["area"], item["name"]))
    coverage = Counter((place["kind"], place["area"]) for place in places)
    output = {
        "metadata": {
            "provider": "OpenStreetMap Overpass",
            "endpoint": args.endpoint,
            "bbox": HANOI_BBOX,
            "fetched_at": fetched_at,
            "license": "ODbL 1.0",
            "count": len(places),
            "coverage_cells": len(coverage),
            "generated_unix": int(time.time()),
        },
        "coverage": [
            {"kind": key[0], "area": key[1], "count": count, "passes_minimum": count >= 3}
            for key, count in sorted(coverage.items())
        ],
        "places": places,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(places)} places to {args.output}")


if __name__ == "__main__":
    main()

