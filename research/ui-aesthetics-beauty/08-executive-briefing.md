# 08 — Executive briefing: Độ đẹp giao diện "Mình Đi Đâu Thế"

Phân tích 100% về **độ đẹp thị giác** (không phải chức năng). Chạy deep-dive Standard: 5 specialist song song → synthesis → red-team đối kháng, với **ảnh chụp thật** từ trang đang chạy (Edge headless 151, pixel analysis + DOM measurement) chứ không chỉ đọc code.

---

## Bottom line

**Giao diện hiện tại: 4.5/10 về độ đẹp.** Bộ xương thiết kế (design tokens) là **7/10** — thực sự tốt trên mức trung bình của sản phẩm AI — nhưng **cái người dùng nhìn thấy chỉ đạt một nửa tham vọng đó**. Lý do không nằm ở ý tưởng thẩm mỹ mà ở 3 lỗi "trình diễn" khiến mọi trang đều kém đẹp hơn khả năng thật sự:

1. **Font chưa bao giờ được tải** — toàn bộ app hiển thị bằng Segoe UI (font mặc định Windows) thay vì Inter/Fig Grotesk đã khai báo. Đây là lý do số 1 khiến mọi tiêu đề trông "thường".
2. **Chế độ sáng (mặc định) trống 95%** — card trắng trên nền trắng, viền và shadow gần như không thấy → giao diện nhìn như trang chưa xong.
3. **Trang plan (màn hình chính) bị lỗi tràn ngang** — thanh cuộn ngang hiện ra mỗi lần mở, map bị cắt mép phải.

Điểm 5: **đáng đầu tư làm đẹp ngay** — đây là sản phẩm "đánh bóng là đẹp" chứ không phải "đập đi xây lại".

---

## Những thứ thực sự đẹp (đừng đụng vào)

- **Bảng màu tím lavender trên nền giấy ấm** — một điểm nhìn thẩm mỹ rõ ràng, không phải template AI (`globals.css:1`)
- **Hệ shadow pha màu mận + vòng halo lavender** — ngôn ngữ đổ bóng đẹp nhất trong app
- **Grid từng slot lịch trình** — số thứ tự / giờ / tiêu đề / mô tả căn chỉnh rất tinh tế (`globals.css:25`)
- **Hero landing** — tỉ lệ 1.05/0.95, headline 88px, tracking -0.035em, card planner có thanh gradient 6px
- **Footer tím đậm** (chế độ sáng) — khoảnh khắc màu mạnh nhất của cả app
- **Motion nhất quán** — 120–200ms cùng một ease curve, tôn trọng `prefers-reduced-motion`

---

## Tier 0 — phải sửa (5 việc, "đòn bẩy đẹp" lớn nhất)

| # | Vấn đề | Sửa thế nào | Vị trí |
|---|---|---|---|
| 1 | **Font không tải** (toàn bộ UI là Segoe UI) | Thêm `next/font/google` Inter (+ Fig Grotesk) hoặc tự host `@font-face` | `layout.tsx`, `package.json` |
| 2 | **Trang plan tràn ngang ~8px** | **Bỏ full-bleed `width:100vw`**; dùng `margin:0 auto;width:min(100%,1500px)` — **đã test thật trong browser, xác nhận hết lỗi** (KHÔNG dùng `margin-inline:calc(50%-50vw)` hay `scrollbar-gutter:stable` — đã test, không ăn) | `globals.css:25` |
| 3 | **Map vẫn dùng màu brand cũ** (xanh teal `#0f766e`, cam `#e4572e`) — lạc giọng với palette tím | Đổi sang token: `var(--accent)`, `var(--sun)`/`var(--danger)` | `MapView.tsx:37,49`; `RoadTripMap.tsx:15-16` |
| 4 | **Dark mode: bôi đen chữ không thấy** (lavender on lavender) | Thêm `::selection{background:var(--lavender);color:var(--brand-contrast)}` trong khối dark | `globals.css:43` |
| 5 | **Dark mode: CTA banner là khối sáng vỡ** (chữ trắng trên nền tím nhạt ~1.35:1) | Thêm override `.cta-banner` + `.cta-banner .primary` riêng cho dark | `globals.css:16,43` |

## Tier 1 — nên sửa trước khi mở rộng

- **Card mất viền trong chế độ sáng** → tăng `--shadow-sm` lên ~0.08 alpha + dịch 2px, tối `--line` lên 1 nấc (`globals.css:1`)
- **Admin booking queue hiện dạng text trần** (thiếu class `.card`) — vẫn chưa sửa từ audit trước (`admin/page.tsx:569`)
- **Mọi tiêu đề trang trong đều 62px** (5 cái clamp bị chết do `main:not(.hero)>h1`) — xóa clamp chết hoặc nâng specificity
- **`font:inherit` làm input mất line-height đẹp**; **`body`/`h1`/`small` không có font-size** (leak UA default 18.72px/13.33px)
- **History empty state chỉ là một dòng chữ xám** trên nền footer tím to chiếm 37% màn hình đầu
- **Không có scale kích thước nút** — 5 kiểu height tự chế (53/46/49/43/38px)
- **`.primary{width:100%}` mặc định** — mọi nơi phải opt-out (bom chờ nổ)

## Tier 2 — polish (làm sau)

Type scale vô tổ chức (13–20px + nhảy vọt 20→44→46→88, h2 44px và 46px đụng nhau); không có token spacing (14 giá trị tay, có số lẻ 18/26/15/11/38px); 5 kiểu line-height khác nhau; icon Unicode ↑↻× lệch tâm; nút "Hủy" bản năng chưa style; roadtrip phơi tọa độ lat/lng; explore page trống hoác (1 form trên 1152px).

## Tier 3 — quyết định sản phẩm

Dark-first hay light-first (hiện đọc theo hướng dark nhưng mặc định light); de-collide token dark (brand=lavender=ink-3 cùng 1 màu làm gradient chết); footer tan vào nền trong dark mode.

---

## Bằng chứng thực tế (ground truth)

- Đo **browser thật** (Edge 151, CDP): `document.fonts` = **0 font Inter**; body = Segoe UI
- Pixel: light mode 94–96% vùng trắng, độ bão hòa 0.03–0.05 (gần như không màu)
- Đo DOM: landing 139 phần tử/text 1658 → trang dài 3095px; explore chỉ 80 phần tử (trang gần như trống)
- Trang plan: scrollWidth **1407** > clientWidth **1399** → scrollbar ngang; tại 1920px bị **lệch trái, hở 402px bên phải** (không cân giữa)
- Đã **test 4 cách sửa overflow trong browser**: chỉ 1 cách (bỏ full-bleed) thực sự hết lỗi
- H1 toàn site = **62px** (login/settings/explore/roadtrip/admin đều vậy, plan 50.9px) — 5 clamp khai báo 72/52/66px đều chết

## Điểm từng trang (theo ảnh thật)

| Trang | Điểm | Lý do chính |
|---|---|---|
| Landing | **7.0** | Hero + planner card + 88px headline — trang duy nhất "có ý đồ" |
| Plan | **6.5** | Grid slot tốt, map đẹp — nhưng overflow 8px + font fallback |
| Settings | **5.0** | Sạch, tối giản, không lỗi — nhưng vô hồn |
| Login | **4.5** | Đầu trang quá rỗng, footer tím chiếm 25% viewport |
| Admin | **4.5** | Text trần, không card, không ảnh chụp (chỉ đọc code) |
| Explore | **3.5** | 1 form trên canvas trống — không có gì khác |
| Roadtrip | **3.0** | Form kỹ thuật (tọa độ thô), không có hình ảnh |
| History | **2.5** | "Chưa có chuyến đi nào." một dòng + khối footer tím 37% |

---

## Confidence: **7.5/10**

**Ground-truth tally:** **16/22** kết luận chính được kiểm chứng bằng dữ kiện bên ngoài (đọc code thật, đo browser thật, test fix thật trong trình duyệt); **6/22** là phán đoán thẩm mỹ chủ quan (thang điểm trang, mức độ nghiêm trọng). Vì phần quyết định (điểm đẹp, thứ tự ưu tiên) có thành phần chủ quan đáng kể, không nâng quá 7.5/10.

Điều gì có thể đổi số: chụp đúng dark mode với token state rõ; đo trên 3+ thiết bị thật (Mac/Linux cho khác font fallback); người dùng thật nhận xét.

---

## Nên làm gì tiếp theo

**Có, đáng đầu tư làm đẹp.** Trả lời thẳng: app có DNA thẩm mỹ tốt nhưng 3 lỗi trình diễn đang giấu nó. Làm **5 việc Tier 0** (~1–2 giờ): tải font, bỏ full-bleed lỗi, đổi màu map, fix 2 lỗi dark mode — đó là cú nhảy đẹp lớn nhất có thể có. Nói "bắt đầu làm đi" và tôi áp dụng trực tiếp vào code.
