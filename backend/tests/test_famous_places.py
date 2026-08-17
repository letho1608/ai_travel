"""Famous-place catalogue: no per-province cap, OSM/Wikidata provenance."""

from app.data import (
    FAMOUS_METADATA,
    FAMOUS_PLACES,
    Place,
    famous_priority,
    finalize_catalogue,
    is_famous_place,
    place_name_key,
)
from app.pipeline.planner import _is_iconic_place, _tourism_quality_score


FOCUS_LABELS = (
    "Hà Nội",
    "Huế",
    "Đà Nẵng",
    "Hội An",
    "Nha Trang",
    "TP.HCM",
    "Hạ Long",
    "Đà Lạt",
    "Ninh Bình",
    "Phú Quốc",
    "Sa Pa",
    "Vũng Tàu",
    "Cần Thơ",
)


def test_famous_file_is_loaded_without_a_per_province_cap():
    assert FAMOUS_METADATA.get("exists") is True, "run: python scripts/build_famous_places.py"
    assert FAMOUS_METADATA.get("no_per_province_cap") is True
    assert FAMOUS_METADATA.get("count", 0) == len(FAMOUS_PLACES)
    assert len(FAMOUS_PLACES) >= 500


def test_famous_file_covers_focus_destinations_without_truncating_to_12():
    grouped = FAMOUS_METADATA.get("by_tinh") or {}
    # These catalogues are dense on OSM; a 12-row cap would truncate them.
    for label in ("Hà Nội", "Huế", "Đà Nẵng", "TP.HCM", "Nha Trang", "Hội An"):
        count = int(grouped.get(label) or 0)
        assert count > 12, f"{label} only has {count} famous places; the file must not cap at 8–12"
    missing = [label for label in FOCUS_LABELS if int(grouped.get(label) or 0) == 0]
    assert missing == [], f"focus destinations with zero famous places: {missing}"


def test_famous_rows_keep_map_provenance():
    sources = {place.source for place in FAMOUS_PLACES}
    assert "OpenStreetMap" in sources
    osm_rows = [place for place in FAMOUS_PLACES if place.id.startswith("osm-")]
    assert osm_rows, "famous file should reuse OSM ids so existing catalogue rows can be ranked"
    assert all(place.source_url for place in osm_rows[:20])


def test_osm_catalogue_row_becomes_famous_after_merge():
    famous = next(place for place in FAMOUS_PLACES if place.id.startswith("osm-"))
    twin = Place(
        famous.id,
        famous.name,
        famous.kind,
        "Việt Nam",
        famous.lat,
        famous.lng,
        0,
        60,
        ("attraction",),
        7,
        22,
        "OpenStreetMap",
        famous.source_url,
    )
    merged = finalize_catalogue([twin])
    found = next(place for place in merged if place.id == famous.id)
    assert is_famous_place(found)
    assert famous_priority(found) >= 1
    assert found.area != "Việt Nam"
    assert "famous" in found.tags
    assert _is_iconic_place(found) or famous_priority(found) == 3
    if famous_priority(found) <= 2:
        assert _tourism_quality_score(found) >= 20


def test_finalize_catalogue_does_not_duplicate_famous_osm_ids():
    famous = next(place for place in FAMOUS_PLACES if place.id.startswith("osm-"))
    merged = finalize_catalogue([
        Place(
            famous.id, famous.name, famous.kind, famous.area,
            famous.lat, famous.lng, 0, 60, famous.tags, 7, 22,
            "OpenStreetMap", famous.source_url,
        )
    ])
    ids = [place.id for place in merged if place_name_key(place.name) == place_name_key(famous.name)]
    assert ids.count(famous.id) == 1
