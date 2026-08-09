# 07 — Red-team đối kháng bản tổng hợp thẩm mỹ — "Mình Đi Đâu Thế"

**Vai trò:** reviewer đối kháng (red-team). Mục tiêu: cố gắng bẻ gãy `06-synthesis.md` — kiểm chứng từng claim số, bóc tách lỗi kỹ thuật thật khỏi sở thích chủ quan, tìm blind spot, và chấm lại điểm.
**Loại:** THUẦN — chỉ đọc, không sửa code.
**Phương pháp:** đọc đầy đủ synthesis + `01-visual-identity.md` + `04-ux-polish.md`; tính lại mọi contrast ratio bằng công thức WCAG (Python); grep đối chiếu từng selector trong `globals.css`; đọc `layout.tsx`, `PlanView.tsx`, `Planner.tsx`, `admin/page.tsx`, `roadtrip/page.tsx`, `MapView.tsx`, `RoadTripMap.tsx`, `LocaleProvider.tsx`, `i18n-core.ts`, `README.md`, `plan/[token]/page.tsx`.

---

## Verdict đối kháng (bản tổng hợp có vững không)

**Bản tổng hợp vững về mặt dữ kiện, yếu về mặt định cỡ (calibration).** Đại đa số claim về code là chính xác — tôi xác minh lại từng cái: màu hard-code `#fff`/`#a03a33`, thiếu override dark cho `.chat-box button`/`.danger`/`.cta-banner`/`::selection`, `.icon-action:hover` dark vẫn 1:1, `<main>` lồng, admin thiếu class `card`/nút trần/grid 4 cột-5 thẻ, roadtrip `withInventory` tràn grid, PlanView render lỗi bằng `.status`, RTL không có selector `[dir]`, font không tải, không favicon/og/404 — **tất cả đều đúng**. Tally ground-truth 31/38 của synthesis là trung thực, không "bịa" dữ kiện.

Nhưng synthesis mắc 3 khuyết tật cấu trúc:

1. **Định cỡ sai mức độ nghiêm trọng.** Gọi 2 vấn đề dark-mode là "Blocker / thao tác chính mất" trong khi: (a) dark mode là chế độ **không mặc định** và **không có nút chuyển** (chỉ theo OS pref), (b) nút gửi chat *không biến mất* — chỉ **glyph ↑ trắng mờ**; bản thân nút (hình tròn lavender trên nền tối) vẫn hiện với contrast 9.84:1 với panel, (c) đây là **MVP/demo** (README.md:1,3,53-60), không phải sản phẩm công khai. "Một nửa số người dùng (dark)" (01:31, lặp lại ở synthesis:39) là **con số bịa** — không có nguồn dữ liệu nào. Blocker nên là High.
2. **Một con số sai lan truyền.** Cả 01 (B2, :36) và synthesis (BL-2, :45) ghi nút CTA dark "chữ `--ink-3` trên nền trắng = 1.4:1". **Sai.** Tính lại: `#cdb3ff` trên `#ffffff` = **1.83:1** (giống hệt chat button). Không ai tái tính con số kế thừa từ lane trước.
3. **Trộn lẫn "lỗi" và "gu".** H-12 (spacing scale), M-1 (brand==ink), M-8, M-9, M-10, M-11 là **đánh giá gu thiết kế**, không phải bug. Gọi chúng High/Tier-1 với ngôn ngữ "nhịp điệu rời rạc", "mất tầng lõm" là quy chụp. Đặc biệt M-1 mâu thuẫn nội bộ với chính điểm mạnh #4 của 01 (gradient ink-3→accent→lavender là "tài sản thương hiệu mạnh") — nếu gradient đã là chữ ký brand thì việc `--brand == --ink` (màu trung tính) là lựa chọn có chủ đích, không phải lỗi "màu thương hiệu không tồn tại".

**Verdict:** synthesis đáng tin ở phần "cái gì hỏng", thiếu tin cậy ở phần "hỏng đến mức nào" và "cái nào phải sửa". Phần khuyến nghị Tier 0/1 trộn bug thật (contrast dark, layout admin) với việc làm đẹp chủ quan (spacing scale, tách brand).

---

## Phản biện theo mức

### Blocker — mục tiêu: BL-1, BL-2

**BL-1 "Nút gửi chat biến mất trong dark mode".**
- *Đúng:* `.chat-box button{background:var(--brand);color:#fff}` (globals.css:22); dark `--brand:#cdb3ff`; **không** override `.chat-box button` trong khối dark (grep xác nhận 0 match trong :43). Arrow trắng trên lavender = 1.83:1 — con số **đúng**.
- *Sai/phóng đại:* (1) "nút biến mất" — nút vẫn là **hình tròn lavender rõ ràng** trên nền panel `#1f1222` (contrast 9.84:1), chỉ glyph ↑ mờ. Một người dùng dark vẫn thấy "có nút", chỉ không đọc rõ ký hiệu. Đây là lỗi contrast của **non-text/graphical object** (cần 3:1 theo WCAG 1.4.11) — fail thật, nhưng là **High**, không phải "mất thao tác chính". (2) "ở một nửa số người dùng" — bịa số liệu; dark chỉ áp dụng khi OS dark, và app không có toggle (chính synthesis ghi nhận ở mục Khoảng trống #6). (3) Mức ảnh hưởng: nút send ở PlanView chỉ là phụ trong flow tinh chỉnh — thao tác **chính** của sản phẩm là tạo plan (Planner) và xem itinerary, không phải nút ↑.
- *Bằng chứng:* globals.css:22,43; PlanView.tsx:126; Planner.tsx:198-200. Contrast tính lại: white-on-`#cdb3ff` = 1.83:1; `#cdb3ff`-on-`#1f1222` = 9.84:1.
- *Xếp lại:* **High.**

**BL-2 "CTA banner vỡ toàn bộ trong dark".**
- *Đúng:* `.cta-banner` gradient `var(--ink-3),var(--accent) 60%,var(--accent-2)` + `color:#fff` (globals.css:16); dark 3 màu đều sáng; không override `.cta-banner` trong :43 (grep 0 match). Trắng trên gradient dark: 1.83–3.93:1 — **đúng**.
- *Sai:* con số "nút CTA = 1.4:1" (01:36, synthesis:45). Giá trị đúng là **1.83:1**. Mọi kết luận "tan vào banner" vẫn giữ, nhưng con số cụ thể là sai và đã được lan truyền qua 2 lớp tài liệu mà không ai kiểm lại.
- *Phóng đại:* "chiêu bài quan trọng nhất của landing" — landing là trang demo; CTA cuối trang không phải hành động chính của MVP. Vỡ dark ở đây là thật nhưng phạm vi hẹp (một block trên một trang, chỉ khi OS dark).
- *Bằng chích:* globals.css:16,43. Contrast tính lại: white-on-`#cdb3ff`=1.83, white-on-`#ae86f7`=2.78, white-on-`#926cd6`=3.93; `#cdb3ff`-on-white=1.83.
- *Xếp lại:* **High.**

**Kết luận chung cho Blocker:** không có vấn đề nào trong bản này đạt chuẩn "chặn release" của một MVP demo. Không có layout nào vỡ không đọc được trong **chế độ mặc định (light)**. Hai "Blocker" đều nằm trong chế độ phụ (dark, không toggle, không mặc định). **Hạ cả hai xuống High.**

### High — mục tiêu: H-1, H-2, H-3, H-4, H-5, H-6, H-7, H-8, H-9, H-10, H-11, H-12, H-13, H-14, H-15

- **H-1 danger dark 2.04:1 — ĐÚNG, giữ High.** `#ff9b8a`+white tính lại = 2.04:1, không override dark. Chính xác.
- **H-2 icon-action hover 1:1 — ĐÚNG, giữ High.** Dark block **có** `.icon-action:hover:not(:disabled)` (globals.css:43) nhưng gán `lavender`/`ink-3` = cùng `#cdb3ff` → 1:1. Synthesis đã chính xác hóa mâu thuẫn lane tốt (Mục mâu thuẫn #1). Đây là điểm synthesis xử lý giỏi.
- **H-3 contrast light dưới AA — con số ĐÚNG, mức ĐÚNG nhưng biên luận lệch.** `--accent:#926cd6`=3.93:1 (white), `--muted:#7f7482`=4.11:1 (paper), `--muted-2:#948b96`=3.29:1 (white) — tất cả khớp tính lại. Nhưng "4.11:1" cho `.lead` 19px là **near-pass** (cần 4.5 cho normal text, nhưng 19px bold? không — lead là regular). Fail thật nhưng đây là lỗi **a11y hiển thị**, ảnh hưởng thẩm mỹ thấp (người dùng vẫn đọc được, chỉ hơi mờ). Xếp High hơi cao; Medium là công bằng. Cần phân biệt: `.muted-2` 11px `source` 3.29:1 mới là vấn đề thực sự.
- **H-4 `<main>` lồng — sự thật đúng, trọng số cao quá.** Nested `<main>` là invalid HTML (chuẩn), và `.workspace-page{max-width:1500px}` (globals.css:25) bị cha `.shell` 1200px chặn → 1500 không bao giờ có hiệu lực. **Nhưng** hậu quả thị giác: workspace hiển thị ở 1112px thay vì 1500px — grid `minmax(260,.65fr) minmax(400,1.2fr) minmax(380,1.05fr)` vẫn đủ chỗ (tổng min 1072px ≤ 1112px). Không vỡ layout, chỉ **hẹp hơn ý đồ**. Đây là lỗi thiết kế-intent, không phải "nuốt thiết kế" như mô tả. High→**Medium-High**; đưa vào Tier 0 là quá.
- **H-5 offer-card admin thiếu class `card` — ĐÚNG, nhưng hạ trọng số.** admin/page.tsx:569 `className="offer-card"` vs explore:66 `className="offer-card card"` + support:62 `className="card offer-card"`. `--offer-card` không có style nền/border/padding (chỉ `h2` và `.secondary`). Thật. Nhưng là trang **admin nội bộ** (không có auth public), và đây là danh sách queue dạng text — vẫn đọc được, chỉ thiếu khung. High→**Medium**, nhất quán với việc chính synthesis hạ M-23 (admin chữ không dấu) xuống Medium vì "chỉ ảnh hưởng admin nội bộ" — **tự mâu thuẫn**: cùng lý do "admin nội bộ" mà H-5/H-6/H-8 giữ High/Tier 0 còn M-23 bị hạ.
- **H-6 admin-strip 5 thẻ trên 4 cột — ĐÚNG, hạ trọng số.** 5 `<article class="card">` (admin:368-372) trong `repeat(4,1fr)` (globals.css:40) → thẻ 5 rớt hàng 2. Thật nhưng **không vỡ** — chỉ là hàng 2 có 1 thẻ chiếm 1/4. Admin nội bộ. High→**Medium**.
- **H-7 roadtrip withInventory tràn grid — ĐÚNG, giữ Medium-High.** `.stop-input` 5 cột `34px repeat(4,minmax(100px,1fr))` (globals.css:31); khi withInventory mỗi hàng 8 phần tử (roadtrip/page.tsx:56: span, name, lat, lng, IATA, arrival, departure, ×). 3 phần tử dư rơi vào implicit row auto-width → lệch cột. Thật, nhưng chỉ khi bật checkbox "bao gồm chỗ ở" — tính năng phụ của trang phụ.
- **H-8 nút "Huy" admin không class — ĐÚNG, hạ.** admin/page.tsx:580 `<button type="button" disabled...>Huy</button>` không class → render mặc định trình duyệt. Đúng, cosmetic, admin nội bộ. High→**Low-Medium**.
- **H-9 PlanView lỗi render như thành công — ĐÚNG, giữ High.** PlanView.tsx:122 render `message` và `busy` đều `.status` + `role="status"`; các key lỗi (`actionFailed`, `refineFailed`, `versionsFailed`, `commentsFailed`, `regenerateFailed` — gán tại :90,100-113) không bao giờ dùng `.error`/`role="alert"`. Ba trang khác làm đúng. Đây là **bug UX/a11y thật**, nhưng là **thẩm mỹ** hay không thì đáng tranh cãi — đây là phạm vi UX-polish, không phải visual aesthetics. Giữ High với nhãn rõ "UX, không phải thẩm mỹ".
- **H-10 RTL — sự thật đúng, mức ảnh hưởng bị thổi phồng.** dir set trong useEffect (LocaleProvider.tsx:101), `<html lang="vi">` hardcode (layout.tsx:9), 0 selector `[dir]` (grep). Đúng. **Nhưng**: app không có locale routing theo URL, locale từ localStorage (settings), mặc định vi; "quảng bá 19 locale" là phóng đại — 19 locale là **khai báo key dịch** (i18n-core.ts:1), không phải cam kết hiển thị RTL. Với MVP demo cho người Việt, tác động RTL là **rất thấp**. High→**Medium** (FOUC chỉ xảy ra nếu người dùng tự chọn ar/he trong settings — hiếm). M-18 (letter-spacing âm phá chữ Ả Rập) cũng là phán đoán chuyên môn không kiểm chứng được (chính 04 thừa nhận 4/25 là phán đoán).
- **H-11 mobile chat order:3 — là gu, không phải lỗi.** `.workspace>.chat-panel{order:3}` (globals.css:25) đặt chat sau map. **Có chủ đích**: itinerary→map→chat là ưu tiên deliverable — chính synthesis công nhận "tư duy hierarchy đúng" ở điểm mạnh #6 rồi lại liệt H-11 High. **Tự mâu thuẫn.** Người dùng mobile xem lịch trình trước là hợp lý. High→**Low** (gu; đáng thử nghiệm A/B hơn là "phải sửa").
- **H-12 không spacing scale — là gu, không phải lỗi.** Đúng là dùng nhiều giá trị lẻ (7/9/11/13/15/17/18/22/26/28px). Nhưng "mắt cảm nhận đầu tiên" là claim không chứng minh được, và nhiều hệ thống thiết kế tốt vẫn có giá trị 14/18/26px. Đây là đề xuất refactor toàn file (hàng trăm giá trị) với ROI thẩm mỹ không đo được. High→**Low-Medium**; nên để ở Tier 2, không Tier 1.
- **H-13 6 cỡ page-title — ĐÚNG nhưng là polish.** explore/roadtrip clamp 42–72px (:28,:31), admin 66px (:40), history 62px (:10), login 52px (:34), settings 54px (:34), trip-header 52px (:25). Thật. Ảnh hưởng thẩm mỹ: khi chuyển trang tiêu đề to nhỏ khác nhau. Đáng Medium, không High.
- **H-14 "drawers" không phải drawer — ĐÚNG, đúng mức.** version-drawer/comment-drawer/feedback-card là `.card` chèn thẳng (PlanView:123-125; globals.css:25 có `.version-drawer,.comment-drawer{margin:12px 0;...}`). Layout shift thật khi bật. Medium đúng.
- **H-15 trip-header 7–9 nút — ĐÚNG, đúng mức.** PlanView:120: share, PDF, calendar, JSON, comments, feedback (có điều kiện), versions, undo (khi ver>1), regenerate = tối đa 9 `.secondary`. Ở 1112px nội dung hàng nút cao 2-3 dòng. Thật, Medium-High hợp lý.

### Medium — mục tiêu: M-1, M-2, M-3, M-4, M-5, M-7, M-12, M-13, M-14, M-23, M-24, M-26

- **M-1 brand==ink — QUÁ QUY CHỤP, mâu thuẫn nội bộ.** `--brand:#2a182e == --ink`, `--brand-hover == --ink-2` (globals.css:1) — dữ kiện đúng. Nhưng khuyến nghị "cho brand tông tím-plum ấm #3d1a4f" là **tái thiết kế thương hiệu**, không phải fix lỗi. Chính 01 khen gradient logo `ink-3→accent→lavender` là "tài sản thương hiệu mạnh" và "dấu hiệu nhận diện có thể nhớ được" — vậy màu đã có bản sắc (tím lavender là brand), `--brand==--ink` là lựa chọn neutral cho action chính. Đây là **gu**, Medium là cao.
- **M-2 surface-2 light = surface — ĐÚNG, Medium hợp lý.** `--surface-2:#ffffff` = `--surface` (globals.css:1) → input light chỉ phân biệt bằng border. Thật nhưng là **chi tiết tinh tế**, mắt thường khó nhận.
- **M-3 ::selection dark 1:1 — ĐÚNG, giữ Medium.** `::selection{background:var(--lavender);color:var(--ink-3)}` (:1); dark cả hai `#cdb3ff`, không override. Thật. Đây nên được gộp với H-2 (cùng gốc `--ink-3` vai trò kép, đã được N-2 chẩn đoán đúng).
- **M-4 map màu hardcode — ĐÚNG, Medium hợp lý.** `#0f766e`/`#e4572e` (MapView:37,49; RoadTripMap:15,16). Thật. Lưu ý: cam đất nung `#e4572e` thực ra là màu ấm đúng concept — M-4 và M-1 đang tự mâu thuẫn về định hướng bản sắc.
- **M-5 lavender 97 vs status 28 — số liệu ĐÚNG nhưng kết luận gu.** Đếm lại: `--lavender`=65, `--accent`=32, tổng 97; `--sun`=6, `--green`=8, `--danger`=10, `--info`=4 = 28. Con số chính xác. Nhưng "khi tất cả đều accent thì không ai là accent" là nhận định thẩm mỹ, không phải defect. Đúng như tuyên bố ở cuối synthesis (7/38 là chủ quan).
- **M-7 3 ngôn ngữ focus — ĐÚNG, Medium.** Thật (planner ring 4px vs outline global).
- **M-12 Unicode ↑↻× — ĐÚNG, Medium hợp lý.** PlanView:126 (↑), :127 (↻), roadtrip:56 (×). Đúng — render lệch theo OS/font. Đây là blind spot mà **synthesis đã bắt kịp** (01/04 không có, synthesis thêm vào).
- **M-13/M-14 busy chỉ text + animation dead code — ĐÚNG, là phát hiện tốt nhất của bộ lane.** `.bubble.typing`/`typingPulse` (globals.css:22) không render; `.slot-photo.loading::after`/`shimmer` (:25) không bao giờ kích hoạt (PlanView.tsx:117). `creatingPlan` (LocaleProvider:75) không dùng. **Đây là phần giá trị nhất của cả deep-dive** — dead code cụ thể, khuyến nghị "tận dụng miễn phí" đúng hướng và surgical.
- **M-23 admin chữ không dấu — ĐÚNG, Medium hợp lý.** "Quan ly he thong", "Huy", "Ghi chu noi bo"... (admin:357,358,362,565,573,580,583). Hạ từ High→Medium nhất quán với "admin nội bộ".
- **M-24 map-panel không `.card` — ĐÚNG, Medium.** PlanView:128 `map-panel` không class card trong khi chat/itinerary có. Thật.
- **M-26 hero mobile — gu, Medium cao.** "clamp(48px,6.5vw,88px) giữ 48px xuống tới 0px" — thật nhưng "áp đảo" là phán đoán; hạ xuống phụ.

### Low / Note — mục tiêu: L-1..L-17, N-1..N-15

- Đa số đúng và được xếp đúng mức. Lưu ý vài điểm:
- **L-1 shimmer trắng dark** — `rgba(255,255,255,.5)` (:25). Nhưng M-14 xác nhận `.slot-photo.loading` không bao giờ render → shimmer là **dead code**, không thể "chói trong dark" nếu chưa từng chạy. Xếp L-1 vào cùng M-14 thì logic hơn — hiện tại synthesis vừa nói "dead code" (M-14) vừa lo "chói mắt" (L-1) — **mâu thuẫn nhỏ nội bộ**.
- **N-1 font không tải — ĐÚNG, và là phát hiện quan trọng.** Không `next/font`, `@font-face`, fontsource, Google Fonts (grep 0 match); package.json không có font. Đúng. Nhưng xếp N-1 (một Note) làm **thay đổi bản sắc lớn nhất Tier 1** là đúng — đây là chỗ synthesis giỏi.
- **N-2 `--ink-3` vai trò kép — chẩn đoán gốc rễ tốt nhất của toàn tài liệu.** Đúng và sắc.

---

## Khuyến nghị surgical thay thế (khác synthesis)

Synthesis tuyên bố "toàn bộ là tinh chỉnh trên nền vững, không viết lại" nhưng Tier 1 của nó lại chứa việc làm to: M-1 (đổi màu brand toàn app), H-12 (refactor toàn bộ spacing), H-13 (gộp title 6→2), H-10 (logical properties khắp file), H-14 (dựng drawer overlay). Đó là **reskin**, không phải surgical. Đề xuất thay thế:

**Nhóm A — Bug thật, sửa 1 buổi (ưu tiên thật sự):**
1. Dark contrast gốc chung: thay `#fff` cứng bằng token trên mọi text-over-color. **Một quy tắc duy nhất** đã chữa BL-1, H-1, M-3 đồng thời: `.chat-box button{color:var(--brand-contrast)}`, `.danger{color:var(--brand-contrast)}`, `::selection` dark override. CTA dark giữ gradient tối cố định + `.cta-banner .primary{background:var(--brand);color:var(--brand-contrast)}`. Không cần đụng gì khác.
2. H-2: `.icon-action:hover:not(:disabled)` dark → `color:var(--brand-contrast)`. Một dòng.
3. H-9: thêm cờ `error` cho `UiMessage`, render `.error` + `role="alert"`. Ràng buộc type trong i18n-core đã có sẵn các key — không đổi schema.
4. Admin: thêm `card` vào class (:569), grid `repeat(5,1fr)` (:40), class cho nút "Huy" (:580). 3 dòng.
5. H-7: khi `withInventory` dùng grid 8 cột hoặc 2 hàng có cấu trúc — 1 media/branch trong roadtrip.
6. H-4: `layout.tsx` đổi `<main className="shell">` thành `<div className="shell">` — một thẻ; không phải sửa 10 trang (mỗi trang vẫn giữ `<main>` đúng chuẩn).

**Nhóm B — Có thể làm, chi phí thấp, ROI thật:**
7. N-1: tải Inter bằng `next/font` — 1 buổi, đúng như synthesis.
8. M-13/M-14: render `.bubble.typing` khi `busy==="refine"` + `.slot-photo.loading` — tận dụng CSS có sẵn, đúng synthesis. **Đây là phần nên làm nhất.**
9. M-23: đưa admin vào i18n hoặc ít nhất thêm dấu.

**Nhóm C — Đừng làm ở Tier 1 (hoãn, thuộc gu/re-skin):**
10. M-1 (đổi brand), H-12 (spacing scale), H-13 (gộp title), H-10 RTL (logical properties) — **hoãn lại sau khi có user thật**. Với MVP demo, việc đổi màu brand là quyết định kinh doanh, không phải bug.
11. M-2, M-5, M-6, M-8→M-11, M-26 — polish chủ quan, để Tier 3.

**Ý chính:** synthesis nên tách 2 câu chuyện — "lỗi kỹ thuật thật cần sửa" (6-9 dòng CSS/class) và "định hướng bản sắc" (quyết định có người dùng thật mới nên chốt). Trộn chúng vào một Tier 0/1 làm "bắt buộc sửa" là over-claim.

---

## Blind spots bị bỏ sót

1. **"Tiếp tục với Google · local"** — loginTranslations có hậu tố "· local" (LocaleProvider.tsx:33-51, mọi locale) — **artefact dev lộ ra UI production**: một trang đăng nhập chính lại in chữ "local" tiếng Anh cạnh nút Google. Không lane nào bắt. Rõ ràng và dễ sửa hơn nhiều mục trong Tier 1.
2. **Map attribution typo** — `attribution:"Ac OpenStreetMap contributors"` (MapView.tsx:28, RoadTripMap.tsx:17) — lẽ ra là "© OpenStreetMap contributors". Typo hiển thị trên **mọi bản đồ**, cả pháp lý (OSM yêu cầu attribution đúng). Không ai bắt.
3. **`toLocaleString("vi-VN")` hardcode** — admin page:560,575,596 dùng `toLocaleString("vi-VN")` kể cả khi locale khác — tương tự M-23, cùng gốc "admin nội bộ" nhưng chưa được liệt kê.
4. **`<br/>` hardcode trong title roadtrip** — roadtrip/page.tsx:56 `{t("titleFirst")}<br/>{t("titleSecond")}` — cứng 2 dòng cho mọi locale, phá vỡ dòng chảy bản dịch dài/ngắn; không được nêu.
5. **Đếm sai số trang có `<main>`:** synthesis ghi "9/9 trang" (synthesis:72) nhưng grep cho **10 trang + PlanView** (layout + page, explore, roadtrip, history, settings, login, privacy, terms, support, admin, + PlanView:119) — admin cũng có `<main className="admin-page">` (admin:355). Sai số lẻ nhưng cho thấy "9/9" là đếm thiếu.
6. **Mâu thuẫn nội bộ M-14 vs L-1** (shimmer vừa "dead code" vừa "chói dark") — đã nêu ở trên.
7. **Chưa nêu: không có manifest / apple-touch-icon** cho PWA dù có `sw.js` (public/sw.js) — "lớp vỏ" browser còn thiếu chứ không chỉ favicon.
8. **`--info` và `--info-soft` không được nêu ở phần Khoảng trống như một token chết tiềm năng** — N-4 có nhắc nhưng không đưa vào khuyến nghị sửa.
9. **`og.png` là ảnh tĩnh dùng chung cho MỌI plan** — plan/[token]/page.tsx:6 dùng cùng `og.png` 1200×630 cho mọi token; chia sẻ mọi kế hoạch đều hiện cùng một hình brand chung — không có ảnh đại diện theo từng plan. Synthesis chỉ nêu "landing không có og", bỏ qua "mọi plan cùng một ảnh".
10. **`consent` "phiên bản 2026-08-05" hardcode trong bản dịch** (LocaleProvider:33) — date cúng trong string, không phải metadata — thẩm mỹ pháp lý, không ai nêu.

---

## Điểm thẩm mỹ của riêng bạn (red-team)

**7.0/10.**

Lý do:
- **Nền tảng thực sự tốt (giữ nguyên đánh giá synthesis):** token hệ 26 biến, dark inversion "đèn pha" có chủ đích, easing duy nhất, focus-visible 3px chuẩn, micro-detail (counter decimal-leading-zero, ring kép slot selected, dashed border last-updated, bubble gương đuôi 6px, sticky nav glare-fix @supports). Đây là tầng rất khó tạo và hiếm ở MVP. **Đáng 8/10 riêng.**
- **Trừ điểm vì:** (a) 3-4 lỗi contrast dark thật (1.83/2.04/1:1) ở đúng nút quan trọng — dù chỉ ở chế độ không mặc định, vẫn là vết nứt nhìn thấy; (b) font thương hiệu không tải — bản sắc typographic chưa hiện thực; (c) không favicon/og/404 — "lớp vỏ" trình duyệt/SEO rỗng, ai nhìn tab cũng thấy; (d) tầng trạng thái (busy/error/loading) chỉ là text — cảm giác "nửa vời"; (e) admin là mặt tiền thô nhất dù nội bộ.
- **Không trừ nhiều hơn vì:** đây là MVP demo (README:1,3,53-60), light mode (mặc định) không vỡ bố cục nào, hầu hết "lỗi" là polish; và phần lớn khiếu nại của synthesis (spacing, brand, lavender) là gu. Tôi không đồng ý với 6.5 vì 2 "Blocker" thực chất là High và 5 "lỗi bố cục thật" nằm trong admin nội bộ — không ảnh hưởng người dùng chính.

So với trung bình lane 6.7, tôi đặt **7.0**: cao hơn synthesis một chút vì tôi không trừ điểm cho các mục gu, thấp hơn 8 vì nền móng tốt chưa được hiện thực đều (font, dark nút, vỏ browser).

---

**Confidence: 8/10**

**Ground-truth tally: 36/42 kết luận quan trọng được tôi tự kiểm chứng bằng công cụ/code:**
- (a) Tính lại contrast bằng Python (WCAG): white-on-`#cdb3ff`=1.83 ✓, white-on-`#ff9b8a`=2.04 ✓, `#926cd6`-on-white=3.93 ✓, `#cdb3ff`-on-white=**1.83** (khác con số 1.4:1 trong 01/synthesis — phát hiện sai số), `#cdb3ff`-on-`#1f1222`=9.84 (nút chat vẫn thấy rõ — luận điểm "biến mất" sai), `#7f7482`-on-paper=4.11 ✓, `#948b96`-on-white=3.29 ✓, `#a99fae`/`#ae86f7`-on-`#141014`=7.41/6.78 ✓, `#cdb3ff`-on-`#2a182e`=9.06 ✓, `#ae86f7`-on-white=2.78 (01 ghi 2.57 — lệch nhỏ).
- (b) Grep khối dark globals.css:43 — 0 override cho `.chat-box button`, `.cta-banner`, `.danger`, `::selection`, `shimmer`, `.planner::before`; **có** `.icon-action:hover` nhưng gán lavender/ink-3 (1:1) ✓.
- (c) Đếm token: `--lavender`=65, `--accent`=32, `--sun`=6, `--green`=8, `--danger`=10, `--info`=4 ✓.
- (d) `<main>` lồng: layout.tsx:9 + 10 trang + PlanView:119 (synthesis ghi 9/9 — đếm thiếu admin) ✓.
- (e) Admin: 5 card trong `repeat(4,1fr)` (admin:368-372, globals.css:40) ✓; offer-card thiếu `card` (:569 vs explore:66/support:62) ✓; "Huy" trần (:580) ✓; `toLocaleString("vi-VN")` (:560,575,596) — blind spot mới.
- (f) Roadtrip withInventory 8 phần tử trong grid 5 cột (roadtrip:56, globals.css:31) ✓.
- (g) PlanView message/busy đều `.status`+`role="status"` (:122); key lỗi gán :90,100-113 ✓; 9 nút trip-header (:120) ✓; slotPhoto không `.loading` (:117) ✓; day-tabs không aria-selected (:127, vs explore:60 role=tablist+aria-selected) ✓.
- (h) RTL: dir trong useEffect (LocaleProvider:101), `lang="vi"` hardcode (layout:9), 0 `[dir]` trong globals.css ✓.
- (i) Font/favicon/meta: 0 match `next/font|@font-face|fonts.googleapis`; app/ không có icon/not-found/loading/error; public/ chỉ og.png+sw.js; layout không openGraph; plan/[token]:6 dùng og.png — mọi plan share chung 1 ảnh (blind spot mới) ✓.
- (j) `.bubble.typing`/`typingPulse` (:22) và `.slot-photo.loading`/shimmer (:25) không được render (grep + PlanView:117) ✓; `creatingPlan` (LocaleProvider:75) không dùng ✓.
- (k) 19 locale khai báo (i18n-core.ts:1) gồm ar/he ✓; `undoSuccess` unused ✓.
- (l) Login button có hậu tố "· local" mọi locale (LocaleProvider:33-51) — blind spot mới ✓; attribution "Ac OpenStreetMap contributors" (MapView:28, RoadTripMap:17) — blind spot mới ✓.
- (m) README.md:1,3,53-60 xác nhận MVP demo, AI_MODE=mock mặc định, không triển khai công khai trước PoC — làm giảm mức Blocker ✓.
- 6/42 còn lại là nhận định thẩm mỹ chủ quan: điểm 7.0 của tôi, xếp hạng lại Blocker→High, "gu vs bug" ở M-1/H-11/H-12/H-26, mức ảnh hưởng RTL, và việc M-1 mâu thuẫn nội bộ với điểm mạnh gradient của 01.
