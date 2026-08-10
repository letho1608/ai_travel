import json
import re
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.data import PLACES, Place, image_for
from app.pipeline.planner import COPY, PipelineUnavailable, _effective_hours, build_plan, travel_minutes, validate_plan
from app.services.ai import ai_adapter
from app.routers.auth import resolve_user
from app.schemas import (
    CommentRequest,
    DeleteSlotRequest,
    PlanRequest,
    ReadNotificationRequest,
    RefineRequest,
    RegenerateRequest,
    ResolveCommentRequest,
    RestoreVersionRequest,
    SwipeRequest,
    TripFeedbackRequest,
)
from app.services.pdf_export import build_itinerary_pdf
from app.services.osm_verify import verify_place_name
from app.services.rate_limit import limiter
from app.services.store import store
from app.text_utils import ascii_fold

SWAP_INTENT = re.compile(
    r"\b(đổi|thay|replace|swap|cambiar|remplacer|ersetzen|sostituire|substituir|"
    r"vervangen|zamień|заменить|değiştir|替换|更换|交換|置き換え|교체|เปลี่ยน|"
    r"استبدال|החלף|बदलें|смени)\b",
    re.IGNORECASE,
)
PEOPLE_INTENT = re.compile(
    r"\b(\d{1,2})\s*(người|people|persons?|personas?|personnes?|personen|persone|"
    r"pessoas?|osób|человек|kişi|人|명|คน|أشخاص|אנשים|लोग|души)\b",
    re.IGNORECASE,
)

router = APIRouter(prefix="/api", tags=["plans"])
GENERATE_NONCE_SCOPE = "00000000-0000-0000-0000-000000000000"


def _generate_nonce_key(session_id: str, nonce: str) -> str:
    return f"{session_id}:{nonce}"


def _conversation(plan: dict) -> list[dict]:
    history = plan.get("hoi_thoai")
    return history if isinstance(history, list) else []


def _append_turn(plan: dict, role: str, text: str) -> None:
    history = _conversation(plan)
    history.append({"vai_tro": role, "noi_dung": text, "thoi_gian": datetime.now(UTC).isoformat()})
    plan["hoi_thoai"] = history[-50:]


def _constraint_echo(request: PlanRequest) -> dict:
    return {
        "ngan_sach": request.ngan_sach,
        "so_nguoi": request.so_nguoi,
        "thoi_luong": request.thoi_luong,
        "ngon_ngu": request.ngon_ngu,
        "ngay_di": request.ngay_di.isoformat() if request.ngay_di else None,
    }


def owner(item, session_id: str | None, authorization: str | None = None) -> None:
    user = resolve_user(authorization)
    if item.user_id and user and item.user_id == user["id"]:
        return
    if not session_id or item.session_id != session_id:
        raise HTTPException(403, "Link chia sẻ chỉ có quyền xem")


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/notifications")
def notifications(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if not user and not x_session_id:
        raise HTTPException(401, "Thiếu phiên hoặc đăng nhập")
    store.materialize_due_reminders()
    return {"items": store.list_notifications(x_session_id or "", user["id"] if user else None)}


@router.patch("/notifications/{notification_id}")
def read_notification(
    notification_id: str, payload: ReadNotificationRequest,
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    try:
        item = store.mark_notification_read(
            notification_id, payload.ma_phien, user["id"] if user else None
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(404, "Không tìm thấy thông báo") from exc
    return {"thong_bao": item}


@router.post("/plan/generate")
async def generate(payload: PlanRequest, request: Request):
    session_id = payload.ma_phien or str(uuid4())
    generate_nonce = _generate_nonce_key(session_id, payload.nonce) if payload.nonce else None
    if payload.nonce:
        existing_token = store.get_nonce(GENERATE_NONCE_SCOPE, generate_nonce or payload.nonce)
        existing = store.get(existing_token) if existing_token else None
        if existing and existing.session_id == session_id:
            async def replay_stream():
                yield sse(
                    "result",
                    {
                        "type": "plan", "ma_phien": session_id,
                        "token": existing.token, "phien_ban": existing.version,
                        "plan": existing.plan,
                    },
                )
            return StreamingResponse(replay_stream(), media_type="text/event-stream")
    ip = request.client.host if request.client else "unknown"
    if not limiter.check_many([
        (f"generate:{ip}:{session_id}", settings.max_generate_per_hour, 3600),
        (f"generate-ip:{ip}", settings.max_generate_ip_per_hour, 3600),
    ]):
        raise HTTPException(429, "Plan generation request limit exceeded")
    try:
        store.reserve_cost(0.0, settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    async def stream():
        yield sse("status", {"status": "finding_places"})
        yield sse("status", {"status": "routing_plan"})
        try:
            plan = await to_thread(build_plan, payload)
            _append_turn(plan, "user", payload.context)
            item = store.save(session_id, plan, payload.model_dump(mode="json"))
            if generate_nonce:
                store.set_nonce(GENERATE_NONCE_SCOPE, generate_nonce, item.token)
            store.log(session_id, "tao_ke_hoach_thanh_cong", {"id_ke_hoach": item.token})
            yield sse("result", {"type": "plan", "ma_phien": session_id, "token": item.token, "phien_ban": 1, "plan": plan})
        except (PipelineUnavailable, RuntimeError) as exc:
            yield sse("error", {"code": "503", "detail": str(exc)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/plans/{token}")
def get_plan(token: str):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại hoặc đã hết hạn")
    return {
        "ke_hoach": item.plan,
        "phien_ban": item.version,
        "token": item.token,
        "tham_so": _constraint_echo(PlanRequest.model_validate(item.request)),
    }


def _ics_escape(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_fold(line: str) -> list[str]:
    folded: list[str] = []
    current = ""
    limit = 75
    for character in line:
        candidate = current + character
        if current and len(candidate.encode("utf-8")) > limit:
            folded.append(current)
            current = " " + character
            limit = 75
        else:
            current = candidate
    folded.append(current)
    return folded


@router.get("/plans/{token}/calendar.ics")
def export_calendar(token: str):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    request = PlanRequest.model_validate(item.request)
    locale = request.ngon_ngu
    start_date = request.ngay_di or datetime.now(UTC).date()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    language = {"zh": "zh-CN"}.get(locale, locale)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN",
        f"PRODID:-//Minh Di Dau The//{language.upper()}",
        f"X-WR-CALNAME;LANGUAGE={language}:Mình Đi Đâu Thế",
    ]
    for day_index, day in enumerate(item.plan.get("ngay", [])):
        event_date = start_date + timedelta(days=day_index)
        for slot in day.get("khoang_gio", []):
            end_date = (
                event_date + timedelta(days=1)
                if slot["ket_thuc"] <= slot["bat_dau"]
                else event_date
            )
            start = event_date.strftime("%Y%m%d") + "T" + slot["bat_dau"].replace(":", "") + "00"
            end = end_date.strftime("%Y%m%d") + "T" + slot["ket_thuc"].replace(":", "") + "00"
            uid = _ics_escape(f"{item.token}-{day_index}-{slot['dia_diem_id']}")
            lines.extend(
                ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
                 f"DTSTART;TZID=Asia/Bangkok:{start}", f"DTEND;TZID=Asia/Bangkok:{end}",
                 f"SUMMARY;LANGUAGE={language}:{_ics_escape(slot['ten_dia_diem'])}",
                 f"DESCRIPTION;LANGUAGE={language}:{_ics_escape(slot.get('mo_ta', ''))}",
                 (
                     f"X-ALT-DESC;FMTTYPE=text/plain;LANGUAGE={language}:"
                     f"{_ics_escape(slot.get('mo_ta', ''))}"
                 ), "END:VEVENT"]
            )
    lines.append("END:VCALENDAR")
    content = "\r\n".join(part for line in lines for part in _ics_fold(line)) + "\r\n"
    return Response(
        content, media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="itinerary-{token}.ics"',
            "Content-Language": language,
        },
    )


@router.get("/plans/{token}/itinerary.pdf")
def export_pdf(token: str):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    request = PlanRequest.model_validate(item.request)
    content = build_itinerary_pdf(item.plan, request.ngon_ngu)
    return Response(
        content, media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="itinerary-{token}.pdf"',
            "Content-Language": {"zh": "zh-CN"}.get(request.ngon_ngu, request.ngon_ngu),
        },
    )


@router.post("/plans/{token}/feedback", status_code=201)
def submit_feedback(
    token: str,
    payload: TripFeedbackRequest,
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, payload.ma_phien, authorization)
    trip_date = PlanRequest.model_validate(item.request).ngay_di
    if not trip_date or trip_date >= datetime.now(UTC).date():
        raise HTTPException(409, "Chỉ có thể gửi phản hồi sau chuyến đi")
    user = resolve_user(authorization)
    try:
        feedback = store.save_feedback(
            token, payload.ma_phien, user["id"] if user else None,
            payload.diem, payload.noi_dung,
        )
    except ValueError as exc:
        raise HTTPException(409, "Bạn đã gửi phản hồi cho chuyến đi này") from exc
    store.log(payload.ma_phien, "phan_hoi_sau_chuyen", {"diem": payload.diem})
    return {"phan_hoi": feedback}


@router.get("/plans/{token}/comments")
def list_comments(token: str):
    if not store.get(token):
        raise HTTPException(404, "Kế hoạch không tồn tại")
    return {"ds_binh_luan": store.list_comments(token)}


@router.post("/plans/{token}/comments", status_code=201)
def add_comment(
    token: str,
    payload: CommentRequest,
    authorization: str | None = Header(default=None),
):
    if not store.get(token):
        raise HTTPException(404, "Kế hoạch không tồn tại")
    if not limiter.check(f"comment:{token}:{payload.ma_phien}", 10, 3600):
        raise HTTPException(429, "Bạn đã gửi quá nhiều bình luận")
    user = resolve_user(authorization)
    comment = store.add_comment(
        token, payload.ma_phien, user["id"] if user else None,
        user.get("ten") or user["email"] if user else payload.ten_hien_thi,
        payload.noi_dung,
    )
    store.log(payload.ma_phien, "them_binh_luan", {"id_binh_luan": comment["id"]})
    return {"binh_luan": comment}


@router.patch("/plans/{token}/comments/{comment_id}")
def resolve_comment(
    token: str,
    comment_id: str,
    payload: ResolveCommentRequest,
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, payload.ma_phien, authorization)
    comment = store.resolve_comment(token, comment_id, payload.da_giai_quyet)
    if not comment:
        raise HTTPException(404, "Bình luận không tồn tại")
    return {"binh_luan": comment}


@router.get("/plans")
def list_plans(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if not x_session_id and not user:
        raise HTTPException(401, "Thiếu phiên hoặc thông tin đăng nhập")
    items = [
        {"token": item.token, "ke_hoach": item.plan, "phien_ban": item.version}
        for item in store.list_for_owner(x_session_id, user["id"] if user else None)
    ]
    return {"ds_ke_hoach": items}


def _place_from_slot(slot: dict) -> Place:
    coordinates = slot.get("toa_do") or {}
    if not slot.get("du_lieu_uoc_tinh") or not slot.get("nguon_url") or not all(key in slot for key in ("gio_mo_cua_uoc_tinh", "gio_dong_cua_uoc_tinh", "chi_phi_moi_nguoi")):
        raise ValueError("Địa điểm ngoài catalog thiếu metadata đã xác minh")
    return Place(slot["dia_diem_id"], slot.get("ten_dia_diem") or slot["dia_diem_id"], slot.get("loai") or "dia_danh", "Hà Nội", float(coordinates.get("lat", 0)), float(coordinates.get("lng", 0)), max(0, int(slot.get("chi_phi_moi_nguoi", 0))), 60, ("verified_external",), int(slot.get("gio_mo_cua_uoc_tinh", 7)), int(slot.get("gio_dong_cua_uoc_tinh", 22)), slot.get("nguon") or "Nominatim", slot.get("nguon_url"), slot.get("anh"), slot.get("anh_nguon"))


def _plan_external_places(plan: dict) -> tuple[Place, ...]:
    catalog_ids = {place.id for place in PLACES}
    places: list[Place] = []
    for day in plan.get("ngay", []):
        for slot in day.get("khoang_gio", []):
            if slot.get("dia_diem_id") and slot["dia_diem_id"] not in catalog_ids:
                try:
                    places.append(_place_from_slot(slot))
                except (TypeError, ValueError):
                    continue
    return tuple(places)


def _replacement_candidates(item, rejected_id: str, *, same_kind: bool = False, additional: tuple[Place, ...] = ()):
    slots = [slot for day in item.plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    matches = [slot for slot in slots if slot.get("dia_diem_id") == rejected_id]
    if len(matches) != 1:
        raise HTTPException(404 if not matches else 409, "Địa điểm không nằm duy nhất trong kế hoạch")
    target = matches[0]
    plan_places = (*PLACES, *_plan_external_places(item.plan), *additional)
    rejected = next((place for place in plan_places if place.id == rejected_id), None)
    if not rejected:
        raise HTTPException(404, "Địa điểm không còn trong danh mục")
    day = next(day for day in item.plan.get("ngay", []) if target in day.get("khoang_gio", []))
    index = day["khoang_gio"].index(target)
    previous_slot = day["khoang_gio"][index - 1] if index else None
    next_slot = day["khoang_gio"][index + 1] if index + 1 < len(day["khoang_gio"]) else None
    by_id = {place.id: place for place in plan_places}
    used_ids = {slot.get("dia_diem_id") for slot in slots}
    used_names = {ascii_fold(slot.get("ten_dia_diem", "")).lower() for slot in slots if slot.get("dia_diem_id") != rejected_id}
    used_places = [by_id[slot_id] for slot_id in used_ids if slot_id != rejected_id and slot_id in by_id]
    request = PlanRequest.model_validate(item.request)

    def minutes(value: str) -> int:
        hour, minute = map(int, value.split(":"))
        return hour * 60 + minute

    def eligible(candidate) -> bool:
        open_hour, close_hour = _effective_hours(candidate)
        if candidate.id in used_ids or ascii_fold(candidate.name).lower() in used_names:
            return False
        if any((candidate.lat - place.lat) ** 2 + (candidate.lng - place.lng) ** 2 < 0.0000001 for place in used_places):
            return False
        if same_kind and candidate.kind != rejected.kind:
            return False
        if not (f"{open_hour:02d}:00" <= target["bat_dau"] and target["ket_thuc"] <= f"{close_hour:02d}:00"):
            return False
        if previous_slot:
            previous = by_id.get(previous_slot["dia_diem_id"])
            if previous and minutes(target["bat_dau"]) - minutes(previous_slot["ket_thuc"]) < travel_minutes(previous, candidate):
                return False
        if next_slot:
            following = by_id.get(next_slot["dia_diem_id"])
            if following and minutes(next_slot["bat_dau"]) - minutes(target["ket_thuc"]) < travel_minutes(candidate, following):
                return False
        next_total = item.plan.get("tong_chi_phi", 0) - target.get("chi_phi", 0) + candidate.cost * request.so_nguoi
        return next_total // request.so_nguoi <= request.ngan_sach

    return target, rejected, [place for place in plan_places if eligible(place)]


def _replacement_rank(candidate: Place, rejected: Place) -> tuple:
    candidate_tags = {ascii_fold(tag).casefold() for tag in candidate.tags}
    rejected_tags = {ascii_fold(tag).casefold() for tag in rejected.tags}
    return (
        candidate.kind != rejected.kind,
        -len(candidate_tags & rejected_tags),
        ascii_fold(candidate.area).casefold() != ascii_fold(rejected.area).casefold(),
        (candidate.lat - rejected.lat) ** 2 + (candidate.lng - rejected.lng) ** 2,
        candidate.id,
    )


@router.patch("/plans/{token}/swipe")
def swipe(
    token: str,
    payload: SwipeRequest,
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    message: str | None = None,
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, x_session_id or payload.ma_phien, authorization)
    if not limiter.check(f"swipe:{item.session_id}", 20):
        raise HTTPException(429, "Bạn đã đổi điểm quá nhiều lần")
    if payload.dia_diem_thay_the and payload.ten_dia_diem_thay_the:
        raise HTTPException(422, "Chỉ chọn ID gợi ý hoặc nhập tên địa điểm")
    requested_place: Place | None = None
    estimated = False
    if payload.ten_dia_diem_thay_the:
        current = next((slot for day in item.plan.get("ngay", []) for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") == payload.diem_bi_loai), None)
        if not current:
            raise HTTPException(404, "Địa điểm không nằm trong kế hoạch")
        coordinates = current.get("toa_do") or {}
        requested_place = verify_place_name(payload.ten_dia_diem_thay_the.strip(), (float(coordinates.get("lat", 21.0285)), float(coordinates.get("lng", 105.8542))))
        if not requested_place:
            raise HTTPException(404, "Không tìm thấy địa điểm này tại Hà Nội")
        if requested_place.id not in {place.id for place in PLACES}:
            try:
                estimate = ai_adapter.estimate_place_metadata(requested_place.name, requested_place.kind, requested_place.area)
            except RuntimeError as exc:
                raise HTTPException(503, "Không thể ước tính dữ liệu địa điểm") from exc
            requested_place = Place(**(requested_place.__dict__ | estimate))
            estimated = True
    external = (requested_place,) if requested_place and requested_place.id not in {place.id for place in PLACES} else ()
    target, rejected, candidates = _replacement_candidates(item, payload.diem_bi_loai, same_kind=False, additional=external)
    if not candidates:
        raise HTTPException(404, "Không có địa điểm thay thế phù hợp")
    if payload.dia_diem_thay_the or requested_place:
        replacement = next((p for p in candidates if p.id == (payload.dia_diem_thay_the or requested_place.id)), None)
        if not replacement:
            raise HTTPException(422, "Địa điểm thay thế không phù hợp với khung giờ hoặc lịch trình")
    else:
        replacement = min(
            candidates,
            key=lambda p: _replacement_rank(p, rejected),
        )
    plan = json.loads(json.dumps(item.plan, ensure_ascii=False))
    new_target = next(
        slot
        for day in plan["ngay"]
        for slot in day["khoang_gio"]
        if slot["dia_diem_id"] == payload.diem_bi_loai
    )
    old_cost = new_target["chi_phi"]
    plan_request = PlanRequest.model_validate(item.request)
    localized_copy = COPY[plan_request.ngon_ngu]
    new_target.update(
        {
            "dia_diem_id": replacement.id,
            "ten_dia_diem": replacement.name,
            "loai": replacement.kind,
            "mo_ta": localized_copy[3].format(place=replacement.name, area=replacement.area),
            "ghi_chu": localized_copy[4],
            "chi_phi": replacement.cost * plan_request.so_nguoi,
            "toa_do": {"lat": replacement.lat, "lng": replacement.lng},
            "nguon": replacement.source,
            "nguon_url": replacement.source_url,
        }
    )
    for stale_key in ("du_lieu_uoc_tinh", "gio_mo_cua_uoc_tinh", "gio_dong_cua_uoc_tinh", "chi_phi_moi_nguoi", "nguon_du_lieu_uoc_tinh"):
        new_target.pop(stale_key, None)
    swap_image_url, swap_image_credit = image_for(replacement)
    new_target["anh"] = swap_image_url
    new_target["anh_nguon"] = swap_image_credit
    if estimated:
        new_target["du_lieu_uoc_tinh"] = True
        new_target["gio_mo_cua_uoc_tinh"] = replacement.open_hour
        new_target["gio_dong_cua_uoc_tinh"] = replacement.close_hour
        new_target["chi_phi_moi_nguoi"] = replacement.cost
        new_target["nguon_du_lieu_uoc_tinh"] = "AI"
        if plan_request.ngon_ngu == "vi":
            new_target["ghi_chu"] = f"AI ước tính: mở {replacement.open_hour}:00–{replacement.close_hour}:00, khoảng {replacement.cost:,} VNĐ/người. Vui lòng kiểm tra lại."
        else:
            new_target["ghi_chu"] = f"AI estimate: open {replacement.open_hour}:00–{replacement.close_hour}:00, about {replacement.cost:,} VND/person. Please verify."
    plan["tong_chi_phi"] += new_target["chi_phi"] - old_cost
    plan["chi_phi_moi_nguoi"] = plan["tong_chi_phi"] // plan_request.so_nguoi
    try:
        trusted_external = _plan_external_places(plan)
        errors = validate_plan(plan, {p.id for p in (*PLACES, *trusted_external)}, plan_request, trusted_places=trusted_external)
        if errors:
            raise PipelineUnavailable("; ".join(errors))
        if message:
            _append_turn(plan, "user", message)
            _append_turn(plan, "assistant", "Đã đổi địa điểm được chọn và kiểm tra lại ràng buộc.")
        store.update(item, payload.phien_ban, plan, item.request, f"Tinh chỉnh: {message or 'Đổi điểm'}")
    except ValueError as exc:
        raise HTTPException(409, "Lịch trình vừa được cập nhật, vui lòng tải lại") from exc
    except PipelineUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    store.penalize_tags(item.session_id, rejected.tags)
    store.log(item.session_id, "vuot_doi_diem", {"id_ke_hoach": token, "id_dia_diem_bi_loai": payload.diem_bi_loai})
    return {"ke_hoach_moi": plan, "phien_ban": item.version}


@router.get("/plans/{token}/replacement-candidates")
def replacement_candidates(
    token: str,
    diem_bi_loai: str,
    q: str = Query(default="", max_length=100),
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, x_session_id, authorization)
    if not limiter.check(f"candidate-search:{item.session_id}", 60):
        raise HTTPException(429, "Bạn đã tìm kiếm quá nhiều lần")
    _, _, eligible = _replacement_candidates(item, diem_bi_loai)
    query = ascii_fold(q.strip()).lower()
    candidates = [
        place for place in eligible
        if not query or query in ascii_fold(f"{place.name} {place.kind} {place.area}").lower()
    ][:10]
    return {"goi_y": [{"id": p.id, "ten": p.name, "loai": p.kind, "khu_vuc": p.area} for p in candidates]}


@router.delete("/plans/{token}/slots")
def delete_slot(
    token: str,
    payload: DeleteSlotRequest,
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, x_session_id or payload.ma_phien, authorization)
    if not limiter.check(f"delete-slot:{item.session_id}", 20):
        raise HTTPException(429, "Bạn đã xóa quá nhiều địa điểm")
    plan = json.loads(json.dumps(item.plan, ensure_ascii=False))
    matches = [(day, slot) for day in plan.get("ngay", []) for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") == payload.dia_diem_id]
    if not matches:
        raise HTTPException(404, "Địa điểm không nằm trong kế hoạch")
    if len(matches) != 1:
        raise HTTPException(409, "Lịch trình chứa địa điểm trùng lặp, vui lòng làm lại")
    day, removed = matches[0]
    day["khoang_gio"] = [slot for slot in day["khoang_gio"] if slot.get("dia_diem_id") != payload.dia_diem_id]
    plan_request = PlanRequest.model_validate(item.request)
    plan["tong_chi_phi"] = sum(
        max(0, slot.get("chi_phi", 0))
        for current_day in plan.get("ngay", [])
        for slot in current_day.get("khoang_gio", [])
    )
    plan["chi_phi_moi_nguoi"] = plan["tong_chi_phi"] // plan_request.so_nguoi
    trusted_external = _plan_external_places(plan)
    errors = validate_plan(plan, {p.id for p in (*PLACES, *trusted_external)}, plan_request, allow_below_minimum=True, trusted_places=trusted_external)
    if errors:
        raise HTTPException(503, "; ".join(errors))
    try:
        store.update(item, payload.phien_ban, plan, item.request, "Xóa địa điểm")
    except ValueError as exc:
        raise HTTPException(409, "Lịch trình vừa được cập nhật, vui lòng tải lại") from exc
    store.log(item.session_id, "xoa_dia_diem", {"id_ke_hoach": token, "id_dia_diem": payload.dia_diem_id})
    return {"ke_hoach_moi": plan, "phien_ban": item.version}


@router.post("/plans/{token}/regenerate")
def regenerate(
    token: str,
    payload: RegenerateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, payload.ma_phien, authorization)
    existing_token = store.get_nonce(token, payload.nonce)
    if existing_token:
        existing = store.get(existing_token)
        if existing:
            return {"ke_hoach": existing.plan, "token": existing.token, "phien_ban": existing.version}
    ip = request.client.host if request.client else "unknown"
    if not limiter.check_many([(f"regenerate:{payload.ma_phien}:{ip}", 5, 3600)]):
        raise HTTPException(429, "Bạn đã làm lại quá nhiều lần")
    try:
        store.reserve_cost(0.0, settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd)
        excluded = {
            slot["dia_diem_id"]
            for day in item.plan.get("ngay", [])
            for slot in day.get("khoang_gio", [])
            if slot.get("dia_diem_id")
        }
        plan = build_plan(PlanRequest.model_validate(item.request), excluded)
        regenerated_ids = {
            slot["dia_diem_id"]
            for day in plan.get("ngay", [])
            for slot in day.get("khoang_gio", [])
            if slot.get("dia_diem_id")
        }
        if not regenerated_ids or regenerated_ids == excluded:
            raise RuntimeError("Không đủ địa điểm để tạo một kế hoạch khác")
        _append_turn(plan, "user", "Làm lại từ đầu")
        _append_turn(plan, "assistant", "Đã tạo lại lịch trình mới từ đầu với cùng yêu cầu ban đầu.")
        store.update(item, item.version, plan, item.request, "Làm lại")
    except ValueError as exc:
        raise HTTPException(409, "Kế hoạch vừa được cập nhật, vui lòng tải lại") from exc
    except (PipelineUnavailable, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    persisted_token = store.set_nonce(token, payload.nonce, token)
    if persisted_token != token:
        existing = store.get(persisted_token)
        if existing:
            return {"ke_hoach": existing.plan, "token": existing.token, "phien_ban": existing.version}
    store.log(item.session_id, "lam_lai_tu_dau", {"id_ke_hoach": token})
    return {"ke_hoach": plan, "token": token, "phien_ban": item.version}


def _refined_request(item, message: str) -> PlanRequest:
    current = PlanRequest.model_validate(item.request)
    updates: dict = {"context": f"{current.context}; {message}"[-500:]}
    normalized = ascii_fold(message)
    people = PEOPLE_INTENT.search(message)
    if people:
        updates["so_nguoi"] = int(people.group(1))
    budget = re.search(
        r"(?:ngân sách|budget|dưới|tối đa)\s*(\d+(?:[.,]\d+)?)\s*(k|nghìn|triệu|tr)?",
        message, re.IGNORECASE,
    )
    if budget:
        amount = float(budget.group(1).replace(",", "."))
        unit = (budget.group(2) or "").lower()
        multiplier = 1_000_000 if unit in {"triệu", "tr"} else 1_000 if unit in {"k", "nghìn"} else 1
        updates["ngan_sach"] = round(amount * multiplier)
    if re.search(r"\b(cheaper|lower cost|save money|re hon|tiet kiem|gia re|it tien)\b", normalized):
        updates["ngan_sach"] = max(100_000, round((updates.get("ngan_sach") or current.ngan_sach) * 0.8))
        updates["context"] = f"{updates['context']}; prioritize lower-cost places and free/low-price experiences"[-500:]
    if re.search(r"\b(less travel|shorter route|nearby|it di chuyen|gan nhau|gan hon|di bo it)\b", normalized):
        updates["context"] = f"{updates['context']}; keep stops geographically close together and reduce transfers"[-500:]
    if re.search(r"\b(more cafe|coffee|cafe|them cafe|quan cafe|ca phe)\b", normalized):
        updates["context"] = f"{updates['context']}; add more cafe and relaxed drink stops when suitable"[-500:]
    return current.model_copy(update=updates)


@router.post("/plans/{token}/refine")
def refine(
    token: str,
    payload: RefineRequest,
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, payload.ma_phien, authorization)
    if not limiter.check(f"refine:{item.session_id}", 20):
        raise HTTPException(429, "Bạn đã tinh chỉnh quá nhiều lần")
    if SWAP_INTENT.search(payload.message):
        if not payload.dia_diem_dang_chon:
            raise HTTPException(422, "Hãy chọn một địa điểm cần đổi")
        result = swipe(
            token,
            SwipeRequest(
                diem_bi_loai=payload.dia_diem_dang_chon,
                phien_ban=payload.phien_ban,
                ma_phien=payload.ma_phien,
            ),
            payload.ma_phien,
            authorization,
            message=payload.message,
        )
        return {
            "ke_hoach": result["ke_hoach_moi"], "phien_ban": result["phien_ban"],
            "tra_loi": "Đã đổi địa điểm được chọn và kiểm tra lại ràng buộc.",
            "tra_loi_key": "swipeSuccess",
            "hoi_thoai": _conversation(result["ke_hoach_moi"]),
        }
    refined = _refined_request(item, payload.message)
    previous = _conversation(item.plan)
    try:
        plan = build_plan(refined)
        plan["hoi_thoai"] = [*previous, *plan.get("hoi_thoai", [])][-50:]
        _append_turn(plan, "user", payload.message)
        _append_turn(
            plan, "assistant",
            f"Đã áp dụng yêu cầu: ngân sách {refined.ngan_sach} VND, {refined.so_nguoi} người, "
            f"{refined.thoi_luong}. Lịch trình mới đã sẵn sàng.",
        )
        store.update(
            item, payload.phien_ban, plan, refined.model_dump(mode="json"),
            f"Tinh chỉnh: {payload.message}",
        )
    except ValueError as exc:
        raise HTTPException(409, "Kế hoạch vừa được cập nhật, vui lòng tải lại") from exc
    except (PipelineUnavailable, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    store.log(item.session_id, "tinh_chinh_bang_chat", {"message": payload.message})
    return {
        "ke_hoach": plan, "phien_ban": item.version,
        "tra_loi": "Đã áp dụng yêu cầu và tạo phiên bản lịch trình mới.",
        "tra_loi_key": "assistantWelcome",
        "tham_so": _constraint_echo(refined),
        "hoi_thoai": plan.get("hoi_thoai", previous),
    }


@router.get("/plans/{token}/versions")
def versions(
    token: str,
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, x_session_id, authorization)
    return {"ds_phien_ban": store.list_versions(token)}


@router.post("/plans/{token}/versions/{version}/restore")
def restore_version(
    token: str,
    version: int,
    payload: RestoreVersionRequest,
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Kế hoạch không tồn tại")
    owner(item, payload.ma_phien, authorization)
    historical = store.get_version(token, version)
    if not historical:
        raise HTTPException(404, "Phiên bản không tồn tại")
    try:
        store.update(
            item, payload.phien_ban_hien_tai, historical["du_lieu"],
            historical["yeu_cau"], f"Khôi phục phiên bản {version}",
        )
    except ValueError as exc:
        raise HTTPException(409, "Kế hoạch vừa được cập nhật, vui lòng tải lại") from exc
    return {"ke_hoach": item.plan, "phien_ban": item.version}

