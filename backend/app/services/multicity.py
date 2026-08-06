import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.schemas import FlightSearchRequest, HotelSearchRequest, RoadTripRequest
from app.services.inventory import InventoryUnavailable, inventory
from app.services.roadtrip import roadtrip
from app.services.store import store


class MultiCityPlanner:
    """Compose verified routing and provider inventory without inventing gaps."""

    def __init__(self, route_adapter=roadtrip, inventory_adapter=inventory, data_store=store):
        self.route_adapter = route_adapter
        self.inventory_adapter = inventory_adapter
        self.store = data_store

    def plan(self, request) -> dict:
        route_request = RoadTripRequest(
            stops=[{"name": stop.name, "location": stop.location.model_dump()}
                   for stop in request.stops],
            round_trip=request.round_trip,
        )
        route_result = self.route_adapter.route(route_request)
        stays = []
        for stop in request.stops:
            if not stop.arrival_date:
                stays.append({"city": stop.name, "status": "dates_required", "offers": []})
                continue
            hotel_request = HotelSearchRequest(
                latitude=stop.location.lat, longitude=stop.location.lng,
                check_in=stop.arrival_date, check_out=stop.departure_date,
                adults=request.adults, room_quantity=request.rooms,
                currency=request.currency, ma_phien=request.ma_phien,
            )
            try:
                result = self.inventory_adapter.hotels(hotel_request)
                snapshot_id = self._validated_snapshot(
                    request.ma_phien, "hotel", hotel_request, result
                )
                stays.append({"city": stop.name, "status": "live", "snapshot_id": snapshot_id,
                              "offers": result["offers"], "provenance": result["provenance"]})
            except (InventoryUnavailable, ValueError, TypeError, KeyError):
                stays.append({"city": stop.name, "status": "provider_unavailable",
                              "offers": []})

        transport = []
        transport_stops = list(request.stops)
        if request.round_trip:
            transport_stops.append(request.stops[0])
        for origin, destination in pairwise(transport_stops):
            if not origin.iata_code or not destination.iata_code:
                transport.append({"from": origin.name, "to": destination.name,
                                  "status": "iata_required", "offers": []})
                continue
            departure = origin.departure_date or destination.arrival_date
            if not departure:
                transport.append({"from": origin.name, "to": destination.name,
                                  "status": "date_required", "offers": []})
                continue
            flight_request = FlightSearchRequest(
                origin=origin.iata_code, destination=destination.iata_code,
                departure_date=departure, adults=request.adults,
                currency=request.currency, ma_phien=request.ma_phien,
            )
            try:
                result = self.inventory_adapter.flights(flight_request)
                snapshot_id = self._validated_snapshot(
                    request.ma_phien, "flight", flight_request, result
                )
                transport.append({"from": origin.name, "to": destination.name,
                                  "status": "live", "snapshot_id": snapshot_id,
                                  "offers": result["offers"], "provenance": result["provenance"]})
            except (InventoryUnavailable, ValueError, TypeError, KeyError):
                transport.append({"from": origin.name, "to": destination.name,
                                  "status": "provider_unavailable", "offers": []})
        live_parts = sum(item["status"] == "live" for item in stays + transport)
        return {
            "route": route_result, "stays": stays, "transport": transport,
            "inventory_summary": {
                "live_parts": live_parts, "total_parts": len(stays) + len(transport),
                "complete": live_parts == len(stays) + len(transport),
            },
        }

    def _validated_snapshot(self, session_id, kind, provider_request, result) -> str:
        if not isinstance(result, dict):
            raise TypeError("invalid provider result")
        offers = result.get("offers")
        if not isinstance(offers, list) or not 1 <= len(offers) <= 20:
            raise ValueError("provider returned no offers")
        if any(not isinstance(offer, dict) or not isinstance(offer.get("id"), str)
               or not offer["id"].strip() or len(offer["id"]) > 300 for offer in offers):
            raise ValueError("invalid provider offers")
        for offer in offers:
            if "price" in offer:
                try:
                    price = float(offer["price"])
                except (TypeError, ValueError) as exc:
                    raise ValueError("invalid provider offer price") from exc
                if price < 0:
                    raise ValueError("invalid provider offer price")
            currency = offer.get("currency")
            if currency is not None and (
                not isinstance(currency, str) or len(currency) != 3 or not currency.isupper()
            ):
                raise ValueError("invalid provider offer currency")
        offer_ids = [offer["id"] for offer in offers]
        if len(set(offer_ids)) != len(offer_ids):
            raise ValueError("duplicate provider offer ids")
        try:
            encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
        except (TypeError, ValueError) as exc:
            raise ValueError("provider result is not serializable") from exc
        if len(encoded) > 1_048_576:
            raise ValueError("provider result exceeds snapshot limit")
        provenance = result.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("is_live") is not True:
            raise ValueError("invalid provider provenance")
        provider = provenance.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("missing provider")
        try:
            fetched = datetime.fromisoformat(provenance["fetched_at"])
            expires = datetime.fromisoformat(provenance["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid provider timestamps") from exc
        if fetched.tzinfo is None or expires.tzinfo is None:
            raise ValueError("provider timestamps require timezone")
        now = datetime.now(UTC)
        if (
            fetched > now + timedelta(minutes=5)
            or now - fetched > timedelta(minutes=5)
            or expires <= now
            or expires <= fetched
        ):
            raise ValueError("provider result is stale")
        snapshot_id = self.store.save_inventory_snapshot(
            session_id, kind, provider_request.model_dump(mode="json"), result
        )
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("snapshot was not persisted")
        return snapshot_id


multicity = MultiCityPlanner()
