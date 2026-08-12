"""Refresh images for the Hanoi catalogue using Wikimedia Commons.

For each place in data/places.json, resolves a photo via Commons title search
(file:"<name>") with strict containment: the folded file title must contain the
full folded place name (or exactly equal it for short names), so generic names
("Bồ câu", "Công", zoo animals) never match unrelated files. Places with no
exact-name file are left without an image (the UI shows a themed placeholder).

Enforces a single image per Commons file across the whole catalogue
(no duplicate image_url across distinct places, unless --allow-dup).
Persists image_url / image_credit / image_source back into the same file.
Idempotent: skips places that already have a non-empty image_url unless
--force is given. Backs up the catalogue before the first write.

Usage:
    python scripts/refresh_place_images.py [--limit 200] [--force]
        [--delay 0.35] [--places data/places.json]
"""

import argparse
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "minh-di-dau-the/0.2 (image refresh; contact project owner)"
THUMB_WIDTH = 800
MIN_GEO_WIDTH = 640
MAX_ATTEMPTS = 3

KIND_PRIORITY = ["dia_danh", "bao_tang", "cong_vien", "di_tich", "chua", "den", "cho", "cafe", "quan_an", "nha_hang"]
SIGHT_ONLY = {"dia_danh", "bao_tang", "cong_vien", "di_tich", "chua", "den"}

Candidate = tuple[str, str, int, str]  # thumb, credit, width, title

# Names without enough of a proper noun to ever resolve to the right photo
# (generic descriptive labels from OSM — not searchable on Commons).
SKIP_NAMES = frozenset({
    "quang truong", "khu vui choi", "abandoned van", "pineapple park",
    "cong viet nam", "0 km", "cong", "bo cau", "bao lua", "cu li nho",
    "ha ma", "ca sau", "ho", "khong ro", "dia diem",
})


def is_skip_name(place: dict) -> bool:
    name = ascii_fold(str(place.get("name", "")).strip())
    return name in SKIP_NAMES or len(name) < 3


def ascii_fold(value: str) -> str:
    import unicodedata

    return "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    ).lower()


def search_terms(place: dict) -> list[str]:
    name = ascii_fold(str(place.get("name", "")).strip())
    base = [name]
    head = name.split("\u2013")[0].strip() or name.split(" - ")[0].strip()
    if head and head != name:
        base.insert(0, head)
    deduped: list[str] = []
    for term in base:
        if term and term not in deduped:
            deduped.append(term)
    return deduped


def _request(params: dict) -> dict:
    params.setdefault("format", "json")
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504):
                last_exc = exc
                time.sleep(1.5 * attempt + random.uniform(0, 0.3))
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - retry any transient network error
            last_exc = exc
            time.sleep(min(2 ** attempt, 6))
    raise last_exc  # type: ignore[misc]


def _candidate_from_page(page) -> Candidate | None:
    if not isinstance(page, dict):
        return None
    info = (page.get("imageinfo") or [{}])[0]
    if not isinstance(info, dict):
        return None
    thumb = info.get("thumburl") or info.get("url")
    if not thumb:
        return None
    title = page.get("title") or ""
    if not title.lower().endswith(PHOTO_EXT):
        return None
    width = int(info.get("thumbwidth") or info.get("width") or 0)
    credit = f"Wikimedia Commons ({title})"
    return thumb, credit, width, title


def search_candidates(term: str, exclude: set[str], limit: int = 8) -> list[Candidate]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'file:"{term}"',
        "gsrnamespace": 6,
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
    }
    payload = _request(params)
    pages = (payload.get("query") or {}).get("pages") or {}
    out: list[Candidate] = []
    for page in pages.values():
        cand = _candidate_from_page(page)
        if cand and cand[0] not in exclude:
            out.append(cand)
    return out


def geosearch_candidates(place: dict, exclude: set[str], limit: int = 12) -> list[Candidate]:
    params = {
        "action": "query",
        "generator": "geosearch",
        "ggsnamespace": 6,
        "ggscoord": f"{place['lat']}|{place['lng']}",
        "ggsradius": "300",
        "ggslimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
    }
    payload = _request(params)
    pages = (payload.get("query") or {}).get("pages") or {}
    out: list[Candidate] = []
    for page in pages.values():
        cand = _candidate_from_page(page)
        if cand and cand[2] >= MIN_GEO_WIDTH and cand[0] not in exclude:
            out.append(cand)
    return out


def title_contains(term: str, title: str) -> bool:
    """Strict check that a Commons file title matches a place name.

    Long, specific names (>7 folded chars) must appear as a full substring
    of the folded title. Short names (zoo animals, "0 km", "Công") require an
    exact folded match, so "Công" can never match "Cong Abbey" or "Công Việt Nam".
    """
    f = ascii_fold(term).replace(" ", "")
    t = ascii_fold(title.replace("File:", "")).replace(" ", "")
    if not f or not t:
        return False
    if len(f) <= 7:
        return t == f
    return f in t


PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".gif")


def choose(candidates: list[Candidate]) -> Candidate | None:
    big = [c for c in candidates if c[2] >= 800]
    pool = big or candidates
    if not pool:
        return None
    pool.sort(key=lambda c: c[2], reverse=True)
    return pool[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--places", type=Path, default=Path("data/places.json"))
    parser.add_argument("--limit", type=int, default=0, help="max places to refresh (0 = all)")
    parser.add_argument("--force", action="store_true", help="refresh even when image_url exists")
    parser.add_argument("--allow-dup", action="store_true", help="permit one file for multiple places")
    parser.add_argument("--delay", type=float, default=0.35, help="seconds between queries")
    parser.add_argument("--save-every", type=int, default=100, help="persist file every N places")
    parser.add_argument("--sights-only", action="store_true", help="only sight kinds (dia_danh/bao_tang/...); cafes & restaurants rarely have Commons files")
    args = parser.parse_args()

    if not args.places.exists():
        sys.exit(f"missing {args.places}")
    payload = json.loads(args.places.read_text(encoding="utf-8"))
    places = payload.get("places", [])
    print(f"catalogue: {len(places)} places")

    def kind_rank(p: dict):
        k = p.get("kind", "")
        try:
            return KIND_PRIORITY.index(k)
        except ValueError:
            return len(KIND_PRIORITY)

    ordered = sorted(places, key=kind_rank)
    if args.sights_only:
        ordered = [p for p in ordered if p.get("kind") in SIGHT_ONLY]

    used_urls = {p.get("image_url") for p in places if p.get("image_url")}
    used_urls.discard(None)

    updated = 0
    skipped = 0
    failed = 0
    dup_suppressed = 0

    for index, place in enumerate(ordered):
        if args.limit and index >= args.limit:
            break
        if place.get("image_url") and not args.force:
            skipped += 1
            continue
        if is_skip_name(place):
            skipped += 1
            continue
        candidates: list[Candidate] = []
        source = "Wikimedia Commons search"
        terms = search_terms(place)

        for term in terms:
            try:
                raw = search_candidates(term, used_urls)
                time.sleep(args.delay)
            except Exception as exc:  # noqa: BLE001 - one failed terms passes to next
                failed += 1
                print(f"  ! {place.get('name')}: {type(exc).__name__}")
                break
            constrained = [c for c in raw if title_contains(term, c[3])]
            if constrained:
                candidates = constrained
                source = "Wikimedia Commons search"
                break

        picked = choose(candidates)
        if not picked:
            failed += 1
            continue

        thumb, credit, _, _ = picked
        if thumb in used_urls and not args.allow_dup:
            dup_suppressed += 1
            failed += 1
            continue
        used_urls.add(thumb)
        place["image_url"] = thumb
        place["image_credit"] = credit
        place["image_source"] = source
        updated += 1
        if args.limit == 0 or (index + 1) % 25 == 0:
            print(f"  ✓ {index + 1} {place.get('name')} -> {thumb[:70]}")
        if updated > 0 and updated % args.save_every == 0:
            args.places.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"  [saved {updated}]")

    payload["image_metadata"] = {
        "provider": "Wikimedia Commons",
        "endpoint": API_URL,
        "refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thumb_width": THUMB_WIDTH,
        "min_geo_width": MIN_GEO_WIDTH,
        "updated": updated,
        "skipped_existing": skipped,
        "failed": failed,
        "dup_suppressed": dup_suppressed,
        "license": "Variable (see image_credit per place)",
    }
    backup = args.places.with_suffix(".json.bak")
    if not backup.exists():
        backup.write_text(args.places.read_text(encoding="utf-8"), encoding="utf-8")
    args.places.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"done: updated={updated} skipped={skipped} failed={failed} dup_suppressed={dup_suppressed}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()