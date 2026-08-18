import json
from collections import deque
from time import time

from fastapi.testclient import TestClient

from app.main import app
from app.routers import plans as plans_router
from app.services.rate_limit import limiter
from app.services.store import store

client = TestClient(app)
PAYLOAD = {
    "context": "đi chơi chill Hà Nội",
    "location": {"lat": 21.0285, "lng": 105.8542},
    "thoi_luong": "ca_ngay",
    "so_nguoi": 2,
    "ngan_sach": 1000000,
    "ma_phien": "chatbot-session",
}


def setup_function():
    store.plans.clear()
    store.versions.clear()
    store.users.clear()
    store.events.clear()
    store.comments.clear()
    store.feedback.clear()
    store.preferences.clear()
    store.notifications.clear()
    store.inventory_snapshots.clear()
    store.booking_requests.clear()
    store.reminders_sent.clear()
    store.available = True
    limiter.hits.clear()
    limiter.available = True


def _generated_plan(payload=None):
    request_payload = payload or PAYLOAD
    response = client.post("/api/plan/generate", json=request_payload)
    assert response.status_code == 200
    result = json.loads(
        next(line for line in response.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    assert result["type"] == "plan"
    return response, result


def _sse_statuses(response) -> list[str]:
    return [
        json.loads(line[6:])["status"]
        for line in response.text.splitlines()
        if line.startswith("data: {\"status\"")
    ]


def _refine(token, message, phien_ban=1, ma_phien=PAYLOAD["ma_phien"], dia_diem_dang_chon=None):
    body = {"message": message, "phien_ban": phien_ban, "ma_phien": ma_phien}
    if dia_diem_dang_chon is not None:
        body["dia_diem_dang_chon"] = dia_diem_dang_chon
    return client.post(f"/api/plans/{token}/refine", json=body)


def test_chat_generate_streams_status_then_plan_result():
    response, result = _generated_plan()
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _sse_statuses(response) == ["finding_places", "routing_plan"]
    assert result["ma_phien"] == PAYLOAD["ma_phien"]
    assert result["phien_ban"] == 1
    assert result["token"]
    assert result["plan"]["ngay"]
    assert result["plan"]["hoi_thoai"][-1]["vai_tro"] == "user"
    assert result["plan"]["hoi_thoai"][-1]["noi_dung"] == PAYLOAD["context"]


def test_chat_generate_asks_followup_when_destination_missing():
    payload = PAYLOAD | {
        "context": "đi chơi chill và ăn ngon",
        "ma_phien": "chatbot-missing-destination",
        "nonce": "missing-destination-0001",
    }
    response = client.post("/api/plan/generate", json=payload)
    assert response.status_code == 200
    error_line = next(line for line in response.text.splitlines() if line.startswith('data: {"code"'))
    body = json.loads(error_line[6:])
    assert body["code"] == "missing_required_input"
    assert body["missing_fields"] == ["diem_den"]
    assert body["questions"]
    assert "điểm đến" in body["detail"].lower()
    events = [event for event in store.events if event["ma_phien"] == "chatbot-missing-destination"]
    assert any(event["su_kien"] == "boc_tach_yeu_cau" for event in events)


def test_chat_generate_rejects_context_too_short():
    response = client.post("/api/plan/generate", json=PAYLOAD | {"context": "x"})
    assert response.status_code == 422


def test_chat_generate_rejects_blank_context_after_stripping():
    response = client.post("/api/plan/generate", json=PAYLOAD | {"context": "   "})
    assert response.status_code == 422


def test_chat_generate_rejects_location_out_of_vietnam_bounds():
    response = client.post(
        "/api/plan/generate", json=PAYLOAD | {"location": {"lat": 1.0, "lng": 105.0}}
    )
    assert response.status_code == 422


def test_chat_generate_rejects_short_nonce():
    response = client.post("/api/plan/generate", json=PAYLOAD | {"nonce": "short"})
    assert response.status_code == 422


def test_chat_generate_sanitizes_html_from_context():
    response, result = _generated_plan(
        PAYLOAD | {"context": "<script>alert(1)</script> đi chơi Hà Nội"}
    )
    assert "<script>" not in response.text
    assert result["plan"]["hoi_thoai"][-1]["noi_dung"] == "scriptalert(1)/script đi chơi Hà Nội"


def test_chat_generate_nonce_replays_existing_plan_without_extra_quota():
    payload = PAYLOAD | {"ma_phien": "chatbot-nonce-session", "nonce": "same-chatbot-nonce"}
    first = client.post("/api/plan/generate", json=payload)
    second = client.post("/api/plan/generate", json=payload)
    assert first.status_code == 200 and second.status_code == 200
    first_result = json.loads(next(line for line in first.text.splitlines() if line.startswith('data: {"type"'))[6:])
    second_result = json.loads(next(line for line in second.text.splitlines() if line.startswith('data: {"type"'))[6:])
    assert first_result["token"] == second_result["token"]
    bucket = next(
        values for key, values in limiter.hits.items()
        if key.startswith("generate:testclient:chatbot-nonce-session")
    )
    assert len(bucket) == 1


def test_chat_generate_rejects_when_quota_exhausted():
    key = f"generate:testclient:{PAYLOAD['ma_phien']}"
    limiter.hits[key] = deque([time()] * plans_router.settings.max_generate_per_hour)
    response = client.post("/api/plan/generate", json=PAYLOAD)
    assert response.status_code == 429


def test_chat_generate_fails_closed_when_budget_counter_unavailable():
    store.available = False
    response = client.post("/api/plan/generate", json=PAYLOAD)
    assert response.status_code == 503


def test_chat_refine_applies_people_and_budget_changes():
    _, result = _generated_plan()
    response = _refine(result["token"], "đi 3 người, ngân sách tối đa 500k")
    assert response.status_code == 200
    body = response.json()
    assert body["phien_ban"] == 2
    assert body["tra_loi_key"] == "assistantWelcome"
    assert body["tra_loi"]
    assert body["tham_so"]["so_nguoi"] == 3
    assert body["tham_so"]["ngan_sach"] == 500000
    stored = store.get(result["token"])
    assert stored.request["so_nguoi"] == 3
    assert stored.request["ngan_sach"] == 500000
    assert body["hoi_thoai"][-1]["vai_tro"] == "assistant"


def test_chat_refine_is_multi_turn_and_accumulates_context():
    _, result = _generated_plan()
    first = _refine(result["token"], "đi 3 người, ngân sách tối đa 500k")
    assert first.status_code == 200
    second = _refine(result["token"], "4 người, ưu tiên yên tĩnh", phien_ban=2)
    assert second.status_code == 200
    body = second.json()
    assert body["phien_ban"] == 3
    assert body["tham_so"]["so_nguoi"] == 4
    assert body["tham_so"]["ngan_sach"] == 500000
    context = store.get(result["token"]).request["context"]
    assert "3 người" in context and "4 người" in context and "ưu tiên yên tĩnh" in context
    roles = [turn["vai_tro"] for turn in body["hoi_thoai"]]
    assert roles == ["user", "user", "assistant", "user", "assistant"]


def test_chat_refine_persists_conversation_across_reloads():
    _, result = _generated_plan()
    _refine(result["token"], "đi 4 người, ngân sách tối đa 500k")
    detail = client.get(f"/api/plans/{result['token']}").json()
    history = detail["ke_hoach"]["hoi_thoai"]
    messages = [turn["noi_dung"] for turn in history]
    assert "đi 4 người, ngân sách tối đa 500k" in messages
    assert PAYLOAD["context"] in messages
    assert any(turn["vai_tro"] == "assistant" for turn in history)
    assert all(turn["thoi_gian"] for turn in history)


def test_chat_refine_cheaper_intent_cuts_budget():
    _, result = _generated_plan()
    response = _refine(result["token"], "Re hon")
    assert response.status_code == 200
    assert response.json()["tham_so"]["ngan_sach"] == 800000
    assert store.get(result["token"]).request["ngan_sach"] == 800000


def test_chat_refine_nearby_intent_keeps_stops_close():
    _, result = _generated_plan()
    response = _refine(result["token"], "chọn địa điểm gần nhau")
    assert response.status_code == 200
    context = store.get(result["token"]).request["context"]
    assert "keep stops geographically close" in context


def test_chat_refine_cafe_intent_adds_relaxed_stops():
    _, result = _generated_plan()
    response = _refine(result["token"], "thêm quán cafe")
    assert response.status_code == 200
    context = store.get(result["token"]).request["context"]
    assert "add more cafe" in context


def test_chat_refine_swap_intent_without_selected_place_rejected():
    _, result = _generated_plan()
    response = _refine(result["token"], "đổi điểm này sang điểm yên tĩnh hơn")
    assert response.status_code == 422


def test_chat_refine_swap_intent_swaps_selected_place():
    _, result = _generated_plan()
    target = result["plan"]["ngay"][0]["khoang_gio"][0]["dia_diem_id"]
    response = _refine(result["token"], "đổi điểm này", dia_diem_dang_chon=target)
    assert response.status_code == 200
    body = response.json()
    assert body["phien_ban"] == 2
    assert body["tra_loi_key"] == "swipeSuccess"
    swapped = {
        slot["dia_diem_id"]
        for day in body["ke_hoach"]["ngay"]
        for slot in day["khoang_gio"]
    }
    assert target not in swapped
    assert body["hoi_thoai"][-1]["vai_tro"] == "assistant"


def test_chat_refine_requires_owner_session():
    _, result = _generated_plan()
    response = _refine(result["token"], "đi 3 người", ma_phien="somebody-else")
    assert response.status_code == 403


def test_chat_refine_unknown_token_returns_404():
    response = _refine("missing-token", "đi 3 người")
    assert response.status_code == 404


def test_chat_refine_stale_version_is_rejected_optimistically():
    _, result = _generated_plan()
    first = _refine(result["token"], "đi 3 người")
    assert first.status_code == 200
    stale = _refine(result["token"], "đi 4 người", phien_ban=1)
    assert stale.status_code == 409


def test_chat_refine_rate_limited_after_burst():
    _, result = _generated_plan()
    limiter.available = False
    response = _refine(result["token"], "đi 3 người")
    assert response.status_code == 429


def test_chat_refine_sanitizes_html_from_message():
    _, result = _generated_plan()
    response = _refine(result["token"], "<script>alert(1)</script> rẻ hơn")
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "<script>" not in store.get(result["token"]).request["context"]


def test_chat_refine_rejects_message_too_short():
    _, result = _generated_plan()
    response = _refine(result["token"], "a")
    assert response.status_code == 422