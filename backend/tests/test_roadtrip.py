import json
from typing import ClassVar

import pytest

from app.schemas import RoadTripRequest
from app.services.roadtrip import OSRMRoadTrip, RoadTripUnavailable


class StubResponse:
    headers: ClassVar[dict[str, str]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def payload(self) -> dict:
        return {"code": "Ok", "waypoints": [{"location": [105.8542, 21.0285]},
                {"location": [105.9745, 20.2506]}],
                "routes": [{"distance": 100000.4, "duration": 7200.2,
                "geometry": {"type": "LineString", "coordinates": [[105.8542,21.0285],[105.9745,20.2506]]},
                "legs": [{"distance": 100000.4, "duration": 7200.2}]}]}

    def iter_bytes(self):
        yield json.dumps(self.payload()).encode()


class StubClient:
    def stream(self, *args, **kwargs) -> StubResponse:
        return StubResponse()


def test_multicity_route_keeps_osrm_geometry_and_leg_metrics():
    request = RoadTripRequest(stops=[
        {"name": "Hà Nội", "location": {"lat": 21.0285, "lng": 105.8542}},
        {"name": "Ninh Bình", "location": {"lat": 20.2506, "lng": 105.9745}},
    ])
    result = OSRMRoadTrip(StubClient()).route(request)  # type: ignore[arg-type]
    assert result["legs"][0]["from"] == "Hà Nội"
    assert result["total_distance_meters"] == 100000
    assert result["geometry"]["type"] == "LineString"
    assert result["provenance"]["provider"] == "OSRM"


@pytest.mark.parametrize("route", [
    {"distance": 1, "duration": 1, "geometry": {"type": "LineString", "coordinates": []},
     "legs": [{"distance": 1, "duration": 1}]},
    {"distance": float("nan"), "duration": 1,
     "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
     "legs": [{"distance": 1, "duration": 1}]},
    {"distance": 1, "duration": 1,
     "geometry": {"type": "LineString", "coordinates": [[0, 0], [181, 1]]},
     "legs": [{"distance": 1, "duration": 1}]},
])
def test_malformed_osrm_route_fails_closed(route):
    class MalformedResponse(StubResponse):
        def payload(self):
            result = super().payload()
            result["routes"] = [route]
            return result

    class MalformedClient:
        def stream(self, *args, **kwargs):
            return MalformedResponse()

    request = RoadTripRequest(stops=[
        {"name": "A", "location": {"lat": 1, "lng": 1}},
        {"name": "B", "location": {"lat": 2, "lng": 2}},
    ])
    with pytest.raises(RoadTripUnavailable, match="provider is unavailable"):
        OSRMRoadTrip(MalformedClient()).route(request)


def test_duplicate_coordinates_are_rejected():
    with pytest.raises(ValueError):
        RoadTripRequest(stops=[
            {"name": "A", "location": {"lat": 1, "lng": 1}},
            {"name": "B", "location": {"lat": 1, "lng": 1}},
        ])


def test_any_duplicate_coordinate_and_blank_sanitized_name_are_rejected():
    with pytest.raises(ValueError):
        RoadTripRequest(stops=[
            {"name": "A", "location": {"lat": 1, "lng": 1}},
            {"name": "B", "location": {"lat": 2, "lng": 2}},
            {"name": "C", "location": {"lat": 1, "lng": 1}},
        ])
    with pytest.raises(ValueError):
        RoadTripRequest(stops=[
            {"name": "  < >  ", "location": {"lat": 1, "lng": 1}},
            {"name": "B", "location": {"lat": 2, "lng": 2}},
        ])


def test_osrm_geometry_must_match_requested_endpoints():
    class WrongGeometryResponse(StubResponse):
        def payload(self):
            result = super().payload()
            result["routes"][0]["geometry"]["coordinates"][-1] = [104.0, 19.0]
            return result

    class WrongGeometryClient:
        def stream(self, *args, **kwargs):
            return WrongGeometryResponse()

    request = RoadTripRequest(stops=[
        {"name": "A", "location": {"lat": 21.0285, "lng": 105.8542}},
        {"name": "B", "location": {"lat": 20.2506, "lng": 105.9745}},
    ])
    with pytest.raises(RoadTripUnavailable, match="provider is unavailable"):
        OSRMRoadTrip(WrongGeometryClient()).route(request)


def test_oversized_osrm_response_fails_closed():
    class OversizedResponse(StubResponse):
        headers: ClassVar[dict[str, str]] = {
            "content-length": str(OSRMRoadTrip.MAX_RESPONSE_BYTES + 1)
        }

    class OversizedClient:
        def stream(self, *args, **kwargs):
            return OversizedResponse()

    request = RoadTripRequest(stops=[
        {"name": "A", "location": {"lat": 1, "lng": 1}},
        {"name": "B", "location": {"lat": 2, "lng": 2}},
    ])
    with pytest.raises(RoadTripUnavailable, match="provider is unavailable"):
        OSRMRoadTrip(OversizedClient()).route(request)
