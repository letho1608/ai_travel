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

