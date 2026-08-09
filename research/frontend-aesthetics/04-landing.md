# Đánh giá Thẩm mỹ Trang chủ (Landing / Hero) & Ấn tượng Thương hiệu

## 1. Tổng quan

Trang chủ là một hero **một màn hình** gọn gàng: eyebrow + h1 lớn (clamp đến 82px) + lead + Planner (chat-welcome). Kiến trúc đơn giản, không nhiễu, có chiều sâu nhờ `.planner` box-shadow mềm và nền gradient nhẹ. Tuy nhiên thiếu yếu tố "wow" (hình ảnh/illustration/hero visual), thiếu nhận diện thương hiệu rõ (không logo), và hero chưa tận dụng khoảng trống để tạo kịch tính.

**Verdict: 6.5/10** — sạch, dễ hiểu, nhưng chưa có "cú đấm" thị giác đầu tiên.

## 2. Phát hiện

### Finding 1: Hero thiếu visual "wow" — HIGH
- **Vị trí**: `app/page.tsx` (`.hero`), `app/globals.css`.
- **Mô tả**: Hero chỉ có text + form chat. Không có ảnh đại diện điểm đến, gradient/illustration nền, hoặc animated element. Với một app du lịch — sản phẩm trực quan — trang đầu tiên không gợi được cảm xúc "muốn đi".
- **Khuyên**: Thêm hero image (Ảnh Hà Nội/điểm đến từ `data/places.json`) với overlay gradient, hoặc một mini collage 3 ảnh phía sau/trên Planner.

### Finding 2: Entry point tốt nhưng chưa tối ưu — MEDIUM
- **Vị trí**: `components/Planner.tsx` (chat-welcome).
- **Mô tả**: Chat-welcome bubble + chips gợi ý là điểm vào rõ ràng và mời gọi (điểm mạnh). Tuy nhiên bubble `chatWelcome` dài, không có nút CTA lớn; người dùng mobile phải scroll để thấy form nhập.
- **Khuyên**: Đưa chat-box lên gần `h1` hơn, hoặc hero tạo flow một cột thẳng đứng giữa màn hình.

### Finding 3: Thiếu nhận diện thương hiệu (logo/branding) — MEDIUM
- **Vị trí**: `app/layout.tsx`, `components/Navigation.tsx`, `app/globals.css`.
- **Mô tả**: Không có logo hoặc wordmark đặc biệt — chỉ có text nav. `.eyebrow` có chữ nhưng không phải branding. Màu teal #0f766e là điểm nhận diện duy nhất.
- **Khuyên**: Tạo logo đơn giản (icon bản đồ + chữ) hoặc ít nhất làm `.eyebrow` trở thành brand-mark nhất quán.

### Finding 4: Typography hero tốt, thiếu hệ thống nhấn — LOW
- **Vị trí**: `app/page.tsx`, `app/globals.css` (`h1 { clamp(44px,7vw,82px) }`).
- **Mô tả**: `clamp` responsive tốt. Nhưng không có font-display riêng (đậm hơn) cho hero, không có letter-spacing cho eyebrow, không có accent color cho từ khoá (vd "Hà Nội" tô teal/orange).
- **Khuyên**: Tô accent `#e4572e` cho từ khóa chính trong `heroTitleSecond`, thêm `letter-spacing` cho `.eyebrow`.

### Finding 5: Footer/legal thiếu đồng bộ thẩm mỹ — LOW
- **Vị trí**: `app/layout.tsx` (footer), `app/globals.css` (`.legal-footer`).
- **Mô tá**: Footer đơn giản và OK, nhưng text bị màn hình hiển thị sai tiếng Việt trong console (không phải lỗi file). Không có `border-top` tách biệt rõ với content.

### Finding 6: Dark mode hero chưa tận dụng — NOTE
- **Vị trí**: `app/globals.css` dark block.
- **Mô tả**: Hero dark mode đổi gradient nền nhưng Planner shadow `0 24px 70px #00000055` rất đậm — có thể tạo cảm giác card "nổi hẫng". Cần shadow mềm hơn trong dark.

## 3. Tổng kết

Trang chủ **sạch, tập trung, dễ hiểu** — điểm vào chat là một ý tưởng tốt. Nhưng như một landing page của app du lịch, nó **thiếu yếu tố cảm xúc**: không hình ảnh điểm đến, không nhận diện thương hiệu, không micro-delight ở hero. Ưu tiên: thêm hero visual + logo + accent màu để có "first impression" đáng nhớ.

**Confidence: 7/10** — dựa trên đọc component + CSS thật; phần "cảm nhận visual" có tính chủ quan, không render thật trong browser.
