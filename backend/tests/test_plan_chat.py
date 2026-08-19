from types import SimpleNamespace

from app.pipeline.plan_chat import (
    classify_plan_message,
    fallback_plan_chat_reply,
    refined_plan_request,
    should_exclude_current_stops,
)

HANOI_REQUEST = {
    "context": "du lịch hà nội 14h-18h 2 người",
    "location": {"lat": 21.0285, "lng": 105.8542},
    "thoi_luong": "vai_gio",
    "so_nguoi": 2,
    "ngan_sach": 1_000_000,
    "ngon_ngu": "vi",
}


def _item():
    return SimpleNamespace(request=HANOI_REQUEST, plan={"ngay": []})


def test_classify_destination_change_rebuilds():
    assert classify_plan_message("Tôi muốn đi hạ long", _item()) == "rebuild"


def test_classify_food_request_rebuilds():
    assert classify_plan_message("tôi muốn ăn uống", _item()) == "rebuild"
    assert classify_plan_message("đổi sang ăn uống", _item()) == "rebuild"


def test_classify_new_itinerary_rebuilds_not_swap():
    item = _item()
    assert classify_plan_message("đổi cho tôi lịch trình khác", item) == "rebuild"
    assert classify_plan_message("đổi tiếp", item) == "rebuild"
    assert should_exclude_current_stops("đổi tiếp", item) is True
    assert should_exclude_current_stops("Tôi muốn đi hạ long", item) is False


def test_classify_swap_this_stop():
    assert classify_plan_message("đổi điểm này", _item(), selected_id="place-1") == "swap"


def test_classify_lunch_break_swap():
    assert classify_plan_message("tôi muốn đổi điểm nghỉ trưa", _item()) == "swap"
    assert classify_plan_message("đổi bữa trưa", _item()) == "swap"


def test_target_slot_prefers_lunch_break_over_selected_sight():
    from app.pipeline.plan_chat import target_slot_id_for_message

    plan = {
        "ngay": [
            {
                "khoang_gio": [
                    {"dia_diem_id": "sight", "ten_dia_diem": "Vườn hoa", "loai": "cong_vien", "bat_dau": "09:00"},
                    {"dia_diem_id": "lunch", "ten_dia_diem": "Cơm niêu", "loai": "nha_hang", "bua_an": "trua", "bat_dau": "12:00"},
                    {"dia_diem_id": "rest", "ten_dia_diem": "Cafe Mê", "loai": "cafe", "bua_an": "nghi", "bat_dau": "13:10"},
                ]
            }
        ]
    }
    assert target_slot_id_for_message(plan, "tôi muốn đổi điểm nghỉ trưa", selected_id="sight") == "lunch"
    assert target_slot_id_for_message(plan, "đổi bữa trưa", selected_id="sight") == "lunch"
    assert target_slot_id_for_message(plan, "đổi điểm nghỉ", selected_id="sight") == "rest"


def test_classify_nearby_and_people_rebuild():
    item = _item()
    assert classify_plan_message("chọn địa điểm gần nhau", item) == "rebuild"
    assert classify_plan_message("đi 3 người, ngân sách tối đa 500k", item) == "rebuild"


def test_refined_request_moves_destination_and_food_theme():
    dest = refined_plan_request(_item(), "Tôi muốn đi hạ long")
    assert abs(float(dest.location.lat) - 20.9712) < 0.2
    food = refined_plan_request(_item(), "đổi sang ăn uống")
    assert "ăn uống" in food.context
    assert food.intent_policy and food.intent_policy.primary_intent == "food"


def test_fallback_reply_does_not_dump_duration_codes():
    reply = fallback_plan_chat_reply(
        "rebuild",
        "vi",
        dest_name="Hạ Long",
        stops=["Đảo Ti Tốp"],
        dest_changed=True,
    )
    assert "Hạ Long" in reply
    assert "vai_gio" not in reply
    food = fallback_plan_chat_reply("rebuild", "vi", theme="food", stops=["Phở Gia Truyền"])
    assert "ăn uống" in food
    assert "1000000" not in food
