"""Score OSM tourist rows for fame: Wikipedia/heritage first, LLM on the grey zone.

OSM proves a place exists. Wikipedia/heritage/curated prove it is notable. The LLM
may only score remaining ids and must not invent names or coordinates.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from app.text_utils import ascii_fold

NOTABLE_EVIDENCE = {"curated", "wikipedia", "heritage"}
JUNK_NAME_RE = re.compile(
    r"(^cua |^bia |nghia trang|cemetery|liet si|^non bo$| farm$| garden$|"
    r"^green garden|^music garden|^landscape |cao diem )"
)
JUNK_TAGS = {"memorial", "boundary_stone"}


def name_key(name: str) -> str:
    return " ".join(ascii_fold(name).replace("\u2013", "-").replace("\u2014", "-").split())


def is_low_fame_place(name: str, tags: Iterable[str] | None = None) -> bool:
    key = name_key(name)
    tag_set = {str(tag) for tag in (tags or [])}
    if JUNK_NAME_RE.search(key):
        return True
    if tag_set & JUNK_TAGS and "attraction" not in tag_set:
        return True
    return False


def parse_llm_scores(payload: object, allowed_ids: set[str]) -> dict[str, dict]:
    """Keep only scores for ids we sent. Unknown ids are dropped."""
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("scores")
    if not isinstance(rows, list):
        return {}
    scored: dict[str, dict] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        place_id = item.get("id")
        if not isinstance(place_id, str) or place_id not in allowed_ids:
            continue
        try:
            rank = int(item.get("muc_uu_tien"))
        except (TypeError, ValueError):
            continue
        if rank not in {1, 2, 3}:
            continue
        reason = item.get("ly_do")
        scored[place_id] = {
            "muc_uu_tien": rank,
            "ly_do": reason.strip()[:180] if isinstance(reason, str) else "",
        }
    return scored


def notable_evidence(
    row: dict,
    *,
    curated_keys: set[str],
    wikipedia_ids: set[str],
    wikipedia_names: set[str],
    heritage_ids: set[str],
    heritage_names: set[str],
) -> str | None:
    key = name_key(str(row.get("name") or ""))
    place_id = str(row.get("id") or "")
    if key in curated_keys or str(row.get("source") or "") == "curated":
        return "curated"
    if place_id in wikipedia_ids or key in wikipedia_names or row.get("wikipedia_url"):
        return "wikipedia"
    if place_id in heritage_ids or key in heritage_names or row.get("wikidata_group") == "heritage":
        return "heritage"
    return None


def apply_hybrid_scores(
    rows: list[dict],
    *,
    curated_keys: set[str],
    wikipedia_ids: set[str] | None = None,
    wikipedia_names: set[str] | None = None,
    heritage_ids: set[str] | None = None,
    heritage_names: set[str] | None = None,
    llm_scores: dict[str, dict] | None = None,
) -> list[dict]:
    wikipedia_ids = wikipedia_ids or set()
    wikipedia_names = wikipedia_names or set()
    heritage_ids = heritage_ids or set()
    heritage_names = heritage_names or set()
    llm_scores = llm_scores or {}
    scored: list[dict] = []
    for row in rows:
        updated = dict(row)
        tags = updated.get("tags") or []
        evidence = notable_evidence(
            updated,
            curated_keys=curated_keys,
            wikipedia_ids=wikipedia_ids,
            wikipedia_names=wikipedia_names,
            heritage_ids=heritage_ids,
            heritage_names=heritage_names,
        )
        if evidence == "curated":
            updated["muc_uu_tien"] = 1
            updated["bang_chung"] = "curated"
        elif is_low_fame_place(str(updated.get("name") or ""), tags):
            updated["muc_uu_tien"] = 3
            updated["bang_chung"] = "low_fame_rule"
        elif evidence:
            updated["muc_uu_tien"] = 1
            updated["bang_chung"] = evidence
        elif updated["id"] in llm_scores:
            llm = llm_scores[updated["id"]]
            updated["muc_uu_tien"] = int(llm["muc_uu_tien"])
            updated["bang_chung"] = "llm"
            if llm.get("ly_do"):
                updated["ghi_chu"] = llm["ly_do"]
        else:
            updated["muc_uu_tien"] = 3
            updated["bang_chung"] = updated.get("bang_chung") or "osm_unscored"
        scored.append(updated)
    return scored


def grey_zone_rows(rows: list[dict]) -> list[dict]:
    """Places OSM mapped as tourism, but Wikipedia/heritage did not prove fame."""
    skip = NOTABLE_EVIDENCE | {"low_fame_rule", "llm"}
    return [row for row in rows if row.get("bang_chung") not in skip]


def llm_candidates(rows: list[dict]) -> list[dict]:
    """Grey-zone rows that look like visitor attractions, so the LLM is not fed every gate/POI."""
    eligible_kinds = {"bao_tang", "bai_bien", "hang_dong", "den_chua", "giai_tri"}
    eligible_tags = {
        "attraction",
        "museum",
        "theme_park",
        "beach",
        "cave_entrance",
        "heritage",
        "nature_reserve",
    }
    chosen: list[dict] = []
    for row in grey_zone_rows(rows):
        tags = {str(tag) for tag in (row.get("tags") or [])}
        if row.get("kind") in eligible_kinds or tags & eligible_tags:
            chosen.append(row)
    return chosen


def llm_prompt(tinh: str, places: list[dict]) -> dict:
    return {
        "yeu_cau": (
            "Cham diem noi tieng du lich cho cac dia diem THAT, da co id. "
            "Chi duoc dung id trong danh sach. Khong bia ten moi, khong doi toa do. "
            "1 = thang canh / diem du khach thuong tim o tinh nay. "
            "2 = dang ghe neu con thoi gian. "
            "3 = khong noi tieng (cong thanh phu, bia, vuon tu, POI nho). "
            "Neu khong chac, chon 3."
        ),
        "tinh": tinh,
        "places": [
            {
                "id": item["id"],
                "name": item["name"],
                "kind": item.get("kind"),
                "area": item.get("area") or item.get("tinh"),
            }
            for item in places
        ],
        "json_mau": {
            "scores": [
                {"id": "osm-node-1", "muc_uu_tien": 3, "ly_do": "ly do ngan"},
            ]
        },
    }


def dumps_prompt(prompt: dict) -> str:
    return json.dumps(prompt, ensure_ascii=False)
