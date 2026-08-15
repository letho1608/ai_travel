from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Duration = Literal["vai_gio", "nua_ngay", "ca_ngay", "nhieu_ngay"]
Locale = Literal[
    "vi", "en", "ar", "bg", "de", "es", "fr", "he", "hi", "it", "ja",
    "nl", "pl", "pt", "ru", "tr", "zh", "ko", "th",
]
HOTEL_AMENITIES = {
    "WIFI", "PARKING", "AIR_CONDITIONING", "RESTAURANT", "FITNESS_CENTER",
    "PETS_ALLOWED", "AIRPORT_SHUTTLE", "DISABLED_FACILITIES", "KITCHEN",
    "ROOM_SERVICE", "SPA", "SWIMMING_POOL",
}


class Coordinate(BaseModel):
    lat: float = Field(ge=8.0, le=24.5)
    lng: float = Field(ge=102.0, le=110.5)


class GlobalCoordinate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PlanRequest(BaseModel):
    context: str = Field(min_length=2, max_length=500)
    location: Coordinate
    thoi_luong: Duration
    so_nguoi: int = Field(default=2, ge=1, le=30)
    ngan_sach: int = Field(default=1_000_000, ge=50_000, le=100_000_000)
    ngay_di: date | None = None
    noi_luu_tru: Coordinate | None = None
    ten_noi_luu_tru: str | None = Field(default=None, max_length=120)
    ma_phien: str | None = Field(default=None, max_length=100)
    ngon_ngu: Locale = "vi"
    nonce: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("context")
    @classmethod
    def plain_text_only(cls, value: str) -> str:
        cleaned = " ".join(value.replace("<", "").replace(">", "").split())
        if not cleaned:
            raise ValueError("Nội dung không hợp lệ")
        return cleaned

    @field_validator("ten_noi_luu_tru")
    @classmethod
    def clean_lodging_name(cls, value: str | None) -> str | None:
        return " ".join(value.replace("<", "").replace(">", "").split()) if value else value


class SwipeRequest(BaseModel):
    diem_bi_loai: str
    dia_diem_thay_the: str | None = Field(default=None, min_length=1, max_length=200)
    ten_dia_diem_thay_the: str | None = Field(default=None, min_length=1, max_length=160)
    phien_ban: int = Field(ge=1)
    ma_phien: str


class DeleteSlotRequest(BaseModel):
    dia_diem_id: str = Field(min_length=1, max_length=200)
    phien_ban: int = Field(ge=1)
    ma_phien: str


class RegenerateRequest(BaseModel):
    ma_phien: str
    nonce: str = Field(min_length=8, max_length=100)


class RefineRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    phien_ban: int = Field(ge=1)
    ma_phien: str
    dia_diem_dang_chon: str | None = None

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        return " ".join(value.replace("<", "").replace(">", "").split())


class RestoreVersionRequest(BaseModel):
    phien_ban_hien_tai: int = Field(ge=1)
    ma_phien: str


class CommentRequest(BaseModel):
    noi_dung: str = Field(min_length=1, max_length=1000)
    ten_hien_thi: str = Field(min_length=1, max_length=80)
    ma_phien: str = Field(min_length=8, max_length=100)

    @field_validator("noi_dung", "ten_hien_thi")
    @classmethod
    def sanitize_comment(cls, value: str) -> str:
        return " ".join(value.replace("<", "").replace(">", "").split())


class ResolveCommentRequest(BaseModel):
    da_giai_quyet: bool
    ma_phien: str


class FlightSearchRequest(BaseModel):
    origin: str = Field(pattern=r"^[A-Z]{3}$")
    destination: str = Field(pattern=r"^[A-Z]{3}$")
    departure_date: date
    return_date: date | None = None
    adults: int = Field(default=1, ge=1, le=9)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    include_price_analysis: bool = True
    ma_phien: str = Field(min_length=8, max_length=100)

    @model_validator(mode="after")
    def valid_route_and_dates(self):
        if self.departure_date < datetime.now(UTC).date():
            raise ValueError("Ngày đi không được ở quá khứ")
        if self.origin == self.destination:
            raise ValueError("Điểm đi và điểm đến phải khác nhau")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Ngày về không được trước ngày đi")
        return self


class HotelSearchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    check_in: date
    check_out: date
    adults: int = Field(default=2, ge=1, le=9)
    room_quantity: int = Field(default=1, ge=1, le=9)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    radius_km: int = Field(default=10, ge=1, le=100)
    ratings: list[int] = Field(default_factory=list, max_length=4)
    amenities: list[str] = Field(default_factory=list, max_length=5)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, gt=0)
    ma_phien: str = Field(min_length=8, max_length=100)

    @field_validator("ratings")
    @classmethod
    def valid_ratings(cls, value: list[int]):
        if any(rating < 1 or rating > 5 for rating in value):
            raise ValueError("Hạng sao phải từ 1 đến 5")
        return sorted(set(value))

    @field_validator("amenities")
    @classmethod
    def valid_amenities(cls, value: list[str]):
        normalized = list(dict.fromkeys(item.upper() for item in value))
        if any(item not in HOTEL_AMENITIES for item in normalized):
            raise ValueError("Tiện nghi khách sạn không được hỗ trợ")
        return normalized

    @field_validator("max_price")
    @classmethod
    def max_after_min(cls, value: float | None, info):
        minimum = info.data.get("min_price")
        if value is not None and minimum is not None and value < minimum:
            raise ValueError("Giá tối đa phải lớn hơn hoặc bằng giá tối thiểu")
        return value

    @field_validator("check_out")
    @classmethod
    def checkout_after_checkin(cls, value: date, info):
        check_in = info.data.get("check_in")
        if check_in and value <= check_in:
            raise ValueError("Ngày trả phòng phải sau ngày nhận phòng")
        return value

    @field_validator("check_in")
    @classmethod
    def checkin_not_in_past(cls, value: date):
        if value < datetime.now(UTC).date():
            raise ValueError("Ngày nhận phòng không được ở quá khứ")
        return value


class BookingAssistanceRequest(BaseModel):
    snapshot_id: str
    offer_id: str = Field(min_length=1, max_length=300)
    ma_phien: str = Field(min_length=8, max_length=100)
    ghi_chu: str | None = Field(default=None, max_length=1000)

    @field_validator("ghi_chu")
    @classmethod
    def sanitize_note(cls, value: str | None) -> str | None:
        return " ".join(value.replace("<", "").replace(">", "").split()) if value else value


class BookingSupportUpdate(BaseModel):
    trang_thai: Literal["reviewing", "needs_customer", "handed_off", "cancelled"]
    phu_trach: str = Field(min_length=2, max_length=120)
    ghi_chu_noi_bo: str | None = Field(default=None, max_length=2000)
    provider_reference: str | None = Field(default=None, max_length=200)

    @field_validator("ghi_chu_noi_bo")
    @classmethod
    def sanitize_note(cls, value: str | None) -> str | None:
        return " ".join(value.replace("<", "").replace(">", "").split()) if value else value


class ActivitySearchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius: int = Field(default=10, ge=1, le=100)
    ma_phien: str = Field(min_length=8, max_length=100)


class TransferSearchRequest(BaseModel):
    start_location_code: str = Field(pattern=r"^[A-Z]{3}$")
    end_address_line: str = Field(min_length=3, max_length=200)
    end_city_name: str = Field(min_length=2, max_length=100)
    end_country_code: str = Field(pattern=r"^[A-Z]{2}$")
    end_name: str = Field(min_length=2, max_length=120)
    end_latitude: float = Field(ge=-90, le=90)
    end_longitude: float = Field(ge=-180, le=180)
    start_datetime: datetime
    passengers: int = Field(default=2, ge=1, le=9)
    transfer_type: Literal["PRIVATE", "SHARED", "TAXI", "HOURLY", "AIRPORT_EXPRESS"] = "PRIVATE"
    ma_phien: str = Field(min_length=8, max_length=100)

    @field_validator("start_datetime")
    @classmethod
    def timezone_required(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời gian đón phải có múi giờ")
        return value


class TripFeedbackRequest(BaseModel):
    diem: int = Field(ge=1, le=5)
    noi_dung: str | None = Field(default=None, max_length=2000)
    ma_phien: str

    @field_validator("noi_dung")
    @classmethod
    def sanitize_feedback(cls, value: str | None) -> str | None:
        return " ".join(value.replace("<", "").replace(">", "").split()) if value else value


class RoadTripStop(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: GlobalCoordinate

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, value: str) -> str:
        normalized = " ".join(value.replace("<", "").replace(">", "").split())
        if not normalized:
            raise ValueError("Stop name cannot be blank")
        return normalized


class RoadTripRequest(BaseModel):
    stops: list[RoadTripStop] = Field(min_length=2, max_length=10)
    round_trip: bool = False
    ma_phien: str | None = Field(default=None, min_length=8, max_length=100)

    @model_validator(mode="after")
    def distinct_stops(self):
        coordinates = [(stop.location.lat, stop.location.lng) for stop in self.stops]
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("Road-trip stops require unique coordinates")
        return self


class MultiCityStop(RoadTripStop):
    iata_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    arrival_date: date | None = None
    departure_date: date | None = None

    @model_validator(mode="after")
    def valid_stay(self):
        if bool(self.arrival_date) != bool(self.departure_date):
            raise ValueError("Cần nhập đủ ngày đến và ngày rời thành phố")
        if self.arrival_date and self.departure_date <= self.arrival_date:
            raise ValueError("Ngày rời phải sau ngày đến")
        if self.arrival_date and self.arrival_date < datetime.now(UTC).date():
            raise ValueError("Arrival date cannot be in the past")
        return self


class MultiCityRequest(BaseModel):
    stops: list[MultiCityStop] = Field(min_length=2, max_length=6)
    adults: int = Field(default=2, ge=1, le=9)
    rooms: int = Field(default=1, ge=1, le=9)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")
    ma_phien: str = Field(min_length=8, max_length=100)
    round_trip: bool = False

    @model_validator(mode="after")
    def chronological(self):
        invalid_order = any(
            previous.departure_date and current.arrival_date
            and current.arrival_date < previous.departure_date
            for previous, current in zip(self.stops, self.stops[1:], strict=False)
        )
        if invalid_order:
            raise ValueError("Các thành phố phải theo thứ tự thời gian")
        return self


class UserPreferencesRequest(BaseModel):
    ngon_ngu: Locale = "vi"
    tien_te: Literal["VND", "USD", "EUR", "GBP", "JPY", "KRW", "THB"] = "VND"
    don_vi: Literal["metric", "imperial"] = "metric"
    ma_phien: str = Field(min_length=8, max_length=100)


class OAuthRequest(BaseModel):
    provider: Literal["google"]
    token: str = Field(min_length=8)
    ma_phien: str
    consent: bool


class AccountDeleteRequest(BaseModel):
    confirmation: Literal["XOA TAI KHOAN"]


class ReadNotificationRequest(BaseModel):
    ma_phien: str = Field(min_length=8, max_length=100)
