import hashlib
import re
import unicodedata
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings
from app.data import DISTANCE_METADATA, PLACES, Place
from app.pipeline.routing import (
    haversine_km,
    is_routable,
    nearest_neighbor,
    travel_minutes,
    two_opt,
)
from app.schemas import PlanRequest
from app.services.ai import ai_adapter
from app.services.osm_verify import verify_place_name
from app.services.weather import WeatherUnavailable, get_daily_weather

LIMITS = {
    "vai_gio": (4, 300, 1),
    "nua_ngay": (5, 600, 1),
    "ca_ngay": (7, 900, 1),
    "nhieu_ngay": (10, 900, 2),
}

AI_FALLBACK_NOTE = {
    "vi": "AI táº¡m thá»i khÃ´ng kháº£ dá»¥ng; lá»‹ch trÃ¬nh Ä‘ang dÃ¹ng bá»™ xáº¿p lá»‹ch an toÃ n tá»« dá»¯ liá»‡u Ä‘Ã£ kiá»ƒm chá»©ng.",
    "en": "AI is temporarily unavailable; this itinerary uses the safe deterministic planner with verified data.",
}

COPY = {
    "vi": ("Chưa tải dự báo trực tuyến", "Dự báo có thể thay đổi", "Open-Meteo tạm thời không khả dụng", "Trải nghiệm {place} tại {area}.", "Kiểm tra giờ mở cửa trước khi đi.", "Ngày {day}", "Một lịch trình tối ưu cho {people} người.", "Chi phí ước tính, có thể chênh lệch", "Mang theo nước và kiểm tra thời tiết"),
    "en": ("Live forecast not loaded", "Forecasts may change", "Open-Meteo is temporarily unavailable", "Experience {place} in {area}.", "Check opening hours before visiting.", "Day {day}", "An optimized itinerary for {people} people.", "Estimated costs may vary", "Bring water and check the weather"),
    "ar": ("لم يتم تحميل التوقعات المباشرة", "قد تتغير التوقعات", "Open-Meteo غير متاح مؤقتًا", "استمتع بتجربة {place} في {area}.", "تحقق من ساعات العمل قبل الزيارة.", "اليوم {day}", "برنامج رحلة محسّن لـ {people} أشخاص.", "قد تختلف التكاليف التقديرية", "أحضر الماء وتحقق من الطقس"),
    "bg": ("Прогнозата на живо не е заредена", "Прогнозата може да се промени", "Open-Meteo временно не е достъпен", "Посетете {place} в {area}.", "Проверете работното време преди посещение.", "Ден {day}", "Оптимизиран маршрут за {people} души.", "Прогнозните разходи може да варират", "Носете вода и проверете времето"),
    "de": ("Live-Vorhersage nicht geladen", "Vorhersagen können sich ändern", "Open-Meteo ist vorübergehend nicht verfügbar", "Erleben Sie {place} in {area}.", "Prüfen Sie vor dem Besuch die Öffnungszeiten.", "Tag {day}", "Eine optimierte Reiseroute für {people} Personen.", "Geschätzte Kosten können abweichen", "Nehmen Sie Wasser mit und prüfen Sie das Wetter"),
    "es": ("Pronóstico en vivo no cargado", "El pronóstico puede cambiar", "Open-Meteo no está disponible temporalmente", "Disfruta de {place} en {area}.", "Consulta el horario antes de ir.", "Día {day}", "Un itinerario optimizado para {people} personas.", "Los costes estimados pueden variar", "Lleva agua y consulta el tiempo"),
    "fr": ("Prévisions en direct non chargées", "Les prévisions peuvent changer", "Open-Meteo est temporairement indisponible", "Découvrez {place} à {area}.", "Vérifiez les horaires avant la visite.", "Jour {day}", "Un itinéraire optimisé pour {people} personnes.", "Les coûts estimés peuvent varier", "Emportez de l’eau et vérifiez la météo"),
    "he": ("התחזית החיה לא נטענה", "התחזית עשויה להשתנות", "Open-Meteo אינו זמין זמנית", "חוו את {place} ב-{area}.", "בדקו את שעות הפתיחה לפני הביקור.", "יום {day}", "מסלול מיטבי עבור {people} אנשים.", "העלויות המשוערות עשויות להשתנות", "הביאו מים ובדקו את מזג האוויר"),
    "hi": ("लाइव मौसम पूर्वानुमान लोड नहीं हुआ", "पूर्वानुमान बदल सकता है", "Open-Meteo अस्थायी रूप से उपलब्ध नहीं है", "{area} में {place} का अनुभव करें।", "जाने से पहले खुलने का समय जाँचें।", "दिन {day}", "{people} लोगों के लिए अनुकूलित यात्रा कार्यक्रम।", "अनुमानित लागत बदल सकती है", "पानी साथ रखें और मौसम जाँचें"),
    "it": ("Previsioni in tempo reale non caricate", "Le previsioni possono cambiare", "Open-Meteo è temporaneamente non disponibile", "Scopri {place} a {area}.", "Controlla gli orari prima della visita.", "Giorno {day}", "Un itinerario ottimizzato per {people} persone.", "I costi stimati possono variare", "Porta dell’acqua e controlla il meteo"),
    "ja": ("ライブ予報は読み込まれていません", "予報は変わる場合があります", "Open-Meteoは一時的に利用できません", "{area}の{place}を体験します。", "訪問前に営業時間を確認してください。", "{day}日目", "{people}人向けに最適化された旅程です。", "推定費用は変動する場合があります", "水を持参し天気を確認してください"),
    "nl": ("Liveverwachting niet geladen", "De verwachting kan veranderen", "Open-Meteo is tijdelijk niet beschikbaar", "Beleef {place} in {area}.", "Controleer voor uw bezoek de openingstijden.", "Dag {day}", "Een geoptimaliseerde route voor {people} personen.", "Geschatte kosten kunnen variëren", "Neem water mee en controleer het weer"),
    "pl": ("Prognoza na żywo nie została wczytana", "Prognoza może się zmienić", "Open-Meteo jest tymczasowo niedostępne", "Odwiedź {place} w {area}.", "Sprawdź godziny otwarcia przed wizytą.", "Dzień {day}", "Zoptymalizowany plan dla {people} osób.", "Szacowane koszty mogą się różnić", "Zabierz wodę i sprawdź pogodę"),
    "pt": ("Previsão em direto não carregada", "A previsão pode mudar", "Open-Meteo está temporariamente indisponível", "Descubra {place} em {area}.", "Confirme o horário antes da visita.", "Dia {day}", "Um itinerário otimizado para {people} pessoas.", "Os custos estimados podem variar", "Leve água e consulte o tempo"),
    "ru": ("Актуальный прогноз не загружен", "Прогноз может измениться", "Open-Meteo временно недоступен", "Посетите {place} в {area}.", "Проверьте часы работы перед посещением.", "День {day}", "Оптимизированный маршрут для {people} человек.", "Ориентировочные расходы могут измениться", "Возьмите воду и проверьте погоду"),
    "tr": ("Canlı hava tahmini yüklenmedi", "Tahmin değişebilir", "Open-Meteo geçici olarak kullanılamıyor", "{area} bölgesindeki {place} deneyimini yaşayın.", "Gitmeden önce çalışma saatlerini kontrol edin.", "Gün {day}", "{people} kişi için optimize edilmiş gezi planı.", "Tahmini maliyetler değişebilir", "Yanınıza su alın ve hava durumunu kontrol edin"),
    "zh": ("尚未加载实时天气预报", "天气预报可能会变化", "Open-Meteo暂时不可用", "体验{area}的{place}。", "出发前请查看开放时间。", "第{day}天", "为{people}人优化的行程。", "预估费用可能有所变化", "请携带饮用水并查看天气"),
    "ko": ("실시간 예보를 불러오지 않았습니다", "예보는 변경될 수 있습니다", "Open-Meteo를 일시적으로 사용할 수 없습니다", "{area}의 {place}을(를) 경험해 보세요.", "방문 전에 운영 시간을 확인하세요.", "{day}일차", "{people}명을 위한 최적화된 일정입니다.", "예상 비용은 달라질 수 있습니다", "물을 챙기고 날씨를 확인하세요"),
    "th": ("ยังไม่ได้โหลดพยากรณ์อากาศแบบสด", "พยากรณ์อากาศอาจเปลี่ยนแปลง", "Open-Meteo ไม่พร้อมใช้งานชั่วคราว", "สัมผัสประสบการณ์ {place} ที่ {area}", "ตรวจสอบเวลาเปิดก่อนเดินทาง", "วันที่ {day}", "แผนการเดินทางที่เหมาะสมสำหรับ {people} คน", "ค่าใช้จ่ายโดยประมาณอาจเปลี่ยนแปลง", "พกน้ำและตรวจสอบสภาพอากาศ"),
}


class PipelineUnavailable(RuntimeError):
    pass


INTENT_PROFILES = {
    "hanoi_highlights": {
        "terms": {"ha_noi", "hanoi", "du_lich", "tham_quan", "noi_tieng", "lan_dau", "classic", "pho_co"},
        "kinds": {"dia_danh"},
        "tags": {"hanoi_icon", "ho_guom", "ho_tay", "lang_bac", "pho_co", "van_hoa", "lich_su"},
    },
    "coffee": {
        "terms": {"cafe", "coffee", "ca_phe", "caphe"},
        "kinds": {"cafe"},
        "tags": {"cafe", "coffee", "coffee_shop", "chill", "view_dep"},
    },
    "food": {
        "terms": {"an", "an_ngon", "am_thuc", "food", "restaurant", "quan_an", "nha_hang"},
        "kinds": {"nha_hang", "quan_an"},
        "tags": {"am_thuc", "an_vat", "vietnamese", "local", "ban_chay", "binh_dan"},
    },
    "culture": {
        "terms": {"van_hoa", "culture", "museum", "bao_tang", "di_tich", "lich_su"},
        "kinds": {"bao_tang", "dia_danh"},
        "tags": {"museum", "van_hoa", "heritage", "history", "checkin"},
    },
    "night": {
        "terms": {"toi", "buoi_toi", "dem", "cho_dem", "night", "evening", "nightlife"},
        "kinds": {"dia_danh", "cho", "cafe", "nha_hang", "quan_an"},
        "tags": {"nightlife", "cho_dem", "night_market", "pho_co", "am_thuc", "view_dep"},
    },
    "walk": {
        "terms": {"di_bo", "walk", "walking", "chill", "ngoai_troi", "park"},
        "kinds": {"cong_vien", "dia_danh"},
        "tags": {"ngoai_troi", "chill", "view_dep", "di_bo"},
    },
}

HANOI_HIGHLIGHT_IDS = (
    "curated-ho-guom",
    "curated-lang-bac",
    "curated-ho-tay",
    "curated-pho-co-ha-noi",
)
HANOI_NIGHT_IDS = ("curated-cho-dem-dong-xuan", "curated-pho-ta-hien")
NON_TRAVEL_NAME_HINTS = {
    "sàn gỗ",
    "nội thất",
    "vật liệu",
    "điện máy",
    "điện lạnh",
    "sửa chữa",
    "phụ tùng",
    "gara",
    "garage",
    "bất động sản",
    "văn phòng",
}
OLD_QUARTER_TERMS = {
    "pho_co",
    "old_quarter",
    "hang_pho",
    "hang_dao",
    "hang_gai",
    "hang_bac",
    "hang_ma",
    "hang_duong",
    "hang_ngang",
    "hang_buom",
    "hang_dau",
    "hang_khay",
    "hang_trong",
}


def _ascii_fold(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def relevant_tags(context: str) -> set[str]:
    normalized = _ascii_fold(context).replace(" ", "_")
    plain = _ascii_fold(context)
    words = plain.split()
    phrases = {
        "_".join(words[index : index + size])
        for size in (2, 3)
        for index in range(0, max(len(words) - size + 1, 0))
    }
    return set(re.findall(r"[a-zA-Z_]+", normalized)) | set(words) | phrases


def _request_seed(request: PlanRequest) -> int:
    raw = "|".join(
        [
            request.context,
            request.thoi_luong,
            str(request.so_nguoi),
            str(request.ngan_sach),
            request.ma_phien or "",
            request.nonce or "",
        ]
    )
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], 16)


def _place_seed(place: Place, seed: int) -> int:
    raw = f"{seed}|{place.id}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


def _intent_profiles(tags: set[str]) -> list[dict[str, set[str]]]:
    return [
        profile
        for profile in INTENT_PROFILES.values()
        if tags.intersection(profile["terms"])
    ]


def _intent_score(place: Place, profiles: list[dict[str, set[str]]]) -> int:
    if not profiles:
        return 0
    score = 0
    place_tags = set(place.tags)
    for profile in profiles:
        if place.kind in profile["kinds"]:
            score += 3
        score += len(place_tags.intersection(profile["tags"]))
    return score


def _highlight_places(request: PlanRequest, excluded: set[str]) -> list[Place]:
    tags = relevant_tags(request.context)
    wants_hanoi_highlights = bool(
        tags.intersection(INTENT_PROFILES["hanoi_highlights"]["terms"])
        or tags.intersection({"ho_guom", "ho_tay", "lang_bac", "ho_chi_minh", "ba_dinh", "pho_co"})
    )
    if not wants_hanoi_highlights:
        return []
    by_id = {place.id: place for place in PLACES}
    place_ids = [
        *HANOI_HIGHLIGHT_IDS,
        *(HANOI_NIGHT_IDS if tags.intersection(INTENT_PROFILES["night"]["terms"]) else ()),
    ]
    return [
        place
        for place_id in place_ids
        if (place := by_id.get(place_id))
        and place.id not in excluded
        and place.cost <= request.ngan_sach
        and is_routable(place)
    ]


def _wants_night(request: PlanRequest) -> bool:
    return bool(relevant_tags(request.context).intersection(INTENT_PROFILES["night"]["terms"]))


def _looks_like_non_travel_business(place: Place) -> bool:
    return any(hint in place.name.casefold() for hint in NON_TRAVEL_NAME_HINTS)


def _wants_old_quarter(request: PlanRequest) -> bool:
    tags = relevant_tags(request.context)
    return bool(
        tags.intersection(OLD_QUARTER_TERMS)
        or tags.intersection(INTENT_PROFILES["hanoi_highlights"]["terms"])
        or _wants_night(request)
    )


def choose_candidates(request: PlanRequest, excluded: set[str] | None = None) -> list[Place]:
    excluded = excluded or set()
    tags = relevant_tags(request.context)
    profiles = _intent_profiles(tags)
    wants_old_quarter = _wants_old_quarter(request)
    wants_night = _wants_night(request)
    seed = _request_seed(request)
    candidates = [
        p for p in PLACES
        if p.id not in excluded
        and p.cost <= request.ngan_sach
        and is_routable(p)
        and not _looks_like_non_travel_business(p)
        and not (
            p.source == "curated"
            and {"pho_co", "old_quarter", "hang_pho"}.intersection(p.tags)
            and not wants_old_quarter
        )
        and not (
            request.thoi_luong in {"vai_gio", "nua_ngay"}
            and not wants_night
            and (p.open_hour >= 17 or "nightlife" in p.tags or "cho_dem" in p.tags)
        )
    ]
    ranked = sorted(
        candidates,
        key=lambda p: (
            -_intent_score(p, profiles),
            -len(tags.intersection(p.tags)),
            haversine_km(request.location.lat, request.location.lng, p.lat, p.lng),
            p.cost,
            _place_seed(p, seed),
        ),
    )
    quality_pool = ranked[: max(80, min(len(ranked), 120))]
    if not quality_pool:
        return []
    intent_matches = [place for place in quality_pool if _intent_score(place, profiles) > 0]
    other_matches = [place for place in quality_pool if _intent_score(place, profiles) <= 0]
    highlights = _highlight_places(request, excluded)
    highlight_ids = {place.id for place in highlights}
    if intent_matches:
        intent_offset = seed % len(intent_matches)
        other_offset = seed % len(other_matches) if other_matches else 0
        ordered = (
            intent_matches[intent_offset:]
            + intent_matches[:intent_offset]
            + other_matches[other_offset:]
            + other_matches[:other_offset]
        )
        return highlights + [place for place in ordered if place.id not in highlight_ids]
    offset = seed % len(quality_pool)
    ordered = quality_pool[offset:] + quality_pool[:offset]
    return highlights + [place for place in ordered if place.id not in highlight_ids]


def validate_plan(plan: dict, trusted_ids: set[str], request: PlanRequest | None = None) -> list[str]:
    errors: list[str] = []
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    if not 4 <= len(slots) <= 10:
        errors.append("Kế hoạch phải có 4–10 địa điểm")
    if any(slot.get("dia_diem_id") not in trusted_ids for slot in slots):
        errors.append("Có địa điểm ngoài danh sách tin cậy")
    by_id = {place.id: place for place in PLACES}
    for day in plan.get("ngay", []):
        previous_end = "00:00"
        for slot in day.get("khoang_gio", []):
            place = by_id.get(slot.get("dia_diem_id"))
            if slot["bat_dau"] < previous_end or slot["bat_dau"] >= slot["ket_thuc"]:
                errors.append(f"Khung giờ không tuần tự: {slot['dia_diem_id']}")
            if place and not (
                f"{place.open_hour:02d}:00" <= slot["bat_dau"]
                and slot["ket_thuc"] <= f"{place.close_hour:02d}:00"
            ):
                errors.append(f"Ngoài giờ mở cửa: {slot['dia_diem_id']}")
            previous_end = slot["ket_thuc"]
    if request and plan.get("chi_phi_moi_nguoi", 0) > request.ngan_sach:
        errors.append("Kế hoạch vượt ngân sách")
    return errors


def _select_within_budget(candidates: list[Place], count: int, budget_per_person: int) -> list[Place]:
    selected: list[Place] = []
    spent = 0
    for place in candidates:
        if spent + place.cost <= budget_per_person:
            selected.append(place)
            spent += place.cost
        if len(selected) == count:
            break
    return selected


def _candidate_payload(candidates: list[Place], request: PlanRequest) -> list[dict]:
    return [
        {
            "id": place.id,
            "name": place.name,
            "kind": place.kind,
            "area": place.area,
            "cost": place.cost,
            "duration_min": place.duration_min,
            "tags": list(place.tags),
            "open_hour": place.open_hour,
            "close_hour": place.close_hour,
            "distance_km": round(
                haversine_km(request.location.lat, request.location.lng, place.lat, place.lng),
                2,
            ),
        }
        for place in candidates[:80]
    ]


def _select_ai_places(candidates: list[Place], count: int, request: PlanRequest) -> list[Place] | None:
    propose = getattr(ai_adapter, "propose_place_ids", None)
    if not callable(propose):
        return None
    try:
        selected_ids = propose(
            request.context,
            _candidate_payload(candidates, request),
            count,
            request.ngon_ngu,
        )
    except RuntimeError:
        return None
    by_id = {place.id: place for place in candidates}
    selected = [by_id[place_id] for place_id in selected_ids if place_id in by_id]
    if len(selected) != count or len({place.id for place in selected}) != count:
        return None
    if sum(place.cost for place in selected) > request.ngan_sach:
        return None
    return selected


def _select_llm_first_places(
    candidates: list[Place],
    count: int,
    request: PlanRequest,
) -> tuple[list[Place], dict[str, dict]] | None:
    draft = getattr(ai_adapter, "draft_itinerary_places", None)
    if not callable(draft):
        return None
    try:
        suggestions = draft(request.context, count, request.ngon_ngu)
    except RuntimeError:
        return None
    selected: list[Place] = []
    details_by_id: dict[str, dict] = {}
    seen: set[str] = set()
    origin = (request.location.lat, request.location.lng)
    for item in suggestions:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        place = verify_place_name(name.strip(), origin)
        if not place or place.id in seen or place.cost > request.ngan_sach:
            continue
        selected.append(place)
        details_by_id[place.id] = item
        seen.add(place.id)
        if len(selected) == count:
            break
    if len(selected) < count:
        for place in candidates:
            if place.id in seen or place.cost > request.ngan_sach:
                continue
            selected.append(place)
            seen.add(place.id)
            if len(selected) == count:
                break
    if len(selected) != count or sum(place.cost for place in selected) > request.ngan_sach:
        return None
    return selected, details_by_id


def _join_sentences(parts: list[str], limit: int = 700) -> str:
    text = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return text[:limit].rstrip()


def _fallback_slot_copy(place: Place, request: PlanRequest, copy: tuple[str, ...]) -> tuple[str, str]:
    tags = set(place.tags)
    if place.kind == "cafe" or {"cafe", "coffee", "chill", "view_dep"}.intersection(tags):
        activity = "Dành thời gian nghỉ chân, gọi một món đặc trưng và ngắm nhịp phố xung quanh thay vì chỉ ghé qua cho có điểm."
        tip = "Nên chọn bàn có view tốt hoặc hỏi nhân viên món được gọi nhiều nhất; nếu quán đông, giữ nhịp linh hoạt để không trễ điểm tiếp theo."
    elif place.kind in {"nha_hang", "quan_an"} or {"am_thuc", "an_vat", "local"}.intersection(tags):
        activity = "Đây là điểm dừng để nạp năng lượng và thử hương vị địa phương, hợp đặt vào giữa lịch để chuyến đi không bị quá dày."
        tip = "Đi lệch giờ cao điểm một chút sẽ dễ có chỗ ngồi hơn; nên gọi vài món chia sẻ nếu đi từ hai người trở lên."
    elif {"pho_co", "old_quarter", "hang_pho", "di_bo"}.intersection(tags):
        activity = "Đi chậm qua các tuyến phố, nhìn mặt tiền nhà cổ, hàng quán nhỏ và nhịp buôn bán đặc trưng của khu phố cổ."
        tip = "Nên gom các phố gần nhau thành một đoạn đi bộ liên tục; buổi tối hợp hơn nếu muốn không khí đông vui và nhiều hàng ăn."
    elif {"hanoi_icon", "lich_su", "van_hoa", "museum", "heritage", "monument"}.intersection(tags):
        activity = "Dành thời gian nghe/đọc câu chuyện phía sau địa điểm, chụp vài góc tiêu biểu và để điểm này làm mốc chính cho cả chặng."
        tip = "Nên đi sớm nếu là điểm nổi tiếng hoặc có giờ mở cửa ngắn; kiểm tra quy định trang phục và vé trước khi xuất phát."
    elif {"ngoai_troi", "view_dep", "cong_vien"}.intersection(tags) or place.kind == "cong_vien":
        activity = "Đây là khoảng thở của lịch trình: đi bộ nhẹ, chụp ảnh và cân bằng lại nhịp sau các điểm đông người."
        tip = "Mang nước, tránh nắng gắt giữa trưa và ưu tiên sáng sớm hoặc chiều muộn nếu muốn ảnh đẹp hơn."
    else:
        activity = "Ghé điểm này như một lát cắt địa phương trong hành trình, vừa đủ thời gian quan sát, chụp ảnh và cảm nhận khu vực xung quanh."
        tip = copy[4]
    description = _join_sentences(
        [
            f"{place.name} ở khu {place.area} được xếp vào lịch vì phù hợp với yêu cầu “{request.context}”.",
            activity,
            "Điểm này cũng giúp tuyến đi bớt rời rạc vì có thể nối tiếp các điểm gần đó trong cùng khu vực.",
        ],
        limit=850,
    )
    return description, tip


def _slot_copy(place: Place, request: PlanRequest, copy: tuple[str, ...], llm_detail: dict | None) -> tuple[str, str]:
    if not llm_detail:
        return _fallback_slot_copy(place, request, copy)
    why = llm_detail.get("why")
    activity = llm_detail.get("activity") or llm_detail.get("what_to_do") or llm_detail.get("experience")
    tip = llm_detail.get("tip") or llm_detail.get("local_tip")
    meal = llm_detail.get("meal") or llm_detail.get("food")
    transport = llm_detail.get("transport") or llm_detail.get("move")
    description = _join_sentences(
        [
            f"{place.name} ({place.area}) phù hợp với yêu cầu “{request.context}”.",
            str(why) if isinstance(why, str) else "",
            str(activity) if isinstance(activity, str) else "",
            f"Gợi ý ăn/uống: {meal}." if isinstance(meal, str) and meal.strip() else "",
        ]
    )
    note = _join_sentences(
        [
            str(tip) if isinstance(tip, str) else "",
            f"Di chuyển: {transport}." if isinstance(transport, str) and transport.strip() else "",
            copy[4],
        ],
        limit=500,
    )
    return description or copy[3].format(place=place.name, area=place.area), note or copy[4]


def _ordered_route(places: list[Place], origin: tuple[float, float]) -> list[Place]:
    evening = [place for place in places if place.open_hour >= 17 or "nightlife" in place.tags or "cho_dem" in place.tags]
    daytime = [place for place in places if place not in evening]
    daytime_route = sorted(
        daytime,
        key=lambda place: (
            place.close_hour,
            haversine_km(origin[0], origin[1], place.lat, place.lng),
            place.open_hour,
        ),
    )
    if not evening:
        return daytime_route
    evening_origin = (
        (daytime_route[-1].lat, daytime_route[-1].lng)
        if daytime_route
        else origin
    )
    evening_route = two_opt(nearest_neighbor(evening, evening_origin))
    return daytime_route + evening_route


def build_plan(request: PlanRequest, excluded: set[str] | None = None) -> dict:
    if not DISTANCE_METADATA.get("loaded") or not DISTANCE_METADATA.get("updated_at"):
        raise PipelineUnavailable("Hệ thống đang khởi tạo bản đồ, vui lòng quay lại sau")
    count, max_minutes, number_of_days = LIMITS[request.thoi_luong]
    candidates = choose_candidates(request, excluded)
    llm_first = _select_llm_first_places(candidates, count, request)
    llm_details_by_id: dict[str, dict] = {}
    if llm_first:
        chosen, llm_details_by_id = llm_first
    else:
        chosen = (
            _select_ai_places(candidates, count, request)
            or _select_within_budget(candidates, count, request.ngan_sach)
        )
    if len(chosen) < count:
        raise PipelineUnavailable("Không đủ địa điểm tin cậy trong ngân sách")
    route = _ordered_route(chosen, (request.location.lat, request.location.lng))
    trip_date = request.ngay_di or datetime.now(UTC).date()
    copy = COPY[request.ngon_ngu]
    weather = {
        "tinh_trang": copy[0],
        "ghi_chu": copy[1],
        "nguon": None,
    }
    if settings.weather_enabled:
        try:
            weather = get_daily_weather(
                request.location.lat, request.location.lng, trip_date, request.ngon_ngu
            )
        except (WeatherUnavailable, ValueError, httpx.HTTPError):
            weather["ghi_chu"] = copy[2]
    split_index = (len(route) + 1) // 2
    day_routes = [route] if number_of_days == 1 else [route[:split_index], route[split_index:]]
    days: list[dict] = []
    total_cost = 0
    for day_index, places in enumerate(day_routes, start=1):
        cursor = datetime.combine(trip_date + timedelta(days=day_index - 1), datetime.min.time()).replace(hour=8)
        day_start = cursor
        slots = []
        previous: Place | None = None
        for place in places:
            if previous:
                cursor += timedelta(minutes=travel_minutes(previous, place))
            opening = cursor.replace(hour=place.open_hour, minute=0)
            cursor = max(cursor, opening)
            visit_minutes = min(place.duration_min, 40) if request.thoi_luong == "vai_gio" else place.duration_min
            end = cursor + timedelta(minutes=visit_minutes)
            closing = cursor.replace(hour=place.close_hour, minute=0)
            if end > closing or int((end - day_start).total_seconds() // 60) > max_minutes:
                raise PipelineUnavailable("Không thể xếp lịch tuần tự trong giờ mở cửa")
            mo_ta, ghi_chu = _slot_copy(place, request, copy, llm_details_by_id.get(place.id))
            slots.append(
                {
                    "bat_dau": cursor.strftime("%H:%M"),
                    "ket_thuc": end.strftime("%H:%M"),
                    "dia_diem_id": place.id,
                    "ten_dia_diem": place.name,
                    "loai": place.kind,
                    "mo_ta": mo_ta,
                    "chi_phi": place.cost * request.so_nguoi,
                    "toa_do": {"lat": place.lat, "lng": place.lng},
                    "nguon": place.source,
                    "nguon_url": place.source_url,
                    "ghi_chu": ghi_chu,
                }
            )
            total_cost += place.cost * request.so_nguoi
            cursor, previous = end, place
        days.append({"thu_tu": day_index, "nhan_de": copy[5].format(day=day_index), "khoang_gio": slots})
    draft = {
        "tieu_de": f"Hà Nội · {request.context[:48]}",
        "tom_tat": copy[6].format(people=request.so_nguoi),
        "thoi_luong": request.thoi_luong,
        "ngay_di": trip_date.isoformat(),
        "tong_chi_phi": total_cost,
        "chi_phi_moi_nguoi": total_cost // request.so_nguoi,
        "thoi_tiet": weather,
        "ngay": days,
        "luu_y": [
            copy[7],
            copy[8],
        ],
    }
    trusted_ids = {p.id for p in [*candidates, *chosen]}
    try:
        plan = ai_adapter.assemble(draft, trusted_ids, request.ngon_ngu)
    except RuntimeError:
        plan = draft
        plan["luu_y"] = [
            *plan.get("luu_y", []),
            AI_FALLBACK_NOTE.get(request.ngon_ngu, AI_FALLBACK_NOTE["en"]),
        ][:6]
    errors = validate_plan(plan, trusted_ids, request)
    if errors:
        raise PipelineUnavailable("; ".join(errors))
    return plan
