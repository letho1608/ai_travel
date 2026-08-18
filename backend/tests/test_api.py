import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.data import Place
from app.main import app
from app.pipeline.planner import AI_FALLBACK_NOTE
from app.routers import plans as plans_router
from app.routers.auth import LOCAL_USERS
from app.services.rate_limit import limiter
from app.services.store import store

client = TestClient(app)
PAYLOAD = {"context": "đi chơi chill Hà Nội", "location": {"lat": 21.0285, "lng": 105.8542}, "thoi_luong": "ca_ngay", "so_nguoi": 2, "ngan_sach": 1000000, "ma_phien": "api-session"}


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
    LOCAL_USERS.clear()
    store.available = True
    limiter.hits.clear()
    limiter.available = True


def test_global_request_body_limit_rejects_oversized_json_before_route_parsing():
    oversized_payload = {
        "latitude": 21.0,
        "longitude": 105.0,
        "ma_phien": "body-limit-session",
        "notes": "x" * (300 * 1024),
    }
    response = client.post("/api/inventory/activities/search", json=oversized_payload)
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large"


def test_intent_parse_endpoint_returns_ask_back_and_suggestions(monkeypatch):
    from app.pipeline import intent_parse

    class FakeAIAdapter:
        def extract_planning_intent(self, _context: str, _locale: str = "vi") -> dict:
            return {"trip_purpose": "healing"}

    monkeypatch.setattr(intent_parse, "ai_adapter", FakeAIAdapter())
    response = client.post("/api/intent/parse", json={"context": "Tôi muốn đi chữa lành", "ngon_ngu": "vi"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ask_user_missing_fields"
    assert body["extraction_source"] == "ai"
    assert "destination" in body["missing_fields"]
    assert body["parsed"]["primary_intent"] == "healing"
    assert body["parsed"]["planner_mode"] == "intent_discovery"
    assert len(body["suggestions"]) >= 2


def test_all_inventory_search_routes_enforce_ip_and_session_limit(monkeypatch):
    from app.routers import inventory as inventory_router

    monkeypatch.setattr(inventory_router, "SEARCH_SESSION_LIMIT", 0)
    cases = [
        ("/api/inventory/flights/search", {
            "origin": "HAN", "destination": "SGN", "departure_date": "2030-01-01",
            "adults": 1, "currency": "VND", "ma_phien": "rate-session",
        }),
        ("/api/inventory/hotels/search", {
            "latitude": 21.0, "longitude": 105.0, "check_in": "2030-01-01",
            "check_out": "2030-01-02", "ma_phien": "rate-session",
        }),
        ("/api/inventory/activities/search", {
            "latitude": 21.0, "longitude": 105.0, "ma_phien": "rate-session",
        }),
        ("/api/inventory/transfers/search", {
            "start_location_code": "HAN", "end_address_line": "1 Trang Tien",
            "end_city_name": "Ha Noi", "end_country_code": "VN", "end_name": "Hoan Kiem",
            "end_latitude": 21.0, "end_longitude": 105.0,
            "start_datetime": "2030-01-01T10:00:00+07:00",
            "ma_phien": "rate-session",
        }),
    ]
    for path, payload in cases:
        assert client.post(path, json=payload).status_code == 429


def test_inventory_rate_limiter_failure_is_closed(monkeypatch):
    from app.routers import inventory as inventory_router

    monkeypatch.setattr(inventory_router, "SEARCH_SESSION_LIMIT", 30)
    limiter.available = False
    response = client.post("/api/inventory/activities/search", json={
        "latitude": 21.0, "longitude": 105.0, "ma_phien": "rate-session",
    })
    assert response.status_code == 429


def test_roadtrip_routes_enforce_ip_and_session_limit(monkeypatch):
    from dataclasses import replace

    from app.routers import roadtrip as roadtrip_router

    monkeypatch.setattr(roadtrip_router, "settings", replace(
        roadtrip_router.settings,
        max_roadtrip_route_per_hour=0,
        max_roadtrip_plan_per_hour=0,
    ))
    stops = [
        {"name": "A", "location": {"lat": 21.0, "lng": 105.0}},
        {"name": "B", "location": {"lat": 20.0, "lng": 106.0}},
    ]
    assert client.post("/api/roadtrip/route", json={"stops": stops}).status_code == 429
    assert client.post("/api/roadtrip/plan", json={
        "stops": stops, "ma_phien": "rate-session",
    }).status_code == 429


def test_roadtrip_rate_limiter_failure_is_closed():
    limiter.available = False
    response = client.post("/api/roadtrip/route", json={"stops": [
        {"name": "A", "location": {"lat": 21.0, "lng": 105.0}},
        {"name": "B", "location": {"lat": 20.0, "lng": 106.0}},
    ]})
    assert response.status_code == 429


def test_password_auth_creates_then_logs_in_existing_user():
    created = client.post("/api/auth/password", json={
        "username": "MinhTravel",
        "password": "abc12345",
        "so_dien_thoai": "0912345678",
        "hanh_dong": "dang_ky",
        "ma_phien": "password-session",
        "consent": True,
    })
    assert created.status_code == 200
    body = created.json()
    assert body["token"].startswith("mock-jwt-")
    assert body["nguoi_dung"]["username"] == "minhtravel"
    assert body["nguoi_dung"]["so_dien_thoai"] == "+84912345678"
    assert "mat_khau_hash" not in body["nguoi_dung"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "minhtravel"
    assert me.json()["so_dien_thoai"] == "+84912345678"
    assert "mat_khau_hash" not in me.json()

    missing = client.post("/api/auth/password", json={
        "username": "nobodyyet",
        "password": "abc12345",
        "hanh_dong": "dang_nhap",
        "ma_phien": "missing-session",
        "consent": True,
    })
    assert missing.status_code == 401

    duplicate = client.post("/api/auth/password", json={
        "username": "MinhTravel",
        "password": "abc12345",
        "so_dien_thoai": "0987654321",
        "hanh_dong": "dang_ky",
        "ma_phien": "password-session-dup",
        "consent": True,
    })
    assert duplicate.status_code == 409

    logged_in = client.post("/api/auth/password", json={
        "username": "MinhTravel",
        "password": "abc12345",
        "hanh_dong": "dang_nhap",
        "ma_phien": "password-session-2",
        "consent": True,
    })
    assert logged_in.status_code == 200
    assert logged_in.json()["nguoi_dung"]["id"] == body["nguoi_dung"]["id"]


def test_password_auth_rejects_weak_or_wrong_password():
    weak = client.post("/api/auth/password", json={
        "username": "weakuser",
        "password": "abcdefgh",
        "hanh_dong": "dang_ky",
        "so_dien_thoai": "0912345678",
        "ma_phien": "weak-session",
        "consent": True,
    })
    assert weak.status_code == 422
    digits = client.post("/api/auth/password", json={
        "username": "digituser",
        "password": "12345678",
        "hanh_dong": "dang_ky",
        "so_dien_thoai": "0912345678",
        "ma_phien": "digit-session",
        "consent": True,
    })
    assert digits.status_code == 422
    no_phone = client.post("/api/auth/password", json={
        "username": "nophone",
        "password": "abc12345",
        "hanh_dong": "dang_ky",
        "ma_phien": "nophone-session",
        "consent": True,
    })
    assert no_phone.status_code == 422

    client.post("/api/auth/password", json={
        "username": "rightuser",
        "password": "abc12345",
        "so_dien_thoai": "0912345678",
        "hanh_dong": "dang_ky",
        "ma_phien": "right-session",
        "consent": True,
    })
    wrong = client.post("/api/auth/password", json={
        "username": "rightuser",
        "password": "wrong1234",
        "hanh_dong": "dang_nhap",
        "ma_phien": "right-session-2",
        "consent": True,
    })
    assert wrong.status_code == 401


def test_password_forgot_always_succeeds_without_leaking_account():
    response = client.post("/api/auth/password/forgot", json={
        "username": "unknownuser",
        "ma_phien": "forgot-session",
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_google_oauth_issues_session_without_password_hash():
    login = client.post(
        "/api/auth/oauth",
        json={"provider": "google", "token": "mock-google-user-123",
              "ma_phien": "google-login-session", "consent": True},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["token"].startswith("mock-jwt-")
    assert body["nguoi_dung"]["email"] == "user-123@demo.local"
    assert "mat_khau_hash" not in body["nguoi_dung"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user-123@demo.local"
    assert "mat_khau_hash" not in me.json()


def test_generate_sse_and_shared_read_only():
    response = client.post("/api/plan/generate", json=PAYLOAD)
    assert response.status_code == 200
    result_line = next(line for line in response.text.splitlines() if line.startswith("data: {\"type\""))
    import json
    result = json.loads(result_line[6:])
    shared = client.get(f"/api/plans/{result['token']}")
    assert shared.status_code == 200
    denied = client.patch(f"/api/plans/{result['token']}/swipe", json={"diem_bi_loai": result["plan"]["ngay"][0]["khoang_gio"][0]["dia_diem_id"], "phien_ban": 1, "ma_phien": "wrong"})
    assert denied.status_code == 403


def test_generate_logs_input_extraction_for_quality_measurement():
    response = client.post(
        "/api/plan/generate",
        json=PAYLOAD | {"ma_phien": "extract-log-session", "context": "du lịch Hà Nội, thích cafe, không thích quá đông"},
    )
    assert response.status_code == 200
    extraction_events = [
        event for event in store.events
        if event["ma_phien"] == "extract-log-session" and event["su_kien"] == "boc_tach_yeu_cau"
    ]
    assert extraction_events
    extracted = extraction_events[0]["du_lieu"]
    assert extracted["schema_version"] == "input-understanding-v1"
    assert extracted["so_nguoi"]["nguon"] == "form_chat"
    assert extracted["ngan_sach"]["nguon"] == "form_chat"
    assert extracted["hanh_dong_tiep_theo"] == "du_dieu_kien_lap_lich"


def test_generate_asks_for_missing_destination_instead_of_guessing():
    payload = PAYLOAD | {
        "context": "đi chơi chill và ăn ngon",
        "ma_phien": "missing-destination-session",
        "nonce": "missing-destination-0001",
    }
    response = client.post("/api/plan/generate", json=payload)
    assert response.status_code == 200
    error_line = next(line for line in response.text.splitlines() if line.startswith('data: {"code"'))
    body = json.loads(error_line[6:])
    assert body["code"] == "missing_required_input"
    assert body["missing_fields"] == ["diem_den"]
    assert "điểm đến" in body["detail"].lower()
    extraction_events = [
        event for event in store.events
        if event["ma_phien"] == "missing-destination-session" and event["su_kien"] == "boc_tach_yeu_cau"
    ]
    assert extraction_events
    assert extraction_events[0]["du_lieu"]["hanh_dong_tiep_theo"] == "hoi_lai_nguoi_dung"


def test_plan_locale_is_persisted_and_reused_by_swipe_and_regenerate():
    payload = PAYLOAD | {"ngon_ngu": "en", "ma_phien": "locale-session"}
    generated = client.post("/api/plan/generate", json=payload)
    result = json.loads(next(
        line for line in generated.text.splitlines() if line.startswith('data: {"type"')
    )[6:])
    assert result["plan"]["ngay"][0]["nhan_de"] == "Day 1"
    assert "optimized itinerary" in result["plan"]["tom_tat"]
    stored = store.get(result["token"])
    assert stored.request["ngon_ngu"] == "en"

    target = result["plan"]["ngay"][0]["khoang_gio"][0]["dia_diem_id"]
    swiped = client.patch(
        f"/api/plans/{result['token']}/swipe",
        headers={"X-Session-Id": payload["ma_phien"]},
        json={"diem_bi_loai": target, "phien_ban": 1, "ma_phien": payload["ma_phien"]},
    )
    assert swiped.status_code == 200
    replacement = next(
        slot for day in swiped.json()["ke_hoach_moi"]["ngay"]
        for slot in day["khoang_gio"] if slot["dia_diem_id"] != target
    )
    assert replacement["ghi_chu"] == "Check opening hours before visiting."

    regenerated = client.post(
        f"/api/plans/{result['token']}/regenerate",
        json={"ma_phien": payload["ma_phien"], "nonce": "locale-regenerate"},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["ke_hoach"]["ngay"][0]["nhan_de"] == "Day 1"
    assert regenerated.json()["token"] == result["token"]

    refined = client.post(
        f"/api/plans/{result['token']}/refine",
        json={"message": "budget 900000", "phien_ban": 3,
              "ma_phien": payload["ma_phien"]},
    )
    assert refined.status_code == 200
    assert refined.json()["ke_hoach"]["ngay"][0]["nhan_de"] == "Day 1"
    assert store.get(result["token"]).request["ngon_ngu"] == "en"


def test_swipe_updates_versioned_behavior_weights_used_by_next_plan():
    payload = PAYLOAD | {"ma_phien": "behavior-learning-session", "nonce": "behavior-plan-0001"}
    generated = client.post("/api/plan/generate", json=payload)
    result = json.loads(next(
        line for line in generated.text.splitlines() if line.startswith('data: {"type"')
    )[6:])
    target = result["plan"]["ngay"][0]["khoang_gio"][0]["dia_diem_id"]

    swiped = client.patch(
        f"/api/plans/{result['token']}/swipe",
        headers={"X-Session-Id": payload["ma_phien"]},
        json={"diem_bi_loai": target, "phien_ban": 1, "ma_phien": payload["ma_phien"]},
    )

    assert swiped.status_code == 200
    profile = store.get_behavior_profile(payload["ma_phien"])
    assert profile["schema_version"] == "behavior-profile-v1"
    assert profile["version"] == 1
    assert profile["observation_count"] == 1
    assert profile["is_active"] is False
    assert profile["tag_weights"] == {}
    assert profile["stored_tag_weights"]
    assert profile["change_log"][0]["reason"] == "user_replaced_place"
    assert profile["change_log"][0]["tag_deltas"]

    next_plan = _generated_plan(payload | {"nonce": "behavior-plan-0002"})["plan"]
    assert next_plan["ho_so_hanh_vi"]["version"] == 1
    assert next_plan["ho_so_hanh_vi"]["dang_ap_dung"] is False
    first_evidence = next_plan["ngay"][0]["khoang_gio"][0]["bang_chung"]["xep_hang"]
    assert first_evidence["ho_so_hanh_vi"]["version"] == 1
    assert "hanh_vi_nguoi_dung" not in first_evidence["thanh_phan"]

    for index in range(4):
        store.adjust_tag_weights(
            payload["ma_phien"],
            {"healing": 5},
            reason=f"acceptance_signal_{index}",
        )
    active_profile = store.get_behavior_profile(payload["ma_phien"])
    assert active_profile["version"] == 5
    assert active_profile["is_active"] is True
    assert active_profile["tag_weights"]["healing"] <= 15


def test_swipe_supports_a_slot_on_the_second_day():
    import json

    payload = PAYLOAD | {"thoi_luong": "nhieu_ngay"}
    generated = client.post("/api/plan/generate", json=payload)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    target = result["plan"]["ngay"][1]["khoang_gio"][0]["dia_diem_id"]
    response = client.patch(
        f"/api/plans/{result['token']}/swipe",
        headers={"X-Session-Id": PAYLOAD["ma_phien"]},
        json={"diem_bi_loai": target, "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert response.status_code == 200


def _generated_plan(payload=None):
    request_payload = payload or PAYLOAD
    response = client.post("/api/plan/generate", json=request_payload)
    return json.loads(next(line for line in response.text.splitlines() if line.startswith('data: {"type"'))[6:])


def test_explicit_replacement_search_delete_and_restore_contract():
    result = _generated_plan()
    token, plan = result["token"], result["plan"]
    target = plan["ngay"][0]["khoang_gio"][0]["dia_diem_id"]
    headers = {"X-Session-Id": PAYLOAD["ma_phien"]}
    denied = client.get(f"/api/plans/{token}/replacement-candidates", params={"diem_bi_loai": target}, headers={"X-Session-Id": "wrong"})
    assert denied.status_code == 403
    search = client.get(f"/api/plans/{token}/replacement-candidates", params={"diem_bi_loai": target}, headers=headers)
    assert search.status_code == 200 and search.json()["goi_y"]
    candidate = search.json()["goi_y"][0]
    replaced = client.patch(f"/api/plans/{token}/swipe", headers=headers, json={"diem_bi_loai": target, "dia_diem_thay_the": candidate["id"], "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]})
    assert replaced.status_code == 200 and replaced.json()["phien_ban"] == 2
    assert any(slot["dia_diem_id"] == candidate["id"] for day in replaced.json()["ke_hoach_moi"]["ngay"] for slot in day["khoang_gio"])
    stale = client.request("DELETE", f"/api/plans/{token}/slots", headers=headers, json={"dia_diem_id": candidate["id"], "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]})
    assert stale.status_code == 409
    deleted = client.request("DELETE", f"/api/plans/{token}/slots", headers=headers, json={"dia_diem_id": candidate["id"], "phien_ban": 2, "ma_phien": PAYLOAD["ma_phien"]})
    assert deleted.status_code == 200 and deleted.json()["phien_ban"] == 3
    remaining = [slot for day in deleted.json()["ke_hoach_moi"]["ngay"] for slot in day["khoang_gio"]]
    assert deleted.json()["ke_hoach_moi"]["tong_chi_phi"] == sum(slot["chi_phi"] for slot in remaining)
    restored = client.post(f"/api/plans/{token}/versions/2/restore", headers=headers, json={"phien_ban_hien_tai": 3, "ma_phien": PAYLOAD["ma_phien"]})
    assert restored.status_code == 200 and restored.json()["phien_ban"] == 4


def test_explicit_replacement_rejects_unknown_id():
    result = _generated_plan()
    target = result["plan"]["ngay"][0]["khoang_gio"][0]["dia_diem_id"]
    headers = {"X-Session-Id": PAYLOAD["ma_phien"]}
    unknown = client.patch(f"/api/plans/{result['token']}/swipe", headers=headers, json={"diem_bi_loai": target, "dia_diem_thay_the": "missing", "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]})
    assert unknown.status_code == 422


def test_auto_replacement_ranks_similarity_before_distance():
    rejected = Place("old", "Old", "museum", "Ba Đình", 21.0, 105.8, 0, 60, ("history", "indoor"))
    close_wrong = Place("close", "Close", "cafe", "Ba Đình", 21.0001, 105.8001, 0, 60, ("coffee",))
    similar = Place("similar", "Similar", "museum", "Hoàn Kiếm", 21.02, 105.82, 0, 60, ("history", "indoor"))
    assert min((close_wrong, similar), key=lambda place: plans_router._replacement_rank(place, rejected)) is similar


def test_free_text_replacement_rejects_unverified_external_operational_data(monkeypatch):
    result = _generated_plan()
    target = result["plan"]["ngay"][0]["khoang_gio"][0]
    external = Place("osm-verified-node-987", "Vườn nghệ thuật mới", "dia_danh", "Hà Nội", target["toa_do"]["lat"], target["toa_do"]["lng"], 0, 60, ("osm_verified",), 7, 22, "Nominatim", "https://www.openstreetmap.org/node/987")
    monkeypatch.setattr(plans_router, "verify_place_name", lambda name, origin: external)
    response = client.patch(f"/api/plans/{result['token']}/swipe", headers={"X-Session-Id": PAYLOAD["ma_phien"]}, json={"diem_bi_loai": target["dia_diem_id"], "ten_dia_diem_thay_the": external.name, "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]})
    assert response.status_code == 422
    assert "không dùng AI" in response.json()["detail"]


def test_budget_counter_fails_closed():
    store.available = False
    assert client.post("/api/plan/generate", json=PAYLOAD).status_code == 503


def test_invalid_html_is_sanitized():
    payload = PAYLOAD | {"context": "<script>alert(1)</script> chill"}
    response = client.post("/api/plan/generate", json=payload)
    assert response.status_code == 200
    assert "<script>" not in response.text


def test_regenerate_nonce_is_idempotent():
    generated = client.post("/api/plan/generate", json=PAYLOAD)
    import json
    result = json.loads(next(line for line in generated.text.splitlines() if line.startswith("data: {\"type\""))[6:])
    body = {"ma_phien": PAYLOAD["ma_phien"], "nonce": "same-nonce"}
    first = client.post(f"/api/plans/{result['token']}/regenerate", json=body).json()
    second = client.post(f"/api/plans/{result['token']}/regenerate", json=body).json()
    assert first["token"] == second["token"]
    regenerate_bucket = next(
        values for key, values in limiter.hits.items() if key.startswith("regenerate:api-session:")
    )
    assert len(regenerate_bucket) == 1


def test_regenerate_stays_in_place_and_preserves_version_chain():
    generated = client.post("/api/plan/generate", json=PAYLOAD)
    import json
    result = json.loads(next(line for line in generated.text.splitlines() if line.startswith("data: {\"type\""))[6:])
    token = result["token"]
    original_ids = {
        slot["dia_diem_id"]
        for day in result["plan"]["ngay"]
        for slot in day["khoang_gio"]
    }
    regenerated = client.post(
        f"/api/plans/{token}/regenerate",
        json={"ma_phien": PAYLOAD["ma_phien"], "nonce": "in-place-nonce"},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["token"] == token
    assert regenerated.json()["phien_ban"] == 2
    regenerated_ids = {
        slot["dia_diem_id"]
        for day in regenerated.json()["ke_hoach"]["ngay"]
        for slot in day["khoang_gio"]
    }
    assert regenerated_ids
    assert regenerated_ids != original_ids
    assert regenerated_ids.isdisjoint(original_ids)
    versions = client.get(
        f"/api/plans/{token}/versions",
        headers={"X-Session-Id": PAYLOAD["ma_phien"]},
    ).json()["ds_phien_ban"]
    assert [entry["phien_ban"] for entry in versions] == [2, 1]


def test_generate_nonce_replays_existing_plan_without_extra_quota():
    payload = PAYLOAD | {"ma_phien": "generate-nonce-session", "nonce": "same-generate-nonce"}
    first = client.post("/api/plan/generate", json=payload)
    second = client.post("/api/plan/generate", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    first_result = json.loads(
        next(line for line in first.text.splitlines() if line.startswith("data: {\"type\""))[6:]
    )
    second_result = json.loads(
        next(line for line in second.text.splitlines() if line.startswith("data: {\"type\""))[6:]
    )
    assert first_result["token"] == second_result["token"]
    generate_bucket = next(
        values for key, values in limiter.hits.items()
        if key.startswith("generate:testclient:generate-nonce-session")
    )
    assert len(generate_bucket) == 1


def test_generate_nonce_is_scoped_to_session():
    first_payload = PAYLOAD | {"ma_phien": "generate-scope-a", "nonce": "shared-generate-nonce"}
    second_payload = PAYLOAD | {"ma_phien": "generate-scope-b", "nonce": "shared-generate-nonce"}
    first = client.post("/api/plan/generate", json=first_payload)
    second = client.post("/api/plan/generate", json=second_payload)
    assert first.status_code == 200
    assert second.status_code == 200
    first_result = json.loads(
        next(line for line in first.text.splitlines() if line.startswith("data: {\"type\""))[6:]
    )
    second_result = json.loads(
        next(line for line in second.text.splitlines() if line.startswith("data: {\"type\""))[6:]
    )
    assert first_result["token"] != second_result["token"]


def test_chat_refine_creates_version_and_restore_is_optimistic():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    token = result["token"]
    refined = client.post(
        f"/api/plans/{token}/refine",
        json={
            "message": "đi 3 người, ngân sách tối đa 500k và ưu tiên yên tĩnh",
            "phien_ban": 1,
            "ma_phien": PAYLOAD["ma_phien"],
        },
    )
    assert refined.status_code == 200
    assert refined.json()["phien_ban"] == 2
    stored = store.get(token)
    assert stored.request["so_nguoi"] == 3
    assert stored.request["ngan_sach"] == 500000
    versions = client.get(
        f"/api/plans/{token}/versions",
        headers={"X-Session-Id": PAYLOAD["ma_phien"]},
    ).json()["ds_phien_ban"]
    assert [entry["phien_ban"] for entry in versions] == [2, 1]

    restored = client.post(
        f"/api/plans/{token}/versions/1/restore",
        json={"phien_ban_hien_tai": 2, "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert restored.status_code == 200
    assert restored.json()["phien_ban"] == 3
    stale = client.post(
        f"/api/plans/{token}/versions/1/restore",
        json={"phien_ban_hien_tai": 2, "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert stale.status_code == 409


def test_chat_refine_persists_conversation_and_echoes_constraints():
    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    token = result["token"]

    detail = client.get(f"/api/plans/{token}").json()
    assert detail["tham_so"]["ngan_sach"] == PAYLOAD["ngan_sach"]
    assert detail["tham_so"]["so_nguoi"] == PAYLOAD["so_nguoi"]
    assert detail["tham_so"]["thoi_luong"] == PAYLOAD["thoi_luong"]

    refined = client.post(
        f"/api/plans/{token}/refine",
        json={"message": "di 4 người, ngân sách tối đa 500k", "phien_ban": 1,
              "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert refined.status_code == 200
    body = refined.json()
    assert body["tham_so"]["so_nguoi"] == 4
    assert body["tham_so"]["ngan_sach"] == 500000
    assert len(body["hoi_thoai"]) >= 3
    roles = [turn["vai_tro"] for turn in body["hoi_thoai"]]
    assert roles[-1] == "assistant"
    assert any(turn["noi_dung"] == PAYLOAD["context"] for turn in body["hoi_thoai"])

    reloaded = client.get(f"/api/plans/{token}").json()
    assert any(
        turn["noi_dung"] == "di 4 người, ngân sách tối đa 500k"
        for turn in reloaded["ke_hoach"].get("hoi_thoai", [])
    )
    assert isinstance(reloaded["ke_hoach"].get("ngay_cap_nhat"), str)
    assert reloaded["ke_hoach"]["ngay_cap_nhat"] >= detail["ke_hoach"]["ngay_cap_nhat"]


def test_quick_refine_cheaper_reduces_saved_budget():
    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.post(
        f"/api/plans/{result['token']}/refine",
        json={"message": "Re hon", "phien_ban": 1, "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert response.status_code == 200
    assert store.get(result["token"]).request["ngan_sach"] == 800000


def test_google_login_claims_anonymous_plans_and_issues_session():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    login = client.post(
        "/api/auth/oauth",
        json={"provider": "google", "token": "local-google-user-123",
              "ma_phien": PAYLOAD["ma_phien"], "consent": True},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    plans = client.get("/api/plans", headers=headers).json()["ds_ke_hoach"]
    assert [plan["token"] for plan in plans] == [result["token"]]


def test_shared_plan_comments_are_sanitized_and_only_owner_can_resolve():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    token = result["token"]
    added = client.post(
        f"/api/plans/{token}/comments",
        json={"noi_dung": "<b>Nên đi sớm</b>", "ten_hien_thi": "Bạn đồng hành",
              "ma_phien": "collaborator-session"},
    )
    assert added.status_code == 201
    comment = added.json()["binh_luan"]
    assert "<" not in comment["noi_dung"]
    assert client.get(f"/api/plans/{token}/comments").json()["ds_binh_luan"][0]["id"] == comment["id"]
    denied = client.patch(
        f"/api/plans/{token}/comments/{comment['id']}",
        json={"da_giai_quyet": True, "ma_phien": "collaborator-session"},
    )
    assert denied.status_code == 403
    resolved = client.patch(
        f"/api/plans/{token}/comments/{comment['id']}",
        json={"da_giai_quyet": True, "ma_phien": PAYLOAD["ma_phien"]},
    )
    assert resolved.status_code == 200
    assert resolved.json()["binh_luan"]["da_giai_quyet"] is True


def test_calendar_export_contains_each_stop_without_html():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.get(f"/api/plans/{result['token']}/calendar.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.text.count("BEGIN:VEVENT") == len(result["plan"]["ngay"][0]["khoang_gio"])
    assert response.text.count("DTSTAMP:") == response.text.count("BEGIN:VEVENT")
    assert all(len(line.encode("utf-8")) <= 75 for line in response.text.splitlines())
    assert "<script>" not in response.text


def test_calendar_export_includes_every_day_of_a_multiday_plan():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD | {"thoi_luong": "nhieu_ngay"})
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.get(f"/api/plans/{result['token']}/calendar.ics")
    expected = sum(len(day["khoang_gio"]) for day in result["plan"]["ngay"])
    assert response.status_code == 200
    assert response.text.count("BEGIN:VEVENT") == expected


def test_calendar_export_uses_saved_plan_language_metadata():
    import json

    generated = client.post(
        "/api/plan/generate", json=PAYLOAD | {"ngon_ngu": "en", "ma_phien": "ics-en"}
    )
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.get(f"/api/plans/{result['token']}/calendar.ics")
    assert response.status_code == 200
    assert response.headers["content-language"] == "en"
    assert "PRODID:-//Minh Di Dau The//EN" in response.text
    assert "SUMMARY;LANGUAGE=en:" in response.text
    assert "DESCRIPTION;LANGUAGE=en:" in response.text
    assert "CALSCALE:GREGORIAN" in response.text


def test_pdf_export_is_valid_and_contains_itinerary_text():
    import json
    from io import BytesIO

    from pypdf import PdfReader

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.get(f"/api/plans/{result['token']}/itinerary.pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert result["plan"]["tieu_de"] in text
    assert result["plan"]["ngay"][0]["khoang_gio"][0]["ten_dia_diem"] in text


def test_pdf_export_uses_saved_plan_language_and_preserves_proper_names():
    import json
    from io import BytesIO

    from pypdf import PdfReader

    generated = client.post(
        "/api/plan/generate", json=PAYLOAD | {"ngon_ngu": "en", "ma_phien": "pdf-en"}
    )
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    response = client.get(f"/api/plans/{result['token']}/itinerary.pdf")
    text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    slot = result["plan"]["ngay"][0]["khoang_gio"][0]
    assert response.headers["content-language"] == "en"
    assert "Departure date" in text
    assert "Weather source" in text
    assert "Page 1" in text
    assert slot["ten_dia_diem"] in text
    assert slot["nguon"] in text


def test_post_trip_feedback_is_owner_only_sanitized_and_unique():
    import json

    payload = PAYLOAD | {
        "ngay_di": (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    }
    generated = client.post("/api/plan/generate", json=payload)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    token = result["token"]
    body = {"diem": 5, "noi_dung": "<b>Rất vui</b>", "ma_phien": PAYLOAD["ma_phien"]}
    response = client.post(f"/api/plans/{token}/feedback", json=body)
    assert response.status_code == 201
    assert "<" not in response.json()["phan_hoi"]["noi_dung"]
    assert client.post(f"/api/plans/{token}/feedback", json=body).status_code == 409


def test_preferences_persist_by_session_and_validate_currency():
    body = {"ngon_ngu": "en", "tien_te": "USD", "don_vi": "imperial",
            "ma_phien": "preferences-session"}
    assert client.put("/api/auth/preferences", json=body).status_code == 200
    loaded = client.get(
        "/api/auth/preferences", headers={"X-Session-Id": "preferences-session"}
    ).json()
    assert loaded == {"ngon_ngu": "en", "tien_te": "USD", "don_vi": "imperial"}
    assert client.put(
        "/api/auth/preferences", json=body | {"tien_te": "BTC"}
    ).status_code == 422


def test_invalid_bearer_never_falls_back_to_anonymous_preferences():
    headers = {"Authorization": "Bearer expired-or-invalid-token",
               "X-Session-Id": "preferences-session"}
    assert client.get("/api/auth/preferences", headers=headers).status_code == 401
    body = {"ngon_ngu": "en", "tien_te": "USD", "don_vi": "metric",
            "ma_phien": "preferences-session"}
    assert client.put(
        "/api/auth/preferences", headers=headers, json=body
    ).status_code == 401


def test_account_deletion_removes_owned_data_and_revokes_session():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    login = client.post(
        "/api/auth/oauth",
        json={"provider": "google", "token": "local-google-delete-user",
              "ma_phien": PAYLOAD["ma_phien"], "consent": True},
    )
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    deleted = client.request(
        "DELETE", "/api/auth/account", headers=headers,
        json={"confirmation": "XOA TAI KHOAN"},
    )
    assert deleted.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.get(f"/api/plans/{result['token']}").status_code == 404
    assert store.users == {}


def test_api_security_headers_and_request_trace_are_always_present():
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["x-request-id"] == "trace-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    api_response = client.get("/api/plans/00000000-0000-0000-0000-000000000000")
    assert api_response.headers["cache-control"] == "no-store"


def test_admin_dashboard_requires_token_and_reports_operational_state():
    store.log("admin-session", "tao_ke_hoach", {"token": "local"})
    store.save(
        "admin-session",
        {"tieu_de": "fallback", "tom_tat": "fallback", "ngay": [], "luu_y": [AI_FALLBACK_NOTE["en"]]},
        {"context": "fallback"},
    )
    denied = client.get("/api/admin/dashboard")
    assert denied.status_code == 401

    response = client.get(
        "/api/admin/dashboard", headers={"X-Admin-Token": "local-support-dev"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "local"
    assert body["providers"][0]["name"] == "AI"
    assert body["providers"][0]["status"] == "offline"
    assert body["provider_diagnostics"]["ai"]["api_key_configured"] is False
    assert body["provider_diagnostics"]["ai"]["circuit_breaker"]["state"] == "closed"
    assert "API_KEY_GROQ" in body["provider_diagnostics"]["ai"]["required_env"]
    assert body["summary"]["events"] == 1
    assert body["limits"]["daily_ai_budget_usd"] == 10.0
    assert body["limits"]["max_request_body_bytes"] == 256 * 1024
    assert body["ai_quality"]["mode"] == "offline"
    assert body["ai_quality"]["deterministic_mode"] is True
    assert body["ai_quality"]["fallback_plan_count"] == 1
    assert body["ai_quality"]["fallback_rate_percent"] == 100.0
    assert body["ai_quality"]["deterministic_plan_count"] == 1
    assert body["ai_quality"]["deterministic_rate_percent"] == 100.0
    assert body["recent_events"][0]["su_kien"] == "tao_ke_hoach"
    assert body["catalog_quality"]["place_count"] > 0
    assert body["catalog_quality"]["distance_matrix"]["loaded"] is True
    assert body["catalog_quality"]["sample_places"][0]["id"]

    diagnostics = client.get(
        "/api/admin/providers/diagnostics", headers={"X-Admin-Token": "local-support-dev"}
    )
    assert diagnostics.status_code == 200
    assert diagnostics.json()["ai"]["ready"] is False

    quality = client.get(
        "/api/admin/ai-quality", headers={"X-Admin-Token": "local-support-dev"}
    )
    assert quality.status_code == 200
    assert quality.json()["fallback_plan_count"] == 1
    assert quality.json()["deterministic_plan_count"] == 1

    catalog_quality = client.get(
        "/api/admin/catalog/quality", headers={"X-Admin-Token": "local-support-dev"}
    )
    assert catalog_quality.status_code == 200
    assert catalog_quality.json()["place_count"] > 0
    assert catalog_quality.json()["distance_matrix"]["loaded"] is True
    assert len(catalog_quality.json()["focus_city_counts"]) >= 8
    assert all(count > 0 for count in catalog_quality.json()["focus_city_counts"].values())
    fields = catalog_quality.json()["field_coverage"]["fields"]
    assert {"source_url", "image", "valid_hours", "rating", "review_count", "official_or_enriched_source"}.issubset(fields)
    assert all(0 <= item["percent"] <= 100 for item in fields.values())

    release = client.get(
        "/api/admin/release-readiness", headers={"X-Admin-Token": "local-support-dev"}
    )
    assert release.status_code == 200
    release_body = release.json()
    assert release_body["benchmark"]["version"] == "planner-quality-benchmark-v1"
    assert release_body["spec_audit"]["problem_count"] == 10
    assert release_body["release_gate"]["pass"] is False


def test_admin_catalog_search_is_authenticated_and_filterable():
    denied = client.get("/api/admin/catalog?q=ho")
    assert denied.status_code == 401
    assert client.get("/api/admin/catalog/export.csv?q=ho").status_code == 401
    assert client.get("/api/admin/catalog/quality").status_code == 401
    response = client.get(
        "/api/admin/catalog?q=ho&limit=5",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body["items"]) <= 5
    assert body["total"] >= len(body["items"])
    assert {"id", "name", "source_url", "tags"}.issubset(body["items"][0])
    exported = client.get(
        "/api/admin/catalog/export.csv?q=ho",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "id,name,kind,area,lat,lng" in exported.text.splitlines()[0]
    assert body["items"][0]["id"] in exported.text


def test_admin_recent_plans_is_authenticated_and_links_created_plans():
    import json

    generated = client.post("/api/plan/generate", json=PAYLOAD)
    result = json.loads(
        next(line for line in generated.text.splitlines() if line.startswith('data: {"type"'))[6:]
    )
    assert client.get("/api/admin/plans").status_code == 401
    response = client.get(
        "/api/admin/plans?q=api-session",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["token"] == result["token"]
    assert body["items"][0]["version"] == 1


def test_admin_users_is_authenticated_filterable_and_counts_owned_records():
    user = store.upsert_user_and_claim(
        "google", "admin-user@example.com", "Admin User", PAYLOAD["ma_phien"], "2026-08-05"
    )
    store.save(PAYLOAD["ma_phien"], {"tieu_de": "Local", "tom_tat": "", "ngay": []}, PAYLOAD)
    store.claim_session(PAYLOAD["ma_phien"], user["id"])

    denied = client.get("/api/admin/users")
    assert denied.status_code == 401
    response = client.get(
        "/api/admin/users?q=admin-user&limit=5",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "admin-user@example.com"
    assert body["items"][0]["plans"] == 1
    assert {"comments", "booking_requests", "feedback", "notifications"}.issubset(body["items"][0])


def test_admin_ai_usage_is_authenticated_and_reports_recent_calls():
    store.record_ai_usage("deepseek", "test-model", 123, 45, 0.001, 10, 300)
    denied = client.get("/api/admin/ai-usage")
    assert denied.status_code == 401
    response = client.get(
        "/api/admin/ai-usage?limit=5",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["provider"] == "deepseek"
    assert body["items"][0]["input_tokens"] == 123
    assert body["items"][0]["cost_usd"] == 0.001


def test_admin_events_is_authenticated_and_searchable():
    store.log("audit-session", "custom_audit_event", {"token": "audit-token"})
    store.log("other-session", "other_event", {"token": "other"})
    denied = client.get("/api/admin/events")
    assert denied.status_code == 401
    response = client.get(
        "/api/admin/events?q=audit-token&limit=5",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["su_kien"] == "custom_audit_event"
    assert body["items"][0]["ma_phien"] == "audit-session"


def test_admin_cleanup_expired_is_authenticated_and_logs_removed_count():
    expired = store.save("expired-admin-session", {"tieu_de": "Old", "tom_tat": "", "ngay": []}, PAYLOAD)
    active = store.save("active-admin-session", {"tieu_de": "Active", "tom_tat": "", "ngay": []}, PAYLOAD)
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    denied = client.post("/api/admin/maintenance/cleanup-expired")
    assert denied.status_code == 401
    response = client.post(
        "/api/admin/maintenance/cleanup-expired",
        headers={"X-Admin-Token": "local-support-dev"},
    )
    assert response.status_code == 200
    assert response.json()["removed_plans"] == 1
    assert store.get(expired.token) is None
    assert store.get(active.token) is not None
    assert store.events[-1]["su_kien"] == "admin_cleanup_expired"


def test_due_trip_notification_is_durable_owner_scoped_and_readable():
    payload = PAYLOAD | {
        "ngay_di": (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
    }
    generated = client.post("/api/plan/generate", json=payload)
    assert generated.status_code == 200
    notifications = client.get(
        "/api/notifications", headers={"X-Session-Id": PAYLOAD["ma_phien"]}
    ).json()["items"]
    assert len(notifications) == 1
    assert notifications[0]["loai"] == "trip_24h"
    assert notifications[0]["plan_title"]
    assert notifications[0]["da_doc"] is False
    assert client.patch(
        f"/api/notifications/{notifications[0]['id']}",
        json={"ma_phien": "wrong-session"},
    ).status_code == 404
    read = client.patch(
        f"/api/notifications/{notifications[0]['id']}",
        json={"ma_phien": PAYLOAD["ma_phien"]},
    )
    assert read.status_code == 200
    assert read.json()["thong_bao"]["da_doc"] is True
