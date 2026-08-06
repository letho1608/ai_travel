from datetime import UTC, date, datetime

import pytest

from app.services import weather


class StubResponse:
    def __init__(self, payload: object | None = None):
        self.payload = payload or {
            "daily": {
                "time": ["2026-08-06"],
                "weather_code": [63],
                "temperature_2m_min": [26.1],
                "temperature_2m_max": [31.4],
                "precipitation_probability_max": [75],
            }
        }

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


@pytest.fixture(autouse=True)
def clear_weather_cache():
    weather.get_daily_weather.cache_clear()
    yield
    weather.get_daily_weather.cache_clear()


def test_open_meteo_forecast_is_normalized_with_live_provenance(monkeypatch):
    monkeypatch.setattr(weather.httpx, "get", lambda *args, **kwargs: StubResponse())
    result = weather.get_daily_weather(21.0285, 105.8542, date(2026, 8, 6), "vi")
    assert result["tinh_trang"] == "Mưa"
    assert result["xac_suat_mua"] == 75
    assert result["nguon"] == "Open-Meteo"
    assert "trong nhà" in result["ghi_chu"]
    fetched = datetime.fromisoformat(result["provenance"]["fetched_at"])
    expires = datetime.fromisoformat(result["provenance"]["expires_at"])
    assert fetched.tzinfo is not None
    assert fetched <= datetime.now(UTC) < expires
    assert (expires - fetched).total_seconds() == weather.FORECAST_TTL_SECONDS


def test_one_cached_forecast_localizes_all_19_locales(monkeypatch):
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return StubResponse()

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    labels = {
        locale: weather.get_daily_weather(21.0285, 105.8542, date(2026, 8, 6), locale)[
            "tinh_trang"
        ]
        for locale in weather.SUPPORTED_LOCALES
    }
    assert len(labels) == 19
    assert all(label and "WMO" not in label for label in labels.values())
    assert labels["en"] == "Rain"
    assert labels["ja"] == "雨"
    assert labels["vi"] == "Mưa"
    assert calls == 1


@pytest.mark.parametrize(
    "daily",
    [
        {},
        {"time": ["2026-08-06"]},
        {
            "time": ["2026-08-06", "2026-08-07"],
            "weather_code": [63],
            "temperature_2m_min": [26.1],
            "temperature_2m_max": [31.4],
            "precipitation_probability_max": [75],
        },
        {
            "time": ["2026-08-07"],
            "weather_code": [63],
            "temperature_2m_min": [26.1],
            "temperature_2m_max": [31.4],
            "precipitation_probability_max": [75],
        },
        {
            "time": ["2026-08-06"],
            "weather_code": [63],
            "temperature_2m_min": [80],
            "temperature_2m_max": [31.4],
            "precipitation_probability_max": [75],
        },
        {
            "time": ["2026-08-06"],
            "weather_code": [63],
            "temperature_2m_min": [26.1],
            "temperature_2m_max": [31.4],
            "precipitation_probability_max": [101],
        },
        {
            "time": ["2026-08-06"],
            "weather_code": [999],
            "temperature_2m_min": [26.1],
            "temperature_2m_max": [31.4],
            "precipitation_probability_max": [75],
        },
    ],
)
def test_invalid_provider_shapes_and_ranges_are_normalized_to_failure(monkeypatch, daily):
    monkeypatch.setattr(
        weather.httpx, "get", lambda *args, **kwargs: StubResponse({"daily": daily})
    )
    with pytest.raises(weather.WeatherUnavailable):
        weather.get_daily_weather(21.0285, 105.8542, date(2026, 8, 6), "en")


def test_unknown_locale_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(weather.httpx, "get", lambda *args, **kwargs: StubResponse())
    result = weather.get_daily_weather(21.0285, 105.8542, date(2026, 8, 6), "xx")
    assert result["tinh_trang"] == "Rain"
