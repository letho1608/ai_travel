from app.services import osm_verify


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_verify_place_name_rejects_non_travel_shop_results(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_verify, "CACHE_PATH", tmp_path / "osm_verify_cache.json")

    def fake_get(*args, **kwargs):
        return FakeResponse(
            [
                {
                    "class": "shop",
                    "type": "flooring",
                    "display_name": "Sàn gỗ Nguyễn Kim, Cầu Giấy, Hà Nội, Việt Nam",
                    "lat": "21.03",
                    "lon": "105.80",
                    "osm_type": "node",
                    "osm_id": 123,
                    "name": "Sàn gỗ Nguyễn Kim",
                }
            ]
        )

    monkeypatch.setattr(osm_verify.httpx, "get", fake_get)

    assert osm_verify.verify_place_name("Sàn gỗ Nguyễn Kim", (21.0285, 105.8542)) is None


def test_verify_place_name_queries_requested_city(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_verify, "CACHE_PATH", tmp_path / "osm_verify_cache.json")
    captured = {}

    def fake_get(*args, **kwargs):
        captured["params"] = kwargs.get("params", {})
        return FakeResponse([])

    monkeypatch.setattr(osm_verify.httpx, "get", fake_get)
    assert osm_verify.verify_place_name("Zzz Lunar Bridge", (16.0544, 108.2022), "Đà Nẵng") is None
    assert captured["params"]["q"] == "Zzz Lunar Bridge, Đà Nẵng, Vietnam"
    assert "Hanoi" not in captured["params"]["q"]


def test_verify_place_name_accepts_attraction_outside_hanoi(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_verify, "CACHE_PATH", tmp_path / "osm_verify_cache.json")

    def fake_get(*args, **kwargs):
        return FakeResponse(
            [
                {
                    "class": "tourism",
                    "type": "attraction",
                    "display_name": "Zzz Marble Tower, Ngũ Hành Sơn, Đà Nẵng, Việt Nam",
                    "lat": "16.0035",
                    "lon": "108.2633",
                    "osm_type": "node",
                    "osm_id": 987654321,
                    "name": "Zzz Marble Tower",
                }
            ]
        )

    monkeypatch.setattr(osm_verify.httpx, "get", fake_get)
    place = osm_verify.verify_place_name("Zzz Marble Tower", (16.0544, 108.2022), "Đà Nẵng")
    assert place is not None
    assert place.area == "Đà Nẵng"
    assert abs(place.lat - 16.0035) < 0.001

