import json
from collections import deque
from dataclasses import dataclass, field
from time import monotonic

import httpx

from app.config import settings
from app.services.store import store


@dataclass
class CircuitBreaker:
    failures: deque[float] = field(default_factory=deque)
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if monotonic() - self.opened_at >= 120:
            self.opened_at = None
            return True
        return False

    def record_failure(self) -> None:
        now = monotonic()
        self.failures.append(now)
        while self.failures and self.failures[0] < now - 300:
            self.failures.popleft()
        if len(self.failures) >= 3:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures.clear()
        self.opened_at = None


breaker = CircuitBreaker()


def breaker_status() -> dict:
    allowed = breaker.allow()
    remaining_open_seconds = 0
    if breaker.opened_at is not None:
        remaining_open_seconds = max(0, round(120 - (monotonic() - breaker.opened_at)))
    return {
        "allowing_calls": allowed,
        "state": "closed" if allowed else "open",
        "recent_failures": len(breaker.failures),
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


class MockAIAdapter:
    cost_per_call_usd = 0.0

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

    def estimate_place_metadata(self, name: str, kind: str, area: str) -> dict:
        return {"open_hour": 8, "close_hour": 22, "cost": 0}


class OpenAICompatibleAIAdapter:
    """Validated JSON adapter; AI may edit copy but never inventory or constraints."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        if not settings.ai_api_key:
            required_key = "API_KEY_GROQ" if settings.ai_mode == "groq" else "API_KEY_DEEPSEEK"
            raise RuntimeError(f"{required_key} is required when AI_MODE={settings.ai_mode}")
        self.client = client or httpx.Client(
            base_url=settings.ai_base_url,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            timeout=httpx.Timeout(10, connect=2),
        )
        self.provider = settings.ai_mode

    def estimate_place_metadata(self, name: str, kind: str, area: str) -> dict:
        if not breaker.allow():
            raise RuntimeError("Cầu dao AI đang mở")
        prompt = {
            "yeu_cau": "Estimate conservative public opening and closing whole hours and typical VND cost per person for this real Hanoi place. Return JSON only. Never return prose.",
            "dia_diem": {"name": name, "kind": kind, "area": area},
            "json_mau": {"open_hour": 8, "close_hour": 22, "cost": 50000},
        }
        try:
            response = self.client.post("/chat/completions", json={
                "model": settings.ai_model,
                "messages": [{"role": "system", "content": "Only return a valid JSON object."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                "response_format": {"type": "json_object"}, "temperature": 0.1, "max_tokens": 120,
            })
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("AI estimate was incomplete")
            payload = json.loads(choice["message"]["content"])
            opening, closing, cost = int(payload["open_hour"]), int(payload["close_hour"]), int(payload["cost"])
            if not (0 <= opening < closing <= 24 and 0 <= cost <= 10_000_000):
                raise ValueError("AI estimate outside safe bounds")
            usage = body.get("usage", {})
            input_tokens, output_tokens = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
            amount = (input_tokens * settings.ai_input_usd_per_million + output_tokens * settings.ai_output_usd_per_million) / 1_000_000
            store.record_ai_usage(self.provider, settings.ai_model, input_tokens, output_tokens, amount, settings.daily_ai_budget_usd, settings.monthly_ai_budget_usd)
            breaker.record_success()
            return {"open_hour": opening, "close_hour": closing, "cost": cost}
        except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            breaker.record_failure()
            raise RuntimeError("AI không thể ước tính dữ liệu địa điểm an toàn") from exc

    def propose_place_ids(
        self,
        context: str,
        candidates: list[dict],
        count: int,
        locale: str = "vi",
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
        prompt = {
            "yeu_cau": (
                f"Select exactly {count} place ids for a useful, non-generic Hanoi itinerary. "
                f"Optimize for the user's request and explainable flow. Use {language} reasoning internally, "
                "but return JSON only. Prefer iconic Hanoi anchors when relevant. Balance landmarks, food/cafe, "
                "and rest stops. Never invent ids; choose only from candidates."
            ),
            "ngu_canh_nguoi_dung": context,
            "json_mau": {"place_ids": ["id1", "id2"]},
            "candidates": candidates[:60],
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "/chat/completions",
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
                breaker.record_failure()
        raise RuntimeError(f"AI không chọn được lịch trình an toàn: {last_error}") from last_error

    def draft_itinerary_places(
        self,
        context: str,
        count: int,
        locale: str = "vi",
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
        prompt = {
            "yeu_cau": (
                f"Create a rich Hanoi itinerary concept in {language}. "
                f"Return exactly {count} real place names in Hanoi, Vietnam. "
                "Prefer useful, recognizable places over obscure POIs. For first-time Hanoi tourism, include "
                "iconic places such as Hồ Gươm, Lăng Chủ tịch Hồ Chí Minh, Hồ Tây, and Phố cổ Hà Nội when appropriate. "
                "If the user mentions evening/night, include a real evening segment such as the Old Quarter, night market, "
                "Tạ Hiện, or Hoàn Kiếm walking streets when appropriate. Balance landmarks, food/cafe, rest stops, "
                "and realistic pacing. Think like a local trip designer, not a POI list. Do not invent fictional places. "
                "For every place, include why it belongs in the route, what the traveler should actually do there, "
                "one local tip, optional food/drink suggestion, and practical movement advice."
            ),
            "ngu_canh_nguoi_dung": context,
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
                    "/chat/completions",
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
                breaker.record_failure()
        raise RuntimeError(f"AI không sinh được lịch trình an toàn: {last_error}") from last_error

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
        prompt = {
            "yeu_cau": (
                f"Write all editable itinerary copy naturally in {language}. "
                "Use only the supplied ids. Preserve place names, proper nouns, source names, "
                "source URLs, coordinates, times, costs and all quantitative facts exactly. "
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
            "ke_hoach": draft,
        }
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self.client.post(
                    "/chat/completions",
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
                breaker.record_failure()
        raise RuntimeError(f"AI không trả kết quả an toàn: {last_error}") from last_error


DeepSeekAIAdapter = OpenAICompatibleAIAdapter


def create_ai_adapter():
    if settings.ai_mode == "mock":
        if settings.app_env != "local":
            raise RuntimeError("AI_MODE=mock is forbidden outside local mode")
        return MockAIAdapter()
    if settings.ai_mode in {"deepseek", "groq"}:
        return OpenAICompatibleAIAdapter()
    raise RuntimeError(f"AI_MODE không được hỗ trợ: {settings.ai_mode}")


ai_adapter = create_ai_adapter()
