"""Build a real OSRM distance matrix for selected imported places."""

import argparse
import json
import urllib.request

import datetime as _dt

if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--places", type=Path, default=Path("data/places.json"))
    parser.add_argument("--output", type=Path, default=Path("data/distance_matrix.json"))
    parser.add_argument("--osrm-url", default="https://router.project-osrm.org")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    source = json.loads(args.places.read_text(encoding="utf-8"))
    eligible = [p for p in source["places"] if p.get("opening_hours_raw")]
    if len(eligible) < args.limit:
        eligible.extend(p for p in source["places"] if p not in eligible)
    places = eligible[: args.limit]
    if len(places) < 4:
        raise SystemExit("Need at least four imported places")
    coords = ";".join(f"{place['lng']},{place['lat']}" for place in places)
    url = f"{args.osrm_url.rstrip('/')}/table/v1/driving/{coords}?annotations=duration,distance"
    request = urllib.request.Request(url, headers={"User-Agent": "minh-di-dau-the/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        matrix = json.load(response)
    if matrix.get("code") != "Ok":
        raise SystemExit(f"OSRM error: {matrix.get('code')}")
    now = datetime.now(UTC).isoformat()
    output = {
        "metadata": {
            "provider": "OSRM",
            "profile": "driving",
            "base_url": args.osrm_url,
            "generated_at": now,
            "place_count": len(places),
            "source_places_fetched_at": source["metadata"]["fetched_at"],
        },
        "place_ids": [place["id"] for place in places],
        "durations_seconds": matrix["durations"],
        "distances_meters": matrix["distances"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(places)}x{len(places)} matrix to {args.output}")


if __name__ == "__main__":
    main()

