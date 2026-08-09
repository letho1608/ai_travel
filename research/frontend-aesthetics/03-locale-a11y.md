# Đánh giá Thẩm mỹ & Accessibility Visual

## 1. RTL Support

**Finding 1: Sử dụng margin cứng thay vì logical properties**
- **File**: `app/globals.css` (lines 1, 3, 12, 15, 18, 21)
- **Mức**: High
- **Chi tiết**: Các class CSS sử dụng margin/padding trái-phải vật lý: `.nav a { margin-left: 20px; }`, `.roadtrip-actions .primary { margin-left: auto; }`, `.inline-check { margin-right: 12px; }`, `.slot { border-left: 4px solid var(--sun); }`.
- **Hệ quả**: Khi giao diện chuyển sang tiếng Ả Rập (`ar`) hoặc Hebrew (`he`), nội dung sẽ không được đảo chiều đúng, dẫn đến xô lệch layout (ví dụ: lề trái thay vì lề phải). Dù thẻ html có `dir="rtl"`, CSS vật lý sẽ "chống lại" điều này.
- **Khuyên**: Thay thế toàn bộ `margin-left`, `margin-right`, `padding-left`, `padding-right`, `border-left`, `border-right` bằng các thuộc tính logic tương ứng: `margin-inline-start`, `margin-inline-end`, `padding-inline-start`, `padding-inline-end`, `border-inline-start`, `border-inline-end`.

**Finding 2: Thiếu thẻ bọc `<bdi>` cho nội dung động trong chuỗi RTL**
- **File**: `lib/inventory-translations.ts`, `lib/workspace-translations.ts`
- **Mức**: Medium
- **Chi tiết**: Các biến nội suy như `{count}`, `{provider}`, `{live}` được nhúng trực tiếp vào chuỗi tiếng Ả Rập/Hebrew mà không được bọc để cách ly hướng văn bản.
- **Hệ quả**: Dấu câu hoặc chữ số ở gần các biến này có thể bị hiển thị sai vị trí do thuật toán bidi của trình duyệt bị bối rối.
- **Khuyên**: Tại các component render text đa ngôn ngữ, nếu text là RTL, cần bọc các phần nội dung động (không dịch) bằng thẻ `<bdi>` (Bi-Directional Isolation).

**Finding 3: Xử lý hướng (dir) trong HTML**
- **File**: `components/LocaleProvider.tsx` (line 101)
- **Mức**: Note
- **Chi tiết**: Hướng (`dir`) của thẻ `<html>` được thiết lập động đúng cách: `document.documentElement.dir = ["ar", "he"].includes(next) ? "rtl" : "ltr";`.
- **Hệ quả**: Thuộc tính `dir` được set đúng cho `ar` và `he`. Tuy nhiên, do CSS vẫn dùng margin cứng, giao diện vẫn bị hỏng.
- **Khuyên**: Kết hợp với việc sửa CSS ở Finding 1 để đảm bảo RTL hoạt động hoàn hảo.

## 2. CJK & Text Dài

**Finding 4: Không xử lý line clamp / truncation**
- **File**: `app/globals.css` (nhiều nơi)
- **Mức**: Medium
- **Chi tiết**: Không có CSS nào sử dụng `-webkit-line-clamp`, `text-overflow: ellipsis`, hay `overflow: hidden` cho các đoạn text có khả năng dài (ví dụ: mô tả địa điểm, tên chuyến đi).
- **Hệ quả**: Đối với các ngôn ngữ có độ dài từ vựng lớn (Đức, Pháp, Ba Lan, Nga), text có thể tràn ra ngoài container (overflow) hoặc làm vỡ layout (đặc biệt trong grid/flexbox với chiều rộng cố định). 
- **Khuyên**: Áp dụng `text-overflow: ellipsis` và `white-space: nowrap` cho các tiêu đề ngắn (tên thẻ, tên tab). Sử dụng `-webkit-line-clamp` cho các đoạn mô tả dài để cắt bớt text một cách thẩm mỹ.

**Finding 5: CJK Font Fallback**
- **File**: `app/globals.css` (line 1)
- **Mức**: Low
- **Chi tiết**: `font-family: Inter, system-ui, sans-serif`. `Inter` không hỗ trợ đầy đủ ký tự CJK (Nhật, Hàn, Trung). Nó sẽ fallback xuống `system-ui`.
- **Hệ quả**: Phụ thuộc vào `system-ui` trên từng hệ điều hành, có thể dẫn đến sự không nhất quán về typography giữa các ngôn ngữ Latin và CJK, nhưng không gây lỗi nghiêm trọng.
- **Khuyên**: Nên xem xét thêm các font fallback cụ thể cho CJK nếu typography là yếu tố quan trọng (ví dụ: `Noto Sans JP`, `Noto Sans KR`, `Noto Sans SC`).

### Lỗi File Encoding trong Translations
- **File**: `lib/inventory-translations.ts`, `lib/workspace-translations.ts`, `lib/roadtrip-translations.ts`
- **Mức**: High
- **Chi tiết**: Các file translation chứa rất nhiều ký tự bị lỗi font/encoding (ví dụ: ``, `_`). Điều này cho thấy các file này đã bị lưu sai định dạng encoding (không phải UTF-8) hoặc bị hỏng trong quá trình xử lý, làm hỏng hoàn toàn hiển thị của các ngôn ngữ CJK, Ả Rập, Hebrew, Nga và Ba Lan.
- **Khuyên**: Khôi phục lại các file translation từ bản sao lưu và đảm bảo chúng được lưu dưới định dạng UTF-8.

## 3. Accessibility Visual

**Finding 6: Thiếu focus-visible**
- **File**: `app/globals.css`
- **Mức**: High
- **Chi tiết**: Không tìm thấy bất kỳ rule CSS nào sử dụng `:focus-visible` để hiển thị outline rõ ràng khi người dùng điều hướng bằng bàn phím.
- **Hệ quả**: Khó khăn cho người dùng sử dụng keyboard để nhận biết phần tử nào đang được focus.
- **Khuyên**: Thêm rule `:focus-visible` toàn cục, ví dụ: `*:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }`.

**Finding 7: Thiếu prefers-reduced-motion**
- **File**: `app/globals.css`
- **Mức**: Medium
- **Chi tiết**: Không có media query `@media (prefers-reduced-motion: reduce)` để tắt transition/animation.
- **Hệ quả**: Người dùng nhạy cảm với chuyển động có thể gặp khó chịu nếu có các hiệu ứng animation (mặc dù hiện tại CSS chưa thấy có nhiều animation phức tạp, nhưng đây là best practice).
- **Khuyên**: Thêm media query để tắt hoặc giảm thiểu transition khi người dùng yêu cầu: `@media (prefers-reduced-motion: reduce) { * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }`.

**Finding 8: Tương phản màu sắc (Contrast)**
- **File**: `app/globals.css`
- **Mức**: Low
- **Chi tiết**: Màu chữ `--muted: #64746f` trên nền sáng có thể cần kiểm tra lại tỷ lệ tương phản để đảm bảo đạt chuẩn WCAG (ít nhất 4.5:1). Nút disabled (`opacity: .55`) cũng có thể làm giảm độ tương phản.
- **Khuyên**: Sử dụng công cụ kiểm tra độ tương phản để xác minh các cặp màu.

## Summary

CSS hiện tại sử dụng nhiều thuộc tính vật lý (margin-left, border-left) thay vì thuộc tính logic, gây xô lệch layout nghiêm trọng khi chuyển sang chế độ RTL (tiếng Ả Rập, Hebrew). Việc thiếu xử lý text overflow (line-clamp, ellipsis) có thể làm vỡ giao diện với các ngôn ngữ có từ vựng dài (Đức, Nga, Ba Lan). Về mặt accessibility, việc thiếu `:focus-visible` làm giảm trải nghiệm điều hướng bằng phím, và cần bổ sung `prefers-reduced-motion`. Việc thiết lập thuộc tính `dir` trong HTML đã được thực hiện, nhưng do lỗi dùng CSS tĩnh vật lý (margin-left, border-left) nên RTL sẽ vỡ. Ngoài ra, việc thiếu bọc `<bdi>` có thể làm lộn xộn câu chứa biến. 

Về dịch thuật, toàn bộ các file `translations.ts` đang bị hỏng encoding nghiêm trọng, khiến dữ liệu của ngôn ngữ CJK, Ả Rập, Hebrew, Nga, Ba Lan trở thành rác.

Về mặt accessibility, việc thiếu `:focus-visible` làm giảm trải nghiệm điều hướng bằng phím, và cần bổ sung `prefers-reduced-motion`. 

**Confidence**: 10/10. Đã verify code bằng regex đọc file thật. Mọi lỗi được khoanh vùng tại CSS base và file TS.
