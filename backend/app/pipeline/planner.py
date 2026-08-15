import hashlib
import random
import re
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import httpx

from app.config import settings
from app.data import DISTANCE_METADATA, PLACES, Place, image_for, source_for
from app.pipeline.visit_guidance import VisitGuidance, guidance_for
from app.pipeline.routing import (
    TRAVEL_ESTIMATE_POLICY,
    estimate_travel,
    haversine_km,
    is_routable,
    nearest_neighbor,
    travel_minutes,
    travel_matrix,
    two_opt,
)
from app.pipeline.cp_sat_solver import (
    optimize_day_schedule_with_cp_sat,
    optimize_order_with_cp_sat,
    select_places_with_cp_sat,
    verify_fixed_schedule_with_cp_sat,
)
from app.schemas import PlanRequest
from app.pipeline.solar import sunset_for_date
from app.services.ai import ai_adapter
from app.services.osm_verify import verify_place_name
from app.services.quality_benchmarks import REQUIRED_BASELINES
from app.services.store import store
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
SIGHT_KINDS = frozenset({"dia_danh", "bao_tang", "cong_vien", "cho", "di_tich", "bai_bien", "hang_dong", "nui", "den_chua", "giai_tri"})
# (start_hour, start_min, end_hour, end_min) — khung giờ ăn / nghỉ mục tiêu
MEAL_WINDOWS: dict[str, tuple[int, int, int, int]] = {
    "sang": (7, 30, 9, 30),
    "trua": (11, 30, 13, 30),
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
DESTINATION_RADIUS_KM = 45.0
DURATION_FALLBACKS: dict[str, tuple[int, int]] = {
    "bao_tang": (90, 180),
    "dia_danh": (45, 120),
    "cong_vien": (45, 120),
    "cho": (45, 90),
    "cafe": (45, 90),
    "nha_hang": (60, 90),
    "quan_an": (45, 75),
}
DATA_STALENESS_POLICY = {
    "gio_mo_cua": {"max_age_days": 30, "refresh": "kiem_tra_lai truoc khi xep lich"},
    "gia": {"max_age_days": 90, "refresh": "lam moi khi dia diem duoc goi trong lich"},
    "trang_thai_hoat_dong": {"max_age_days": 7, "refresh": "chan neu co dau hieu dong cua"},
    "thoi_luong": {"max_age_days": 180, "refresh": "hieu chinh bang phan hoi giu bo va thuc dia"},
    "di_chuyen": {"max_age_days": 30, "refresh": "ban thu nghiem dung duong thang co bu sai so"},
}
GENERIC_DESTINATION_NAMES = {
    "du lich",
    "tham quan",
    "di choi",
    "check in",
    "checkin",
}
DESTINATION_NAME_PREFIXES = (
    "vinh ",
    "tp ",
    "thanh pho ",
    "khu du lich ",
    "dao ",
    "bien ",
)

FOCUS_DESTINATIONS: dict[str, dict[str, object]] = {
    "ha_noi": {
        "label": "Hà Nội",
        "lat": 21.0285,
        "lng": 105.8542,
        "aliases": {"ha noi", "hanoi", "thu do"},
    },
    "tp_hcm": {
        "label": "TP.HCM",
        "lat": 10.7769,
        "lng": 106.7009,
        "aliases": {"tp hcm", "tp.hcm", "ho chi minh", "sai gon", "saigon", "thanh pho ho chi minh"},
    },
    "ha_long": {
        "label": "Hạ Long",
        "lat": 20.9712,
        "lng": 107.0448,
        "aliases": {"ha long", "vinh ha long", "quang ninh"},
    },
    "da_nang": {
        "label": "Đà Nẵng",
        "lat": 16.0544,
        "lng": 108.2022,
        "aliases": {"da nang", "danang", "thanh pho da nang"},
    },
    "hoi_an": {
        "label": "Hội An",
        "lat": 15.8801,
        "lng": 108.3380,
        "aliases": {"hoi an", "pho co hoi an"},
    },
    "nha_trang": {
        "label": "Nha Trang",
        "lat": 12.2388,
        "lng": 109.1967,
        "aliases": {"nha trang", "khanh hoa"},
    },
    "phu_quoc": {
        "label": "Phú Quốc",
        "lat": 10.2899,
        "lng": 103.9840,
        "aliases": {"phu quoc", "dao phu quoc"},
    },
    "sa_pa": {
        "label": "Sa Pa",
        "lat": 22.3364,
        "lng": 103.8438,
        "aliases": {"sa pa", "sapa"},
    },
}

VIETNAM_TRAFFIC_PEAK_POLICY = {
    "nguon": "quy_tac_noi_bo_gio_cao_diem_do_thi_viet_nam",
    "trang_thai": "heuristic_no_live_traffic",
    "khung_gio": [
        {"ten": "cao_diem_sang", "tu": "07:00", "den": "09:00"},
        {"ten": "cao_diem_chieu", "tu": "16:30", "den": "19:00"},
    ],
    "ghi_chu": "Dùng để ghi/né rủi ro giờ cao điểm khi chưa có provider traffic thật; không thay thế dữ liệu giao thông production.",
}

SEASONAL_TOURISM_POLICY: dict[str, dict[str, object]] = {
    "ha_noi": {
        "best_months": (3, 4, 10, 11),
        "caution_months": (6, 7, 8, 12, 1, 2),
        "festival_notes": ("Tết Nguyên đán", "2/9", "mùa thu Hà Nội"),
    },
    "tp_hcm": {
        "best_months": (12, 1, 2, 3, 4),
        "caution_months": (5, 6, 7, 8, 9, 10),
        "festival_notes": ("Tết Nguyên đán", "30/4-1/5", "lễ hội cuối năm"),
    },
    "ha_long": {
        "best_months": (3, 4, 10, 11),
        "caution_months": (6, 7, 8, 9),
        "festival_notes": ("mùa hè du lịch biển", "lễ hội Hạ Long"),
    },
    "da_nang": {
        "best_months": (3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11, 12),
        "festival_notes": ("mùa biển", "lễ hội pháo hoa quốc tế Đà Nẵng"),
    },
    "hoi_an": {
        "best_months": (2, 3, 4, 5, 6, 7, 8),
        "caution_months": (9, 10, 11),
        "festival_notes": ("đêm phố cổ", "rằm âm lịch"),
    },
    "nha_trang": {
        "best_months": (2, 3, 4, 5, 6, 7, 8),
        "caution_months": (10, 11, 12),
        "festival_notes": ("mùa biển", "Festival Biển Nha Trang"),
    },
    "phu_quoc": {
        "best_months": (11, 12, 1, 2, 3, 4),
        "caution_months": (6, 7, 8, 9, 10),
        "festival_notes": ("mùa biển khô", "cao điểm cuối năm"),
    },
    "sa_pa": {
        "best_months": (3, 4, 5, 9, 10, 11),
        "caution_months": (12, 1, 2, 6, 7, 8),
        "festival_notes": ("mùa lúa chín", "mùa săn mây"),
    },
}

EVENING_PLACE_IDS = (
    "osm-node-4489385889",
    "osm-relation-7112202",
    "osm-way-765597030",
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
        "terms": {"ha_noi", "hanoi", "pho_co"},
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
        "terms": {"buoi_toi", "ban_dem", "dem", "cho_dem", "night", "evening", "nightlife"},
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
    "osm-way-37625751",
    "curated-ho-tay",
    "curated-pho-co-ha-noi",
    "van-mieu",
    "chua-tran-quoc",
    "bao-tang-phu-nu",
    "long-bien",
)
HANOI_NIGHT_IDS = ("osm-node-4489385889", "osm-relation-7112202", "osm-way-765597030")
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
    "travel",
    "media",
    "tour",
    "tourism",
}
GENERIC_PLACE_NAME_KEYS = {"du lich", "tham quan", "check in", "checkin"}
CLOSED_PLACE_HINTS = {"closed", "dong cua", "ngung hoat dong", "tam dong"}
LOW_VALUE_TOURIST_NAME_KEYS = {
    "7 wonders",
    "hard to climb",
    "hero statue",
    "louvre",
    "nha trang",
    "pont main",
    "queen cobra",
    "rao chan",
    "saturday option",
    "small waterfall",
}
FAMOUS_TOURIST_NAME_HINTS = {
    "ba na",
    "bai bien my khe",
    "bao tang cham",
    "bao tang da nang",
    "bao tang nghe thuat dieu khac cham",
    "cau rong",
    "cau song han",
    "cau vang",
    "cho con",
    "chua cau",
    "chua long son",
    "de hai van",
    "dinh ban co",
    "hai van quan",
    "hon chong",
    "hon mun",
    "hon tam",
    "hoi an",
    "i-resort",
    "lang co",
    "lang da my nghe non nuoc",
    "my khe",
    "nha tho da nha trang",
    "nha trang",
    "ngu hanh son",
    "nui son tra",
    "pho co hoi an",
    "thap ba ponagar",
    "thap po nagar",
    "vien hai duong hoc",
    "vinpearl",
    "vinwonders",
    "vinwonders nha trang",
    "vinh nha trang",
    "son tra",
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

SEMANTIC_TAG_ALIASES = {
    "tre_em": {"tre_em", "tre", "em", "gia_dinh", "gia", "dinh", "family", "kids"},
    "gia_re": {"gia_re", "tiet_kiem", "binh_dan", "cheap", "budget"},
    "yen_tinh": {"yen_tinh", "chill", "healing", "chua", "lanh", "chua_lanh", "thu_gian"},
    "checkin": {"checkin", "song_ao", "anh_dep", "view_dep"},
    "ngoai_troi": {"ngoai_troi", "bien", "nui", "di_bo", "outdoor"},
    "trong_nha": {"trong_nha", "bao_tang", "museum", "indoor"},
    "am_thuc": {"an_ngon", "am_thuc", "hai_san", "food", "restaurant"},
}

VIETNAM_HOLIDAY_WINDOWS = (
    ("tet_nguyen_dan", (1, 20), (2, 20), "Tết Nguyên đán: giờ mở cửa có thể đổi theo từng năm."),
    ("giai_phong_quoc_te_lao_dong", (4, 30), (5, 1), "Dịp 30/4 và 1/5: điểm du lịch có thể đông và đổi giờ phục vụ."),
    ("quoc_khanh", (9, 1), (9, 3), "Dịp Quốc khánh 2/9: điểm du lịch có thể đông và đổi giờ phục vụ."),
)


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


@lru_cache(maxsize=1024)
def _destination_context_from_text(context: str, lat: float, lng: float) -> tuple[float, float, str | None]:
    if not context:
        return lat, lng, None
    for destination in FOCUS_DESTINATIONS.values():
        aliases = destination["aliases"]
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", context) for alias in aliases):
            return float(destination["lat"]), float(destination["lng"]), str(destination["label"])
    best: tuple[int, float, Place] | None = None
    for place in PLACES:
        if _looks_like_non_travel_business(place) or _looks_closed(place):
            continue
        name = _ascii_fold(place.name).casefold()
        area = _ascii_fold(place.area).casefold()
        if name in GENERIC_DESTINATION_NAMES:
            continue
        name_aliases = {name}
        for prefix in DESTINATION_NAME_PREFIXES:
            if name.startswith(prefix):
                name_aliases.add(name.removeprefix(prefix).strip())
        name_match = any(alias and len(alias) >= 4 and alias in context for alias in name_aliases)
        area_match = bool(
            area
            and area not in {"viet nam", "vietnam"}
            and len(area) >= 4
            and area in context
        )
        if not name_match and not area_match:
            continue
        score = 0
        if name_match:
            score += 12
        if area_match:
            score += 7
        if place.kind in SIGHT_KINDS or place.kind in {"di_tich", "bai_bien", "hang_dong", "nui"}:
            score += 6
        if place.kind in DINING_KINDS or place.kind in {"cafe", "khach_san", "nha_nghi", "homestay"}:
            score -= 7
        if place.source == "curated":
            score += 2
        distance = haversine_km(lat, lng, place.lat, place.lng)
        candidate = (score, -distance, place)
        if best is None or candidate > best:
            best = candidate
    if not best or best[0] < 6:
        return lat, lng, None
    place = best[2]
    area_key = _ascii_fold(place.area).casefold()
    label = place.area if area_key not in {"viet nam", "vietnam"} else place.name
    return place.lat, place.lng, label or place.name


def _destination_context(request: PlanRequest) -> tuple[float, float, str | None]:
    """Infer the trip center from the user's text instead of assuming Hanoi.

    The frontend can send a default coordinate, so destination intent is
    recovered from the prompt first. Known focus cities are resolved before
    catalog matching to prevent brand-name false positives like "Hạ Long" food
    chains in Hà Nội.
    """
    context = _ascii_fold(request.context).casefold()
    return _destination_context_from_text(
        context,
        round(_lodging_anchor(request)[0], 4),
        round(_lodging_anchor(request)[1], 4),
    )


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


def _semantic_tags_from_context(tags: set[str]) -> set[str]:
    semantic: set[str] = set()
    for label, aliases in SEMANTIC_TAG_ALIASES.items():
        if tags.intersection(aliases):
            semantic.add(label)
    return semantic


def _disliked_profiles(context: str) -> set[str]:
    plain = _ascii_fold(context)
    dislikes: set[str] = set()
    for profile_name, profile in INTENT_PROFILES.items():
        for term in profile["terms"]:
            term_text = term.replace("_", " ")
            if f"khong thich {term_text}" in plain or f"tranh {term_text}" in plain:
                dislikes.add(profile_name)
    return dislikes


def _field(value, source: str, evidence: str | None = None, status: str = "present") -> dict:
    return {
        "gia_tri": value,
        "nguon": source,
        "bang_chung": evidence,
        "trang_thai": status,
    }


def _safe_ai_intent(context: str, locale: str) -> tuple[dict, str]:
    extractor = getattr(ai_adapter, "extract_request_intent", None)
    if not callable(extractor):
        return {}, "rule_based_fallback"
    try:
        payload = extractor(context, locale)
    except RuntimeError:
        return {}, "rule_based_fallback"
    return payload if isinstance(payload, dict) else {}, "ai_extracted"


def _ai_text_field(payload: dict, key: str) -> tuple[str | None, str | None]:
    item = payload.get(key)
    if not isinstance(item, dict):
        return None, None
    value = item.get("value")
    evidence = item.get("evidence")
    return (
        value.strip() if isinstance(value, str) and value.strip() else None,
        evidence.strip() if isinstance(evidence, str) and evidence.strip() else None,
    )


def _ai_list(payload: dict, key: str) -> list[dict]:
    values = payload.get(key)
    if not isinstance(values, list):
        return []
    result: list[dict] = []
    for item in values[:12]:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        evidence = item.get("evidence")
        result.append(
            _field(
                value.strip()[:80],
                "ai_extracted",
                evidence.strip()[:160] if isinstance(evidence, str) and evidence.strip() else None,
            )
        )
    return result


def _rule_preference_fields(tags: set[str]) -> list[dict]:
    fields: list[dict] = []
    for profile_name, profile in INTENT_PROFILES.items():
        if tags.intersection(profile["terms"]):
            fields.append(_field(profile_name, "rule_based_context", profile_name))
    return fields


def _rule_dislike_fields(context: str) -> list[dict]:
    plain_context = " ".join(context.split())
    fields = [
        _field(profile, "rule_based_context", profile)
        for profile in sorted(_disliked_profiles(context))
    ]
    for match in re.finditer(r"(?:không thích|không muốn|tránh)\s+([^,.。;]{2,60})", plain_context, re.IGNORECASE):
        value = match.group(1).strip()
        if value:
            fields.append(_field(value[:80], "rule_based_context", match.group(0)[:160]))
    return fields


def _dedupe_field_values(fields: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for field in fields:
        key = _ascii_fold(str(field.get("gia_tri", "")))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(field)
    return result


def _request_understanding(request: PlanRequest) -> dict:
    tags = relevant_tags(request.context)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    ai_payload, extraction_source = _safe_ai_intent(request.context, request.ngon_ngu)
    ai_destination, ai_destination_evidence = _ai_text_field(ai_payload, "destination_text")
    destination_value = destination_label or ai_destination
    destination_source = (
        "doi_chieu_catalog"
        if destination_label
        else "ai_extracted"
        if ai_destination
        else "missing"
    )
    max_places_match = re.search(r"(?:toi da|khong qua|qua)\s+(\d{1,2})\s+(?:cho|diem|dia diem)", _ascii_fold(request.context))
    constraints = [
        _field(request.thoi_luong, "form_chat", None),
        _field(request.so_nguoi, "form_chat", None),
        _field(request.ngan_sach, "form_chat", None),
    ]
    if max_places_match:
        constraints.append(_field(int(max_places_match.group(1)), "rule_based_context", max_places_match.group(0)))
    constraints.extend(_ai_list(ai_payload, "constraints"))
    dislikes = [*_ai_list(ai_payload, "dislikes"), *_rule_dislike_fields(request.context)]
    missing_required = []
    if not destination_value:
        missing_required.append("diem_den")
    return {
        "schema_version": "input-understanding-v1",
        "context_goc": request.context,
        "diem_den": _field(
            {
                "ten": destination_value,
                "toa_do": {"lat": destination_lat, "lng": destination_lng} if destination_value else None,
            },
            destination_source,
            destination_label or ai_destination_evidence,
            "present" if destination_value else "missing",
        ),
        "so_ngay": _field(1 if request.thoi_luong != "nhieu_ngay" else 2, "form_chat", request.thoi_luong),
        "so_nguoi": _field(request.so_nguoi, "form_chat", None),
        "ngan_sach": _field(request.ngan_sach, "form_chat", None),
        "thoi_luong": _field(request.thoi_luong, "form_chat", None),
        "so_thich": _dedupe_field_values([*_ai_list(ai_payload, "preferences"), *_rule_preference_fields(tags)]),
        "khong_thich": _dedupe_field_values(dislikes),
        "rang_buoc": _dedupe_field_values(constraints),
        "muc_bat_buoc": _dedupe_field_values(_ai_list(ai_payload, "must_visit")),
        "tag_ngu_nghia": _field(sorted(_semantic_tags_from_context(tags)), "rule_based_context", None),
        "bat_buoc_thieu": missing_required,
        "hanh_dong_tiep_theo": (
            "hoi_lai_nguoi_dung" if missing_required else "du_dieu_kien_lap_lich"
        ),
        "xuat_xu": {
            "form_chat": ["thoi_luong", "so_ngay", "so_nguoi", "ngan_sach"],
            "ai_extracted": ["diem_den", "so_thich", "khong_thich", "rang_buoc", "muc_bat_buoc"]
            if extraction_source == "ai_extracted"
            else [],
            "rule_based_context": ["diem_den", "tag_ngu_nghia", "so_thich", "khong_thich", "rang_buoc"],
        },
        "nguon_boc_tach_dinh_tinh": extraction_source,
        "ghi_chu": "Định lượng lấy từ form. Định tính lấy từ AI nếu có cấu hình và qua kiểm tra kiểu dữ liệu; thiếu mục bắt buộc thì đánh dấu để hỏi lại, không tự bịa.",
    }


def missing_required_inputs(request: PlanRequest) -> dict:
    understanding = _request_understanding(request)
    missing = list(understanding.get("bat_buoc_thieu") or [])
    questions = {
        "diem_den": "Bạn muốn đi điểm đến/thành phố nào?",
    }
    return {
        "missing_fields": missing,
        "questions": [questions.get(field, f"Vui lòng bổ sung {field}") for field in missing],
        "understanding": understanding,
    }


def _distance_score(distance_km: float) -> int:
    if distance_km < 1:
        return 100
    if distance_km < 3:
        return 80
    if distance_km < 5:
        return 60
    if distance_km <= 10:
        return 40
    return 20


def _numeric_place_metric(place: Place, *names: str) -> float | None:
    for name in names:
        value = getattr(place, name, None)
        if isinstance(value, int | float):
            return float(value)
    return None


def _review_count_score(review_count: float | None) -> int:
    if review_count is None or review_count <= 0:
        return 20
    if review_count >= 1000:
        return 100
    if review_count >= 100:
        return 80
    if review_count >= 10:
        return 60
    return 40


def _ranking_evidence(
    place: Place,
    request: PlanRequest,
    tags: set[str],
    profiles: list[dict[str, set[str]]],
    destination_lat: float,
    destination_lng: float,
    behavior_profile: dict | None = None,
) -> dict:
    place_tags = set(place.tags)
    matched_profiles = 0
    for profile in profiles:
        if place.kind in profile["kinds"] or place_tags.intersection(profile["tags"]):
            matched_profiles += 1
    suitability = 50 if not profiles else int((matched_profiles / len(profiles)) * 100)
    semantic_matches = len(place_tags.intersection(_semantic_tags_from_context(tags)))
    suitability = min(100, suitability + semantic_matches * 5)
    disliked = _disliked_profiles(request.context)
    for profile_name in disliked:
        profile = INTENT_PROFILES[profile_name]
        if place.kind in profile["kinds"] or place_tags.intersection(profile["tags"]):
            suitability = max(0, suitability - 30)
    distance = haversine_km(destination_lat, destination_lng, place.lat, place.lng)
    open_hour, close_hour = _effective_hours(place)
    opening_score = 100 if 0 <= open_hour < close_hour <= 24 else 0
    rating_value = _numeric_place_metric(place, "rating", "diem_danh_gia", "google_rating")
    review_count = _numeric_place_metric(place, "review_count", "so_nhan_xet", "google_review_count")
    rating_score = (
        max(0, min(100, round((rating_value / 5) * 100)))
        if rating_value is not None and 0 <= rating_value <= 5
        else 40
    )
    review_score = _review_count_score(review_count)
    tag_weights = (behavior_profile or {}).get("tag_weights") if isinstance(behavior_profile, dict) else {}
    behavior_signal = 0
    if isinstance(tag_weights, dict):
        behavior_signal = sum(
            int(tag_weights.get(tag, 0))
            for tag in place_tags
            if isinstance(tag_weights.get(tag, 0), int)
        )
    weighted_components = [
        (30, suitability),
        (25, rating_score),
        (20, _distance_score(distance)),
        (15, opening_score),
        (10, review_score),
    ]
    total_weight = sum(weight for weight, _ in weighted_components)
    total = round(sum(weight * score for weight, score in weighted_components) / total_weight, 2)
    missing = []
    if rating_value is None:
        missing.append("rating")
    if review_count is None:
        missing.append("so_review")
    if not place.image_url and not image_for(place)[0]:
        missing.append("anh")
    return {
        "diem_tong": total,
        "thanh_phan": {
            "muc_phu_hop": suitability,
            "diem_danh_gia": rating_score,
            "vi_tri_khoang_cach": _distance_score(distance),
            "khop_gio_mo_cua": opening_score,
            "so_nhan_xet": review_score,
        },
        "ho_so_hanh_vi": {
            "schema_version": (behavior_profile or {}).get("schema_version"),
            "version": (behavior_profile or {}).get("version", 0),
            "tin_hieu_tag": behavior_signal,
            "gioi_han": "Hành vi người dùng được ghi riêng để điều chỉnh trọng số/tag trong giới hạn an toàn; công thức điểm phát hành vẫn giữ 5 tiêu chí cố định.",
        },
        "khoang_cach_km": round(distance, 2),
        "du_lieu_thuc_te": {
            "rating": rating_value,
            "so_nhan_xet": int(review_count) if review_count is not None else None,
        },
        "du_lieu_thieu": missing,
        "ghi_chu": "Rating thiếu dùng điểm dự phòng 40 và số nhận xét thiếu dùng 20 theo spec; dữ liệu thiếu vẫn được đánh dấu, không bịa giá trị thật.",
    }


def _holiday_note(trip_date) -> dict | None:
    month_day = (trip_date.month, trip_date.day)
    for code, start, end, note in VIETNAM_HOLIDAY_WINDOWS:
        if start <= month_day <= end:
            return {
                "ma": code,
                "ghi_chu": note,
                "nguon": "quy_tac_noi_bo_lich_nghi_le_viet_nam",
                "gio_mo_cua_can_xac_minh": True,
                "khong_dung_gio_thuong_lam_bang_chung_phat_hanh": code == "tet_nguyen_dan",
            }
    return None


def _holiday_hours_status(holiday: dict | None) -> dict | None:
    if not holiday:
        return None
    return {
        "ma": holiday.get("ma"),
        "ghi_chu": holiday.get("ghi_chu"),
        "nguon": holiday.get("nguon"),
        "gio_mo_cua_can_xac_minh": True,
        "trang_thai_xac_minh": (
            "holiday_hours_required_before_release"
            if holiday.get("khong_dung_gio_thuong_lam_bang_chung_phat_hanh")
            else "holiday_hours_warning"
        ),
    }


def _destination_key_from_label(label: str | None) -> str | None:
    if not label:
        return None
    normalized = _ascii_fold(label).casefold()
    for key, destination in FOCUS_DESTINATIONS.items():
        if _ascii_fold(str(destination["label"])).casefold() == normalized:
            return key
    return None


def _seasonal_context(destination_label: str | None, trip_date) -> dict:
    key = _destination_key_from_label(destination_label)
    policy = SEASONAL_TOURISM_POLICY.get(key or "")
    if not policy:
        return {
            "co_san": False,
            "nguon": "seasonal_tourism_policy_v1",
            "trang_thai": "no_focus_city_policy",
            "ghi_chu": "Chưa có policy mùa vụ nội bộ cho điểm đến này.",
        }
    month = trip_date.month
    best_months = tuple(policy["best_months"])
    caution_months = tuple(policy["caution_months"])
    status = "recommended_season" if month in best_months else "caution_season" if month in caution_months else "neutral_season"
    return {
        "co_san": True,
        "nguon": "seasonal_tourism_policy_v1",
        "trang_thai": status,
        "thang": month,
        "diem_den": destination_label,
        "thang_de_xuat": list(best_months),
        "thang_can_luu_y": list(caution_months),
        "ghi_chu_le_hoi": list(policy["festival_notes"]),
        "gioi_han": "Heuristic nội bộ theo thành phố; cần lịch sự kiện/nguồn chính thức theo năm trước phát hành.",
    }


def _is_sunset_suitable(place: Place) -> bool:
    return (
        bool({"view_dep", "ho_tay", "beach", "bien", "ngoai_troi", "song", "ho"}.intersection(place.tags))
        or place.kind in {"bai_bien", "nui", "dia_danh", "cong_vien"}
    ) and not _is_morning_only(place)


def _near_sunset(start: datetime, solar_context: dict | None) -> bool:
    sunset_minute = (solar_context or {}).get("hoang_hon_phut")
    if not isinstance(sunset_minute, int):
        return False
    start_minute = start.hour * 60 + start.minute
    return sunset_minute - 105 <= start_minute <= sunset_minute + 20


def _time_reason(
    place: Place,
    meal_type: str | None,
    start: datetime,
    weather: dict | None,
    solar_context: dict | None = None,
) -> str:
    if meal_type == "trua":
        return "Bữa trưa được giữ trong khung 11:30 đến 13:30."
    if meal_type == "toi":
        return "Bữa tối được giữ trong khung 18:00 đến 21:00."
    if _is_night_market(place):
        return "Chợ đêm được xếp sau 18:00."
    if _is_morning_only(place):
        return "Địa điểm này ưu tiên buổi sáng do giờ hoạt động hoặc guidance."
    if _is_sunset_suitable(place) and _near_sunset(start, solar_context):
        return "Địa điểm ngắm cảnh/ngoài trời được ưu tiên gần hoàng hôn theo tính toán thiên văn."
    if _is_outdoor_place(place) and _weather_discourages_midday_outdoor(weather):
        return "Địa điểm ngoài trời được tránh buổi trưa khi trời nóng hoặc mưa."
    guidance = _guidance(place)
    if guidance:
        return "Khung giờ dựa trên visit_guidance đã lưu."
    return "Khung giờ được chọn theo giờ mở cửa, thời lượng và tuyến di chuyển."


def _slot_evidence(
    place: Place,
    request: PlanRequest,
    start: datetime,
    meal_type: str | None,
    weather: dict | None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
) -> dict:
    tags = relevant_tags(request.context)
    profiles = _intent_profiles(tags)
    destination_lat, destination_lng, _ = _destination_context(request)
    open_hour, close_hour = _effective_hours(place)
    timing = {
        "ly_do": _time_reason(place, meal_type, start, weather, solar_context),
        "gio_mo_cua_hieu_luc": {"open": open_hour, "close": close_hour},
    }
    if solar_context and solar_context.get("co_san"):
        timing["thien_van"] = {
            "hoang_hon": solar_context.get("hoang_hon"),
            "nguon": solar_context.get("nguon"),
            "gan_hoang_hon": _is_sunset_suitable(place) and _near_sunset(start, solar_context),
        }
    return {
        "xep_hang": _ranking_evidence(
            place,
            request,
            tags,
            profiles,
            destination_lat,
            destination_lng,
            behavior_profile,
        ),
        "du_lieu": {
            "nguon": place.source,
            "nguon_url": source_for(place)[0],
            "co_toa_do": True,
            "co_gio_mo_cua": 0 <= open_hour < close_hour <= 24,
            "co_anh": bool(image_for(place)[0]),
        },
        "thoi_diem": timing,
    }


def _highlight_places(request: PlanRequest, excluded: set[str]) -> list[Place]:
    tags = relevant_tags(request.context)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    destination_key = _ascii_fold(destination_label or "").casefold()
    destination_is_hanoi = destination_key in {"ha noi", "hanoi"} or (
        destination_label is None and haversine_km(destination_lat, destination_lng, 21.0285, 105.8542) <= 20
    )
    explicit_anchor = tags.intersection({"ha_noi", "hanoi", "pho_co", "ho_guom", "ho_tay", "lang_bac", "ho_chi_minh", "ba_dinh"})
    wants_hanoi_highlights = bool(destination_is_hanoi and explicit_anchor and (destination_label is None or tags.intersection({"ha_noi", "hanoi", "pho_co"})))
    wants_night = bool(destination_is_hanoi and tags.intersection(INTENT_PROFILES["night"]["terms"]))
    by_id = {place.id: place for place in PLACES}
    if wants_night:
        place_ids = [
            "curated-ho-guom",
            "curated-ho-tay",
            "curated-pho-co-ha-noi",
            *HANOI_NIGHT_IDS,
            *((*HANOI_HIGHLIGHT_IDS,) if wants_hanoi_highlights else ()),
        ]
    else:
        place_ids = list(HANOI_HIGHLIGHT_IDS) if wants_hanoi_highlights else []
    return [
        place
        for place_id in place_ids
        if (place := by_id.get(place_id))
        and place.id not in excluded
        and _near_anchor(place, (destination_lat, destination_lng))
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


def _lodging_anchor(request: PlanRequest) -> tuple[float, float]:
    if request.noi_luu_tru:
        return (request.noi_luu_tru.lat, request.noi_luu_tru.lng)
    return (request.location.lat, request.location.lng)


def _lodging_context(request: PlanRequest) -> dict:
    anchor = _lodging_anchor(request)
    return {
        "co_noi_luu_tru": request.noi_luu_tru is not None,
        "ten": request.ten_noi_luu_tru,
        "toa_do": {"lat": anchor[0], "lng": anchor[1]},
        "nguon": "plan_request.noi_luu_tru" if request.noi_luu_tru else "plan_request.location",
        "rang_buoc": [
            "Dùng nơi lưu trú làm điểm neo xuất phát/kết thúc khi người dùng cung cấp.",
            "Chọn bữa ăn và điểm phụ gần nơi lưu trú/cụm điểm trong ngày để giảm vòng di chuyển.",
        ],
    }


def _near_anchor(place: Place, anchor: tuple[float, float], radius_km: float = DESTINATION_RADIUS_KM) -> bool:
    return haversine_km(anchor[0], anchor[1], place.lat, place.lng) <= radius_km


@lru_cache(maxsize=512)
def _places_near(lat: float, lng: float, radius_km: float = DESTINATION_RADIUS_KM) -> tuple[Place, ...]:
    return tuple(
        place
        for place in PLACES
        if haversine_km(lat, lng, place.lat, place.lng) <= radius_km
    )


def _nearby_places(anchor: tuple[float, float], radius_km: float = DESTINATION_RADIUS_KM) -> tuple[Place, ...]:
    return _places_near(round(anchor[0], 3), round(anchor[1], 3), radius_km)


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
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and _near_anchor(place, anchor)
        and _is_dining_place(place)
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
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
    candidates = _extra_sight_candidates(
        request, excluded, anchor, seed, budget_per_person, excluded_names
    )
    return candidates[0] if candidates else None


def _extra_sight_candidates(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> list[Place]:
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and _near_anchor(place, anchor)
        and place.kind in SIGHT_KINDS
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and is_routable(place)
        and place.open_hour <= 16
        and place.close_hour >= 12
    ]
    if not pool:
        return []
    return sorted(
        pool,
        key=lambda place: (
            -_tourism_quality_score(place),
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
    _, _, destination_label = _destination_context(request)
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and _near_anchor(place, anchor)
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and place.open_hour <= 9
        and place.close_hour >= 11
    ]
    if not pool:
        pool = [
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and _near_anchor(place, anchor)
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
            and not _mentions_other_destination(place, destination_label)
            and not _looks_closed(place)
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
    if place.id in EVENING_PLACE_IDS:
        return True
    if open_hour >= 17:
        return True
    return _is_night_market(place)


def _is_night_market(place: Place) -> bool:
    """Recognize explicit tags and untagged provider records named as night markets."""
    if {"cho_dem", "night_market"}.intersection(place.tags):
        return True
    if place.kind != "cho":
        return False
    name_key = _place_name_key(place)
    return "cho dem" in name_key or "night market" in name_key


def _choose_midday_rest(
    request: PlanRequest,
    excluded: set[str],
    anchor: tuple[float, float],
    seed: int,
    budget_per_person: int,
    excluded_names: set[str] | None = None,
) -> Place | None:
    _, _, destination_label = _destination_context(request)
    """Quiet cafe/snack stop to bridge the hot early afternoon."""
    pool = [
        place
        for place in _nearby_places(anchor)
        if place.id not in excluded
        and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
        and _near_anchor(place, anchor)
        and place.kind == "cafe"
        and place.cost <= budget_per_person
        and not _looks_like_non_travel_business(place)
        and not _mentions_other_destination(place, destination_label)
        and not _looks_closed(place)
        and place.open_hour <= 12
        and place.close_hour >= 15
        and is_routable(place)
    ]
    if not pool:
        pool = [
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and _near_anchor(place, anchor)
            and place.kind == "quan_an"
            and "an_vat" in place.tags
            and place.cost <= budget_per_person
            and not _looks_like_non_travel_business(place)
            and not _mentions_other_destination(place, destination_label)
            and not _looks_closed(place)
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
        for place_id in ids:
            place = by_id.get(place_id)
            if (
                place
                and place.id not in excluded
                and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
                and _near_anchor(place, anchor)
                and place.cost <= budget_per_person
                and is_routable(place)
            ):
                return place
        return None

    return pick(EVENING_PLACE_IDS) or pick(EVENING_FALLBACK_IDS) or min(
        (
            place
            for place in _nearby_places(anchor)
            if place.id not in excluded
            and not ((key := _place_name_key(place)) and key in (excluded_names or set()))
            and _near_anchor(place, anchor)
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
        anchor = _anchor_for_places(day_sights, _lodging_anchor(request))
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
    anchor = _anchor_for_places(sights, _lodging_anchor(request))
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
    anchor = _anchor_for_places(day_sights, _lodging_anchor(request))
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


def _weather_discourages_midday_outdoor(weather: dict | None) -> bool:
    if not weather:
        return False
    temperature = weather.get("nhiet_do_max")
    rain = weather.get("xac_suat_mua")
    return (
        isinstance(temperature, (int, float)) and temperature >= 33
    ) or (
        isinstance(rain, (int, float)) and rain >= 60
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


def _duration_estimate_for(place: Place, meal_type: str | None, planned_minutes: int | None = None) -> dict:
    if meal_type:
        base = MEAL_DURATION.get(meal_type, place.duration_min or 60)
        lower, upper = max(30, base - 15), min(120, base + 15)
        source = "meal_window_policy"
        confidence = "medium"
        estimated = True
    else:
        tip = _guidance(place)
        if tip and tip.duration_min:
            lower = max(20, tip.duration_min - 15)
            upper = tip.duration_min + 30
            source = tip.source or "official_or_guide_guidance"
            confidence = "high"
            estimated = False
        elif place.duration_min > 0:
            lower = max(20, round(place.duration_min * 0.8))
            upper = max(lower, round(place.duration_min * 1.25))
            source = place.source
            confidence = "medium" if place.source not in {"local_seed", "curated"} else "low"
            estimated = place.source in {"local_seed", "curated"}
        else:
            lower, upper = DURATION_FALLBACKS.get(place.kind, (45, 90))
            source = "fallback_by_place_kind"
            confidence = "low"
            estimated = True
    if planned_minutes is not None:
        lower = min(lower, planned_minutes)
        upper = max(upper, planned_minutes)
    return {
        "toi_thieu_phut": lower,
        "toi_da_phut": upper,
        "ke_hoach_phut": planned_minutes,
        "do_tin_cay": confidence,
        "nguon": source,
        "uoc_luong": estimated,
        "ghi_chu": "AI khong tu sinh thoi luong; gia tri nay lay tu huong dan, catalog hoac fallback co cau truc.",
    }


def _slot_duration_minutes(slot: dict) -> int:
    return max(0, _parse_slot_clock(slot["ket_thuc"]) - _parse_slot_clock(slot["bat_dau"]))


def _traffic_peak_for_clock(clock: str) -> dict:
    minute = _parse_slot_clock(clock)
    for window in VIETNAM_TRAFFIC_PEAK_POLICY["khung_gio"]:
        start = _parse_slot_clock(window["tu"])
        end = _parse_slot_clock(window["den"])
        if start <= minute <= end:
            return {
                "trong_gio_cao_diem": True,
                "khung": window["ten"],
                "nguon": VIETNAM_TRAFFIC_PEAK_POLICY["nguon"],
                "ghi_chu": VIETNAM_TRAFFIC_PEAK_POLICY["ghi_chu"],
            }
    return {
        "trong_gio_cao_diem": False,
        "khung": None,
        "nguon": VIETNAM_TRAFFIC_PEAK_POLICY["nguon"],
        "ghi_chu": VIETNAM_TRAFFIC_PEAK_POLICY["ghi_chu"],
    }


def _attach_evidence(plan: dict, request: PlanRequest, places: tuple[Place, ...]) -> None:
    by_id = {place.id: place for place in places}
    decision_log: list[dict] = []
    holiday = (
        plan.get("tieu_chi_thoi_diem", {}).get("lich_nghi_le")
        if isinstance(plan.get("tieu_chi_thoi_diem"), dict)
        else None
    )
    holiday_status = _holiday_hours_status(holiday if isinstance(holiday, dict) else None)
    for day in plan.get("ngay", []):
        previous: Place | None = None
        for slot in day.get("khoang_gio", []):
            place = by_id.get(slot.get("dia_diem_id"))
            if not place:
                continue
            planned_minutes = _slot_duration_minutes(slot)
            duration = _duration_estimate_for(place, slot.get("bua_an"), planned_minutes)
            slot["thoi_luong"] = duration
            open_hour, close_hour = _effective_hours(place)
            guidance = _guidance(place)
            slot["gio_mo_cua"] = {
                "mo": f"{open_hour:02d}:00",
                "dong": f"{close_hour:02d}:00",
                "nguon": guidance.source if guidance else place.source,
            }
            if holiday_status:
                slot["gio_mo_cua"]["trang_thai_xac_minh"] = holiday_status["trang_thai_xac_minh"]
                slot["gio_mo_cua"]["ghi_chu_ngay_le"] = holiday_status["ghi_chu"]
            travel = None
            if previous:
                estimate = estimate_travel(previous, place)
                travel = estimate.__dict__
                travel["gio_cao_diem"] = _traffic_peak_for_clock(slot["bat_dau"])
                slot["di_chuyen_tu_diem_truoc"] = travel
            reasons = [
                f"khop gio mo cua {open_hour:02d}:00 den {close_hour:02d}:00",
                f"thoi luong ke hoach {planned_minutes} phut trong khoang {duration['toi_thieu_phut']} den {duration['toi_da_phut']} phut",
            ]
            if travel:
                reasons.append(f"di chuyen tam tinh {travel['minutes']} phut tu diem truoc")
                if travel.get("gio_cao_diem", {}).get("trong_gio_cao_diem"):
                    reasons.append("chặng này được đánh dấu rủi ro giờ cao điểm")
            if holiday_status:
                reasons.append("giờ mở cửa ngày lễ/Tết cần xác minh bằng nguồn chính thức trước khi phát hành")
            evidence = slot.get("bang_chung") if isinstance(slot.get("bang_chung"), dict) else {}
            timing_evidence = evidence.get("thoi_diem") if isinstance(evidence.get("thoi_diem"), dict) else {}
            if holiday_status:
                timing_evidence["lich_nghi_le"] = holiday_status
                timing_evidence["gio_mo_cua_hieu_luc"] = {
                    **(timing_evidence.get("gio_mo_cua_hieu_luc") or {}),
                    "trang_thai_xac_minh": holiday_status["trang_thai_xac_minh"],
                }
                evidence["thoi_diem"] = timing_evidence
            evidence.update({
                "dia_diem_id": place.id,
                "nguon_dia_diem": place.source,
                "nguon_url": source_for(place)[0],
                "thoi_luong": duration,
                "di_chuyen": travel,
                "rang_buoc_da_ap": ["gio_mo_cua", "ngan_sach", "khong_trung_dia_diem", "thoi_gian_di_chuyen"],
                "tag_khop": sorted(place.tags),
                "ly_do_luat": reasons,
                "lay_luc": datetime.now(UTC).isoformat(),
            })
            slot["bang_chung"] = evidence
            slot["giai_thich"] = f"{place.name} được chọn vì " + "; ".join(reasons) + "."
            decision_log.append(slot["bang_chung"])
            previous = place
    all_places = [by_id[slot["dia_diem_id"]] for day in plan.get("ngay", []) for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") in by_id]
    plan["bang_chung_quyet_dinh"] = decision_log
    plan["chinh_sach_do_cu_du_lieu"] = DATA_STALENESS_POLICY
    plan["bang_thoi_gian_di_chuyen"] = {
        "trang_thai": TRAVEL_ESTIMATE_POLICY["status"],
        "cong_thuc": TRAVEL_ESTIMATE_POLICY["formula"],
        "ghi_chu": TRAVEL_ESTIMATE_POLICY["note"],
        "ma_tran": travel_matrix(all_places),
    }


def _quality_report(plan: dict, request: PlanRequest, trusted_ids: set[str], places: tuple[Place, ...]) -> dict:
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    max_minutes = LIMITS[request.thoi_luong][1] * LIMITS[request.thoi_luong][2]
    scheduled_minutes = sum(_slot_duration_minutes(slot) for slot in slots)
    utilization = round(scheduled_minutes / max_minutes, 2) if max_minutes else 0
    tags = {
        tag
        for tag in relevant_tags(request.context)
        if tag not in {"du", "lich", "di", "choi", "ngay", "nguoi", "toi", "va"}
    }
    by_id = {place.id: place for place in places}
    covered = sorted(
        tag
        for tag in tags
        if any(tag in {ascii_fold(item).replace(" ", "_") for item in by_id.get(slot.get("dia_diem_id"), Place("", "", "", "", 0, 0, 0, 0, ())).tags} for slot in slots)
    )
    feasibility_errors = validate_plan(plan, trusted_ids, request)
    cp_sat = verify_fixed_schedule_with_cp_sat(plan, by_id, travel_minutes)
    day_optimizer_reports = []
    for day in plan.get("ngay", []):
        day_slots = [slot for slot in day.get("khoang_gio", []) if slot.get("dia_diem_id") in by_id]
        day_places = [by_id[slot["dia_diem_id"]] for slot in day_slots]
        if not day_places:
            continue
        starts = [_parse_slot_clock(slot["bat_dau"]) for slot in day_slots]
        ends = [_parse_slot_clock(slot["ket_thuc"]) for slot in day_slots]
        durations = {slot["dia_diem_id"]: _slot_duration_minutes(slot) for slot in day_slots}
        scores = {
            slot["dia_diem_id"]: int(
                ((slot.get("bang_chung") or {}).get("xep_hang") or {}).get("diem_tong", 0) * 100
            )
            for slot in day_slots
        }
        result = optimize_day_schedule_with_cp_sat(
            day_places,
            min(starts) if starts else 8 * 60,
            max(ends) if ends else 22 * 60,
            durations,
            scores,
            travel_minutes,
            min_places=len(day_places),
            max_places=len(day_places),
            budget_per_person=request.ngan_sach,
            max_candidates=50,
        )
        day_optimizer_reports.append(
            {
                "ngay": day.get("thu_tu"),
                "co_san": result.available,
                "hop_le": result.feasible,
                "trang_thai": result.status,
                "so_ung_vien_xet": result.candidate_count,
                "selected_ids": list(result.selected_ids),
                "starts": {key: f"{value // 60:02d}:{value % 60:02d}" for key, value in result.starts.items()},
                "objective_score": result.objective_score,
                "chan_bo": list(result.blockers),
            }
        )
    release_blockers = []
    if feasibility_errors:
        release_blockers.extend(feasibility_errors)
    if not cp_sat.available or not cp_sat.feasible:
        release_blockers.extend(f"CP-SAT: {blocker}" for blocker in cp_sat.blockers)
    if utilization < 0.6:
        release_blockers.append("Lich dung duoi 60 phan tram khung gio kha thi")
    holiday = (
        plan.get("tieu_chi_thoi_diem", {}).get("lich_nghi_le")
        if isinstance(plan.get("tieu_chi_thoi_diem"), dict)
        else None
    )
    if isinstance(holiday, dict) and holiday.get("khong_dung_gio_thuong_lam_bang_chung_phat_hanh"):
        release_blockers.append(
            "Tết Nguyên đán: cần giờ mở cửa/lịch hoạt động chính thức theo năm, không dùng giờ thường làm bằng chứng phát hành"
        )
    return {
        "phien_ban_bo_do": "release-readiness-quality-v1",
        "tinh_kha_thi": {"hop_le": not feasibility_errors, "loi": feasibility_errors},
        "do_phu_so_thich": {
            "so_thich_nhan_dien": sorted(tags),
            "so_thich_duoc_phu": covered,
            "ty_le": round(len(covered) / len(tags), 2) if tags else 1.0,
            "ghi_chu": "Do tren tag co san cua dia diem, khong dung diem cua he thong lam dap an chuan.",
        },
        "muc_su_dung_khung_gio": utilization,
        "bo_giai_cp_sat": {
            "thu_vien": "ortools.sat.python.cp_model",
            "vai_tro": "kiem_chung_kha_thi_lich_da_chon",
            "co_san": cp_sat.available,
            "hop_le": cp_sat.feasible,
            "trang_thai": cp_sat.status,
            "so_slot_kiem_tra": cp_sat.checked_slots,
            "objective_minutes": cp_sat.objective_minutes,
            "chan_bo": list(cp_sat.blockers),
        },
        "bo_giai_cp_sat_ngay": {
            "thu_vien": "ortools.sat.python.cp_model",
            "vai_tro": "toi_uu_lai_theo_ngay_voi_time_window_travel_budget_tren_slot_da_chon",
            "gioi_han_hien_tai": "Chạy trên các slot đã chọn để kiểm tra mô hình joint scheduling; chưa thay thế full optimizer 50-100 ứng viên trước phát hành.",
            "ket_qua": day_optimizer_reports,
            "tat_ca_hop_le": bool(day_optimizer_reports) and all(item["hop_le"] for item in day_optimizer_reports),
        },
        "moc_so_sanh_bat_buoc": {
            name: {
                "bat_buoc": True,
                "trang_thai": "required_before_release",
                "chan_phat_hanh_neu_thua": True,
            }
            for name in REQUIRED_BASELINES
        },
        "cong_phat_hanh": {"dat": not release_blockers, "chan_bo": release_blockers},
    }


def _preference_score(
    place: Place,
    meal_type: str | None,
    hour: float,
    weather: dict | None = None,
    solar_context: dict | None = None,
) -> float:
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
        if _weather_discourages_midday_outdoor(weather) and 11 <= hour < 15:
            return -35
        sunset_minute = (solar_context or {}).get("hoang_hon_phut")
        if _is_sunset_suitable(place) and isinstance(sunset_minute, int):
            sunset_hour = sunset_minute / 60
            sunset_score = 18 - abs(hour - (sunset_hour - 0.75)) * 8
            if sunset_hour - 1.75 <= hour <= sunset_hour + 0.35:
                return max(16, sunset_score)
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
    weather: dict | None = None,
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
        # Meal slots are semantic commitments: lunch stays at lunch time,
        # dinner stays at dinner time. Do not relax them into another daypart.
        earliest = max(earliest, preferred_open)
        latest_end = min(latest_end, preferred_close)
    elif not relax:
        # Keep visits inside researched preferred windows when possible.
        latest_end = min(latest_end, preferred_close, closing, day_end)

    ideal = max(earliest, preferred_open)
    # Outdoor without explicit dual guidance: morning if early, else afternoon cool window.
    tip = _guidance(place)
    adverse_outdoor_weather = _weather_discourages_midday_outdoor(weather)
    if not meal_type and _is_outdoor_place(place) and not tip and not relax:
        arrive_hour = arrive.hour + arrive.minute / 60
        cool_start, cool_end = _outdoor_afternoon_window(arrive)
        if adverse_outdoor_weather:
            cool_start = _at_clock(arrive, 15, 0)
        if arrive_hour < 11:
            ideal = max(earliest, _at_clock(arrive, max(open_hour, 7), 0))
            latest_end = min(latest_end, _at_clock(arrive, 10, 30), closing, day_end)
        elif cool_start + timedelta(minutes=MIN_VISIT_MINUTES) <= min(cool_end, closing, day_end):
            if (cool_start - arrive).total_seconds() / 60 > 60:
                cool_start = max(arrive, cool_start)
            ideal = max(earliest, cool_start)
            latest_end = min(cool_end, closing, day_end)
    elif (
        not meal_type
        and adverse_outdoor_weather
        and _is_outdoor_place(place)
        and 11 <= (arrive.hour + arrive.minute / 60) < 15
    ):
        ideal = max(earliest, _at_clock(arrive, 15, 0))
    idle = (ideal - arrive).total_seconds() / 60
    strict = night_market or bool(meal_type) or (
        (not relax)
        and (
            _is_morning_only(place)
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
        if relax and not meal_type and not night_market:
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
    weather: dict | None = None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
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
                    place, meal_type, arrive, day_start, day_end, request, relax=relax, weather=weather
                )
                if not bounds:
                    continue
                start, end, _visit = bounds
                idle = max(0, (start - arrive).total_seconds() / 60)
                score = _preference_score(
                    place,
                    meal_type,
                    start.hour + start.minute / 60,
                    weather,
                    solar_context,
                )
                score -= idle * 0.6
                score -= travel * 0.15
                if relax:
                    score -= 5
                if any(mt == "trua" for _, mt in remaining):
                    lunch_ready = _at_clock(day_start, 10, 45)
                    lunch_close = _at_clock(day_start, MEAL_WINDOWS["trua"][2], MEAL_WINDOWS["trua"][3])
                    if cursor >= lunch_ready:
                        if meal_type == "trua":
                            score += 80
                        elif cursor < lunch_close:
                            score -= 80
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
            "nguon_url": source_for(place)[0],
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
            "bang_chung": _slot_evidence(
                place,
                request,
                start,
                meal_type,
                weather,
                solar_context,
                behavior_profile,
            ),
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
    weather: dict | None = None,
    solar_context: dict | None = None,
    behavior_profile: dict | None = None,
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
        candidate = None
        bounds = None
        options = _extra_sight_candidates(
            request,
            used_ids | scheduled_ids,
            anchor,
            seed + index + len(slots),
            remaining_budget,
            scheduled_names,
        )[:80]
        for option in options:
            travel = travel_minutes(prev_place, option)
            arrive = cursor + timedelta(minutes=travel)
            option_bounds = _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, weather=weather
            ) or _compute_slot_bounds(
                option, None, arrive, day_start, day_end, request, relax=True, weather=weather
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
            "nguon_url": source_for(candidate)[0],
            "anh": image_url,
            "anh_nguon": image_credit,
            "ghi_chu": ghi_chu,
            "bang_chung": _slot_evidence(
                candidate,
                request,
                start,
                None,
                weather,
                solar_context,
                behavior_profile,
            ),
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
        "nguon_url": source_for(place)[0],
        "anh": image_url,
        "anh_nguon": image_credit,
        "ghi_chu": ghi_chu,
    }
    if meal_type:
        slot["bua_an"] = meal_type
        slot["nhan_bua"] = labels[meal_type]
    return slot, end, place.cost * request.so_nguoi


def _looks_like_non_travel_business(place: Place) -> bool:
    name_key = _place_name_key(place)
    return (
        name_key in GENERIC_PLACE_NAME_KEYS
        or name_key in LOW_VALUE_TOURIST_NAME_KEYS
        or any(hint in name_key for hint in NON_TRAVEL_NAME_HINTS)
    )


def _looks_closed(place: Place) -> bool:
    name_key = _place_name_key(place)
    return any(hint in name_key for hint in CLOSED_PLACE_HINTS)


def _mentions_other_destination(place: Place, current_label: str | None) -> bool:
    if not current_label:
        return False
    name_key = _place_name_key(place)
    current_key = _ascii_fold(current_label).casefold()
    destination_terms = {
        "Hà Nội": {"ha noi", "hanoi"},
        "TP.HCM": {"tp hcm", "sai gon", "saigon", "thanh pho ho chi minh"},
        "Hạ Long": {"ha long", "halong"},
        "Đà Nẵng": {"da nang", "danang"},
        "Hội An": {"hoi an"},
        "Nha Trang": {"nha trang"},
        "Phú Quốc": {"phu quoc"},
        "Sa Pa": {"sa pa", "sapa"},
        "Vũng Tàu": {"vung tau"},
        "Đà Lạt": {"da lat", "dalat"},
        "Huế": {"hue"},
        "Cần Thơ": {"can tho"},
        "Ninh Bình": {"ninh binh"},
    }
    current_terms = next(
        (terms for label, terms in destination_terms.items() if _ascii_fold(label).casefold() == current_key),
        set(),
    )
    for terms in destination_terms.values():
        if terms is current_terms:
            continue
        if any(term in name_key for term in terms):
            return True
    return False


def _tourism_quality_score(place: Place) -> int:
    """Prefer places that are recognizable as tourism anchors, not just nearby POIs."""
    name_key = _place_name_key(place)
    tags = set(place.tags)
    score = 0
    if name_key in LOW_VALUE_TOURIST_NAME_KEYS:
        return -100
    if any(hint in name_key for hint in FAMOUS_TOURIST_NAME_HINTS):
        score += 70
    if place.image_url or image_for(place)[0]:
        score += 35
    if place.kind in {"bai_bien", "nui", "hang_dong", "di_tich", "den_chua", "bao_tang", "giai_tri"}:
        score += 24
    elif place.kind == "dia_danh":
        score += 14
    elif place.kind in {"cho", "cong_vien"}:
        score += 8
    if tags.intersection({"beach", "peak", "viewpoint", "museum", "monument", "heritage", "historic", "temple"}):
        score += 12
    if "attraction" in tags:
        score += 8
    if tags.intersection({"artwork", "tree", "path", "limited"}) and not any(
        hint in name_key for hint in FAMOUS_TOURIST_NAME_HINTS
    ):
        score -= 12
    return score


def _wants_old_quarter(request: PlanRequest) -> bool:
    tags = relevant_tags(request.context)
    return bool(
        tags.intersection(OLD_QUARTER_TERMS)
        or tags.intersection({"ha_noi", "hanoi", "pho_co"})
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
    behavior_profile = store.get_behavior_profile(request.ma_phien) if request.ma_phien else {}
    tag_weights = behavior_profile.get("tag_weights", {}) if isinstance(behavior_profile, dict) else {}
    destination_lat, destination_lng, destination_label = _destination_context(request)
    source_places = _nearby_places((destination_lat, destination_lng))
    candidates = [
        p for p in source_places
        if p.id not in excluded
        and p.cost <= request.ngan_sach
        and is_routable(p)
        and not _looks_like_non_travel_business(p)
        and not _mentions_other_destination(p, destination_label)
        and not _looks_closed(p)
        and haversine_km(destination_lat, destination_lng, p.lat, p.lng) <= DESTINATION_RADIUS_KM
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
            -_tourism_quality_score(p),
            -int(p.kind in SIGHT_KINDS),
            -int(p.kind in {"dia_danh", "bao_tang"}),
            -int(p.source == "curated"),
            -len(tags.intersection(p.tags)),
            -sum(int(tag_weights.get(tag, 0)) for tag in p.tags if isinstance(tag_weights.get(tag, 0), int)),
            haversine_km(destination_lat, destination_lng, p.lat, p.lng),
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
    return highlights + [place for place in quality_pool if place.id not in highlight_ids]


def validate_plan(
    plan: dict,
    trusted_ids: set[str],
    request: PlanRequest | None = None,
    *,
    allow_below_minimum: bool = False,
    trusted_places: tuple[Place, ...] = (),
) -> list[str]:
    errors: list[str] = []
    slots = [slot for day in plan.get("ngay", []) for slot in day.get("khoang_gio", [])]
    thoi_luong = (request.thoi_luong if request else plan.get("thoi_luong")) or "ca_ngay"
    min_slots = _min_plan_slots(thoi_luong) if thoi_luong in LIMITS else 4
    max_slots = _max_plan_slots(thoi_luong) if thoi_luong in LIMITS else 10
    if (not allow_below_minimum and len(slots) < min_slots) or len(slots) > max_slots:
        errors.append(f"Kế hoạch phải có {min_slots}–{max_slots} địa điểm")
    if any(slot.get("dia_diem_id") not in trusted_ids for slot in slots):
        errors.append("Có địa điểm ngoài danh sách tin cậy")
    place_ids = [slot.get("dia_diem_id") for slot in slots]
    if len(place_ids) != len(set(place_ids)):
        errors.append("Kế hoạch chứa địa điểm trùng lặp")
    by_id = {place.id: place for place in (*PLACES, *trusted_places)}
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
    if request:
        destination_lat, destination_lng, destination_label = _destination_context(request)
        if destination_label:
            for slot in slots:
                coordinates = slot.get("toa_do") or {}
                try:
                    slot_lat = float(coordinates.get("lat"))
                    slot_lng = float(coordinates.get("lng"))
                except (TypeError, ValueError):
                    errors.append(f"Thiếu tọa độ địa điểm: {slot.get('dia_diem_id')}")
                    continue
                distance_km = haversine_km(destination_lat, destination_lng, slot_lat, slot_lng)
                if distance_km > DESTINATION_RADIUS_KM:
                    errors.append(
                        f"Địa điểm nằm ngoài vùng {destination_label}: {slot.get('dia_diem_id')}"
                    )
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
    destination_lat, destination_lng, _ = _destination_context(request)
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
                haversine_km(destination_lat, destination_lng, place.lat, place.lng),
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
    candidate_ids = {place.id for place in candidates}
    destination_lat, destination_lng, destination_label = _destination_context(request)
    origin = (destination_lat, destination_lng)
    for item in suggestions:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        place = verify_place_name(name.strip(), origin)
        if not place or place.id not in candidate_ids or place.id in seen or place.cost > request.ngan_sach:
            continue
        if destination_label and not _near_anchor(place, origin):
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
    max_minutes: int,
    number_of_days: int,
) -> tuple[list[Place], dict[str, dict], dict]:
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
            return chosen[:sight_count], llm_details_by_id, {
                "phuong_phap": "llm_catalog_guarded",
                "ghi_chu": "LLM chỉ chọn id có trong catalog tin cậy; planner vẫn kiểm tra ràng buộc sau đó.",
            }
    score_by_id = {
        place.id: max(1, (len(sight_pool) - index) * 10 + _tourism_quality_score(place))
        for index, place in enumerate(sight_pool)
    }
    cp_day = None
    if number_of_days == 1:
        cp_day = optimize_day_schedule_with_cp_sat(
            sight_pool,
            8 * 60,
            8 * 60 + max_minutes,
            {place.id: max(MIN_VISIT_MINUTES, place.duration_min or 60) for place in sight_pool[:80]},
            score_by_id,
            travel_minutes,
            min_places=sight_count,
            max_places=sight_count,
            budget_per_person=request.ngan_sach,
            max_candidates=80,
        )
        if cp_day.selected_ids:
            by_id = {place.id: place for place in sight_pool}
            chosen = [by_id[place_id] for place_id in cp_day.selected_ids if place_id in by_id]
            if len(chosen) >= min(sight_count, 2):
                return _dedupe_places(chosen)[:sight_count], llm_details_by_id, {
                    "phuong_phap": "ortools_cp_sat_day_joint_selection",
                    "thu_vien": "ortools.sat.python.cp_model",
                    "trang_thai": cp_day.status,
                    "vai_tro": "chon_va_xep_lai_ung_vien_theo_ngay_voi_time_window_duration_travel_budget",
                    "so_ung_vien_xet": cp_day.candidate_count,
                    "gioi_han_ung_vien": 80,
                    "objective_score": cp_day.objective_score,
                    "selected_ids": list(cp_day.selected_ids),
                    "suggested_starts": {
                        place_id: f"{minute // 60:02d}:{minute % 60:02d}"
                        for place_id, minute in cp_day.starts.items()
                    },
                    "chan_bo": list(cp_day.blockers),
                }
    cp_selection = select_places_with_cp_sat(
        sight_pool,
        sight_count,
        request.ngan_sach,
        score_by_id,
        max_candidates=40,
    )
    if cp_selection.selected_ids:
        by_id = {place.id: place for place in sight_pool}
        chosen = [by_id[place_id] for place_id in cp_selection.selected_ids if place_id in by_id]
        if len(chosen) >= min(sight_count, 2):
            origin = _lodging_anchor(request)
            origin_place = Place(
                id="__origin__",
                name="Origin",
                kind="origin",
                area="origin",
                lat=origin[0],
                lng=origin[1],
                cost=0,
                duration_min=0,
                tags=(),
            )
            order = optimize_order_with_cp_sat(
                _dedupe_places(chosen)[:sight_count],
                origin,
                lambda _origin, place: travel_minutes(origin_place, place),
                travel_minutes,
            )
            if order.ordered_ids:
                ordered_by_id = {place.id: place for place in chosen}
                chosen = [ordered_by_id[place_id] for place_id in order.ordered_ids if place_id in ordered_by_id]
            return _dedupe_places(chosen)[:sight_count], llm_details_by_id, {
                "phuong_phap": "ortools_cp_sat_selection",
                "thu_vien": "ortools.sat.python.cp_model",
                "trang_thai": cp_selection.status,
                "so_ung_vien_xet": cp_selection.candidate_count,
                "gioi_han_ung_vien": 40,
                "objective_score": cp_selection.objective_score,
                "sap_thu_tu": {
                    "phuong_phap": "ortools_cp_sat_order",
                    "trang_thai": order.status,
                    "so_diem_xet": order.candidate_count,
                    "objective_travel_minutes": order.objective_travel_minutes,
                    "chan_bo": list(order.blockers),
                },
                "chan_bo": list(cp_selection.blockers),
            }
    chosen = (
        _select_ai_places(sight_pool, sight_count, request)
        or _select_within_budget(sight_pool, sight_count, request.ngan_sach)
    )
    chosen = [
        place
        for place in chosen
        if not _is_dining_place(place) and _is_sight_place(place, allow_cafe=allow_cafe)
    ]
    return _dedupe_places(chosen)[:sight_count], llm_details_by_id, {
        "phuong_phap": "fallback_ranked_budget",
        "cp_sat": {
            "co_san": cp_selection.available,
            "trang_thai": cp_selection.status,
            "chan_bo": list(cp_selection.blockers),
        },
        "cp_sat_day_joint": (
            {
                "co_san": cp_day.available,
                "trang_thai": cp_day.status,
                "so_ung_vien_xet": cp_day.candidate_count,
                "chan_bo": list(cp_day.blockers),
            }
            if cp_day
            else {"co_san": False, "trang_thai": "not_applicable_multi_day_or_disabled"}
        ),
    }


def build_plan(request: PlanRequest, excluded: set[str] | None = None) -> dict:
    if not DISTANCE_METADATA.get("loaded") or not DISTANCE_METADATA.get("updated_at"):
        raise PipelineUnavailable("Hệ thống đang khởi tạo bản đồ, vui lòng quay lại sau")
    count, max_minutes, number_of_days = LIMITS[request.thoi_luong]
    meals_per_day = _meals_per_day(request.thoi_luong)
    meals_total = len(meals_per_day) * number_of_days
    sight_total = _sight_total(count, meals_total, request.thoi_luong)
    max_slots = _max_plan_slots(request.thoi_luong)
    min_slots = _min_plan_slots(request.thoi_luong)
    destination_lat, destination_lng, destination_label = _destination_context(request)
    input_understanding = _request_understanding(request)
    candidates = choose_candidates(request, excluded)
    behavior_profile = store.get_behavior_profile(request.ma_phien) if request.ma_phien else {}
    sight_chosen, llm_details_by_id, selection_solver_evidence = _select_sight_places(
        candidates,
        sight_total,
        request,
        max_minutes,
        number_of_days,
    )
    sight_chosen = _dedupe_places(sight_chosen)
    if len(sight_chosen) < min(sight_total, 2):
        raise PipelineUnavailable("Không đủ địa điểm tham quan tin cậy trong ngân sách")

    origin = _lodging_anchor(request)
    ordered_sights = _ordered_route(sight_chosen, origin)
    split_index = (len(ordered_sights) + 1) // 2
    sight_by_day = (
        [ordered_sights]
        if number_of_days == 1
        else [ordered_sights[:split_index], ordered_sights[split_index:]]
    )

    trip_date = request.ngay_di or datetime.now(UTC).date()
    holiday_context = _holiday_note(trip_date)
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
                destination_lat, destination_lng, trip_date, request.ngon_ngu
            )
        except (WeatherUnavailable, ValueError, httpx.HTTPError):
            weather["ghi_chu"] = copy[2]
    solar_context = sunset_for_date(trip_date, destination_lat, destination_lng)
    seasonal_context = _seasonal_context(destination_label, trip_date)

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
            weather,
            solar_context,
            behavior_profile,
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
            weather,
            solar_context,
            behavior_profile,
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
        "tieu_de": f"{destination_label or 'Việt Nam'} · {request.context[:48]}",
        "tom_tat": copy[6].format(people=request.so_nguoi),
        "thoi_luong": request.thoi_luong,
        "ngay_di": trip_date.isoformat(),
        "tong_chi_phi": total_cost,
        "chi_phi_moi_nguoi": total_cost // request.so_nguoi,
        "thoi_tiet": weather,
        "dau_vao_da_hieu": input_understanding,
        "du_lieu_ung_vien": {
            "tong_ung_vien": len(candidates),
            "nguon": sorted({place.source for place in candidates if place.source}),
            "ban_kinh_km": DESTINATION_RADIUS_KM,
            "diem_den": input_understanding["diem_den"],
            "ghi_chu": "Ứng viên được lọc từ catalog hiện có, loại điểm không phù hợp du lịch, kiểm tra ngân sách, tọa độ và vùng.",
        },
        "rang_buoc_luu_tru": _lodging_context(request),
        "bo_giai_chon_ung_vien": selection_solver_evidence,
        "ho_so_hanh_vi": {
            "schema_version": behavior_profile.get("schema_version"),
            "version": behavior_profile.get("version", 0),
            "so_tin_hieu": behavior_profile.get("observation_count", 0),
            "kich_hoat_sau": behavior_profile.get("active_after_observations", 5),
            "dang_ap_dung": bool(behavior_profile.get("is_active")),
            "co_log_thay_doi": bool(behavior_profile.get("change_log")),
            "nguon": "store.ho_so_so_thich",
        },
        "tieu_chi_thoi_diem": {
            "lich_nghi_le": holiday_context,
            "thien_van": solar_context,
            "mua_vu_le_hoi": seasonal_context,
            "thoi_tiet": {
                "co_du_bao": bool(weather.get("nguon")),
                "tranh_outdoor_buoi_trua": _weather_discourages_midday_outdoor(weather),
            },
            "gio_cao_diem": VIETNAM_TRAFFIC_PEAK_POLICY,
            "quy_tac": [
                "Bữa trưa giữ trong khung 11:30 đến 13:30.",
                "Bữa tối giữ trong khung 18:00 đến 21:00.",
                "Chợ đêm được xếp sau 18:00.",
                "Điểm ngoài trời tránh buổi trưa khi trời nóng hoặc mưa nếu có dữ liệu thời tiết.",
                "Điểm ngắm cảnh/ngoài trời được ưu tiên gần hoàng hôn khi có tính toán thiên văn.",
                "Mùa vụ/lễ hội theo thành phố được ghi như heuristic nội bộ; lịch sự kiện chính thức theo năm vẫn là điều kiện phát hành.",
                "Chặng di chuyển trong 07:00-09:00 hoặc 16:30-19:00 được đánh dấu rủi ro giờ cao điểm khi chưa có dữ liệu traffic live.",
                "Visit guidance đã lưu được ưu tiên khi có dữ liệu.",
            ],
        },
        "ngay": days,
        "luu_y": [
            copy[7],
            copy[8],
            "Thoi gian di chuyen uu tien ma tran OSRM/PostgreSQL da build; cap thieu du lieu se duoc danh dau fallback.",
            "Neu co noi luu tru, lich trinh dung toa do do lam diem neo xuat phat/ket thuc thay vi chi dung tam thanh pho.",
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
    evidence_places = tuple([*PLACES, *candidates, *sight_chosen, *meal_places])
    _attach_evidence(plan, request, evidence_places)
    plan["danh_gia_chat_luong"] = _quality_report(plan, request, trusted_ids, evidence_places)
    errors = validate_plan(plan, trusted_ids, request)
    if errors:
        raise PipelineUnavailable("; ".join(errors))
    return plan
