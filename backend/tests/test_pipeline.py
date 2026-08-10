from dataclasses import replace

from app.data import PLACES
from app.pipeline import planner
from app.pipeline.planner import COPY, build_plan, validate_plan
from app.schemas import PlanRequest, UserPreferencesRequest
from app.services.weather import WEATHER_COPY


def request() -> PlanRequest:
    return PlanRequest(context="cuối tuần chill và ăn ngon", location={"lat": 21.0285, "lng": 105.8542}, thoi_luong="ca_ngay", so_nguoi=2, ngan_sach=1_000_000, ma_phien="test-session")


def test_schedule_reserves_travel_time_between_stops():
    from app.pipeline.routing import travel_minutes as travel

    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày",
                "thoi_luong": "ca_ngay",
                "nonce": "nonce-travel-gap-0001",
            }
        )
    )
    by_id = {place.id: place for place in PLACES}
    for day in plan["ngay"]:
        previous = None
        for slot in day["khoang_gio"]:
            place = by_id[slot["dia_diem_id"]]
            if previous:
                need = travel(previous[0], place)
                ph, pm = map(int, previous[1].split(":"))
                sh, sm = map(int, slot["bat_dau"].split(":"))
                gap = (sh * 60 + sm) - (ph * 60 + pm)
                assert gap >= need
            previous = (place, slot["ket_thuc"])


def test_full_day_schedule_avoids_long_gaps_and_midday_west_lake():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày Hồ Tây Lăng Bác",
                "thoi_luong": "ca_ngay",
                "nonce": "nonce-schedule-quality-0001",
            }
        )
    )
    slots = plan["ngay"][0]["khoang_gio"]
    assert len(slots) >= 4
    # No multi-hour holes between consecutive stops
    for left, right in zip(slots, slots[1:]):
        lh, lm = map(int, left["ket_thuc"].split(":"))
        rh, rm = map(int, right["bat_dau"].split(":"))
        assert (rh * 60 + rm) - (lh * 60 + lm) <= 120
    # Opening hours respected with known overrides
    by_id = {place.id: place for place in PLACES}
    for slot in slots:
        place = by_id[slot["dia_diem_id"]]
        open_hour, close_hour = planner._effective_hours(place)
        assert slot["bat_dau"] >= f"{open_hour:02d}:00"
        assert slot["ket_thuc"] <= f"{close_hour:02d}:00"
    west = next((slot for slot in slots if "Hồ Tây" in slot["ten_dia_diem"]), None)
    if west:
        start = int(west["bat_dau"][:2]) + int(west["bat_dau"][3:]) / 60
        assert start < 11 or start >= 14


def test_full_day_plan_includes_scheduled_dining():
    plan = build_plan(request().model_copy(update={"thoi_luong": "ca_ngay"}))
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    dining = [slot for slot in slots if slot["loai"] in {"nha_hang", "quan_an"} and slot.get("bua_an") in {"trua", "toi"}]
    assert len(dining) >= 2
    meal_types = {slot["bua_an"] for slot in dining if slot.get("bua_an")}
    assert "trua" in meal_types
    assert "toi" in meal_types
    lunch = next(slot for slot in dining if slot.get("bua_an") == "trua")
    dinner = next(slot for slot in dining if slot.get("bua_an") == "toi")
    assert lunch["bat_dau"] >= "11:30"
    assert dinner["bat_dau"] >= "18:00"
    assert all(slot.get("nhan_bua") for slot in dining)


def test_full_day_has_midday_rest_and_evening_after_dinner():
    plan = build_plan(
        request().model_copy(
            update={"thoi_luong": "ca_ngay", "nonce": "nonce-rest-evening-0001"}
        )
    )
    slots = plan["ngay"][0]["khoang_gio"]
    rest = next((slot for slot in slots if slot.get("bua_an") == "nghi"), None)
    lunch = next((slot for slot in slots if slot.get("bua_an") == "trua"), None)
    dinner = next((slot for slot in slots if slot.get("bua_an") == "toi"), None)
    assert rest is not None
    assert lunch is not None and dinner is not None
    assert lunch["ket_thuc"] <= rest["bat_dau"]
    assert "12:00" <= rest["bat_dau"] <= "14:30"
    after_dinner = [slot for slot in slots if slot["bat_dau"] >= dinner["ket_thuc"]]
    assert after_dinner, "expected at least one evening stop after dinner"


def test_each_night_market_tag_has_hard_evening_floor_in_normal_and_relax():
    day_start = planner.datetime(2026, 8, 10, 8)
    day_end = day_start.replace(hour=22)

    for tag in ("cho_dem", "night_market"):
        market = replace(
            PLACES[0],
            id=f"all-day-{tag}",
            name=f"Night market {tag}",
            tags=[tag],
            open_hour=8,
            close_hour=23,
            duration_min=60,
        )
        for relax in (False, True):
            bounds = planner._compute_slot_bounds(
                market,
                None,
                day_start,
                day_start,
                day_end,
                request(),
                relax=relax,
            )

            assert bounds is not None
            assert bounds[0] >= day_start.replace(hour=18)

        meal_bounds = planner._compute_slot_bounds(
            market,
            "trua",
            day_start,
            day_start,
            day_end,
            request(),
            relax=True,
        )
        assert meal_bounds is not None
        assert meal_bounds[0] >= day_start.replace(hour=18)


def test_night_market_is_skipped_when_evening_window_is_too_short():
    market = replace(
        PLACES[0],
        id="night-market-without-room",
        name="Night market without room",
        tags=["night_market"],
        open_hour=8,
        close_hour=23,
        duration_min=60,
    )
    day_start = planner.datetime(2026, 8, 10, 8)
    day_end = day_start.replace(hour=18, minute=20)

    for relax in (False, True):
        assert planner._compute_slot_bounds(
            market,
            None,
            day_start,
            day_start,
            day_end,
            request(),
            relax=relax,
        ) is None


def test_nightlife_only_place_keeps_daytime_scheduling():
    nightlife = replace(
        PLACES[0],
        id="daytime-nightlife-landmark",
        name="Daytime nightlife landmark",
        tags=["nightlife"],
        open_hour=8,
        close_hour=23,
        duration_min=60,
    )
    day_start = planner.datetime(2026, 8, 10, 8)

    bounds = planner._compute_slot_bounds(
        nightlife,
        None,
        day_start,
        day_start,
        day_start.replace(hour=22),
        request(),
    )

    assert bounds is not None
    assert bounds[0] < day_start.replace(hour=18)


def test_half_day_plan_includes_lunch():
    plan = build_plan(request().model_copy(update={"thoi_luong": "nua_ngay"}))
    slots = plan["ngay"][0]["khoang_gio"]
    dining = [slot for slot in slots if slot.get("bua_an") == "trua"]
    assert len(dining) == 1
    assert dining[0]["loai"] in {"nha_hang", "quan_an"}
    assert dining[0]["bat_dau"] >= "11:30"


def test_plan_never_repeats_same_place_name():
    for duration, nonce in (
        ("ca_ngay", "nonce-dedupe-day-0001"),
        ("nhieu_ngay", "nonce-dedupe-multi-0001"),
    ):
        plan = build_plan(
            request().model_copy(
                update={
                    "context": "du lịch Hà Nội lần đầu, tham quan điểm nổi tiếng",
                    "thoi_luong": duration,
                    "nonce": nonce,
                }
            )
        )
        slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
        ids = [slot["dia_diem_id"] for slot in slots]
        names = [slot["ten_dia_diem"] for slot in slots]
        assert len(ids) == len(set(ids))
        normalized_names = [
            planner._place_name_key(replace(PLACES[0], name=name)) for name in names
        ]
        assert len(normalized_names) == len(set(normalized_names))
        assert names.count("Lăng Chủ tịch Hồ Chí Minh") <= 1


def test_place_name_dedupe_uses_accent_case_and_spacing_normalization():
    first = replace(PLACES[0], id="alias-one", name="  Café   Đinh ")
    alias = replace(PLACES[0], id="alias-two", name="cafe dinh")
    distinct = replace(PLACES[0], id="distinct", name="Café Phố Cổ")

    deduped = planner._dedupe_places([first, alias, distinct])

    assert len(deduped) == 2
    assert {planner._place_name_key(place) for place in deduped} == {
        "cafe dinh",
        "cafe pho co",
    }


def test_extra_candidate_skips_used_name_alias_and_tries_next(monkeypatch):
    alias = replace(
        PLACES[0],
        id="alias-nearest",
        name="  Café   Đinh ",
        kind="dia_danh",
        lat=21.0285,
        lng=105.8542,
        source="curated",
    )
    fallback = replace(
        PLACES[0],
        id="different-next",
        name="Văn Miếu",
        kind="dia_danh",
        lat=21.03,
        lng=105.85,
        source="curated",
    )
    monkeypatch.setattr(planner, "PLACES", [alias, fallback])

    chosen = planner._choose_extra_sight(
        request(),
        set(),
        (21.0285, 105.8542),
        1,
        1_000_000,
        {"cafe dinh"},
    )

    assert chosen is not None
    assert chosen.id == "different-next"


def test_backfill_tries_next_candidate_when_first_cannot_fit(monkeypatch):
    day_start = planner.datetime(2026, 8, 10, 8)
    previous = replace(PLACES[0], id="previous", name="Điểm đầu")
    following = replace(PLACES[0], id="following", name="Điểm cuối")
    cannot_fit = replace(PLACES[0], id="cannot-fit", name="Không vừa giờ")
    fits = replace(PLACES[0], id="fits", name="Điểm thay thế")
    monkeypatch.setattr(planner, "PLACES", [previous, following, cannot_fit, fits])

    def choose(*args, **kwargs):
        excluded = args[1]
        return fits if cannot_fit.id in excluded else cannot_fit

    def bounds(place, _meal, _arrive, *_args, **_kwargs):
        if place.id == cannot_fit.id:
            return None
        return day_start.replace(hour=10), day_start.replace(hour=10, minute=30), 30

    monkeypatch.setattr(planner, "_choose_extra_sight", choose)
    monkeypatch.setattr(planner, "_compute_slot_bounds", bounds)
    monkeypatch.setattr(planner, "travel_minutes", lambda *_args: 5)
    monkeypatch.setattr(planner, "_slot_copy", lambda *_args: ("Mô tả", "Ghi chú"))
    monkeypatch.setattr(planner, "image_for", lambda *_args: (None, None))
    monkeypatch.setattr(planner, "_tighten_day_gaps", lambda slots, _end: slots)
    slots = [
        {"bat_dau": "08:00", "ket_thuc": "09:00", "dia_diem_id": previous.id},
        {"bat_dau": "12:00", "ket_thuc": "13:00", "dia_diem_id": following.id},
    ]

    result, _ = planner._backfill_day_gaps(
        slots, day_start, 600, request(), COPY["vi"], {}, planner._meal_labels("vi"),
        {previous.id, following.id}, {"diem dau", "diem cuoi"}, set(), 1_000_000, 1, 5,
    )

    assert [slot["dia_diem_id"] for slot in result] == [previous.id, fits.id, following.id]


def test_plan_has_one_valid_route_with_trusted_places():
    from app.pipeline.planner import _max_plan_slots, _min_plan_slots

    plan = build_plan(request())
    slots = plan["ngay"][0]["khoang_gio"]
    assert _min_plan_slots("ca_ngay") <= len(slots) <= _max_plan_slots("ca_ngay")
    assert len({slot["dia_diem_id"] for slot in slots}) == len(slots)
    assert validate_plan(plan, {slot["dia_diem_id"] for slot in slots}) == []


def test_validator_rejects_hallucinated_place():
    plan = build_plan(request())
    plan["ngay"][0]["khoang_gio"][0]["dia_diem_id"] = "fake"
    assert "Có địa điểm ngoài danh sách tin cậy" in validate_plan(plan, set())


def test_all_duration_modes_are_supported():
    from app.pipeline.planner import _max_plan_slots, _min_plan_slots

    for duration in ("vai_gio", "nua_ngay", "ca_ngay", "nhieu_ngay"):
        payload = request().model_copy(update={"thoi_luong": duration})
        plan = build_plan(payload)
        slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
        assert _min_plan_slots(duration) <= len(slots) <= _max_plan_slots(duration)
        assert len(plan["ngay"]) == (2 if duration == "nhieu_ngay" else 1)
        if duration == "nhieu_ngay":
            day_counts = [len(day["khoang_gio"]) for day in plan["ngay"]]
            assert all(count >= 4 for count in day_counts)
            assert sum(day_counts) >= 10


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


def test_tourism_plan_prefers_attractions_over_cafes():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội 2 ngày tham quan",
                "thoi_luong": "nhieu_ngay",
                "nonce": "nonce-sights-not-cafe-0001",
            }
        )
    )
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    kinds = [slot["loai"] for slot in slots]
    cafe_as_sightseeing = sum(
        1 for slot in slots if slot["loai"] == "cafe" and not slot.get("bua_an")
    )
    sight_count = sum(1 for kind in kinds if kind in {"dia_danh", "bao_tang", "cong_vien", "cho"})
    meal_count = sum(1 for slot in slots if slot.get("bua_an") in {"trua", "toi"})
    assert cafe_as_sightseeing == 0
    assert sight_count >= 6
    assert meal_count >= 2
    assert sight_count > cafe_as_sightseeing
    assert any(slot.get("bua_an") == "nghi" for slot in slots)
    for day in plan["ngay"]:
        dinner = next((slot for slot in day["khoang_gio"] if slot.get("bua_an") == "toi"), None)
        assert dinner is not None
        assert any(
            slot.get("bua_an") == "dem" or slot["bat_dau"] >= dinner["ket_thuc"]
            for slot in day["khoang_gio"]
        )


def test_visit_guidance_keeps_lang_bac_in_morning_window():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội tham quan Lăng Bác và phố cổ",
                "thoi_luong": "ca_ngay",
                "nonce": "nonce-lang-bac-morning-0001",
            }
        )
    )
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    lang = next(
        (slot for slot in slots if "Lăng" in slot["ten_dia_diem"] or "lang" in slot["dia_diem_id"]),
        None,
    )
    assert lang is not None
    assert lang["bat_dau"] < "11:00"
    assert lang["ket_thuc"] <= "11:00"
    dinner = next((slot for slot in slots if slot.get("bua_an") == "toi"), None)
    assert dinner is not None
    assert dinner["bat_dau"] >= "18:00"


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
    from app.pipeline.planner import _max_plan_slots, _min_plan_slots

    assert _min_plan_slots("ca_ngay") <= len(slots) <= _max_plan_slots("ca_ngay")
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
