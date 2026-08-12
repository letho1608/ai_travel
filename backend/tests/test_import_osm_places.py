import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_osm_places.py"
spec = importlib.util.spec_from_file_location("import_osm_places", SCRIPT)
import_osm_places = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(import_osm_places)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_google_enrichment_adds_rating_maps_and_photo(monkeypatch):
    place = {
        "id": "osm-node-1",
        "name": "Hoan Kiem Lake",
        "kind": "dia_danh",
        "area": "Hoan Kiem",
        "address": "",
        "lat": 21.0287,
        "lng": 105.8522,
    }

    def fake_urlopen(request, timeout):
        assert timeout == 30
        assert request.headers["X-goog-api-key"] == "test-key"
        assert "places.photos" in request.headers["X-goog-fieldmask"]
        return FakeResponse({
            "places": [{
                "id": "google-place-1",
                "formattedAddress": "Hoan Kiem, Hanoi",
                "googleMapsUri": "https://maps.google.com/?cid=1",
                "rating": 4.6,
                "userRatingCount": 1234,
                "photos": [{"name": "places/google-place-1/photos/photo-1"}],
            }]
        })

    monkeypatch.setattr(import_osm_places.urllib.request, "urlopen", fake_urlopen)

    enriched = import_osm_places.enrich_with_google(place, "test-key")

    assert enriched["google_place_id"] == "google-place-1"
    assert enriched["google_rating"] == 4.6
    assert enriched["google_user_rating_count"] == 1234
    assert enriched["google_maps_url"] == "https://maps.google.com/?cid=1"
    assert enriched["address"] == "Hoan Kiem, Hanoi"
    assert enriched["image_credit"] == "Google Places"
    assert "places/google-place-1/photos/photo-1/media" in enriched["image_url"]
    assert "maxWidthPx=800" in enriched["image_url"]


def test_google_enrichment_can_skip_photo_to_protect_free_cap(monkeypatch):
    place = {
        "id": "osm-node-1",
        "name": "Hoan Kiem Lake",
        "kind": "dia_danh",
        "area": "Hoan Kiem",
        "address": "",
        "lat": 21.0287,
        "lng": 105.8522,
    }

    monkeypatch.setattr(import_osm_places, "fetch_google_place", lambda *_args: {
        "id": "google-place-1",
        "photos": [{"name": "places/google-place-1/photos/photo-1"}],
    })

    enriched = import_osm_places.enrich_with_google(place, "test-key", include_photo=False)

    assert enriched["google_place_id"] == "google-place-1"
    assert "image_url" not in enriched


def test_checked_google_limit_defaults_and_blocks_paid_overrun():
    assert import_osm_places.checked_google_limit(0, 5000) == 100
    assert import_osm_places.checked_google_limit(200, 5000) == 200
    assert import_osm_places.checked_google_limit(2000, 100) == 100
    try:
        import_osm_places.checked_google_limit(951, 5000)
    except SystemExit as exc:
        assert "free-tier cap" in str(exc)
    else:
        raise AssertionError("expected limit above photo cap to stop")
