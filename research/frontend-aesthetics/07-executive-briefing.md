# Executive Briefing: Đánh giá Thẩm mỹ & Trải nghiệm Giao diện Frontend

**TL;DR:** Giao diện hiện tại là một **bản nháp chức năng sạch sẽ** hơn là một **sản phẩm thương mại được đánh bóng**. Kiến trúc tốt (vùng bấm rộng, hierarchy rõ, màu Teal hiện đại, typography responsive), nhưng **thiếu hoàn toàn lớp "polish"**: không micro-interaction, không transition, không skeleton, magic numbers dày đặc, và có 2 lỗi vỡ layout (RTL, contrast).

**Điểm thẩm mỹ tổng thể: 6/10** — nền tốt, thiếu sức sống.

**Confidence: 8/10.**
*(Ground-truth tally: 6/6 load-bearing conclusions được verify bằng đọc file CSS/component thật + tính toán luminance thủ công; 0 phụ thuộc phán đoán thuần.)*

---

## 1. Điểm sáng thật (đáng giữ)
- **Vùng bấm mobile rộng**: `.slot-select` phủ toàn thẻ, chip/nút dễ nhấn — tốt hơn nhiều app.
- **Màu chủ đạo Teal #0f766e** xuyên suốt, hiện đại và đáng tin.
- **Typography responsive** (`clamp(44px,7vw,82px)`) co giãn mượt.
- **Cấu trúc workspace** (itinerary / map / chat) có thứ bậc rõ, không nhiễu.

---

## 2. Vấn đề cốt lõi (xếp theo ưu tiên)

### Tier 0 — BLOCKER (vỡ giao diện, phải sửa)
1. **RTL vỡ hoàn toàn** — `globals.css` dùng margin/padding vật lý (`margin-left`, `border-left`) thay vì logical properties. Tiếng Ả Rập/Hebrew (được hỗ trợ chính thức) bị ngược lề, xô lệch. *(`.nav a`, `.inline-check`, `.slot`)*

### Tier 1 — HIGH (xấu rõ, ảnh hưởng cảm nhận)
2. **Không có transition/micro-interaction** — mọi thứ tức thời, giật cục. Nhấn nút không có phản hồi scale, hover không mượt.
3. **Contrast chưa đạt WCAG AA** — `--muted: #64746f` trên nền sáng ≈ **4.34:1** (chuẩn cần 4.5:1). *(Tính từ luminance, verified)*
4. **Thiếu `:focus-visible`** — người dùng keyboard khó nhận biết vị trí focus.
5. **Landing "bộ mặt" trống trải** — app du lịch nhưng không có hình ảnh điểm đến, không logo/branding. *(Red-team gợi ý hạ xuống Medium nếu ưu tiên chức năng — tùy chiến lược.)*

### Tier 2 — MEDIUM (thiếu tinh tế)
6. **Magic numbers dày đặc** (7px, 11px, 13px, 22px) — không theo grid chuẩn.
7. **Dark Mode hardcode** — nút `.primary` giữ màu tối `#0f766e` trong dark, bị chìm; gradient thừa.
8. **Thiếu line-clamp/truncation** — ngôn ngữ dài (Đức, Ba Lan, Nga) có thể tràn khung.
9. **Không skeleton/typing indicator** — ảnh và chat AI chờ tĩnh.
10. **Drawer cứng nhắc** — không animation slide.

### Tier 3 — LOW/Note (best practice)
- Scrollbar mặc định thô (Windows), z-index chưa token, thiếu `prefers-reduced-motion`, thiếu `<bdi>` cho biến RTL, Leaflet marker quá basic, `.inventory-tabs` mobile có thể tràn (thiếu `overflow-x: auto`).

---

## 3. Khuyến nghị hành động (impact/effort)

| Bước | Việc | Công sức | Tác động |
|---|---|---|---|
| 1 | Sửa margin/padding → logical properties (RTL) + `--muted` đậm hơn + transition cơ bản + `:focus-visible` | ~15 phút (CSS) | Cao — gỡ Blocker + High |
| 2 | Dọn dark mode (nút primary dùng `var(--brand)`) | ~20 phút | Trung |
| 3 | Skeleton shimmer + typing 3-dot + custom scrollbar | ~30 phút | Cao — cảm giác "sống" |
| 4 | Hero image + logo | ~1-2h | Cao cho landing |
| 5 | Refactor design tokens (grid 4px, shadow scale) | Dài hạn | Giảm nợ kỹ thuật |

**Nên làm ngay (gói Tier 0-1):** RTL, contrast, transition, focus-visible — chỉ là CSS thuần, rủi ro thấp, nâng thẩm mỹ và accessibility rõ rệt.

*Toàn bộ báo cáo chi tiết theo từng góc (design system, interaction, locale/a11y, landing) nằm trong `research/frontend-aesthetics/01-06*.md`.*
