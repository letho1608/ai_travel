"""Load the verified OSM catalogue and OSRM matrix into PostgreSQL."""

import argparse
import datetime as _dt
import json
import os
from datetime import datetime, timezone
from pathlib import Path

if not hasattr(_dt, "UTC"):
    _dt.UTC = timezone.utc
UTC = getattr(_dt, "UTC", timezone.utc)

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/minhdidauthe"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load a places.json-compatible catalogue and route matrix into PostgreSQL."
    )
    parser.add_argument(
        "--places",
        type=Path,
        default=Path(os.getenv("PLACES_DATA_FILE", "data/vietnam_places.json")),
        help="Path to a places.json-compatible catalogue. Defaults to PLACES_DATA_FILE or data/vietnam_places.json.",
    )
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("data/distance_matrix.json"),
        help="Path to a distance matrix JSON file.",
    )
    args = parser.parse_args()
    places_path = args.places if args.places.is_absolute() else ROOT / args.places
    matrix_path = args.matrix if args.matrix.is_absolute() else ROOT / args.matrix

    place_payload = json.loads(places_path.read_text(encoding="utf-8"))
    places = place_payload["places"]
    matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix_ids = matrix_payload["place_ids"]
    durations = matrix_payload["durations_seconds"]
    distances = matrix_payload["distances_meters"]

    # Imported lazily so this script never triggers app.data's Postgres branch
    # at import time; only the pure image/name helpers are needed here.
    from app.data import (
        CURATED_HANOI_ANCHORS,
        CURATED_HANOI_DINING,
        CURATED_NHA_TRANG_ANCHORS,
        CURATED_OTHER_PROVINCE_ANCHORS,
        PLACE_IMAGE_CREDITS_BY_NAME,
        PLACE_IMAGE_URLS_BY_NAME,
        place_name_key,
    )

    def recorded_image(item: dict) -> tuple[str | None, str | None]:
        """Source image_url/credit, falling back to the curated name-keyed map."""
        url = item.get("image_url") or PLACE_IMAGE_URLS_BY_NAME.get(place_name_key(item["name"]))
        credit = item.get("image_credit") or PLACE_IMAGE_CREDITS_BY_NAME.get(place_name_key(item["name"]))
        return url, credit

    ids: dict[str, str] = {}
    with psycopg.connect(os.getenv("URL_CSDL_POSTGRES", DEFAULT_URL)) as connection:
        for place in places:
            image_url, image_credit = recorded_image(place)
            row = connection.execute(
                """
                INSERT INTO dia_diem(
                  ten,ten_bo_dau,loai,khu_vuc,dia_chi,gia_trung_binh,tags,
                  phong_cach,gio_mo_cua,toa_do,mo_ta,hinh_anh,hinh_anh_nguon,
                  nguon,nguon_url,website,ma_nguon,thoi_luong_phut,
                  diem_danh_gia,so_nhan_xet,google_place_id,google_maps_url
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(nguon_url) DO UPDATE SET
                  ten=EXCLUDED.ten, loai=EXCLUDED.loai, khu_vuc=EXCLUDED.khu_vuc,
                  dia_chi=EXCLUDED.dia_chi, tags=EXCLUDED.tags,
                  gio_mo_cua=EXCLUDED.gio_mo_cua, toa_do=EXCLUDED.toa_do,
                  ma_nguon=EXCLUDED.ma_nguon, hinh_anh=EXCLUDED.hinh_anh,
                  hinh_anh_nguon=EXCLUDED.hinh_anh_nguon,
                  website=EXCLUDED.website,
                  thoi_luong_phut=EXCLUDED.thoi_luong_phut,
                  diem_danh_gia=EXCLUDED.diem_danh_gia,
                  so_nhan_xet=EXCLUDED.so_nhan_xet,
                  google_place_id=EXCLUDED.google_place_id,
                  google_maps_url=EXCLUDED.google_maps_url,
                  ngay_tao=now()
                RETURNING id
                """,
                (
                    place["name"], place["name"], place["kind"], place.get("area"),
                    place.get("address"), place.get("cost", 0), place.get("tags", []),
                    [], json.dumps(
                        {"open": place.get("open_hour", 7),
                         "close": place.get("close_hour", 22),
                         "raw": place.get("opening_hours_raw")}
                    ), json.dumps(
                        {"lat": place["lat"], "lng": place["lng"]}
                    ), None, image_url, image_credit,
                    place.get("source", "OpenStreetMap"),
                    place.get("source_url"), place.get("website"),
                    place.get("id"), place.get("duration_min", 60),
                    place.get("google_rating"), place.get("google_user_rating_count"),
                    place.get("google_place_id"), place.get("google_maps_url"),
                ),
            ).fetchone()
            ids[str(place["id"])] = str(row[0])

        # Seed the curated anchors/dining so the same stops exist in
        # production (ids = `curated-*`, images from the curated maps).
        curated_upserted = 0
        for curated in (
            *CURATED_HANOI_ANCHORS,
            *CURATED_HANOI_DINING,
            *CURATED_NHA_TRANG_ANCHORS,
            *CURATED_OTHER_PROVINCE_ANCHORS,
        ):
            image_url, image_credit = recorded_image(
                {"name": curated.name, "image_url": curated.image_url, "image_credit": curated.image_credit}
            )
            row = connection.execute(
                """
                INSERT INTO dia_diem(
                  ten,ten_bo_dau,loai,khu_vuc,dia_chi,gia_trung_binh,tags,
                  phong_cach,gio_mo_cua,toa_do,mo_ta,hinh_anh,hinh_anh_nguon,
                  nguon,nguon_url,website,ma_nguon,thoi_luong_phut,
                  diem_danh_gia,so_nhan_xet,google_place_id,google_maps_url
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(nguon_url) DO UPDATE SET
                  ten=EXCLUDED.ten, loai=EXCLUDED.loai, khu_vuc=EXCLUDED.khu_vuc,
                  tags=EXCLUDED.tags, gio_mo_cua=EXCLUDED.gio_mo_cua,
                  toa_do=EXCLUDED.toa_do, hinh_anh=EXCLUDED.hinh_anh,
                  hinh_anh_nguon=EXCLUDED.hinh_anh_nguon,
                  website=EXCLUDED.website,
                  thoi_luong_phut=EXCLUDED.thoi_luong_phut,
                  diem_danh_gia=EXCLUDED.diem_danh_gia,
                  so_nhan_xet=EXCLUDED.so_nhan_xet,
                  google_place_id=EXCLUDED.google_place_id,
                  google_maps_url=EXCLUDED.google_maps_url,
                  ngay_tao=now()
                RETURNING id
                """,
                (
                    curated.name, curated.name, curated.kind, curated.area,
                    None, curated.cost, list(curated.tags),
                    [], json.dumps({"open": curated.open_hour, "close": curated.close_hour}),
                    json.dumps({"lat": curated.lat, "lng": curated.lng}),
                    None, image_url, image_credit,
                    "curated", f"curated:{curated.id}", None, curated.id, curated.duration_min,
                    curated.rating, curated.review_count, curated.google_place_id, curated.google_maps_url,
                ),
            ).fetchone()
            ids[curated.id] = str(row[0])
            curated_upserted += 1

        inserted = 0
        for origin_index, origin in enumerate(matrix_ids):
            for destination_index, destination in enumerate(matrix_ids):
                if origin not in ids or destination not in ids or origin == destination:
                    continue
                seconds = durations[origin_index][destination_index]
                metres = distances[origin_index][destination_index]
                if seconds is None or metres is None:
                    continue
                connection.execute(
                    """
                    INSERT INTO bang_khoang_cach(
                      diem_a_id,diem_b_id,phuong_tien,khoang_cach_met,
                      thoi_gian_giay,ngay_cap_nhat
                    ) VALUES(%s,%s,'driving',%s,%s,%s)
                    ON CONFLICT(diem_a_id,diem_b_id,phuong_tien) DO UPDATE SET
                      khoang_cach_met=EXCLUDED.khoang_cach_met,
                      thoi_gian_giay=EXCLUDED.thoi_gian_giay,
                      ngay_cap_nhat=EXCLUDED.ngay_cap_nhat
                    """,
                    (ids[origin], ids[destination], round(metres), round(seconds),
                     datetime.now(UTC)),
                )
                inserted += 1
    print(
        f"Seeded {len(ids)} places from {places_path} and {inserted} OSRM routes; "
        f"{curated_upserted} curated anchors upserted."
    )


if __name__ == "__main__":
    main()
