# Nghiên cứu thẩm mỹ giao diện — Cấp component

**Trang web**: "Mình Đi Đâu Thế" (Next.js + TypeScript)
**Phạm vi**: Buttons, inputs/forms, chat bubbles, cards, drawers/sections, tabs/pills, chips, icon-actions
**Loại nghiên cứu**: THUẦN — đọc phân tích, không sửa code
**Nguồn**: `frontend/app/globals.css`, `components/Planner.tsx`, `components/PlanView.tsx`, `app/page.tsx`, `app/explore/page.tsx`, `app/roadtrip/page.tsx`, `app/admin/page.tsx`, `app/login/page.tsx`, `app/settings/page.tsx`, `app/history/page.tsx`

---

## Tóm tắt điều hành

Hệ thống component của "Mình Đi Đâu Thế" có một nền tảng token vững chắc: một bảng màu lavender ấm, 5 cấp bán kính và 4 cấp bóng được định nghĩa nhất quán (`globals.css:1`), và bộ 3 nút `primary/secondary/danger` chia sẻ cùng một "body" hình học (`globals.css:7`). Nhìn tổng thể, UI có một cá tính rõ ràng và hiếm khi "vô hồn" — ngược lại, gần như mọi component đều mang một micro-detail tinh tế (halo 6px của `assistant-dot`, ring 4px của slot đang chọn, dấu chấm social-proof, dash-border của `last-updated`).

Tuy nhiên, sự tinh tế này **không được quản lý tập trung**. Cùng một pattern nhưng mỗi context lại tự chọn một biến thể: input có 3 kiểu focus khác nhau (ring lavender / outline toàn cục / không có gì), card có 4 mức bán kính khác nhau, hover "nâng lên" có 3 biên độ khác nhau (-1px, -2px, -4px), tab có 2 ngôn ngữ thị giác khác nhau (fill mềm vs outline cứng). Hệ quả là sự đồng nhất chỉ đúng ở tầng token, không đúng ở tầng component.

Hai vấn đề đáng chú ý nhất:
1. **Bug thị giác thật**: card booking trong admin bỏ mất class `card` → toàn bộ khối "Booking support queue" hiển thị dưới dạng text trần không nền, không viền, không padding trên nền giấy xám (`admin/page.tsx:569` — so với `explore/page.tsx:66` và `support/page.tsx:62` đều có class này).
2. **"Drawer" không phải drawer**: version-drawer, comment-drawer, feedback-card thực chất là các section `.card` chèn thẳng vào luồng trang; khi mở chúng đẩy toàn bộ workspace xuống (layout shift) và nằm cách xa itinerary — không có overlay, animation hay affordance nào của một drawer thật.

Điểm thẩm mỹ tổng thể: **7/10** — một hệ thống token ấm áp, có cá tính và rất nhiều chi tiết tinh tế, nhưng thiếu một lớp "điều phối component" để các trạng thái (focus/hover/disabled) và hình học (radius, lift, padding) không bị phân mảnh giữa các trang.

---

## Điểm mạnh (component đẹp nhất + lý do)

**1. Chip (quick-actions) — component đẹp nhất.** `globals.css:7` + `Planner.tsx:164-183`.
- Pill bo tròn hoàn toàn, padding `9px 16px`, font 13px/600 — tỉ lệ đúng chuẩn cho một phần tử "nhẹ".
- Trạng thái active dùng `aria-pressed` + nền `brand` đặc, khác biệt rõ với trạng thái idle (nền trắng + viền `line-2`), hover có cả `border-color` lẫn nền `lavender-50`.
- Nhờ đúng chuẩn accessibility semantics, trạng thái thẩm mỹ luôn khớp với trạng thái logic — đây là cặp "đẹp + đúng" hiếm có trong codebase.

**2. Trạng thái `selected` của slot.** `globals.css:25` + `PlanView.tsx:127`.
- Viền `accent` + box-shadow `0 0 0 4px lavender-soft` tạo hiệu ứng "viền kép" mềm mại, đúng nhịp với focus ring của input planner — một ngôn ngữ "đang chọn" xuyên component. Chi tiết này không hét to mà vẫn không thể nhầm lẫn.

**3. `trip-facts` pills + `last-updated`.** `globals.css:25` + `PlanView.tsx:121`.
- Những pill thông tin nhỏ (thời tiết, chi phí, số địa điểm) dùng nền `lavender-50`; riêng `last-updated` đổi sang `border-style:dashed` + màu muted — một mẹo rất tinh: "dữ liệu tĩnh" được đánh dấu bằng nét đứt, tạo phân tầng thông tin không cần thêm 1 dòng text.

**4. Hệ thống `admin-pill` mã màu.** `globals.css:40` + `admin/page.tsx:381,394,451`.
- 3 trạng thái (ok/green, mock/sun, missing/down/danger) dùng màu soft + chữ đậm tương phản tối, tạo bảng mã thị giác "quét nhanh" rất hiệu quả cho một dashboard admin vốn dễ nhàm chán.

**5. Bubbles chat với góc "đuôi" bất đối xứng.** `globals.css:22`.
- Cả hai phía đều bo `radius-md` ở 3 góc và 6px ở góc "đuôi" (dưới-trái cho assistant, dưới-phải cho user) — đối xứng gương hoàn hảo, là chi tiết phân biệt "ai nói" mà không cần màu sắc hét to. Typing indicator (3 chấm nhảy `typingPulse` 1.2s) là micro-interaction chuẩn.

**6. Số đếm `step` (landing).** `globals.css:16` + `page.tsx:71-78`.
- Badge 40px, bo 12px, nền `brand`, dùng `counter(step, decimal-leading-zero)` để in "01, 02, 03" — không cần state, không cần icon, vẫn tạo nhịp thị giác trang nhã cho 3 bước.

**7. `.assistant-dot` halo.** `globals.css:22` + `Planner.tsx:161`.
- Chấm 12px màu accent với `box-shadow 0 0 0 6px lavender-soft` — một "quầng sáng" 6px tạo cảm giác đang online/suy nghĩ, chi tiết nhỏ nhưng góp phần đáng kể vào cá tính chat.

---

## Vấn đề theo mức

### Blocker

_Không có vấn đề nào thực sự "vỡ trang" ở mức render error. Vấn đề nặng nhất được xếp ở High._

### High

**H1. Card booking trong admin mất class `card` — khối thị giác vỡ hoàn toàn.**
`admin/page.tsx:569` sử dụng `<article className="offer-card">` trong khi `explore/page.tsx:66` và `support/page.tsx:62` dùng `<article className="offer-card card">`. CSS chỉ định nghĩa `.offer-card h2` và `.offer-card .secondary` (`globals.css:28`) — mọi thứ nền/border/padding/radius đều nằm trong `.card` (`globals.css:10`). Kết quả: các yêu cầu hỗ trợ booking hiển thị dưới dạng text trần trong lưới 3 cột trên nền giấy, không phân biệt được đâu là "card".
*Gợi ý*: thêm class `card` (hoặc cho `.offer-grid article` một kiểu card riêng trong CSS admin).

**H2. Dark mode: nút send chat và nút danger mất tương phản chữ.**
`.chat-box button{...color:#fff}` (`globals.css:22`) và `.danger{...color:#fff}` (`globals.css:7`) hard-code trắng, trong khi dark mode đổi `--brand` thành lavender nhạt `#cdb3ff` và `--danger` thành salmon nhạt `#ff9b8a` (`globals.css:43`). Chữ trắng trên nền lavender/salmon nhạt có contrast rất thấp — nút send trong workspace (chỗ người dùng dùng nhiều nhất) trở nên "mờ chữ". Các nút khác (`primary`) dùng đúng `--brand-contrast` nên không bị.
*Gợi ý*: dùng `var(--brand-contrast)` và `var(--danger)`-tương ứng thay `#fff`; thêm rule dark mode cho `.chat-box button`.

**H3. "Drawers" chỉ là section chèn thẳng — gây layout shift và mất ngữ cảnh.**
`version-drawer`, `comment-drawer` (`globals.css:25`), `feedback-card` (`globals.css:25`) đều là `.card` `max-width:760px` hiển thị *trên* workspace (`PlanView.tsx:123-125`). Hệ quả thẩm mỹ:
- Khi bật, nội dung đẩy toàn bộ workspace xuống — người dùng đang đọc itinerary bỗng bị "đá" khỏi vị trí.
- "Drawer" nằm cách xa đối tượng liên quan (version list cách xa itinerary, form bình luận cách xa khu vực itinerary) — không có liên hệ không gian.
- Không có overlay/backdrop, không animation, không affordance "có thể đóng" → trông như một card bình thường bị lạc chỗ, không phải một lớp nổi.
*Gợi ý*: ít nhất thêm animation (fade + slide nhẹ) và giữ nội dung trong luồng gần itinerary; lý tưởng là modal/drawer thật với overlay.

### Medium

**M1. Ba ngôn ngữ focus khác nhau giữa các input.**
- Input planner: `outline:none` + `border-color:accent` + ring `0 0 0 4px lavender-soft` (`globals.css:19`).
- Chat input: cùng ring nhưng `border-radius:full` (`globals.css:22`).
- inventory-search, comment-form, feedback-card, admin, stop-input, settings: **không có rule focus riêng** (`globals.css:28,25,40,31,34`) → chỉ dựa vào `:focus-visible` toàn cục (outline 3px `accent-2`) (`globals.css:1`).
Mắt người dùng sẽ thấy "ông nào có halo lavender, ông nào có outline tím nhạt, ông nào chỉ hơi sáng viền". Một form hỗn hợp (planner) đã tự chứa 2 kiểu focus (chat pill vs people input).
*Gợi ý*: đưa ring `border-color + 4px lavender-soft` thành một class `.field` dùng chung; chỉ giữ outline toàn cục cho phần tử không phải form.

**M2. Input "Số người" đặt dưới chat-box phá vỡ khối đối thoại.**
`Planner.tsx:207-218`: chat-welcome + chips + chat-box tạo thành một khối "hội thoại" tròn trịa (pill radius-full), nhưng rồi một `label` + `input[type=number]` (radius-sm, full-width block) bị thả xuống ngay dưới nút send — khác hẳn hình học xung quanh. Thêm nữa `label` của nó **không có style** (các label khác đều có `font-weight:700/800`: inventory-search `globals.css:28`, settings `globals.css:34`, feedback-card `globals.css:25`), nên dòng chữ "Số người" đứng cạnh các label to đậm khác trông "lạc giọng".
*Gợi ý*: gộp people input vào một hàng riêng có label chuẩn và padding đệm phù hợp (hoặc đưa thành chip-chọn người trong khối quick-actions), đồng thời thêm rule `.planner label`.

**M3. Hai ngôn ngữ tab khác nhau.**
- `day-tabs` (`globals.css:25`): nền `lavender-50`, **không viền**, hover đổi nền, active = `brand`.
- `inventory-tabs` (`globals.css:28`): nền `surface`, **có viền `line-2`**, hover chỉ đổi `border-color` (không đổi nền), active = `brand`.
Cùng là "tab", cùng active màu `brand`, nhưng idle/hover lại hoàn toàn khác nhau — người dùng chuyển giữa plan page và explore page sẽ thấy hai "thương hiệu tab" khác nhau.
*Gợi ý*: chọn một ngôn ngữ (khuyến nghị bản outline của inventory-tabs vì có viền rõ ranh giới, hoặc thống nhất bản fill mềm của day-tabs) và áp cho cả hai.

**M4. Hover "nâng lên" có 3 biên độ khác nhau.**
- `.featured-card:hover{transform:translateY(-4px)}` (`globals.css:16`)
- `.timeline a.card:hover{transform:translateY(-2px)}` (`globals.css:34`)
- `.primary/.secondary/.danger:hover{transform:translateY(-1px)}` (`globals.css:7`), `.slot:hover{transform:translateY(-1px)}` (`globals.css:25`)
Cả 3 đều là "card/link/button nâng lên" nhưng độ nâng khác nhau → hệ thống "độ sâu" không có logic (featured-card to nhất -4px hợp lý, nhưng timeline card -2px lại nặng hơn slot -1px dù slot dày thông tin hơn).
*Gợi ý*: định nghĩa 2 cấp: lift nhẹ `-1px` cho interactive row/slot, lift mạnh `-4px` cho card lớn; timeline card nên dùng `-1px`.

**M5. Hai ngôn ngữ chuyển động nút.**
`.icon-action` hover dùng `scale(1.06)` / active `scale(.94)` (`globals.css:7`) trong khi mọi nút khác dùng `translateY(-1px)` (và chat-box send dùng `scale(.94)` active `globals.css:22`). Cùng một hệ thống nút có hai "bộ máy" motion khác nhau (phóng to vs trượt lên) → cảm giác tay nghề không đồng nhất khi chạm vào các icon-action (swap, remove stop).
*Gợi ý*: thống nhất motion cho icon-only buttons: giữ scale nhẹ nhưng hover thêm viền/đổi nền đúng chuẩn `icon-action` hiện tại ở mọi nơi.

**M6. Ladder bán kính bị áp lộn xộn giữa các card.**
Token có thang đẹp (xs8/sm12/md16/lg24/xl32, `globals.css:1`) nhưng gán không có hệ thống: planner = xl32 (`globals.css:19`), card = lg24 (`globals.css:10`), workspace card bị ép về lg24 (`globals.css:25`), faq-item = md16 (`globals.css:16`), slot = md16 (`globals.css:25`), comment = sm12 (`globals.css:25`). Các "hộp nội dung" cùng cấp (card, faq-item, slot) có 3 mức bo khác nhau trong cùng một trang/trang kề.
*Gợi ý*: quy định rõ cấp: surface chính = lg24, surface phụ/row = md16, chip/badge = full; faq-item nên về lg24 hoặc md16 tùy quyết định nhưng phải là quy tắc, không phải tùy hứng.

**M7. Icon nút dùng ký tự Unicode (↑ ↻ ×) thay vì SVG.**
Send chat dùng `↑` (`Planner.tsx:199`, `PlanView.tsx:126`), swap dùng `↻` (`PlanView.tsx:127`), remove stop dùng `×` (`roadtrip/page.tsx:56`). Các glyph này render tùy font máy, dễ lệch baseline/bold khác nhau giữa các OS, và độ tinh của nét kém xa so với inline SVG stroke 1.5-2px. Ở kích thước 46px (nút send) một glyph `↑` nhỏ bé trông "thô".
*Gợi ý*: thay bằng SVG (hoặc thư viện icon) 18-20px stroke đồng nhất; giữ `aria-label` hiện có.

**M8. Disabled opacity không thống nhất cho cùng một loại nút.**
`.chat-box button:disabled{opacity:.5}` (`globals.css:22`) nhưng `.planner .chat-box button:disabled{opacity:.55}` (`globals.css:19`) — cùng nút send, hai độ mờ khác nhau giữa landing và workspace. Các nút khác đều `.5`.
*Gợi ý*: bỏ override `.55`, dùng `.5` toàn cục.

**M9. Kích thước badge số không đồng nhất.**
`step::before` 40px/radius 12 (`globals.css:16`), `stop-index` 28px/radius 50% (`globals.css:25`), `stop-input>span` 30px/radius 50% (`globals.css:31`). Ba "con số thứ tự" trên 3 màn hình khác nhau về kích thước, bo góc, kiểu (chữ nhật bo 12 vs tròn) — không có lý do rõ ràng.
*Gợi ý*: thống nhất một badge tròn (28px) cho thứ tự trong itinerary/roadtrip, giữ badge 40px chỉ cho bước landing.

**M10. Giờ kết thúc trong slot không có phân tầng thị giác.**
`<strong>{slot.bat_dau}<br/><span>{slot.ket_thuc}</span></strong>` (`PlanView.tsx:127`) — cả giờ bắt đầu lẫn kết thúc đều nằm trong `<strong>` nên cùng độ đậm 14px; không có style cho `<span>` con (`globals.css:25`). Người đọc khó phân biệt "khi nào bắt đầu / khi nào kết thúc" bằng mắt.
*Gợi ý*: style `span` kết thúc thành màu muted + font-weight 500, giảm kích thước nhẹ.

### Low

**L1. `.primary{width:100%}` làm mặc định toàn cục.** `globals.css:7`. Mọi nút primary mặc định dãn full-width, buộc từng context phải override (`roadtrip-actions .primary{width:auto}`, `cta-banner .primary{width:auto}`, `inventory-search .primary{height:46px}` — `globals.css:31,16,28`). Điều này tạo rủi ro: bất kỳ context mới nào quên override đều có nút dãn bất ngờ (đúng kiểu bug đã xảy ra ở admin).
*Gợi ý*: bỏ `width:100%` khỏi lớp nền, chỉ áp tại nơi cần full-width (form submit, banner).

**L2. `.retry-action` thu nhỏ pill secondary.** `globals.css:10` + `Planner.tsx:227`. Padding `8px 16px` biến secondary (13px 24px) thành một mini-pill — hợp lý cho nội tuyến, nhưng là biến thể "chui" không có tên riêng.
*Gợi ý*: thêm class `btn-sm` riêng thay vì override padding.

**L3. Hover của `faq-item` không tồn tại.** `globals.css:16` + `page.tsx:89`. Các item khác đều có hover nâng/bóng; FAQ là vùng tương tác (summary clickable) nhưng không có bất kỳ phản hồi hover nào ngoài con trỏ — thiếu một trong những affordance dễ thấy nhất.
*Gợi ý*: thêm `summary:hover{background:lavender-50}` hoặc một chút `box-shadow`.

**L4. Nút `.secondary` (13px 24px) quá lớn trong drawer rows.** `version-row` có padding `11px 0` (`globals.css:25`) nhưng nút Restore vẫn là pill đầy đủ (`PlanView.tsx:123`); comment-resolve cũng vậy (`PlanView.tsx:124`). Pill to chen vào row mỏng tạo tỉ lệ lệch.
*Gợi ý*: dùng mini-pill hoặc `.button-link` cho hành động cấp row.

**L5. `offer-card` trong explore phụ thuộc hoàn toàn `.card`.** Mặc dù đúng class, mức độ phụ thuộc này nghĩa là không thể điều chỉnh riêng offer-card mà không ảnh hưởng các card khác — và chính là nguyên nhân gốc của H1 (thiếu class → mất toàn bộ style).
*Gợi ý*: cho `.offer-card` một bộ style độc lập (kế thừa tokens) để không phụ thuộc class cha.

### Note

**N1. CSS chết: `.planner textarea` và `.planner select`.** `globals.css:19` định nghĩa textarea (min-height 110px, resize) và select trong planner, nhưng `Planner.tsx` chỉ dùng một `<input>` trong `.chat-box` — không có textarea/select nào. Tương tự rule dark-mode. Nên xóa hoặc dành cho một flow "mô tả dài" sau này.

**N2. CSS chết: `.bubble.typing`.** `globals.css:22` định nghĩa đầy đủ typing indicator (3 chấm + `typingPulse`) nhưng **không component nào render nó** (grep toàn bộ `.tsx` chỉ thấy `bubble assistant`). Hiện tại trạng thái chờ được thay bằng text `status` "Đang tìm địa điểm…". Micro-interaction rất đẹp nhưng đang bị bỏ phí.

**N3. `::selection` dùng `lavender` làm nền.** `globals.css:1` — chữ bôi đen tím trên nền tím; ở light mode `--lavender:#cdb3ff` + chữ `--ink-3:#4b2c82` có contrast thấp. Chi tiết nhỏ nhưng dễ thấy khi chọn đoạn văn dài.

**N4. `.status` và `.error` thiếu icon.** `globals.css:10` — chỉ text đậm màu (accent/danger), không có icon ✓/⚠. Khối message trong workspace (`PlanView.tsx:122`) và các form trông "phẳng" so với phần còn lại vốn có nhiều micro-detail.

**N5. `inventory-search` không có rule hover cho input.** `globals.css:28` — input chỉ đổi khi focus (outline toàn cục), không có border-color nhẹ khi hover như planner/chat-box. Cảm giác "chạm được" thấp hơn các form khác.

**N6. `admin-ai-table`/`admin-place-table` dùng grid số cột cứng.** `globals.css:40` — các bảng admin (6-7 cột) ép `font-size:13px` và `white-space:nowrap` để vừa; trên màn hình trung bình dễ tràn/co kéo. Đây là vấn đề thẩm mỹ "bảng", nằm ngoài phạm vi component đơn nhưng đáng ghi nhận.

**N7. `slot-select` overlay chiếm toàn bộ slot.** `PlanView.tsx:127` + `globals.css:25` — nút trong suốt phủ cả card; về thẩm mỹ OK (CSS đã gán `z-index:3` + `pointer-events:auto` cho icon-action), chỉ note về khả năng hiểu vùng click.

---

## Ma trận component → trạng thái

Ký hiệu: **D**=default, **H**=hover, **A**=active/selected, **Dis**=disabled, **F**=focus.

| Component | D | H | A | Dis | F | Nguồn |
|---|---|---|---|---|---|---|
| `.primary` | brand đặc, shadow-sm, pill 13x24 | brand-hover, shadow-md, lift -1px | (không có phản hồi active) | opacity .5, not-allowed | outline toàn cục 3px accent-2 | globals.css:7,1 |
| `.secondary` | nền trong, viền line-2 | viền accent, nền lavender-50, lift -1px | — | opacity .5 | outline toàn cục | globals.css:7 |
| `.danger` | nền danger, chữ #fff | nền đậm hơn, lift -1px | — | opacity .5 | outline toàn cục | globals.css:7 (⚠ contrast dark mode, H2) |
| `.icon-action` | 34x34, lavender-soft/accent | lavender, scale 1.06 | scale .94 | opacity .5 | outline toàn cục | globals.css:7 |
| `.chip` | nền surface, viền line-2 | viền accent, nền lavender-50 | nền brand, chữ trắng (aria-pressed) | opacity .5 | outline toàn cục | globals.css:7 |
| nút send chat-box | tròn brand, glyph ↑ | brand-hover | scale .94 | opacity .5 / .55 (planner) | outline toàn cục | globals.css:22,19 |
| input planner | radius-sm, nền surface-2 | (không hover riêng) | — | — | border accent + ring 4px lavender-soft | globals.css:19 |
| chat input | pill radius-full | (không hover riêng) | — | — | border accent + ring 4px | globals.css:22 |
| input inventory/comment/admin/stop/settings | radius-sm, nền surface-2 | (không hover riêng, N5) | — | — | chỉ outline toàn cục (M1) | globals.css:28,25,40,31,34 |
| `.card` | nền surface, viền line, lg24, shadow-sm | (tùy ngữ cảnh lift) | — | — | n/a | globals.css:10 |
| `.featured-card` | thumb 150px gradient + emoji 44px | lift -4px, shadow-lg | — | — | n/a (link) | globals.css:16 |
| `.slot` | grid 28/56/1fr/auto, md16 | shadow-md, lift -1px | viền accent + ring 4px | — | n/a | globals.css:25 |
| `.step` | lg24, badge 40px brand | — | — | — | n/a | globals.css:16 |
| `.faq-item` | md16, không hover (L3) | không có | mở: "+" xoay 45° | — | n/a | globals.css:16 |
| `.day-tabs` | pill nền lavender-50, không viền | nền lavender-soft | nền brand, chữ trắng | — | outline toàn cục | globals.css:25 |
| `.inventory-tabs` | pill nền surface, viền line-2 | chỉ đổi viền accent (M3) | nền brand + viền brand | disabled qua attribute | outline toàn cục | globals.css:28 |
| `.admin-pill` | pill lavender-50 12px/900 | n/a (tĩnh) | n/a | — | n/a | globals.css:40 |
| `.trip-facts span` | pill lavender-50 | n/a | n/a | — | n/a | globals.css:25 |
| `.bubble.assistant` | nền lavender-50, đuôi 6px trái | — | — | — | n/a | globals.css:22 |
| `.bubble.user` | nền brand, đuôi 6px phải | — | — | — | n/a | globals.css:22 |
| `.comment` | nền lavender-50, sm12 | — | resolved: opacity .58 + gạch ngang | — | n/a | globals.css:25 |
| `.timeline a.card` | card chuẩn | lift -2px, shadow-lg (M4) | — | — | outline toàn cục | globals.css:34 |

---

## Kết luận

**Điểm thẩm mỹ: 7/10.**

Lý do: hệ thống token màu/bán kính/bóng ấm áp và giàu cá tính, nhiều micro-detail thực sự tinh tế (chip active, slot selected ring, trip-facts dashed, admin-pill mã màu, bubble đối xứng gương) — nhưng đang thiếu một lớp điều phối component để ngôn ngữ hover/focus/radius/disabled không bị phân mảnh giữa các trang, cộng hai khiếm khuyết rõ rệt là card booking admin mất class `card` và dark-mode tương phản chữ trên nút send/danger.

---

**Confidence: 8/10**

**Ground-truth tally: 26/27 kết luận dựa trên code trực tiếp**
- Xác minh bằng đọc code (CSS token/state + TSX render): token `globals.css:1`; buttons `globals.css:7`; chip active `globals.css:7`; icon-action `globals.css:7`; planner focus ring `globals.css:19`; chat-box `globals.css:22`; bubbles + typing `globals.css:22`; typing KHÔNG được dùng (grep `.tsx` chỉ 1 match `bubble assistant` tại `Planner.tsx:162`); card `globals.css:10`; featured-card `globals.css:16`; step badge `globals.css:16`; faq-item `globals.css:16`; slot + selected `globals.css:25` + `PlanView.tsx:127`; version/comment-drawer + feedback-card `globals.css:25` + `PlanView.tsx:123-125`; day-tabs `globals.css:25`; inventory-tabs `globals.css:28`; timeline hover `globals.css:34`; admin-pill `globals.css:40`; admin offer-card thiếu `card` `admin/page.tsx:569` vs có `card` `explore/page.tsx:66`, `support/page.tsx:62`; dark-mode màu `globals.css:43` + `#fff` hard-code `globals.css:7,22`; disabled 0.5 vs 0.55 `globals.css:22,19`; people input dưới chat-box `Planner.tsx:207-218`; glyph ↑↻× `Planner.tsx:199`, `PlanView.tsx:126,127`, `roadtrip/page.tsx:56`; badge 40/30/28px `globals.css:16,31,25`; `.primary{width:100%}` `globals.css:7`.
- 1 kết luận dựa trên suy luận thiết kế (không có màn hình chạy thực tế): đánh giá tương phản/đẹp theo giá trị màu — xác suất hiệu lực cao (dựa trên mã hex trực tiếp) nhưng không đo bằng công cụ.
