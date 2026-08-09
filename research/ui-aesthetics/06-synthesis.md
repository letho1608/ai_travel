# 06 — Tổng hợp thẩm mỹ giao diện — "Mình Đi Đâu Thế"

**Vai trò:** Agent tổng hợp (synthesis) — hợp nhất 5 lane nghiên cứu thẩm mỹ, đối chiếu chéo, xác minh trực tiếp code nguồn, và phát hành một bức tranh duy nhất kèm khuyến nghị ưu tiên.
**Loại:** THUẦN — chỉ đọc, không sửa code.
**Nguồn đầu vào:** `01-visual-identity.md` (5.5/10), `02-layout-hierarchy.md` (7/10), `03-components.md` (7/10), `04-ux-polish.md` (6.5/10), `05-walkthrough.md` (7.5/10) + đối chiếu trực tiếp `globals.css`, `layout.tsx`, `PlanView.tsx`, `MapView.tsx`, `RoadTripMap.tsx`, `LocaleProvider.tsx`, `admin/page.tsx`, `roadtrip/page.tsx`, `page.tsx`, `support/page.tsx`, `i18n-core.ts`, `package.json`, cấu trúc `app/` và `public/`.

---

## Verdict tổng hợp

**Điểm thẩm mỹ tổng thể: 6.5/10.**

Sản phẩm sở hữu một nền tảng thiết kế thực sự tốt — hệ token màu ngữ nghĩa 26 biến, dark mode được thiết kế như một hệ đảo ngược "đèn pha" thay vì bôi đen, một easing duy nhất cho toàn bộ chuyển động, focus-visible toàn cục chuẩn, và một landing + workspace đầy micro-detail tinh tế khiến mọi thứ nhìn "được chăm chút" ngay lần đầu lướt qua. Nhưng chất lượng không đều và có những vết nứt thực sự: dark mode vỡ ở đúng các action quan trọng nhất (nút gửi chat, CTA banner, nút danger — tất cả do màu `#fff` hard-code không được override); admin page có lỗi bố cục thật (strip 5 thẻ trên lưới 4 cột, card booking mất class, nút trần); `<main>` lồng nhau nuốt ý định thiết kế 1500px của workspace; bản sắc "Hà Nội ấm áp" chưa được hiện thực bằng màu vì `--brand` trùng y hệt `--ink` và font thương hiệu khai báo nhưng không bao giờ tải; còn RTL và toàn bộ tầng phản hồi động (spinner/skeleton/error) ở trạng thái "cài đặt nửa vời". Nền tảng xứng 8/10, nhưng số lỗi thị giác nhìn thấy được trong dark mode và admin kéo điểm thực tế về 6.5.

---

## Điểm mạnh thật sự

Không nói qua loa — những thứ dưới đây là tài sản thực sự, xác minh được trong code:

1. **Dark mode là một hệ đảo ngược có chủ đích, không phải "bôi đen".** Toàn bộ khối `@media(prefers-color-scheme:dark)` (globals.css:43) đảo đồng bộ 4 lớp: nền, chữ, brand→lavender sáng, status→tông sáng trên soft tối. Cặp `--brand`/`--brand-contrast` dark = `#cdb3ff`/`#2a182e` đạt 9.06:1. Contrast text dark đo được đều vượt AA (`--muted` 7.41:1, `--accent` 6.78:1). Hiếm có ở MVP.
2. **Một easing duy nhất cho toàn bộ chuyển động.** `--ease: cubic-bezier(.4,0,.2,1)` (globals.css:1) được tham chiếu nhất quán trong mọi transition; duration có quy luật (transform .12s nhanh, box-shadow/color .2s chậm hơn một nhịp). Đây là dấu hiệu của design-token có chủ đích, tạo cảm giác "một thương hiệu chuyển động".
3. **Sticky nav xử lý glare đúng chuẩn hiếm thấy.** Có `@supports(backdrop-filter)` giảm độ trong suốt từ .86 → .82 khi blur khả dụng (globals.css:4), kèm variant dark riêng.
4. **Micro-detail giàu cá tính ở cấp component.** Chip quick-action dùng `aria-pressed` (trạng thái thẩm mỹ luôn khớp trạng thái logic — globals.css:7), slot selected dùng ring kép accent + `0 0 0 4px lavender-soft` (globals.css:25), `last-updated` dùng `border-style:dashed` đánh dấu "dữ liệu tĩnh" không cần thêm một dòng chữ (globals.css:25), bubble chat đối xứng gương với đuôi 6px (globals.css:22), số bước dùng `counter(step, decimal-leading-zero)` in "01/02/03" không cần state (globals.css:16), chấm `assistant-dot` với halo 6px (globals.css:22). Không phải code được sinh ra mà là code được thiết kế.
5. **Landing flow có nhịp điệu thật sự.** Hero full-height → các section `padding:72px 0` + `border-top:1px` → CTA gradient → footer `margin-top:72px` (globals.css:16,37). Border-top 1px làm "ngắt trang" tinh tế; khuôn mẫu eyebrow → h1 → lead xuất hiện nhất quán ở 6 trang khác nhau.
6. **Quyết định hierarchy trên mobile workspace đúng hướng.** Ở ≤760px thứ tự đổi thành itinerary → map → chat (globals.css:25) — ưu tiên deliverable lên đầu. Sai về vị trí thực dụng (chat bị đẩy xa — xem H11) nhưng tư duy hierarchy đúng.
7. **Trải nghiệm bàn phím được đặt nền tốt.** `:focus-visible` 3px accent-2 + offset (globals.css:1), planner dùng ring `0 0 0 4px lavender-soft`, `aria-live`/`role="alert"`/`aria-busy` được gắn đúng chỗ, icon buttons đều có aria-label. Nền tảng SR vững — chỉ thiếu mảng visual (busy/error).

---

## Danh sách vấn đề hợp nhất

Phân loại gộp của synthesis, dựa trên trọng số ảnh hưởng thẩm mỹ thực tế (điều chỉnh khi các lane khác nhau — ghi rõ ở mục Mâu thuẫn). Mã nguồn gốc: [A1]–[A5] + mã của lane đó.

### Blocker (vỡ thị giác, thao tác chính mất/không đọc được)

**BL-1. Nút gửi chat biến mất trong dark mode — `color:#fff` cứng trên nền brand sáng.**
- Mô tả: `.chat-box button{background:var(--brand);color:#fff}` (globals.css:22). Dark đổi `--brand:#cdb3ff` nhưng **không có override `.chat-box button`** trong khối dark (đã xác minh bằng grep). Mũi tên ↑ trắng trên nền lavender nhạt = 1.83:1.
- Ảnh hưởng: nút hành động chính của toàn flow tạo/tinh chỉnh plan (Planner.tsx:198, PlanView.tsx:126) mất hút ở một nửa người dùng.
- File:line: `frontend/app/globals.css:22`, `:43` (thiếu override).
- Gợi ý: dark thêm `.chat-box button{color:var(--brand-contrast)}`, hoặc đổi gốc luôn.
- Nguồn: [A1 B1], [A3 H2], [A4 H-2].

**BL-2. CTA banner vỡ toàn bộ trong dark mode.**
- Mô tả: `.cta-banner` gradient `ink-3→accent→accent-2` + `color:#fff`, nút primary `background:#fff;color:var(--ink-3)` (globals.css:16). Dark: cả 3 màu gradient đều thành lavender sáng → nền gần như trắng tím, chữ trắng 1.83–3.93:1, và nút CTA là chữ `--ink-3` (dark = `#cdb3ff`) trên nền trắng = 1.4:1 — tan vào banner.
- Ảnh hưởng: "chiêu bài" quan trọng nhất của landing thành một mảng màu phẳng, nút biến mất.
- File:line: `frontend/app/globals.css:16`.
- Gợi ý: trong khối dark giữ gradient bằng màu tối cố định (vd `#2a182e→#4b2c82 60%→#926cd6`) và override `.cta-banner .primary{background:var(--brand);color:var(--brand-contrast)}`.
- Nguồn: [A1 B2]. (A5 khen CTA "rất đẹp" — đúng ở light, không kiểm tra dark; xem Mâu thuẫn.)

### High (mất đọc được / lỗi bố cục thực tế / sai ngữ nghĩa màn hình quan trọng)

**H-1. Nút Danger dark mode: chữ trắng trên nền cá hồi + hover còn sót màu light.**
- Mô tả: `.danger{background:var(--danger);color:#fff}`, hover `#a03a33` (globals.css:7). Dark `--danger:#ff9b8a` → chữ trắng = 2.04:1; hover `#a03a33` là đỏ gạch của light, lạc tông. Không có override `.danger` trong dark (đã xác minh). Đây là nút xoá/huỷ dữ liệu — nơi cần đọc rõ nhất.
- File:line: `globals.css:7`, `:43`.
- Gợi ý: dark override `.danger{background:var(--danger);color:var(--brand-contrast)}` (nền sáng + chữ tối), hover dùng tông sáng của danger.
- Nguồn: [A1 H1], [A3 H2], [A4 H-2], [A4 L-8].

**H-2. Icon-action hover dark mode 1:1 — icon đồng màu nền.**
- Mô tả: `.icon-action:hover:not(:disabled){background:var(--lavender);color:var(--ink-3)}` (globals.css:7). Dark: `--lavender` = `--ink-3` = `#cdb3ff`. **Lưu ý chính xác hoá:** dark block *có* override `.icon-action:hover:not(:disabled)` nhưng giá trị vẫn là `lavender`/`ink-3` (globals.css:43) → không có tác dụng, kết quả vẫn 1:1. Nút ↻ (swipe) và remove stop khi hover hiện nền lavender với icon cùng màu.
- File:line: `globals.css:7`, `:43`.
- Gợi ý: dark override hover thành `color:var(--brand-contrast)`.
- Nguồn: [A1 H2], [A3 matrix].

**H-3. Contrast light mode không đạt AA cho text nhỏ và link.**
- Mô tả: `--accent:#926cd6` = 3.93:1 (link, `.eyebrow` 12px, `.status`) — fail AA; `--muted:#7f7482` = 4.11:1 (`.lead` 19px, `.faq-body` 15px, `slot p`, `disclaimer`); `--muted-2:#948b96` = 3.29:1 (disclaimer 13px, `source` 11px). Đều dưới 4.5:1 cho normal text. Dark mode mảng này pass (7.41:1 / 5.74:1).
- File:line: `globals.css:1`, `:10`.
- Gợi ý: đậm hoá `--accent` (~`#7a5ab8`) và `--muted`/`--muted-2` (~`#6e6374`/`#7d7483`) ở light; tách token `--link` nếu cần bảo vệ bản sắc.
- Nguồn: [A1 H3/M4], [A4 H-3].

**H-4. `<main>` lồng nhau — invalid HTML và nguyên nhân gốc nuốt 1500px workspace.**
- Mô tả: `layout.tsx:9` bọc mọi route trong `<main className="shell">` (max 1200px); **9/9 trang đọc được** render thêm `<main>` riêng (page.tsx:27, explore:59, roadtrip:56, history:55, settings:37, login:64, privacy:4, terms/support + PlanView:119). `.workspace-page{max-width:1500px}` (globals.css:25) không bao giờ có hiệu lực → 3 cột bị nén trong ~1112px, cột chat (~276px) hẹp nhất.
- File:line: `layout.tsx:9`, `PlanView.tsx:119`, `globals.css:25`.
- Gợi ý: layout chỉ giữ `shell` như div, mỗi trang giữ một `<main>`.
- Nguồn: [A2 H1/H2], [A5 #5].

**H-5. Card booking admin mất class `card` — khối thị giác vỡ thành text trần.**
- Mô tả: `admin/page.tsx:569` dùng `className="offer-card"` trong khi `explore/page.tsx:66` và `support/page.tsx:62` có đủ `card`. CSS `.offer-card` không định nghĩa nền/border/padding — mọi style nằm ở `.card` (globals.css:10).
- Ảnh hưởng: "Booking support queue" hiện thành chữ trần trên nền giấy.
- File:line: `admin/page.tsx:569` (vs `explore:66`, `support:62`), `globals.css:10,28`.
- Gợi ý: thêm class `card` (hoặc style độc lập cho `.offer-card`).
- Nguồn: [A3 H1], [A3 L5].

**H-6. Admin strip 5 thẻ trên lưới 4 cột — thẻ thứ 5 rớt hàng.**
- Mô tả: `.admin-strip{grid-template-columns:repeat(4,1fr)}` (globals.css:40) với 5 `<article class="card">` (admin/page.tsx:367-372). Thẻ "Open support" rớt xuống hàng 2 chiếm 1/4 chiều rộng.
- File:line: `admin/page.tsx:368-372`, `globals.css:40`.
- Gợi ý: đổi `repeat(4,1fr)` → `repeat(5,1fr)` (hoặc auto-fit).
- Nguồn: [A5 #1].

**H-7. Roadtrip stop-editor vỡ cột khi bật "bao gồm chỗ ở".**
- Mô tả: `.stop-input{grid-template-columns:34px repeat(4,minmax(100px,1fr))}` (5 cột, globals.css:31) nhưng khi `withInventory` mỗi hàng có tới 8 phần tử (span, name, lat, lng, IATA, arrival, departure, ×) — 3 phần tử dư rơi vào cột implicit auto-width, lệch cột, nguy cơ tràn ngang (roadtrip/page.tsx:56).
- File:line: `roadtrip/page.tsx:56`, `globals.css:31`.
- Gợi ý: khi withInventory đổi grid sang `34px repeat(7,minmax(100px,1fr))` (8 cột) hoặc 2 hàng có cấu trúc rõ.
- Nguồn: [A5 #2].

**H-8. Nút "Huy" trong admin không có class — render theo button mặc định trình duyệt.**
- Mô tả: `<button type="button" disabled=...>Huy</button>` (admin/page.tsx:580) không có class → xung khắc hoàn toàn với `.secondary`/`.danger` xung quanh.
- File:line: `admin/page.tsx:580`.
- Gợi ý: thêm class `danger` hoặc `secondary`.
- Nguồn: [A5 #3].

**H-9. PlanView đối xử mọi message như "thành công" — lỗi không có màu đỏ, không role=alert.**
- Mô tả: `PlanView.tsx:122` render `message` và `busy` đều bằng `.status` (màu accent) + `role="status"`, trong khi các key **lỗi** (`actionFailed`, `refineFailed`, `versionsFailed`, `commentsFailed`, `regenerateFailed`, `offlineSaveFailed`, `copyFailed` — gán tại PlanView.tsx:90,100,101,106,108-113) phải dùng `.error` + `role="alert"`. Ba trang khác (Planner.tsx:224-231, explore:65, settings:37) làm đúng.
- Ảnh hưởng: "Đổi điểm thất bại", "Lỗi bình luận" trông y hệt "Đã sao chép liên kết" trên màn hình quan trọng nhất.
- File:line: `PlanView.tsx:122`, `globals.css:10`.
- Gợi ý: thêm cờ `error` cho `UiMessage`, render `.error` + `role="alert"`.
- Nguồn: [A4 H-1], [A3 N4].

**H-10. RTL chỉ "gắn" ở runtime, không có một selector `[dir=rtl]` nào trong CSS — FOUC + layout sai hướng.**
- Mô tả: `LocaleProvider.tsx:101` set `document.documentElement.dir` trong `useEffect` (client-only); `layout.tsx:9` hardcode `<html lang="vi">`. Grep xác nhận **0 selector `[dir]` trong globals.css**. Hardcode hướng LTR: `text-align:left` login-card (globals.css:34), `margin-right:12px` inline-check (:28), `margin-left:8px` nav-admin (:4), `margin-left:auto` roadtrip primary (:31), `footer-col a:hover{transform:translateX(2px)}` (:37).
- Ảnh hưởng: trang ar/he (trong 19 locale hỗ trợ) tải FOUC LTR→RTL và các margin/transform ngược hướng.
- File:line: `LocaleProvider.tsx:101`, `layout.tsx:9`, `globals.css:28,31,34,37`.
- Gợi ý: set `dir` sớm hơn (SSR hoặc useLayoutEffect kèm hydrate-sync), chuyển sang logical properties.
- Nguồn: [A4 H-4].

**H-11. Mobile workspace: chat bị đẩy xuống cuối trang — phải cuộn dài để tinh chỉnh.**
- Mô tả: `.workspace>.chat-panel{order:3}` (globals.css:25, media 760) đặt chat sau map (order:2); `chat-panel min-height:430px`. Ô nhập yêu cầu — trung tâm "hội thoại" — nằm sát footer.
- File:line: `globals.css:25`.
- Gợi ý: order `itinerary → chat → map`, hoặc ghim chat input `position:sticky`.
- Nguồn: [A2 M3].

**H-12. Không có spacing scale — nhịp điệu margin/padding/gap rời rạc.**
- Mô tả: file dùng gần như mọi số nguyên 1–72px (kể cả 7, 9, 11, 13, 15, 17, 18, 22, 26, 28); input padding 4 biến thể (10/11/12/14px), button padding 5 biến thể (6/8/9/11/13px). Không có token spacing nào — 30+ biến màu/radius/shadow nhưng 0 biến khoảng cách.
- Ảnh hưởng: các form/panel cùng một trang không "đồng nhịp"; đây là thứ mắt cảm nhận đầu tiên.
- File:line: `globals.css` toàn file (đặc biệt :1, :19, :22, :25, :28, :40).
- Gợi ý: định nghĩa scale 4/8/12/16/24/32/48/64, thay các giá trị lẻ bằng giá trị scale gần nhất.
- Nguồn: [A2 H3].

**H-13. "Page title" không nhất quán — 6 cỡ khác nhau cho cùng một cấp.**
- Mô tả: explore/roadtrip `clamp(42px,5.5vw,72px)` (:28,:31), admin 66px (:40), history dùng generic 62px (:10), login 52px (:34), settings 54px (:34), trip-header 52px (:25). Settings (trang phụ) lại to hơn login (cũng trang phụ) → nhiễu.
- File:line: `globals.css:10,25,28,31,34,40`.
- Gợi ý: 2 bậc duy nhất — bậc chính (explore/roadtrip) 72px, bậc phụ (settings/login) 52px.
- Nguồn: [A2 H4], [A5 #6], [A1 M5].

**H-14. "Drawers" không phải drawer — section chèn thẳng gây layout shift và mất ngữ cảnh.**
- Mô tả: `version-drawer`, `comment-drawer`, `feedback-card` là `.card` `max-width:760px` chèn *trên* workspace (PlanView.tsx:123-125, globals.css:25) — không overlay, không animation, không affordance đóng; đẩy toàn bộ nội dung xuống khi bật, và đặt xa đối tượng liên quan (version list cách xa itinerary).
- File:line: `PlanView.tsx:123-125`, `globals.css:25`.
- Gợi ý: ít nhất fade + slide nhẹ; lý tưởng là drawer/modal thật có overlay.
- Nguồn: [A3 H3].

**H-15. Trip-header 7–9 nút nhồi chung một hàng.**
- Mô tả: `trip-actions` chứa share, PDF, calendar, JSON, comments, feedback (có điều kiện), versions, undo (khi ver>1), regenerate (PlanView.tsx:120) — tối đa 9 nút `.secondary`. Ở ~1150px nội dung, hàng nút cao 2–3 dòng, cạnh tranh với h1 52px; nút undo dễ bị lẫn.
- File:line: `PlanView.tsx:120`, `globals.css:25`.
- Gợi ý: nhóm nút phụ (undo, versions, regenerate) vào dropdown/toolbar; giữ header ≤4 action.
- Nguồn: [A2 M5], [A5 #7].

### Medium (không nhất quán / lạc tông / thiếu polish, không vỡ)

**M-1. `--brand` trùng y hệt `--ink` — "màu thương hiệu" không tồn tại.**
- `--brand:#2a182e == --ink:#2a182e`, `--brand-hover:#352438 == --ink-2` (globals.css:1). Mọi action chính đều đen-tím gần đen; bản sắc không có tông riêng, CTA đen không "ấm" với concept du lịch.
- File:line: `globals.css:1`. Gợi ý: cho `--brand` tông tím-plum ấm rõ (~`#3d1a4f`), kéo `--ink` về đen pha tím nhạt hơn.
- Nguồn: [A1 M1].

**M-2. `--surface-2` vô dụng ở light — input mất tầng "lõm".**
- Light `--surface-2:#ffffff = --surface` (globals.css:1); input chỉ phân biệt bằng border. Dark làm đúng (`#2a182e` trên `#1f1222`).
- Gợi ý: light `--surface-2` về `#f2f0f4`-ish.
- Nguồn: [A1 M2].

**M-3. `::selection` dark mode đồng màu — 1:1.**
- `::selection{background:var(--lavender);color:var(--ink-3)}` (globals.css:1); dark cả hai = `#cdb3ff`. Không có override trong dark. Bôi đen để copy trong dark thấy không được văn bản.
- Gợi ý: dark override `color:var(--surface)`.
- Nguồn: [A1 M3], [A3 N3].

**M-4. Bảng màu bản đồ nằm ngoài hệ thống — "đốm màu" dễ thấy nhất.**
- `MapView.tsx:37,49` và `RoadTripMap.tsx:15,16` hardcode teal `#0f766e` (route) + cam `#e4572e` (marker chọn). Không có token, dark mode không đổi. Cam đất nung thực ra rất "Hà Nội ấm" nhưng vì không được quản lý thành bản sắc nên đọc ra là ngoại lệ.
- Gợi ý: thêm token `--map-route`/`--map-selected` + variant dark; hoặc nâng cam lên màu thứ ba của brand.
- Nguồn: [A1 M6], [A4 M-6], [A5 #4].

**M-5. Lavender bị lạm dụng — nhận diện "một-tông tím", không có "nắng Hà Nội".**
- Đếm token: họ `--lavender*` 65 + `--accent*` 32 = 97 lần vs họ trạng thái (green/sun/danger/info) ~28 lần (globals.css). `--sun` chỉ 6 lần, toàn trong admin pills; ngoài chấm xanh social-proof không có một giọt nắng nào ở landing. Khi tất cả đều accent thì không ai là accent.
- File:line: `globals.css:13,16,19,22,25,37,40`.
- Gợi ý: cắt lavender-50/-soft ở vùng thứ cấp (thumb, facts, price chips), đưa sun/cam vào 1–2 điểm nhấn landing.
- Nguồn: [A1 M8].

**M-6. Footer dark mất "chữ ký" — hòa vào nền trang.**
- Dark `.site-footer{background:var(--surface-2)}` = `#2a182e` trên paper `#141014` → footer gần như dính trang; light thì tương phản mạnh và là mốc thị giác cuối trang.
- File:line: `globals.css:37`, `:43`. Gợi ý: dark nền `#0e0a10` hoặc border-top rõ.
- Nguồn: [A1 M7].

**M-7. Ba ngôn ngữ focus khác nhau giữa các input.**
- Planner: `outline:none` + border accent + ring 4px lavender-soft (globals.css:19); chat: cùng ring nhưng radius-full (:22); inventory/comment/admin/stop/settings: chỉ outline toàn cục (:28,25,40,31,34). Một form (planner) tự chứa 2 kiểu.
- Gợi ý: class `.field` dùng chung với ring chuẩn.
- Nguồn: [A3 M1], [A4 L-1 (ring dark quá tối)].

**M-8. Hai ngôn ngữ tab khác nhau.**
- `day-tabs` (globals.css:25): fill mềm lavender-50, không viền, hover đổi nền. `inventory-tabs` (:28): nền surface, viền line-2, hover chỉ đổi viền. Cùng "tab" nhưng hai thương hiệu thị giác.
- Gợi ý: chọn một ngôn ngữ cho cả hai.
- Nguồn: [A3 M3].

**M-9. Hover "nâng lên" 3 biên độ — độ sâu không có logic.**
- Featured-card −4px (:16), timeline a.card −2px (:34), button/slot −1px (:7,:25). Timeline card (dày thông tin) nặng hơn slot.
- Gợi ý: 2 cấp — row/slot −1px, card lớn −4px.
- Nguồn: [A3 M4], [A4 #2].

**M-10. Hai "bộ máy" motion nút: scale vs translateY.**
- `.icon-action` dùng scale 1.06/.94 (globals.css:7); mọi nút khác dùng translateY(−1px); chat send active scale .94 (:22).
- Gợi ý: thống nhất — giữ scale cho icon-only.
- Nguồn: [A3 M5].

**M-11. Ladder bán kính áp lộn xộn.**
- Card lg24 (:10), planner xl32 (:19), workspace card ép lg24 (:25), faq-item md16 (:16), slot md16 (:25), comment sm12 (:25) — các "hộp nội dung" cùng cấp có 3 mức bo.
- Gợi ý: surface chính lg24, surface phụ md16, chip/full — thành quy tắc.
- Nguồn: [A3 M6].

**M-12. Icon nút dùng ký tự Unicode (↑ ↻ ×) thay vì SVG.**
- `Planner.tsx:199`, `PlanView.tsx:126-127`, `roadtrip/page.tsx:56`. Render lệch baseline theo OS, nét kém sắc so với SVG stroke 1.5–2px; ↑ 18px trong nút 46px trông "thô".
- Gợi ý: SVG 18–20px, giữ aria-label.- Nguồn: [A3 M7].

**M-13. Busy state chỉ là một dòng text — không spinner, không skeleton, không progress.**
- `PlanView.tsx:122` busy = `.status` "Đang xử lý…". `creatingPlan` key tồn tại (LocaleProvider:75) nhưng không dùng. MapLoading = ô trắng + chữ (PlanView.tsx:13); explore/roadtrip `setResult(null)` → kết quả biến mất rồi bung đột ngột (explore:52-53, roadtrip:52).
- Gợi ý: tận dụng `typingPulse`/`shimmer` CSS đã viết (xem M-14), bọc skeleton cho grid/timeline/map.
- Nguồn: [A4 M-1], [A4 M-3].

**M-14. CSS animation "dead code": `typingPulse` và `shimmer` chưa bao giờ render.**
- `.bubble.typing` + `@keyframes typingPulse` (globals.css:22) — không component nào render; `.slot-photo.loading::after` + shimmer (:25) — `slotPhoto()` không bao giờ kèm `.loading` (PlanView.tsx:117). Cả hai đã thiết kế xong nhưng bỏ phí — tận dụng gần như miễn phí.
- Nguồn: [A3 N2], [A4 M-2]. (A5 khen slot có shimmer "xử lý cẩn thận" — thực tế là dead code; xem Mâu thuẫn.)

**M-15. Status message không auto-dismiss, không phân loại, gây layout-shift.**
- Message tồn tại vô thời hạn (start() mới xoá, PlanView.tsx:87); xuất hiện/ẩn làm đẩy khối workspace (`margin-top:14px`, globals.css:10) — không vùng dành sẵn, không toast, không fade.
- Gợi ý: toast auto-dismiss 3–5s hoặc dành sẵn dòng status.
- Nguồn: [A4 M-4].

**M-16. Day-tabs thiếu semantics & phản hồi chuyển đổi.**
- `PlanView.tsx:127` tab chỉ có class active, không `role="tablist/tab"`/`aria-selected` (explore:60 làm đúng); đổi ngày slots thay đổi đột ngột, focus không được quản lý.
- Gợi ý: aria-selected + arrow-nav + transition nhẹ 150ms.
- Nguồn: [A4 M-5].

**M-17. Tương tác không đồng bộ khi busy.**
- Khi busy, nút disabled nhưng `.slot-select` (phủ toàn card, PlanView.tsx:127) và marker map (`onSelect`, MapView.tsx:39) vẫn nhận click → chọn điểm trong lúc refine đang chạy rồi bị override bởi plan mới.
- Gợi ý: disable tương tác khi busy hoặc giữ selectedId của user.
- Nguồn: [A4 M-8].

**M-18. RTL typography: `letter-spacing` âm phá chữ Ả Rập/Hebrew.**
- `h1,h2,h3{letter-spacing:-.02em}` (:1), hero `-.035em` (:13,28,31). Chữ nối glyph bị dính/rách khi spacing âm; không có nhánh `[dir=rtl]` reset.
- Gợi ý: `[dir=rtl] h1,h2,h3{letter-spacing:0}`.- Nguồn: [A4 M-7].

**M-19. Disabled opacity không nhất quán cùng loại nút.**
- `.chat-box button:disabled{opacity:.5}` (:22) vs `.planner .chat-box button:disabled{opacity:.55}` (:19).
- Gợi ý: `.5` toàn cục.
- Nguồn: [A3 M8], [A4 L-7].

**M-20. Input "Số người" đặt dưới chat-box phá vỡ khối đối thoại + label không style.**
- `Planner.tsx:207-218`: input number radius-sm full-width thả dưới nút ↑ tròn; label không có rule (các label khác font-weight 700/800).
- Gợi ý: gộp vào hàng riêng có label chuẩn hoặc thành chip; thêm `.planner label`.
- Nguồn: [A3 M2].

**M-21. Badge số thứ tự không đồng nhất.**
- `step::before` 40px/radius 12 (:16), `stop-index` 28px/radius 50% (:25), `stop-input>span` 30px/50% (:31).
- Gợi ý: thống nhất badge tròn 28px cho itinerary/roadtrip.
- Nguồn: [A3 M9].

**M-22. Giờ kết thúc trong slot không phân tầng.**
- `slot.bat_dau` và `slot.ket_thuc` cùng trong `<strong>` 14px (PlanView.tsx:127, globals.css:25) → khó phân biệt lúc nào bắt đầu/kết thúc.
- Gợi ý: span kết thúc → muted + weight 500.
- Nguồn: [A3 M10].

**M-23. Admin chữ Việt không dấu hard-code, không i18n.**
- "Quan ly he thong", "Theo doi du lieu..." (:357-358), "Nhan su phu trach" (:565), "Ghi chu noi bo" (:573), "Dang tai..." (:362), "Huy" (:580), "Khong co yeu cau..." (:583) — lệch hoàn toàn với phần còn lại dùng `t()` có dấu.
- File:line: `admin/page.tsx:357,358,362,565,573,583,580,...`.
- Gợi ý: đưa vào i18n (ít nhất dấu tiếng Việt chuẩn).
- Nguồn: [A5 #9]. (Xếp Medium thay vì High vì chỉ ảnh hưởng trang admin nội bộ.)

**M-24. Map panel không phải `.card` — 3 cột workspace không đồng bộ surface.**
- `chat-panel`/`itinerary-panel` có class `card` (PlanView.tsx:126-127), `map-panel` không (PlanView.tsx:128, globals.css:25) → cột bản đồ "trần", đáy 3 panel lệch.
- Gợi ý: thêm class card cho map-panel với padding riêng.
- Nguồn: [A2 M4].

**M-25. Trục dọc đầu trang không nhất quán.**
- Sau nav: explore/roadtrip/history/admin bắt đầu 0, login margin 64px, settings 48px, legal 24px/48px, workspace 0 (globals.css:34,40,25...). Vị trí tiêu đề nhảy khi đổi trang.
- Gợi ý: một giá trị duy nhất (vd 40px).
- Nguồn: [A2 M6].

**M-26. Hero mobile: h1 floor 48px quá lớn; desktop cân bằng theo chiều cao kém.**
- `clamp(48px,6.5vw,88px)` (:13) giữ 48px xuống tới 0px → trên 375px tiêu đề 2 dòng ~96px áp đảo. Desktop `.hero{min-height:calc(100vh-120px)}` + `.hero-left{justify-content:center}` tạo khoảng trống rơi không đều khi cột text ngắn hơn planner.
- Gợi ý: mobile thêm mốc ~480px hạ 34–38px; desktop bỏ min-height cứng hoặc align-items:start.
- Nguồn: [A2 M1/M2].

### Low (cosmetic / hiển thị không đáng kể)

- **L-1. Shimmer loading trắng trong dark** — `rgba(255,255,255,.5)` (globals.css:25) chói trên nền tối. Gợi ý: dark override `.08`. [A1 L1]
- **L-2. Thanh gradient đỉnh planner phẳng trong dark** — 3 màu đều lavender sáng (globals.css:19,43), không có override `.planner::before`. Gợi ý: dark gradient `#926cd6→#6a4bb0→#4b2c82`. [A1 L2]
- **L-3. Thumbnail featured dùng emoji ☕🍜🏛️** — 3 card giống nhau trên cùng gradient lavender (page.tsx:6-9, globals.css:16); emoji render khác theo OS. Gợi ý: 3 tông nền theo concept hoặc ảnh thật. [A1 L3], [A5 #11]
- **L-4. `.danger:hover #a03a33` lệch hệ với `--danger:#bb4d45`** — hover "đổi màu" thay vì "đậm lên" (globals.css:7). Gợi ý: `--danger-hover` cùng không gian màu. [A1 L4]
- **L-5. Inset ngang workspace lệch 20px so với mọi trang** — `workspace-page{padding:0 20px}` (globals.css:25) + shell 24px = 44px vs 24px. [A2 L1]
- **L-6. `.primary{width:100%}` làm mặc định toàn cục** — mỗi context phải override (globals.css:7; roadtrip:31, cta-banner:16, inventory-search:28); rủi ro nút dãn bất ngờ ở context mới. Gợi ý: modifier `.primary--block`. [A2 L2], [A3 L1]
- **L-7. `.timeline` hai ngữ nghĩa, đệm chồng** — history + slot itinerary (globals.css:34,25) + `margin-bottom:10px` slot chồng gap 14px. [A2 L3]
- **L-8. `faq-item` không có hover** — summary clickable nhưng chỉ đổi con trỏ (globals.css:16, page.tsx:89). [A3 L3]
- **L-9. Nút `.secondary` quá lớn trong drawer rows** — version-row `padding:11px 0` chen pill đầy đủ (globals.css:25, PlanView.tsx:123-124). [A3 L4]
- **L-10. `retry-action` là biến thể "chui"** — `padding:8px 16px` thu nhỏ secondary (globals.css:10, Planner.tsx:227). Gợi ý: class `btn-sm`. [A3 L2]
- **L-11. `smooth-scroll` không nằm trong reduced-motion** — `html{scroll-behavior:smooth}` (:1) không bị block reduce tắt. [A4 L-2/L-3]
- **L-12. aria-label hardcode ngôn ngữ** — `Navigation.tsx:29` "Main" (en), `MapView.tsx:58` "Bản đồ lịch trình" (vi). [A4 L-4]
- **L-13. Footer/legal hardcode nội dung** — `Footer.tsx:26,30,31` "Support"/"Điều khoản"/"Bảo mật"; layout metadata tiếng Việt cố định. [A4 L-5]
- **L-14. Unused translation keys phản ánh tính năng thiếu** — `creatingPlan` (LocaleProvider.tsx:75), `undoSuccess` (i18n-core.ts:9) chưa dùng → nút Undo sau restore chưa có. [A4 L-6]
- **L-15. Chip "places" trong trip-facts chỉ đếm slot ngày đang xem** — `slots = plan.ngay[activeDay].khoang_gio` (PlanView.tsx:121) nên số nhảy khi đổi tab ngày. [A5 #12]
- **L-16. Offer-card thiếu điểm nhấn thị giác** — card trắng + chữ xám, không khí "bảng giá" thay vì "khám phá" (explore:66, globals.css:28). [A5 #13]
- **L-17. Hero h1 `line-height:.98` ở 88px** có thể cắt đỉnh dấu tiếng Việt (globals.css:13). Nếu cắt thì nâng 1.0–1.05. [A1 N3], [A5 #10]

### Note (dead code / chủ ý cần làm rõ)

- **N-1. Font thương hiệu không bao giờ được tải.** `--font:"Inter","Fig Grotesk",system-ui` (globals.css:1) nhưng không có `next/font`, `@font-face`, fontsource hay Google Fonts (xác minh: không match nào; package.json không có font dep). Trình duyệt rơi về `system-ui` — weight 800/900, letter-spacing áp lên font khác nhau theo OS. **Lý do lớn nhất khiến "bản sắc" chưa hoàn chỉnh; sửa được trong một buổi.** [A1 N1]
- **N-2. `--ink-3` mang hai vai trò xung đột** (globals.css:1) — "mực chữ" lẫn "màu brand/gradient"; dark đảo thành lavender kéo theo vụ nổ contrast ở ::selection và icon-action hover (gốc của M-3, H-2). Gợi ý: tách `--brand-strong`. [A1 N2]
- **N-3. Mọi text trên màu nên dùng token, không `#fff` cứng** — quy ước thiếu này là gốc của BL-1, BL-2, H-1, M-3. [A1 N5]
- **N-4. `--info` hầu như chết** — định nghĩa (:1) chỉ ~4 lần trong file. [A1 N4]
- **N-5. Breakpoint các module không đồng bộ** — 600/760/800/900/1100px rải theo module; tablet 768px: roadtrip đã 1 cột trong khi explore còn 2 cột. Gợi ý: chuẩn hoá 1200/900/600 (+1100 workspace). [A2 N1]
- **N-6. FAQ cột hẹp 720px giữa 2 section full-width** — co 1152→720→1152px hơi gấp (globals.css:16). [A2 N2]
- **N-7. Không xử lý viewport rất rộng** — container 1200px cố định, màn 1440–2560px chỉ có dải nền trống. [A2 N3]
- **N-8. CSS chết:** `.planner textarea`/`.planner select` (globals.css:19), `.bubble.typing` (không render), `.trip-actions .icon-action` (:25), `.nav{border-radius:0 0 0 0}` (:4). [A3 N1], [A5 #14]
- **N-9. `.status`/`.error` thiếu icon** ✓/⚠ (globals.css:10). [A3 N4]
- **N-10. `inventory-search` input không có hover border** (globals.css:28). [A3 N5]
- **N-11. Bảng admin grid số cột cứng** — ép `font-size:13px` + `nowrap`, dễ tràn (globals.css:40). [A3 N6]
- **N-12. Admin pills KHÔNG lạc palette** — `--green/sun/danger-soft` đều là token có dark override (globals.css:1,43); cái làm admin lạc giọng là 3 lỗi H-5/H-6/H-8 + chữ không dấu. [A5 xác nhận], [A3 strength #4]
- **N-13. "100%" social-proof là khẳng định chưa có nguồn hiển thị** (page.tsx:37-42). [A5 #16]
- **N-14. CTA banner lặp lại `heroLead`** — copy cuối trang yếu (page.tsx:102). [A5 #17]
- **N-15. Featured-card `href="/"`** — click chuột giữa/tab mới về trang chủ thay vì focus planner (page.tsx:54). [A5 #15]

---

## Mâu thuẫn giữa các lane đã xử lý

Không có mâu thuẫn lớn nào làm đảo ngược kết luận, nhưng có 5 điểm chênh cần ghi nhận khi sửa:

1. **Dark override `.icon-action` tồn tại hay không?** [A1 H2] nói "khối dark không override"; thực tế dark block **có** `.icon-action:hover:not(:disabled)` (globals.css:43) — nhưng vẫn gán `lavender`/`ink-3` (cùng `#cdb3ff`) nên kết quả 1:1. Kết luận: override vô hiệu về màu — vẫn là lỗi, cách sửa không đổi. Nguồn gốc đúng nhất là [A1 N2] (vai trò kép của `--ink-3`).
2. **CTA banner "đẹp" hay "vỡ"?** [A5] chấm CTA "rất đẹp"; [A1 B2] coi là Blocker. Cả hai đúng ở chế độ họ đánh giá: light đẹp thật, dark vỡ thật (gradient + nút đều mất). Xếp Blocker vì dark là chế độ được quảng bá.
3. **Slot-photo có shimmer "xử lý cẩn thận"?** [A5] khen shimmer loading; [A4 M-2] và [A3 N2] xác nhận `.slot-photo.loading` **chưa bao giờ được render** (dead code). [A5] đánh giá theo CSS tồn tại, không phải render thực tế — [A4] đúng. Slot vẫn tốt nhờ `onError` ẩn ảnh hỏng (PlanView.tsx:117).
4. **Phân loại admin chữ không dấu (High vs Medium):** [A5] xếp High; synthesis hạ xuống Medium vì chỉ ảnh hưởng trang admin nội bộ (đúng là lỗi i18n, không phải vỡ bố cục người dùng). Tương tự "trip-actions quá tải" được [A2] và [A5] cùng đồng thuận High — giữ nguyên.
5. **Điểm số:** 5.5/7/7/6.5/7.5 — trung bình 6.7. Synthesis chốt **6.5** thay vì làm tròn 7, vì hai Blocker nằm ở đúng thao tác chính + 5 lỗi bố cục thật (H-5→H-8, H-7) — lỗi nhìn thấy nhiều hơn con số trung bình gợi ý.

---

## Khoảng trống các agent bỏ sót

Cả 5 lane đều tập trung vào bên trong màn hình; không ai quét các "lớp vỏ" trình duyệt/SEO/meta. Bị bỏ sót toàn bộ:

1. **Không có favicon/icon tùy chỉnh.** `app/` không có `icon.*`/`favicon.ico`, `public/` chỉ có `og.png` + `sw.js`. Tab trình duyệt hiện icon mặc định.
2. **Root layout không có OpenGraph/Twitter metadata.** `og.png` chỉ được dùng trong `generateMetadata` của `plan/[token]/page.tsx:6`; `layout.tsx:8` chỉ có `title`/`description`. Landing — trang được share nhiều nhất — share lên mạng xã hội chỉ hiện chữ.
3. **Không có 404 / not-found page.** Không có `app/not-found.tsx` hay `error.tsx` — URL hỏng hiện trang mặc định của Next, mất thương hiệu.
4. **Không có `@media print`.** Nút "Download PDF" có nhưng Ctrl+P itinerary output không tối ưu (nav sticky, màu nền, drawer).
5. **Không có loading.tsx toàn trang.** `plan/[token]` chỉ có skeleton text từ `dynamic(MapView)` (PlanView.tsx:13); không có `app/loading.tsx`/Suspense cấp route — chuyển trang plan là màn trắng chờ dữ liệu.
6. **Không có theme toggle.** Chỉ `prefers-color-scheme` (globals.css:43); không nút chuyển thủ công, không lưu lựa chọn — dark mode đẹp nhưng người dùng không chọn được.
7. **Không có `theme-color` meta** — màu thanh browser mobile mặc định, không khớp palette.
8. **Không có view-transition / route transition** — đổi trang "nhảy thẳng".
9. **Scroll-margin dưới nav sticky** — nội dung bị nav che khi focus phần tử sau cuộn.
10. **Không có entrance/reveal animation cho landing** — page tĩnh khi load (đáng Tier 2).

---

## Khuyến nghị ưu tiên Tier 0/1/2/3

**Tier 0 — Phải sửa (bug thị giác, action chính hỏng, lỗi bố cục thật):**
- BL-1, BL-2: dark `.chat-box button` và `.cta-banner` (thêm override `color`/gradient dark).
- H-1, H-2, M-3: dark `.danger`, `.icon-action:hover`, `::selection` → `--brand-contrast`/tối.
- H-5, H-6, H-8: admin — thêm class `card`, đổi grid 4→5 cột, class cho nút "Huy".
- H-7: roadtrip withInventory grid 8 cột.
- H-4: dỡ `<main>` lồng để workspace 1500px có hiệu lực.
- H-9: PlanView render lỗi bằng `.error` + `role="alert"`.

**Tier 1 — Nên sửa trước khi mở rộng (nền tảng bản sắc & a11y):**
- N-1: tải font Inter/Fig Grotesk thật (next/font) — thay đổi bản sắc lớn nhất với chi phí 1 buổi.
- H-10 + M-18: RTL — set dir sớm, logical properties, reset letter-spacing; app đang quảng bá 19 locale.
- H-3: contrast light `--accent`/`--muted`/`--muted-2` lên AA.
- M-1: tách `--brand` khỏi `--ink` — cho thương hiệu một màu thật.
- H-12, H-13: spacing scale + thống nhất page-title 2 bậc.- H-14, H-15: drawer thật (hoặc không shift layout), thu gọn trip-header.
- H-11: đưa chat về vị trí dùng được trên mobile.
- M-13, M-14: hiện typing-bubble + shimmer (dead code) cho busy/loading.
- M-7: thống nhất focus ring form; H-16 (a11y) day-tabs semantics.

**Tier 2 — Polish (tinh chỉnh cảm nhận):**
- M-4: đưa màu bản đồ (teal/cam) vào token + variant dark; cân nhắc cam thành màu thứ ba.
- M-5: cắt lavender ở vùng thứ cấp, thả "nắng Hà Nội" vào landing.
- M-2, M-6: `--surface-2` light phân biệt; footer dark tương phản hơn.
- M-8→M-11, M-19, M-21, M-22: thống nhất ngôn ngữ tab / lift / motion / radius / disabled / badge / giờ slot.
- M-12: thay ↑↻× bằng SVG.
- M-15, M-16: toast auto-dismiss, transition day-tab.
- M-24, M-25, M-26, L-5, L-6: đồng bộ surface panel, trục dọc trang, hero mobile/desktop, inset, primary.
- L-3, L-16: thumbnail featured 3 tông concept + offer-card điểm nhấn.
- Khoảng trống: favicon, `theme-color`, landing og-image, loading.tsx route.

**Tier 3 — Ý tưởng tương lai:**
- 404 page thiết kế riêng (cơ hội kể chuyện thương hiệu).
- Print styles cho itinerary (PDF client-side tốt hơn).
- Theme toggle (light/dark/system) lưu lựa chọn.
- View-transition khi đổi trang.
- Entrance/reveal animation landing (đã có reduced-motion guard).
- N-4: tận dụng `--info`; M-17: đồng bộ busy với map/slot interaction.

---

## Kết luận

Nền móng (token, dark inversion, motion, focus, micro-detail) xứng đáng 8/10 và là thứ rất khó tạo ra từ đầu — phần lớn site làm không tới. Nhưng khoảng cách giữa nền móng và bề mặt người dùng đang bị lấp bởi 2 Blocker dark mode, 5+ lỗi bố cục thật, `<main>` lồng nuốt thiết kế, font không tải, và một tầng phản hồi trạng thái chỉ là chữ. Đây không phải vấn đề thiếu kỹ năng mà là vấn đề "chưa điều phối": mỗi phần làm tốt riêng, ghép lại chưa thành một hệ. Ưu tiên Tier 0 có thể xử lý trong một phiên; Tier 1 đưa sản phẩm từ "được chăm chút nhưng không đều" sang "có bản sắc thật". Không có vấn đề nào yêu cầu thiết kế lại từ đầu — toàn bộ là tinh chỉnh trên nền vững.

---

**Confidence: 8/10**

**Ground-truth tally: 31/38 kết luận quan trọng dựa trên code đọc trực tiếp:**
- (a) Đọc nguyên văn `:root` và khối dark (`globals.css:1`, `:43`): `--brand:#2a182e == --ink`, `--brand-hover == --ink-2`, `--surface-2 == --surface` (light), `--ink-3 == --lavender` (dark).
- (b) Grep khối dark: KHÔNG có override `.chat-box button`, `.cta-banner`, `.danger`, `::selection`, `shimmer`, `.planner::before`; CÓ `.icon-action:hover` nhưng vẫn gán `lavender`/`ink-3` (1:1).
- (c) `<main>` lồng: `layout.tsx:9` + 9/9 trang; `.workspace-page{max-width:1500px}` tại globals.css:25.
- (d) Admin: 5 card trong `.admin-strip` `repeat(4,1fr)` (admin/page.tsx:368-372, globals.css:40); `offer-card` thiếu `card` (:569) so với explore:66, support:62; nút "Huy" trần (:580); chữ không dấu (:357,358,565,573,583).
- (e) Roadtrip: `.stop-input` 5 cột (globals.css:31) vs 8 phần tử khi withInventory (roadtrip/page.tsx:56).
- (f) Map: `#0f766e`/`#e4572e` tại MapView.tsx:37,49 và RoadTripMap.tsx:15,16.
- (g) PlanView: message/busy đều `.status` + `role="status"` (:122); 9 nút trip-header (:120); slotPhoto không `.loading` (:117); day-tabs không aria-selected (:127); `slots` đếm theo activeDay (:121/84).
- (h) RTL: dir set trong useEffect (LocaleProvider.tsx:101); `<html lang="vi">` (layout.tsx:9); 0 selector `[dir` trong globals.css.
- (i) Font/favicon/meta: không match `next/font|@font-face|fonts.googleapis` trong app; package.json không có "font"; `app/` không có icon/favicon/not-found/loading/error; `public/` chỉ `og.png` + `sw.js`; `layout.tsx:8` không openGraph, `plan/[token]/page.tsx:6` có og.png.
- (j) Workspace grid `minmax(260px,.65fr) minmax(400px,1.2fr) minmax(380px,1.05fr)` (globals.css:25), mobile `order:3` chat (media 760), map-panel không class card (PlanView.tsx:128).
- (k) `#fff` hard-code tại globals.css:7 (danger), :16 (cta-banner), :22 (chat-box button); hover `#a03a33` tại :7.
- (l) `prefers-reduced-motion` không tắt `scroll-behavior:smooth` (:1); disabled opacity .5 vs .55 (:22,:19).
- (m) i18n-core.ts:1 khai báo 19 locale (gồm ar, he); unused keys `creatingPlan` (LocaleProvider:75), `undoSuccess` (i18n-core.ts:9).
- (n) Emoji ☕🍜🏛️ tại page.tsx:6-9; hero `line-height:.98` (globals.css:13).
- 7/38 còn lại là nhận định thẩm mỹ chủ quan: trọng số điểm 6.5, mức "lạm dụng tím" (dựa trên đếm token 97 vs 28), mức FOUC RTL ngoài runtime, hiệu ứng letter-spacing trên chữ Ả Rập, emoji render theo OS, cắt dấu tiếng Việt ở hero, và xếp hạng Tier 0/1/2/3.
