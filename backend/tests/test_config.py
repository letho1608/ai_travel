import pytest
import json

from app.config import Settings


def _calibration_file(tmp_path, *, sample_count=20, mape_percent=20):
    path = tmp_path / "route_calibration.json"
    path.write_text(
        json.dumps({"summary": {"sample_count": sample_count, "mape_percent": mape_percent}}),
        encoding="utf-8",
    )
    return str(path)


def _event_calendar_file(tmp_path, *, generated_at="2026-08-15", city_count=8, events_per_city=3):
    path = tmp_path / "events.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "source": "official-tourism-board-fixture",
                "cities": {
                    f"city_{city_index}": [
                        {
                            "name": f"Festival {city_index}-{event_index}",
                            "start_date": "2026-09-01",
                            "source_url": f"https://example.com/{city_index}/{event_index}",
                        }
                        for event_index in range(events_per_city)
                    ]
                    for city_index in range(city_count)
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_default_ai_mode_uses_live_provider(monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    monkeypatch.delenv("API_KEY_GROQ", raising=False)
    monkeypatch.delenv("API_KEY_DEEPSEEK", raising=False)
    settings = Settings.from_env()
    assert settings.ai_mode == "groq"
    assert settings.ai_api_key is None


def test_production_configuration_fails_closed_when_secrets_or_https_are_missing():
    settings = Settings(app_env="production", cors_origins=("http://example.com",))
    with pytest.raises(RuntimeError, match="Production configuration incomplete") as error:
        settings.validate_production()
    assert "APP_JWT_SECRET" in str(error.value)
    assert "CORS_ORIGINS" in str(error.value)
    assert "AMADEUS" in str(error.value)
    assert "OSRM_BASE_URL" in str(error.value)


def test_complete_production_configuration_passes_validation(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path),
    )
    settings.validate_production()


def test_production_rejects_missing_route_calibration_file():
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
    )
    with pytest.raises(RuntimeError, match="ROUTE_CALIBRATION_FILE"):
        settings.validate_production()


def test_production_rejects_missing_google_places_key(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path),
    )
    with pytest.raises(RuntimeError, match="GOOGLE_MAPS_API_KEY"):
        settings.validate_production()


def test_production_rejects_invalid_google_places_caps(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path),
        google_places_runtime_per_plan_cap=0,
    )
    with pytest.raises(RuntimeError, match="GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP"):
        settings.validate_production()


def test_production_rejects_invalid_route_calibration_report(tmp_path):
    path = tmp_path / "route_calibration.json"
    path.write_text(json.dumps({"summary": {"sample_count": 20}}), encoding="utf-8")
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=str(path),
        event_calendar_file=_event_calendar_file(tmp_path),
    )
    with pytest.raises(RuntimeError, match="summary.sample_count/mape_percent"):
        settings.validate_production()


def test_production_rejects_low_sample_route_calibration_report(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path, sample_count=4),
        event_calendar_file=_event_calendar_file(tmp_path),
        route_calibration_min_samples=20,
    )
    with pytest.raises(RuntimeError, match="sample_count>=20"):
        settings.validate_production()


def test_production_rejects_high_error_route_calibration_report(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path, sample_count=30, mape_percent=55),
        event_calendar_file=_event_calendar_file(tmp_path),
        route_calibration_max_mape_percent=35,
    )
    with pytest.raises(RuntimeError, match="mape_percent<=35"):
        settings.validate_production()


def test_production_rejects_missing_event_calendar_file(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
    )
    with pytest.raises(RuntimeError, match="EVENT_CALENDAR_FILE"):
        settings.validate_production()


def test_production_rejects_invalid_event_calendar_schema(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"generated_at": "2026-08-15"}), encoding="utf-8")
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=str(path),
    )
    with pytest.raises(RuntimeError, match="generated_at/cities"):
        settings.validate_production()


def test_production_rejects_stale_event_calendar_file(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path, generated_at="2020-01-01"),
        event_calendar_max_age_days=90,
    )
    with pytest.raises(RuntimeError, match="EVENT_CALENDAR_FILE age<=90 days"):
        settings.validate_production()


def test_production_rejects_low_event_calendar_city_coverage(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path, city_count=3),
        event_calendar_min_cities=8,
    )
    with pytest.raises(RuntimeError, match="EVENT_CALENDAR_FILE city_count>=8"):
        settings.validate_production()


def test_production_rejects_low_event_calendar_event_coverage(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", google_maps_api_key="maps-key",
        app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path, events_per_city=1),
        event_calendar_min_events=24,
    )
    with pytest.raises(RuntimeError, match="EVENT_CALENDAR_FILE event_count>=24"):
        settings.validate_production()


def test_production_rejects_stale_public_transit_gtfs_feed(tmp_path):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
        route_calibration_file=_calibration_file(tmp_path),
        event_calendar_file=_event_calendar_file(tmp_path),
        public_transit_enabled=True,
        gtfs_feed_date="2018-01-01",
    )
    with pytest.raises(RuntimeError, match="GTFS_FEED_DATE"):
        settings.validate_production()


def test_local_mode_always_allows_frontend_ports_3000_to_3010(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    settings = Settings.from_env()
    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:3001" in settings.cors_origins
    assert "http://127.0.0.1:3001" in settings.cors_origins
    assert "http://localhost:3010" in settings.cors_origins


def test_groq_environment_uses_groq_key_model_and_base_url(monkeypatch):
    monkeypatch.setenv("AI_MODE", "groq")
    monkeypatch.setenv("API_KEY_GROQ", "groq-key")
    monkeypatch.setenv("TEN_MODEL_GROQ", "llama-3.3-70b-versatile")
    monkeypatch.delenv("TEN_MODEL_GROQ_CHAT", raising=False)
    monkeypatch.delenv("API_KEY_DEEPSEEK", raising=False)
    settings = Settings.from_env()
    assert settings.ai_mode == "groq"
    assert settings.ai_api_key == "groq-key"
    assert settings.ai_model == "llama-3.3-70b-versatile"
    assert settings.ai_chat_model == "qwen/qwen3.6-27b"
    assert settings.ai_base_url == "https://api.groq.com/openai/v1"


@pytest.mark.parametrize("url", ["", "https://router.project-osrm.org/", "http://router.project-osrm.org", "http://osrm.travel.example", "https://localhost:5000"])
def test_production_rejects_public_osrm_reference_url(url):
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url=url,
    )
    with pytest.raises(RuntimeError, match="OSRM_BASE_URL"):
        settings.validate_production()


def test_production_rejects_amadeus_test_environment():
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://test.api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
    )
    with pytest.raises(RuntimeError, match="AMADEUS_BASE_URL"):
        settings.validate_production()
