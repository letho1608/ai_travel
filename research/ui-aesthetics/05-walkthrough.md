# Walkthrough thẩm mỹ toàn trang — "Mình Đi Đâu Thế"

> Đánh giá THUẦN (chỉ đọc, không sửa code). Phạm vi: ấn tượng thị giác tổng thể qua từng trang và sự nhất quán giữa các trang. Các chi tiết bản sắc / layout / component / UX được các agent khác đảm nhận.

---

## Tóm tắt điều hành

Sản phẩm có một **nền tảng thiết kế rất chắc chắn** — một hệ token màu tím (lavender/ink/accent) xuyên suốt `globals.css`, bộ radius nhất quán (8–32px, pill tràn đầy), chữ đậm 800/900, bóng mềm cùng tông, và dark mode được viết lại toàn diện (gần như mọi component đều có override ở `globals.css:43`). Khi lướt nhanh, ấn tượng đầu tiên là một sản phẩm *được chăm chút cẩn thận*, không phải một template AI cào ra.

Nhưng chất lượng thị giác **không đều giữa các trang**. Cực sáng là **Landing** và **Plan workspace** (đầy đủ chi tiết, nhịp điệu tốt, có "personality"). Cực tối là **Admin** — vừa mắc lỗi bố cục thực sự (hàng strip 5 thẻ trên lưới 4 cột), vừa có nút hủy không có style, vừa dùng chữ Việt không dấu hard-code. **Explore** và **Roadtrip** ở mức trung bình: form dày đặc, một vài điểm vỡ cột khi bật tính năng phụ.

Ba sự không nhất quán xương sống:

1. **Thang chữ heading nội trang không đồng bộ** — h1 nội trang dao động từ 52px (login) đến 72px (explore/roadtrip) dù cùng "tầng" trang: `globals.css:34` (login 52px, settings 54px) vs `globals.css:28` (explore 72px), `globals.css:31` (roadtrip 72px), `globals.css:40` (admin 66px), còn history dùng generic 62px từ `globals.css:10`.
2. **Chiều rộng trang không đồng bộ** — workspace plan được định nghĩa `max-width:1500px` (`globals.css:25`) nhưng layout bọc tất cả trong `<main className="shell">` `max-width:1200px` (`layout.tsx:9`) nên ý định "trang rộng cho workspace" bị triệt tiêu, 3 panel bị bó trong ~1150px.
3. **Màu bản đồ lạc palette** — marker/polyline trên cả hai map dùng teal `#0f766e` và cam `#e4572e` (`MapView.tsx:37,49`, `RoadTripMap.tsx:15-16`), trong khi toàn bộ sản phẩm là tím. Đây là "đốm màu ngoài hệ" dễ thấy nhất.

Điểm thẩm mỹ tổng thể: **7.5/10**.

---

## Bảng chấm điểm từng trang

| Trang | Điểm | Lý do ngắn |
|---|---|---|
| Landing `/` | **9** | Hero 88px + planner + social-proof ăn khớp, nhịp section đều, CTA banner đẹp; trừ điểm nhỏ vì emoji thumb thiếu "chất" |
| Plan workspace `/plan/[token]` | **8** | Giàu chi tiết và xử lý trạng thái tốt, slot + photo + map đẹp; header 9 nút nhồi, màu map lạc, bị bó chiều rộng |
| Explore `/explore` | **6** | Form 6 cột chặt, fieldset star/amenities bị bóp vào cột hẹp, kết quả offer-card đều đặn nhưng khô |
| Roadtrip `/roadtrip` | **6** | Stop-editor sạch khi cơ bản nhưng **vỡ cột khi bật "bao gồm chỗ ở"**; summary 380px + map kết quả tốt |
| History `/history` | **7** | Timeline card sạch, nhất quán; nhưng là trang "giản lược" nhất trong nhóm nội dung — h1 generic 62px |
| Settings `/settings` | **8** | Card 620px gọn, form 3 select thoáng, danger-zone tách bạch; hơi trống ở vùng giữa |
| Login `/login` | **8** | Card trung tâm 600px thoáng, consent rõ ràng; phụ thuộc nút Google render bên ngoài (khó kiểm soát thẩm mỹ) |
| Admin `/admin` | **5** | Lỗi strip 5→4 cột, nút "Huy" không style, chữ Việt không dấu hard-code; còn lại đã theo ngôn ngữ card chung |

---

## Hành trình người dùng

### Bước 1 — Landing: ấn tượng đầu tiên

Màn hình đầu tiên là một hero 2 cột: bên trái chữ khổng lồ **88px** hai dòng (`globals.css:13`, `page.tsx:31-35`) với `letter-spacing:-.035em`, eyebrow pill tím (`page.tsx:30`), lead 20px và social-proof chấm xanh + "100%" (`page.tsx:37-42`). Bên phải là planner card với vạch gradient 6px trên cùng và bong bóng chào (`globals.css:19`, `Planner.tsx:159-163`).

**Đánh giá:** tỷ lệ rất tốt. H1 lên tới 88px nhưng `line-height:.98` đặt đúng tone "to-tiếng" của landing, không hề choáng. Chữ tím đen `--ink` trên nền `--paper` kem tạo cảm giác ấm và thủ công — hợp sản phẩm du lịch. Planner có trọng lượng thị giác đủ để cân bằng khối chữ trái. Chấm xanh "100%" với halo `--green-soft` (`globals.css:13`) đọc như trạng thái "live" — một dụng cụ tạo niềm tin hợp lý, dù con số 100% chưa có căn cứ hiển thị (chỉ là nhận định).

Điểm trừ thẩm mỹ duy nhất ở đây là **emoji ☕🍜🏛️** trong featured-card thumb (`page.tsx:6-9`, `globals.css:16`): 3 emoji ở cỡ 44px trên gradient lavender phẳng 150px. Emoji render **khác nhau theo hệ điều hành** (Windows 10/11, macOS, mobile) — trên Windows nó có màu chói, trên macOS nhạt hơn; nên mức độ "đẹp" không ổn định. Thêm nữa, gradient một chiều `lavender-soft → lavender` hơi bằng phẳng, không có texture/hình. Kết luận: **không phải lỗi, nhưng là chi tiết kém "pro" nhất của landing** — chấp nhận được ở MVP, không hợp nếu muốn cạnh tranh về thẩm mỹ.

### Bước 2 — CTA banner (cuối landing)

`.cta-banner` là một gradient `ink-3 → accent → accent-2` (tím đậm → tím → tím nhạt), bo `--radius-xl`, bóng `--shadow-xl`, chữ trắng, nút primary nền trắng (`globals.css:16`, `page.tsx:100-106`). Nhìn chung **rất đẹp và đúng chuẩn** — đây là một trong những khối thị giác tốt nhất site. Không có lỗi. Điểm trừ nhỏ: nội dung lặp lại `heroLead` (cùng câu chữ với hero, `page.tsx:102`) nên cảm giác "trang giảm giá trị cuối" hơi đuối, nhưng đây là vấn đề copy, không phải thẩm mỹ.

### Bước 3 — Tạo plan (Planner)

Planner gồm: chat-welcome (dot + bubble), 3 chip idea, input tròn + nút ↑ tròn, label + input số người, status/error, disclaimer kép (`Planner.tsx:164-233`). Thẩm mỹ nhất quán với phần còn lại (chip pill, focus-ring tím). Một chi tiết thú vị: nút gửi dùng ký tự mũi tên "↑" cỡ 18px trong nút tròn đen (`Planner.tsx:199`) — đơn giản nhưng hợp nhịp, không lòe loẹt. Hai disclaimer xếp chồng (`Planner.tsx:232-233`) tạo khối chữ nhỏ khá nặng cuối card nhưng chấp nhận được.

### Bước 4 — Plan workspace (trang kết quả chính)

Sau khi generate, người dùng được chuyển tới `/plan/[token]`. Đây là **trang đồ sộ nhất**:

- **Trip-header** (`globals.css:25`, `PlanView.tsx:120`): eyebrow + h1 tới 52px + summary. Bên phải **7–9 nút** `.secondary` (share, PDF, calendar, JSON, comments, feedback [có điều kiện], versions, undo [khi ver>1], regenerate). Đây là điểm nghẽn thị giác rõ nhất của trang: ở ~1150px nội dung, hàng nút này **nhồi thành 2 dòng dày đặc**, cạnh tranh luôn cả chữ tiêu đề. Người dùng phải "đọc menu" trước khi đọc tiêu đề. Nút **"undo"** mới (`PlanView.tsx:120`, cuối dãy) là một `.secondary` thường — không phá vỡ, nhưng quá dễ lẫn vào 8 nút kia; không có biểu tượng hay sự phân cấp để đáng chú ý dù đây là hành động "cứu mạng" phổ biến.
- **Trip-facts** (`PlanView.tsx:121`): 4–5 chip tím nhạt bo pill + 1 chip dashed "last-updated". Rất dễ nhìn, nhịp tốt — đây là điểm sáng thẩm mỹ của trang. Lưu ý nhỏ: chip "places" chỉ đếm slot của ngày đang xem (`t("places",{count:slots.length})`, với `slots = plan.ngay[activeDay]`), nên số thay đổi khi chuyển tab ngày — hơi bất ngờ về thông tin nhưng không phải lỗi nhìn.
- **3 panel** (`globals.css:25`): chat (min-height 620px) | itinerary (max-height 720px, scroll) | map (min-height 520px + legend). Khi bị bó trong 1152px, mỗi cột ~360–430px. Không vỡ nhưng **không đạt được độ "phóng khoáng"** mà `max-width:1500px` định ý — bằng chứng một ý định thiết kế bị layout cha nuốt mất (`layout.tsx:9`).
- **Slot itinerary** (`globals.css:25`): mỗi slot là grid `28px 56px 1fr auto`, có `.slot-photo` 150px phủ ngang, stop-index tròn đen, thời gian, mô tả + chi phí + source, nút swap ↻. Khi có ảnh, slot cao đáng kể nhưng có `shimmer` loading và `onError` ẩn ảnh hỏng (`PlanView.tsx:117`) — xử lý rất cẩn thận. Panel này nhìn "cao cấp" hơn cả explore.

Ấn tượng chung: trang rất "đầy" và hơi **dày hơn so với mật độ của landing**, nhưng mọi trạng thái (busy, message, drawer version/comment, feedback) đều được định dạng đúng hệ. Đây là trang thứ hai đẹp nhất.

### Bước 5 — Explore (khám phá chuyến bay/khách sạn/hoạt động)

H1 72px hai dòng (`explore/page.tsx:59`), 4 tab pill, form `inventory-search` **6 cột** (`globals.css:28`, `explore/page.tsx:61-64`).

- Form flight (4 field + adults + nút) đúng 6 cột — gọn.
- Form hotel 12 phần tử (8 field + 2 fieldset + adults + nút) → 2 hàng. **Vấn đề thị giác**: fieldset "starRating" và "amenities" là các *grid item* chỉ chiếm 1 cột (~170px), trong khi bên trong có 3–5 checkbox `.inline-check` → bị bóp, nhãn xếp dồn, đọc rối. Đây là chỗ thô nhất của trang.
- Form transfer 10 field → 2 hàng, chấp nhận được.

Kết quả `offer-card` 3 cột (`globals.css:28`, `explore/page.tsx:66`) nhìn đều và sạch: eyebrow nhỏ, giá h2 26px đậm, nút `.secondary` full width. Nhưng thiếu hình ảnh/điểm nhấn màu — card trắng + chữ xám trên nền kem tạo cảm giác "bảng giá", không phải "khám phá". Khối `price-analysis` dùng pill tím lavender (`globals.css:25` trong `.price-analysis span`) nhất quán.

**Đánh giá:** đây là trang **kém duyên nhất** trong nhóm trang chức năng — đúng chức năng, sai "không khí".

### Bước 6 — Roadtrip

H1 72px, form builder card với `stop-editor` lưới `34px repeat(4,minmax(100px,1fr))` (`globals.css:31`, `roadtrip/page.tsx:56`): số tròn đen + name + lat + lng. Khi **không** bật "bao gồm chỗ ở", hàng 4 cột rất gọn và dễ nhìn. Khi **bật** vớiInventory, mỗi hàng thêm 4 input (IATA + arrival + departure + nút ×) → 8 phần tử trên lưới chỉ có 5 cột được định nghĩa; 3 phần tử còn lại rơi vào **cột implicit auto-width** → hàng input bị lệch cột so với các hàng khác, nguy cơ tràn ngang card. Đây là vỡ bố cục có thật, không chỉ lý thuyết.

Kết quả: `roadtrip-result` grid `380px 1fr` (`globals.css:31`) — summary 380px + map 580px. Nhìn tốt, minh bạch. Điểm trừ: đường/marker map lại teal/cam (`RoadTripMap.tsx:15-16`).

### Bước 7 — History

Trang giản lược nhất: h1 + danh sách thông báo (`.card.notification`) + timeline `a.card` (`history/page.tsx:55`, `globals.css:34`). Nhất quán về ngôn ngữ card, nhưng không có `.page` class riêng nên h1 rơi vào generic 62px (`globals.css:10`) — khác scale với settings (54px) dù cùng "tầng". Không xấu, chỉ là trang "khiêm tốn" hơn hẳn anh em.

### Bước 8 — Settings

Card 620px giữa trang, h1 54px, 3 select (ngôn ngữ 19 tùy chọn / tiền tệ / đơn vị), nút save, danger-zone tách bằng border-top (`settings/page.tsx:37`, `globals.css:34`). Thoáng, sạch, đúng vai. Không quá trống: mật độ vừa phải cho một trang cài đặt; danger-zone màu danger tạo điểm nhấn đỏ duy nhất cần thiết. **Không đáng trừ điểm.**

### Bước 9 — Login

Card 600px giữa trang (`globals.css:34`, `login/page.tsx:64-75`), h1 52px, lead, consent với link terms/privacy, nút Google width 360 do Google render. Thẩm mỹ phụ thuộc phần lớn vào nút Google (ngoài tầm kiểm soát) nhưng khung trang đủ trang nhã. Không trống nhờ có lead + consent. Ổn.

### Bước 10 — Admin

Trang này **lạc giọng** theo hai cách:

1. **Lỗi bố cục thật**: `admin-strip` có **5 thẻ** (Environment, Plans, AI cost, AI deterministic, Open support — `admin/page.tsx:368-372`) trên grid `repeat(4,1fr)` (`globals.css:40`) → thẻ thứ 5 rớt xuống hàng 2, chiếm 1/4 chiều rộng, trông như lỗi.
2. **Nút không style**: nút "Huy" trong queue (`admin/page.tsx:580`) là `<button>` trần không có class → render theo button mặc định trình duyệt, **xung khắc hoàn toàn** với `.secondary`/`.danger` xung quanh.
3. **Chữ hard-code không dấu, không i18n**: "Quan ly he thong", "Nhan su phu trach", "Ghi chu noi bo", "Dang tai...", "Bam Load AI usage..." (`admin/page.tsx:357,358,565,573,454,531,...`) — lệch hoàn toàn với phần còn lại (mọi trang khác dùng `t()` có dấu tiếng Việt). Nhìn tổng thể như "trang tool nội bộ chắp vá" cạnh một sản phẩm chỉn chu.

Về câu hỏi *màu sắc pills*: **không thực sự lạc palette** — `--green-soft`, `--sun-soft`, `--danger-soft` đều là token trong `:root` (`globals.css:1`) và có dark-mode override (`globals.css:43`). Việc dùng pills ngữ nghĩa xanh/vàng/đỏ trong một dashboard admin là chuẩn ngành. Cái làm admin lạc giọng không phải màu pills mà là 3 lỗi trên.

---

## Vấn đề theo mức

### Blocker
Không có lỗi thị giác "vỡ toàn bộ" nào ở chế độ desktop/mobile thông thường.

### High
1. **Admin strip 5 thẻ trong lưới 4 cột** — thẻ thứ 5 rớt hàng, chiếm 1/4 width.
   `app/admin/page.tsx:368-372` · `frontend/app/globals.css:40` (`.admin-strip{grid-template-columns:repeat(4,1fr)}`)
2. **Roadtrip stop-editor vỡ cột khi bật vớiInventory** — lưới định nghĩa 5 cột (`34px repeat(4,1fr)`) nhưng hàng có tới 8 phần tử (thêm IATA + 2 date + nút ×), phần dư rơi vào cột implicit auto → lệch cột, nguy cơ tràn ngang.
   `app/roadtrip/page.tsx:56` · `frontend/app/globals.css:31` (`.stop-input{grid-template-columns:34px repeat(4,minmax(100px,1fr))}`)
3. **Nút "Huy" booking không có class** — hiển thị như button mặc định trình duyệt, xung khắc hệ nút.
   `app/admin/page.tsx:580`

### Medium
4. **Màu map lạc brand** — marker/polyline teal `#0f766e` và cam `#e4572e` trong khi sản phẩm dùng palette tím; hai map đều mắc.
   `components/MapView.tsx:37,49` · `components/RoadTripMap.tsx:15-16`
5. **Chiều rộng workspace bị layout cha nuốt** — `.workspace-page{max-width:1500px}` không bao giờ phát huy vì bọc trong `.shell{max-width:1200px}`.
   `frontend/app/globals.css:25` · `app/layout.tsx:9`
6. **Thang h1 nội trang không đồng bộ**: explore/roadtrip 72px, admin 66px, history 62px (generic), settings 54px, login 52px.
   `globals.css:28` (72px) · `globals.css:31` (72px) · `globals.css:40` (66px) · `globals.css:10` (62px generic) · `globals.css:34` (54px / 52px)
7. **Trip-header 7–9 nút nhồi chung hàng** — nút cạnh tranh với tiêu đề 52px; nút undo mới dễ bị lẫn.
   `components/PlanView.tsx:120` · `globals.css:25`
8. **Fieldset star/amenities bị bóp vào cột 1/6 của lưới 6 cột** trên form hotel.
   `app/explore/page.tsx:62` · `globals.css:28`
9. **Admin chữ Việt không dấu hard-code, không i18n** — lệch chất lượng với toàn bộ phần còn lại.
   `app/admin/page.tsx:357,358,565,573,454,531,584,...`

### Low
10. **Hero h1 `line-height:.98` ở 88px** có thể cắt đỉnh dấu tiếng Việt (ă, ộ, ơ, thanh) ở một số font/webkit.
    `globals.css:13`
11. **Emoji thumb 44px** render không nhất quán theo OS; gradient thumb bằng phẳng, thiếu "chất" so với phần còn lại.
    `app/page.tsx:6-9` · `globals.css:16`
12. **Chip "places" trong trip-facts chỉ đếm slot của ngày đang xem** — số nhảy khi chuyển tab ngày.
    `components/PlanView.tsx:121` (dùng `slots` của `activeDay`)
13. **Offer-card thiếu điểm nhấn thị giác** — card trắng chữ xám đều đặn, không khí "bảng giá" thay vì "khám phá".
    `app/explore/page.tsx:66` · `globals.css:28`

### Note
14. CSS chết: `.trip-actions .icon-action` (`globals.css:25`) không bao giờ áp dụng vì các nút là `.secondary`; `.planner textarea` (`globals.css:19`) không dùng vì Planner dùng `input`; `.nav{border-radius:0 0 0 0}` (`globals.css:4`).
15. Featured-card là `a href="/"` — click chuột giữa/tab mới sẽ về trang chủ thay vì focus planner (`app/page.tsx:54`). Vấn đề hành vi nhẹ, không phải thẩm mỹ.
16. "100%" social-proof là khẳng định chưa có nguồn hiển thị — dụng cụ tạo niềm tin hơn là bằng chứng (`app/page.tsx:40`).
17. CTA banner lặp lại `heroLead` ở cuối trang (`app/page.tsx:102`) — copy yếu hơn, không phải thẩm mỹ.

---

## Kết luận

**Điểm thẩm mỹ tổng thể: 7.5/10** — hệ thiết kế token tím nhất quán + dark mode hoàn chỉnh đã tạo nền rất tốt, nhưng chất lượng trang không đều (landing/workspace rất đẹp, admin/explore kém duyên) và vài lỗi bố cục thực tế (strip 5→4 cột, stop-editor vỡ cột, nút trần) kéo điểm xuống.

**Confidence: 8/10**

**Ground-truth tally: 17/19 kết luận dựa trực tiếp trên code** — các file:line cụ thể nêu ở bảng (CSS `globals.css:13,16,19,25,28,31,34,37,40,43`; TSX `page.tsx:30-42,54,100-106`; `PlanView.tsx:120-121,126-128`; `explore/page.tsx:59-66`; `roadtrip/page.tsx:56`; `history/page.tsx:55`; `settings/page.tsx:37`; `login/page.tsx:64-75`; `admin/page.tsx:367-373,580`; `MapView.tsx:37,49`; `RoadTripMap.tsx:15-16`; `layout.tsx:9`). 2 kết luận còn lại (cắt dấu tiếng Việt ở hero, emoji render theo OS) là phán đoán từ kinh nghiệm render thực tế, không xác minh được bằng code.
