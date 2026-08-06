import math
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx

FORECAST_TTL_SECONDS = 900
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
SUPPORTED_LOCALES = {
    "ar", "bg", "de", "en", "es", "fr", "he", "hi", "it", "ja",
    "ko", "nl", "pl", "pt", "ru", "th", "tr", "vi", "zh",
}

# Concise WMO groups keep every supported language complete without duplicating
# provider-specific wording for each individual rain/snow intensity code.
WEATHER_COPY = {
    "ar": ("سماء صافية", "غائم جزئياً", "ضباب", "رذاذ", "مطر", "ثلج", "زخات", "عاصفة رعدية", "قد تتغير التوقعات", "فضّل الأماكن الداخلية"),
    "bg": ("Ясно", "Облачно", "Мъгла", "Ръмеж", "Дъжд", "Сняг", "Превалявания", "Гръмотевична буря", "Прогнозата може да се промени", "Предпочетете закрити места"),
    "de": ("Klar", "Bewölkt", "Nebel", "Nieselregen", "Regen", "Schnee", "Schauer", "Gewitter", "Vorhersagen können sich ändern", "Innenbereiche bevorzugen"),
    "en": ("Clear sky", "Cloudy", "Fog", "Drizzle", "Rain", "Snow", "Showers", "Thunderstorm", "Forecasts may change", "Prefer indoor places"),
    "es": ("Cielo despejado", "Nublado", "Niebla", "Llovizna", "Lluvia", "Nieve", "Chubascos", "Tormenta", "El pronóstico puede cambiar", "Prioriza lugares interiores"),
    "fr": ("Ciel dégagé", "Nuageux", "Brouillard", "Bruine", "Pluie", "Neige", "Averses", "Orage", "Les prévisions peuvent changer", "Privilégiez les lieux couverts"),
    "he": ("שמיים בהירים", "מעונן", "ערפל", "טפטוף", "גשם", "שלג", "ממטרים", "סופת רעמים", "התחזית עשויה להשתנות", "העדיפו מקומות מקורים"),
    "hi": ("साफ़ आसमान", "बादल", "कोहरा", "बूंदाबांदी", "बारिश", "बर्फ़", "बौछार", "आंधी-तूफ़ान", "पूर्वानुमान बदल सकता है", "इनडोर स्थानों को प्राथमिकता दें"),
    "it": ("Cielo sereno", "Nuvoloso", "Nebbia", "Pioviggine", "Pioggia", "Neve", "Rovesci", "Temporale", "Le previsioni possono cambiare", "Preferisci luoghi al coperto"),
    "ja": ("快晴", "曇り", "霧", "霧雨", "雨", "雪", "にわか雨", "雷雨", "予報は変わる場合があります", "屋内の場所を優先してください"),
    "ko": ("맑음", "흐림", "안개", "이슬비", "비", "눈", "소나기", "뇌우", "예보는 변경될 수 있습니다", "실내 장소를 우선하세요"),
    "nl": ("Heldere lucht", "Bewolkt", "Mist", "Motregen", "Regen", "Sneeuw", "Buien", "Onweer", "De verwachting kan veranderen", "Kies bij voorkeur binnenlocaties"),
    "pl": ("Bezchmurnie", "Pochmurno", "Mgła", "Mżawka", "Deszcz", "Śnieg", "Przelotne opady", "Burza", "Prognoza może się zmienić", "Wybierz miejsca wewnątrz"),
    "pt": ("Céu limpo", "Nublado", "Nevoeiro", "Chuvisco", "Chuva", "Neve", "Aguaceiros", "Trovoada", "A previsão pode mudar", "Prefira locais cobertos"),
    "ru": ("Ясно", "Облачно", "Туман", "Морось", "Дождь", "Снег", "Ливни", "Гроза", "Прогноз может измениться", "Отдайте предпочтение помещениям"),
    "th": ("ท้องฟ้าแจ่มใส", "มีเมฆ", "หมอก", "ฝนปรอย", "ฝน", "หิมะ", "ฝนตกเป็นช่วง", "พายุฝนฟ้าคะนอง", "พยากรณ์อาจเปลี่ยนแปลง", "ควรเลือกสถานที่ในร่ม"),
    "tr": ("Açık", "Bulutlu", "Sis", "Çiseleme", "Yağmur", "Kar", "Sağanak", "Gök gürültülü fırtına", "Tahmin değişebilir", "Kapalı mekânları tercih edin"),
    "vi": ("Trời quang", "Có mây", "Sương mù", "Mưa phùn", "Mưa", "Tuyết", "Mưa rào", "Dông", "Dự báo có thể thay đổi", "Nên ưu tiên điểm trong nhà"),
    "zh": ("晴朗", "多云", "雾", "毛毛雨", "雨", "雪", "阵雨", "雷暴", "天气预报可能变化", "建议优先选择室内场所"),
}


class WeatherUnavailable(RuntimeError):
    """Provider response is unavailable or violates the forecast contract."""


def _weather_group(code: int) -> int:
    if code == 0:
        return 0
    if code in {1, 2, 3}:
        return 1
    if code in {45, 48}:
        return 2
    if code in {51, 53, 55, 56, 57}:
        return 3
    if code in {61, 63, 65, 66, 67}:
        return 4
    if code in {71, 73, 75, 77, 85, 86}:
        return 5
    if code in {80, 81, 82}:
        return 6
    if code in {95, 96, 99}:
        return 7
    raise WeatherUnavailable("Open-Meteo returned an unsupported WMO weather code")


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherUnavailable(f"Open-Meteo returned invalid {name}")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise WeatherUnavailable(f"Open-Meteo returned out-of-range {name}")
    return result


def _normalize(payload: Any, trip_date: date, fetched_at: datetime) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("daily"), dict):
        raise WeatherUnavailable("Open-Meteo response has no daily forecast")
    daily = payload["daily"]
    fields = (
        "time", "weather_code", "temperature_2m_min",
        "temperature_2m_max", "precipitation_probability_max",
    )
    arrays = {name: daily.get(name) for name in fields}
    if any(not isinstance(values, list) for values in arrays.values()):
        raise WeatherUnavailable("Open-Meteo daily fields must be arrays")
    lengths = {len(values) for values in arrays.values()}
    if lengths != {1} or arrays["time"][0] != trip_date.isoformat():
        raise WeatherUnavailable("Open-Meteo daily fields do not match the requested date")
    code_value = arrays["weather_code"][0]
    if isinstance(code_value, bool) or not isinstance(code_value, int):
        raise WeatherUnavailable("Open-Meteo returned an invalid weather code")
    _weather_group(code_value)
    minimum = _number(arrays["temperature_2m_min"][0], "minimum temperature", -100, 70)
    maximum = _number(arrays["temperature_2m_max"][0], "maximum temperature", -100, 70)
    if minimum > maximum:
        raise WeatherUnavailable("Open-Meteo minimum temperature exceeds maximum")
    rain = _number(arrays["precipitation_probability_max"][0], "rain probability", 0, 100)
    expires_at = fetched_at + timedelta(seconds=FORECAST_TTL_SECONDS)
    return {
        "weather_code": code_value,
        "nhiet_do_min": minimum,
        "nhiet_do_max": maximum,
        "xac_suat_mua": int(rain),
        "ngay": trip_date.isoformat(),
        "provenance": {
            "provider": "Open-Meteo",
            "source_url": "https://open-meteo.com/",
            "fetched_at": fetched_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        },
    }


@lru_cache(maxsize=256)
def _get_daily_weather(lat: float, lng: float, trip_date: date, ttl_bucket: int) -> dict:
    del ttl_bucket
    params = {
        "latitude": round(lat, 4), "longitude": round(lng, 4),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Bangkok", "start_date": trip_date.isoformat(),
        "end_date": trip_date.isoformat(),
    }
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            response = httpx.get(
                OPEN_METEO_URL, params=params, timeout=httpx.Timeout(6, connect=2)
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except (TypeError, ValueError) as exc:
                raise WeatherUnavailable("Open-Meteo returned malformed JSON") from exc
            return _normalize(payload, trip_date, datetime.now(UTC))
        except httpx.HTTPError as exc:
            last_error = exc
    raise WeatherUnavailable("Open-Meteo is temporarily unavailable") from last_error


def get_daily_weather(lat: float, lng: float, trip_date: date, locale: str = "vi") -> dict:
    """Return a validated, localized daily forecast with cache provenance."""
    language = locale if locale in SUPPORTED_LOCALES else "en"
    bucket = int(datetime.now(UTC).timestamp()) // FORECAST_TTL_SECONDS
    raw = _get_daily_weather(round(lat, 4), round(lng, 4), trip_date, bucket)
    copy = WEATHER_COPY[language]
    result = dict(raw)
    result["provenance"] = dict(raw["provenance"])
    result.update({
        "tinh_trang": copy[_weather_group(raw["weather_code"])],
        "ghi_chu": copy[9] if raw["xac_suat_mua"] >= 60 else copy[8],
        "nguon": raw["provenance"]["provider"],
        "nguon_url": raw["provenance"]["source_url"],
    })
    return result


get_daily_weather.cache_clear = _get_daily_weather.cache_clear  # type: ignore[attr-defined]
