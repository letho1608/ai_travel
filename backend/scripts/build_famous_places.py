"""Build famous_places.json from OSM, Wikipedia/heritage evidence, then LLM scores.

OSM proves a mapped tourist/heritage feature exists. Wikipedia, national
heritage, or curated anchors set muc_uu_tien=1. The LLM may only score
remaining ids and cannot invent places.

  python scripts/build_famous_places.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(ROOT))

from app.data import (  # noqa: E402
    CURATED_HANOI_ANCHORS,
    CURATED_NHA_TRANG_ANCHORS,
    CURATED_OTHER_PROVINCE_ANCHORS,
    CURATED_VN_ANCHORS,
    Place,
    place_match_key,
    place_name_key,
)
from app.pipeline.famous_score import (  # noqa: E402
    apply_hybrid_scores,
    dumps_prompt,
    grey_zone_rows,
    llm_candidates,
    llm_prompt,
    parse_llm_scores,
)

DATA_DIR = ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "vietnam_places.json"
DEFAULT_OUTPUT = DATA_DIR / "famous_places.json"
LLM_CACHE_PATH = DATA_DIR / "famous_llm_cache.json"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "MinhDiDauThe/1.0 (famous places local build)"
VN_LAT = (8.0, 24.5)
VN_LNG = (102.0, 110.5)

SIGHT_KINDS = {
    "bai_bien",
    "bao_tang",
    "cam_trai",
    "cho",
    "cong_vien",
    "den_chua",
    "di_tich",
    "dia_danh",
    "giai_tri",
    "hang_dong",
    "nui",
    "thac_nuoc",
}
ALWAYS_KINDS = {"bao_tang", "bai_bien", "hang_dong", "den_chua", "giai_tri"}
GOOD_TAGS = {
    "attraction",
    "aquarium",
    "archaeological_site",
    "bay",
    "beach",
    "castle",
    "cave_entrance",
    "gallery",
    "heritage",
    "museum",
    "nature_reserve",
    "pagoda",
    "ruins",
    "temple",
    "theme_park",
    "tomb",
    "viewpoint",
    "waterfall",
    "zoo",
}
SKIP_TAGS = {"artwork", "tree", "boundary_stone", "path"}
SKIP_KINDS = {"nha_hang", "cafe", "quan_an", "khach_san", "nha_nghi", "homestay"}
DI_TICH_TAGS = {
    "archaeological_site",
    "castle",
    "city_gate",
    "heritage",
    "memorial",
    "monument",
    "ruins",
    "tomb",
}
DURATION_BY_KIND = {
    "bai_bien": 90,
    "bao_tang": 75,
    "cam_trai": 90,
    "cho": 75,
    "cong_vien": 70,
    "den_chua": 60,
    "di_tich": 75,
    "dia_danh": 60,
    "giai_tri": 150,
    "hang_dong": 90,
    "nui": 90,
    "thac_nuoc": 75,
}
BLOCKED_WIKIDATA = {
    "Q5",
    "Q16521",
    "Q19675",
    "Q27686",
    "Q316",
}
CITY_NAME_ALLOW = {"ha long", "nha trang"}

# Nearest-hub assignment for tinh. Tourist names, not 2025 merger codes.
DESTINATION_HUBS: tuple[tuple[str, float, float], ...] = (
    ("Hà Nội", 21.0285, 105.8542),
    ("Hải Phòng", 20.8449, 106.6881),
    ("Hạ Long", 20.9712, 107.0448),
    ("Cát Bà", 20.7278, 107.0482),
    ("Cô Tô", 20.9770, 107.7660),
    ("Ninh Bình", 20.2506, 105.9745),
    ("Nam Định", 20.4389, 106.1621),
    ("Thanh Hóa", 19.8067, 105.7852),
    ("Vinh", 18.6796, 105.6813),
    ("Hà Tĩnh", 18.3428, 105.9059),
    ("Phong Nha", 17.5908, 106.2833),
    ("Đồng Hới", 17.4689, 106.6223),
    ("Huế", 16.4637, 107.5909),
    ("Đà Nẵng", 16.0544, 108.2022),
    ("Hội An", 15.8801, 108.3380),
    ("Lý Sơn", 15.3804, 109.1173),
    ("Quảng Ngãi", 15.1214, 108.8044),
    ("Quy Nhơn", 13.7820, 109.2196),
    ("Tuy Hòa", 13.0882, 109.0929),
    ("Nha Trang", 12.2388, 109.1967),
    ("Phan Rang", 11.5643, 108.9886),
    ("Mũi Né", 10.9334, 108.2700),
    ("Vũng Tàu", 10.4114, 107.1362),
    ("Côn Đảo", 8.6930, 106.6100),
    ("TP.HCM", 10.7769, 106.7009),
    ("Tây Ninh", 11.3350, 106.1090),
    ("Cần Thơ", 10.0452, 105.7469),
    ("Châu Đốc", 10.7000, 105.1170),
    ("Phú Quốc", 10.2899, 103.9840),
    ("Cà Mau", 9.1769, 105.1524),
    ("Đà Lạt", 11.9404, 108.4583),
    ("Buôn Ma Thuột", 12.6662, 108.0382),
    ("Pleiku", 13.9833, 108.0000),
    ("Kon Tum", 14.3545, 108.0076),
    ("Sa Pa", 22.3364, 103.8438),
    ("Điện Biên Phủ", 21.3860, 103.0160),
    ("Hà Giang", 22.8233, 104.9836),
    ("Đồng Văn", 23.2764, 105.3581),
    ("Cao Bằng", 22.6666, 106.2639),
    ("Lạng Sơn", 21.8530, 106.7610),
    ("Mai Châu", 20.6560, 105.0850),
    ("Yên Bái", 21.7228, 104.9113),
    ("Phú Thọ", 21.3846, 105.3131),
    ("Mỹ Tho", 10.3600, 106.3650),
)

VIWIKI_QUERY = """
SELECT DISTINCT ?qid ?itemLabel ?lat ?lon ?article WHERE {
  ?item wdt:P17 wd:Q881 .
  ?item p:P625/psv:P625/wikibase:geoLatitude ?lat .
  ?item p:P625/psv:P625/wikibase:geoLongitude ?lon .
  FILTER(?lat >= 8 && ?lat <= 24.5 && ?lon >= 102 && ?lon <= 110.5)
  {
    ?item wdt:P1435 ?heritage .
  } UNION {
    VALUES ?class { wd:Q570116 wd:Q33506 wd:Q46169 wd:Q839954 wd:Q4989906 wd:Q23413 wd:Q9259 wd:Q40080 wd:Q35509 wd:Q16970 wd:Q108169 wd:Q44539 }
    ?item wdt:P31/wdt:P279* ?class .
  }
  ?article schema:about ?item ;
           schema:isPartOf <https://vi.wikipedia.org/> .
  MINUS { ?item wdt:P31/wdt:P279* wd:Q5 . }
  MINUS { ?item wdt:P31/wdt:P279* wd:Q16521 . }
  BIND(STRAFTER(STR(?item), "entity/") AS ?qid)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en". }
}
"""

WIKIDATA_QUERY = """
SELECT DISTINCT ?qid ?itemLabel ?lat ?lon ?group WHERE {
  ?item wdt:P17 wd:Q881 .
  ?item p:P625/psv:P625/wikibase:geoLatitude ?lat .
  ?item p:P625/psv:P625/wikibase:geoLongitude ?lon .
  {
    ?item wdt:P1435 ?h .
    BIND("heritage" AS ?group)
  } UNION {
    ?item wdt:P31/wdt:P279* wd:Q33506 .
    BIND("museum" AS ?group)
  } UNION {
    ?item wdt:P31/wdt:P279* wd:Q46169 .
    BIND("national_park" AS ?group)
  }
  BIND(STRAFTER(STR(?item), "entity/") AS ?qid)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en". }
}
"""


def ascii_fold(value: str) -> str:
    translated = value.translate(str.maketrans({"đ": "d", "Đ": "D"}))
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", translated) if not unicodedata.combining(ch)
    )
    return stripped.encode("ascii", "ignore").decode("ascii").lower()


def in_vietnam(lat: float, lng: float) -> bool:
    return VN_LAT[0] <= lat <= VN_LAT[1] and VN_LNG[0] <= lng <= VN_LNG[1]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlng1, rlat2, rlng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    dlat, dlng = rlat2 - rlat1, rlng2 - rlng1
    chord = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(chord), math.sqrt(1 - chord))


def assign_tinh(lat: float, lng: float, area: str | None = None) -> str:
    area_key = ascii_fold(area or "")
    for label, hub_lat, hub_lng in DESTINATION_HUBS:
        if area_key and area_key == ascii_fold(label):
            return label
    nearest = min(
        DESTINATION_HUBS,
        key=lambda hub: haversine_km(lat, lng, hub[1], hub[2]),
    )
    return nearest[0]


def skip_admin_name(name: str, kind: str, tags: set[str]) -> bool:
    key = place_name_key(name)
    hub_keys = {ascii_fold(label) for label, _, _ in DESTINATION_HUBS}
    if key not in hub_keys:
        return False
    if key in CITY_NAME_ALLOW and tags.intersection({"beach", "bay", "attraction", "nature_reserve"}):
        return False
    return kind in {"di_tich", "dia_danh"} and "attraction" not in tags


def is_osm_tourist(item: dict) -> bool:
    kind = item.get("kind") or ""
    if kind in SKIP_KINDS or kind not in SIGHT_KINDS:
        return False
    tags = set(item.get("tags") or [])
    if tags & SKIP_TAGS and not tags.intersection({"attraction", "museum", "theme_park"}):
        return False
    if skip_admin_name(item.get("name") or "", kind, tags):
        return False
    qid = str(item.get("wikidata_id") or "")
    if qid in BLOCKED_WIKIDATA:
        return False
    if kind in ALWAYS_KINDS:
        return True
    if tags & GOOD_TAGS:
        return True
    if kind == "di_tich" and tags & DI_TICH_TAGS:
        return True
    if kind == "nui" and (item.get("wikidata_id") or item.get("image_url") or tags.intersection({"attraction", "viewpoint"})):
        return True
    if kind == "cong_vien" and tags.intersection({"attraction", "nature_reserve", "garden"}):
        return True
    return False


def sparql_json(query: str, timeout: int = 90) -> dict:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
    request = urllib.request.Request(
        WIKIDATA_SPARQL,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _binding_point(binding: dict) -> tuple[str, str, float, float] | None:
    qid = binding.get("qid", {}).get("value")
    name = binding.get("itemLabel", {}).get("value")
    try:
        lat = float(binding.get("lat", {}).get("value"))
        lng = float(binding.get("lon", {}).get("value"))
    except (TypeError, ValueError):
        return None
    if not qid or not name or not qid.startswith("Q") or not in_vietnam(lat, lng):
        return None
    if qid in BLOCKED_WIKIDATA:
        return None
    if name.startswith("Q") and name[1:].isdigit():
        return None
    return qid, name, lat, lng


def fetch_wikidata(timeout: int = 90) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    payload = sparql_json(WIKIDATA_QUERY, timeout=timeout)
    kind_by_group = {"museum": "bao_tang", "national_park": "cong_vien", "heritage": "di_tich"}
    for binding in payload.get("results", {}).get("bindings", []):
        parsed = _binding_point(binding)
        if parsed is None:
            continue
        qid, name, lat, lng = parsed
        if qid in seen:
            continue
        seen.add(qid)
        group = binding.get("group", {}).get("value") or "heritage"
        rows.append(
            {
                "id": f"wd-{qid}",
                "name": name,
                "kind": kind_by_group.get(group, "di_tich"),
                "lat": lat,
                "lng": lng,
                "wikidata_id": qid,
                "source": "Wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{qid}",
                "wikidata_group": group,
            }
        )
    return rows


def fetch_viwiki_places(timeout: int = 90) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    payload = sparql_json(VIWIKI_QUERY, timeout=timeout)
    for binding in payload.get("results", {}).get("bindings", []):
        parsed = _binding_point(binding)
        if parsed is None:
            continue
        qid, name, lat, lng = parsed
        if qid in seen:
            continue
        seen.add(qid)
        article = binding.get("article", {}).get("value")
        rows.append(
            {
                "id": f"wd-{qid}",
                "name": name,
                "lat": lat,
                "lng": lng,
                "wikidata_id": qid,
                "wikipedia_url": article,
            }
        )
    return rows


def match_named_points(osm_rows: list[dict], named_rows: list[dict]) -> tuple[list[dict], int, set[str], set[str]]:
    extras: list[dict] = []
    matched_count = 0
    matched_ids: set[str] = set()
    matched_names: set[str] = set()
    for named in named_rows:
        named_key = place_name_key(named["name"])
        best = None
        best_km = 2.5
        for osm in osm_rows:
            distance = haversine_km(named["lat"], named["lng"], float(osm["lat"]), float(osm["lng"]))
            same_name = place_name_key(osm["name"]) == named_key
            if not same_name and distance > 0.8:
                continue
            if distance < best_km and (same_name or distance <= 0.8):
                best = osm
                best_km = distance
        if best is None:
            extras.append(named)
            continue
        matched_count += 1
        matched_ids.add(best["id"])
        matched_names.add(place_name_key(best["name"]))
        if named.get("wikidata_id") and not best.get("wikidata_id"):
            best["wikidata_id"] = named["wikidata_id"]
        if named.get("wikipedia_url"):
            best["wikipedia_url"] = named["wikipedia_url"]
        if named.get("wikidata_group"):
            tags = list(best.get("tags") or [])
            if named["wikidata_group"] == "heritage" and "heritage" not in tags:
                tags.append("heritage")
            best["tags"] = tags
            best["wikidata_group"] = named["wikidata_group"]
    return extras, matched_count, matched_ids, matched_names


def row_from_osm(item: dict, curated_keys: set[str]) -> dict:
    lat, lng = float(item["lat"]), float(item["lng"])
    area = item.get("area") or ""
    tinh = assign_tinh(lat, lng, area)
    tags = list(item.get("tags") or [])
    if "famous" not in tags:
        tags.append("famous")
    kind = item["kind"]
    return {
        "id": item["id"],
        "name": item["name"],
        "kind": kind,
        "tinh": tinh,
        "area": tinh if ascii_fold(area) in {"", "viet nam", "vietnam"} else area,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "cost": int(item.get("cost") or 0),
        "duration_min": int(item.get("duration_min") or DURATION_BY_KIND.get(kind, 60)),
        "open_hour": int(item.get("open_hour") or 7),
        "close_hour": int(item.get("close_hour") or 22),
        "tags": sorted(set(tags)),
        "muc_uu_tien": 3,
        "bang_chung": "osm_unscored",
        "source": item.get("source") or "OpenStreetMap",
        "source_url": item.get("source_url"),
        "image_url": item.get("image_url"),
        "image_credit": item.get("image_credit"),
        "wikidata_id": item.get("wikidata_id"),
        "wikipedia_url": item.get("wikipedia_url"),
        "ghi_chu": "",
    }


def row_from_place(place: Place, curated_keys: set[str]) -> dict:
    tinh = assign_tinh(place.lat, place.lng, place.area)
    tags = list(place.tags)
    if "famous" not in tags:
        tags.append("famous")
    return {
        "id": place.id,
        "name": place.name,
        "kind": place.kind,
        "tinh": tinh,
        "area": place.area,
        "lat": round(place.lat, 6),
        "lng": round(place.lng, 6),
        "cost": place.cost,
        "duration_min": place.duration_min,
        "open_hour": place.open_hour,
        "close_hour": place.close_hour,
        "tags": sorted(set(tags)),
        "muc_uu_tien": 1,
        "bang_chung": "curated",
        "source": place.source or "curated",
        "source_url": place.source_url,
        "image_url": place.image_url,
        "image_credit": place.image_credit,
        "wikidata_id": None,
        "wikipedia_url": None,
        "ghi_chu": "curated_anchor",
    }


def row_from_wikidata(item: dict) -> dict:
    tinh = assign_tinh(item["lat"], item["lng"])
    kind = item["kind"]
    return {
        "id": item["id"],
        "name": item["name"],
        "kind": kind,
        "tinh": tinh,
        "area": tinh,
        "lat": round(item["lat"], 6),
        "lng": round(item["lng"], 6),
        "cost": 0,
        "duration_min": DURATION_BY_KIND.get(kind, 75),
        "open_hour": 7,
        "close_hour": 22,
        "tags": ["famous", "heritage"] if item.get("wikidata_group") == "heritage" else ["famous"],
        "muc_uu_tien": 1,
        "bang_chung": "heritage" if item.get("wikidata_group") == "heritage" else "wikipedia",
        "source": "Wikidata",
        "source_url": item["source_url"],
        "image_url": None,
        "image_credit": None,
        "wikidata_id": item["wikidata_id"],
        "wikipedia_url": item.get("wikipedia_url"),
        "ghi_chu": item.get("wikidata_group") or "",
    }


def dedupe(rows: list[dict]) -> list[dict]:
    kept: list[dict] = []
    index: dict[str, int] = {}
    for row in rows:
        key = place_match_key(row["name"]) or place_name_key(row["name"])
        existing_i = index.get(key)
        if existing_i is None:
            index[key] = len(kept)
            kept.append(row)
            continue
        existing = kept[existing_i]
        distance = haversine_km(existing["lat"], existing["lng"], row["lat"], row["lng"])
        if distance > 3.0:
            index[f"{key}:{row['id']}"] = len(kept)
            kept.append(row)
            continue
        score = (
            int(bool(row.get("wikidata_id"))),
            int(bool(row.get("image_url"))),
            int(row.get("id", "").startswith("osm-")),
            -int(row.get("muc_uu_tien") or 3),
        )
        current = (
            int(bool(existing.get("wikidata_id"))),
            int(bool(existing.get("image_url"))),
            int(existing.get("id", "").startswith("osm-")),
            -int(existing.get("muc_uu_tien") or 3),
        )
        if score > current:
            kept[existing_i] = row
    return kept


def load_llm_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_llm_cache(path: Path, cache: dict) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def llm_client_config() -> dict | None:
    from app.config import settings

    if settings.ai_mode == "mock" or not settings.ai_api_key:
        return None
    return {
        "base_url": settings.ai_base_url.rstrip("/"),
        "api_key": settings.ai_api_key,
        "model": settings.ai_model,
    }


def call_llm_batch(config: dict, prompt: dict) -> dict:
    import httpx

    response = httpx.post(
        f"{config['base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {config['api_key']}"},
        json={
            "model": config["model"],
            "messages": [
                {"role": "system", "content": "Only return a valid JSON object."},
                {"role": "user", "content": dumps_prompt(prompt)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 1400,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise TypeError("LLM fame score is not an object")
    return payload


def score_grey_with_llm(
    grey: list[dict],
    cache: dict,
    *,
    batch_size: int = 20,
    sleep_s: float = 0.4,
) -> tuple[dict[str, dict], dict]:
    config = llm_client_config()
    stats = {
        "cache_hits": 0,
        "scored": 0,
        "batches": 0,
        "errors": 0,
        "skipped": config is None,
        "skip_reason": None if config else "AI_MODE=mock or missing API key",
    }
    scores: dict[str, dict] = {}
    pending: list[dict] = []
    for row in grey:
        cached = cache.get(row["id"])
        if isinstance(cached, dict) and cached.get("name_key") == place_name_key(row["name"]):
            scores[row["id"]] = {
                "muc_uu_tien": int(cached["muc_uu_tien"]),
                "ly_do": cached.get("ly_do") or "",
            }
            stats["cache_hits"] += 1
            continue
        pending.append(row)
    if config is None:
        return scores, stats

    by_tinh: dict[str, list[dict]] = {}
    for row in pending:
        by_tinh.setdefault(str(row.get("tinh") or "Việt Nam"), []).append(row)

    for tinh, group in by_tinh.items():
        for start in range(0, len(group), batch_size):
            batch = group[start : start + batch_size]
            allowed = {item["id"] for item in batch}
            stats["batches"] += 1
            try:
                payload = call_llm_batch(config, llm_prompt(tinh, batch))
                parsed = parse_llm_scores(payload, allowed)
            except Exception:
                stats["errors"] += 1
                continue
            for place_id, item in parsed.items():
                scores[place_id] = item
                cache[place_id] = {
                    "name_key": place_name_key(next(row["name"] for row in batch if row["id"] == place_id)),
                    "muc_uu_tien": item["muc_uu_tien"],
                    "ly_do": item.get("ly_do") or "",
                }
                stats["scored"] += 1
            time.sleep(sleep_s)
    return scores, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-wikidata", action="store_true")
    parser.add_argument("--skip-wikipedia", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--llm-cache", type=Path, default=LLM_CACHE_PATH)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    catalog = payload.get("places") or []
    curated = (
        *CURATED_HANOI_ANCHORS,
        *CURATED_NHA_TRANG_ANCHORS,
        *CURATED_OTHER_PROVINCE_ANCHORS,
        *CURATED_VN_ANCHORS,
    )
    curated_keys = {place_name_key(place.name) for place in curated} | {
        place_match_key(place.name) for place in curated
    }

    osm_hits = [
        item
        for item in catalog
        if is_osm_tourist(item) and in_vietnam(float(item["lat"]), float(item["lng"]))
    ]

    wd_extras: list[dict] = []
    wd_matched = 0
    heritage_ids: set[str] = set()
    heritage_names: set[str] = set()
    wikidata_error = None
    if not args.skip_wikidata:
        try:
            wd_rows = fetch_wikidata()
            wd_extras, wd_matched, heritage_ids, heritage_names = match_named_points(osm_hits, wd_rows)
            for extra in wd_extras:
                if extra.get("id"):
                    heritage_ids.add(str(extra["id"]))
                if extra.get("name"):
                    heritage_names.add(place_name_key(str(extra["name"])))
        except Exception as exc:  # noqa: BLE001 — network overlay is optional
            wikidata_error = str(exc)

    wikipedia_ids: set[str] = set()
    wikipedia_names: set[str] = set()
    wikipedia_matched = 0
    wikipedia_error = None
    if not args.skip_wikipedia:
        try:
            wiki_rows = fetch_viwiki_places()
            _, wikipedia_matched, wikipedia_ids, wikipedia_names = match_named_points(osm_hits, wiki_rows)
        except Exception as exc:  # noqa: BLE001 — network overlay is optional
            wikipedia_error = str(exc)

    rows = [row_from_osm(item, curated_keys) for item in osm_hits]
    for extra in wd_extras:
        if extra.get("name") and extra.get("lat"):
            if "kind" not in extra:
                extra["kind"] = "di_tich"
            if "source_url" not in extra:
                extra["source_url"] = f"https://www.wikidata.org/wiki/{extra.get('wikidata_id')}"
            rows.append(row_from_wikidata(extra))
    existing_keys = {place_name_key(row["name"]) for row in rows}
    existing_matches = {place_match_key(row["name"]) for row in rows}
    for place in curated:
        if place.kind in SKIP_KINDS:
            continue
        if place_name_key(place.name) in existing_keys or place_match_key(place.name) in existing_matches:
            continue
        rows.append(row_from_place(place, curated_keys))
        existing_keys.add(place_name_key(place.name))
        existing_matches.add(place_match_key(place.name))

    rows = [row for row in dedupe(rows) if in_vietnam(row["lat"], row["lng"])]
    rows = apply_hybrid_scores(
        rows,
        curated_keys=curated_keys,
        wikipedia_ids=wikipedia_ids,
        wikipedia_names=wikipedia_names,
        heritage_ids=heritage_ids,
        heritage_names=heritage_names,
    )

    llm_stats = {"skipped": True, "skip_reason": "--skip-llm"}
    if not args.skip_llm:
        cache = load_llm_cache(args.llm_cache)
        llm_scores, llm_stats = score_grey_with_llm(llm_candidates(rows), cache, batch_size=12, sleep_s=0.8)
        save_llm_cache(args.llm_cache, cache)
        rows = apply_hybrid_scores(
            rows,
            curated_keys=curated_keys,
            wikipedia_ids=wikipedia_ids,
            wikipedia_names=wikipedia_names,
            heritage_ids=heritage_ids,
            heritage_names=heritage_names,
            llm_scores=llm_scores,
        )

    rows.sort(key=lambda item: (item["tinh"], item["muc_uu_tien"], item["kind"], item["name"]))
    by_tinh = Counter(row["tinh"] for row in rows)
    by_evidence = Counter(row.get("bang_chung") or "unknown" for row in rows)
    by_rank = Counter(row.get("muc_uu_tien") for row in rows)
    output = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "license": "ODbL 1.0 for OpenStreetMap rows; CC0 for Wikidata/Wikipedia",
            "input": str(args.input),
            "count": len(rows),
            "no_per_province_cap": True,
            "osm_tourist_rows": len(osm_hits),
            "wikidata_matched_existing": wd_matched,
            "wikidata_added": len(wd_extras),
            "wikidata_error": wikidata_error,
            "wikipedia_matched_existing": wikipedia_matched,
            "wikipedia_error": wikipedia_error,
            "llm": llm_stats,
            "by_bang_chung": dict(sorted(by_evidence.items(), key=lambda item: (-item[1], item[0]))),
            "by_muc_uu_tien": {str(key): value for key, value in sorted(by_rank.items())},
            "by_tinh": dict(sorted(by_tinh.items(), key=lambda item: (-item[1], item[0]))),
            "rule": (
                "OSM keeps real mapped tourist/heritage features. Wikipedia/heritage/curated "
                "set muc_uu_tien=1. LLM scores only remaining ids and cannot invent places."
            ),
        },
        "places": rows,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(rows)} places, {len(by_tinh)} hubs)")
    print(f"evidence {dict(by_evidence)} ranks {dict(by_rank)}")
    print(f"wikipedia matched {wikipedia_matched}; heritage matched {wd_matched}")
    print(f"llm {llm_stats}")
    if wikidata_error:
        print(f"wikidata overlay skipped: {wikidata_error}")
    if wikipedia_error:
        print(f"wikipedia overlay skipped: {wikipedia_error}")


if __name__ == "__main__":
    main()
