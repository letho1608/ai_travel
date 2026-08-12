# Work item 06 — Thời gian đi chơi dự kiến tại mỗi địa điểm: nó từ đâu ra, có căn cứ không, và làm sao để minh bạch

Workstream: **visit-duration display and basis** (lane duy nhất của tài liệu này).
Phạm vi nghiên cứu, KHÔNG sửa code. Toàn bộ trích dẫn theo `file:line` của monorepo
`ai_travel`. Ngày phân tích: 2026-08-11.

---

## 1. Câu trả lời ngắn

Số phút "thời gian đi chơi dự kiến" mà người dùng nhìn thấy trên thẻ slot — thực ra là
**phép trừ giữa `ket_thuc` và `bat_dau`** (frontend không hiển thị một trường `thoi_luong` nào
cả) — đến từ đúng **một nguồn duy nhất trong 95% trường hợp**: hằng số `60` phút được
hard-code vào toàn bộ 3.508 địa điểm trong catalog nhập từ OpenStreetMap
(`import_osm_places.py:105`), không phân theo loại điểm. Với 13 địa điểm curated, nó được ghi
đè bởi `VisitGuidance.duration_min` trong `visit_guidance.py` (các số 60/75/90/50/45) — những
con số thủ công, gắn nhãn "research-backed" nhưng không có citation kiểm chứng được. Sau đó
bộ xếp lịch **có thể kéo dài** thời gian hiển thị thêm tối đa 90 phút để "hút khoảng trống"
(`planner.py:1130-1156`), và **AI không bao giờ viết** các giá trị này.

Kết luận trung thực cho câu hỏi cốt lõi của người dùng:

- **Vị trí/căn chỉnh của slot thì có căn cứ** (rất tốt): giờ mở/đóng cửa, window ưa thích,
  bay 18:00 cho chợ đêm, travel time, floor 25 phút đều là ràng buộc cứng, được `validate_plan`
  kiểm lại.
- **Con số thời lượng bản thân nó thì phần lớn là tùy tiện**: một hằng số 60 phút áp dụng
  đồng loạt cho cafe, bảo tàng, công viên, chợ, nhà hàng, danh lam — trái với cả nghiên cứu lẫn
  thực tiễn ngành (xem mục 5). Với 13 địa điểm curated, các con số là heuristic tay, không đo
  đạc, không citation.
- **Không có provenance đến UI**: slot không hề mang một trường `thoi_luong` hay nguồn gốc nào;
  frontend chỉ vẽ `bat_dau`/`ket_thuc` (`PlanView.tsx:235`) và không có caption giải thích.

---

## 2. Chuỗi đầy đủ: con số hiển thị đến từ đâu

### 2.0 Trước tiên — UI hiển thị GÌ

- `Slot` type ở frontend chỉ có `bat_dau`, `ket_thuc` (string `"HH:MM"`) —
  `frontend/lib/types.ts:1`. **Không có trường `thoi_luong`, không có trường provenance.**
- `PlanView.tsx:235` render thẻ slot: `<strong>{slot.bat_dau}<br/><span>{slot.ket_thuc}</span></strong>`.
  Người dùng tự suy thời lượng = `ket_thuc − bat_dau`. Không có dòng chữ dạng
  "ước tính theo loại địa điểm · thường 1–2h".
- PDF export cũng chỉ in `bat_dau`/`ket_thuc` (`services/pdf_export.py:142`).
- Toàn bộ i18n không có key nào về time lượng điểm; caption "estimate" duy nhất
  (`estimateDisclaimer` trong `workspace-translations.ts`) là về **chi phí**, không phải giờ.
- Các tip pro — ví dụ "dành 60–90 phút" (`visit_guidance.py:43`) — chỉ là văn xuôi trong
  `ghi_chu`, đôi khi **mâu thuẫn** với con số thời lượng thực đã xếp (không được kiểm tra).

⇒ Kết luận A: "Thời gian đi chơi dự kiến" mà người dùng hỏi thực chất là **một phép trừ hai
mốc giờ**; sản phẩm chưa hề hiển thị một con số thời lượng mang tính giải trình.

### 2.1 Lớp catalog: `Place.duration_min`

`Place` có trường `duration_min: int` (`data.py:19`). Trường này được fill từ ba nơi:

1. **OSM import (nguồn thật của catalog vận hành)**: `import_osm_places.py:105` ghi cứng
   `"duration_min": 60` cho MỌI dòng, bất kể `kind` (cafe/nhà hàng/bảo tàng…). Đã xác minh trực
   tiếp trên `data/places.json`: **3.508/3.508 địa điểm có `duration_min = 60`**, phân bố kind
   là `nha_hang 1489, cafe 1191, quan_an 288, cong_vien 250, cho 155, dia_danh 96, bao_tang 39`.
2. **Postgres**: `_load_postgres_places()` đọc cột `thoi_luong_phut` (`data.py:317,327`); cột này
   được seed từ chính `places.json` (`seed_postgres.py:59`, mặc định `60`) và DB default là
   `thoi_luong_phut integer NOT NULL DEFAULT 60` (`alembic/versions/0001_initial.sql:8,133`).
3. **Nominatim (địa điểm LLM đề xuất)**: `osm_verify.py:193` cũng hard-code `duration_min=60`.

Một danh sách demo curated trong `data.py:80-92` và `data.py:121-222` có duration phân loại
bằng tay (Hồ Gươm 60, Văn Miếu 75, Long Biên 45, Kem Tràng Tiền 35…), **nhưng bị shadow ngay**
bởi `if IMPORTED_PLACES: PLACES = IMPORTED_PLACES` (`data.py:117-118`) — `places.json` tồn tại
trong repo nên nhánh curated đó hầu như không bao giờ chạy trong môi trường thật.

⇒ Kết luận B: **duration_min của toàn bộ kho dữ liệu = hằng số 60 phút cho 100% địa điểm
thuộc mọi loại.** Không có bất kỳ khác biệt kind→duration nào ở lớp catalog.

### 2.2 Lớp override curated: `visit_guidance.py`

`VisitGuidance` (dataclass) mang `duration_min: int | None` (`visit_guidance.py:22`). Bảng
`VISIT_GUIDANCE_BY_NAME` (dòng 28–133) gán duration cho 13 địa điểm:

| Địa điểm | duration_min | source ghi trên entry |
|---|---|---|
| Lăng Chủ tịch HCM (`:33`) | 60 | "VnExpress / Vietnam Wayfarer" |
| Văn Miếu (`:42`) | 75 | "YourVietnamTravel" |
| Hồ Gươm / Ho Guom (`:51,:60`) | 60 | "Nomado / C-Vietnam Tours" |
| Đường ven Hồ Tây / Hồ Tây (`:69,:78`) | 75 | "Nomado West Lake guide" |
| Chùa Trấn Quốc (`:87`) | 50 | "Nomado West Lake guide" |
| Phố cổ Hà Nội (`:96`) | 90 | "Hanoi Old Quarter visitor guides" |
| Cầu Long Biên (`:105`) | 45 | "local traveler guides" |
| Bảo tàng Phụ nữ (`:113`) | 75 | "museum listings" |
| Chợ đêm Đồng Xuân (`:121`) | 75 | "Hanoi walking street guides" |
| Phố Tạ Hiện (`:129`) | 60 | "Old Quarter nightlife guides" |

Các chuỗi `source` này là **diễn đạt chung, không có URL, không có ngày truy cập, không thể
verify**. `guidance_for()` (`visit_guidance.py:152-153`) match theo id/name-key.

⇒ Kết luận C: 13 con số curated là **heuristic tay** (60/75/90/50/45 — toàn bội số của 15),
đóng khung bằng ngôn từ "research-backed" trong docstring (`visit_guidance.py:1-6`) mà không có
căn cứ đo đạc nào ngoài các trang travel-blog thương mại. Không phải dữ liệu đo được.

### 2.3 Bộ xếp lịch: `_visit_minutes_for` (trái tim của thời lượng)

`planner.py:849-861` là điểm duy nhất quyết định "bao nhiêu phút cho một slot":

```python
def _visit_minutes_for(place, meal_type, request) -> int:
    if meal_type:
        minutes = min(MEAL_DURATION[meal_type], place.duration_min, 90)   # :851
        if request.thoi_luong == "vai_gio":
            minutes = min(minutes, 45)                                     # :852
        return max(MIN_VISIT_MINUTES, minutes)                             # :854
    tip = _guidance(place)
    minutes = tip.duration_min if tip and tip.duration_min else place.duration_min  # :856
    if request.thoi_luong == "vai_gio":
        minutes = min(minutes, 35)                                         # :858
        if place.kind == "cafe":
            minutes = min(minutes, 30)                                     # :860
    return max(MIN_VISIT_MINUTES, minutes)                                 # :861
```

Hệ quả quan trọng với catalog thật (duration_min=60):

- **Bữa ăn**: `MEAL_DURATION = {"sang":45,"trua":60,"nghi":50,"toi":75,"dem":75}`
  (`planner.py:42`). Với `place.duration_min=60` thì
  `toi = min(75, 60, 90) = 60` — **hằng số catalog 60 phút vô hiệu hóa con số 75 phút cho bữa
  tối** mà bộ xếp lịch "muốn". `dem = min(75,60,90)=60`. Chỉ `sang=45` và `nghi=50` là không bị
  chặn. Nói cách khác: dù code có một bảng thời lượng bữa ăn hợp lý, **giá trị hiển thị thực tế
  lại bị cắt bởi duration_min=60**.
- **Điểm tham quan (không phải bữa)**: nếu không có guidance → `minutes = 60` cho mọi kind
  (cafe 60, bảo tàng 60, công viên 60, danh lam 60). Nếu có guidance → số curated trong 2.2.
- **Chế độ "vài giờ" (`vai_gio`)**: cắt tham quan xuống ≤35 phút, cafe ≤30, bữa ≤45 — chứng
  tỏ hằng số 60/75/90 chỉ là "giá trị mặc định" chứ không phải "thời lượng thực" mà sản phẩm
  cam kết.

⇒ Kết luận D: con số thời lượng = `min(duration_min_hoặc_guidance, cửa sổ còn khả dụng)`.

### 2.4 Bộ xếp lịch: `_compute_slot_bounds` và luồng hiển thị

`_compute_slot_bounds` (`planner.py:914-991`):

- Mở đầu bằng giờ mở/đóng hiệu lực `_effective_hours` (`planner.py:755-764`) — ưu tiên guidance,
  rồi `KNOWN_HOURS_BY_NAME` (Lăng Bác 7–11, `:64-66`), rồi giờ từ catalog.
- `latest_end = min(closing, preferred_close, day_end)` (`:936-943`) — slot bị kẹp vào window
  ưa thích khi không `relax`.
- **Chợ đêm**: `earliest = max(earliest, 18:00)` (`:934-935`) — sàn cứng 18:00 như prompt nhắc.
- `available = int((latest_end-start).total_seconds()//60)`; `visit = min(visit, available)`
  (`:984-985`) — thời lượng bị bóp lại khi window/đóng cửa ngắn.
- `MIN_VISIT_MINUTES = 25` (`:51`) là sàn; nếu không đạt → slot bị loại (`:986-987`).

Thời lượng được ghi ra slot dưới dạng `bat_dau`/`ket_thuc` (string) ở `:1076-1077` (pack chính),
`:1253-1254` (backfill), `:1299-1300` (single schedule). **Không ghi `thoi_luong` dạng số.**

⇒ Kết luận E: khi `window` hàng ngày chật (ngày "vài giờ", giờ đóng sớm), thời lượng hiển thị
sẽ NGẮN hơn 60 phút — tức cùng một địa điểm hiển thị các con số khác nhau theo ngày, hoàn toàn
vì ràng buộc lịch chứ không phải vì đặc tính địa điểm.

### 2.5 Thủ phạm quan trọng: `_tighten_day_gaps` KÉO DÀI thời lượng hiển thị

`planner.py:1108-1157`. Khi khoảng hở giữa hai slot > 40 phút (và không phải bữa ăn), bộ xếp
lịch **sửa thẳng `ket_thuc`** thêm `min(gap − reserve − 8, 90)` phút (`:1130`), còn bị giới hạn
bởi giờ đóng và window ưa thích (`:1133-1153`):

```python
extend = min(gap - reserve - 8, 90)     # :1130
...
current["ket_thuc"] = f"..."            # :1156  — MUTATE trực tiếp
```

Hệ quả: **con số thời lượng người dùng thấy = thời lượng mô hình + phần hấp thụ idle lên tới
90 phút, không có dấu hiệu nào cho biết điều này.** Một điểm tham quan 60 phút có thể hiển thị
"14:30–16:15" (105 phút) chỉ vì slot kế tiếp cách xa. Không sai về ràng buộc (validate_plan
vẫn pass, `planner.py:1422-1443`), nhưng hoàn toàn sai về nghĩa "thời gian dự kiến đi chơi ở
địa điểm" — người dùng sẽ đọc đó là thời lượng khám phá.

### 2.6 AI có viết thời lượng không? — Không.

- `assemble` của AI chỉ patch `tieu_de`, `tom_tat`, `mo_ta_theo_id`, `luu_y`
  (`services/ai.py:54-71` `_apply_copy`). Không đụng `bat_dau`/`ket_thuc`.
- Prompt assemble yêu cầu rõ: *"Preserve … times … and all quantitative facts exactly"*
  (`services/ai.py:336`).
- `draft_itinerary_places` (`ai.py:226-320`) trả về `why/activity/tip/meal/transport` — chỉ
  dùng cho văn bản `mo_ta/ghi_chu` qua `_slot_copy` (`planner.py:1647-1679`), không cho thời lượng.

⇒ Kết luận F: mọi thời lượng hiển thị là **kết quả tất định của pipeline**, không có AI sinh
số ở bước nào. Điểm yếu provenance không nằm ở "AI bịa", mà nằm ở **chỗ số liệu gốc là hằng
số / heuristic vô danh và không được chuyển tới UI**.

### 2.7 Bug provenance khi đổi địa điểm (liên quan trực tiếp lane này)

`routers/plans.py:466-508` (endpoint `/swipe`): khi thay thế 1 địa điểm, slot mới `update`
các trường `dia_diem_id/ten_dia_diem/loai/...` (**`plans.py:476-488`**) nhưng **giữ nguyên
`bat_dau`/`ket_thuc` của địa điểm BỊ LOẠI**. Tức là sau khi người dùng "đổi điểm này", thời
lượng hiển thị của địa điểm mới = thời lượng của địa điểm cũ (dù `duration_min` khác). Đây là
một gap provenance cụ thể, dễ chứng minh, thuộc đúng câu hỏi "con số đó từ đâu ra".

---

## 3. Các ràng buộc thời gian hỗ trợ (đã kiểm bằng code)

Để công bằng, phần "căn chỉnh khung giờ" được xây khá cẩn thận:

- Window bữa ăn: `MEAL_WINDOWS` (`planner.py:35-41`), preferred start (`:43-49`).
- Window ưa thích theo loại: `_preferred_window` (`planner.py:791-813`) — bảo tàng 8:30–17:00,
  ngoài trời 7:00–10:00, cafe 9:00–17:00, chợ đêm ≥18h.
- Điểm chỉ buổi sáng (Lăng Bác, Văn Miếu sáng) — `_is_morning_only` (`:781-788`).
- `_pick_visit_window` chọn primary/alt window gần giờ đến nhất (`:816-842`).
- `validate_plan` kiểm: tuần tự, trong giờ mở cửa, đủ thời gian di chuyển (`planner.py:1421-1444`).

⇒ Những thứ này tạo cảm giác 'chính xác' cho slot — và việc hiển thị giờ dạng `08:30–09:30`
càng củng cố ấn tượng đó, dù con số thời lượng bên trong yếu.

---

## 4. Provenance gaps (tổng kết)

1. **Catalog khô khốc**: 100% địa điểm = 60 phút, mọi loại (`import_osm_places.py:105`).
2. **Curated bằng tay**, không citation, "source" chỉ là tên travel-blog (`visit_guidance.py`).
3. **Không lưu/trả provenance**: slot chỉ có `bat_dau/ket_thuc`; UI không có caption, không có
   trường `thoi_luong` (`types.ts:1`, `PlanView.tsx:235`).
4. **`_tighten_day_gaps` bơm thêm tới 90 phút vào `ket_thuc`** mà không đánh dấu
   (`planner.py:1130-1156`).
5. **Meal dinner 75 bị chặn thành 60** bởi hằng số catalog (`planner.py:851`).
6. **Swap giữ nguyên thời lượng địa điểm cũ** (`plans.py:476-488`).
7. **Văn xuôi tip có thể mâu thuẫn số hiển thị** ("dành 60–90 phút" vs slot 45 phút).

---

## 5. Căn cứ bên ngoài: thời lượng trung bình theo loại điểm

Yêu cầu 2+ nguồn cho mỗi nhận định. Phân biệt rõ nghiên cứu đo đạc vs heuristic.

### 5.1 Bảo tàng / di tích trong nhà

- **Serrell (1997), "Paying Attention", Curator — nghiên cứu đo đạc trên 108 exhibition**:
  người xem thường ở dưới 20 phút trong triển lãm; sweep rate 200–400 ft²/phút.
  Đây là con số rất thấp cho "triển lãm", chứ không phải cả bảo tàng.
- **"Time allocation in a museum: an empirical investigation" (Eur. J. Tourism Research,
  2014)** — khảo sát Bảo tàng Khảo cổ South Tyrol: trung bình ~2 giờ/khách.
- **Khảo sát khách bảo tàng Iceland (RMF 2026)**: phổ mode 30–60 phút (38%) và 1–2 giờ (47%).
- **National Museum of Bahrain (Buildings 2025, MDPI)**: behavior-mapping, tour cá nhân
  15–20 phút, nhóm có hướng dẫn ~30 phút; trung bình cả gallery ~45 phút.

⇒ Phạm vi thực đo: **từ ~20 phút (triển lãm nhỏ/khách lướt) đến ~120 phút (bảo tàng neo)**.
"60–75 phút" là điểm giữa hợp lý VỀ MẶT kinh nghiệm, nhưng hiển thị một con số cố định mà
không kèm khoảng bất định là không trung thực về độ biến thiên thực có. (Hai con số đầu tiên
này đã được đối chiếu chéo hai nguồn độc lập.)

### 5.2 Nhà hàng / cafe

- **Kimes et al. (2002)** — khảo sát khách Mỹ: kỳ vọng bữa restaurant thường ~60 phút;
  meal duration >20% không ảnh hưởng hài lòng.
- **RestaurantTables (2026) — 523 nhà hàng, 2,8 triệu lượt**: fast casual trung bình 28 phút;
  casual 2-top 48 phút, 4-top 64 phút; fine dining 94 phút.
- **Local Brand Hub (2026)**: quick-service/café 20–40 phút; casual lunch 45–60; full-service
  dinner 75–105 phút.
- **restaurantbookingsystem.com**: fine dining 90–120, casual 45–60, fast casual 20–30.

⇒ So với `MEAL_DURATION {sang:45, trua:60, toi:75, dem:75}` (`planner.py:42`): `trua=60` ăn
khớp tốt Kimes; `toi=75` hơi thấp so với 75–105 phút dinner; cafe ~45 phút là hợp lý nhưng
**không bao giờ được hiển thị vì catalog chặn ở 60** và lunch/dinner danh cho `nha_hang`
cũng bị cắt. Nghĩa là bảng MEAL_DURATION – vốn đỡ đúng hướng – bị vô hiệu một phần.

### 5.3 Thực tiễn "suggested duration" của ngành

- **Tourific AI / BestRoadTrip — "The 60-Minute Truth" audit (2026), 1.294 travel reels**:
  median toàn cầu của "thời lượng gợi ý trên mỗi địa điểm" là **90 phút**; bucket mode
  61–90 phút (34%); **90-phút là "convention" mặc định của tour-bus đã bị sao chép qua các app**.
  Đáng chú ý: thời lượng gợi ý **phụ thuộc hoạt động** — chụp ảnh/tín ngưỡng median 60 phút,
  văn hóa/ẩm thực/mua sắm 90 phút, thiên nhiên 120 phút. Kết luận của báo cáo: *"default 90
  phút cho mọi nơi là sai một hệ số 1.5–2x cho nhiều quốc gia; cần default có country/activity
  awareness"*. (Nguồn thương mại, dữ liệu model-estimated — chưa đạt chuẩn peer-review.)
- **TripAdvisor**: trường "suggested duration" là nội dung biên tập/crowd-sourced theo từng
  điểm (nhận định từ tra cứu; chưa verify chính thức — flagged *unverified*).
- **Google "AI trip ideas in Search" (Research Blog, Google)**: LLM đề xuất kèm "suggested
  duration" RỒI thuật toán tối ưu hóa khả thi theo giờ mở cửa + travel time. Đây là mẫu kiến
  trúc trung thực (độ dài = giả định + bước xác thực), giống hệt hướng nên làm ở sản phẩm này.

⇒ Nhận định ngành: hằng số 60 phút của repo thấp hơn median 90 phút toàn cầu và **đặc biệt
bỏ qua chiều "activity/kind"** — chính là chiều mà audit 60-Minute Truth coi là biến quan
trọng nhất ("activity is a stronger predictor than country").

### 5.4 Học thuật TTDP — thời lượng là INPUT cần đo/được cung cấp

- **Lim, Chan, Leckie, Karunasekera — "Personalized Tour Recommendation … POI Visit
  Durations" (IJCAI 2015, PERSTOUR)**: POI visit duration **được suy ra từ ảnh geotagged**
  (hiệu hai mốc thời gian ảnh đầu–cuối tại POI), sau đó personalized theo độ quan tâm người
  dùng; so sánh "average visit duration" vs "personalized" cho thấy dùng hằng số trung bình
  cho mọi người là phép ước lượng xấu (RMS error cao hơn).
- **Vu et al., Smart Loire / ROADEF 2019, TTDP rich constraints**: mọi POI mang thuộc tính
  "average duration tᵢ" như là **dữ liệu đầu vào** cho ILP — tức cộng đồng ngầm định rằng
  thời lượng phải được đo/được cấp, không tự sinh.
- **TTDP-BWB (OPSEARCH 2023, Springer)**: mô hình TTDP thêm ràng buộc weather + break —
  ủng hộ kiến trúc của repo (weather obey, midday rest 13:00, evening floor), tức phần *khung
  giờ* của repo đi đúng xu hướng literature, còn phần *thời lượng* thì không được cấp dữ liệu.

⇒ Consensus học thuật: **không có con số "đúng" duy nhất; thời lượng nên là dữ liệu theo loại/
theo điểm (từ quan sát) hoặc một heuristic được khai báo rõ, và nên hiển thị dưới dạng khoảng
chứ không phải mốc giờ chính xác.**

### 5.5 Tổng hợp khuyến nghị kind→duration mặc định (dựa trên 5.1–5.4)

| kind | default (phút) | khoảng gợi ý hiển thị | căn cứ |
|---|---|---|---|
| `bao_tang` | 75 | 45–120 | Serrell thấp 20–45; Iceland 30–120 (5.1) |
| `dia_danh` (di tích, danh lam) | 90 | 45–150 | 90-min median, culture 90 (5.3) |
| `cong_vien`/ngoài trời | 90 | 45–180 | nature 120 (5.3) |
| `cafe` | 45 | 30–60 | café dwell 20–40 (5.2) |
| `nha_hang` (toi) | 90 | 60–120 | full-service dinner 75–105 (5.2) |
| `quan_an` (trua) | 60 | 45–75 | casual lunch 45–60 (5.2) |
| `cho` / `cho_dem` | 75 | 45–120 | 90-min median, shopping 90 (5.3) |

Đây là giá trị **mặc định theo loại, có nguồn hai chiều**, tất cả phải ghi chú "ước tính".

---

## 6. Mô hình minh bạch đề xuất (design)

Mọi khuyến nghị thuộc lane "hiển thị thời lượng + căn cứ"; không thuộc các lane khác.

### 6.1 Ba nguồn, một thứ tự ưu tiên

```
duration_final = (
    per_place_override (visit_guidance.duration_min / admin duration_min)  # user/tay curated
    hoặc kind_default (bảng KIND_DURATION trong data.py, có citation)       # mặc định mới
)
capped_by = opening/window/MEAL_DURATION                                    # giữ nguyên
floored_by = MIN_VISIT_MINUTES                                              # giữ nguyên
```

- `data.py`: thêm bảng `KIND_DURATION_MINUTES: dict[kind, int]` + `KIND_DURATION_SOURCE` gắn
  citation (2 nguồn trong mục 5). Đây là nơi duy nhất giữ "bằng chứng".
- Catalog: `import_osm_places.py:105` BỎ hằng 60, thay bằng `KIND_DURATION_MINUTES[kind]`;
  `seed_postgres.py:59` và `osm_verify.py:193` theo sau. `alembic` thêm cột
  `thoi_luong_nguon text` (mặc định `'kind_default'`).
- Cơ chế per-place đã TỒN TẠI cả hai đường (catalog `duration_min` + `visit_guidance`) — chỉ
  cần khai báo rõ thứ tự ưu tiên và nguồn cuối.

### 6.2 Expose thời lượng + provenance tới UI

Mỗi slot thêm 2–3 trường (thay đổi `slots` dict ở `planner.py:1075-1093` + `types.ts`):

```jsonc
{
  "bat_dau": "10:00", "ket_thuc": "11:15",
  "thoi_luong_phut": 75,                       // con số mô hình, KHÔNG tính padding
  "thoi_luong_nguon": "kind_default",          // kind_default | curated | catalog | padding
  "thoi_luong_nguon_mo_ta": "bảo tàng · thường 45–120 phút · ước tính theo loại địa điểm"
}
```

- UI (`PlanView.tsx:235` / i18n): nếu `thoi_luong_nguon == "padding"` hiển thị thêm nút "thời
  gian linh hoạt"; luôn kèm caption nguồn ngắn. Bổ sung key mới trong
  `workspace-translations.ts` (19 ngôn ngữ, theo pattern có sẵn).
- **Tách "thời lượng mô hình" khỏi "thời lượng padding"**: `_tighten_day_gaps` không sửa
  `bat_dau/ket_thuc` ảo — hoặc giữ nguyên nhưng phải đánh dấu `thoi_luong_nguon="padding"`;
  tốt nhất: hạn chế phần kéo dài để `ket_thuc` không lệch `thoi_luong_phut` quá X phút.

### 6.3 Sửa các lỗi provenance cụ thể (không đổi thuật toán chính)

- `plans.py:swipe` (`:466-508`): sau khi thay, **recompute** `bat_dau/ket_thuc` cho slot mới
  bằng `_compute_slot_bounds(replacement, ...)` thay vì giữ nguyên của địa điểm cũ.
- `validate_plan` (`planner.py:1429-1434`): thêm check `thoi_luong_phut` ≤ window và phần
  padding được đánh dấu, để tip văn xuôi không mâu thuẫn số (grep các tip có "phút").

### 6.4 Trung thực về bất định

- Mọi cửa sổ hiển thị dạng khoảng: "thường **1–2 giờ**" chứ không "1 giờ 15 phút".
- Caption mặc định: "ước tính theo loại địa điểm" / "theo ghi chú curated: Lăng Bác 7:30–10:30".
- `estimateDisclaimer` hiện chỉ nói chi phí; mở rộng 1 câu về giờ: "giờ là ước tính, có thể
  đổi khi bạn muốn đi nhanh/chậm". (Thuộc lane UI để cùng chỉnh.)

### 6.5 Vận hành dữ liệu

- Script cập nhật catalog: gán `thoi_luong_phut` theo `KIND_DURATION_MINUTES[kind]`, sau đó
  overrides thủ công cho ~20 địa điểm curated có citation thật (Lăng Bác 60–75, Văn Miếu
  75–90…).
- Thêm `thoi_luong_nguon` vào places.json metadata và Postgres; admin (đã có `admin.py:291-297`,
  `:333` sửa `duration_min`) hiển thị nguồn.

---

## 7. Phân loại mức độ và Tier plan

Mức độ nghiêm trọng: **CAO về tính trung thực ("thời lượng hiển thị không có căn cứ"), THẤP
về an toàn/ổn định** (không crash, không vi phạm ràng buộc, validate giữ được tính khả thi).

- **Tier 0 (làm ngay, < 1 ngày, không đổi thuật toán):**
  1. Ghi provenance trên slot: `thoi_luong_phut`, `thoi_luong_nguon`, caption nguồn; UI hiển
     thị khoảng + "ước tính".
  2. Sửa `swipe` giữ thời lượng địa điểm cũ (`plans.py:476-488`).
  3. Đánh dấu padding từ `_tighten_day_gaps` để không "nói dối" giờ.
- **Tier 1 (1–2 sprint): dữ liệu đúng nguồn**
  1. Thêm `KIND_DURATION_MINUTES` + citation vào `data.py`; bỏ hằng 60 trong
     `import_osm_places.py:105`, `osm_verify.py:193`, `seed_postgres.py:59`.
  2. Thêm `thoi_luong_nguon` DB + re-seed; admin hiển thị nguồn.
  3. Bảng `MEAL_DURATION.toi=75` hoạt động trở lại (bỏ chặn của catalog hằng 60).
- **Tier 2 (khi có dữ liệu): dữ liệu theo điểm**
  1. Gắn "suggested duration" từ TripAdvisor/Google Popular times cho các điểm neo (có nguồn,
     có ngày lấy); ghi vào overrides.
  2. Tùy chọn: đo duration từ ảnh geotagged (hướng PERSTOUR, IJCAI'15) cho Hà Nội —
     tham vọng, không bắt buộc MVP.
- **Tier 3 (dài hạn): cá nhân hóa + thói quen**
  1. Động từ khóa/nội dung: slow-travel → +30%, chụp ảnh → −15% (theo 5.3).
  2. Ghi nhận feedback thực tế (đã có `phan_hoi_chuyen_di`) để hiệu chỉnh KIND_DURATION theo
     thời gian — đưa sản phẩm từ heuristic sang dữ liệu vận hành.

---

## 8. Executive summary (~250 từ)

Mỗi slot trong lịch trình hiển thị hai mốc giờ `bat_dau`/`ket_thuc` (`PlanView.tsx:235`);
"thời gian đi chơi dự kiến" mà người dùng đọc được chỉ là phép trừ của hai mốc đó — sản phẩm
không có trường `thoi_luong` và không có caption nào giải thích nguồn gốc. Truy vết đầy đủ:
99% catalog (3.508 địa điểm OSM mọi loại) đều mang hằng số `duration_min = 60` phút
(`import_osm_places.py:105`), một con số không phân biệt bảo tàng/cafe/công viên/chợ và không
được hỗ trợ bởi bất kỳ đo đạc nào; 13 địa điểm curated có override thủ công 45–90 phút gắn
nhãn travel-blog không verify (`visit_guidance.py:28-133`). Bộ xếp lịch lấy `minutes =
min(duration_min, cửa sổ còn lại)` (`planner.py:849-991`), còn `_tighten_day_gaps` có thể bơm
thêm tới 90 phút vào `ket_thuc` để hút khoảng trống (`planner.py:1130-1156`) — nên thời lượng
hiển thị thường không bằng thời lượng mô hình. AI không hề tham gia viết các con số này
(`services/ai.py:54-71`). Phần căn chỉnh khung giờ (giờ mở cửa, window ưa thích, sàn 18h chợ
đêm, floor 25 phút, travel time) được xây hợp lý và `validate_plan` kiểm chặt — nhưng giá trị
thời lượng tự thân là tùy tiện. Nghiên cứu và thực tiễn ngành cho thấy thời lượng điểm phải
phân theo loại (bảo tàng 45–120, cafe 30–60, dinner 75–105 phút — nhiều nguồn đo/chỉ số) và
nên hiển thị dạng khoảng kèm nguồn. Khuyến nghị: bảng KIND_DURATION có citation trong data.py,
per-place override, expose `thoi_luong` + `thoi_luong_nguon` kèm caption "ước tính theo loại",
sửa lỗi swipe giữ thời lượng cũ, và gắn nhãn padding.

## 9. Top 5 phát hiện đáng lo nhất

1. **Hằng số 60 phút áp cho 100% catalog, mọi loại điểm** (`import_osm_places.py:105`;
   verify `places.json`: 3.508/3.508) — không có khác biệt kind nào ở tầng dữ liệu.
2. **`_tighten_day_gaps` bơm tới +90 phút vào `ket_thuc`**, làm con số hiển thị khác hẳn thời
   lượng mô hình, không đánh dấu (`planner.py:1130-1156`).
3. **Không trường/provenance nào được expose và không caption nào trong i18n** —
   `types.ts:1` chỉ có `bat_dau/ket_thuc`; người dùng không thể biết con số dựa trên gì.
4. **Per-place override 13 điểm là heuristic tay "research-backed" không kiểm được**
   (`visit_guidance.py:1,28-133`); chỉ có tên tạp chí/travel-blog, không URL/ngày/citation.
5. **`swipe` giữ nguyên khung giờ của địa điểm bị loại cho địa điểm thay thế**
   (`plans.py:476-488`) — sau khi đổi điểm, "thời lượng" hiển thị là của nơi cũ.

## 10. Confidence & ground-truth tally

**Độ tin cậy: 8/10.**

Lý do trừ điểm: (a) các value "research-backed" của visit_guidance không verify được từ repo —
tôi chỉ chứng minh được chúng không có citation, không chứng minh được là sai; (b) bảng
KIND_DURATION đề xuất là tổng hợp kinh nghiệm từ nguồn rời rạc và biến thiên lớn, không phải
con số chuẩn; (c) hai nguồn thương mại (Tourific audit, RestaurantTables) chưa peer-review.
Phần "chúng đến từ đâu" thì tin cậy cao vì tôi đọc trực tiếp mọi code-path liên quan
(`import`, `data`, `planner._visit_minutes_for`, `_compute_slot_bounds`, `_tighten_day_gaps`,
`plans.swipe`, `ai._apply_copy`).

**Ground-truth tally** (sự kiện được đối chiếu bên ngoài vs phán đoán mô hình):

- Được kiểm chứng từ bên ngoài / đọc trực tiếp code (như tính được): 12 — (1) 3.508/3.508
  places.json `duration_min=60`; (2) `import_osm_places.py:105`; (3) `osm_verify.py:193`;
  (4) `seed_postgres.py:59`; (5) `alembic:8,133` DEFAULT 60; (6) `visit_guidance.py` đủ 13 entry
  + source strings; (7) `planner.py:849-861` công thức cắt min/floor; (8) `planner.py:914-991`
  bounds + ngưỡng 18h; (9) `planner.py:1130-1156` padding; (10) `ai.py:54-71` + `:336` AI không
  viết giờ; (11) `plans.py:476-488` swipe giữ giờ cũ; (12) `types.ts:1`/`PlanView.tsx:235` không
  có thoi_luong. — Nguồn ngoài (web, không mở lại bản gốc): 6 — Serrell 1997; Eur. J. Tourism
  Research 2014; RMF Iceland 2026; RestaurantTables 2026; Tourific/BestRoadTrip 2026;
  Google Research blog. — Phán đoán mô hình: 4 — bảng KIND_DURATION value; ranking severity;
  đánh giá "nên hiển thị khoảng"; mapping kind→caption.