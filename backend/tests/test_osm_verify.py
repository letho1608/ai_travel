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


def test_verify_place_name_accepts_jsonv2_category_island_after_empty_viewbox(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_verify, "CACHE_PATH", tmp_path / "osm_verify_cache.json")
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs.get("params", {}))
        if kwargs.get("params", {}).get("bounded") == 1:
            return FakeResponse([])
        return FakeResponse(
            [
                {
                    "category": "place",
                    "type": "island",
                    "display_name": "Đảo San Hô Ảo, Hạ Long, Quảng Ninh, Việt Nam",
                    "lat": "20.9200",
                    "lon": "106.9800",
                    "osm_type": "relation",
                    "osm_id": 19465350,
                    "name": "Đảo San Hô Ảo",
                },
                {
                    "category": "place",
                    "type": "island",
                    "display_name": "Đảo xa, Hạ Long, Quảng Ninh, Việt Nam",
                    "lat": "20.7000",
                    "lon": "107.2000",
                    "osm_type": "way",
                    "osm_id": 222,
                    "name": "Đảo xa",
                },
            ]
        )

    monkeypatch.setattr(osm_verify.httpx, "get", fake_get)
    place = osm_verify.verify_place_name("đảo san hô ảo", (20.9100, 107.1830), "Hạ Long")
    assert place is not None
    assert place.name == "Đảo San Hô Ảo"
    assert place.id == "osm-verified-relation-19465350"
    assert abs(place.lat - 20.92) < 0.001
    assert any(params.get("bounded") == 1 for params in calls)
    assert any("bounded" not in params for params in calls)


def test_catalog_match_finds_cau_rong_from_hanoi_origin():
    place = osm_verify._catalog_match("cầu rồng", (21.0285, 105.8542))
    assert place is not None
    assert place.name == "Cầu Rồng"


def test_catalog_match_finds_tuan_chau():
    place = osm_verify._catalog_match("đảo tuần châu", (20.8589, 107.0803))
    assert place is not None
    assert place.id == "curated-dao-tuan-chau"
    assert place.name == "Đảo Tuần Châu"


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


def test_verify_place_name_nationwide_finds_place_far_from_origin(monkeypatch, tmp_path):
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
    nearby = osm_verify.verify_place_name("Zzz Marble Tower", (21.0285, 105.8542), "Hà Nội")
    assert nearby is None
    far = osm_verify.verify_place_name(
        "Zzz Marble Tower", (21.0285, 105.8542), "Hà Nội", nationwide=True
    )
    assert far is not None
    assert abs(far.lat - 16.0035) < 0.001


def test_verify_place_name_nationwide_finds_cafe_without_plan_city(monkeypatch, tmp_path):
    monkeypatch.setattr(osm_verify, "CACHE_PATH", tmp_path / "osm_verify_cache.json")
    queries: list[str] = []

    def fake_get(*args, **kwargs):
        params = kwargs.get("params") or {}
        queries.append(str(params.get("q") or ""))
        return FakeResponse(
            [
                {
                    "class": "amenity",
                    "type": "cafe",
                    "display_name": "Góc Đà Lạt Coffee, Đà Lạt, Lâm Đồng, Việt Nam",
                    "lat": "11.9404",
                    "lon": "108.4583",
                    "osm_type": "node",
                    "osm_id": 555,
                    "name": "Góc Đà Lạt Coffee",
                }
            ]
        )

    monkeypatch.setattr(osm_verify.httpx, "get", fake_get)
    cafe = osm_verify.verify_place_name(
        "Góc đà Lạt coffee", (21.0285, 105.8542), "Hà Nội", nationwide=True
    )
    assert cafe is not None
    assert cafe.name == "Góc Đà Lạt Coffee"
    assert queries and "hà nội" not in queries[0].casefold()

