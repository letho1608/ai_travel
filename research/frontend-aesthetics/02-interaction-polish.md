# Đánh giá Thẩm mỹ Giao diện & Chất lượng Thao tác (UI/UX Polish & Micro-interactions)

## 1. Tổng quan

Giao diện cơ bản gọn gàng, đặc biệt làm tốt vùng bấm mobile (`.slot-select` toàn bộ thẻ, `.chip`, `.icon-action`) và cấu trúc workspace (itinerary / map / chat) có thứ bậc rõ ràng. Tuy nhiên, toàn bộ mảng **micro-interaction gần như trống**: thiếu transition, thiếu phản hồi nhấn, thiếu skeleton/typing indicator. Trải nghiệm thao tác hiện "cứng ngắc" và ít cảm giác "sống".

**Verdict: 6/10** — nền tốt, thiếu polish tầng tinh tế.

## 2. Phát hiện (Findings)

### Finding 1: Thiếu transition trên mọi thành phần tương tác — HIGH
- **Vị trí**: `app/globals.css` toàn bộ (không có rule `transition` nào cho button/chip/tab/card/slot).
- **Mô tả**: Hover/focus/active của nút (`.primary`, `.secondary`, `.chip`, `.day-tabs button`) đổi trạng thái **tức thời**, không có chuyển tiếp êm. Nhấn nút không có phản hồi `transform: scale(0.98)`.
- **Khuyên**: Thêm baseline `button, a, .chip, .card, .slot { transition: background-color .2s ease, border-color .2s ease, box-shadow .2s ease, transform .15s ease; }` và `:active { transform: scale(.98); }`.

### Finding 2: Không có loading skeleton / typing indicator — MEDIUM
- **Vị trí**: `components/PlanView.tsx` (slotPhoto), `components/Planner.tsx` (busy state), `components/MapView.tsx`.
- **Mô tả**: Khi ảnh `.slot-photo` đang tải từ Wikimedia, hiển thị nền phẳng `#e8f0ec` — không có shimmer/skeleton. Chat AI chỉ có text `"Đang xử lý..."` qua aria-live, không có bubble typing animation. Bản đồ Leaflet render nền xám tĩnh trong lúc tiles tải.
- **Khuyên**: Thêm `.slot-photo::before` shimmer gradient; thêm bubble typing 3 dot cho assistant khi `busy==="refine"`; Leaflet có sẵn `loadingControl` hoặc overlay skeleton.

### Finding 3: Drawer (versions/comments) dạng block cứng, không slide — MEDIUM
- **Vị trí**: `components/PlanView.tsx` (`.version-drawer`, `.comment-drawer`), `app/globals.css`.
- **Mô tả**: Drawer xuất hiện/ẩn tức thời (conditional render), không có animation slide-in, không có backdrop, mobile không có gesture đóng. Cảm giác "bật tắt" thay vì "trượt mở".
- **Khuyên**: CSS `@keyframes slide-down { from { opacity:0; transform: translateY(-8px);} }` cho drawer; thêm backdrop + nút đóng X.

### Finding 4: Trạng thái error/status quá phẳng — MEDIUM
- **Vị trí**: `components/PlanView.tsx` (`.status`, `.error`), `components/Planner.tsx` (`.retry-panel`).
- **Mô tả**: Thông báo lỗi/thành công là text một dòng đổi màu, không có icon, không animation fade-in, `.retry-panel` không tách biệt về mặt visual với phần còn lại.
- **Khuyên**: Thêm icon (✓/⚠), `fade-in` nhẹ, đặt status trong `role="status"` có `transition`.

### Finding 5: Tab/chip không có hover state khác biệt — LOW
- **Vị trí**: `.day-tabs button`, `.inventory-tabs button`, `.chip`.
- **Mô tả**: Hover chỉ đổi màu chữ/border nhẹ, không đủ nhận diện; `aria-pressed`/`aria-selected` không đi kèm visual accent đậm.
- **Khuyên**: Thêm `:hover` tăng độ đậm nền, `:focus-visible` outline brand.

### Finding 6: Dark mode chuyển tức thời, không mượt — LOW
- **Vị trí**: `app/globals.css` block `@media (prefers-color-scheme: dark)`.
- **Mô tả**: Khi hệ điều hành đổi theme, toàn bộ màu nền nhảy đột ngột do không có `transition: background-color .3s ease, color .3s ease` trên `body, .card, .planner, .slot`.
- **Khuyên**: Thêm transition màu nền cho các surface chính (vẫn tôn trọng `prefers-reduced-motion`).

### Finding 7: Nút ↑ (send) thiếu affordance rõ — NOTE
- **Vị trí**: `components/Planner.tsx`, `components/PlanView.tsx` (nút `↑`).
- **Mô tả**: Nút gửi dùng ký tự `↑` thô, không có hình dạng tròn/icon SVG, aria-label có nhưng visual ít gợi ý hành động gửi.
- **Khuyên**: Dùng icon SVG arrow-up trong `border-radius:999px` button.

## 3. Tổng kết

Điểm mạnh: vùng bấm rộng, hierarchy workspace tốt, empty/disabled states có. Điểm yếu cốt lõi: **không có lớp chuyển động/phản hồi** — mọi thứ tức thời. Bổ sung transition baseline + 3 micro-interaction (typing, skeleton, drawer slide) sẽ nâng cảm giác polished rõ rệt mà tốn rất ít công.

**Confidence: 8/10** — dựa trên đọc trực tiếp component + CSS thật (chưa render thật trong browser để quan sát motion).
