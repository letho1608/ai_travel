import math
import re
from dataclasses import dataclass
from typing import Literal

from app.data import PLACES, Place
from app.services.ai import ai_adapter
from app.text_utils import ascii_fold
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_TRIP_DAYS = 30
DESTINATION_RADIUS_KM = 55.0


@dataclass(frozen=True)
class IntentDestination:
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class ThemeSpec:
    terms: tuple[str, ...]
    allowed_place_themes: tuple[str, ...]
    avoid_place_themes: tuple[str, ...]
    tags: tuple[str, ...]
    kinds: tuple[str, ...]


class AIPlanningTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_hour: int | None = Field(default=None, ge=0, le=23)
    start_minute: int | None = Field(default=None, ge=0, le=59)
    end_hour: int | None = Field(default=None, ge=0, le=23)
    end_minute: int | None = Field(default=None, ge=0, le=59)


class AIPlanningAmbiguity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=60)
    value: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=300)
    question: str = Field(min_length=1, max_length=300)


class AIPlanningIntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str | None = Field(default=None, max_length=40)
    destination_text: str | None = Field(default=None, max_length=120)
    trip_purpose: Literal["general_travel", "healing", "beach", "mountain", "food", "cafe"] | None = None
    duration_value: float | None = Field(default=None, gt=0, le=30)
    duration_unit: Literal["minute", "hour", "day", "week"] | None = None
    time_window: AIPlanningTimeWindow | None = None
    people: int | None = Field(default=None, ge=1, le=30)
    budget: int | None = Field(default=None, ge=50_000, le=100_000_000)
    preferences: list[str] = Field(default_factory=list, max_length=12)
    dislikes: list[str] = Field(default_factory=list, max_length=12)
    must_visit: list[str] = Field(default_factory=list, max_length=12)
    ambiguities: list[AIPlanningAmbiguity] = Field(default_factory=list, max_length=8)

    @field_validator("destination_text")
    @classmethod
    def clean_destination(cls, value: str | None) -> str | None:
        return " ".join(value.replace("<", "").replace(">", "").split()) if value else None

    @field_validator("preferences", "dislikes", "must_visit")
    @classmethod
    def clean_text_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            normalized = " ".join(str(item).replace("<", "").replace(">", "").split())[:120]
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


FOCUS_DESTINATIONS: tuple[IntentDestination, ...] = (
    IntentDestination("Hà Nội", 21.0285, 105.8542),
    IntentDestination("TP.HCM", 10.7769, 106.7009),
    IntentDestination("Đà Nẵng", 16.0544, 108.2022),
    IntentDestination("Hội An", 15.8801, 108.3380),
    IntentDestination("Huế", 16.4637, 107.5909),
    IntentDestination("Đà Lạt", 11.9404, 108.4583),
    IntentDestination("Nha Trang", 12.2388, 109.1967),
    IntentDestination("Ninh Bình", 20.2506, 105.9745),
    IntentDestination("Hạ Long", 20.9712, 107.0448),
    IntentDestination("Sa Pa", 22.3364, 103.8438),
    IntentDestination("Phú Quốc", 10.2899, 103.9840),
    IntentDestination("Cần Thơ", 10.0452, 105.7469),
    IntentDestination("Vũng Tàu", 10.3460, 107.0843),
    IntentDestination("Quy Nhơn", 13.7820, 109.2197),
    IntentDestination("Phan Thiết", 10.9273, 108.1021),
    IntentDestination("Quảng Bình", 17.4764, 106.6022),
    IntentDestination("Hà Giang", 22.8233, 104.9839),
    IntentDestination("Hải Phòng", 20.8449, 106.6881),
)

DESTINATION_ALIASES: dict[str, tuple[str, ...]] = {
    "Hà Nội": ("ha noi", "hanoi", "thu do"),
    "TP.HCM": ("tp hcm", "ho chi minh", "sai gon", "saigon", "thanh pho ho chi minh"),
    "Đà Nẵng": ("da nang", "danang"),
    "Hội An": ("hoi an", "pho co hoi an"),
    "Huế": ("hue", "thua thien hue", "co do hue"),
    "Đà Lạt": ("da lat", "dalat", "lam dong"),
    "Nha Trang": ("nha trang", "khanh hoa"),
    "Ninh Bình": ("ninh binh", "trang an", "bai dinh", "tam coc"),
    "Hạ Long": ("ha long", "halong", "quang ninh", "vinh ha long"),
    "Sa Pa": ("sa pa", "sapa", "lao cai", "fansipan"),
    "Phú Quốc": ("phu quoc", "dao phu quoc", "kien giang"),
    "Cần Thơ": ("can tho", "tay do", "ninh kieu"),
    "Vũng Tàu": ("vung tau", "ba ria vung tau"),
    "Quy Nhơn": ("quy nhon", "binh dinh", "eo gio", "ky co"),
    "Phan Thiết": ("phan thiet", "mui ne", "binh thuan"),
    "Quảng Bình": ("quang binh", "dong hoi", "phong nha"),
    "Hà Giang": ("ha giang", "dong van", "ma pi leng"),
    "Hải Phòng": ("hai phong", "cat ba", "do son"),
}

THEMES: dict[str, ThemeSpec] = {
    "general_travel": ThemeSpec(
        terms=("du lich", "di choi", "tham quan", "travel", "trip"),
        allowed_place_themes=("landmark", "culture", "food", "nature", "viewpoint"),
        avoid_place_themes=(),
        tags=("view_dep", "checkin", "heritage", "local", "van_hoa"),
        kinds=("dia_danh", "bao_tang", "di_tich", "cong_vien", "cho", "bai_bien", "nui"),
    ),
    "healing": ThemeSpec(
        terms=("chua lanh", "healing", "nghi duong", "di tron", "chill", "thu gian", "yen tinh", "di nhe"),
        allowed_place_themes=("quiet", "nature", "lake", "forest", "cafe_chill", "viewpoint", "slow_walk"),
        avoid_place_themes=("crowded_landmark", "heavy_history", "dense_schedule", "strenuous_activity"),
        tags=("chill", "yen_tinh", "thu_gian", "view_dep", "ngoai_troi", "ho", "song", "beach", "bien"),
        kinds=("cong_vien", "dia_danh", "bai_bien", "nui", "cafe"),
    ),
    "beach": ThemeSpec(
        terms=("bien", "bai bien", "dao", "hai san", "hoang hon bien", "ngam hoang hon", "san ho", "beach", "island"),
        allowed_place_themes=("beach", "island", "seafood", "sunset", "coastal_view", "resort"),
        avoid_place_themes=("urban_museum", "inland_landmark"),
        tags=("beach", "bien", "dao", "island", "ngoai_troi", "view_dep", "hai_san"),
        kinds=("bai_bien", "dia_danh", "nha_hang", "quan_an"),
    ),
    "mountain": ThemeSpec(
        terms=("leo nui", "trekking", "trail", "san may", "dinh nui", "dinh", "deo", "fansipan", "langbiang"),
        allowed_place_themes=("mountain", "trekking", "trail", "peak", "pass", "viewpoint", "nature"),
        avoid_place_themes=("museum", "urban_landmark", "shopping"),
        tags=("nui", "peak", "trekking", "trail", "viewpoint", "ngoai_troi", "view_dep"),
        kinds=("nui", "hang_dong", "dia_danh"),
    ),
    "food": ThemeSpec(
        terms=("an ngon", "am thuc", "food", "hai san", "nha hang", "quan an", "an vat"),
        allowed_place_themes=("food", "local_food", "market", "seafood"),
        avoid_place_themes=(),
        tags=("am_thuc", "local", "hai_san", "an_vat", "dac_san"),
        kinds=("nha_hang", "quan_an", "cho"),
    ),
    "cafe": ThemeSpec(
        terms=("cafe", "coffee", "ca phe", "caphe"),
        allowed_place_themes=("cafe", "cafe_chill", "viewpoint", "slow_walk"),
        avoid_place_themes=("dense_schedule",),
        tags=("cafe", "coffee", "chill", "view_dep"),
        kinds=("cafe", "dia_danh", "cong_vien"),
    ),
}


def _fold(value: str) -> str:
    return " ".join(ascii_fold(value).casefold().split())


def _contains_term(folded: str, term: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", folded))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _find_destination(folded: str) -> IntentDestination | None:
    by_name = {item.name: item for item in FOCUS_DESTINATIONS}
    for name, aliases in DESTINATION_ALIASES.items():
        if any(_contains_term(folded, alias) for alias in aliases):
            return by_name[name]
    return None


def _place_theme_score(place: Place, spec: ThemeSpec | None) -> int:
    if spec is None:
        return int(place.kind in {"dia_danh", "bao_tang", "bai_bien", "nui", "cong_vien"}) + len(set(place.tags).intersection({"view_dep", "checkin", "local"}))
    tags = set(place.tags)
    score = 0
    if place.kind in spec.kinds:
        score += 6
    score += len(tags.intersection(spec.tags)) * 3
    if place.source == "curated":
        score += 2
    if isinstance(place.rating, int | float) and place.rating >= 4.5:
        score += 1
    return score


PLACE_THEME_KINDS: dict[str, set[str]] = {
    "landmark": {"dia_danh", "di_tich"},
    "culture": {"bao_tang", "di_tich"},
    "urban_museum": {"bao_tang"},
    "museum": {"bao_tang"},
    "food": {"nha_hang", "quan_an", "cho"},
    "local_food": {"nha_hang", "quan_an", "cho"},
    "market": {"cho"},
    "cafe": {"cafe"},
    "cafe_chill": {"cafe"},
    "beach": {"bai_bien"},
    "island": {"bai_bien", "dia_danh"},
    "seafood": {"nha_hang", "quan_an"},
    "mountain": {"nui", "hang_dong"},
    "trekking": {"nui", "hang_dong"},
    "trail": {"nui"},
    "peak": {"nui"},
    "pass": {"nui", "dia_danh"},
    "nature": {"cong_vien", "bai_bien", "nui", "hang_dong"},
    "lake": {"cong_vien", "dia_danh"},
    "forest": {"cong_vien", "nui"},
    "viewpoint": {"dia_danh", "nui", "bai_bien", "cong_vien"},
    "quiet": {"cong_vien", "bai_bien", "nui", "cafe"},
    "slow_walk": {"cong_vien", "dia_danh", "cafe"},
    "crowded_landmark": set(),
    "heavy_history": {"bao_tang", "di_tich"},
    "urban_landmark": set(),
    "inland_landmark": set(),
    "shopping": {"cho"},
}

PLACE_THEME_TAGS: dict[str, set[str]] = {
    "landmark": {"checkin", "hanoi_icon", "heritage", "van_hoa"},
    "culture": {"museum", "van_hoa", "heritage", "history", "lich_su"},
    "urban_museum": {"museum"},
    "museum": {"museum"},
    "food": {"am_thuc", "an_vat", "local", "vietnamese"},
    "local_food": {"am_thuc", "an_vat", "local", "dac_san"},
    "market": {"cho_dem", "night_market", "local"},
    "cafe": {"cafe", "coffee"},
    "cafe_chill": {"cafe", "coffee", "chill", "view_dep", "yen_tinh"},
    "beach": {"beach", "bien"},
    "island": {"dao", "island"},
    "seafood": {"hai_san"},
    "sunset": {"hoang_hon", "view_dep", "bien"},
    "coastal_view": {"beach", "bien", "view_dep"},
    "mountain": {"nui", "peak", "fansipan"},
    "trekking": {"trekking", "trail", "nui"},
    "trail": {"trail", "trekking"},
    "peak": {"peak", "nui"},
    "pass": {"deo", "pass", "view_dep"},
    "nature": {"ngoai_troi", "view_dep", "beach", "bien", "nui", "ho", "song"},
    "lake": {"ho", "song", "view_dep", "yen_tinh"},
    "forest": {"rung", "ngoai_troi", "nui"},
    "viewpoint": {"view_dep", "checkin", "peak"},
    "quiet": {"chill", "yen_tinh", "thu_gian"},
    "slow_walk": {"di_bo", "chill", "ngoai_troi", "yen_tinh"},
    "crowded_landmark": {"hanoi_icon", "lang_bac", "checkin"},
    "heavy_history": {"history", "lich_su", "museum", "di_tich", "lang_bac"},
    "urban_landmark": {"hanoi_icon", "pho_co", "checkin"},
    "inland_landmark": {"hanoi_icon", "heritage", "pho_co"},
    "shopping": {"shopping", "market"},
}


def place_themes(place: Place) -> set[str]:
    tags = set(place.tags)
    themes: set[str] = set()
    for theme, kinds in PLACE_THEME_KINDS.items():
        if place.kind in kinds:
            themes.add(theme)
    for theme, theme_tags in PLACE_THEME_TAGS.items():
        if tags.intersection(theme_tags):
            themes.add(theme)
    return themes


def place_policy_score(place: Place, allowed: set[str], avoided: set[str]) -> int:
    themes = place_themes(place)
    return 4 * len(themes.intersection(allowed)) - 8 * len(themes.intersection(avoided))


def place_matches_policy(place: Place, allowed: set[str], avoided: set[str]) -> bool:
    themes = place_themes(place)
    if avoided and themes.intersection(avoided):
        return False
    if allowed and not themes.intersection(allowed):
        return False
    return True


def _destination_suggestions(purpose: str | None) -> list[dict]:
    spec = THEMES.get(purpose or "")
    scored: list[tuple[int, IntentDestination, list[str]]] = []
    for destination in FOCUS_DESTINATIONS:
        matches: list[tuple[int, Place]] = []
        for place in PLACES:
            if _haversine_km(destination.lat, destination.lng, place.lat, place.lng) > DESTINATION_RADIUS_KM:
                continue
            score = _place_theme_score(place, spec)
            if score > 0:
                matches.append((score, place))
        if not matches:
            continue
        matches.sort(key=lambda item: (-item[0], item[1].id))
        top = matches[:8]
        score = sum(item[0] for item in top)
        reasons = []
        for _score, place in top[:3]:
            if place.kind not in reasons:
                reasons.append(place.kind)
        scored.append((score, destination, reasons))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    return [
        {
            "label": destination.name,
            "lat": destination.lat,
            "lng": destination.lng,
            "reason": "nhiều điểm phù hợp trong catalog: " + ", ".join(reasons),
            "score": score,
        }
        for score, destination, reasons in scored[:4]
    ]


def _duration_shape(days: int | None, minutes: int | None, window: dict | None) -> tuple[str | None, str | None, float | None, str | None, int | None]:
    if days:
        if days == 1:
            return "ca_ngay", "day", 1, "day_trip", None
        mode = "long_trip" if days >= 8 else "multi_day_trip"
        return "nhieu_ngay", "day", days, mode, None
    effective_minutes = window["minutes"] if window else minutes
    if effective_minutes is None:
        return None, None, None, "intent_discovery", None
    if effective_minutes < 45:
        return None, "minute", effective_minutes, "micro_visit", effective_minutes
    if effective_minutes <= 240:
        return "vai_gio", "minute", effective_minutes, "short_trip", effective_minutes
    if effective_minutes <= 420:
        return "nua_ngay", "minute", effective_minutes, "short_trip", effective_minutes
    return "ca_ngay", "minute", effective_minutes, "day_trip", effective_minutes


def _fallback_parse_intent(context: str, locale: str = "vi") -> dict:
    return {
        "schema_version": "intent-parse-v2",
        "extraction_source": "fallback_unavailable",
        "status": "ask_user_missing_fields",
        "question": "Mình chưa đọc được yêu cầu đủ chắc chắn. Bạn cho biết điểm đến, thời lượng và số người nhé?",
        "missing_fields": ["destination", "duration", "people"],
        "ambiguities": [],
        "validation_errors": [{
            "field": "intent",
            "code": "ai_intent_unavailable",
            "message": "AI intent normalization không khả dụng hoặc trả schema không hợp lệ; backend không tự suy đoán bằng regex.",
        }],
        "suggestions": [],
        "parsed": {
            "destination": None,
            "trip_purpose": None,
            "primary_intent": None,
            "planner_mode": "needs_clarification",
            "duration": None,
            "duration_value": None,
            "duration_unit": None,
            "duration_minutes": None,
            "duration_days": None,
            "time_window": None,
            "people": None,
            "budget": None,
            "date": None,
            "allowed_place_themes": [],
            "avoid_place_themes": [],
            "confidence": "low",
        },
    }


def _coerce_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _coerce_int(value: object) -> int | None:
    number = _coerce_number(value)
    return round(number) if number is not None else None


def _coerce_purpose(value: object) -> str | None:
    return value if isinstance(value, str) and value in THEMES else None


def _resolve_destination(value: object) -> IntentDestination | None:
    if not isinstance(value, str) or not value.strip():
        return None
    folded = _fold(value)
    found = _find_destination(folded)
    if found:
        return found
    by_name = {_fold(item.name): item for item in FOCUS_DESTINATIONS}
    return by_name.get(folded)


def _normalize_time_window(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    start_hour = _coerce_int(value.get("start_hour"))
    end_hour = _coerce_int(value.get("end_hour"))
    start_minute = _coerce_int(value.get("start_minute")) or 0
    end_minute = _coerce_int(value.get("end_minute")) or 0
    if start_hour is None or end_hour is None:
        return None
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23 and 0 <= start_minute < 60 and 0 <= end_minute < 60):
        return None
    start_total = start_hour * 60 + start_minute
    end_total = end_hour * 60 + end_minute
    if end_total <= start_total:
        end_total += 24 * 60
    minutes = end_total - start_total
    if minutes < 45 or minutes > 16 * 60:
        return None
    return {
        "start_hour": start_hour,
        "start_minute": start_minute,
        "end_hour": end_hour,
        "end_minute": end_minute,
        "minutes": minutes,
        "label": f"{start_hour}h–{end_hour}h",
    }


def _time_window_validation_error(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    start_hour = _coerce_int(value.get("start_hour"))
    end_hour = _coerce_int(value.get("end_hour"))
    start_minute = _coerce_int(value.get("start_minute")) or 0
    end_minute = _coerce_int(value.get("end_minute")) or 0
    if start_hour is None or end_hour is None:
        return None
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23 and 0 <= start_minute < 60 and 0 <= end_minute < 60):
        return {
            "field": "time_window",
            "code": "time_window_invalid_clock",
            "message": "Khung giờ không hợp lệ.",
        }
    start_total = start_hour * 60 + start_minute
    end_total = end_hour * 60 + end_minute
    if end_total <= start_total:
        end_total += 24 * 60
    minutes = end_total - start_total
    if minutes < 45:
        return {
            "field": "time_window",
            "code": "time_window_too_short",
            "message": "Khung giờ này quá ngắn để lập lịch trình nhiều điểm.",
        }
    if minutes > 16 * 60:
        return {
            "field": "time_window",
            "code": "time_window_too_long",
            "message": "Khung giờ này quá dài cho một ngày lịch trình.",
        }
    return None


def _normalize_duration(value: object, unit: object) -> tuple[int | None, int | None]:
    number = _coerce_number(value)
    if number is None or not isinstance(unit, str):
        return None, None
    if unit == "week":
        return min(MAX_TRIP_DAYS, round(number * 7)), None
    if unit == "day":
        return min(MAX_TRIP_DAYS, round(number)), None
    if unit == "hour":
        return None, round(number * 60)
    if unit == "minute":
        return None, round(number)
    return None, None


def _normalize_ambiguities(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    ambiguities: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        question = str(item.get("question") or "").strip()
        if field and question:
            ambiguities.append({
                "field": field,
                "value": str(item.get("value") or "").strip(),
                "reason": str(item.get("reason") or "").strip(),
                "question": question,
            })
    return ambiguities


def _normalize_ai_intent(context: str, payload: dict) -> dict:
    payload = AIPlanningIntentPayload.model_validate(payload).model_dump(exclude_none=True)
    purpose = _coerce_purpose(payload.get("trip_purpose"))
    destination = _resolve_destination(payload.get("destination_text"))
    raw_window = payload.get("time_window")
    window = _normalize_time_window(raw_window)
    days, minutes = _normalize_duration(payload.get("duration_value"), payload.get("duration_unit"))
    if window:
        minutes = None
    duration, duration_unit, duration_value, planner_mode, duration_minutes = _duration_shape(days, minutes, window)
    people = _coerce_int(payload.get("people"))
    budget = _coerce_int(payload.get("budget"))
    ambiguities = _normalize_ambiguities(payload.get("ambiguities"))
    spec = THEMES.get(purpose or "")

    missing: list[str] = []
    validation_errors: list[dict] = []
    window_error = _time_window_validation_error(raw_window) if raw_window and not window else None
    if window_error:
        missing.append("duration")
        validation_errors.append(window_error)
    if duration_minutes is not None and duration_minutes < 45:
        missing.append("duration")
        validation_errors.append({
            "field": "duration",
            "code": "duration_too_short_for_itinerary",
            "message": "Thời lượng này quá ngắn để lập lịch trình nhiều điểm.",
        })
    if any(item.get("field") == "duration" for item in ambiguities):
        missing.append("duration")
    if not destination:
        missing.append("destination")
    if duration is None and "duration" not in missing:
        missing.append("duration")
    if people is None:
        missing.append("people")
    missing = list(dict.fromkeys(missing))

    suggestions = _destination_suggestions(purpose) if not destination else []
    question = None
    if validation_errors:
        if validation_errors[0]["code"] == "duration_too_short_for_itinerary":
            question = "30 phút hơi ngắn để lập lịch trình. Bạn muốn tìm 1 điểm gần nhất hay tăng thời lượng lên 1-2 giờ?"
        elif validation_errors[0]["code"] == "time_window_too_short":
            question = "Khung giờ này hơi ngắn. Bạn muốn tìm 1 điểm gần nhất hay tăng thời lượng lên 1-2 giờ?"
        elif validation_errors[0]["code"] == "time_window_too_long":
            question = "Khung giờ này quá dài cho một ngày. Bạn muốn chia thành nhiều ngày hay chọn khung giờ ngắn hơn?"
        else:
            question = "Khung giờ chưa hợp lệ. Bạn muốn đi từ mấy giờ đến mấy giờ?"
    elif ambiguities:
        question = ambiguities[0]["question"]
    elif "destination" in missing:
        question = "Bạn muốn đi ở đâu? Mình gợi ý vài điểm phù hợp để bạn chọn." if suggestions else "Bạn muốn đi điểm đến/thành phố nào?"
    elif "duration" in missing:
        question = "Bạn đi trong bao lâu: vài giờ, 1 ngày hay nhiều ngày?"
    elif "people" in missing:
        question = "Bạn đi mấy người?"

    parsed_destination = None
    if destination:
        parsed_destination = {"name": destination.name, "lat": destination.lat, "lng": destination.lng}
    return {
        "schema_version": "intent-parse-v2",
        "extraction_source": "ai",
        "status": "ask_user_missing_fields" if missing else "ready_to_plan",
        "question": question,
        "missing_fields": missing,
        "ambiguities": ambiguities,
        "validation_errors": validation_errors,
        "suggestions": suggestions,
        "parsed": {
            "destination": parsed_destination,
            "trip_purpose": purpose,
            "primary_intent": purpose,
            "planner_mode": planner_mode,
            "duration": duration,
            "duration_value": duration_value,
            "duration_unit": duration_unit,
            "duration_minutes": duration_minutes,
            "duration_days": days,
            "time_window": window,
            "people": people,
            "budget": budget,
            "date": None,
            "allowed_place_themes": list(spec.allowed_place_themes) if spec else [],
            "avoid_place_themes": list(spec.avoid_place_themes) if spec else [],
            "confidence": "high" if destination or purpose or days or window or minutes else "low",
            "extraction_source": "ai",
        },
    }


def parse_intent(context: str, locale: str = "vi", extractor=None) -> dict:
    extractor = extractor or getattr(ai_adapter, "extract_planning_intent", None)
    if extractor:
        try:
            payload = extractor(context, locale)
            if isinstance(payload, dict) and payload:
                return _normalize_ai_intent(context, payload)
        except (RuntimeError, TypeError, ValueError, ValidationError):
            pass
    result = _fallback_parse_intent(context, locale)
    result["parsed"]["extraction_source"] = result["extraction_source"]
    return result
