import json
from datetime import UTC, datetime, timedelta
from math import isfinite

import httpx

from app.config import settings


class RoadTripUnavailable(RuntimeError):
    pass


class OSRMRoadTrip:
    MAX_RESPONSE_BYTES = 4_194_304

    def __init__(self, client: httpx.Client | None = None, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.osrm_base_url).rstrip("/")
        self.client = client or httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(12, connect=3),
        )

    def route(self, request) -> dict:
        stops = list(request.stops)
        route_stops = stops + [stops[0]] if request.round_trip else stops
        coordinates = ";".join(
            f"{stop.location.lng},{stop.location.lat}" for stop in route_stops
        )
        try:
            payload = self._bounded_payload(
                f"/route/v1/driving/{coordinates}",
                {"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            route = self._validated_route(payload, route_stops)
        except (
            httpx.HTTPError, ValueError, TypeError, KeyError,
            json.JSONDecodeError, RecursionError,
        ):
            from app.pipeline.routing import haversine_km
            legs = []
            total_dist = 0
            total_dur = 0
            coords = []
            for i in range(len(route_stops) - 1):
                p1 = route_stops[i].location
                p2 = route_stops[i + 1].location
                d_km = haversine_km(p1.lat, p1.lng, p2.lat, p2.lng) * 1.3
                d_meters = round(d_km * 1000)
                dur_secs = round(d_km / 50 * 3600)
                total_dist += d_meters
                total_dur += dur_secs
                coords.append([p1.lng, p1.lat])
                legs.append({
                    "from": route_stops[i].name,
                    "to": route_stops[i + 1].name,
                    "distance_meters": d_meters,
                    "duration_seconds": dur_secs,
                    "is_overwater": True,
                    "note": "Ước tính đường bộ / trung chuyển (có thể cần phà hoặc máy bay)",
                })
            coords.append([route_stops[-1].location.lng, route_stops[-1].location.lat])
            fetched = datetime.now(UTC)
            return {
                "stops": [stop.model_dump() for stop in route_stops],
                "legs": legs,
                "total_distance_meters": total_dist,
                "total_duration_seconds": total_dur,
                "geometry": {"type": "LineString", "coordinates": coords},
                "provenance": {
                    "provider": "Estimate_Fallback",
                    "profile": "transit_estimate",
                    "fetched_at": fetched.isoformat(),
                    "expires_at": (fetched + timedelta(days=7)).isoformat(),
                    "is_live": False,
                },
            }

        legs = [
            {
                "from": route_stops[index].name,
                "to": route_stops[index + 1].name,
                "distance_meters": round(leg["distance"]),
                "duration_seconds": round(leg["duration"]),
            }
            for index, leg in enumerate(route["legs"])
        ]
        fetched = datetime.now(UTC)
        return {
            "stops": [stop.model_dump() for stop in route_stops],
            "legs": legs,
            "total_distance_meters": round(route["distance"]),
            "total_duration_seconds": round(route["duration"]),
            "geometry": route["geometry"],
            "provenance": {
                "provider": "OSRM",
                "profile": "driving",
                "fetched_at": fetched.isoformat(),
                "expires_at": (fetched + timedelta(days=7)).isoformat(),
                "is_live": True,
            },
        }

    def _bounded_payload(self, path: str, params: dict) -> object:
        with self.client.stream("GET", path, params=params) as response:
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > self.MAX_RESPONSE_BYTES:
                raise ValueError("OSRM response exceeds size limit")
            chunks = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > self.MAX_RESPONSE_BYTES:
                    raise ValueError("OSRM response exceeds size limit")
                chunks.append(chunk)
        return json.loads(b"".join(chunks))

    @staticmethod
    def _validated_route(payload: object, route_stops: list) -> dict:
        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            raise ValueError("invalid OSRM response")
        routes = payload.get("routes")
        if not isinstance(routes, list) or len(routes) != 1 or not isinstance(routes[0], dict):
            raise ValueError("invalid OSRM routes")
        route = routes[0]
        waypoints = payload.get("waypoints")
        if not isinstance(waypoints, list) or len(waypoints) != len(route_stops):
            raise ValueError("invalid OSRM waypoints")
        for waypoint, stop in zip(waypoints, route_stops, strict=True):
            location = waypoint.get("location") if isinstance(waypoint, dict) else None
            if not isinstance(location, list) or len(location) != 2:
                raise ValueError("invalid OSRM waypoint")
            if abs(location[0] - stop.location.lng) > 0.001 or abs(location[1] - stop.location.lat) > 0.001:
                raise ValueError("OSRM waypoint does not match requested stop")
        legs = route.get("legs")
        if not isinstance(legs, list) or len(legs) != len(route_stops) - 1:
            raise ValueError("invalid OSRM legs")
        for leg in legs:
            if not isinstance(leg, dict):
                raise TypeError("invalid OSRM leg")
            OSRMRoadTrip._validate_metrics(leg, 100_000_000)
        OSRMRoadTrip._validate_metrics(route, 1_000_000_000)
        for field in ("distance", "duration"):
            leg_total = sum(leg[field] for leg in legs)
            tolerance = max(1.0, leg_total * 0.01)
            if abs(route[field] - leg_total) > tolerance:
                raise ValueError("OSRM route total does not match legs")
        geometry = route.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
            raise ValueError("invalid OSRM geometry")
        points = geometry.get("coordinates")
        if not isinstance(points, list) or not 2 <= len(points) <= 50_000:
            raise ValueError("invalid OSRM geometry points")
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("invalid OSRM coordinate")
            lng, lat = point
            if not all(
                isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
                for value in point
            ) or not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise ValueError("invalid OSRM coordinate")
        requested_endpoints = (
            (route_stops[0].location.lng, route_stops[0].location.lat),
            (route_stops[-1].location.lng, route_stops[-1].location.lat),
        )
        for actual, requested in zip((points[0], points[-1]), requested_endpoints, strict=True):
            if abs(actual[0] - requested[0]) > 0.001 or abs(actual[1] - requested[1]) > 0.001:
                raise ValueError("OSRM geometry does not match requested endpoints")
        return route

    @staticmethod
    def _validate_metrics(item: dict, maximum: int) -> None:
        for field in ("distance", "duration"):
            value = item.get(field)
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(value)
                or value < 0
                or value > maximum
            ):
                raise ValueError("invalid OSRM metric")


roadtrip = OSRMRoadTrip()
