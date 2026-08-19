from dataclasses import replace
from datetime import date, datetime, timedelta

from app.data import PLACES, Place, place_match_key, place_name_key, source_for
from app.pipeline import planner
from app.pipeline import visit_guidance
from app.pipeline.cp_sat_solver import (
    optimize_day_schedule_with_cp_sat,
    optimize_order_with_cp_sat,
    select_places_with_cp_sat,
    verify_fixed_schedule_with_cp_sat,
)
from app.pipeline.planner import COPY, build_plan, validate_plan
from app.pipeline.solar import sunset_for_date
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


def test_intent_policy_filters_sight_candidates_by_theme():
    req = request().model_copy(update={
        "context": "muốn đi leo núi ở Sa Pa 1 ngày 2 người",
        "intent_policy": {
            "schema_version": "intent-parse-v2",
            "primary_intent": "mountain",
            "planner_mode": "day_trip",
            "allowed_place_themes": ["mountain", "trekking", "viewpoint", "nature"],
            "avoid_place_themes": ["museum", "urban_landmark"],
        },
    })
    museum = planner.Place(
        id="test-museum",
        name="Bảo tàng đô thị",
        kind="bao_tang",
        area="Sa Pa",
        lat=22.33,
        lng=103.84,
        cost=0,
        duration_min=60,
        tags=("museum", "history"),
    )
    peak = planner.Place(
        id="test-peak",
        name="Đỉnh núi thử nghiệm",
        kind="nui",
        area="Sa Pa",
        lat=22.34,
        lng=103.85,
        cost=0,
        duration_min=90,
        tags=("nui", "view_dep", "trekking"),
    )

    filtered, evidence = planner._apply_intent_policy_to_sights([museum, peak], req, 1)

    assert evidence["che_do"] == "strict_filter"
    assert [place.id for place in filtered] == ["test-peak"]


def test_food_trip_sight_pool_uses_restaurants_not_city_named_gardens():
    req = request().model_copy(update={
        "context": "Đà Lạt chữa lành; đổi sang ăn uống",
        "intent_policy": {
            "schema_version": "intent-parse-v2",
            "primary_intent": "food",
            "allowed_place_themes": ["food", "local_food", "market", "seafood"],
            "avoid_place_themes": [],
        },
    })
    garden = planner.Place(
        id="test-garden",
        name="Vườn hoa thành phố Đà Lạt",
        kind="cong_vien",
        area="Đà Lạt",
        lat=11.94,
        lng=108.44,
        cost=0,
        duration_min=60,
        tags=("view_dep", "checkin"),
    )
    restaurant = planner.Place(
        id="test-food",
        name="Quán lẩu gà lá é",
        kind="nha_hang",
        area="Đà Lạt",
        lat=11.94,
        lng=108.45,
        cost=150_000,
        duration_min=60,
        tags=("am_thuc", "local"),
    )
    market = planner.Place(
        id="test-market",
        name="Chợ Đà Lạt",
        kind="cho",
        area="Đà Lạt",
        lat=11.94,
        lng=108.43,
        cost=0,
        duration_min=45,
        tags=("am_thuc", "local"),
    )
    pool = planner._sight_candidates([garden, restaurant, market], req)
    assert restaurant in pool
    assert market in pool
    filtered, evidence = planner._apply_intent_policy_to_sights(pool, req, 2)
    ids = {place.id for place in filtered[:4]}
    assert "test-food" in ids or "test-market" in ids
    assert evidence["che_do"] != "soft_rank_not_enough_strict_matches" or restaurant in filtered



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


def test_healing_anywhere_with_dalat_coords_is_not_nui_chua():
    req = PlanRequest(
        context="tôi muốn đi chữa lành tôi không biết nữa, đi đâu cũng được 3 ngày 2 người",
        location={"lat": 11.9404, "lng": 108.4583},
        thoi_luong="nhieu_ngay",
        so_nguoi=2,
        ngan_sach=1_000_000,
        ma_phien="heal-dalat-title",
    )
    _, _, label = planner._destination_context(req)
    assert label == "Đà Lạt"
    title = planner._plan_title(label, req, 3)
    assert "Đà Lạt" in title
    folded = planner._ascii_fold(title).casefold()
    assert "nui chua" not in folded

    hanoi_coords = PlanRequest.model_validate(
        {**req.model_dump(mode="json"), "location": {"lat": 21.0285, "lng": 105.8542}}
    )
    _, _, hanoi_label = planner._destination_context(hanoi_coords)
    assert planner._ascii_fold(hanoi_label or "").casefold() != "nui chua"


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
    assert date_timing.clock_label != "8h–22h"
    assert date_timing.clock_label != "8h–21h"
    assert planner._plan_title("Hà Nội", dates, 3) == "Lịch trình du lịch Hà Nội 20/8–22/8 cho 2 người"

    month_days = request().model_copy(update={"context": "từ ngày 20 đến ngày 22", "thoi_luong": "nhieu_ngay"})
    day_timing = planner._trip_timing(month_days, today=today)
    assert day_timing.days == 3
    assert day_timing.start_date == date(2026, 8, 20)


def test_trip_timing_understands_relative_dates():
    today = date(2026, 8, 17)

    tomorrow = request().model_copy(update={"context": "Hà Nội ngày mai", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(tomorrow, today=today)
    assert timing.start_date == today + timedelta(days=1)
    assert timing.date_label == "18/8"

    day_after = request().model_copy(update={"context": "Hà Nội ngày mốt", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(day_after, today=today)
    assert timing.start_date == today + timedelta(days=2)

    next_sat = request().model_copy(update={"context": "Hà Nội thứ bảy tuần sau", "thoi_luong": "nhieu_ngay"})
    timing = planner._trip_timing(next_sat, today=today)
    assert timing.start_date == today + timedelta(days=(5 - today.weekday()) % 7 + 7)
    assert timing.date_label == "Thứ 7"

    this_sat = request().model_copy(update={"context": "Hà Nội thứ bảy", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(this_sat, today=today)
    expected = (5 - today.weekday()) % 7
    assert timing.start_date == today + timedelta(days=expected or 7)

    next_week = request().model_copy(update={"context": "Hà Nội tuần sau", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(next_week, today=today)
    assert timing.start_date == today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    october = request().model_copy(update={"context": "Hà Nội tháng 10", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(october, today=today)
    assert timing.start_date == date(2026, 10, 1)
    assert timing.date_label == "1/10"

    bare_weekend = request().model_copy(update={"context": "cuối tuần chill và ăn ngon", "thoi_luong": "ca_ngay"})
    timing = planner._trip_timing(bare_weekend, today=today)
    assert timing.start_date is None
    assert timing.date_label is None


def test_trip_timing_prefers_structured_intent_policy_over_context_regex():
    today = date(2026, 8, 18)
    clock = request().model_copy(update={
        "context": "du lịch Hà Nội 2 giờ nhưng intent đã chuẩn hóa 15h-18h",
        "thoi_luong": "vai_gio",
        "intent_policy": {
            "schema_version": "intent-parse-v2",
            "duration": "vai_gio",
            "duration_minutes": 180,
            "time_window": {
                "start_hour": 15,
                "start_minute": 0,
                "end_hour": 18,
                "end_minute": 0,
                "minutes": 180,
                "label": "15h–18h",
            },
        },
    })
    timing = planner._trip_timing(clock, today=today)
    assert timing.start_hour == 15
    assert timing.max_minutes == 180
    assert timing.clock_label == "15h–18h"

    long_trip = request().model_copy(update={
        "context": "du lịch Hà Nội",
        "thoi_luong": "ca_ngay",
        "intent_policy": {
            "schema_version": "intent-parse-v2",
            "duration": "nhieu_ngay",
            "duration_days": 20,
        },
    })
    assert planner._trip_timing(long_trip, today=today).days == 20


def test_trip_timing_reads_day_counts_and_afternoon_windows_from_text():
    today = date(2026, 8, 18)
    three = request().model_copy(update={"context": "du lịch Hà Nội 3 ngày 2 người", "thoi_luong": "nhieu_ngay"})
    assert planner._trip_timing(three, today=today).days == 3

    thirty = request().model_copy(update={
        "context": "du lịch sai gòn 30 ngày 4 người",
        "thoi_luong": "nhieu_ngay",
        "location": {"lat": 10.7769, "lng": 106.7009},
    })
    assert planner._trip_timing(thirty, today=today).days == 30

    wrong_form = request().model_copy(update={"context": "du lịch Hà Nội 3 ngày", "thoi_luong": "ca_ngay"})
    assert planner._trip_timing(wrong_form, today=today).days == 3

    window = request().model_copy(update={"context": "du lịch Hà Nội từ 15h-18h 2 người", "thoi_luong": "vai_gio"})
    timing = planner._trip_timing(window, today=today)
    assert timing.start_hour == 15
    assert timing.max_minutes == 180


def test_hundred_day_request_is_capped_with_friendly_overflow_copy():
    today = date(2026, 8, 18)
    payload = request().model_copy(
        update={
            "context": "du lịch Hà Nội 100 ngày 2 người ngân sách 50 triệu chữa lành",
            "thoi_luong": "nhieu_ngay",
            "ngan_sach": 50_000_000,
        }
    )
    timing = planner._trip_timing(payload, today=today)
    assert timing.asked_days == 100
    assert timing.days == 30
    copy = planner._overflow_leg_copy(payload, timing.asked_days, timing.days, "Hà Nội")
    assert copy
    assert "100 ngày" in copy["note"]
    assert "30 ngày" in copy["note"]
    assert "khủng" in copy["note"]
    assert "chữa lành" in copy["note"]
    assert "Hà Nội" in copy["summary"]
    assert "50 triệu" in copy["summary"]
    assert "15 triệu" in copy["summary"]


def test_slot_limits_scale_with_requested_days():
    assert planner._min_plan_slots("nhieu_ngay", 3) == 3
    assert planner._min_plan_slots("nhieu_ngay", 30) == 30
    assert planner._max_plan_slots("nhieu_ngay", 4) >= 32
    assert planner._max_plan_slots("nhieu_ngay", 4) > 22


def test_safe_ai_intent_accepts_valid_ai_payload(monkeypatch):
    class ValidAI:
        def extract_request_intent(self, context, locale):
            return {
                "destination_text": {"value": "Hà Nội", "evidence": "user said"},
                "preferences": [{"value": "cà phê", "evidence": "coffee"}],
            }

    monkeypatch.setattr(planner, "ai_adapter", ValidAI())
    payload, source = planner._safe_ai_intent("đi Hà Nội uống cà phê", "vi")
    assert source == "ai_extracted"
    assert payload["destination_text"]["value"] == "Hà Nội"
    assert payload["preferences"] == [{"value": "cà phê", "evidence": "coffee"}]


def test_safe_ai_intent_rejects_malformed_ai_payload(monkeypatch):
    class MalformedAI:
        def extract_request_intent(self, context, locale):
            return {
                "destination_text": {"value": "Hà Nội", "evidence": "user said"},
                "preferences": "not-a-list",
            }

    monkeypatch.setattr(planner, "ai_adapter", MalformedAI())
    payload, source = planner._safe_ai_intent("đi Hà Nội", "vi")
    assert source == "rule_based_fallback"
    assert payload == {}


def test_dislike_detection_precision():
    assert "coffee" not in planner._disliked_profiles("ghé quán cà phê uống nước")
    assert "coffee" not in planner._disliked_profiles("ghé cafe checkin view đẹp")
    assert "coffee" not in planner._disliked_profiles("đi xem tranh ở bảo tàng")

    assert "coffee" in planner._disliked_profiles("không thích cà phê")
    assert "coffee" in planner._disliked_profiles("ghét cafe")
    assert "coffee" in planner._disliked_profiles("sợ cafe")
    assert "food" in planner._disliked_profiles("không muốn nhà hàng")
    assert "night" in planner._disliked_profiles("không muốn chợ đêm")


def test_dislike_hard_filter_keeps_positive_cafe_and_drops_disliked():
    cafe = next(place for place in PLACES if place.kind == "cafe")
    positive = planner._disliked_profiles("ghé quán cà phê uống nước")
    assert not planner._is_place_disliked(cafe, positive, "ghé quán cà phê uống nước")

    disliked = planner._disliked_profiles("không thích cà phê")
    assert planner._is_place_disliked(cafe, disliked, "không thích cà phê")


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


def test_planner_follows_corrected_city_after_thoi():
    req = request().model_copy(
        update={
            "context": "hà nội có những chỗ nào chơi? thôi tôi muốn đi biển cơ Nha Trang 2 ngày, 2 người",
            "thoi_luong": "nhieu_ngay",
            "nonce": "nonce-thoi-nhatrang-0001",
        }
    )
    _, _, destination_label = planner._destination_context(req)
    assert destination_label == "Nha Trang"


def test_yen_tu_plan_is_not_quang_ninh_beach():
    req = request().model_copy(
        update={
            "context": "tôi mệt quá tôi stress quá tôi muốn đi biển tôi muốn leo núi t muốn đi núi yên tử 4 người, 2 ngày",
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 4,
            "nonce": "nonce-yen-tu-not-beach-0001",
            "intent_policy": {
                "schema_version": "intent-parse-v2",
                "primary_intent": "mountain",
                "planner_mode": "multi_day_trip",
                "allowed_place_themes": ["mountain", "trekking", "viewpoint", "nature"],
                "avoid_place_themes": ["museum", "urban_landmark"],
            },
        }
    )
    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "Yên Tử"
    assert abs(destination_lat - 21.1506) < 0.05
    assert abs(destination_lng - 106.7189) < 0.05
    title = planner._plan_title(destination_label, req, 2)
    assert "Yên Tử" in title
    assert "biển" not in title
    assert "Quảng Ninh" not in title

    plan = build_plan(req)
    names = {slot["ten_dia_diem"] for day in plan["ngay"] for slot in day["khoang_gio"]}
    ids = {slot["dia_diem_id"] for day in plan["ngay"] for slot in day["khoang_gio"]}
    folded_names = {planner._ascii_fold(name) for name in names}
    assert "curated-yen-tu" in ids
    assert any("yen tu" in key for key in folded_names)
    assert not any("hai phong" in key or "vuon hoa cheo" in key or "bai tho" in key or "cat ba" in key for key in folded_names)
    assert "Yên Tử" in plan["tieu_de"]
    assert "biển" not in plan["tieu_de"]
    sight_slots = [
        slot
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
        if not slot.get("bua_an")
    ]
    def minutes(slot):
        start = slot["bat_dau"].split(":")
        end = slot["ket_thuc"].split(":")
        return int(end[0]) * 60 + int(end[1]) - (int(start[0]) * 60 + int(start[1]))
    mountain_slots = [
        slot for slot in sight_slots
        if "yen tu" in planner._ascii_fold(slot.get("ten_dia_diem") or "")
        or "bao ton" in planner._ascii_fold(slot.get("ten_dia_diem") or "")
        or "thien vien" in planner._ascii_fold(slot.get("ten_dia_diem") or "")
    ]
    assert mountain_slots
    assert max(minutes(slot) for slot in mountain_slots) >= 150


def test_yen_tu_attraction_is_not_treated_as_bare_city():
    yen = next(place for place in PLACES if place.id == "curated-yen-tu")
    assert planner._is_bare_city_place(yen) is False
    assert planner._looks_like_non_travel_business(yen) is False


def test_mountain_visits_use_half_or_full_day_windows():
    req = request().model_copy(update={"thoi_luong": "nhieu_ngay", "context": "leo núi Yên Tử 2 ngày"})
    yen = next(place for place in PLACES if place.id == "curated-yen-tu")
    monastery = next(place for place in PLACES if place.id == "curated-yen-tu-thien-vien")
    cable = next(place for place in PLACES if place.id == "curated-yen-tu-cap-treo")
    cafe = next((place for place in PLACES if place.kind == "cafe"), PLACES[0])
    assert planner._visit_minutes_for(yen, None, req) >= 240
    assert planner._visit_minutes_for(monastery, None, req) >= 180
    assert planner._visit_minutes_for(cable, None, req) <= 60
    if cafe.kind == "cafe":
        assert planner._visit_minutes_for(cafe, None, req) < 120

    reserve = replace(
        yen,
        id="osm-tay-yen-tu",
        name="Khu bảo tồn thiên nhiên Tây Yên Tử",
        kind="dia_danh",
        tags=("nui", "ngoai_troi"),
        duration_min=60,
        source="OpenStreetMap",
    )
    assert planner._visit_minutes_for(reserve, None, req) >= 180
    day_start = planner.datetime(2026, 8, 19, 8, 0)
    bounds = planner._compute_slot_bounds(
        reserve, None, day_start, day_start, day_start.replace(hour=17), req
    )
    assert bounds is not None
    start, end, visit = bounds
    assert visit >= 150
    assert end > day_start.replace(hour=10, minute=30)

    details = planner._enrich_visit_durations([yen, monastery, cable], req, {})
    assert details[yen.id]["thoi_luong_phut"] >= 180
    assert details[cable.id]["thoi_luong_phut"] <= 60


def test_other_provinces_select_famous_tourism_anchors():
    provinces_to_test = [
        ("tôi muốn du lịch Huế 1 ngày", "Huế", {"Đại Nội Huế", "Chùa Thiên Mụ", "Lăng Khải Định", "Lăng Tự Đức"}),
        ("du lịch Đà Lạt cuối tuần ngắm hoa", "Đà Lạt", {"Thung lũng Tình Yêu", "Đỉnh Langbiang", "Hồ Xuân Hương", "Chùa Linh Phước", "Dinh III Bảo Đại"}),
        ("đi tour Ninh Bình khám phá hang động", "Ninh Bình", {"Quần thể danh thắng Tràng An", "Chùa Bái Đính", "Tam Cốc – Bích Động", "Hang Múa"}),
        ("du lịch Cần Thơ miền tây sông nước", "Cần Thơ", {"Chợ nổi Cái Răng", "Bến Ninh Kiều", "Nhà cổ Bình Thủy"}),
        ("nghỉ dưỡng vịnh Hạ Long 1 ngày", "Hạ Long", {"Vịnh Hạ Long", "Hang Sửng Sốt", "Đảo Ti Tốp"}),
        ("đi Sa Pa săn mây và leo núi", "Sa Pa", {"Đỉnh Fansipan Legend", "Bản Cát Cát", "Nhà thờ Đá Sa Pa"}),
    ]

    for prompt, expected_label, expected_anchors in provinces_to_test:
        req = PlanRequest.model_validate(
            {
                "context": prompt,
                "location": {"lat": 21.0285, "lng": 105.8542}, # Form default coord
                "thoi_luong": "ca_ngay",
                "so_nguoi": 2,
                "ngan_sach": 2_000_000,
                "ma_phien": "test-multicity-session",
                "nonce": f"nonce-test-{expected_label}-001",
            }
        )
        destination_lat, destination_lng, destination_label = planner._destination_context(req)
        assert destination_label == expected_label, f"Failed resolving label for prompt: {prompt}"

        plan = build_plan(req)
        slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
        names = {slot["ten_dia_diem"] for slot in slots}

        # Must include at least 1-2 iconic landmarks from our curated famous anchor list
        assert names.intersection(expected_anchors), f"Expected at least one of {expected_anchors} in {names} for {expected_label}"
        assert all(
            planner.haversine_km(destination_lat, destination_lng, slot["toa_do"]["lat"], slot["toa_do"]["lng"])
            <= planner.DESTINATION_RADIUS_KM
            for slot in slots
        ), f"Some stops exceeded radius in {expected_label}"


def test_ha_long_three_day_plan_uses_famous_stops_once():
    req = PlanRequest.model_validate(
        {
            "context": "du lịch Hạ Long 3 ngày 2 người",
            "location": {"lat": 20.9712, "lng": 107.0448},
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 2,
            "ngan_sach": 5_000_000,
            "ma_phien": "test-halong-3day",
            "nonce": "nonce-halong-3day-famous-0001",
        }
    )
    destination_lat, destination_lng, destination_label = planner._destination_context(req)
    assert destination_label == "Hạ Long"

    plan = build_plan(req)
    assert len(plan["ngay"]) == 3
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    names = [slot["ten_dia_diem"] for slot in slots]
    ids = [slot["dia_diem_id"] for slot in slots]
    assert len(ids) == len(set(ids))
    titop_slots = [name for name in names if place_match_key(name) == "titop"]
    assert len(titop_slots) <= 1
    famous_anchors = {
        "Vịnh Hạ Long",
        "Hang Sửng Sốt",
        "Đảo Ti Tốp",
        "Đảo Titop",
        "Động Thiên Cung",
        "Hang Đầu Gỗ",
        "Hang Luồn",
        "Bãi Cháy",
        "Núi Bài Thơ",
        "Bảo tàng Quảng Ninh",
    }
    assert set(names).intersection(famous_anchors), f"expected famous Ha Long stops, got {names}"
    obscure = {"High long mountain", "Thay Cave", "Bãi tắm Quảng Hồng"}
    assert not set(names).intersection(obscure)
    cat_co = [name for name in names if "cát cỏ" in name.casefold() or "cat co" in place_match_key(name)]
    assert len(cat_co) <= 1
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


def test_llm_place_names_outside_catalog_are_ignored(monkeypatch):
    def draft_external(context: str, count: int, locale: str):
        return [
            {"name": "Imaginary Verified Park", "kind": "dia_danh", "why": "not in catalog"}
            for _ in range(count)
        ]

    external = Place(
        "osm-verified-node-999",
        "Imaginary Verified Park",
        "dia_danh",
        "Hà Nội",
        21.0285,
        105.8542,
        0,
        60,
        ("osm_verified",),
        7,
        22,
        "Nominatim",
        "https://www.openstreetmap.org/node/999",
    )
    monkeypatch.setattr(planner.ai_adapter, "draft_itinerary_places", draft_external)
    monkeypatch.setattr(planner, "verify_place_name", lambda name, origin: external)

    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày",
                "nonce": "nonce-ignore-external-llm-place-0001",
            }
        )
    )

    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    assert external.id not in {slot["dia_diem_id"] for slot in slots}


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
    assert evidence["xep_hang"]["ho_so_hanh_vi"]["version"] == 0
    assert evidence["xep_hang"]["ho_so_hanh_vi"]["tin_hieu_tag"] == 0
    assert evidence["du_lieu"]["nguon"]
    assert evidence["du_lieu"]["co_toa_do"] is True
    assert evidence["xep_hang"]["thanh_phan"]["diem_danh_gia"] == 40
    assert evidence["xep_hang"]["thanh_phan"]["so_nhan_xet"] == 20
    assert {"rating", "so_review"} <= set(evidence["xep_hang"]["du_lieu_thieu"])
    assert evidence["xep_hang"]["du_lieu_thuc_te"] == {"rating": None, "so_nhan_xet": None}
    assert evidence["thoi_diem"]["ly_do"]


def test_ranking_evidence_uses_fixed_five_factor_formula_with_missing_fallbacks():
    req = request().model_copy(update={"context": "thích lịch sử và chữa lành"})
    profiles = planner._intent_profiles(planner.relevant_tags(req.context))
    place = Place(
        id="formula-place",
        name="Formula Museum",
        kind="bao_tang",
        area="Hà Nội",
        lat=req.location.lat,
        lng=req.location.lng,
        cost=50_000,
        duration_min=90,
        tags=("lich_su", "healing"),
        open_hour=8,
        close_hour=18,
        source="test",
    )
    object.__setattr__(place, "rating", 4.5)
    object.__setattr__(place, "review_count", 1000)

    evidence = planner._ranking_evidence(
        place,
        req,
        planner.relevant_tags(req.context),
        profiles,
        req.location.lat,
        req.location.lng,
    )

    assert evidence["thanh_phan"] == {
        "muc_phu_hop": 100,
        "diem_danh_gia": 90,
        "vi_tri_khoang_cach": 100,
        "khop_gio_mo_cua": 100,
        "so_nhan_xet": 100,
    }
    assert evidence["diem_tong"] == 97.5

    missing_evidence = planner._ranking_evidence(
        Place(
            id="missing-place",
            name="Missing Rating Place",
            kind="dia_danh",
            area="Hà Nội",
            lat=req.location.lat + 0.02,
            lng=req.location.lng,
            cost=0,
            duration_min=60,
            tags=(),
            open_hour=8,
            close_hour=18,
            source="test",
        ),
        req,
        set(),
        [],
        req.location.lat,
        req.location.lng,
    )
    assert missing_evidence["thanh_phan"]["diem_danh_gia"] == 40
    assert missing_evidence["thanh_phan"]["so_nhan_xet"] == 20
    assert {"rating", "so_review"} <= set(missing_evidence["du_lieu_thieu"])


def test_place_model_keeps_google_rating_review_and_maps_source():
    req = request()
    place = Place(
        id="google-backed-place",
        name="Google Backed Place",
        kind="dia_danh",
        area="Hoàn Kiếm",
        lat=req.location.lat,
        lng=req.location.lng,
        cost=0,
        duration_min=60,
        tags=("view_dep",),
        open_hour=8,
        close_hour=18,
        source="OpenStreetMap",
        source_url="https://www.openstreetmap.org/node/1",
        rating=4.7,
        review_count=1200,
        google_place_id="google-place-1",
        google_maps_url="https://maps.google.com/?cid=1",
    )

    evidence = planner._ranking_evidence(
        place,
        req,
        planner.relevant_tags(req.context),
        planner._intent_profiles(planner.relevant_tags(req.context)),
        req.location.lat,
        req.location.lng,
    )
    source_url, source_label = source_for(place)

    assert evidence["du_lieu_thuc_te"] == {"rating": 4.7, "so_nhan_xet": 1200}
    assert "rating" not in evidence["du_lieu_thieu"]
    assert "so_review" not in evidence["du_lieu_thieu"]
    assert source_url == "https://maps.google.com/?cid=1"
    assert source_label == "google_places_source"


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
    assert timing["lich_nghi_le"]["gio_mo_cua_can_xac_minh"] is True
    assert "Chợ đêm" in " ".join(timing["quy_tac"])
    slots = [slot for day in plan["ngay"] for slot in day["khoang_gio"]]
    assert all(slot["gio_mo_cua"]["trang_thai_xac_minh"] == "holiday_hours_warning" for slot in slots)
    assert all(
        slot["bang_chung"]["thoi_diem"]["lich_nghi_le"]["ma"] == "quoc_khanh"
        for slot in slots
    )


def test_tet_plan_does_not_treat_normal_hours_as_release_evidence():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội dịp Tết Nguyên đán",
                "ngay_di": date(2026, 2, 17),
                "nonce": "nonce-tet-holiday-hours-0001",
            }
        )
    )

    timing = plan["tieu_chi_thoi_diem"]["lich_nghi_le"]
    assert timing["ma"] == "tet_nguyen_dan"
    assert timing["khong_dung_gio_thuong_lam_bang_chung_phat_hanh"] is True
    blockers = plan["danh_gia_chat_luong"]["cong_phat_hanh"]["chan_bo"]
    assert any("Tết Nguyên đán" in blocker for blocker in blockers)
    for slot in [slot for day in plan["ngay"] for slot in day["khoang_gio"]]:
        assert slot["gio_mo_cua"]["trang_thai_xac_minh"] == "holiday_hours_required_before_release"
        holiday = slot["bang_chung"]["thoi_diem"]["lich_nghi_le"]
        assert holiday["ma"] == "tet_nguyen_dan"
        assert holiday["gio_mo_cua_can_xac_minh"] is True
        assert "giờ mở cửa ngày lễ/Tết cần xác minh" in slot["giai_thich"]


def test_seasonal_festival_policy_is_recorded_for_focus_city():
    plan = build_plan(
        PlanRequest.model_validate(
            {
                "context": "du lịch Đà Nẵng mùa biển",
                "location": {"lat": 16.0544, "lng": 108.2022},
                "thoi_luong": "ca_ngay",
                "so_nguoi": 2,
                "ngan_sach": 1_000_000,
                "ma_phien": "test-session",
                "ngay_di": date(2026, 6, 15),
                "nonce": "nonce-seasonal-policy-0001",
            }
        )
    )

    seasonal = plan["tieu_chi_thoi_diem"]["mua_vu_le_hoi"]
    assert seasonal["co_san"] is True
    assert seasonal["diem_den"] == "Đà Nẵng"
    assert seasonal["trang_thai"] == "recommended_season"
    assert seasonal["thang"] == 6
    assert "lễ hội pháo hoa" in " ".join(seasonal["ghi_chu_le_hoi"]).lower()
    assert "Mùa vụ/lễ hội" in " ".join(plan["tieu_chi_thoi_diem"]["quy_tac"])


def test_sunset_context_is_computed_and_attached_to_timing_evidence():
    sunset = sunset_for_date(date(2026, 9, 2), 21.0285, 105.8542)

    assert sunset["co_san"] is True
    assert sunset["nguon"] == "noaa_solar_position_approximation"
    assert 17 * 60 <= sunset["hoang_hon_phut"] <= 19 * 60

    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội Hồ Tây ngắm hoàng hôn",
                "ngay_di": date(2026, 9, 2),
                "nonce": "nonce-sunset-context-0001",
            }
        )
    )

    timing = plan["tieu_chi_thoi_diem"]
    assert timing["thien_van"]["co_san"] is True
    assert timing["thien_van"]["hoang_hon"] == sunset["hoang_hon"]
    assert "hoàng hôn" in " ".join(timing["quy_tac"])
    slot_timing = [
        slot["bang_chung"]["thoi_diem"]
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
    ]
    assert all(item["thien_van"]["nguon"] == "noaa_solar_position_approximation" for item in slot_timing)

    ho_tay = next(place for place in PLACES if place.id == "curated-ho-tay")
    sunset_start = datetime(2026, 9, 2, 17, 15)
    evidence = planner._slot_evidence(ho_tay, request(), sunset_start, None, None, sunset)
    assert evidence["thoi_diem"]["thien_van"]["gan_hoang_hon"] is True
    assert "hoàng hôn" in evidence["thoi_diem"]["ly_do"]


def test_traffic_peak_policy_is_recorded_in_plan_and_travel_evidence():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày, đi lại hợp lý",
                "nonce": "nonce-traffic-peak-policy-0001",
            }
        )
    )

    peak_policy = plan["tieu_chi_thoi_diem"]["gio_cao_diem"]
    assert peak_policy["trang_thai"] == "heuristic_no_live_traffic"
    assert {window["ten"] for window in peak_policy["khung_gio"]} == {
        "cao_diem_sang",
        "cao_diem_chieu",
    }

    legs = [
        slot["di_chuyen_tu_diem_truoc"]
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
        if slot.get("di_chuyen_tu_diem_truoc")
    ]
    assert legs
    assert all(leg["gio_cao_diem"]["nguon"] == "quy_tac_noi_bo_gio_cao_diem_do_thi_viet_nam" for leg in legs)

    assert planner._traffic_peak_for_clock("08:15")["khung"] == "cao_diem_sang"
    assert planner._traffic_peak_for_clock("17:30")["khung"] == "cao_diem_chieu"
    assert planner._traffic_peak_for_clock("11:00")["trong_gio_cao_diem"] is False


def test_lodging_coordinates_are_used_as_route_anchor(monkeypatch):
    captured: dict[str, tuple[float, float]] = {}
    original_ordered_route = planner._ordered_route
    lodging = {"lat": 21.0401, "lng": 105.7902}

    def capture_route(places, origin):
        captured["origin"] = origin
        return original_ordered_route(places, origin)

    monkeypatch.setattr(planner, "_ordered_route", capture_route)
    plan = build_plan(
        PlanRequest.model_validate(
            request().model_dump(mode="json")
            | {
                "context": "du lịch Hà Nội cả ngày",
                "noi_luu_tru": lodging,
                "ten_noi_luu_tru": "<b>Khách sạn Hồ Tây</b>",
                "nonce": "nonce-lodging-anchor-0001",
            }
        )
    )

    assert captured["origin"] == (lodging["lat"], lodging["lng"])
    lodging_context = plan["rang_buoc_luu_tru"]
    assert lodging_context["co_noi_luu_tru"] is True
    assert lodging_context["ten"] == "bKhách sạn Hồ Tây/b"
    assert lodging_context["toa_do"] == lodging
    assert lodging_context["nguon"] == "plan_request.noi_luu_tru"


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


def test_osm_night_market_name_still_has_evening_floor():
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


def test_place_name_dedupe_collapses_titop_spelling_twins():
    first = replace(PLACES[0], id="curated-dao-ti-top", name="Đảo Ti Tốp")
    twin = replace(PLACES[0], id="curated-dao-titop", name="Đảo Titop")
    distinct = replace(PLACES[0], id="curated-hang-sung-sot", name="Hang Sửng Sốt")
    deduped = planner._dedupe_places([first, twin, distinct])
    assert len(deduped) == 2
    assert planner._name_taken(twin, planner._place_name_keys(first))
    names = {place.name for place in deduped}
    assert "Hang Sửng Sốt" in names
    assert len({place_match_key(name) for name in names if place_match_key(name) == "titop"}) == 1


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
    planner._places_near.cache_clear()


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
    previous = replace(PLACES[0], id="previous", name="Điểm đầu", kind="dia_danh", lat=21.0285, lng=105.8542, open_hour=7, close_hour=22, source="curated")
    following = replace(PLACES[0], id="following", name="Điểm cuối", kind="dia_danh", lat=21.0290, lng=105.8545, open_hour=7, close_hour=22, source="curated")
    cannot_fit = replace(PLACES[0], id="cannot-fit", name="Không vừa giờ", kind="dia_danh", lat=21.0287, lng=105.8543, open_hour=7, close_hour=22, source="curated")
    fits = replace(PLACES[0], id="fits", name="Điểm thay thế", kind="dia_danh", lat=21.0288, lng=105.8544, open_hour=7, close_hour=22, source="curated")
    monkeypatch.setattr(planner, "PLACES", [previous, following, cannot_fit, fits])
    planner._places_near.cache_clear()

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


def test_cp_sat_feasibility_rejects_missing_travel_gap():
    a = Place("cp-a", "A", "dia_danh", "Ha Noi", 21.0, 105.8, 0, 60, (), 8, 22, "test")
    b = Place("cp-b", "B", "dia_danh", "Ha Noi", 21.01, 105.81, 0, 60, (), 8, 22, "test")
    plan = {
        "ngay": [
            {
                "khoang_gio": [
                    {"dia_diem_id": "cp-a", "bat_dau": "08:00", "ket_thuc": "09:00"},
                    {"dia_diem_id": "cp-b", "bat_dau": "09:00", "ket_thuc": "10:00"},
                ]
            }
        ]
    }

    result = verify_fixed_schedule_with_cp_sat(plan, {"cp-a": a, "cp-b": b}, lambda _a, _b: 30)

    assert result.available is True
    assert result.feasible is False
    assert result.blockers == ("cp_sat_infeasible",)


def test_cp_sat_candidate_selection_respects_budget_and_count():
    cheap_good = Place(
        id="sel-a", name="A", kind="dia_danh", area="Hà Nội", lat=21.0, lng=105.8,
        cost=20_000, duration_min=60, tags=("view_dep",), source="OpenStreetMap",
    )
    expensive_best = Place(
        id="sel-b", name="B", kind="dia_danh", area="Hà Nội", lat=21.0, lng=105.81,
        cost=200_000, duration_min=60, tags=("view_dep",), source="OpenStreetMap",
    )
    cheap_ok = Place(
        id="sel-c", name="C", kind="dia_danh", area="Hà Nội", lat=21.0, lng=105.82,
        cost=30_000, duration_min=60, tags=("view_dep",), source="OpenStreetMap",
    )

    result = select_places_with_cp_sat(
        [cheap_good, expensive_best, cheap_ok],
        2,
        60_000,
        {"sel-a": 80, "sel-b": 100, "sel-c": 70},
    )

    assert result.available is True
    assert set(result.selected_ids) == {"sel-a", "sel-c"}
    assert result.objective_score == 150


def test_cp_sat_order_optimizer_minimizes_travel_from_origin():
    a = Place("ord-a", "A", "dia_danh", "Ha Noi", 21.0, 105.8, 0, 60, (), 8, 22, "test")
    b = Place("ord-b", "B", "dia_danh", "Ha Noi", 21.0, 105.9, 0, 60, (), 8, 22, "test")
    c = Place("ord-c", "C", "dia_danh", "Ha Noi", 21.0, 106.0, 0, 60, (), 8, 22, "test")
    origin_minutes = {"ord-a": 1, "ord-b": 50, "ord-c": 60}
    pair_minutes = {
        ("ord-a", "ord-b"): 1,
        ("ord-b", "ord-c"): 1,
        ("ord-a", "ord-c"): 60,
        ("ord-c", "ord-b"): 1,
        ("ord-b", "ord-a"): 1,
        ("ord-c", "ord-a"): 60,
    }

    result = optimize_order_with_cp_sat(
        [c, b, a],
        (21.0, 105.8),
        lambda _origin, place: origin_minutes[place.id],
        lambda left, right: pair_minutes[(left.id, right.id)],
    )

    assert result.available is True
    assert result.ordered_ids == ("ord-a", "ord-b", "ord-c")
    assert result.objective_travel_minutes == 3


def test_cp_sat_day_schedule_jointly_selects_times_and_respects_travel_budget():
    a = Place("day-a", "A", "dia_danh", "Ha Noi", 21.0, 105.8, 20_000, 60, (), 8, 12, "test")
    b = Place("day-b", "B", "dia_danh", "Ha Noi", 21.0, 105.81, 30_000, 60, (), 9, 18, "test")
    c = Place("day-c", "C", "dia_danh", "Ha Noi", 21.0, 105.82, 200_000, 60, (), 9, 18, "test")

    result = optimize_day_schedule_with_cp_sat(
        [a, b, c],
        8 * 60,
        12 * 60,
        {"day-a": 60, "day-b": 60, "day-c": 60},
        {"day-a": 80, "day-b": 70, "day-c": 100},
        lambda _left, _right: 30,
        min_places=2,
        max_places=2,
        budget_per_person=60_000,
    )

    assert result.available is True
    assert result.feasible is True
    assert result.selected_ids == ("day-a", "day-b")
    assert 8 * 60 <= result.starts["day-a"] <= 11 * 60
    assert result.starts["day-b"] >= result.starts["day-a"] + 90


def test_cp_sat_day_schedule_fails_when_time_windows_cannot_fit():
    a = Place("tight-a", "A", "dia_danh", "Ha Noi", 21.0, 105.8, 0, 90, (), 8, 10, "test")
    b = Place("tight-b", "B", "dia_danh", "Ha Noi", 21.0, 105.81, 0, 90, (), 8, 10, "test")

    result = optimize_day_schedule_with_cp_sat(
        [a, b],
        8 * 60,
        10 * 60,
        {"tight-a": 90, "tight-b": 90},
        {"tight-a": 80, "tight-b": 70},
        lambda _left, _right: 45,
        min_places=2,
        max_places=2,
        budget_per_person=100_000,
    )

    assert result.available is True
    assert result.feasible is False
    assert result.blockers == ("cp_sat_day_schedule_infeasible",)


def test_planner_uses_cp_sat_candidate_selection_when_llm_is_unavailable(monkeypatch):
    monkeypatch.setattr(planner.ai_adapter, "draft_itinerary_places", None, raising=False)
    monkeypatch.setattr(planner.ai_adapter, "propose_place_ids", None, raising=False)

    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày văn hóa lịch sử",
                "nonce": "nonce-cp-sat-selection-plan-0001",
            }
        )
    )

    evidence = plan["bo_giai_chon_ung_vien"]
    assert evidence["phuong_phap"] in {
        "ortools_cp_sat_day_joint_selection",
        "ortools_cp_sat_selection",
    }
    assert evidence["thu_vien"] == "ortools.sat.python.cp_model"
    assert evidence["so_ung_vien_xet"] <= evidence["gioi_han_ung_vien"]
    if evidence["phuong_phap"] == "ortools_cp_sat_day_joint_selection":
        assert evidence["gioi_han_ung_vien"] == 80
        assert "time_window" in evidence["vai_tro"]
        assert "travel" in evidence["vai_tro"]
        assert "budget" in evidence["vai_tro"]
        assert evidence["suggested_starts"]
    else:
        assert evidence["sap_thu_tu"]["phuong_phap"] == "ortools_cp_sat_order"
        assert evidence["sap_thu_tu"]["objective_travel_minutes"] is not None


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


def test_afternoon_window_creates_short_hanoi_plan():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội từ 15h-18h 2 người",
                "thoi_luong": "vai_gio",
                "nonce": "nonce-afternoon-window-0001",
            }
        )
    )
    assert len(plan["ngay"]) == 1
    slots = plan["ngay"][0]["khoang_gio"]
    assert 2 <= len(slots) <= 5
    assert slots[0]["bat_dau"] >= "15:00"
    assert slots[-1]["ket_thuc"] <= "18:00"
    assert slots[-1]["ket_thuc"] >= "17:20"


def test_three_day_hanoi_request_keeps_three_days():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội 3 ngày 2 người",
                "thoi_luong": "nhieu_ngay",
                "nonce": "nonce-hanoi-3-days-0001",
            }
        )
    )
    assert len(plan["ngay"]) == 3


def test_wizard_bare_day_count_is_not_collapsed_to_two_days():
    ten = request().model_copy(
        update={
            "context": "đi Hà Nội\n10\n2 người",
            "thoi_luong": "nhieu_ngay",
            "nonce": "nonce-hanoi-wizard-10-days-0001",
        }
    )
    assert planner._trip_timing(ten).days == 10

    five = request().model_copy(
        update={
            "context": "đi biển Phú Quốc\n5\n2 người",
            "location": {"lat": 10.2899, "lng": 103.984},
            "thoi_luong": "nhieu_ngay",
            "so_nguoi": 2,
            "nonce": "nonce-phu-quoc-wizard-5-days-0001",
        }
    )
    assert planner._trip_timing(five).days == 5


def test_multi_day_hanoi_ignores_stale_short_time_window():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội 3 ngày 2 người",
                "thoi_luong": "nhieu_ngay",
                "nonce": "nonce-hanoi-3-days-stale-window-0001",
                "intent_policy": {
                    "schema_version": "intent-parse-v2",
                    "duration": "nhieu_ngay",
                    "duration_days": 3,
                    "duration_minutes": 180,
                    "time_window": {
                        "start_hour": 15,
                        "start_minute": 0,
                        "end_hour": 18,
                        "end_minute": 0,
                        "minutes": 180,
                        "label": "15h–18h",
                    },
                },
            }
        )
    )
    assert len(plan["ngay"]) == 3
    assert plan["ngay"][0]["khoang_gio"][0]["bat_dau"] < "15:00"


def test_four_day_hanoi_request_keeps_four_days():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội 4 ngày 2 người",
                "thoi_luong": "nhieu_ngay",
                "nonce": "nonce-hanoi-4-days-0001",
            }
        )
    )
    assert len(plan["ngay"]) == 4


def test_thirty_day_hanoi_request_keeps_thirty_days():
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội 30 ngày 2 người",
                "thoi_luong": "nhieu_ngay",
                "so_nguoi": 2,
                "nonce": "nonce-hanoi-30-days-0001",
            }
        )
    )
    assert len(plan["ngay"]) == 30
    assert all(day["khoang_gio"] for day in plan["ngay"])
    day_counts = [len(day["khoang_gio"]) for day in plan["ngay"]]
    assert max(day_counts) <= 7
    assert day_counts[0] <= 7


def test_chunk_sights_spreads_long_trips_instead_of_front_loading():
    sights = [
        Place(
            f"sight-{index}",
            f"Điểm {index}",
            "dia_danh",
            "Hà Nội",
            21.02 + (index % 6) * 0.008,
            105.84 + (index // 6) * 0.008,
            0,
            60,
            ("view",),
        )
        for index in range(40)
    ]
    chunks = planner._chunk_sights_by_day(sights, 20)
    assert len(chunks) == 20
    sizes = [len(chunk) for chunk in chunks]
    assert sum(sizes) == 40
    assert min(sizes) >= 1
    assert max(sizes) <= 3


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


def test_planner_can_use_llm_first_catalog_places_after_verification(monkeypatch):
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
    assert "LLM Verified Stop" not in place_names
    assert {"Hồ Gươm", "Hồ Tây", "Lăng Chủ tịch Hồ Chí Minh"} <= place_names


def test_llm_first_details_are_used_in_slot_copy(monkeypatch):
    class DraftingAI:
        def draft_itinerary_places(self, context, count, locale):
            return [
                {
                    "name": "Hồ Gươm",
                    "kind": "dia_danh",
                    "why": "Start here because it gives the trip a clear story.",
                    "activity": "Spend time on the main walk, photo spot, and nearby side streets.",
                    "tip": "Go before the busiest window.",
                    "meal": "Try a nearby street snack.",
                    "transport": "Walk to the next Old Quarter stop.",
                },
                {"name": "Hồ Tây", "kind": "dia_danh", "why": "icon"},
                {"name": "Lăng Chủ tịch Hồ Chí Minh", "kind": "dia_danh", "why": "icon"},
                {"name": "Cà phê phố cổ", "kind": "cafe", "why": "break"},
                {"name": "Phố cổ Hà Nội", "kind": "dia_danh", "why": "evening walk"},
                {"name": "Phố Tạ Hiện", "kind": "dia_danh", "why": "nightlife"},
            ][:count]

        def assemble(self, draft, trusted_ids, locale):
            return draft

    def fake_verify(name, origin):
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
        if slot["ten_dia_diem"] == "Hồ Gươm"
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
        assert slot["nguon_url"] == source_for(place)[0]
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
