from __future__ import annotations

from app.data import PLACES, PLACE_METADATA, Place, image_for, source_for
from app.pipeline.routing import haversine_km


def _has_numeric(place: Place, *names: str) -> bool:
    return any(isinstance(getattr(place, name, None), int | float) for name in names)


def _valid_hours(place: Place) -> bool:
    return 0 <= place.open_hour < place.close_hour <= 24


def _percent(count: int, total: int) -> float:
    return round((count / total * 100) if total else 0, 2)


def _source_quality(place: Place) -> str:
    url, label = source_for(place)
    if label == "official_website":
        return "official_website"
    if label == "curated_editorial_source":
        return "curated_editorial_source"
    if label == "google_places_source":
        return "google_places_source"
    if url and "openstreetmap.org" in url:
        return "openstreetmap_source"
    if url:
        return "third_party_source"
    return "missing_source"


def _source_quality_counts(places: list[Place]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for place in places:
        key = _source_quality(place)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def catalogue_field_coverage(
    *,
    focus_destinations: dict[str, dict[str, object]] | None = None,
    radius_km: float = 45.0,
) -> dict:
    total = len(PLACES)
    counts = {
        "source_url": sum(1 for place in PLACES if source_for(place)[0]),
        "image": sum(1 for place in PLACES if place.image_url or image_for(place)[0]),
        "valid_hours": sum(1 for place in PLACES if _valid_hours(place)),
        "rating": sum(1 for place in PLACES if _has_numeric(place, "rating", "diem_danh_gia", "google_rating")),
        "review_count": sum(1 for place in PLACES if _has_numeric(place, "review_count", "so_nhan_xet", "google_review_count")),
        "official_or_enriched_source": sum(
            1
            for place in PLACES
            if place.source not in {"OpenStreetMap", "curated"}
            or ((source_url := source_for(place)[0]) and "openstreetmap.org" not in source_url)
        ),
    }
    fields = {
        key: {"count": value, "percent": _percent(value, total)}
        for key, value in counts.items()
    }
    by_source: dict[str, int] = {}
    for place in PLACES:
        by_source[place.source] = by_source.get(place.source, 0) + 1
    source_quality_counts = _source_quality_counts(list(PLACES))
    focus_city_field_coverage = {}
    if focus_destinations:
        for key, destination in focus_destinations.items():
            city_places = [
                place
                for place in PLACES
                if haversine_km(float(destination["lat"]), float(destination["lng"]), place.lat, place.lng)
                <= radius_km
            ]
            city_total = len(city_places)
            focus_city_field_coverage[key] = {
                "place_count": city_total,
                "source_url_percent": _percent(sum(1 for place in city_places if source_for(place)[0]), city_total),
                "image_percent": _percent(sum(1 for place in city_places if place.image_url or image_for(place)[0]), city_total),
                "valid_hours_percent": _percent(sum(1 for place in city_places if _valid_hours(place)), city_total),
                "official_or_enriched_source_percent": _percent(
                    sum(
                        1
                        for place in city_places
                        if _source_quality(place) in {
                            "official_website",
                            "curated_editorial_source",
                            "google_places_source",
                            "third_party_source",
                        }
                    ),
                    city_total,
                ),
                "source_quality_counts": _source_quality_counts(city_places),
            }
    return {
        "place_count": total,
        "metadata": PLACE_METADATA,
        "fields": fields,
        "source_counts": dict(sorted(by_source.items(), key=lambda item: item[1], reverse=True)),
        "source_quality_counts": source_quality_counts,
        "google_places_fields": {
            "place_id": {
                "count": sum(1 for place in PLACES if place.google_place_id),
                "percent": _percent(sum(1 for place in PLACES if place.google_place_id), total),
            },
            "maps_url": {
                "count": sum(1 for place in PLACES if place.google_maps_url),
                "percent": _percent(sum(1 for place in PLACES if place.google_maps_url), total),
            },
        },
        "focus_city_field_coverage": focus_city_field_coverage,
        "release_thresholds": {
            "source_url_percent": 95,
            "image_percent": 80,
            "rating_percent": 80,
            "review_count_percent": 80,
            "official_or_enriched_source_percent": 70,
            "valid_hours_percent": 99,
        },
        "notes": [
            "Rating/review fields count only real catalog/cache attributes; missing values are not imputed.",
            "Image coverage includes curated image parity via image_for(place).",
            "official_or_enriched_source counts official websites, curated editorial sources, or non-OSM third-party sources.",
            "source_quality_counts separates OpenStreetMap source URLs from stronger official/editorial evidence.",
        ],
    }
