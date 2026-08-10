import os
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    app_name: str = "Mình Đi Đâu Thế API"
    cors_origins: tuple[str, ...] = tuple(
        origin
        for port in range(3000, 3011)
        for origin in (f"http://localhost:{port}", f"http://127.0.0.1:{port}")
    )
    max_generate_per_hour: int = 5
    max_generate_ip_per_hour: int = 100
    max_roadtrip_route_per_hour: int = 30
    max_roadtrip_route_ip_per_hour: int = 120
    max_roadtrip_plan_per_hour: int = 5
    max_roadtrip_plan_ip_per_hour: int = 20
    daily_ai_budget_usd: float = 10.0
    monthly_ai_budget_usd: float = 300.0
    ai_mode: str = "mock"
    app_env: str = "local"
    weather_enabled: bool = False
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-v4-flash"
    ai_api_key: str | None = None
    ai_input_usd_per_million: float = 0.14
    ai_output_usd_per_million: float = 0.28
    google_client_id: str | None = None
    app_jwt_secret: str | None = None
    amadeus_base_url: str = "https://test.api.amadeus.com"
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None
    support_admin_token: str | None = None
    osrm_base_url: str = "https://router.project-osrm.org"
    max_request_body_bytes: int = 256 * 1024

    def validate_production(self) -> None:
        if self.app_env == "local":
            return
        missing = []
        if self.ai_mode == "mock" or not self.ai_api_key:
            missing.append("AI_MODE/AI provider API key")
        if not self.google_client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not self.app_jwt_secret or len(self.app_jwt_secret) < 32:
            missing.append("APP_JWT_SECRET>=32")
        if not self.support_admin_token or len(self.support_admin_token) < 32:
            missing.append("SUPPORT_ADMIN_TOKEN>=32")
        if not self.amadeus_client_id or not self.amadeus_client_secret:
            missing.append("AMADEUS_CLIENT_ID/SECRET")
        amadeus_url = urlparse(self.amadeus_base_url.strip())
        if (amadeus_url.scheme != "https"
                or amadeus_url.hostname != "api.amadeus.com"
                or amadeus_url.port not in (None, 443)
                or amadeus_url.username is not None
                or amadeus_url.password is not None):
            missing.append("AMADEUS_BASE_URL=production HTTPS endpoint")
        normalized_osrm = self.osrm_base_url.strip().rstrip("/")
        osrm_url = urlparse(normalized_osrm)
        osrm_host = osrm_url.hostname
        unsafe_osrm_host = osrm_host in {None, "localhost", "router.project-osrm.org"}
        if osrm_host:
            try:
                address = ip_address(osrm_host)
                unsafe_osrm_host = unsafe_osrm_host or address.is_loopback or address.is_link_local
            except ValueError:
                pass
        if (not normalized_osrm or osrm_url.scheme != "https" or unsafe_osrm_host):
            missing.append("OSRM_BASE_URL=private production instance")
        if not self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
            missing.append("CORS_ORIGINS=https://...")
        if missing:
            raise RuntimeError("Production configuration incomplete: " + ", ".join(missing))

    @classmethod
    def from_env(cls) -> "Settings":
        local_frontend_origins = tuple(
            origin
            for port in range(3000, 3011)
            for origin in (f"http://localhost:{port}", f"http://127.0.0.1:{port}")
        )
        configured_origins = tuple(
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", ",".join(local_frontend_origins)).split(",")
            if origin.strip()
        )
        app_env = os.getenv("APP_ENV", "local")
        cors_origins = (
            tuple(dict.fromkeys([*configured_origins, *local_frontend_origins]))
            if app_env == "local"
            else configured_origins
        )
        return cls(
            cors_origins=cors_origins,
            max_generate_per_hour=int(os.getenv("GIOI_HAN_TAO", "100")),
            max_generate_ip_per_hour=int(os.getenv("GIOI_HAN_TAO_IP", "100")),
            max_roadtrip_route_per_hour=int(os.getenv("GIOI_HAN_ROADTRIP_ROUTE", "30")),
            max_roadtrip_route_ip_per_hour=int(os.getenv("GIOI_HAN_ROADTRIP_ROUTE_IP", "120")),
            max_roadtrip_plan_per_hour=int(os.getenv("GIOI_HAN_ROADTRIP_PLAN", "5")),
            max_roadtrip_plan_ip_per_hour=int(os.getenv("GIOI_HAN_ROADTRIP_PLAN_IP", "20")),
            daily_ai_budget_usd=float(os.getenv("TRAN_CHI_PHI_NGAY", "10")),
            monthly_ai_budget_usd=float(os.getenv("TRAN_CHI_PHI_THANG", "300")),
            ai_mode=os.getenv("AI_MODE", "mock"),
            app_env=app_env,
            weather_enabled=os.getenv("WEATHER_ENABLED", "false").lower() == "true",
            ai_base_url=os.getenv(
                "AI_BASE_URL",
                "https://api.groq.com/openai/v1"
                if os.getenv("AI_MODE", "mock") == "groq"
                else "https://api.deepseek.com",
            ),
            ai_model=(
                os.getenv("TEN_MODEL_GROQ")
                if os.getenv("AI_MODE", "mock") == "groq"
                else os.getenv("TEN_MODEL_DEEPSEEK")
            ) or (
                "llama-3.3-70b-versatile"
                if os.getenv("AI_MODE", "mock") == "groq"
                else "deepseek-v4-flash"
            ),
            ai_api_key=(
                os.getenv("API_KEY_GROQ")
                if os.getenv("AI_MODE", "mock") == "groq"
                else os.getenv("API_KEY_DEEPSEEK")
            ),
            ai_input_usd_per_million=float(os.getenv("AI_INPUT_USD_PER_MILLION", "0.14")),
            ai_output_usd_per_million=float(os.getenv("AI_OUTPUT_USD_PER_MILLION", "0.28")),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            app_jwt_secret=os.getenv("APP_JWT_SECRET"),
            amadeus_base_url=os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com"),
            amadeus_client_id=os.getenv("AMADEUS_CLIENT_ID"),
            amadeus_client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
            support_admin_token=os.getenv("SUPPORT_ADMIN_TOKEN") or (
                "local-support-demo" if os.getenv("APP_ENV", "local") == "local" else None
            ),
            osrm_base_url=os.getenv(
                "OSRM_BASE_URL", "https://router.project-osrm.org"
            ).strip().rstrip("/"),
            max_request_body_bytes=int(os.getenv("MAX_REQUEST_BODY_BYTES", str(256 * 1024))),
        )


settings = Settings.from_env()
