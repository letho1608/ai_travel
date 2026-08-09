from fastapi import APIRouter, Header, HTTPException, Request

from app.routers.auth import resolve_user
from app.schemas import (
    ActivitySearchRequest,
    BookingAssistanceRequest,
    FlightSearchRequest,
    HotelSearchRequest,
    TransferSearchRequest,
)
from app.services.inventory import InventoryUnavailable, inventory
from app.services.rate_limit import limiter
from app.services.store import store

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
SEARCH_SESSION_LIMIT = 30
SEARCH_IP_LIMIT = 120


def _check_search_limit(request: Request, session_id: str) -> None:
    ip = request.client.host if request.client else "unknown"
    if not limiter.check_many([
        (f"inventory:{ip}:{session_id}", SEARCH_SESSION_LIMIT, 3600),
        (f"inventory-ip:{ip}", SEARCH_IP_LIMIT, 3600),
    ]):
        raise HTTPException(429, "Inventory request limit exceeded")


@router.post("/flights/search")
def search_flights(payload: FlightSearchRequest, request: Request):
    _check_search_limit(request, payload.ma_phien)
    try:
        result = inventory.flights(payload)
        result["snapshot_id"] = store.save_inventory_snapshot(
            payload.ma_phien, "flight", payload.model_dump(mode="json"), result
        )
        return result
    except InventoryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/hotels/search")
def search_hotels(payload: HotelSearchRequest, request: Request):
    _check_search_limit(request, payload.ma_phien)
    try:
        result = inventory.hotels(payload)
        result["snapshot_id"] = store.save_inventory_snapshot(
            payload.ma_phien, "hotel", payload.model_dump(mode="json"), result
        )
        return result
    except InventoryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/activities/search")
def search_activities(payload: ActivitySearchRequest, request: Request):
    _check_search_limit(request, payload.ma_phien)
    try:
        result = inventory.activities(payload)
        result["snapshot_id"] = store.save_inventory_snapshot(
            payload.ma_phien, "activity", payload.model_dump(mode="json"), result
        )
        return result
    except InventoryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/transfers/search")
def search_transfers(payload: TransferSearchRequest, request: Request):
    _check_search_limit(request, payload.ma_phien)
    try:
        result = inventory.transfers(payload)
        result["snapshot_id"] = store.save_inventory_snapshot(
            payload.ma_phien, "transfer", payload.model_dump(mode="json"), result
        )
        return result
    except InventoryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/booking-assistance", status_code=202)
def request_booking_assistance(
    payload: BookingAssistanceRequest,
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    try:
        item = store.create_booking_request(
            payload.snapshot_id, payload.ma_phien, user["id"] if user else None,
            payload.offer_id, payload.ghi_chu,
        )
    except ValueError as exc:
        raise HTTPException(404, "Snapshot hoặc offer không còn hợp lệ") from exc
    return {
        "yeu_cau": item,
        "thong_bao": "Đã ghi nhận yêu cầu hỗ trợ; đây chưa phải xác nhận đặt chỗ.",
    }

