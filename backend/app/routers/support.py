import secrets

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import settings
from app.schemas import BookingSupportUpdate
from app.services.store import store

router = APIRouter(prefix="/api/support", tags=["support"])
VALID_STATUSES = {"requested", "reviewing", "needs_customer", "handed_off", "cancelled"}


def _authorize(token: str | None) -> None:
    if not settings.support_admin_token:
        raise HTTPException(503, "Kênh vận hành hỗ trợ chưa được cấu hình")
    if not token or not secrets.compare_digest(token, settings.support_admin_token):
        raise HTTPException(401, "Thông tin xác thực nhân sự không hợp lệ")


@router.get("/booking-requests")
def booking_queue(
    status: str | None = Query(default=None),
    x_support_token: str | None = Header(default=None),
):
    _authorize(x_support_token)
    if status and status not in VALID_STATUSES:
        raise HTTPException(400, "Trạng thái hàng đợi không hợp lệ")
    return {"items": store.list_booking_requests(status)}


@router.patch("/booking-requests/{request_id}")
def update_booking_request(
    request_id: str, payload: BookingSupportUpdate,
    x_support_token: str | None = Header(default=None),
):
    _authorize(x_support_token)
    try:
        item = store.update_booking_request(
            request_id, payload.trang_thai, payload.phu_trach,
            payload.ghi_chu_noi_bo, payload.provider_reference,
        )
    except (ValueError, TypeError) as exc:
        detail = "Không tìm thấy yêu cầu" if str(exc) == "BOOKING_REQUEST_NOT_FOUND" else "Chuyển trạng thái không hợp lệ"
        raise HTTPException(409, detail) from exc
    return {"yeu_cau": item, "booking_confirmed": False}
