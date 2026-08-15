from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLACES = ROOT / "data" / "vietnam_places.json"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from import_osm_places import checked_google_limit, enrich_with_google


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _needs_google(place: dict, *, refresh_existing: bool) -> bool:
    if refresh_existing:
        return True
    return not (
        place.get("google_place_id")
        and place.get("google_maps_url")
        and place.get("google_rating") is not None
        and place.get("google_user_rating_count") is not None
    )


def enrich_payload(
    payload: dict,
    api_key: str,
    *,
    limit: int,
    offset: int = 0,
    include_photos: bool = False,
    delay_seconds: float = 0.0,
    refresh_existing: bool = False,
) -> tuple[dict, dict]:
    places = payload.get("places")
    if not isinstance(places, list):
        raise SystemExit("places payload must contain a list at key 'places'")
    effective_limit = checked_google_limit(limit, len(places))
    selected_indexes = [
        index
        for index, place in enumerate(places[offset:], start=offset)
        if isinstance(place, dict) and _needs_google(place, refresh_existing=refresh_existing)
    ][:effective_limit]
    enriched_count = 0
    failed_count = 0
    for ordinal, index in enumerate(selected_indexes):
        original = places[index]
        try:
            enriched = enrich_with_google(
                original,
                api_key,
                include_photo=include_photos,
            )
        except Exception:
            failed_count += 1
            continue
        places[index] = enriched
        if enriched.get("google_place_id") and enriched.get("google_place_id") != original.get("google_place_id"):
            enriched_count += 1
        elif enriched.get("google_rating") is not None and original.get("google_rating") is None:
            enriched_count += 1
        if delay_seconds > 0 and ordinal < len(selected_indexes) - 1:
            time.sleep(delay_seconds)
    metadata = payload.setdefault("metadata", {})
    runs = metadata.setdefault("google_places_enrichment_runs", [])
    run = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "offset": offset,
        "requested_limit": limit,
        "applied_limit": effective_limit,
        "selected_count": len(selected_indexes),
        "enriched_count": enriched_count,
        "failed_count": failed_count,
        "include_photos": include_photos,
        "refresh_existing": refresh_existing,
        "source": "Google Places API Text Search",
    }
    if isinstance(runs, list):
        runs.append(run)
    metadata["google_places_latest_enrichment"] = run
    return payload, run


def main() -> int:
    _load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(
        description="Enrich an existing places.json catalogue with official Google Places API fields."
    )
    parser.add_argument("--places", type=Path, default=DEFAULT_PLACES)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--include-photos", action="store_true")
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GOOGLE_MAPS_API_KEY is required; refusing to run without an official provider key.")
    places_path = args.places if args.places.is_absolute() else ROOT / args.places
    if not places_path.exists():
        raise SystemExit(f"missing catalogue: {places_path}")
    payload = json.loads(places_path.read_text(encoding="utf-8"))
    updated, run = enrich_payload(
        payload,
        api_key,
        limit=args.limit,
        offset=args.offset,
        include_photos=args.include_photos,
        delay_seconds=args.delay,
        refresh_existing=args.refresh_existing,
    )
    if not args.no_backup:
        backup = places_path.with_suffix(places_path.suffix + f".{int(time.time())}.bak")
        shutil.copy2(places_path, backup)
    places_path.write_text(json.dumps(updated, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
