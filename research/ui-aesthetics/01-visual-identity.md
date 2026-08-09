# 01 — Bản sắc thị giác & Hệ màu — "Mình Đi Đâu Thế"

**Phạm vi:** nghiên cứu thuần đọc, không sửa code. Tài liệu chính: `frontend/app/globals.css` (43 dòng, mỗi dòng là cả một module), `page.tsx`, `components/Planner.tsx`, `PlanView.tsx`, `Navigation.tsx`, `Footer.tsx`, `app/layout.tsx`, `MapView.tsx`, `RoadTripMap.tsx`. Trọng tâm: bản sắc thương hiệu và hệ màu. Layout, cấu trúc component, UX là phạm vi của các agent khác.

---

## Tóm tắt điều hành

Hệ thống màu là một **token map gọn, đặt tên chuẩn và dark mode được đảo ngược một cách có chủ ý**, nhưng đang bị kéo căng bởi 4 vấn đề cốt lõi: (1) **`--brand` trùng lặp hoàn toàn với `--ink`** (`#2a182e`), khiến "màu thương hiệu" không có cá tính riêng và mọi action chính đều đen-nhạt thay vì tím ấm; (2) **dark mode để sót màu cứng** (`#fff`, `#a03a33`) trong `.chat-box button`, `.danger`, `.cta-banner` — ở dark, chữ trắng trên nền lavender nhạt có contrast chỉ 1.83–2.04:1 (không đọc được); (3) **dòng lavender/ accent bị lạm dụng** — 97 lần dùng tổng cộng so với toàn bộ nhóm màu trạng thái (green/sun/danger/info) chỉ ~28 lần, khiến nhận diện đọc ra là "một-tông tím" thay vì "Hà Nội ấm áp"; (4) **typography mất bản sắc vì font không được tải** — stack khai báo `Inter`/`Fig Grotesk` nhưng không có `next/font`, `@font-face` hay fontsource nào, trình duyệt rơi về `system-ui`. Dark mode về mặt token tốt hơn light mode (contrast text đều pass), nhưng 4-5 điểm chết vì màu hard-code. Điểm thẩm mỹ tổng: 5.5/10 — nền tảng sạch, hệ token tốt, nhưng bản sắc "ấm áp" chưa được hiện thực bằng màu và dark mode còn lỗi nhìn thấy bằng mắt.

---

## Điểm mạnh

1. **Hệ token gọn và ngữ nghĩa rõ.** 26 biến màu chia đúng vai trò: nền (`--paper`, `--surface`, `--surface-2`), chữ (`--ink`, `--ink-2`, `--ink-3`, `--muted`, `--muted-2`), thương hiệu (`--brand`), nhấn (`--accent`, `--accent-2`, `--lavender`), trạng thái (`--green`, `--sun`, `--danger`, `--info`), đường kẻ (`--line`, `--line-2`), đổ bóng/radius/container/font/easing riêng. Việc tách shadow, radius, easing thành token giúp nhịp bo góc và độ nổi thống nhất toàn app — hiếm gặp ở mức chất lượng này (globals.css:1).
2. **Dark mode được thiết kế như một hệ thống đảo ngược chứ không phải "bôi đen".** Toàn bộ khối `@media(prefers-color-scheme:dark)` (globals.css:43) đảo cả 4 lớp: nền tối, chữ sáng, brand trở thành lavender sáng + `--brand-contrast` đen, và status color chuyển sang tông sáng trên nền soft tối. Cặp `--brand`/`--brand-contrast` dark = `#cdb3ff`/`#2a182e`, contrast 9.06:1 — chuẩn AA.
3. **Contrast dark mode thực sự tốt hơn light mode.** Đo được bằng công thức WCAG: `--muted:#a99fae` trên `--paper:#141014` = 7.41:1; `--accent:#ae86f7` trên paper = 6.78:1; `--muted-2` 5.74:1. Trong khi light mode `--muted` chỉ 4.11:1 và `--muted-2` 3.04:1.
4. **Mô-típ gradient là tài sản thương hiệu mạnh.** Gradient `ink-3 → accent → lavender` xuất hiện nhất quán ở logo `.brand::before` (globals.css:4), thanh đỉnh `.planner::before` (globals.css:19), và `.cta-banner` (globals.css:16). Cùng motif "logo chấm gradient + chữ 900" lặp lại ở footer `.footer-brand::before` (globals.css:37). Đây là dấu hiệu nhận diện có thể nhớ được.
5. **Hệ bo góc phối tầng hợp lý.** `--radius-xs..xl` (8→32px) cho surface, `--radius-full` 999px cho mọi yếu tố tương tác (nav link, button, chip, tab, pill, dot). Có phân tầng rõ: tương tác = tròn đầy, surface = 16–32px. Nhịp điệu đồng nhất.
6. **Màu trạng thái được tiết chế tốt.** Green/sun/danger chỉ được dùng ở nơi thực sự mang ý nghĩa: chấm xanh social-proof, admin pills trạng thái (`--green-soft`, `--sun-soft`, `--danger-soft` — globals.css:40). Không bị "phun màu" ra khắp nơi như các app admin thường mắc.
7. **Focus-visible, selection, reduced-motion được chăm.** `:focus-visible` có outline 3px tông accent-2 + offset (globals.css:1), `::selection` phối lavender/ink-3, và khối `prefers-reduced-motion` chặn mọi animation (globals.css:1). Đây là tín hiệu độ chín về thẩm mỹ + khả năng tiếp cận.

---

## Vấn đề theo mức

### Blocker

**B1. Nút gửi chat biến mất trong dark mode — `color:#fff` cứng trên nền brand sáng.**
- Mô tả: `.chat-box button{background:var(--brand);color:#fff}` (globals.css:22). Light: brand `#2a182e` + chữ trắng = 16.55:1, đẹp. Dark: brand đảo thành `#cdb3ff` (lavender sáng), nhưng `color:#fff` không được override trong khối dark (globals.css:43 chỉ override `.planner .chat-box input`, không override button). Mũi tên ↑ trắng trên nền lavender nhạt = **1.83:1**, mất hút. Đây là nút hành động chính của toàn bộ flow tạo kế hoạch (Planner.tsx:198, PlanView.tsx:126).
- Ảnh hưởng thẩm mỹ: thao tác chính của sản phẩm vô hình ở một nửa số người dùng (dark). Không chỉ về thẩm mỹ mà là vỡ nhận diện: nút "đen" trở thành "trắng trắng".
- File:line: `frontend/app/globals.css:22` (gốc), `frontend/app/globals.css:43` (thiếu override).
- Cách sửa: trong khối dark thêm `.chat-box button{color:var(--brand-contrast)}`, hoặc đổi gốc thành `color:var(--brand-contrast)` luôn (đã có sẵn token).

**B2. CTA banner vỡ toàn bộ trong dark mode.**
- Mô tả: `.cta-banner` = gradient `var(--ink-3),var(--accent) 60%,var(--accent-2)` với `color:#fff`, `.cta-banner h2{color:#fff}`, `.cta-banner p{color:rgba(255,255,255,.85)}`, `.cta-banner .primary{background:#fff;color:var(--ink-3)}` (globals.css:16). Dark: cả 3 điểm dừng gradient đều trở thành lavender sáng (`--ink-3:#cdb3ff`, `--accent:#ae86f7`, `--accent-2:#926cd6`) → nền banner gần như trắng tím, chữ trắng = 1.83–3.93:1. Tệ hơn, nút CTA "primary" là nền trắng + chữ `var(--ink-3)` = `#cdb3ff` → chữ màu trên nền trắng 1.4:1, nút tan vào banner.
- Ảnh hưởng thẩm mỹ: khối CTA cuối landing — "chiêu bài" quan trọng nhất — biến thành một mảng màu phẳng, chữ không đọc được, nút biến mất trong dark. Đây là trang được mở nhiều nhất (landing).
- File:line: `frontend/app/globals.css:16`.
- Cách sửa: thêm vào khối dark: giữ gradient tối bằng màu cố định tối (vd `linear-gradient(135deg,#2a182e,#4b2c82 60%,#926cd6)`) và override `.cta-banner .primary{background:var(--brand);color:var(--brand-contrast)}`; hoặc định nghĩa riêng token gradient sáng/tối.

### High

**H1. Nút Danger trong dark mode: chữ trắng trên nền cá hồi + màu hover còn sót của light.**
- Mô tả: `.danger{background:var(--danger);color:#fff}`, hover `#a03a33` (globals.css:7). Dark `--danger:#ff9b8a` (hồng cá hồi sáng) → chữ trắng = **2.04:1**. Hover `#a03a33` là đỏ gạch tối của light mode, hoàn toàn lạc tông trong dark (đang là nút sáng bỗng thành nút tối). Đây là nút xoá/hủy dữ liệu — nơi người dùng cần đọc rõ nhất.
- Ảnh hưởng: hành động phá hoại có màu mơ hồ, không phải "đỏ nguy hiểm", làm yếu cảnh báo thị giác lẫn an toàn thao tác.
- File:line: `frontend/app/globals.css:7`.
- Cách sửa: dùng `color:var(--brand-contrast)`… chưa đủ. Tốt nhất: dark override `.danger{background:var(--danger);color:#2a182e}` (nền sáng + chữ tối, giống pattern brand), và hover dùng tông sáng của danger thay vì `#a03a33`.

**H2. Icon-action hover trong dark mode: chữ/biểu tượng đồng màu nền — 1:1.**
- Mô tả: `.icon-action:hover:not(:disabled){background:var(--lavender);color:var(--ink-3)}` (globals.css:7). Dark: `--lavender:#cdb3ff` và `--ink-3:#cdb3ff` — **cùng một màu**. Nút ↻ (swipe địa điểm) và các icon trong itinerary khi hover sẽ hiện nền lavender với icon màu y hệt nền — không thấy gì.
- Ảnh hưởng: thao tác swipe/remove là cốt lõi của flow tinh chỉnh kế hoạch (PlanView.tsx:127); hover là tín hiệu "có thể bấm" duy nhất, giờ vô hình.
- File:line: `frontend/app/globals.css:7`.
- Cách sửa: dark override hover thành `color:var(--brand-contrast)` hoặc `color:var(--ink)` — đảm bảo tương phản trên nền lavender sáng.

**H3. Link/accent light mode dưới chuẩn AA.**
- Mô tả: `a{color:var(--accent)}`, `.eyebrow{color:var(--accent)}`, `.status{color:var(--accent)}` (globals.css:1, 10). `--accent:#926cd6` trên trắng = **3.93:1**, trên paper = **3.64:1**. Chuẩn WCAG AA yêu cầu 4.5:1 cho text thường. Link 15px, eyebrow 12px caps, status 14px đều chạm ngưỡng thấp.
- Ảnh hưởng: link màu tím nhạt, đặc biệt trên nền paper (`--paper:#f7f6f3` hơi ngả xám nên tệ hơn nền trắng), đọc mỏng, nhất là `--accent-2:#ae86f7` chỉ 2.57:1 (may mắn chỉ dùng cho outline focus và gradient).
- File:line: `frontend/app/globals.css:1`, `:10`.
- Cách sửa: tối ưu hóa accent về `#7c56c4`-ish (giữ tông tím nhưng đậm hơn), hoặc chỉ dùng accent cho large text/link hover, đổi `.eyebrow` sang `--ink-3`.

### Medium

**M1. Brand trùng Ink — "màu thương hiệu" không tồn tại như một màu.**
- Mô tả: `--brand:#2a182e` = `--ink:#2a182e`; `--brand-hover:#352438` = `--ink-2:#352438` (globals.css:1). Đây không phải "gần trùng" mà là **trùng y hệt**. Hệ quả ngữ nghĩa: brand không có tông riêng; mọi action chính (`.primary`, `.nav-cta`, `.bubble.user`, `.stop-index`, `.day-tabs.active`, `.inventory-tabs.active`, `.step::before`) đều là đen-tím gần đen.
- Ảnh hưởng thẩm mỹ: hai tín hiệu nhận diện đang cạnh tranh — "đen plum" cho hành động và "tím lavender" cho mọi thứ khác. Bản sắc không có một "màu thương hiệu" để người dùng nhớ; gradient chỉ sống ở logo nhỏ và thanh đỉnh planner. Với concept du lịch ấm áp, nút CTA đen không "ấm" chút nào.
- File:line: `frontend/app/globals.css:1`.
- Cách sửa: cho `--brand` một tông tím-plum ấm rõ rệt (vd `#3d1a4f`), kéo `--ink` về đen pha tím nhạt hơn, và để `--brand`/`--ink` diễn vai khác nhau. Chí ít cần có chú thích ý đồ nếu cố tình trùng.

**M2. `--surface-2` vô dụng ở light — mất tầng nổi cho input.**
- Mô tả: light `--surface-2:#ffffff` = `--surface:#ffffff` (globals.css:1). Input (textarea/select/input) chỉ phân biệt với card bằng border `--line`, mất hẳn tầng "input lõm" mà dark mode đang có tốt (`--surface-2:#2a182e` trên `--surface:#1f1222`).
- Ảnh hưởng: các field trong planner/workspace ở light trông phẳng, thiếu affordance "đây là ô nhập".
- File:line: `frontend/app/globals.css:1`.
- Cách sửa: light `--surface-2` về tông xám tím nhạt (vd `#f2f0f4` hoặc `#fbfafc`).

**M3. `::selection` dark mode đồng màu — 1:1.**
- Mô tả: `::selection{background:var(--lavender);color:var(--ink-3)}` (globals.css:1). Light: lavender + ink-3 đậm = 5.8:1, đẹp. Dark: `--lavender` và `--ink-3` cùng `#cdb3ff` → vùng chọn hiện nền lavender với **chữ cùng màu nền**. Không thấy được văn bản mình đang chọn.
- Ảnh hưởng: đặc biệt khó chịu khi người dùng bôi đen đoạn chat/plan để copy trong dark.
- File:line: `frontend/app/globals.css:1`.
- Cách sửa: dark override `::selection{background:var(--lavender);color:var(--surface)}` hoặc `color:#141014`.

**M4. Muted/Muted-2 light mode không đạt AA cho text nhỏ.**
- Mô tả: `--muted:#7f7482` trên paper = **4.11:1**; `--muted-2:#948b96` trên surface = **3.29:1** (globals.css:1). Text 13–15px dùng muted: `.featured-card p`, `.step p`, `.faq-body`, `.inventory-meta`, `.timeline p`; disclaimer 13px dùng muted-2. Đều dưới 4.5:1.
- Ảnh hưởng: chữ phụ mờ, đặc biệt "muted-2" (disclaimer, source link 11px) gần như mất — vừa thẩm mỹ vừa a11y.
- File:line: `frontend/app/globals.css:1`.
- Cách sửa: muted → `#6e6374`-ish, muted-2 → `#7d7483`-ish ở light.

**M5. Thang đo tiêu đề không nhất quán giữa các trang.**
- Mô tả: các clamp max không nằm trên một scale: hero `clamp(48px,6.5vw,88px)` (globals.css:13), generic h1 `clamp(38px,5vw,62px)` (globals.css:10), trip `clamp(30px,3.6vw,52px)` (globals.css:25), explore `clamp(42px,5.5vw,72px)` (globals.css:28), admin `clamp(40px,5vw,66px)` (globals.css:40). Các max 52/62/66/72/88 không theo nhịp nào.
- Ảnh hưởng: khi lướt từ trang này sang trang khác, "độ to" của tiêu đề chính thay đổi cảm nhận ngẫu nhiên; landing 88px rất hoành tráng nhưng explore 72px cùng hệ — sự chênh không có chủ đích.
- File:line: `frontend/app/globals.css:10,13,25,28,40`.
- Cách sửa: định nghĩa 4 bậc (vd 48/56/64/72 max) và gán theo mức độ "marketing vs task page".

**M6. Bảng màu bản đồ nằm ngoài hệ thống.**
- Mô tả: `MapView.tsx:37,49` và `RoadTripMap.tsx:15,16` dùng màu cứng teal `#0f766e` (route) và cam đất nung `#e4572e` (marker chọn). Không có token nào tương ứng trong `:root` hay dark.
- Ảnh hưởng: bản đồ — yếu tố giàu cảm xúc nhất của app du lịch — lại là chỗ duy nhất "lệch tông": teal/cam nóng đối lập hoàn toàn với tím lavender của toàn app. Thực ra màu cam đất nung rất "Hà Nội ấm", nhưng vì không được quản lý như token, nó thành ngoại lệ chứ không phải bản sắc. Dark mode không đổi → teal/cam vẫn hiển thị như cũ trên nền tối.
- File:line: `frontend/components/MapView.tsx:37,49`, `frontend/components/RoadTripMap.tsx:15,16`.
- Cách sửa: thêm token `--map-route`/`--map-selected` + variant dark, hoặc cố tình nâng cam `#e4572e` lên thành màu thứ ba của brand (kết hợp với tím) để có "ấm + tím".

**M7. Footer dark mode mất "chữ ký" — hòa vào nền trang.**
- Mô tả: `.site-footer{background:var(--ink)}` light. Dark override: `.site-footer{background:var(--surface-2)}` = `#2a182e` (globals.css:43). Với nền trang dark `--paper:#141014`, footer chỉ tối hơn một chút — khối footer to gần như dính vào page. Trong khi light mode footer đen tím tương phản mạnh mẽ và là mốc thị giác cuối trang.
- Ảnh hưởng: mất "cột mốc" kết trang; dark mode cả trang là một dải tối liền.
- File:line: `frontend/app/globals.css:37`, `:43`.
- Cách sửa: dark dùng nền tối hơn paper (vd `#0e0a10`) hoặc bọc footer bằng border-top rõ.

**M8. Nhận diện "một-tông tím" — lavender bị dùng quá tay.**
- Mô tả: đếm token trong `globals.css`: họ `--lavender*` 65 lần + `--accent*` 32 lần = **97 lần**, so với tổng họ trạng thái `--green*`+`--sun*`+`--danger*`+`--info*` ≈ 28 lần. Lavender hiện diện ở: hero eyebrow, bubble assistant, icon-action, focus ring, chip hover, day-tabs, trip-facts, thumb gradient, comments, price-analysis chips, admin tags, env-snippet, selected slot ring, map legend… gần như mọi thành phần thứ cấp đều được "tô tím".
- Ảnh hưởng: không còn điểm nhấn — khi tất cả đều là accent thì không ai là accent. Concept "Hà Nội ấm áp" (phở, cafe, mặt trời) không có biểu hiện bằng màu ấm ở bề mặt người dùng: `--sun` chỉ xuất hiện 6 lần, toàn trong admin pills. Ngoài chấm xanh `--green` social-proof, không có một giọt nắng nào ở landing.
- File:line: `frontend/app/globals.css:13,16,19,22,25,37,40` (các nơi dùng lavender).
- Cách sửa: cắt giảm lavender-50/-soft ở các vùng thứ cấp (thumb, facts, price chips), nhường chỗ cho giấy/surface trung tính; đưa sun/cam vào 1–2 điểm nhấn landing (chấm social-proof, icon thumb cafe) để có "nắng Hà Nội".

### Low

**L1. Shimmer loading trắng trong dark mode.**
- Mô tả: `.slot-photo.loading::after` dùng `rgba(255,255,255,.5)` (globals.css:25). Trên nền slot tối (dark), vệt trắng 50% chạy ngang rất chói, lóe gắt so với tông tối.
- Cách sửa: dark override bằng `rgba(255,255,255,.08)` hoặc dùng token shimmer sáng/tối.

**L2. Thanh gradient đỉnh planner phẳng trong dark.**
- Mô tả: `.planner::before` gradient `ink-3→accent→lavender` (globals.css:19). Dark: 3 màu đều thuộc nhóm lavender sáng (`#cdb3ff`, `#ae86f7`, `#cdb3ff`) → dải 6px gần như 1 màu phẳng, mất hiệu ứng "một dải sáng tím" như light. Note: còn có điểm trùng lặp — ink-3 và lavender cùng `#cdb3ff`, nên gradient dark thực chất chỉ 2 tông.
- Cách sửa: dark override gradient bằng `#926cd6→#6a4bb0→#4b2c82` để giữ độ tương phản với nền.

**L3. Thumbnail feature dùng emoji làm minh hoạ.**
- Mô tả: 3 card featured chỉ khác nhau ở emoji `☕ 🍜 🏛️` trên cùng một gradient lavender (page.tsx:53-61, globals.css:16 `.featured-card .thumb`). Cả 3 nhìn như nhau, không tạo "hình ảnh đại diện" cho ý tưởng cafe/ẩm thực/văn hoá.
- Ảnh hưởng: không phải lỗi màu, nhưng là lỗ hổng bản sắc thị giác — mảng "minh hoạ" của toàn landing trông như chỗ trống chờ ảnh thật.
- Cách sửa: 3 tông nền khác nhau theo concept (cafe = nâu/cam nhạt, food = vàng nắng, culture = tím) — vừa phá "một-tông tím" vừa gắn màu với ý nghĩa.

**L4. `.danger:hover #a03a33` (light) — tông đỏ gạch khác hệ với `--danger:#bb4d45`.**
- Mô tả: hover đỏ gạch đậm hơn hẳn, không phải biến thể tối của `--danger` (globals.css:7). Hệ quả: nút đỏ khi hover "đổi màu" thay vì "đậm lên", gây nhảy thị giác nhỏ. Kết hợp H1 khiến nút danger có tới 3 sắc độ khác nhau giữa các trạng thái/theme.
- Cách sửa: định nghĩa `--danger-hover` bằng cách tối hoá danger trong cùng không gian màu.

### Note

**N1. Font khai báo nhưng không được tải.** `--font:"Inter","Fig Grotesk",system-ui` (globals.css:1) nhưng không có `next/font`, `@font-face`, fontsource, hay thẻ Google Fonts nào trong `layout.tsx` (layout.tsx:1-9) hay `package.json`. Trình duyệt bỏ qua Inter/Fig Grotesk, rơi về `system-ui`. Bản sắc typographic "Inter + Fig Grotesk" không bao giờ được hiện thực. Mọi đánh giá font-weight 800/900, letter-spacing đang áp lên một font hệ thống khác nhau trên từng máy — tiêu đề 88px sẽ nhìn khác trên Windows (Segoe UI) vs macOS (SF Pro).
- Ảnh hưởng: đây là lý do lớn nhất khiến "bản sắc" chưa hoàn chỉnh; sửa trong một buổi.

**N2. `--ink-3` mang hai vai trò xung đột.** Light: `--ink-3:#4b2c82` = tím đậm (dùng làm text trên lavender-soft, endpoint gradient, text selection). Dark: `#cdb3ff` = lavender sáng (dùng làm text trên lavender-soft — ok, nhưng cũng là endpoint gradient, và là "text trên lavender" trong ::selection/icon-action hover → nguyên nhân trực tiếp của M3 và H2). Một token phục vụ cả "mực chữ" lẫn "màu brand" nên khi đảo dark nó kéo theo những vụ nổ contrast không lường trước.
- Cách sửa: tách `--brand-strong` (gradient/selection) khỏi `--ink-3` (chữ).

**N3. `line-height:.98` cho hero 88px với tiếng Việt.** `.hero h1{line-height:.98}` (globals.css:13). Tiếng Việt giàu dấu (đ, ơ, ế) — dòng cao 0.98 rất dễ cắt đuôi/chữ dấu mũ của dòng trên/dòng dưới khi hai dòng đè sát. Nên kiểm tra render thực tế; nếu không thể thì nâng lên 1.0–1.05.

**N4. `--info` hầu như chết.** Định nghĩa (globals.css:1) nhưng chỉ xuất hiện 4 lần trong file, gần như không có nơi dùng trong UI người dùng. Đây là token tốt nên được tận dụng cho hint/meta thay vì chung một màu với muted.

**N5. `.danger` dùng `#fff` cứng trong khi toàn hệ có `--brand-contrast`.** Mặc dù tình cờ pass light (4.93:1), nhưng pattern "màu trắng cứng trên nền sáng" là nguồn gốc của mọi bug dark mode (B1, B2, H1). Quy ước nên là: *mọi nơi có text trên màu = dùng token, không dùng `#fff`/`#000` trừ khi có lý do.*

---

## Đánh giá dark mode riêng

**Token map dark là phần tốt nhất của toàn bộ hệ thống.** Cách đảo brand/contrast theo kiểu "đèn pha" (brand sáng thành lavender, chữ brand-contrast thành đen tím) là lựa chọn bản sắc thông minh: giữ cùng tông màu, chỉ đảo sáng/tối — app vẫn "là chính nó" trong dark, không bị tẩy trắng. Contrast đo được ở dark đều vượt AA: `--ink` 15.47:1, `--muted` 7.41:1, `--accent` 6.78:1, `--brand`/`--brand-contrast` 9.06:1, status soft (green/sun/danger) dùng pattern "soft tối + chữ màu sáng" rất đúng.

Nhưng dark mode gánh **4 vết nứt do màu cứng**: `.chat-box button` (B1), `.cta-banner` (B2), `.danger` + hover (H1), `.icon-action:hover` (H2) — tất cả cùng một gốc: code gốc đặt `color:#fff` hoặc `--ink-3` ở chỗ nền là brand, và khối dark chỉ override *surface/input* chứ không override *text-on-brand*. Cộng thêm `::selection` 1:1 (M3) và shimmer trắng (L1). Nói gọn: **dark mode đẹp về token, vỡ về nơi màu cứng còn sót — và các nơi đó lại là action quan trọng nhất (gửi chat, CTA, xoá).**

Một quan sát tinh tế: `--surface-2` (dark `#2a182e`) lại chính là `--brand`/`--ink` của light mode — tức là nền input dark "gợi lại" màu brand light, một chi tiết nhất quán về mặt cảm nhận dù vô tình.

Footer dark (M7) và thanh gradient planner dark (L2) là hai điểm "mất năng lượng" thị giác còn lại sau khi vá màu cứng.

---

## Kết luận: Điểm thẩm mỹ

**5.5/10** — Nền tảng token và dark-mode inversion rất chín chắn, nhưng bản sắc "Hà Nội ấm áp" chưa được hiện thực bằng màu (tím bị lạm dụng, không có nắng ở bề mặt user), font thương hiệu không được tải, và dark mode còn nguyên 4 điểm vỡ ở các action chính do màu `#fff` hard-code.

### Một câu cho mỗi mức độ ưu tiên
- **Blocker (2):** sửa `color:#fff` → `var(--brand-contrast)` trong `.chat-box button` (globals.css:22) và dựng lại gradient + nút CTA cho dark (globals.css:16) trước khi giao bất kỳ ai dùng dark.
- **High (3):** vá danger + icon-action hover dark, và đậm hóa accent light để link đạt 4.5:1.
- **Medium (8):** tách `--brand` khỏi `--ink`, cho `--surface-2` thật sự khác biệt ở light, sửa `::selection` dark, đậm muted light, thống nhất scale tiêu đề, đưa màu bản đồ vào hệ token, khôi phục tương phản footer dark, cắt bớt lavender và thả một chút "nắng Hà Nội".
- **Low (4) + Note (5):** tải font Inter/Fig Grotesc thật (ưu tiên cao nhất trong nhóm này — nó quyết định bản sắc typographic), tách vai trò `--ink-3`, kiểm tra hero line-height với dấu tiếng Việt, tận dụng `--info`, đổi shimmer/thumbnail.

---

**Confidence: 8/10**

**Ground-truth tally:** 17/21 kết luận quan trọng dựa trên code đọc trực tiếp và số liệu tính được — (a) đọc nguyên văn `:root` và khối dark tại `globals.css:1`, `:43`; (b) trùng khớp `--brand:#2a182e == --ink:#2a182e`, `--brand-hover == --ink-2`, `--surface-2 == --surface` (light), `--ink-3 == --lavender` (dark) đối chiếu từng hex; (c) mọi contrast ratio tính bằng công thức WCAG từ hex trong code; (d) 12 giá trị màu hard-code (`#fff` ở globals.css:7,16,22; `#a03a33` ở :7; `#e4572e`/`#0f766e` ở MapView.tsx:37,49 và RoadTripMap.tsx:15,16; `#28491f`/`#5c3a0e`/`#5c1a14` ở :40) và danh sách dark override không có `.chat-box button`, `.cta-banner`, `.danger:hover`, `.icon-action:hover` đối chiếu từng selector; (e) đếm tần suất token bằng regex trên toàn file (lavender+accent 97, status ~28); (f) xác nhận không có `next/font`/`@font-face`/fontsource qua grep `layout.tsx` và `package.json`. Còn lại (4/21) là nhận định thẩm mỹ chủ quan: mức độ "lạm dụng tím" cảm nhận như thế nào, "ấm áp Hà Nội" nên hiện ở đâu, và trọng số cho điểm tổng.
