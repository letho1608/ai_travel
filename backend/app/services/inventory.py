from datetime import UTC, datetime, timedelta
from functools import wraps
from threading import Lock
from urllib.parse import urlparse

import httpx

from app.config import settings


class InventoryUnavailable(RuntimeError):
    pass


def provider_payload_guard(method):
    """Turn malformed provider structures into a controlled availability error."""
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except InventoryUnavailable:
            raise
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise InventoryUnavailable("Provider inventory returned malformed data") from exc
    return guarded


class AmadeusInventory:
    """Live Amadeus inventory; never returns synthetic prices or availability."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url=settings.amadeus_base_url,
            timeout=httpx.Timeout(12, connect=3),
        )
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._token_lock = Lock()

    def _credentials(self) -> tuple[str, str]:
        if not settings.amadeus_client_id or not settings.amadeus_client_secret:
            raise InventoryUnavailable("Amadeus inventory chưa được cấu hình")
        return settings.amadeus_client_id, settings.amadeus_client_secret

    def _token(self) -> str:
        now = datetime.now(UTC)
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        with self._token_lock:
            now = datetime.now(UTC)
            if self._access_token and now < self._token_expires_at:
                return self._access_token
            client_id, client_secret = self._credentials()
            try:
                response = self.client.post(
                    "/v1/security/oauth2/token",
                    data={"grant_type": "client_credentials", "client_id": client_id,
                          "client_secret": client_secret},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TypeError("token payload must be an object")
                token = payload["access_token"]
                if not isinstance(token, str) or not token:
                    raise TypeError("access token must be a non-empty string")
                self._access_token = token
                self._token_expires_at = now + timedelta(
                    seconds=max(30, int(payload.get("expires_in", 1800)) - 60)
                )
                return token
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                raise InventoryUnavailable("Không thể xác thực nhà cung cấp inventory") from exc

    def _get(self, path: str, params: dict) -> dict:
        try:
            response = self.client.get(
                path, params=params, headers={"Authorization": f"Bearer {self._token()}"}
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("provider payload must be an object")
            return payload
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InventoryUnavailable("Nhà cung cấp inventory tạm thời không khả dụng") from exc

    def _post_json(self, path: str, payload: dict) -> dict:
        try:
            response = self.client.post(
                path, json=payload,
                headers={"Authorization": f"Bearer {self._token()}",
                         "Content-Type": "application/vnd.amadeus+json"},
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise TypeError("provider payload must be an object")
            return result
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InventoryUnavailable("Nhà cung cấp inventory tạm thời không khả dụng") from exc

    @staticmethod
    def _provenance() -> dict:
        fetched = datetime.now(UTC)
        return {
            "provider": "Amadeus", "fetched_at": fetched.isoformat(),
            "expires_at": (fetched + timedelta(minutes=15)).isoformat(),
            "is_live": True,
        }

    @staticmethod
    def _safe_booking_link(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        return value if parsed.scheme == "https" and parsed.netloc else None

    @provider_payload_guard
    def flights(self, request) -> dict:
        params = {
            "originLocationCode": request.origin,
            "destinationLocationCode": request.destination,
            "departureDate": request.departure_date.isoformat(),
            "adults": request.adults, "currencyCode": request.currency, "max": 20,
        }
        if request.return_date:
            params["returnDate"] = request.return_date.isoformat()
        payload = self._get("/v2/shopping/flight-offers", params)
        offers = [
            {
                "id": item["id"], "price": item["price"]["grandTotal"],
                "currency": item["price"]["currency"],
                "bookable_seats": item.get("numberOfBookableSeats"),
                "itineraries": item["itineraries"],
                "validating_airlines": item.get("validatingAirlineCodes", []),
                "booking_status": "requires_provider_confirmation",
            }
            for item in payload.get("data", [])
        ]
        analysis = {"status": "not_requested", "metrics": []}
        if request.include_price_analysis:
            try:
                metrics_payload = self._get(
                    "/v1/analytics/itinerary-price-metrics",
                    {"originIataCode": request.origin,
                     "destinationIataCode": request.destination,
                     "departureDate": request.departure_date.isoformat(),
                     "currencyCode": request.currency,
                     "oneWay": request.return_date is None},
                )
                metrics = []
                for itinerary in metrics_payload.get("data", []):
                    for metric in itinerary.get("priceMetrics", []):
                        metrics.append({
                            "amount": metric.get("amount"),
                            "quartile_ranking": metric.get("quartileRanking"),
                        })
                analysis = {
                    "status": "live", "metrics": metrics,
                    "provider": "Amadeus Itinerary Price Metrics",
                    "basis": "historical_fares", "currency": request.currency,
                }
            except InventoryUnavailable as exc:
                analysis = {"status": "provider_unavailable", "metrics": [],
                            "detail": str(exc)}
        return {"offers": offers, "price_analysis": analysis,
                "provenance": self._provenance()}

    @provider_payload_guard
    def hotels(self, request) -> dict:
        list_params = {
            "latitude": request.latitude, "longitude": request.longitude,
            "radius": request.radius_km, "radiusUnit": "KM", "hotelSource": "ALL",
        }
        if request.ratings:
            list_params["ratings"] = ",".join(str(value) for value in request.ratings)
        if request.amenities:
            list_params["amenities"] = ",".join(request.amenities)
        hotels = self._get(
            "/v1/reference-data/locations/hotels/by-geocode",
            list_params,
        ).get("data", [])[:20]
        hotel_ids = [hotel["hotelId"] for hotel in hotels]
        if not hotel_ids:
            return {"offers": [], "provenance": self._provenance()}
        payload = self._get(
            "/v3/shopping/hotel-offers",
            {"hotelIds": ",".join(hotel_ids), "adults": request.adults,
             "checkInDate": request.check_in.isoformat(),
             "checkOutDate": request.check_out.isoformat(),
             "roomQuantity": request.room_quantity, "currency": request.currency},
        )
        offers = []
        for hotel in payload.get("data", []):
            for offer in hotel.get("offers", [])[:1]:
                price_total = float(offer["price"]["total"])
                if request.min_price is not None and price_total < request.min_price:
                    continue
                if request.max_price is not None and price_total > request.max_price:
                    continue
                offers.append(
                    {"id": offer["id"], "hotel_id": hotel["hotel"]["hotelId"],
                     "hotel_name": hotel["hotel"].get("name"),
                     "price": offer["price"]["total"],
                     "currency": offer["price"]["currency"],
                     "check_in": offer.get("checkInDate"),
                     "check_out": offer.get("checkOutDate"),
                     "matched_filters": {
                         "ratings": request.ratings, "amenities": request.amenities,
                         "min_price": request.min_price, "max_price": request.max_price,
                     },
                     "booking_status": "requires_provider_confirmation"}
                )
        return {"offers": offers, "provenance": self._provenance()}

    @provider_payload_guard
    def activities(self, request) -> dict:
        payload = self._get(
            "/v1/shopping/activities",
            {"latitude": request.latitude, "longitude": request.longitude,
             "radius": request.radius},
        )
        offers = []
        for item in payload.get("data", []):
            price = item.get("price") or {}
            booking_link = self._safe_booking_link(item.get("bookingLink"))
            offers.append(
                {"id": item["id"], "name": item.get("name"),
                 "description": item.get("shortDescription"),
                 "latitude": item.get("geoCode", {}).get("latitude"),
                 "longitude": item.get("geoCode", {}).get("longitude"),
                 "price": price.get("amount"), "currency": price.get("currencyCode"),
                 "rating": item.get("rating"), "pictures": item.get("pictures", [])[:4],
                 "booking_link": booking_link,
                 "booking_status": "external_provider_handoff" if booking_link
                 else "requires_provider_confirmation"}
            )
        return {"offers": offers, "provenance": self._provenance()}

    @provider_payload_guard
    def transfers(self, request) -> dict:
        payload = {
            "startLocationCode": request.start_location_code,
            "endAddressLine": request.end_address_line,
            "endCityName": request.end_city_name,
            "endCountryCode": request.end_country_code,
            "endName": request.end_name,
            "endGeoCode": f"{request.end_latitude},{request.end_longitude}",
            "transferType": request.transfer_type,
            "startDateTime": request.start_datetime.isoformat(),
            "passengers": request.passengers,
        }
        response = self._post_json("/v1/shopping/transfer-offers", payload)
        offers = []
        for item in response.get("data", []):
            quotation = item.get("quotation") or {}
            provider = item.get("serviceProvider") or {}
            vehicle = item.get("vehicle") or {}
            offers.append({
                "id": item["id"], "transfer_type": item.get("transferType"),
                "provider_name": provider.get("name"), "provider_code": provider.get("code"),
                "vehicle_description": vehicle.get("description"),
                "seats": vehicle.get("seats"), "price": quotation.get("monetaryAmount"),
                "currency": quotation.get("currencyCode"),
                "booking_status": "requires_provider_confirmation",
            })
        return {"offers": offers, "provenance": self._provenance()}


inventory = AmadeusInventory()
