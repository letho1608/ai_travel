import io
import json
import urllib.error
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

    assert slot["google_maps_url"] == "https://www.google.com/maps/place/?q=place_id:google-place-1"
    assert "query_place_id=google-place-1" not in slot["google_maps_url"]
    assert slot["google_review_url"] == slot["google_maps_url"]
    assert slot["thong_tin_danh_gia"] == {
        "rating": 4.6,
        "so_nhan_xet": 1234,
        "nguon": "Google Places API",
        "nguon_url": "https://maps.google.com/?cid=1",
        "lay_luc": "2026-08-15T00:00:00+00:00",
    }
    ranking = slot["bang_chung"]["xep_hang"]
    assert ranking["du_lieu_thuc_te"] == {"rating": 4.6, "so_nhan_xet": 1234}
    assert "rating" not in ranking["du_lieu_thieu"]
    assert "so_review" not in ranking["du_lieu_thieu"]
    assert slot["bang_chung"]["thong_tin_danh_gia"]["nguon"] == "Google Places API"


class FakeUrlOpen:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload


def test_search_named_place_returns_google_hit(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key="test-key"),
    )

    def fake_urlopen(request, timeout=8):
        return FakeUrlOpen(
            {
                "places": [
                    {
                        "id": "ChIJtuanChau",
                        "displayName": {"text": "Đảo Tuần Châu"},
                        "location": {"latitude": 20.9226, "longitude": 106.9894},
                        "types": ["tourist_attraction"],
                        "googleMapsUri": "https://maps.google.com/?cid=tuan-chau",
                        "rating": 4.4,
                        "userRatingCount": 3200,
                    }
                ]
            }
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    place = google_places.search_named_place("đảo tuần châu", (20.9108, 107.1839), "Hạ Long")
    assert place is not None
    assert place.id == "google-ChIJtuanChau"
    assert place.name == "Đảo Tuần Châu"
    assert place.source == "Google Places"
    assert place.kind == "dia_danh"
    assert place.google_place_id == "ChIJtuanChau"


def test_search_named_place_keeps_vietnam_hit_and_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key="test-key"),
    )

    def fake_urlopen(request, timeout=8):
        return FakeUrlOpen(
            {
                "places": [
                    {
                        "id": "ChIJcauRong",
                        "displayName": {"text": "Cầu Rồng"},
                        "location": {"latitude": 16.0611, "longitude": 108.2272},
                        "types": ["tourist_attraction"],
                        "googleMapsUri": "https://maps.google.com/?cid=cau-rong",
                        "photos": [{"name": "places/ChIJcauRong/photos/abc"}],
                    }
                ]
            }
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    place = google_places.search_named_place("cầu rồng", (16.0544, 108.2022), "Đà Nẵng")
    assert place is not None
    assert place.name == "Cầu Rồng"
    assert abs(place.lat - 16.0611) < 0.001
    assert place.image_url
    assert "places/ChIJcauRong/photos/abc/media" in place.image_url
    assert place.image_credit == "Google Places"


def test_search_named_place_rejects_hit_outside_plan_area(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key="test-key"),
    )
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=8):
        data = getattr(request, "data", None)
        if data:
            captured["body"] = json.loads(data.decode())
        return FakeUrlOpen(
            {
                "places": [
                    {
                        "id": "ChIJgocDaLat",
                        "displayName": {"text": "Góc Đà Lạt Coffee"},
                        "formattedAddress": "Đà Lạt, Lâm Đồng, Việt Nam",
                        "location": {"latitude": 11.9404, "longitude": 108.4583},
                        "types": ["cafe", "coffee_shop"],
                        "googleMapsUri": "https://maps.google.com/?cid=goc-da-lat",
                    }
                ]
            }
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    place = google_places.search_named_place("Góc đà Lạt coffee", (21.0285, 105.8542), "Hà Nội")
    assert place is None
    assert "hà nội" in str(captured["body"]["textQuery"]).casefold()


def test_search_named_place_falls_back_to_legacy_text_search(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key="test-key"),
    )

    def fake_urlopen(request, timeout=8):
        url = getattr(request, "full_url", str(request))
        if "places.googleapis.com" in url:
            raise urllib.error.HTTPError(
                google_places.GOOGLE_TEXT_SEARCH_URL,
                403,
                "Forbidden",
                {},
                io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED"}}'),
            )
        return FakeUrlOpen(
            {
                "status": "OK",
                "results": [
                    {
                        "place_id": "ChIJgocDaLat",
                        "name": "Góc đà Lạt coffee",
                        "formatted_address": "Số 28 A19, Tây Mỗ, Hà Nội, Việt Nam",
                        "geometry": {"location": {"lat": 21.008078, "lng": 105.7324507}},
                        "types": ["cafe", "food", "point_of_interest"],
                        "photos": [{"photo_reference": "photo-ref-1"}],
                    }
                ],
            }
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    place = google_places.search_named_place("Góc đà Lạt coffee", (21.0285, 105.8542), "Hà Nội")
    assert place is not None
    assert place.name == "Góc đà Lạt coffee"
    assert place.kind == "cafe"
    assert abs(place.lat - 21.008078) < 0.001
    assert place.image_url
    assert "photo-ref-1" in place.image_url
    assert "Hà Nội" in place.area


def test_enrich_does_not_count_blocked_places_api(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(
            google_places.settings,
            google_maps_api_key="test-key",
            google_places_runtime_photos=False,
            google_places_runtime_hours=False,
        ),
    )

    def fake_urlopen(request, timeout=8):
        raise urllib.error.HTTPError(
            google_places.GOOGLE_TEXT_SEARCH_URL,
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED"}}'),
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    plan = {
        "ngay": [
            {
                "khoang_gio": [
                    {
                        "dia_diem_id": "osm-node-1",
                        "ten_dia_diem": "Hồ Gươm",
                        "toa_do": {"lat": 21.0285, "lng": 105.852},
                    },
                    {
                        "dia_diem_id": "osm-node-2",
                        "ten_dia_diem": "Văn Miếu",
                        "toa_do": {"lat": 21.0278, "lng": 105.835},
                    },
                ]
            }
        ]
    }

    enriched = google_places.enrich_plan_with_google(plan)

    assert enriched["google_places"]["text_search_requests_this_plan"] == 0
    assert enriched["google_places"]["text_search_daily_used"] == 0
    assert enriched["google_places"]["quota_blocked"] == 1


def test_nearest_google_place_picks_closer_duplicate_name():
    far = {
        "id": "far-hoang-nhi",
        "displayName": {"text": "QUÁN HOÀNG NHI"},
        "location": {"latitude": 11.95, "longitude": 108.45},
    }
    near = {
        "id": "near-hoang-nhi",
        "displayName": {"text": "Ẩm thực chay Hoàng Nhi"},
        "location": {"latitude": 11.9418, "longitude": 108.4339},
    }
    chosen = google_places._nearest_google_place([far, near], 11.94182, 108.43387)
    assert chosen is not None
    assert chosen["id"] == "near-hoang-nhi"


def test_resolve_maps_place_url_uses_cached_place_id(tmp_path, monkeypatch):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    cache = {
        "metadata": {},
        "places": {
            "osm-cafe-1": {
                "google_place_id": "ChIJ-an-cafe",
                "display_name": "An Cafe",
            }
        },
    }
    google_places._save_cache(cache)
    url = google_places.resolve_maps_place_url(
        name="An Cafe",
        lat=11.9418,
        lng=108.4338,
        city="Đà Lạt",
        slot_id="osm-cafe-1",
    )
    assert "q=place_id:ChIJ-an-cafe" in url
    assert "/maps/place/" in url


def test_resolve_maps_place_url_uses_legacy_search_when_places_new_is_forbidden(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(google_places.settings, google_maps_api_key="test-key"),
    )

    def fake_urlopen(request, timeout=8):
        url = getattr(request, "full_url", str(request))
        if "places.googleapis.com" in url:
            raise urllib.error.HTTPError(
                google_places.GOOGLE_NEARBY_SEARCH_URL,
                403,
                "Forbidden",
                {},
                io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED"}}'),
            )
        return FakeUrlOpen(
            {
                "status": "OK",
                "results": [
                    {
                        "place_id": "ChIJ-far-an",
                        "name": "Cafe An - an coffee",
                        "geometry": {"location": {"lat": 11.95004, "lng": 108.43258}},
                    },
                    {
                        "place_id": "ChIJ-near-an-cafe",
                        "name": "An Cafe",
                        "geometry": {"location": {"lat": 11.9416988, "lng": 108.4338265}},
                    },
                ],
            }
        )

    monkeypatch.setattr(google_places.urllib.request, "urlopen", fake_urlopen)
    url = google_places.resolve_maps_place_url(
        name="An Cafe",
        lat=11.9418201,
        lng=108.4338744,
        city="Đà Lạt",
        slot_id="osm-node-4206500720",
    )
    assert url == "https://www.google.com/maps/place/?q=place_id:ChIJ-near-an-cafe"
    assert "query=" not in url
