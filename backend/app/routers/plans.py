import json
import re
import unicodedata
from asyncio import to_thread
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.data import PLACES
from app.pipeline.planner import COPY, PipelineUnavailable, build_plan, validate_plan
from app.routers.auth import resolve_user
from app.schemas import (
    CommentRequest,
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
from app.services.rate_limit import limiter
from app.services.store import store

SWAP_INTENT = re.compile(
    r"\b(Ä‘á»•i|thay|replace|swap|cambiar|remplacer|ersetzen|sostituire|substituir|"
    r"vervangen|zamieÅ„|Ð·Ð°Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ|deÄŸiÅŸtir|æ›¿æ¢|æ›´æ¢|äº¤æ›|ç½®ãæ›ãˆ|êµì²´|à¹€à¸›à¸¥à¸µà¹ˆà¸¢à¸™|"
    r"Ø§Ø³ØªØ¨Ø¯Ø§Ù„|×”×—×œ×£|à¤¬à¤¦à¤²à¥‡à¤‚|ÑÐ¼ÐµÐ½Ð¸)\b",
    re.IGNORECASE,
)
PEOPLE_INTENT = re.compile(
    r"\b(\d{1,2})\s*(ngÆ°á»i|people|persons?|personas?|personnes?|personen|persone|"
    r"pessoas?|osÃ³b|Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº|kiÅŸi|äºº|ëª…|à¸„à¸™|Ø£Ø´Ø®Ø§Øµ|×× ×©×™×|à¤²à¥‹à¤—|Ð´ÑƒÑˆÐ¸)\b",
    re.IGNORECASE,
)

router = APIRouter(prefix="/api", tags=["plans"])
GENERATE_NONCE_SCOPE = "00000000-0000-0000-0000-000000000000"


def _generate_nonce_key(session_id: str, nonce: str) -> str:
    return f"{session_id}:{nonce}"


def owner(item, session_id: str | None, authorization: str | None = None) -> None:
    user = resolve_user(authorization)
    if item.user_id and user and item.user_id == user["id"]:
        return
    if not session_id or item.session_id != session_id:
        raise HTTPException(403, "Link chia sáº» chá»‰ cÃ³ quyá»n xem")


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/notifications")
def notifications(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if not user and not x_session_id:
        raise HTTPException(401, "Thiáº¿u phiÃªn hoáº·c Ä‘Äƒng nháº­p")
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
        raise HTTPException(404, "KhÃ´ng tÃ¬m tháº¥y thÃ´ng bÃ¡o") from exc
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i hoáº·c Ä‘Ã£ háº¿t háº¡n")
    return {"ke_hoach": item.plan, "phien_ban": item.version, "token": item.token}


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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    request = PlanRequest.model_validate(item.request)
    locale = request.ngon_ngu
    start_date = request.ngay_di or datetime.now(UTC).date()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    language = {"zh": "zh-CN"}.get(locale, locale)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN",
        f"PRODID:-//Minh Di Dau The//{language.upper()}",
        f"X-WR-CALNAME;LANGUAGE={language}:MÃ¬nh Äi ÄÃ¢u Tháº¿",
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, payload.ma_phien, authorization)
    trip_date = PlanRequest.model_validate(item.request).ngay_di
    if not trip_date or trip_date >= datetime.now(UTC).date():
        raise HTTPException(409, "Chá»‰ cÃ³ thá»ƒ gá»­i pháº£n há»“i sau chuyáº¿n Ä‘i")
    user = resolve_user(authorization)
    try:
        feedback = store.save_feedback(
            token, payload.ma_phien, user["id"] if user else None,
            payload.diem, payload.noi_dung,
        )
    except ValueError as exc:
        raise HTTPException(409, "Báº¡n Ä‘Ã£ gá»­i pháº£n há»“i cho chuyáº¿n Ä‘i nÃ y") from exc
    store.log(payload.ma_phien, "phan_hoi_sau_chuyen", {"diem": payload.diem})
    return {"phan_hoi": feedback}


@router.get("/plans/{token}/comments")
def list_comments(token: str):
    if not store.get(token):
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    return {"ds_binh_luan": store.list_comments(token)}


@router.post("/plans/{token}/comments", status_code=201)
def add_comment(
    token: str,
    payload: CommentRequest,
    authorization: str | None = Header(default=None),
):
    if not store.get(token):
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    if not limiter.check(f"comment:{token}:{payload.ma_phien}", 10, 3600):
        raise HTTPException(429, "Báº¡n Ä‘Ã£ gá»­i quÃ¡ nhiá»u bÃ¬nh luáº­n")
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, payload.ma_phien, authorization)
    comment = store.resolve_comment(token, comment_id, payload.da_giai_quyet)
    if not comment:
        raise HTTPException(404, "BÃ¬nh luáº­n khÃ´ng tá»“n táº¡i")
    return {"binh_luan": comment}


@router.get("/plans")
def list_plans(
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    user = resolve_user(authorization)
    if not x_session_id and not user:
        raise HTTPException(401, "Thiáº¿u phiÃªn hoáº·c thÃ´ng tin Ä‘Äƒng nháº­p")
    items = [
        {"token": item.token, "ke_hoach": item.plan, "phien_ban": item.version}
        for item in store.list_for_owner(x_session_id, user["id"] if user else None)
    ]
    return {"ds_ke_hoach": items}


@router.patch("/plans/{token}/swipe")
def swipe(
    token: str,
    payload: SwipeRequest,
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, x_session_id or payload.ma_phien, authorization)
    if not limiter.check(f"swipe:{item.session_id}", 20):
        raise HTTPException(429, "Báº¡n Ä‘Ã£ Ä‘á»•i Ä‘iá»ƒm quÃ¡ nhiá»u láº§n")
    slots = [slot for day in item.plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    matching_slots = [slot for slot in slots if slot["dia_diem_id"] == payload.diem_bi_loai]
    if not matching_slots:
        raise HTTPException(404, "Äá»‹a Ä‘iá»ƒm khÃ´ng náº±m trong káº¿ hoáº¡ch")
    if len(matching_slots) != 1:
        raise HTTPException(409, "Lá»‹ch trÃ¬nh chá»©a Ä‘á»‹a Ä‘iá»ƒm trÃ¹ng láº·p, vui lÃ²ng lÃ m láº¡i")
    used = {s["dia_diem_id"] for s in slots}
    rejected = next((p for p in PLACES if p.id == payload.diem_bi_loai), None)
    if not rejected:
        raise HTTPException(404, "Äá»‹a Ä‘iá»ƒm khÃ´ng cÃ²n trong danh má»¥c")
    target = matching_slots[0]
    candidates = [
        p
        for p in PLACES
        if p.id not in used
        and p.kind == rejected.kind
        and p.open_hour <= int(target["bat_dau"][:2])
        and int(target["ket_thuc"][:2]) <= p.close_hour
    ]
    if not candidates:
        raise HTTPException(404, "KhÃ´ng cÃ³ Ä‘á»‹a Ä‘iá»ƒm thay tháº¿ phÃ¹ há»£p")
    replacement = min(
        candidates,
        key=lambda p: (p.lat - rejected.lat) ** 2 + (p.lng - rejected.lng) ** 2,
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
    plan["tong_chi_phi"] += new_target["chi_phi"] - old_cost
    plan["chi_phi_moi_nguoi"] = plan["tong_chi_phi"] // plan_request.so_nguoi
    try:
        errors = validate_plan(plan, {p.id for p in PLACES}, plan_request)
        if errors:
            raise PipelineUnavailable("; ".join(errors))
        store.update(item, payload.phien_ban, plan)
    except ValueError as exc:
        raise HTTPException(409, "Lá»‹ch trÃ¬nh vá»«a Ä‘Æ°á»£c cáº­p nháº­t, vui lÃ²ng táº£i láº¡i") from exc
    except PipelineUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    store.penalize_tags(item.session_id, rejected.tags)
    store.log(item.session_id, "vuot_doi_diem", {"id_ke_hoach": token, "id_dia_diem_bi_loai": payload.diem_bi_loai})
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, payload.ma_phien, authorization)
    existing_token = store.get_nonce(token, payload.nonce)
    if existing_token:
        existing = store.get(existing_token)
        if existing:
            return {"ke_hoach": existing.plan, "token": existing.token, "phien_ban": existing.version}
    ip = request.client.host if request.client else "unknown"
    if not limiter.check_many([(f"regenerate:{payload.ma_phien}:{ip}", 5, 3600)]):
        raise HTTPException(429, "Báº¡n Ä‘Ã£ lÃ m láº¡i quÃ¡ nhiá»u láº§n")
    try:
        store.reserve_cost(0.0, settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd)
        first_slot = next(
            (slot for day in item.plan.get("ngay", []) for slot in day.get("khoang_gio", [])),
            None,
        )
        excluded = {first_slot["dia_diem_id"]} if first_slot else set()
        plan = build_plan(PlanRequest.model_validate(item.request), excluded)
    except (PipelineUnavailable, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    new_item = store.save(item.session_id, plan, item.request)
    persisted_token = store.set_nonce(token, payload.nonce, new_item.token)
    if persisted_token != new_item.token:
        existing = store.get(persisted_token)
        if existing:
            return {"ke_hoach": existing.plan, "token": existing.token, "phien_ban": existing.version}
    store.log(item.session_id, "lam_lai_tu_dau", {"id_ke_hoach_cu": token})
    return {"ke_hoach": plan, "token": new_item.token, "phien_ban": 1}


def _refined_request(item, message: str) -> PlanRequest:
    current = PlanRequest.model_validate(item.request)
    updates: dict = {"context": f"{current.context}; {message}"[-500:]}
    normalized = unicodedata.normalize("NFKD", message).encode("ascii", "ignore").decode("ascii").lower()
    people = PEOPLE_INTENT.search(message)
    if people:
        updates["so_nguoi"] = int(people.group(1))
    budget = re.search(
        r"(?:ngÃ¢n sÃ¡ch|budget|dÆ°á»›i|tá»‘i Ä‘a)\s*(\d+(?:[.,]\d+)?)\s*(k|nghÃ¬n|triá»‡u|tr)?",
        message, re.IGNORECASE,
    )
    if budget:
        amount = float(budget.group(1).replace(",", "."))
        unit = (budget.group(2) or "").lower()
        multiplier = 1_000_000 if unit in {"triá»‡u", "tr"} else 1_000 if unit in {"k", "nghÃ¬n"} else 1
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, payload.ma_phien, authorization)
    if not limiter.check(f"refine:{item.session_id}", 20):
        raise HTTPException(429, "Báº¡n Ä‘Ã£ tinh chá»‰nh quÃ¡ nhiá»u láº§n")
    if SWAP_INTENT.search(payload.message):
        if not payload.dia_diem_dang_chon:
            raise HTTPException(422, "HÃ£y chá»n má»™t Ä‘á»‹a Ä‘iá»ƒm cáº§n Ä‘á»•i")
        result = swipe(
            token,
            SwipeRequest(
                diem_bi_loai=payload.dia_diem_dang_chon,
                phien_ban=payload.phien_ban,
                ma_phien=payload.ma_phien,
            ),
            payload.ma_phien,
            authorization,
        )
        return {
            "ke_hoach": result["ke_hoach_moi"], "phien_ban": result["phien_ban"],
            "tra_loi": "ÄÃ£ Ä‘á»•i Ä‘á»‹a Ä‘iá»ƒm Ä‘Æ°á»£c chá»n vÃ  kiá»ƒm tra láº¡i rÃ ng buá»™c.",
            "tra_loi_key": "swipeSuccess",
        }
    refined = _refined_request(item, payload.message)
    try:
        plan = build_plan(refined)
        store.update(
            item, payload.phien_ban, plan, refined.model_dump(mode="json"),
            f"Tinh chá»‰nh: {payload.message}",
        )
    except ValueError as exc:
        raise HTTPException(409, "Káº¿ hoáº¡ch vá»«a Ä‘Æ°á»£c cáº­p nháº­t, vui lÃ²ng táº£i láº¡i") from exc
    except (PipelineUnavailable, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    store.log(item.session_id, "tinh_chinh_bang_chat", {"message": payload.message})
    return {
        "ke_hoach": plan, "phien_ban": item.version,
        "tra_loi": "ÄÃ£ Ã¡p dá»¥ng yÃªu cáº§u vÃ  táº¡o phiÃªn báº£n lá»‹ch trÃ¬nh má»›i.",
        "tra_loi_key": "assistantWelcome",
    }


@router.get("/plans/{token}/versions")
def versions(
    token: str,
    x_session_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    item = store.get(token)
    if not item:
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
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
        raise HTTPException(404, "Káº¿ hoáº¡ch khÃ´ng tá»“n táº¡i")
    owner(item, payload.ma_phien, authorization)
    historical = store.get_version(token, version)
    if not historical:
        raise HTTPException(404, "PhiÃªn báº£n khÃ´ng tá»“n táº¡i")
    try:
        store.update(
            item, payload.phien_ban_hien_tai, historical["du_lieu"],
            historical["yeu_cau"], f"KhÃ´i phá»¥c phiÃªn báº£n {version}",
        )
    except ValueError as exc:
        raise HTTPException(409, "Káº¿ hoáº¡ch vá»«a Ä‘Æ°á»£c cáº­p nháº­t, vui lÃ²ng táº£i láº¡i") from exc
    return {"ke_hoach": item.plan, "phien_ban": item.version}

