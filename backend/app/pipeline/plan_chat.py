import logging
import re

from app.pipeline.chat_turn import _looks_like_question
from app.pipeline.intent_parse import (
    FOCUS_DESTINATIONS,
    THEMES,
    _duration_shape,
    _extract_purpose,
    _find_destination,
    _fold,
    _rule_extract,
)
from app.pipeline.planner import _destination_context
from app.schemas import Coordinate, IntentPolicy, PlanRequest
from app.services.ai import ai_adapter
from app.text_utils import ascii_fold

logger = logging.getLogger(__name__)

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

_NEW_ITINERARY_HINTS = (
    "lich trinh khac",
    "doi lich",
    "doi tiep",
    "lam lai",
    "plan khac",
    "itinerary khac",
    "xep lai",
    "lich khac",
    "doi cho toi lich",
    "another itinerary",
    "different itinerary",
    "new itinerary",
)
_SWAP_STOP_HINTS = (
    "doi diem nay",
    "thay diem nay",
    "doi cho nay",
    "doi diem dang chon",
    "doi cho dang chon",
    "swap this",
    "replace this",
    "doi diem do",
    "thay diem",
    "doi diem",
)
_CHANGE_WORDS = ("doi", "thay", "swap", "replace")
_MEAL_PHRASES = (
    ("nghi trua", ("trua", "nghi")),
    ("bua trua", ("trua",)),
    ("an trua", ("trua",)),
    ("cho an trua", ("trua",)),
    ("diem nghi", ("nghi",)),
    ("lunch", ("trua", "nghi")),
    ("bua toi", ("toi",)),
    ("an toi", ("toi",)),
    ("dinner", ("toi",)),
    ("bua sang", ("sang",)),
    ("an sang", ("sang",)),
    ("breakfast", ("sang",)),
)
_DINING_KINDS = {"nha_hang", "quan_an", "cafe"}
_WANT_DEST_HINTS = (
    "muon di",
    "muon den",
    "doi sang",
    "chuyen sang",
    "chuyen qua",
    "xep lich",
    "len lich",
)
_THEME_HINTS = (
    "an uong",
    "am thuc",
    "an ngon",
    "nha hang",
    "quan an",
    "food tour",
)


def _folded(message: str) -> str:
    return " ".join(ascii_fold(message).casefold().split())


def plan_stops(plan: dict | None, theme: str | None = None) -> list[str]:
    slots = [
        slot
        for day in (plan or {}).get("ngay") or []
        for slot in day.get("khoang_gio") or []
    ]
    if theme == "food":
        food_slots = [
            slot for slot in slots
            if slot.get("loai") in {"nha_hang", "quan_an", "cho", "cafe"} or slot.get("bua_an")
        ]
        if food_slots:
            slots = food_slots
    names: list[str] = []
    for slot in slots:
        name = str(slot.get("ten_dia_diem") or "").strip()
        if name and name not in names:
            names.append(name)
    return names[:8]


def current_destination_label(item) -> str | None:
    request = PlanRequest.model_validate(item.request)
    return _destination_context(request)[2]


def _wants_new_itinerary(folded: str) -> bool:
    if any(hint in folded for hint in _NEW_ITINERARY_HINTS):
        if "doi tiep" in folded and "diem" in folded:
            return False
        return True
    return False


def _wants_change_word(folded: str) -> bool:
    return any(word in folded for word in _CHANGE_WORDS)


def named_meal_types(folded: str) -> tuple[str, ...] | None:
    for phrase, meals in _MEAL_PHRASES:
        if phrase in folded:
            return meals
    if _wants_change_word(folded) and "trua" in folded:
        return ("trua", "nghi")
    return None


def _wants_swap_stop(folded: str) -> bool:
    if named_meal_types(folded) and _wants_change_word(folded):
        return True
    return any(hint in folded for hint in _SWAP_STOP_HINTS)


def _plan_slots(plan: dict | None) -> list[dict]:
    return [
        slot
        for day in (plan or {}).get("ngay") or []
        for slot in day.get("khoang_gio") or []
        if slot.get("dia_diem_id")
    ]


def target_slot_id_for_message(
    plan: dict | None, message: str, selected_id: str | None = None
) -> str | None:
    folded = _folded(message)
    slots = _plan_slots(plan)
    meals = named_meal_types(folded)
    if meals:
        for meal in meals:
            found = [slot for slot in slots if slot.get("bua_an") == meal]
            if found:
                return found[0].get("dia_diem_id")
        if any(meal in {"trua", "nghi"} for meal in meals):
            for slot in slots:
                start = str(slot.get("bat_dau") or "")[:5]
                if "11:00" <= start <= "14:30" and slot.get("loai") in _DINING_KINDS | {"cong_vien"}:
                    return slot.get("dia_diem_id")
    if selected_id:
        return selected_id
    if any(word in folded for word in ("cafe", "ca phe", "coffee")):
        cafe_slots = [slot for slot in slots if slot.get("loai") in ("cafe", "ca_phe", "drinks")]
        if cafe_slots:
            return cafe_slots[0].get("dia_diem_id")
    return slots[0].get("dia_diem_id") if slots else None


def _wants_theme_change(message: str, folded: str) -> str | None:
    purpose = _extract_purpose(_fold(message))
    if purpose in {"food", "cafe", "beach", "mountain", "healing"}:
        return purpose
    if any(hint in folded for hint in _THEME_HINTS):
        return "food"
    return None


_CONSTRAINT_HINTS = (
    "cheaper",
    "lower cost",
    "save money",
    "re hon",
    "tiet kiem",
    "gia re",
    "it tien",
    "less travel",
    "shorter route",
    "nearby",
    "it di chuyen",
    "gan nhau",
    "gan hon",
    "di bo it",
    "more cafe",
    "them cafe",
    "quan cafe",
    "ca phe",
)


def _constraint_change(message: str, folded: str) -> bool:
    if PEOPLE_INTENT.search(message):
        return True
    if re.search(
        r"(?:ngân sách|budget|dưới|tối đa)\s*(\d+(?:[.,]\d+)?)\s*(k|nghìn|triệu|tr)?",
        message,
        re.IGNORECASE,
    ):
        return True
    if "cafe" in folded or "coffee" in folded:
        return True
    return any(hint in folded for hint in _CONSTRAINT_HINTS)


def _focus_destination(message: str):
    dest = _find_destination(_fold(message))
    if dest and dest.name in {item.name for item in FOCUS_DESTINATIONS}:
        return dest
    return None


def classify_plan_message(message: str, item, selected_id: str | None = None) -> str:
    folded = _folded(message)
    current_label = current_destination_label(item)
    dest = _focus_destination(message)
    dest_changed = bool(dest and current_label and dest.name != current_label)
    if dest_changed:
        if _looks_like_question(message) and not any(hint in folded for hint in _WANT_DEST_HINTS):
            return "talk"
        return "rebuild"
    if _wants_new_itinerary(folded):
        return "rebuild"
    if _wants_swap_stop(folded):
        return "swap"
    if _wants_theme_change(message, folded) or _constraint_change(message, folded):
        return "rebuild"
    if selected_id and SWAP_INTENT.search(message) and "lich" not in folded:
        return "swap"
    return "talk"


def should_exclude_current_stops(message: str, item) -> bool:
    folded = _folded(message)
    dest = _focus_destination(message)
    current_label = current_destination_label(item)
    if dest and current_label and dest.name != current_label:
        return False
    if _wants_theme_change(message, folded):
        return True
    if _constraint_change(message, folded):
        return False
    return _wants_new_itinerary(folded)


def excluded_ids_for_refine(message: str, item) -> set[str] | None:
    folded = _folded(message)
    purpose = _wants_theme_change(message, folded)
    if purpose == "food":
        skipped = {
            slot["dia_diem_id"]
            for slot in _plan_slots(item.plan)
            if slot.get("loai") not in {"nha_hang", "quan_an", "cho", "cafe"}
            and not slot.get("bua_an")
        }
        return skipped or None
    if should_exclude_current_stops(message, item):
        return current_place_ids(item.plan)
    return None


def current_place_ids(plan: dict | None) -> set[str]:
    return {
        slot["dia_diem_id"]
        for day in (plan or {}).get("ngay") or []
        for slot in day.get("khoang_gio") or []
        if slot.get("dia_diem_id")
    }


def _merge_intent_policy(current: PlanRequest, purpose: str | None, rules: dict) -> IntentPolicy | None:
    spec = THEMES.get(purpose or "")
    duration, _unit, _value, planner_mode, duration_minutes = _duration_shape(
        rules.get("days"),
        rules.get("minutes"),
        rules.get("window"),
    )
    if not spec and duration is None and rules.get("window") is None:
        return current.intent_policy
    data = current.intent_policy.model_dump() if current.intent_policy else {
        "schema_version": "intent-parse-v2",
        "allowed_place_themes": [],
        "avoid_place_themes": [],
    }
    if spec:
        data["primary_intent"] = purpose
        data["allowed_place_themes"] = list(spec.allowed_place_themes)
        data["avoid_place_themes"] = list(spec.avoid_place_themes)
    if duration:
        data["duration"] = duration
        data["planner_mode"] = planner_mode
        data["duration_minutes"] = duration_minutes
        data["duration_days"] = rules.get("days")
    if rules.get("window"):
        data["time_window"] = rules["window"]
    try:
        return IntentPolicy.model_validate(data)
    except (TypeError, ValueError):
        return current.intent_policy


def refined_plan_request(item, message: str) -> PlanRequest:
    current = PlanRequest.model_validate(item.request)
    updates: dict = {"context": f"{current.context}; {message}"[-500:]}
    normalized = ascii_fold(message)
    people = PEOPLE_INTENT.search(message)
    if people:
        updates["so_nguoi"] = int(people.group(1))
    budget = re.search(
        r"(?:ngân sách|budget|dưới|tối đa)\s*(\d+(?:[.,]\d+)?)\s*(k|nghìn|triệu|tr)?",
        message,
        re.IGNORECASE,
    )
    if budget:
        amount = float(budget.group(1).replace(",", "."))
        unit = (budget.group(2) or "").lower()
        multiplier = 1_000_000 if unit in {"triệu", "tr"} else 1_000 if unit in {"k", "nghìn"} else 1
        updates["ngan_sach"] = round(amount * multiplier)
    if re.search(r"\b(cheaper|lower cost|save money|re hon|tiet kiem|gia re|it tien)\b", normalized):
        updates["ngan_sach"] = max(100_000, round((updates.get("ngan_sach") or current.ngan_sach) * 0.8))
        updates["context"] = f"{updates['context']}; prioritize lower-cost places and free/low-price experiences"[-500:]
    if any(hint in normalized for hint in ("less travel", "shorter route", "nearby", "it di chuyen", "gan nhau", "gan hon", "di bo it")):
        updates["context"] = f"{updates['context']}; keep stops geographically close together and reduce transfers"[-500:]
    if re.search(r"\b(more cafe|coffee|cafe|them cafe|quan cafe|ca phe)\b", normalized):
        updates["context"] = f"{updates['context']}; add more cafe and relaxed drink stops when suitable"[-500:]

    rules = _rule_extract(message)
    dest = _focus_destination(message)
    if dest:
        current_label = _destination_context(current)[2]
        if dest.name != current_label:
            updates["location"] = Coordinate(lat=dest.lat, lng=dest.lng)
    if rules.get("people") and "so_nguoi" not in updates:
        updates["so_nguoi"] = rules["people"]
    duration, _unit, _value, _mode, _minutes = _duration_shape(
        rules.get("days"),
        rules.get("minutes"),
        rules.get("window"),
    )
    if duration:
        updates["thoi_luong"] = duration
    purpose = _wants_theme_change(message, _folded(message))
    if purpose == "food":
        updates["context"] = f"{updates['context']}; ưu tiên ăn uống, nhà hàng, món địa phương"[-500:]
    policy = _merge_intent_policy(current, purpose, rules)
    if policy is not None:
        updates["intent_policy"] = policy
    return PlanRequest.model_validate({**current.model_dump(), **updates})


def conversation_messages(plan: dict | None, extra_user: str | None = None) -> list[dict]:
    messages: list[dict] = []
    for turn in (plan or {}).get("hoi_thoai") or []:
        role = "user" if turn.get("vai_tro") == "user" else "assistant"
        content = str(turn.get("noi_dung") or "").strip()
        if content:
            messages.append({"role": role, "content": content})
    if extra_user and extra_user.strip():
        messages.append({"role": "user", "content": extra_user.strip()})
    return messages[-12:]


def fallback_plan_chat_reply(
    action: str,
    locale: str,
    *,
    dest_name: str | None = None,
    stops: list[str] | None = None,
    theme: str | None = None,
    dest_changed: bool = False,
    old_name: str | None = None,
    new_name: str | None = None,
) -> str:
    named = ", ".join((stops or [])[:2])
    dest = dest_name or ("chuyến này" if locale == "vi" else "this trip")
    if locale != "vi":
        if action == "swap":
            if old_name and new_name:
                return f"Swapped {old_name} for {new_name}. Take a look, or tell me another stop to change."
            return "I swapped that stop. Check the new itinerary?"
        if action == "rebuild" and dest_changed:
            return f"I rebuilt the {dest} itinerary" + (f", including {named}." if named else ".")
        if action == "rebuild" and theme == "food":
            return "I leaned the day toward food" + (f" — {named}." if named else ".")
        if action == "rebuild":
            return "I updated the itinerary to match that. Tell me if you want another change."
        return f"Current stops include {named}. What should we change?" if named else "What would you like to change in this itinerary?"
    if action == "swap":
        if old_name and new_name:
            return f"Mình đổi {old_name} sang {new_name} rồi. Bạn xem ổn không, hay muốn đổi điểm khác?"
        return "Mình đổi điểm đó rồi. Bạn xem lịch mới ổn không?"
    if action == "rebuild" and dest_changed:
        return f"Mình xếp lại lịch {dest} theo ý bạn" + (f", có {named}." if named else ".")
    if action == "rebuild" and theme == "food":
        return "Mình nghiêng lịch sang ăn uống hơn" + (f" — ghé {named}." if named else ".")
    if action == "rebuild":
        return "Mình chỉnh lịch theo ý bạn rồi. Cứ nói nếu muốn đổi điểm hay thêm gì nhé."
    if named:
        return f"Lịch hiện tại đang có {named}. Bạn muốn mình giải thích điểm nào, hay muốn đổi gì?"
    return "Bạn muốn mình chỉnh điểm nào, hay hỏi gì về lịch này?"


def compose_plan_chat_reply(
    *,
    locale: str,
    action: str,
    message: str,
    plan: dict | None,
    dest_name: str | None = None,
    theme: str | None = None,
    dest_changed: bool = False,
    old_name: str | None = None,
    new_name: str | None = None,
) -> str:
    stops = plan_stops(plan, theme=theme)
    extra = {
        "dest_name": dest_name,
        "stops": stops,
        "theme": theme,
        "dest_changed": dest_changed,
        "old_name": old_name,
        "new_name": new_name,
    }
    intent = {
        "user_goal": "edit_plan",
        "edit_action": action,
        "last_user_message": message,
        "plan_title": (plan or {}).get("tieu_de"),
        "highlight_places": stops,
        "swap_from": old_name,
        "swap_to": new_name,
        "missing_fields": [],
        "status": "editing_plan",
        "parsed": {
            "destination": {"name": dest_name} if dest_name else None,
            "people": None,
            "primary_intent": theme,
            "duration": None,
        },
    }
    reply = ""
    composer = getattr(ai_adapter, "compose_chat_reply", None)
    if composer:
        try:
            reply = composer(
                messages=conversation_messages(plan, message),
                intent=intent,
                locale=locale,
            ) or ""
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("compose_plan_chat_reply failed: %s", exc)
            reply = ""
    cleaned = " ".join(str(reply).split())
    banned = ("vai_gio", "nua_ngay", "ca_ngay", "nhieu_ngay", "ràng buộc")
    if cleaned and any(token in cleaned for token in banned):
        cleaned = ""
    return cleaned[:800] or fallback_plan_chat_reply(action, locale, **extra)
