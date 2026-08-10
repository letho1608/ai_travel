import pytest

from app.config import Settings


def test_production_configuration_fails_closed_when_secrets_or_https_are_missing():
    settings = Settings(app_env="production", cors_origins=("http://example.com",))
    with pytest.raises(RuntimeError, match="Production configuration incomplete") as error:
        settings.validate_production()
    assert "APP_JWT_SECRET" in str(error.value)
    assert "CORS_ORIGINS" in str(error.value)
    assert "AMADEUS" in str(error.value)
    assert "OSRM_BASE_URL" in str(error.value)


def test_complete_production_configuration_passes_validation():
    settings = Settings(
        app_env="production", ai_mode="deepseek", ai_api_key="provider-key",
        google_client_id="google-client", app_jwt_secret="j" * 32,
        support_admin_token="s" * 32, amadeus_client_id="amadeus-id",
        amadeus_client_secret="amadeus-secret",
        amadeus_base_url="https://api.amadeus.com",
        cors_origins=("https://travel.example",),
        osrm_base_url="https://osrm.travel.example",
    )
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
    monkeypatch.delenv("API_KEY_DEEPSEEK", raising=False)
    settings = Settings.from_env()
    assert settings.ai_mode == "groq"
    assert settings.ai_api_key == "groq-key"
    assert settings.ai_model == "llama-3.3-70b-versatile"
    assert settings.ai_base_url == "https://api.groq.com/openai/v1"


@pytest.mark.parametrize("url", ["", "https://router.project-osrm.org/", "http://router.project-osrm.org", "http://osrm.travel.example", "https://localhost:5000"])
def test_production_rejects_public_osrm_demo_url(url):
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
