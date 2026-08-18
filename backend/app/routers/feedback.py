from typing import Literal
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.routers.auth import resolve_user
from app.services.store import store

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class SubmitFeedbackRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    contact: str = Field(min_length=3, max_length=100)
    rating: int = Field(ge=1, le=5)
    category: Literal["trai_nghiem", "tinh_nang", "dia_diem", "khac"] = "trai_nghiem"
    title: str = Field(default="", max_length=120)
    content: str = Field(min_length=5, max_length=2000)
    ma_phien: str = Field(max_length=64)


class UpdateFeedbackRequest(BaseModel):
    status: Literal["new", "reviewed", "resolved", "hidden"] | None = None
    admin_reply: str | None = Field(default=None, max_length=1000)


def _check_admin(
    authorization: str | None,
    x_admin_token: str | None,
    x_support_token: str | None,
) -> None:
    user = resolve_user(authorization)
    if user and (user.get("role") == "admin" or user.get("username") in ("admin", "root", "administrator")):
        return
    admin_tok = x_admin_token or x_support_token
    if admin_tok and settings.admin_token and admin_tok == settings.admin_token:
        return
    if admin_tok and settings.support_token and admin_tok == settings.support_token:
        return
    if user:
        raise HTTPException(403, "Tài khoản của bạn không có quyền Quản trị viên")
    raise HTTPException(401, "Yêu cầu quyền Quản trị viên (Admin)")


@router.post("", status_code=201)
def submit_feedback(
    payload: SubmitFeedbackRequest,
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    user_id = user["id"] if user else None
    review = store.add_user_review(
        name=payload.name,
        contact=payload.contact,
        rating=payload.rating,
        category=payload.category,
        title=payload.title or "Góp ý từ người dùng",
        content=payload.content,
        session_id=payload.ma_phien,
        user_id=user_id,
    )
    store.log(payload.ma_phien, "gui_danh_gia", {"review_id": review["id"], "rating": payload.rating})
    return {"status": "success", "review": review}


@router.get("")
def list_feedback(
    category: str | None = Query(default=None),
    min_rating: int | None = Query(default=None, ge=1, le=5),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    reviews = store.list_user_reviews(
        status=status,
        category=category,
        min_rating=min_rating,
        limit=limit,
    )
    all_reviews = store.list_user_reviews(limit=500)
    avg_score = round(sum(r["rating"] for r in all_reviews) / len(all_reviews), 1) if all_reviews else 5.0
    return {
        "reviews": reviews,
        "total": len(reviews),
        "all_total": len(all_reviews),
        "average_rating": avg_score,
    }


@router.patch("/{review_id}")
def update_feedback(
    review_id: str,
    payload: UpdateFeedbackRequest,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
    x_support_token: str | None = Header(default=None),
):
    _check_admin(authorization, x_admin_token, x_support_token)
    try:
        updated = store.update_user_review(
            review_id=review_id,
            status=payload.status,
            admin_reply=payload.admin_reply,
        )
        return {"status": "success", "review": updated}
    except ValueError as exc:
        raise HTTPException(404, "Không tìm thấy đánh giá") from exc
