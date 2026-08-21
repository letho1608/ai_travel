from dataclasses import replace

from app.services import google_places, place_images


def _plan(slots: list[dict], destination: str = "Hạ Long") -> dict:
    return {
        "tieu_de": f"Lịch trình {destination}",
        "dau_vao_da_hieu": {
            "diem_den": {"gia_tri": {"ten": destination}},
        },
        "ngay": [{"thu_tu": 1, "khoang_gio": slots}],
    }


def test_wikipedia_fills_missing_slot_and_cover(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")

    def fake_request(url, timeout=4.0):
        assert "wikipedia.org" in url
        return {
            "query": {
                "pages": {
                    "1": {
                        "title": "Vịnh Hạ Long",
                        "thumbnail": {
                            "source": "https://upload.wikimedia.org/wikipedia/commons/halong.jpg"
                        },
                    }
                }
            }
        }

    monkeypatch.setattr(place_images, "_request_json", fake_request)
    plan = _plan([{"dia_diem_id": "osm-1", "ten_dia_diem": "Vịnh Hạ Long"}], destination="Phú Thọ")

    filled = place_images.enrich_plan_images(plan)

    slot = filled["ngay"][0]["khoang_gio"][0]
    assert slot["anh"] == "https://upload.wikimedia.org/wikipedia/commons/halong.jpg"
    assert "Wikipedia" in str(slot["anh_nguon"])
    assert filled["anh_bia"] == slot["anh"]


def test_wikipedia_keeps_catalog_image(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(place_images, "_request_json", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not call wiki")))
    plan = _plan(
        [
            {
                "dia_diem_id": "osm-1",
                "ten_dia_diem": "Vịnh Hạ Long",
                "anh": "https://commons.wikimedia.org/wiki/Special:FilePath/existing.jpg?width=800",
                "anh_nguon": "catalog",
            }
        ],
        destination="Phú Thọ",
    )

    filled = place_images.enrich_plan_images(plan)

    slot = filled["ngay"][0]["khoang_gio"][0]
    assert slot["anh"].endswith("existing.jpg?width=800")
    assert slot["anh_nguon"] == "catalog"
    assert filled["anh_bia"] == slot["anh"]


def test_wikipedia_rejects_unrelated_title(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(
        place_images,
        "_request_json",
        lambda *args, **kwargs: {
            "query": {
                "pages": {
                    "1": {
                        "title": "List of restaurants",
                        "thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/wrong.jpg"},
                    }
                }
            }
        },
    )
    plan = _plan([{"dia_diem_id": "osm-1", "ten_dia_diem": "Hải sản Bé Mặn"}])

    filled = place_images.enrich_plan_images(plan)

    assert "anh" not in filled["ngay"][0]["khoang_gio"][0]


def test_wikipedia_rejects_coffee_machine_for_cafe(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(
        place_images,
        "_request_json",
        lambda *args, **kwargs: {
            "query": {
                "pages": {
                    "1": {
                        "title": "Máy pha cà phê",
                        "thumbnail": {
                            "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Consumer_Reports_-_Zojirushi_coffeemaker_alt.tif/lossy-page1-960px.jpg"
                        },
                    }
                }
            }
        },
    )
    plan = _plan(
        [{"dia_diem_id": "osm-1", "ten_dia_diem": "Cà phê pha máy"}],
        destination="Phú Thọ",
    )
    filled = place_images.enrich_plan_images(plan)
    assert "anh" not in filled["ngay"][0]["khoang_gio"][0]
    assert "zojirushi" not in str(filled.get("anh_bia") or "").casefold()


def test_google_does_not_overwrite_existing_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(
            google_places.settings,
            google_maps_api_key="test-key",
            google_places_runtime_photos=True,
        ),
    )
    slot = {
        "dia_diem_id": "osm-1",
        "ten_dia_diem": "Vịnh Hạ Long",
        "anh": "https://upload.wikimedia.org/wikipedia/commons/halong.jpg",
        "anh_nguon": "Wikipedia (vi: Vịnh Hạ Long)",
    }
    google_places._apply_enrichment(
        slot,
        {"google_photo_name": "places/abc/photos/1", "google_place_id": "abc"},
        "test-key",
    )
    assert slot["anh"] == "https://upload.wikimedia.org/wikipedia/commons/halong.jpg"
    assert slot["anh_nguon"] == "Wikipedia (vi: Vịnh Hạ Long)"


def test_google_fills_missing_photo_from_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(google_places, "CACHE_PATH", tmp_path / "google_place_cache.json")
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(
        google_places,
        "settings",
        replace(
            google_places.settings,
            google_maps_api_key="test-key",
            google_places_runtime_photos=False,
        ),
    )
    tmp_path.joinpath("google_place_cache.json").write_text(
        """{"places":{"osm-1":{"google_photo_name":"places/abc/photos/1","google_place_id":"abc"}},"metadata":{}}""",
        encoding="utf-8",
    )
    plan = _plan([{"dia_diem_id": "osm-1", "ten_dia_diem": "Quán ven biển chưa có wiki"}], destination="Phú Thọ")

    filled = google_places.enrich_plan_with_google(plan)

    slot = filled["ngay"][0]["khoang_gio"][0]
    assert slot["anh"].startswith("https://places.googleapis.com/v1/places/abc/photos/1/media")
    assert slot["anh_nguon"] == "Google Places"
    assert filled["anh_bia"] == slot["anh"]


def test_cat_ba_cover_uses_destination_catalog_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(place_images, "_request_json", lambda *args, **kwargs: None)
    plan = _plan(
        [{"dia_diem_id": "curated-thi-tran-cat-ba", "ten_dia_diem": "Thị trấn Cát Bà"}],
        destination="Cát Bà",
    )
    plan["tieu_de"] = "Lịch trình du lịch chữa lành Cát Bà 2 ngày cho 2 người"

    filled = place_images.enrich_plan_images(plan)

    assert filled["anh_bia"]
    assert "Cat_Ba" in filled["anh_bia"] or "Cat%20Ba" in filled["anh_bia"]


def test_da_lat_cover_is_lake_not_first_cafe(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(place_images, "_request_json", lambda *args, **kwargs: None)
    plan = _plan(
        [
            {
                "dia_diem_id": "osm-cafe",
                "ten_dia_diem": "Góc cà phê Đà Lạt",
                "loai": "cafe",
                "anh": "https://example.com/zojirushi-coffee-maker.jpg",
                "anh_nguon": "Wikipedia",
            }
        ],
        destination="Đà Lạt",
    )
    plan["tieu_de"] = "Lịch trình du lịch chữa lành Đà Lạt 1 ngày cho 4 người"
    plan["anh_bia"] = "https://example.com/zojirushi-coffee-maker.jpg"

    filled = place_images.enrich_plan_images(plan)

    assert "Huy_Phuong" in filled["anh_bia"] or "Ho_Xuan_Huong" in filled["anh_bia"]
    assert "zojirushi" not in filled["anh_bia"].casefold()


def test_city_covers_use_scenic_landmarks(monkeypatch, tmp_path):
    monkeypatch.setattr(place_images, "CACHE_PATH", tmp_path / "place_image_cache.json")
    monkeypatch.setattr(place_images, "_request_json", lambda *args, **kwargs: None)
    for city, needle in (
        ("Hà Nội", "Hoan"),
        ("Đà Nẵng", "My_Khe"),
        ("Hội An", "Hoi_An"),
        ("Huế", "Imperial_City_Hue"),
        ("Nha Trang", "Nha%20Trang%20Bay"),
        ("Sa Pa", "Fansipan"),
        ("TP.HCM", "Saigon"),
    ):
        plan = _plan(
            [
                {
                    "dia_diem_id": "osm-cafe",
                    "ten_dia_diem": f"Cafe {city}",
                    "loai": "cafe",
                    "anh": "https://example.com/coffee-machine.jpg",
                }
            ],
            destination=city,
        )
        filled = place_images.enrich_plan_images(plan)
        assert needle in filled["anh_bia"] or needle.replace("_", "%20") in filled["anh_bia"], city
        assert "coffee-machine" not in filled["anh_bia"]
