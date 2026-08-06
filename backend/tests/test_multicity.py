from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas import MultiCityRequest
from app.services.inventory import InventoryUnavailable
from app.services.multicity import MultiCityPlanner
from app.services.store import MemoryStore


class RouteStub:
    def route(self, request):
        return {"stops": [stop.model_dump() for stop in request.stops],
                "legs": [{"from": "Hà Nội", "to": "Đà Nẵng"}],
                "provenance": {"provider": "OSRM", "is_live": True}}


class InventoryStub:
    @staticmethod
    def provenance():
        fetched = datetime.now(UTC) - timedelta(minutes=1)
        return {"provider": "Amadeus", "is_live": True,
                "fetched_at": fetched.isoformat(),
                "expires_at": (fetched + timedelta(minutes=15)).isoformat()}

    def hotels(self, request):
        return {"offers": [{"id": f"hotel-{request.latitude}", "price": "100"}],
                "provenance": self.provenance()}

    def flights(self, request):
        return {"offers": [{"id": f"flight-{request.origin}-{request.destination}",
                             "price": "50"}],
                "provenance": self.provenance()}


def request():
    return MultiCityRequest(
        stops=[
            {"name": "Hà Nội", "location": {"lat": 21.0285, "lng": 105.8542},
             "iata_code": "HAN", "arrival_date": date(2026, 9, 1),
             "departure_date": date(2026, 9, 3)},
            {"name": "Đà Nẵng", "location": {"lat": 16.0544, "lng": 108.2022},
             "iata_code": "DAD", "arrival_date": date(2026, 9, 3),
             "departure_date": date(2026, 9, 6)},
        ],
        ma_phien="multicity-session",
    )


def test_multicity_composes_route_live_stays_and_flights_with_snapshots():
    store = MemoryStore()
    result = MultiCityPlanner(RouteStub(), InventoryStub(), store).plan(request())
    assert result["route"]["provenance"]["provider"] == "OSRM"
    assert [item["status"] for item in result["stays"]] == ["live", "live"]
    assert result["transport"][0]["status"] == "live"
    assert result["inventory_summary"] == {"live_parts": 3, "total_parts": 3,
                                            "complete": True}
    assert len(store.inventory_snapshots) == 3


def test_multicity_never_fills_provider_gaps_with_fake_offers():
    class UnavailableInventory(InventoryStub):
        def hotels(self, request):
            raise InventoryUnavailable("provider down")

        def flights(self, request):
            raise InventoryUnavailable("provider down")

    result = MultiCityPlanner(RouteStub(), UnavailableInventory(), MemoryStore()).plan(request())
    assert result["inventory_summary"]["complete"] is False
    assert all(item["offers"] == [] for item in result["stays"] + result["transport"])
    assert all(item["status"] == "provider_unavailable"
               for item in result["stays"] + result["transport"])
    assert all("detail" not in item for item in result["stays"] + result["transport"])


def test_multicity_rejects_stale_or_empty_provider_results_without_snapshot():
    class StaleInventory(InventoryStub):
        def hotels(self, request):
            expired = datetime.now(UTC) - timedelta(hours=1)
            return {"offers": [{"id": "hotel"}], "provenance": {
                "provider": "Amadeus", "is_live": True,
                "fetched_at": (expired - timedelta(minutes=1)).isoformat(),
                "expires_at": expired.isoformat(),
            }}

        def flights(self, request):
            return {"offers": [], "provenance": self.provenance()}

    store = MemoryStore()
    result = MultiCityPlanner(RouteStub(), StaleInventory(), store).plan(request())
    assert all(item["status"] == "provider_unavailable"
               for item in result["stays"] + result["transport"])
    assert store.inventory_snapshots == {}


def test_multicity_dates_cannot_overlap():
    with pytest.raises(ValueError):
        MultiCityRequest(stops=[
            {"name": "A", "location": {"lat": 1, "lng": 1},
             "arrival_date": date(2026, 9, 1), "departure_date": date(2026, 9, 5)},
            {"name": "B", "location": {"lat": 2, "lng": 2},
             "arrival_date": date(2026, 9, 4), "departure_date": date(2026, 9, 7)},
        ], ma_phien="multicity-session")


def test_multicity_rejects_duplicate_and_oversized_provider_offers():
    class InvalidInventory(InventoryStub):
        def hotels(self, request):
            return {"offers": [{"id": "duplicate"}, {"id": "duplicate"}],
                    "provenance": self.provenance()}

        def flights(self, request):
            return {"offers": [{"id": "flight", "payload": "x" * 1_100_000}],
                    "provenance": self.provenance()}

    store = MemoryStore()
    result = MultiCityPlanner(RouteStub(), InvalidInventory(), store).plan(request())
    assert all(item["status"] == "provider_unavailable"
               for item in result["stays"] + result["transport"])
    assert store.inventory_snapshots == {}


def test_multicity_rejects_old_fetched_at_even_when_expiry_is_future():
    class OldInventory(InventoryStub):
        @staticmethod
        def provenance():
            fetched = datetime.now(UTC) - timedelta(minutes=10)
            return {"provider": "Amadeus", "is_live": True,
                    "fetched_at": fetched.isoformat(),
                    "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()}

    store = MemoryStore()
    result = MultiCityPlanner(RouteStub(), OldInventory(), store).plan(request())
    assert all(item["status"] == "provider_unavailable"
               for item in result["stays"] + result["transport"])
    assert store.inventory_snapshots == {}
