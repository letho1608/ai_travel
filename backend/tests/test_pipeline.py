from dataclasses import replace

from app.data import PLACES
from app.pipeline import planner
from app.pipeline.planner import COPY, build_plan, validate_plan
from app.schemas import PlanRequest, UserPreferencesRequest
from app.services.weather import WEATHER_COPY


def request() -> PlanRequest:
    return PlanRequest(context="cuối tuần chill và ăn ngon", location={"lat": 21.0285, "lng": 105.8542}, thoi_luong="ca_ngay", so_nguoi=2, ngan_sach=1_000_000, ma_phien="test-session")


def test_plan_has_one_valid_route_with_trusted_places():
    plan = build_plan(request())
    slots = plan["ngay"][0]["khoang_gio"]
    assert 4 <= len(slots) <= 10
    assert len({slot["dia_diem_id"] for slot in slots}) == len(slots)
    assert validate_plan(plan, {slot["dia_diem_id"] for slot in slots}) == []


def test_validator_rejects_hallucinated_place():
    plan = build_plan(request())
    plan["ngay"][0]["khoang_gio"][0]["dia_diem_id"] = "fake"
    assert "Có địa điểm ngoài danh sách tin cậy" in validate_plan(plan, set())


def test_all_duration_modes_are_supported():
    for duration in ("vai_gio", "nua_ngay", "ca_ngay", "nhieu_ngay"):
        payload = request().model_copy(update={"thoi_luong": duration})
        plan = build_plan(payload)
        slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
        assert 4 <= len(slots) <= 10
        assert len(plan["ngay"]) == (2 if duration == "nhieu_ngay" else 1)


def test_plan_never_exceeds_per_person_budget():
    payload = request().model_copy(update={"ngan_sach": 250_000})
    plan = build_plan(payload)
    assert plan["chi_phi_moi_nguoi"] <= 250_000


def test_same_intent_can_generate_different_routes_with_new_nonce():
    first = request().model_copy(
        update={"context": "cà phê và đi bộ cuối tuần", "nonce": "nonce-variety-0001"}
    )
    second = request().model_copy(
        update={"context": "cà phê và đi bộ cuối tuần", "nonce": "nonce-variety-0002"}
    )
    first_ids = [slot["dia_diem_id"] for day in build_plan(first)["ngay"] for slot in day["khoang_gio"]]
    second_ids = [slot["dia_diem_id"] for day in build_plan(second)["ngay"] for slot in day["khoang_gio"]]
    assert first_ids != second_ids


def test_context_intent_changes_candidate_mix():
    coffee_plan = build_plan(
        request().model_copy(update={"context": "cà phê chill có view đẹp", "nonce": "nonce-coffee-0001"})
    )
    culture_plan = build_plan(
        request().model_copy(update={"context": "văn hóa bảo tàng lịch sử", "nonce": "nonce-culture-0001"})
    )
    coffee_kinds = {
        slot["loai"] for day in coffee_plan["ngay"] for slot in day["khoang_gio"]
    }
    culture_kinds = {
        slot["loai"] for day in culture_plan["ngay"] for slot in day["khoang_gio"]
    }
    assert "cafe" in coffee_kinds
    assert {"bao_tang", "dia_danh"}.intersection(culture_kinds)


def test_deterministic_plan_has_richer_slot_descriptions():
    plan = build_plan(
        request().model_copy(update={"context": "du lịch Hà Nội có phố cổ, cafe và ăn ngon"})
    )
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    assert all(len(slot["mo_ta"]) >= 120 for slot in slots)
    assert any("Đi chậm" in slot["mo_ta"] or "Dành thời gian" in slot["mo_ta"] for slot in slots)


def test_hanoi_tourism_intent_includes_iconic_highlights():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội lần đầu, tham quan điểm nổi tiếng",
                "nonce": "nonce-hanoi-icons-0001",
            }
        )
    )
    place_names = {
        slot["ten_dia_diem"] for day in plan["ngay"] for slot in day["khoang_gio"]
    }
    assert {"Hồ Gươm", "Hồ Tây", "Lăng Chủ tịch Hồ Chí Minh", "Phố cổ Hà Nội"} <= place_names


def test_hanoi_evening_intent_includes_old_quarter_night_stops():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày và buổi tối, phố cổ, chợ đêm",
                "nonce": "nonce-hanoi-night-0001",
            }
        )
    )
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    place_names = {slot["ten_dia_diem"] for slot in slots}
    assert "Phố cổ Hà Nội" in place_names
    assert {"Chợ đêm Hàng Đào – Đồng Xuân", "Phố Tạ Hiện"}.intersection(place_names)
    assert any(slot["bat_dau"] >= "17:00" for slot in slots)


def test_curated_old_quarter_streets_are_available():
    expected = {
        "Hàng Đào", "Hàng Gai", "Hàng Bạc", "Hàng Mã", "Hàng Đường",
        "Hàng Ngang", "Hàng Buồm", "Hàng Dầu", "Hàng Khay", "Hàng Trống",
    }
    streets = {place.name: place for place in planner.PLACES if place.name in expected}
    assert set(streets) == expected
    assert all("pho_co" in place.tags and place.source == "curated" for place in streets.values())


def test_planner_uses_ai_to_select_places_before_scheduling(monkeypatch):
    class SelectingAI:
        def propose_place_ids(self, context, candidates, count, locale):
            assert context
            assert locale == "vi"
            ids = [item["id"] for item in candidates]
            preferred = [
                place_id
                for place_id in ("curated-ho-tay", "curated-lang-bac", "curated-ho-guom")
                if place_id in ids
            ]
            return [*preferred, *[place_id for place_id in ids if place_id not in preferred]][:count]

        def assemble(self, draft, trusted_ids, locale):
            return draft

    monkeypatch.setattr(planner, "ai_adapter", SelectingAI())
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội lần đầu",
                "nonce": "nonce-ai-select-0001",
            }
        )
    )
    place_ids = {
        slot["dia_diem_id"] for day in plan["ngay"] for slot in day["khoang_gio"]
    }
    assert {"curated-ho-tay", "curated-lang-bac", "curated-ho-guom"} <= place_ids


def test_planner_can_use_llm_first_places_after_osm_verification(monkeypatch):
    class DraftingAI:
        def draft_itinerary_places(self, context, count, locale):
            return [
                {"name": "LLM Verified Stop", "kind": "dia_danh", "why": "fresh idea"},
                {"name": "Hồ Gươm", "kind": "dia_danh", "why": "icon"},
                {"name": "Hồ Tây", "kind": "dia_danh", "why": "icon"},
                {"name": "Lăng Chủ tịch Hồ Chí Minh", "kind": "dia_danh", "why": "icon"},
                {"name": "Cà phê phố cổ", "kind": "cafe", "why": "break"},
            ][:count]

        def propose_place_ids(self, context, candidates, count, locale):
            raise AssertionError("planner should try LLM-first before whitelist selection")

        def assemble(self, draft, trusted_ids, locale):
            return draft

    verified = planner.Place(
        "verified-llm-stop",
        "LLM Verified Stop",
        "dia_danh",
        "Hà Nội",
        21.03,
        105.85,
        0,
        45,
        ("osm_verified",),
        7,
        22,
        "Nominatim",
        None,
    )

    def fake_verify(name, origin):
        if name == "LLM Verified Stop":
            return verified
        return next((place for place in planner.PLACES if place.name == name), None)

    monkeypatch.setattr(planner, "ai_adapter", DraftingAI())
    monkeypatch.setattr(planner, "verify_place_name", fake_verify)
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội thật chi tiết",
                "nonce": "nonce-llm-first-0001",
            }
        )
    )
    place_names = {
        slot["ten_dia_diem"] for day in plan["ngay"] for slot in day["khoang_gio"]
    }
    assert "LLM Verified Stop" in place_names


def test_llm_first_details_are_used_in_slot_copy(monkeypatch):
    class DraftingAI:
        def draft_itinerary_places(self, context, count, locale):
            return [
                {
                    "name": "LLM Verified Stop",
                    "kind": "dia_danh",
                    "why": "Start here because it gives the trip a clear story.",
                    "activity": "Spend time on the main walk, photo spot, and nearby side streets.",
                    "tip": "Go before the busiest window.",
                    "meal": "Try a nearby street snack.",
                    "transport": "Walk to the next Old Quarter stop.",
                },
                {"name": "Hồ Gươm", "kind": "dia_danh", "why": "icon"},
                {"name": "Hồ Tây", "kind": "dia_danh", "why": "icon"},
                {"name": "Lăng Chủ tịch Hồ Chí Minh", "kind": "dia_danh", "why": "icon"},
                {"name": "Cà phê phố cổ", "kind": "cafe", "why": "break"},
                {"name": "Phố cổ Hà Nội", "kind": "dia_danh", "why": "evening walk"},
                {"name": "Phố Tạ Hiện", "kind": "dia_danh", "why": "nightlife"},
            ][:count]

        def assemble(self, draft, trusted_ids, locale):
            return draft

    verified = planner.Place(
        "verified-llm-stop",
        "LLM Verified Stop",
        "dia_danh",
        "Hà Nội",
        21.03,
        105.85,
        0,
        45,
        ("osm_verified",),
        7,
        22,
        "Nominatim",
        None,
    )

    def fake_verify(name, origin):
        if name == "LLM Verified Stop":
            return verified
        return next((place for place in planner.PLACES if place.name == name), None)

    monkeypatch.setattr(planner, "ai_adapter", DraftingAI())
    monkeypatch.setattr(planner, "verify_place_name", fake_verify)
    plan = build_plan(
        request().model_copy(
            update={"context": "detailed Hanoi itinerary with evening old quarter"}
        )
    )
    slot = next(
        slot
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
        if slot["dia_diem_id"] == "verified-llm-stop"
    )
    assert "clear story" in slot["mo_ta"]
    assert "photo spot" in slot["mo_ta"]
    assert "street snack" in slot["mo_ta"]
    assert "Walk to the next Old Quarter stop" in slot["ghi_chu"]


def test_ai_failure_falls_back_to_verified_deterministic_plan(monkeypatch):
    class FailingAI:
        def assemble(self, draft, trusted_ids, locale):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(planner, "ai_adapter", FailingAI())
    payload = request().model_copy(update={"ngon_ngu": "en"})
    plan = build_plan(payload)
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    assert 4 <= len(slots) <= 10
    assert validate_plan(plan, {slot["dia_diem_id"] for slot in slots}, payload) == []
    assert any("AI is temporarily unavailable" in note for note in plan["luu_y"])


def test_all_supported_locales_localize_copy_without_translating_names_or_sources():
    locales = UserPreferencesRequest.model_fields["ngon_ngu"].annotation.__args__
    assert set(locales) == set(COPY)
    for locale in locales:
        localized_request = request().model_copy(update={"ngon_ngu": locale})
        plan = build_plan(localized_request)
        slot = plan["ngay"][0]["khoang_gio"][0]
        place = next(item for item in PLACES if item.id == slot["dia_diem_id"])
        assert plan["tom_tat"] == COPY[locale][6].format(people=localized_request.so_nguoi)
        assert plan["ngay"][0]["nhan_de"] == COPY[locale][5].format(day=1)
        assert slot["ten_dia_diem"] == place.name
        assert slot["nguon"] == place.source
        assert slot["nguon_url"] == place.source_url
        assert "anh" in slot
        assert "anh_nguon" in slot
        assert place.name in slot["mo_ta"]
        assert place.area in slot["mo_ta"]


def test_planner_passes_all_supported_locales_to_weather_adapter(monkeypatch):
    locales = UserPreferencesRequest.model_fields["ngon_ngu"].annotation.__args__
    seen: list[str] = []

    def fake_weather(lat, lng, trip_date, locale):
        seen.append(locale)
        return {
            "tinh_trang": WEATHER_COPY[locale][0],
            "ghi_chu": WEATHER_COPY[locale][8],
            "nguon": "Open-Meteo",
        }

    monkeypatch.setattr(planner, "settings", replace(planner.settings, weather_enabled=True))
    monkeypatch.setattr(planner, "get_daily_weather", fake_weather)
    for locale in locales:
        plan = build_plan(request().model_copy(update={"ngon_ngu": locale}))
        assert plan["thoi_tiet"]["tinh_trang"] == WEATHER_COPY[locale][0]
    assert set(seen) == set(locales)
