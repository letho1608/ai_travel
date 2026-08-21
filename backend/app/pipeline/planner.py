import hashlib
import inspect
import random
import re
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import NamedTuple
from functools import lru_cache

UTC = timezone.utc

import httpx

from app.config import settings
from app.data import (
    DISTANCE_METADATA,
    KNOWN_PLACE_NAMES_BY_ID,
    PLACES,
    Place,
    cover_for_destination,
    famous_priority,
    image_for,
    is_famous_place,
    place_match_key,
    source_for,
)
from app.pipeline.visit_guidance import VisitGuidance, guidance_for
from app.pipeline.routing import (
    TRAVEL_ESTIMATE_POLICY,
    estimate_travel,
    haversine_km,
    is_routable,
    nearest_neighbor,
    public_transit_policy_status,
    route_calibration_status,
    travel_minutes,
    travel_matrix,
    two_opt,
)
from app.pipeline.cp_sat_solver import (
    optimize_day_schedule_with_cp_sat,
    optimize_order_with_cp_sat,
    select_places_with_cp_sat,
    verify_fixed_schedule_with_cp_sat,
)
from app.pipeline.intent_parse import place_matches_policy, place_policy_score, rule_structured_intent
from app.schemas import AIExtractPayload, PlanRequest
from pydantic import ValidationError
from app.pipeline.solar import sunset_for_date
from app.services.ai import ai_adapter
from app.services.osm_verify import verify_place_name
from app.services.quality_benchmarks import REQUIRED_BASELINES
from app.services.store import store
from app.services.weather import WeatherUnavailable, get_daily_weather
from app.text_utils import ascii_fold

LIMITS = {
    "vai_gio": (4, 300, 1),
    "nua_ngay": (5, 600, 1),
    "ca_ngay": (8, 900, 1),
    # ~8 stops/day including midday rest + evening, matching denser full days.
    "nhieu_ngay": (16, 900, 2),
}
LONG_TRIP_DAYS = 8
TRAVEL_MATRIX_PLACE_CAP = 25
# Frontend/schema still send 1 triệu when the user never named a budget.
_DEFAULT_UNSTATED_BUDGET = 1_000_000
UNCONSTRAINED_BUDGET = 100_000_000


def _is_long_trip(days: int) -> bool:
    return days >= LONG_TRIP_DAYS


def _budget_mentioned(context: str) -> bool:
    folded = " ".join(ascii_fold(context).split())
    return bool(
        re.search(r"\b\d+(?:[.,]\d+)?\s*(?:trieu|tr|nghin|ngan|dong|vnd|million)\b", folded)
        or "ngan sach" in folded
        or "budget" in folded
    )


def budget_applies(request: PlanRequest | None) -> bool:
    """Budget is a hard cap only when the user (or a refine/test) actually set one."""
    if not request:
        return False
    if _budget_mentioned(request.context):
        return True
    return request.ngan_sach != _DEFAULT_UNSTATED_BUDGET


def budget_cap(request: PlanRequest | None) -> int:
    if budget_applies(request):
        return request.ngan_sach
    return UNCONSTRAINED_BUDGET


def _title_prefix(locale: str) -> str:
    return "Lịch trình du lịch" if locale == "vi" else "Travel itinerary:"


_MONTH_LABELS_EN = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _is_month_only_label(label: str | None) -> bool:
    folded = " ".join(_ascii_fold(label or "").casefold().split())
    if re.fullmatch(r"thang \d{1,2}", folded):
        return True
    return folded in {name.casefold() for name in _MONTH_LABELS_EN if name}


def _duration_span(request: PlanRequest, number_of_days: int) -> str:
    if number_of_days >= 2:
        return f"{number_of_days} ngày" if request.ngon_ngu == "vi" else f"{number_of_days} days"
    if request.ngon_ngu == "vi":
        if request.thoi_luong == "vai_gio":
            return "vài giờ"
        if request.thoi_luong == "nua_ngay":
            return "nửa ngày"
        if request.thoi_luong == "ca_ngay":
            return "1 ngày"
        return "1 ngày"
    if request.thoi_luong == "vai_gio":
        return "a few hours"
    if request.thoi_luong == "nua_ngay":
        return "half day"
    return "1 day"


def _title_span(request: PlanRequest, number_of_days: int) -> str:
    timing = _trip_timing(request)
    duration = _duration_span(request, number_of_days)
    if _is_month_only_label(timing.date_label):
        if number_of_days >= 2 or timing.asked_days >= 2:
            return f"{timing.date_label}, {duration}"
        return timing.date_label or duration
    if timing.date_label or timing.clock_label:
        return timing.date_label or timing.clock_label or ""
    return duration


def _title_motif(request: PlanRequest, destination_label: str | None = None) -> str:
    folded = " ".join(_ascii_fold(request.context).split())
    locale = request.ngon_ngu
    dest_key = _ascii_fold(destination_label or "").casefold()
    inland = dest_key in {"yen tu", "chua huong"}
    catalog: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (("ca phe", "cafe", "coffee"), "cà phê", "coffee"),
        (("an ngon", "am thuc", "hai san", "food"), "ẩm thực", "food"),
        (("van hoa", "culture", "bao tang", "museum"), "văn hóa", "culture"),
        (("bien", "beach", "bai bien"), "biển", "the beach"),
        (("di bo", "walk"), "đi bộ", "walking"),
        (("checkin", "check in"), "check-in", "photo stops"),
        (("chua lanh", "chill", "healing"), "chữa lành", "a slower pace"),
        (("cuoi tuan", "weekend"), "cuối tuần", "the weekend"),
    )
    picked: list[str] = []
    for keys, vi_label, en_label in catalog:
        if inland and vi_label in {"biển", "the beach"}:
            continue
        if any(key in folded for key in keys):
            picked.append(vi_label if locale == "vi" else en_label)
        if len(picked) == 2:
            break
    return " ".join(picked)


def _plan_title(destination_label: str | None, request: PlanRequest, number_of_days: int) -> str:
    dest = destination_label or ("Việt Nam" if request.ngon_ngu == "vi" else "Vietnam")
    people = request.so_nguoi
    motif = _title_motif(request, destination_label)
    span = _title_span(request, number_of_days)
    prefix = _title_prefix(request.ngon_ngu)
    if request.ngon_ngu == "vi":
        head = " ".join(part for part in (prefix, motif, dest) if part)
        return f"{head} {span} cho {people} người"
    people_unit = "person" if people == 1 else "people"
    head = " ".join(part for part in (prefix, motif, dest) if part)
    return f"{head} · {span} for {people} {people_unit}"


def _title_has_destination(title: str, destination_label: str | None) -> bool:
    if not destination_label:
        return True
    dest_key = re.sub(r"[^a-z0-9]+", "", _ascii_fold(destination_label).casefold())
    title_key = re.sub(r"[^a-z0-9]+", "", _ascii_fold(title).casefold())
    aliases = {dest_key}
    if dest_key in {"tphcm", "hochiminh", "hochiminhcity"}:
        aliases.update({"tphcm", "saigon", "hochiminh"})
    if dest_key == "hanoi":
        aliases.add("hanoi")
    return any(alias and alias in title_key for alias in aliases)


def _finalize_plan_title(
    proposed: object,
    destination_label: str | None,
    request: PlanRequest,
    number_of_days: int,
) -> str:
    fallback = _plan_title(destination_label, request, number_of_days)
    if not isinstance(proposed, str):
        return fallback
    cleaned = " ".join(proposed.replace("“", "").replace("”", "").replace('"', "").split()).rstrip(" .")
    if not cleaned or cleaned.count("·") >= 2:
        return fallback
    prefix = _title_prefix(request.ngon_ngu)
    if not _ascii_fold(cleaned).casefold().startswith(_ascii_fold(prefix).casefold()):
        cleaned = f"{prefix} {cleaned}".strip()
    if len(cleaned) < 18 or len(cleaned) > 90:
        return fallback
    if destination_label and destination_label not in {"Việt Nam", "Vietnam"} and not _title_has_destination(cleaned, destination_label):
        cleaned = f"{cleaned} ở {destination_label}" if request.ngon_ngu == "vi" else f"{cleaned} in {destination_label}"
        if len(cleaned) > 90:
            return fallback
    timing = _trip_timing(request)
    folded = _ascii_fold(cleaned).casefold()
    if _is_month_only_label(timing.date_label) and re.search(r"\b\d{1,2}/\d{1,2}\b", cleaned) and "–" not in cleaned:
        return fallback
    if number_of_days >= 2:
        has_days = (
            re.search(rf"\b{number_of_days}\s*ngay\b", folded)
            or re.search(rf"\b{number_of_days}\s*days?\b", folded)
        )
        if not has_days:
            return fallback
    people = request.so_nguoi
    if people and not re.search(rf"\b{people}\b", cleaned) and not (
        people == 2 and ("hai nguoi" in folded or "two people" in folded)
    ):
        return fallback
    return cleaned


MAX_TRIP_DAYS = 30
MAX_ASKED_DAYS = 365
_ASKED_DAY_COUNT_RE = re.compile(r"\b([1-9]\d{0,2})\s*(?:ngay|days?)\b", re.IGNORECASE)
_CLOCK_RANGE_RE = re.compile(
    r"(?:(?:tu|from)\s+)?(?:luc\s+)?"
    r"(?<![0-9/.])(\d{1,2})(?:[:h\.](\d{2}))?\s*(?:gio|tieng|h(?!\w)|hours?|hrs?)?\s*"
    r"(sang|chieu|am|pm)?"
    r"\s*(?:-|–|—|~|den|toi|to|until)\s*"
    r"(?:luc\s+)?"
    r"(?<![0-9/.])(\d{1,2})(?:[:h\.](\d{2}))?\s*(?:gio|tieng|h(?!\w)|hours?|hrs?)?\s*"
    r"(sang|chieu|toi|am|pm)?",
    re.IGNORECASE,
)
_HOUR_SPAN_RE = re.compile(
    r"\b(\d{1,2}(?:[.,]\d+)?)\s*(?:gio(?:\s+dong\s+ho)?|tieng|hours?|hrs?)\b",
    re.IGNORECASE,
)
_HOUR_COMPACT_RE = re.compile(r"\b(\d{1,2})h\b", re.IGNORECASE)
_HOUR_WORD = {
    "mot gio": 1,
    "hai gio": 2,
    "ba gio": 3,
    "bon gio": 4,
    "nam gio": 5,
    "sau gio": 6,
    "one hour": 1,
    "two hours": 2,
    "three hours": 3,
    "four hours": 4,
}
_DATE_RANGE_RE = re.compile(
    r"(?:(?:tu|from)\s+)?(?:ngay\s+)?"
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?/?\s*"
    r"(?:-|–|—|den|toi|to|until)\s*"
    r"(?:ngay\s+)?"
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?",
    re.IGNORECASE,
)
_DAY_RANGE_RE = re.compile(
    r"(?:tu|from)\s+ngay\s+(\d{1,2})\s+(?:den|toi|to)\s+ngay\s+(\d{1,2})",
    re.IGNORECASE,
)


class TripTiming(NamedTuple):
    start_hour: int
    start_minute: int
    max_minutes: int
    days: int
    start_date: date | None
    clock_label: str | None
    date_label: str | None
    asked_days: int


def _parse_asked_day_count(folded: str) -> int | None:
    match = _ASKED_DAY_COUNT_RE.search(folded)
    if not match:
        return None
    return min(MAX_ASKED_DAYS, max(1, int(match.group(1))))


def _vnd_brief(amount: int, locale: str) -> str:
    if amount >= 1_000_000 and amount % 1_000_000 == 0:
        trieu = amount // 1_000_000
        return f"{trieu} triệu" if locale == "vi" else f"{trieu} million VND"
    if locale == "vi":
        return f"{amount:,}đ".replace(",", ".")
    return f"{amount:,} VND"


def _overflow_leg_copy(
    request: PlanRequest,
    asked_days: int,
    planned_days: int,
    destination_label: str,
) -> dict[str, str] | None:
    if asked_days <= planned_days:
        return None
    dest = destination_label if destination_label and destination_label not in {"Việt Nam", "Vietnam"} else (
        "chặng này" if request.ngon_ngu == "vi" else "this destination"
    )
    folded = " ".join(_ascii_fold(request.context).split())
    healing = (
        "chua lanh" in folded
        or "healing" in folded
        or str(_policy_get(request.intent_policy, "primary_intent") or "") == "healing"
    )
    stated_budget = budget_applies(request)
    first_budget = max(50_000, round(request.ngan_sach * planned_days / asked_days)) if asked_days else request.ngan_sach
    if request.ngon_ngu == "vi":
        pace = "theo phong cách chữa lành bền vững" if healing else "theo nhịp bền vững, không nhồi nhét"
        note = (
            f'Úi, có vẻ như kế hoạch {asked_days} ngày của chúng mình hơi "khủng" so với hệ thống rồi '
            f"(giới hạn hiện tại là {MAX_TRIP_DAYS} ngày cho mỗi chặng)! Nhưng không sao, mình vẫn xếp {pace} nhé."
        )
        budget_bit = (
            f" Với ngân sách {_vnd_brief(request.ngan_sach, 'vi')} cho {asked_days} ngày "
            f"(khoảng {_vnd_brief(first_budget, 'vi')} cho chặng đầu), lịch được chia đều để đi thoải mái."
            if stated_budget
            else " Lịch được chia đều để đi thoải mái chứ không nhồi hết vào vài ngày đầu."
        )
        summary = f"Mình đã tạo lịch {planned_days} ngày đầu tiên tại {dest} để bạn xem trước.{budget_bit}"
    else:
        pace = "in a slower, more sustainable rhythm" if healing else "at a sustainable pace, without cramming"
        note = (
            f"Whoa — a {asked_days}-day plan is a bit huge for the system right now "
            f"(the current limit is {MAX_TRIP_DAYS} days per leg). No worries, we'll still plan {pace}."
        )
        budget_bit = (
            f" With a budget of {_vnd_brief(request.ngan_sach, 'en')} for {asked_days} days "
            f"(about {_vnd_brief(first_budget, 'en')} for this first leg), the days are paced so you can actually enjoy them."
            if stated_budget
            else " The days are paced evenly so the first week is not overloaded."
        )
        summary = f"I've built the first {planned_days} days in {dest} for you to preview.{budget_bit}"
    return {"note": note, "summary": summary, "greeting": f"{note}\n\n{summary}"}


def _hour_with_meridiem(hour: int, meridiem: str | None) -> int:
    if not meridiem:
        return hour
    key = meridiem.lower()
    if key in {"pm", "chieu"} and hour < 12:
        return hour + 12
    if key in {"am", "sang"} and hour == 12:
        return 0
    return hour


def _clock_minutes(start_h: int, start_m: int, end_h: int, end_m: int) -> int | None:
    if not (0 <= start_h <= 23 and 0 <= end_h <= 23 and 0 <= start_m < 60 and 0 <= end_m < 60):
        return None
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if end <= start:
        end += 24 * 60
    span = end - start
    if span < 45 or span > 16 * 60:
        return None
    return span


def _parse_year(raw: str | None, today: date) -> int:
    if not raw:
        return today.year
    year = int(raw)
    if year < 100:
        year += 2000
    return year


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


_WEEKDAY_NAMES_VI = {
    "hai": 0,
    "ba": 1,
    "tu": 2,
    "nam": 3,
    "sau": 4,
    "bay": 5,
    "nhat": 6,
}
_WEEKDAY_LABELS_VI = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")
_WEEKDAY_LABELS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _date_label(d: date, locale: str) -> str:
    return f"{d.day}/{d.month}"


def _relative_trip_date(folded: str, today: date, locale: str) -> tuple[date, str] | None:
    """Trả về (ngày bắt đầu, nhãn) cho mốc thời gian tương đối; None nếu không nhận diện được.

    Chỉ nhận diện cụm không mập mờ: hôm nay, ngày mai, ngày mốt, thứ N (+ tuần sau/này),
    cuối tuần sau, tuần sau, tháng N. Không chạm cụm "cuối tuần" trần vì thường là motif
    (cuối tuần chill) chứ không phải ngày đi cụ thể.
    """
    if re.search(r"\bhom nay\b", folded):
        return today, ("Hôm nay" if locale == "vi" else "Today")
    if re.search(r"\bngay mot\b", folded):
        target = today + timedelta(days=2)
        return target, _date_label(target, locale)
    if re.search(r"\b(?:ngay )?mai\b", folded):
        target = today + timedelta(days=1)
        return target, _date_label(target, locale)

    weekday_match = re.search(
        r"\b(?:thu (hai|ba|tu|nam|sau|bay)|chu nhat)\b(?:\s+(tuan sau|tuan toi|sang tuan|tuan nay))?",
        folded,
    )
    if weekday_match:
        name = weekday_match.group(1) or "nhat"
        weekday = _WEEKDAY_NAMES_VI[name]
        qualifier = weekday_match.group(2)
        base = (weekday - today.weekday()) % 7
        if qualifier in {"tuan sau", "tuan toi", "sang tuan"}:
            delta = base + 7
        else:
            delta = base if base > 0 else 7
        target = today + timedelta(days=delta)
        if locale == "vi":
            label = _WEEKDAY_LABELS_VI[target.weekday()]
        else:
            label = _WEEKDAY_LABELS_EN[target.weekday()]
        return target, label

    if re.search(r"\bcuoi tuan sau\b", folded):
        delta = (5 - today.weekday()) % 7 + 7
        target = today + timedelta(days=delta)
        return target, ("Thứ 7" if locale == "vi" else "Saturday")

    if re.search(r"\btuan sau\b", folded):
        delta = (7 - today.weekday()) % 7 or 7
        target = today + timedelta(days=delta)
        return target, _date_label(target, locale)

    month_match = re.search(r"\bthang\s+(\d{1,2})\b", folded)
    if month_match:
        month = int(month_match.group(1))
        if 1 <= month <= 12:
            year = today.year
            if month < today.month or (month == today.month and today.day > 1):
                year += 1
            target = _safe_date(year, month, 1)
            if target:
                label = f"tháng {month}" if locale == "vi" else _MONTH_LABELS_EN[month]
                return target, label
    return None


def _policy_get(policy: object, key: str):
    if isinstance(policy, dict):
        return policy.get(key)
    return getattr(policy, key, None)


def _structured_time_window(policy: object) -> dict | None:
    window = _policy_get(policy, "time_window") if policy else None
    if not window:
        return None
    if not isinstance(window, dict):
        window = window.model_dump() if hasattr(window, "model_dump") else None
    return window if isinstance(window, dict) else None


def _trip_timing(request: PlanRequest, today: date | None = None) -> TripTiming:
    today = today or datetime.now(UTC).date()
    _, default_minutes, default_days = LIMITS[request.thoi_luong]
    folded = " ".join(_ascii_fold(request.context).split())
    start_hour, start_minute = 8, 0
    max_minutes = default_minutes
    days = default_days if request.thoi_luong == "nhieu_ngay" else 1
    start_date = request.ngay_di
    clock_label = None
    date_label = None
    policy = request.intent_policy
    structured_duration_minutes = int(_policy_get(policy, "duration_minutes") or 0) if policy else 0
    structured_duration_days = int(_policy_get(policy, "duration_days") or 0) if policy else 0
    structured_window = _structured_time_window(policy)
    text_intent = rule_structured_intent(request.context)
    if not structured_duration_days and text_intent.get("duration_days"):
        structured_duration_days = int(text_intent["duration_days"])
    if not structured_duration_minutes and text_intent.get("duration_minutes"):
        structured_duration_minutes = int(text_intent["duration_minutes"])
    if not structured_window and isinstance(text_intent.get("time_window"), dict):
        structured_window = text_intent["time_window"]

    if structured_duration_minutes:
        max_minutes = max(45, min(structured_duration_minutes, 16 * 60))
        hours = max_minutes / 60
        clock_label = f"{hours:g} giờ" if request.ngon_ngu == "vi" else f"{hours:g} hours"
    if structured_duration_days:
        days = min(MAX_TRIP_DAYS, max(1, structured_duration_days))
        # Multi-day requests keep a clock window only when this same sentence also has hours.
        if days >= 2 and structured_window and not text_intent.get("time_window"):
            structured_window = None
            if structured_duration_minutes and structured_duration_minutes <= 8 * 60:
                structured_duration_minutes = 0
    if structured_window:
        span = int(structured_window.get("minutes") or 0)
        start_h = int(structured_window.get("start_hour") or 0)
        start_m = int(structured_window.get("start_minute") or 0)
        if 45 <= span <= 16 * 60 and 0 <= start_h <= 23 and 0 <= start_m < 60:
            start_hour = start_h
            start_minute = start_m
            max_minutes = span
            clock_label = structured_window.get("label") or f"{start_hour}h"

    hour_span = None if structured_duration_minutes or structured_window else _HOUR_SPAN_RE.search(folded)
    compact_hour = None if hour_span or structured_duration_minutes or structured_window else _HOUR_COMPACT_RE.search(folded)
    if hour_span:
        hours = float(hour_span.group(1).replace(",", "."))
        if 0.75 <= hours <= 12:
            max_minutes = max(90, min(int(hours * 60), 12 * 60))
            clock_label = f"{int(hours)} giờ" if request.ngon_ngu == "vi" else f"{int(hours)} hours"
    elif compact_hour:
        hours = int(compact_hour.group(1))
        if 1 <= hours <= 12:
            max_minutes = hours * 60
            clock_label = f"{hours} giờ" if request.ngon_ngu == "vi" else f"{hours} hours"
    elif not structured_duration_minutes and not structured_window:
        for phrase, hours in _HOUR_WORD.items():
            if phrase in folded:
                max_minutes = hours * 60
                clock_label = f"{hours} giờ" if request.ngon_ngu == "vi" else f"{hours} hours"
                break

    dated_preview = _DATE_RANGE_RE.search(folded)
    clock = None if structured_window else _CLOCK_RANGE_RE.search(folded)
    if clock and dated_preview and not re.search(r"(?:[:h]|gio|tieng)", clock.group(0), re.I):
        clock = None
    if clock:
        start_h = _hour_with_meridiem(int(clock.group(1)), clock.group(3))
        end_h = _hour_with_meridiem(int(clock.group(4)), clock.group(6))
        span = _clock_minutes(start_h, int(clock.group(2) or 0), end_h, int(clock.group(5) or 0))
        if span:
            start_hour = start_h
            start_minute = int(clock.group(2) or 0)
            max_minutes = span
            clock_label = f"{start_hour}h–{end_h}h"

    night_shift = None if structured_window else re.search(r"\b(\d{1,2})\s*(?:h|gio|tieng)?\s*(?:dem|toi|pm)\s*(?:den|-|toi)\s*(\d{1,2})\s*(?:h|gio|tieng)?\s*(?:dem|toi|pm|sang|am)?\b", folded)
    if night_shift and not clock:
        start_raw = int(night_shift.group(1))
        end_raw = int(night_shift.group(2))
        s_h = start_raw if start_raw >= 12 else start_raw + 12
        e_h = end_raw if end_raw >= 12 else (end_raw if "sang" in night_shift.group(0) or "am" in night_shift.group(0) else end_raw + 12)
        span_min = (e_h * 60 - s_h * 60) if e_h > s_h else (e_h * 60 + 24 * 60 - s_h * 60)
        if 45 <= span_min <= 12 * 60:
            start_hour = s_h % 24
            max_minutes = span_min
            clock_label = f"{start_hour}h–{e_h % 24}h"

    dated = _DATE_RANGE_RE.search(folded)
    if dated:
        year1 = _parse_year(dated.group(3), today)
        year2 = _parse_year(dated.group(6), today) if dated.group(6) else year1
        left = _safe_date(year1, int(dated.group(2)), int(dated.group(1)))
        right = _safe_date(year2, int(dated.group(5)), int(dated.group(4)))
        if left and right:
            if right < left:
                right = _safe_date(year2 + 1, int(dated.group(5)), int(dated.group(4))) or right
            if left < today - timedelta(days=2) and left.year == today.year and not request.ngay_di:
                left = _safe_date(left.year + 1, left.month, left.day) or left
                right = _safe_date(right.year + 1, right.month, right.day) or right
            span_days = (right - left).days + 1
            if 1 <= span_days <= MAX_TRIP_DAYS:
                if not structured_duration_days:
                    days = span_days
                start_date = request.ngay_di or left
                date_label = f"{left.day}/{left.month}–{right.day}/{right.month}"
    else:
        month_days = None if structured_duration_days else _DAY_RANGE_RE.search(folded)
        if month_days:
            start_day = int(month_days.group(1))
            end_day = int(month_days.group(2))
            left = _safe_date(today.year, today.month, start_day)
            right = _safe_date(today.year, today.month, end_day)
            if left and right:
                if right < left:
                    month = 1 if today.month == 12 else today.month + 1
                    year = today.year + 1 if today.month == 12 else today.year
                    right = _safe_date(year, month, end_day)
                if left < today - timedelta(days=2) and not request.ngay_di:
                    next_month = 1 if today.month == 12 else today.month + 1
                    next_year = today.year + 1 if today.month == 12 else today.year
                    left = _safe_date(next_year, next_month, start_day) or left
                    right = _safe_date(next_year, next_month, end_day) or right
                    if right and left and right < left:
                        follow_month = 1 if next_month == 12 else next_month + 1
                        follow_year = next_year + 1 if next_month == 12 else next_year
                        right = _safe_date(follow_year, follow_month, end_day) or right
                span_days = (right - left).days + 1 if left and right else 0
                if 1 <= span_days <= MAX_TRIP_DAYS:
                    days = span_days
                    start_date = request.ngay_di or left
                    date_label = f"{span_days} ngày"

    labeled_days = None if date_label else _parse_asked_day_count(folded)
    if labeled_days and not date_label:
        days = min(MAX_TRIP_DAYS, labeled_days)

    if start_date is None and not date_label:
        relative = _relative_trip_date(folded, today, request.ngon_ngu)
        if relative:
            start_date, date_label = relative

    if days >= 2:
        pass
    elif request.thoi_luong != "nhieu_ngay" and not date_label and not structured_duration_days:
        days = 1
    asked_days = max(days, labeled_days or 0, structured_duration_days or 0)
    if asked_days > MAX_TRIP_DAYS:
        days = MAX_TRIP_DAYS
    return TripTiming(start_hour, start_minute, max_minutes, days, start_date, clock_label, date_label, asked_days)


def _chunk_sights_by_day(sights: list[Place], days: int) -> list[list[Place]]:
    """Cluster sights geographically per day, then even out so long trips are not front-loaded."""
    if days <= 1:
        return [sights]
    if not sights:
        return [[] for _ in range(days)]
    if len(sights) <= days:
        return [[p] for p in sights] + [[] for _ in range(days - len(sights))]

    seeds = [sights[0]]
    for _ in range(1, days):
        farthest_place = max(
            sights,
            key=lambda p: min(haversine_km(p.lat, p.lng, s.lat, s.lng) for s in seeds),
        )
        seeds.append(farthest_place)

    day_clusters: list[list[Place]] = [[] for _ in range(days)]
    for place in sights:
        nearest_idx = min(
            range(days),
            key=lambda idx: haversine_km(place.lat, place.lng, seeds[idx].lat, seeds[idx].lng),
        )
        day_clusters[nearest_idx].append(place)

    while any(not cluster for cluster in day_clusters):
        empty = next(index for index, cluster in enumerate(day_clusters) if not cluster)
        richest = max(range(days), key=lambda index: len(day_clusters[index]))
        if len(day_clusters[richest]) <= 1:
            break
        day_clusters[empty].append(day_clusters[richest].pop())

    cap = max(1, (len(sights) + days - 1) // days)
    for _ in range(len(sights)):
        heavy_idx = max(range(days), key=lambda index: len(day_clusters[index]))
        if len(day_clusters[heavy_idx]) <= cap:
            break
        light_idx = min(range(days), key=lambda index: (len(day_clusters[index]), index))
        if light_idx == heavy_idx or len(day_clusters[light_idx]) >= cap:
            break
        heavy = day_clusters[heavy_idx]
        light = day_clusters[light_idx]
        if light:
            dest_lat = sum(place.lat for place in light) / len(light)
            dest_lng = sum(place.lng for place in light) / len(light)
            mover = min(heavy, key=lambda place: haversine_km(place.lat, place.lng, dest_lat, dest_lng))
        else:
            mover = heavy[-1]
        heavy.remove(mover)
        light.append(mover)
    return day_clusters


DINING_KINDS = frozenset({"nha_hang", "quan_an"})
SIGHT_KINDS = frozenset({"dia_danh", "bao_tang", "cong_vien", "cho", "di_tich", "bai_bien", "hang_dong", "nui", "den_chua", "giai_tri"})
# (start_hour, start_min, end_hour, end_min) — khung giờ ăn / nghỉ mục tiêu
MEAL_WINDOWS: dict[str, tuple[int, int, int, int]] = {
    "sang": (7, 30, 9, 30),
    "trua": (11, 30, 13, 30),
    "nghi": (12, 30, 14, 30),
    "toi": (18, 0, 21, 0),
    "dem": (19, 0, 22, 30),
}
MEAL_DURATION = {"sang": 45, "trua": 60, "nghi": 50, "toi": 75, "dem": 75}
MEAL_PREFERRED_START = {
    "sang": (7, 45),
    "trua": (11, 30),
    "nghi": (13, 0),
    "toi": (18, 30),
    "dem": (19, 30),
}
MAX_IDLE_MINUTES = 35
MIN_VISIT_MINUTES = 25
MAX_GAP_BEFORE_FILL_MINUTES = 55
DESTINATION_RADIUS_KM = 45.0
DURATION_FALLBACKS: dict[str, tuple[int, int]] = {
    "bao_tang": (90, 180),
    "dia_danh": (45, 120),
    "cong_vien": (45, 120),
    "cho": (45, 90),
    "cafe": (45, 90),
    "nha_hang": (60, 90),
    "quan_an": (45, 75),
    "nui": (180, 360),
    "hang_dong": (90, 180),
    "den_chua": (60, 180),
}
_MOUNTAIN_DESTINATION_KEYS = {
    "yen tu",
    "chua huong",
    "sa pa",
    "ha giang",
    "tam dao",
    "bach ma",
    "nui chua",
}
_MOUNTAIN_COMPLEX_HINTS = (
    "yen tu",
    "chua huong",
    "fansipan",
    "langbiang",
    "ba na",
    "tam dao",
    "bach ma",
    "bao ton",
    "vuon quoc gia",
    "thien nhien",
    "nui chua",
)
_MOUNTAIN_TRANSIT_HINTS = ("cap treo", "cable car", "ga cap")
DATA_STALENESS_POLICY = {
    "gio_mo_cua": {"max_age_days": 30, "refresh": "kiem_tra_lai truoc khi xep lich"},
    "gia": {"max_age_days": 90, "refresh": "lam moi khi dia diem duoc goi trong lich"},
    "trang_thai_hoat_dong": {"max_age_days": 7, "refresh": "chan neu co dau hieu dong cua"},
    "thoi_luong": {"max_age_days": 180, "refresh": "hieu chinh bang phan hoi giu bo va thuc dia"},
    "di_chuyen": {"max_age_days": 30, "refresh": "ban thu nghiem dung duong thang co bu sai so"},
}
GENERIC_DESTINATION_NAMES = {
    "du lich",
    "tham quan",
    "di choi",
    "check in",
    "checkin",
}
_WEAK_STRIPPED_DESTINATION_ALIASES = {
    "chua",
    "nui",
    "den",
    "vinh",
    "dao",
    "bien",
    "ho",
    "song",
    "cau",
    "cho",
    "park",
    "peak",
    "temple",
    "pagoda",
}
DESTINATION_NAME_PREFIXES = (
    "quan the di tich danh thang ",
    "quan the danh thang ",
    "khu du lich ",
    "thien vien ",
    "chua dong ",
    "pho co ",
    "chua ",
    "nui ",
    "den ",
    "vinh ",
    "tp ",
    "thanh pho ",
    "dao ",
    "bien ",
)

FOCUS_DESTINATIONS: dict[str, dict[str, object]] = {
    "ha_noi": {
        "label": "Hà Nội",
        "lat": 21.0285,
        "lng": 105.8542,
        "aliases": {"ha noi", "hanoi", "thu do"},
    },
    "tp_hcm": {
        "label": "TP.HCM",
        "lat": 10.7769,
        "lng": 106.7009,
        "aliases": {"tp hcm", "tp.hcm", "ho chi minh", "sai gon", "saigon", "thanh pho ho chi minh"},
    },
    "da_nang": {
        "label": "Đà Nẵng",
        "lat": 16.0544,
        "lng": 108.2022,
        "aliases": {"da nang", "danang", "thanh pho da nang"},
    },
    "hoi_an": {
        "label": "Hội An",
        "lat": 15.8801,
        "lng": 108.3380,
        "aliases": {"hoi an", "pho co hoi an", "quang nam"},
    },
    "hue": {
        "label": "Huế",
        "lat": 16.4637,
        "lng": 107.5909,
        "aliases": {"hue", "thua thien hue", "co do hue", "tp hue"},
    },
    "da_lat": {
        "label": "Đà Lạt",
        "lat": 11.9404,
        "lng": 108.4583,
        "aliases": {"da lat", "dalat", "lam dong", "thanh pho ngan hoa"},
    },
    "nha_trang": {
        "label": "Nha Trang",
        "lat": 12.2388,
        "lng": 109.1967,
        "aliases": {"nha trang", "khanh hoa", "tp nha trang"},
    },
    "ninh_binh": {
        "label": "Ninh Bình",
        "lat": 20.2506,
        "lng": 105.9745,
        "aliases": {"ninh binh", "trang an", "bai dinh", "tam coc", "hoa lu"},
    },
    "ha_long": {
        "label": "Hạ Long",
        "lat": 20.9712,
        "lng": 107.0448,
        "aliases": {"ha long", "vinh ha long"},
    },
    "yen_tu": {
        "label": "Yên Tử",
        "lat": 21.1506,
        "lng": 106.7189,
        "landmark": True,
        "aliases": {"yen tu", "nui yen tu", "chua yen tu", "thien vien yen tu", "danh thang yen tu"},
    },
    "cat_ba": {
        "label": "Cát Bà",
        "lat": 20.7278,
        "lng": 107.0482,
        "landmark": True,
        "radius_km": 13.0,
        "aliases": {"cat ba", "dao cat ba", "vinh lan ha", "lan ha"},
    },
    "sa_pa": {
        "label": "Sa Pa",
        "lat": 22.3364,
        "lng": 103.8438,
        "aliases": {"sa pa", "sapa", "lao cai", "fansipan"},
    },
    "phu_quoc": {
        "label": "Phú Quốc",
        "lat": 10.2899,
        "lng": 103.9840,
        "aliases": {"phu quoc", "dao phu quoc", "kien giang"},
    },
    "can_tho": {
        "label": "Cần Thơ",
        "lat": 10.0452,
        "lng": 105.7469,
        "aliases": {"can tho", "tay do", "tp can tho", "ninh kieu"},
    },
    "vung_tau": {
        "label": "Vũng Tàu",
        "lat": 10.3460,
        "lng": 107.0843,
        "aliases": {"vung tau", "ba ria vung tau", "tp vung tau"},
    },
    "quy_nhon": {
        "label": "Quy Nhơn",
        "lat": 13.7820,
        "lng": 109.2197,
        "aliases": {"quy nhon", "binh dinh", "tp quy nhon", "eo gio", "ky co"},
    },
    "phan_thiet": {
        "label": "Phan Thiết",
        "lat": 10.9273,
        "lng": 108.1021,
        "aliases": {"phan thiet", "mui ne", "binh thuan"},
    },
    "quang_binh": {
        "label": "Quảng Bình",
        "lat": 17.4764,
        "lng": 106.6022,
        "aliases": {"quang binh", "dong hoi", "phong nha", "phong nha ke bang"},
    },
    "ha_giang": {
        "label": "Hà Giang",
        "lat": 22.8233,
        "lng": 104.9839,
        "aliases": {"ha giang", "dong van", "ma pi leng", "meo vac"},
    },
    "hai_phong": {
        "label": "Hải Phòng",
        "lat": 20.8449,
        "lng": 106.6881,
        "aliases": {"hai phong", "do son", "dat cang"},
    },
}

VIETNAM_TRAFFIC_PEAK_POLICY = {
    "nguon": "quy_tac_noi_bo_gio_cao_diem_do_thi_viet_nam",
    "trang_thai": "heuristic_no_live_traffic",
    "khung_gio": [
        {"ten": "cao_diem_sang", "tu": "07:00", "den": "09:00"},
        {"ten": "cao_diem_chieu", "tu": "16:30", "den": "19:00"},
    ],
    "ghi_chu": "Dùng để ghi/né rủi ro giờ cao điểm khi chưa có provider traffic thật; không thay thế dữ liệu giao thông production.",
}

SEASONAL_TOURISM_POLICY: dict[str, dict[str, object]] = {
    "ha_noi": {
        "best_months": (3, 4, 10, 11),
        "caution_months": (6, 7, 8, 12, 1, 2),
        "festival_notes": ("Tết Nguyên đán", "2/9", "mùa thu Hà Nội"),
    },
    "tp_hcm": {
        "best_months": (12, 1, 2, 3, 4),
        "caution_months": (5, 6, 7, 8, 9, 10),
        "festival_notes": ("Tết Nguyên đán", "30/4-1/5", "lễ hội cuối năm"),
    },
    "ha_long": {
        "best_months": (3, 4, 10, 11),
        "caution_months": (6, 7, 8, 9),
        "festival_notes": ("mùa hè du lịch biển", "lễ hội Hạ Long"),
    },
    "da_nang": {
        "best_months": (3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11, 12),
        "festival_notes": ("mùa biển", "lễ hội pháo hoa quốc tế Đà Nẵng"),
    },
    "hoi_an": {
        "best_months": (2, 3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11),
        "festival_notes": ("đêm phố cổ", "rằm âm lịch"),
    },
    "nha_trang": {
        "best_months": (2, 3, 4, 5, 6, 7, 8),
        "caution_months": (10, 11, 12),
        "festival_notes": ("mùa biển", "Festival Biển Nha Trang"),
    },
    "phu_quoc": {
        "best_months": (11, 12, 1, 2, 3, 4),
        "caution_months": (6, 7, 8, 9, 10),
        "festival_notes": ("mùa biển khô", "cao điểm cuối năm"),
    },
    "sa_pa": {
        "best_months": (3, 4, 5, 9, 10, 11),
        "caution_months": (12, 1, 2, 6, 7, 8),
        "festival_notes": ("mùa lúa chín", "mùa săn mây"),
    },
    "hue": {
        "best_months": (1, 2, 3, 4),
        "caution_months": (9, 10, 11, 12),
        "festival_notes": ("Festival Huế", "du lịch di sản Cố đô"),
    },
    "da_lat": {
        "best_months": (11, 12, 1, 2, 3, 4),
        "caution_months": (6, 7, 8, 9),
        "festival_notes": ("Festival Hoa Đà Lạt", "mùa săn mây, dã quỳ"),
    },
    "ninh_binh": {
        "best_months": (1, 2, 3, 5, 6),
        "caution_months": (7, 8, 9),
        "festival_notes": ("Lễ hội Tràng An", "mùa lúa chín Tam Cốc"),
    },
    "can_tho": {
        "best_months": (12, 1, 2, 3, 4),
        "caution_months": (8, 9, 10),
        "festival_notes": ("Lễ hội Bánh dân gian Nam Bộ", "mùa trái cây miệt vườn"),
    },
    "vung_tau": {
        "best_months": (11, 12, 1, 2, 3, 4),
        "caution_months": (7, 8, 9),
        "festival_notes": ("Lễ hội Nghinh Ông", "du lịch biển cuối tuần"),
    },
    "quy_nhon": {
        "best_months": (3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11, 12),
        "festival_notes": ("mùa biển Eo Gió - Kỳ Co", "lễ hội võ cổ truyền"),
    },
    "phan_thiet": {
        "best_months": (11, 12, 1, 2, 3, 4, 5),
        "caution_months": (7, 8),
        "festival_notes": ("Lễ hội Kate", "lướt ván buồm Mũi Né"),
    },
    "quang_binh": {
        "best_months": (3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11, 12),
        "festival_notes": ("mùa khám phá hang động Phong Nha", "du lịch biển Nhật Lệ"),
    },
    "ha_giang": {
        "best_months": (9, 10, 11, 12, 1, 2),
        "caution_months": (6, 7, 8),
        "festival_notes": ("Lễ hội hoa Tam giác mạch", "mùa lúa chín Hoàng Su Phì"),
    },
    "hai_phong": {
        "best_months": (4, 5, 6, 7, 8, 9),
        "caution_months": (12, 1, 2),
        "festival_notes": ("Lễ hội Hoa Phượng Đỏ", "mùa biển Đồ Sơn"),
    },
    "cat_ba": {
        "best_months": (4, 5, 6, 7, 8, 9),
        "caution_months": (12, 1, 2),
        "festival_notes": ("mùa biển Cát Bà", "Vịnh Lan Hạ"),
    },
}

EVENING_PLACE_IDS = (
    "osm-node-4489385889",
    "osm-relation-7112202",
    "osm-way-765597030",
)
EVENING_FALLBACK_IDS = (
    "curated-ho-guom",
    "curated-pho-co-ha-noi",
    "curated-cho-dem-dong-xuan",
    "curated-pho-ta-hien",
    "curated-hang-dao",
    "curated-pho-di-bo-cat-ba",
    "curated-thi-tran-cat-ba",
    "curated-lang-chai-cai-beo",
    "curated-bai-chay",
    "curated-pho-co-hoi-an",
    "curated-cau-rong",
    "curated-my-khe",
    "curated-pho-di-bo-nguyen-hue",
    "curated-song-huong",
    "curated-sunset-sanato",
    "curated-nha-tho-da-sapa",
    "curated-ho-xuan-huong",
)

# Official / practical hours when OSM catalogue is wrong or too broad.
KNOWN_HOURS_BY_NAME: dict[str, tuple[int, int]] = {
    "lang chu tich ho chi minh": (7, 11),
}

MEAL_LABELS: dict[str, dict[str, str]] = {
    "vi": {"sang": "Bữa sáng", "trua": "Bữa trưa", "nghi": "Nghỉ trưa", "toi": "Bữa tối", "dem": "Buổi tối"},
    "en": {"sang": "Breakfast", "trua": "Lunch", "nghi": "Midday break", "toi": "Dinner", "dem": "Evening"},
    "ar": {"sang": "فطور", "trua": "غداء", "nghi": "استراحة ظهيرة", "toi": "عشاء", "dem": "مساء"},
    "bg": {"sang": "Закуска", "trua": "Обяд", "nghi": "Обедна почивка", "toi": "Вечеря", "dem": "Вечер"},
    "de": {"sang": "Frühstück", "trua": "Mittagessen", "nghi": "Mittagsruhe", "toi": "Abendessen", "dem": "Abendprogramm"},
    "es": {"sang": "Desayuno", "trua": "Almuerzo", "nghi": "Descanso del mediodía", "toi": "Cena", "dem": "Noche"},
    "fr": {"sang": "Petit-déjeuner", "trua": "Déjeuner", "nghi": "Pause de midi", "toi": "Dîner", "dem": "Soirée"},
    "he": {"sang": "ארוחת בוקר", "trua": "ארוחת צהריים", "nghi": "הפסקת צהריים", "toi": "ארוחת ערב", "dem": "ערב"},
    "hi": {"sang": "नाश्ता", "trua": "दोपहर का भोजन", "nghi": "दोपहर का विश्राम", "toi": "रात का खाना", "dem": "शाम"},
    "it": {"sang": "Colazione", "trua": "Pranzo", "nghi": "Pausa pranzo", "toi": "Cena", "dem": "Serata"},
    "ja": {"sang": "朝食", "trua": "昼食", "nghi": "昼休み", "toi": "夕食", "dem": "夜の予定"},
    "nl": {"sang": "Ontbijt", "trua": "Lunch", "nghi": "Middagpauze", "toi": "Diner", "dem": "Avond"},
    "pl": {"sang": "Śniadanie", "trua": "Obiad", "nghi": "Przerwa południowa", "toi": "Kolacja", "dem": "Wieczór"},
    "pt": {"sang": "Pequeno-almoço", "trua": "Almoço", "nghi": "Pausa do meio-dia", "toi": "Jantar", "dem": "Noite"},
    "ru": {"sang": "Завтрак", "trua": "Обед", "nghi": "Дневной отдых", "toi": "Ужин", "dem": "Вечер"},
    "tr": {"sang": "Kahvaltı", "trua": "Öğle yemeği", "nghi": "Öğle molası", "toi": "Akşam yemeği", "dem": "Akşam"},
    "zh": {"sang": "早餐", "trua": "午餐", "nghi": "午休", "toi": "晚餐", "dem": "晚间"},
    "ko": {"sang": "아침", "trua": "점심", "nghi": "낮 휴식", "toi": "저녁", "dem": "저녁 일정"},
    "th": {"sang": "มื้อเช้า", "trua": "มื้อกลางวัน", "nghi": "พักเที่ยง", "toi": "มื้อเย็น", "dem": "ช่วงเย็น"},
}

AI_FALLBACK_NOTE = {
    "vi": "AI tạm thời không khả dụng; lịch trình đang dùng bộ xếp lịch an toàn từ dữ liệu đã kiểm chứng.",
    "en": "AI is temporarily unavailable; this itinerary uses the safe deterministic planner with verified data.",
}

COPY = {
    "vi": ("Chưa tải dự báo trực tuyến", "Dự báo có thể thay đổi", "Open-Meteo tạm thời không khả dụng", "Trải nghiệm {place} tại {area}.", "Kiểm tra giờ mở cửa trước khi đi.", "Ngày {day}", "Một lịch trình tối ưu cho {people} người.", "Chi phí ước tính, có thể chênh lệch", "Mang theo nước và kiểm tra thời tiết"),
    "en": ("Live forecast not loaded", "Forecasts may change", "Open-Meteo is temporarily unavailable", "Experience {place} in {area}.", "Check opening hours before visiting.", "Day {day}", "An optimized itinerary for {people} people.", "Estimated costs may vary", "Bring water and check the weather"),
    "ar": ("لم يتم تحميل التوقعات المباشرة", "قد تتغير التوقعات", "Open-Meteo غير متاح مؤقتًا", "استمتع بتجربة {place} في {area}.", "تحقق من ساعات العمل قبل الزيارة.", "اليوم {day}", "برنامج رحلة محسّن لـ {people} أشخاص.", "قد تختلف التكاليف التقديرية", "أحضر الماء وتحقق من الطقس"),
    "bg": ("Прогнозата на живо не е заредена", "Прогнозата може да се промени", "Open-Meteo временно не е достъпен", "Посетете {place} в {area}.", "Проверете работното време преди посещение.", "Ден {day}", "Оптимизиран маршрут за {people} души.", "Прогнозните разходи може да варират", "Носете вода и проверете времето"),
    "de": ("Live-Vorhersage nicht geladen", "Vorhersagen können sich ändern", "Open-Meteo ist vorübergehend nicht verfügbar", "Erleben Sie {place} in {area}.", "Prüfen Sie vor dem Besuch die Öffnungszeiten.", "Tag {day}", "Eine optimierte Reiseroute für {people} Personen.", "Geschätzte Kosten können abweichen", "Nehmen Sie Wasser mit und prüfen Sie das Wetter"),
    "es": ("Pronóstico en vivo no cargado", "El pronóstico puede cambiar", "Open-Meteo no está disponible temporalmente", "Disfruta de {place} en {area}.", "Consulta el horario antes de ir.", "Día {day}", "Un itinerario optimizado para {people} personas.", "Los costes estimados pueden variar", "Lleva agua y consulta el tiempo"),
    "fr": ("Prévisions en direct non chargées", "Les prévisions peuvent changer", "Open-Meteo est temporairement indisponible", "Découvrez {place} à {area}.", "Vérifiez les horaires avant la visite.", "Jour {day}", "Un itinéraire optimisé pour {people} personnes.", "Les coûts estimés peuvent varier", "Emportez de l’eau et vérifiez la météo"),
    "he": ("התחזית החיה לא נטענה", "התחזית עשויה להשתנות", "Open-Meteo אינו זמין זמנית", "חוו את {place} ב-{area}.", "בדקו את שעות הפתיחה לפני הביקור.", "יום {day}", "מסלול מיטבי עבור {people} אנשים.", "העלויות המשוערות עשויות להשתנות", "הביאו מים ובדקו את מזג האוויר"),
    "hi": ("लाइव मौसम पूर्वानुमान लोड नहीं हुआ", "पूर्वानुमान बदल सकता है", "Open-Meteo अस्थायी रूप से उपलब्ध नहीं है", "{area} में {place} का अनुभव करें।", "जाने से पहले खुलने का समय जाँचें।", "दिन {day}", "{people} लोगों के लिए अनुकूलित यात्रा कार्यक्रम।", "अनुमानित लागत बदल सकती है", "पानी साथ रखें और मौसम जाँचें"),
    "it": ("Previsioni in tempo reale non caricate", "Le previsioni possono cambiare", "Open-Meteo è temporaneamente non disponibile", "Scopri {place} a {area}.", "Controlla gli orari prima della visita.", "Giorno {day}", "Un itinerario ottimizzato per {people} persone.", "I costi stimati possono variare", "Porta dell’acqua e controlla il meteo"),
    "ja": ("ライブ予報は読み込まれていません", "予報は変わる場合があります", "Open-Meteoは一時的に利用できません", "{area}の{place}を体験します。", "訪問前に営業時間を確認してください。", "{day}日目", "{people}人向けに最適化された旅程です。", "推定費用は変動する場合があります", "水を持参し天気を確認してください"),
    "nl": ("Liveverwachting niet geladen", "De verwachting kan veranderen", "Open-Meteo is tijdelijk niet beschikbaar", "Beleef {place} in {area}.", "Controleer voor uw bezoek de openingstijden.", "Dag {day}", "Een geoptimaliseerde route voor {people} personen.", "Geschatte kosten kunnen variëren", "Neem water mee en controleer het weer"),
    "pl": ("Prognoza na żywo nie została wczytana", "Prognoza może się zmienić", "Open-Meteo jest tymczasowo niedostępne", "Odwiedź {place} w {area}.", "Sprawdź godziny otwarcia przed wizytą.", "Dzień {day}", "Zoptymalizowany plan dla {people} osób.", "Szacowane koszty mogą się różnić", "Zabierz wodę i sprawdź pogodę"),
    "pt": ("Previsão em direto não carregada", "A previsão pode mudar", "Open-Meteo está temporariamente indisponível", "Descubra {place} em {area}.", "Confirme o horário antes da visita.", "Dia {day}", "Um itinerário otimizado para {people} pessoas.", "Os custos estimados podem variar", "Leve água e consulte o tempo"),
    "ru": ("Актуальный прогноз не загружен", "Прогноз может измениться", "Open-Meteo временно недоступен", "Посетите {place} в {area}.", "Проверьте часы работы перед посещением.", "День {day}", "Оптимизированный маршрут для {people} человек.", "Ориентировочные расходы могут измениться", "Возьмите воду и проверьте погоду"),
    "tr": ("Canlı hava tahmini yüklenmedi", "Tahmin değişebilir", "Open-Meteo geçici olarak kullanılamıyor", "{area} bölgesindeki {place} deneyimini yaşayın.", "Gitmeden önce çalışma saatlerini kontrol edin.", "Gün {day}", "{people} kişi için optimize edilmiş gezi planı.", "Tahmini maliyetler değişebilir", "Yanınıza su alın ve hava durumunu kontrol edin"),
    "zh": ("尚未加载实时天气预报", "天气预报可能会变化", "Open-Meteo暂时不可用", "体验{area}的{place}。", "出发前请查看开放时间。", "第{day}天", "为{people}人优化的行程。", "预估费用可能有所变化", "请携带饮用水并查看天气"),
    "ko": ("실시간 예보를 불러오지 않았습니다", "예보는 변경될 수 있습니다", "Open-Meteo를 일시적으로 사용할 수 없습니다", "{area}의 {place}을(를) 경험해 보세요.", "방문 전에 운영 시간을 확인하세요.", "{day}일차", "{people}명을 위한 최적화된 일정입니다.", "예상 비용은 달라질 수 있습니다", "물을 챙기고 날씨를 확인하세요"),
    "th": ("ยังไม่ได้โหลดพยากรณ์อากาศแบบสด", "พยากรณ์อากาศอาจเปลี่ยนแปลง", "Open-Meteo ไม่พร้อมใช้งานชั่วคราว", "สัมผัสประสบการณ์ {place} ที่ {area}", "ตรวจสอบเวลาเปิดก่อนเดินทาง", "วันที่ {day}", "แผนการเดินทางที่เหมาะสมสำหรับ {people} คน", "ค่าใช้จ่ายโดยประมาณอาจเปลี่ยนแปลง", "พกน้ำและตรวจสอบสภาพอากาศ"),
}


class PipelineUnavailable(RuntimeError):
    pass


INTENT_PROFILES = {
    "hanoi_highlights": {
        "terms": {"ha_noi", "hanoi", "pho_co"},
        "kinds": {"dia_danh"},
        "tags": {"hanoi_icon", "ho_guom", "ho_tay", "lang_bac", "pho_co", "van_hoa", "lich_su"},
    },
    "coffee": {
        "terms": {"cafe", "coffee", "ca_phe", "caphe"},
        "kinds": {"cafe"},
        "tags": {"cafe", "coffee", "coffee_shop", "chill", "view_dep"},
    },
    "food": {
        "terms": {"an", "an_ngon", "an_uong", "am_thuc", "food", "restaurant", "quan_an", "nha_hang"},
        "kinds": {"nha_hang", "quan_an"},
        "tags": {"am_thuc", "an_vat", "vietnamese", "local", "hai_san", "binh_dan"},
    },
    "culture": {
        "terms": {"van_hoa", "culture", "museum", "bao_tang", "di_tich", "lich_su"},
        "kinds": {"bao_tang", "dia_danh"},
        "tags": {"museum", "van_hoa", "heritage", "history", "checkin"},
    },
    "night": {
        "terms": {"buoi_toi", "ban_dem", "dem", "cho_dem", "night", "evening", "nightlife"},
        "kinds": {"dia_danh", "cho", "cafe", "nha_hang", "quan_an"},
        "tags": {"nightlife", "cho_dem", "night_market", "pho_co", "am_thuc", "view_dep"},
    },
    "walk": {
        "terms": {"di_bo", "walk", "walking", "chill", "ngoai_troi", "park"},
        "kinds": {"cong_vien", "dia_danh"},
        "tags": {"ngoai_troi", "chill", "view_dep", "di_bo"},
    },
}

HANOI_HIGHLIGHT_IDS = (
    "curated-ho-guom",
    "osm-way-37625751",
    "curated-ho-tay",
    "curated-pho-co-ha-noi",
    "van-mieu",
    "chua-tran-quoc",
    "bao-tang-phu-nu",
    "long-bien",
)
HANOI_NIGHT_IDS = ("osm-node-4489385889", "osm-relation-7112202", "osm-way-765597030")
NON_TRAVEL_NAME_HINTS = {
    "sàn gỗ",
    "nội thất",
    "vật liệu",
    "điện máy",
    "điện lạnh",
    "sửa chữa",
    "phụ tùng",
    "gara",
    "garage",
    "bất động sản",
    "văn phòng",
    "travel",
    "media",
    "tour",
    "tourism",
}
GENERIC_PLACE_NAME_KEYS = {"du lich", "tham quan", "check in", "checkin"}
BARE_CITY_SPELLINGS = {
    "can tho",
    "da lat",
    "da nang",
    "dalat",
    "danang",
    "ha long",
    "ha noi",
    "hai phong",
    "halong",
    "hanoi",
    "hoi an",
    "hue",
    "lam dong",
    "nha trang",
    "ninh binh",
    "phu quoc",
    "sa pa",
    "sai gon",
    "saigon",
    "sapa",
    "thanh pho da nang",
    "thanh pho ho chi minh",
    "thanh pho hue",
    "tp hcm",
    "vung tau",
}
CLOSED_PLACE_HINTS = {"closed", "dong cua", "ngung hoat dong", "tam dong"}
LOW_VALUE_TOURIST_NAME_KEYS = {
    "7 wonders",
    "hard to climb",
    "hero statue",
    "louvre",
    "nha trang",
    "pont main",
    "queen cobra",
    "rao chan",
    "saturday option",
    "small waterfall",
    "hoa don ban hang",
    "1",
    "7",
    "14",
    "nguoi tinh nha co binh thuy",
}
FAMOUS_TOURIST_NAME_HINTS = {
    # Đà Nẵng & Hội An
    "ba na",
    "ba na hills",
    "bai bien my khe",
    "bai chay",
    "bai sau",
    "bai sao",
    "ban cat cat",
    "bao tang cham",
    "bao tang chung tich",
    "bao tang da nang",
    "bao tang nghe thuat dieu khac cham",
    "biet thu hang nga",
    "cau rong",
    "cau song han",
    "cau vang",
    "cho ben thanh",
    "cho con",
    "cho dong ba",
    "cho noi cai rang",
    "chua cau",
    "chua linh ung",
    "chua long son",
    "chua thien mu",
    "co do hoa lu",
    "crazy house",
    "dai noi",
    "dao ti top",
    "dao titop",
    "dong thien cung",
    "hang dau go",
    "hang luon",
    "nui bai tho",
    "de hai van",
    "dinh ban co",
    "dinh cau",
    "dinh doc lap",
    "fansipan",
    "golden bridge",
    "hai van quan",
    "hang mua",
    "hang nga",
    "hang sung sot",
    "ho guom",
    "ho hoan kiem",
    "ho tay",
    "ho xuan huong",
    "hon chong",
    "hon mun",
    "hon tam",
    "hoi an",
    "i-resort",
    "independence palace",
    "lang bac",
    "lang chu tich",
    "lang co",
    "lang da my nghe non nuoc",
    "lang khai dinh",
    "long bien",
    "marble mountains",
    "my khe",
    "ngu hanh son",
    "nha tho con ga",
    "nha tho da nha trang",
    "nha tho duc ba",
    "nha trang",
    "nui fansipan",
    "nui son tra",
    "pho co ha noi",
    "pho co hoi an",
    "pho di bo nguyen hue",
    "son tra",
    "song huong",
    "tam coc",
    "thap ba ponagar",
    "thap po nagar",
    "thien mu",
    "thung lung tinh yeu",
    "titop",
    "trang an",
    "tuong chua kito",
    "van mieu",
    "vien hai duong hoc",
    "vinh ha long",
    "yen tu",
    "nui yen tu",
    "vinpearl",
    "vinwonders",
    "vinwonders nha trang",
    "vinh nha trang",
    # Huế
    "dai noi",
    "dai noi hue",
    "chua thien mu",
    "thien mu",
    "lang khai dinh",
    "lang tu duc",
    "lang minh mang",
    "hoang thanh hue",
    "song huong",
    "cau trang tien",
    # Đà Lạt
    "thung lung tinh yeu",
    "langbiang",
    "lang biang",
    "ho xuan huong",
    "chua linh phuoc",
    "chua ve chai",
    "dinh bao dai",
    "thac datanla",
    "datanla",
    "thac pren",
    "crazy house",
    "nha tho con ga",
    "quang truong lam vien",
    # Ninh Bình
    "trang an",
    "chua bai dinh",
    "bai dinh",
    "tam coc",
    "tam coc bich dong",
    "hang mua",
    "tuyet tinh coc",
    "co do hoa lu",
    "hoa lu",
    "thung nham",
    # Cần Thơ & Miền Tây
    "cho noi cai rang",
    "cai rang",
    "ben ninh kieu",
    "ninh kieu",
    "nha co binh thuy",
    "chua ong can tho",
    "thien vien truc lam phuong nam",
    # Hạ Long & Quảng Ninh
    "vinh ha long",
    "hang sung sot",
    "dao ti top",
    "dao titop",
    "titop",
    "dong thien cung",
    "hang dau go",
    "hang luon",
    "nui bai tho",
    "dao tuan chau",
    "tuan chau",
    "bao tang quang ninh",
    "yen tu",
    # Sa Pa & Lào Cai
    "fansipan",
    "dinh fansipan",
    "ban cat cat",
    "cat cat",
    "nha tho da sapa",
    "nui ham rong",
    "deo o quy ho",
    "o quy ho",
    "ta van",
    # Phú Quốc
    "bai sao",
    "bai khem",
    "vinwonders phu quoc",
    "safari phu quoc",
    "sunset sanato",
    "hon thom",
    "cap treo hon thom",
    "grand world",
    # Vũng Tàu
    "tuong chua kito",
    "chua kito",
    "hai dang vung tau",
    "mui nghinh phong",
    "bai sau vung tau",
    "bai truoc vung tau",
    "bach dinh",
    # Quy Nhơn
    "eo gio",
    "ky co",
    "thap banh it",
    "thap doi",
    "ghenh rang tien sa",
    # Phan Thiết & Mũi Né
    "doi cat bay",
    "doi cat do",
    "bau trang",
    "suoi tien mui ne",
    "thap cham poshanu",
    # Quảng Bình
    "phong nha",
    "dong phong nha",
    "dong thien duong",
    "suoi nuoc mooc",
    "song chay hang toi",
    # Hà Giang
    "ma pi leng",
    "deo ma pi leng",
    "cot co lung cu",
    "lung cu",
    "dinh thu vua meo",
    "song nho que",
    "dong van",
    # Hải Phòng
    "vinh lan ha",
    "lan ha",
    "dao cat ba",
    "cat ba",
    "vuon quoc gia cat ba",
    "bai cat co",
    "hang quan y",
    "cai beo",
    "bai bien do son",
    "war remnants",
}
OLD_QUARTER_TERMS = {
    "pho_co",
    "old_quarter",
    "hang_pho",
    "hang_dao",
    "hang_gai",
    "hang_bac",
    "hang_ma",
    "hang_duong",
    "hang_ngang",
    "hang_buom",
    "hang_dau",
    "hang_khay",
    "hang_trong",
}

SEMANTIC_TAG_ALIASES = {
    "tre_em": {"tre_em", "tre", "em", "gia_dinh", "gia", "dinh", "family", "kids"},
    "gia_re": {"gia_re", "tiet_kiem", "binh_dan", "cheap", "budget"},
    "yen_tinh": {"yen_tinh", "chill", "healing", "chua", "lanh", "chua_lanh", "thu_gian"},
    "checkin": {"checkin", "song_ao", "anh_dep", "view_dep"},
    "ngoai_troi": {"ngoai_troi", "bien", "nui", "di_bo", "outdoor"},
    "trong_nha": {"trong_nha", "bao_tang", "museum", "indoor"},
    "am_thuc": {"an_ngon", "am_thuc", "hai_san", "food", "restaurant"},
}

VIETNAM_HOLIDAY_WINDOWS = (
    ("tet_nguyen_dan", (1, 20), (2, 20), "Tết Nguyên đán: giờ mở cửa có thể đổi theo từng năm."),
    ("giai_phong_quoc_te_lao_dong", (4, 30), (5, 1), "Dịp 30/4 và 1/5: điểm du lịch có thể đông và đổi giờ phục vụ."),
    ("quoc_khanh", (9, 1), (9, 3), "Dịp Quốc khánh 2/9: điểm du lịch có thể đông và đổi giờ phục vụ."),
)


def _ascii_fold(value: str) -> str:
    return ascii_fold(value)


def _destination_radius_km(destination_label: str | None) -> float:
    if not destination_label:
        return DESTINATION_RADIUS_KM
    normalized = _ascii_fold(destination_label).casefold()
    for destination in FOCUS_DESTINATIONS.values():
        if _ascii_fold(str(destination["label"])).casefold() != normalized:
            continue
        radius = destination.get("radius_km")
        if isinstance(radius, int | float) and radius > 0:
            return float(radius)
        return DESTINATION_RADIUS_KM
    return DESTINATION_RADIUS_KM


def relevant_tags(context: str) -> set[str]:
    normalized = _ascii_fold(context).replace(" ", "_")
    plain = _ascii_fold(context)
    words = plain.split()
    phrases = {
        "_".join(words[index : index + size])
        for size in (2, 3)
        for index in range(0, max(len(words) - size + 1, 0))
    }
    return set(re.findall(r"[a-zA-Z_]+", normalized)) | set(words) | phrases


def _request_seed(request: PlanRequest) -> int:
    raw = "|".join(
        [
            request.context,
            request.thoi_luong,
            str(request.so_nguoi),
            str(request.ngan_sach),
            request.ma_phien or "",
            request.nonce or "",
        ]
    )
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)


def _place_seed(place: Place, seed: int) -> int:
    raw = f"{seed}|{place.id}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


def _destination_match_aliases(name: str) -> set[str]:
    folded = _ascii_fold(name).casefold()
    if not folded or folded in GENERIC_DESTINATION_NAMES:
        return set()
    aliases = {folded}
    for prefix in DESTINATION_NAME_PREFIXES:
        if not folded.startswith(prefix):
            continue
        remainder = folded.removeprefix(prefix).strip()
        if (
            remainder
            and remainder not in _WEAK_STRIPPED_DESTINATION_ALIASES
            and remainder not in GENERIC_DESTINATION_NAMES
            and (len(remainder) >= 5 or remainder in {"hue", "sa pa", "ha giang"})
        ):
            aliases.add(remainder)
    return aliases


def _alias_mentioned(alias: str, context: str) -> bool:
    if not alias:
        return False
    if len(alias) < 4 and alias not in {"hue", "sa pa", "ha giang"}:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", context))


def _nearest_focus_destination(lat: float, lng: float, max_km: float = 25.0) -> dict[str, object] | None:
    best: tuple[float, dict[str, object]] | None = None
    for destination in FOCUS_DESTINATIONS.values():
        distance = haversine_km(lat, lng, float(destination["lat"]), float(destination["lng"]))
        if distance > max_km:
            continue
        if best is None or distance < best[0]:
            best = (distance, destination)
    return None if best is None else best[1]


@lru_cache(maxsize=1024)
def _destination_context_from_text(context: str, lat: float, lng: float) -> tuple[float, float, str | None]:
    if not context:
        return lat, lng, None
    hits: list[tuple[int, dict[str, object]]] = []
    for destination in FOCUS_DESTINATIONS.values():
        aliases = destination["aliases"]
        if not isinstance(aliases, set | tuple | list):
            continue
        for alias in aliases:
            alias_key = str(alias).strip()
            if not alias_key:
                continue
            for match in re.finditer(rf"(?<![a-z0-9]){re.escape(alias_key)}(?![a-z0-9])", context):
                hits.append((match.start(), destination))
    if hits:
        hits.sort(key=lambda row: row[0])
        cut = None
        for match in re.finditer(r"(?<![a-z0-9])thoi(?![a-z0-9])", context):
            cut = match.start()
        chosen = hits[-1][1]
        if cut is not None:
            after = [item for item in hits if item[0] >= cut]
            if after:
                chosen = after[-1][1]
        return float(chosen["lat"]), float(chosen["lng"]), str(chosen["label"])
    best: tuple[int, float, Place] | None = None
    for place in PLACES:
        if _looks_like_non_travel_business(place) or _looks_closed(place):
            continue
        name_aliases = _destination_match_aliases(place.name)
        if not name_aliases:
            continue
        name_match = any(_alias_mentioned(alias, context) for alias in name_aliases)
        area = _ascii_fold(place.area).casefold()
        area_match = bool(
            area
            and area not in {"viet nam", "vietnam"}
            and (len(area) >= 4 or area in {"hue", "sa pa", "ha giang"})
            and re.search(rf"(?<![a-z0-9]){re.escape(area)}(?![a-z0-9])", context)
        )
        if not name_match and not area_match:
            continue
        score = 0
        if name_match:
            score += 12
        if area_match:
            score += 7
        if place.kind in SIGHT_KINDS or place.kind in {"di_tich", "bai_bien", "hang_dong", "nui"}:
            score += 6
        if place.kind in DINING_KINDS or place.kind in {"cafe", "khach_san", "nha_nghi", "homestay"}:
            score -= 7
        if place.source == "curated":
            score += 2
        distance = haversine_km(lat, lng, place.lat, place.lng)
        candidate = (score, -distance, place)
        if best is None or candidate > best:
            best = candidate
    if best and best[0] >= 6:
        place = best[2]
        named = any(_alias_mentioned(alias, context) for alias in _destination_match_aliases(place.name))
        if named:
            return place.lat, place.lng, place.name
        area_key = _ascii_fold(place.area).casefold()
        label = place.area if area_key not in {"viet nam", "vietnam"} else place.name
        return place.lat, place.lng, label or place.name
    nearest = _nearest_focus_destination(lat, lng)
    if nearest:
        return float(nearest["lat"]), float(nearest["lng"]), str(nearest["label"])
    return lat, lng, None


def _destination_context(request: PlanRequest) -> tuple[float, float, str | None]:
    """Infer the trip center from the user's text instead of assuming Hanoi.

    The frontend can send a default coordinate, so destination intent is
    recovered from the prompt first. Known focus cities are resolved before
    catalog matching to prevent brand-name false positives like "Hạ Long" food
    chains in Hà Nội.
    """
    context = _ascii_fold(request.context).casefold()
    return _destination_context_from_text(
        context,
        round(_lodging_anchor(request)[0], 4),
        round(_lodging_anchor(request)[1], 4),
    )


def _in_requested_destination(place: Place, request: PlanRequest) -> bool:
    destination_lat, destination_lng, destination_label = _destination_context(request)
    if not destination_label:
        return True
    return haversine_km(destination_lat, destination_lng, place.lat, place.lng) <= _destination_radius_km(destination_label)


def _attach_plan_cover(plan: dict, destination_label: str | None) -> None:
    url, credit = cover_for_destination(destination_label)
    if not (isinstance(url, str) and url.startswith("http")):
        skip_kinds = {"cafe", "ca_phe", "nha_hang", "quan_an", "cho", "drinks"}
        for day in plan.get("ngay") or []:
            if not isinstance(day, dict):
                continue
            for slot in day.get("khoang_gio") or []:
                if not isinstance(slot, dict):
                    continue
                if str(slot.get("loai") or "") in skip_kinds:
                    continue
                anh = slot.get("anh")
                if isinstance(anh, str) and anh.startswith("http"):
                    url, credit = anh, slot.get("anh_nguon")
                    break
            if isinstance(url, str) and url.startswith("http"):
                break
    if isinstance(url, str) and url.startswith("http"):
        plan["anh_bia"] = url
        plan["anh_bia_nguon"] = credit


def _intent_profiles(tags: set[str]) -> list[dict[str, set[str]]]:
    return [
        profile
        for profile in INTENT_PROFILES.values()
        if tags.intersection(profile["terms"])
    ]


def _intent_score(place: Place, profiles: list[dict[str, set[str]]]) -> int:
    if not profiles:
        return 0
    score = 0
    place_tags = set(place.tags)
    for profile in profiles:
        if place.kind in profile["kinds"]:
            score += 3
        score += len(place_tags.intersection(profile["tags"]))
    return score


def _semantic_tags_from_context(tags: set[str]) -> set[str]:
    semantic: set[str] = set()
    for label, aliases in SEMANTIC_TAG_ALIASES.items():
        if tags.intersection(aliases):
            semantic.add(label)
    return semantic


DISLIKE_PREFIXES = (
    "khong thich", "ko thich", "tranh", "khong muon", "ko muon",
    "khong di", "khong an", "khong den", "so", "ghet", "di ung voi",
)


def _disliked_profiles(context: str) -> set[str]:
    plain = _ascii_fold(context)
    dislikes: set[str] = set()
    for profile_name, profile in INTENT_PROFILES.items():
        for term in profile["terms"]:
            term_text = term.replace("_", " ")
            if any(f"{prefix} {term_text}" in plain for prefix in DISLIKE_PREFIXES):
                dislikes.add(profile_name)
    return dislikes


def _is_place_disliked(place: Place, disliked_profiles: set[str], context: str = "") -> bool:
    """Hard filter: strictly forbid disliked categories and terms."""
    if not disliked_profiles and not context:
        return False
    place_tags = set(place.tags)
    for profile_name in disliked_profiles:
        profile = INTENT_PROFILES.get(profile_name)
        if profile and (place.kind in profile["kinds"] or place_tags.intersection(profile["tags"])):
            return True
    plain = _ascii_fold(context)
    place_name_folded = _ascii_fold(place.name)
    # Check specific keyword dislikes
    for phrase in ["leo nui", "nui", "trekking", "di bo nhieu", "mo hoi"]:
        if f"khong thich {phrase}" in plain or f"tranh {phrase}" in plain:
            if "nui" in place.tags or "trekking" in place.tags or "nui" in place_name_folded or "hill" in place_name_folded:
                return True
    return False


def _field(value, source: str, evidence: str | None = None, status: str = "present") -> dict:
    return {
        "gia_tri": value,
        "nguon": source,
        "bang_chung": evidence,
        "trang_thai": status,
    }


def _safe_ai_intent(context: str, locale: str) -> tuple[dict, str]:
    extractor = getattr(ai_adapter, "extract_request_intent", None)
    if not callable(extractor):
        return {}, "rule_based_fallback"
    try:
        payload = extractor(context, locale)
    except RuntimeError:
        return {}, "rule_based_fallback"
    if not isinstance(payload, dict):
        return {}, "rule_based_fallback"
    if ai_adapter.__class__.__name__ == "OfflineAIAdapter":
        return payload, "rule_based_fallback"
    try:
        payload = AIExtractPayload.model_validate(payload).model_dump(exclude_none=True)
    except ValidationError:
        return {}, "rule_based_fallback"
    return payload, "ai_extracted"


def _ai_text_field(payload: dict, key: str) -> tuple[str | None, str | None]:
    item = payload.get(key)
    if not isinstance(item, dict):
        return None, None
    value = item.get("value")
    evidence = item.get("evidence")
    return (
        value.strip() if isinstance(value, str) and value.strip() else None,
        evidence.strip() if isinstance(evidence, str) and evidence.strip() else None,
    )


def _ai_list(payload: dict, key: str) -> list[dict]:
    values = payload.get(key)
    if not isinstance(values, list):
        return []
    result: list[dict] = []
    for item in values[:12]:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        evidence = item.get("evidence")
        result.append(
            _field(
                value.strip()[:80],
                "ai_extracted",
                evidence.strip()[:160] if isinstance(evidence, str) and evidence.strip() else None,
            )
        )
    return result


def _rule_preference_fields(tags: set[str]) -> list[dict]:
    fields: list[dict] = []
    for profile_name, profile in INTENT_PROFILES.items():
        if tags.intersection(profile["terms"]):
            fields.append(_field(profile_name, "rule_based_context", profile_name))
    return fields


def _rule_dislike_fields(context: str) -> list[dict]:
    plain_context = " ".join(context.split())
    fields = [
        _field(profile, "rule_based_context", profile)
        for profile in sorted(_disliked_profiles(context))
    ]
    for match in re.finditer(r"(?:không thích|ko thích|không muốn|ko muốn|tránh|sợ|ghét|dị ứng với)\s+([^,.。;]{2,60})", plain_context, re.IGNORECASE):
        value = match.group(1).strip()
        if value:
            fields.append(_field(value[:80], "rule_based_context", match.group(0)[:160]))
    return fields


def _dedupe_field_values(fields: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for field in fields:
        key = _ascii_fold(str(field.get("gia_tri", "")))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(field)
    return result


def _request_understanding(request: PlanRequest) -> dict:
    tags = relevant_tags(request.context)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    ai_payload, extraction_source = _safe_ai_intent(request.context, request.ngon_ngu)
    ai_destination, ai_destination_evidence = _ai_text_field(ai_payload, "destination_text")
    destination_value = destination_label or ai_destination
    destination_source = (
        "doi_chieu_catalog"
        if destination_label
        else "ai_extracted"
        if ai_destination
        else "missing"
    )
    max_places_match = re.search(r"(?:toi da|khong qua|qua)\s+(\d{1,2})\s+(?:cho|diem|dia diem)", _ascii_fold(request.context))
    constraints = [
        _field(request.thoi_luong, "form_chat", None),
        _field(request.so_nguoi, "form_chat", None),
        _field(request.ngan_sach, "form_chat", None),
    ]
    if max_places_match:
        constraints.append(_field(int(max_places_match.group(1)), "rule_based_context", max_places_match.group(0)))
    constraints.extend(_ai_list(ai_payload, "constraints"))
    dislikes = [*_ai_list(ai_payload, "dislikes"), *_rule_dislike_fields(request.context)]
    missing_required = []
    if not destination_value:
        missing_required.append("diem_den")
    return {
        "schema_version": "input-understanding-v1",
        "context_goc": request.context,
        "diem_den": _field(
            {
                "ten": destination_value,
                "toa_do": {"lat": destination_lat, "lng": destination_lng} if destination_value else None,
            },
            destination_source,
            destination_label or ai_destination_evidence,
            "present" if destination_value else "missing",
        ),
        "so_ngay": _field(_trip_timing(request).days, "form_chat", request.thoi_luong),
        "so_nguoi": _field(request.so_nguoi, "form_chat", None),
        "ngan_sach": _field(request.ngan_sach, "form_chat", None),
        "thoi_luong": _field(request.thoi_luong, "form_chat", None),
        "so_thich": _dedupe_field_values([*_ai_list(ai_payload, "preferences"), *_rule_preference_fields(tags)]),
        "khong_thich": _dedupe_field_values(dislikes),
        "rang_buoc": _dedupe_field_values(constraints),
        "muc_bat_buoc": _dedupe_field_values(_ai_list(ai_payload, "must_visit")),
        "tag_ngu_nghia": _field(sorted(_semantic_tags_from_context(tags)), "rule_based_context", None),
        "bat_buoc_thieu": missing_required,
        "hanh_dong_tiep_theo": (
            "hoi_lai_nguoi_dung" if missing_required else "du_dieu_kien_lap_lich"
        ),
        "xuat_xu": {
            "form_chat": ["thoi_luong", "so_ngay", "so_nguoi", "ngan_sach"],
            "ai_extracted": ["diem_den", "so_thich", "khong_thich", "rang_buoc", "muc_bat_buoc"]
            if extraction_source == "ai_extracted"
            else [],
            "rule_based_context": ["diem_den", "tag_ngu_nghia", "so_thich", "khong_thich", "rang_buoc"],
        },
        "nguon_boc_tach_dinh_tinh": extraction_source,
        "ghi_chu": "Định lượng lấy từ form. Định tính lấy từ AI nếu có cấu hình và qua kiểm tra kiểu dữ liệu; thiếu mục bắt buộc thì đánh dấu để hỏi lại, không tự bịa.",
    }


def missing_required_inputs(request: PlanRequest, understanding: dict | None = None) -> dict:
    if understanding is None:
        understanding = _request_understanding(request)
    missing = list(understanding.get("bat_buoc_thieu") or [])
    questions = {
        "diem_den": "Bạn muốn đi điểm đến/thành phố nào?",
    }
    return {
        "missing_fields": missing,
        "questions": [questions.get(field, f"Vui lòng bổ sung {field}") for field in missing],
        "understanding": understanding,
    }


def _distance_score(distance_km: float) -> int:
    if distance_km < 1:
        return 100
    if distance_km < 3:
        return 80
    if distance_km < 5:
        return 60
    if distance_km <= 10:
        return 40
    return 20


def _numeric_place_metric(place: Place, *names: str) -> float | None:
    for name in names:
        value = getattr(place, name, None)
        if isinstance(value, int | float):
            return float(value)
    return None


def _review_count_score(review_count: float | None) -> int:
    if review_count is None or review_count <= 0:
        return 20
    if review_count >= 1000:
        return 100
    if review_count >= 100:
        return 80
    if review_count >= 10:
        return 60
    return 40


def _ranking_evidence(
    place: Place,
    request: PlanRequest,
    tags: set[str],
    profiles: list[dict[str, set[str]]],
    destination_lat: float,
    destination_lng: float,
    behavior_profile: dict | None = None,
) -> dict:
    place_tags = set(place.tags)
    matched_profiles = 0
    for profile in profiles:
        if place.kind in profile["kinds"] or place_tags.intersection(profile["tags"]):
            matched_profiles += 1
    suitability = 50 if not profiles else int((matched_profiles / len(profiles)) * 100)
    semantic_matches = len(place_tags.intersection(_semantic_tags_from_context(tags)))
    suitability = min(100, suitability + semantic_matches * 5)
    disliked = _disliked_profiles(request.context)
    for profile_name in disliked:
        profile = INTENT_PROFILES[profile_name]
        if place.kind in profile["kinds"] or place_tags.intersection(profile["tags"]):
            suitability = max(0, suitability - 30)
    distance = haversine_km(destination_lat, destination_lng, place.lat, place.lng)
    open_hour, close_hour = _effective_hours(place)
    opening_score = 100 if 0 <= open_hour < close_hour <= 24 else 0
    rating_value = _numeric_place_metric(place, "rating", "diem_danh_gia", "google_rating")
    review_count = _numeric_place_metric(place, "review_count", "so_nhan_xet", "google_review_count")
    rating_score = (
        max(0, min(100, round((rating_value / 5) * 100)))
        if rating_value is not None and 0 <= rating_value <= 5
        else 40
    )
    review_score = _review_count_score(review_count)
    tag_weights = (behavior_profile or {}).get("tag_weights") if isinstance(behavior_profile, dict) else {}
    behavior_signal = 0
    if isinstance(tag_weights, dict):
        behavior_signal = sum(
            int(tag_weights.get(tag, 0))
            for tag in place_tags
            if isinstance(tag_weights.get(tag, 0), int)
        )
    weighted_components = [
        (30, suitability),
        (25, rating_score),
        (20, _distance_score(distance)),
        (15, opening_score),
        (10, review_score),
    ]
    total_weight = sum(weight for weight, _ in weighted_components)
    total = round(sum(weight * score for weight, score in weighted_components) / total_weight, 2)
    missing = []
    if rating_value is None:
        missing.append("rating")
    if review_count is None:
        missing.append("so_review")
    if not place.image_url and not image_for(place)[0]:
        missing.append("anh")
    return {
        "diem_tong": total,
        "thanh_phan": {
            "muc_phu_hop": suitability,
            "diem_danh_gia": rating_score,
            "vi_tri_khoang_cach": _distance_score(distance),
            "khop_gio_mo_cua": opening_score,
            "so_nhan_xet": review_score,
        },
        "ho_so_hanh_vi": {
            "schema_version": (behavior_profile or {}).get("schema_version"),
            "version": (behavior_profile or {}).get("version", 0),
            "tin_hieu_tag": behavior_signal,
            "gioi_han": "Hành vi người dùng được ghi riêng để điều chỉnh trọng số/tag trong giới hạn an toàn; công thức điểm phát hành vẫn giữ 5 tiêu chí cố định.",
        },
        "khoang_cach_km": round(distance, 2),
        "du_lieu_thuc_te": {
            "rating": rating_value,
            "so_nhan_xet": int(review_count) if review_count is not None else None,
        },
        "du_lieu_thieu": missing,
        "ghi_chu": "Rating thiếu dùng điểm dự phòng 40 và số nhận xét thiếu dùng 20 theo spec; dữ liệu thiếu vẫn được đánh dấu, không bịa giá trị thật.",
    }


def _holiday_note(trip_date) -> dict | None:
    month_day = (trip_date.month, trip_date.day)
    for code, start, end, note in VIETNAM_HOLIDAY_WINDOWS:
        if start <= month_day <= end:
            return {
                "ma": code,
                "ghi_chu": note,
                "nguon": "quy_tac_noi_bo_lich_nghi_le_viet_nam",
                "gio_mo_cua_can_xac_minh": True,
                "khong_dung_gio_thuong_lam_bang_chung_phat_hanh": code == "tet_nguyen_dan",
            }
    return None


def _holiday_hours_status(holiday: dict | None) -> dict | None:
    if not holiday:
        return None
    return {
        "ma": holiday.get("ma"),
        "ghi_chu": holiday.get("ghi_chu"),
        "nguon": holiday.get("nguon"),
        "gio_mo_cua_can_xac_minh": True,
        "trang_thai_xac_minh": (
            "holiday_hours_required_before_release"
            if holiday.get("khong_dung_gio_thuong_lam_bang_chung_phat_hanh")
            else "holiday_hours_warning"
        ),
    }


def _destination_key_from_label(label: str | None) -> str | None:
    if not label:
        return None
    normalized = _ascii_fold(label).casefold()
    for key, destination in FOCUS_DESTINATIONS.items():
        if _ascii_fold(str(destination["label"])).casefold() == normalized:
            return key
    return None


def _seasonal_context(destination_label: str | None, trip_date) -> dict:
    key = _destination_key_from_label(destination_label)
    policy = SEASONAL_TOURISM_POLICY.get(key or "")
    if not policy:
        return {
            "co_san": False,
            "nguon": "seasonal_tourism_policy_v1",
            "trang_thai": "no_focus_city_policy",
            "ghi_chu": "Chưa có policy mùa vụ nội bộ cho điểm đến này.",
        }
    month = trip_date.month
    best_months = tuple(policy["best_months"])
    caution_months = tuple(policy["caution_months"])
    status = "recommended_season" if month in best_months else "caution_season" if month in caution_months else "neutral_season"
    return {
        "co_san": True,
        "nguon": "seasonal_tourism_policy_v1",
        "trang_thai": status,
        "thang": month,
        "diem_den": destination_label,
        "thang_de_xuat": list(best_months),
        "thang_can_luu_y": list(caution_months),
        "ghi_chu_le_hoi": list(policy["festival_notes"]),
        "gioi_han": "Heuristic nội bộ theo thành phố; cần lịch sự kiện/nguồn chính thức theo năm trước phát hành.",
    }


def _is_sunset_suitable(place: Place) -> bool:
    return (
        bool({"view_dep", "ho_tay", "beach", "bien", "ngoai_troi", "song", "ho"}.intersection(place.tags))
        or place.kind in {"bai_bien", "nui", "dia_danh", "cong_vien"}
    ) and not _is_morning_only(place)


def _near_sunset(start: datetime, solar_context: dict | None) -> bool:
    sunset_minute = (solar_context or {}).get("hoang_hon_phut")
    if not isinstance(sunset_minute, int):
        return False
    start_minute = start.hour * 60 + start.minute
    return sunset_minute - 105 <= start_minute <= sunset_minute + 20


def _time_reason(
    place: Place,
    meal_type: str | None,
    start: datetime,
    weather: dict | None,
    solar_context: dict | None = None,
) -> str:
    if meal_type == "trua":
        return "Bữa trưa được giữ trong khung 11:30 đến 13:30."
    if meal_type == "toi":
        return "Bữa tối được giữ trong khung 18:00 đến 21:00."
    if _is_night_market(place):
        return "Chợ đêm được xếp sau 18:00."
    if _is_morning_only(place):
        return "Địa điểm này ưu tiên buổi sáng do giờ hoạt động hoặc guidance."
    if _is_sunset_suitable(place) and _near_sunset(start, solar_context):
        return "Địa điểm ngắm cảnh/ngoài trời được ưu tiên gần hoàng hôn theo tính toán thiên văn."
    if _is_outdoor_place(place) and _weather_discourages_midday_outdoor(weather):
        return "Địa điểm ngoài trời được tránh buổi trưa khi trời nóng hoặc mưa."
    guidance = _guidance(place)
    if guidance:
        return "Khung giờ dựa trên visit_guidance đã lưu."
    return "Khung giờ được chọn theo giờ mở cửa, thời lượng và tuyến di chuyển."


def _slot_evidence(
    place: Place,
    request: PlanRequest,
    start: datetime,
    meal_type: str | None,
    weather: dict | None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
) -> dict:
    tags = relevant_tags(request.context)
    profiles = _intent_profiles(tags)
    destination_lat, destination_lng, _ = _destination_context(request)
    open_hour, close_hour = _effective_hours(place)
    timing = {
        "ly_do": _time_reason(place, meal_type, start, weather, solar_context),
        "gio_mo_cua_hieu_luc": {"open": open_hour, "close": close_hour},
    }
    if solar_context and solar_context.get("co_san"):
        timing["thien_van"] = {
            "hoang_hon": solar_context.get("hoang_hon"),
            "nguon": solar_context.get("nguon"),
            "gan_hoang_hon": _is_sunset_suitable(place) and _near_sunset(start, solar_context),
        }
    return {
        "xep_hang": _ranking_evidence(
            place,
            request,
            tags,
            profiles,
            destination_lat,
            destination_lng,
            behavior_profile,
        ),
        "du_lieu": {
            "nguon": place.source,
            "nguon_url": source_for(place)[0],
            "co_toa_do": True,
            "co_gio_mo_cua": 0 <= open_hour < close_hour <= 24,
            "co_anh": bool(image_for(place)[0]),
        },
        "thoi_diem": timing,
    }


PROVINCE_HIGHLIGHT_MAP: dict[str, tuple[str, ...]] = {
    "ha_noi": HANOI_HIGHLIGHT_IDS,
    "da_nang": ("curated-cau-rong", "curated-ngu-hanh-son", "curated-bai-bien-my-khe", "curated-ba-na-hills", "curated-chua-linh-ung"),
    "hoi_an": ("curated-pho-co-hoi-an", "curated-chua-cau-hoi-an"),
    "hue": ("curated-dai-noi-hue", "curated-chua-thien-mu", "curated-lang-khai-dinh", "curated-lang-tu-duc"),
    "da_lat": ("curated-thung-lung-tinh-yeu", "curated-langbiang", "curated-ho-xuan-huong", "curated-chua-linh-phuoc", "curated-dinh-bao-dai"),
    "nha_trang": ("curated-thap-ba-ponagar", "curated-nha-trang-beach", "curated-hon-chong", "curated-vien-hai-duong-hoc", "curated-chua-long-son"),
    "ninh_binh": ("curated-trang-an", "curated-chua-bai-dinh", "curated-tam-coc", "curated-hang-mua"),
    "can_tho": ("curated-cho-noi-cai-rang", "curated-ben-ninh-kieu", "curated-nha-co-binh-thuy"),
    "ha_long": (
        "curated-vinh-ha-long",
        "curated-hang-sung-sot",
        "curated-dao-ti-top",
        "curated-dao-tuan-chau",
        "curated-dong-thien-cung",
        "curated-hang-dau-go",
        "curated-hang-luon",
        "curated-bai-chay",
        "curated-nui-bai-tho",
    ),
    "yen_tu": (
        "curated-yen-tu",
        "curated-yen-tu-chua-dong",
        "curated-yen-tu-thien-vien",
        "curated-yen-tu-cap-treo",
        "curated-yen-tu-giai-oan",
    ),
    "cat_ba": (
        "curated-vuon-quoc-gia-cat-ba",
        "curated-bai-cat-co-1",
        "curated-bai-cat-co-3",
        "curated-hang-quan-y",
        "curated-phao-dai-than-cong",
        "curated-vinh-lan-ha",
        "curated-lang-chai-cai-beo",
        "curated-thi-tran-cat-ba",
    ),
    "sa_pa": ("curated-fansipan-peak", "curated-ban-cat-cat", "curated-nha-tho-da-sapa"),
    "phu_quoc": ("curated-bai-sao-phu-quoc", "curated-vinwonders-phu-quoc", "curated-sunset-sanato"),
}


def _catalog_place(place_id: str, by_id: dict[str, Place]) -> Place | None:
    """Resolve a curated id even when the catalogue kept an OSM twin of the same stop."""
    found = by_id.get(place_id)
    if found:
        return found
    name = KNOWN_PLACE_NAMES_BY_ID.get(place_id)
    if not name:
        return None
    want = place_match_key(name)
    return next((place for place in by_id.values() if place_match_key(place.name) == want), None)


def _highlight_places(request: PlanRequest, excluded: set[str]) -> list[Place]:
    tags = relevant_tags(request.context)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    origin = (destination_lat, destination_lng)
    radius = _destination_radius_km(destination_label)
    destination_key = _ascii_fold(destination_label or "").casefold()
    by_id = {place.id: place for place in PLACES}
    pinned: list[Place] = []
    seen: set[str] = set()
    seen_names: set[str] = set()

    def _keep(place: Place | None) -> None:
        if (
            not place
            or place.id in excluded
            or place.id in seen
            or _name_taken(place, seen_names)
            or place.cost > budget_cap(request)
            or not is_routable(place)
            or not _near_anchor(place, origin, radius)
            or _looks_like_non_travel_business(place)
            or _looks_closed(place)
            or _mentions_other_destination(place, destination_label)
        ):
            return
        pinned.append(place)
        seen.add(place.id)
        seen_names.update(_place_name_keys(place))

    matching_key = None
    province_key = destination_key.replace(" ", "_")
    if province_key in PROVINCE_HIGHLIGHT_MAP:
        matching_key = province_key
    else:
        for key, dest_info in FOCUS_DESTINATIONS.items():
            if _ascii_fold(str(dest_info["label"])).casefold() == _ascii_fold(destination_label or "").casefold():
                matching_key = key
                break
    if matching_key and matching_key in PROVINCE_HIGHLIGHT_MAP:
        explicit_anchor = tags.intersection({"ha_noi", "hanoi", "pho_co", "ho_guom", "ho_tay", "lang_bac", "ho_chi_minh", "ba_dinh", "lan_dau"})
        if matching_key == "ha_noi":
            wants_night = bool(tags.intersection(INTENT_PROFILES["night"]["terms"]))
            wants_hanoi_highlights = bool(explicit_anchor and (destination_label is None or tags.intersection({"ha_noi", "hanoi", "pho_co", "lan_dau"})))
            if wants_night:
                place_ids = [
                    "curated-ho-guom",
                    "curated-ho-tay",
                    "curated-pho-co-ha-noi",
                    *HANOI_NIGHT_IDS,
                    *((*HANOI_HIGHLIGHT_IDS,) if wants_hanoi_highlights else ()),
                ]
            elif wants_hanoi_highlights:
                place_ids = list(HANOI_HIGHLIGHT_IDS)
            else:
                place_ids = list(HANOI_HIGHLIGHT_IDS)
        else:
            place_ids = list(PROVINCE_HIGHLIGHT_MAP[matching_key])
        for place_id in place_ids:
            _keep(_catalog_place(place_id, by_id))

    destination_is_hanoi = destination_key in {"ha noi", "hanoi"} or (
        destination_label is None and haversine_km(destination_lat, destination_lng, 21.0285, 105.8542) <= 20
    )
    explicit_anchor = tags.intersection({"ha_noi", "hanoi", "pho_co", "ho_guom", "ho_tay", "lang_bac", "ho_chi_minh", "ba_dinh"})
    wants_hanoi_highlights = bool(destination_is_hanoi and explicit_anchor and (destination_label is None or tags.intersection({"ha_noi", "hanoi", "pho_co"})))
    wants_night = bool(destination_is_hanoi and tags.intersection(INTENT_PROFILES["night"]["terms"]))
    context_key = " ".join(_ascii_fold(request.context).split())
    dest_key = _ascii_fold(destination_label or "").casefold()

    for place in _nearby_places(origin, radius):
        name_key = _place_name_key(place)
        named_dest = bool(dest_key and dest_key in name_key)
        mentioned = bool(
            name_key
            and " " in name_key
            and name_key in context_key
        )
        if (
            (named_dest or mentioned)
            and not _is_evening_place(place)
            and not _is_bare_city_place(place)
            and (
                mentioned
                or (
                    _is_sight_place(place)
                    and _is_iconic_place(place)
                    and place.kind not in {"khach_san", "nha_nghi", "homestay"}
                )
            )
        ):
            _keep(place)
    for place_id in (
        *((*HANOI_HIGHLIGHT_IDS,) if wants_hanoi_highlights else ()),
        *((*HANOI_NIGHT_IDS,) if wants_night else ()),
    ):
        _keep(_catalog_place(place_id, by_id))
    if destination_label:
        famous = sorted(
            (
                place
                for place in _nearby_places(origin, radius)
                if _is_sight_place(place) and _is_iconic_place(place) and not _is_bare_city_place(place)
            ),
            key=lambda place: (
                famous_priority(place) or 9,
                0 if place.source == "curated" else 1,
                0 if any(hint in _place_name_key(place) for hint in FAMOUS_TOURIST_NAME_HINTS) else 1,
                -_tourism_quality_score(place),
                haversine_km(destination_lat, destination_lng, place.lat, place.lng),
            ),
        )
        highlight_cap = 12 if request.thoi_luong == "nhieu_ngay" else 6
        for place in famous[:highlight_cap]:
            _keep(place)
    return pinned


def _wants_night(request: PlanRequest) -> bool:
    return bool(relevant_tags(request.context).intersection(INTENT_PROFILES["night"]["terms"]))


def _wants_coffee(request: PlanRequest) -> bool:
    return bool(relevant_tags(request.context).intersection(INTENT_PROFILES["coffee"]["terms"])) or _is_food_trip(request)


def _is_food_trip(request: PlanRequest | None) -> bool:
    if not request:
        return False
    return str(_policy_get(request.intent_policy, "primary_intent") or "") == "food"


def _is_sight_place(place: Place, *, allow_cafe: bool = False, allow_food: bool = False) -> bool:
    if place.kind in SIGHT_KINDS:
        return True
    if allow_food and place.kind in DINING_KINDS:
        return True
    return allow_cafe and place.kind == "cafe"


def _place_name_key(place: Place) -> str:
    return " ".join(_ascii_fold(place.name).split())


def _place_alias_key(place: Place) -> str:
    """Collapse OSM twins like 'Bãi Trường' / 'Bãi Trường Beach' and 'Ti Tốp' / 'Titop'."""
    return place_match_key(place.name)


def _place_name_keys(place: Place) -> set[str]:
    return {key for key in (_place_name_key(place), _place_alias_key(place), place_match_key(place.name)) if key}


def _name_taken(place: Place, used_names: set[str] | None) -> bool:
    return bool(used_names) and bool(_place_name_keys(place) & used_names)


def _prefer_place(left: Place, right: Place) -> Place:
    left_score = (
        int(left.source == "curated"),
        int(bool(left.rating)),
        int(left.review_count or 0),
        int(left.source == "Nominatim"),
        int("beach" in left.tags),
        -len(left.name),
        -left.cost,
    )
    right_score = (
        int(right.source == "curated"),
        int(bool(right.rating)),
        int(right.review_count or 0),
        int(right.source == "Nominatim"),
        int("beach" in right.tags),
        -len(right.name),
        -right.cost,
    )
    return left if left_score >= right_score else right


def _dedupe_places(places: list[Place]) -> list[Place]:
    """Keep one stop per place id, per display-name alias, and per close geographic duplicate."""
    by_id: dict[str, Place] = {}
    for place in places:
        existing = by_id.get(place.id)
        by_id[place.id] = _prefer_place(existing, place) if existing else place

    by_name: dict[str, Place] = {}
    order: list[str] = []
    for place in by_id.values():
        key = _place_alias_key(place) or place.id
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = place
            order.append(key)
            continue
        by_name[key] = _prefer_place(existing, place)

    deduped: list[Place] = []
    for key in order:
        current = by_name[key]
        # Merge close duplicates only when names are genuinely similar (OSM/seed twins).
        close_duplicate = False
        current_key = _place_name_key(current)
        for i, existing in enumerate(deduped):
            if haversine_km(current.lat, current.lng, existing.lat, existing.lng) >= 0.15:
                continue
            if SequenceMatcher(None, current_key, _place_name_key(existing)).ratio() < 0.8:
                continue
            deduped[i] = _prefer_place(existing, current)
            close_duplicate = True
            break
        if not close_duplicate:
            deduped.append(current)
    return deduped


def _is_dining_place(place: Place) -> bool:
    return place.kind in DINING_KINDS


_VEGETARIAN_NAME_RE = re.compile(
    r"(?<![a-z0-9])(quan chay|nha hang chay|com chay|an chay|thuc chay|do chay|vegan|vegetarian|chay)(?![a-z0-9])"
)
_SEAFOOD_NAME_RE = re.compile(r"(?<![a-z0-9])(hai san|seafood)(?![a-z0-9])")
_VEGETARIAN_TAGS = frozenset({"ban_chay", "vegetarian", "vegan"})
_SEAFOOD_TAGS = frozenset({"hai_san", "seafood", "fish"})
_VEGETARIAN_CONTEXT_TERMS = frozenset({
    "chay", "an_chay", "quan_chay", "com_chay", "thuc_chay", "do_chay", "vegan", "vegetarian",
})
_SEAFOOD_CONTEXT_TERMS = frozenset({"hai_san", "hai san", "seafood"})


def _wants_vegetarian(request: PlanRequest | None) -> bool:
    if not request:
        return False
    return bool(relevant_tags(request.context).intersection(_VEGETARIAN_CONTEXT_TERMS))


def _wants_seafood(request: PlanRequest | None) -> bool:
    if not request:
        return False
    tags = relevant_tags(request.context)
    if tags.intersection(_SEAFOOD_CONTEXT_TERMS):
        return True
    return str(_policy_get(request.intent_policy, "primary_intent") or "") == "beach"


def _looks_vegetarian_dining(place: Place) -> bool:
    if set(place.tags).intersection(_VEGETARIAN_TAGS):
        return True
    return bool(_VEGETARIAN_NAME_RE.search(_place_name_key(place)))


def _looks_seafood_dining(place: Place) -> bool:
    if set(place.tags).intersection(_SEAFOOD_TAGS):
        return True
    return bool(_SEAFOOD_NAME_RE.search(_place_name_key(place)))


def _dining_preference_score(place: Place, request: PlanRequest | None) -> int:
    if not request or not _is_dining_place(place):
        return 0
    score = 0
    if _wants_seafood(request):
        if _looks_seafood_dining(place):
            score += 20
        if _looks_vegetarian_dining(place) and not _wants_vegetarian(request):
            score -= 40
    if _wants_vegetarian(request) and _looks_vegetarian_dining(place):
        score += 20
    return score


def _dining_budget_cap(request: PlanRequest, leftover: int) -> int:
    if not budget_applies(request):
        return UNCONSTRAINED_BUDGET
    return max(leftover, 0)


def _meals_per_day(thoi_luong: str, request: PlanRequest | None = None) -> tuple[str, ...]:
    if thoi_luong == "vai_gio":
        meals: tuple[str, ...] = ("trua",)
    elif thoi_luong == "nua_ngay":
        meals = ("trua",)
    else:
        meals = ("trua", "toi")
    if not request:
        return meals
    timing = _trip_timing(request)
    start = timing.start_hour * 60 + timing.start_minute
    end = start + timing.max_minutes
    if timing.max_minutes <= 180:
        return ()
    if timing.days >= 8:
        meals = ("trua",)
        kept = []
        start = timing.start_hour * 60 + timing.start_minute
        end = start + timing.max_minutes
        if start < 14 * 60 and end > 11 * 60:
            kept.append("trua")
        return tuple(kept)
    kept: list[str] = []
    if "trua" in meals and start < 14 * 60 and end > 11 * 60:
        kept.append("trua")
    if "toi" in meals and start < 21 * 60 and end > 17 * 60 + 30:
        kept.append("toi")
    return tuple(kept)


def _meal_labels(locale: str) -> dict[str, str]:
    return MEAL_LABELS.get(locale, MEAL_LABELS["en"])


def _sight_candidates(candidates: list[Place], request: PlanRequest | None = None) -> list[Place]:
    if request and _is_food_trip(request):
        foodish = [
            place
            for place in candidates
            if _is_dining_place(place)
            or place.kind in {"cho", "cafe"}
            or "am_thuc" in place.tags
        ]
        if len(foodish) >= 2:
            return foodish
    allow_cafe = bool(request and _wants_coffee(request))
    sights = [
        place
        for place in candidates
        if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
    ]
    if sights:
        return sights
    non_dining = [place for place in candidates if not _is_dining_place(place)]
    attractions = [place for place in non_dining if place.kind in SIGHT_KINDS]
    if attractions:
        return attractions
    if allow_cafe:
        return non_dining or candidates
    without_cafe = [place for place in non_dining if place.kind != "cafe"]
    return without_cafe or non_dining or candidates


def _intent_policy_sets(request: PlanRequest) -> tuple[set[str], set[str]]:
    policy = request.intent_policy
    if not policy:
        return set(), set()
    if isinstance(policy, dict):
        return set(policy.get("allowed_place_themes") or []), set(policy.get("avoid_place_themes") or [])
    return set(policy.allowed_place_themes), set(policy.avoid_place_themes)


def _is_requested_place(place: Place, destination_label: str | None, context: str) -> bool:
    dest_key = _ascii_fold(destination_label or "").casefold()
    name_key = _place_name_key(place)
    if dest_key and dest_key in name_key:
        return True
    context_key = " ".join(_ascii_fold(context).split())
    return bool(name_key and " " in name_key and name_key in context_key)


def _famous_first_places(places: list[Place], request: PlanRequest) -> list[Place]:
    highlight_ids = {place.id for place in _highlight_places(request, set())}
    return sorted(
        places,
        key=lambda place: (
            0 if place.id in highlight_ids else 1,
            famous_priority(place) or 9,
            0 if is_famous_place(place) or _is_iconic_place(place) else 1,
            -_tourism_quality_score(place),
            place.id,
        ),
    )


def _pinned_destination_highlights(sights: list[Place], request: PlanRequest) -> list[Place]:
    highlight_ids = {place.id for place in _highlight_places(request, set())}
    return [place for place in sights if place.id in highlight_ids]


def _apply_intent_policy_to_sights(sights: list[Place], request: PlanRequest, sight_count: int) -> tuple[list[Place], dict | None]:
    allowed, avoided = _intent_policy_sets(request)
    pinned = _pinned_destination_highlights(sights, request)
    pinned_ids = {place.id for place in pinned}
    if not allowed and not avoided:
        return _dedupe_places(pinned + sights), None
    _, _, destination_label = _destination_context(request)
    named = []
    if not _is_food_trip(request):
        named = [place for place in sights if _is_requested_place(place, destination_label, request.context)]
    named_ids = {place.id for place in named}
    strict = [
        place
        for place in sights
        if place.id not in named_ids and place.id not in pinned_ids and place_matches_policy(place, allowed, avoided)
    ]
    min_needed = min(sight_count, 2)
    if named or pinned or len(strict) >= min_needed:
        ranked = sorted(
            strict,
            key=lambda place: (
                -place_policy_score(place, allowed, avoided),
                -_dining_preference_score(place, request),
                -_tourism_quality_score(place),
                place.id,
            ),
        )
        filtered = _dedupe_places(pinned + named + ranked)
        return filtered, {
            "ap_dung": True,
            "che_do": "strict_filter",
            "allowed_place_themes": sorted(allowed),
            "avoid_place_themes": sorted(avoided),
            "so_ung_vien_truoc": len(sights),
            "so_ung_vien_sau": len(filtered),
        }
    ranked = sorted(
        sights,
        key=lambda place: (
            -place_policy_score(place, allowed, avoided),
            -_dining_preference_score(place, request),
            -_tourism_quality_score(place),
            place.id,
        ),
    )
    filtered = _dedupe_places(pinned + ranked)
    return filtered, {
        "ap_dung": True,
        "che_do": "soft_rank_not_enough_strict_matches",
        "allowed_place_themes": sorted(allowed),
        "avoid_place_themes": sorted(avoided),
        "so_ung_vien_truoc": len(sights),
        "so_ung_vien_sau": len(strict),
    }


def _anchor_for_places(places: list[Place], fallback: tuple[float, float]) -> tuple[float, float]:
    if not places:
        return fallback
    return (
        sum(place.lat for place in places) / len(places),
        sum(place.lng for place in places) / len(places),
    )


def _lodging_anchor(request: PlanRequest) -> tuple[float, float]:
    if request.noi_luu_tru:
        return (request.noi_luu_tru.lat, request.noi_luu_tru.lng)
    return (request.location.lat, request.location.lng)


def _lodging_context(request: PlanRequest) -> dict:
    anchor = _lodging_anchor(request)
    return {
        "co_noi_luu_tru": request.noi_luu_tru is not None,
        "ten": request.ten_noi_luu_tru,
        "toa_do": {"lat": anchor[0], "lng": anchor[1]},
        "nguon": "plan_request.noi_luu_tru" if request.noi_luu_tru else "plan_request.location",
        "rang_buoc": [
            "Dùng nơi lưu trú làm điểm neo xuất phát/kết thúc khi người dùng cung cấp.",
            "Chọn bữa ăn và điểm phụ gần nơi lưu trú/cụm điểm trong ngày để giảm vòng di chuyển.",
        ],
    }


def _near_anchor(place: Place, anchor: tuple[float, float], radius_km: float = DESTINATION_RADIUS_KM) -> bool:
    return haversine_km(anchor[0], anchor[1], place.lat, place.lng) <= radius_km


@lru_cache(maxsize=512)
def _places_near(lat: float, lng: float, radius_km: float, catalog_size: int) -> tuple[Place, ...]:
    return tuple(
        place
        for place in PLACES
        if haversine_km(lat, lng, place.lat, place.lng) <= radius_km
    )


def _nearby_places(anchor: tuple[float, float], radius_km: float = DESTINATION_RADIUS_KM) -> tuple[Place, ...]:
    return _places_near(round(anchor[0], 3), round(anchor[1], 3), radius_km, len(PLACES))


def _open_for_meal(place: Place, meal_type: str) -> bool:
    open_hour, close_hour = _effective_hours(place)
    start_h, start_m, end_h, end_m = MEAL_WINDOWS[meal_type]
    window_start = start_h * 60 + start_m
    window_end = end_h * 60 + end_m
    open_minutes = open_hour * 60
    close_minutes = 24 * 60 if close_hour >= 24 else close_hour * 60
    overlap = min(window_end, close_minutes) - max(window_start, open_minutes)
    return overlap >= MEAL_DURATION.get(meal_type, MIN_VISIT_MINUTES)


def _choose_meal_place(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    meal_type: str,
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    food_profile = INTENT_PROFILES["food"]
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not _name_taken(place, excluded_names)
        and _near_anchor(place, anchor)
        and _is_dining_place(place)
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and _in_requested_destination(place, request)
        and _open_for_meal(place, meal_type)
    ]
    if not pool:
        return None
    preferred = pool
    if _wants_seafood(request) and not _wants_vegetarian(request):
        without_chay = [place for place in pool if not _looks_vegetarian_dining(place)]
        seafood = [place for place in without_chay if _looks_seafood_dining(place)]
        preferred = seafood or without_chay or pool
    elif _wants_vegetarian(request):
        vegetarian = [place for place in pool if _looks_vegetarian_dining(place)]
        preferred = vegetarian or pool
    ranked = sorted(
        preferred,
        key=lambda place: (
            -_dining_preference_score(place, request),
            -int(place.source == "curated"),
            -_intent_score(place, [food_profile]),
            -len({"am_thuc", "an_vat", "local", "vietnamese", "hai_san"}.intersection(place.tags)),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            place.cost,
            _place_seed(place, seed),
        ),
    )
    return ranked[0]


def _choose_extra_sight(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    candidates = _extra_sight_candidates(
        request, excluded, anchor, seed, budget_per_person, excluded_names
    )
    return candidates[0] if candidates else None


def _extra_sight_candidates(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> list[Place]:
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not _name_taken(place, excluded_names)
        and _near_anchor(place, anchor)
        and place.kind in SIGHT_KINDS
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and is_routable(place)
        and _in_requested_destination(place, request)
        and place.open_hour <= 16
        and place.close_hour >= 12
    ]
    if not pool:
        return []
    return sorted(
        pool,
        key=lambda place: (
            -_tourism_quality_score(place),
            -int(place.source == "curated"),
            -int(place.kind in {"dia_danh", "bao_tang"}),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _choose_refreshment(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not _name_taken(place, excluded_names)
        and _near_anchor(place, anchor)
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and _in_requested_destination(place, request)
        and place.open_hour <= 9
        and place.close_hour >= 11
    ]
    if not pool:
        pool = [
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not _name_taken(place, excluded_names)
            and _near_anchor(place, anchor)
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
            and not _mentions_other_destination(place, destination_label)
            and not _looks_closed(place)
            and _in_requested_destination(place, request)
        ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _sight_total(count: int, meals_total: int, thoi_luong: str) -> int:
    if thoi_luong == "vai_gio":
        return 2
    # Reserve room for midday rest + evening stop on full days.
    reserve = 2 if thoi_luong in {"ca_ngay", "nhieu_ngay"} else 0
    return max(2, count - meals_total - reserve)


def _min_plan_slots(thoi_luong: str, days: int | None = None) -> int:
    _, _, known_days = LIMITS[thoi_luong]
    actual_days = days if days is not None else known_days
    if thoi_luong == "vai_gio":
        return 1
    if actual_days <= 1:
        return 4
    if actual_days == 2:
        return 6
    return actual_days


def _max_plan_slots(thoi_luong: str, days: int | None = None) -> int:
    count, _, known_days = LIMITS[thoi_luong]
    actual_days = days if days is not None else known_days
    if actual_days > known_days or actual_days > 1:
        return max(count + known_days * 3, 8 * actual_days)
    return count + known_days * 3


def _max_day_slots(thoi_luong: str, days: int, max_minutes: int) -> int:
    """Keep each day full but paced; long trips must not dump the catalog into day 1."""
    if max_minutes <= 90:
        return 3
    if max_minutes <= 240 or thoi_luong == "vai_gio":
        return 5
    if days <= 1:
        return 9
    if days <= 4:
        return 8
    if days <= 7:
        return 6
    return 6


def _still_open_in_evening(place: Place) -> bool:
    """True when a visit can still start after dinner inside opening hours."""
    if _is_dining_place(place) or _is_morning_only(place):
        return False
    if _is_major_mountain_complex(place) and not _is_evening_place(place):
        return False
    open_hour, close_hour = _effective_hours(place)
    close_minutes = 24 * 60 if close_hour >= 24 else close_hour * 60
    start_h, start_m, end_h, end_m = MEAL_WINDOWS["dem"]
    window_start = start_h * 60 + start_m
    window_end = end_h * 60 + end_m
    overlap = min(window_end, close_minutes) - max(window_start, open_hour * 60)
    return overlap >= MIN_VISIT_MINUTES


def _is_evening_place(place: Place) -> bool:
    """True only for stops that belong after dinner, not dual-use daytime icons."""
    open_hour, _ = _effective_hours(place)
    if place.id in EVENING_PLACE_IDS:
        return True
    if open_hour >= 17:
        return True
    return _is_night_market(place)


def _is_night_market(place: Place) -> bool:
    """Recognize explicit tags and untagged provider records named as night markets."""
    if {"cho_dem", "night_market"}.intersection(place.tags):
        return True
    if place.kind != "cho":
        return False
    name_key = _place_name_key(place)
    return "cho dem" in name_key or "night market" in name_key


def _choose_midday_rest(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    _, _, destination_label = _destination_context(request)
    """Quiet cafe/snack stop to bridge the hot early afternoon."""
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not _name_taken(place, excluded_names)
        and _near_anchor(place, anchor)
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and place.open_hour <= 12
        and place.close_hour >= 15
        and is_routable(place)
        and _in_requested_destination(place, request)
    ]
    if not pool:
        pool = [
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not _name_taken(place, excluded_names)
            and _near_anchor(place, anchor)
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
            and not _mentions_other_destination(place, destination_label)
            and not _looks_closed(place)
            and is_routable(place)
            and _in_requested_destination(place, request)
        ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            place.cost,
            _place_seed(place, seed),
        ),
    )


def _choose_evening_place(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    by_id = {place.id: place for place in PLACES}
    _, _, destination_label = _destination_context(request)

    def pick(ids: tuple[str, ...]) -> Place | None:
        for place_id in ids:
            place = by_id.get(place_id)
            if (
                place
                and place.id not in excluded
                and not _name_taken(place, excluded_names)
                and _near_anchor(place, anchor)
                and place.cost <= budget_per_person
                and is_routable(place)
                and _in_requested_destination(place, request)
                and (_is_evening_place(place) or _still_open_in_evening(place))
            ):
                return place
        return None

    return pick(EVENING_PLACE_IDS) or pick(EVENING_FALLBACK_IDS) or min(
        (
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not _name_taken(place, excluded_names)
            and _near_anchor(place, anchor)
            and not _is_dining_place(place)
            and not _looks_like_non_travel_business(place)
            and not _mentions_other_destination(place, destination_label)
            and not _looks_closed(place)
            and place.cost <= budget_per_person
            and is_routable(place)
            and _in_requested_destination(place, request)
            and (_is_evening_place(place) or _still_open_in_evening(place))
        ),
        default=None,
        key=lambda place: (
            0 if _is_evening_place(place) else 1,
            0 if {"nightlife", "cho_dem", "night_market", "di_bo", "pho_co"}.intersection(place.tags) else 1,
            -_effective_hours(place)[1],
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _build_day_route(
    request: PlanRequest,
    day_sights: list[Place],
    day_meals: list[tuple[str, Place]],
    used: set[str],
    remaining_budget: int,
    seed: int,
    used_names: set[str],
) -> list[tuple[Place, str | None]]:
    if request.thoi_luong != "vai_gio":
        route = _interleave_meals(day_sights, day_meals)
        timing = _trip_timing(request)
        anchor = _anchor_for_places(day_sights, _lodging_anchor(request))
        window_end = timing.start_hour * 60 + timing.start_minute + timing.max_minutes
        lunch_at = next((i for i, (_, meal) in enumerate(route) if meal == "trua"), None)
        if request.thoi_luong in {"ca_ngay", "nhieu_ngay"} and remaining_budget > 0 and lunch_at is not None and window_end > 13 * 60:
            rest = _choose_midday_rest(request, used, anchor, seed, remaining_budget, used_names)
            if rest:
                route.insert(lunch_at + 1, (rest, "nghi"))
                used.add(rest.id)
                used_names.update(_place_name_keys(rest))
                remaining_budget -= rest.cost
            # Keep one more afternoon attraction when the day still looks thin.
            thin_day = len(day_sights) + len(day_meals) <= (3 if _is_long_trip(timing.days) else 5)
            if thin_day and not _is_mountain_destination(request):
                extra = _choose_extra_sight(request, used, anchor, seed + 1, remaining_budget, used_names)
                if extra:
                    insert_at = lunch_at + (2 if rest else 1)
                    route.insert(insert_at, (extra, None))
                    used.add(extra.id)
                    used_names.update(_place_name_keys(extra))
                    remaining_budget -= extra.cost
        # Only add an evening stop when the stated window still covers evening.
        if request.thoi_luong in {"ca_ngay", "nhieu_ngay"} and window_end > 17 * 60 + 30:
            has_evening = any(meal_type == "dem" or (meal_type is None and _is_evening_place(place)) for place, meal_type in route)
            if not has_evening:
                evening = _choose_evening_place(
                    request, used, anchor, seed + 3, max(remaining_budget, 0), used_names
                )
                if evening:
                    dinner_at = next((i for i, (_, meal) in enumerate(route) if meal == "toi"), None)
                    insert_at = (dinner_at + 1) if dinner_at is not None else len(route)
                    route.insert(insert_at, (evening, "dem"))
                    used.add(evening.id)
                    used_names.update(_place_name_keys(evening))
        return route
    timing = _trip_timing(request)
    sight_cap = 2 if timing.max_minutes <= 90 else 3 if timing.max_minutes <= 150 else min(4, max(2, timing.max_minutes // 45))
    if _is_mountain_destination(request) and timing.max_minutes > 180:
        sight_cap = min(2, sight_cap)
    sights = day_sights[:sight_cap]
    anchor = _anchor_for_places(sights, _lodging_anchor(request))
    refresh = None
    if _wants_coffee(request) or (request.thoi_luong == "vai_gio" and timing.max_minutes >= 150):
        refresh = _choose_refreshment(request, used, anchor, seed, remaining_budget, used_names)
        if refresh:
            used.add(refresh.id)
            used_names.update(_place_name_keys(refresh))
    if not day_meals:
        return [(place, None) for place in sights]
    lunch_type, lunch_place = day_meals[0]
    route: list[tuple[Place, str | None]] = [(place, None) for place in sights]
    if refresh:
        insert_at = 1 if route else 0
        route.insert(insert_at, (refresh, None))
    route.append((lunch_place, lunch_type))
    return route


def _interleave_meals(
    sights: list[Place],
    meals: list[tuple[str, Place]],
) -> list[tuple[Place, str | None]]:
    """Seed order: morning → lunch → afternoon → dinner → evening."""
    if not meals:
        return [(place, None) for place in sights]
    morning = [place for place in sights if _is_morning_only(place)]
    evening = [place for place in sights if place not in morning and _is_evening_place(place)]
    outdoor = [
        place
        for place in sights
        if place not in morning and place not in evening and _is_outdoor_place(place)
    ]
    flexible = [
        place
        for place in sights
        if place not in morning and place not in evening and place not in outdoor
    ]
    lunch = next((item for item in meals if item[0] == "trua"), None)
    dinner = next((item for item in meals if item[0] == "toi"), None)
    other_meals = [item for item in meals if item is not lunch and item is not dinner]
    morning_flex_count = (len(flexible) + 1) // 2
    morning_flex = flexible[:morning_flex_count]
    afternoon_flex = flexible[morning_flex_count:]
    route: list[tuple[Place, str | None]] = [(place, None) for place in [*morning, *morning_flex]]
    if lunch:
        route.append((lunch[1], lunch[0]))
    route.extend((place, None) for place in [*outdoor, *afternoon_flex])
    if dinner:
        route.append((dinner[1], dinner[0]))
    route.extend((place, None) for place in evening)
    for meal, place in other_meals:
        route.append((place, meal))
    return route


def _pick_day_meals(
    request: PlanRequest,
    day_sights: list[Place],
    used: set[str],
    budget_per_person: int,
    seed: int,
    used_names: set[str],
) -> list[tuple[str, Place]]:
    anchor = _anchor_for_places(day_sights, _lodging_anchor(request))
    meals: list[tuple[str, Place]] = []
    remaining = _dining_budget_cap(request, budget_per_person)
    dining_ids = {place.id for place in PLACES if _is_dining_place(place)}
    dining_used = used & dining_ids
    for meal_type in _meals_per_day(request.thoi_luong, request):
        place = _choose_meal_place(request, used, anchor, meal_type, seed, remaining, used_names)
        if not place:
            place = _choose_meal_place(
                request, used - dining_used, anchor, meal_type, seed, remaining, None
            )
        if not place:
            continue
        meals.append((meal_type, place))
        used.add(place.id)
        used_names.update(_place_name_keys(place))
        dining_used.add(place.id)
        remaining -= place.cost
    return meals


def _guidance(place: Place) -> VisitGuidance | None:
    return guidance_for(place.id, _place_name_key(place))


def _effective_hours(place: Place) -> tuple[int, int]:
    tip = _guidance(place)
    if tip and tip.open_hour is not None and tip.close_hour is not None:
        return tip.open_hour, tip.close_hour
    known = KNOWN_HOURS_BY_NAME.get(_place_name_key(place))
    if known:
        return known
    open_hour = max(0, min(23, place.open_hour))
    close_hour = max(open_hour + 1, min(24, place.close_hour))
    return open_hour, close_hour


def _place_folded_name(place: Place) -> str:
    return _ascii_fold(place.name)


def _is_mountain_transit(place: Place) -> bool:
    folded = _place_folded_name(place)
    return any(hint in folded for hint in _MOUNTAIN_TRANSIT_HINTS)


def _is_major_mountain_complex(place: Place) -> bool:
    if _is_mountain_transit(place):
        return False
    folded = _place_folded_name(place)
    if place.kind == "nui":
        return True
    return any(hint in folded for hint in _MOUNTAIN_COMPLEX_HINTS)


def _is_mountain_experience(place: Place) -> bool:
    if _is_mountain_transit(place):
        return False
    if _is_major_mountain_complex(place):
        return True
    tags = set(place.tags)
    if place.kind == "nui":
        return True
    return bool({"nui", "trekking", "peak"}.intersection(tags))


def _is_mountain_destination(request: PlanRequest) -> bool:
    if _is_food_trip(request):
        return False
    purpose = _policy_get(request.intent_policy, "primary_intent") if request.intent_policy else None
    if purpose == "mountain":
        return True
    _, _, label = _destination_context(request)
    key = _ascii_fold(label or "")
    return key in _MOUNTAIN_DESTINATION_KEYS or any(hint in key for hint in ("yen tu", "nui "))


def _is_outdoor_place(place: Place) -> bool:
    tags = set(place.tags)
    if "nightlife" in tags or "cho_dem" in tags or _effective_hours(place)[0] >= 17:
        return False
    tip = _guidance(place)
    if tip and tip.alt_preferred and tip.preferred[2] <= 11:
        return True
    return (
        place.kind == "cong_vien"
        or bool({"ngoai_troi", "ho_tay", "ho_guom", "view_dep"}.intersection(tags))
        or (place.kind == "dia_danh" and "di_bo" in tags and "pho_co" not in tags)
    )


def _weather_discourages_midday_outdoor(weather: dict | None) -> bool:
    if not weather:
        return False
    temperature = weather.get("nhiet_do_max")
    rain = weather.get("xac_suat_mua")
    return (
        isinstance(temperature, (int, float)) and temperature >= 33
    ) or (
        isinstance(rain, (int, float)) and rain >= 60
    )


def _is_morning_only(place: Place) -> bool:
    open_hour, close_hour = _effective_hours(place)
    tip = _guidance(place)
    if tip and tip.preferred[2] <= 11 and tip.alt_preferred is None:
        return True
    if close_hour <= 12:
        return True
    return bool({"lang_bac", "ho_chi_minh"}.intersection(place.tags))


def _preferred_window(place: Place, meal_type: str | None) -> tuple[int, int, int, int]:
    """Return preferred (start_h, start_m, end_h, end_m) local visit window."""
    open_hour, close_hour = _effective_hours(place)
    if _is_night_market(place):
        return max(open_hour, 18), 0, close_hour, 0
    if meal_type:
        start_h, start_m, end_h, end_m = MEAL_WINDOWS[meal_type]
        return start_h, start_m, end_h, end_m
    tip = _guidance(place)
    if tip:
        return tip.preferred
    tags = set(place.tags)
    if "bai_bien" in tags or "beach" in tags or "sunset" in tags:
        # Realistic beach sunset window
        return 16, 30, 18, 30
    if _is_morning_only(place):
        return open_hour, 0, close_hour, 0
    if "nightlife" in tags or "cho_dem" in tags or open_hour >= 17:
        return max(open_hour, 18), 0, close_hour, 0
    if _is_mountain_experience(place):
        return max(open_hour, 7), 0, min(close_hour, 17), 0
    if place.kind == "bao_tang" or {"museum", "van_hoa", "lich_su", "heritage"}.intersection(tags):
        return max(open_hour, 8), 30, min(close_hour, 17), 0
    if _is_outdoor_place(place):
        return 7, 0, 10, 0
    if place.kind == "cafe":
        return max(open_hour, 9), 0, min(close_hour, 17), 0
    return open_hour, 0, close_hour, 0


def _pick_visit_window(
    place: Place,
    meal_type: str | None,
    arrive: datetime,
) -> tuple[int, int, int, int]:
    """Choose primary or alternate preferred window closest to arrival."""
    if _is_night_market(place):
        return _preferred_window(place, meal_type)
    if meal_type:
        return _preferred_window(place, meal_type)
    tip = _guidance(place)
    primary = _preferred_window(place, None)
    if not tip or not tip.alt_preferred:
        return primary
    arrive_hour = arrive.hour + arrive.minute / 60
    windows = [primary, tip.alt_preferred]

    def window_score(window: tuple[int, int, int, int]) -> float:
        start = window[0] + window[1] / 60
        end = window[2] + window[3] / 60
        if start <= arrive_hour <= end:
            return 0
        if arrive_hour < start:
            return start - arrive_hour
        return arrive_hour - end + 8

    return min(windows, key=window_score)


def _outdoor_afternoon_window(base: datetime) -> tuple[datetime, datetime]:
    return _at_clock(base, 14, 0), _at_clock(base, 17, 45)


def _visit_minutes_for(
    place: Place,
    meal_type: str | None,
    request: PlanRequest,
    duration_override: int | None = None,
) -> int:
    short_window = request.thoi_luong == "vai_gio" or _trip_timing(request).max_minutes <= 180
    if meal_type:
        minutes = min(MEAL_DURATION[meal_type], place.duration_min, 90)
        if short_window:
            minutes = min(minutes, 45)
        return max(MIN_VISIT_MINUTES, minutes)

    # Specific realistic durations for major landmark categories
    folded_name = _ascii_fold(place.name)
    if _is_mountain_transit(place):
        minutes = min(60, max(40, place.duration_min or 45))
    elif any(k in folded_name for k in ["ba na hills", "vinwonders", "sun world", "fansipan"]):
        minutes = 240
    elif _is_major_mountain_complex(place):
        tip = _guidance(place)
        minutes = max(240, tip.duration_min if tip and tip.duration_min else 0, place.duration_min or 0)
        minutes = min(360, minutes)
    elif _is_mountain_experience(place):
        tip = _guidance(place)
        minutes = max(180, tip.duration_min if tip and tip.duration_min else 0, place.duration_min or 0)
        minutes = min(300, minutes)
    elif place.kind == "bao_tang" or any(k in folded_name for k in ["dai noi", "dinh doc lap", "hoang thanh"]):
        minutes = max(90, place.duration_min)
    elif place.kind in {"cau", "tuong_dai"} or any(k in folded_name for k in ["cau rong", "cau vang", "cot co"]):
        minutes = 35
    else:
        tip = _guidance(place)
        minutes = tip.duration_min if tip and tip.duration_min else place.duration_min
    if duration_override and not meal_type:
        minutes = max(MIN_VISIT_MINUTES, min(480, int(duration_override)))
        if _is_major_mountain_complex(place):
            minutes = max(180, minutes)
        elif _is_mountain_experience(place):
            minutes = max(120, minutes)
    if short_window and minutes < 180 and not _is_mountain_experience(place):
        window_minutes = _trip_timing(request).max_minutes
        if window_minutes <= 90:
            minutes = min(minutes, 35)
        elif window_minutes <= 150:
            minutes = min(max(minutes, 40), 50)
        else:
            minutes = min(max(minutes, 45), 70)
        if place.kind == "cafe":
            minutes = min(minutes, 45 if window_minutes > 90 else 30)
    return max(MIN_VISIT_MINUTES, minutes)


def _duration_estimate_for(place: Place, meal_type: str | None, planned_minutes: int | None = None) -> dict:
    if meal_type:
        base = MEAL_DURATION.get(meal_type, place.duration_min or 60)
        lower, upper = max(30, base - 15), min(120, base + 15)
        source = "meal_window_policy"
        confidence = "medium"
        estimated = True
    else:
        tip = _guidance(place)
        if tip and tip.duration_min:
            lower = max(20, tip.duration_min - 15)
            upper = tip.duration_min + 30
            source = tip.source or "official_or_guide_guidance"
            confidence = "high"
            estimated = False
        elif place.duration_min > 0:
            lower = max(20, round(place.duration_min * 0.8))
            upper = max(lower, round(place.duration_min * 1.25))
            source = place.source
            confidence = "medium" if place.source not in {"local_seed", "curated"} else "low"
            estimated = place.source in {"local_seed", "curated"}
        else:
            lower, upper = DURATION_FALLBACKS.get(place.kind, (45, 90))
            source = "fallback_by_place_kind"
            confidence = "low"
            estimated = True
    if planned_minutes is not None:
        lower = min(lower, planned_minutes)
        upper = max(upper, planned_minutes)
    return {
        "toi_thieu_phut": lower,
        "toi_da_phut": upper,
        "ke_hoach_phut": planned_minutes,
        "do_tin_cay": confidence,
        "nguon": source,
        "uoc_luong": estimated,
        "ghi_chu": "AI khong tu sinh thoi luong; gia tri nay lay tu huong dan, catalog hoac fallback co cau truc.",
    }


def _slot_duration_minutes(slot: dict) -> int:
    return max(0, _parse_slot_clock(slot["ket_thuc"]) - _parse_slot_clock(slot["bat_dau"]))


def _traffic_peak_for_clock(clock: str) -> dict:
    minute = _parse_slot_clock(clock)
    for window in VIETNAM_TRAFFIC_PEAK_POLICY["khung_gio"]:
        start = _parse_slot_clock(window["tu"])
        end = _parse_slot_clock(window["den"])
        if start <= minute <= end:
            return {
                "trong_gio_cao_diem": True,
                "khung": window["ten"],
                "nguon": VIETNAM_TRAFFIC_PEAK_POLICY["nguon"],
                "ghi_chu": VIETNAM_TRAFFIC_PEAK_POLICY["ghi_chu"],
            }
    return {
        "trong_gio_cao_diem": False,
        "khung": None,
        "nguon": VIETNAM_TRAFFIC_PEAK_POLICY["nguon"],
        "ghi_chu": VIETNAM_TRAFFIC_PEAK_POLICY["ghi_chu"],
    }


def _attach_evidence(plan: dict, request: PlanRequest, places: tuple[Place, ...]) -> None:
    by_id = {place.id: place for place in places}
    decision_log: list[dict] = []
    holiday = (
        plan.get("tieu_chi_thoi_diem", {}).get("lich_nghi_le")
        if isinstance(plan.get("tieu_chi_thoi_diem"), dict)
        else None
    )
    holiday_status = _holiday_hours_status(holiday if isinstance(holiday, dict) else None)
    for day in plan.get("ngay", []):
        previous: Place | None = None
        for slot in day.get("khoang_gio", []):
            place = by_id.get(slot.get("dia_diem_id"))
            if not place:
                continue
            planned_minutes = _slot_duration_minutes(slot)
            duration = _duration_estimate_for(place, slot.get("bua_an"), planned_minutes)
            slot["thoi_luong"] = duration
            open_hour, close_hour = _effective_hours(place)
            guidance = _guidance(place)
            slot["gio_mo_cua"] = {
                "mo": f"{open_hour:02d}:00",
                "dong": f"{close_hour:02d}:00",
                "nguon": guidance.source if guidance else place.source,
            }
            if holiday_status:
                slot["gio_mo_cua"]["trang_thai_xac_minh"] = holiday_status["trang_thai_xac_minh"]
                slot["gio_mo_cua"]["ghi_chu_ngay_le"] = holiday_status["ghi_chu"]
            travel = None
            if previous:
                estimate = estimate_travel(previous, place)
                travel = estimate.__dict__
                travel["gio_cao_diem"] = _traffic_peak_for_clock(slot["bat_dau"])
                slot["di_chuyen_tu_diem_truoc"] = travel
            reasons = [
                f"khop gio mo cua {open_hour:02d}:00 den {close_hour:02d}:00",
                f"thoi luong ke hoach {planned_minutes} phut trong khoang {duration['toi_thieu_phut']} den {duration['toi_da_phut']} phut",
            ]
            if travel:
                reasons.append(f"di chuyen tam tinh {travel['minutes']} phut tu diem truoc")
                if travel.get("gio_cao_diem", {}).get("trong_gio_cao_diem"):
                    reasons.append("chặng này được đánh dấu rủi ro giờ cao điểm")
            if holiday_status:
                reasons.append("giờ mở cửa ngày lễ/Tết cần xác minh bằng nguồn chính thức trước khi phát hành")
            evidence = slot.get("bang_chung") if isinstance(slot.get("bang_chung"), dict) else {}
            timing_evidence = evidence.get("thoi_diem") if isinstance(evidence.get("thoi_diem"), dict) else {}
            if holiday_status:
                timing_evidence["lich_nghi_le"] = holiday_status
                timing_evidence["gio_mo_cua_hieu_luc"] = {
                    **(timing_evidence.get("gio_mo_cua_hieu_luc") or {}),
                    "trang_thai_xac_minh": holiday_status["trang_thai_xac_minh"],
                }
                evidence["thoi_diem"] = timing_evidence
            evidence.update({
                "dia_diem_id": place.id,
                "nguon_dia_diem": place.source,
                "nguon_url": source_for(place)[0],
                "thoi_luong": duration,
                "di_chuyen": travel,
                "rang_buoc_da_ap": ["gio_mo_cua", "ngan_sach", "khong_trung_dia_diem", "thoi_gian_di_chuyen"],
                "tag_khop": sorted(place.tags),
                "ly_do_luat": reasons,
                "lay_luc": datetime.now(UTC).isoformat(),
            })
            slot["bang_chung"] = evidence
            slot["giai_thich"] = f"{place.name} được chọn vì " + "; ".join(reasons) + "."
            decision_log.append(slot["bang_chung"])
            previous = place
    all_places = [by_id[slot["dia_diem_id"]] for day in plan.get("ngay", []) for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") in by_id]
    plan["bang_chung_quyet_dinh"] = decision_log
    plan["chinh_sach_do_cu_du_lieu"] = DATA_STALENESS_POLICY
    if len(all_places) > TRAVEL_MATRIX_PLACE_CAP:
        plan["bang_thoi_gian_di_chuyen"] = {
            "trang_thai": TRAVEL_ESTIMATE_POLICY["status"],
            "cong_thuc": TRAVEL_ESTIMATE_POLICY["formula"],
            "ghi_chu": TRAVEL_ESTIMATE_POLICY["note"],
            "ma_tran": {
                "_metadata": {
                    "live_provider_status": "skipped_long_trip",
                    "provider": TRAVEL_ESTIMATE_POLICY["live_provider"]["provider"],
                    "error": None,
                    "policy": TRAVEL_ESTIMATE_POLICY["live_provider"],
                    "public_transit_policy": public_transit_policy_status(),
                    "route_calibration": route_calibration_status(),
                    "place_count": len(all_places),
                    "note": "Omitted full pairwise matrix for long itineraries.",
                }
            },
        }
    else:
        plan["bang_thoi_gian_di_chuyen"] = {
            "trang_thai": TRAVEL_ESTIMATE_POLICY["status"],
            "cong_thuc": TRAVEL_ESTIMATE_POLICY["formula"],
            "ghi_chu": TRAVEL_ESTIMATE_POLICY["note"],
            "ma_tran": travel_matrix(all_places),
        }


def _quality_report(plan: dict, request: PlanRequest, trusted_ids: set[str], places: tuple[Place, ...]) -> dict:
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    max_minutes = LIMITS[request.thoi_luong][1] * LIMITS[request.thoi_luong][2]
    scheduled_minutes = sum(_slot_duration_minutes(slot) for slot in slots)
    utilization = round(scheduled_minutes / max_minutes, 2) if max_minutes else 0
    tags = {
        tag
        for tag in relevant_tags(request.context)
        if tag not in {"du", "lich", "di", "choi", "ngay", "nguoi", "toi", "va"}
    }
    by_id = {place.id: place for place in places}
    covered = sorted(
        tag
        for tag in tags
        if any(tag in {ascii_fold(item).replace(" ", "_") for item in by_id.get(slot.get("dia_diem_id"), Place("", "", "", "", 0, 0, 0, 0, ())).tags} for slot in slots)
    )
    feasibility_errors = validate_plan(plan, trusted_ids, request)
    cp_sat = verify_fixed_schedule_with_cp_sat(plan, by_id, travel_minutes)
    day_optimizer_reports = []
    if not _is_long_trip(len(plan.get("ngay") or [])):
        for day in plan.get("ngay", []):
            day_slots = [slot for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") in by_id]
            day_places = [by_id[slot["dia_diem_id"]] for slot in day_slots]
            if not day_places:
                continue
            starts = [_parse_slot_clock(slot["bat_dau"]) for slot in day_slots]
            ends = [_parse_slot_clock(slot["ket_thuc"]) for slot in day_slots]
            durations = {slot["dia_diem_id"]: _slot_duration_minutes(slot) for slot in day_slots}
            scores = {
                slot["dia_diem_id"]: int(
                    ((slot.get("bang_chung") or {}).get("xep_hang") or {}).get("diem_tong", 0) * 100
                )
                for slot in day_slots
            }
            result = optimize_day_schedule_with_cp_sat(
                day_places,
                min(starts) if starts else 8 * 60,
                max(ends) if ends else 22 * 60,
                durations,
                scores,
                travel_minutes,
                min_places=len(day_places),
                max_places=len(day_places),
                budget_per_person=budget_cap(request),
                max_candidates=50,
            )
            day_optimizer_reports.append(
                {
                    "ngay": day.get("thu_tu"),
                    "co_san": result.available,
                    "hop_le": result.feasible,
                    "trang_thai": result.status,
                    "so_ung_vien_xet": result.candidate_count,
                    "selected_ids": list(result.selected_ids),
                    "starts": {key: f"{value // 60:02d}:{value % 60:02d}" for key, value in result.starts.items()},
                    "objective_score": result.objective_score,
                    "chan_bo": list(result.blockers),
                }
            )
    release_blockers = []
    if feasibility_errors:
        release_blockers.extend(feasibility_errors)
    if not cp_sat.available or not cp_sat.feasible:
        release_blockers.extend(f"CP-SAT: {blocker}" for blocker in cp_sat.blockers)
    if utilization < 0.6:
        release_blockers.append("Lich dung duoi 60 phan tram khung gio kha thi")
    holiday = (
        plan.get("tieu_chi_thoi_diem", {}).get("lich_nghi_le")
        if isinstance(plan.get("tieu_chi_thoi_diem"), dict)
        else None
    )
    if isinstance(holiday, dict) and holiday.get("khong_dung_gio_thuong_lam_bang_chung_phat_hanh"):
        release_blockers.append(
            "Tết Nguyên đán: cần giờ mở cửa/lịch hoạt động chính thức theo năm, không dùng giờ thường làm bằng chứng phát hành"
        )
    return {
        "phien_ban_bo_do": "release-readiness-quality-v1",
        "tinh_kha_thi": {"hop_le": not feasibility_errors, "loi": feasibility_errors},
        "do_phu_so_thich": {
            "so_thich_nhan_dien": sorted(tags),
            "so_thich_duoc_phu": covered,
            "ty_le": round(len(covered) / len(tags), 2) if tags else 1.0,
            "ghi_chu": "Do tren tag co san cua dia diem, khong dung diem cua he thong lam dap an chuan.",
        },
        "muc_su_dung_khung_gio": utilization,
        "bo_giai_cp_sat": {
            "thu_vien": "ortools.sat.python.cp_model",
            "vai_tro": "kiem_chung_kha_thi_lich_da_chon",
            "co_san": cp_sat.available,
            "hop_le": cp_sat.feasible,
            "trang_thai": cp_sat.status,
            "so_slot_kiem_tra": cp_sat.checked_slots,
            "objective_minutes": cp_sat.objective_minutes,
            "chan_bo": list(cp_sat.blockers),
        },
        "bo_giai_cp_sat_ngay": {
            "thu_vien": "ortools.sat.python.cp_model",
            "vai_tro": "toi_uu_lai_theo_ngay_voi_time_window_travel_budget_tren_slot_da_chon",
            "gioi_han_hien_tai": "Chạy trên các slot đã chọn để kiểm tra mô hình joint scheduling; chưa thay thế full optimizer 50-100 ứng viên trước phát hành.",
            "ket_qua": day_optimizer_reports,
            "tat_ca_hop_le": bool(day_optimizer_reports) and all(item["hop_le"] for item in day_optimizer_reports),
        },
        "moc_so_sanh_bat_buoc": {
            name: {
                "bat_buoc": True,
                "trang_thai": "required_before_release",
                "chan_phat_hanh_neu_thua": True,
            }
            for name in REQUIRED_BASELINES
        },
        "cong_phat_hanh": {"dat": not release_blockers, "chan_bo": release_blockers},
    }


def _preference_score(
    place: Place,
    meal_type: str | None,
    hour: float,
    weather: dict | None = None,
    solar_context: dict | None = None,
) -> float:
    if _is_night_market(place):
        open_hour, close_hour = _effective_hours(place)
        return 12 if max(open_hour, 18) <= hour < close_hour else -50
    if meal_type:
        preferred = MEAL_PREFERRED_START[meal_type]
        preferred_hour = preferred[0] + preferred[1] / 60
        return 20 - abs(hour - preferred_hour) * 4
    open_hour, close_hour = _effective_hours(place)
    if hour < open_hour or hour >= close_hour:
        return -50
    tip = _guidance(place)
    if tip:
        windows = [tip.preferred] + ([tip.alt_preferred] if tip.alt_preferred else [])
        best = max(
            (
                16 - abs(hour - ((w[0] + w[1] / 60 + w[2] + w[3] / 60) / 2)) * 3
                if (w[0] + w[1] / 60) <= hour <= (w[2] + w[3] / 60)
                else 4 - abs(hour - ((w[0] + w[1] / 60 + w[2] + w[3] / 60) / 2))
            )
            for w in windows
        )
        return best
    if _is_morning_only(place):
        return 15 - abs(hour - 8.5) if hour < 12 else -20
    if _is_outdoor_place(place):
        if _weather_discourages_midday_outdoor(weather) and 11 <= hour < 15:
            return -35
        sunset_minute = (solar_context or {}).get("hoang_hon_phut")
        if _is_sunset_suitable(place) and isinstance(sunset_minute, int):
            sunset_hour = sunset_minute / 60
            sunset_score = 18 - abs(hour - (sunset_hour - 0.75)) * 8
            if sunset_hour - 1.75 <= hour <= sunset_hour + 0.35:
                return max(16, sunset_score)
        if 7 <= hour < 10.5:
            return 14
        if 14 <= hour <= 18:
            return 16
        if 11 <= hour < 14:
            return -10
        return 2
    if "nightlife" in place.tags or "cho_dem" in place.tags:
        return 12 if hour >= 18.5 else -5
    pref_start, pref_m, pref_end, pref_end_m = _preferred_window(place, None)
    pref_from = pref_start + pref_m / 60
    pref_to = pref_end + pref_end_m / 60
    if pref_from <= hour <= pref_to:
        return 12
    center = (pref_from + pref_to) / 2
    return 6 - abs(hour - center)


def _at_clock(base: datetime, hour: int, minute: int = 0) -> datetime:
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _visit_duration_override(details: dict | None) -> int | None:
    if not isinstance(details, dict):
        return None
    raw = details.get("thoi_luong_phut") or details.get("duration_min")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if MIN_VISIT_MINUTES <= value <= 480:
        return value
    return None


def _capped_visit_for_lunch(
    place: Place,
    meal_type: str | None,
    arrive: datetime,
    day_start: datetime,
    remaining: list[tuple[Place, str | None]],
    duration_override: int | None,
    request: PlanRequest,
) -> int | None:
    if meal_type or not any(mt == "trua" for _, mt in remaining):
        return duration_override
    lunch_open = _at_clock(day_start, MEAL_WINDOWS["trua"][0], MEAL_WINDOWS["trua"][1])
    until_lunch = int((lunch_open - arrive).total_seconds() // 60)
    if until_lunch < MIN_VISIT_MINUTES:
        return duration_override
    planned = duration_override if duration_override is not None else _visit_minutes_for(place, None, request)
    if planned <= until_lunch:
        return duration_override
    return until_lunch


def _merge_highlights(
    chosen: list[Place],
    sight_pool: list[Place],
    request: PlanRequest,
    sight_count: int,
) -> list[Place]:
    pinned = _pinned_destination_highlights(sight_pool, request)
    if not pinned or sight_count <= 0:
        return chosen[:sight_count]
    keep = min(len(pinned), max(2, min(4, sight_count)))
    must = pinned[:keep]
    must_ids = {place.id for place in must}
    rest = [place for place in chosen if place.id not in must_ids]
    return _dedupe_places(must + rest)[:sight_count]


def _compute_slot_bounds(
    place: Place,
    meal_type: str | None,
    arrive: datetime,
    day_start: datetime,
    day_end: datetime,
    request: PlanRequest,
    *,
    relax: bool = False,
    weather: dict | None = None,
    duration_override: int | None = None,
) -> tuple[datetime, datetime, int] | None:
    open_hour, close_hour = _effective_hours(place)
    opening = _at_clock(arrive, open_hour, 0)
    closing = _at_clock(arrive, close_hour, 0) if close_hour < 24 else day_end
    pref_start, pref_m, pref_end, pref_end_m = _pick_visit_window(place, meal_type, arrive)
    preferred_open = _at_clock(arrive, pref_start, pref_m)
    preferred_close = _at_clock(arrive, pref_end, pref_end_m)
    visit = _visit_minutes_for(place, meal_type, request, duration_override)
    night_market = _is_night_market(place)

    earliest = max(arrive, opening, day_start)
    if night_market:
        earliest = max(earliest, _at_clock(arrive, 18, 0))
    latest_end = min(closing, preferred_close if meal_type else closing, day_end)
    if meal_type:
        # Meal slots are semantic commitments: lunch stays at lunch time,
        # dinner stays at dinner time. Do not relax them into another daypart.
        earliest = max(earliest, preferred_open)
        latest_end = min(latest_end, preferred_close)
    elif not relax:
        # Keep visits inside researched preferred windows when possible.
        latest_end = min(latest_end, preferred_close, closing, day_end)

    ideal = max(earliest, preferred_open)
    # Outdoor without explicit dual guidance: morning if early, else afternoon cool window.
    tip = _guidance(place)
    adverse_outdoor_weather = _weather_discourages_midday_outdoor(weather)
    if not meal_type and _is_outdoor_place(place) and not _is_mountain_experience(place) and not tip and not relax:
        arrive_hour = arrive.hour + arrive.minute / 60
        cool_start, cool_end = _outdoor_afternoon_window(arrive)
        if adverse_outdoor_weather:
            cool_start = _at_clock(arrive, 15, 0)
        if arrive_hour < 11:
            ideal = max(earliest, _at_clock(arrive, max(open_hour, 7), 0))
            latest_end = min(latest_end, _at_clock(arrive, 10, 30), closing, day_end)
        elif cool_start + timedelta(minutes=MIN_VISIT_MINUTES) <= min(cool_end, closing, day_end):
            if (cool_start - arrive).total_seconds() / 60 > 60:
                cool_start = max(arrive, cool_start)
            ideal = max(earliest, cool_start)
            latest_end = min(cool_end, closing, day_end)
    elif (
        not meal_type
        and adverse_outdoor_weather
        and _is_outdoor_place(place)
        and not _is_mountain_experience(place)
        and 11 <= (arrive.hour + arrive.minute / 60) < 15
    ):
        ideal = max(earliest, _at_clock(arrive, 15, 0))
    idle = (ideal - arrive).total_seconds() / 60
    strict = night_market or bool(meal_type) or (
        (not relax)
        and (
            _is_morning_only(place)
            or (
                _is_outdoor_place(place)
                and not meal_type
                and 11 <= (arrive.hour + arrive.minute / 60) < 14
            )
        )
    )
    if idle > MAX_IDLE_MINUTES and not strict:
        start = earliest
    elif idle > MAX_IDLE_MINUTES and meal_type and arrive >= _at_clock(arrive, pref_start, 0):
        start = earliest
    else:
        start = ideal

    if start + timedelta(minutes=MIN_VISIT_MINUTES) > latest_end:
        if relax and not meal_type and not night_market:
            latest_end = min(closing, day_end)
        if start + timedelta(minutes=MIN_VISIT_MINUTES) > latest_end:
            return None
    available = int((latest_end - start).total_seconds() // 60)
    visit = min(visit, available)
    if visit < MIN_VISIT_MINUTES:
        return None
    end = start + timedelta(minutes=visit)
    for limit in (closing, day_end):
        if end > limit:
            visit = int((limit - start).total_seconds() // 60)
            if visit < MIN_VISIT_MINUTES:
                return None
            end = start + timedelta(minutes=visit)
    if start < opening or end > closing or end > day_end:
        return None
    return start, end, visit


def _effective_slot_cost(place: Place, meal_type: str | None, so_nguoi: int) -> int:
    if place.cost > 0:
        return place.cost * so_nguoi
    kind = getattr(place, "kind", "")
    if meal_type or kind in ("nha_hang", "food", "quan_an", "am_thuc"):
        return 50_000 * so_nguoi
    if kind in ("cafe", "ca_phe", "drinks"):
        return 35_000 * so_nguoi
    if kind in ("bar", "pub", "club"):
        return 100_000 * so_nguoi
    return 0


def _pack_day_slots(
    route_stops: list[tuple[Place, str | None]],
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_details_by_id: dict[str, dict],
    labels: dict[str, str],
    scheduled_ids: set[str],
    scheduled_names: set[str],
    weather: dict | None = None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
    max_slots: int = 10,
) -> tuple[list[dict], int]:
    day_end = day_start + timedelta(minutes=max_minutes)
    remaining = [
        (place, meal_type)
        for place, meal_type in route_stops
        if meal_type
        or (place.id not in scheduled_ids and not _name_taken(place, scheduled_names))
    ]
    slots: list[dict] = []
    total_cost = 0
    cursor = day_start
    previous: Place | None = None
    plan_slot_count = len(scheduled_ids)

    while remaining and plan_slot_count + len(slots) < max_slots:
        best_index = -1
        best_score = -1e9
        best_bounds: tuple[datetime, datetime, int] | None = None
        # Prefer quality constraints first; if nothing fits, relax outdoor windows.
        # Short/afternoon windows rarely overlap morning preferred hours, so relax immediately.
        relax_order = (True,) if max_minutes <= 180 or day_start.hour >= 14 else (False, True)
        for relax in relax_order:
            best_index = -1
            best_score = -1e9
            best_bounds = None
            for index, (place, meal_type) in enumerate(remaining):
                travel = travel_minutes(previous, place) if previous else 0
                arrive = cursor + timedelta(minutes=travel)
                bounds = _compute_slot_bounds(
                    place, meal_type, arrive, day_start, day_end, request, relax=relax, weather=weather,
                    duration_override=_capped_visit_for_lunch(
                        place,
                        meal_type,
                        arrive,
                        day_start,
                        remaining,
                        _visit_duration_override(llm_details_by_id.get(place.id)),
                        request,
                    ),
                )
                if not bounds:
                    continue
                start, end, _visit = bounds
                reserved_meals = [mt for _, mt in remaining if mt in {"trua", "toi", "dem"}]
                reserved_after = [mt for mt in reserved_meals if mt != meal_type] if meal_type in {"trua", "toi", "dem"} else reserved_meals
                room_after = max_slots - plan_slot_count - len(slots) - 1
                if meal_type not in {"trua", "toi", "dem"} and room_after < len(reserved_after):
                    continue
                idle = max(0, (start - arrive).total_seconds() / 60)
                score = _preference_score(
                    place,
                    meal_type,
                    start.hour + start.minute / 60,
                    weather,
                    solar_context,
                )
                score -= idle * 0.6
                score -= travel * 0.15
                if relax:
                    score -= 5
                if any(mt == "trua" for _, mt in remaining):
                    lunch_close = _at_clock(day_start, MEAL_WINDOWS["trua"][2], MEAL_WINDOWS["trua"][3])
                    lunch_ready = _at_clock(day_start, 10, 0)
                    if meal_type == "trua" and cursor >= lunch_ready:
                        score += 80
                    elif meal_type != "trua" and cursor >= lunch_ready and cursor < lunch_close:
                        score -= 80
                if meal_type == "toi" and any(mt == "trua" for _, mt in remaining):
                    score -= 30
                if meal_type == "nghi" and any(mt == "trua" for _, mt in remaining):
                    score -= 40
                # After lunch, finish the midday rest before more sightseeing.
                if any(mt == "nghi" for _, mt in remaining) and meal_type != "nghi":
                    score -= 55
                # Daytime sights before dinner; evening block after dinner.
                if meal_type == "toi" and any(
                    mt is None and not _is_evening_place(place) for place, mt in remaining
                ):
                    score -= 45
                if meal_type == "dem" and any(mt == "toi" for _, mt in remaining):
                    score -= 50
                if meal_type == "dem" and not any(mt == "toi" for _, mt in remaining):
                    score += 90
                if (
                    meal_type is None
                    and _is_evening_place(place)
                    and any(mt == "toi" for _, mt in remaining)
                ):
                    score -= 50
                if score > best_score:
                    best_score = score
                    best_index = index
                    best_bounds = bounds
            if best_index >= 0:
                break
        if best_index < 0 or best_bounds is None:
            break
        place, meal_type = remaining.pop(best_index)
        start, end, _visit = best_bounds
        mo_ta, ghi_chu = _slot_copy(place, request, copy, llm_details_by_id.get(place.id), meal_type, labels)
        image_url, image_credit = image_for(place)
        slot = {
            "bat_dau": start.strftime("%H:%M"),
            "ket_thuc": end.strftime("%H:%M"),
            "dia_diem_id": place.id,
            "ten_dia_diem": place.name,
            "loai": place.kind,
            "khu_vuc": place.area,
            "dia_chi": place.address,
            "google_place_id": place.google_place_id,
            "google_maps_url": place.google_maps_url,
            "mo_ta": mo_ta,
            "chi_phi": place.cost * request.so_nguoi,
            "toa_do": {"lat": place.lat, "lng": place.lng},
            "nguon": place.source,
            "nguon_url": source_for(place)[0],
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
            "bang_chung": _slot_evidence(
                place,
                request,
                start,
                meal_type,
                weather,
                solar_context,
                behavior_profile,
            ),
        }
        if meal_type:
            slot["bua_an"] = meal_type
            slot["nhan_bua"] = labels[meal_type]
        slots.append(slot)
        total_cost += place.cost * request.so_nguoi
        scheduled_ids.add(place.id)
        scheduled_names.update(_place_name_keys(place))
        packed_meals = {(slot.get("dia_diem_id"), slot.get("bua_an")) for slot in slots if slot.get("bua_an")}
        remaining = [
            (item_place, item_meal)
            for item_place, item_meal in remaining
            if (item_meal and (item_place.id, item_meal) not in packed_meals)
            or (not item_meal and not _name_taken(item_place, scheduled_names))
        ]
        cursor = end
        previous = place
    slots = _tighten_day_gaps(slots, day_end)
    return slots, total_cost


def _tighten_day_gaps(slots: list[dict], day_end: datetime) -> list[dict]:
    """Extend visits slightly to avoid long empty holes between stops."""
    if len(slots) < 2:
        return slots
    by_id = {place.id: place for place in PLACES}
    for index in range(len(slots) - 1):
        current = slots[index]
        nxt = slots[index + 1]
        cur_end_h, cur_end_m = map(int, current["ket_thuc"].split(":"))
        next_start_h, next_start_m = map(int, nxt["bat_dau"].split(":"))
        gap = (next_start_h * 60 + next_start_m) - (cur_end_h * 60 + cur_end_m)
        if gap <= 40:
            continue
        place = by_id.get(current["dia_diem_id"])
        next_place = by_id.get(nxt["dia_diem_id"])
        if not place or not next_place or current.get("bua_an"):
            continue
        waiting_for_meal = nxt.get("bua_an") in {"trua", "toi"}
        travel = travel_minutes(place, next_place)
        reserve = max(travel, 12)
        if gap <= reserve + 15:
            continue
        _, close_hour = _effective_hours(place)
        extend = min(gap - reserve - 8, 120 if waiting_for_meal else 90)
        new_end_minutes = cur_end_h * 60 + cur_end_m + extend
        close_minutes = close_hour * 60
        day_end_minutes = day_end.hour * 60 + day_end.minute
        latest_allowed = next_start_h * 60 + next_start_m - reserve
        tip = _guidance(place)
        if tip:
            window_ends = [tip.preferred[2] * 60 + tip.preferred[3]]
            if tip.alt_preferred:
                window_ends.append(tip.alt_preferred[2] * 60 + tip.alt_preferred[3])
            # Cap extension by the preferred window that covers the current visit start.
            start_minutes = cur_end_h * 60 + cur_end_m - 1
            covering = [
                end
                for (window, end) in (
                    (tip.preferred, tip.preferred[2] * 60 + tip.preferred[3]),
                    *(( (tip.alt_preferred, tip.alt_preferred[2] * 60 + tip.alt_preferred[3]),)
                      if tip.alt_preferred else ()),
                )
                if window[0] * 60 + window[1] <= start_minutes <= end + 90
            ]
            if covering:
                latest_allowed = min(latest_allowed, max(covering))
        new_end_minutes = min(new_end_minutes, close_minutes, day_end_minutes, latest_allowed)
        if new_end_minutes <= cur_end_h * 60 + cur_end_m:
            continue
        current["ket_thuc"] = f"{new_end_minutes // 60:02d}:{new_end_minutes % 60:02d}"
    return slots


def _parse_slot_clock(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _extend_last_slot_to_window_end(slots: list[dict], day_end: datetime, max_extend: int = 80) -> list[dict]:
    if not slots:
        return slots
    last = slots[-1]
    end_minutes = _parse_slot_clock(last["ket_thuc"])
    day_end_minutes = day_end.hour * 60 + day_end.minute
    leftover = day_end_minutes - end_minutes
    if leftover < 20:
        return slots
    by_id = {place.id: place for place in PLACES}
    place = by_id.get(last["dia_diem_id"])
    if not place:
        return slots
    _, close_hour = _effective_hours(place)
    new_end = min(end_minutes + min(leftover, max_extend), close_hour * 60, day_end_minutes)
    if new_end >= end_minutes + 10:
        last["ket_thuc"] = f"{new_end // 60:02d}:{new_end % 60:02d}"
    return slots


def _fill_trailing_window(
    slots: list[dict],
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_details_by_id: dict[str, dict],
    labels: dict[str, str],
    scheduled_ids: set[str],
    scheduled_names: set[str],
    used_ids: set[str],
    remaining_budget: int,
    seed: int,
    max_slots: int,
    weather: dict | None = None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
) -> tuple[list[dict], int]:
    if not slots or len(slots) >= max_slots or max_minutes > 240:
        return slots, 0
    day_end = day_start + timedelta(minutes=max_minutes)
    by_id = {place.id: place for place in PLACES}
    extra_cost = 0
    while len(slots) < max_slots:
        last = slots[-1]
        leftover = (day_end.hour * 60 + day_end.minute) - _parse_slot_clock(last["ket_thuc"])
        if leftover < 40:
            break
        prev_place = by_id.get(last["dia_diem_id"])
        if not prev_place:
            break
        cursor_minutes = _parse_slot_clock(last["ket_thuc"])
        cursor = day_start.replace(hour=cursor_minutes // 60, minute=cursor_minutes % 60)
        options = _extra_sight_candidates(
            request,
            used_ids | scheduled_ids,
            (prev_place.lat, prev_place.lng),
            seed + len(slots),
            remaining_budget,
            scheduled_names,
        )[:80]
        added = False
        for option in options:
            travel = travel_minutes(prev_place, option)
            arrive = cursor + timedelta(minutes=travel)
            bounds = _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, relax=True, weather=weather,
                duration_override=_visit_duration_override(llm_details_by_id.get(option.id)),
            )
            if not bounds:
                continue
            start, end, _visit = bounds
            if end > day_end:
                continue
            mo_ta, ghi_chu = _slot_copy(
                option, request, copy, llm_details_by_id.get(option.id), None, labels
            )
            image_url, image_credit = image_for(option)
            slots.append({
                "bat_dau": start.strftime("%H:%M"),
                "ket_thuc": end.strftime("%H:%M"),
                "dia_diem_id": option.id,
                "ten_dia_diem": option.name,
                "loai": option.kind,
                "khu_vuc": option.area,
                "dia_chi": option.address,
                "google_place_id": option.google_place_id,
                "google_maps_url": option.google_maps_url,
                "mo_ta": mo_ta,
                "chi_phi": option.cost * request.so_nguoi,
                "toa_do": {"lat": option.lat, "lng": option.lng},
                "nguon": option.source,
                "nguon_url": source_for(option)[0],
                "anh": image_url,
                "anh_nguon": image_credit,
                "ghi_chu": ghi_chu,
                "bang_chung": _slot_evidence(
                    option, request, start, None, weather, solar_context, behavior_profile
                ),
            })
            scheduled_ids.add(option.id)
            used_ids.add(option.id)
            scheduled_names.update(_place_name_keys(option))
            remaining_budget -= option.cost
            extra_cost += option.cost * request.so_nguoi
            added = True
            break
        if not added:
            break
    return _extend_last_slot_to_window_end(slots, day_end), extra_cost


def _backfill_day_gaps(
    slots: list[dict],
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_details_by_id: dict[str, dict],
    labels: dict[str, str],
    scheduled_ids: set[str],
    scheduled_names: set[str],
    used_ids: set[str],
    remaining_budget: int,
    seed: int,
    max_slots: int,
    weather: dict | None = None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
) -> tuple[list[dict], int]:
    """Insert nearby attractions into long idle gaps between packed stops."""
    if len(slots) < 1 or len(slots) >= max_slots:
        return slots, 0
    day_end = day_start + timedelta(minutes=max_minutes)
    by_id = {place.id: place for place in PLACES}
    extra_cost = 0
    index = 0
    while index < len(slots) - 1 and len(slots) < max_slots:
        current = slots[index]
        nxt = slots[index + 1]
        gap = _parse_slot_clock(nxt["bat_dau"]) - _parse_slot_clock(current["ket_thuc"])
        if gap < MAX_GAP_BEFORE_FILL_MINUTES:
            index += 1
            continue
        prev_place = by_id.get(current["dia_diem_id"])
        next_place = by_id.get(nxt["dia_diem_id"])
        if not prev_place or not next_place:
            index += 1
            continue
        # Do not squeeze a stop into the wait before dinner if gap is mostly meal wait.
        if nxt.get("bua_an") == "toi" and gap < 100:
            index += 1
            continue
        cursor_h, cursor_m = map(int, current["ket_thuc"].split(":"))
        cursor = day_start.replace(hour=cursor_h, minute=cursor_m)
        travel_out = travel_minutes(prev_place, prev_place)  # noop placeholder
        del travel_out
        anchor = (prev_place.lat, prev_place.lng)
        next_start = day_start.replace(
            hour=int(nxt["bat_dau"][:2]), minute=int(nxt["bat_dau"][3:5])
        )
        candidate = None
        bounds = None
        options = _extra_sight_candidates(
            request,
            used_ids | scheduled_ids,
            anchor,
            seed + index + len(slots),
            remaining_budget,
            scheduled_names,
        )[:80]
        for option in options:
            travel = travel_minutes(prev_place, option)
            arrive = cursor + timedelta(minutes=travel)
            option_bounds = _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, weather=weather,
                duration_override=_visit_duration_override(llm_details_by_id.get(option.id)),
            ) or _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, relax=True, weather=weather,
                duration_override=_visit_duration_override(llm_details_by_id.get(option.id)),
            )
            if not option_bounds:
                continue
            _start, option_end, _visit = option_bounds
            if option_end + timedelta(minutes=travel_minutes(option, next_place)) > next_start:
                continue
            candidate = option
            bounds = option_bounds
            break
        if not candidate or not bounds:
            index += 1
            continue
        start, end, _visit = bounds
        mo_ta, ghi_chu = _slot_copy(
            candidate, request, copy, llm_details_by_id.get(candidate.id), None, labels
        )
        image_url, image_credit = image_for(candidate)
        slot = {
            "bat_dau": start.strftime("%H:%M"),
            "ket_thuc": end.strftime("%H:%M"),
            "dia_diem_id": candidate.id,
            "ten_dia_diem": candidate.name,
            "loai": candidate.kind,
            "khu_vuc": candidate.area,
            "dia_chi": candidate.address,
            "google_place_id": candidate.google_place_id,
            "google_maps_url": candidate.google_maps_url,
            "mo_ta": mo_ta,
            "chi_phi": candidate.cost * request.so_nguoi,
            "toa_do": {"lat": candidate.lat, "lng": candidate.lng},
            "nguon": candidate.source,
            "nguon_url": source_for(candidate)[0],
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
            "bang_chung": _slot_evidence(
                candidate,
                request,
                start,
                None,
                weather,
                solar_context,
                behavior_profile,
            ),
        }
        slots.insert(index + 1, slot)
        scheduled_ids.add(candidate.id)
        used_ids.add(candidate.id)
        scheduled_names.update(_place_name_keys(candidate))
        remaining_budget -= candidate.cost
        extra_cost += candidate.cost * request.so_nguoi
        index += 2
    slots = _tighten_day_gaps(slots, day_end)
    slots, trail_cost = _fill_trailing_window(
        slots,
        day_start,
        max_minutes,
        request,
        copy,
        llm_details_by_id,
        labels,
        scheduled_ids,
        scheduled_names,
        used_ids,
        remaining_budget,
        seed,
        max_slots,
        weather,
        solar_context,
        behavior_profile,
    )
    return slots, extra_cost + trail_cost


def _schedule_stop(
    place: Place,
    meal_type: str | None,
    cursor: datetime,
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_detail: dict | None,
    labels: dict[str, str],
) -> tuple[dict | None, datetime, int]:
    day_end = day_start + timedelta(minutes=max_minutes)
    bounds = _compute_slot_bounds(
        place, meal_type, cursor, day_start, day_end, request,
        duration_override=_visit_duration_override(llm_detail),
    )
    if not bounds:
        return None, cursor, 0
    start, end, _visit = bounds
    mo_ta, ghi_chu = _slot_copy(place, request, copy, llm_detail, meal_type, labels)
    image_url, image_credit = image_for(place)
    slot = {
        "bat_dau": start.strftime("%H:%M"),
        "ket_thuc": end.strftime("%H:%M"),
        "dia_diem_id": place.id,
        "ten_dia_diem": place.name,
        "loai": place.kind,
        "khu_vuc": place.area,
        "dia_chi": place.address,
        "google_place_id": place.google_place_id,
        "google_maps_url": place.google_maps_url,
        "mo_ta": mo_ta,
        "chi_phi": place.cost * request.so_nguoi,
        "toa_do": {"lat": place.lat, "lng": place.lng},
        "nguon": place.source,
        "nguon_url": source_for(place)[0],
        "anh": image_url,
        "anh_nguon": image_credit,
        "ghi_chu": ghi_chu,
    }
    if meal_type:
        slot["bua_an"] = meal_type
        slot["nhan_bua"] = labels[meal_type]
    return slot, end, place.cost * request.so_nguoi


def _landmark_destination_labels() -> set[str]:
    return {
        _ascii_fold(str(destination["label"])).casefold()
        for destination in FOCUS_DESTINATIONS.values()
        if destination.get("landmark")
    }


def _is_bare_city_place(place: Place) -> bool:
    """True when the catalogue row is the city itself, not a visit-able stop."""
    name_key = _place_name_key(place)
    if not name_key:
        return False
    if name_key in _landmark_destination_labels():
        return False
    if name_key in BARE_CITY_SPELLINGS:
        return True
    return any(
        name_key == _ascii_fold(str(destination["label"])).casefold()
        for destination in FOCUS_DESTINATIONS.values()
        if not destination.get("landmark")
    )


def _looks_like_non_travel_business(place: Place) -> bool:
    name_key = _place_name_key(place)
    return (
        name_key in GENERIC_PLACE_NAME_KEYS
        or name_key in LOW_VALUE_TOURIST_NAME_KEYS
        or _is_bare_city_place(place)
        or any(hint in name_key for hint in NON_TRAVEL_NAME_HINTS)
    )


def _looks_closed(place: Place) -> bool:
    name_key = _place_name_key(place)
    return any(hint in name_key for hint in CLOSED_PLACE_HINTS)


def _mentions_other_destination(place: Place, current_label: str | None) -> bool:
    if not current_label:
        return False
    name_key = _place_name_key(place)
    area_key = _ascii_fold(place.area).casefold()
    current_key = _ascii_fold(current_label).casefold()
    destination_terms = {
        "Hà Nội": {"ha noi", "hanoi"},
        "TP.HCM": {"tp hcm", "sai gon", "saigon", "thanh pho ho chi minh"},
        "Hạ Long": {"ha long", "halong", "bai chay", "tuan chau", "sung sot", "ti top", "titop", "thien cung", "dau go", "hang luon", "bai tho"},
        "Đà Nẵng": {"da nang", "danang"},
        "Hội An": {"hoi an"},
        "Nha Trang": {"nha trang"},
        "Phú Quốc": {"phu quoc"},
        "Sa Pa": {"sa pa", "sapa"},
        "Vũng Tàu": {"vung tau"},
        "Đà Lạt": {"da lat", "dalat"},
        "Huế": {"hue"},
        "Cần Thơ": {"can tho"},
        "Ninh Bình": {"ninh binh"},
        "Hải Phòng": {"hai phong", "haiphong", "do son"},
        "Cát Bà": {"cat ba", "lan ha", "cat co"},
        "Yên Tử": {"yen tu"},
        "Chùa Hương": {"chua huong"},
    }
    current_terms = next(
        (terms for label, terms in destination_terms.items() if _ascii_fold(label).casefold() == current_key),
        set(),
    )
    for terms in destination_terms.values():
        if terms is current_terms:
            continue
        if any(
            term in name_key
            and not (term == "hue" and "nguyen hue" in name_key)
            for term in terms
        ):
            return True
    landmark_homes = {
        "yen tu": {"quang ninh", "yen tu", "uong bi", "viet nam", "vietnam"},
        "chua huong": {"ha noi", "hanoi", "my duc", "viet nam", "vietnam"},
        "cat ba": {"cat ba", "cat hai", "lan ha", "viet nam", "vietnam"},
    }
    if current_key in landmark_homes and current_key not in name_key:
        if area_key in landmark_homes[current_key]:
            return False
        foreign_area_terms = {
            "ha noi", "hanoi", "hai phong", "haiphong", "ha long", "halong",
            "thanh pho hai phong", "cat ba", "do son", "da nang", "nha trang",
            "sa pa", "sapa", "tp hcm", "hoi an", "hue", "da lat", "vung tau",
        }
        if any(term in area_key for term in foreign_area_terms):
            return True
    return False


def _tourism_quality_score(place: Place) -> int:
    """Prefer places that are recognizable as tourism anchors, not just nearby POIs."""
    name_key = _place_name_key(place)
    tags = set(place.tags)
    score = 0
    if name_key in LOW_VALUE_TOURIST_NAME_KEYS:
        return -100
    priority = famous_priority(place)
    if priority == 1:
        score += 80
    elif any(hint in name_key for hint in FAMOUS_TOURIST_NAME_HINTS):
        score += 70
    elif priority == 2:
        score += 55
    elif priority == 3:
        score += 8
    if (place.review_count or 0) >= 5000:
        score += 18
    elif (place.review_count or 0) >= 1000:
        score += 8
    if place.image_url or image_for(place)[0]:
        score += 35
    if place.kind in {"bai_bien", "nui", "hang_dong", "di_tich", "den_chua", "bao_tang", "giai_tri"}:
        score += 24
    elif place.kind == "dia_danh":
        score += 14
    elif place.kind in {"cho", "cong_vien"}:
        score += 8
    if tags.intersection({"beach", "peak", "viewpoint", "museum", "monument", "heritage", "historic", "temple"}):
        score += 12
    if "attraction" in tags:
        score += 8
    if tags.intersection({"artwork", "tree", "path", "limited"}) and not any(
        hint in name_key for hint in FAMOUS_TOURIST_NAME_HINTS
    ) and priority == 0:
        score -= 12
    return score


def _is_iconic_place(place: Place) -> bool:
    if place.source == "curated":
        return True
    if is_famous_place(place) and famous_priority(place) == 1:
        return True
    return _tourism_quality_score(place) >= 70


def _wants_old_quarter(request: PlanRequest) -> bool:
    tags = relevant_tags(request.context)
    return bool(
        tags.intersection(OLD_QUARTER_TERMS)
        or tags.intersection({"ha_noi", "hanoi", "pho_co"})
        or _wants_night(request)
    )


def choose_candidates(request: PlanRequest, excluded: set[str] | None = None) -> list[Place]:
    excluded = excluded or set()
    tags = relevant_tags(request.context)
    profiles = _intent_profiles(tags)
    wants_old_quarter = _wants_old_quarter(request)
    wants_night = _wants_night(request)
    wants_coffee = _wants_coffee(request)
    seed = _request_seed(request)
    behavior_profile = store.get_behavior_profile(request.ma_phien) if request.ma_phien else {}
    tag_weights = behavior_profile.get("tag_weights", {}) if isinstance(behavior_profile, dict) else {}
    destination_lat, destination_lng, destination_label = _destination_context(request)
    radius = _destination_radius_km(destination_label)
    source_places = _nearby_places((destination_lat, destination_lng), radius)
    disliked_profiles = _disliked_profiles(request.context)
    candidates = [
        p for p in source_places
        if p.id not in excluded
        and str(p.name or "").strip()
        and p.cost <= budget_cap(request)
        and is_routable(p)
        and not _is_place_disliked(p, disliked_profiles, request.context)
        and not _looks_like_non_travel_business(p)
        and not _mentions_other_destination(p, destination_label)
        and not _looks_closed(p)
        and haversine_km(destination_lat, destination_lng, p.lat, p.lng) <= radius
        and not (
            p.source == "curated"
            and {"pho_co", "old_quarter", "hang_pho"}.intersection(p.tags)
            and not wants_old_quarter
        )
        and not (
            request.thoi_luong in {"vai_gio", "nua_ngay"}
            and not wants_night
            and (p.open_hour >= 17 or "nightlife" in p.tags or "cho_dem" in p.tags)
        )
        and not (p.kind == "cafe" and not wants_coffee)
    ]
    ranked = sorted(
        candidates,
        key=lambda p: (
            -int(_is_requested_place(p, destination_label, request.context)),
            -int(_is_food_trip(request) and (_is_dining_place(p) or p.kind in {"cho", "cafe"})),
            -_intent_score(p, profiles),
            -_tourism_quality_score(p),
            -int(p.kind in SIGHT_KINDS),
            -int(p.kind in {"dia_danh", "bao_tang"}),
            -int(is_famous_place(p) or p.source == "curated"),
            -len(tags.intersection(p.tags)),
            -sum(int(tag_weights.get(tag, 0)) for tag in p.tags if isinstance(tag_weights.get(tag, 0), int)),
            haversine_km(destination_lat, destination_lng, p.lat, p.lng),
            p.cost,
            _place_seed(p, seed),
        ),
    )
    quality_pool = ranked[: max(80, min(len(ranked), 160 if destination_label else 120))]
    if not quality_pool:
        return []
    highlights = _highlight_places(request, excluded)
    must_see_ids = {
        place_id
        for ids in PROVINCE_HIGHLIGHT_MAP.values()
        for place_id in ids
    } | set(HANOI_HIGHLIGHT_IDS) | set(HANOI_NIGHT_IDS)
    must_highlights = [place for place in highlights if place.id in must_see_ids]
    flex_highlights = [place for place in highlights if place.id not in must_see_ids]
    rng = random.Random(seed)
    rng.shuffle(must_highlights)
    rng.shuffle(flex_highlights)
    highlights = must_highlights + flex_highlights
    highlight_ids = {place.id for place in highlights}
    intent_matches = [place for place in quality_pool if _intent_score(place, profiles) > 0]
    other_matches = [place for place in quality_pool if _intent_score(place, profiles) <= 0]
    if destination_label:
        nearby_iconic = {
            place.id
            for place in quality_pool
            if _near_anchor(place, (destination_lat, destination_lng), radius)
            and _is_iconic_place(place)
        }
        iconic_matches = sorted(
            [place for place in quality_pool if place.id in nearby_iconic],
            key=lambda place: (
                famous_priority(place) or 9,
                0 if place.source == "curated" else 1,
                0 if any(hint in _place_name_key(place) for hint in FAMOUS_TOURIST_NAME_HINTS) else 1,
                -_tourism_quality_score(place),
                haversine_km(destination_lat, destination_lng, place.lat, place.lng),
            ),
        )
        rest_intent = [place for place in intent_matches if place.id not in nearby_iconic]
        rest_other = [place for place in other_matches if place.id not in nearby_iconic]
        fillers = sorted(
            rest_intent[3:] + rest_other,
            key=lambda place: (
                -_tourism_quality_score(place),
                famous_priority(place) or 9,
                haversine_km(destination_lat, destination_lng, place.lat, place.lng),
            ),
        )
        notable = [place for place in fillers if _tourism_quality_score(place) >= 50]
        obscure = [place for place in fillers if _tourism_quality_score(place) < 50]
        rng.shuffle(iconic_matches)
        rng.shuffle(notable)
        ordered = iconic_matches + rest_intent[:3] + notable + obscure
        return highlights + [place for place in ordered if place.id not in highlight_ids]
    if intent_matches:
        pinned = intent_matches[:1]
        pool = intent_matches[len(pinned):] + other_matches
        shuffled_pool = pool[:]
        rng.shuffle(shuffled_pool)
        ordered = pinned + shuffled_pool
        return highlights + [place for place in ordered if place.id not in highlight_ids]
    return highlights + [place for place in quality_pool if place.id not in highlight_ids]


def validate_plan(
    plan: dict,
    trusted_ids: set[str],
    request: PlanRequest | None = None,
    *,
    allow_below_minimum: bool = False,
    trusted_places: tuple[Place, ...] = (),
    user_requested_ids: set[str] | frozenset[str] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    thoi_luong = (request.thoi_luong if request else plan.get("thoi_luong")) or "ca_ngay"
    timing = _trip_timing(request) if request else None
    plan_days = len(plan.get("ngay") or []) or (timing.days if timing else None)
    min_slots = _min_plan_slots(thoi_luong, plan_days) if thoi_luong in LIMITS else 4
    max_slots = _max_plan_slots(thoi_luong, plan_days) if thoi_luong in LIMITS else 10
    if timing and timing.max_minutes <= 180:
        min_slots = min(min_slots, 1)
    if (not allow_below_minimum and len(slots) < min_slots) or len(slots) > max_slots:
        errors.append(f"Kế hoạch phải có {min_slots}–{max_slots} địa điểm")
    if any(slot.get("dia_diem_id") not in trusted_ids for slot in slots):
        errors.append("Có địa điểm ngoài danh sách tin cậy")
    place_ids = [slot.get("dia_diem_id") for slot in slots]
    by_id = {place.id: place for place in (*PLACES, *trusted_places)}

    def _duplicate_is_reusable_dining(slot_id: str) -> bool:
        place = by_id.get(slot_id)
        if not place or not _is_dining_place(place):
            return False
        return all(
            slot.get("bua_an")
            for slot in slots
            if slot.get("dia_diem_id") == slot_id
        )

    duplicate_ids = {slot_id for slot_id in place_ids if isinstance(slot_id, str) and place_ids.count(slot_id) > 1}
    if any(not _duplicate_is_reusable_dining(slot_id) for slot_id in duplicate_ids):
        errors.append("Kế hoạch chứa địa điểm trùng lặp")
    name_keys = [
        _place_alias_key(by_id[slot_id]) or _place_name_key(by_id[slot_id])
        for slot_id in place_ids
        if isinstance(slot_id, str) and slot_id in by_id
    ]
    duplicate_names = {key for key in name_keys if name_keys.count(key) > 1}
    if duplicate_names:
        named_slots = [
            slot
            for slot in slots
            if isinstance(slot.get("dia_diem_id"), str)
            and slot.get("dia_diem_id") in by_id
            and (_place_alias_key(by_id[slot["dia_diem_id"]]) or _place_name_key(by_id[slot["dia_diem_id"]]))
            in duplicate_names
        ]
        if not all(
            _is_dining_place(by_id[slot["dia_diem_id"]]) and slot.get("bua_an")
            for slot in named_slots
        ):
            errors.append("Kế hoạch chứa địa điểm trùng tên")
    for day in plan.get("ngay", []):
        previous_end = "00:00"
        previous_place: Place | None = None
        for slot in day.get("khoang_gio", []):
            place = by_id.get(slot.get("dia_diem_id"))
            requested = slot.get("dia_diem_id") in user_requested_ids
            if slot["bat_dau"] < previous_end or slot["bat_dau"] >= slot["ket_thuc"]:
                errors.append(f"Khung giờ không tuần tự: {slot['dia_diem_id']}")
            if place and not requested:
                open_hour, close_hour = _effective_hours(place)
                if not (
                    f"{open_hour:02d}:00" <= slot["bat_dau"]
                    and slot["ket_thuc"] <= f"{close_hour:02d}:00"
                ):
                    errors.append(f"Ngoài giờ mở cửa: {slot['dia_diem_id']}")
            if previous_place and place and not requested and previous_place.id not in user_requested_ids:
                ph, pm = map(int, previous_end.split(":"))
                sh, sm = map(int, slot["bat_dau"].split(":"))
                gap = (sh * 60 + sm) - (ph * 60 + pm)
                need = travel_minutes(previous_place, place)
                if gap < need:
                    errors.append(
                        f"Không đủ thời gian di chuyển: {previous_place.id} → {place.id}"
                    )
            previous_end = slot["ket_thuc"]
            previous_place = place
    if request and budget_applies(request) and plan.get("chi_phi_moi_nguoi", 0) > request.ngan_sach:
        errors.append("Kế hoạch vượt ngân sách")
    if request:
        destination_lat, destination_lng, destination_label = _destination_context(request)
        if destination_label:
            for slot in slots:
                coordinates = slot.get("toa_do") or {}
                try:
                    slot_lat = float(coordinates.get("lat"))
                    slot_lng = float(coordinates.get("lng"))
                except (TypeError, ValueError):
                    errors.append(f"Thiếu tọa độ địa điểm: {slot.get('dia_diem_id')}")
                    continue
                distance_km = haversine_km(destination_lat, destination_lng, slot_lat, slot_lng)
                if distance_km > _destination_radius_km(destination_label) and slot.get("dia_diem_id") not in user_requested_ids:
                    errors.append(
                        f"Địa điểm nằm ngoài vùng {destination_label}: {slot.get('dia_diem_id')}"
                    )
    return errors


def _select_within_budget(candidates: list[Place], count: int, budget_per_person: int) -> list[Place]:
    selected: list[Place] = []
    spent = 0
    used_ids: set[str] = set()
    used_names: set[str] = set()
    for place in _dedupe_places(candidates):
        if place.id in used_ids or _name_taken(place, used_names):
            continue
        if spent + place.cost <= budget_per_person:
            selected.append(place)
            spent += place.cost
            used_ids.add(place.id)
            used_names.update(_place_name_keys(place))
        if len(selected) == count:
            break
    return selected


def _candidate_payload(candidates: list[Place], request: PlanRequest) -> list[dict]:
    destination_lat, destination_lng, _ = _destination_context(request)
    ordered = _famous_first_places(candidates, request)
    return [
        {
            "id": place.id,
            "name": place.name,
            "kind": place.kind,
            "area": place.area,
            "cost": place.cost,
            "duration_min": place.duration_min,
            "tags": list(place.tags),
            "open_hour": place.open_hour,
            "close_hour": place.close_hour,
            "distance_km": round(
                haversine_km(destination_lat, destination_lng, place.lat, place.lng),
                2,
            ),
            "iconic": _is_iconic_place(place),
            "famous": is_famous_place(place) or _is_iconic_place(place),
            "famous_priority": famous_priority(place) or None,
        }
        for place in ordered[:80]
    ]


def _call_with_destination(method, *args, destination: str | None):
    kwargs = {}
    try:
        if "destination" in inspect.signature(method).parameters:
            kwargs["destination"] = destination
    except (TypeError, ValueError):
        pass
    return method(*args, **kwargs)


def _select_ai_places(candidates: list[Place], count: int, request: PlanRequest) -> list[Place] | None:
    propose = getattr(ai_adapter, "propose_place_ids", None)
    if not callable(propose):
        return None
    try:
        _, _, destination_label = _destination_context(request)
        selected_ids = _call_with_destination(
            propose,
            request.context,
            _candidate_payload(candidates, request),
            count,
            request.ngon_ngu,
            destination=destination_label,
        )
    except RuntimeError:
        return None
    by_id = {place.id: place for place in candidates}
    selected: list[Place] = []
    used_names: set[str] = set()
    for place_id in selected_ids:
        place = by_id.get(place_id)
        if not place:
            continue
        if place.id in {item.id for item in selected} or _name_taken(place, used_names):
            continue
        selected.append(place)
        used_names.update(_place_name_keys(place))
        if len(selected) == count:
            break
    if len(selected) != count:
        return None
    if sum(place.cost for place in selected) > budget_cap(request):
        return None
    return selected


def _select_llm_first_places(
    candidates: list[Place],
    count: int,
    request: PlanRequest,
) -> tuple[list[Place], dict[str, dict]] | None:
    draft = getattr(ai_adapter, "draft_itinerary_places", None)
    if not callable(draft):
        return None
    try:
        _, _, destination_label = _destination_context(request)
        suggestions = _call_with_destination(
            draft,
            request.context,
            count,
            request.ngon_ngu,
            destination=destination_label,
        )
    except RuntimeError:
        return None
    selected: list[Place] = []
    details_by_id: dict[str, dict] = {}
    seen: set[str] = set()
    seen_names: set[str] = set()
    candidate_ids = {place.id for place in candidates}
    destination_lat, destination_lng, destination_label = _destination_context(request)
    origin = (destination_lat, destination_lng)
    for item in suggestions:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        verify_kwargs = {}
        try:
            if "city" in inspect.signature(verify_place_name).parameters:
                verify_kwargs["city"] = destination_label
        except (TypeError, ValueError):
            pass
        place = verify_place_name(name.strip(), origin, **verify_kwargs)
        if not place or place.id not in candidate_ids or place.id in seen or place.cost > budget_cap(request):
            continue
        if destination_label and not _near_anchor(place, origin, _destination_radius_km(destination_label)):
            continue
        if _name_taken(place, seen_names):
            continue
        selected.append(place)
        details_by_id[place.id] = item
        seen.add(place.id)
        seen_names.update(_place_name_keys(place))
        if len(selected) == count:
            break
    if len(selected) < count:
        for place in _famous_first_places(_dedupe_places(candidates), request):
            if place.id in seen or place.cost > budget_cap(request):
                continue
            if _name_taken(place, seen_names):
                continue
            selected.append(place)
            seen.add(place.id)
            seen_names.update(_place_name_keys(place))
            if len(selected) == count:
                break
    if len(selected) != count or sum(place.cost for place in selected) > budget_cap(request):
        return None
    return selected, details_by_id


def _enrich_visit_durations(
    places: list[Place],
    request: PlanRequest,
    details_by_id: dict[str, dict] | None,
) -> dict[str, dict]:
    details = dict(details_by_id or {})
    if not places:
        return details
    payload = [
        {
            "id": place.id,
            "name": place.name,
            "kind": place.kind,
            "tags": list(place.tags)[:8],
            "area": place.area,
            "catalog_minutes": _visit_minutes_for(place, None, request),
        }
        for place in places[:16]
    ]
    estimates: dict = {}
    should_ask_llm = _is_mountain_destination(request) or any(
        _is_mountain_experience(place) or _is_major_mountain_complex(place) for place in places
    )
    estimator = getattr(ai_adapter, "estimate_visit_durations", None)
    if should_ask_llm and callable(estimator):
        try:
            estimates = estimator(payload, request.ngon_ngu) or {}
        except Exception:
            estimates = {}
    if not isinstance(estimates, dict):
        estimates = {}
    for place in places:
        raw = estimates.get(place.id)
        try:
            minutes = int(raw)
        except (TypeError, ValueError):
            minutes = 0
        if minutes < MIN_VISIT_MINUTES or minutes > 480:
            continue
        if _is_major_mountain_complex(place):
            minutes = max(180, minutes)
        elif _is_mountain_experience(place):
            minutes = max(120, minutes)
        elif _is_mountain_transit(place):
            minutes = min(60, minutes)
        entry = dict(details.get(place.id) or {})
        entry["thoi_luong_phut"] = minutes
        details[place.id] = entry
    return details


def _join_sentences(parts: list[str], limit: int = 700) -> str:
    text = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return text[:limit].rstrip()


def _copy_area(place: Place, request: PlanRequest) -> str:
    area_key = _ascii_fold(place.area).casefold()
    if area_key not in {"", "viet nam", "vietnam"}:
        return place.area
    _, _, label = _destination_context(request)
    return label or place.area


def _named_attraction_copy(place: Place) -> tuple[str, str] | None:
    key = _place_name_key(place)
    named = (
        (("vinpearl safari", "safari phu quoc"),
         "Đi xe safari xem thú trong khu bán hoang dã: hổ, tê giác, thú ăn cỏ ngoài đồng — đây là nửa ngày trong công viên, không phải điểm check-in 30 phút.",
         "Đi sớm cho mát và đúng giờ xuất bến; mang mũ, nước, và hỏi lịch xe khứ hồi trước khi tách khỏi đoàn."),
        (("vinwonders", "vinpearl land"),
         "Công viên giải trí lớn: tàu lượn, show, khu nước hoặc thủy cung. Chọn 3–4 cụm thay vì cố xem hết trong một buổi.",
         "Mua vé combo và vào cửa sớm để tránh hàng; chừa sức nếu ngày đó còn biển hoặc sân bay."),
        (("dinh cau",),
         "Mỏm đá Dinh Cậu nhìn về phía tây: ghé gần hoàng hôn để xem thuyền và mặt trời lặn, không cần lịch dài.",
         "Tối mức nước và đá trơn; đến trước lúc trời tối hẳn để còn đường ra."),
        (("bai sao",),
         "Bãi cát trắng nước trong phía nam đảo: tắm, đi bộ bờ và nghỉ nhẹ, tránh giờ trưa nắng gắt.",
         "Thuê dù/ghế theo giờ và mang nước; đường ra bãi có thể mất hơn kỳ vọng nếu kẹt xe."),
        (("cau vang", "golden bridge"),
         "Cầu Vàng trên Bà Nà: đi cáp, chụp trên đôi bàn tay đá và nhìn xuống đèo Hải Vân — cụm này thường chiếm nửa ngày.",
         "Đi sớm để tránh sương và đông; giữ vé cáp khứ hồi và lịch xuống núi trước khi tối."),
        (("ba na",),
         "Bà Nà Hills: làng Pháp, vườn hoa, trò chơi trên đỉnh núi. Chọn một cụm chính rồi mới sang Cầu Vàng.",
         "Mang áo khoác vì đỉnh núi lạnh hơn Đà Nẵng; tính thời gian cáp treo vào lịch."),
        (("my khe",),
         "Bãi Mỹ Khê: tắm biển, đi bộ dọc bờ và nghỉ giữa các điểm trong phố.",
         "Tránh 11h–15h nếu nắng gắt; giữ đồ trên bãi và chừa thời gian về trung tâm."),
        (("thien mu",),
         "Chùa Thiên Mụ trên đồi nhìn sông Hương: thăm tháp Phước Duyên, sân chùa và góc chụp sông.",
         "Trang phục kín đáo; ghép thuyền sông hoặc xe về Đại Nội thay vì đi riêng lẻ."),
        (("dai noi",),
         "Đại Nội Huế: Kinh thành, cung điện và lầu Thái Hòa — đi chậm theo trục chính, không cần xem hết từng nhà.",
         "Mua vé đúng cổng; nắng sân rộng nên mang nước và nón."),
        (("cho noi", "cai rang"),
         "Chợ nổi Cái Răng: đi thuyền giữa ghe bán trái cây, hủ tiếu và cà phê sáng trên sông.",
         "Đi từ sáng sớm khi chợ đông nhất; mặc đồ có thể văng nước."),
        (("tam coc",),
         "Tam Cốc: thuyền xuyên mùa lúa/núi đá và hang — nhịp chậm, một hành trình sông chứ không phải điểm đứng chụp.",
         "Đi sớm tránh đông; đội nón, bôi kem nắng, thỏa thuận giá chụp ảnh trước."),
        (("trang an",),
         "Tràng An: thuyền qua hang và thung lũng đá vôi — chọn một tuyến và giữ nguyên nhịp cả buổi.",
         "Mang áo mưa mỏng trong hang; vé theo tuyến, hỏi rõ thời lượng trước khi xuống thuyền."),
        (("fansipan",),
         "Fansipan: cáp hoặc trekking lên nóc nhà Đông Dương, nhiệt độ thấp hơn thị trấn Sa Pa rõ rệt.",
         "Mang áo ấm; tính giờ cáp khứ hồi, mây dày có thể che view."),
        (("yen tu", "chua dong"),
         "Yên Tử là hành trình núi và chùa: cáp hoặc leo bộ lên Chùa Đồng, dừng thở và xuống chậm — nửa ngày đến cả ngày, không phải điểm ghé 1 giờ.",
         "Đi sớm, mang giày bám và nước; tính giờ cáp khứ hồi và xuống trước khi cổng đóng."),
        (("thien vien truc lam",),
         "Thiền viện Trúc Lâm dưới chân Yên Tử: đi chậm qua sân, chính điện và vườn thông, chừa nửa buổi.",
         "Giữ yên lặng trong chính điện; ghép với cáp/lên núi trong cùng ngày thay vì tách tour."),
        (("vuon quoc gia cat ba", "cat ba national"),
         "Vườn quốc gia Cát Bà: rừng trên đảo đá vôi, đường mòn và view vịnh — nửa ngày, không phải điểm check-in 20 phút.",
         "Mang giày bám, nước và áo mưa mỏng; hỏi lối Trung Trang / Ngự Lâm trước khi lên."),
        (("bai cat co", "cat co"),
         "Bãi Cát Cò trên đảo Cát Bà: tắm, leo bãi đá và nhìn Lan Hạ. Ở lại đảo, không ghép Đồ Sơn hay nội thành Hải Phòng.",
         "Đi sớm tránh đông; dép bám đá, không để đồ không người trông."),
        (("hang quan y",),
         "Hang Quân Y: hầm bệnh viện trong núi thời chiến, đi chậm trong hang mát và hẹp.",
         "Mang đèn pin/điện thoại; trần thấp, không hợp nếu sợ không gian kín."),
        (("lan ha", "vinh lan ha"),
         "Vịnh Lan Hạ sát Cát Bà: thuyền giữa đảo đá, tắm và kayak — xuất phát từ bến đảo chứ không từ Bãi Cháy.",
         "Chọn tour trong ngày từ thị trấn Cát Bà; mang áo phao và kem nắng."),
        (("phao dai than cong", "cannon fort"),
         "Pháo đài thần công trên đỉnh đảo: view thị trấn, Lan Hạ và Hoàng hôn. Leo bộ hoặc xe máy.",
         "Đi chiều mát; đường dốc, mang nước."),
        (("cai beo",),
         "Làng chài Cái Bèo: bến thuyền, nhà bè và hải sản ven vịnh, gần thị trấn Cát Bà.",
         "Đi chiều hoặc tối ăn hải sản; hỏi giá trước, không nhầm tour Hạ Long."),
        (("bao ton", "vuon quoc gia"),
         "Khu bảo tồn / rừng núi: đi lối mòn, quan sát và nghỉ trong rừng cả buổi thay vì check-in rồi đi.",
         "Mang nước, mũ và xuống trước tối; hỏi lối mòn nào được phép đi."),
    )
    for hints, activity, tip in named:
        if any(hint in key for hint in hints):
            return activity, tip
    return None


def _kind_attraction_copy(place: Place, copy: tuple[str, ...]) -> tuple[str, str]:
    tags = set(place.tags)
    if place.kind == "giai_tri":
        return (
            f"Dành một khối thời gian cho {place.name}: trò chơi, show hoặc khu trải nghiệm — đây thường là điểm nửa ngày chứ không phải ghé nhanh.",
            "Giữ vé và lịch show trong tay; chừa buffer ra vào cổng trước khi sang điểm kế.",
        )
    if place.kind == "bai_bien" or "beach" in tags:
        return (
            f"Tắm, đi bộ bờ và nghỉ tại {place.name}; đây là nhịp thở của ngày, không phải điểm check-in đứng chụp rồi đi.",
            "Tránh nắng 11h–15h, mang nước và không để đồ mắc trên cát.",
        )
    if place.kind in {"nui", "hang_dong"}:
        return (
            f"Đi theo lối mòn/hang tại {place.name}: view và nhịp chậm hơn phố, tính thời gian lên xuống rõ ràng.",
            "Mang giày bám, nước, và xuống trước khi tối nếu không có chiếu sáng.",
        )
    if place.kind == "cafe" or {"cafe", "coffee"}.intersection(tags):
        return (
            "Dành thời gian nghỉ chân, gọi một món đặc trưng và ngắm nhịp phố xung quanh thay vì chỉ ghé qua cho có điểm.",
            "Nên chọn bàn có view tốt hoặc hỏi nhân viên món được gọi nhiều nhất; nếu quán đông, giữ nhịp linh hoạt để không trễ điểm tiếp theo.",
        )
    if {"pho_co", "old_quarter", "hang_pho", "di_bo"}.intersection(tags) and place.kind not in {"giai_tri", "bai_bien"}:
        return (
            "Đi chậm qua các tuyến phố, nhìn mặt tiền nhà cổ, hàng quán nhỏ và nhịp buôn bán đặc trưng của khu phố cổ.",
            "Nên gom các phố gần nhau thành một đoạn đi bộ liên tục; buổi tối hợp hơn nếu muốn không khí đông vui và nhiều hàng ăn.",
        )
    if place.kind in {"den_chua", "di_tich", "bao_tang"} or {"hanoi_icon", "lich_su", "van_hoa", "museum", "heritage", "monument", "temple"}.intersection(tags):
        return (
            f"Thăm {place.name} theo hành lang trưng bày hoặc sân di tích: đọc vài tấm bảng, chụp một góc tiêu biểu rồi để điểm này làm mốc của chặng.",
            "Kiểm tra giờ mở cửa và trang phục; đi sớm nếu điểm nổi tiếng hoặc đóng cửa giữa trưa.",
        )
    if place.kind == "cho":
        return (
            f"Đi chợ {place.name}: thử món trên tay, nhìn hàng địa phương và nhịp mua bán — gói gọn 45–75 phút cho đỡ lệch lịch.",
            "Giữ đồ sát người; hỏi giá trước khi mua và tránh giờ đóng sạp.",
        )
    if {"ngoai_troi", "view_dep"}.intersection(tags) or place.kind == "cong_vien":
        return (
            "Đây là khoảng thở của lịch trình: đi bộ nhẹ, chụp ảnh và cân bằng lại nhịp sau các điểm đông người.",
            "Mang nước, tránh nắng gắt giữa trưa và ưu tiên sáng sớm hoặc chiều muộn nếu muốn ảnh đẹp hơn.",
        )
    return (
        f"Tham quan {place.name}: quan sát, chụp vài góc đặc trưng và hiểu khu vực trước khi chuyển điểm kế.",
        copy[4],
    )


def _slot_connector(place: Place, meal_type: str | None) -> str:
    if meal_type:
        return "Quán được chọn gần các điểm tham quan trong ngày để tiết kiệm thời gian di chuyển."
    kind_lines = {
        "giai_tri": (
            "Chừa buffer vé và xe đưa đón — khu giải trí thường kéo dài hơn vẻ trên bản đồ.",
            "Chọn một cụm hoạt động chính ở đây rồi mới chuyển điểm, đừng cố xem hết.",
        ),
        "bai_bien": (
            "Ghép bãi biển với điểm gần nhất trong cùng cụm để khỏi chạy đường trùng.",
            "Rời bãi trước khi kẹt xe giờ tan; cát ướt dễ làm lệch giờ điểm kế.",
        ),
        "den_chua": (
            "Ghép điểm tâm linh/di tích này với stop kế trong cùng trục đường.",
            "Đi xong đúng hướng cổng ra để khỏi vòng lại đường vào.",
        ),
        "di_tich": (
            "Để điểm này làm mốc giữa buổi rồi mới nhảy cụm khác.",
            "Không nhồi thêm stop xa ngay sau di tích lớn.",
        ),
        "bao_tang": (
            "Bảo tàng hợp buổi sáng hoặc trước mưa; sau đó mới sang điểm ngoài trời.",
            "Ra cửa đúng hướng điểm kế để khỏi vòng quanh trung tâm.",
        ),
        "nui": (
            "Tính thời gian lên xuống; đừng xếp điểm xa ngay sau khi xuống núi.",
            "Nếu mây/mưa, cắt ngắn và chuyển cụm thấp hơn.",
        ),
        "cho": (
            "Chợ nên đứng trước bữa hoặc sau điểm văn hóa gần đó, không kẹp giữa hai khu xa.",
            "Ra chợ đúng hướng xe/thuyền đã hẹn.",
        ),
    }
    options = kind_lines.get(place.kind, (
        "Ghép điểm này với các stop gần trong cùng cụm để đỡ đi đường trùng.",
        "Giữ {name} làm nhịp chính của buổi rồi mới chuyển cụm khác.".replace("{name}", place.name),
        "Chừa 15–20 phút di chuyển thực tế giữa điểm này và stop kế.",
    ))
    return options[_place_seed(place, 91) % len(options)]


def _fallback_slot_copy(
    place: Place,
    request: PlanRequest,
    copy: tuple[str, ...],
    meal_type: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    tags = set(place.tags)
    area = _copy_area(place, request)
    is_hanoi = _ascii_fold(area).casefold() in {"ha noi", "hanoi", "hoan kiem", "tay ho", "ba dinh"}
    meal_prefix = ""
    if meal_type and labels:
        meal_prefix = f"{labels[meal_type]} tại {place.name}: "
    named = None if meal_type or _is_dining_place(place) else _named_attraction_copy(place)
    if named:
        activity, tip = named
    elif _is_dining_place(place) or {"am_thuc", "an_vat", "local"}.intersection(tags):
        if meal_type == "trua":
            activity = (
                "Dừng chân ăn trưa với các món đặc sản địa phương — phở, bún, cơm hoặc các quán bình dân được người Hà Nội hay ghé."
                if is_hanoi
                else f"Dừng chân ăn trưa với món địa phương ở {area} — quán bình dân hoặc đặc sản vùng, vừa đủ no để đi tiếp chiều."
            )
            tip = "Nên đến trước 12h để tránh đông; gọi vài món chia sẻ nếu đi từ hai người trở lên để thử nhiều hương vị hơn."
        elif meal_type == "nghi":
            activity = "Nghỉ chân tránh nắng giữa trưa: ngồi quán mát, uống gì đó nhẹ và lấy sức trước khi đi tiếp buổi chiều."
            tip = "Khung 12h30–14h30 thường oi bức; nghỉ 40–60 phút giúp lịch chiều đỡ trống và dễ chịu hơn."
        elif meal_type == "dem":
            activity = (
                "Buổi tối khám phá không khí Hà Nội: phố cổ, chợ đêm hoặc hồ Gươm về đêm sau bữa tối."
                if is_hanoi
                else f"Buổi tối đi khu biển/phố đêm ở {area} sau bữa — một vòng ngắn cho đỡ đặc lịch ban ngày."
            )
            tip = "Nên đi sau 19h khi đèn lên và khu vực đông vui hơn; giữ đồ gọn nếu đi chợ đêm."
        elif meal_type == "toi":
            activity = (
                "Buổi tối thưởng thức ẩm thực Hà Nội — có thể là bún chả, lẩu, nướng hoặc các món đường phố ở khu phố cổ."
                if is_hanoi
                else f"Buổi tối ăn đặc sản {area} — hải sản, nướng hoặc quán địa phương gần cụm tham quan trong ngày."
            )
            tip = (
                "Buổi tối khu phố cổ và Tạ Hiện thường đông; đặt bàn trước hoặc đến khoảng 18h30–19h nếu muốn ngồi thoải mái."
                if is_hanoi
                else "Đến khoảng 18h30–19h để còn chỗ; hỏi giá hải sản/set trước khi gọi."
            )
        elif meal_type == "sang":
            activity = (
                "Bắt đầu ngày với bữa sáng Hà Nội — phở, bánh mì, xôi hoặc cà phê sữa đá."
                if is_hanoi
                else f"Bắt đầu ngày với bữa sáng ở {area} — quán gần chỗ nghỉ, ăn xong ra điểm đầu tiên."
            )
            tip = "Quán sáng thường đông 7h30–9h; gọi món nhanh và ăn tại chỗ để kịp lịch tham quan."
        else:
            activity = "Đây là điểm dừng để nạp năng lượng và thử hương vị địa phương, hợp đặt vào giữa lịch để chuyến đi không bị quá dày."
            tip = "Đi lệch giờ cao điểm một chút sẽ dễ có chỗ ngồi hơn; nên gọi vài món chia sẻ nếu đi từ hai người trở lên."
    else:
        activity, tip = _kind_attraction_copy(place, copy)
    guidance = _guidance(place)
    if guidance and guidance.tip and not meal_type:
        tip = guidance.tip
    description = _join_sentences(
        [
            meal_prefix + f"{place.name} tại {area} là điểm dừng chân thú vị trong chuyến đi."
            if not meal_prefix
            else meal_prefix + f"Quán nằm tại khu vực {area}, thuận tiện ghé thưởng thức.",
            activity,
            _slot_connector(place, meal_type),
        ],
        limit=850,
    )
    return description, tip


def _slot_copy(
    place: Place,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_detail: dict | None,
    meal_type: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    if not llm_detail:
        return _fallback_slot_copy(place, request, copy, meal_type, labels)
    why = llm_detail.get("why")
    activity = llm_detail.get("activity") or llm_detail.get("what_to_do") or llm_detail.get("experience")
    tip = llm_detail.get("tip") or llm_detail.get("local_tip")
    meal = llm_detail.get("meal") or llm_detail.get("food")
    transport = llm_detail.get("transport") or llm_detail.get("move")
    meal_label = labels.get(meal_type, "") if meal_type and labels else ""
    description = _join_sentences(
        [
            f"{meal_label} tại {place.name} ({place.area})." if meal_label else f"{place.name} ({place.area}) là điểm đến nổi bật.",
            str(why) if isinstance(why, str) else "",
            str(activity) if isinstance(activity, str) else "",
            f"Gợi ý món: {meal}." if isinstance(meal, str) and meal.strip() else "",
        ]
    )
    note = _join_sentences(
        [
            str(tip) if isinstance(tip, str) else "",
            f"Di chuyển: {transport}." if isinstance(transport, str) and transport.strip() else "",
            copy[4],
        ],
        limit=500,
    )
    return description or copy[3].format(place=place.name, area=place.area), note or copy[4]


def _ordered_route(places: list[Place], origin: tuple[float, float]) -> list[Place]:
    morning = [place for place in places if _is_morning_only(place)]
    evening = [
        place
        for place in places
        if place not in morning
        and (
            _effective_hours(place)[0] >= 17
            or "nightlife" in place.tags
            or "cho_dem" in place.tags
        )
    ]
    outdoor = [
        place
        for place in places
        if place not in morning and place not in evening and _is_outdoor_place(place)
    ]
    flexible = [
        place
        for place in places
        if place not in morning and place not in evening and place not in outdoor
    ]

    def near(items: list[Place], from_point: tuple[float, float]) -> list[Place]:
        return sorted(
            items,
            key=lambda place: (
                haversine_km(from_point[0], from_point[1], place.lat, place.lng),
                place.id,
            ),
        )

    route: list[Place] = []
    cursor = origin
    for group in (morning, flexible, outdoor, evening):
        if not group:
            continue
        ordered = near(group, cursor)
        if len(ordered) > 2:
            ordered = two_opt(nearest_neighbor(ordered, cursor))
        route.extend(ordered)
        cursor = (ordered[-1].lat, ordered[-1].lng)
    return route


def _select_sight_places(
    candidates: list[Place],
    sight_count: int,
    request: PlanRequest,
    max_minutes: int,
    number_of_days: int,
) -> tuple[list[Place], dict[str, dict], dict]:
    sight_pool = _dedupe_places(_sight_candidates(candidates, request))
    sight_pool, policy_evidence = _apply_intent_policy_to_sights(sight_pool, request, sight_count)
    sight_pool = _famous_first_places(sight_pool, request)
    llm_details_by_id: dict[str, dict] = {}
    allow_cafe = _wants_coffee(request)
    allow_food = _is_food_trip(request)
    llm_first = _select_llm_first_places(sight_pool, sight_count, request)
    if llm_first:
        chosen, llm_details_by_id = llm_first
        chosen = _dedupe_places(
            [
                place
                for place in chosen
                if _is_sight_place(place, allow_cafe=allow_cafe, allow_food=allow_food)
                and (allow_food or not _is_dining_place(place))
                and not (
                    _wants_seafood(request)
                    and not _wants_vegetarian(request)
                    and _looks_vegetarian_dining(place)
                )
            ]
        )
        if len(chosen) >= min(sight_count, 2):
            evidence: dict[str, object] = {
                "phuong_phap": "llm_catalog_guarded",
                "ghi_chu": "LLM chỉ chọn id có trong catalog tin cậy; planner vẫn kiểm tra ràng buộc sau đó.",
            }
            if policy_evidence:
                evidence["intent_policy"] = policy_evidence
            return _merge_highlights(chosen, sight_pool, request, sight_count), llm_details_by_id, evidence
    ai_chosen = _select_ai_places(sight_pool, sight_count, request)
    if ai_chosen:
        evidence: dict[str, object] = {
            "phuong_phap": "ai_catalog_selection",
            "ghi_chu": "AI chọn danh sách từ ứng viên hợp lệ trong catalog.",
        }
        if policy_evidence:
            evidence["intent_policy"] = policy_evidence
        return _merge_highlights(_dedupe_places(ai_chosen), sight_pool, request, sight_count), llm_details_by_id, evidence
    score_by_id = {
        place.id: max(1, (len(sight_pool) - index) * 10 + _tourism_quality_score(place))
        for index, place in enumerate(sight_pool)
    }
    cp_day = None
    if number_of_days == 1:
        cp_day = optimize_day_schedule_with_cp_sat(
            sight_pool,
            8 * 60,
            8 * 60 + max_minutes,
            {place.id: _visit_minutes_for(place, None, request) for place in sight_pool[:80]},
            score_by_id,
            travel_minutes,
            min_places=sight_count,
            max_places=sight_count,
            budget_per_person=budget_cap(request),
            max_candidates=80,
        )
        if cp_day.selected_ids:
            by_id = {place.id: place for place in sight_pool}
            chosen = [by_id[place_id] for place_id in cp_day.selected_ids if place_id in by_id]
            if len(chosen) >= min(sight_count, 2):
                evidence: dict[str, object] = {
                    "phuong_phap": "ortools_cp_sat_day_joint_selection",
                    "thu_vien": "ortools.sat.python.cp_model",
                    "trang_thai": cp_day.status,
                    "vai_tro": "chon_va_xep_lai_ung_vien_theo_ngay_voi_time_window_duration_travel_budget",
                    "so_ung_vien_xet": cp_day.candidate_count,
                    "gioi_han_ung_vien": 80,
                    "objective_score": cp_day.objective_score,
                    "selected_ids": list(cp_day.selected_ids),
                    "suggested_starts": {
                        place_id: f"{minute // 60:02d}:{minute % 60:02d}"
                        for place_id, minute in cp_day.starts.items()
                    },
                    "chan_bo": list(cp_day.blockers),
                }
                if policy_evidence:
                    evidence["intent_policy"] = policy_evidence
                return _merge_highlights(_dedupe_places(chosen), sight_pool, request, sight_count), llm_details_by_id, evidence
    cp_selection = select_places_with_cp_sat(
        sight_pool,
        sight_count,
        budget_cap(request),
        score_by_id,
        max_candidates=40,
    )
    if cp_selection.selected_ids:
        by_id = {place.id: place for place in sight_pool}
        chosen = [by_id[place_id] for place_id in cp_selection.selected_ids if place_id in by_id]
        if len(chosen) >= min(sight_count, 2):
            origin = _lodging_anchor(request)
            origin_place = Place(
                id="__origin__",
                name="Origin",
                kind="origin",
                area="origin",
                lat=origin[0],
                lng=origin[1],
                cost=0,
                duration_min=0,
                tags=(),
            )
            order = optimize_order_with_cp_sat(
                _dedupe_places(chosen)[:sight_count],
                origin,
                lambda _origin, place: travel_minutes(origin_place, place),
                travel_minutes,
            )
            if order.ordered_ids:
                ordered_by_id = {place.id: place for place in chosen}
                chosen = [ordered_by_id[place_id] for place_id in order.ordered_ids if place_id in ordered_by_id]
            evidence: dict[str, object] = {
                "phuong_phap": "ortools_cp_sat_selection",
                "thu_vien": "ortools.sat.python.cp_model",
                "trang_thai": cp_selection.status,
                "so_ung_vien_xet": cp_selection.candidate_count,
                "gioi_han_ung_vien": 40,
                "objective_score": cp_selection.objective_score,
                "sap_thu_tu": {
                    "phuong_phap": "ortools_cp_sat_order",
                    "trang_thai": order.status,
                    "so_diem_xet": order.candidate_count,
                    "objective_travel_minutes": order.objective_travel_minutes,
                    "chan_bo": list(order.blockers),
                },
                "chan_bo": list(cp_selection.blockers),
            }
            if policy_evidence:
                evidence["intent_policy"] = policy_evidence
            return _merge_highlights(_dedupe_places(chosen), sight_pool, request, sight_count), llm_details_by_id, evidence
    chosen = _select_ai_places(sight_pool, sight_count, request) or _select_within_budget(
        sight_pool, sight_count, budget_cap(request)
    )
    chosen = [
        place
        for place in chosen
        if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
    ]
    evidence: dict[str, object] = {
        "phuong_phap": "fallback_ranked_budget",
        "cp_sat": (
            {
                "co_san": cp_selection.available,
                "trang_thai": cp_selection.status,
                "chan_bo": list(cp_selection.blockers),
            }
            if cp_selection
            else {"co_san": False, "trang_thai": "skipped_long_trip", "chan_bo": []}
        ),
        "cp_sat_day_joint": (
            {
                "co_san": cp_day.available,
                "trang_thai": cp_day.status,
                "so_ung_vien_xet": cp_day.candidate_count,
                "chan_bo": list(cp_day.blockers),
            }
            if cp_day
            else {"co_san": False, "trang_thai": "not_applicable_multi_day_or_disabled"}
        ),
    }
    if policy_evidence:
        evidence["intent_policy"] = policy_evidence
    return _merge_highlights(_dedupe_places(chosen), sight_pool, request, sight_count), llm_details_by_id, evidence


def build_plan(request: PlanRequest, excluded: set[str] | None = None, input_understanding: dict | None = None) -> dict:
    if not DISTANCE_METADATA.get("loaded") or not DISTANCE_METADATA.get("updated_at"):
        raise PipelineUnavailable("Hệ thống đang khởi tạo bản đồ, vui lòng quay lại sau")
    count, default_minutes, _default_days = LIMITS[request.thoi_luong]
    timing = _trip_timing(request)
    asked_days = max(timing.asked_days, timing.days)
    requested_days = asked_days
    number_of_days = min(max(1, timing.days), MAX_TRIP_DAYS)
    max_minutes = timing.max_minutes
    if number_of_days >= 2 and max_minutes <= 240 and not (timing.clock_label and "h–" in (timing.clock_label or "")):
        max_minutes = default_minutes
    if number_of_days > 2:
        per_day = 4
        count = max(count, min(per_day * number_of_days, 160))
    meals_per_day = _meals_per_day(request.thoi_luong, request)
    meals_total = len(meals_per_day) * number_of_days
    sight_total = max(_sight_total(count, meals_total, request.thoi_luong), number_of_days)
    max_slots = _max_plan_slots(request.thoi_luong, number_of_days)
    min_slots = _min_plan_slots(request.thoi_luong, number_of_days)
    if max_minutes <= 240:
        sight_total = max(sight_total, min(4, max(2, max_minutes // 45)))
        if max_minutes <= 90:
            min_slots = min(min_slots, 1)
        else:
            min_slots = max(min(min_slots, 2), 2)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    if _is_mountain_destination(request) and max_minutes > 180:
        sight_total = min(sight_total, max(2, 2 * number_of_days))
    if input_understanding is None:
        input_understanding = _request_understanding(request)
    candidates = choose_candidates(request, excluded)
    behavior_profile = store.get_behavior_profile(request.ma_phien) if request.ma_phien else {}
    sight_chosen, llm_details_by_id, selection_solver_evidence = _select_sight_places(
        candidates,
        sight_total,
        request,
        max_minutes,
        number_of_days,
    )
    sight_chosen = _dedupe_places(sight_chosen)
    llm_details_by_id = _enrich_visit_durations(sight_chosen, request, llm_details_by_id)
    if len(sight_chosen) < min(sight_total, 2):
        raise PipelineUnavailable("Không đủ địa điểm tham quan tin cậy trong ngân sách")

    origin = _lodging_anchor(request)
    ordered_sights = _ordered_route(sight_chosen, origin)
    sight_by_day = _chunk_sights_by_day(ordered_sights, number_of_days)

    trip_date = timing.start_date or request.ngay_di or datetime.now(UTC).date()
    holiday_context = _holiday_note(trip_date)
    copy = COPY[request.ngon_ngu]
    labels = _meal_labels(request.ngon_ngu)
    weather = {
        "tinh_trang": copy[0],
        "ghi_chu": copy[1],
        "nguon": None,
    }
    if settings.weather_enabled:
        try:
            weather = get_daily_weather(
                destination_lat, destination_lng, trip_date, request.ngon_ngu
            )
        except (WeatherUnavailable, ValueError, httpx.HTTPError):
            weather["ghi_chu"] = copy[2]
    solar_context = sunset_for_date(trip_date, destination_lat, destination_lng)
    seasonal_context = _seasonal_context(destination_label, trip_date)

    seed = _request_seed(request)
    used_ids = {place.id for place in sight_chosen} | (excluded or set())
    remaining_budget = budget_cap(request) - sum(place.cost for place in sight_chosen)
    meal_places: list[Place] = []
    days: list[dict] = []
    total_cost = 0
    scheduled_ids: set[str] = set()
    scheduled_names: set[str] = set()
    used_names = {
        name_key
        for place in sight_chosen
        for name_key in _place_name_keys(place)
    }

    for day_index, day_sights in enumerate(sight_by_day, start=1):
        day_meals = _pick_day_meals(
            request,
            day_sights,
            used_ids,
            remaining_budget,
            seed + day_index,
            used_names,
        )
        meal_places.extend(place for _, place in day_meals)
        for _, place in day_meals:
            remaining_budget -= place.cost
        route_stops = _build_day_route(
            request,
            day_sights,
            day_meals,
            used_ids,
            remaining_budget,
            seed + day_index,
            used_names,
        )
        refreshment = [
            place
            for place, meal_type in route_stops
            if meal_type is None and place.id not in {sight.id for sight in day_sights}
        ]
        for place in refreshment:
            used_ids.add(place.id)
            remaining_budget -= place.cost
            meal_places.append(place)
        day_start = datetime.combine(
            trip_date + timedelta(days=day_index - 1),
            datetime.min.time(),
        ).replace(hour=timing.start_hour, minute=timing.start_minute)
        day_slot_budget = min(
            max_slots,
            len(scheduled_ids) + _max_day_slots(request.thoi_luong, number_of_days, max_minutes),
        )
        slots, day_cost = _pack_day_slots(
            route_stops,
            day_start,
            max_minutes,
            request,
            copy,
            llm_details_by_id,
            labels,
            scheduled_ids,
            scheduled_names,
            weather,
            solar_context,
            behavior_profile,
            max_slots=day_slot_budget,
        )
        fill_cost = 0
        slots, fill_cost = _backfill_day_gaps(
            slots,
            day_start,
            max_minutes,
            request,
            copy,
            llm_details_by_id,
            labels,
            scheduled_ids,
            scheduled_names,
            used_ids,
            remaining_budget,
            seed + day_index,
            day_slot_budget,
            weather,
            solar_context,
            behavior_profile,
        )
        total_cost += day_cost + fill_cost
        remaining_budget -= fill_cost // max(request.so_nguoi, 1)
        min_day_slots = 1 if number_of_days >= 3 or max_minutes <= 90 else (
            2 if max_minutes <= 240 else (4 if number_of_days == 1 else 2)
        )
        if len(slots) < min_day_slots:
            extra = _choose_extra_sight(
                request,
                used_ids,
                _lodging_anchor(request),
                seed + day_index + 17,
                max(remaining_budget, 0),
                used_names | scheduled_names,
            )
            if extra:
                extra_slots, extra_cost = _pack_day_slots(
                    [(extra, None)],
                    day_start,
                    max_minutes,
                    request,
                    copy,
                    llm_details_by_id,
                    labels,
                    scheduled_ids,
                    scheduled_names,
                    weather,
                    solar_context,
                    behavior_profile,
                    max_slots=day_slot_budget,
                )
                slots.extend(extra_slots)
                total_cost += extra_cost
                used_ids.add(extra.id)
                used_names.update(_place_name_keys(extra))
        if len(slots) < 1:
            raise PipelineUnavailable("Không đủ thời gian để xếp đủ địa điểm trong ngày")
        if number_of_days == 1 and len(slots) < min_day_slots:
            raise PipelineUnavailable("Không đủ thời gian để xếp đủ địa điểm trong ngày")
        days.append({"thu_tu": day_index, "nhan_de": copy[5].format(day=day_index), "khoang_gio": slots})

    all_slots = [slot for day in days for slot in day["khoang_gio"]]
    if not min_slots <= len(all_slots) <= max_slots:
        raise PipelineUnavailable("Không đủ thời gian để xếp đủ địa điểm trong ngày")

    scheduled_ids = {slot["dia_diem_id"] for day in days for slot in day["khoang_gio"]}
    trusted_ids = scheduled_ids | {place.id for place in candidates} | {place.id for place in PLACES}
    overflow = _overflow_leg_copy(request, asked_days, number_of_days, destination_label)
    draft = {
        "tieu_de": _plan_title(destination_label, request, number_of_days),
        "tom_tat": overflow["summary"] if overflow else copy[6].format(people=request.so_nguoi),
        "thoi_luong": request.thoi_luong,
        "ngay_di": trip_date.isoformat(),
        "tong_chi_phi": total_cost,
        "chi_phi_moi_nguoi": total_cost // request.so_nguoi,
        "thoi_tiet": weather,
        "diem_den": destination_label,
        "dau_vao_da_hieu": input_understanding,
        "du_lieu_ung_vien": {
            "tong_ung_vien": len(candidates),
            "nguon": sorted({place.source for place in candidates if place.source}),
            "ban_kinh_km": _destination_radius_km(destination_label),
            "diem_den": input_understanding["diem_den"],
            "ghi_chu": "Ứng viên được lọc từ catalog hiện có, loại điểm không phù hợp du lịch, kiểm tra ngân sách, tọa độ và vùng.",
        },
        "rang_buoc_luu_tru": _lodging_context(request),
        "bo_giai_chon_ung_vien": selection_solver_evidence,
        "ho_so_hanh_vi": {
            "schema_version": behavior_profile.get("schema_version"),
            "version": behavior_profile.get("version", 0),
            "so_tin_hieu": behavior_profile.get("observation_count", 0),
            "kich_hoat_sau": behavior_profile.get("active_after_observations", 5),
            "dang_ap_dung": bool(behavior_profile.get("is_active")),
            "co_log_thay_doi": bool(behavior_profile.get("change_log")),
            "nguon": "store.ho_so_so_thich",
        },
        "tieu_chi_thoi_diem": {
            "lich_nghi_le": holiday_context,
            "thien_van": solar_context,
            "mua_vu_le_hoi": seasonal_context,
            "thoi_tiet": {
                "co_du_bao": bool(weather.get("nguon")),
                "tranh_outdoor_buoi_trua": _weather_discourages_midday_outdoor(weather),
            },
            "gio_cao_diem": VIETNAM_TRAFFIC_PEAK_POLICY,
            "quy_tac": [
                "Bữa trưa giữ trong khung 11:30 đến 13:30.",
                "Bữa tối giữ trong khung 18:00 đến 21:00.",
                "Chợ đêm được xếp sau 18:00.",
                "Điểm ngoài trời tránh buổi trưa khi trời nóng hoặc mưa nếu có dữ liệu thời tiết.",
                "Điểm ngắm cảnh/ngoài trời được ưu tiên gần hoàng hôn khi có tính toán thiên văn.",
                "Mùa vụ/lễ hội theo thành phố được ghi như heuristic nội bộ; lịch sự kiện chính thức theo năm vẫn là điều kiện phát hành.",
                "Chặng di chuyển trong 07:00-09:00 hoặc 16:30-19:00 được đánh dấu rủi ro giờ cao điểm khi chưa có dữ liệu traffic live.",
                "Visit guidance đã lưu được ưu tiên khi có dữ liệu.",
            ],
        },
        "ngay": days,
        "anh_bia": None,
        "anh_bia_nguon": None,
        "luu_y": [
            copy[7],
            copy[8],
            *(
                [overflow["note"]]
                if overflow
                else []
            ),
            "Thoi gian di chuyen uu tien ma tran OSRM/PostgreSQL da build; cap thieu du lieu se duoc danh dau fallback.",
            "Neu co noi luu tru, lich trinh dung toa do do lam diem neo xuat phat/ket thuc thay vi chi dung tam thanh pho.",
        ],
    }
    try:
        plan = ai_adapter.assemble(draft, trusted_ids, request.ngon_ngu)
    except RuntimeError:
        plan = draft
        plan["luu_y"] = [
            *plan.get("luu_y", []),
            AI_FALLBACK_NOTE.get(request.ngon_ngu, AI_FALLBACK_NOTE["en"]),
        ][:6]
    evidence_places = tuple([*PLACES, *candidates, *sight_chosen, *meal_places])
    _attach_evidence(plan, request, evidence_places)
    if overflow:
        plan["tom_tat"] = overflow["summary"][:500]
        rest = [note for note in plan.get("luu_y", []) if note != overflow["note"]]
        plan["luu_y"] = [overflow["note"][:300], *rest][:6]
        plan["loi_chao_chang"] = overflow["greeting"]
    plan["danh_gia_chat_luong"] = _quality_report(plan, request, trusted_ids, evidence_places)
    errors = validate_plan(plan, trusted_ids, request)
    if errors:
        raise PipelineUnavailable("; ".join(errors))
    plan["tieu_de"] = _finalize_plan_title(plan.get("tieu_de"), destination_label, request, number_of_days)
    _attach_plan_cover(plan, destination_label)
    return plan
