import json
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


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


PLACE_IMAGE_URLS: dict[str, str] = {
    "ho-guom": "https://commons.wikimedia.org/wiki/Special:FilePath/Hoan_Kiem.jpg?width=800",
    "van-mieu": "https://commons.wikimedia.org/wiki/Special:FilePath/V%C4%83n_Mi%E1%BA%BFu_Street%2C_Hanoi.jpg?width=800",
    "chua-tran-quoc": "https://commons.wikimedia.org/wiki/Special:FilePath/Ch%C3%B9a_Tr%E1%BA%A5n_Qu%E1%BB%91c%2C_H%C3%A0_N%E1%BB%99i.jpg?width=800",
    "long-bien": "https://commons.wikimedia.org/wiki/Special:FilePath/Long_bien_bridge.jpg?width=800",
    "bao-tang-phu-nu": "https://commons.wikimedia.org/wiki/Special:FilePath/Vietnamese_Women%27s_Museum_Building.JPG?width=800",
    "curated-ho-guom": "https://commons.wikimedia.org/wiki/Special:FilePath/Hoan_Kiem.jpg?width=800",
    "curated-ho-tay": "https://commons.wikimedia.org/wiki/Special:FilePath/H%E1%BB%93_T%C3%A2y_ho%C3%A0ng_h%C3%B4n_-_NKS.jpg?width=800",
    "curated-lang-bac": "https://commons.wikimedia.org/wiki/Special:FilePath/L%C4%83ng_B%C3%A1c_-_NKS.jpg?width=800",
    "curated-pho-co-ha-noi": "https://commons.wikimedia.org/wiki/Special:FilePath/T%E1%BA%A1_Hi%E1%BB%87n_Street%2C_Hanoi%2C_Vietnam_14.jpg?width=800",
    "curated-cho-dem-dong-xuan": "https://commons.wikimedia.org/wiki/Special:FilePath/Ch%E1%BB%A3_%C4%90%E1%BB%93ng_Xu%C3%A2n_-_NKS.jpg?width=800",
    "curated-pho-ta-hien": "https://commons.wikimedia.org/wiki/Special:FilePath/T%E1%BA%A1_Hi%E1%BB%87n_Street%2C_Hanoi%2C_Vietnam_14.jpg?width=800",
    "curated-hang-dao": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-gai": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-bac": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-ma": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-duong": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-ngang": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-buom": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-dau": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-khay": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hang-trong": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_shophouse_2.jpg?width=800",
    "curated-hoang-thanh-thang-long": "https://commons.wikimedia.org/wiki/Special:FilePath/Central_Sector_of_the_Imperial_Citadel_of_Thang_Long_-_Hanoi.jpg?width=800",
    "curated-nha-hat-lon": "https://commons.wikimedia.org/wiki/Special:FilePath/Hanoi_Opera_House_1.jpg?width=800",
}

PLACE_IMAGE_CREDITS: dict[str, str] = {
    "ho-guom": "Wikimedia Commons (Hoan_Kiem.jpg)",
    "van-mieu": "Wikimedia Commons (Văn Miếu Street, Hanoi)",
    "chua-tran-quoc": "Wikimedia Commons (Chùa Trấn Quốc, Hà Nội)",
    "long-bien": "Wikimedia Commons (Long_bien_bridge.jpg)",
    "bao-tang-phu-nu": "Wikimedia Commons (Vietnamese Women's Museum Building)",
    "curated-ho-guom": "Wikimedia Commons (Hoan_Kiem.jpg)",
    "curated-ho-tay": "Wikimedia Commons (Hồ Tây hoàng hôn – NKS)",
    "curated-lang-bac": "Wikimedia Commons (Lăng Bác – NKS)",
    "curated-pho-co-ha-noi": "Wikimedia Commons (Tạ Hiện Street, Hanoi)",
    "curated-cho-dem-dong-xuan": "Wikimedia Commons (Chợ Đồng Xuân – NKS)",
    "curated-pho-ta-hien": "Wikimedia Commons (Tạ Hiện Street, Hanoi)",
    "curated-hoang-thanh-thang-long": "Wikimedia Commons (Imperial Citadel of Thang Long)",
    "curated-nha-hat-lon": "Wikimedia Commons (Hanoi Opera House 1)",
}


def image_for(place: "Place") -> tuple[str | None, str | None]:
    if place.image_url:
        return place.image_url, place.image_credit
    url = PLACE_IMAGE_URLS.get(place.id)
    return url, PLACE_IMAGE_CREDITS.get(place.id)


PLACES = [
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
if IMPORTED_PLACES:
    PLACES = IMPORTED_PLACES


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
        17,
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

_existing_place_ids = {place.id for place in PLACES}
PLACES = [*PLACES, *(place for place in CURATED_HANOI_ANCHORS if place.id not in _existing_place_ids)]


def _load_postgres_places() -> tuple[list[Place], dict]:
    database_url = os.getenv("URL_CSDL_POSTGRES")
    if not database_url:
        raise RuntimeError("URL_CSDL_POSTGRES is required outside local mode")
    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=3) as connection:
        rows = connection.execute(
            "SELECT ten,loai,khu_vuc,gia_trung_binh,tags,gio_mo_cua,toa_do,"
            "nguon,nguon_url,ma_nguon,thoi_luong_phut,hinh_anh FROM dia_diem "
            "WHERE trang_thai='active' AND ma_nguon IS NOT NULL"
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
            image_url=row["hinh_anh"],
        )
        for row in rows
    ]
    return places, {"provider": "PostgreSQL catalogue", "count": len(places)}


if os.getenv("APP_ENV", "local") != "local":
    PLACES, PLACE_METADATA = _load_postgres_places()


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
