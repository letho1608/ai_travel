from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas import (
    ActivitySearchRequest,
    FlightSearchRequest,
    HotelSearchRequest,
    TransferSearchRequest,
)
from app.services.inventory import AmadeusInventory, InventoryUnavailable
from app.services.store import MemoryStore


class StubResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class StubClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple] = []

    def get(self, *args, **kwargs) -> StubResponse:
        self.calls.append((args, kwargs))
        return StubResponse(self.responses.pop(0))

    def post(self, *args, **kwargs) -> StubResponse:
        self.calls.append((args, kwargs))
        return StubResponse(self.responses.pop(0))


def authenticated(client: StubClient) -> AmadeusInventory:
    adapter = AmadeusInventory(client)  # type: ignore[arg-type]
    adapter._access_token = "verified-provider-token"
    adapter._token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    return adapter


def test_flight_search_rejects_same_airport_and_reversed_dates():
    base = {
        "origin": "HAN", "destination": "SGN", "departure_date": date(2030, 1, 10),
        "adults": 1, "currency": "VND", "ma_phien": "inventory-session",
    }
    with pytest.raises(ValueError):
        FlightSearchRequest(**(base | {"destination": "HAN"}))
    with pytest.raises(ValueError):
        FlightSearchRequest(**(base | {"return_date": date(2030, 1, 9)}))
    with pytest.raises(ValueError):
        FlightSearchRequest(**(base | {
            "departure_date": datetime.now(UTC).date() - timedelta(days=1)
        }))


def test_hotel_rejects_past_checkin_and_transfer_requires_timezone():
    with pytest.raises(ValueError):
        HotelSearchRequest(
            latitude=21.0, longitude=105.0,
            check_in=datetime.now(UTC).date() - timedelta(days=1),
            check_out=datetime.now(UTC).date(),
            ma_phien="inventory-session",
        )
    with pytest.raises(ValueError):
        TransferSearchRequest(
            start_location_code="HAN", end_address_line="1 Trang Tien",
            end_city_name="Ha Noi", end_country_code="VN", end_name="Hoan Kiem",
            end_latitude=21.0, end_longitude=105.0,
            start_datetime="2030-01-01T10:00:00", ma_phien="inventory-session",
        )


def test_flight_offer_keeps_provider_price_and_provenance():
    adapter = authenticated(
        StubClient([{"data": [{"id": "offer-1", "price": {"grandTotal": "120.50", "currency": "USD"},
                               "numberOfBookableSeats": 3, "itineraries": [{"duration": "PT2H"}],
                               "validatingAirlineCodes": ["VN"]}]},
                    {"data": [{"priceMetrics": [
                        {"amount": "80.00", "quartileRanking": "FIRST"},
                        {"amount": "120.00", "quartileRanking": "MEDIUM"},
                    ]}]}])
    )
    result = adapter.flights(
        FlightSearchRequest(origin="HAN", destination="SGN", departure_date=date(2026, 9, 1),
                            ma_phien="inventory-session")
    )
    assert result["offers"][0]["price"] == "120.50"
    assert result["offers"][0]["bookable_seats"] == 3
    assert result["provenance"]["provider"] == "Amadeus"
    assert result["provenance"]["is_live"] is True
    assert result["price_analysis"]["status"] == "live"
    assert result["price_analysis"]["metrics"][1]["quartile_ranking"] == "MEDIUM"


def test_hotel_search_uses_geocode_then_live_offer():
    client = StubClient([
            {"data": [{"hotelId": "HAN001"}]},
            {"data": [{"hotel": {"hotelId": "HAN001", "name": "Hotel One"},
                       "offers": [{"id": "room-1", "price": {"total": "88.00", "currency": "USD"},
                                   "checkInDate": "2026-09-01", "checkOutDate": "2026-09-02"}]}]},
        ])
    adapter = authenticated(client)
    result = adapter.hotels(
        HotelSearchRequest(latitude=21.0285, longitude=105.8542,
                           check_in=date(2026, 9, 1), check_out=date(2026, 9, 2),
                           ma_phien="inventory-session")
    )
    assert result["offers"][0]["hotel_name"] == "Hotel One"
    assert result["offers"][0]["price"] == "88.00"


def test_hotel_filters_are_validated_sent_to_provider_and_applied_to_price():
    client = StubClient([
        {"data": [{"hotelId": "HAN001"}]},
        {"data": [{"hotel": {"hotelId": "HAN001", "name": "Hotel One"},
                   "offers": [{"id": "room-1", "price": {"total": "188.00", "currency": "USD"}}]}]},
    ])
    request = HotelSearchRequest(
        latitude=21.0285, longitude=105.8542, check_in=date(2026, 9, 1),
        check_out=date(2026, 9, 2), ratings=[5, 4], amenities=["wifi", "parking"],
        max_price=100, ma_phien="inventory-session",
    )
    result = authenticated(client).hotels(request)
    provider_params = client.calls[0][1]["params"]
    assert provider_params["ratings"] == "4,5"
    assert provider_params["amenities"] == "WIFI,PARKING"
    assert result["offers"] == []


def test_inventory_without_credentials_fails_closed():
    with pytest.raises(InventoryUnavailable, match="chưa được cấu hình"):
        AmadeusInventory(StubClient([]))._token()  # type: ignore[arg-type]


def test_booking_assistance_only_accepts_offer_from_snapshot():
    store = MemoryStore()
    result = {
        "offers": [{"id": "real-offer"}],
        "provenance": {"expires_at": "2026-09-01T00:00:00+00:00"},
    }
    snapshot_id = store.save_inventory_snapshot(
        "inventory-session", "flight", {"origin": "HAN"}, result
    )
    request = store.create_booking_request(
        snapshot_id, "inventory-session", None, "real-offer", "Cần tư vấn"
    )
    assert request["trang_thai"] == "requested"
    duplicate = store.create_booking_request(
        snapshot_id, "inventory-session", None, "real-offer", "ignored second note"
    )
    assert duplicate["id"] == request["id"]
    assert len(store.booking_requests) == 1
    with pytest.raises(ValueError, match="OFFER_NOT_FOUND"):
        store.create_booking_request(
            snapshot_id, "inventory-session", None, "invented-offer", None
        )


def test_booking_assistance_rejects_expired_snapshot():
    store = MemoryStore()
    snapshot_id = store.save_inventory_snapshot(
        "inventory-session", "flight", {},
        {"offers": [{"id": "offer"}], "provenance": {
            "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        }},
    )
    with pytest.raises(ValueError, match="SNAPSHOT_NOT_FOUND"):
        store.create_booking_request(
            snapshot_id, "inventory-session", None, "offer", None
        )


@pytest.mark.parametrize(
    ("method", "responses", "schema_request"),
    [
        ("flights", [{"data": [{}]}], FlightSearchRequest(
            origin="HAN", destination="SGN", departure_date=date(2030, 1, 1),
            include_price_analysis=False, ma_phien="inventory-session")),
        ("hotels", [{"data": [{}]}], HotelSearchRequest(
            latitude=21.0, longitude=105.0, check_in=date(2030, 1, 1),
            check_out=date(2030, 1, 2), ma_phien="inventory-session")),
        ("activities", [{"data": [{}]}], ActivitySearchRequest(
            latitude=21.0, longitude=105.0, ma_phien="inventory-session")),
        ("transfers", [{"data": [{}]}], TransferSearchRequest(
            start_location_code="HAN", end_address_line="1 Trang Tien",
            end_city_name="Ha Noi", end_country_code="VN", end_name="Hoan Kiem",
            end_latitude=21.0, end_longitude=105.0,
            start_datetime="2030-01-01T10:00:00+07:00", ma_phien="inventory-session")),
    ],
)
def test_malformed_provider_payload_is_controlled(method, responses, schema_request):
    adapter = authenticated(StubClient(responses))
    with pytest.raises(InventoryUnavailable, match="malformed"):
        getattr(adapter, method)(schema_request)


def test_concurrent_token_refresh_uses_one_provider_call(monkeypatch):
    client = StubClient([{"access_token": "one-token", "expires_in": 1800}])
    adapter = AmadeusInventory(client)  # type: ignore[arg-type]
    monkeypatch.setattr(adapter, "_credentials", lambda: ("id", "secret"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(lambda _: adapter._token(), range(8)))
    assert tokens == ["one-token"] * 8
    assert len(client.calls) == 1


def test_support_queue_enforces_booking_state_machine():
    store = MemoryStore()
    result = {
        "offers": [{"id": "real-offer"}],
        "provenance": {"expires_at": "2026-09-01T00:00:00+00:00"},
    }
    snapshot_id = store.save_inventory_snapshot(
        "inventory-session", "hotel", {"city": "HAN"}, result
    )
    item = store.create_booking_request(
        snapshot_id, "inventory-session", None, "real-offer", "Phòng yên tĩnh"
    )
    reviewing = store.update_booking_request(
        item["id"], "reviewing", "Lan", "Đang kiểm tra offer", None
    )
    assert reviewing["trang_thai"] == "reviewing"
    assert store.list_booking_requests("reviewing")[0]["phu_trach"] == "Lan"
    handed_off = store.update_booking_request(
        item["id"], "handed_off", "Lan", "Đã chuyển nhà cung cấp", "provider-case-1"
    )
    assert handed_off["provider_reference"] == "provider-case-1"
    with pytest.raises(ValueError, match="INVALID_BOOKING_TRANSITION"):
        store.update_booking_request(item["id"], "reviewing", "Lan", None, None)


def test_activity_keeps_only_provider_booking_link():
    adapter = authenticated(
        StubClient([{"data": [{"id": "activity-1", "name": "Walking tour",
                               "price": {"amount": "10", "currencyCode": "EUR"},
                               "bookingLink": "https://provider.example/verified-offer",
                               "geoCode": {"latitude": 21.02, "longitude": 105.85}}]}])
    )
    result = adapter.activities(
        ActivitySearchRequest(latitude=21.0285, longitude=105.8542,
                              ma_phien="inventory-session")
    )
    assert result["offers"][0]["booking_link"] == "https://provider.example/verified-offer"
    assert result["offers"][0]["booking_status"] == "external_provider_handoff"


def test_transfer_search_posts_provider_payload_and_keeps_verified_quote():
    client = StubClient([{"data": [{
        "id": "transfer-1", "transferType": "PRIVATE",
        "serviceProvider": {"name": "Provider", "code": "PVD"},
        "vehicle": {"description": "Sedan", "seats": 3},
        "quotation": {"monetaryAmount": "25.50", "currencyCode": "EUR"},
    }]}])
    result = authenticated(client).transfers(TransferSearchRequest(
        start_location_code="HAN", end_address_line="1 Tràng Tiền",
        end_city_name="Hà Nội", end_country_code="VN", end_name="Hồ Hoàn Kiếm",
        end_latitude=21.0285, end_longitude=105.8542,
        start_datetime="2026-09-01T10:00:00+07:00", passengers=2,
        ma_phien="inventory-session",
    ))
    assert client.calls[0][0][0] == "/v1/shopping/transfer-offers"
    assert client.calls[0][1]["json"]["transferType"] == "PRIVATE"
    assert result["offers"][0]["price"] == "25.50"
    assert result["offers"][0]["booking_status"] == "requires_provider_confirmation"
