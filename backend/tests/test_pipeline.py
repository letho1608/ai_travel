from dataclasses import replace
from datetime import date

from app.data import PLACES, Place, place_name_key
from app.pipeline import planner
from app.pipeline import visit_guidance
from app.pipeline.planner import COPY, build_plan, validate_plan
from app.schemas import PlanRequest, UserPreferencesRequest
from app.services.weather import WEATHER_COPY


def request() -> PlanRequest:
    return PlanRequest(context="cuối tuần chill và ăn ngon", location={"lat": 21.0285, "lng": 105.8542}, thoi_luong="ca_ngay", so_nguoi=2, ngan_sach=1_000_000, ma_phien="test-session")


def test_plan_explains_input_understanding_and_candidate_data():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày, thích cafe checkin, không thích quá đông",
                "nonce": "nonce-input-understanding-0001",
            }
        )
    )

    understood = plan["dau_vao_da_hieu"]
    assert understood["schema_version"] == "input-understanding-v1"
    assert understood["context_goc"].startswith("du lịch Hà Nội")
    assert understood["diem_den"]["gia_tri"]["ten"]
    assert understood["diem_den"]["nguon"] in {"doi_chieu_catalog", "ai_extracted"}
    assert understood["so_ngay"] == {"gia_tri": 1, "nguon": "form_chat", "bang_chung": "ca_ngay", "trang_thai": "present"}
    assert understood["so_nguoi"]["gia_tri"] == 2
    assert understood["so_nguoi"]["nguon"] == "form_chat"
    assert understood["ngan_sach"]["gia_tri"] == 1_000_000
    assert understood["thoi_luong"]["nguon"] == "form_chat"
    assert understood["so_thich"]
    assert understood["khong_thich"]
    assert isinstance(understood["muc_bat_buoc"], list)
    assert understood["bat_buoc_thieu"] == []
    assert understood["hanh_dong_tiep_theo"] == "du_dieu_kien_lap_lich"
    assert "form_chat" in understood["xuat_xu"]
    assert "rule_based_context" in understood["xuat_xu"]

    candidates = plan["du_lieu_ung_vien"]
    assert candidates["tong_ung_vien"] > 0
    assert candidates["ban_kinh_km"] == planner.DESTINATION_RADIUS_KM
    assert candidates["nguon"]


def test_destination_region_filters_candidates_before_ranking():
    req = request().model_copy(
        update={
            "context": "tôi muốn đi chữa lành\nCả ngày\nĐà Nẵng",
            "nonce": "nonce-da-nang-region-0001",
        }
    )

    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "Đà Nẵng"
    assert planner._wants_night(req) is False

    plan = build_plan(req)
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]

    assert plan["tieu_de"] == "Lịch trình du lịch chữa lành Đà Nẵng 1 ngày cho 2 người"
    assert len(slots) >= 4
    names = {slot["ten_dia_diem"] for slot in slots}
    assert names.intersection(
        {
            "Bãi biển Mỹ Khê",
            "Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng",
            "Cầu Rồng",
            "Cầu Sông Hàn",
            "Ngũ Hành Sơn",
            "Núi Sơn Trà",
        }
    )
    assert not {"Hero Statue", "Pont main", "Louvre"}.intersection(names)
    assert not {
        "osm-node-4489385889",
        "osm-relation-7112202",
        "osm-way-765597030",
    }.intersection({slot["dia_diem_id"] for slot in slots})
    assert all(
        planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
        <= planner.DESTINATION_RADIUS_KM
        for slot in slots
    )


def test_plan_title_labels_days_and_people_instead_of_raw_numbers():
    req = request().model_copy(
        update={
            "context": "du lịch hà nội\n2\n2",
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 2,
        }
    )
    assert planner._plan_title("Hà Nội", req, 2) == "Lịch trình du lịch Hà Nội 2 ngày cho 2 người"
    english = req.model_copy(update={"ngon_ngu": "en"})
    assert planner._plan_title("Hà Nội", english, 2) == "Travel itinerary: Hà Nội · 2 days for 2 people"


def test_finalize_plan_title_prefers_llm_sentence_from_user_request():
    req = request().model_copy(update={"context": "cà phê và đi bộ cuối tuần ở Hà Nội", "thoi_luong": "vai_gio"})
    kept = planner._finalize_plan_title(
        "Lịch trình du lịch cà phê đi bộ một buổi chiều Hà Nội cho hai người",
        "Hà Nội",
        req,
        1,
    )
    assert kept.startswith("Lịch trình du lịch")
    assert "Hà Nội" in kept
    prefixed = planner._finalize_plan_title(
        "Cà phê cuối tuần dạo phố cổ Hà Nội cho 2 người",
        "Hà Nội",
        req,
        1,
    )
    assert prefixed.startswith("Lịch trình du lịch")
    dumped = planner._finalize_plan_title("Hà Nội · 2 giờ · 2 người", "Hà Nội", req, 1)
    assert dumped == planner._plan_title("Hà Nội", req, 1)


def test_trip_timing_understands_hours_clock_and_date_ranges():
    today = date(2026, 8, 17)

    hours = request().model_copy(update={"context": "Hà Nội 2 giờ", "thoi_luong": "vai_gio"})
    two_hours = planner._trip_timing(hours, today=today)
    assert two_hours.max_minutes == 120
    assert two_hours.clock_label == "2 giờ"
    assert two_hours.days == 1
    assert planner._plan_title("Hà Nội", hours, 1) == "Lịch trình du lịch Hà Nội 2 giờ cho 2 người"
    assert planner._meals_per_day("vai_gio", hours) == ()

    compact = request().model_copy(update={"context": "Hà Nội 2h", "thoi_luong": "vai_gio"})
    assert planner._trip_timing(compact, today=today).max_minutes == 120

    spoken = request().model_copy(update={"context": "đi hai giờ", "thoi_luong": "vai_gio"})
    assert planner._trip_timing(spoken, today=today).max_minutes == 120

    clock = request().model_copy(update={"context": "từ 9 giờ đến 17 giờ", "thoi_luong": "ca_ngay"})
    clock_timing = planner._trip_timing(clock, today=today)
    assert clock_timing.start_hour == 9
    assert clock_timing.max_minutes == 480
    assert clock_timing.clock_label == "9h–17h"
    assert planner._meals_per_day("ca_ngay", clock) == ("trua",)
    assert planner._plan_title("Hà Nội", clock, 1) == "Lịch trình du lịch Hà Nội 9h–17h cho 2 người"

    english_clock = request().model_copy(
        update={"context": "from 9am to 5pm", "thoi_luong": "ca_ngay", "ngon_ngu": "en"}
    )
    english_timing = planner._trip_timing(english_clock, today=today)
    assert english_timing.start_hour == 9
    assert english_timing.max_minutes == 480

    dates = request().model_copy(update={"context": "từ 20/8 đến 22/8", "thoi_luong": "ca_ngay"})
    date_timing = planner._trip_timing(dates, today=today)
    assert date_timing.days == 3
    assert date_timing.start_date == date(2026, 8, 20)
    assert date_timing.date_label == "20/8–22/8"
    assert planner._plan_title("Hà Nội", dates, 3) == "Lịch trình du lịch Hà Nội 20/8–22/8 cho 2 người"

    month_days = request().model_copy(update={"context": "từ ngày 20 đến ngày 22", "thoi_luong": "nhieu_ngay"})
    day_timing = planner._trip_timing(month_days, today=today)
    assert day_timing.days == 3
    assert day_timing.start_date == date(2026, 8, 20)


def test_short_hour_and_clock_windows_actually_pack():
    two_hours = build_plan(
        request().model_copy(
            update={
                "context": "Hà Nội 2 giờ",
                "thoi_luong": "vai_gio",
                "nonce": "nonce-two-hours-window-0001",
            }
        )
    )
    two_slots = two_hours["ngay"][0]["khoang_gio"]
    assert two_hours["tieu_de"] == "Lịch trình du lịch Hà Nội 2 giờ cho 2 người"
    assert 2 <= len(two_slots) <= 3
    start_h, start_m = map(int, two_slots[0]["bat_dau"].split(":"))
    end_h, end_m = map(int, two_slots[-1]["ket_thuc"].split(":"))
    assert (end_h * 60 + end_m) - (start_h * 60 + start_m) <= 150

    clock = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội từ 9h đến 17h",
                "thoi_luong": "ca_ngay",
                "nonce": "nonce-clock-window-0001",
            }
        )
    )
    clock_slots = clock["ngay"][0]["khoang_gio"]
    assert clock["tieu_de"] == "Lịch trình du lịch Hà Nội 9h–17h cho 2 người"
    assert clock_slots[0]["bat_dau"].startswith("09:")
    last_h, _ = map(int, clock_slots[-1]["ket_thuc"].split(":"))
    assert last_h <= 17


def test_saigon_alias_resolves_to_hcm_region():
    req = request().model_copy(
        update={
            "context": "tôi muốn đi sài gòn 2 ngày",
            "thoi_luong": "nhieu_ngay",
            "nonce": "nonce-saigon-region-0001",
        }
    )

    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "TP.HCM"

    plan = build_plan(req)
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]

    assert plan["tieu_de"] == "Lịch trình du lịch TP.HCM 2 ngày cho 2 người"
    assert len(plan["ngay"]) == 2
    assert all(
        planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
        <= planner.DESTINATION_RADIUS_KM
        for slot in slots
    )


def test_nha_trang_uses_curated_tourism_anchors():
    req = PlanRequest.model_validate(
        {
            "context": "tôi muốn du lịch nha trang 1 ngày",
            "location": {"lat": 12.2388, "lng": 109.1967},
            "thoi_luong": "ca_ngay",
            "so_nguoi": 2,
            "ngan_sach": 1_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-nha-trang-curated-0001",
        }
    )

    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "Nha Trang"

    plan = build_plan(req)
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    names = {slot["ten_dia_diem"] for slot in slots}

    assert names.intersection(
        {
            "Bãi biển Nha Trang",
            "Tháp Bà Ponagar",
            "Hòn Chồng",
            "Viện Hải dương học Nha Trang",
            "Nhà thờ Đá Nha Trang",
            "Chùa Long Sơn",
            "VinWonders Nha Trang",
            "Hòn Mun",
            "Hòn Tằm",
        }
    )
    assert not {"Nha Trang", "LOVE", "Showroom", "Some Motobikes", "GAS station"}.intersection(names)
    assert all(
        planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
        <= planner.DESTINATION_RADIUS_KM
        for slot in slots
    )


def test_da_nang_plan_includes_famous_attractions():
    req = PlanRequest.model_validate(
        {
            "context": "tôi muốn du lịch Đà Nẵng 1 ngày",
            "location": {"lat": 16.0544, "lng": 108.2022},
            "thoi_luong": "ca_ngay",
            "so_nguoi": 2,
            "ngan_sach": 1_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-da-nang-famous-0001",
        }
    )
    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "Đà Nẵng"
    plan = build_plan(req)
    names = {slot["ten_dia_diem"] for day in plan["ngay"] for slot in day["khoang_gio"]}
    assert names.intersection(
        {
            "Cầu Vàng",
            "Bà Nà Hills",
            "Bãi biển Mỹ Khê",
            "Ngũ Hành Sơn",
            "Chùa Linh Ứng Sơn Trà",
            "Cầu Rồng",
            "Bảo tàng Điêu khắc Chăm",
            "Phố cổ Hội An",
            "Chùa Cầu",
        }
    )
    assert all(
        planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
        <= planner.DESTINATION_RADIUS_KM
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
    )


def test_destination_city_name_is_not_used_as_a_stop():
    req = PlanRequest.model_validate(
        {
            "context": "du lịch đà lạt 2 ngày cho 2 người Đà Lạt",
            "location": {"lat": 11.9404, "lng": 108.4583},
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 2,
            "ngan_sach": 2_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-da-lat-city-name-0001",
        }
    )
    _, _, destination_label = planner._destination_context(req)
    assert destination_label == "Đà Lạt"
    names = {slot["ten_dia_diem"] for day in build_plan(req)["ngay"] for slot in day["khoang_gio"]}
    assert "Đà Lạt" not in names
    assert "Dalat" not in names


def test_hue_plan_includes_famous_attractions():
    req = PlanRequest.model_validate(
        {
            "context": "tôi muốn du lịch Huế cả ngày",
            "location": {"lat": 16.4637, "lng": 107.5909},
            "thoi_luong": "ca_ngay",
            "so_nguoi": 2,
            "ngan_sach": 1_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-hue-famous-0001",
        }
    )
    _, _, destination_label = planner._destination_context(req)
    assert destination_label == "Huế"
    names = {slot["ten_dia_diem"] for day in build_plan(req)["ngay"] for slot in day["khoang_gio"]}
    assert names.intersection({"Đại Nội Huế", "Chùa Thiên Mụ", "Sông Hương", "Lăng Khải Định"})


def test_llm_place_names_outside_destination_are_ignored(monkeypatch):
    def draft_hanoi_first(context: str, count: int, locale: str):
        return [
            {"name": "Hồ Tây", "kind": "dia_danh", "why": "wrong city"},
            {"name": "Phố cổ Hà Nội", "kind": "dia_danh", "why": "wrong city"},
        ]

    monkeypatch.setattr(planner.ai_adapter, "draft_itinerary_places", draft_hanoi_first)
    req = request().model_copy(
        update={
            "context": "tôi muốn đi chữa lành Đà Nẵng",
            "nonce": "nonce-da-nang-ignore-llm-hanoi-0001",
        }
    )

    destination_lat, destination_lng, _ = planner._destination_context(req)
    plan = build_plan(req)
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]

    assert "Hồ Tây" not in {slot["ten_dia_diem"] for slot in slots}
    assert all(
        planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
        <= planner.DESTINATION_RADIUS_KM
        for slot in slots
    )


def test_validate_plan_rejects_slots_outside_requested_destination():
    hanoi_plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày",
                "nonce": "nonce-hanoi-region-guard-0001",
            }
        )
    )
    danang_request = PlanRequest.model_validate(
        {
            "context": "tôi muốn đi chữa lành Đà Nẵng",
            "location": {"lat": 16.0544, "lng": 108.2022},
            "thoi_luong": "ca_ngay",
            "so_nguoi": 2,
            "ngan_sach": 1_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-danang-region-guard-0001",
        }
    )
    trusted_ids = {slot["dia_diem_id"] for day in hanoi_plan["ngay"] for slot in day["khoang_gio"]} | {
        place.id for place in PLACES
    }

    errors = validate_plan(hanoi_plan, trusted_ids, danang_request)

    assert any("ngoài vùng Đà Nẵng" in error for error in errors)


def test_slots_include_ranking_data_source_and_time_reason():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "Hà Nội chill ăn ngon cả ngày",
                "nonce": "nonce-slot-evidence-0001",
            }
        )
    )
    slot = plan["ngay"][0]["khoang_gio"][0]
    evidence = slot["bang_chung"]

    assert set(evidence["xep_hang"]["thanh_phan"]) == {
        "muc_phu_hop",
        "diem_danh_gia",
        "vi_tri_khoang_cach",
        "khop_gio_mo_cua",
        "so_nhan_xet",
    }
    assert evidence["du_lieu"]["nguon"]
    assert evidence["du_lieu"]["co_toa_do"] is True
    assert evidence["xep_hang"]["thanh_phan"]["diem_danh_gia"] is None
    assert evidence["xep_hang"]["thanh_phan"]["so_nhan_xet"] is None
    assert {"rating", "so_review"} <= set(evidence["xep_hang"]["du_lieu_thieu"])
    assert evidence["xep_hang"]["du_lieu_thuc_te"] == {"rating": None, "so_nhan_xet": None}
    assert evidence["thoi_diem"]["ly_do"]


def test_plan_marks_vietnam_holiday_timing_context():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày",
                "ngay_di": date(2026, 9, 2),
                "nonce": "nonce-holiday-context-0001",
            }
        )
    )

    timing = plan["tieu_chi_thoi_diem"]
    assert timing["lich_nghi_le"]["ma"] == "quoc_khanh"
    assert "Chợ đêm" in " ".join(timing["quy_tac"])


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


def test_lunch_cannot_be_relaxed_into_evening():
    place = replace(
        PLACES[0],
        id="late-lunch-place",
        name="Late lunch place",
        kind="nha_hang",
        open_hour=8,
        close_hour=23,
        duration_min=60,
    )
    day_start = planner.datetime(2026, 8, 10, 8)
    arrive = day_start.replace(hour=19, minute=30)

    assert planner._compute_slot_bounds(
        place,
        "trua",
        arrive,
        day_start,
        day_start.replace(hour=22),
        request(),
        relax=True,
    ) is None


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


def test_untagged_osm_night_market_name_still_has_evening_floor():
    market = next(place for place in PLACES if place.id == "osm-node-4489385889")
    assert "attraction" in market.tags
    assert planner._is_evening_place(market)
    day_start = planner.datetime(2026, 8, 10, 8)

    for relax in (False, True):
        bounds = planner._compute_slot_bounds(
            market,
            None,
            day_start,
            day_start,
            day_start.replace(hour=22),
            request(),
            relax=relax,
        )

        assert bounds is not None
        assert bounds[0] >= day_start.replace(hour=18)

    english_market = replace(market, id="english-night-market", name="Weekend Night Market")
    assert planner._is_night_market(english_market)

    restaurant = replace(
        market,
        id="restaurant-at-night-market",
        name="Bánh Xèo Bizon - Chợ Đêm Đồng Xuân",
        kind="nha_hang",
    )
    assert not planner._is_night_market(restaurant)


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
            planner._place_alias_key(replace(PLACES[0], name=name)) for name in names
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


def test_osm_beach_name_and_english_suffix_are_the_same_stop():
    beach = replace(
        PLACES[0],
        id="bai-truong",
        name="Bãi Trường",
        tags=("attraction", "beach"),
    )
    twin = replace(
        PLACES[0],
        id="bai-truong-beach",
        name="Bãi Trường Beach",
        tags=("attraction",),
    )
    other = replace(
        PLACES[0],
        id="bai-sao",
        name="Bãi Sao",
        tags=("attraction", "beach"),
    )

    deduped = planner._dedupe_places([beach, twin, other])

    assert len(deduped) == 2
    names = {place.name for place in deduped}
    assert "Bãi Sao" in names
    assert "Bãi Trường" in names
    assert "Bãi Trường Beach" not in names
    assert planner._name_taken(twin, planner._place_name_keys(beach))


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
    planner._places_near.cache_clear()

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


def test_extra_candidate_skips_beach_english_suffix_alias(monkeypatch):
    beach = replace(
        PLACES[0],
        id="bai-truong",
        name="Bãi Trường",
        kind="dia_danh",
        lat=21.0285,
        lng=105.8542,
        source="OpenStreetMap",
        tags=("attraction", "beach"),
    )
    twin = replace(
        PLACES[0],
        id="bai-truong-beach",
        name="Bãi Trường Beach",
        kind="dia_danh",
        lat=21.0286,
        lng=105.8543,
        source="OpenStreetMap",
        tags=("attraction",),
    )
    other = replace(
        PLACES[0],
        id="bai-sao",
        name="Bãi Sao",
        kind="dia_danh",
        lat=21.03,
        lng=105.85,
        source="OpenStreetMap",
        tags=("attraction", "beach"),
    )
    monkeypatch.setattr(planner, "PLACES", [twin, other])
    planner._places_near.cache_clear()

    chosen = planner._choose_extra_sight(
        request(),
        set(),
        (21.0285, 105.8542),
        1,
        1_000_000,
        planner._place_name_keys(beach),
    )

    assert chosen is not None
    assert chosen.id == "bai-sao"


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


def test_delete_validation_relaxes_only_minimum_cardinality():
    payload = request()
    plan = build_plan(payload)
    slot = plan["ngay"][0]["khoang_gio"][0]
    for day in plan["ngay"]:
        day["khoang_gio"] = []
    plan["ngay"][0]["khoang_gio"] = [slot]
    assert validate_plan(plan, {slot["dia_diem_id"]}, payload, allow_below_minimum=True) == []
    slot["dia_diem_id"] = "fake"
    assert validate_plan(plan, set(), payload, allow_below_minimum=True)


def test_validator_accepts_verified_external_place_metadata():
    payload = request()
    plan = build_plan(payload)
    slot = plan["ngay"][0]["khoang_gio"][0]
    external = Place("osm-verified-node-42", "Điểm mới", "dia_danh", "Hà Nội", slot["toa_do"]["lat"], slot["toa_do"]["lng"], 0, 60, ("osm_verified",), 7, 22, "Nominatim")
    slot.update({"dia_diem_id": external.id, "ten_dia_diem": external.name, "toa_do": {"lat": external.lat, "lng": external.lng}})
    trusted = {item["dia_diem_id"] for day in plan["ngay"] for item in day["khoang_gio"]}
    assert validate_plan(plan, trusted, payload, trusted_places=(external,)) == []


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


def test_attraction_descriptions_are_not_copy_pasted():
    req = PlanRequest.model_validate(
        {
            "context": "du lịch Phú Quốc 2 ngày 2 đêm",
            "location": {"lat": 10.2899, "lng": 103.9840},
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 2,
            "ngan_sach": 1_000_000,
            "ma_phien": "test-session",
            "nonce": "nonce-phu-quoc-copy-0001",
        }
    )
    sights = [
        slot
        for day in build_plan(req)["ngay"]
        for slot in day["khoang_gio"]
        if slot["loai"] not in {"nha_hang", "quan_an"}
    ]
    assert len(sights) >= 2
    stripped = [slot["mo_ta"].replace(slot["ten_dia_diem"], "ĐỊA_ĐIỂM") for slot in sights]
    assert "lát cắt địa phương" not in " ".join(stripped)
    assert len(set(stripped)) >= min(3, len(stripped))
    alias_keys = [
        planner._place_alias_key(replace(PLACES[0], name=slot["ten_dia_diem"]))
        for slot in sights
    ]
    assert len(alias_keys) == len(set(alias_keys))


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
    place_keys = {place_name_key(name) for name in place_names}
    assert "Phố cổ Hà Nội" in place_names
    assert {
        place_name_key("Chợ đêm"),
        place_name_key("Chợ đêm Hàng Đào – Đồng Xuân"),
        place_name_key("Phố Tạ Hiện"),
    }.intersection(place_keys)
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
                for place_id in ("curated-ho-tay", "osm-way-37625751", "curated-ho-guom")
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
    assert {"curated-ho-tay", "osm-way-37625751", "curated-ho-guom"} <= place_ids


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


def test_hot_weather_pushes_outdoor_midday_after_three_pm():
    place = replace(
        PLACES[0],
        id="hot-outdoor",
        name="Điểm ngoài trời nóng",
        kind="cong_vien",
        tags=("ngoai_troi", "view_dep"),
        open_hour=6,
        close_hour=20,
        duration_min=45,
    )
    day_start = planner.datetime(2026, 8, 12, 8, 0)
    arrive = day_start.replace(hour=12, minute=0)
    bounds = planner._compute_slot_bounds(
        place,
        None,
        arrive,
        day_start,
        day_start.replace(hour=20),
        request(),
        weather={"nhiet_do_max": 35, "xac_suat_mua": 10},
    )
    assert bounds is not None
    assert bounds[0] >= day_start.replace(hour=15, minute=0)


def test_rainy_weather_penalizes_outdoor_midday_score():
    place = replace(
        PLACES[0],
        id="rainy-outdoor",
        name="Điểm ngoài trời mưa",
        kind="cong_vien",
        tags=("ngoai_troi",),
    )
    clear = planner._preference_score(place, None, 12.0, {"nhiet_do_max": 28, "xac_suat_mua": 20})
    rainy = planner._preference_score(place, None, 12.0, {"nhiet_do_max": 28, "xac_suat_mua": 70})
    assert rainy < clear


def test_generated_visit_guidance_json_is_loaded():
    assert visit_guidance.GENERATED_GUIDANCE_PATH.name == "visit_guidance.json"
    assert visit_guidance.GENERATED_VISIT_GUIDANCE_BY_ID
    guidance = next(iter(visit_guidance.GENERATED_VISIT_GUIDANCE_BY_ID.values()))
    assert guidance.preferred[0] < guidance.preferred[2]
    assert guidance.source
