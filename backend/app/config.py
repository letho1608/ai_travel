import os
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import date
from ipaddress import ip_address
from urllib.parse import urlparse


def _load_dotenv_defaults() -> None:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv_defaults()


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        from datetime import datetime

        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None


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
    ai_mode: str = "groq"
    app_env: str = "local"
    weather_enabled: bool = False
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-v4-flash"
    ai_api_key: str | None = None
    ai_input_usd_per_million: float = 0.14
    ai_output_usd_per_million: float = 0.28
    google_client_id: str | None = None
    google_maps_api_key: str | None = None
    google_places_text_search_daily_cap: int = 300
    google_places_text_search_monthly_cap: int = 9500
    google_places_photo_daily_cap: int = 30
    google_places_photo_monthly_cap: int = 950
    google_places_hours_daily_cap: int = 20
    google_places_hours_monthly_cap: int = 900
    google_places_runtime_per_plan_cap: int = 8
    google_places_runtime_photos: bool = False
    google_places_runtime_hours: bool = False
    app_jwt_secret: str | None = None
    amadeus_base_url: str = "https://test.api.amadeus.com"
    amadeus_client_id: str | None = None
    amadeus_client_secret: str | None = None
    support_admin_token: str | None = None
    osrm_base_url: str = "https://router.project-osrm.org"
    plan_route_geometry: bool = True
    plan_live_travel_matrix: bool = False
    plan_live_travel_matrix_max_places: int = 25
    route_calibration_file: str | None = None
    route_calibration_max_mape_percent: float = 35.0
    route_calibration_min_samples: int = 20
    public_transit_enabled: bool = False
    gtfs_feed_date: str | None = None
    event_calendar_file: str | None = None
    event_calendar_max_age_days: int = 90
    event_calendar_min_cities: int = 8
    event_calendar_min_events: int = 24
    max_request_body_bytes: int = 256 * 1024

    def validate_production(self) -> None:
        if self.app_env == "local":
            return
        missing = []
        if self.ai_mode == "offline" or not self.ai_api_key:
            missing.append("AI_MODE/AI provider API key")
        if not self.google_client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not self.google_maps_api_key:
            missing.append("GOOGLE_MAPS_API_KEY")
        if self.google_places_runtime_per_plan_cap <= 0:
            missing.append("GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP>0")
        if self.google_places_text_search_daily_cap <= 0 or self.google_places_text_search_monthly_cap <= 0:
            missing.append("GOOGLE_PLACES_TEXT_SEARCH daily/monthly caps >0")
        if self.google_places_runtime_photos and (
            self.google_places_photo_daily_cap <= 0 or self.google_places_photo_monthly_cap <= 0
        ):
            missing.append("GOOGLE_PLACES_PHOTO daily/monthly caps >0 when photos enabled")
        if self.google_places_runtime_hours and (
            self.google_places_hours_daily_cap <= 0 or self.google_places_hours_monthly_cap <= 0
        ):
            missing.append("GOOGLE_PLACES_HOURS daily/monthly caps >0 when hours enabled")
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
        if not self.route_calibration_file:
            missing.append("ROUTE_CALIBRATION_FILE")
        else:
            calibration_path = Path(self.route_calibration_file)
            if not calibration_path.exists():
                missing.append("ROUTE_CALIBRATION_FILE existing JSON report")
            else:
                try:
                    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
                    summary = payload.get("summary") if isinstance(payload, dict) else None
                    sample_count = int((summary or {}).get("sample_count") or 0)
                    mape_percent = (summary or {}).get("mape_percent")
                    if not isinstance(summary, dict) or not isinstance(mape_percent, (int, float)):
                        missing.append("ROUTE_CALIBRATION_FILE summary.sample_count/mape_percent")
                    elif sample_count < self.route_calibration_min_samples:
                        missing.append(
                            f"ROUTE_CALIBRATION_FILE sample_count>={self.route_calibration_min_samples}"
                        )
                    elif float(mape_percent) > self.route_calibration_max_mape_percent:
                        missing.append(
                            f"ROUTE_CALIBRATION_FILE mape_percent<={self.route_calibration_max_mape_percent}"
                        )
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    missing.append("ROUTE_CALIBRATION_FILE valid JSON report")
        if self.public_transit_enabled:
            if not self.gtfs_feed_date:
                missing.append("GTFS_FEED_DATE within 90 days when PUBLIC_TRANSIT_ENABLED=true")
            else:
                try:
                    feed_date = date.fromisoformat(self.gtfs_feed_date)
                except ValueError:
                    missing.append("GTFS_FEED_DATE=YYYY-MM-DD")
                else:
                    if (date.today() - feed_date).days > 90:
                        missing.append("GTFS_FEED_DATE within 90 days when PUBLIC_TRANSIT_ENABLED=true")
        if not self.event_calendar_file:
            missing.append("EVENT_CALENDAR_FILE official event/festival calendar")
        else:
            event_calendar_path = Path(self.event_calendar_file)
            if not event_calendar_path.exists():
                missing.append("EVENT_CALENDAR_FILE existing JSON report")
            else:
                try:
                    payload = json.loads(event_calendar_path.read_text(encoding="utf-8"))
                    generated_at = _parse_iso_date(payload.get("generated_at") if isinstance(payload, dict) else None)
                    cities = payload.get("cities") if isinstance(payload, dict) else None
                    if not generated_at or not isinstance(cities, dict):
                        missing.append("EVENT_CALENDAR_FILE generated_at/cities")
                    elif (date.today() - generated_at).days < 0:
                        missing.append("EVENT_CALENDAR_FILE generated_at not in future")
                    elif (date.today() - generated_at).days > self.event_calendar_max_age_days:
                        missing.append(f"EVENT_CALENDAR_FILE age<={self.event_calendar_max_age_days} days")
                    else:
                        city_count = 0
                        event_count = 0
                        for city_key, events in cities.items():
                            if not isinstance(city_key, str) or not isinstance(events, list) or not events:
                                continue
                            city_count += 1
                            for event in events:
                                if not isinstance(event, dict):
                                    continue
                                name = str(event.get("name", "")).strip()
                                start_date = _parse_iso_date(event.get("start_date"))
                                source_url = str(event.get("source_url", "")).strip()
                                if name and start_date and source_url:
                                    event_count += 1
                        if city_count < self.event_calendar_min_cities:
                            missing.append(f"EVENT_CALENDAR_FILE city_count>={self.event_calendar_min_cities}")
                        elif event_count < self.event_calendar_min_events:
                            missing.append(f"EVENT_CALENDAR_FILE event_count>={self.event_calendar_min_events}")
                except (OSError, TypeError, json.JSONDecodeError):
                    missing.append("EVENT_CALENDAR_FILE valid JSON report")
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
            ai_mode=os.getenv("AI_MODE", "groq").strip().lower(),
            app_env=app_env,
            weather_enabled=os.getenv("WEATHER_ENABLED", "false").lower() == "true",
            ai_base_url=os.getenv(
                "AI_BASE_URL",
                "https://api.groq.com/openai/v1"
                if os.getenv("AI_MODE", "groq") == "groq"
                else "https://api.deepseek.com",
            ),
            ai_model=(
                os.getenv("TEN_MODEL_GROQ")
                if os.getenv("AI_MODE", "groq") == "groq"
                else os.getenv("TEN_MODEL_DEEPSEEK")
            ) or (
                "llama-3.3-70b-versatile"
                if os.getenv("AI_MODE", "groq") == "groq"
                else "deepseek-v4-flash"
            ),
            ai_api_key=(
                os.getenv("API_KEY_GROQ")
                if os.getenv("AI_MODE", "groq") == "groq"
                else os.getenv("API_KEY_DEEPSEEK")
            ),
            ai_input_usd_per_million=float(os.getenv("AI_INPUT_USD_PER_MILLION", "0.14")),
            ai_output_usd_per_million=float(os.getenv("AI_OUTPUT_USD_PER_MILLION", "0.28")),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
            google_places_text_search_daily_cap=int(
                os.getenv(
                    "GOOGLE_PLACES_TEXT_SEARCH_DAILY_CAP",
                    os.getenv("GOOGLE_PLACES_RUNTIME_DAILY_CAP", "300"),
                )
            ),
            google_places_text_search_monthly_cap=int(
                os.getenv(
                    "GOOGLE_PLACES_TEXT_SEARCH_MONTHLY_CAP",
                    os.getenv("GOOGLE_PLACES_RUNTIME_MONTHLY_CAP", "9500"),
                )
            ),
            google_places_photo_daily_cap=int(
                os.getenv("GOOGLE_PLACES_PHOTO_DAILY_CAP", "30")
            ),
            google_places_photo_monthly_cap=int(
                os.getenv("GOOGLE_PLACES_PHOTO_MONTHLY_CAP", "950")
            ),
            google_places_hours_daily_cap=int(
                os.getenv("GOOGLE_PLACES_HOURS_DAILY_CAP", "20")
            ),
            google_places_hours_monthly_cap=int(
                os.getenv("GOOGLE_PLACES_HOURS_MONTHLY_CAP", "900")
            ),
            google_places_runtime_per_plan_cap=int(
                os.getenv("GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP", "8")
            ),
            google_places_runtime_photos=os.getenv(
                "GOOGLE_PLACES_RUNTIME_PHOTOS", "false"
            ).lower() == "true",
            google_places_runtime_hours=os.getenv(
                "GOOGLE_PLACES_RUNTIME_HOURS", "false"
            ).lower() == "true",
            app_jwt_secret=os.getenv("APP_JWT_SECRET"),
            amadeus_base_url=os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com"),
            amadeus_client_id=os.getenv("AMADEUS_CLIENT_ID"),
            amadeus_client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
            support_admin_token=os.getenv("SUPPORT_ADMIN_TOKEN") or (
                "local-support-dev" if os.getenv("APP_ENV", "local") == "local" else None
            ),
            osrm_base_url=os.getenv(
                "OSRM_BASE_URL", "https://router.project-osrm.org"
            ).strip().rstrip("/"),
            plan_route_geometry=os.getenv("PLAN_ROUTE_GEOMETRY", "1").lower()
            not in {"0", "false", "off"},
            plan_live_travel_matrix=os.getenv("PLAN_LIVE_TRAVEL_MATRIX", "0").lower()
            in {"1", "true", "on"},
            plan_live_travel_matrix_max_places=int(
                os.getenv("PLAN_LIVE_TRAVEL_MATRIX_MAX_PLACES", "25")
            ),
            route_calibration_file=os.getenv("ROUTE_CALIBRATION_FILE"),
            route_calibration_max_mape_percent=float(
                os.getenv("ROUTE_CALIBRATION_MAX_MAPE_PERCENT", "35")
            ),
            route_calibration_min_samples=int(
                os.getenv("ROUTE_CALIBRATION_MIN_SAMPLES", "20")
            ),
            public_transit_enabled=os.getenv("PUBLIC_TRANSIT_ENABLED", "false").lower()
            in {"1", "true", "on"},
            gtfs_feed_date=os.getenv("GTFS_FEED_DATE"),
            event_calendar_file=os.getenv("EVENT_CALENDAR_FILE"),
            event_calendar_max_age_days=int(
                os.getenv("EVENT_CALENDAR_MAX_AGE_DAYS", "90")
            ),
            event_calendar_min_cities=int(
                os.getenv("EVENT_CALENDAR_MIN_CITIES", "8")
            ),
            event_calendar_min_events=int(
                os.getenv("EVENT_CALENDAR_MIN_EVENTS", "24")
            ),
            max_request_body_bytes=int(os.getenv("MAX_REQUEST_BODY_BYTES", str(256 * 1024))),
        )


settings = Settings.from_env()
