"""Image + curated-anchor parity across catalogue modes.

These tests drive the shipped catalogue-assembly functions
(`app.data.finalize_catalogue`, `app.data.image_for`) and the real planning
entry point (`app.pipeline.planner.build_plan`) with a Postgres-style
catalogue (ids are `ma_nguon`/`osm-*` values, no `curated-*` entries) — the
exact shape `_load_postgres_places()` produces. They intentionally do NOT
stub `image_for` or re-implement the resolution logic.
"""

from app import data as data_module
from app.data import (
    PLACE_IMAGE_CREDITS,
    PLACE_IMAGE_URLS,
    CURATED_HANOI_ANCHORS,
    CURATED_HANOI_DINING,
    Place,
    place_name_key,
)
from app.pipeline import planner
from app.pipeline.planner import build_plan
from app.schemas import PlanRequest


def request() -> PlanRequest:
    return PlanRequest(
        context="cuối tuần chill và ăn ngon",
        location={"lat": 21.0285, "lng": 105.8542},
        thoi_luong="ca_ngay",
        so_nguoi=2,
        ngan_sach=1_000_000,
        ma_phien="parity-test-session",
    )


POSTGRES_STYLE_CATALOGUE = data_module.finalize_catalogue(data_module.IMPORTED_PLACES)


def test_finalize_catalogue_appends_all_curated_anchors_when_catalogue_is_empty():
    merged = data_module.finalize_catalogue([])
    ids = {place.id for place in merged}
    assert {"curated-ho-guom", "curated-hang-dao", "curated-pho-ta-hien"} <= ids
    # no two merged curated rows share a normalized name
    keys = [place_name_key(place.name) for place in merged]
    assert len(keys) == len(set(keys))


def test_finalize_catalogue_dedups_by_name_keeping_catalogue_row():
    base = [
        Place(
            "osm-pho-ta-hien", "Phố Tạ Hiện", "dia_danh", "Hoàn Kiếm",
            21.0353, 105.8522, 0, 75, ("attraction",), 7, 23,
            "OpenStreetMap", "https://osm.org/way/765597030",
        )
    ]
    merged = data_module.finalize_catalogue(base)
    ids = [place.id for place in merged]
    assert "osm-pho-ta-hien" in ids, (
        "catalogue row must win the name collision (curated twin dropped)"
    )
    assert "curated-pho-ta-hien" not in ids
    # other non-colliding curated anchors are still appended
    assert "curated-ho-guom" in ids


def test_postgres_style_catalogue_keeps_curated_anchor_names():
    names = {place_name_key(place.name) for place in POSTGRES_STYLE_CATALOGUE}
    for anchor in (
        "Hồ Gươm",
        "Hồ Tây",
        "Lăng Chủ tịch Hồ Chí Minh",
        "Phố cổ Hà Nội",
        "Chợ đêm Hàng Đào – Đồng Xuân",
        "Phố Tạ Hiện",
    ):
        assert place_name_key(anchor) in names, f"missing {anchor} in Postgres-style catalogue"
    # every curated anchor resolves to an id in the merged catalogue: either
    # its own `curated-*` id (no same-name row) or a same-name `osm-*` row.
    catalogue_ids = {place.id for place in POSTGRES_STYLE_CATALOGUE}
    by_name = {place_name_key(place.name): place for place in POSTGRES_STYLE_CATALOGUE}
    for curated in (*CURATED_HANOI_ANCHORS, *CURATED_HANOI_DINING):
        resolved = (
            curated.id in catalogue_ids
            or place_name_key(curated.name) in by_name
        )
        assert resolved, f"curated anchor {curated.id} unresolved in Postgres-style catalogue"


def test_postgres_style_night_intent_plan_has_curated_evening_stop(monkeypatch):
    monkeypatch.setattr(planner, "PLACES", POSTGRES_STYLE_CATALOGUE)
    plan = build_plan(
        request().model_copy(
            update={
                "context": "du lịch Hà Nội cả ngày và buổi tối, sau bữa tối đi chợ đêm",
                "thoi_luong": "ca_ngay",
                "nonce": "nonce-pg-night-0001",
            }
        )
    )
    slots = plan["ngay"][0]["khoang_gio"]
    dinner = next((slot for slot in slots if slot.get("bua_an") == "toi"), None)
    assert dinner is not None
    after_dinner = [slot for slot in slots if slot["bat_dau"] >= dinner["ket_thuc"]]
    assert after_dinner, "expected at least one after-dinner stop in Postgres mode"
    night_names = {place_name_key("Chợ đêm Hàng Đào – Đồng Xuân"), place_name_key("Phố Tạ Hiện")}
    after_keys = {place_name_key(slot["ten_dia_diem"]) for slot in after_dinner}
    assert night_names.intersection(after_keys), (
        "after-dinner stop should be a curated night stop, got "
        f"{sorted(after_keys)}"
    )


def test_image_for_returns_url_and_credit_for_every_curated_anchor():
    for curated in (*CURATED_HANOI_ANCHORS, *CURATED_HANOI_DINING):
        url, credit = data_module.image_for(curated)
        assert url and url.startswith("https://commons.wikimedia.org/"), curated.id
        assert credit and credit.startswith("Wikimedia Commons"), curated.id
        assert PLACE_IMAGE_URLS[curated.id] == url, curated.id
        assert PLACE_IMAGE_CREDITS[curated.id] == credit, curated.id


def test_image_for_resolves_recorded_catalogue_images_from_live_mapping():
    from app.data import PLACE_IMAGE_CREDITS_BY_NAME, PLACE_IMAGE_URLS_BY_NAME

    catalogued = []
    for place in data_module.PLACES:
        key = place_name_key(place.name)
        if place.image_url or key in PLACE_IMAGE_URLS_BY_NAME:
            catalogued.append(place)
    assert catalogued, "expected image-bearing places in the loaded catalogue"
    for place in catalogued:
        url, credit = data_module.image_for(place)
        key = place_name_key(place.name)
        expected_url = place.image_url or PLACE_IMAGE_URLS_BY_NAME[key]
        assert url == expected_url, place.id
        expected_credit = place.image_credit or PLACE_IMAGE_CREDITS_BY_NAME.get(key)
        assert credit == expected_credit or (expected_credit is None and credit is not None), place.id
        assert url and url.startswith("https://"), place.id


def test_no_dead_image_keys_in_any_supported_catalogue():
    """Every image-map key resolves to a place in at least one catalogue mode.

    A key is live when its id is present in the loaded catalogue, when the
    place with that (canonical) name exists there — the name-key resolution
    path — or when it belongs to the demo/demo-curated catalogue used when
    places.json is absent.
    """
    loaded_ids = {place.id for place in data_module.PLACES}
    loaded_names = {place_name_key(place.name) for place in data_module.PLACES}
    demo_ids = {place.id for place in data_module.finalize_catalogue(data_module.DEMO_PLACES)}
    unresolved = [
        place_id
        for place_id in PLACE_IMAGE_URLS
        if place_id not in loaded_ids
        and place_id not in demo_ids
        and (
            (name := data_module.KNOWN_PLACE_NAMES_BY_ID.get(place_id)) is None
            or place_name_key(name) not in loaded_names
        )
    ]
    assert unresolved == [], f"dead image keys: {unresolved}"


def test_image_for_name_fallback_matches_osm_twin():
    """An OSM/Postgres row whose id is `osm-*` still gets the curated photo."""
    osm_twin = next(place for place in POSTGRES_STYLE_CATALOGUE if place.id == "osm-way-37625751")
    url, credit = data_module.image_for(osm_twin)
    curated = next(place for place in CURATED_HANOI_ANCHORS if place.id == "curated-lang-bac")
    assert url == PLACE_IMAGE_URLS[curated.id]
    assert credit == PLACE_IMAGE_CREDITS[curated.id]