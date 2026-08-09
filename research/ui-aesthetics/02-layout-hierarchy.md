# 02 — Layout, Hierarchy & Composition

**Trang web:** "Mình Đi Đâu Thế" (Next.js + TypeScript)
**Phạm vi:** `frontend/app/globals.css`, `app/layout.tsx`, `app/page.tsx`, `components/Planner.tsx`, `components/PlanView.tsx`, `components/Navigation.tsx`, `components/Footer.tsx`, `components/MapView.tsx`, và các trang `app/{explore,roadtrip,history,settings,login,admin,plan/[token],privacy}.tsx`.
**Loại:** Nghiên cứu THUẦN (chỉ đọc/phân tích, không sửa code).
**Trọng tâm:** spacing & scale, grid & alignment, typography hierarchy, cân bằng hero, workspace plan page, landing flow, và liệt kê vấn đề layout cụ thể kèm `file:line`.

> Ghi chú phương pháp: file `globals.css` được viết minified — toàn bộ 43 dòng đều dài hàng nghìn ký tự, mỗi dòng chứa 20–60 selector. Mọi trích dẫn `globals.css:Lxx` đều chỉ dòng vật lý của file.

---

## Tóm tắt điều hành

Về tổng thể, giao diện có **khung xương layout tốt**: hệ thống container `.shell` 1200px nhất quán, bộ card/surface dùng chung, typography dùng `clamp()` với hệ số `vw` đều đặn, và landing page có nhịp section rõ ràng (72px + border-top). Đây là nền tảng vững để tạo cảm giác "đã được thiết kế".

Tuy nhiên có **3 vấn đề xương sống kéo tụt chất lượng thẩm mỹ tổng thể**:

1. **`<main>` bị lồng nhau** — `layout.tsx` bọc mọi trang trong `<main className="shell">` (L9) trong khi **mỗi trang tự render thêm một `<main>` nữa** (7/8 trang có `main` riêng). Hệ quả layout trực tiếp: `.workspace-page{max-width:1500px}` (L25) không bao giờ có hiệu lực vì bị kẹp trong shell 1200px — 3 cột workspace bị nén, cột chat chỉ còn ~276px.
2. **Không có spacing scale** — CSS dùng **gần như mọi số nguyên từ 1 đến 72px** (kể cả 7, 9, 11, 13, 15, 17, 18, 22, 26, 28) cho margin/padding/gap. Nhịp điệu dọc/ngang bị rời rạc; cùng một "vai trò" spacing (padding input, gap panel) lại có 4–5 giá trị khác nhau.
3. **Tầng bậc tiêu đề trang không nhất quán giữa các trang** — "page title" được render với 6 cỡ khác nhau (34–72px) tùy trang, dù đều cùng một cấp độ.

Không có vấn đề **Blocker** (không lỗi gãy layout hoàn toàn ở breakpoint chuẩn), nhưng có **4 vấn đề High** và **6 vấn đề Medium** được liệt kê chi tiết bên dưới.

---

## Điểm mạnh

1. **Hệ thống container & gutters nhất quán.** `.shell{max-width:1200px;padding:0 24px}` (globals.css:L1) áp cho nav, footer và gần như mọi trang → mọi khối nội dung đều căn cùng một lề ngang 24px. Việc này tạo "vertical line" vô hình giúp mắt dễ quét.

2. **Bộ card/surface dùng chung rất ổn định.** `.card{padding:24px;border:1px solid var(--line);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm)}` (L10) được tái sử dụng cho planner, workspace panel, drawer, admin section, login, offer-card, step, faq-item… Một file chỉ định nghĩa 1 lần, tạo cảm giác hệ thống gắn kết.

3. **Typography `clamp()` có hệ số vw đồng pha.** Hero 6.5vw (L13), page title 5–5.5vw (L28, L31), section 4vw (L16), panel 16px cố định (L25). Đường kính chữ tỷ lệ đều theo viewport; trong cùng một trang, tầng bậc hero→section→card rất rõ (88px → 46px → 20/19px).

4. **Landing flow có nhịp điệu thật sự.** Hero (full-height) → các `.landing-section` đều `padding:72px 0;border-top:1px solid var(--line)` (L16) → CTA banner gradient → footer `margin-top:72px` (L37). Border-top 1px tạo nhịp "ngắt trang" tinh tế, không quá nặng; khoảng 72px tạo nhịp thở đồng đều giữa các khối.

5. **Eyebrow + title + lead là khuôn mẫu thống nhất.** Explore (L59), roadtrip (L56), admin (L355–357), plan (L120), login (L66–68), settings (L37) đều mở đầu bằng `.eyebrow` nhỏ → h1 lớn → `.lead` — giúp 6 trang khác nhau có cùng "phong thái mở bài".

6. **Quyết định reorder workspace trên mobile rất đúng hướng.** Ở ≤760px, thứ tự chuyển thành itinerary → map → chat (L25), tức ưu tiên nội dung (lịch trình) lên đầu thay vì hội thoại — một lựa chọn hierarchy đáng ghi nhận.

7. **Footer-grid cân đối.** `1.6fr 1fr 1fr 1fr` (L37) với cột brand rộng hơn hẳn — tỷ lệ đúng cho một footer bốn cột, tránh cảm giác 4 cột giống hệt nhau đơn điệu.

---

## Vấn đề theo mức

### Blocker
Không có. Không tìm thấy lỗi nào làm vỡ hoàn toàn bố cục (overflow ngang ở viewport chuẩn, phần tử biến mất, hoặc không thể sử dụng) tại desktop/tablet/mobile.

### High

**H1. Workspace 3 cột bị nén do `max-width:1500px` vô hiệu — cột chat quá hẹp.**
`layout.tsx:9` render `<main className="shell">` (max 1200px, padding 24px) bọc toàn bộ children; `PlanView.tsx:119` lại render `<main className="workspace-page">` có `max-width:1500px` (globals.css:L25). Vì `.shell` đã giới hạn chiều rộng parent, max-width 1500px **không bao giờ có hiệu lực**. Tính toán thực tế trên desktop: nội dung khả dụng = 1200 − 48 (shell) − 40 (padding workspace-page 20px×2) = **1112px**. Cột tối thiểu `260+400+380 + 2×16 gap = 1072px` (L25) → sau phân bổ fr (0.65/1.2/1.05) cột chat rơi vào khoảng **276px**, itinerary ~430px, map ~406px. Cột **chat — nơi nhập văn bản tinh chỉnh, là trung tâm "hội thoại" của sản phẩm** — là cột hẹp nhất và bị đặt bên trái (vị trí ưu tiên quét đầu tiên), trong khi itinerary (deliverable chính) chỉ hơn 400px. *Gợi ý:* dỡ bỏ `<main>` lồng (xem H2) để workspace-page lấy đúng 1500px; hoặc đổi grid thành `minmax(280px,0.8fr) minmax(360px,1fr) minmax(320px,0.9fr)` với `fr` tính trên 1500px thay vì 1112px. Cân nhắc đảo thứ tự cột thành chat giữa, itinerary trái.

**H2. `<main>` lồng nhau — invalid HTML, nguyên nhân gốc của H1.**
`layout.tsx:9` (main.`shell`) + `<main>` riêng trong: `page.tsx:27`, `explore/page.tsx:59`, `roadtrip/page.tsx:56`, `history/page.tsx:55`, `settings/page.tsx:37`, `login/page.tsx:64`, `admin/page.tsx:354`, `privacy/page.tsx:4`, và `plan/[token]/page.tsx:7` (qua `PlanView.tsx:119`). Trừ trang `terms`/`support` chưa đọc, gần như mọi route đều lồng 2 `<main>`. Ngoài việc sai ngữ nghĩa/a11y, nó khiến `max-width` riêng của từng trang (workspace 1500px, explore/admin 1200–1220px) bị shell chèn ép. *Gợi ý:* `layout.tsx` chỉ giữ `shell` như div thường (hoặc bỏ bọc `<main>`), mỗi trang giữ duy nhất một `<main>`; hoặc đưa `padding:0 24px` vào từng trang và bỏ class `.shell` ở layout.

**H3. Không có spacing scale — giá trị margin/padding/gap tràn lan, không theo hệ 4px/8px.**
Scan toàn file cho thấy gần như **mọi số nguyên 1–72px** xuất hiện làm khoảng cách: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,54,56,60,62,64,66,70,72 (globals.css, toàn file). Các giá trị lẻ 7/9/11/13/15/17/18/22/26/28 không thuộc bất kỳ scale 4px hay 8px nào. Bằng chứng cụ thể về "cùng vai trò, khác giá trị":
- **padding input**: planner `14px` (L19) · chat-box `12px 18px` (L22) · inventory/comment `11px 14px` (L28/L25) · settings/admin `12px 14px` (L34/L40) · stop-input `10px 12px` (L31).
- **padding button/pill**: primary `13px 24px` (L8) · tab `11px 20px` (L28) · day-tab `8px 14px` (L25) · chip `9px 16px` và quick-chip `8px 13px` (L8) · pill `6px 11px` (L40).
- **gap nội bộ**: nav `16px` (L4) · chip `7px` (L8) · chat `10px` (L22) · trip-facts `10px` (L25) · panel-title `9px` (L25) · day-tabs `6px` (L25) · slot `10px` (L25) · admin `10–12px` (L40).
- **khoảng cách dọc section**: 72px landing (L16) · 52px mobile (L16) · 64px login (L34) · 48px settings (L34) · 24/48px legal (L40) · 56px footer top (L37).
*Gợi ý:* định nghĩa 1 scale 4px/8px (4, 8, 12, 16, 24, 32, 48, 64) làm token, thay các giá trị 7, 9, 11, 13, 15, 17, 18, 22, 26, 28 bằng giá trị gần nhất trong scale; dùng `--space-*` để đảm bảo một vai trò = một giá trị.

**H4. "Page title" không nhất quán giữa các trang — tầng bậc tiêu đề lỏng lẻo.**
Cùng một cấp độ (h1 của trang) nhưng 6 cỡ khác nhau:
- explore `clamp(42px,5.5vw,72px)` (L28) · roadtrip `clamp(42px,5.5vw,72px)` (L31) · admin `clamp(40px,5vw,66px)` (L40) · history dùng base `clamp(38px,5vw,62px)` (L10) · login `clamp(36px,5vw,52px)` (L34) · settings `clamp(34px,4.5vw,54px)` (L34) · trip-header `clamp(30px,3.6vw,52px)` (L25).
Trang "settings" (hành động phụ) lại được hạ thấp xuống 54px trong khi "explore" lên 72px — đúng ý đồ nhấn mạnh, nhưng settings 54px > login 52px gây nhiễu: hai trang cùng tầng phụ lại xếp ngược nhau. Lệch cực đại 52→72px trên cùng một cấp tạo cảm giác "mỗi trang một kích cỡ". *Gợi ý:* chuẩn hóa về 2 bậc duy nhất: bậc chính (explore/roadtrip) `clamp(42px,5.5vw,72px)` và bậc phụ (settings/login) `clamp(34px,4.5vw,52px)`; bỏ override lẻ tẻ (history, admin).

### Medium

**M1. Hero mobile: h1 clamp floor 48px quá lớn so với nội dung.**
`.hero h1{font-size:clamp(48px,6.5vw,88px)}` (L13) — floor 48px nghĩa là mọi màn hình dưới ~738px đều giữ 48px. Trên 375px, tiêu đề 2 dòng (`heroTitleFirst` + `<br/>` `heroTitleSecond`, page.tsx:31–35) chiếm ~96px, trong khi lead 20px và planner form ở dưới. Khi hero chuyển 1 cột ở ≤900px (L13), cột text ngắn + chữ khổng lồ tạo tỷ lệ mất cân bằng trên mobile. *Gợi ý:* hạ floor xuống ~34–38px cho dưới 600px (ví dụ `clamp(34px,9vw,48px)` cho mobile) và thêm media query nhỏ.

**M2. Cân bằng hero desktop lệch theo chiều cao, không theo chiều rộng.**
`1.05fr/.95fr` + gap 56px (L13) cân bằng chiều ngang tốt, nhưng `.hero{min-height:calc(100vh - 120px)}` (L13) kết hợp nội dung cột text ngắn (eyebrow + h1 + lead + 1 dòng social-proof) khiến cột text có vùng trống lớn bên dưới khi planner (form dài: chat-welcome, 3 chips, input, people, status/error, 2 disclaimer — Planner.tsx:159–234) cao hơn. `.hero-left{justify-content:center}` (L13) chỉ căn giữa theo trục — nếu cột text ngắn hơn, khoảng trống rơi cả trên lẫn dưới, còn eyebrow bị đẩy xa khỏi mép trên. *Gợi ý:* bỏ `min-height` cứng hoặc đổi sang `align-items:start` với padding-top cố định, để khoảng trống phân bố tự nhiên thay vì "giãn đều".

**M3. Mobile workspace: chat bị đẩy xuống cuối trang — người dùng phải cuộn dài để tinh chỉnh.**
Ở ≤760px, `.workspace>.chat-panel{order:3}` (L25) đặt chat sau map. Hợp lý về ưu tiên đọc nội dung, nhưng hệ quả thực dụng: ô chat (nơi nhập yêu cầu tinh chỉnh lịch trình) nằm sát footer, phải cuộn qua toàn bộ itinerary + map 400px (L25) mới dùng được. `chat-panel min-height:430px` (L25) càng đẩy sâu. *Gợi ý:* đặt order `itinerary → chat → map` (chat ngay sau nội dung chính, map là chi tiết tham khảo cuối cùng), hoặc ghim chat input bằng `position:sticky`.

**M4. Map panel không phải `.card` — 3 cột workspace không đồng bộ surface.**
`chat-panel` và `itinerary-panel` đều có class `card` (PlanView.tsx:126–127) → nhận `padding:18px` + border + shadow (L25/L10). `map-panel` (PlanView.tsx:128) **không có class card**; chỉ có `.map` (border, radius, không padding — L25) + `.map-legend.card` bên dưới. Kết quả: cột bản đồ nhìn "trần" so với 2 cột có nền trắng, và đáy 3 panel không cùng đường lề trong. *Gợi ý:* thêm class `card` cho `.map-panel` và đặt padding riêng để map tràn tới mép card (hoặc gắn nền/border cho cả panel).

**M5. `trip-actions` quá tải — header plan bị dồn nút.**
PlanView.tsx:120 render 8–9 nút `.secondary` trong header (share, PDF, calendar, JSON, comments, feedback, versions, undo, regenerate). Desktop: `.trip-actions{gap:8px;flex-wrap:wrap}` với `align-items:flex-end` (L25) → hàng nút có thể cao 2–3 dòng, cạnh tranh chiều cao với h1 `clamp(30,3.6vw,52px)` và đẩy `.trip-facts` xuống. Mobile: `.trip-actions button{flex:1 1 42%}` (L25) tạo lưới 2 cột nút chiếm toàn chiều rộng — mật độ control quá cao ở tầng header. *Gợi ý:* nhóm nút phụ (undo, versions, regenerate) vào dropdown hoặc chuyển xuống `.trip-facts`/toolbar riêng; giữ header tối đa 3–4 hành động chính.

**M6. Trục dọc bắt đầu trang không nhất quán.**
Sau nav (margin-bottom 32px — L4): explore/roadtrip/history/admin bắt đầu ngay (0), login thêm `margin:64px auto` (L34), settings `margin:48px auto` (L34), legal `margin:24px auto 48px` (L40), còn plan/workspace không có margin-top riêng (L25). Cùng là "khoảng cách dưới nav" nhưng 4 giá trị khác nhau (0/24/48/64px) → khi chuyển trang, vị trí tiêu đề nhảy dọc, làm loãng cảm giác hệ thống. *Gợi ý:* chuẩn hóa một giá trị duy nhất (ví dụ 40px) cho khoảng cách tiêu đề–nav trên toàn bộ trang.

### Low

**L1. Inset ngang của workspace lệch 20px so với mọi trang khác.**
`workspace-page{padding:0 20px}` (L25) chồng lên shell 24px → nội dung plan cách mép **44px**, trong khi explore/roadtrip/admin/history cách **24px**. Trip-header của plan không cùng đường lề với tiêu đề các trang khác khi lướt qua lại. *Gợi ý:* bỏ padding của workspace-page hoặc đổi shell.

**L2. `.primary{width:100%}` toàn cục phải override khắp nơi.**
`globals.css:L8` ép nút chính full-width; mỗi nơi cần width tự nhiên lại override thủ công (`.roadtrip-actions .primary{width:auto;margin-left:auto}` L31; `.cta-banner .primary{width:auto}` L16; `.inventory-search .primary{height:46px}` L28). Nguy cơ: nút full-width không mong muốn khi class được dùng ngoài form. *Gợi ý:* đưa `width:100%` vào modifier riêng (vd `.primary--block`), để `.primary` mặc định inline.

**L3. Class `.timeline` bị dùng với 2 ngữ nghĩa, đệm chồng lấn.**
`.timeline{display:grid;gap:14px}` phục vụ cả history (L34, history/page.tsx:55) lẫn slot itinerary (L25, PlanView.tsx:127). Trong itinerary, slot còn có `margin-bottom:10px` (L25) chồng lên grid gap 14px — quy tắc đệm mơ hồ. *Gợi ý:* tách class (`.history-list` / `.slot-list`) và giữ một nguồn duy nhất cho khoảng cách.

### Note

**N1. Breakpoint các module không đồng bộ** (chi tiết ở mục Responsive) — mỗi module tự chọn 600/760/800/900/1100px thay vì một bộ breakpoint thống nhất.

**N2. FAQ là cột hẹp (720px) giữa 2 section full-width.** `faq-list{max-width:720px;margin:auto}` (L16) tạo hiệu ứng "thắt lại" giữa featured grid (full) và CTA banner (full) — chủ ý dừng nhịp, nhưng khoảng co từ ~1152px → 720px → 1152px hơi gấp; có thể căn trái theo `.section-head` thay vì giữa để đồng nhất với featured/steps.

**N3. Không có xử lý viewport rất rộng.** Container cố định 1200px (L1) khiến màn 1440–2560px chỉ có hai dải nền trống lớn; hero 88px và workspace 3 cột không hưởng lợi từ không gian thừa. Chấp nhận được với thiết kế container cố định, nhưng hero nên được phép kéo tối đa.

---

## Spacing scale

### Bảng giá trị thực tế (trích từ scan toàn file)

Nhóm **hệ 4px/8px** (hợp lệ, cần giữ): 4 · 8 · 12 · 16 · 20 · 24 · 28 · 32 · 36 · 40 · 44 · 48 · 52 · 56 · 64 · 72.
Nhóm **giá trị lẻ / ngoài scale** (nguồn nhiễu nhịp điệu): 1 · 2 · 3 · 5 · 6 · 7 · 9 · 10 · 11 · 13 · 14 · 15 · 17 · 18 · 19 · 22 · 26 · 30 · 34 · 38 · 42 · 46 · 50 · 54 · 60 · 62 · 66 · 70.

### Nhận xét tính nhất quán

- **Không có token spacing.** File định nghĩa 30+ biến màu/radius/shadow/font (L1) nhưng **không có một biến khoảng cách nào** — mọi margin/padding/gap viết trực tiếp số px. Đây là lý do gốc của sự phân tán.
- **Tỷ lệ nhiễu cao.** Trong nhóm khoảng cách thân mật (dưới 24px), hầu như mọi số nguyên 1–20px đều xuất hiện (13 giá trị liên tiếp). Nếu chia theo scale 8px lý tưởng (8/16/24…), số "giá trị không khớp" chiếm đa số (7, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20 — tức 12/15 giá trị < 24px).
- **Cùng vai trò, khác giá trị** (bằng chứng ở H3): input padding 4 biến thể (10/11/12/14px), button padding 5 biến thể (6/8/9/11/13px), gap panel 5 biến thể (6/7/9/10/16px). Về mặt thị giác, các form/panel trên cùng một trang không "đồng nhịp" — ví dụ ngay trong Planner, input context padding 14px (L19) đứng cạnh people input cũng 14px (L19) nhưng khác chat input 12px 18px (L22) dù cùng loại.
- **Khoảng cách dọc section là nơi gọn nhất.** 72px landing (L16) → 52px mobile (L16) → 64px login (L34) → 48px settings (L34) → 24/48px legal (L40). Đúng là một "dải section rhythm" (72/52) cho landing và một dải "page shell rhythm" cho các trang khác, nhưng hai dải này không thống nhất với nhau — cùng là "khoảng trắng trên dưới của một trang" lại chia 5 giá trị.

**Kết luận spacing:** nên định nghĩa một scale duy nhất, ví dụ hệ **4/8/12/16/24/32/48/64/96** (hoặc hệ 8/16/24/32/48/64/96 với 12/20 cho trung gian), rồi thay 28 giá trị lẻ bằng giá trị scale gần nhất. Chi phí thấp, tác động thẩm mỹ cao vì nhịp điệu là thứ mắt người cảm nhận đầu tiên.

---

## Đánh giá responsive

### Các media query hiện có
| Breakpoint | Module | Nội dung chính |
|---|---|---|
| 1100px | Workspace (L25) | 3 cột → `320px 1fr`, map xuống full-width |
| 900px | Hero (L13) | 2 cột → 1 cột |
| 900px | Landing sections (L16) | featured/steps 3 → 1 cột |
| 900px | Explore (L28) | search 6 → 2 cột, offer-grid 3 → 2 cột |
| 900px | Footer (L37) | 4 → 2 cột |
| 900px | Admin (L40) | strip/grid → 2 cột |
| 800px | Roadtrip (L31) | stop-input → 1 cột, result → 1 cột |
| 760px | Nav (L5) | nav wrap, link thu nhỏ |
| 760px | Workspace (L25) | flex 1 cột, order itinerary→map→chat |
| 600px | Explore/Footer/Admin (L28/L37/L40) | tất cả → 1 cột |

### Nhận xét

1. **Không có bộ breakpoint thống nhất.** 5 mốc khác nhau (600/760/800/900/1100) phân bổ tùy module. Hệ quả: ở viewport 820px, explore vẫn 2 cột offer-grid nhưng roadtrip đã 1 cột; ở 768px (iPad), roadtrip đã single-column trong khi explore còn 2 cột — trải nghiệm "đổi bố cục" không diễn ra cùng một thời điểm, gây cảm giác mỗi trang có nhịp riêng. *Gợi ý:* chuẩn hóa 3 mốc `1200/900/600` (với mốc 1100 cho workspace vì lý do 3 cột) và dùng chung cho mọi module.

2. **Khoảng giữa 900–1100 là "khu vực mù" của workspace.** Ở 1101px+, workspace 3 cột với cột chat ~276px (đã nén theo H1); vừa xuống 1100px thì chuyển hẳn 2 cột. Không có mốc trung gian 1000px giúp 3 cột thở dần — sự đổi bố cục diễn ra đột ngột ở một điểm duy nhất.

3. **Hero và landing đổi bố cục cùng lúc (900px)** — đồng bộ tốt, nhưng h1 floor 48px (M1) không được tinh chỉnh theo breakpoint nào cả: 900px dùng 58px (6.5vw) nhưng dưới 738px giữ nguyên 48px cho tới 0px. Nên có mốc ~480px hạ tiếp xuống 34–38px.

4. **Tablet chưa có chiến lược riêng.** Ở 768px, explore-search là 2 cột (L28) — hợp lý; admin-strip là 2 cột (L40) — chấp nhận được; workspace 2 cột + map full — ok. Nhưng không có module nào tận dụng chiều ngang tablet tốt hơn; mọi thứ chỉ thuần "co lại", không "tái sắp xếp" (trừ workspace).

5. **Mobile 1 cột cuối cùng đủ tốt.** Tại ≤600px mọi grid về 1 cột (L28/L37/L40), nav wrap (L5), trip-header chồng dọc (L25). Không thấy overflow ngang do `minmax` đã được xử lý (vd `.inventory-search` → 1fr ở 600px L28). Điểm trừ duy nhất là thứ tự chat ở workspace (M3).

---

## Kết luận

**Điểm thẩm mỹ: 7/10.**

Lý do: khung xương layout (container, card, typography clamp, landing rhythm, reorder mobile) rất vững và chuyên nghiệp, nhưng bị kéo xuống bởi không có spacing scale (nhịp điệu rời rạc), `<main>` lồng làm nén 3 cột workspace, và tầng bậc tiêu đề trang không nhất quán giữa các trang.

---

**Confidence: 7/10**

Lý do hạ 1 điểm so với mức cao nhất: file CSS minified 43 dòng dài, có 2 trang (`terms`, `support`) chưa đọc để đối chiếu lớp `.legal-page`; các con số chiều rộng cột workspace (~276/430/406px) là **tính toán từ spec CSS** (fr, gap, minmax) chứ chưa được đo bằng render thực tế; không chạy build/preview nên chưa xác nhận 100% hành vi browser đối với nested `<main>`.

**Ground-truth tally: 26/28 kết luận dựa trên code (file:line)**
- 26 kết luận có trích dẫn trực tiếp `file:line` (globals.css, layout.tsx, page.tsx, PlanView.tsx, Planner.tsx, các trang app/*).
- 2 kết luận dựa trên suy luận toán học không render trực tiếp: bề rộng cột workspace (H1, mục Responsive #2) — dùng công thức từ grid spec tại `globals.css:25` và `layout.tsx:9`, chưa đo thực tế.
