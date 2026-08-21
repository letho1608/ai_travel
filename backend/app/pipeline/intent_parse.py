import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Literal

from app.data import PLACES, Place
from app.services.ai import ai_adapter
from app.text_utils import ascii_fold
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MAX_TRIP_DAYS = 30
MAX_ASKED_DAYS = 365
DESTINATION_RADIUS_KM = 55.0


@dataclass(frozen=True)
class IntentDestination:
    name: str
    lat: float
    lng: float
    radius_km: float | None = None


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
    duration_value: float | None = Field(default=None, gt=0, le=365)
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
    "Hà Nội": ("ha noi", "hanoi", "thu do", "하노이", "河内", "ハノイ"),
    "TP.HCM": ("tp hcm", "ho chi minh", "sai gon", "saigon", "thanh pho ho chi minh", "hcmc", "호치민", "사이공", "胡志明", "ホーチミン"),
    "Đà Nẵng": ("da nang", "danang", "da nang city", "다낭", "岘港", "ダナン"),
    "Hội An": ("hoi an", "pho co hoi an", "hoi an ancient town", "호이안", "会安", "ホイアン"),
    "Huế": ("hue", "thua thien hue", "co do hue", "hue city", "후에", "훼", "顺化", "フエ"),
    "Đà Lạt": ("da lat", "dalat", "lam dong", "da lat city", "달랏", "大叻", "ダラット"),
    "Nha Trang": ("nha trang", "khanh hoa", "nha trang beach", "나트랑", "芽庄", "ニャチャン"),
    "Ninh Bình": ("ninh binh", "trang an", "bai dinh", "tam coc", "ninh binh province", "닌빈", "宁平"),
    "Hạ Long": ("ha long", "halong", "vinh ha long", "ha long bay", "halong bay", "하롱베이", "하롱", "下龙湾"),
    "Sa Pa": ("sa pa", "sapa", "lao cai", "fansipan", "sapa town", "사파", "沙坝"),
    "Phú Quốc": ("phu quoc", "dao phu quoc", "kien giang", "phu quoc island", "푸꾸옥", "富国岛"),
    "Cần Thơ": ("can tho", "tay do", "ninh kieu", "can tho city", "껀터", "芹苴"),
    "Vũng Tàu": ("vung tau", "ba ria vung tau", "vung tau city", "붕따우", "头顿"),
    "Quy Nhơn": ("quy nhon", "binh dinh", "eo gio", "ky co", "quy nhon city", "꾸이년", "归仁"),
    "Phan Thiết": ("phan thiet", "mui ne", "binh thuan", "mui ne beach", "판티엣", "무이네", "潘切"),
    "Quảng Bình": ("quang binh", "dong hoi", "phong nha", "phong nha ke bang", "꽝빈", "广平"),
    "Hà Giang": ("ha giang", "dong van", "ma pi leng", "ha giang loop", "하기앙", "河江"),
    "Hải Phòng": ("hai phong", "do son", "하이퐁", "海防"),
}

# Named sights that are trip destinations even when they are not focus cities.
LANDMARK_DESTINATIONS: tuple[IntentDestination, ...] = (
    IntentDestination("Cát Bà", 20.7278, 107.0482, 13.0),
    IntentDestination("Yên Tử", 21.1506, 106.7189),
    IntentDestination("Chùa Hương", 20.6194, 105.7456),
)
LANDMARK_ALIASES: dict[str, tuple[str, ...]] = {
    "Cát Bà": ("cat ba", "dao cat ba", "cat ba island", "vinh lan ha", "lan ha"),
    "Yên Tử": ("yen tu", "chua yen tu", "nui yen tu", "thien vien yen tu", "chua dong yen tu", "danh thang yen tu"),
    "Chùa Hương": ("chua huong", "huong tich", "chua huong tich", "huong son"),
}


def _destination_payload(destination: IntentDestination) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": destination.name,
        "lat": destination.lat,
        "lng": destination.lng,
    }
    if destination.radius_km:
        payload["radius_km"] = destination.radius_km
    return payload


POI_NAME_PREFIXES = (
    "quan the di tich danh thang ",
    "quan the danh thang ",
    "di tich danh thang ",
    "khu du lich ",
    "thien vien ",
    "chua dong ",
    "pho co ",
    "chua ",
    "nui ",
    "den ",
    "dong ",
    "thac ",
    "bai ",
    "vinh ",
    "dao ",
    "bien ",
    "tp ",
    "thanh pho ",
)
POI_STOPWORDS = frozenset({
    "quan", "the", "di", "tich", "danh", "thang", "khu", "du", "lich",
    "chua", "nui", "den", "thien", "vien", "dong", "thanh", "pho", "tp",
    "vinh", "dao", "bien", "bai", "cho", "ho", "song", "cau", "lang",
    "complex", "pagoda", "temple", "mountain", "park",
})
GENERIC_POI_ALIASES = {
    "du lich", "tham quan", "di choi", "check in", "checkin",
    "chua", "nui", "den", "dong", "thac", "bai", "bien", "dao", "pho",
}
WEAK_USER_TOKENS = frozenset({
    "toi", "tui", "minh", "ban", "muon", "len", "plan", "ke", "hoach",
    "di", "cho", "do", "met", "khong", "biet", "dau", "nay", "tuan",
    "cuoi", "nhe", "lam", "duoc", "thich", "voi", "va", "mot", "cai",
    "kia", "the", "nao", "bao", "lau", "ngay", "gio", "nguoi",
})
SIGHT_POI_KINDS = frozenset({
    "dia_danh", "bao_tang", "cong_vien", "cho", "di_tich", "bai_bien",
    "hang_dong", "nui", "den_chua", "giai_tri",
})

THEMES: dict[str, ThemeSpec] = {
    "general_travel": ThemeSpec(
        terms=("du lich", "di choi", "tham quan", "travel", "trip"),
        allowed_place_themes=("landmark", "culture", "food", "nature", "viewpoint"),
        avoid_place_themes=(),
        tags=("view_dep", "checkin", "heritage", "local", "van_hoa"),
        kinds=("dia_danh", "bao_tang", "di_tich", "cong_vien", "cho", "bai_bien", "nui"),
    ),
    "healing": ThemeSpec(
        terms=(
            "chua lanh", "healing", "nghi duong", "di tron", "chill", "thu gian", "yen tinh", "di nhe",
            "met moi", "can nghi", "giam stress", "xa stress", "ap luc", "burnout", "detox",
            "nghi ngoi", "nhe dau", "yen binh", "reset", "do met", "cho do met",
            "stress", "cang thang", "stressed", "moi met", "met qua", "nang dau",
        ),
        allowed_place_themes=("quiet", "nature", "lake", "forest", "cafe_chill", "viewpoint", "slow_walk"),
        avoid_place_themes=("crowded_landmark", "heavy_history", "dense_schedule", "strenuous_activity"),
        tags=("chill", "yen_tinh", "thu_gian", "view_dep", "ngoai_troi", "ho", "song", "beach", "bien"),
        kinds=("cong_vien", "dia_danh", "bai_bien", "nui", "cafe"),
    ),
    "beach": ThemeSpec(
        terms=("bien", "bai bien", "dao", "hai san", "hoang hon bien", "ngam hoang hon", "san ho", "beach", "island", "tam bien", "di bien", "nghi bien", "ven bien"),
        allowed_place_themes=("beach", "island", "seafood", "sunset", "coastal_view", "resort"),
        avoid_place_themes=("urban_museum", "inland_landmark"),
        tags=("beach", "bien", "dao", "island", "ngoai_troi", "view_dep", "hai_san"),
        kinds=("bai_bien", "dia_danh", "nha_hang", "quan_an"),
    ),
    "mountain": ThemeSpec(
        terms=("leo nui", "trekking", "trail", "san may", "dinh nui", "dinh", "deo", "fansipan", "langbiang", "di nui", "phuot nui", "phuot"),
        allowed_place_themes=("mountain", "trekking", "trail", "peak", "pass", "viewpoint", "nature"),
        avoid_place_themes=("museum", "urban_landmark", "shopping"),
        tags=("nui", "peak", "trekking", "trail", "viewpoint", "ngoai_troi", "view_dep"),
        kinds=("nui", "hang_dong", "dia_danh"),
    ),
    "food": ThemeSpec(
        terms=("an ngon", "an uong", "am thuc", "food", "hai san", "nha hang", "quan an", "an vat", "food tour", "foodtour", "no bung", "an gi"),
        allowed_place_themes=("food", "local_food", "market", "seafood"),
        avoid_place_themes=(),
        tags=("am_thuc", "local", "hai_san", "an_vat", "dac_san"),
        kinds=("nha_hang", "quan_an", "cho"),
    ),
    "cafe": ThemeSpec(
        terms=("cafe", "coffee", "ca phe", "caphe", "uong cafe", "checkin cafe", "check in cafe"),
        allowed_place_themes=("cafe", "cafe_chill", "viewpoint", "slow_walk"),
        avoid_place_themes=("dense_schedule",),
        tags=("cafe", "coffee", "chill", "view_dep"),
        kinds=("cafe", "dia_danh", "cong_vien"),
    ),
}


def _fold(value: str) -> str:
    val = value.translate(str.maketrans({"đ": "d", "Đ": "D"}))
    decomposed = unicodedata.normalize("NFD", val)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def _contains_term(folded: str, term: str) -> bool:
    term_folded = _fold(term)
    if not term_folded:
        return False
    if any(ord(c) > 127 for c in term_folded):
        return term_folded in folded
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term_folded)}(?![a-z0-9])", folded))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _place_search_aliases(name: str) -> set[str]:
    folded = _fold(name)
    aliases: set[str] = set()
    if folded and folded not in GENERIC_POI_ALIASES:
        aliases.add(folded)
    stripped = folded
    for prefix in POI_NAME_PREFIXES:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
            if stripped:
                aliases.add(stripped)
    tokens = folded.split()
    content = [token for token in tokens if token not in POI_STOPWORDS]
    if len(content) >= 2:
        aliases.add(" ".join(content[-2:]))
        aliases.add(" ".join(content))
    elif len(content) == 1 and len(content[0]) >= 6:
        aliases.add(content[0])
    return {alias for alias in aliases if alias and not _alias_too_weak(alias)}


def _alias_too_weak(alias: str) -> bool:
    if alias in GENERIC_POI_ALIASES or alias in POI_STOPWORDS:
        return True
    tokens = alias.split()
    if not tokens:
        return True
    if all(token in POI_STOPWORDS or token in GENERIC_POI_ALIASES or len(token) <= 2 for token in tokens):
        return True
    if len(tokens) <= 2 and tokens[0] in POI_STOPWORDS and max(len(token) for token in tokens[1:]) <= 3:
        return True
    return len(alias) < 4 and " " not in alias


def _gram_too_weak(gram: str) -> bool:
    tokens = gram.split()
    if not tokens:
        return True
    return all(token in WEAK_USER_TOKENS or token in POI_STOPWORDS or len(token) <= 2 for token in tokens)


@lru_cache(maxsize=1)
def _city_alias_keys() -> frozenset[str]:
    keys = {_fold(item.name) for item in FOCUS_DESTINATIONS}
    for aliases in DESTINATION_ALIASES.values():
        keys.update(_fold(alias) for alias in aliases)
    return frozenset(keys)


@lru_cache(maxsize=1)
def _catalog_alias_map() -> dict[str, IntentDestination]:
    ranked: dict[str, tuple[int, IntentDestination]] = {}
    city_keys = _city_alias_keys()
    for place in PLACES:
        if place.kind in {"cafe", "khach_san", "nha_nghi", "homestay"}:
            continue
        score = 0
        if place.kind in SIGHT_POI_KINDS:
            score += 6
        if place.kind in {"nha_hang", "quan_an"}:
            score -= 7
        if place.source == "curated":
            score += 2
        if score < 0:
            continue
        destination = IntentDestination(place.name, place.lat, place.lng)
        for alias in _place_search_aliases(place.name):
            if alias in city_keys:
                continue
            current = ranked.get(alias)
            if current is None or score > current[0]:
                ranked[alias] = (score, destination)
    return {alias: destination for alias, (_score, destination) in ranked.items()}


def _find_landmark(folded: str) -> IntentDestination | None:
    mentions = _landmark_mention_spans(folded)
    if not mentions:
        return None
    last_positive: IntentDestination | None = None
    for start, _end, item in mentions:
        if _mention_is_negated(folded, start):
            if last_positive and last_positive.name == item.name:
                last_positive = None
            continue
        last_positive = item
    return last_positive


def _find_catalog_destination(folded: str) -> IntentDestination | None:
    mapping = _catalog_alias_map()
    tokens = folded.split()
    best: tuple[int, IntentDestination] | None = None
    for length in range(min(4, len(tokens)), 0, -1):
        for index in range(len(tokens) - length + 1):
            gram = " ".join(tokens[index:index + length])
            if _gram_too_weak(gram):
                continue
            destination = mapping.get(gram)
            if destination is None:
                continue
            candidate = (len(gram), destination)
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best:
            return best[1]
    return None


def _term_spans(folded: str, term: str) -> list[tuple[int, int]]:
    term_folded = _fold(term)
    if not term_folded:
        return []
    if any(ord(ch) > 127 for ch in term_folded):
        spans: list[tuple[int, int]] = []
        start = 0
        while True:
            idx = folded.find(term_folded, start)
            if idx < 0:
                return spans
            spans.append((idx, idx + len(term_folded)))
            start = idx + 1
    return [
        (match.start(), match.end())
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(term_folded)}(?![a-z0-9])", folded)
    ]


def _mention_is_negated(folded: str, start: int) -> bool:
    prefix = folded[max(0, start - 32):start]
    return bool(re.search(
        r"(?:khong|ko|chang)\s+(?:muon\s+)?(?:di|den|ve|thich)?\s*$",
        prefix,
    ))


def _collapse_destination_spans(
    hits: list[tuple[int, int, IntentDestination]],
) -> list[tuple[int, int, IntentDestination]]:
    hits.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    collapsed: list[tuple[int, int, IntentDestination]] = []
    last_end = -1
    for start, end, item in hits:
        if start < last_end:
            continue
        collapsed.append((start, end, item))
        last_end = end
    return collapsed


def _city_mention_spans(folded: str) -> list[tuple[int, int, IntentDestination]]:
    hits: list[tuple[int, int, IntentDestination]] = []
    for item in FOCUS_DESTINATIONS:
        terms = (item.name, *DESTINATION_ALIASES.get(item.name, ()))
        for term in terms:
            for start, end in _term_spans(folded, term):
                hits.append((start, end, item))
    return _collapse_destination_spans(hits)


def _landmark_mention_spans(folded: str) -> list[tuple[int, int, IntentDestination]]:
    hits: list[tuple[int, int, IntentDestination]] = []
    by_name = {item.name: item for item in LANDMARK_DESTINATIONS}
    for name, aliases in LANDMARK_ALIASES.items():
        item = by_name[name]
        terms = (name, *aliases)
        for term in terms:
            for start, end in _term_spans(folded, term):
                hits.append((start, end, item))
    return _collapse_destination_spans(hits)


def _hits_in_order(spans: list[tuple[int, int, IntentDestination]]) -> list[IntentDestination]:
    ordered: list[IntentDestination] = []
    for _start, _end, item in spans:
        if ordered and ordered[-1].name == item.name:
            continue
        ordered.append(item)
    return ordered


def _city_hits_in_order(folded: str) -> list[IntentDestination]:
    return _hits_in_order(_city_mention_spans(folded))


def _destination_hits_in_order(folded: str) -> list[IntentDestination]:
    mentions = _collapse_destination_spans(
        _city_mention_spans(folded) + _landmark_mention_spans(folded)
    )
    return _hits_in_order(mentions)


def _find_destination(folded: str) -> IntentDestination | None:
    mentions = _city_mention_spans(folded) + _landmark_mention_spans(folded)
    mentions.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    if mentions:
        cut = None
        for start, _end in _term_spans(folded, "thoi"):
            cut = start
        last_positive: IntentDestination | None = None
        for start, _end, item in mentions:
            if cut is not None and start < cut:
                continue
            if _mention_is_negated(folded, start):
                if last_positive and last_positive.name == item.name:
                    last_positive = None
                continue
            last_positive = item
        if last_positive:
            return last_positive
    landmark = _find_landmark(folded)
    if landmark:
        return landmark
    by_name = {item.name: item for item in FOCUS_DESTINATIONS}
    if _contains_term(folded, "mien trung") and any(
        _contains_term(folded, term) for term in ("bien", "tam bien", "bai bien", "dao")
    ):
        return by_name["Nha Trang"]
    for terms, name in REGION_DESTINATIONS:
        if any(_contains_term(folded, term) for term in terms):
            return by_name[name]
    return _find_catalog_destination(folded)


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
    # Seafood is tag-based (hai_san), not "any restaurant". Otherwise quán chay
    # matches beach trips because every nha_hang/quan_an was treated as seafood.
    "seafood": set(),
    "mountain": {"nui", "hang_dong", "den_chua"},
    "trekking": {"nui", "hang_dong", "den_chua"},
    "trail": {"nui"},
    "peak": {"nui"},
    "pass": {"nui", "dia_danh"},
    "nature": {"cong_vien", "bai_bien", "nui", "hang_dong", "den_chua"},
    "lake": {"cong_vien", "dia_danh"},
    "forest": {"cong_vien", "nui"},
    "viewpoint": {"dia_danh", "nui", "bai_bien", "cong_vien"},
    "quiet": {"cong_vien", "bai_bien", "nui", "cafe", "den_chua"},
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
    "crowded_landmark": {"hanoi_icon", "lang_bac"},
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


THEME_DESTINATION_PRIORITY: dict[str, tuple[str, ...]] = {
    "healing": ("Đà Lạt", "Sa Pa", "Ninh Bình", "Phú Quốc", "Huế"),
    "beach": ("Nha Trang", "Phú Quốc", "Đà Nẵng", "Vũng Tàu", "Phan Thiết"),
    "mountain": ("Sa Pa", "Hà Giang", "Đà Lạt", "Ninh Bình", "Quảng Bình"),
    "food": ("Hà Nội", "TP.HCM", "Hội An", "Huế"),
    "cafe": ("Đà Lạt", "Hà Nội", "Hội An", "Đà Nẵng"),
    "general_travel": ("Hà Nội", "Đà Nẵng", "Hội An", "TP.HCM"),
}

THEME_SUGGESTION_REASON: dict[str, str] = {
    "healing": "nhịp chậm, thiên nhiên yên tĩnh, dễ chữa lành",
    "beach": "bãi biển, hải sản và kỳ nghỉ ven biển",
    "mountain": "núi, trekking và săn mây",
    "food": "ẩm thực địa phương phong phú",
    "cafe": "cafe view và nhịp đi chậm",
    "general_travel": "điểm đến phổ biến, dễ lập lịch",
}

THEME_PURPOSE_LABEL_VI: dict[str, str] = {
    "healing": "chữa lành",
    "beach": "biển",
    "mountain": "núi",
    "food": "ẩm thực",
    "cafe": "cà phê",
    "general_travel": "du lịch",
}

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
_DATE_RANGE_RE = re.compile(
    r"(?:(?:tu|from)\s+)?(?:ngay\s+)?"
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?/?\s*"
    r"(?:-|–|—|den|toi|to|until)\s*"
    r"(?:ngay\s+)?"
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?",
    re.IGNORECASE,
)
_DAY_COUNT_RE = re.compile(r"\b([1-9]\d{0,2})\s*(?:ngay|days?)\b", re.IGNORECASE)
_BARE_DAY_COUNT_RE = re.compile(
    r"\b([1-9]|[12][0-9]|30)\b(?!\s*(?:nguoi|nguoi lon|ban|dua|khach|pax|adults?|people|person|travelers?|ngay|days?|gio|tieng|hours?|trieu|dong|vnd|ngan))",
    re.IGNORECASE,
)
_WEEK_COUNT_RE = re.compile(r"\b([1-9]|1[0-2])\s*(?:tuan|weeks?)\b", re.IGNORECASE)
_HOUR_SPAN_RE = re.compile(
    r"\b(\d{1,2}(?:[.,]\d+)?)\s*(?:gio(?:\s+dong\s+ho)?|tieng|hours?|hrs?)\b",
    re.IGNORECASE,
)
_HOUR_COMPACT_RE = re.compile(r"(?<![0-9.,])(\d{1,2})h\b", re.IGNORECASE)
_FRACTION_HOUR_RE = re.compile(r"\b(0[.,]\d+)\s*h\b", re.IGNORECASE)
_MINUTE_SPAN_RE = re.compile(r"\b(\d{1,3})\s*(?:p(?![a-z])|phut|minutes?)\b", re.IGNORECASE)
_PEOPLE_RE = re.compile(
    r"\b([1-9]|[12][0-9]|30)\s*(?:nguoi|nguoi lon|ban|dua|khach|pax|adults?|people|person|travelers?)\b",
    re.IGNORECASE,
)
_DAY_WORDS = {
    "hai ngay": 2, "ba ngay": 3, "bon ngay": 4, "nam ngay": 5,
    "sau ngay": 6, "bay ngay": 7, "tam ngay": 8, "chin ngay": 9, "muoi ngay": 10,
    "two days": 2, "three days": 3, "four days": 4, "five days": 5,
    "cuoi tuan": 2, "cuoi tuan nay": 2, "weekend": 2, "ky nghi le": 3, "ky nghi": 2,
}
_WEEK_WORDS = {
    "mot tuan": 7, "hai tuan": 14, "ba tuan": 21, "bon tuan": 28,
    "one week": 7, "two weeks": 14, "three weeks": 21,
}
_PEOPLE_WORDS = {
    "mot nguoi": 1, "hai nguoi": 2, "ba nguoi": 3, "bon nguoi": 4,
    "one person": 1, "two people": 2, "couple": 2, "vo chong": 2,
    "di mot minh": 1, "mot minh": 1, "minh toi": 1, "di doi": 2, "nguoi yeu": 2, "gia dinh": 4,
}
REGION_DESTINATIONS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("tay nguyen",), "Đà Lạt"),
    (("tay bac", "vung cao"), "Sa Pa"),
    (("dong bang song cuu long", "mien tay", "mekong"), "Cần Thơ"),
    (("bien mien trung", "tam bien mien trung", "pho bien mien trung", "nam trung bo"), "Nha Trang"),
    (("pho co mien trung",), "Hội An"),
    (("mien trung",), "Đà Nẵng"),
    (("mien nam",), "TP.HCM"),
    (("mien bac",), "Hà Nội"),
)


def _hour_with_meridiem(hour: int, meridiem: str | None) -> int:
    if not meridiem:
        return hour
    mer = meridiem.casefold()
    if mer in {"pm", "chieu", "toi"} and hour < 12:
        return hour + 12
    if mer in {"am", "sang"} and hour == 12:
        return 0
    return hour


def _destination_suggestions(purpose: str | None) -> list[dict]:
    spec = THEMES.get(purpose or "")
    by_name = {item.name: item for item in FOCUS_DESTINATIONS}
    priority_names = THEME_DESTINATION_PRIORITY.get(purpose or "", THEME_DESTINATION_PRIORITY["general_travel"])
    reason = THEME_SUGGESTION_REASON.get(purpose or "", THEME_SUGGESTION_REASON["general_travel"])
    suggestions: list[dict] = []
    for index, name in enumerate(priority_names):
        destination = by_name.get(name)
        if not destination:
            continue
        catalog_score = 0
        for place in PLACES:
            if _haversine_km(destination.lat, destination.lng, place.lat, place.lng) > (
                destination.radius_km or DESTINATION_RADIUS_KM
            ):
                continue
            catalog_score += _place_theme_score(place, spec)
        suggestions.append({
            "label": destination.name,
            "lat": destination.lat,
            "lng": destination.lng,
            "reason": reason,
            "score": 1000 - index * 10 + min(catalog_score, 50),
        })
    return suggestions[:4]


def _destination_ask_question(locale: str, purpose: str | None, suggestions: list[dict]) -> str:
    labels = ", ".join(item["label"] for item in suggestions[:4] if item.get("label"))
    purpose_vi = THEME_PURPOSE_LABEL_VI.get(purpose or "", "du lịch")
    if locale == "vi":
        if labels:
            return (
                f"Bạn muốn đi {purpose_vi} ở đâu? Mình gợi ý {labels}. "
                "Chọn một điểm, hoặc nói 'bạn chọn giúp' để mình thiết kế hộ."
            )
        return "Bạn muốn đi điểm đến/thành phố nào?"
    if labels:
        return (
            f"Where would you like to go? Suggestions: {labels}. "
            "Pick one, or say 'surprise me' and I'll choose for you."
        )
    return "Which destination or city would you like to visit?"


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


def _parse_dmy_year(raw: str | None, today: date) -> int:
    if not raw:
        return today.year
    year = int(raw)
    if year < 100:
        year += 2000
    return year


def _safe_dmy(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_date_range_days(folded: str, today: date | None = None) -> int | None:
    today = today or date.today()
    match = _DATE_RANGE_RE.search(folded)
    if not match:
        return None
    left = _safe_dmy(_parse_dmy_year(match.group(3), today), int(match.group(2)), int(match.group(1)))
    year2 = _parse_dmy_year(match.group(6), today) if match.group(6) else _parse_dmy_year(match.group(3), today)
    right = _safe_dmy(year2, int(match.group(5)), int(match.group(4)))
    if not left or not right:
        return None
    if right < left:
        try:
            right = date(right.year + 1, right.month, right.day)
        except ValueError:
            return None
    days = (right - left).days + 1
    if 1 <= days <= MAX_ASKED_DAYS:
        return days
    return None


def _has_explicit_clock(folded: str) -> bool:
    return bool(re.search(r"\d{1,2}\s*(?:[:h]|gio|tieng|hours?|hrs?)", folded, re.I))


def _extract_time_window(folded: str) -> dict | None:
    date_match = _DATE_RANGE_RE.search(folded)
    for match in _CLOCK_RANGE_RE.finditer(folded):
        if date_match and match.start() >= date_match.start() and match.end() <= date_match.end():
            continue
        if date_match and not re.search(r"(?:[:h]|gio|tieng)", match.group(0), re.I):
            continue
        window = _normalize_time_window({
            "start_hour": _hour_with_meridiem(int(match.group(1)), match.group(3)),
            "start_minute": int(match.group(2) or 0),
            "end_hour": _hour_with_meridiem(int(match.group(4)), match.group(6)),
            "end_minute": int(match.group(5) or 0),
        })
        if window:
            return window
    return None


def _extract_days(folded: str) -> int | None:
    weeks = _WEEK_COUNT_RE.search(folded)
    if weeks:
        return min(MAX_ASKED_DAYS, int(weeks.group(1)) * 7)
    for phrase, days in _WEEK_WORDS.items():
        if phrase in folded:
            return min(MAX_ASKED_DAYS, days)
    labeled = _DAY_COUNT_RE.search(folded)
    if labeled:
        return min(MAX_ASKED_DAYS, max(1, int(labeled.group(1))))
    for phrase, days in _DAY_WORDS.items():
        if phrase in folded:
            return days
    dated = _extract_date_range_days(folded)
    if dated:
        return dated
    # Wizard answers like "10" then "2 người" lose the word "ngày" after folding.
    people = _extract_people(folded)
    if people is None:
        return None
    for match in _BARE_DAY_COUNT_RE.finditer(folded):
        value = int(match.group(1))
        if value != people:
            return min(MAX_ASKED_DAYS, value)
    return None


def _extract_duration_minutes(folded: str, has_window: bool) -> tuple[int | None, list[dict]]:
    if has_window:
        return None, []
    fraction = _FRACTION_HOUR_RE.search(folded)
    if fraction:
        hours = float(fraction.group(1).replace(",", "."))
        return round(hours * 60), []
    minute_span = _MINUTE_SPAN_RE.search(folded)
    if minute_span:
        return int(minute_span.group(1)), []
    span = _HOUR_SPAN_RE.search(folded)
    if span:
        hours = float(span.group(1).replace(",", "."))
        if 10 <= hours <= 23:
            whole = int(hours)
            return None, [{
                "field": "duration",
                "value": span.group(0),
                "reason": "could be duration or start time",
                "question": f"Bạn muốn đi trong {whole} tiếng hay bắt đầu lúc {whole}h?",
            }]
        if 0.75 <= hours <= 12:
            return round(hours * 60), []
    compact = _HOUR_COMPACT_RE.search(folded)
    if compact:
        hours = int(compact.group(1))
        if 10 <= hours <= 23:
            return None, [{
                "field": "duration",
                "value": compact.group(0),
                "reason": "could be duration or start time",
                "question": f"Bạn muốn đi trong {hours} tiếng hay bắt đầu lúc {hours}h?",
            }]
        if 1 <= hours <= 9:
            return hours * 60, []
    return None, []


# Beach-theme terms that mean the coast, not just seafood restaurants.
_COASTAL_BEACH_TERMS = frozenset({
    "bien",
    "bai bien",
    "dao",
    "hoang hon bien",
    "ngam hoang hon",
    "san ho",
    "beach",
    "island",
    "tam bien",
    "di bien",
    "nghi bien",
    "ven bien",
})


def _extract_purpose(folded: str) -> str | None:
    hits: list[tuple[int, int, str, str]] = []
    for key in ("healing", "beach", "mountain", "cafe", "food", "general_travel"):
        spec = THEMES[key]
        for term in spec.terms:
            for start, end in _term_spans(folded, term):
                hits.append((start, end, key, term))
    if not hits:
        return None
    matched = {row[2] for row in hits}
    # "thích biển và hải sản" must stay a beach trip. "hải sản" is also a food
    # term and would otherwise win as the last hit, turning the plan into a
    # restaurant crawl (often quán chay from OSM).
    if "beach" in matched and "food" in matched:
        if any(key == "beach" and term in _COASTAL_BEACH_TERMS for *_, key, term in hits):
            return "beach"
    hits.sort(key=lambda row: (row[0], row[1]))
    return hits[-1][2]


def _purpose_for_destination(destination: IntentDestination | None, purpose: str | None) -> str | None:
    if destination and destination.name in {"Yên Tử", "Chùa Hương"} and purpose == "beach":
        return "mountain"
    return purpose


def _extract_people(folded: str) -> int | None:
    match = _PEOPLE_RE.search(folded)
    if match:
        return int(match.group(1))
    for phrase, count in _PEOPLE_WORDS.items():
        if phrase in folded:
            return count
    return None


def _rule_extract(context: str) -> dict:
    folded = _fold(context)
    window = _extract_time_window(folded)
    days = _extract_days(folded)
    minutes, ambiguities = _extract_duration_minutes(folded, window is not None)
    if days:
        minutes = None
        ambiguities = [item for item in ambiguities if item.get("field") != "duration"]
    destination = _find_destination(folded)
    return {
        "destination": destination,
        "purpose": _purpose_for_destination(destination, _extract_purpose(folded)),
        "days": days,
        "minutes": minutes,
        "window": window,
        "raw_window": window,
        "people": _extract_people(folded),
        "ambiguities": ambiguities,
    }


def rule_structured_intent(context: str) -> dict:
    rules = _rule_extract(context)
    destination = rules["destination"]
    duration, duration_unit, duration_value, planner_mode, duration_minutes = _duration_shape(
        rules["days"], rules["minutes"], rules["window"]
    )
    return {
        "destination": _destination_payload(destination) if destination else None,
        "trip_purpose": rules["purpose"],
        "planner_mode": planner_mode,
        "duration": duration,
        "duration_value": duration_value,
        "duration_unit": duration_unit,
        "duration_minutes": duration_minutes,
        "duration_days": rules["days"],
        "time_window": rules["window"],
        "people": rules["people"],
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
        return min(MAX_ASKED_DAYS, round(number * 7)), None
    if unit == "day":
        return min(MAX_ASKED_DAYS, round(number)), None
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


def _destination_mentioned(folded: str, destination: IntentDestination) -> bool:
    if _contains_term(folded, destination.name) or _fold(destination.name) in folded:
        return True
    aliases = DESTINATION_ALIASES.get(destination.name, ()) + LANDMARK_ALIASES.get(destination.name, ())
    return any(_contains_term(folded, alias) for alias in aliases)


def _build_intent_result(
    *,
    locale: str,
    source: str,
    purpose: str | None,
    destination: IntentDestination | None,
    days: int | None,
    minutes: int | None,
    window: dict | None,
    raw_window: object,
    people: int | None,
    budget: int | None,
    ambiguities: list[dict],
) -> dict:
    duration, duration_unit, duration_value, planner_mode, duration_minutes = _duration_shape(days, minutes, window)
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
            question = "30 phút hơi ngắn để lập lịch trình. Bạn muốn tìm 1 điểm gần nhất hay tăng thời lượng lên 1-2 giờ?" if locale == "vi" else "The duration is too short for a multi-stop itinerary. Would you like to increase it?"
        elif validation_errors[0]["code"] == "time_window_too_short":
            question = "Khung giờ này hơi ngắn. Bạn muốn tìm 1 điểm gần nhất hay tăng thời lượng lên 1-2 giờ?" if locale == "vi" else "This time window is a bit short. Would you like to extend it to 1-2 hours?"
        elif validation_errors[0]["code"] == "time_window_too_long":
            question = "Khung giờ này quá dài cho một ngày. Bạn muốn chia thành nhiều ngày hay chọn khung giờ ngắn hơn?" if locale == "vi" else "This time window is too long for one day. Would you like to split into multiple days?"
        else:
            question = "Khung giờ chưa hợp lệ. Bạn muốn đi từ mấy giờ đến mấy giờ?" if locale == "vi" else "Invalid time window. What hours do you prefer?"
    elif ambiguities and ambiguities[0].get("question"):
        question = ambiguities[0]["question"]
    elif "destination" in missing:
        question = _destination_ask_question(locale, purpose, suggestions)
    elif "duration" in missing:
        if locale == "vi":
            question = (
                f"Mình hiểu bạn muốn đi {destination.name}. Bạn đi trong bao lâu: vài giờ, 1 ngày hay nhiều ngày?"
                if destination
                else "Bạn đi trong bao lâu: vài giờ, 1 ngày hay nhiều ngày?"
            )
        else:
            question = (
                f"Got it — {destination.name}. How long do you plan to stay: a few hours, 1 day, or multiple days?"
                if destination
                else "How long do you plan to stay: a few hours, 1 day, or multiple days?"
            )
    elif "people" in missing:
        if locale == "vi":
            question = f"Đi {destination.name} thì bạn đi mấy người?" if destination else "Bạn đi mấy người?"
        else:
            question = f"How many people for {destination.name}?" if destination else "How many people are traveling?"

    parsed_destination = None
    if destination:
        parsed_destination = _destination_payload(destination)
    return {
        "schema_version": "intent-parse-v2",
        "extraction_source": source,
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
            "extraction_source": source,
        },
    }


def _normalize_ai_intent(context: str, payload: dict, locale: str = "vi") -> dict:
    payload = AIPlanningIntentPayload.model_validate(payload).model_dump(exclude_none=True)
    rules = _rule_extract(context)
    folded = _fold(context)
    purpose = rules.get("purpose") or _coerce_purpose(payload.get("trip_purpose"))
    destination = rules.get("destination")
    if not destination:
        ai_destination = _resolve_destination(payload.get("destination_text"))
        if ai_destination and _destination_mentioned(folded, ai_destination):
            destination = ai_destination
    window = rules.get("window")
    raw_window = rules.get("raw_window") or payload.get("time_window")
    if window is None:
        ai_window = _normalize_time_window(payload.get("time_window"))
        if ai_window and _DATE_RANGE_RE.search(folded) and not _has_explicit_clock(folded):
            ai_window = None
        window = ai_window
    days = rules.get("days")
    minutes = rules.get("minutes")
    if days is None and minutes is None and window is None:
        days, minutes = _normalize_duration(payload.get("duration_value"), payload.get("duration_unit"))
        if days and not _DAY_COUNT_RE.search(folded) and not any(phrase in folded for phrase in _DAY_WORDS) and not any(phrase in folded for phrase in _WEEK_WORDS) and not _WEEK_COUNT_RE.search(folded) and not _DATE_RANGE_RE.search(folded):
            days = None
        if minutes and not _HOUR_SPAN_RE.search(folded) and not _HOUR_COMPACT_RE.search(folded) and not _MINUTE_SPAN_RE.search(folded) and not _FRACTION_HOUR_RE.search(folded):
            minutes = None
    if window:
        minutes = None
    people = rules.get("people")
    if people is None:
        ai_people = _coerce_int(payload.get("people"))
        if ai_people and (_PEOPLE_RE.search(folded) or any(phrase in folded for phrase in _PEOPLE_WORDS)):
            people = ai_people
    budget = _coerce_int(payload.get("budget"))
    ambiguities = rules.get("ambiguities") or []
    if not ambiguities:
        ambiguities = _normalize_ambiguities(payload.get("ambiguities"))
    return _build_intent_result(
        locale=locale,
        source="ai",
        purpose=purpose,
        destination=destination,
        days=days,
        minutes=minutes,
        window=window,
        raw_window=raw_window,
        people=people,
        budget=budget,
        ambiguities=ambiguities,
    )


def _result_from_rules(context: str, locale: str = "vi") -> dict:
    rules = _rule_extract(context)
    return _build_intent_result(
        locale=locale,
        source="rules",
        purpose=rules.get("purpose"),
        destination=rules.get("destination"),
        days=rules.get("days"),
        minutes=rules.get("minutes"),
        window=rules.get("window"),
        raw_window=rules.get("raw_window"),
        people=rules.get("people"),
        budget=None,
        ambiguities=rules.get("ambiguities") or [],
    )


def parse_intent(context: str, locale: str = "vi", extractor=None) -> dict:
    extractor = extractor or getattr(ai_adapter, "extract_planning_intent", None)
    if extractor:
        try:
            payload = extractor(context, locale)
            if isinstance(payload, dict) and payload:
                return _normalize_ai_intent(context, payload, locale)
        except (RuntimeError, TypeError, ValueError, ValidationError):
            pass
    return _result_from_rules(context, locale)
