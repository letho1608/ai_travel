"""Research-backed visit windows for major Hanoi stops.

Sources synthesized from traveler guides (Vietnam Wayfarer, VnExpress,
Nomado, YourVietnamTravel, etc.): morning-only mausoleum hours, cooler
outdoor windows, museum daytime blocks, and evening Old Quarter energy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.text_utils import ascii_fold


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


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
GENERATED_GUIDANCE_PATH = DATA_DIR / "visit_guidance.json"


def _name_key(value: str) -> str:
    return " ".join(ascii_fold(value).split())


def _clock_window(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None
    try:
        start_h, start_m, end_h, end_m = (int(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not (0 <= start_h <= 23 and 0 <= end_h <= 24):
        return None
    if not (0 <= start_m <= 59 and 0 <= end_m <= 59):
        return None
    if start_h * 60 + start_m >= end_h * 60 + end_m:
        return None
    return start_h, start_m, end_h, end_m


def _guidance_from_item(item: object) -> VisitGuidance | None:
    if not isinstance(item, dict):
        return None
    preferred = _clock_window(item.get("preferred"))
    if preferred is None:
        return None
    alt_preferred = _clock_window(item.get("alt_preferred"))

    def optional_int(key: str, lower: int, upper: int) -> int | None:
        raw = item.get(key)
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        if lower <= value <= upper:
            return value
        return None

    open_hour = optional_int("open_hour", 0, 23)
    close_hour = optional_int("close_hour", 1, 24)
    if open_hour is not None and close_hour is not None and open_hour >= close_hour:
        return None
    duration_min = optional_int("duration_min", 20, 240)
    tip = item.get("tip")
    source = item.get("source")
    return VisitGuidance(
        open_hour=open_hour,
        close_hour=close_hour,
        preferred=preferred,
        alt_preferred=alt_preferred,
        duration_min=duration_min,
        tip=tip.strip()[:300] if isinstance(tip, str) else "",
        source=source.strip()[:160] if isinstance(source, str) else "",
    )


def _load_generated_guidance() -> tuple[dict[str, VisitGuidance], dict[str, VisitGuidance]]:
    if not GENERATED_GUIDANCE_PATH.exists():
        return {}, {}
    try:
        payload = json.loads(GENERATED_GUIDANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    by_id: dict[str, VisitGuidance] = {}
    by_name: dict[str, VisitGuidance] = {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}, {}
    for item in items:
        guidance = _guidance_from_item(item)
        if not guidance or not isinstance(item, dict):
            continue
        place_id = item.get("id")
        name_key = item.get("name_key")
        name = item.get("name")
        if isinstance(place_id, str) and place_id.strip():
            by_id[place_id.strip()] = guidance
        normalized_name = ""
        if isinstance(name_key, str):
            normalized_name = _name_key(name_key)
        elif isinstance(name, str):
            normalized_name = _name_key(name)
        if normalized_name:
            by_name[normalized_name] = guidance
    return by_id, by_name


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
    # Đà Nẵng & Hội An
    "cau rong": VisitGuidance(
        open_hour=6, close_hour=23,
        preferred=(17, 30, 21, 30),
        duration_min=45,
        tip="Buổi tối lung linh ánh đèn; cuối tuần 21h00 có phun lửa và nước.",
        source="Danang Tourism Portal",
    ),
    "ngu hanh son": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(7, 30, 10, 30),
        alt_preferred=(14, 30, 16, 30),
        duration_min=90,
        tip="Nên đi sáng sớm để leo bậc đá đỡ nóng và khám phá động Huyền Không.",
        source="Vietnam Tourism Guide",
    ),
    "bai bien my khe": VisitGuidance(
        open_hour=5, close_hour=22,
        preferred=(5, 30, 8, 30),
        alt_preferred=(16, 0, 18, 30),
        duration_min=90,
        tip="Tắm biển và ngắm bình minh sáng sớm hoặc chiều lộng gió mát.",
        source="Danang Beach Guide",
    ),
    "chua cau hoi an": VisitGuidance(
        open_hour=7, close_hour=22,
        preferred=(8, 0, 10, 0),
        alt_preferred=(17, 0, 21, 0),
        duration_min=45,
        tip="Biểu tượng Hội An, chụp ảnh đẹp nhất sáng sớm vắng người hoặc tối lung linh đèn lồng.",
        source="Hoi An Heritage Guide",
    ),
    "pho co hoi an": VisitGuidance(
        open_hour=7, close_hour=23,
        preferred=(16, 0, 21, 30),
        duration_min=120,
        tip="Phố cổ đẹp nhất từ lúc hoàng hôn và thắp đèn lồng, thả hoa đăng trên sông Hoài.",
        source="Hoi An Travel Guide",
    ),
    # Huế
    "dai noi hue": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(7, 30, 10, 30),
        alt_preferred=(14, 0, 16, 30),
        duration_min=150,
        tip="Hoàng thành rất rộng, đi sáng sớm mát mẻ hoặc thuê xe điện/áo ngũ thân chụp ảnh.",
        source="Hue Monument Conservation Centre",
    ),
    "chua thien mu": VisitGuidance(
        open_hour=7, close_hour=18,
        preferred=(7, 30, 9, 30),
        alt_preferred=(16, 0, 17, 30),
        duration_min=60,
        tip="Ngắm hoàng hôn bên bờ sông Hương từ tháp Phước Duyên rất thơ mộng.",
        source="Hue Tourism Guide",
    ),
    # Đà Lạt
    "thung lung tinh yeu": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(8, 0, 11, 0),
        alt_preferred=(14, 0, 16, 30),
        duration_min=120,
        tip="Khuôn viên rộng với đồi thông và vườn hoa; đi buổi sáng mát mẻ.",
        source="Dalat Tourist",
    ),
    "dinh langbiang": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(8, 0, 11, 30),
        duration_min=150,
        tip="Đi xe jeep lên đỉnh ngắm toàn cảnh suối Vàng suối Bạc lúc trời trong.",
        source="Lam Dong Tourism",
    ),
    "langbiang": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(8, 0, 11, 30),
        duration_min=150,
        tip="Đi xe jeep lên đỉnh ngắm toàn cảnh suối Vàng suối Bạc lúc trời trong.",
        source="Lam Dong Tourism",
    ),
    "ho xuan huong": VisitGuidance(
        open_hour=5, close_hour=23,
        preferred=(6, 0, 8, 30),
        alt_preferred=(16, 30, 19, 0),
        duration_min=60,
        tip="Dạo bộ ngắm sương sớm hoặc đạp vịt, thưởng thức sữa đậu nành nóng chiều tối.",
        source="Dalat City Guide",
    ),
    # Ninh Bình
    "quan the danh thang trang an": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(7, 30, 10, 30),
        alt_preferred=(13, 30, 16, 30),
        duration_min=180,
        tip="Tour chèo thuyền xuyên hang động 2.5 - 3 tiếng; nên đi sớm tránh nắng gắt trên sông.",
        source="Trang An Eco-tourism Complex",
    ),
    "trang an": VisitGuidance(
        open_hour=7, close_hour=17,
        preferred=(7, 30, 10, 30),
        alt_preferred=(13, 30, 16, 30),
        duration_min=180,
        tip="Tour chèo thuyền xuyên hang động 2.5 - 3 tiếng; nên đi sớm tránh nắng gắt trên sông.",
        source="Trang An Eco-tourism Complex",
    ),
    "chua bai dinh": VisitGuidance(
        open_hour=7, close_hour=21,
        preferred=(8, 0, 11, 0),
        alt_preferred=(15, 0, 18, 0),
        duration_min=150,
        tip="Quần thể chùa rất lớn, nên đi xe điện kết hợp viếng bảo tháp và hành lang La Hán.",
        source="Ninh Binh Tourism",
    ),
    "hang mua": VisitGuidance(
        open_hour=6, close_hour=18,
        preferred=(6, 30, 8, 30),
        alt_preferred=(16, 0, 18, 0),
        duration_min=90,
        tip="Leo 500 bậc thang đón bình minh hoặc săn hoàng hôn nhìn toàn cảnh Tam Cốc ngoạn mục.",
        source="Ninh Binh Traveler Guide",
    ),
    # Cần Thơ
    "cho noi cai rang": VisitGuidance(
        open_hour=5, close_hour=10,
        preferred=(5, 30, 8, 0),
        duration_min=90,
        tip="Bắt buộc đi lúc 5h30–7h30 sáng khi chợ ghe tấp nập giao thương và ăn hủ tiếu ghe.",
        source="Mekong Delta River Tour Guide",
    ),
    "ben ninh kieu": VisitGuidance(
        open_hour=5, close_hour=23,
        preferred=(17, 30, 21, 30),
        duration_min=60,
        tip="Tản bộ cầu đi bộ Tình Yêu và ngắm sông Hậu lộng gió buổi tối.",
        source="Can Tho Tourism",
    ),
    # Hạ Long
    "vinh ha long": VisitGuidance(
        open_hour=7, close_hour=18,
        preferred=(8, 0, 12, 0),
        alt_preferred=(13, 0, 16, 30),
        duration_min=240,
        tip="Đi tàu tham quan vịnh, chèo kayak khám phá hang động và ngắm đảo đá vôi kỳ vĩ.",
        source="Halong Bay Management Board",
    ),
    # Sa Pa
    "dinh fansipan legend": VisitGuidance(
        open_hour=7, close_hour=18,
        preferred=(8, 30, 11, 30),
        alt_preferred=(13, 30, 16, 0),
        duration_min=180,
        tip="Đi cáp treo lên đỉnh Fansipan khi trời quang mây; mang áo ấm vì nhiệt độ trên đỉnh thấp.",
        source="Sun World Fansipan Legend",
    ),
    "ban cat cat": VisitGuidance(
        open_hour=6, close_hour=18,
        preferred=(8, 0, 11, 0),
        alt_preferred=(14, 0, 16, 30),
        duration_min=120,
        tip="Đi bộ ngắm cọn nước, thác Tiên Sa và trải nghiệm văn hóa bản địa người H'Mông.",
        source="Sapa Tourism",
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
}

GENERATED_VISIT_GUIDANCE_BY_ID, GENERATED_VISIT_GUIDANCE_BY_NAME = _load_generated_guidance()


def guidance_for(place_id: str, name_key: str) -> VisitGuidance | None:
    return (
        GENERATED_VISIT_GUIDANCE_BY_ID.get(place_id)
        or VISIT_GUIDANCE_BY_ID.get(place_id)
        or GENERATED_VISIT_GUIDANCE_BY_NAME.get(name_key)
        or VISIT_GUIDANCE_BY_NAME.get(name_key)
    )
