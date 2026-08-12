"""Research-backed visit windows for major Hanoi stops.

Sources synthesized from traveler guides (Vietnam Wayfarer, VnExpress,
Nomado, YourVietnamTravel, etc.): morning-only mausoleum hours, cooler
outdoor windows, museum daytime blocks, and evening Old Quarter energy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisitGuidance:
    # Official / practical opening override when catalog hours are wrong.
    open_hour: int | None = None
    close_hour: int | None = None
    # Primary preferred visit window (local clock).
    preferred: tuple[int, int, int, int] = (8, 0, 17, 0)
    # Optional second cool/peak window (e.g. lakes at late afternoon).
    alt_preferred: tuple[int, int, int, int] | None = None
    duration_min: int | None = None
    tip: str = ""
    source: str = ""


# Keys are ascii-folded lowercase place names (same as planner._place_name_key).
VISIT_GUIDANCE_BY_NAME: dict[str, VisitGuidance] = {
    "lang chu tich ho chi minh": VisitGuidance(
        open_hour=7,
        close_hour=11,
        preferred=(7, 30, 10, 30),
        duration_min=60,
        tip="Nên đến sớm 7h30–8h để tránh đoàn đông; mặc đồ kín đáo. Thường đóng cửa sáng sớm khoảng 10h30–11h.",
        source="VnExpress / Vietnam Wayfarer",
    ),
    "van mieu quoc tu giam": VisitGuidance(
        open_hour=8,
        close_hour=17,
        preferred=(8, 0, 11, 0),
        alt_preferred=(14, 0, 16, 30),
        duration_min=75,
        tip="Ôn hòa nhất lúc mở cửa 8h hoặc sau 14h khi bớt đoàn tour; dành 60–90 phút.",
        source="YourVietnamTravel",
    ),
    "ho hoan kiem": VisitGuidance(
        open_hour=5,
        close_hour=23,
        preferred=(7, 0, 9, 30),
        alt_preferred=(16, 0, 19, 0),
        duration_min=60,
        tip="Sáng sớm thấy người tập dưỡng sinh; chiều tối 16h–19h đông vui, cuối tuần còn phố đi bộ.",
        source="Nomado / C-Vietnam Tours",
    ),
    "ho guom": VisitGuidance(
        open_hour=5,
        close_hour=23,
        preferred=(7, 0, 9, 30),
        alt_preferred=(16, 0, 19, 0),
        duration_min=60,
        tip="Sáng sớm yên tĩnh; chiều tối đẹp ánh đèn và không khí địa phương.",
        source="Nomado / C-Vietnam Tours",
    ),
    "duong ven ho tay": VisitGuidance(
        open_hour=5,
        close_hour=22,
        preferred=(6, 30, 9, 30),
        alt_preferred=(16, 30, 18, 30),
        duration_min=75,
        tip="Tránh nắng gắt 10h–15h; đẹp nhất sáng sớm hoặc gần hoàng hôn.",
        source="Nomado West Lake guide",
    ),
    "ho tay": VisitGuidance(
        open_hour=5,
        close_hour=22,
        preferred=(6, 30, 9, 30),
        alt_preferred=(16, 30, 18, 30),
        duration_min=75,
        tip="Đi bộ ven hồ hợp sáng sớm hoặc chiều muộn trước ăn tối.",
        source="Nomado West Lake guide",
    ),
    "chua tran quoc": VisitGuidance(
        open_hour=7,
        close_hour=18,
        preferred=(7, 30, 10, 0),
        alt_preferred=(15, 30, 17, 30),
        duration_min=50,
        tip="Sáng sớm hoặc chiều mát ít đông; kết hợp Hồ Tây.",
        source="Nomado West Lake guide",
    ),
    "pho co ha noi": VisitGuidance(
        open_hour=7,
        close_hour=23,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 20, 0),
        duration_min=90,
        tip="Sáng–trưa dễ đi bộ tham quan; chiều tối nhộn nhịp ăn uống và phố cổ.",
        source="Hanoi Old Quarter visitor guides",
    ),
    "cau long bien": VisitGuidance(
        open_hour=5,
        close_hour=22,
        preferred=(7, 0, 9, 30),
        alt_preferred=(16, 30, 18, 30),
        duration_min=45,
        tip="Hợp check-in sáng sớm hoặc chiều gió mát; tránh đứng lâu giữa trưa nắng.",
        source="local traveler guides",
    ),
    "bao tang phu nu viet nam": VisitGuidance(
        open_hour=8,
        close_hour=17,
        preferred=(9, 0, 15, 30),
        duration_min=75,
        tip="Đi trong khung giờ bảo tàng mở cửa ban ngày; khoảng 60–90 phút.",
        source="museum listings",
    ),
    "cho dem dong xuan": VisitGuidance(
        open_hour=18,
        close_hour=23,
        preferred=(19, 0, 21, 30),
        duration_min=75,
        tip="Sôi động sau 19h cuối tuần; nối từ Hồ Gươm / phố cổ.",
        source="Hanoi walking street guides",
    ),
    "pho ta hien": VisitGuidance(
        open_hour=17,
        close_hour=24,
        preferred=(19, 0, 22, 0),
        duration_min=60,
        tip="Không khí bar street rõ nhất sau 19h.",
        source="Old Quarter nightlife guides",
    ),
    "hoang thanh thang long": VisitGuidance(
        open_hour=8,
        close_hour=17,
        preferred=(9, 0, 11, 30),
        alt_preferred=(14, 0, 16, 30),
        duration_min=90,
        tip="Di tích rộng, nên đi bộ tham quan 60–90 phút; sáng sớm bớt đông.",
        source="UNESCO / VnExpress",
    ),
    "nha hat lon ha noi": VisitGuidance(
        open_hour=9,
        close_hour=21,
        preferred=(10, 0, 12, 0),
        alt_preferred=(18, 0, 20, 0),
        duration_min=45,
        tip="Giữa buổi sáng hoặc trước giờ diễn tối; khu vực quảng trường thoáng.",
        source="Hanoi opera house guides",
    ),
    "cong vien thong nhat": VisitGuidance(
        open_hour=6,
        close_hour=22,
        preferred=(7, 0, 10, 0),
        alt_preferred=(16, 0, 18, 30),
        duration_min=70,
        tip="Sáng sớm mát mẻ hoặc chiều muộn trước giờ ăn tối.",
        source="local park guides",
    ),
    "cafe dinh": VisitGuidance(
        open_hour=7,
        close_hour=22,
        preferred=(8, 0, 10, 30),
        alt_preferred=(14, 0, 17, 30),
        duration_min=45,
        tip="Cà phê trứng và không gian nhỏ; 30–60 phút là hợp lý.",
        source="Hanoi café guides",
    ),
    "serein cafe lounge": VisitGuidance(
        open_hour=8,
        close_hour=23,
        preferred=(9, 0, 11, 30),
        alt_preferred=(15, 0, 18, 30),
        duration_min=60,
        tip="View Tây Hồ đẹp nhất chiều muộn; kết hợp đi bộ ven hồ.",
        source="West Lake café guides",
    ),
    "pho bat dan": VisitGuidance(
        open_hour=6,
        close_hour=22,
        preferred=(7, 0, 10, 0),
        alt_preferred=(17, 0, 20, 0),
        duration_min=45,
        tip="Bán sáng và trưa; tránh giờ cao điểm 11h–13h.",
        source="Hanoi pho guides",
    ),
    "bun cha huong lien": VisitGuidance(
        open_hour=10,
        close_hour=21,
        preferred=(11, 30, 13, 30),
        alt_preferred=(17, 0, 20, 0),
        duration_min=50,
        tip="Đông nhất buổi trưa; 45–60 phút cho bữa bún chả.",
        source="VnExpress food guide",
    ),
    "bun cha dac kim": VisitGuidance(
        open_hour=8,
        close_hour=21,
        preferred=(11, 0, 13, 30),
        alt_preferred=(17, 0, 20, 0),
        duration_min=45,
        tip="Quán ăn ngon quanh phố cổ; 30–60 phút cho bữa.",
        source="Hanoi street food guides",
    ),
    "cha ca thang long": VisitGuidance(
        open_hour=10,
        close_hour=22,
        preferred=(11, 30, 14, 0),
        alt_preferred=(18, 0, 21, 0),
        duration_min=60,
        tip="Chả cá rán tự làm; trải nghiệm chính là tự nướng nên cần 45–75 phút.",
        source="Hanoi food guides",
    ),
    "hang dao": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 21, 0),
        duration_min=35,
        tip="Đi bộ ngắm tuyến phố và mua quà; sáng sớm dễ chụp ảnh.",
        source="Old Quarter walking guides",
    ),
    "hang gai": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 20, 0),
        duration_min=35,
        tip="Chuyên lụa và quà lưu niệm; dạo quanh 15–30 phút.",
        source="Old Quarter shopping guides",
    ),
    "hang bac": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 20, 0),
        duration_min=35,
        tip="Làng nghề bạc trong phố cổ; 15–30 phút.",
        source="Old Quarter walking guides",
    ),
    "hang ma": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 21, 0),
        duration_min=35,
        tip="Đồ trang trí lễ hội; rực rỡ nhất trước Tết.",
        source="Old Quarter themed-street guides",
    ),
    "hang duong": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 20, 0),
        duration_min=35,
        tip="Ô mai và kẹo truyền thống; nối tiếp phố Hàng Ngang.",
        source="Hanoi snacks guides",
    ),
    "hang ngang": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(16, 0, 21, 0),
        duration_min=35,
        tip="Phố lịch sử giữa lòng phố cổ; dừng chân 15–30 phút.",
        source="Hanoi history guides",
    ),
    "hang buom": VisitGuidance(
        open_hour=9,
        close_hour=23,
        preferred=(17, 0, 21, 0),
        duration_min=40,
        tip="Khu phố ẩm thực và bar về đêm; bắt đầu sau 17h.",
        source="Old Quarter nightlife guides",
    ),
    "hang dau": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(15, 0, 20, 0),
        duration_min=30,
        tip="Chuyên giày dép; dạo nhanh 15–30 phút.",
        source="Old Quarter shopping guides",
    ),
    "hang khay": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(15, 0, 20, 0),
        duration_min=30,
        tip="Sát Hồ Gươm, nối cho các điểm tham quan ban ngày.",
        source="Hanoi map guides",
    ),
    "hang trong": VisitGuidance(
        open_hour=9,
        close_hour=22,
        preferred=(9, 0, 12, 0),
        alt_preferred=(15, 0, 20, 0),
        duration_min=35,
        tip="Tranh dân gian và đồ thủ công; dừng chân 15–30 phút.",
        source="Hanoi craft guides",
    ),
}

# Extra id aliases when name keys differ between curated/OSM copies.
VISIT_GUIDANCE_BY_ID: dict[str, VisitGuidance] = {
    "curated-lang-bac": VISIT_GUIDANCE_BY_NAME["lang chu tich ho chi minh"],
    "curated-ho-guom": VISIT_GUIDANCE_BY_NAME["ho guom"],
    "curated-ho-tay": VISIT_GUIDANCE_BY_NAME["ho tay"],
    "curated-pho-co-ha-noi": VISIT_GUIDANCE_BY_NAME["pho co ha noi"],
    "curated-cho-dem-dong-xuan": VISIT_GUIDANCE_BY_NAME["cho dem dong xuan"],
    "curated-pho-ta-hien": VISIT_GUIDANCE_BY_NAME["pho ta hien"],
    "van-mieu": VISIT_GUIDANCE_BY_NAME["van mieu quoc tu giam"],
    "ho-guom": VISIT_GUIDANCE_BY_NAME["ho guom"],
    "ho-tay": VISIT_GUIDANCE_BY_NAME["ho tay"],
    "chua-tran-quoc": VISIT_GUIDANCE_BY_NAME["chua tran quoc"],
    "long-bien": VISIT_GUIDANCE_BY_NAME["cau long bien"],
    "bao-tang-phu-nu": VISIT_GUIDANCE_BY_NAME["bao tang phu nu viet nam"],
    "curated-cafe-dinh": VISIT_GUIDANCE_BY_NAME["cafe dinh"],
    "curated-pho-bat-dan": VISIT_GUIDANCE_BY_NAME["pho bat dan"],
    "curated-bun-cha-huong-lien": VISIT_GUIDANCE_BY_NAME["bun cha huong lien"],
    "curated-bun-cha-dac-kim": VISIT_GUIDANCE_BY_NAME["bun cha dac kim"],
    "curated-cha-ca-thang-long": VISIT_GUIDANCE_BY_NAME["cha ca thang long"],
    "curated-hang-dao": VISIT_GUIDANCE_BY_NAME["hang dao"],
    "curated-hang-gai": VISIT_GUIDANCE_BY_NAME["hang gai"],
    "curated-hang-bac": VISIT_GUIDANCE_BY_NAME["hang bac"],
    "curated-hang-ma": VISIT_GUIDANCE_BY_NAME["hang ma"],
    "curated-hang-duong": VISIT_GUIDANCE_BY_NAME["hang duong"],
    "curated-hang-ngang": VISIT_GUIDANCE_BY_NAME["hang ngang"],
    "curated-hang-buom": VISIT_GUIDANCE_BY_NAME["hang buom"],
    "curated-hang-dau": VISIT_GUIDANCE_BY_NAME["hang dau"],
    "curated-hang-khay": VISIT_GUIDANCE_BY_NAME["hang khay"],
    "curated-hang-trong": VISIT_GUIDANCE_BY_NAME["hang trong"],
    "curated-hoang-thanh-thang-long": VISIT_GUIDANCE_BY_NAME["hoang thanh thang long"],
    "curated-nha-hat-lon": VISIT_GUIDANCE_BY_NAME["nha hat lon ha noi"],
    "cong-vien-thong-nhat": VISIT_GUIDANCE_BY_NAME["cong vien thong nhat"],
    "serein-cafe": VISIT_GUIDANCE_BY_NAME["serein cafe lounge"],
}

DEFAULT_KIND_GUIDANCE: dict[str, VisitGuidance] = {
    "dia_danh": VisitGuidance(duration_min=45, source="thời lượng mặc định cho điểm tham quan ngoài trời (khoảng 45 phút)"),
    "bao_tang": VisitGuidance(duration_min=75, source="mặc định bảo tàng (60–90 phút)"),
    "cong_vien": VisitGuidance(duration_min=70, source="mặc định công viên (60–90 phút)"),
    "cafe": VisitGuidance(duration_min=45, source="mặc định quán cà phê (30–60 phút)"),
    "quan_an": VisitGuidance(duration_min=45, source="mặc định quán ăn nhanh (30–45 phút)"),
    "nha_hang": VisitGuidance(duration_min=60, source="mặc định nhà hàng (45–75 phút)"),
    "cho": VisitGuidance(duration_min=60, source="mặc định chợ (45–75 phút)"),
}


def guidance_for(place_id: str, name_key: str) -> VisitGuidance | None:
    return (
        VISIT_GUIDANCE_BY_ID.get(place_id)
        or VISIT_GUIDANCE_BY_NAME.get(name_key)
        or _kind_guidance_from_id(place_id)
    )


def duration_guidance_for(place_id: str, name_key: str, kind: str | None = None) -> VisitGuidance | None:
    """Guidance used only for the visit-duration basis (never for scheduling)."""
    direct = VISIT_GUIDANCE_BY_ID.get(place_id) or VISIT_GUIDANCE_BY_NAME.get(name_key)
    if direct:
        return direct
    if kind and kind in DEFAULT_KIND_GUIDANCE:
        return DEFAULT_KIND_GUIDANCE[kind]
    return _kind_guidance_from_id(place_id)


def _kind_guidance_from_id(place_id: str) -> VisitGuidance | None:
    if not place_id or not place_id.startswith("osm-"):
        return None
    mapping = {
        "museum": "bao_tang",
        "viewpoint": "dia_danh",
        "park": "cong_vien",
        "cafe": "cafe",
        "restaurant": "nha_hang",
        "fast_food": "quan_an",
        "marketplace": "cho",
    }
    for prefix, kind in mapping.items():
        if prefix in place_id:
            return DEFAULT_KIND_GUIDANCE[kind]
    return None
