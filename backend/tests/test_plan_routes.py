from types import SimpleNamespace

import httpx
import pytest

from app.services import plan_routes

_ORIGINAL_CLIENT = httpx.Client


def _slots(*pairs: tuple[str, float, float]) -> list[dict]:
    return [
        {"dia_diem_id": place_id, "toa_do": {"lat": lat, "lng": lng}}
        for place_id, lat, lng in pairs
    ]


def _line_string(*points) -> dict:
    return {"type": "LineString", "coordinates": list(points)}


@pytest.fixture
def routing(monkeypatch):
    settings = SimpleNamespace(plan_route_geometry=True, osrm_base_url="https://router.project-osrm.org")
    monkeypatch.setattr(plan_routes, "settings", settings)
    monkeypatch.setattr(plan_routes, "_cache", {})
    return settings


class FakeOSRM:
    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch
        self.calls: list[httpx.Request] = []

    def install(self, handler):
        def respond(request):
            self.calls.append(request)
            return handler(request)

        client = _ORIGINAL_CLIENT(transport=httpx.MockTransport(respond))
        self.monkeypatch.setattr(plan_routes.httpx, "Client", lambda *args, **kwargs: client)


@pytest.fixture
def fake_osrm(monkeypatch):
    return FakeOSRM(monkeypatch)


def test_resolve_day_route_with_live_osrm(routing, fake_osrm):
    slots = _slots(("a", 21.0285, 105.8542), ("b", 20.2506, 105.9745))

    def handler(request):
        assert request.url.path.endswith("/route/v1/driving/105.8542,21.0285;105.9745,20.2506")
        return httpx.Response(
            200, json={"code": "Ok", "routes": [{"geometry": _line_string([105.8542, 21.0285], [105.9745, 20.2506])}]}
        )

    fake_osrm.install(handler)
    result = plan_routes.resolve_day_route(slots)
    assert result == {"type": "LineString", "coordinates": [[105.8542, 21.0285], [105.9745, 20.2506]]}
    assert plan_routes._cache["a|b"] == [[105.8542, 21.0285], [105.9745, 20.2506]]
    assert len(fake_osrm.calls) == 1


def test_resolve_day_route_hits_cache_without_network(routing, fake_osrm):
    plan_routes._cache["a|b"] = [[105.8542, 21.0285], [105.9745, 20.2506]]
    fake_osrm.install(lambda request: httpx.Response(500))
    result = plan_routes.resolve_day_route(_slots(("a", 21.0285, 105.8542), ("b", 20.2506, 105.9745)))
    assert result["type"] == "LineString"
    assert fake_osrm.calls == []


def test_resolve_day_route_falls_back_on_transport_failure(routing, fake_osrm):
    fake_osrm.install(lambda request: httpx.Response(500))
    assert plan_routes.resolve_day_route(_slots(("a", 21.0285, 105.8542), ("b", 20.2506, 105.9745))) is None
    # failed fetches are never cached
    assert plan_routes._cache == {}


@pytest.mark.parametrize("payload", [
    {"code": "NoRoute"},
    {"code": "Ok", "routes": []},
    {"code": "Ok", "routes": [{"geometry": {"type": "Point", "coordinates": [1, 2]}}]},
    {"code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": [[181, 0], [1, 1]]}}]},
    {"code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": [[105.9, 21.0], [106.0, 21.9]]}}]},
])
def test_resolve_day_route_falls_back_on_invalid_response(routing, fake_osrm, payload):
    fake_osrm.install(lambda request: httpx.Response(200, json=payload))
    assert plan_routes.resolve_day_route(_slots(("a", 21.0285, 105.8542), ("b", 20.2506, 105.9745))) is None


def test_resolve_day_route_skipped_when_disabled_or_too_few_slots(routing):
    routing.plan_route_geometry = False
    assert plan_routes.resolve_day_route(_slots(("a", 1, 2), ("b", 3, 4))) is None
    routing.plan_route_geometry = True
    assert plan_routes.resolve_day_route(_slots(("a", 1, 2))) is None
    assert plan_routes.resolve_day_route(_slots()) is None


def test_enrich_plan_routes_attaches_geometry_per_day(routing):
    plan_routes._cache["a|b"] = [[105.8542, 21.0285], [105.9745, 20.2506]]
    plan = {
        "ngay": [
            {"thu_tu": 1, "khoang_gio": _slots(("a", 21.0285, 105.8542), ("b", 20.2506, 105.9745))},
            {"thu_tu": 2, "khoang_gio": _slots(("c", 1, 2), ("d", 3, 4))},
        ],
    }
    result = plan_routes.enrich_plan_routes(plan)
    assert result["ngay"][0]["tuyen_duong"]["type"] == "LineString"
    assert "tuyen_duong" not in result["ngay"][1]


def test_enrich_plan_routes_noop_when_disabled(routing):
    routing.plan_route_geometry = False
    plan = {"ngay": [{"thu_tu": 1, "khoang_gio": _slots(("a", 1, 2), ("b", 3, 4))}]}
    assert plan_routes.enrich_plan_routes(plan) is plan
    assert "tuyen_duong" not in plan["ngay"][0]