"""Fill missing itinerary photos from Wikipedia/Wikimedia, then leave Maps as fallback.

LLM is not used to invent image URLs. Lookups are cached and fail closed.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.data import DATA_DIR, cover_for_destination, destination_cover_from_title
from app.text_utils import ascii_fold

CACHE_PATH = DATA_DIR / "place_image_cache.json"
USER_AGENT = "minh-di-dau-the/0.3 (itinerary photos; local project)"
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=800"
MIN_NAME_CHARS = 4
MAX_LIVE_LOOKUPS = 8
GENERIC_NAMES = frozenset({
    "quan an", "nha hang", "cafe", "cong vien", "cho", "bai bien", "dia diem",
})
_PRODUCT_IMAGE_HINTS = (
    "zojirushi",
    "coffeemaker",
    "coffee maker",
    "consumer reports",
    "may pha ca phe",
    "may pha cà phê",
    "lossy-page",
)


def _fold(value: str) -> str:
    return " ".join(ascii_fold(value).split())


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"lookups": {}}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"lookups": {}}
    lookups = payload.get("lookups") if isinstance(payload, dict) else None
    return {"lookups": lookups if isinstance(lookups, dict) else {}}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _request_json(url: str, timeout: float = 4.0) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_product_photo(url: str = "", title: str = "") -> bool:
    blob = _fold(f"{url} {title}")
    return any(_fold(hint) in blob for hint in _PRODUCT_IMAGE_HINTS)


def _title_matches(name: str, title: str) -> bool:
    folded_name = _fold(name).replace(" ", "")
    folded_title = _fold(title).replace(" ", "")
    if len(folded_name) < MIN_NAME_CHARS or not folded_title:
        return False
    if _is_product_photo(title=title):
        return False
    if _fold(name) in GENERIC_NAMES:
        return False
    tokens = [token for token in _fold(name).split() if len(token) >= 3]
    if len(folded_name) <= 8:
        return folded_name in folded_title
    return folded_name in folded_title or (len(tokens) >= 2 and all(token in folded_title for token in tokens[:3]))


def _wikipedia_thumb(name: str, lang: str) -> tuple[str, str] | None:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": name,
            "gsrlimit": "5",
            "gsrnamespace": "0",
            "prop": "pageimages",
            "piprop": "thumbnail|name",
            "pithumbsize": "800",
            "redirects": "1",
        }
    )
    payload = _request_json(f"{WIKI_API.format(lang=lang)}?{params}")
    pages = (payload or {}).get("query", {}).get("pages") if payload else None
    if not isinstance(pages, dict):
        return None
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        title = str(page.get("title") or "")
        thumb = page.get("thumbnail") if isinstance(page.get("thumbnail"), dict) else {}
        url = thumb.get("source") if isinstance(thumb, dict) else None
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        if _is_product_photo(url, title):
            continue
        if not _title_matches(name, title):
            continue
        credit = f"Wikipedia ({lang}: {title})"
        return url, credit
    return None


def lookup_place_image(name: str, extra: str | None = None) -> tuple[str, str] | None:
    clean = re.sub(r"\s+", " ", (name or "").strip())
    if len(_fold(clean)) < MIN_NAME_CHARS or _fold(clean) in GENERIC_NAMES:
        return None
    queries = [clean]
    if extra:
        tagged = f"{clean} {extra}".strip()
        if tagged not in queries:
            queries.append(tagged)
    if "việt nam" not in _fold(clean) and "vietnam" not in _fold(clean):
        queries.append(f"{clean} Việt Nam")
    for query in queries:
        for lang in ("vi", "en"):
            found = _wikipedia_thumb(query, lang)
            if found:
                return found
    return None


def _slot_has_image(slot: dict[str, Any]) -> bool:
    url = slot.get("anh")
    return isinstance(url, str) and url.startswith("http")


_HERO_SKIP_KINDS = frozenset({
    "cafe", "ca_phe", "nha_hang", "quan_an", "cho", "drinks", "khach_san", "nha_nghi", "homestay",
})
_HERO_PREFER_KINDS = frozenset({
    "dia_danh", "bai_bien", "nui", "cong_vien", "di_tich", "den_chua", "hang_dong",
})


def _plan_destination(plan: dict[str, Any]) -> str | None:
    understood = plan.get("dau_vao_da_hieu") if isinstance(plan.get("dau_vao_da_hieu"), dict) else {}
    dest_field = understood.get("diem_den") if isinstance(understood, dict) else None
    if isinstance(dest_field, dict):
        value = dest_field.get("gia_tri")
        if isinstance(value, dict) and isinstance(value.get("ten"), str):
            return value.get("ten")
        if isinstance(value, str) and value.strip():
            return value
    candidates = plan.get("du_lieu_ung_vien") if isinstance(plan.get("du_lieu_ung_vien"), dict) else {}
    dest_field = candidates.get("diem_den") if isinstance(candidates, dict) else None
    if isinstance(dest_field, dict):
        value = dest_field.get("gia_tri")
        if isinstance(value, dict) and isinstance(value.get("ten"), str):
            return value.get("ten")
        if isinstance(value, str) and value.strip():
            return value
    return None


def _slot_is_hero_candidate(slot: dict[str, Any]) -> bool:
    if not _slot_has_image(slot):
        return False
    kind = str(slot.get("loai") or "").strip().casefold()
    if kind in _HERO_SKIP_KINDS:
        return False
    folded = _fold(str(slot.get("ten_dia_diem") or ""))
    if any(token in folded for token in ("cafe", "coffee", "ca phe", "quan cafe")):
        return False
    url = str(slot.get("anh") or "")
    credit = str(slot.get("anh_nguon") or "")
    if _is_product_photo(url, credit):
        return False
    return True


def ensure_plan_cover(plan: dict[str, Any]) -> dict[str, Any]:
    """Prefer a destination landmark photo over the first cafe/restaurant slot."""
    destination = _plan_destination(plan)
    cover_url, cover_credit = cover_for_destination(destination)
    if not (isinstance(cover_url, str) and cover_url.startswith("http")):
        cover_url, cover_credit = destination_cover_from_title(plan.get("tieu_de"))
    if isinstance(cover_url, str) and cover_url.startswith("http"):
        plan["anh_bia"] = cover_url
        plan["anh_bia_nguon"] = cover_credit
        return plan
    scenic = None
    other = None
    for day in plan.get("ngay") or []:
        if not isinstance(day, dict):
            continue
        for slot in day.get("khoang_gio") or []:
            if not isinstance(slot, dict) or not _slot_is_hero_candidate(slot):
                continue
            kind = str(slot.get("loai") or "").strip().casefold()
            if kind in _HERO_PREFER_KINDS and scenic is None:
                scenic = slot
            elif other is None:
                other = slot
    chosen = scenic or other
    if chosen:
        plan["anh_bia"] = chosen.get("anh")
        plan["anh_bia_nguon"] = chosen.get("anh_nguon")
    return plan


def enrich_plan_images(plan: dict[str, Any]) -> dict[str, Any]:
    """Attach Wikipedia/Wikimedia photos to slots that still have no image."""
    cache = _load_cache()
    lookups = cache.setdefault("lookups", {})
    filled = 0
    attempted = 0
    cache_hits = 0
    live_lookups = 0
    cache_changed = False
    destination = _plan_destination(plan)
    cover_url, cover_credit = cover_for_destination(destination if isinstance(destination, str) else None)
    if not (isinstance(cover_url, str) and cover_url.startswith("http")):
        cover_url, cover_credit = destination_cover_from_title(plan.get("tieu_de"))
    if isinstance(cover_url, str) and cover_url.startswith("http"):
        plan["anh_bia"] = cover_url
        plan["anh_bia_nguon"] = cover_credit

    for day in plan.get("ngay") or []:
        if not isinstance(day, dict):
            continue
        for slot in day.get("khoang_gio") or []:
            if not isinstance(slot, dict) or _slot_has_image(slot):
                continue
            name = str(slot.get("ten_dia_diem") or "").strip()
            if not name:
                continue
            cache_key = _fold(f"{name}|{destination or ''}")
            cached = lookups.get(cache_key)
            attempted += 1
            if isinstance(cached, dict):
                cache_hits += 1
                url = cached.get("url")
                if isinstance(url, str) and url.startswith("http") and not _is_product_photo(url, str(cached.get("credit") or "")):
                    slot["anh"] = url
                    slot["anh_nguon"] = cached.get("credit") or "Wikipedia"
                    filled += 1
                continue
            if live_lookups >= MAX_LIVE_LOOKUPS:
                continue
            live_lookups += 1
            found = lookup_place_image(name, destination if isinstance(destination, str) else None)
            cache_changed = True
            if found:
                url, credit = found
                lookups[cache_key] = {"url": url, "credit": credit}
                slot["anh"] = url
                slot["anh_nguon"] = credit
                filled += 1
            else:
                lookups[cache_key] = {"url": None, "credit": None}

    ensure_plan_cover(plan)
    if not _slot_has_image({"anh": plan.get("anh_bia")}) and isinstance(destination, str) and destination.strip():
        dest_key = _fold(f"cover|{destination}")
        cached = lookups.get(dest_key)
        if isinstance(cached, dict) and isinstance(cached.get("url"), str) and not _is_product_photo(
            str(cached.get("url") or ""), str(cached.get("credit") or "")
        ):
            plan["anh_bia"] = cached["url"]
            plan["anh_bia_nguon"] = cached.get("credit") or "Wikipedia"
        elif live_lookups < MAX_LIVE_LOOKUPS:
            live_lookups += 1
            found = lookup_place_image(destination)
            cache_changed = True
            if found:
                url, credit = found
                lookups[dest_key] = {"url": url, "credit": credit}
                plan["anh_bia"] = url
                plan["anh_bia_nguon"] = credit
            else:
                lookups[dest_key] = {"url": None, "credit": None}

    if cache_changed:
        _save_cache(cache)
    plan["anh_bo_sung"] = {
        "nguon": "wikipedia_wikimedia",
        "so_o_da_dien": filled,
        "so_o_thieu_anh": attempted,
        "cache_hits": cache_hits,
        "live_lookups": live_lookups,
    }
    return plan
