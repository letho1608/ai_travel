"""Import verified POIs from OpenStreetMap Overpass with provenance.

Usage:
  python scripts/import_osm_places.py --output data/places.json
  python scripts/import_osm_places.py --scope vietnam --output data/vietnam_places.json

The output keeps the existing catalogue schema used by backend/data.py.
"""

import argparse
import datetime as _dt
import json
import math
import os
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"
GOOGLE_FREE_TEXT_SEARCH_MONTHLY_CAP = 9500
GOOGLE_FREE_PHOTO_MONTHLY_CAP = 950
DEFAULT_GOOGLE_IMPORT_LIMIT = 100
HANOI_BBOX = "20.90,105.70,21.16,106.02"
VIETNAM_AREA = "3600049915"

KIND_BY_AMENITY = {
    "bar": "quan_an",
    "biergarten": "quan_an",
    "cafe": "cafe",
    "fast_food": "quan_an",
    "food_court": "quan_an",
    "ice_cream": "quan_an",
    "marketplace": "cho",
    "place_of_worship": "den_chua",
    "pub": "quan_an",
    "restaurant": "nha_hang",
}
KIND_BY_TOURISM = {
    "alpine_hut": "nha_nghi",
    "apartment": "khach_san",
    "aquarium": "giai_tri",
    "artwork": "dia_danh",
    "attraction": "dia_danh",
    "camp_site": "cam_trai",
    "caravan_site": "cam_trai",
    "chalet": "homestay",
    "gallery": "bao_tang",
    "guest_house": "nha_nghi",
    "hostel": "nha_nghi",
    "hotel": "khach_san",
    "motel": "nha_nghi",
    "museum": "bao_tang",
    "picnic_site": "cam_trai",
    "theme_park": "giai_tri",
    "viewpoint": "dia_danh",
    "wilderness_hut": "nha_nghi",
    "zoo": "giai_tri",
}
KIND_BY_LEISURE = {
    "garden": "cong_vien",
    "nature_reserve": "dia_danh",
    "park": "cong_vien",
    "theme_park": "giai_tri",
    "water_park": "giai_tri",
}
KIND_BY_NATURAL = {
    "bay": "dia_danh",
    "beach": "bai_bien",
    "cave_entrance": "hang_dong",
    "cliff": "dia_danh",
    "peak": "nui",
    "rock": "dia_danh",
    "volcano": "nui",
    "waterfall": "thac_nuoc",
}
KIND_BY_HISTORIC = {
    "archaeological_site": "di_tich",
    "battlefield": "di_tich",
    "castle": "di_tich",
    "city_gate": "di_tich",
    "fort": "di_tich",
    "heritage": "di_tich",
    "memorial": "di_tich",
    "monument": "di_tich",
    "ruins": "di_tich",
    "tomb": "di_tich",
    "yes": "di_tich",
}
KIND_BY_BUILDING = {
    "pagoda": "den_chua",
    "shrine": "den_chua",
    "temple": "den_chua",
}
KIND_BY_HIGHWAY = {"trailhead": "dia_danh"}
FOOD_KINDS = {"cafe", "cho", "nha_hang", "quan_an"}
TRAVEL_ANCHOR_KINDS = {
    "bai_bien",
    "bao_tang",
    "cam_trai",
    "den_chua",
    "di_tich",
    "dia_danh",
    "giai_tri",
    "hang_dong",
    "nui",
    "thac_nuoc",
}
DEFAULT_FOOD_ANCHOR_RADIUS_KM = 15.0
DEFAULT_VIETNAM_GROUPS = (
    "food",
    "stay",
    "tourism",
    "nature",
    "worship_tourism",
    "worship_historic",
    "historic",
    "leisure",
)
VIETNAM_GROUP_QUERIES = {
    "food": 'nwr[amenity~"^(bar|biergarten|cafe|fast_food|food_court|ice_cream|marketplace|pub|restaurant)$"](area.searchArea);',
    "stay": 'nwr[tourism~"^(alpine_hut|apartment|camp_site|caravan_site|chalet|guest_house|hostel|hotel|motel|wilderness_hut)$"](area.searchArea);',
    "tourism": 'nwr[tourism~"^(aquarium|artwork|attraction|gallery|museum|picnic_site|theme_park|viewpoint|zoo)$"](area.searchArea);',
    "nature": 'nwr[natural~"^(bay|beach|cave_entrance|cliff|peak|rock|volcano|waterfall)$"](area.searchArea);',
    "worship_tourism": (
        "nwr[amenity=place_of_worship][tourism](area.searchArea);\n  "
        'nwr[tourism=attraction][religion](area.searchArea);\n  '
        'nwr[building~"^(pagoda|shrine|temple)$"][tourism](area.searchArea);'
    ),
    "worship_historic": (
        "nwr[amenity=place_of_worship][historic](area.searchArea);\n  "
        "nwr[amenity=place_of_worship][heritage](area.searchArea);\n  "
        'nwr[building~"^(pagoda|shrine|temple)$"][historic](area.searchArea);'
    ),
    "worship_wiki": (
        "nwr[amenity=place_of_worship][wikidata](area.searchArea);\n  "
        "nwr[amenity=place_of_worship][wikipedia](area.searchArea);\n  "
        'nwr[building~"^(pagoda|shrine|temple)$"][wikidata](area.searchArea);\n  '
        'nwr[building~"^(pagoda|shrine|temple)$"][wikipedia](area.searchArea);'
    ),
    "historic": "nwr[historic](area.searchArea);",
    "leisure": 'nwr[leisure~"^(garden|nature_reserve|park|theme_park|water_park)$"](area.searchArea);\n  nwr[highway=trailhead](area.searchArea);',
}


def query(scope: str = "hanoi", group: str = "all") -> str:
    if scope == "vietnam":
        group_query = "\n  ".join(VIETNAM_GROUP_QUERIES.values()) if group == "all" else VIETNAM_GROUP_QUERIES[group]
        return f"""
[out:json][timeout:900];
area({VIETNAM_AREA})->.searchArea;
(
  {group_query}
);
out center tags;
""".strip()
    return f"""
[out:json][timeout:120];
(
  nwr[amenity~"^(cafe|restaurant|fast_food|food_court|marketplace)$"]({HANOI_BBOX});
  nwr[tourism~"^(museum|attraction|viewpoint)$"]({HANOI_BBOX});
  nwr[leisure~"^(park|theme_park)$"]({HANOI_BBOX});
);
out center tags;
""".strip()


def fetch_overpass(endpoint: str, query_text: str, retries: int = 3, retry_wait: int = 45) -> dict:
    body = urllib.parse.urlencode({"data": query_text}).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"User-Agent": "minh-di-dau-the/0.1 (data import; contact project owner)"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt >= retries:
                raise
            wait = retry_wait * (attempt + 1)
            print(f"Overpass rate-limited. Waiting {wait}s before retry...", flush=True)
            time.sleep(wait)
    raise RuntimeError("unreachable Overpass retry state")


def fetch_google_place(place: dict, api_key: str) -> dict | None:
    query_text = f"{place['name']} {place.get('area') or 'Vietnam'} Vietnam"
    body = json.dumps(
        {
            "textQuery": query_text,
            "languageCode": "vi",
            "regionCode": "VN",
            "locationBias": {
                "circle": {
                    "center": {"latitude": place["lat"], "longitude": place["lng"]},
                    "radius": 1200.0,
                }
            },
            "pageSize": 1,
        }
    ).encode()
    request = urllib.request.Request(
        GOOGLE_TEXT_SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.googleMapsUri,places.rating,places.userRatingCount,"
                "places.photos"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        places = json.load(response).get("places", [])
    return places[0] if places else None


def google_photo_url(photo_name: str, api_key: str) -> str:
    return (
        GOOGLE_PHOTO_MEDIA_URL.format(photo_name=photo_name)
        + "?"
        + urllib.parse.urlencode({"maxWidthPx": 800, "key": api_key})
    )


def enrich_with_google(place: dict, api_key: str, include_photo: bool = True) -> dict:
    google = fetch_google_place(place, api_key)
    if not google:
        return place
    place = dict(place)
    place["google_place_id"] = google.get("id")
    place["google_maps_url"] = google.get("googleMapsUri")
    place["google_rating"] = google.get("rating")
    place["google_user_rating_count"] = google.get("userRatingCount")
    if google.get("formattedAddress") and not place.get("address"):
        place["address"] = google["formattedAddress"]
    photos = google.get("photos") or []
    photo_name = photos[0].get("name") if photos and isinstance(photos[0], dict) else None
    if photo_name and include_photo:
        place["image_url"] = google_photo_url(photo_name, api_key)
        place["image_credit"] = "Google Places"
    return place


def checked_google_limit(requested: int, place_count: int) -> int:
    limit = requested or min(DEFAULT_GOOGLE_IMPORT_LIMIT, place_count)
    if limit < 0:
        raise SystemExit("--google-limit must be greater than or equal to 0")
    free_cap = min(GOOGLE_FREE_TEXT_SEARCH_MONTHLY_CAP, GOOGLE_FREE_PHOTO_MONTHLY_CAP)
    if limit > free_cap:
        raise SystemExit(
            f"--google-limit {limit} exceeds the guarded free-tier cap {free_cap}. "
            "Run in smaller monthly batches or raise the cap in code after accepting billing risk."
        )
    return min(limit, place_count)


def category(tags: dict[str, str]) -> str | None:
    for key, mapping in (
        ("amenity", KIND_BY_AMENITY),
        ("tourism", KIND_BY_TOURISM),
        ("leisure", KIND_BY_LEISURE),
        ("natural", KIND_BY_NATURAL),
        ("historic", KIND_BY_HISTORIC),
        ("building", KIND_BY_BUILDING),
        ("highway", KIND_BY_HIGHWAY),
    ):
        raw = tags.get(key)
        if raw in mapping:
            return mapping[raw]
    if tags.get("religion") and tags.get("amenity") == "place_of_worship":
        return "den_chua"
    if tags.get("historic"):
        return "di_tich"
    return None


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
    area = (
        tags.get("addr:province")
        or tags.get("addr:city")
        or tags.get("addr:district")
        or tags.get("addr:suburb")
        or tags.get("is_in:province")
        or tags.get("is_in")
        or "Việt Nam"
    )
    feature_tags = [
        value
        for value in (
            tags.get("amenity"),
            tags.get("building"),
            tags.get("cuisine"),
            tags.get("historic"),
            tags.get("highway"),
            tags.get("leisure"),
            tags.get("natural"),
            tags.get("outdoor_seating"),
            tags.get("religion"),
            tags.get("tourism"),
            tags.get("wheelchair"),
        )
        if value and value not in {"yes", "no"}
    ]
    place = {
        "id": f"osm-{osm_type}-{osm_id}",
        "name": name,
        "kind": kind,
        "area": area,
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
    if tags.get("wikidata"):
        place["wikidata_id"] = tags["wikidata"]
    wikipedia_url = tags.get("wikipedia")
    if wikipedia_url:
        place["wikipedia"] = wikipedia_url
    return place


def distance_km(first: dict, second: dict) -> float:
    lat1, lng1 = math.radians(float(first["lat"])), math.radians(float(first["lng"]))
    lat2, lng2 = math.radians(float(second["lat"])), math.radians(float(second["lng"]))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    haversine = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 6371.0 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def filter_food_near_travel_anchors(
    places: list[dict], radius_km: float = DEFAULT_FOOD_ANCHOR_RADIUS_KM
) -> tuple[list[dict], int]:
    anchors = [place for place in places if place["kind"] in TRAVEL_ANCHOR_KINDS]
    if not anchors:
        return places, 0
    filtered: list[dict] = []
    removed = 0
    for place in places:
        if place["kind"] not in FOOD_KINDS:
            filtered.append(place)
            continue
        if any(distance_km(place, anchor) <= radius_km for anchor in anchors):
            filtered.append(place)
        else:
            removed += 1
    return filtered, removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=OVERPASS_URL)
    parser.add_argument("--scope", choices=("hanoi", "vietnam"), default="hanoi")
    parser.add_argument(
        "--group",
        choices=("all", *VIETNAM_GROUP_QUERIES.keys()),
        default="all",
        help="Vietnam import group. all fetches smaller groups sequentially and merges them.",
    )
    parser.add_argument("--pause-between-groups", type=int, default=12)
    parser.add_argument("--food-anchor-radius-km", type=float, default=DEFAULT_FOOD_ANCHOR_RADIUS_KM)
    parser.add_argument("--output", type=Path, default=Path("data/places.json"))
    parser.add_argument(
        "--with-google",
        action="store_true",
        help="Enrich OSM places with Google Places data when GOOGLE_MAPS_API_KEY is set.",
    )
    parser.add_argument(
        "--google-limit",
        type=int,
        default=0,
        help=(
            f"Maximum places to enrich with Google Places. 0 uses the safe default "
            f"{DEFAULT_GOOGLE_IMPORT_LIMIT}. Hard-capped at "
            f"{min(GOOGLE_FREE_TEXT_SEARCH_MONTHLY_CAP, GOOGLE_FREE_PHOTO_MONTHLY_CAP)}."
        ),
    )
    args = parser.parse_args()
    fetched_at = datetime.now(UTC).isoformat()
    query_groups = (
        list(DEFAULT_VIETNAM_GROUPS)
        if args.scope == "vietnam" and args.group == "all"
        else [args.group]
    )
    elements_by_key: dict[tuple[str, int], dict] = {}
    for group in query_groups:
        query_text = query(args.scope, group)
        print(f"Fetching OSM group: {group}", flush=True)
        payload = fetch_overpass(args.endpoint, query_text)
        before = len(elements_by_key)
        for element in payload.get("elements", []):
            element_type, element_id = element.get("type"), element.get("id")
            if isinstance(element_type, str) and isinstance(element_id, int):
                elements_by_key[(element_type, element_id)] = element
        print(f"Fetched group {group}: +{len(elements_by_key) - before} unique elements", flush=True)
        if args.scope == "vietnam" and group != query_groups[-1] and args.pause_between_groups > 0:
            time.sleep(args.pause_between_groups)
    places = [
        place for element in elements_by_key.values() if (place := normalize(element, fetched_at))
    ]
    food_filtered_count = 0
    if args.scope == "vietnam":
        places, food_filtered_count = filter_food_near_travel_anchors(
            places, args.food_anchor_radius_km
        )
    google_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    google_enriched = 0
    if args.with_google:
        if not google_api_key:
            raise SystemExit("--with-google requires GOOGLE_MAPS_API_KEY")
        limit = checked_google_limit(args.google_limit, len(places))
        enriched_places = []
        for index, place in enumerate(places):
            if index < limit:
                place = enrich_with_google(
                    place,
                    google_api_key,
                    include_photo=index < GOOGLE_FREE_PHOTO_MONTHLY_CAP,
                )
                google_enriched += 1 if place.get("google_place_id") else 0
            enriched_places.append(place)
        places = enriched_places
    places.sort(key=lambda item: (item["kind"], item["area"], item["name"]))
    coverage = Counter((place["kind"], place["area"]) for place in places)
    output = {
        "metadata": {
            "provider": "OpenStreetMap Overpass",
            "endpoint": args.endpoint,
            "scope": args.scope,
            "groups": query_groups,
            "bbox": HANOI_BBOX if args.scope == "hanoi" else None,
            "osm_area": VIETNAM_AREA if args.scope == "vietnam" else None,
            "fetched_at": fetched_at,
            "license": "ODbL 1.0",
            "schema": "places.json-compatible",
            "food_anchor_radius_km": args.food_anchor_radius_km if args.scope == "vietnam" else None,
            "food_filtered_out_count": food_filtered_count,
            "count": len(places),
            "coverage_cells": len(coverage),
            "generated_unix": int(time.time()),
            "google_places": {
                "enabled": bool(args.with_google),
                "requested_limit": args.google_limit,
                "applied_limit": checked_google_limit(args.google_limit, len(places))
                if args.with_google
                else 0,
                "monthly_guard_caps": {
                    "text_search": GOOGLE_FREE_TEXT_SEARCH_MONTHLY_CAP,
                    "photos": GOOGLE_FREE_PHOTO_MONTHLY_CAP,
                },
                "enriched_count": google_enriched,
                "pricing_note": (
                    "Guarded to stay below the configured free-tier caps. "
                    "Keep Google Cloud budget alerts enabled."
                ),
            },
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
