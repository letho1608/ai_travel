"""Enrich existing places JSON with Wikidata/Wikimedia image metadata.

This script keeps the existing places.json-compatible schema and only adds
optional metadata fields when a trusted Wikimedia/Wikidata match is found.
It is intended for tourism/nature/historic places, not restaurants or hotels.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

ENRICHABLE_KINDS = {
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
FAMOUS_KIND_PRIORITY = {
    "dia_danh": 0,
    "di_tich": 1,
    "bao_tang": 2,
    "den_chua": 3,
    "bai_bien": 4,
    "hang_dong": 5,
    "nui": 6,
    "thac_nuoc": 7,
    "giai_tri": 8,
    "cam_trai": 9,
}
FAMOUS_NAME_HINTS = (
    "bãi ",
    "bảo tàng",
    "cao nguyên",
    "chùa ",
    "cố đô",
    "di tích",
    "dinh ",
    "hang ",
    "hồ ",
    "khu du lịch",
    "lăng ",
    "miếu ",
    "nhà thờ",
    "núi ",
    "phố cổ",
    "suối ",
    "thác ",
    "thành ",
    "tháp ",
    "vịnh ",
    "đền ",
    "động ",
)
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
COMMONS_FILEPATH_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
MIN_SEARCH_NAME_CHARS = 4
GENERIC_SEARCH_NAMES = {"ba", "dumb", "ave maria", "flower market"}
VIETNAM_HINTS = (
    "việt nam",
    "vietnam",
    "hà nội",
    "ha noi",
    "huế",
    "hue",
    "đà nẵng",
    "da nang",
    "hồ chí minh",
    "ho chi minh",
    "quảng",
    "quang",
    "khánh hòa",
    "khanh hoa",
    "lâm đồng",
    "lam dong",
    "ninh bình",
    "ninh binh",
    "lào cai",
    "lao cai",
    "sa pa",
    "sapa",
)


def request_json(url: str, timeout: int = 5, retries: int = 0) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "minh-di-dau-the/0.1 (wikimedia enrichment; local project)"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                return None
            time.sleep(2 * (attempt + 1))
        except (OSError, URLError, json.JSONDecodeError):
            return None
    return None


def normalize_wikipedia_tag(value: str | None) -> str | None:
    if not value or ":" not in value:
        return None
    language, title = value.split(":", 1)
    language = language.strip()
    title = title.strip().replace(" ", "_")
    if not language or not title:
        return None
    return f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(title)}"


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def is_searchable_name(name: str) -> bool:
    normalized = normalized_text(name)
    letters = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)
    if len(letters) < MIN_SEARCH_NAME_CHARS:
        return False
    return normalized not in GENERIC_SEARCH_NAMES


def wikidata_search(place: dict) -> str | None:
    name = str(place.get("name") or "").strip()
    area = str(place.get("area") or "").strip()
    if not name or not is_searchable_name(name):
        return None
    queries = [name]
    if area:
        queries.append(f"{name} {area}")
    queries.append(f"{name} Việt Nam")
    seen_queries: set[str] = set()
    for query in queries:
        if query in seen_queries:
            continue
        seen_queries.add(query)
        params = urllib.parse.urlencode(
            {
                "action": "wbsearchentities",
                "format": "json",
                "language": "vi",
                "uselang": "vi",
                "type": "item",
                "limit": 5,
                "search": query,
            }
        )
        payload = request_json(f"{WIKIDATA_SEARCH_URL}?{params}")
        if not payload:
            continue
        results = payload.get("search")
        if not isinstance(results, list):
            continue
        for result in results:
            qid = result.get("id")
            if not isinstance(qid, str) or not qid.startswith("Q"):
                continue
            haystack = " ".join(
                str(value or "")
                for value in (
                    result.get("label"),
                    result.get("description"),
                    result.get("match", {}).get("text")
                    if isinstance(result.get("match"), dict)
                    else "",
                )
            ).casefold()
            normalized_area = normalized_text(area)
            if normalized_area and normalized_area in haystack:
                return qid
            if any(hint in haystack for hint in VIETNAM_HINTS):
                return qid
    return None


def entity_claim(entity: dict, property_id: str) -> str | None:
    claims = entity.get("claims")
    if not isinstance(claims, dict):
        return None
    values = claims.get(property_id)
    if not isinstance(values, list) or not values:
        return None
    mainsnak = values[0].get("mainsnak")
    if not isinstance(mainsnak, dict):
        return None
    datavalue = mainsnak.get("datavalue")
    if not isinstance(datavalue, dict):
        return None
    value = datavalue.get("value")
    if isinstance(value, str):
        return value
    return None


def enrich_place(place: dict, *, allow_search: bool) -> tuple[dict, bool, str]:
    if place.get("kind") not in ENRICHABLE_KINDS:
        return place, False, "skipped_kind"
    if not is_searchable_name(str(place.get("name") or "")):
        return place, False, "unsafe_name"
    qid = place.get("wikidata_id") or place.get("wikidata")
    if not qid and allow_search:
        qid = wikidata_search(place)
    wikipedia_url = place.get("wikipedia_url") or normalize_wikipedia_tag(place.get("wikipedia"))
    if not qid:
        if wikipedia_url and not place.get("wikipedia_url"):
            enriched = dict(place)
            enriched["wikipedia_url"] = wikipedia_url
            return enriched, True, "matched_wikipedia"
        return place, False, "not_found"
    payload = request_json(WIKIDATA_ENTITY_URL.format(qid=urllib.parse.quote(str(qid))))
    if not payload:
        return place, False, "entity_fetch_failed"
    entity = payload.get("entities", {}).get(qid)
    if not isinstance(entity, dict):
        return place, False, "entity_missing"
    enriched = dict(place)
    enriched["wikidata_id"] = qid
    if wikipedia_url:
        enriched["wikipedia_url"] = wikipedia_url
    commons_category = entity_claim(entity, "P373")
    if commons_category:
        enriched["wikimedia_commons_category"] = commons_category
    image_file = entity_claim(entity, "P18")
    if image_file and not enriched.get("image_url"):
        encoded_file = urllib.parse.quote(image_file.replace(" ", "_"))
        enriched["image_url"] = COMMONS_FILEPATH_URL.format(filename=encoded_file) + "?width=800"
        enriched["image_credit"] = "Wikimedia Commons"
    return enriched, enriched != place, "matched"


def already_enriched(place: dict) -> bool:
    return bool(
        place.get("wikidata_id")
        or place.get("wikimedia_commons_category")
        or place.get("wikipedia_url")
        or place.get("image_url")
    )


def already_attempted(place: dict) -> bool:
    return bool(place.get("wikimedia_attempted"))


def mark_attempt(place: dict, status: str) -> dict:
    marked = dict(place)
    marked["wikimedia_attempted"] = True
    marked["wikimedia_status"] = status
    marked["wikimedia_attempted_at"] = datetime.now(UTC).isoformat()
    return marked


def clear_wikimedia_fields(place: dict) -> dict:
    cleaned = dict(place)
    for key in (
        "wikidata_id",
        "wikimedia_commons_category",
        "wikipedia_url",
        "image_url",
        "image_credit",
    ):
        cleaned.pop(key, None)
    return cleaned


def is_suspect_enrichment(place: dict) -> bool:
    if not already_enriched(place):
        return False
    return not is_searchable_name(str(place.get("name") or ""))


def famous_priority(place: dict) -> tuple[int, int, str]:
    kind = str(place.get("kind") or "")
    name = str(place.get("name") or "").casefold()
    hint_rank = 0 if any(hint in name for hint in FAMOUS_NAME_HINTS) else 1
    return (FAMOUS_KIND_PRIORITY.get(kind, 99), hint_rank, name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/vietnam_places.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--search-wikidata",
        action="store_true",
        help="Search Wikidata by name when OSM did not provide a wikidata tag.",
    )
    parser.add_argument("--pause", type=float, default=0.1)
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print progress after this many enrichable places; use 0 to disable.",
    )
    parser.add_argument(
        "--prioritize-famous",
        action="store_true",
        help="Process likely famous tourism places first, then append the rest unchanged.",
    )
    parser.add_argument(
        "--skip-enriched",
        action="store_true",
        help="Do not spend requests on places that already have Wikimedia/Wikidata metadata.",
    )
    parser.add_argument(
        "--skip-attempted",
        action="store_true",
        help="Do not spend requests on places that were already attempted, even when no match was found.",
    )
    parser.add_argument(
        "--kinds",
        help="Comma-separated place kinds to enrich; defaults to all Wikimedia-suitable kinds.",
    )
    parser.add_argument(
        "--clean-suspect",
        action="store_true",
        help="Remove existing Wikimedia fields from places with unsafe/generic names before enriching.",
    )
    parser.add_argument(
        "--mark-legacy-attempted",
        type=int,
        default=0,
        help="Mark this many prioritized matching places as attempted without calling Wikidata.",
    )
    parser.add_argument(
        "--mark-legacy-only",
        action="store_true",
        help="Only mark legacy attempted places, then write output without running enrichment.",
    )
    args = parser.parse_args()
    output_path = args.output or args.input
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    places = payload.get("places", [])
    allowed_kinds = (
        {kind.strip() for kind in args.kinds.split(",") if kind.strip()}
        if args.kinds
        else ENRICHABLE_KINDS
    )
    enriched_count = 0
    cleaned_count = 0
    processed = 0
    status_counts: dict[str, int] = {}
    indexed_places = list(enumerate(places))
    if args.prioritize_famous:
        indexed_places.sort(key=lambda item: famous_priority(item[1]))
    enriched_by_index: dict[int, dict] = {}
    legacy_marked_count = 0
    for original_index, place in indexed_places:
        if args.clean_suspect and is_suspect_enrichment(place):
            place = clear_wikimedia_fields(place)
            cleaned_count += 1
        if (
            args.mark_legacy_attempted
            and legacy_marked_count < args.mark_legacy_attempted
            and place.get("kind") in allowed_kinds
            and not already_attempted(place)
        ):
            place = mark_attempt(
                place,
                "legacy_matched" if already_enriched(place) else "legacy_attempted",
            )
            legacy_marked_count += 1
            enriched_by_index[original_index] = place
            continue
        if args.mark_legacy_only:
            enriched_by_index[original_index] = place
            continue
        if args.limit and processed >= args.limit:
            enriched_by_index[original_index] = place
            continue
        if (
            place.get("kind") in allowed_kinds
            and not (args.skip_enriched and already_enriched(place))
            and not (args.skip_attempted and already_attempted(place))
        ):
            processed += 1
            if args.progress_every and processed == 1:
                print(f"Processing Wikimedia enrichment from {args.input} ...", flush=True)
            place, changed, status = enrich_place(place, allow_search=args.search_wikidata)
            place = mark_attempt(place, status)
            status_counts[status] = status_counts.get(status, 0) + 1
            if changed:
                enriched_count += 1
            if args.progress_every and processed % args.progress_every == 0:
                print(
                    f"Processed {processed} enrichable places; enriched {enriched_count}.",
                    flush=True,
                )
            if args.pause > 0:
                time.sleep(args.pause)
        enriched_by_index[original_index] = place
    result = [enriched_by_index.get(index, place) for index, place in enumerate(places)]
    payload["places"] = result
    metadata = payload.setdefault("metadata", {})
    metadata["wikimedia"] = {
        "enabled": True,
        "search_wikidata": args.search_wikidata,
        "kinds": sorted(allowed_kinds),
        "processed_count": processed,
        "enriched_count": enriched_count,
        "cleaned_suspect_count": cleaned_count,
        "legacy_marked_count": legacy_marked_count,
        "status_counts": status_counts,
        "license_note": "Images are linked from Wikimedia Commons; preserve attribution/license before reuse.",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Enriched {enriched_count}/{processed} places with Wikimedia data -> {output_path}")


if __name__ == "__main__":
    main()
