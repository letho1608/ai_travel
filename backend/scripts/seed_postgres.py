"""Load the verified OSM catalogue and OSRM matrix into PostgreSQL."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/minhdidauthe"


def main() -> None:
    place_payload = json.loads(
        (ROOT / "data" / "places.json").read_text(encoding="utf-8")
    )
    places = place_payload["places"]
    matrix_payload = json.loads(
        (ROOT / "data" / "distance_matrix.json").read_text(encoding="utf-8")
    )
    matrix_ids = matrix_payload["place_ids"]
    durations = matrix_payload["durations_seconds"]
    distances = matrix_payload["distances_meters"]
    ids: dict[str, str] = {}
    with psycopg.connect(os.getenv("URL_CSDL_POSTGRES", DEFAULT_URL)) as connection:
        for place in places:
            row = connection.execute(
                """
                INSERT INTO dia_diem(
                  ten,ten_bo_dau,loai,khu_vuc,dia_chi,gia_trung_binh,tags,
                  phong_cach,gio_mo_cua,toa_do,mo_ta,hinh_anh,nguon,nguon_url,
                  ma_nguon,thoi_luong_phut
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(nguon_url) DO UPDATE SET
                  ten=EXCLUDED.ten, loai=EXCLUDED.loai, khu_vuc=EXCLUDED.khu_vuc,
                  dia_chi=EXCLUDED.dia_chi, tags=EXCLUDED.tags,
                  gio_mo_cua=EXCLUDED.gio_mo_cua, toa_do=EXCLUDED.toa_do,
                  ma_nguon=EXCLUDED.ma_nguon,
                  thoi_luong_phut=EXCLUDED.thoi_luong_phut, ngay_tao=now()
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
                    ), None, None, place.get("source", "OpenStreetMap"),
                    place.get("source_url"),
                    place.get("id"), place.get("duration_min", 60),
                ),
            ).fetchone()
            ids[str(place["id"])] = str(row[0])

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
    print(f"Seeded {len(ids)} OSM places and {inserted} OSRM routes.")


if __name__ == "__main__":
    main()
