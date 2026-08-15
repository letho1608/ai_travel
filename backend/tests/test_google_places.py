from dataclasses import replace

from app.services import google_places


def test_google_places_readiness_fails_closed_without_key(monkeypatch):
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key=None),
    )

    status = google_places.google_places_readiness()

    assert status["ready"] is False
    assert status["api_key_configured"] is False
    assert status["api_key_length"] == 0
    assert any("GOOGLE_MAPS_API_KEY" in blocker for blocker in status["blockers"])


def test_google_places_readiness_reports_caps_without_exposing_key(monkeypatch):
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(
            google_places.settings,
            google_maps_api_key="secret-maps-key",
            google_places_runtime_per_plan_cap=3,
            google_places_text_search_daily_cap=20,
            google_places_text_search_monthly_cap=100,
        ),
    )

    status = google_places.google_places_readiness()

    assert status["ready"] is True
    assert status["api_key_configured"] is True
    assert status["api_key_length"] == len("secret-maps-key")
    assert "secret-maps-key" not in str(status)
    assert status["runtime_per_plan_cap"] == 3


def test_google_enrichment_applies_rating_review_to_slot_and_evidence():
    slot = {
        "dia_diem_id": "osm-node-1",
        "ten_dia_diem": "Hồ Gươm",
        "bang_chung": {
            "xep_hang": {
                "du_lieu_thuc_te": {"rating": None, "so_nhan_xet": None},
                "du_lieu_thieu": ["rating", "so_review", "anh"],
            }
        },
    }
    enriched = {
        "google_place_id": "google-place-1",
        "google_maps_url": "https://maps.google.com/?cid=1",
        "google_rating": 4.6,
        "google_user_rating_count": 1234,
        "google_updated_at": "2026-08-15T00:00:00+00:00",
    }

    google_places._apply_enrichment(slot, enriched, "test-key")

    assert slot["thong_tin_danh_gia"] == {
        "rating": 4.6,
        "so_nhan_xet": 1234,
        "nguon": "Google Places API",
        "nguon_url": "https://maps.google.com/?cid=1",
        "lay_luc": "2026-08-15T00:00:00+00:00",
    }
    assert slot["google_review_url"] == "https://maps.google.com/?cid=1"
    ranking = slot["bang_chung"]["xep_hang"]
    assert ranking["du_lieu_thuc_te"] == {"rating": 4.6, "so_nhan_xet": 1234}
    assert "rating" not in ranking["du_lieu_thieu"]
    assert "so_review" not in ranking["du_lieu_thieu"]
    assert slot["bang_chung"]["thong_tin_danh_gia"]["nguon"] == "Google Places API"
