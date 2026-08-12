# Kế hoạch sửa lỗi hardcode (theo kết quả deep-dive)

> Trạng thái: **đang triển khai** — cập nhật tại `## Tiến độ` và `## Đã làm`.

## Mục tiêu

Khắc phục các lỗi do dữ liệu hardcode phát hiện trong deep-dive, theo 3 tiêu chí:

1. **Curated anchors hoạt động trong chế độ catalogue không-local (Postgres).** Khi catalogue là danh sách kiểu Postgres (chỉ id `osm-*`, không có mục `curated-*` — tương ứng `dia_diem.ma_nguon`), catalogue dùng để lập kế hoạch vẫn chứa các anchor Hà Nội (Hồ Gươm, Hồ Tây, Lăng Chủ tịch Hồ Chí Minh, Phố cổ Hà Nội, Chợ đêm Hàng Đào–Đồng Xuân, Phố Tạ Hiện), khử trùng theo tên chuẩn hóa với các dòng catalogue. Plan "buổi tối/điểm nổi bật" chọn được một trong các điểm đêm curated cho slot sau bữa tối (trước đây rơi vào slot trống/chung chung).
2. **Ảnh phân giải đúng ở mọi chế độ (parity local ⟷ Postgres).**
   - `PLACE_IMAGE_URLS` / `PLACE_IMAGE_CREDITS` không còn key chết — mọi key phân giải tới một địa điểm tồn tại trong catalogue đã nạp (hoặc là anchor `curated-*` sau merge);
   - `seed_postgres.py` ghi `image_url`/`image_credit` vào `dia_diem.hinh_anh` (+ cột credit) thay vì ghi cứng `NULL`, và giữ chúng khi upsert;
   - với catalogue kiểu Postgres + curated anchors đã merge, mọi slot của địa điểm curated/có ảnh mang `"anh"` và `"anh_nguon"` không rỗng.
3. **Sửa bảng màu dark-mode trong `frontend/app/globals.css`.** Bỏ block `:root` trùng lặp (block thứ hai re-pin `--brand:#086b27`); token hóa/thêm override dark cho `.action-toast`, `.itinerary-summary-badge`, `.itinerary-regenerate`, `.itinerary-summary-actions .primary`, `.result-back-to-chat`, `.result-ready-badge`; cặp `.itinerary-regenerate` đạt WCAG-AA ≥ 4.5:1 ở CẢ hai palette (dark hiện đo 1.99:1).

## Phạm vi không làm (deferred)

- Di trọn i18n các trang `history`, `support`, `admin` vào hệ thống `t()` (cần quyết định sản phẩm về mức độ localize trang admin).
- Hardening env frontend (fail-fast khi thiếu `NEXT_PUBLIC_API_URL`) và lời khuyên credentials `docker-compose.yml` — ghi nhận, chưa sửa code.
- Chương trình ảnh rộng hơn (wikidata→P18→Commons cascade, `place_images.json` overlay, admin `image_coverage_percent`, job refresh tuần, hiển thị `anh_nguon` trong `PlanView.tsx`). Chỉ làm parity để ảnh đã ghi nhận sống sót tới Postgres.
- Sửa flash `<html lang="vi">` SSR và các phát hiện khác ngoài 3 tiêu chí.

## Đã làm

### Backend

- **`backend/app/data.py`**
  - Thêm `place_name_key()` — chuẩn hóa tên (bỏ dấu, gạch en/em → `-`, gộp khoảng trắng) làm định danh ổn định xuyên các chế độ catalogue.
  - Gỡ 4 key ảnh demo chết (`ho-guom`, `van-mieu`, `chua-tran-quoc`, `long-bien` — địa điểm không tồn tại trong places.json/OSM); giữ `bao-tang-phu-nu` (twin OSM tồn tại).
  - Thêm `finalize_catalogue(rows)` — bước merge thuần: dòng catalogue thắng khi trùng tên; anchor curated chỉ được thêm nếu chưa có dòng cùng tên chuẩn hóa. Dùng chung cho cả đường local lẫn Postgres.
  - Đổi danh sách demo `PLACES` → `DEMO_PLACES`; `PLACES = finalize_catalogue(IMPORTED_PLACES if ... else DEMO_PLACES)`.
  - Thêm `KNOWN_PLACE_NAMES_BY_ID` (id curated/demo → tên) để planner phân giải id bằng tên.
  - Thêm `PLACE_IMAGE_URLS_BY_NAME` / `PLACE_IMAGE_CREDITS_BY_NAME` (project id→tên) + `image_for()` dự phòng theo tên (place.image_url → map theo id → map theo tên), kèm credit.
  - Đường Postgres: `_load_postgres_places()` đọc thêm cột `hinh_anh_nguon` → `Place.image_credit`; sau load áp `finalize_catalogue()`.
- **`backend/app/pipeline/planner.py`** (đang dở)
  - Import `KNOWN_PLACE_NAMES_BY_ID`.
  - Thêm `_name_key(name)` và `_place_name_key()` dùng chung; thêm `_resolve_by_id()` — phân giải id curated/demo: theo id trước, theo tên chuẩn hóa sau (để catalogue `ma_nguon` vẫn tìm thấy điểm curated).
  - `_highlight_places()` chuyển sang `_resolve_by_id()` (thay `by_id.get` cũ).
  - Còn lại: `_choose_evening_place.pick()` dùng `_resolve_by_id`; `_is_evening_place()` nhận diện theo tên.

## Sắp làm (theo thứ tự)

1. **planner.py** — `_choose_evening_place.pick()` dùng `_resolve_by_id`; `_is_evening_place()` thêm so khớp tên chuẩn hóa với `EVENING_PLACE_IDS`/`EVENING_FALLBACK_IDS`.
2. **`backend/scripts/seed_postgres.py` + schema** — ghi `hinh_anh`/`hinh_anh_nguon` từ source catalogue (image_url hoặc map theo tên) khi INSERT và ON CONFLICT DO UPDATE; thêm cột `hinh_anh_nguon` idempotent vào `backend/alembic/versions/0001_initial.sql`; upsert các curated anchors (nguon_url `curated:<id>`, ma_nguon = id curated, kèm ảnh).
3. **Test backend** — trong `backend/tests/test_pipeline.py` (+ có thể `tests/test_image_parity.py`):
   - catalogue kiểu Postgres (osm-only ids) + merge curated → build_plan intent đêm có slot sau bữa tối thuộc nhóm điểm đêm curated;
   - `image_for` trả URL + credit cho mọi anchor curated và mọi tên catalogue có ảnh (đối chiếu mapping sống, không viết lại giá trị cứng);
   - không còn key ảnh chết (mọi key phân giải tới địa điểm trong catalogue đã nạp hoặc theo tên);
   - chạy `python -m pytest -q` toàn bộ → exit 0. Sẽ điều chỉnh 2 assertion cũ sang so khớp theo tên chuẩn hóa (lý do: catalogue merge ưu tiên dòng OSM trùng tên, id curated bị khử — ví dụ `test_hanoi_evening_intent_*` so casing `Chợ Đêm` vs `Chợ đêm`, `test_planner_uses_ai_to_select_*` mong id `curated-lang-bac`).
4. **`frontend/app/globals.css`** — một block `:root` duy nhất; token hóa các literal xanh đậm ở các class nêu trên; override dark để `.itinerary-regenerate` ≥ 4.5:1.
5. **`frontend/tests/contrast.test.mjs`** — đọc `globals.css`, phân giải chuỗi `var()`, assert tỷ lệ WCAG cả 2 palette; chạy `node --test tests` (gồm suite cũ, cập nhật `i18n.test.mjs` nếu nó pin literal đã đổi).
6. **Bằng chứng** — ghi ra scratch:
   - `{SCRATCH}/pytest.log` — `python -m pytest -q` exit 0 kèm test mới;
   - `{SCRATCH}/seed-check.log` — đọc tĩnh `seed_postgres.py` (INSERT/upsert ghi hinh_anh + credit; cột idempotent); nếu có Postgres (`URL_CSDL_POSTGRES`) chạy thật + `SELECT count(*) ... hinh_anh IS NOT NULL`;
   - `{SCRATCH}/launch.log` — khởi server thật (uvicorn `app.main:app` port 8432, APP_ENV=local) hoặc `TestClient`, POST 2 lần `/api/plan/generate` context đêm → slot sau bữa tối thuộc nhóm curated + `"anh"`/`"anh_nguon"` không rỗng ở cả 2 lần;
   - `{SCRATCH}/frontend-tests.log` — `node --test tests` xanh + grep cấu trúc (1 block `:root` light, không còn `#086b27` raw thiếu override).

## Cách kiểm chứng nhanh

```bash
# Backend
cd backend && python -m pytest -q

# Frontend
cd frontend && node --test tests

# Server thật (tùy chọn)
cd backend && python -m uvicorn app.main:app --port 8432
# POST /api/plan/generate: {"context":"du lịch Hà Nội buổi tối, sau bữa tối đi chợ đêm","location":{"lat":21.0285,"lng":105.8542},"thoi_luong":"ca_ngay","so_nguoi":2,"ngan_sach":1000000,"ma_phien":"demo","nonce":"demo-1"}
```

## Ghi chú / rủi ro

- Sandbox không chạy được Postgres + `APP_ENV=production` (cần `URL_CSDL_POSTGRES`, validate_production bắt buộc). Vì vậy Verification 3 chạy local mode (entry path thật); hành vi Postgres được chứng minh bằng unit test catalogue kiểu Postgres + seed static/db-if-available.
- Curated anchors không có dòng OSRM matrix trong non-local mode → `routing.travel_minutes` tự fallback haversine (đã được thiết kế sẵn, không đổi).
