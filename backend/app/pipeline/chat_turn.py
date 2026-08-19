import logging
import re

from app.data import PLACES
from app.pipeline.intent_parse import (
    DESTINATION_RADIUS_KM,
    FOCUS_DESTINATIONS,
    THEME_DESTINATION_PRIORITY,
    _CLOCK_RANGE_RE,
    _DATE_RANGE_RE,
    _destination_hits_in_order,
    _find_destination,
    _fold,
    _haversine_km,
    parse_intent,
)
from app.services.ai import _strip_cjk, _strip_chat_reasoning, ai_adapter
from app.text_utils import ascii_fold

logger = logging.getLogger(__name__)

_BARE_COUNT_RE = re.compile(r"^\s*([1-9]|[12][0-9]|30)\s*$")
_DURATION_PHRASES = {
    "vai gio": "3 giờ",
    "few hours": "3 hours",
    "nua ngay": "5 giờ",
    "half day": "5 hours",
    "ca ngay": "1 ngày",
    "full day": "1 day",
    "mot ngay": "1 ngày",
    "one day": "1 day",
    "nhieu ngay": "2 ngày",
    "multiple days": "2 days",
    "multi day": "2 days",
}


def _user_texts(messages: list[dict]) -> list[str]:
    texts: list[str] = []
    for item in messages:
        if item.get("role") != "user":
            continue
        content = " ".join(str(item.get("content") or "").split())
        if content:
            texts.append(content)
    return texts


def _fold_phrase(value: str) -> str:
    return " ".join(ascii_fold(value).casefold().split())


_PEOPLE_ASK_HINTS = (
    "may nguoi",
    "bao nhieu nguoi",
    "di cung",
    "di voi ai",
    "cung ai",
    "gia dinh",
    "ban be",
    "mot minh",
    "how many people",
    "traveling with",
    "with family",
    "with friends",
    "group size",
)
_DURATION_ASK_HINTS = (
    "may ngay",
    "bao nhieu ngay",
    "bao lau",
    "keo dai",
    "trong bao nhieu ngay",
    "how many days",
    "how long",
)
_ITINERARY_MARKERS = (
    "ngay dau",
    "ngay thu nhat",
    "ngay thu hai",
    "ngay 1",
    "ngay 2",
    "day 1",
    "day 2",
    "buoi sang",
    "buoi trua",
    "buoi chieu",
    "buoi toi",
    "lich trinh chi tiet",
    "goi y lich trinh",
    "duoi day la",
)
_ACK_EXACT = {
    "ok",
    "oke",
    "okay",
    "okey",
    "dc",
    "duoc",
    "duoc roi",
    "uh",
    "um",
    "u",
    "uk",
    "vang",
    "vang a",
    "da",
    "roi",
    "roi nha",
    "yes",
    "yep",
    "yeah",
    "sure",
    "alright",
    "got it",
}


def _expand_last(last: str, missing: list[str] | None = None, assistant: str = "") -> str:
    folded = _fold_phrase(last)
    mapped = _DURATION_PHRASES.get(folded)
    if mapped:
        return mapped
    count = _BARE_COUNT_RE.match(last)
    if not count:
        return last
    missing = missing or []
    slot = _assistant_asked_slot(assistant)
    if slot == "people":
        return f"{count.group(1)} người"
    if slot == "duration":
        return f"{count.group(1)} ngày"
    if slot == "both" or "duration" in missing:
        return f"{count.group(1)} ngày"
    if "people" in missing:
        return f"{count.group(1)} người"
    return last


def _asks_people(folded: str) -> bool:
    return any(hint in folded for hint in _PEOPLE_ASK_HINTS)


def _asks_duration(folded: str) -> bool:
    return any(hint in folded for hint in _DURATION_ASK_HINTS)


def _assistant_question_tail(text: str) -> str:
    folded = _fold_phrase(text)
    if not folded:
        return ""
    chunks = [part.strip() for part in re.split(r"[?!.]", folded) if part.strip()]
    if chunks:
        return " ".join(chunks[-2:])[-240:]
    return folded[-240:]


def _assistant_asked_slot(text: str) -> str | None:
    folded = _fold_phrase(text)
    if not folded:
        return None
    tail = _assistant_question_tail(text)
    people = _asks_people(tail)
    duration = _asks_duration(tail)
    if people and duration:
        return "both"
    if people:
        return "people"
    if duration:
        return "duration"
    people = _asks_people(folded)
    duration = _asks_duration(folded)
    if people and duration:
        return "both"
    if people:
        return "people"
    if duration:
        return "duration"
    return None


def _looks_like_itinerary(text: str) -> bool:
    folded = _fold_phrase(text)
    hits = sum(1 for marker in _ITINERARY_MARKERS if marker in folded)
    if hits >= 2:
        return True
    if hits >= 1 and any(token in folded for token in ("lich trinh", "tham quan", "chua ", "itinerary", "leo nui")):
        return True
    return False


def _asks_two_slots(text: str) -> bool:
    folded = _fold_phrase(text)
    return _asks_duration(folded) and _asks_people(folded)


def _is_ack(text: str) -> bool:
    return _fold_phrase(text) in _ACK_EXACT


def _compose_context(messages: list[dict], missing: list[str] | None = None) -> str:
    texts: list[str] = []
    last_assistant = ""
    last_user_index = -1
    for index, item in enumerate(messages):
        if item.get("role") == "user" and str(item.get("content") or "").strip():
            last_user_index = index
    for index, item in enumerate(messages):
        role = item.get("role")
        content = " ".join(str(item.get("content") or "").split())
        if not content:
            continue
        if role == "assistant":
            last_assistant = content
            continue
        if role != "user":
            continue
        slot_missing = missing if index == last_user_index else None
        texts.append(_expand_last(content, slot_missing, last_assistant))
    return "\n".join(texts)


_UNCERTAIN_EXACT = {
    "khong biet",
    "toi khong biet",
    "chua biet",
    "dau cung duoc",
    "cung duoc",
    "tuy",
    "tuy ban",
    "ban chon",
    "ban chon giup",
    "chon giup",
    "goi y",
    "goi y cho toi",
    "surprise me",
    "whatever",
    "anywhere",
    "any place",
    "idk",
    "i dont know",
    "i don't know",
}

_UNCERTAIN_PHRASES = (
    "khong biet",
    "chua biet",
    "dau cung duoc",
    "ban chon giup",
    "chon giup",
    "goi y cho toi",
    "goi y",
    "surprise me",
    "i dont know",
    "i don't know",
    "anywhere is fine",
)


def _last_user_text(messages: list[dict]) -> str:
    texts = _user_texts(messages)
    return texts[-1] if texts else ""


def _last_assistant_text(messages: list[dict]) -> str:
    for item in reversed(messages):
        if str(item.get("role") or "").strip().lower() == "assistant":
            return str(item.get("content") or "").strip()
    return ""


_PLACE_ASK_PHRASES = (
    "cho nao choi",
    "cho nao",
    "choi gi",
    "co gi hay",
    "co gi choi",
    "co nhung",
    "dia diem",
    "tham quan",
    "nen di dau",
    "di dau choi",
    "o dau choi",
    "choi o",
    "places to",
    "what to do",
    "what to see",
    "attractions",
    "things to do",
    "where to visit",
)


_SLOT_PEOPLE = {
    "1 nguoi",
    "2 nguoi",
    "4 nguoi",
    "1 person",
    "2 people",
    "4 people",
    "mot minh",
    "one person",
}

_QUESTION_HINTS = (
    "an gi",
    "an uong",
    "mon gi",
    "choi gi",
    "co gi",
    "cho nao",
    "o dau",
    "khi nao",
    "mua nao",
    "bao nhieu",
    "the nao",
    "lam sao",
    "nen o",
    "nen di",
    "nen an",
    "di chuyen",
    "thoi tiet",
    "khach san",
    "o khu",
    "co dong",
    "co dep",
    "mac gi",
    "di bang",
    "bao lau",
    "may ngay thi",
    "toi dang hoi",
    "dia diem",
    "tham quan",
    "lich trinh",
    "places to",
    "what to",
    "where to",
    "how to",
    "how much",
    "when to",
    "best time",
)

_FOOD_HINTS = (
    "an gi",
    "an uong",
    "mon gi",
    "quan an",
    "dac san",
    "food",
    "eat",
    "pho ",
    " bun",
    "cafe",
)

_SEASON_HINTS = (
    "mua nao",
    "di mua",
    "mua dep",
    "thang nao",
    "thoi diem",
    "khi nao di",
    "khi nao nen",
    "best time",
    "which season",
    "when to go",
    "when to visit",
    "mua mua",
    "mua kho",
    "mua hoa",
)

_SEASON_NOTES_VI = {
    "Đà Lạt": "Đà Lạt dễ chịu nhất khoảng tháng 11 đến tháng 3: se lạnh, khô hơn, hoa nở nhiều. Tháng 5–10 vẫn đi được nhưng mưa chiều khá thường.",
    "Hà Nội": "Hà Nội đẹp dễ đi khoảng tháng 3–4 và tháng 9–11. Tháng 6–8 nóng ẩm, tháng 12–2 se lạnh, có thể có nồm.",
    "Sa Pa": "Sa Pa đẹp tầm tháng 9–11 (lúa chín) và tháng 3–5. Tháng 12–2 rất lạnh, có thể có băng giá.",
    "Phú Quốc": "Phú Quốc nên đi mùa khô khoảng tháng 11 đến tháng 4. Tháng 5–10 sóng gió, mưa nhiều hơn.",
    "Nha Trang": "Nha Trang đẹp biển khoảng tháng 1–8. Tháng 9–12 hay mưa, biển động hơn.",
    "Hội An": "Hội An dễ chịu khoảng tháng 2–5. Tháng 10–11 mưa, có lúc ngập phố cổ.",
    "Đà Nẵng": "Đà Nẵng đẹp khoảng tháng 2–5. Tháng 9–11 mưa bão, biển kém dễ chịu hơn.",
}

_SEASON_NOTES_EN = {
    "Đà Lạt": "Da Lat is nicest from November to March: cooler and drier. May–October is still doable but afternoon rain is common.",
    "Hà Nội": "Hanoi is easiest in March–April and September–November. June–August is hot; December–February is cool and damp.",
}

_BEACH_HINTS = (
    "di bien",
    "muon di bien",
    "tam bien",
    "bai bien",
    "nghi bien",
    "bien ",
    " bien",
    "beach",
    "seaside",
)
_HEALING_HINTS = (
    "stress",
    "cang thang",
    "ap luc",
    "met moi",
    "met qua",
    "chua lanh",
    "healing",
    "thu gian",
    "yen tinh",
    "burnout",
    "nhe dau",
    "do met",
    "can nghi",
    "detox",
    "met ",
    "an ui",
    "buon",
)
_MOUNTAIN_HINTS = (
    "leo nui",
    "di nui",
    "trekking",
    "nui ",
    "mountain",
    "hiking",
    "san may",
)
_BEACH_CITIES = set(THEME_DESTINATION_PRIORITY["beach"])
_MOUNTAIN_CITIES = set(THEME_DESTINATION_PRIORITY["mountain"])
_INLAND_SIGHT_MARKERS = (
    "duc ba",
    "nha tho",
    "nguyen hue",
    "uy ban nhan dan",
    "tuong dai chu tich",
    "pho di bo",
)

_DURATION_ONLY_MARKERS = (
    "ban di khoang may ngay",
    "ban muon di khoang may ngay",
    "how many days",
)
_PLACE_SLOT_FOLLOWUP_HINTS = (
    "may ngay",
    "bao nhieu ngay",
    "bao lau",
    "how many days",
    "how long",
    "du dinh di",
    "di trong bao",
)
_GARBLE_RE = re.compile(r"[\u3000-\u303f\uff00-\uffef]|\s,(\s|$)|,\s+[,.]")


def _looks_like_question(text: str) -> bool:
    raw = text or ""
    folded = _fold_phrase(raw)
    if not folded:
        return False
    if "?" in raw or "？" in raw:
        return True
    if folded.endswith(" khong") or folded.endswith(" ko") or folded.endswith(" chu"):
        return True
    return any(hint in folded for hint in _QUESTION_HINTS)


def _is_destination_only(text: str) -> bool:
    folded = _fold_phrase(text)
    if not folded:
        return False
    names = {_fold_phrase(item.name) for item in FOCUS_DESTINATIONS}
    return folded in names


def _is_date_range_fill(text: str) -> bool:
    if _looks_like_question(text):
        return False
    folded = _fold_phrase(text)
    return bool(folded and _DATE_RANGE_RE.search(folded))


def _is_clock_fill(text: str) -> bool:
    if _looks_like_question(text) or _is_date_range_fill(text):
        return False
    folded = _fold_phrase(text)
    if not folded:
        return False
    if _CLOCK_RANGE_RE.search(folded):
        return True
    return bool(re.fullmatch(r"\d{1,2}(?:[:.]\d{2})?\s*(?:h|gio|tieng)(?:\s*dong ho)?", folded))


def _looks_confused(text: str) -> bool:
    folded = _fold_phrase(text)
    return bool(re.fullmatch(
        r"(?:ua |huh )?(?:(?:cai )?gi(?: the| day| vay)?|sao(?: vay)?|kho hieu|noi gi(?: vay)?)",
        folded,
    ))


def _is_slot_fill(text: str) -> bool:
    if _looks_like_question(text):
        return False
    folded = _fold_phrase(text)
    if folded in _UNCERTAIN_EXACT or folded in _DURATION_PHRASES or folded in _SLOT_PEOPLE:
        return True
    if _BARE_COUNT_RE.match((text or "").strip()):
        return True
    if re.fullmatch(r"[1-9]\d?\s*(nguoi|ngay|gio|hours?|days?|people|person)", folded):
        return True
    if _is_date_range_fill(text) or _is_clock_fill(text):
        return True
    return _is_destination_only(text)


def _is_count_fill(text: str) -> bool:
    if _is_destination_only(text) or _looks_like_question(text):
        return False
    return _is_slot_fill(text)


def _committed_destination(messages: list[dict]):
    if not _is_count_fill(_last_user_text(messages)):
        return None
    assistant = _last_assistant_text(messages)
    if not assistant:
        return None
    folded = _fold(assistant)
    places = _destination_hits_in_order(folded)
    transit = set()
    for match in re.finditer(r"\b(?:tu|from)\s+(.{0,48})", folded):
        window = match.group(1)
        for place in places:
            if _fold(place.name) in window:
                transit.add(place.name)
    focused = [place for place in places if place.name not in transit]
    names = list(dict.fromkeys(item.name for item in focused))
    if not names or len(names) >= 3:
        return None
    return focused[0]


def _lock_destination_on_slot_fill(intent: dict, messages: list[dict]) -> dict:
    last_user = _last_user_text(messages)
    if not _is_count_fill(last_user):
        return intent
    parsed = dict(intent.get("parsed") or {})
    current = parsed.get("destination") if isinstance(parsed.get("destination"), dict) else None
    user_dest = _find_destination(_fold(last_user)) if last_user else None
    if current and current.get("name") and (not user_dest or user_dest.name == current.get("name")):
        return intent
    committed = _committed_destination(messages)
    if not committed:
        return intent
    parsed = dict(intent.get("parsed") or {})
    current = parsed.get("destination") if isinstance(parsed.get("destination"), dict) else None
    if current and current.get("name") == committed.name:
        return intent
    parsed["destination"] = {"name": committed.name, "lat": committed.lat, "lng": committed.lng}
    missing = [field for field in (intent.get("missing_fields") or []) if field != "destination"]
    updated = dict(intent)
    updated["parsed"] = parsed
    updated["missing_fields"] = missing
    if missing:
        updated["status"] = "ask_user_missing_fields"
        if "duration" in missing:
            updated["question"] = f"Mình hiểu bạn muốn đi {committed.name}. Bạn đi khoảng mấy ngày?"
        elif "people" in missing:
            updated["question"] = f"Đi {committed.name} thì bạn đi mấy người?"
        else:
            updated["question"] = None
    else:
        updated["status"] = "ready_to_plan"
        updated["question"] = None
    return updated


def _rejects_destination(text: str, dest_name: str) -> bool:
    folded = _fold_phrase(text)
    name = _fold_phrase(dest_name)
    if not folded or not name:
        return False
    return bool(re.search(
        rf"(?:khong|ko|chang)\s+(?:muon\s+)?(?:di|den|ve|thich)?\s*.{{0,16}}{re.escape(name)}",
        folded,
    ))


def _clear_destination(intent: dict) -> dict:
    parsed = dict(intent.get("parsed") or {})
    parsed["destination"] = None
    missing = ["destination", *[field for field in (intent.get("missing_fields") or []) if field != "destination"]]
    updated = dict(intent)
    updated["parsed"] = parsed
    updated["missing_fields"] = list(dict.fromkeys(missing))
    updated["status"] = "ask_user_missing_fields"
    updated["question"] = None
    return updated


def _wants_chat_answer(text: str) -> bool:
    if _is_ack(text) or _is_slot_fill(text) or _looks_confused(text):
        return False
    if _asks_to_plan(text):
        return False
    if _looks_like_question(text):
        return True
    topic = _classify_topic(text)
    return topic in {"season", "food", "beach", "mountain", "places", "healing", "tips"}


_PLAN_HINTS = (
    "len lich",
    "xep lich",
    "lap lich",
    "tao lich",
    "len plan",
    "thiet ke lich",
    "make a plan",
    "itinerary",
)


def _asks_to_plan(text: str) -> bool:
    folded = _fold_phrase(text)
    return any(hint in folded for hint in _PLAN_HINTS)


def _asks_about_food(text: str) -> bool:
    folded = _fold_phrase(text)
    return any(hint in folded for hint in _FOOD_HINTS)


def _asks_about_season(text: str) -> bool:
    folded = _fold_phrase(text)
    return any(hint in folded for hint in _SEASON_HINTS)


def _asks_about_beach(text: str) -> bool:
    folded = f" {_fold_phrase(text)} "
    return any(hint in folded for hint in _BEACH_HINTS) or folded.strip().endswith("bien")


def _asks_about_mountain(text: str) -> bool:
    folded = f" {_fold_phrase(text)} "
    return any(hint in folded for hint in _MOUNTAIN_HINTS)


def _asks_about_healing(text: str) -> bool:
    folded = f" {_fold_phrase(text)} "
    return any(hint in folded for hint in _HEALING_HINTS)


def _classify_topic(text: str) -> str:
    if _asks_about_season(text):
        return "season"
    if _asks_about_healing(text):
        return "healing"
    if _asks_about_beach(text):
        return "beach"
    if _asks_about_mountain(text):
        return "mountain"
    if _asks_about_food(text):
        return "food"
    if _asks_about_tips(text):
        return "tips"
    if _asks_about_places(text):
        return "places"
    return "general"


def _theme_suggestions(purpose: str, near: str | None = None) -> list[dict]:
    by_name = {item.name: item for item in FOCUS_DESTINATIONS}
    names = list(THEME_DESTINATION_PRIORITY.get(purpose, ()))
    if purpose == "beach" and near in {"TP.HCM", "Cần Thơ"}:
        names = ["Vũng Tàu", *[name for name in names if name != "Vũng Tàu"]]
    suggestions: list[dict] = []
    for name in names:
        item = by_name.get(name)
        if not item:
            continue
        suggestions.append({"label": item.name, "lat": item.lat, "lng": item.lng, "reason": purpose})
        if len(suggestions) >= 4:
            break
    return suggestions


def _fits_theme(name: str, topic: str) -> bool:
    if topic == "beach":
        return name in _BEACH_CITIES
    if topic == "mountain":
        return name in _MOUNTAIN_CITIES
    return True


def _suggestion_labels(intent: dict, limit: int | None = None) -> str:
    names = [
        str(item.get("label") or item.get("name") or "").strip()
        for item in (intent.get("suggestions") or [])
        if isinstance(item, dict)
    ]
    names = [name for name in names if name]
    if limit:
        names = names[:limit]
    return ", ".join(names)


def _pivot_away_from_destination(intent: dict, topic: str, from_name: str) -> dict:
    parsed = dict(intent.get("parsed") or {})
    parsed["destination"] = None
    parsed["primary_intent"] = topic
    parsed["trip_purpose"] = topic
    missing = [field for field in (intent.get("missing_fields") or []) if field != "destination"]
    updated = dict(intent)
    updated["parsed"] = parsed
    updated["missing_fields"] = ["destination", *missing]
    updated["suggestions"] = _theme_suggestions(topic, from_name)
    updated["status"] = "ask_user_missing_fields"
    updated["question"] = None
    updated["highlight_places"] = []
    updated["theme_from"] = from_name
    updated["theme_pivot"] = True
    return updated


def _season_note(destination_name: str, locale: str) -> str:
    table = _SEASON_NOTES_VI if locale == "vi" else _SEASON_NOTES_EN
    return table.get(destination_name) or (
        f"{destination_name} nên xem mùa khô/mùa mưa của vùng đó. Miền Bắc có bốn mùa; miền Nam chủ yếu nắng và mưa."
        if locale == "vi"
        else f"For {destination_name}, check the local dry vs rainy months. The north has four seasons; the south is mostly wet/dry."
    )


def _mentions_season(text: str) -> bool:
    folded = _fold_phrase(text)
    return any(token in folded for token in ("mua", "thang", "season", "november", "rainy", "dry"))


def _looks_uncertain(text: str) -> bool:
    folded = _fold_phrase(text)
    if not folded:
        return False
    if folded in _UNCERTAIN_EXACT:
        return True
    return any(phrase in folded for phrase in _UNCERTAIN_PHRASES)


_TIPS_HINTS = (
    "chu y",
    "luu y",
    "can mang",
    "nen mang",
    "mang gi",
    "mac gi",
    "nen mac",
    "chuan bi gi",
    "kieng ki",
    "what to bring",
    "what to pack",
    "things to know",
    "watch out",
    "pay attention",
)


def _asks_about_tips(text: str) -> bool:
    folded = _fold_phrase(text)
    return bool(folded) and any(hint in folded for hint in _TIPS_HINTS)


def _asks_about_places(text: str) -> bool:
    folded = _fold_phrase(text)
    if not folded:
        return False
    if _asks_about_tips(text):
        return False
    if any(phrase in folded for phrase in _PLACE_ASK_PHRASES):
        return True
    return "?" in (text or "") and any(
        token in folded for token in ("choi", "cho nao", "dia diem", "where", "what to", "attractions")
    )


def _highlight_places(destination: dict | None, limit: int = 5, mode: str = "sights") -> list[str]:
    if not isinstance(destination, dict):
        return []
    try:
        lat = float(destination["lat"])
        lng = float(destination["lng"])
    except (KeyError, TypeError, ValueError):
        return []
    sight_kinds = {"dia_danh", "di_tich", "bao_tang", "cong_vien", "cho"}
    food_kinds = {"nha_hang", "quan_an", "cafe", "am_thuc"}
    ranked: list[tuple[int, float, str]] = []
    for place in PLACES:
        dist = _haversine_km(lat, lng, place.lat, place.lng)
        if dist > DESTINATION_RADIUS_KM:
            continue
        if mode == "food":
            if place.kind not in food_kinds and not {"am_thuc", "food", "an_uong"}.intersection(place.tags):
                continue
        elif place.kind in {"khach_san"} and place.source != "curated":
            continue
        score = 0
        if place.source == "curated":
            score += 80
        if any(str(tag).endswith("_icon") for tag in place.tags):
            score += 20
        if mode == "food" and place.kind in food_kinds:
            score += 16
        if mode != "food" and place.kind in sight_kinds:
            score += 12
        if place.rating:
            score += int(place.rating * 4)
        ranked.append((score, -dist, place.name))
    ranked.sort(reverse=True)
    names: list[str] = []
    seen: set[str] = set()
    for _, _, name in ranked:
        key = _fold_phrase(name)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _mentions_any_place(text: str, names: list[str]) -> bool:
    folded = _fold_phrase(text)
    return any(_fold_phrase(name) and _fold_phrase(name) in folded for name in names)


def _auto_pick_destination(intent: dict, locale: str) -> dict:
    parsed = dict(intent.get("parsed") or {})
    if parsed.get("destination"):
        return intent
    suggestions = [item for item in (intent.get("suggestions") or []) if isinstance(item, dict)]
    if not suggestions:
        return intent
    picked = suggestions[0]
    name = str(picked.get("label") or picked.get("name") or "").strip()
    if not name:
        return intent
    parsed["destination"] = {
        "name": name,
        "lat": picked.get("lat"),
        "lng": picked.get("lng"),
    }
    missing = [field for field in (intent.get("missing_fields") or []) if field != "destination"]
    updated = dict(intent)
    updated["parsed"] = parsed
    updated["missing_fields"] = missing
    updated["suggestions"] = []
    updated["auto_picked_destination"] = True
    if missing:
        updated["status"] = "ask_user_missing_fields"
        if "duration" in missing:
            updated["question"] = (
                f"Mình chọn {name} giúp bạn. Bạn muốn đi khoảng mấy ngày?"
                if locale == "vi"
                else f"I'll pick {name} for you. How many days would you like?"
            )
        elif "people" in missing:
            updated["question"] = (
                f"Mình chọn {name} giúp bạn. Đi mấy người?"
                if locale == "vi"
                else f"Let's go with {name}. How many people?"
            )
        else:
            updated["question"] = None
    else:
        updated["status"] = "ready_to_plan"
        updated["question"] = None
    return updated


def _repeats_city_script(text: str) -> bool:
    folded = ascii_fold(text or "")
    hits = sum(
        1
        for city in ("ha noi", "da nang", "da lat", "sa pa", "ninh binh", "phu quoc", "hoi an")
        if city in folded
    )
    return hits >= 3


def _is_duration_only_script(text: str, destination_name: str = "", known_names: list[str] | None = None) -> bool:
    folded = _fold_phrase(text)
    if not folded:
        return False
    if destination_name:
        script = _fold_phrase(f"Ok, mình hiểu bạn muốn đi {destination_name}. Bạn đi khoảng mấy ngày?")
        if folded == script:
            return True
    if not any(marker in folded for marker in _DURATION_ONLY_MARKERS):
        return False
    if known_names and _mentions_any_place(text, known_names):
        return False
    return len(folded.split()) <= 18


def _asks_place_question_slot_followup(text: str) -> bool:
    folded = _fold_phrase(text)
    return bool(folded) and any(hint in folded for hint in _PLACE_SLOT_FOLLOWUP_HINTS)


def _looks_garbled_reply(text: str) -> bool:
    return bool(_GARBLE_RE.search(text or ""))


def _sanitize_reply(reply: str, intent: dict, messages: list[dict], locale: str = "vi") -> str:
    text = _strip_cjk(" ".join(str(reply or "").split()).strip(), locale)
    if not text:
        return ""
    previous = _last_assistant_text(messages)
    destination = ((intent.get("parsed") or {}).get("destination") or {}).get("name") or ""
    highlights = [name for name in (intent.get("highlight_places") or []) if isinstance(name, str)]
    foods = [name for name in (intent.get("highlight_foods") or []) if isinstance(name, str)]
    topic = intent.get("ask_topic") or "general"
    folded = _fold_phrase(text)
    if not _strip_chat_reasoning(text):
        return ""
    if intent.get("user_goal") == "places" and _looks_garbled_reply(text):
        return ""
    if previous and (_fold_phrase(text) == _fold_phrase(previous) or (
        len(previous) > 24 and _fold_phrase(previous)[:48] in _fold_phrase(text)
    )):
        return ""
    if topic in {"beach", "mountain"} and any(marker in folded for marker in _INLAND_SIGHT_MARKERS):
        return ""
    if destination and topic not in {"beach", "mountain"} and _repeats_city_script(text):
        return ""
    if intent.get("user_goal") in {"answer", "places"} and _is_duration_only_script(text, destination, highlights + foods):
        return ""
    if intent.get("user_goal") == "places" and topic == "places" and _asks_place_question_slot_followup(text):
        return ""
    if topic == "tips" and (
        "nhieu cho hay" in folded or "di bo trong pho" in folded or "walk in the city" in folded
    ):
        return ""
    if intent.get("ask_topic") == "healing" and _asks_place_question_slot_followup(text):
        return ""
    if _looks_like_itinerary(text):
        return ""
    if intent.get("status") != "ready_to_plan" and _asks_two_slots(text):
        return ""
    if topic == "season" and not _mentions_season(text):
        return ""
    question = str(intent.get("question") or "").strip()
    if question and _fold_phrase(text) == _fold_phrase(question) and _repeats_city_script(text):
        return ""
    return text


_DESTINATION_BLURBS_VI = {
    "Đà Lạt": "se lạnh, thông và sương",
    "Sa Pa": "núi mây, ruộng bậc thang",
    "Ninh Bình": "sông núi, đi thuyền yên",
    "Phú Quốc": "đảo, biển và hoàng hôn",
    "Nha Trang": "biển trong, tắm dễ",
    "Đà Nẵng": "biển và núi gần nhau",
    "Vũng Tàu": "gần Sài Gòn, đi trong ngày",
    "Hà Giang": "đèo đá, săn mây",
    "Huế": "chậm, sông Hương",
    "Quảng Bình": "động và thiên nhiên",
    "Phan Thiết": "biển, đồi cát",
    "Hội An": "phố cổ, đèn lồng",
    "Hà Nội": "phố cổ, hồ",
    "TP.HCM": "ăn uống, đi đêm",
}
_DESTINATION_BLURBS_EN = {
    "Đà Lạt": "cool pine air",
    "Sa Pa": "clouds and terraces",
    "Ninh Bình": "rivers and limestone",
    "Phú Quốc": "island sunsets",
    "Nha Trang": "clear swimming water",
    "Đà Nẵng": "beach next to mountains",
    "Vũng Tàu": "close to Saigon",
    "Hà Giang": "highland passes",
}


def _theme_place_blurbs(intent: dict, locale: str, topic: str, near: str | None = None) -> str:
    suggestions = intent.get("suggestions") or _theme_suggestions(
        topic if topic != "healing" else "healing",
        near,
    )
    names = [
        str(item.get("label") or item.get("name") or "").strip()
        for item in suggestions
        if isinstance(item, dict)
    ]
    names = [name for name in names if name][:4]
    blurbs = _DESTINATION_BLURBS_VI if locale == "vi" else _DESTINATION_BLURBS_EN
    parts = []
    for name in names:
        note = blurbs.get(name)
        parts.append(f"{name} ({note})" if note else name)
    return ", ".join(parts)


def _theme_fallback(intent: dict, locale: str) -> str | None:
    topic = intent.get("ask_topic")
    if topic not in {"beach", "mountain", "healing"}:
        return None
    destination = ((intent.get("parsed") or {}).get("destination") or {}).get("name")
    from_city = intent.get("theme_from")
    names = _theme_place_blurbs(intent, locale, topic, from_city or destination)
    if locale == "vi":
        if topic == "healing":
            if destination:
                return (
                    f"Mệt thì mình ở đây nghe bạn, không cần lên lịch ngay. "
                    f"Nếu muốn đi cho nhẹ đầu thì {names or 'Đà Lạt (se lạnh, thông và sương), Ninh Bình (sông núi yên)'} cũng hợp hơn phố. "
                    "Bạn muốn mình an ủi tiếp hay gợi ý chỗ khác?"
                )
            return (
                f"Nghe bạn đang mệt. Đi chữa lành mình hay nghĩ {names}. "
                "Bạn nghiêng chỗ nào cho nhẹ đầu?"
            )
        if topic == "beach":
            if destination and _fits_theme(str(destination), "beach"):
                return f"{destination} hợp đi biển. Bạn muốn đi khoảng mấy ngày để mình xếp lịch tắm biển cụ thể hơn?"
            if from_city:
                return (
                    f"{from_city} không sát biển. Gần nhất thường là Vũng Tàu (đi trong ngày); "
                    f"muốn nghỉ biển hơn thì {names}. Bạn muốn đi biển ở đâu?"
                )
            return f"Muốn đi biển thì mình gợi ý {names}. Bạn muốn tắm biển ở đâu?"
        if destination and _fits_theme(str(destination), "mountain"):
            return f"{destination} hợp leo núi và săn mây. Bạn muốn đi khoảng mấy ngày?"
        if from_city:
            return f"Leo núi thì {from_city} không phải lựa chọn hợp. Mình gợi ý {names}. Bạn muốn đi núi ở đâu?"
        return f"Leo núi mình hay nghĩ {names}. Bạn muốn đi núi ở đâu?"
    if topic == "healing":
        if destination:
            return (
                "I'm here with you — no need to plan a trip right now. "
                f"If you do want a quiet reset, {names or 'Da Lat, Sa Pa'} might feel lighter. "
                "Want comfort, or a different place?"
            )
        return f"Sounds like you need a reset. I'd start with {names}. Where would you like to go?"
    if topic == "beach":
        if destination and _fits_theme(str(destination), "beach"):
            return f"{destination} is great for the beach. How many days should I plan?"
        if from_city:
            return (
                f"{from_city} is not on the coast. Vung Tau is closest; "
                f"for a longer beach trip try {names}. Where do you want to go?"
            )
        return f"For a beach trip I'd suggest {names}. Where should I plan?"
    if destination and _fits_theme(str(destination), "mountain"):
        return f"{destination} is great for mountains. How many days?"
    if from_city:
        return f"{from_city} is not a mountain trip. I'd suggest {names}. Where do you want to go?"
    return f"For mountains in Vietnam I'd start with {names}. Where do you want to go?"


_DESTINATION_INTROS_VI = {
    "Yên Tử": "Yên Tử ở Quảng Ninh là danh thắng tâm linh trên núi, khí trời mát và yên, hợp đi chậm để tĩnh tâm.",
    "Đà Lạt": "Đà Lạt se lạnh, nhiều thông và sương, hợp nghỉ cho nhẹ đầu.",
    "Sa Pa": "Sa Pa trên Tây Bắc, núi mây và ruộng bậc thang, không khí lạnh và chậm.",
    "Ninh Bình": "Ninh Bình nhiều núi đá và sông, đi thuyền hay leo động đều khá yên.",
    "Hội An": "Hội An phố cổ đèn lồng, đi bộ chậm và ăn ngon.",
    "Nha Trang": "Nha Trang biển trong, hợp tắm biển và nghỉ.",
    "Phú Quốc": "Phú Quốc đảo lớn, biển và sunset khá đã.",
    "Hà Nội": "Hà Nội phố cổ, hồ và nhịp sống riêng, hợp đi bộ khám phá.",
    "Đà Nẵng": "Đà Nẵng biển và núi gần nhau, đi lại tiện.",
    "Huế": "Huế chậm, nhiều di tích và sông Hương.",
    "TP.HCM": "TP.HCM năng động, ăn uống và đi đêm khá vui.",
}
_DESTINATION_INTROS_EN = {
    "Yên Tử": "Yen Tu in Quang Ninh is a quiet mountain pilgrimage site — cool air, temples, and a slower pace.",
}


def _destination_intro(name: str | None, locale: str) -> str:
    if not name:
        return ""
    table = _DESTINATION_INTROS_VI if locale == "vi" else _DESTINATION_INTROS_EN
    return table.get(name) or (
        f"{name} là một điểm đến đáng đi ở Việt Nam."
        if locale == "vi"
        else f"{name} is a worthwhile place to visit in Vietnam."
    )


def _fallback_reply(intent: dict, locale: str) -> str:
    destination = ((intent.get("parsed") or {}).get("destination") or {}).get("name")
    missing = intent.get("missing_fields") or []
    auto_picked = bool(intent.get("auto_picked_destination"))
    highlights = [name for name in (intent.get("highlight_places") or []) if isinstance(name, str)]
    place_list = ", ".join(highlights[:4])
    if intent.get("status") == "ready_to_plan":
        if locale == "vi":
            return (
                f"Mình đã đủ thông tin cho {destination}. Mình bắt đầu thiết kế lịch trình nhé."
                if destination
                else "Mình đã đủ thông tin. Mình bắt đầu thiết kế lịch trình nhé."
            )
        return (
            f"I have enough to plan {destination}. I'll design the itinerary now."
            if destination
            else "I have enough to start designing the itinerary."
        )
    theme_reply = _theme_fallback(intent, locale)
    if theme_reply:
        return theme_reply
    if locale == "vi":
        if intent.get("user_goal") in {"places", "answer"} and destination:
            topic = intent.get("ask_topic") or "general"
            if topic in {"season", "food", "places", "beach", "mountain", "tips"}:
                if topic == "season":
                    note = _season_note(str(destination), locale)
                    return f"{note} Nếu muốn mình xếp lịch theo mùa đó, nói luôn đi mấy ngày nhé."
                if topic == "tips":
                    note = _season_note(str(destination), locale)
                    return (
                        f"{note} "
                        "Nên mang đồ theo thời tiết chỗ đó, đi chậm trên đường đèo/phố đông, và đừng nhồi quá nhiều điểm một ngày."
                    )
                foods = [name for name in (intent.get("highlight_foods") or []) if isinstance(name, str)]
                food_list = ", ".join(foods[:3])
                if topic == "food" and food_list:
                    return f"Ở {destination} nên thử {food_list}."
                if topic == "places" and place_list:
                    return (
                        f"Ở {destination} nhiều chỗ hay — ví dụ {place_list}. "
                        "Bạn đang muốn đi bộ trong phố, thiên nhiên, hay ăn uống?"
                    )
                if place_list:
                    return f"Ở {destination} nhiều chỗ hay — ví dụ {place_list}."
        if auto_picked and destination and "duration" in missing:
            return f"Mình chọn {destination} giúp bạn. Bạn muốn đi khoảng mấy ngày?"
        if auto_picked and destination and "people" in missing:
            return f"Mình chọn {destination} giúp bạn. Đi mấy người?"
        if destination and "duration" in missing:
            intro = _destination_intro(str(destination), locale)
            return f"{intro} Bạn muốn đi khoảng mấy ngày?"
        if destination and "people" in missing:
            window = (intent.get("parsed") or {}).get("time_window") or {}
            label = window.get("label") if isinstance(window, dict) else None
            if label:
                return f"Khung {label} mình nhận rồi. Đi {destination} thì bạn đi mấy người?"
            days = (intent.get("parsed") or {}).get("duration_days")
            if days:
                return f"Lịch {days} ngày mình nhận rồi. Đi {destination} thì bạn đi mấy người?"
            return f"Đi {destination} thì bạn đi mấy người?"
        if "destination" in missing:
            names = ", ".join(
                item.get("label") or item.get("name") or ""
                for item in (intent.get("suggestions") or [])[:3]
                if isinstance(item, dict) and (item.get("label") or item.get("name"))
            )
            purpose = str((intent.get("parsed") or {}).get("primary_intent") or (intent.get("parsed") or {}).get("trip_purpose") or "")
            if names and purpose in {"healing", "beach", "mountain"}:
                if purpose == "healing":
                    return f"{names} đều hợp nghỉ cho nhẹ đầu — bạn nghiêng chỗ nào?"
                if purpose == "beach":
                    return f"Vậy mình gợi ý biển ở {names}. Bạn muốn đi đâu?"
                return f"Leo núi thì {names} đáng thử. Bạn nghiêng chỗ nào?"
            if names:
                return f"Bạn muốn đi đâu lần này? Nếu chưa nghĩ ra, mình có thể chọn giúp — ví dụ {names}."
            return "Bạn muốn đi đâu lần này?"
        return intent.get("question") or "Bạn muốn đi đâu?"
    if intent.get("user_goal") in {"places", "answer"} and destination:
        topic = intent.get("ask_topic") or "general"
        if topic in {"season", "food", "places", "beach", "mountain", "tips"}:
            if topic == "season":
                note = _season_note(str(destination), locale)
                return f"{note} If you want an itinerary for that season, tell me how many days."
            if topic == "tips":
                note = _season_note(str(destination), locale)
                return (
                    f"{note} "
                    "Pack for the local weather, take mountain/city roads slowly, and don't cram too many stops into one day."
                )
            foods = [name for name in (intent.get("highlight_foods") or []) if isinstance(name, str)]
            food_list = ", ".join(foods[:3])
            extra = f" For food, try {food_list}." if food_list and topic == "food" else ""
            if topic == "food" and food_list:
                return f"In {destination} try {food_list}."
            if topic == "places" and place_list:
                return f"In {destination} a good start is {place_list}. Want city wandering, nature, or food?"
            if extra:
                return f"Got your question about {destination}.{extra}".strip()
    if auto_picked and destination and "duration" in missing:
        return f"I'll pick {destination} for you. How many days would you like?"
    if auto_picked and destination and "people" in missing:
        return f"Let's go with {destination}. How many people?"
    if destination and "duration" in missing:
        intro = _destination_intro(str(destination), locale)
        return f"{intro} How many days would you like?"
    if destination and "people" in missing:
        return f"{destination} is locked in. How many people?"
    return intent.get("question") or "Where do you want to go?"


def _repeat_recovery_reply(intent: dict, locale: str) -> str:
    topic = intent.get("ask_topic") or ""
    last_user = str(intent.get("last_user_message") or "")
    if topic == "healing" or _asks_about_healing(last_user):
        names = _theme_place_blurbs(intent, locale, "healing") or "Đà Lạt (se lạnh, thông và sương), Ninh Bình (sông núi yên)"
        if locale == "vi":
            return (
                f"Mình nghe bạn mệt thật, không cần quyết ngay. "
                f"Nếu muốn đi cho nhẹ đầu thì {names} cũng được. Bạn nghiêng chỗ nào?"
            )
        return "I'm still here with you. No need to pick a trip yet — beach, mountain, or somewhere cooler?"
    destination = ((intent.get("parsed") or {}).get("destination") or {}).get("name")
    missing = intent.get("missing_fields") or []
    if locale == "vi":
        if "people" in missing:
            return f"Mình hỏi lại cho rõ: đi {destination or 'chuyến này'} thì bạn đi mấy người?"
        if "duration" in missing:
            return f"Bạn muốn đi {destination or 'chuyến này'} khoảng mấy ngày, hay một khung giờ như 15h–18h?"
        return "Bạn nói rõ hơn một chút được không? Mình đang nghe để xếp lịch."
    if "people" in missing:
        return f"Just to confirm — how many people for {destination or 'the trip'}?"
    if "duration" in missing:
        return f"How long for {destination or 'the trip'}: a few hours, a time window like 3–6pm, or a few days?"
    return "Could you say a bit more so I can plan?"


def run_chat_turn(messages: list[dict], locale: str = "vi") -> dict:
    context = _compose_context(messages)
    if len(context) < 2:
        intent = {
            "status": "ask_user_missing_fields",
            "question": "Bạn muốn đi đâu?" if locale == "vi" else "Where would you like to go?",
            "missing_fields": ["destination", "duration", "people"],
            "suggestions": [],
            "parsed": {"destination": None},
        }
        return {"reply": _fallback_reply(intent, locale), "intent": intent, "ready_to_plan": False}

    intent = parse_intent(context, locale)
    missing = list(intent.get("missing_fields") or [])
    expanded = _compose_context(messages, missing)
    if expanded != context:
        intent = parse_intent(expanded, locale)

    if _looks_uncertain(_last_user_text(messages)):
        intent = _auto_pick_destination(intent, locale)
    intent = _lock_destination_on_slot_fill(intent, messages)

    last_user = _last_user_text(messages)
    intent = dict(intent)
    intent["last_user_message"] = last_user
    dest_name = str(((intent.get("parsed") or {}).get("destination") or {}).get("name") or "")
    if dest_name and _rejects_destination(last_user, dest_name):
        intent = _clear_destination(intent)
        dest_name = ""
    topic = _classify_topic(last_user)
    dest_in_last = bool(dest_name) and _fold_phrase(dest_name) in _fold_phrase(last_user)
    planning_statement = (
        dest_in_last
        and not _looks_like_question(last_user)
        and not _rejects_destination(last_user, dest_name)
        and topic not in {"season", "food", "places", "healing", "tips"}
    )
    if _wants_chat_answer(last_user) and not planning_statement:
        intent["user_goal"] = "places" if topic == "places" else "answer"
        intent["ask_topic"] = topic
        destination = dict((intent.get("parsed") or {}).get("destination") or {})
        if topic in {"beach", "mountain"}:
            if dest_name and not _fits_theme(dest_name, topic):
                intent = _pivot_away_from_destination(intent, topic, dest_name)
            else:
                intent["suggestions"] = _theme_suggestions(topic, dest_name or None)
                if dest_name:
                    intent["highlight_places"] = _highlight_places(
                        (intent.get("parsed") or {}).get("destination") or destination
                    )
        elif topic == "healing":
            intent["suggestions"] = _theme_suggestions("healing", dest_name or None)
        elif dest_name:
            if topic == "season":
                intent["season_note"] = _season_note(dest_name, locale)
            elif topic == "food":
                intent["highlight_foods"] = _highlight_places(destination, limit=3, mode="food")
            elif topic == "tips":
                intent["season_note"] = _season_note(dest_name, locale)
            elif topic == "places":
                intent["highlight_places"] = _highlight_places(destination)

    if planning_statement and dest_name:
        destination = dict((intent.get("parsed") or {}).get("destination") or {})
        intent["highlight_places"] = _highlight_places(destination)
        intent["ask_topic"] = "destination_intro"

    reply = ""
    use_llm = not _is_slot_fill(last_user) and not _is_ack(last_user) and not _looks_confused(last_user)
    composer = getattr(ai_adapter, "compose_chat_reply", None)
    if use_llm and composer:
        try:
            reply = composer(messages=messages, intent=intent, locale=locale) or ""
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("compose_chat_reply failed: %s", exc)
            reply = ""
    reply = _sanitize_reply(reply, intent, messages, locale)
    if _looks_confused(last_user):
        reply = ""
    if not reply:
        reply = _fallback_reply(intent, locale)
        previous = _last_assistant_text(messages)
        if previous and _fold_phrase(reply) == _fold_phrase(previous):
            reply = _repeat_recovery_reply(intent, locale)
    return {
        "reply": reply[:800],
        "intent": intent,
        "ready_to_plan": intent.get("status") == "ready_to_plan",
    }
