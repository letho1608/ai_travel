import httpx
import pytest

from app.services.ai import (
    OfflineAIAdapter,
    _apply_copy,
    _error_kind,
    breaker,
    breaker_status,
)


def draft() -> dict:
    return {
        "tieu_de": "Cũ", "tom_tat": "Cũ", "luu_y": [],
        "ngay": [{"khoang_gio": [{"dia_diem_id": "osm-1", "mo_ta": "Cũ",
                                    "chi_phi": 10, "toa_do": {"lat": 1, "lng": 2}}]}],
    }


def test_ai_copy_can_only_change_narrative_fields():
    result = _apply_copy(
        draft(),
        {"tieu_de": "Mới", "tom_tat": "Tóm tắt",
         "mo_ta_theo_id": {"osm-1": "Mô tả mới"}, "luu_y": ["Lưu ý"]},
        {"osm-1"},
    )
    assert result["tieu_de"] == "Mới"
    assert result["ngay"][0]["khoang_gio"][0]["mo_ta"] == "Mô tả mới"
    assert result["ngay"][0]["khoang_gio"][0]["chi_phi"] == 10
    assert result["ngay"][0]["khoang_gio"][0]["toa_do"] == {"lat": 1, "lng": 2}


def test_ai_copy_rejects_unknown_inventory_id():
    with pytest.raises(ValueError, match="ngoài danh sách"):
        _apply_copy(draft(), {"mo_ta_theo_id": {"hallucinated": "Sai"}}, {"osm-1"})


def test_ai_breaker_status_reports_safe_diagnostics():
    breaker.record_success()
    status = breaker_status()
    assert status["state"] == "closed"
    assert status["allowing_calls"] is True
    assert status["recent_failures"] == 0


def test_deepseek_prompt_requests_locale_and_preserves_provenance(monkeypatch):
    import app.services.ai as ai_module

    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}], "usage": {}}

    class Client:
        def post(self, path, json):
            captured.update(json)
            return Response()

    monkeypatch.setattr(ai_module.store, "record_ai_usage", lambda *args: None)
    adapter = ai_module.DeepSeekAIAdapter.__new__(ai_module.DeepSeekAIAdapter)
    adapter.client = Client()
    adapter.assemble(draft(), {"osm-1"}, "ja")
    prompt = captured["messages"][1]["content"]
    assert "Japanese" in prompt
    assert "Preserve place names, proper nouns, source names" in prompt
    assert "Lịch trình du lịch" in prompt
    assert "context_goc" in prompt


def test_error_kind_classifies_provider_vs_validation_errors():
    request = httpx.Request("POST", "http://example.test")
    rate = httpx.HTTPStatusError("rate", request=request, response=httpx.Response(429))
    assert _error_kind(rate) == "rate_limited"
    server = httpx.HTTPStatusError("boom", request=request, response=httpx.Response(502))
    assert _error_kind(server) == "server_error"
    assert _error_kind(httpx.ConnectTimeout("slow")) == "network_error"
    assert _error_kind(httpx.ReadTimeout("slow")) == "network_error"
    assert _error_kind(ValueError("bad json")) == "validation_error"
    assert _error_kind(TypeError("no")) == "validation_error"


def test_breaker_validation_failures_do_not_trip():
    breaker.record_success()
    for _ in range(5):
        breaker.record_failure("validation_error")
    assert breaker.opened_at is None
    assert breaker.allow() is True
    status = breaker_status()
    assert status["validation_failures"] == 5
    assert status["recent_failures"] == 0


def test_breaker_provider_failures_trip_after_three():
    breaker.record_success()
    for _ in range(3):
        breaker.record_failure("rate_limited")
    assert breaker.opened_at is not None
    assert breaker.allow() is False
    status = breaker_status()
    assert status["state"] == "open"
    breaker.record_success()


def test_create_ai_adapter_falls_back_offline_in_local_without_key(monkeypatch):
    import app.services.ai as ai_module

    class FakeSettings:
        ai_mode = "groq"
        app_env = "local"
        ai_api_key = None

    monkeypatch.setattr(ai_module, "settings", FakeSettings())
    adapter = ai_module.create_ai_adapter()
    assert isinstance(adapter, OfflineAIAdapter)


def test_create_ai_adapter_raises_outside_local_without_key(monkeypatch):
    import app.services.ai as ai_module

    class FakeSettings:
        ai_mode = "groq"
        app_env = "production"
        ai_api_key = None

    monkeypatch.setattr(ai_module, "settings", FakeSettings())
    with pytest.raises(RuntimeError):
        ai_module.create_ai_adapter()
