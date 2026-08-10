import hashlib
import random
import re
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings
from app.data import DISTANCE_METADATA, PLACES, Place, image_for
from app.pipeline.visit_guidance import VisitGuidance, guidance_for
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
from app.text_utils import ascii_fold

LIMITS = {
    "vai_gio": (4, 300, 1),
    "nua_ngay": (5, 600, 1),
    "ca_ngay": (8, 900, 1),
    # ~8 stops/day including midday rest + evening, matching denser full days.
    "nhieu_ngay": (16, 900, 2),
}

DINING_KINDS = frozenset({"nha_hang", "quan_an"})
SIGHT_KINDS = frozenset({"dia_danh", "bao_tang", "cong_vien", "cho"})
# (start_hour, start_min, end_hour, end_min) — khung giờ ăn / nghỉ mục tiêu
MEAL_WINDOWS: dict[str, tuple[int, int, int, int]] = {
    "sang": (7, 30, 9, 30),
    "trua": (11, 0, 13, 30),
    "nghi": (12, 30, 14, 30),
    "toi": (18, 0, 21, 0),
    "dem": (19, 0, 22, 30),
}
MEAL_DURATION = {"sang": 45, "trua": 60, "nghi": 50, "toi": 75, "dem": 75}
MEAL_PREFERRED_START = {
    "sang": (7, 45),
    "trua": (11, 30),
    "nghi": (13, 0),
    "toi": (18, 30),
    "dem": (19, 30),
}
MAX_IDLE_MINUTES = 35
MIN_VISIT_MINUTES = 25
MAX_GAP_BEFORE_FILL_MINUTES = 55

EVENING_PLACE_IDS = (
    "curated-cho-dem-dong-xuan",
    "curated-pho-ta-hien",
)
EVENING_FALLBACK_IDS = (
    "curated-ho-guom",
    "curated-pho-co-ha-noi",
)

# Official / practical hours when OSM catalogue is wrong or too broad.
KNOWN_HOURS_BY_NAME: dict[str, tuple[int, int]] = {
    "lang chu tich ho chi minh": (7, 11),
}

MEAL_LABELS: dict[str, dict[str, str]] = {
    "vi": {"sang": "Bữa sáng", "trua": "Bữa trưa", "nghi": "Nghỉ trưa", "toi": "Bữa tối", "dem": "Buổi tối"},
    "en": {"sang": "Breakfast", "trua": "Lunch", "nghi": "Midday break", "toi": "Dinner", "dem": "Evening"},
    "ar": {"sang": "فطور", "trua": "غداء", "nghi": "استراحة ظهيرة", "toi": "عشاء", "dem": "مساء"},
    "bg": {"sang": "Закуска", "trua": "Обяд", "nghi": "Обедна почивка", "toi": "Вечеря", "dem": "Вечер"},
    "de": {"sang": "Frühstück", "trua": "Mittagessen", "nghi": "Mittagsruhe", "toi": "Abendessen", "dem": "Abendprogramm"},
    "es": {"sang": "Desayuno", "trua": "Almuerzo", "nghi": "Descanso del mediodía", "toi": "Cena", "dem": "Noche"},
    "fr": {"sang": "Petit-déjeuner", "trua": "Déjeuner", "nghi": "Pause de midi", "toi": "Dîner", "dem": "Soirée"},
    "he": {"sang": "ארוחת בוקר", "trua": "ארוחת צהריים", "nghi": "הפסקת צהריים", "toi": "ארוחת ערב", "dem": "ערב"},
    "hi": {"sang": "नाश्ता", "trua": "दोपहर का भोजन", "nghi": "दोपहर का विश्राम", "toi": "रात का खाना", "dem": "शाम"},
    "it": {"sang": "Colazione", "trua": "Pranzo", "nghi": "Pausa pranzo", "toi": "Cena", "dem": "Serata"},
    "ja": {"sang": "朝食", "trua": "昼食", "nghi": "昼休み", "toi": "夕食", "dem": "夜の予定"},
    "nl": {"sang": "Ontbijt", "trua": "Lunch", "nghi": "Middagpauze", "toi": "Diner", "dem": "Avond"},
    "pl": {"sang": "Śniadanie", "trua": "Obiad", "nghi": "Przerwa południowa", "toi": "Kolacja", "dem": "Wieczór"},
    "pt": {"sang": "Pequeno-almoço", "trua": "Almoço", "nghi": "Pausa do meio-dia", "toi": "Jantar", "dem": "Noite"},
    "ru": {"sang": "Завтрак", "trua": "Обед", "nghi": "Дневной отдых", "toi": "Ужин", "dem": "Вечер"},
    "tr": {"sang": "Kahvaltı", "trua": "Öğle yemeği", "nghi": "Öğle molası", "toi": "Akşam yemeği", "dem": "Akşam"},
    "zh": {"sang": "早餐", "trua": "午餐", "nghi": "午休", "toi": "晚餐", "dem": "晚间"},
    "ko": {"sang": "아침", "trua": "점심", "nghi": "낮 휴식", "toi": "저녁", "dem": "저녁 일정"},
    "th": {"sang": "มื้อเช้า", "trua": "มื้อกลางวัน", "nghi": "พักเที่ยง", "toi": "มื้อเย็น", "dem": "ช่วงเย็น"},
}

AI_FALLBACK_NOTE = {
    "vi": "AI tạm thời không khả dụng; lịch trình đang dùng bộ xếp lịch an toàn từ dữ liệu đã kiểm chứng.",
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
    "van-mieu",
    "chua-tran-quoc",
    "bao-tang-phu-nu",
    "long-bien",
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
    return ascii_fold(value)


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
    generic_tourism = tags.intersection({"du_lich", "tham_quan", "noi_tieng", "lan_dau", "classic"})
    explicit_anchor = tags.intersection({"ho_guom", "ho_tay", "lang_bac", "ho_chi_minh", "ba_dinh"})
    wants_hanoi_highlights = bool(generic_tourism or explicit_anchor)
    wants_night = bool(tags.intersection(INTENT_PROFILES["night"]["terms"]))
    by_id = {place.id: place for place in PLACES}
    place_ids = [
        *((*HANOI_HIGHLIGHT_IDS,) if wants_hanoi_highlights else ()),
        *((*HANOI_NIGHT_IDS,) if wants_night else ()),
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


def _wants_coffee(request: PlanRequest) -> bool:
    return bool(relevant_tags(request.context).intersection(INTENT_PROFILES["coffee"]["terms"]))


def _is_sight_place(place: Place, *, allow_cafe: bool = False) -> bool:
    if place.kind in SIGHT_KINDS:
        return True
    return allow_cafe and place.kind == "cafe"


def _place_name_key(place: Place) -> str:
    return " ".join(_ascii_fold(place.name).split())


def _prefer_place(left: Place, right: Place) -> Place:
    left_score = (
        int(left.source == "curated"),
        int(left.source == "Nominatim"),
        -left.cost,
    )
    right_score = (
        int(right.source == "curated"),
        int(right.source == "Nominatim"),
        -right.cost,
    )
    return left if left_score >= right_score else right


def _dedupe_places(places: list[Place]) -> list[Place]:
    """Keep one stop per place id and per display name (prefer curated)."""
    by_id: dict[str, Place] = {}
    for place in places:
        existing = by_id.get(place.id)
        by_id[place.id] = _prefer_place(existing, place) if existing else place

    by_name: dict[str, Place] = {}
    order: list[str] = []
    for place in by_id.values():
        key = _place_name_key(place)
        if not key:
            order.append(place.id)
            by_name[place.id] = place
            continue
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = place
            order.append(key)
            continue
        by_name[key] = _prefer_place(existing, place)
    return [by_name[key] for key in order]


def _is_dining_place(place: Place) -> bool:
    return place.kind in DINING_KINDS


def _meals_per_day(thoi_luong: str) -> tuple[str, ...]:
    if thoi_luong == "vai_gio":
        return ("trua",)
    if thoi_luong == "nua_ngay":
        return ("trua",)
    return ("trua", "toi")


def _meal_labels(locale: str) -> dict[str, str]:
    return MEAL_LABELS.get(locale, MEAL_LABELS["en"])


def _sight_candidates(candidates: list[Place], request: PlanRequest | None = None) -> list[Place]:
    allow_cafe = bool(request and _wants_coffee(request))
    sights = [
        place
        for place in candidates
        if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
    ]
    if sights:
        return sights
    non_dining = [place for place in candidates if not _is_dining_place(place)]
    attractions = [place for place in non_dining if place.kind in SIGHT_KINDS]
    if attractions:
        return attractions
    if allow_cafe:
        return non_dining or candidates
    without_cafe = [place for place in non_dining if place.kind != "cafe"]
    return without_cafe or non_dining or candidates


def _anchor_for_places(places: list[Place], fallback: tuple[float, float]) -> tuple[float, float]:
    if not places:
        return fallback
    return (
        sum(place.lat for place in places) / len(places),
        sum(place.lng for place in places) / len(places),
    )


def _choose_meal_place(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    meal_type: str,
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    start_h, _, end_h, _ = MEAL_WINDOWS[meal_type]
    food_profile = INTENT_PROFILES["food"]
    pool = [
        place
        for place in PLACES
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and _is_dining_place(place)
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and _effective_hours(place)[0] <= start_h
        and _effective_hours(place)[1] >= end_h
    ]
    if not pool:
        return None
    ranked = sorted(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            -_intent_score(place, [food_profile]),
            -len({"am_thuc", "an_vat", "local", "vietnamese"}.intersection(place.tags)),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            place.cost,
            _place_seed(place, seed),
        ),
    )
    return ranked[0]


def _choose_extra_sight(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    pool = [
        place
        for place in PLACES
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and place.kind in SIGHT_KINDS
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and is_routable(place)
        and place.open_hour <= 16
        and place.close_hour >= 12
    ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            -int(place.kind in {"dia_danh", "bao_tang"}),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _choose_refreshment(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    pool = [
        place
        for place in PLACES
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and place.open_hour <= 9
        and place.close_hour >= 11
    ]
    if not pool:
        pool = [
            place
            for place in PLACES
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
        ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _sight_total(count: int, meals_total: int, thoi_luong: str) -> int:
    if thoi_luong == "vai_gio":
        return 2
    # Reserve room for midday rest + evening stop on full days.
    reserve = 2 if thoi_luong in {"ca_ngay", "nhieu_ngay"} else 0
    return max(2, count - meals_total - reserve)


def _min_plan_slots(thoi_luong: str) -> int:
    _, _, days = LIMITS[thoi_luong]
    return 4 if days == 1 else 6


def _max_plan_slots(thoi_luong: str) -> int:
    count, _, days = LIMITS[thoi_luong]
    # Buffer for midday rest + evening (+ optional fill) each day.
    return count + days * 3


def _is_evening_place(place: Place) -> bool:
    """True only for stops that belong after dinner, not dual-use daytime icons."""
    open_hour, _ = _effective_hours(place)
    tags = set(place.tags)
    if place.id in EVENING_PLACE_IDS:
        return True
    if open_hour >= 17:
        return True
    return bool({"cho_dem", "night_market"}.intersection(tags))


def _is_night_market(place: Place) -> bool:
    """Return whether a place has explicit night-market semantics."""
    return bool({"cho_dem", "night_market"}.intersection(place.tags))


def _choose_midday_rest(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    """Quiet cafe/snack stop to bridge the hot early afternoon."""
    pool = [
        place
        for place in PLACES
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and place.open_hour <= 12
        and place.close_hour >= 15
        and is_routable(place)
    ]
    if not pool:
        pool = [
            place
            for place in PLACES
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
            and is_routable(place)
        ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda place: (
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            place.cost,
            _place_seed(place, seed),
        ),
    )


def _choose_evening_place(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    by_id = {place.id: place for place in PLACES}

    def pick(ids: tuple[str, ...]) -> Place | None:
        pool = [
            place
            for place_id in ids
            if (place := by_id.get(place_id))
            and place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and place.cost <= budget_per_person
            and is_routable(place)
        ]
        if not pool:
            return None
        return min(
            pool,
            key=lambda place: (
                -int(place.source == "curated"),
                haversine_km(anchor[0], anchor[1], place.lat, place.lng),
                _place_seed(place, seed),
            ),
        )

    return pick(EVENING_PLACE_IDS) or pick(EVENING_FALLBACK_IDS) or min(
        (
            place
            for place in PLACES
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and _is_evening_place(place)
            and not _is_dining_place(place)
            and place.cost <= budget_per_person
            and is_routable(place)
        ),
        default=None,
        key=lambda place: (
            -int(place.source == "curated"),
            haversine_km(anchor[0], anchor[1], place.lat, place.lng),
            _place_seed(place, seed),
        ),
    )


def _build_day_route(
    request: PlanRequest,
    day_sights: list[Place],
    day_meals: list[tuple[str, Place]],
    used: set[str],
    remaining_budget: int,
    seed: int,
    used_names: set[str],
) -> list[tuple[Place, str | None]]:
    if request.thoi_luong != "vai_gio":
        route = _interleave_meals(day_sights, day_meals)
        anchor = _anchor_for_places(day_sights, (request.location.lat, request.location.lng))
        lunch_at = next((i for i, (_, meal) in enumerate(route) if meal == "trua"), None)
        if request.thoi_luong in {"ca_ngay", "nhieu_ngay"} and remaining_budget > 0 and lunch_at is not None:
            rest = _choose_midday_rest(request, used, anchor, seed, remaining_budget, used_names)
            if rest:
                route.insert(lunch_at + 1, (rest, "nghi"))
                used.add(rest.id)
                if name_key := _place_name_key(rest):
                    used_names.add(name_key)
                remaining_budget -= rest.cost
            # Keep one more afternoon attraction when the day still looks thin.
            if len(day_sights) + len(day_meals) <= 5:
                extra = _choose_extra_sight(request, used, anchor, seed + 1, remaining_budget, used_names)
                if extra:
                    insert_at = lunch_at + (2 if rest else 1)
                    route.insert(insert_at, (extra, None))
                    used.add(extra.id)
                    if name_key := _place_name_key(extra):
                        used_names.add(name_key)
                    remaining_budget -= extra.cost
        # Always add an evening stop after dinner for full/multi-day trips.
        if request.thoi_luong in {"ca_ngay", "nhieu_ngay"}:
            has_evening = any(meal_type == "dem" or (meal_type is None and _is_evening_place(place)) for place, meal_type in route)
            if not has_evening:
                evening = _choose_evening_place(
                    request, used, anchor, seed + 3, max(remaining_budget, 0), used_names
                )
                if evening:
                    dinner_at = next((i for i, (_, meal) in enumerate(route) if meal == "toi"), None)
                    insert_at = (dinner_at + 1) if dinner_at is not None else len(route)
                    route.insert(insert_at, (evening, "dem"))
                    used.add(evening.id)
                    if name_key := _place_name_key(evening):
                        used_names.add(name_key)
        return route
    sights = day_sights[:2]
    anchor = _anchor_for_places(sights, (request.location.lat, request.location.lng))
    refresh = None
    if _wants_coffee(request) or request.thoi_luong == "vai_gio":
        refresh = _choose_refreshment(request, used, anchor, seed, remaining_budget, used_names)
        if refresh:
            used.add(refresh.id)
            if name_key := _place_name_key(refresh):
                used_names.add(name_key)
    if not day_meals:
        return [(place, None) for place in sights]
    lunch_type, lunch_place = day_meals[0]
    route: list[tuple[Place, str | None]] = []
    if sights:
        route.append((sights[0], None))
    if refresh:
        route.append((refresh, None))
    if len(sights) > 1:
        route.append((sights[1], None))
    route.append((lunch_place, lunch_type))
    return route


def _interleave_meals(
    sights: list[Place],
    meals: list[tuple[str, Place]],
) -> list[tuple[Place, str | None]]:
    """Seed order: morning → lunch → afternoon → dinner → evening."""
    if not meals:
        return [(place, None) for place in sights]
    morning = [place for place in sights if _is_morning_only(place)]
    evening = [place for place in sights if place not in morning and _is_evening_place(place)]
    outdoor = [
        place
        for place in sights
        if place not in morning and place not in evening and _is_outdoor_place(place)
    ]
    flexible = [
        place
        for place in sights
        if place not in morning and place not in evening and place not in outdoor
    ]
    lunch = next((item for item in meals if item[0] == "trua"), None)
    dinner = next((item for item in meals if item[0] == "toi"), None)
    other_meals = [item for item in meals if item is not lunch and item is not dinner]
    morning_flex_count = (len(flexible) + 1) // 2
    morning_flex = flexible[:morning_flex_count]
    afternoon_flex = flexible[morning_flex_count:]
    route: list[tuple[Place, str | None]] = [(place, None) for place in [*morning, *morning_flex]]
    if lunch:
        route.append((lunch[1], lunch[0]))
    route.extend((place, None) for place in [*outdoor, *afternoon_flex])
    if dinner:
        route.append((dinner[1], dinner[0]))
    route.extend((place, None) for place in evening)
    for meal, place in other_meals:
        route.append((place, meal))
    return route


def _pick_day_meals(
    request: PlanRequest,
    day_sights: list[Place],
    used: set[str],
    budget_per_person: int,
    seed: int,
    used_names: set[str],
) -> list[tuple[str, Place]]:
    anchor = _anchor_for_places(day_sights, (request.location.lat, request.location.lng))
    meals: list[tuple[str, Place]] = []
    remaining = budget_per_person
    for meal_type in _meals_per_day(request.thoi_luong):
        place = _choose_meal_place(request, used, anchor, meal_type, seed, remaining, used_names)
        if not place:
            continue
        meals.append((meal_type, place))
        used.add(place.id)
        if name_key := _place_name_key(place):
            used_names.add(name_key)
        remaining -= place.cost
    return meals


def _guidance(place: Place) -> VisitGuidance | None:
    return guidance_for(place.id, _place_name_key(place))


def _effective_hours(place: Place) -> tuple[int, int]:
    tip = _guidance(place)
    if tip and tip.open_hour is not None and tip.close_hour is not None:
        return tip.open_hour, tip.close_hour
    known = KNOWN_HOURS_BY_NAME.get(_place_name_key(place))
    if known:
        return known
    open_hour = max(0, min(23, place.open_hour))
    close_hour = max(open_hour + 1, min(24, place.close_hour))
    return open_hour, close_hour


def _is_outdoor_place(place: Place) -> bool:
    tags = set(place.tags)
    if "nightlife" in tags or "cho_dem" in tags or _effective_hours(place)[0] >= 17:
        return False
    tip = _guidance(place)
    if tip and tip.alt_preferred and tip.preferred[2] <= 11:
        return True
    return (
        place.kind == "cong_vien"
        or bool({"ngoai_troi", "ho_tay", "ho_guom", "view_dep"}.intersection(tags))
        or (place.kind == "dia_danh" and "di_bo" in tags and "pho_co" not in tags)
    )


def _is_morning_only(place: Place) -> bool:
    open_hour, close_hour = _effective_hours(place)
    tip = _guidance(place)
    if tip and tip.preferred[2] <= 11 and tip.alt_preferred is None:
        return True
    if close_hour <= 12:
        return True
    return bool({"lang_bac", "ho_chi_minh"}.intersection(place.tags))


def _preferred_window(place: Place, meal_type: str | None) -> tuple[int, int, int, int]:
    """Return preferred (start_h, start_m, end_h, end_m) local visit window."""
    open_hour, close_hour = _effective_hours(place)
    if _is_night_market(place):
        return max(open_hour, 18), 0, close_hour, 0
    if meal_type:
        start_h, start_m, end_h, end_m = MEAL_WINDOWS[meal_type]
        return start_h, start_m, end_h, end_m
    tip = _guidance(place)
    if tip:
        return tip.preferred
    tags = set(place.tags)
    if _is_morning_only(place):
        return open_hour, 0, close_hour, 0
    if "nightlife" in tags or "cho_dem" in tags or open_hour >= 17:
        return max(open_hour, 18), 0, close_hour, 0
    if place.kind == "bao_tang" or {"museum", "van_hoa", "lich_su", "heritage"}.intersection(tags):
        return max(open_hour, 8), 30, min(close_hour, 17), 0
    if _is_outdoor_place(place):
        return 7, 0, 10, 0
    if place.kind == "cafe":
        return max(open_hour, 9), 0, min(close_hour, 17), 0
    return open_hour, 0, close_hour, 0


def _pick_visit_window(
    place: Place,
    meal_type: str | None,
    arrive: datetime,
) -> tuple[int, int, int, int]:
    """Choose primary or alternate preferred window closest to arrival."""
    if _is_night_market(place):
        return _preferred_window(place, meal_type)
    if meal_type:
        return _preferred_window(place, meal_type)
    tip = _guidance(place)
    primary = _preferred_window(place, None)
    if not tip or not tip.alt_preferred:
        return primary
    arrive_hour = arrive.hour + arrive.minute / 60
    windows = [primary, tip.alt_preferred]

    def window_score(window: tuple[int, int, int, int]) -> float:
        start = window[0] + window[1] / 60
        end = window[2] + window[3] / 60
        if start <= arrive_hour <= end:
            return 0
        if arrive_hour < start:
            return start - arrive_hour
        return arrive_hour - end + 8

    return min(windows, key=window_score)


def _outdoor_afternoon_window(base: datetime) -> tuple[datetime, datetime]:
    return _at_clock(base, 14, 0), _at_clock(base, 17, 45)


def _visit_minutes_for(place: Place, meal_type: str | None, request: PlanRequest) -> int:
    if meal_type:
        minutes = min(MEAL_DURATION[meal_type], place.duration_min, 90)
        if request.thoi_luong == "vai_gio":
            minutes = min(minutes, 45)
        return max(MIN_VISIT_MINUTES, minutes)
    tip = _guidance(place)
    minutes = tip.duration_min if tip and tip.duration_min else place.duration_min
    if request.thoi_luong == "vai_gio":
        minutes = min(minutes, 35)
        if place.kind == "cafe":
            minutes = min(minutes, 30)
    return max(MIN_VISIT_MINUTES, minutes)


def _preference_score(place: Place, meal_type: str | None, hour: float) -> float:
    if _is_night_market(place):
        open_hour, close_hour = _effective_hours(place)
        return 12 if max(open_hour, 18) <= hour < close_hour else -50
    if meal_type:
        preferred = MEAL_PREFERRED_START[meal_type]
        preferred_hour = preferred[0] + preferred[1] / 60
        return 20 - abs(hour - preferred_hour) * 4
    open_hour, close_hour = _effective_hours(place)
    if hour < open_hour or hour >= close_hour:
        return -50
    tip = _guidance(place)
    if tip:
        windows = [tip.preferred] + ([tip.alt_preferred] if tip.alt_preferred else [])
        best = max(
            (
                16 - abs(hour - ((w[0] + w[1] / 60 + w[2] + w[3] / 60) / 2)) * 3
                if (w[0] + w[1] / 60) <= hour <= (w[2] + w[3] / 60)
                else 4 - abs(hour - ((w[0] + w[1] / 60 + w[2] + w[3] / 60) / 2))
            )
            for w in windows
        )
        return best
    if _is_morning_only(place):
        return 15 - abs(hour - 8.5) if hour < 12 else -20
    if _is_outdoor_place(place):
        if 7 <= hour < 10.5:
            return 14
        if 14 <= hour <= 18:
            return 16
        if 11 <= hour < 14:
            return -10
        return 2
    if "nightlife" in place.tags or "cho_dem" in place.tags:
        return 12 if hour >= 18.5 else -5
    pref_start, pref_m, pref_end, pref_end_m = _preferred_window(place, None)
    pref_from = pref_start + pref_m / 60
    pref_to = pref_end + pref_end_m / 60
    if pref_from <= hour <= pref_to:
        return 12
    center = (pref_from + pref_to) / 2
    return 6 - abs(hour - center)


def _at_clock(base: datetime, hour: int, minute: int = 0) -> datetime:
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _compute_slot_bounds(
    place: Place,
    meal_type: str | None,
    arrive: datetime,
    day_start: datetime,
    day_end: datetime,
    request: PlanRequest,
    *,
    relax: bool = False,
) -> tuple[datetime, datetime, int] | None:
    open_hour, close_hour = _effective_hours(place)
    opening = _at_clock(arrive, open_hour, 0)
    closing = _at_clock(arrive, close_hour, 0) if close_hour < 24 else day_end
    pref_start, pref_m, pref_end, pref_end_m = _pick_visit_window(place, meal_type, arrive)
    preferred_open = _at_clock(arrive, pref_start, pref_m)
    preferred_close = _at_clock(arrive, pref_end, pref_end_m)
    visit = _visit_minutes_for(place, meal_type, request)
    night_market = _is_night_market(place)

    earliest = max(arrive, opening, day_start)
    if night_market:
        earliest = max(earliest, _at_clock(arrive, 18, 0))
    latest_end = min(closing, preferred_close if meal_type else closing, day_end)
    if meal_type:
        # Soft meal window: allow a little earlier than classic lunch/dinner.
        earliest = max(earliest, _at_clock(arrive, pref_start, 0))
        latest_end = min(latest_end, preferred_close)
    elif not relax:
        # Keep visits inside researched preferred windows when possible.
        latest_end = min(latest_end, preferred_close, closing, day_end)

    ideal = max(earliest, preferred_open)
    # Outdoor without explicit dual guidance: morning if early, else afternoon cool window.
    tip = _guidance(place)
    if not meal_type and _is_outdoor_place(place) and not tip and not relax:
        arrive_hour = arrive.hour + arrive.minute / 60
        cool_start, cool_end = _outdoor_afternoon_window(arrive)
        if arrive_hour < 11:
            ideal = max(earliest, _at_clock(arrive, max(open_hour, 7), 0))
            latest_end = min(latest_end, _at_clock(arrive, 10, 30), closing, day_end)
        elif cool_start + timedelta(minutes=MIN_VISIT_MINUTES) <= min(cool_end, closing, day_end):
            if (cool_start - arrive).total_seconds() / 60 > 60:
                cool_start = max(arrive, _at_clock(arrive, 14, 0))
            ideal = max(earliest, cool_start)
            latest_end = min(latest_end, cool_end, closing, day_end)
    idle = (ideal - arrive).total_seconds() / 60
    strict = night_market or (
        (not relax)
        and (
            _is_morning_only(place)
            or bool(meal_type)
            or (
                _is_outdoor_place(place)
                and not meal_type
                and 11 <= (arrive.hour + arrive.minute / 60) < 14
            )
        )
    )
    if idle > MAX_IDLE_MINUTES and not strict:
        start = earliest
    elif idle > MAX_IDLE_MINUTES and meal_type and arrive >= _at_clock(arrive, pref_start, 0):
        start = earliest
    else:
        start = ideal

    if start + timedelta(minutes=MIN_VISIT_MINUTES) > latest_end:
        if relax:
            latest_end = min(closing, day_end)
        if start + timedelta(minutes=MIN_VISIT_MINUTES) > latest_end:
            return None
    available = int((latest_end - start).total_seconds() // 60)
    visit = min(visit, available)
    if visit < MIN_VISIT_MINUTES:
        return None
    end = start + timedelta(minutes=visit)
    if end > closing or end > day_end:
        return None
    return start, end, visit


def _pack_day_slots(
    route_stops: list[tuple[Place, str | None]],
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_details_by_id: dict[str, dict],
    labels: dict[str, str],
    scheduled_ids: set[str],
    scheduled_names: set[str],
    max_slots: int = 10,
) -> tuple[list[dict], int]:
    day_end = day_start + timedelta(minutes=max_minutes)
    remaining = [
        (place, meal_type)
        for place, meal_type in route_stops
        if place.id not in scheduled_ids
        and not ((key := _place_name_key(place)) and key in scheduled_names)
    ]
    slots: list[dict] = []
    total_cost = 0
    cursor = day_start
    previous: Place | None = None
    plan_slot_count = len(scheduled_ids)

    while remaining and plan_slot_count + len(slots) < max_slots:
        best_index = -1
        best_score = -1e9
        best_bounds: tuple[datetime, datetime, int] | None = None
        # Prefer quality constraints first; if nothing fits, relax outdoor windows.
        for relax in (False, True):
            best_index = -1
            best_score = -1e9
            best_bounds = None
            for index, (place, meal_type) in enumerate(remaining):
                travel = travel_minutes(previous, place) if previous else 0
                arrive = cursor + timedelta(minutes=travel)
                bounds = _compute_slot_bounds(
                    place, meal_type, arrive, day_start, day_end, request, relax=relax
                )
                if not bounds:
                    continue
                start, end, _visit = bounds
                idle = max(0, (start - arrive).total_seconds() / 60)
                score = _preference_score(place, meal_type, start.hour + start.minute / 60)
                score -= idle * 0.6
                score -= travel * 0.15
                if relax:
                    score -= 5
                if meal_type == "toi" and any(mt == "trua" for _, mt in remaining):
                    score -= 30
                if meal_type == "nghi" and any(mt == "trua" for _, mt in remaining):
                    score -= 40
                # After lunch, finish the midday rest before more sightseeing.
                if any(mt == "nghi" for _, mt in remaining) and meal_type != "nghi":
                    score -= 55
                # Daytime sights before dinner; evening block after dinner.
                if meal_type == "toi" and any(
                    mt is None and not _is_evening_place(place) for place, mt in remaining
                ):
                    score -= 45
                if meal_type == "dem" and any(mt == "toi" for _, mt in remaining):
                    score -= 50
                if (
                    meal_type is None
                    and _is_evening_place(place)
                    and any(mt == "toi" for _, mt in remaining)
                ):
                    score -= 50
                if score > best_score:
                    best_score = score
                    best_index = index
                    best_bounds = bounds
            if best_index >= 0:
                break
        if best_index < 0 or best_bounds is None:
            break
        place, meal_type = remaining.pop(best_index)
        start, end, _visit = best_bounds
        mo_ta, ghi_chu = _slot_copy(place, request, copy, llm_details_by_id.get(place.id), meal_type, labels)
        image_url, image_credit = image_for(place)
        slot = {
            "bat_dau": start.strftime("%H:%M"),
            "ket_thuc": end.strftime("%H:%M"),
            "dia_diem_id": place.id,
            "ten_dia_diem": place.name,
            "loai": place.kind,
            "mo_ta": mo_ta,
            "chi_phi": place.cost * request.so_nguoi,
            "toa_do": {"lat": place.lat, "lng": place.lng},
            "nguon": place.source,
            "nguon_url": place.source_url,
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
        }
        if meal_type:
            slot["bua_an"] = meal_type
            slot["nhan_bua"] = labels[meal_type]
        slots.append(slot)
        total_cost += place.cost * request.so_nguoi
        scheduled_ids.add(place.id)
        name_key = _place_name_key(place)
        if name_key:
            scheduled_names.add(name_key)
            remaining = [
                item for item in remaining if _place_name_key(item[0]) != name_key
            ]
        cursor = end
        previous = place
    slots = _tighten_day_gaps(slots, day_end)
    return slots, total_cost


def _tighten_day_gaps(slots: list[dict], day_end: datetime) -> list[dict]:
    """Extend visits slightly to avoid long empty holes between stops."""
    if len(slots) < 2:
        return slots
    by_id = {place.id: place for place in PLACES}
    for index in range(len(slots) - 1):
        current = slots[index]
        nxt = slots[index + 1]
        cur_end_h, cur_end_m = map(int, current["ket_thuc"].split(":"))
        next_start_h, next_start_m = map(int, nxt["bat_dau"].split(":"))
        gap = (next_start_h * 60 + next_start_m) - (cur_end_h * 60 + cur_end_m)
        if gap <= 40:
            continue
        place = by_id.get(current["dia_diem_id"])
        next_place = by_id.get(nxt["dia_diem_id"])
        if not place or not next_place or current.get("bua_an"):
            continue
        travel = travel_minutes(place, next_place)
        reserve = max(travel, 12)
        if gap <= reserve + 15:
            continue
        _, close_hour = _effective_hours(place)
        extend = min(gap - reserve - 8, 90)
        new_end_minutes = cur_end_h * 60 + cur_end_m + extend
        close_minutes = close_hour * 60
        day_end_minutes = day_end.hour * 60 + day_end.minute
        latest_allowed = next_start_h * 60 + next_start_m - reserve
        tip = _guidance(place)
        if tip:
            window_ends = [tip.preferred[2] * 60 + tip.preferred[3]]
            if tip.alt_preferred:
                window_ends.append(tip.alt_preferred[2] * 60 + tip.alt_preferred[3])
            # Cap extension by the preferred window that covers the current visit start.
            start_minutes = cur_end_h * 60 + cur_end_m - 1
            covering = [
                end
                for (window, end) in (
                    (tip.preferred, tip.preferred[2] * 60 + tip.preferred[3]),
                    *(( (tip.alt_preferred, tip.alt_preferred[2] * 60 + tip.alt_preferred[3]),)
                      if tip.alt_preferred else ()),
                )
                if window[0] * 60 + window[1] <= start_minutes <= end + 90
            ]
            if covering:
                latest_allowed = min(latest_allowed, max(covering))
        new_end_minutes = min(new_end_minutes, close_minutes, day_end_minutes, latest_allowed)
        if new_end_minutes <= cur_end_h * 60 + cur_end_m:
            continue
        current["ket_thuc"] = f"{new_end_minutes // 60:02d}:{new_end_minutes % 60:02d}"
    return slots


def _parse_slot_clock(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _backfill_day_gaps(
    slots: list[dict],
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_details_by_id: dict[str, dict],
    labels: dict[str, str],
    scheduled_ids: set[str],
    scheduled_names: set[str],
    used_ids: set[str],
    remaining_budget: int,
    seed: int,
    max_slots: int,
) -> tuple[list[dict], int]:
    """Insert nearby attractions into long idle gaps between packed stops."""
    if len(slots) < 1 or len(slots) >= max_slots:
        return slots, 0
    day_end = day_start + timedelta(minutes=max_minutes)
    by_id = {place.id: place for place in PLACES}
    extra_cost = 0
    index = 0
    while index < len(slots) - 1 and len(slots) < max_slots:
        current = slots[index]
        nxt = slots[index + 1]
        gap = _parse_slot_clock(nxt["bat_dau"]) - _parse_slot_clock(current["ket_thuc"])
        if gap < MAX_GAP_BEFORE_FILL_MINUTES:
            index += 1
            continue
        prev_place = by_id.get(current["dia_diem_id"])
        next_place = by_id.get(nxt["dia_diem_id"])
        if not prev_place or not next_place:
            index += 1
            continue
        # Do not squeeze a stop into the wait before dinner if gap is mostly meal wait.
        if nxt.get("bua_an") == "toi" and gap < 100:
            index += 1
            continue
        cursor_h, cursor_m = map(int, current["ket_thuc"].split(":"))
        cursor = day_start.replace(hour=cursor_h, minute=cursor_m)
        travel_out = travel_minutes(prev_place, prev_place)  # noop placeholder
        del travel_out
        anchor = (prev_place.lat, prev_place.lng)
        next_start = day_start.replace(
            hour=int(nxt["bat_dau"][:2]), minute=int(nxt["bat_dau"][3:5])
        )
        attempted_ids: set[str] = set()
        attempted_names: set[str] = set()
        candidate = None
        bounds = None
        while True:
            option = _choose_extra_sight(
                request,
                used_ids | scheduled_ids | attempted_ids,
                anchor,
                seed + index + len(slots),
                remaining_budget,
                scheduled_names | attempted_names,
            )
            if not option:
                break
            attempted_ids.add(option.id)
            if option_name := _place_name_key(option):
                attempted_names.add(option_name)
            travel = travel_minutes(prev_place, option)
            arrive = cursor + timedelta(minutes=travel)
            option_bounds = _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request
            ) or _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, relax=True
            )
            if not option_bounds:
                continue
            _start, option_end, _visit = option_bounds
            if option_end + timedelta(minutes=travel_minutes(option, next_place)) > next_start:
                continue
            candidate = option
            bounds = option_bounds
            break
        if not candidate or not bounds:
            index += 1
            continue
        start, end, _visit = bounds
        mo_ta, ghi_chu = _slot_copy(
            candidate, request, copy, llm_details_by_id.get(candidate.id), None, labels
        )
        image_url, image_credit = image_for(candidate)
        slot = {
            "bat_dau": start.strftime("%H:%M"),
            "ket_thuc": end.strftime("%H:%M"),
            "dia_diem_id": candidate.id,
            "ten_dia_diem": candidate.name,
            "loai": candidate.kind,
            "mo_ta": mo_ta,
            "chi_phi": candidate.cost * request.so_nguoi,
            "toa_do": {"lat": candidate.lat, "lng": candidate.lng},
            "nguon": candidate.source,
            "nguon_url": candidate.source_url,
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
        }
        slots.insert(index + 1, slot)
        scheduled_ids.add(candidate.id)
        used_ids.add(candidate.id)
        name_key = _place_name_key(candidate)
        if name_key:
            scheduled_names.add(name_key)
        remaining_budget -= candidate.cost
        extra_cost += candidate.cost * request.so_nguoi
        index += 2
    slots = _tighten_day_gaps(slots, day_end)
    return slots, extra_cost


def _schedule_stop(
    place: Place,
    meal_type: str | None,
    cursor: datetime,
    day_start: datetime,
    max_minutes: int,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_detail: dict | None,
    labels: dict[str, str],
) -> tuple[dict | None, datetime, int]:
    day_end = day_start + timedelta(minutes=max_minutes)
    bounds = _compute_slot_bounds(place, meal_type, cursor, day_start, day_end, request)
    if not bounds:
        return None, cursor, 0
    start, end, _visit = bounds
    mo_ta, ghi_chu = _slot_copy(place, request, copy, llm_detail, meal_type, labels)
    image_url, image_credit = image_for(place)
    slot = {
        "bat_dau": start.strftime("%H:%M"),
        "ket_thuc": end.strftime("%H:%M"),
        "dia_diem_id": place.id,
        "ten_dia_diem": place.name,
        "loai": place.kind,
        "mo_ta": mo_ta,
        "chi_phi": place.cost * request.so_nguoi,
        "toa_do": {"lat": place.lat, "lng": place.lng},
        "nguon": place.source,
        "nguon_url": place.source_url,
        "anh": image_url,
        "anh_nguon": image_credit,
        "ghi_chu": ghi_chu,
    }
    if meal_type:
        slot["bua_an"] = meal_type
        slot["nhan_bua"] = labels[meal_type]
    return slot, end, place.cost * request.so_nguoi


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
    wants_coffee = _wants_coffee(request)
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
        and not (p.kind == "cafe" and not wants_coffee)
    ]
    ranked = sorted(
        candidates,
        key=lambda p: (
            -_intent_score(p, profiles),
            -int(p.kind in SIGHT_KINDS),
            -int(p.kind in {"dia_danh", "bao_tang"}),
            -int(p.source == "curated"),
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
        count, _, _ = LIMITS[request.thoi_luong]
        keep = max(count - len(highlights), 0)
        pinned = intent_matches[: max(min(keep, 3), 1)]
        pool = intent_matches[len(pinned):] + other_matches
        rng = random.Random(seed)
        shuffled_pool = pool[:]
        rng.shuffle(shuffled_pool)
        ordered = pinned + shuffled_pool
        return highlights + [place for place in ordered if place.id not in highlight_ids]
    offset = seed % len(quality_pool)
    ordered = quality_pool[offset:] + quality_pool[:offset]
    return highlights + [place for place in ordered if place.id not in highlight_ids]


def validate_plan(plan: dict, trusted_ids: set[str], request: PlanRequest | None = None) -> list[str]:
    errors: list[str] = []
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    thoi_luong = (request.thoi_luong if request else plan.get("thoi_luong")) or "ca_ngay"
    min_slots = _min_plan_slots(thoi_luong) if thoi_luong in LIMITS else 4
    max_slots = _max_plan_slots(thoi_luong) if thoi_luong in LIMITS else 10
    if not min_slots <= len(slots) <= max_slots:
        errors.append(f"Kế hoạch phải có {min_slots}–{max_slots} địa điểm")
    if any(slot.get("dia_diem_id") not in trusted_ids for slot in slots):
        errors.append("Có địa điểm ngoài danh sách tin cậy")
    place_ids = [slot.get("dia_diem_id") for slot in slots]
    if len(place_ids) != len(set(place_ids)):
        errors.append("Kế hoạch chứa địa điểm trùng lặp")
    by_id = {place.id: place for place in PLACES}
    name_keys = [
        _place_name_key(by_id[slot_id])
        for slot_id in place_ids
        if isinstance(slot_id, str) and slot_id in by_id
    ]
    if len(name_keys) != len(set(name_keys)):
        errors.append("Kế hoạch chứa địa điểm trùng tên")
    for day in plan.get("ngay", []):
        previous_end = "00:00"
        previous_place: Place | None = None
        for slot in day.get("khoang_gio", []):
            place = by_id.get(slot.get("dia_diem_id"))
            if slot["bat_dau"] < previous_end or slot["bat_dau"] >= slot["ket_thuc"]:
                errors.append(f"Khung giờ không tuần tự: {slot['dia_diem_id']}")
            if place:
                open_hour, close_hour = _effective_hours(place)
                if not (
                    f"{open_hour:02d}:00" <= slot["bat_dau"]
                    and slot["ket_thuc"] <= f"{close_hour:02d}:00"
                ):
                    errors.append(f"Ngoài giờ mở cửa: {slot['dia_diem_id']}")
            if previous_place and place:
                ph, pm = map(int, previous_end.split(":"))
                sh, sm = map(int, slot["bat_dau"].split(":"))
                gap = (sh * 60 + sm) - (ph * 60 + pm)
                need = travel_minutes(previous_place, place)
                if gap < need:
                    errors.append(
                        f"Không đủ thời gian di chuyển: {previous_place.id} → {place.id}"
                    )
            previous_end = slot["ket_thuc"]
            previous_place = place
    if request and plan.get("chi_phi_moi_nguoi", 0) > request.ngan_sach:
        errors.append("Kế hoạch vượt ngân sách")
    return errors


def _select_within_budget(candidates: list[Place], count: int, budget_per_person: int) -> list[Place]:
    selected: list[Place] = []
    spent = 0
    used_ids: set[str] = set()
    used_names: set[str] = set()
    for place in _dedupe_places(candidates):
        name_key = _place_name_key(place)
        if place.id in used_ids or name_key in used_names:
            continue
        if spent + place.cost <= budget_per_person:
            selected.append(place)
            spent += place.cost
            used_ids.add(place.id)
            if name_key:
                used_names.add(name_key)
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
    selected: list[Place] = []
    used_names: set[str] = set()
    for place_id in selected_ids:
        place = by_id.get(place_id)
        if not place:
            continue
        name_key = _place_name_key(place)
        if place.id in {item.id for item in selected} or (name_key and name_key in used_names):
            continue
        selected.append(place)
        if name_key:
            used_names.add(name_key)
        if len(selected) == count:
            break
    if len(selected) != count:
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
    seen_names: set[str] = set()
    origin = (request.location.lat, request.location.lng)
    for item in suggestions:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        place = verify_place_name(name.strip(), origin)
        if not place or place.id in seen or place.cost > request.ngan_sach:
            continue
        name_key = _place_name_key(place)
        if name_key and name_key in seen_names:
            continue
        selected.append(place)
        details_by_id[place.id] = item
        seen.add(place.id)
        if name_key:
            seen_names.add(name_key)
        if len(selected) == count:
            break
    if len(selected) < count:
        for place in _dedupe_places(candidates):
            if place.id in seen or place.cost > request.ngan_sach:
                continue
            name_key = _place_name_key(place)
            if name_key and name_key in seen_names:
                continue
            selected.append(place)
            seen.add(place.id)
            if name_key:
                seen_names.add(name_key)
            if len(selected) == count:
                break
    if len(selected) != count or sum(place.cost for place in selected) > request.ngan_sach:
        return None
    return selected, details_by_id


def _join_sentences(parts: list[str], limit: int = 700) -> str:
    text = " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    return text[:limit].rstrip()


def _fallback_slot_copy(
    place: Place,
    request: PlanRequest,
    copy: tuple[str, ...],
    meal_type: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    tags = set(place.tags)
    meal_prefix = ""
    if meal_type and labels:
        meal_prefix = f"{labels[meal_type]} tại {place.name}: "
    if place.kind == "cafe" or {"cafe", "coffee", "chill", "view_dep"}.intersection(tags):
        activity = "Dành thời gian nghỉ chân, gọi một món đặc trưng và ngắm nhịp phố xung quanh thay vì chỉ ghé qua cho có điểm."
        tip = "Nên chọn bàn có view tốt hoặc hỏi nhân viên món được gọi nhiều nhất; nếu quán đông, giữ nhịp linh hoạt để không trễ điểm tiếp theo."
    elif _is_dining_place(place) or {"am_thuc", "an_vat", "local"}.intersection(tags):
        if meal_type == "trua":
            activity = "Dừng chân ăn trưa với các món đặc sản địa phương — phở, bún, cơm hoặc các quán bình dân được người Hà Nội hay ghé."
            tip = "Nên đến trước 12h để tránh đông; gọi vài món chia sẻ nếu đi từ hai người trở lên để thử nhiều hương vị hơn."
        elif meal_type == "nghi":
            activity = "Nghỉ chân tránh nắng giữa trưa: ngồi quán mát, uống gì đó nhẹ và lấy sức trước khi đi tiếp buổi chiều."
            tip = "Khung 12h30–14h30 thường oi bức; nghỉ 40–60 phút giúp lịch chiều đỡ trống và dễ chịu hơn."
        elif meal_type == "dem":
            activity = "Buổi tối khám phá không khí Hà Nội: phố cổ, chợ đêm hoặc hồ Gươm về đêm sau bữa tối."
            tip = "Nên đi sau 19h khi đèn lên và khu vực đông vui hơn; giữ đồ gọn nếu đi chợ đêm."
        elif meal_type == "toi":
            activity = "Buổi tối thưởng thức ẩm thực Hà Nội — có thể là bún chả, lẩu, nướng hoặc các món đường phố ở khu phố cổ."
            tip = "Buổi tối khu phố cổ và Tạ Hiện thường đông; đặt bàn trước hoặc đến khoảng 18h30–19h nếu muốn ngồi thoải mái."
        elif meal_type == "sang":
            activity = "Bắt đầu ngày với bữa sáng Hà Nội — phở, bánh mì, xôi hoặc cà phê sữa đá."
            tip = "Quán sáng thường đông 7h30–9h; gọi món nhanh và ăn tại chỗ để kịp lịch tham quan."
        else:
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
    guidance = _guidance(place)
    if guidance and guidance.tip and not meal_type:
        tip = guidance.tip
    description = _join_sentences(
        [
            meal_prefix + f"{place.name} ở khu {place.area} được xếp vào lịch vì phù hợp với yêu cầu “{request.context}”."
            if not meal_prefix
            else meal_prefix + f"Quán nằm ở khu {place.area}, phù hợp với hành trình “{request.context}”.",
            activity,
            "Điểm này cũng giúp tuyến đi bớt rời rạc vì có thể nối tiếp các điểm gần đó trong cùng khu vực."
            if not meal_type
            else "Quán được chọn gần các điểm tham quan trong ngày để tiết kiệm thời gian di chuyển.",
        ],
        limit=850,
    )
    return description, tip


def _slot_copy(
    place: Place,
    request: PlanRequest,
    copy: tuple[str, ...],
    llm_detail: dict | None,
    meal_type: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[str, str]:
    if not llm_detail:
        return _fallback_slot_copy(place, request, copy, meal_type, labels)
    why = llm_detail.get("why")
    activity = llm_detail.get("activity") or llm_detail.get("what_to_do") or llm_detail.get("experience")
    tip = llm_detail.get("tip") or llm_detail.get("local_tip")
    meal = llm_detail.get("meal") or llm_detail.get("food")
    transport = llm_detail.get("transport") or llm_detail.get("move")
    meal_label = labels.get(meal_type, "") if meal_type and labels else ""
    description = _join_sentences(
        [
            f"{meal_label} tại {place.name} ({place.area})." if meal_label else f"{place.name} ({place.area}) phù hợp với yêu cầu “{request.context}”.",
            str(why) if isinstance(why, str) else "",
            str(activity) if isinstance(activity, str) else "",
            f"Gợi ý món: {meal}." if isinstance(meal, str) and meal.strip() else "",
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
    morning = [place for place in places if _is_morning_only(place)]
    evening = [
        place
        for place in places
        if place not in morning
        and (
            _effective_hours(place)[0] >= 17
            or "nightlife" in place.tags
            or "cho_dem" in place.tags
        )
    ]
    outdoor = [
        place
        for place in places
        if place not in morning and place not in evening and _is_outdoor_place(place)
    ]
    flexible = [
        place
        for place in places
        if place not in morning and place not in evening and place not in outdoor
    ]

    def near(items: list[Place], from_point: tuple[float, float]) -> list[Place]:
        return sorted(
            items,
            key=lambda place: (
                haversine_km(from_point[0], from_point[1], place.lat, place.lng),
                place.id,
            ),
        )

    route: list[Place] = []
    cursor = origin
    for group in (morning, flexible, outdoor, evening):
        if not group:
            continue
        ordered = near(group, cursor)
        if len(ordered) > 2:
            ordered = two_opt(nearest_neighbor(ordered, cursor))
        route.extend(ordered)
        cursor = (ordered[-1].lat, ordered[-1].lng)
    return route


def _select_sight_places(
    candidates: list[Place],
    sight_count: int,
    request: PlanRequest,
) -> tuple[list[Place], dict[str, dict]]:
    sight_pool = _dedupe_places(_sight_candidates(candidates, request))
    llm_details_by_id: dict[str, dict] = {}
    allow_cafe = _wants_coffee(request)
    llm_first = _select_llm_first_places(sight_pool, sight_count, request)
    if llm_first:
        chosen, llm_details_by_id = llm_first
        chosen = _dedupe_places(
            [
                place
                for place in chosen
                if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
            ]
        )
        if len(chosen) >= min(sight_count, 2):
            return chosen[:sight_count], llm_details_by_id
    chosen = (
        _select_ai_places(sight_pool, sight_count, request)
        or _select_within_budget(sight_pool, sight_count, request.ngan_sach)
    )
    chosen = [
        place
        for place in chosen
        if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
    ]
    return _dedupe_places(chosen)[:sight_count], llm_details_by_id


def build_plan(request: PlanRequest, excluded: set[str] | None = None) -> dict:
    if not DISTANCE_METADATA.get("loaded") or not DISTANCE_METADATA.get("updated_at"):
        raise PipelineUnavailable("Hệ thống đang khởi tạo bản đồ, vui lòng quay lại sau")
    count, max_minutes, number_of_days = LIMITS[request.thoi_luong]
    meals_per_day = _meals_per_day(request.thoi_luong)
    meals_total = len(meals_per_day) * number_of_days
    sight_total = _sight_total(count, meals_total, request.thoi_luong)
    max_slots = _max_plan_slots(request.thoi_luong)
    min_slots = _min_plan_slots(request.thoi_luong)
    candidates = choose_candidates(request, excluded)
    sight_chosen, llm_details_by_id = _select_sight_places(candidates, sight_total, request)
    sight_chosen = _dedupe_places(sight_chosen)
    if len(sight_chosen) < min(sight_total, 2):
        raise PipelineUnavailable("Không đủ địa điểm tham quan tin cậy trong ngân sách")

    origin = (request.location.lat, request.location.lng)
    ordered_sights = _ordered_route(sight_chosen, origin)
    split_index = (len(ordered_sights) + 1) // 2
    sight_by_day = (
        [ordered_sights]
        if number_of_days == 1
        else [ordered_sights[:split_index], ordered_sights[split_index:]]
    )

    trip_date = request.ngay_di or datetime.now(UTC).date()
    copy = COPY[request.ngon_ngu]
    labels = _meal_labels(request.ngon_ngu)
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

    seed = _request_seed(request)
    used_ids = {place.id for place in sight_chosen} | (excluded or set())
    remaining_budget = request.ngan_sach - sum(place.cost for place in sight_chosen)
    meal_places: list[Place] = []
    days: list[dict] = []
    total_cost = 0
    scheduled_ids: set[str] = set()
    scheduled_names: set[str] = set()
    used_names = {
        name_key
        for place in sight_chosen
        if (name_key := _place_name_key(place))
    }

    for day_index, day_sights in enumerate(sight_by_day, start=1):
        day_meals = _pick_day_meals(
            request,
            day_sights,
            used_ids,
            remaining_budget,
            seed + day_index,
            used_names,
        )
        meal_places.extend(place for _, place in day_meals)
        for _, place in day_meals:
            remaining_budget -= place.cost
        route_stops = _build_day_route(
            request,
            day_sights,
            day_meals,
            used_ids,
            remaining_budget,
            seed + day_index,
            used_names,
        )
        refreshment = [
            place
            for place, meal_type in route_stops
            if meal_type is None and place.id not in {sight.id for sight in day_sights}
        ]
        for place in refreshment:
            used_ids.add(place.id)
            remaining_budget -= place.cost
            meal_places.append(place)
        day_start = datetime.combine(
            trip_date + timedelta(days=day_index - 1),
            datetime.min.time(),
        ).replace(hour=8)
        slots, day_cost = _pack_day_slots(
            route_stops,
            day_start,
            max_minutes,
            request,
            copy,
            llm_details_by_id,
            labels,
            scheduled_ids,
            scheduled_names,
            max_slots=max_slots,
        )
        slots, fill_cost = _backfill_day_gaps(
            slots,
            day_start,
            max_minutes,
            request,
            copy,
            llm_details_by_id,
            labels,
            scheduled_ids,
            scheduled_names,
            used_ids,
            remaining_budget,
            seed + day_index,
            max_slots,
        )
        total_cost += day_cost + fill_cost
        remaining_budget -= fill_cost // max(request.so_nguoi, 1)
        min_day_slots = 4 if number_of_days == 1 else 3
        if len(slots) < min_day_slots:
            raise PipelineUnavailable("Không đủ thời gian để xếp đủ địa điểm trong ngày")
        days.append({"thu_tu": day_index, "nhan_de": copy[5].format(day=day_index), "khoang_gio": slots})

    all_slots = [slot for day in days for slot in day["khoang_gio"]]
    if not min_slots <= len(all_slots) <= max_slots:
        raise PipelineUnavailable("Không đủ thời gian để xếp đủ địa điểm trong ngày")

    scheduled_ids = {slot["dia_diem_id"] for day in days for slot in day["khoang_gio"]}
    trusted_ids = scheduled_ids | {place.id for place in candidates} | {place.id for place in PLACES}
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
