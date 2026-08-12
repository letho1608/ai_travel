import json
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.text_utils import ascii_fold


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    kind: str
    area: str
    lat: float
    lng: float
    cost: int
    duration_min: int
    tags: tuple[str, ...]
    open_hour: int = 7
    close_hour: int = 22
    source: str = "demo"
    source_url: str | None = None
    image_url: str | None = None
    image_credit: str | None = None


def place_name_key(name: str) -> str:
    """Stable normalized identity for a place name across catalogue modes.

    Vietnamese diacritics are folded away, en/em dashes are normalized to
    hyphens, and whitespace is collapsed so an OSM import row and its curated
    anchor carry the same key regardless of spelling/casing differences.
    """
    return " ".join(ascii_fold(name).replace("\u2013", "-").replace("\u2014", "-").split())


PLACE_IMAGE_URLS: dict[str, str] = {
    "bao-tang-phu-nu": "https://commons.wikimedia.org/wiki/Special:FilePath/Vietnamese_Women%27s_Museum_Building.JPG?width=800",
    "curated-ho-guom": "https://commons.wikimedia.org/wiki/Special:FilePath/August%202003%20Hoan%20Kiem%20.jpg?width=800",
    "curated-ho-tay": "https://commons.wikimedia.org/wiki/Special:FilePath/H%E1%BB%93%20T%C3%A2y.png?width=800",
    "curated-lang-bac": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi%20Vietnam%20Mausoleum-of-Ho-Chi-Minh-01.jpg?width=800",
    "curated-pho-co-ha-noi": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi%20old%20quarter%20shophouse.jpg?width=800",
    "curated-cho-dem-dong-xuan": "https://commons.wikimedia.org/wiki/Special:FilePath/Ch%E1%BB%A3%20%C4%90%E1%BB%93ng%20Xu%C3%A2n%2C%20Le%20grand%20march%C3%A9%2C%20H%C3%A0%20N%E1%BB%99i%2C%201926.jpg?width=800",
    "curated-pho-ta-hien": "https://commons.wikimedia.org/wiki/Special:FilePath/20190923%20095622Ph%E1%BB%91%20T%E1%BA%A1%20Hi%E1%BB%87n%20H%C3%A0%20N%E1%BB%99i.jpg?width=800",
    "curated-hang-dao": "https://commons.wikimedia.org/wiki/Special:FilePath/Balloon%20seller%2C%20Hanoi%20%284856307014%29.jpg?width=800",
    "curated-hang-gai": "https://commons.wikimedia.org/wiki/Special:FilePath/Crossroad%20in%20Hanoi.jpg?width=800",
    "curated-hang-bac": "https://commons.wikimedia.org/wiki/Special:FilePath/Bovloj%20%C4%B5us%20lavitaj%20kaj%20lasitaj%20sur%20trotuaro%20en%20Hanojo%2001.jpg?width=800",
    "curated-hang-ma": "https://commons.wikimedia.org/wiki/Special:FilePath/H%C3%A0ng%20M%C3%A3%20Street%2C%20Hanoi.jpg?width=800",
    "curated-hang-duong": "https://commons.wikimedia.org/wiki/Special:FilePath/2024-11-03%20H%C3%A0ng%20%C4%90%C6%B0%E1%BB%9Dng%20Street%2C%20Hanoi.jpg?width=800",
    "curated-hang-ngang": "https://commons.wikimedia.org/wiki/Special:FilePath/Street%20corner%20in%20Hanoi.JPG?width=800",
    "curated-hang-buom": "https://commons.wikimedia.org/wiki/Special:FilePath/A%20Chinese%20temple%20in%20the%20Hanoi%20old%20quarter%202016-11-01%20%28flickr31416950736%29.jpg?width=800",
    "curated-hang-dau": "https://commons.wikimedia.org/wiki/Special:FilePath/H%C3%A0ng%20D%E1%BA%A7u%20Street%2C%20Hanoi%2C%2020240204%201340%205780.jpg?width=800",
    "curated-hang-khay": "https://commons.wikimedia.org/wiki/Special:FilePath/DAI%20BO%20%28%20HOANG%20KIEM%20LAKE%29%20-%20panoramio.jpg?width=800",
    "curated-hang-trong": "https://commons.wikimedia.org/wiki/Special:FilePath/Five%20tigers%2C%20Hang%20Trong%20painting%2C%20Hanoi%2C%20paper%2C%20view%201%20-%20Vietnam%20National%20Museum%20of%20Fine%20Arts%20-%20Hanoi%2C%20Vietnam%20-%20DSC05281.JPG?width=800",
    "curated-bun-cha-dac-kim": "https://commons.wikimedia.org/wiki/Special:FilePath/Bun%20cha.jpg?width=800",
    "curated-bun-cha-huong-lien": "https://commons.wikimedia.org/wiki/Special:FilePath/Bun%20cha%20Hanoi.jpg?width=800",
    "curated-cafe-dinh": "https://commons.wikimedia.org/wiki/Special:FilePath/C%C3%80%20PH%C3%8A%20KEM%20TR%E1%BB%A8NG%20%28Egg%20cream%20coffee%29.jpg?width=800",
    "curated-cha-ca-thang-long": "https://commons.wikimedia.org/wiki/Special:FilePath/Cha%20ca%20La%20Vong.jpg?width=800",
    "curated-pho-bat-dan": "https://commons.wikimedia.org/wiki/Special:FilePath/Pho%20Ha%20Noi.jpg?width=800",
}

PLACE_IMAGE_CREDITS: dict[str, str] = {
    "bao-tang-phu-nu": "Wikimedia Commons (Vietnamese Women's Museum Building)",
    "curated-ho-guom": "Wikimedia Commons (August 2003 Hoan Kiem .jpg)",
    "curated-ho-tay": "Wikimedia Commons (Hồ Tây.png)",
    "curated-lang-bac": "Wikimedia Commons (Hanoi Vietnam Mausoleum-of-Ho-Chi-Minh-01.jpg)",
    "curated-pho-co-ha-noi": "Wikimedia Commons (Hanoi old quarter shophouse.jpg)",
    "curated-cho-dem-dong-xuan": "Wikimedia Commons (Chợ Đồng Xuân, Le grand marché, Hà Nội, 1926.jpg)",
    "curated-pho-ta-hien": "Wikimedia Commons (20190923 095622Phố Tạ Hiện Hà Nội.jpg)",
    "curated-hang-dao": "Wikimedia Commons (Balloon seller, Hanoi (4856307014).jpg)",
    "curated-hang-gai": "Wikimedia Commons (Crossroad in Hanoi.jpg)",
    "curated-hang-bac": "Wikimedia Commons (Bovloj ĵus lavitaj kaj lasitaj sur trotuaro en Hanojo 01.jpg)",
    "curated-hang-ma": "Wikimedia Commons (Hàng Mã Street, Hanoi.jpg)",
    "curated-hang-duong": "Wikimedia Commons (2024-11-03 Hàng Đường Street, Hanoi.jpg)",
    "curated-hang-ngang": "Wikimedia Commons (Street corner in Hanoi.JPG)",
    "curated-hang-buom": "Wikimedia Commons (A Chinese temple in the Hanoi old quarter 2016-11-01 (flickr31416950736).jpg)",
    "curated-hang-dau": "Wikimedia Commons (Hàng Dầu Street, Hanoi, 20240204 1340 5780.jpg)",
    "curated-hang-khay": "Wikimedia Commons (DAI BO ( HOANG KIEM LAKE) - panoramio.jpg)",
    "curated-hang-trong": "Wikimedia Commons (Five tigers, Hang Trong painting, Hanoi, paper, view 1 - Vietnam National Museum of Fine Arts - Hanoi, Vietnam - DSC05281.JPG)",
    "curated-bun-cha-dac-kim": "Wikimedia Commons (Bun cha.jpg)",
    "curated-bun-cha-huong-lien": "Wikimedia Commons (Bun cha Hanoi.jpg)",
    "curated-cafe-dinh": "Wikimedia Commons (CÀ PHÊ KEM TRỨNG (Egg cream coffee).jpg)",
    "curated-cha-ca-thang-long": "Wikimedia Commons (Cha ca La Vong.jpg)",
    "curated-pho-bat-dan": "Wikimedia Commons (Pho Ha Noi.jpg)",
}


def image_for(place: "Place") -> tuple[str | None, str | None]:
    """Resolve a place's image (URL, credit) in any catalogue mode.

    Order: the place's own recorded image (OSM import / Postgres row), then the
    id-keyed curated map, then the name-keyed map so a catalogue row whose
    normalized name matches a curated/demo place still surfaces its image even
    when the catalogue runs on `ma_nguon` ids (Postgres mode).
    """
    if place.image_url:
        credit = place.image_credit or PLACE_IMAGE_CREDITS_BY_NAME.get(place_name_key(place.name))
        return place.image_url, credit
    url = PLACE_IMAGE_URLS.get(place.id)
    if url:
        return url, PLACE_IMAGE_CREDITS.get(place.id)
    key = place_name_key(place.name)
    return PLACE_IMAGE_URLS_BY_NAME.get(key), PLACE_IMAGE_CREDITS_BY_NAME.get(key)


DEMO_PLACES = [
    Place("ho-guom", "Hồ Hoàn Kiếm", "dia_danh", "Hoàn Kiếm", 21.0287, 105.8522, 0, 60, ("di_bo", "chill", "ngoai_troi"), 5, 23),
    Place("bao-tang-phu-nu", "Bảo tàng Phụ nữ Việt Nam", "bao_tang", "Hoàn Kiếm", 21.0235, 105.8515, 40_000, 75, ("van_hoa", "trong_nha"), 8, 17),
    Place("van-mieu", "Văn Miếu – Quốc Tử Giám", "dia_danh", "Đống Đa", 21.0277, 105.8355, 70_000, 75, ("van_hoa", "checkin"), 8, 17),
    Place("cafe-dinh", "Café Đinh", "cafe", "Hoàn Kiếm", 21.0321, 105.8521, 60_000, 60, ("cafe", "hoai_co", "chill"), 7, 22),
    Place("trang-tien", "Kem Tràng Tiền", "quan_an", "Hoàn Kiếm", 21.0245, 105.8558, 50_000, 35, ("an_vat", "ban_chay"), 8, 23),
    Place("pho-bat-dan", "Phở Bát Đàn", "quan_an", "Hoàn Kiếm", 21.0337, 105.8472, 80_000, 45, ("am_thuc", "binh_dan"), 6, 22),
    Place("ho-tay", "Đường ven Hồ Tây", "dia_danh", "Tây Hồ", 21.0583, 105.8142, 0, 75, ("view_dep", "ngoai_troi", "chill"), 5, 23),
    Place("chua-tran-quoc", "Chùa Trấn Quốc", "dia_danh", "Tây Hồ", 21.0479, 105.8367, 0, 50, ("van_hoa", "yen_tinh"), 7, 18),
    Place("cafe-serein", "Serein Café & Lounge", "cafe", "Hoàn Kiếm", 21.0446, 105.8491, 120_000, 60, ("cafe", "view_dep", "tre_trung"), 8, 23),
    Place("long-bien", "Cầu Long Biên", "dia_danh", "Long Biên", 21.0433, 105.8602, 0, 45, ("checkin", "ngoai_troi"), 5, 23),
    Place("cong-vien-thong-nhat", "Công viên Thống Nhất", "cong_vien", "Hai Bà Trưng", 21.0151, 105.8431, 10_000, 70, ("ngoai_troi", "gia_dinh"), 6, 22),
    Place("bun-cha-huong-lien", "Bún chả Hương Liên", "nha_hang", "Hai Bà Trưng", 21.0183, 105.8533, 90_000, 50, ("am_thuc", "ban_chay"), 10, 21),
]

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_imported_places() -> tuple[list[Place], dict]:
    path = DATA_DIR / "places.json"
    if not path.exists():
        return [], {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    places = [
        Place(
            id=item["id"], name=item["name"], kind=item["kind"], area=item["area"],
            lat=float(item["lat"]), lng=float(item["lng"]), cost=int(item.get("cost", 0)),
            duration_min=int(item.get("duration_min", 60)), tags=tuple(item.get("tags", [])),
            open_hour=int(item.get("open_hour", 7)), close_hour=int(item.get("close_hour", 22)),
            source=item.get("source", "OpenStreetMap"), source_url=item.get("source_url"),
            image_url=item.get("image_url"), image_credit=item.get("image_credit"),
        )
        for item in payload.get("places", [])
    ]
    return places, payload.get("metadata", {})


IMPORTED_PLACES, PLACE_METADATA = _load_imported_places()


def finalize_catalogue(rows: list[Place]) -> list[Place]:
    """Merge catalogue rows with the curated Hanoi anchors/dining.

    Catalogue rows always win a name collision (they carry OSM verification and
    route-matrix ids); a curated anchor is only appended when no row shares its
    normalized name. This single step keeps the local (places.json/demo) and
    Postgres (`ma_nguon`) catalogues consistent, so planning logic sees the
    same curated stops in every mode.
    """
    merged = list(rows)
    seen_ids = {place.id for place in merged}
    seen_names = {place_name_key(place.name) for place in merged}
    for curated in (*CURATED_HANOI_ANCHORS, *CURATED_HANOI_DINING):
        if curated.id in seen_ids:
            continue
        key = place_name_key(curated.name)
        if key in seen_names:
            continue
        merged.append(curated)
        seen_ids.add(curated.id)
        seen_names.add(key)
    return merged


CURATED_HANOI_ANCHORS = [
    Place(
        "curated-ho-guom",
        "Hồ Gươm",
        "dia_danh",
        "Hoàn Kiếm",
        21.0287,
        105.8522,
        0,
        60,
        ("hanoi_icon", "ho_guom", "hoan_kiem", "di_bo", "chill", "ngoai_troi", "checkin"),
        5,
        23,
        "curated",
        None,
    ),
    Place(
        "curated-ho-tay",
        "Hồ Tây",
        "dia_danh",
        "Tây Hồ",
        21.0583,
        105.8142,
        0,
        75,
        ("hanoi_icon", "ho_tay", "di_bo", "chill", "ngoai_troi", "view_dep"),
        5,
        23,
        "curated",
        None,
    ),
    Place(
        "curated-lang-bac",
        "Lăng Chủ tịch Hồ Chí Minh",
        "dia_danh",
        "Ba Đình",
        21.0368,
        105.8347,
        0,
        60,
        ("hanoi_icon", "lang_bac", "ho_chi_minh", "ba_dinh", "van_hoa", "lich_su", "monument"),
        7,
        11,
        "curated",
        None,
    ),
    Place(
        "curated-pho-co-ha-noi",
        "Phố cổ Hà Nội",
        "dia_danh",
        "Hoàn Kiếm",
        21.0341,
        105.8523,
        0,
        90,
        ("hanoi_icon", "pho_co", "old_quarter", "di_bo", "am_thuc", "nightlife", "checkin"),
        7,
        23,
        "curated",
        None,
    ),
    Place(
        "curated-cho-dem-dong-xuan",
        "Chợ đêm Hàng Đào – Đồng Xuân",
        "cho",
        "Hoàn Kiếm",
        21.0383,
        105.8499,
        0,
        75,
        ("pho_co", "cho_dem", "night_market", "am_thuc", "mua_sam", "nightlife"),
        18,
        23,
        "curated",
        None,
    ),
    Place(
        "curated-pho-ta-hien",
        "Phố Tạ Hiện",
        "dia_danh",
        "Hoàn Kiếm",
        21.0353,
        105.8522,
        0,
        75,
        ("pho_co", "nightlife", "am_thuc", "di_bo", "checkin"),
        17,
        23,
        "curated",
        None,
    ),
    Place("curated-hang-dao", "Hàng Đào", "dia_danh", "Hoàn Kiếm", 21.0359, 105.8508, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "cho_dem", "nightlife"), 7, 23, "curated", None),
    Place("curated-hang-gai", "Hàng Gai", "dia_danh", "Hoàn Kiếm", 21.0322, 105.8498, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "lua_to_tam", "checkin"), 7, 22, "curated", None),
    Place("curated-hang-bac", "Hàng Bạc", "dia_danh", "Hoàn Kiếm", 21.0347, 105.8523, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "thu_cong", "checkin"), 7, 22, "curated", None),
    Place("curated-hang-ma", "Hàng Mã", "dia_danh", "Hoàn Kiếm", 21.0378, 105.8477, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "le_hoi", "checkin"), 7, 22, "curated", None),
    Place("curated-hang-duong", "Hàng Đường", "dia_danh", "Hoàn Kiếm", 21.0372, 105.8492, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "am_thuc", "o_mai", "mua_sam"), 7, 22, "curated", None),
    Place("curated-hang-ngang", "Hàng Ngang", "dia_danh", "Hoàn Kiếm", 21.0365, 105.8501, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "lich_su", "checkin"), 7, 22, "curated", None),
    Place("curated-hang-buom", "Hàng Buồm", "dia_danh", "Hoàn Kiếm", 21.0355, 105.8528, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "am_thuc", "nightlife", "checkin"), 7, 23, "curated", None),
    Place("curated-hang-dau", "Hàng Dầu", "dia_danh", "Hoàn Kiếm", 21.0311, 105.8535, 0, 30, ("pho_co", "old_quarter", "hang_pho", "di_bo", "mua_sam", "giay_dep"), 7, 22, "curated", None),
    Place("curated-hang-khay", "Hàng Khay", "dia_danh", "Hoàn Kiếm", 21.0292, 105.8518, 0, 30, ("pho_co", "old_quarter", "hang_pho", "di_bo", "ho_guom", "checkin"), 7, 22, "curated", None),
    Place("curated-hang-trong", "Hàng Trống", "dia_danh", "Hoàn Kiếm", 21.0301, 105.8499, 0, 35, ("pho_co", "old_quarter", "hang_pho", "di_bo", "van_hoa", "tranh_dan_gian", "am_thuc"), 7, 22, "curated", None),
]

CURATED_HANOI_DINING = [
    Place(
        "curated-bun-cha-huong-lien",
        "Bún chả Hương Liên",
        "nha_hang",
        "Hai Bà Trưng",
        21.0183,
        105.8533,
        90_000,
        50,
        ("am_thuc", "ban_chay", "local", "vietnamese", "bun_cha"),
        10,
        21,
        "curated",
        None,
    ),
    Place(
        "curated-pho-bat-dan",
        "Phở Bát Đàn",
        "quan_an",
        "Hoàn Kiếm",
        21.0337,
        105.8472,
        80_000,
        45,
        ("am_thuc", "binh_dan", "local", "vietnamese", "pho"),
        6,
        22,
        "curated",
        None,
    ),
    Place(
        "curated-bun-cha-dac-kim",
        "Bún chả Đắc Kim",
        "quan_an",
        "Hoàn Kiếm",
        21.0340,
        105.8489,
        85_000,
        45,
        ("am_thuc", "binh_dan", "local", "vietnamese", "bun_cha", "pho_co"),
        8,
        21,
        "curated",
        None,
    ),
    Place(
        "curated-cha-ca-thang-long",
        "Chả cá Thăng Long",
        "nha_hang",
        "Hoàn Kiếm",
        21.0355,
        105.8485,
        150_000,
        60,
        ("am_thuc", "local", "vietnamese", "cha_ca", "pho_co"),
        10,
        22,
        "curated",
        None,
    ),
    Place(
        "curated-cafe-dinh",
        "Café Đinh",
        "cafe",
        "Hoàn Kiếm",
        21.0321,
        105.8521,
        60_000,
        45,
        ("cafe", "hoai_co", "chill", "pho_co"),
        7,
        22,
        "curated",
        None,
    ),
]

# Canonical id -> display name for every curated/demo place, so planning code
# can resolve a `curated-*`/demo id against a Postgres-style catalogue by name.
KNOWN_PLACE_NAMES_BY_ID: dict[str, str] = {
    place.id: place.name
    for place in (*DEMO_PLACES, *CURATED_HANOI_ANCHORS, *CURATED_HANOI_DINING)
}

_CURATED_NAME_KEYS = {place_name_key(name) for name in KNOWN_PLACE_NAMES_BY_ID.values()}


def is_curated_named(place: "Place") -> bool:
    """True when a place carries a canonical curated/demo name.

    Used by routing so the OSM twin that finalize_catalogue keeps in place of a
    dropped curated anchor (Postgres-style catalogues have no `curated-*` rows)
    stays routable — the same physical stop in every catalogue mode.
    """
    return (
        place.id in KNOWN_PLACE_NAMES_BY_ID
        or place_name_key(place.name) in _CURATED_NAME_KEYS
    )


def _build_name_image_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Project the id-keyed image maps onto normalized place names.

    Name keys are the stable identity that survives catalogue-mode switches
    (an OSM row whose name matches a curated anchor keeps its image even when
    its id is `ma_nguon`-based), which is how image parity is achieved.
    """
    urls: dict[str, str] = {}
    credits: dict[str, str] = {}
    for place_id, url in PLACE_IMAGE_URLS.items():
        name = KNOWN_PLACE_NAMES_BY_ID.get(place_id)
        if not name:
            continue
        key = place_name_key(name)
        urls[key] = url
        if place_id in PLACE_IMAGE_CREDITS:
            credits[key] = PLACE_IMAGE_CREDITS[place_id]
    return urls, credits


PLACE_IMAGE_URLS_BY_NAME, PLACE_IMAGE_CREDITS_BY_NAME = _build_name_image_maps()

# Local catalogue: imported OSM rows (or the demo list when places.json is
# absent), merged with the curated anchors once the curated lists exist above.
PLACES = finalize_catalogue(IMPORTED_PLACES if IMPORTED_PLACES else DEMO_PLACES)


def _load_postgres_places() -> tuple[list[Place], dict]:
    database_url = os.getenv("URL_CSDL_POSTGRES")
    if not database_url:
        raise RuntimeError("URL_CSDL_POSTGRES is required outside local mode")
    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=3) as connection:
        rows = connection.execute(
            "SELECT ten,loai,khu_vuc,gia_trung_binh,tags,gio_mo_cua,toa_do,"
            "nguon,nguon_url,ma_nguon,thoi_luong_phut,hinh_anh,hinh_anh_nguon "
            "FROM dia_diem WHERE trang_thai='active' AND ma_nguon IS NOT NULL"
        ).fetchall()
    if not rows:
        raise RuntimeError("PostgreSQL catalogue is empty; run scripts/seed_postgres.py")
    places = [
        Place(
            id=row["ma_nguon"], name=row["ten"], kind=row["loai"],
            area=row["khu_vuc"] or "Hà Nội", lat=float(row["toa_do"]["lat"]),
            lng=float(row["toa_do"]["lng"]), cost=int(row["gia_trung_binh"] or 0),
            duration_min=int(row["thoi_luong_phut"]), tags=tuple(row["tags"] or []),
            open_hour=int((row["gio_mo_cua"] or {}).get("open", 7)),
            close_hour=int((row["gio_mo_cua"] or {}).get("close", 22)),
            source=row["nguon"], source_url=row["nguon_url"],
            image_url=row["hinh_anh"], image_credit=row["hinh_anh_nguon"],
        )
        for row in rows
    ]
    return places, {"provider": "PostgreSQL catalogue", "count": len(places)}


if os.getenv("APP_ENV", "local") != "local":
    PLACES, PLACE_METADATA = _load_postgres_places()
    # Postgres ids are `ma_nguon` values, so the curated anchors are merged in
    # the same way as the local path (deduped by normalized name).
    PLACES = finalize_catalogue(PLACES)


def _load_distance_metadata() -> dict:
    if os.getenv("APP_ENV", "local") != "local":
        database_url = os.getenv("URL_CSDL_POSTGRES")
        if not database_url:
            raise RuntimeError("URL_CSDL_POSTGRES is required outside local mode")
        with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=3) as connection:
            row = connection.execute(
                "SELECT count(*) AS count,max(ngay_cap_nhat) AS updated_at "
                "FROM bang_khoang_cach WHERE phuong_tien='driving'"
            ).fetchone()
        return {
            "loaded": bool(row["count"]), "updated_at": row["updated_at"],
            "profile": "driving", "place_count": len(PLACES),
        }
    path = DATA_DIR / "distance_matrix.json"
    if not path.exists():
        return {"loaded": False, "profile": None, "place_count": 0}
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    return {
        "loaded": bool(payload.get("durations_seconds")),
        "updated_at": metadata.get("generated_at"),
        "profile": metadata.get("profile"),
        "place_count": metadata.get("place_count", 0),
    }


DISTANCE_METADATA = _load_distance_metadata()
if not DISTANCE_METADATA["loaded"] and os.getenv("APP_ENV", "local") == "local":
    DISTANCE_METADATA = {
        "loaded": True,
        "updated_at": "local-demo",
        "profile": "demo_haversine",
        "place_count": len(PLACES),
    }
