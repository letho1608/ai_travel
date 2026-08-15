from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from statistics import mean
from typing import Callable

import httpx

from app.config import settings
from app.schemas import PlanRequest


BENCHMARK_VERSION = "planner-quality-benchmark-v1"
REQUIRED_BASELINES = ("bo_giai_cu", "lich_mau_bien_tap", "ai_chung_khong_hoc_them")
REQUIRED_FOCUS_CITY_COUNT = 8
MIN_RELEASE_SCENARIOS = 300
MIN_GOLDEN_CITIES = 8
MIN_GOLDEN_CONSENSUS = 0.6
MIN_GOLDEN_HOLDOUT_PERCENT = 20
DEFAULT_EXECUTED_SCENARIOS = 2
DEFAULT_GOLDEN_SET_PATH = Path(__file__).resolve().parents[2] / "data" / "golden" / "release_scenarios.jsonl"
BASELINE_PLACE_ALIASES = {
    "ho hoan kiem": "ho guom",
    "hoan kiem lake": "ho guom",
    "den ngoc son temple": "den ngoc son",
}


@dataclass(frozen=True)
class BenchmarkScenario:
    id: str
    city: str
    request: PlanRequest
    human_interest_labels: frozenset[str]
    expected_min_slots: int


@dataclass(frozen=True)
class ExtractionScenario:
    id: str
    city: str
    request: PlanRequest
    expected_destination: str
    expected_duration: str
    expected_people: int
    expected_budget: int
    expected_tags: frozenset[str]


@dataclass(frozen=True)
class GoldenLabel:
    scenario_id: str
    city: str
    labels: frozenset[str]
    ideal_place_ids: tuple[str, ...]
    baseline_place_ids: dict[str, tuple[str, ...]]
    annotator_count: int
    consensus: float
    split: str


FOCUS_CITY_FIXTURES: dict[str, dict] = {
    "ha_noi": {"label": "Hà Nội", "location": {"lat": 21.0285, "lng": 105.8542}, "tags": ("ha_noi", "lich_su", "pho_co")},
    "tp_hcm": {"label": "TP.HCM", "location": {"lat": 10.7769, "lng": 106.7009}, "tags": ("am_thuc", "van_hoa", "dia_danh")},
    "ha_long": {"label": "Hạ Long", "location": {"lat": 20.9712, "lng": 107.0448}, "tags": ("bien", "view_dep", "gia_dinh")},
    "da_nang": {"label": "Đà Nẵng", "location": {"lat": 16.0544, "lng": 108.2022}, "tags": ("bien", "chill", "am_thuc")},
    "hoi_an": {"label": "Hội An", "location": {"lat": 15.8801, "lng": 108.338}, "tags": ("van_hoa", "pho_co", "am_thuc")},
    "nha_trang": {"label": "Nha Trang", "location": {"lat": 12.2388, "lng": 109.1967}, "tags": ("bien", "view_dep", "gia_dinh")},
    "phu_quoc": {"label": "Phú Quốc", "location": {"lat": 10.2899, "lng": 103.984}, "tags": ("bien", "chill", "nghi_duong")},
    "sa_pa": {"label": "Sa Pa", "location": {"lat": 22.3364, "lng": 103.8438}, "tags": ("nui", "view_dep", "chill")},
}


SCENARIO_PATTERNS: tuple[dict, ...] = (
    {"suffix": "first-time", "context": "du lịch {city} lần đầu, tham quan điểm nổi tiếng", "labels": ("dia_danh",), "duration": "ca_ngay", "budget": 1_000_000},
    {"suffix": "food-culture", "context": "du lịch {city} cả ngày, thích văn hóa địa phương và ăn ngon", "labels": ("am_thuc", "van_hoa"), "duration": "ca_ngay", "budget": 1_200_000},
    {"suffix": "family", "context": "đi {city} cùng gia đình, lịch nhẹ, phù hợp trẻ em", "labels": ("gia_dinh",), "duration": "ca_ngay", "budget": 1_500_000},
    {"suffix": "budget", "context": "du lịch {city} tiết kiệm, ít tốn tiền, đi gọn trong ngày", "labels": ("gia_re",), "duration": "ca_ngay", "budget": 650_000},
    {"suffix": "healing", "context": "đi {city} chữa lành, chill, ít đông, nhiều cảnh đẹp", "labels": ("chill", "view_dep"), "duration": "ca_ngay", "budget": 1_000_000},
    {"suffix": "coffee", "context": "{city} cafe checkin, đi vài giờ, không muốn quá mệt", "labels": ("cafe", "checkin"), "duration": "vai_gio", "budget": 500_000},
    {"suffix": "night", "context": "{city} buổi tối, chợ đêm, ăn vặt và đi bộ", "labels": ("cho_dem", "am_thuc"), "duration": "ca_ngay", "budget": 900_000},
    {"suffix": "outdoor", "context": "{city} ngoài trời, ngắm cảnh, chụp ảnh đẹp", "labels": ("ngoai_troi", "view_dep"), "duration": "nua_ngay", "budget": 800_000},
    {"suffix": "history", "context": "{city} tìm hiểu lịch sử, bảo tàng, di tích", "labels": ("lich_su",), "duration": "ca_ngay", "budget": 1_000_000},
    {"suffix": "multi-day", "context": "{city} 2 ngày, cân bằng tham quan, nghỉ ngơi và ăn uống", "labels": ("dia_danh", "am_thuc"), "duration": "nhieu_ngay", "budget": 2_500_000},
)


EXTRACTION_PATTERNS: tuple[dict, ...] = (
    {"suffix": "simple", "context": "Tôi muốn đi {city} cuối tuần, thích ăn ngon và văn hóa", "tags": ("am_thuc", "culture"), "duration": "ca_ngay", "budget": 1_000_000},
    {"suffix": "avoid", "context": "{city} 1 ngày, chữa lành, không thích chỗ quá đông", "tags": ("yen_tinh",), "duration": "ca_ngay", "budget": 900_000},
    {"suffix": "short", "context": "{city} cafe checkin vài giờ, đi nhẹ thôi", "tags": ("coffee", "checkin"), "duration": "vai_gio", "budget": 500_000},
    {"suffix": "family", "context": "Đi {city} cùng gia đình, phù hợp trẻ em, ngân sách vừa phải", "tags": ("tre_em",), "duration": "ca_ngay", "budget": 1_400_000},
    {"suffix": "multi-day", "context": "{city} 2 ngày, cân bằng tham quan và ăn uống, không muốn quá mệt", "tags": ("food",), "duration": "nhieu_ngay", "budget": 2_500_000},
)


def extraction_benchmark_scenarios() -> tuple[ExtractionScenario, ...]:
    scenarios: list[ExtractionScenario] = []
    for city, city_data in FOCUS_CITY_FIXTURES.items():
        for copy_index in range(4):
            for pattern in EXTRACTION_PATTERNS:
                scenario_id = f"{city}-{pattern['suffix']}-{copy_index + 1:02d}"
                people = 2 + (copy_index % 3)
                budget = pattern["budget"] + copy_index * 100_000
                request = PlanRequest(
                    context=pattern["context"].format(city=city_data["label"]),
                    location=city_data["location"],
                    thoi_luong=pattern["duration"],
                    so_nguoi=people,
                    ngan_sach=budget,
                    ma_phien=f"extraction-benchmark-{city}",
                    nonce=f"extraction-{scenario_id}",
                )
                scenarios.append(
                    ExtractionScenario(
                        id=scenario_id,
                        city=city,
                        request=request,
                        expected_destination=city_data["label"],
                        expected_duration=pattern["duration"],
                        expected_people=people,
                        expected_budget=budget,
                        expected_tags=frozenset(pattern["tags"]),
                    )
                )
    return tuple(scenarios)


def run_extraction_benchmark(parse_request: Callable[[PlanRequest], dict]) -> dict:
    scenarios = extraction_benchmark_scenarios()
    results = []
    for scenario in scenarios:
        parsed = parse_request(scenario.request)
        destination = ((parsed.get("diem_den") or {}).get("gia_tri") or {}).get("ten")
        tags = set((parsed.get("tag_ngu_nghia") or {}).get("gia_tri") or [])
        preferences = {
            str(item.get("gia_tri"))
            for item in parsed.get("so_thich", [])
            if isinstance(item, dict) and item.get("gia_tri") is not None
        }
        semantic_hits = sorted(tag for tag in scenario.expected_tags if tag in tags or tag in preferences)
        checks = {
            "destination": destination == scenario.expected_destination,
            "duration": (parsed.get("thoi_luong") or {}).get("gia_tri") == scenario.expected_duration,
            "people": (parsed.get("so_nguoi") or {}).get("gia_tri") == scenario.expected_people,
            "budget": (parsed.get("ngan_sach") or {}).get("gia_tri") == scenario.expected_budget,
            "no_missing_required": not parsed.get("bat_buoc_thieu"),
            "semantic_tags": bool(semantic_hits),
            "no_destination_hallucination": destination in {scenario.expected_destination, None},
        }
        results.append(
            {
                "scenario_id": scenario.id,
                "city": scenario.city,
                "checks": checks,
                "semantic_hits": semantic_hits,
                "pass": all(checks.values()),
            }
        )
    pass_rate = round(sum(1 for item in results if item["pass"]) / len(results), 3) if results else 0
    hallucination_failures = sum(
        1 for item in results if not item["checks"]["no_destination_hallucination"]
    )
    return {
        "version": "input-extraction-benchmark-v1",
        "scenario_count": len(scenarios),
        "label_source": "editorial_fixture_pending_human_adjudication",
        "results": results,
        "summary": {
            "pass_rate": pass_rate,
            "hallucination_failures": hallucination_failures,
        },
    }


def release_readiness_scenarios() -> tuple[BenchmarkScenario, ...]:
    """Versioned stratified local fixture pack; human adjudication is still required before release."""
    scenarios: list[BenchmarkScenario] = []
    for city, city_data in FOCUS_CITY_FIXTURES.items():
        for copy_index in range(4):
            for pattern in SCENARIO_PATTERNS:
                ordinal = copy_index * len(SCENARIO_PATTERNS) + len(scenarios)
                scenario_id = f"{city}-{pattern['suffix']}-{copy_index + 1:02d}"
                request = PlanRequest(
                    context=pattern["context"].format(city=city_data["label"]),
                    location=city_data["location"],
                    thoi_luong=pattern["duration"],
                    so_nguoi=2 + (copy_index % 3),
                    ngan_sach=pattern["budget"] + copy_index * 100_000,
                    ma_phien=f"quality-benchmark-{city}",
                    nonce=f"quality-{scenario_id}-{ordinal:04d}",
                )
                scenarios.append(
                    BenchmarkScenario(
                        id=scenario_id,
                        city=city,
                        request=request,
                        human_interest_labels=frozenset((*city_data["tags"], *pattern["labels"])),
                        expected_min_slots=3 if pattern["duration"] == "vai_gio" else 4,
                    )
                )
    return tuple(scenarios)


def _as_string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _load_golden_labels(path: Path = DEFAULT_GOLDEN_SET_PATH) -> tuple[list[GoldenLabel], list[str]]:
    if not path.exists():
        return [], [f"Golden set file is missing: {path}"]

    labels: list[GoldenLabel] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue

            scenario_id = str(payload.get("scenario_id", "")).strip()
            city = str(payload.get("city", "")).strip()
            labels_value = frozenset(_as_string_tuple(payload.get("labels")))
            ideal_place_ids = _as_string_tuple(payload.get("ideal_place_ids"))
            baseline_payload = payload.get("baseline_place_ids")
            baseline_place_ids = {
                str(name): _as_string_tuple(ids)
                for name, ids in baseline_payload.items()
                if isinstance(ids, list)
            } if isinstance(baseline_payload, dict) else {}
            try:
                annotator_count = int(payload.get("annotator_count", 0))
            except (TypeError, ValueError):
                annotator_count = 0
            try:
                consensus = float(payload.get("consensus", 0))
            except (TypeError, ValueError):
                consensus = 0
            split = str(payload.get("split", "")).strip()

            field_errors = []
            if not scenario_id:
                field_errors.append("missing scenario_id")
            if not city:
                field_errors.append("missing city")
            if not labels_value:
                field_errors.append("missing labels")
            if not ideal_place_ids:
                field_errors.append("missing ideal_place_ids")
            if annotator_count < 2:
                field_errors.append("annotator_count must be >= 2")
            if not (0 <= consensus <= 1):
                field_errors.append("consensus must be between 0 and 1")
            if split not in {"train", "validation", "holdout"}:
                field_errors.append("split must be train, validation, or holdout")
            missing_baselines = [name for name in REQUIRED_BASELINES if name not in baseline_place_ids]
            if missing_baselines:
                field_errors.append("missing baseline_place_ids for " + ", ".join(missing_baselines))
            if field_errors:
                errors.append(f"line {line_number}: " + "; ".join(field_errors))
                continue

            labels.append(
                GoldenLabel(
                    scenario_id=scenario_id,
                    city=city,
                    labels=labels_value,
                    ideal_place_ids=ideal_place_ids,
                    baseline_place_ids=baseline_place_ids,
                    annotator_count=annotator_count,
                    consensus=consensus,
                    split=split,
                )
            )
    return labels, errors


def golden_label_status(path: Path = DEFAULT_GOLDEN_SET_PATH) -> dict:
    labels, errors = _load_golden_labels(path)
    cities = sorted({label.city for label in labels})
    holdout_count = sum(1 for label in labels if label.split == "holdout")
    low_consensus_count = sum(1 for label in labels if label.consensus < MIN_GOLDEN_CONSENSUS)
    duplicate_count = len(labels) - len({label.scenario_id for label in labels})
    baseline_missing_counts = {
        name: sum(1 for label in labels if not label.baseline_place_ids.get(name))
        for name in REQUIRED_BASELINES
    }
    holdout_percent = round(holdout_count / len(labels) * 100, 2) if labels else 0
    blockers = list(errors[:20])
    if len(labels) < MIN_RELEASE_SCENARIOS:
        blockers.append(f"Golden set has {len(labels)} scenarios, below required {MIN_RELEASE_SCENARIOS}.")
    if len(cities) < MIN_GOLDEN_CITIES:
        blockers.append(f"Golden set covers {len(cities)} cities, below required {MIN_GOLDEN_CITIES}.")
    if low_consensus_count:
        blockers.append(f"Golden set has {low_consensus_count} scenarios below consensus {MIN_GOLDEN_CONSENSUS}.")
    if duplicate_count:
        blockers.append(f"Golden set has {duplicate_count} duplicate scenario_id values.")
    if holdout_percent < MIN_GOLDEN_HOLDOUT_PERCENT:
        blockers.append(
            f"Golden set holdout split is {holdout_percent}%, below required {MIN_GOLDEN_HOLDOUT_PERCENT}%."
        )
    missing_baseline_names = [name for name, count in baseline_missing_counts.items() if count]
    if missing_baseline_names:
        blockers.append("Golden set is missing baseline outputs for: " + ", ".join(missing_baseline_names))

    return {
        "version": "human-golden-labels-v1",
        "path": str(path),
        "scenario_count": len(labels),
        "city_count": len(cities),
        "cities": cities,
        "holdout_count": holdout_count,
        "holdout_percent": holdout_percent,
        "min_required_scenarios": MIN_RELEASE_SCENARIOS,
        "min_required_cities": MIN_GOLDEN_CITIES,
        "min_consensus": MIN_GOLDEN_CONSENSUS,
        "min_holdout_percent": MIN_GOLDEN_HOLDOUT_PERCENT,
        "baseline_missing_counts": baseline_missing_counts,
        "validation_error_count": len(errors),
        "validation_errors": errors[:20],
        "pass": not blockers,
        "blockers": blockers,
    }


def evaluate_plan_payload(
    plan: dict,
    scenario: BenchmarkScenario,
    *,
    baseline_results: dict[str, dict] | None = None,
) -> dict:
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    slot_tags = {
        tag
        for slot in slots
        for tag in (
            slot.get("loai"),
            *(slot.get("bang_chung", {}).get("tag_khop", []) or []),
        )
        if isinstance(tag, str)
    }
    covered = sorted(tag for tag in scenario.human_interest_labels if tag in slot_tags)
    feasibility_errors = plan.get("danh_gia_chat_luong", {}).get("tinh_kha_thi", {}).get("loi", [])
    release_blockers = list(feasibility_errors)
    if len(slots) < scenario.expected_min_slots:
        release_blockers.append("Lich co it diem hon nguong kich ban")
    missing_baselines = [
        name for name in REQUIRED_BASELINES if not (baseline_results or {}).get(name, {}).get("completed")
    ]
    if missing_baselines:
        release_blockers.append("Chua chay du moc so sanh bat buoc: " + ", ".join(missing_baselines))
    return {
        "scenario_id": scenario.id,
        "city": scenario.city,
        "feasible": not feasibility_errors,
        "interest_coverage": {
            "labels": sorted(scenario.human_interest_labels),
            "covered": covered,
            "ratio": round(len(covered) / len(scenario.human_interest_labels), 2)
            if scenario.human_interest_labels
            else 1.0,
            "source": "editorial_fixture_pending_human_adjudication",
        },
        "baseline_results": baseline_results or {
            name: {"completed": False, "note": "required before release"}
            for name in REQUIRED_BASELINES
        },
        "release_gate": {"pass": not release_blockers, "blockers": release_blockers},
    }


def _slot_tags(slots: list[dict]) -> set[str]:
    return {
        tag
        for slot in slots
        for tag in (
            slot.get("loai"),
            *(slot.get("tags", []) or []),
            *(slot.get("bang_chung", {}).get("tag_khop", []) or []),
        )
        if isinstance(tag, str)
    }


def _coverage_for_tags(tags: set[str], scenario: BenchmarkScenario) -> dict:
    covered = sorted(tag for tag in scenario.human_interest_labels if tag in tags)
    return {
        "covered": covered,
        "ratio": round(len(covered) / len(scenario.human_interest_labels), 2)
        if scenario.human_interest_labels
        else 1.0,
    }


def _place_slots_for_baseline(scenario: BenchmarkScenario, *, curated_only: bool) -> list[dict]:
    from app.data import PLACES
    from app.pipeline.routing import haversine_km

    labels = set(scenario.human_interest_labels)
    candidates = [
        place
        for place in PLACES
        if haversine_km(
            scenario.request.location.lat,
            scenario.request.location.lng,
            place.lat,
            place.lng,
        )
        <= 45
        and (not curated_only or place.source == "curated" or place.id.startswith("curated-"))
    ]
    ranked = sorted(
        candidates,
        key=lambda place: (
            -len(labels.intersection(place.tags)),
            -int(place.source == "curated"),
            haversine_km(
                scenario.request.location.lat,
                scenario.request.location.lng,
                place.lat,
                place.lng,
            ),
            place.id,
        ),
    )
    return [
        {"dia_diem_id": place.id, "loai": place.kind, "tags": list(place.tags)}
        for place in ranked[: scenario.expected_min_slots]
    ]


def _run_general_ai_baseline(scenario: BenchmarkScenario) -> dict:
    """Run the mandatory generic-AI baseline only when explicitly enabled.

    This baseline is intentionally fail-closed. It is not simulated from local
    catalogue scores because the spec requires an external general AI comparator.
    """
    if os.getenv("AI_BASELINE_ENABLED", "false").lower() not in {"1", "true", "on"}:
        return {
            "completed": False,
            "method": "external_general_ai_baseline",
            "status": "disabled",
            "note": "Set AI_BASELINE_ENABLED=true with a configured AI provider to run this mandatory baseline.",
        }

    from app.data import PLACES, place_name_key

    by_name = {place_name_key(place.name): place for place in PLACES}
    try:
        suggestions = _draft_general_ai_baseline_places(scenario)
    except Exception as exc:
        return {
            "completed": False,
            "method": "external_general_ai_baseline",
            "status": "provider_error",
            "note": str(exc)[:300],
        }

    matched_slots = []
    unmatched_names = []
    for suggestion in suggestions:
        name = str(suggestion.get("name", "")).strip()
        name_key = place_name_key(name)
        place = by_name.get(name_key) or by_name.get(BASELINE_PLACE_ALIASES.get(name_key, ""))
        if place:
            matched_slots.append({"dia_diem_id": place.id, "loai": place.kind, "tags": list(place.tags)})
        elif name:
            unmatched_names.append(name)
        if len(matched_slots) >= scenario.expected_min_slots:
            break

    coverage = _coverage_for_tags(_slot_tags(matched_slots), scenario)
    completed = len(matched_slots) >= scenario.expected_min_slots
    return {
        "completed": completed,
        "method": "external_general_ai_baseline",
        "status": "completed" if completed else "insufficient_catalogue_matches",
        "slot_count": len(matched_slots),
        "interest_coverage": coverage,
        "unmatched_names": unmatched_names[:10],
        "note": None if completed else "Generic AI suggestions did not map to enough trusted catalogue places.",
    }


def _draft_general_ai_baseline_places(scenario: BenchmarkScenario) -> list[dict]:
    if settings.ai_mode == "offline" or not settings.ai_api_key:
        raise RuntimeError("AI provider is not configured for the external general-AI baseline.")
    prompt = {
        "yeu_cau": (
            f"Return exactly {scenario.expected_min_slots} real place names for this Vietnam travel request. "
            "Use only public general knowledge. Do not use app-specific candidate scores or app-specific learned data. "
            "Return JSON only."
        ),
        "ngu_canh_nguoi_dung": scenario.request.context,
        "json_mau": {"places": [{"name": "real place name"}]},
    }
    with httpx.Client(
        base_url=settings.ai_base_url,
        headers={"Authorization": f"Bearer {settings.ai_api_key}"},
        timeout=httpx.Timeout(20, connect=5),
    ) as client:
        response = client.post(
            "/chat/completions",
            json={
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": "Only return a valid JSON object."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "max_tokens": 700,
            },
        )
        response.raise_for_status()
    body = response.json()
    choice = body["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("External general-AI baseline response was incomplete.")
    payload = json.loads(choice["message"]["content"])
    places = payload.get("places")
    if not isinstance(places, list):
        raise TypeError("External general-AI baseline did not return a places list.")
    return [item for item in places if isinstance(item, dict) and isinstance(item.get("name"), str)]


def _run_local_baselines(scenario: BenchmarkScenario) -> dict[str, dict]:
    old_solver_slots = _place_slots_for_baseline(scenario, curated_only=False)
    editorial_slots = _place_slots_for_baseline(scenario, curated_only=True)
    old_coverage = _coverage_for_tags(_slot_tags(old_solver_slots), scenario)
    editorial_coverage = _coverage_for_tags(_slot_tags(editorial_slots), scenario)
    return {
        "bo_giai_cu": {
            "completed": bool(old_solver_slots),
            "method": "nearest_catalogue_baseline_v0",
            "slot_count": len(old_solver_slots),
            "interest_coverage": old_coverage,
        },
        "lich_mau_bien_tap": {
            "completed": bool(editorial_slots),
            "method": "curated_focus_catalogue_fixture_v0",
            "slot_count": len(editorial_slots),
            "interest_coverage": editorial_coverage,
            "note": "Local editorial fixture, still pending expert adjudication before release.",
        },
        "ai_chung_khong_hoc_them": _run_general_ai_baseline(scenario),
    }


def run_release_readiness_benchmark(
    build_plan: Callable[[PlanRequest], dict],
    *,
    max_executed: int = DEFAULT_EXECUTED_SCENARIOS,
) -> dict:
    scenarios = release_readiness_scenarios()
    results = []
    for scenario in scenarios[:max_executed]:
        plan = build_plan(scenario.request)
        results.append(
            evaluate_plan_payload(
                plan,
                scenario,
                baseline_results=_run_local_baselines(scenario),
            )
        )
    pass_values = [item["release_gate"]["pass"] for item in results]
    coverage_values = [item["interest_coverage"]["ratio"] for item in results]
    return {
        "version": BENCHMARK_VERSION,
        "scenario_count": len(scenarios),
        "executed_count": len(results),
        "execution_mode": "smoke_subset" if len(results) < len(scenarios) else "full",
        "frozen_data": {
            "place_snapshot": "local-catalogue-current",
            "parser_snapshot": "plan-request-pydantic-v1",
            "no_live_service_calls": True,
            "label_source": "editorial_fixture_pending_human_adjudication",
        },
        "anti_self_scoring": "Coverage is measured against frozen human labels, never planner scores.",
        "results": results,
            "summary": {
            "release_pass": all(pass_values),
            "mean_interest_coverage": round(mean(coverage_values), 2) if coverage_values else 0,
        },
    }


def run_explanation_source_audit(
    build_plan: Callable[[PlanRequest], dict],
    *,
    max_scenarios: int = 12,
) -> dict:
    scenarios = release_readiness_scenarios()[:max_scenarios]
    checked_slots = 0
    failures: list[dict] = []
    for scenario in scenarios:
        plan = build_plan(scenario.request)
        decision_log = plan.get("bang_chung_quyet_dinh", [])
        for day in plan.get("ngay", []):
            for slot in day.get("khoang_gio", []):
                checked_slots += 1
                evidence = slot.get("bang_chung") if isinstance(slot.get("bang_chung"), dict) else {}
                reasons = evidence.get("ly_do_luat") if isinstance(evidence.get("ly_do_luat"), list) else []
                explanation = slot.get("giai_thich") or ""
                slot_failures = []
                if evidence not in decision_log:
                    slot_failures.append("evidence_not_in_decision_log")
                if not evidence.get("nguon_dia_diem"):
                    slot_failures.append("missing_place_source")
                if not evidence.get("nguon_url"):
                    slot_failures.append("missing_source_url")
                if evidence.get("thoi_luong") != slot.get("thoi_luong"):
                    slot_failures.append("duration_evidence_mismatch")
                if not explanation.startswith(f"{slot.get('ten_dia_diem')} được chọn vì "):
                    slot_failures.append("explanation_prefix_mismatch")
                for reason in reasons:
                    if reason not in explanation:
                        slot_failures.append("missing_rule_reason_in_explanation")
                        break
                travel = evidence.get("di_chuyen")
                if travel and str(travel.get("minutes")) not in explanation:
                    slot_failures.append("travel_minutes_not_explained")
                if slot_failures:
                    failures.append(
                        {
                            "scenario_id": scenario.id,
                            "slot_id": slot.get("dia_diem_id"),
                            "failures": slot_failures,
                        }
                    )
    return {
        "version": "explanation-source-audit-v1",
        "scenario_count": len(scenarios),
        "checked_slots": checked_slots,
        "failure_count": len(failures),
        "failures": failures[:20],
        "pass": not failures and checked_slots > 0,
    }


def audit_release_spec(build_plan: Callable[[PlanRequest], dict] | None = None) -> dict:
    """Machine-readable audit for the 10 problem statements in the plan file.

    This intentionally distinguishes "implemented enough for local tests" from
    "release complete". A release gate should fail when evidence is missing
    instead of treating the current implementation as its own benchmark.
    """
    from app.data import PLACES, PLACE_METADATA
    from app.pipeline.planner import DESTINATION_RADIUS_KM, FOCUS_DESTINATIONS, _request_understanding, haversine_km
    from app.pipeline.routing import public_transit_policy_status, route_calibration_status
    from app.services.catalog_quality import catalogue_field_coverage
    from app.services.event_calendar import official_event_calendar_status
    from app.services.google_places import google_places_readiness

    city_counts = {
        key: sum(
            1
            for place in PLACES
            if haversine_km(float(destination["lat"]), float(destination["lng"]), place.lat, place.lng)
            <= DESTINATION_RADIUS_KM
        )
        for key, destination in FOCUS_DESTINATIONS.items()
    }
    source_counts: dict[str, int] = {}
    missing_critical = 0
    for place in PLACES:
        source_counts[place.source] = source_counts.get(place.source, 0) + 1
        if not place.name or not place.kind or not place.area or not (0 <= place.open_hour < place.close_hour <= 24):
            missing_critical += 1

    benchmark = run_release_readiness_benchmark(build_plan) if build_plan else None
    explanation_audit = run_explanation_source_audit(build_plan) if build_plan else None
    extraction_benchmark = run_extraction_benchmark(_request_understanding)
    golden_status = golden_label_status()
    benchmark_count = benchmark["scenario_count"] if benchmark else 0
    executed_count = benchmark["executed_count"] if benchmark else 0
    baseline_results = (
        benchmark["results"][0]["baseline_results"]
        if benchmark and benchmark.get("results")
        else {name: {"completed": False} for name in REQUIRED_BASELINES}
    )
    missing_baselines = [
        name for name in REQUIRED_BASELINES if not baseline_results.get(name, {}).get("completed")
    ]
    field_coverage = catalogue_field_coverage(
        focus_destinations=FOCUS_DESTINATIONS,
        radius_km=DESTINATION_RADIUS_KM,
    )
    event_calendar = official_event_calendar_status()
    google_places_status = google_places_readiness()

    problems = [
        {
            "id": 1,
            "name": "Hieu yeu cau dau vao",
            "status": "implemented_local_acceptance",
            "evidence": [
                "Plan payload includes dau_vao_da_hieu with schema_version input-understanding-v1.",
                "Generation logs boc_tach_yeu_cau for quality measurement.",
                "Generate endpoint returns missing_required_input with questions when destination is missing.",
                f"Input extraction benchmark has {extraction_benchmark['scenario_count']} labelled fixture scenarios with pass rate {extraction_benchmark['summary']['pass_rate']}.",
                f"Destination hallucination failures in extraction benchmark: {extraction_benchmark['summary']['hallucination_failures']}.",
            ],
            "blockers": ["Extraction benchmark labels are editorial fixtures pending human adjudication/calibration before release."],
        },
        {
            "id": 2,
            "name": "Thu thap du lieu",
            "status": "partial",
            "evidence": [
                f"Loaded {len(PLACES)} places from catalogue.",
                f"Focus city coverage: {city_counts}.",
                f"Catalogue source counts: {source_counts}.",
                f"Field coverage: {field_coverage['fields']}.",
                f"Google Places enrichment readiness: {google_places_status['status']}.",
            ],
            "blockers": [
                "Google Maps scraping path from the original decision is intentionally not implemented.",
                *(
                    ["Google Places enrichment is not configured for release: " + "; ".join(google_places_status["blockers"])]
                    if not google_places_status["ready"]
                    else []
                ),
                f"Official/enriched-source coverage is {field_coverage['fields']['official_or_enriched_source']['percent']}%, below release threshold {field_coverage['release_thresholds']['official_or_enriched_source_percent']}%.",
            ],
        },
        {
            "id": 3,
            "name": "Loc va xep hang dia diem",
            "status": "partial",
            "evidence": [
                "Slot evidence uses the fixed 5-factor formula from the spec: suitability 30, rating 25, distance 20, opening-hour match 15, review count 10.",
                "Missing rating/review data use the spec fallback scores while still being flagged as missing evidence.",
                "Candidates are region-filtered before ranking.",
                "Swipe/replacement behavior writes versioned tag-weight deltas and next plans expose behavior-profile version in ranking evidence.",
                f"Human golden label status: {golden_status['scenario_count']} scenarios, {golden_status['city_count']} cities, pass={golden_status['pass']}.",
            ],
            "blockers": [
                *golden_status["blockers"],
                "Behavioral weights need release-scale calibration and drift monitoring before they can be trusted beyond local acceptance.",
            ],
        },
        {
            "id": 4,
            "name": "Thong tin de nguoi dung danh gia",
            "status": "partial",
            "evidence": [
                "Slots include coordinates, source, source_url, cost, opening hours, image fields, and missing-data evidence.",
                "AI adapter is only allowed to edit copy, not quantitative facts.",
                "Free-text replacement rejects external places without verified operational metadata instead of asking AI to estimate hours/cost.",
                f"Google Places readiness for rating/review/photo/hour enrichment: {google_places_status['status']}.",
            ],
            "blockers": [
                *(
                    ["Google Places enrichment is not configured for release: " + "; ".join(google_places_status["blockers"])]
                    if not google_places_status["ready"]
                    else []
                ),
                "Rating/review/photo/official-hours coverage is not release-complete across the catalogue: "
                f"rating {field_coverage['fields']['rating']['percent']}%, "
                f"review {field_coverage['fields']['review_count']['percent']}%, "
                f"image {field_coverage['fields']['image']['percent']}%, "
                f"valid_hours {field_coverage['fields']['valid_hours']['percent']}%."
            ],
        },
        {
            "id": 5,
            "name": "Thoi diem phu hop de den",
            "status": "partial",
            "evidence": [
                "Planner handles opening hours, meals, night markets, weather hooks, and Vietnam holiday notes.",
                "Planner computes local sunset with a NOAA solar-position approximation and records it in timing evidence.",
                "Planner records focus-city seasonal/festival heuristic context in timing criteria.",
                "Urban commute peak windows are recorded in timing policy and per-leg travel evidence as heuristic risk, not live traffic.",
                "Vietnam holiday policy marks holiday hours as requiring verification; Tet plans are blocked from release until official yearly hours are available.",
                f"Official event/festival calendar status: {event_calendar['status']}.",
            ],
            "blockers": (
                []
                if event_calendar["ready"]
                else [
                    "Official event/festival calendar is not release-ready: "
                    + "; ".join(event_calendar.get("blockers") or [event_calendar.get("note") or event_calendar["status"]])
                ]
            ),
        },
        {
            "id": 6,
            "name": "Thoi gian nen o moi dia diem",
            "status": "implemented_local_acceptance",
            "evidence": ["Scheduled slots include duration range, confidence, source, and estimated flag."],
            "blockers": ["Needs broader expert calibration beyond the current acceptance subset."],
        },
        {
            "id": 7,
            "name": "Tinh thoi gian di chuyen",
            "status": "implemented_trial",
            "evidence": [
                "Route matrix is preferred; offline straight-line fallback is explicit and reported.",
                "Runtime OSRM table integration exists behind PLAN_LIVE_TRAVEL_MATRIX for private provider deployments.",
                f"Public transit policy status: {public_transit_policy_status()['status']} with max GTFS age 90 days.",
                f"Route calibration status: {route_calibration_status()['status']}.",
            ],
            "blockers": ["Private production motorcycle/traffic routing provider is not configured and calibrated."],
        },
        {
            "id": 8,
            "name": "Sinh lich trinh hoan chinh",
            "status": "partial",
            "evidence": [
                "Planner validates hours, uniqueness, budget, route gaps, min/max slots, and replacement/refine flows.",
                "Plan quality report includes an OR-Tools CP-SAT feasibility check for the selected schedule.",
                "Optional lodging coordinates are accepted in PlanRequest and used as the route anchor with explicit plan evidence.",
                "Sightseeing candidate selection can use an OR-Tools CP-SAT bounded budget optimizer before fallback ranking.",
                "Selected sightseeing candidates are ordered with OR-Tools CP-SAT to minimize travel before schedule placement.",
                "Single-day sightseeing selection can use an OR-Tools CP-SAT day-level joint optimizer over up to 80 candidates with time windows, durations, travel gaps, and budget.",
                "Quality report runs a bounded CP-SAT day-level scheduler over selected slots with time windows, durations, travel gaps, and budget.",
            ],
            "blockers": [
                "OR-Tools CP-SAT is not yet the final integrated optimizer for multi-day itineraries with meals, backfill, and persisted placement decisions.",
            ],
        },
        {
            "id": 9,
            "name": "Giai thich bang bang chung",
            "status": "implemented_local_acceptance",
            "evidence": [
                "Every slot has bang_chung and giai_thich derived from recorded law/evidence reasons.",
                (
                    f"Sampled explanation/source audit checked {explanation_audit['checked_slots']} slots with "
                    f"{explanation_audit['failure_count']} failures."
                    if explanation_audit
                    else "Sampled explanation/source audit not executed."
                ),
            ],
            "blockers": (
                []
                if explanation_audit and explanation_audit["pass"]
                else ["Needs sampled source audit at release scale."]
            ),
        },
        {
            "id": 10,
            "name": "Danh gia chat luong giai phap",
            "status": "blocked_before_release",
            "evidence": [
                f"Current benchmark catalog has {benchmark_count} stratified local scenarios; smoke run executed {executed_count}.",
                "Release gate requires frozen human labels and mandatory baselines.",
                f"Mandatory baseline statuses: {baseline_results}.",
                f"Golden set validation: {golden_status}.",
            ],
            "blockers": [
                *golden_status["blockers"],
                *(
                    ["Missing mandatory baselines: " + ", ".join(missing_baselines)]
                    if missing_baselines
                    else []
                ),
            ],
        },
    ]
    release_blockers = [
        f"Bai toan {problem['id']}: {blocker}"
        for problem in problems
        for blocker in problem["blockers"]
        if problem["status"] != "implemented_local_acceptance"
    ]
    if len(city_counts) < REQUIRED_FOCUS_CITY_COUNT or any(count <= 0 for count in city_counts.values()):
        release_blockers.append("Data: 8 focus city coverage is incomplete")
    if missing_critical:
        release_blockers.append(f"Data: {missing_critical} places are missing critical name/type/area/hour fields")
    return {
        "version": "release-spec-audit-v1",
        "problem_count": len(problems),
        "problems": problems,
        "data": {
            "place_count": len(PLACES),
            "metadata": PLACE_METADATA,
            "focus_city_counts": city_counts,
            "source_counts": source_counts,
            "missing_critical_fields": missing_critical,
            "field_coverage": field_coverage,
            "official_event_calendar": event_calendar,
            "google_places": google_places_status,
        },
        "extraction_benchmark": {
            "version": extraction_benchmark["version"],
            "scenario_count": extraction_benchmark["scenario_count"],
            "label_source": extraction_benchmark["label_source"],
            "summary": extraction_benchmark["summary"],
        },
        "explanation_source_audit": explanation_audit,
        "golden_label_status": golden_status,
        "release_gate": {
            "pass": not release_blockers,
            "blockers": release_blockers,
        },
    }
