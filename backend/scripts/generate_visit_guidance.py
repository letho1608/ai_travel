"""Generate reusable visit-time guidance for Hanoi places.

Default mode is free and deterministic: it creates conservative heuristics from
catalog tags/opening hours. Add --with-llm to ask a configured chat-completion
provider to summarize better visit windows, then validates the JSON before
writing backend/data/visit_guidance.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data import DATA_DIR, PLACES, Place  # noqa: E402
from app.text_utils import ascii_fold  # noqa: E402


DEFAULT_OUTPUT = DATA_DIR / "visit_guidance.json"
PROJECT_ROOT = ROOT.parent


def load_env_files() -> None:
    """Load simple KEY=VALUE pairs from .env files without printing secrets."""
    for path in (PROJECT_ROOT / ".env", ROOT / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")


def name_key(value: str) -> str:
    return " ".join(ascii_fold(value).split())


def heuristic_window(place: Place) -> dict[str, Any]:
    tags = set(place.tags)
    if {"cho_dem", "night_market"}.intersection(tags) or "chợ đêm" in place.name.lower():
        preferred = [19, 0, 21, 30]
        tip = "Nên đi sau 19h để đúng không khí chợ đêm; tránh xếp vào buổi sáng."
    elif place.kind in {"cong_vien", "dia_danh"} and {
        "ngoai_troi",
        "view_dep",
        "checkin",
    }.intersection(tags):
        preferred = [7, 0, 10, 30]
        tip = (
            "Ưu tiên sáng sớm hoặc chiều mát; "
            "tránh ngoài trời giữa trưa khi nóng hoặc mưa."
        )
    elif place.kind == "bao_tang" or {"trong_nha", "museum", "van_hoa"}.intersection(tags):
        preferred = [9, 0, 15, 30]
        tip = (
            "Phù hợp khung giờ ban ngày, "
            "đặc biệt khi thời tiết xấu hoặc trời quá nóng."
        )
    elif place.kind in {"nha_hang", "quan_an"}:
        preferred = [11, 30, 13, 30]
        tip = "Phù hợp quanh giờ ăn; có thể chuyển sang buổi tối nếu lịch trình cần."
    elif place.kind == "cafe":
        preferred = [9, 0, 11, 0]
        tip = "Phù hợp đầu ngày hoặc làm điểm nghỉ giữa hành trình."
    else:
        preferred = [max(place.open_hour, 8), 0, min(place.close_hour, 17), 0]
        tip = "Dùng khung giờ an toàn theo giờ mở cửa catalog."
    if preferred[0] < place.open_hour:
        preferred[0], preferred[1] = place.open_hour, 0
    if preferred[2] > place.close_hour:
        preferred[2], preferred[3] = place.close_hour, 0
    if preferred[0] * 60 + preferred[1] >= preferred[2] * 60 + preferred[3]:
        preferred = [place.open_hour, 0, place.close_hour, 0]
    return {
        "id": place.id,
        "name": place.name,
        "name_key": name_key(place.name),
        "open_hour": place.open_hour,
        "close_hour": place.close_hour,
        "preferred": preferred,
        "alt_preferred": [15, 0, 17, 30] if "ngoai_troi" in tags and preferred[2] <= 11 else None,
        "duration_min": place.duration_min,
        "tip": tip,
        "source": "heuristic-generator",
    }


def load_existing_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def merge_items(
    existing: list[dict[str, Any]],
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {
        str(item["id"]): item
        for item in existing
        if isinstance(item.get("id"), str)
    }
    for item in new_items:
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            merged_by_id[item_id] = item
    catalog_order = {place.id: index for index, place in enumerate(PLACES)}
    return sorted(
        merged_by_id.values(),
        key=lambda item: catalog_order.get(str(item.get("id")), len(catalog_order)),
    )


def extract_llm_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "places", "guidance", "results", "visit_guidance"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def prompt_for(places: list[Place]) -> dict[str, Any]:
    return {
        "task": (
            "For each real Hanoi place, return practical visit guidance as JSON only. "
            "Prefer cooler outdoor windows, morning-only official sites, museum hours, "
            "food mealtimes, and night markets after 18:00. Do not invent new places."
        ),
        "schema": {
            "items": [
                {
                    "id": "catalog id",
                    "preferred": [8, 0, 10, 30],
                    "alt_preferred": [15, 0, 17, 30],
                    "duration_min": 60,
                    "tip": "short Vietnamese reason",
                    "source": "LLM synthesis",
                }
            ]
        },
        "places": [
            {
                "id": place.id,
                "name": place.name,
                "kind": place.kind,
                "area": place.area,
                "tags": list(place.tags),
                "open_hour": place.open_hour,
                "close_hour": place.close_hour,
                "duration_min": place.duration_min,
            }
            for place in places
        ],
    }


def call_llm(places: list[Place]) -> list[dict[str, Any]]:
    import httpx

    load_env_files()
    api_key = (
        os.getenv("LLM_VISIT_GUIDANCE_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("API_KEY_DEEPSEEK")
    )
    if not api_key:
        raise SystemExit(
            "Set OPENROUTER_API_KEY or LLM_VISIT_GUIDANCE_API_KEY before --with-llm."
        )
    base_url = os.getenv("LLM_VISIT_GUIDANCE_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("LLM_VISIT_GUIDANCE_MODEL", "openrouter/free")
    if "openrouter.ai" in base_url and model != "openrouter/free" and not model.endswith(":free"):
        raise SystemExit(
            "OpenRouter is configured, but the model is not free. "
            "Use LLM_VISIT_GUIDANCE_MODEL=openrouter/free or a model ending with :free."
        )
    with httpx.Client(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": os.getenv("NEXT_PUBLIC_BASE_URL", "http://localhost:3000"),
            "X-Title": "Minh Di Dau The",
        },
        timeout=httpx.Timeout(45, connect=5),
    ) as client:
        response = client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Only return one valid JSON object."},
                    {"role": "user", "content": json.dumps(prompt_for(places), ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_tokens": 4000,
            },
        )
        response.raise_for_status()
        body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise SystemExit("LLM response was truncated; reduce --limit or batch size.")
        payload = json.loads(choice["message"]["content"])
        items = extract_llm_items(payload)
        if not items:
            raise ValueError("LLM did not return a usable items array.")
        by_id = {place.id: place for place in places}
        merged = []
        for item in items:
            if not isinstance(item, dict) or item.get("id") not in by_id:
                continue
            fallback = heuristic_window(by_id[item["id"]])
            fallback.update(
                {
                    key: item[key]
                    for key in ("preferred", "alt_preferred", "duration_min", "tip", "source")
                    if key in item
                }
            )
            merged.append(fallback)
        return merged


def generate_items(places: list[Place], *, with_llm: bool, batch_size: int) -> list[dict[str, Any]]:
    if not with_llm:
        return [heuristic_window(place) for place in places]
    items: list[dict[str, Any]] = []
    safe_batch_size = max(1, min(batch_size, 25))
    for start in range(0, len(places), safe_batch_size):
        batch = places[start : start + safe_batch_size]
        try:
            batch_items = call_llm(batch)
        except Exception as exc:
            print(
                f"Skipped batch {start // safe_batch_size + 1}: {exc}",
                flush=True,
            )
            continue
        items.extend(batch_items)
        print(
            f"Generated {len(batch_items)}/{len(batch)} records "
            f"for batch {start // safe_batch_size + 1}",
            flush=True,
        )
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of places per LLM request. Smaller batches are safer for free models.",
    )
    parser.add_argument("--with-llm", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Keep existing records and only generate guidance for places not already present.",
    )
    args = parser.parse_args()
    limit = max(1, min(args.limit, 200))
    existing_items = load_existing_items(args.output)
    existing_ids = {
        str(item["id"])
        for item in existing_items
        if isinstance(item.get("id"), str)
    }
    candidates = [
        place
        for place in PLACES
        if not args.skip_existing or place.id not in existing_ids
    ]
    places = candidates[:limit]
    if args.skip_existing and not places:
        print(
            f"No new places to generate; kept {len(existing_items)} existing records "
            f"in {args.output}"
        )
        return
    items = generate_items(places, with_llm=args.with_llm, batch_size=args.batch_size)
    output_items = merge_items(existing_items, items) if args.skip_existing else items
    payload = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": "llm" if args.with_llm else "heuristic",
            "place_count": len(output_items),
            "generated_this_run": len(items),
            "skip_existing": args.skip_existing,
            "note": "Planner loads this file at startup as supplemental visit-time guidance.",
        },
        "items": output_items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(output_items)} visit-guidance records to {args.output} "
        f"({len(items)} generated this run)"
    )


if __name__ == "__main__":
    main()
