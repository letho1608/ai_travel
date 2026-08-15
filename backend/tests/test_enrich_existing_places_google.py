import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "enrich_existing_places_google.py"
spec = importlib.util.spec_from_file_location("enrich_existing_places_google", SCRIPT)
enrich_script = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(enrich_script)


def test_enrich_payload_updates_only_missing_google_fields(monkeypatch):
    payload = {
        "metadata": {},
        "places": [
            {"id": "a", "name": "A", "lat": 21.0, "lng": 105.8},
            {
                "id": "b",
                "name": "B",
                "lat": 21.0,
                "lng": 105.81,
                "google_place_id": "already",
                "google_maps_url": "https://maps.google.com/?cid=2",
                "google_rating": 4.2,
                "google_user_rating_count": 42,
            },
            {"id": "c", "name": "C", "lat": 21.0, "lng": 105.82},
        ],
    }

    calls = []

    def fake_enrich(place, api_key, include_photo=True):
        calls.append((place["id"], include_photo))
        enriched = dict(place)
        enriched.update(
            {
                "google_place_id": f"google-{place['id']}",
                "google_maps_url": f"https://maps.google.com/?cid={place['id']}",
                "google_rating": 4.6,
                "google_user_rating_count": 123,
            }
        )
        return enriched

    monkeypatch.setattr(enrich_script, "enrich_with_google", fake_enrich)

    updated, run = enrich_script.enrich_payload(
        payload,
        "test-key",
        limit=2,
        include_photos=False,
    )

    assert calls == [("a", False), ("c", False)]
    assert updated["places"][0]["google_place_id"] == "google-a"
    assert updated["places"][1]["google_place_id"] == "already"
    assert updated["places"][2]["google_user_rating_count"] == 123
    assert run["selected_count"] == 2
    assert run["enriched_count"] == 2
    assert run["source"] == "Google Places API Text Search"
    assert updated["metadata"]["google_places_latest_enrichment"] == run


def test_enrich_payload_respects_offset_and_refresh_existing(monkeypatch):
    payload = {
        "places": [
            {"id": "a", "name": "A", "lat": 21.0, "lng": 105.8},
            {
                "id": "b",
                "name": "B",
                "lat": 21.0,
                "lng": 105.81,
                "google_place_id": "already",
                "google_maps_url": "https://maps.google.com/?cid=2",
                "google_rating": 4.2,
                "google_user_rating_count": 42,
            },
        ]
    }
    calls = []

    def fake_enrich(place, api_key, include_photo=True):
        calls.append(place["id"])
        enriched = dict(place)
        enriched["google_rating"] = 4.8
        return enriched

    monkeypatch.setattr(enrich_script, "enrich_with_google", fake_enrich)

    updated, run = enrich_script.enrich_payload(
        payload,
        "test-key",
        limit=1,
        offset=1,
        refresh_existing=True,
    )

    assert calls == ["b"]
    assert updated["places"][1]["google_rating"] == 4.8
    assert run["selected_count"] == 1
