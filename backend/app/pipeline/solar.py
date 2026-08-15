from __future__ import annotations

import math
from datetime import date


VIETNAM_TIMEZONE_OFFSET_HOURS = 7
SUNSET_SOURCE = "noaa_solar_position_approximation"


def _normalize_degrees(value: float) -> float:
    return value % 360


def _minutes_to_clock(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def sunset_for_date(
    day: date,
    latitude: float,
    longitude: float,
    *,
    timezone_offset_hours: int = VIETNAM_TIMEZONE_OFFSET_HOURS,
) -> dict:
    """Approximate local sunset using NOAA's public solar position equations."""
    day_of_year = day.timetuple().tm_yday
    lng_hour = longitude / 15
    t = day_of_year + ((18 - lng_hour) / 24)
    mean_anomaly = (0.9856 * t) - 3.289
    true_longitude = _normalize_degrees(
        mean_anomaly
        + (1.916 * math.sin(math.radians(mean_anomaly)))
        + (0.020 * math.sin(math.radians(2 * mean_anomaly)))
        + 282.634
    )
    right_ascension = math.degrees(
        math.atan(0.91764 * math.tan(math.radians(true_longitude)))
    )
    right_ascension = _normalize_degrees(right_ascension)
    longitude_quadrant = math.floor(true_longitude / 90) * 90
    ascension_quadrant = math.floor(right_ascension / 90) * 90
    right_ascension = (right_ascension + longitude_quadrant - ascension_quadrant) / 15

    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    zenith = 90.833
    cos_hour_angle = (
        math.cos(math.radians(zenith))
        - (sin_declination * math.sin(math.radians(latitude)))
    ) / (cos_declination * math.cos(math.radians(latitude)))
    if cos_hour_angle > 1:
        return {
            "co_san": False,
            "trang_thai": "sun_never_rises",
            "nguon": SUNSET_SOURCE,
        }
    if cos_hour_angle < -1:
        return {
            "co_san": False,
            "trang_thai": "sun_never_sets",
            "nguon": SUNSET_SOURCE,
        }

    hour_angle = math.degrees(math.acos(cos_hour_angle)) / 15
    local_mean_time = hour_angle + right_ascension - (0.06571 * t) - 6.622
    utc_hour = (local_mean_time - lng_hour) % 24
    local_hour = (utc_hour + timezone_offset_hours) % 24
    minutes = int(round(local_hour * 60)) % (24 * 60)
    return {
        "co_san": True,
        "trang_thai": "computed",
        "hoang_hon": _minutes_to_clock(minutes),
        "hoang_hon_phut": minutes,
        "mui_gio": f"UTC+{timezone_offset_hours}",
        "nguon": SUNSET_SOURCE,
        "do_chinh_xac": "approx_5_10_minutes",
    }

