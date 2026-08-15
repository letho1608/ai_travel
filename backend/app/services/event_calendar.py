from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from app.config import settings


def _parse_generated_at(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None


def official_event_calendar_status(today: date | None = None) -> dict:
    """Validate the official event/festival calendar required for release timing logic."""
    today = today or datetime.now(UTC).date()
    path_value = settings.event_calendar_file
    base = {
        "required": settings.app_env != "local",
        "path": path_value,
        "max_age_days": settings.event_calendar_max_age_days,
        "min_cities": settings.event_calendar_min_cities,
        "min_events": settings.event_calendar_min_events,
    }
    if not path_value:
        note = "Configure EVENT_CALENDAR_FILE with official event/festival calendar data before release."
        return {
            **base,
            "status": "missing_event_calendar_file",
            "ready": False,
            "note": note,
            "blockers": [note],
        }

    path = Path(path_value)
    if not path.exists():
        note = "EVENT_CALENDAR_FILE does not exist."
        return {
            **base,
            "status": "missing_event_calendar_file",
            "ready": False,
            "note": note,
            "blockers": [note],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        note = str(exc)[:300]
        return {
            **base,
            "status": "invalid_event_calendar_file",
            "ready": False,
            "note": note,
            "blockers": [note],
        }

    generated_at = _parse_generated_at(payload.get("generated_at"))
    if not generated_at:
        note = "generated_at must be an ISO date or datetime."
        return {
            **base,
            "status": "invalid_event_calendar_file",
            "ready": False,
            "note": note,
            "blockers": [note],
        }
    age_days = (today - generated_at).days
    if age_days < 0:
        note = "generated_at cannot be in the future."
        return {
            **base,
            "status": "invalid_event_calendar_file",
            "ready": False,
            "generated_at": generated_at.isoformat(),
            "age_days": age_days,
            "note": note,
            "blockers": [note],
        }

    cities_payload = payload.get("cities")
    if not isinstance(cities_payload, dict):
        note = "cities must be an object keyed by focus city."
        return {
            **base,
            "status": "invalid_event_calendar_file",
            "ready": False,
            "generated_at": generated_at.isoformat(),
            "age_days": age_days,
            "note": note,
            "blockers": [note],
        }

    city_count = 0
    event_count = 0
    source_urls = set()
    for city_key, events in cities_payload.items():
        if not isinstance(city_key, str) or not isinstance(events, list) or not events:
            continue
        city_count += 1
        for event in events:
            if not isinstance(event, dict):
                continue
            name = str(event.get("name", "")).strip()
            start_date = _parse_generated_at(event.get("start_date"))
            source_url = str(event.get("source_url", "")).strip()
            if name and start_date and source_url:
                event_count += 1
                source_urls.add(source_url)

    if age_days > settings.event_calendar_max_age_days:
        note = "Official event/festival calendar is older than the allowed freshness window."
        return {
            **base,
            "status": "stale_event_calendar_file",
            "ready": False,
            "generated_at": generated_at.isoformat(),
            "age_days": age_days,
            "city_count": city_count,
            "event_count": event_count,
            "source_url_count": len(source_urls),
            "note": note,
            "blockers": [note],
        }
    if city_count < settings.event_calendar_min_cities:
        note = f"Official event/festival calendar covers {city_count} cities, below required {settings.event_calendar_min_cities}."
        return {
            **base,
            "status": "insufficient_event_city_coverage",
            "ready": False,
            "generated_at": generated_at.isoformat(),
            "age_days": age_days,
            "city_count": city_count,
            "event_count": event_count,
            "source_url_count": len(source_urls),
            "note": note,
            "blockers": [note],
        }
    if event_count < settings.event_calendar_min_events:
        note = f"Official event/festival calendar has {event_count} sourced events, below required {settings.event_calendar_min_events}."
        return {
            **base,
            "status": "insufficient_event_coverage",
            "ready": False,
            "generated_at": generated_at.isoformat(),
            "age_days": age_days,
            "city_count": city_count,
            "event_count": event_count,
            "source_url_count": len(source_urls),
            "note": note,
            "blockers": [note],
        }

    return {
        **base,
        "status": "ready",
        "ready": True,
        "generated_at": generated_at.isoformat(),
        "age_days": age_days,
        "city_count": city_count,
        "event_count": event_count,
        "source_url_count": len(source_urls),
        "source": payload.get("source") or "official_event_calendar",
        "blockers": [],
    }
