import json
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from time import monotonic

import httpx

from app.config import settings
from app.services.store import store

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_TAG_RE = re.compile(r"</?think>", re.IGNORECASE)
_REASONING_LEAK_RE = re.compile(
    r"here'?s a thinking process|grounded_intent|user_goal is|highlight_places|"
    r"never invent specific place|2-5 short sentences|reply in vietnamese",
    re.IGNORECASE,
)
_CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]+")
_EMPTY_SLOT_RE = re.compile(r"\s+,(\s+|$)")
_CJK_TERM_MAP = (
    ("行程", "lịch trình"),
    ("旅游", "du lịch"),
    ("景点", "điểm đến"),
    ("推荐", "gợi ý"),
    ("计划", "kế hoạch"),
    ("天数", "số ngày"),
    ("人数", "số người"),
)


def _assistant_message_text(message: dict | None) -> str:
    if not isinstance(message, dict):
        return ""
    chunks: list[str] = []
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        chunks.append(content.strip())
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str) and part.strip():
                chunks.append(part.strip())
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
    if not chunks:
        for key in ("reasoning", "reasoning_content"):
            extra = message.get(key)
            if isinstance(extra, str) and extra.strip():
                chunks.append(extra.strip())
                break
    return "\n".join(chunks).strip()


def _chat_models() -> list[str]:
    models: list[str] = []
    for name in (settings.ai_chat_model, settings.ai_model):
        label = str(name or "").strip()
        if label and label not in models:
            models.append(label)
    return models


def _chat_reply_payload(model: str, messages: list[dict]) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.95,
        "max_tokens": 420,
    }
    if "qwen" in model.lower():
        payload["reasoning_effort"] = "none"
        payload["reasoning_format"] = "hidden"
        payload["top_p"] = 0.9
        payload["presence_penalty"] = 0.4
    return payload


def _strip_chat_reasoning(content: str) -> str:
    text = _THINK_BLOCK_RE.sub(" ", content or "")
    text = _THINK_TAG_RE.sub(" ", text)
    text = " ".join(text.replace("```", "").split())
    if not _REASONING_LEAK_RE.search(text):
        return text
    kept = []
    for part in re.split(r"(?<=[.!?…])\s+", text):
        chunk = part.strip()
        if not chunk:
            continue
        if _REASONING_LEAK_RE.search(chunk):
            continue
        if "CATALOG" in chunk or "allowed_place_names" in chunk:
            continue
        kept.append(chunk)
    return " ".join(kept).strip()


def _strip_cjk(content: str, locale: str = "vi") -> str:
    if locale in {"zh", "ja", "ko"}:
        return content
    text = content or ""
    for source, target in _CJK_TERM_MAP:
        text = text.replace(source, f" {target} ")
    text = _CJK_RE.sub(" ", text)
    text = _EMPTY_SLOT_RE.sub(r"\1", text)
    return " ".join(text.split())


@dataclass
class CircuitBreaker:
    failures: deque[float] = field(default_factory=deque)
    opened_at: float | None = None
    validation_failures: int = 0

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if monotonic() - self.opened_at >= 120:
            self.opened_at = None
            return True
        return False

    def record_failure(self, kind: str = "unknown") -> None:
        if kind == "validation_error":
            self.validation_failures += 1
            return
        now = monotonic()
        self.failures.append(now)
        while self.failures and self.failures[0] < now - 300:
            self.failures.popleft()
        if len(self.failures) >= 3:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures.clear()
        self.opened_at = None
        self.validation_failures = 0


breaker = CircuitBreaker()


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "rate_limited"
        if status >= 500:
            return "server_error"
        return "http_error"
    if isinstance(exc, httpx.TransportError):
        return "network_error"
    return "validation_error"


def breaker_status() -> dict:
    allowed = breaker.allow()
    remaining_open_seconds = 0
    if breaker.opened_at is not None:
        remaining_open_seconds = max(0, round(120 - (monotonic() - breaker.opened_at)))
    return {
        "allowing_calls": allowed,
        "state": "closed" if allowed else "open",
        "recent_failures": len(breaker.failures),
        "validation_failures": breaker.validation_failures,
        "remaining_open_seconds": remaining_open_seconds,
    }


def _apply_copy(draft: dict, payload: dict, trusted_ids: set[str]) -> dict:
    descriptions = payload.get("mo_ta_theo_id", {})
    if not isinstance(descriptions, dict) or not set(descriptions) <= trusted_ids:
        raise ValueError("AI trả địa điểm ngoài danh sách tin cậy")
    result = json.loads(json.dumps(draft, ensure_ascii=False))
    if isinstance(payload.get("tieu_de"), str):
        result["tieu_de"] = payload["tieu_de"][:120]
    if isinstance(payload.get("tom_tat"), str):
        result["tom_tat"] = payload["tom_tat"][:500]
    for day in result["ngay"]:
        for slot in day["khoang_gio"]:
            copy = descriptions.get(slot["dia_diem_id"])
            if isinstance(copy, str) and copy.strip():
                slot["mo_ta"] = copy.strip()[:900]
    notes = payload.get("luu_y")
    if isinstance(notes, list) and all(isinstance(note, str) for note in notes):
        result["luu_y"] = [note[:300] for note in notes[:6]]
    return result


class OfflineAIAdapter:
    cost_per_call_usd = 0.0

    def extract_request_intent(self, context: str, locale: str = "vi") -> dict:
        return {}

    def extract_planning_intent(self, context: str, locale: str = "vi") -> dict:
        return {}

    def propose_place_ids(
        self,
        context: str,
        candidates: list[dict],
        count: int,
        locale: str = "vi",
    ) -> list[str]:
        return [str(item["id"]) for item in candidates[:count]]

    def draft_itinerary_places(
        self,
        context: str,
        count: int,
        locale: str = "vi",
    ) -> list[dict]:
        return []

    def assemble(self, draft: dict, trusted_ids: set[str], locale: str = "vi") -> dict:
        return json.loads(json.dumps(draft, ensure_ascii=False))

    def compose_chat_reply(self, messages: list[dict], intent: dict, locale: str = "vi") -> str:
        return ""

    def estimate_visit_durations(self, places: list[dict], locale: str = "vi") -> dict[str, int]:
        result: dict[str, int] = {}
        for item in places:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            try:
                minutes = int(item.get("catalog_minutes") or 60)
            except (TypeError, ValueError):
                minutes = 60
            result[item["id"]] = max(25, min(480, minutes))
        return result

class OpenAICompatibleAIAdapter:
    """Validated JSON adapter; AI may edit copy but never inventory or constraints."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        if not settings.ai_api_key:
            required_key = "API_KEY_GROQ" if settings.ai_mode == "groq" else "API_KEY_DEEPSEEK"
            raise RuntimeError(f"{required_key} is required when AI_MODE={settings.ai_mode}")
        base_url = settings.ai_base_url.rstrip("/") + "/"
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            timeout=httpx.Timeout(15, connect=3),
        )
        self.provider = settings.ai_mode

    def extract_request_intent(self, context: str, locale: str = "vi") -> dict:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        prompt = {
            "yeu_cau": (
                f"Extract only qualitative travel intent from this user text in {language}. "
                "Do not invent missing facts. Do not infer people, budget or trip duration unless the text says it. "
                "Return JSON only. Every extracted value must have short evidence copied or paraphrased from the user text."
            ),
            "text": context,
            "json_mau": {
                "destination_text": {"value": "string|null", "evidence": "string|null"},
                "preferences": [{"value": "string", "evidence": "string"}],
                "dislikes": [{"value": "string", "evidence": "string"}],
                "constraints": [{"value": "string", "evidence": "string"}],
                "must_visit": [{"value": "string", "evidence": "string"}],
            },
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "chat/completions",
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": "Only return a valid JSON object."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.0,
                        "max_tokens": 700,
                    },
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("AI intent extraction was incomplete")
                content = choice["message"].get("content")
                if not content:
                    raise ValueError("AI returned empty intent extraction")
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise TypeError("AI intent extraction is not an object")
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                amount = (
                    input_tokens * settings.ai_input_usd_per_million
                    + output_tokens * settings.ai_output_usd_per_million
                ) / 1_000_000
                store.record_ai_usage(
                    getattr(self, "provider", settings.ai_mode), settings.ai_model,
                    input_tokens, output_tokens, amount,
                    settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                )
                breaker.record_success()
                return payload
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                breaker.record_failure(_error_kind(exc))
        raise RuntimeError(f"AI không bóc tách được yêu cầu an toàn: {last_error}") from last_error

    def extract_planning_intent(self, context: str, locale: str = "vi") -> dict:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        prompt = {
            "yeu_cau": (
                f"Normalize this travel request in {language} into structured JSON. "
                "Extract the user's meaning, not literal regex tokens. Do not invent missing facts. "
                "If a value is ambiguous, put it in ambiguities and leave the normalized field null. "
                "Examples: '10h' alone may mean 10 hours or start at 10:00; mark ambiguous. "
                "'30p' or '0.5h' means 30 minutes. '20 ngày' means 20 days. "
                "Return JSON only."
            ),
            "text": context,
            "json_mau": {
                "schema_version": "intent-parse-v2",
                "destination_text": "string|null",
                "trip_purpose": "general_travel|healing|beach|mountain|food|cafe|null",
                "duration_value": "number|null",
                "duration_unit": "minute|hour|day|week|null",
                "time_window": {
                    "start_hour": "number|null",
                    "start_minute": "number|null",
                    "end_hour": "number|null",
                    "end_minute": "number|null",
                },
                "people": "number|null",
                "budget": "number|null",
                "preferences": ["string"],
                "dislikes": ["string"],
                "must_visit": ["string"],
                "ambiguities": [{"field": "string", "value": "string", "reason": "string", "question": "string"}],
            },
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "chat/completions",
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": "Only return a valid JSON object."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.0,
                        "max_tokens": 900,
                    },
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("AI intent normalization was incomplete")
                content = choice["message"].get("content")
                if not content:
                    raise ValueError("AI returned empty intent normalization")
                payload = json.loads(content)
                if not isinstance(payload, dict):
                    raise TypeError("AI intent normalization is not an object")
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                amount = (
                    input_tokens * settings.ai_input_usd_per_million
                    + output_tokens * settings.ai_output_usd_per_million
                ) / 1_000_000
                store.record_ai_usage(
                    getattr(self, "provider", settings.ai_mode), settings.ai_model,
                    input_tokens, output_tokens, amount,
                    settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                )
                breaker.record_success()
                return payload
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                breaker.record_failure(_error_kind(exc))
        raise RuntimeError(f"AI không chuẩn hóa được yêu cầu an toàn: {last_error}") from last_error

    def compose_chat_reply(self, messages: list[dict], intent: dict, locale: str = "vi") -> str:
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        parsed = intent.get("parsed") if isinstance(intent.get("parsed"), dict) else {}
        destination = parsed.get("destination") if isinstance(parsed.get("destination"), dict) else None
        missing = intent.get("missing_fields") or []
        last_user = str(intent.get("last_user_message") or "").strip()
        previous_assistant = ""
        for item in reversed(messages or []):
            if item.get("role") == "assistant":
                previous_assistant = str(item.get("content") or "")[:280]
                break
        catalog = {
            "destination": (destination or {}).get("name"),
            "duration": parsed.get("duration"),
            "people": parsed.get("people"),
            "purpose": parsed.get("primary_intent"),
            "missing_fields": missing,
            "next_field": missing[0] if missing else None,
            "user_goal": intent.get("user_goal") or "plan",
            "ask_topic": intent.get("ask_topic") or "general",
            "season_note": intent.get("season_note"),
            "theme_from": intent.get("theme_from"),
            "previous_assistant": previous_assistant,
            "allowed_place_names": [
                name
                for name in (
                    *(intent.get("highlight_places") or []),
                    *(intent.get("highlight_foods") or []),
                    *(
                        item.get("label")
                        for item in (intent.get("suggestions") or [])
                        if isinstance(item, dict)
                    ),
                )
                if isinstance(name, str) and name.strip()
            ][:8],
            "status": intent.get("status"),
        }
        history = [
            {"role": item.get("role"), "content": str(item.get("content") or "")[:500]}
            for item in messages[-12:]
            if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
        ]
        if intent.get("user_goal") == "edit_plan":
            catalog.update({
                "plan_title": intent.get("plan_title"),
                "edit_action": intent.get("edit_action") or "talk",
                "swap_from": intent.get("swap_from"),
                "swap_to": intent.get("swap_to"),
                "missing_fields": [],
                "next_field": None,
                "status": "editing_plan",
            })
        facts = json.dumps(catalog, ensure_ascii=False)
        if intent.get("user_goal") == "edit_plan":
            system = (
                f"You are a Vietnam travel friend chatting in {language}. "
                "When Vietnamese: refer to yourself as tôi or mình, and call the user bạn. "
                "Never address them as chị, anh, em, cô, chú, or bác. "
                "An itinerary already exists. Help the user edit or understand it. "
                "Answer the latest user message first, like a friend, in 2 short sentences. "
                "Do not ask destination, days, or people — those are already known. "
                "Never mention vai_gio, ngan_sach, ràng buộc, or dump budget VND amounts. "
                "CATALOG.allowed_place_names are the only stop names you may mention. "
                "If CATALOG.edit_action is swap: say you changed the stop and name CATALOG.swap_to. "
                "If CATALOG.edit_action is rebuild: say you updated the itinerary to match their request; "
                "name 1-2 stops from CATALOG.allowed_place_names. "
                "If CATALOG.edit_action is talk: answer the question about the current plan. "
                "Never invent new stop names. No markdown, no JSON, no thinking, no CATALOG echo. "
                f"When language is {language}, write only that language. "
                "Never mix Chinese, Japanese, or Korean characters. "
                "Write lịch trình, not 行程.\n"
                f"Latest user message: {last_user or '(see history)'}\n"
                f"CATALOG: {facts}"
            )
        else:
            system = (
                f"You are a Vietnam travel friend chatting in {language}. "
                "When Vietnamese: refer to yourself as tôi or mình, and call the user bạn. "
                "Never address them as chị, anh, em, cô, chú, or bác. "
                "Answer the latest user message first, like a friend. "
                "If they ask for comfort or share a feeling, comfort them. Do not ask how many days or people. "
                "If CATALOG.ask_topic is healing or they sound tired/stressed: answer freely like a friend. "
                "Do not follow a template, do not copy CATALOG.previous_assistant, and do not use stock lines "
                "such as 'Nghe bạn đang mệt', 'Chưa thúc bạn chọn', 'Đi chữa lành mình hay nghĩ', or 'nghiêng khí trời'. "
                "Write original wording. Mention 0-4 names from CATALOG.allowed_place_names only if it helps. "
                "Do not ask days or people. Do not write an itinerary. "
                "If CATALOG.ask_topic is beach or mountain and they have not picked a city: name up to 4 places "
                "with a short vibe each, then ask which they prefer. Do not say xếp lịch. "
                "Do not repeat the previous assistant message. "
                "If they reject a place, acknowledge the rejection and ask where else — never confirm the rejected place. "
                "Follow topic changes. If they switch from city sights to beach, food, season, or mountains, "
                "answer that new question — do not repeat your previous message. "
                "Do not run a slot form, and never ask days and people in the same message. "
                "If they just named a destination they want to visit: write 2 short sentences introducing the vibe "
                "(why it is special), then ask only next_field. Do not write a day-by-day itinerary. "
                "If CATALOG.user_goal is places: they asked what to see/do. Name 2-4 places from "
                "CATALOG.allowed_place_names. Do not ask days or people. "
                "If CATALOG.ask_topic is tips: answer weather, clothes, and road cautions. "
                "Do not list CATALOG.allowed_place_names. "
                "If CATALOG.missing_fields is not empty: do not write a day-by-day itinerary, "
                "morning/afternoon schedule, restaurants, distances, or transport plan. "
                "If they share a feeling (stress, tired, healing), empathize; place names from CATALOG are optional. "
                "Never invent people, days, destination, or an itinerary. "
                "CATALOG lists the only specific place names you may mention. "
                "Use a name only when it helps this answer; never dump the whole list. "
                "Never leave blank slots or dangling commas. "
                "High-level advice is OK: vibe, season, neighborhoods, how to get there. "
                f"When language is {language}, write only that language. "
                "Never mix Chinese, Japanese, or Korean characters. "
                "Write lịch trình, not 行程. "
                "Write original wording. No markdown, no JSON, no thinking, no CATALOG echo.\n"
                f"Latest user message: {last_user or '(see history)'}\n"
                f"CATALOG: {facts}"
            )
        payload_messages = [{"role": "system", "content": system}, *history]
        last_error: Exception | None = None
        for chat_model in _chat_models():
            payload = _chat_reply_payload(chat_model, payload_messages)
            for _attempt in range(2):
                try:
                    response = self.client.post("chat/completions", json=payload)
                    response.raise_for_status()
                    body = response.json()
                    choice = body["choices"][0]
                    message = choice.get("message") or {}
                    content = _assistant_message_text(message)
                    if not content:
                        raise ValueError("AI returned empty chat reply")
                    content = _strip_cjk(_strip_chat_reasoning(content), locale)
                    if not content:
                        raise ValueError("AI returned empty chat reply")
                    usage = body.get("usage", {})
                    input_tokens = int(usage.get("prompt_tokens", 0))
                    output_tokens = int(usage.get("completion_tokens", 0))
                    amount = (
                        input_tokens * settings.ai_input_usd_per_million
                        + output_tokens * settings.ai_output_usd_per_million
                    ) / 1_000_000
                    store.record_ai_usage(
                        getattr(self, "provider", settings.ai_mode), chat_model,
                        input_tokens, output_tokens, amount,
                        settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                    )
                    breaker.record_success()
                    return content[:800]
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    logger.warning(
                        "compose_chat_reply HTTP %s model=%s: %s",
                        exc.response.status_code,
                        chat_model,
                        (exc.response.text or "")[:300],
                    )
                    if exc.response.status_code == 400 and "reasoning_effort" in payload:
                        payload.pop("reasoning_effort", None)
                        payload.pop("reasoning_format", None)
                        continue
                    break
                except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
                    logger.warning("compose_chat_reply failed model=%s: %s", chat_model, exc)
                    if isinstance(exc, ValueError):
                        continue
                    break
        if last_error is not None:
            breaker.record_failure(_error_kind(last_error))
        raise RuntimeError(f"AI không soạn được câu trả lời: {last_error}") from last_error

    def propose_place_ids(
        self,
        context: str,
        candidates: list[dict],
        count: int,
        locale: str = "vi",
        destination: str | None = None,
    ) -> list[str]:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        trusted_ids = {str(item["id"]) for item in candidates}
        city = destination or "Vietnam"
        prompt = {
            "yeu_cau": (
                f"Select exactly {count} place ids for a useful, non-generic {city} itinerary. "
                f"Optimize for the user's request and explainable flow. Use {language} reasoning internally, "
                f"but return JSON only. Prefer iconic, well-known tourist attractions that first-time visitors "
                f"to {city} actually go to when those candidates exist. Avoid obscure shops, unnamed parks, "
                "street corners, and generic OSM POIs. Balance landmarks, food/cafe, and rest stops. "
                "Never invent ids; choose only from candidates. Prefer candidates marked famous/iconic "
                "or with a lower famous_priority number. If a candidate is a spelling twin of another "
                "(for example Titop / Ti Tốp), keep only one."
            ),
            "ngu_canh_nguoi_dung": context,
            "diem_den": city,
            "json_mau": {"place_ids": ["id1", "id2"]},
            "candidates": candidates[:60],
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "chat/completions",
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": "Only return a valid JSON object."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.45,
                        "max_tokens": 900,
                    },
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("AI response bị cắt hoặc không hoàn tất")
                content = choice["message"].get("content")
                if not content:
                    raise ValueError("AI trả nội dung rỗng")
                payload = json.loads(content)
                ids = payload.get("place_ids")
                if not isinstance(ids, list) or len(ids) != count:
                    raise ValueError("AI không chọn đúng số địa điểm")
                normalized = [str(item) for item in ids]
                if len(set(normalized)) != len(normalized) or not set(normalized) <= trusted_ids:
                    raise ValueError("AI chọn địa điểm ngoài danh sách tin cậy")
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                amount = (
                    input_tokens * settings.ai_input_usd_per_million
                    + output_tokens * settings.ai_output_usd_per_million
                ) / 1_000_000
                store.record_ai_usage(
                    getattr(self, "provider", settings.ai_mode), settings.ai_model,
                    input_tokens, output_tokens, amount,
                    settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                )
                breaker.record_success()
                return normalized
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                breaker.record_failure(_error_kind(exc))
        raise RuntimeError(f"AI không chọn được lịch trình an toàn: {last_error}") from last_error

    def draft_itinerary_places(
        self,
        context: str,
        count: int,
        locale: str = "vi",
        destination: str | None = None,
    ) -> list[dict]:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        city = destination or "Vietnam"
        prompt = {
            "yeu_cau": (
                f"Create a rich {city} itinerary concept in {language}. "
                f"Return exactly {count} real, famous tourist place names in {city}, Vietnam. "
                f"Prefer well-known landmarks, heritage sites, museums, beaches, and viewpoints that first-time visitors to {city} actually go to. "
                "Do not suggest obscure unnamed parks, street art, shops, or generic POIs. "
                "Do not invent fictional places, and do not use places from a different city. "
                "If the user mentions evening/night, include a real local evening area. "
                "Balance landmarks, food/cafe, rest stops, and realistic pacing. Think like a local trip designer, not a POI list. "
                "For every place, include why it belongs in the route, what the traveler should actually do there, "
                "one local tip, optional food/drink suggestion, and practical movement advice."
            ),
            "ngu_canh_nguoi_dung": context,
            "diem_den": city,
            "json_mau": {
                "places": [
                    {
                        "name": "real place name",
                        "kind": "dia_danh|bao_tang|cafe|nha_hang|quan_an|cong_vien",
                        "why": "short reason",
                        "activity": "what to do here in this itinerary",
                        "tip": "local practical tip",
                        "meal": "optional food or drink suggestion nearby",
                        "transport": "how this stop fits the route",
                    }
                ]
            },
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "chat/completions",
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": "Only return a valid JSON object."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.7,
                        "max_tokens": 1400,
                    },
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("AI response bị cắt hoặc không hoàn tất")
                content = choice["message"].get("content")
                if not content:
                    raise ValueError("AI trả nội dung rỗng")
                payload = json.loads(content)
                places = payload.get("places")
                if not isinstance(places, list):
                    raise TypeError("AI không trả danh sách places")
                result = [
                    item
                    for item in places
                    if isinstance(item, dict) and isinstance(item.get("name"), str)
                ][:count]
                if len(result) < count:
                    raise ValueError("AI trả quá ít địa điểm")
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                amount = (
                    input_tokens * settings.ai_input_usd_per_million
                    + output_tokens * settings.ai_output_usd_per_million
                ) / 1_000_000
                store.record_ai_usage(
                    getattr(self, "provider", settings.ai_mode), settings.ai_model,
                    input_tokens, output_tokens, amount,
                    settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                )
                breaker.record_success()
                return result
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                breaker.record_failure(_error_kind(exc))
        raise RuntimeError(f"AI không sinh được lịch trình an toàn: {last_error}") from last_error

    def estimate_visit_durations(self, places: list[dict], locale: str = "vi") -> dict[str, int]:
        if not breaker.allow() or not places:
            return {}
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        trusted = {
            str(item["id"])
            for item in places
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
        }
        prompt = {
            "yeu_cau": (
                f"Estimate realistic on-site visit minutes for each Vietnam attraction in {language} context. "
                "Cable cars 40-60. City cafes/photo bridges 30-60. Museums 60-120. "
                "Mountain pilgrimage, nature reserve, peak, trekking, or large temple-on-mountain: 180-360 "
                "(half day to a full day). Do not invent ids. Return JSON only."
            ),
            "places": places,
            "json_mau": {"durations": [{"id": "catalog-id", "minutes": 180}]},
        }
        try:
            response = self.client.post(
                "chat/completions",
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": "Only return a valid JSON object."},
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.0,
                    "max_tokens": 700,
                },
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"].get("content")
            if not content:
                return {}
            payload = json.loads(content)
            rows = payload.get("durations") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                return {}
            result: dict[str, int] = {}
            for item in rows:
                if not isinstance(item, dict):
                    continue
                place_id = item.get("id")
                if place_id not in trusted:
                    continue
                try:
                    minutes = int(item.get("minutes"))
                except (TypeError, ValueError):
                    continue
                if 25 <= minutes <= 480:
                    result[place_id] = minutes
            usage = body.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
            amount = (
                input_tokens * settings.ai_input_usd_per_million
                + output_tokens * settings.ai_output_usd_per_million
            ) / 1_000_000
            store.record_ai_usage(
                getattr(self, "provider", settings.ai_mode), settings.ai_model,
                input_tokens, output_tokens, amount,
                settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
            )
            return result
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def assemble(self, draft: dict, trusted_ids: set[str], locale: str = "vi") -> dict:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        language = {
            "vi": "Vietnamese", "en": "English", "ar": "Arabic", "bg": "Bulgarian",
            "de": "German", "es": "Spanish", "fr": "French", "he": "Hebrew",
            "hi": "Hindi", "it": "Italian", "ja": "Japanese", "nl": "Dutch",
            "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
            "zh": "Simplified Chinese", "ko": "Korean", "th": "Thai",
        }[locale]
        understood = draft.get("dau_vao_da_hieu") if isinstance(draft.get("dau_vao_da_hieu"), dict) else {}
        dest = understood.get("diem_den") if isinstance(understood.get("diem_den"), dict) else {}
        dest_value = dest.get("gia_tri") if isinstance(dest.get("gia_tri"), dict) else {}
        dest_name = dest_value.get("ten") if isinstance(dest_value, dict) else None
        people_field = understood.get("so_nguoi") if isinstance(understood.get("so_nguoi"), dict) else {}
        days_field = understood.get("so_ngay") if isinstance(understood.get("so_ngay"), dict) else {}
        seed_title = str(draft.get("tieu_de") or "")
        title_facts = {
            "destination": dest_name,
            "days": len(draft.get("ngay") or []) or days_field.get("gia_tri"),
            "people": people_field.get("gia_tri"),
            "seed_title": seed_title,
            "month_only": bool(
                re.search(r"\btháng\s+\d{1,2}\b", seed_title, re.I)
                or re.search(
                    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
                    seed_title,
                    re.I,
                )
            ),
        }
        prompt = {
            "yeu_cau": (
                f"Write all editable itinerary copy naturally in {language}. "
                "Use only the supplied ids. Preserve place names, proper nouns, source names, "
                "source URLs, coordinates, times, costs and all quantitative facts exactly. "
                "For tieu_de, write one catchy itinerary title in that language from title_facts. "
                "Vietnamese titles MUST start with 'Lịch trình du lịch'. "
                "Keep destination, days, people, and month/date from title_facts. "
                "If title_facts.month_only is true, write the month (tháng 11) — never a calendar day like 1/11. "
                "Weave in the traveler's original request from context_goc "
                "(coffee, food, walking, weekend, mood) plus the real destination. "
                "Do not write a label like 'Hà Nội · 2 giờ · 2 người'. "
                "Keep it to 8-22 words, no quotes, no trailing period. "
                "For each place description, write 3-5 vivid and practical sentences: set the scene, "
                "explain why it fits this trip, say exactly what to do there, mention nearby food/cafe "
                "or photo angles when useful, and include a local-feeling tip. Avoid generic phrases "
                "like 'experience this place'; make it feel like a real local itinerary."
            ),
            "json_mau": {
                "tieu_de": "string", "tom_tat": "string",
                "mo_ta_theo_id": {"id": "string"}, "luu_y": ["string"],
            },
            "id_tin_cay": sorted(trusted_ids),
            "context_goc": understood.get("context_goc") or draft.get("tieu_de") or "",
            "title_facts": title_facts,
            "ke_hoach": draft,
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "chat/completions",
                    json={
                        "model": settings.ai_model,
                        "messages": [
                            {"role": "system", "content": "Chỉ trả về một JSON object hợp lệ."},
                            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                        "max_tokens": 1800,
                    },
                )
                response.raise_for_status()
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("AI response bị cắt hoặc không hoàn tất")
                content = choice["message"].get("content")
                if not content:
                    raise ValueError("AI trả nội dung rỗng")
                result = _apply_copy(draft, json.loads(content), trusted_ids)
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
                amount = (
                    input_tokens * settings.ai_input_usd_per_million
                    + output_tokens * settings.ai_output_usd_per_million
                ) / 1_000_000
                store.record_ai_usage(
                    getattr(self, "provider", settings.ai_mode), settings.ai_model,
                    input_tokens, output_tokens, amount,
                    settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd,
                )
                breaker.record_success()
                return result
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                breaker.record_failure(_error_kind(exc))
        raise RuntimeError(f"AI không trả kết quả an toàn: {last_error}") from last_error


DeepSeekAIAdapter = OpenAICompatibleAIAdapter


def create_ai_adapter():
    if settings.ai_mode == "offline":
        if settings.app_env != "local":
            raise RuntimeError("AI_MODE=offline is forbidden outside local mode")
        return OfflineAIAdapter()
    if settings.ai_mode not in {"deepseek", "groq"}:
        raise RuntimeError(f"AI_MODE không được hỗ trợ: {settings.ai_mode}")
    try:
        return OpenAICompatibleAIAdapter()
    except RuntimeError:
        if settings.app_env != "local":
            raise
        logger.warning(
            "AI_MODE=%s thiếu API key (%s); dùng chế độ offline cục bộ. "
            "Đặt API_KEY_GROQ hoặc API_KEY_DEEPSEEK để bật AI thật.",
            settings.ai_mode,
            "API_KEY_GROQ" if settings.ai_mode == "groq" else "API_KEY_DEEPSEEK",
        )
        return OfflineAIAdapter()


ai_adapter = create_ai_adapter()
