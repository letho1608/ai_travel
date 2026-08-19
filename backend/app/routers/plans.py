import asyncio
import json
import logging
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.data import PLACES, Place, image_for
from app.pipeline.chat_turn import run_chat_turn
from app.pipeline.intent_parse import parse_intent
from app.pipeline.plan_chat import (
    _folded,
    _wants_theme_change,
    classify_plan_message,
    compose_plan_chat_reply,
    current_destination_label,
    excluded_ids_for_refine,
    refined_plan_request,
    target_slot_id_for_message,
)
from app.pipeline.planner import (
    COPY,
    LONG_TRIP_DAYS,
    PipelineUnavailable,
    _destination_context,
    _effective_hours,
    _request_understanding,
    _trip_timing,
    build_plan,
    missing_required_inputs,
    travel_minutes,
    validate_plan,
)
from app.routers.auth import resolve_user
from app.schemas import (
    ChatTurnRequest,
    CommentRequest,
    DeleteSlotRequest,
    IntentParseRequest,
    PlanRequest,
    ReadNotificationRequest,
    RefineRequest,
    RegenerateRequest,
    ResolveCommentRequest,
    RestoreVersionRequest,
    SwipeRequest,
    TripFeedbackRequest,
)
from app.services.google_places import enrich_plan_with_google, search_named_place
from app.services.osm_verify import _catalog_match, verify_place_name
from app.services.pdf_export import build_itinerary_pdf
from app.services.rate_limit import limiter
from app.services.store import store
from app.text_utils import ascii_fold

router = APIRouter(prefix="/api", tags=["plans"])
logger = logging.getLogger(__name__)
GENERATE_NONCE_SCOPE = "00000000-0000-0000-0000-000000000000"
_MAP_PLACE_CACHE: dict[str, Place] = {}
_MAP_SOURCES = {"Google Places", "Nominatim"}


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
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"


async def _keepalive_until(task: asyncio.Task):
    try:
        while True:
            done, _pending = await asyncio.wait({task}, timeout=8.0)
            if done:
                return
            yield ": keepalive\n\n"
    except BaseException:
        if not task.done():
            task.cancel()
        raise


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


@router.post("/intent/parse")
def parse_user_intent(payload: IntentParseRequest):
    return parse_intent(payload.context, payload.ngon_ngu)


@router.post("/chat/turn")
def chat_turn(payload: ChatTurnRequest):
    return run_chat_turn(
        [{"role": item.role, "content": item.content} for item in payload.messages],
        payload.ngon_ngu,
    )


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
        try:
            timing = await to_thread(_trip_timing, payload)
            if timing.days >= LONG_TRIP_DAYS:
                yield sse("status", {"status": "long_trip_wait"})
            yield sse("status", {"status": "routing_plan"})
            understanding = await to_thread(_request_understanding, payload)
            required = await to_thread(missing_required_inputs, payload, understanding)
            if required["missing_fields"]:
                store.log(session_id, "boc_tach_yeu_cau", required["understanding"])
                yield sse(
                    "error",
                    {
                        "code": "missing_required_input",
                        "detail": required["questions"][0],
                        "missing_fields": required["missing_fields"],
                        "questions": required["questions"],
                    },
                )
                return
            build_task = asyncio.create_task(to_thread(build_plan, payload, None, understanding))
            async for chunk in _keepalive_until(build_task):
                yield chunk
            plan = build_task.result()
            enrich_task = asyncio.create_task(to_thread(enrich_plan_with_google, plan))
            async for chunk in _keepalive_until(enrich_task):
                yield chunk
            plan = enrich_task.result()
            _append_turn(plan, "user", payload.context)
            greeting = plan.get("loi_chao_chang")
            if isinstance(greeting, str) and greeting.strip():
                _append_turn(plan, "assistant", greeting.strip())
            item = store.save(session_id, plan, payload.model_dump(mode="json"))
            if generate_nonce:
                store.set_nonce(GENERATE_NONCE_SCOPE, generate_nonce, item.token)
            if isinstance(plan.get("dau_vao_da_hieu"), dict):
                store.log(session_id, "boc_tach_yeu_cau", plan["dau_vao_da_hieu"])
            store.log(session_id, "tao_ke_hoach_thanh_cong", {"id_ke_hoach": item.token})
            yield sse("result", {"type": "plan", "ma_phien": session_id, "token": item.token, "phien_ban": 1, "plan": plan})
        except asyncio.CancelledError:
            yield sse(
                "error",
                {
                    "code": "499",
                    "detail": "Kết nối bị ngắt khi đang tạo lịch trình. Vui lòng thử lại.",
                },
            )
            return
        except (PipelineUnavailable, RuntimeError) as exc:
            yield sse("error", {"code": "503", "detail": str(exc)})
        except Exception:
            logger.exception("plan generate failed")
            yield sse(
                "error",
                {
                    "code": "500",
                    "detail": "Không tạo được lịch trình cho điểm đến này. Vui lòng thử lại.",
                },
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/plans/history")
def plan_history_alias(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    return list_plans(x_session_id=x_session_id, authorization=authorization)


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


def _remember_map_place(place: Place | None) -> Place | None:
    if place and place.id not in {item.id for item in PLACES}:
        _MAP_PLACE_CACHE[place.id] = place
    return place


def _slot_origin(slot: dict, request: PlanRequest) -> tuple[tuple[float, float], str | None]:
    dest_lat, dest_lng, dest_name = _destination_context(request)
    coordinates = slot.get("toa_do") or {}
    try:
        lat = float(coordinates.get("lat", dest_lat))
        lng = float(coordinates.get("lng", dest_lng))
    except (TypeError, ValueError):
        lat, lng = dest_lat, dest_lng
    return (lat, lng), dest_name


def _resolve_named_place(name: str, origin: tuple[float, float], city: str | None = None) -> Place | None:
    catalog = _catalog_match(name, origin)
    if catalog:
        return catalog
    google = search_named_place(name, origin, city)
    if google:
        return _remember_map_place(google)
    osm = verify_place_name(name, origin, city)
    if osm:
        return _remember_map_place(osm)
    return None


def _place_from_slot(slot: dict) -> Place:
    coordinates = slot.get("toa_do") or {}
    try:
        lat = float(coordinates["lat"])
        lng = float(coordinates["lng"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Địa điểm ngoài catalog thiếu tọa độ") from exc
    source = str(slot.get("nguon") or "")
    source_url = slot.get("nguon_url")
    map_verified = source in _MAP_SOURCES and bool(source_url)
    estimated = bool(slot.get("du_lieu_uoc_tinh")) and bool(source_url) and all(
        key in slot for key in ("gio_mo_cua_uoc_tinh", "gio_dong_cua_uoc_tinh", "chi_phi_moi_nguoi")
    )
    if not map_verified and not estimated:
        raise ValueError("Địa điểm ngoài catalog thiếu metadata đã xác minh")
    return Place(
        id=slot["dia_diem_id"],
        name=slot.get("ten_dia_diem") or slot["dia_diem_id"],
        kind=slot.get("loai") or "dia_danh",
        area=slot.get("khu_vuc") or "Việt Nam",
        lat=lat,
        lng=lng,
        cost=max(0, int(slot.get("chi_phi_moi_nguoi", 0))),
        duration_min=60,
        tags=("verified_external", "map_verified") if map_verified else ("verified_external",),
        open_hour=int(slot.get("gio_mo_cua_uoc_tinh", 7)),
        close_hour=int(slot.get("gio_dong_cua_uoc_tinh", 22)),
        source=source or "Nominatim",
        source_url=source_url,
        image_url=slot.get("anh"),
        image_credit=slot.get("anh_nguon"),
        google_place_id=slot.get("google_place_id"),
        google_maps_url=slot.get("google_maps_url") or slot.get("google_review_url"),
    )


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


def _replacement_candidates(item, rejected_id: str, *, same_kind: bool = False, additional: tuple[Place, ...] = (), strict_travel: bool = True):
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
        if previous_slot and strict_travel:
            previous = by_id.get(previous_slot["dia_diem_id"])
            if previous and minutes(target["bat_dau"]) - minutes(previous_slot["ket_thuc"]) < travel_minutes(previous, candidate):
                return False
        if next_slot and strict_travel:
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
    if payload.ten_dia_diem_thay_the:
        current = next((slot for day in item.plan.get("ngay", []) for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") == payload.diem_bi_loai), None)
        if not current:
            raise HTTPException(404, "Địa điểm không nằm trong kế hoạch")
        origin, city = _slot_origin(current, PlanRequest.model_validate(item.request))
        requested_place = _resolve_named_place(payload.ten_dia_diem_thay_the.strip(), origin, city)
        if not requested_place:
            raise HTTPException(404, "Địa điểm không tồn tại")
    elif payload.dia_diem_thay_the:
        requested_place = _MAP_PLACE_CACHE.get(payload.dia_diem_thay_the)
    catalog_ids = {place.id for place in PLACES}
    external = (requested_place,) if requested_place and requested_place.id not in catalog_ids else ()
    explicit = bool(payload.dia_diem_thay_the or payload.ten_dia_diem_thay_the)
    target, rejected, candidates = _replacement_candidates(
        item,
        payload.diem_bi_loai,
        same_kind=False,
        additional=external,
        strict_travel=not explicit,
    )
    meal_type = target.get("bua_an")
    if meal_type and not explicit:
        preferred = [place for place in candidates if place.kind == rejected.kind]
        if not preferred and meal_type in {"trua", "toi", "sang"}:
            preferred = [place for place in candidates if place.kind in {"nha_hang", "quan_an"}]
        if not preferred and meal_type == "nghi":
            preferred = [place for place in candidates if place.kind in {"cafe", "cong_vien", "nha_hang", "quan_an"}]
        if preferred:
            candidates = preferred
    if payload.dia_diem_thay_the or requested_place:
        replacement = next((p for p in candidates if p.id == (payload.dia_diem_thay_the or requested_place.id)), None)
        if not replacement:
            raise HTTPException(422, "Địa điểm thay thế không phù hợp với khung giờ hoặc lịch trình")
    else:
        if not candidates:
            raise HTTPException(404, "Không có địa điểm thay thế phù hợp")
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
    for stale_key in ("du_lieu_uoc_tinh", "nguon_du_lieu_uoc_tinh"):
        new_target.pop(stale_key, None)
    if replacement.id in catalog_ids:
        for stale_key in ("gio_mo_cua_uoc_tinh", "gio_dong_cua_uoc_tinh", "chi_phi_moi_nguoi", "google_place_id", "google_maps_url"):
            new_target.pop(stale_key, None)
    else:
        new_target["gio_mo_cua_uoc_tinh"] = replacement.open_hour
        new_target["gio_dong_cua_uoc_tinh"] = replacement.close_hour
        new_target["chi_phi_moi_nguoi"] = replacement.cost
        if replacement.google_place_id:
            new_target["google_place_id"] = replacement.google_place_id
        if replacement.google_maps_url:
            new_target["google_maps_url"] = replacement.google_maps_url
    swap_image_url, swap_image_credit = image_for(replacement)
    new_target["anh"] = swap_image_url
    new_target["anh_nguon"] = swap_image_credit
    plan["tong_chi_phi"] += new_target["chi_phi"] - old_cost
    plan["chi_phi_moi_nguoi"] = plan["tong_chi_phi"] // plan_request.so_nguoi
    try:
        trusted_external = _plan_external_places(plan)
        errors = validate_plan(plan, {p.id for p in (*PLACES, *trusted_external)}, plan_request, trusted_places=trusted_external)
        if errors:
            raise PipelineUnavailable("; ".join(errors))
        plan = enrich_plan_with_google(plan)
        if message:
            dest_name = _destination_context(plan_request)[2]
            reply = compose_plan_chat_reply(
                locale=plan_request.ngon_ngu,
                action="swap",
                message=message,
                plan=plan,
                dest_name=dest_name,
                old_name=rejected.name,
                new_name=replacement.name,
            )
            _append_turn(plan, "user", message)
            _append_turn(plan, "assistant", reply)
        store.update(item, payload.phien_ban, plan, item.request, f"Tinh chỉnh: {message or 'Đổi điểm'}")
    except ValueError as exc:
        raise HTTPException(409, "Lịch trình vừa được cập nhật, vui lòng tải lại") from exc
    except PipelineUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    tag_deltas = {tag: -1 for tag in rejected.tags}
    for tag in replacement.tags:
        tag_deltas[tag] = tag_deltas.get(tag, 0) + 1
    store.adjust_tag_weights(
        item.session_id,
        tag_deltas,
        user_id=item.user_id,
        reason="user_replaced_place",
        evidence={
            "id_ke_hoach": token,
            "id_dia_diem_bi_loai": rejected.id,
            "id_dia_diem_thay_the": replacement.id,
        },
    )
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
    target, _, eligible = _replacement_candidates(item, diem_bi_loai)
    query = ascii_fold(q.strip()).lower()
    candidates = [
        place for place in eligible
        if not query or query in ascii_fold(f"{place.name} {place.kind} {place.area}").lower()
    ]
    if q.strip() and len(q.strip()) >= 3:
        plan_request = PlanRequest.model_validate(item.request)
        origin, city = _slot_origin(target, plan_request)
        mapped = _resolve_named_place(q.strip(), origin, city)
        used_ids = {
            slot.get("dia_diem_id")
            for day in item.plan.get("ngay", [])
            for slot in day.get("khoang_gio", [])
        }
        if mapped and mapped.id not in used_ids and mapped.id not in {place.id for place in candidates}:
            candidates = [mapped, *candidates]
    return {"goi_y": [{"id": p.id, "ten": p.name, "loai": p.kind, "khu_vuc": p.area} for p in candidates[:10]]}


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
        plan = enrich_plan_with_google(plan)
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
    return refined_plan_request(item, message)


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
    current_request = PlanRequest.model_validate(item.request)
    locale = current_request.ngon_ngu
    action = classify_plan_message(payload.message, item, payload.dia_diem_dang_chon)
    theme = _wants_theme_change(payload.message, _folded(payload.message))

    if action == "swap":
        target_slot_id = target_slot_id_for_message(
            item.plan, payload.message, payload.dia_diem_dang_chon
        )
        if target_slot_id:
            try:
                result = swipe(
                    token,
                    SwipeRequest(
                        diem_bi_loai=target_slot_id,
                        phien_ban=payload.phien_ban,
                        ma_phien=payload.ma_phien,
                    ),
                    payload.ma_phien,
                    authorization,
                    message=payload.message,
                )
                plan = result["ke_hoach_moi"]
                history = _conversation(plan)
                reply = history[-1]["noi_dung"] if history and history[-1].get("vai_tro") == "assistant" else result.get("tra_loi")
                return {
                    "ke_hoach": plan,
                    "phien_ban": result["phien_ban"],
                    "tra_loi": reply or "Mình đổi điểm đó rồi.",
                    "tra_loi_key": "swipeSuccess",
                    "tham_so": _constraint_echo(current_request),
                    "hoi_thoai": history,
                }
            except Exception:
                action = "rebuild"

    if action == "talk":
        plan = json.loads(json.dumps(item.plan, ensure_ascii=False))
        reply = compose_plan_chat_reply(
            locale=locale,
            action="talk",
            message=payload.message,
            plan=plan,
            dest_name=current_destination_label(item),
        )
        try:
            _append_turn(plan, "user", payload.message)
            _append_turn(plan, "assistant", reply)
            store.update(item, payload.phien_ban, plan, item.request, f"Chat: {payload.message}")
        except ValueError as exc:
            raise HTTPException(409, "Kế hoạch vừa được cập nhật, vui lòng tải lại") from exc
        store.log(item.session_id, "tinh_chinh_bang_chat", {"message": payload.message, "action": "talk"})
        return {
            "ke_hoach": plan,
            "phien_ban": item.version,
            "tra_loi": reply,
            "tra_loi_key": "assistantWelcome",
            "tham_so": _constraint_echo(current_request),
            "hoi_thoai": plan.get("hoi_thoai", []),
        }

    refined = refined_plan_request(item, payload.message)
    previous = _conversation(item.plan)
    dest_name = _destination_context(refined)[2]
    dest_changed = dest_name != current_destination_label(item)
    excluded = excluded_ids_for_refine(payload.message, item)
    try:
        try:
            plan = build_plan(refined, excluded)
        except PipelineUnavailable:
            if theme == "food" and excluded:
                plan = build_plan(refined, None)
            else:
                raise
        plan = enrich_plan_with_google(plan)
        plan["hoi_thoai"] = [*previous, *plan.get("hoi_thoai", [])][-50:]
        reply = compose_plan_chat_reply(
            locale=locale,
            action="rebuild",
            message=payload.message,
            plan=plan,
            dest_name=dest_name,
            theme=theme,
            dest_changed=bool(dest_changed),
        )
        _append_turn(plan, "user", payload.message)
        _append_turn(plan, "assistant", reply)
        store.update(
            item, payload.phien_ban, plan, refined.model_dump(mode="json"),
            f"Tinh chỉnh: {payload.message}",
        )
    except ValueError as exc:
        raise HTTPException(409, "Kế hoạch vừa được cập nhật, vui lòng tải lại") from exc
    except (PipelineUnavailable, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    store.log(item.session_id, "tinh_chinh_bang_chat", {"message": payload.message, "action": "rebuild"})
    return {
        "ke_hoach": plan, "phien_ban": item.version,
        "tra_loi": reply,
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

