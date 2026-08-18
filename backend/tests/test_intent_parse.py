from app.pipeline.intent_parse import parse_intent


def ai(payload):
    def extractor(_context: str, _locale: str = "vi"):
        return payload
    return extractor


def test_parse_intent_understands_long_trip_durations():
    three = parse_intent(
        "du lịch Hà Nội 3 ngày 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "duration_value": 3, "duration_unit": "day", "people": 2}),
    )
    assert three["parsed"]["destination"]["name"] == "Hà Nội"
    assert three["parsed"]["duration"] == "nhieu_ngay"
    assert three["parsed"]["duration_days"] == 3
    assert three["parsed"]["planner_mode"] == "multi_day_trip"
    assert three["parsed"]["people"] == 2

    thirty = parse_intent(
        "du lịch Sài Gòn 30 ngày 4 người",
        extractor=ai({"destination_text": "Sài Gòn", "trip_purpose": "general_travel", "duration_value": 30, "duration_unit": "day", "people": 4}),
    )
    assert thirty["parsed"]["destination"]["name"] == "TP.HCM"
    assert thirty["parsed"]["duration_days"] == 30
    assert thirty["parsed"]["planner_mode"] == "long_trip"

    twenty = parse_intent(
        "du lịch Đà Nẵng 20 ngày 2 người",
        extractor=ai({"destination_text": "Đà Nẵng", "trip_purpose": "general_travel", "duration_value": 20, "duration_unit": "day", "people": 2}),
    )
    assert twenty["parsed"]["duration_days"] == 20
    assert twenty["parsed"]["planner_mode"] == "long_trip"

    two_weeks = parse_intent(
        "đi Đà Nẵng 2 tuần 2 người",
        extractor=ai({"destination_text": "Đà Nẵng", "trip_purpose": "general_travel", "duration_value": 2, "duration_unit": "week", "people": 2}),
    )
    assert two_weeks["parsed"]["duration_days"] == 14
    assert two_weeks["parsed"]["planner_mode"] == "long_trip"


def test_parse_intent_understands_vietnamese_time_windows():
    compact = parse_intent(
        "du lịch Hà Nội 15h-18h 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "time_window": {"start_hour": 15, "start_minute": 0, "end_hour": 18, "end_minute": 0}, "people": 2}),
    )
    assert compact["parsed"]["duration"] == "vai_gio"
    assert compact["parsed"]["time_window"]["minutes"] == 180
    assert compact["parsed"]["time_window"]["label"] == "15h–18h"

    spoken = parse_intent(
        "du lịch Hà Nội 15 giờ đến 18 giờ 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "time_window": {"start_hour": 15, "end_hour": 18}, "people": 2}),
    )
    assert spoken["parsed"]["duration"] == "vai_gio"
    assert spoken["parsed"]["time_window"]["minutes"] == 180


def test_parse_intent_reports_invalid_time_windows():
    too_short = parse_intent(
        "du lịch Hà Nội 10h-10h20 2 người",
        extractor=ai({"destination_text": "Hà Nội", "time_window": {"start_hour": 10, "start_minute": 0, "end_hour": 10, "end_minute": 20}, "people": 2}),
    )
    assert too_short["status"] == "ask_user_missing_fields"
    assert too_short["parsed"]["destination"]["name"] == "Hà Nội"
    assert too_short["validation_errors"][0]["code"] == "time_window_too_short"
    assert "duration" in too_short["missing_fields"]

    too_long = parse_intent(
        "du lịch Hà Nội 1h-23h 2 người",
        extractor=ai({"destination_text": "Hà Nội", "time_window": {"start_hour": 1, "start_minute": 0, "end_hour": 23, "end_minute": 0}, "people": 2}),
    )
    assert too_long["validation_errors"][0]["code"] == "time_window_too_long"
    assert "nhiều ngày" in too_long["question"]


def test_parse_intent_handles_tiny_and_ambiguous_duration():
    half_hour = parse_intent(
        "đi Hà Nội 0,5h 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "duration_value": 0.5, "duration_unit": "hour", "people": 2}),
    )
    assert half_hour["status"] == "ask_user_missing_fields"
    assert half_hour["parsed"]["planner_mode"] == "micro_visit"
    assert half_hour["parsed"]["duration_minutes"] == 30
    assert half_hour["validation_errors"][0]["code"] == "duration_too_short_for_itinerary"

    thirty_minutes = parse_intent(
        "đi Hà Nội 30p 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "duration_value": 30, "duration_unit": "minute", "people": 2}),
    )
    assert thirty_minutes["parsed"]["duration_minutes"] == 30
    assert "duration" in thirty_minutes["missing_fields"]

    ambiguous = parse_intent(
        "đi Hà Nội 10h 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "people": 2, "ambiguities": [{"field": "duration", "value": "10h", "reason": "could be duration or start time", "question": "Bạn muốn đi trong 10 tiếng hay bắt đầu lúc 10h?"}]}),
    )
    assert ambiguous["status"] == "ask_user_missing_fields"
    assert ambiguous["ambiguities"][0]["field"] == "duration"
    assert "10 tiếng hay bắt đầu lúc 10h" in ambiguous["question"]

    ambiguous_11h = parse_intent(
        "đi Hà Nội 11h 2 người",
        extractor=ai({"destination_text": "Hà Nội", "trip_purpose": "general_travel", "people": 2, "ambiguities": [{"field": "duration", "value": "11h", "reason": "could be duration or start time", "question": "Bạn muốn đi trong 11 tiếng hay bắt đầu lúc 11h?"}]}),
    )
    assert ambiguous_11h["ambiguities"][0]["field"] == "duration"


def test_parse_intent_suggests_destinations_for_intent_only_requests():
    healing = parse_intent("Tôi muốn đi chữa lành", extractor=ai({"trip_purpose": "healing"}))
    assert healing["status"] == "ask_user_missing_fields"
    assert "destination" in healing["missing_fields"]
    assert healing["parsed"]["primary_intent"] == "healing"
    assert healing["parsed"]["planner_mode"] == "intent_discovery"
    assert "quiet" in healing["parsed"]["allowed_place_themes"]
    assert len(healing["suggestions"]) >= 2
    assert all(item["score"] > 0 for item in healing["suggestions"])
    assert healing["suggestions"][0]["label"] == "Đà Lạt"
    assert "Đà Lạt" in healing["question"]
    assert "bạn chọn giúp" in healing["question"]

    beach = parse_intent("Tôi muốn đi biển", extractor=ai({"trip_purpose": "beach"}))
    assert beach["parsed"]["primary_intent"] == "beach"
    assert "beach" in beach["parsed"]["allowed_place_themes"]
    assert len(beach["suggestions"]) >= 2
    assert "Nha Trang" in beach["question"]

    mountain = parse_intent("Muốn đi leo núi", extractor=ai({"trip_purpose": "mountain"}))
    assert mountain["parsed"]["primary_intent"] == "mountain"
    assert "mountain" in mountain["parsed"]["allowed_place_themes"]
    assert len(mountain["suggestions"]) >= 2


def test_parse_intent_general_travel_asks_destination_without_hardcoded_intent():
    result = parse_intent("Tôi muốn đi du lịch", extractor=ai({"trip_purpose": "general_travel"}))
    assert result["status"] == "ask_user_missing_fields"
    assert result["parsed"]["primary_intent"] == "general_travel"
    assert "destination" in result["missing_fields"]
    assert len(result["suggestions"]) >= 2


def test_parse_intent_rejects_invalid_ai_schema_and_falls_back():
    result = parse_intent("du lịch Hà Nội 3 ngày 2 người", extractor=ai({"duration_unit": "century"}))
    assert result["extraction_source"] == "rules"
    assert result["parsed"]["destination"]["name"] == "Hà Nội"
    assert result["parsed"]["duration_days"] == 3
    assert result["parsed"]["people"] == 2


def test_parse_intent_rules_recognize_hanoi_without_asking_destination():
    result = parse_intent("du lịch Hà Nội", extractor=ai({"trip_purpose": "general_travel"}))
    assert result["parsed"]["destination"]["name"] == "Hà Nội"
    assert "destination" not in result["missing_fields"]
    assert "duration" in result["missing_fields"]


def test_parse_intent_rules_parse_time_windows_without_ai():
    def boom(_context: str, _locale: str = "vi"):
        raise RuntimeError("offline")

    compact = parse_intent("du lịch Hà Nội từ 15h-18h 2 người", extractor=boom)
    assert compact["parsed"]["destination"]["name"] == "Hà Nội"
    assert compact["parsed"]["duration"] == "vai_gio"
    assert compact["parsed"]["time_window"]["minutes"] == 180
    assert "duration" not in compact["missing_fields"]

    spoken = parse_intent("du lịch Hà Nội 15 giờ đến 18 giờ 2 người", extractor=boom)
    assert spoken["parsed"]["time_window"]["minutes"] == 180
    assert spoken["status"] == "ready_to_plan"

    dashed = parse_intent("du lịch Hà Nội 15h đến 18h 2 người", extractor=boom)
    assert dashed["parsed"]["time_window"]["label"] == "15h–18h"


def test_parse_intent_rules_parse_multi_day_trips_without_ai():
    def boom(_context: str, _locale: str = "vi"):
        raise RuntimeError("offline")

    three = parse_intent("du lịch Hà Nội 3 ngày 2 người", extractor=boom)
    assert three["parsed"]["duration_days"] == 3
    assert three["parsed"]["planner_mode"] == "multi_day_trip"

    thirty = parse_intent("du lịch sai gòn 30 ngày 4 người", extractor=boom)
    assert thirty["parsed"]["destination"]["name"] == "TP.HCM"
    assert thirty["parsed"]["duration_days"] == 30
    assert thirty["parsed"]["planner_mode"] == "long_trip"

    hundred = parse_intent("du lịch Hà Nội 100 ngày 2 người ngân sách 50 triệu", extractor=boom)
    assert hundred["parsed"]["duration_days"] == 100
    assert hundred["parsed"]["duration"] == "nhieu_ngay"
    assert hundred["parsed"]["planner_mode"] == "long_trip"


def test_parse_intent_does_not_invent_destination_for_theme_only_requests():
    beach = parse_intent(
        "Tôi muốn đi biển",
        extractor=ai({"destination_text": "Đà Nẵng", "trip_purpose": "beach", "duration_value": 2, "duration_unit": "day", "people": 2}),
    )
    assert beach["parsed"]["destination"] is None
    assert "destination" in beach["missing_fields"]
    assert beach["suggestions"][0]["label"] in {"Nha Trang", "Phú Quốc", "Đà Nẵng", "Vũng Tàu", "Phan Thiết"}

    mountain = parse_intent("Muốn đi leo núi", extractor=ai({"destination_text": "Đà Nẵng", "trip_purpose": "mountain"}))
    assert mountain["parsed"]["destination"] is None
    assert mountain["suggestions"][0]["label"] in {"Sa Pa", "Hà Giang", "Đà Lạt", "Ninh Bình", "Quảng Bình"}

    healing = parse_intent("Tôi muốn đi chữa lành", extractor=ai({"destination_text": "Đà Nẵng", "trip_purpose": "healing"}))
    assert healing["parsed"]["destination"] is None
    assert healing["suggestions"][0]["label"] in {"Đà Lạt", "Sa Pa", "Ninh Bình", "Phú Quốc", "Huế"}
