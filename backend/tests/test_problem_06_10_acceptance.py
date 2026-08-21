from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from app.data import PLACES, Place, place_name_key
from app.pipeline import planner, routing
from app.pipeline.planner import build_plan, validate_plan
from app.schemas import PlanRequest
from app.services.quality_benchmarks import (
    REQUIRED_BASELINES,
    BenchmarkScenario,
    _run_general_ai_baseline,
    audit_release_spec,
    evaluate_plan_payload,
    golden_label_status,
    release_readiness_scenarios,
    run_explanation_source_audit,
    run_extraction_benchmark,
    run_release_readiness_benchmark,
)
from app.services import event_calendar


def base_request(**updates) -> PlanRequest:
    payload = {
        "context": "du lịch Hà Nội cả ngày, văn hóa lịch sử, phố cổ, ăn ngon",
        "location": {"lat": 21.0285, "lng": 105.8542},
        "thoi_luong": "ca_ngay",
        "so_nguoi": 2,
        "ngan_sach": 1_000_000,
        "ma_phien": "acceptance-session",
        "nonce": "acceptance-0610-0001",
    }
    payload.update(updates)
    return PlanRequest(**payload)


def all_slots(plan: dict) -> list[dict]:
    return [slot for day in plan["ngay"] for slot in day["khoang_gio"]]


def test_problem_06_duration_priority_uses_guidance_then_structured_fallback():
    guided_place = next(
        place
        for place in PLACES
        if (tip := planner._guidance(place)) and tip.duration_min
    )
    guided_tip = planner._guidance(guided_place)
    guided = planner._duration_estimate_for(guided_place, None, planned_minutes=guided_tip.duration_min)

    assert guided["nguon"] == guided_tip.source
    assert guided["do_tin_cay"] == "high"
    assert guided["uoc_luong"] is False
    assert guided["toi_thieu_phut"] <= guided["ke_hoach_phut"] <= guided["toi_da_phut"]

    missing_duration = Place(
        "acceptance-museum-no-duration",
        "Acceptance Museum Without Guidance",
        "bao_tang",
        "Ha Noi",
        guided_place.lat,
        guided_place.lng,
        0,
        0,
        ("museum",),
        8,
        17,
        "OpenStreetMap",
    )
    fallback = planner._duration_estimate_for(missing_duration, None)

    assert fallback["nguon"] == "fallback_by_place_kind"
    assert fallback["do_tin_cay"] == "low"
    assert fallback["uoc_luong"] is True
    assert (fallback["toi_thieu_phut"], fallback["toi_da_phut"]) == (90, 180)
    assert "AI khong tu sinh thoi luong" in fallback["ghi_chu"]


def test_problem_06_every_scheduled_duration_has_source_or_estimate_flag():
    plan = build_plan(base_request(nonce="acceptance-duration-plan-0001"))

    for slot in all_slots(plan):
        duration = slot["thoi_luong"]
        assert duration["nguon"]
        assert isinstance(duration["uoc_luong"], bool)
        assert duration["toi_thieu_phut"] <= duration["ke_hoach_phut"] <= duration["toi_da_phut"]
        assert slot["bang_chung"]["thoi_luong"] == duration


def test_problem_07_route_matrix_is_used_before_offline_straight_line_fallback():
    by_id = {place.id: place for place in PLACES}
    matrix_pair = next(
        (
            (source_id, target_id, minutes)
            for (source_id, target_id), minutes in routing.TRAVEL_MINUTES.items()
            if source_id in by_id and target_id in by_id and source_id != target_id
        ),
        None,
    )
    if matrix_pair is None:
        pytest.skip("local route matrix has no pair matching the current catalogue")

    source_id, target_id, matrix_minutes = matrix_pair
    matrix_estimate = routing.estimate_travel(by_id[source_id], by_id[target_id])

    assert matrix_estimate.source == "route_matrix"
    assert matrix_estimate.status == "matrix_available"
    assert matrix_estimate.formula == "precomputed_osrm_or_postgres_duration_seconds"
    assert matrix_estimate.minutes == matrix_minutes
    assert routing.travel_minutes(by_id[source_id], by_id[target_id]) == matrix_minutes

    unknown_a = replace(by_id[source_id], id="acceptance-unmapped-a")
    unknown_b = replace(by_id[target_id], id="acceptance-unmapped-b")
    fallback = routing.estimate_travel(unknown_a, unknown_b, mode="walk")

    assert fallback.source == "offline_straight_line_fallback"
    assert fallback.status == "fallback_missing_route_matrix_pair"
    assert "haversine_km" in fallback.formula
    assert fallback.mode == "walk"
    assert fallback.minutes >= 5


def test_problem_07_live_osrm_table_adapter_is_opt_in_and_validated(monkeypatch):
    places = [
        Place("live-a", "A", "dia_danh", "Hà Nội", 21.0, 105.8, 0, 8, 18, ("view_dep",), "OpenStreetMap"),
        Place("live-b", "B", "dia_danh", "Hà Nội", 21.01, 105.81, 0, 8, 18, ("view_dep",), "OpenStreetMap"),
    ]

    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            plan_live_travel_matrix=False,
            plan_live_travel_matrix_max_places=25,
            osrm_base_url="https://routing.example",
        ),
    )
    disabled = routing.fetch_live_travel_matrix(places)
    assert disabled.status == "disabled"
    assert disabled.matrix == {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": "Ok", "durations": [[0, 600], [720, 0]]}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, params):
            assert "/table/v1/driving/" in url
            assert params == {"annotations": "duration"}
            return Response()

    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            plan_live_travel_matrix=True,
            plan_live_travel_matrix_max_places=25,
            osrm_base_url="https://routing.example",
        ),
    )
    monkeypatch.setattr(routing.httpx, "Client", Client)

    live = routing.fetch_live_travel_matrix(places)

    assert live.status == "live"
    assert live.matrix[("live-a", "live-b")].source == "live_osrm_table"
    assert live.matrix[("live-a", "live-b")].minutes == 10

    monkeypatch.setattr(Response, "json", lambda self: {"code": "Ok", "durations": [[0]]})
    invalid = routing.fetch_live_travel_matrix(places)
    assert invalid.status == "invalid_provider_payload"
    assert invalid.matrix == {}


def test_problem_07_public_transit_gtfs_policy_fails_closed(monkeypatch):
    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            public_transit_enabled=True,
            gtfs_feed_date="2018-01-01",
        ),
    )
    stale = routing.public_transit_policy_status()
    assert stale["status"] == "blocked_stale_gtfs_feed"
    assert stale["max_feed_age_days"] == 90

    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            public_transit_enabled=True,
            gtfs_feed_date=None,
        ),
    )
    missing = routing.public_transit_policy_status()
    assert missing["status"] == "blocked_missing_gtfs_feed_date"


def test_problem_07_route_calibration_policy_fails_closed_and_validates_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            route_calibration_file=None,
            route_calibration_min_samples=20,
            route_calibration_max_mape_percent=35,
        ),
    )
    missing = routing.route_calibration_status()
    assert missing["status"] == "missing_calibration_file"

    report = tmp_path / "route_calibration.json"
    report.write_text(json.dumps({"summary": {"sample_count": 10, "mape_percent": 20}}), encoding="utf-8")
    monkeypatch.setattr(
        routing,
        "settings",
        SimpleNamespace(
            route_calibration_file=str(report),
            route_calibration_min_samples=20,
            route_calibration_max_mape_percent=35,
        ),
    )
    insufficient = routing.route_calibration_status()
    assert insufficient["status"] == "insufficient_samples"

    report.write_text(json.dumps({"summary": {"sample_count": 25, "mape_percent": 50}}), encoding="utf-8")
    failed = routing.route_calibration_status()
    assert failed["status"] == "failed_error_threshold"

    report.write_text(json.dumps({"summary": {"sample_count": 25, "mape_percent": 18}}), encoding="utf-8")
    ready = routing.route_calibration_status()
    assert ready["status"] == "ready"
    assert ready["sample_count"] == 25


def test_problem_07_plan_exposes_travel_table_and_each_leg_keeps_gap():
    plan = build_plan(base_request(nonce="acceptance-route-table-0001"))
    by_id = {place.id: place for place in PLACES}

    travel_table = plan["bang_thoi_gian_di_chuyen"]
    assert travel_table["trang_thai"] == "matrix_or_offline_estimate"
    assert travel_table["ma_tran"]
    assert travel_table["ma_tran"]["_metadata"]["public_transit_policy"]["status"] in {
        "disabled",
        "blocked_missing_gtfs_feed_date",
        "blocked_invalid_gtfs_feed_date",
        "blocked_stale_gtfs_feed",
        "ready",
    }
    assert travel_table["ma_tran"]["_metadata"]["route_calibration"]["status"] in {
        "missing_calibration_file",
        "invalid_calibration_file",
        "insufficient_samples",
        "failed_error_threshold",
        "ready",
    }

    for day in plan["ngay"]:
        previous_slot = None
        previous_place = None
        for slot in day["khoang_gio"]:
            place = by_id[slot["dia_diem_id"]]
            if previous_slot and previous_place:
                previous_end = planner._parse_slot_clock(previous_slot["ket_thuc"])
                current_start = planner._parse_slot_clock(slot["bat_dau"])
                assert current_start - previous_end >= routing.travel_minutes(previous_place, place)
                assert slot["di_chuyen_tu_diem_truoc"]["minutes"] == routing.travel_minutes(previous_place, place)
            previous_slot = slot
            previous_place = place


def test_problem_08_solver_output_respects_hours_uniqueness_budget_and_day_size():
    request = base_request(ngan_sach=300_000, nonce="acceptance-solver-constraints-0001")
    plan = build_plan(request)
    slots = all_slots(plan)
    by_id = {place.id: place for place in PLACES}

    assert validate_plan(plan, {slot["dia_diem_id"] for slot in slots}, request) == []
    assert plan["chi_phi_moi_nguoi"] <= request.ngan_sach
    assert len({slot["dia_diem_id"] for slot in slots}) == len(slots)

    for slot in slots:
        place = by_id[slot["dia_diem_id"]]
        open_hour, close_hour = planner._effective_hours(place)
        assert f"{open_hour:02d}:00" <= slot["bat_dau"]
        assert slot["ket_thuc"] <= f"{close_hour:02d}:00"
        assert "ngan_sach" in slot["bang_chung"]["rang_buoc_da_ap"]
        assert "thoi_gian_di_chuyen" in slot["bang_chung"]["rang_buoc_da_ap"]


def test_problem_08_validator_rejects_budget_and_travel_constraint_violations():
    request = base_request(
        context="du lịch Hà Nội cả ngày, văn hóa lịch sử, phố cổ, ăn ngon, ngân sách 1000000 đồng",
        nonce="acceptance-validator-negative-0001",
    )
    plan = build_plan(request)
    slots = all_slots(plan)
    trusted_ids = {slot["dia_diem_id"] for slot in slots}

    over_budget = dict(plan)
    over_budget["chi_phi_moi_nguoi"] = request.ngan_sach + 1
    assert "Kế hoạch vượt ngân sách" in validate_plan(over_budget, trusted_ids, request)

    if len(plan["ngay"][0]["khoang_gio"]) >= 2:
        impossible_travel = {
            **plan,
            "ngay": [
                {
                    **plan["ngay"][0],
                    "khoang_gio": [dict(slot) for slot in plan["ngay"][0]["khoang_gio"]],
                }
            ],
        }
        impossible_travel["ngay"][0]["khoang_gio"][1]["bat_dau"] = impossible_travel["ngay"][0]["khoang_gio"][0]["ket_thuc"]
        errors = validate_plan(impossible_travel, trusted_ids, request)
        assert any("Không đủ thời gian di chuyển" in error for error in errors)


def test_problem_09_explanations_are_derived_from_evidence_log_only():
    plan = build_plan(base_request(nonce="acceptance-explanation-evidence-0001"))

    assert len(plan["bang_chung_quyet_dinh"]) == len(all_slots(plan))
    for slot in all_slots(plan):
        evidence = slot["bang_chung"]
        assert evidence in plan["bang_chung_quyet_dinh"]
        assert evidence["lay_luc"]
        assert evidence["nguon_dia_diem"]
        assert evidence["thoi_luong"] == slot["thoi_luong"]
        assert slot["giai_thich"].startswith(f"{slot['ten_dia_diem']} được chọn vì ")
        for reason in evidence["ly_do_luat"]:
            assert reason in slot["giai_thich"]
        if evidence["di_chuyen"]:
            assert str(evidence["di_chuyen"]["minutes"]) in slot["giai_thich"]


def test_problem_09_data_staleness_policy_has_explicit_limits_for_each_evidence_type():
    plan = build_plan(base_request(nonce="acceptance-staleness-policy-0001"))
    policy = plan["chinh_sach_do_cu_du_lieu"]

    for key in ("gio_mo_cua", "gia", "trang_thai_hoat_dong", "thoi_luong", "di_chuyen"):
        assert key in policy
        assert policy[key]["max_age_days"] > 0
        assert policy[key]["refresh"]


def test_problem_09_sampled_explanation_source_audit_passes():
    audit = run_explanation_source_audit(build_plan, max_scenarios=4)

    assert audit["version"] == "explanation-source-audit-v1"
    assert audit["scenario_count"] == 4
    assert audit["checked_slots"] > 0
    assert audit["failure_count"] == 0
    assert audit["pass"] is True


def test_problem_10_release_gate_blocks_missing_baselines_and_empty_itineraries():
    request = base_request(nonce="acceptance-quality-negative-0001")
    scenario = BenchmarkScenario(
        id="acceptance-empty-plan",
        city="ha_noi",
        request=request,
        human_interest_labels=frozenset({"pho_co"}),
        expected_min_slots=4,
    )
    empty_plan = {"ngay": [{"khoang_gio": []}], "danh_gia_chat_luong": {"tinh_kha_thi": {"loi": []}}}

    result = evaluate_plan_payload(empty_plan, scenario)

    assert result["release_gate"]["pass"] is False
    assert "Lich co it diem hon nguong kich ban" in result["release_gate"]["blockers"]
    assert any("Chua chay du moc so sanh bat buoc" in blocker for blocker in result["release_gate"]["blockers"])
    assert set(result["baseline_results"]) == set(REQUIRED_BASELINES)
    assert result["interest_coverage"]["source"] == "editorial_fixture_pending_human_adjudication"


def test_problem_10_scenario_catalog_is_stratified_across_focus_cities():
    scenarios = release_readiness_scenarios()
    cities = {scenario.city for scenario in scenarios}

    assert len(scenarios) >= 300
    assert len(cities) >= 8
    for city in cities:
        assert sum(1 for scenario in scenarios if scenario.city == city) >= 40
    assert all(scenario.request.nonce for scenario in scenarios)
    assert all(scenario.human_interest_labels for scenario in scenarios)


def test_problem_10_release_readiness_report_runs_and_does_not_self_score():
    report = run_release_readiness_benchmark(build_plan)

    assert report["version"] == "planner-quality-benchmark-v1"
    assert report["scenario_count"] >= 300
    assert report["executed_count"] == 2
    assert report["execution_mode"] == "smoke_subset"
    assert report["frozen_data"]["no_live_service_calls"] is True
    assert report["frozen_data"]["label_source"] == "editorial_fixture_pending_human_adjudication"
    assert "never planner scores" in report["anti_self_scoring"]
    assert 0 <= report["summary"]["mean_interest_coverage"] <= 1
    assert report["summary"]["release_pass"] is False
    for result in report["results"]:
        assert set(result["baseline_results"]) == set(REQUIRED_BASELINES)
        assert result["baseline_results"]["bo_giai_cu"]["completed"] is True
        assert result["baseline_results"]["lich_mau_bien_tap"]["completed"] is True
        assert result["baseline_results"]["ai_chung_khong_hoc_them"]["completed"] is False


def test_problem_10_general_ai_baseline_is_fail_closed_when_disabled(monkeypatch):
    monkeypatch.delenv("AI_BASELINE_ENABLED", raising=False)
    scenario = release_readiness_scenarios()[0]

    baseline = _run_general_ai_baseline(scenario)

    assert baseline["completed"] is False
    assert baseline["status"] == "disabled"
    assert baseline["method"] == "external_general_ai_baseline"


def test_problem_10_general_ai_baseline_maps_only_trusted_catalogue_places(monkeypatch):
    scenario = release_readiness_scenarios()[0]
    trusted_places = []
    seen_names = set()
    for place in PLACES:
        name_key = place_name_key(place.name)
        if name_key not in seen_names:
            trusted_places.append(place)
            seen_names.add(name_key)
        if len(trusted_places) == scenario.expected_min_slots:
            break

    class Adapter:
        def draft_itinerary_places(self, context, count, locale="vi"):
            return [{"name": place.name} for place in trusted_places] + [{"name": "Invented Place"}]

    monkeypatch.setenv("AI_BASELINE_ENABLED", "true")
    monkeypatch.setattr(
        "app.services.quality_benchmarks._draft_general_ai_baseline_places",
        lambda scenario: Adapter().draft_itinerary_places(scenario.request.context, scenario.expected_min_slots),
    )

    baseline = _run_general_ai_baseline(scenario)

    assert baseline["completed"] is True
    assert baseline["status"] == "completed"
    assert baseline["slot_count"] == scenario.expected_min_slots
    assert "Invented Place" not in baseline["unmatched_names"]


def test_problem_10_general_ai_baseline_maps_hanoi_landmark_alias(monkeypatch):
    scenario = release_readiness_scenarios()[0]

    monkeypatch.setenv("AI_BASELINE_ENABLED", "true")
    monkeypatch.setattr(
        "app.services.quality_benchmarks._draft_general_ai_baseline_places",
        lambda scenario: [
            {"name": "Hồ Hoàn Kiếm"},
            {"name": "Đền Ngọc Sơn"},
            {"name": "Lăng Chủ tịch Hồ Chí Minh"},
            {"name": "Phố cổ Hà Nội"},
        ],
    )

    baseline = _run_general_ai_baseline(scenario)

    assert baseline["completed"] is True
    assert baseline["slot_count"] == scenario.expected_min_slots
    assert baseline["unmatched_names"] == []


def test_problem_01_extraction_benchmark_has_100_to_300_labelled_vietnamese_cases():
    report = run_extraction_benchmark(planner._request_understanding)

    assert report["version"] == "input-extraction-benchmark-v1"
    assert 100 <= report["scenario_count"] <= 300
    assert report["label_source"] == "editorial_fixture_pending_human_adjudication"
    assert report["summary"]["hallucination_failures"] == 0
    assert report["summary"]["pass_rate"] >= 0.95


def test_release_spec_audit_reports_all_problem_blockers_and_data_counts():
    audit = audit_release_spec(build_plan)

    assert audit["version"] == "release-spec-audit-v1"
    assert audit["problem_count"] == 10
    assert {problem["id"] for problem in audit["problems"]} == set(range(1, 11))
    assert audit["data"]["place_count"] >= 30_000
    assert audit["data"]["field_coverage"]["place_count"] == audit["data"]["place_count"]
    assert audit["golden_label_status"]["version"] == "human-golden-labels-v1"
    assert audit["golden_label_status"]["pass"] is False
    assert audit["golden_label_status"]["scenario_count"] < 300
    assert audit["extraction_benchmark"]["scenario_count"] >= 100
    assert audit["extraction_benchmark"]["summary"]["hallucination_failures"] == 0
    for field in ("source_url", "image", "valid_hours", "rating", "review_count", "official_or_enriched_source"):
        assert field in audit["data"]["field_coverage"]["fields"]
        assert 0 <= audit["data"]["field_coverage"]["fields"][field]["percent"] <= 100
    source_quality_counts = audit["data"]["field_coverage"]["source_quality_counts"]
    assert sum(source_quality_counts.values()) == audit["data"]["place_count"]
    assert source_quality_counts["openstreetmap_source"] > source_quality_counts["official_website"]
    assert source_quality_counts["official_website"] > 0
    assert source_quality_counts["curated_editorial_source"] > 0
    google_fields = audit["data"]["field_coverage"]["google_places_fields"]
    assert {"place_id", "maps_url"} <= set(google_fields)
    assert 0 <= google_fields["place_id"]["percent"] <= 100
    assert 0 <= google_fields["maps_url"]["percent"] <= 100
    google_readiness = audit["data"]["google_places"]
    assert google_readiness["status"] in {"ready", "missing_or_invalid_configuration"}
    assert "api_key_configured" in google_readiness
    assert "api_key_length" in google_readiness
    assert "api_key_value" not in google_readiness
    assert len(audit["data"]["focus_city_counts"]) >= 8
    assert all(count > 0 for count in audit["data"]["focus_city_counts"].values())
    focus_coverage = audit["data"]["field_coverage"]["focus_city_field_coverage"]
    assert set(audit["data"]["focus_city_counts"]).issubset(focus_coverage)
    for city_key, city_quality in focus_coverage.items():
        assert sum(city_quality["source_quality_counts"].values()) == city_quality["place_count"]
        assert 0 <= city_quality["official_or_enriched_source_percent"] <= 100
    assert audit["release_gate"]["pass"] is False
    blockers = "\n".join(audit["release_gate"]["blockers"])
    assert "Needs 100-200 labelled Vietnamese extraction benchmark" not in blockers
    assert "Bai toan 9: Needs sampled source audit" not in blockers
    assert audit["explanation_source_audit"]["pass"] is True
    assert "OR-Tools CP-SAT is not yet the final integrated optimizer for multi-day itineraries" in blockers
    assert "Missing mandatory baselines: ai_chung_khong_hoc_them" in blockers
    assert "Golden set" in blockers


def test_release_spec_audit_does_not_emit_empty_missing_baseline_blocker(monkeypatch):
    trusted_places = []
    seen_names = set()
    for place in PLACES:
        name_key = place_name_key(place.name)
        if name_key not in seen_names:
            trusted_places.append(place)
            seen_names.add(name_key)
        if len(trusted_places) == 10:
            break

    class Adapter:
        def draft_itinerary_places(self, context, count, locale="vi"):
            return [{"name": place.name} for place in trusted_places[:count]]

    monkeypatch.setenv("AI_BASELINE_ENABLED", "true")
    monkeypatch.setattr(
        "app.services.quality_benchmarks._draft_general_ai_baseline_places",
        lambda scenario: Adapter().draft_itinerary_places(scenario.request.context, scenario.expected_min_slots),
    )

    audit = audit_release_spec(build_plan)
    blockers = "\n".join(audit["release_gate"]["blockers"])

    assert "Missing mandatory baselines:" not in blockers
    assert "Golden set" in blockers


def test_problem_10_golden_label_status_is_fail_closed_for_missing_file(tmp_path):
    missing = tmp_path / "release_scenarios.jsonl"

    status = golden_label_status(missing)

    assert status["pass"] is False
    assert status["scenario_count"] == 0
    assert any("missing" in blocker.lower() for blocker in status["blockers"])


def test_problem_10_golden_label_status_validates_schema_and_baselines(tmp_path):
    path = tmp_path / "release_scenarios.jsonl"
    path.write_text(
        json.dumps(
            {
                "scenario_id": "bad-001",
                "city": "ha_noi",
                "labels": ["lich_su"],
                "ideal_place_ids": ["p1"],
                "baseline_place_ids": {"bo_giai_cu": ["p1"]},
                "annotator_count": 1,
                "consensus": 0.5,
                "split": "dev",
            }
        ),
        encoding="utf-8",
    )

    status = golden_label_status(path)

    assert status["pass"] is False
    assert status["validation_error_count"] == 1
    assert "annotator_count" in status["validation_errors"][0]
    assert "missing baseline_place_ids" in status["validation_errors"][0]


def test_problem_10_golden_label_status_accepts_release_scale_file(tmp_path):
    path = tmp_path / "release_scenarios.jsonl"
    cities = ("ha_noi", "tp_hcm", "ha_long", "da_nang", "hoi_an", "nha_trang", "phu_quoc", "sa_pa")
    rows = []
    for index in range(300):
        city = cities[index % len(cities)]
        split = "holdout" if index < 60 else "train"
        rows.append(
            json.dumps(
                {
                    "scenario_id": f"{city}-golden-{index:03d}",
                    "city": city,
                    "labels": ["dia_danh", city],
                    "ideal_place_ids": [f"{city}-ideal-{index}"],
                    "baseline_place_ids": {
                        "bo_giai_cu": [f"{city}-old-{index}"],
                        "lich_mau_bien_tap": [f"{city}-editorial-{index}"],
                        "ai_chung_khong_hoc_them": [f"{city}-general-ai-{index}"],
                    },
                    "annotator_count": 3,
                    "consensus": 0.75,
                    "split": split,
                }
            )
        )
    path.write_text("\n".join(rows), encoding="utf-8")

    status = golden_label_status(path)

    assert status["pass"] is True
    assert status["scenario_count"] == 300
    assert status["city_count"] == 8
    assert status["holdout_percent"] == 20
    assert status["baseline_missing_counts"] == {name: 0 for name in REQUIRED_BASELINES}


def test_problem_05_official_event_calendar_status_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        event_calendar,
        "settings",
        replace(
            event_calendar.settings,
            app_env="production",
            event_calendar_file=None,
            event_calendar_min_cities=8,
            event_calendar_min_events=24,
        ),
    )
    missing = event_calendar.official_event_calendar_status()
    assert missing["ready"] is False
    assert missing["status"] == "missing_event_calendar_file"

    stale_path = tmp_path / "events.json"
    stale_path.write_text(
        json.dumps(
            {
                "generated_at": "2020-01-01",
                "cities": {
                    f"city_{index}": [
                        {
                            "name": f"Festival {index}",
                            "start_date": "2020-02-01",
                            "source_url": f"https://example.com/{index}",
                        }
                    ]
                    for index in range(8)
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        event_calendar,
        "settings",
        replace(
            event_calendar.settings,
            app_env="production",
            event_calendar_file=str(stale_path),
            event_calendar_max_age_days=90,
            event_calendar_min_cities=8,
            event_calendar_min_events=8,
        ),
    )
    stale = event_calendar.official_event_calendar_status()
    assert stale["ready"] is False
    assert stale["status"] == "stale_event_calendar_file"


def test_problem_05_official_event_calendar_status_accepts_fresh_release_data(tmp_path, monkeypatch):
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-15",
                "source": "official-tourism-board-fixture",
                "cities": {
                    f"city_{city_index}": [
                        {
                            "name": f"Festival {city_index}-{event_index}",
                            "start_date": "2026-09-01",
                            "source_url": f"https://example.com/{city_index}/{event_index}",
                        }
                        for event_index in range(3)
                    ]
                    for city_index in range(8)
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        event_calendar,
        "settings",
        replace(
            event_calendar.settings,
            app_env="production",
            event_calendar_file=str(path),
            event_calendar_max_age_days=90,
            event_calendar_min_cities=8,
            event_calendar_min_events=24,
        ),
    )

    status = event_calendar.official_event_calendar_status()

    assert status["ready"] is True
    assert status["status"] == "ready"
    assert status["city_count"] == 8
    assert status["event_count"] == 24
    assert status["blockers"] == []


def test_problem_08_quality_report_includes_cp_sat_feasibility_check():
    plan = build_plan(base_request(nonce="acceptance-cp-sat-quality-0001"))
    cp_sat = plan["danh_gia_chat_luong"]["bo_giai_cp_sat"]
    cp_sat_day = plan["danh_gia_chat_luong"]["bo_giai_cp_sat_ngay"]

    assert cp_sat["thu_vien"] == "ortools.sat.python.cp_model"
    assert cp_sat["co_san"] is True
    assert cp_sat["hop_le"] is True
    assert cp_sat["so_slot_kiem_tra"] == len(all_slots(plan))
    assert plan["bo_giai_chon_ung_vien"]["phuong_phap"] in {
        "ortools_cp_sat_day_joint_selection",
        "ortools_cp_sat_selection",
        "llm_catalog_guarded",
        "fallback_ranked_budget",
    }
    if plan["bo_giai_chon_ung_vien"]["phuong_phap"] == "ortools_cp_sat_day_joint_selection":
        assert plan["bo_giai_chon_ung_vien"]["gioi_han_ung_vien"] == 80
        assert "time_window" in plan["bo_giai_chon_ung_vien"]["vai_tro"]
        assert plan["bo_giai_chon_ung_vien"]["suggested_starts"]
    if plan["bo_giai_chon_ung_vien"]["phuong_phap"] == "ortools_cp_sat_selection":
        assert plan["bo_giai_chon_ung_vien"]["sap_thu_tu"]["phuong_phap"] == "ortools_cp_sat_order"
    assert cp_sat_day["thu_vien"] == "ortools.sat.python.cp_model"
    assert cp_sat_day["ket_qua"]
    assert cp_sat_day["tat_ca_hop_le"] is True
    assert "time_window" in cp_sat_day["vai_tro"]
