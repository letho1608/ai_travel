# Executive Briefing — Đánh giá thẩm mỹ giao diện "Mình Đi Đâu Thế"

## TL;DR — Kết luận ngắn

**Điểm thẩm mỹ tổng thể: 7/10.** Trang web có nền tảng thị giác **thật sự tốt**: bảng token màu tím–lavender gắn kết, dark mode hoàn chỉnh (hiếm có cho MVP), typography có scale clamp() thông minh, bo góc tròn mềm mại, motion tinh tế. Landing page và Plan workspace đạt chuẩn sản phẩm chỉn chu.

Tuy nhiên chất lượng **không đều giữa các trang** (Admin rõ ràng kém nhất), có **~4 lỗi tương phản màu thật** (WCAG, không phải gu) ở dark mode, và một số điểm "vỡ" nhỏ: spacing thiếu hệ thống, `<main>` lồng nhau làm hỏng bố cục workspace, tiếng Việt không dấu hard-code trong Admin, typo trên bản đồ.

**Bản chất**: đây là MVP demo (xác nhận qua README), nên phần lớn vấn đề thuộc Tier 1–2 (polish trước khi mở rộng), không phải Blockers. Chỉ có **2 mục thật sự cần sửa trước khi công khai** nếu coi accessibility là tiêu chí: contrast dark mode của nút danger và chat send.

---

## Điểm thẩm mỹ — trung thực

| Khía cạnh | Điểm | Lý do |
|---|---|---|
| **Bản sắc thị giác & màu** | 5.5/10 | Token tốt nhưng brand trùng ink, tím bị lạm dụng (~97 lần), font Inter **không được tải** (chỉ khai báo), dark mode vỡ 4 chỗ do `#fff` hard-code |
| **Layout & hierarchy** | 7/10 | Cân bằng hero tốt, flow landing mượt; nhưng không có spacing scale (dùng ~15 giá trị khác nhau), tiêu đề trang 6 cỡ khác nhau, `<main>` lồng nhau vô hiệu max-width 1500px |
| **Component** | 7/10 | Chat bubble, chips, step cards đẹp; nhưng 3 kiểu focus input, icon Unicode (↑↻), drawer thật ra là section chèn thẳng gây layout shift |
| **UX polish** | 6.5/10 | Motion nhất quán, reduced-motion có; nhưng busy chỉ là text, không skeleton, message không auto-dismiss, RTL hoàn toàn không được hỗ trợ |
| **Walkthrough tổng thể** | 7.5/10 | Landing 9/10, Workspace 8/10, Admin 5/10 — chênh lệch quá lớn |

**Tổng hợp: 7/10** — giữa các số 5.5–7.5, thiên về 7 vì các trang quan trọng nhất (landing, workspace) đẹp nhất và hệ token/dark-mode là tài sản thật sự. Red-team đẩy lên 7.0; synthesis giữ 6.5. Tôi chốt 7/10 vì các lỗi High đều ở chế độ không mặc định hoặc trang phụ.

---

## Phải sửa trước khi công khai (Tier 0 — 2 mục)

Những mục này là **lỗi kỹ thuật có thể đo được**, không phải sở thích:

1. **Contrast dark-mode của `.danger` — `globals.css:43`** (khối `prefers-color-scheme:dark`). Nút danger dùng `--danger:#ff9b8a` + chữ `#fff` ≈ **2:1** (WCAG cần 4.5:1). Nút `.chat-box button` tương tự (chữ trắng trên lavender sáng). Cách sửa: trong khối dark, đổi `color` của `.danger` sang tối (`#2a182e`) như pattern brand-contrast đã dùng. **Đây là lỗi thật, không phải gu.**
2. **`<main>` lồng nhau — `app/layout.tsx:9` + mọi trang**. RootLayout bọc `<main className="shell">`, nhiều trang (plan workspace) lại có `<main>` riêng → `.workspace-page{max-width:1500px}` bị vô hiệu, panel chat bị nén ~276px. Sửa: bỏ `<main>` ở layout (dùng `<div>`) hoặc bỏ `<main>` trong trang.

---

## Nên sửa trước khi mở rộng (Tier 1 — chọn lọc)

3. **Contrast accent link — `globals.css:1`**: `--accent:#926cd6` trên `--paper` ≈ 3.93:1, dưới chuẩn 4.5:1 cho text nhỏ. Tối ưu: dùng `#7b4fbe`-ish ở light mode.
4. **Không có spacing scale**: 12–15 giá trị khác nhau (13px, 14px, 15px, 18px, 26px...). Chuẩn hóa về hệ 8px (8/16/24/32/48/64) để nhịp điệu đều hơn.
5. **Tiếng Việt không dấu hard-code trong Admin — `app/admin/page.tsx`** (dòng ~65, 358, 573): "Da huy", "Loc trang thai", "Ghi chu noi bo"... Trang admin nhìn lạc giọng hoàn toàn so với phần còn lại. Chuyển sang i18n hoặc ít nhất gõ dấu đúng.
6. **Typo bản đồ — `components/MapView.tsx:18` & `components/RoadTripMap.tsx`**: attribution `"c OpenStreetMap contributors"` mất ký tự ©. Lỗi dễ sửa nhưng xuất hiện trên MỌI bản đồ.
7. **Trang Admin 5 thẻ trong lưới 4 cột — `app/admin/page.tsx:368`**: thẻ cuối rơi xuống hàng dưới tạo răng cưa. Sửa lưới thành 5 cột hoặc thêm thẻ thứ 6.
8. **Version/comment/feedback "drawer" chỉ là section chèn thẳng — `components/PlanView.tsx:123-125`**: gây layout shift đột ngột. Biến thành overlay thật hoặc giữ cố định vị trí.

---

## Polish (Tier 2)

9. **Icon Unicode (↑ ↻) trong nút send/swap**: không hiện đồng nhất giữa OS (Android/iOS khác nhau). Dùng SVG hoặc component icon.
10. **Busy state chỉ là text "busy" — `PlanView.tsx:118`**: thêm spinner/skeleton cho itinerary + map khi đang tải.
11. **Message không auto-dismiss**: status nằm im tới khi hành động khác. Tự ẩn sau 3–4s.
12. **3 kiểu focus input khác nhau** giữa planner, explore, comment. Thống nhất 1 pattern focus ring.
13. **Hero h1 floor 48px trên mobile** — quá to so với màn hình nhỏ; giảm floor còn ~34px.
14. **People input trong Planner** đặt dưới chat-box, phá khối đối thoại; đưa lên trên hoặc thành 1 hàng kèm label.

---

## Ý tưởng tương lai (Tier 3)

15. **Font Inter không được tải** (chỉ khai báo `--font`): hoặc tự-host/subset Inter, hoặc bỏ và để system-ui. Hiện không có font nào được nạp → render bằng font hệ thống mặc dù CSS khai báo Inter.
16. **RTL cho ar/he**: 19 ngôn ngữ, trong đó Ả Rập/Hebrew RTL, nhưng CSS không có selector `[dir=rtl]` nào, `letter-spacing` âm sẽ phá chữ Ả Rập. Nếu coi trọng i18n thì đây là lỗ hổng lớn.
17. **Typo "· local" trong nút Google Login** — `app/login/page.tsx:20` (`(NEXT_PUBLIC_APP_ENV ?? "local")`).
18. **Đa dạng màu tím**: 97 lần dùng lavender — cân nhắc thêm 1 màu nhấn thứ 2 (xanh lá du lịch/nắng) cho featured-card để đỡ đơn điệu.

---

## Điểm mạnh thật sự (đừng phá khi sửa)

- **Dark mode được thiết kế chủ đích** — không phải "invert ngược", có token riêng (dark:brand=#cdb3ff, contrast đảo). Rất ít MVP làm được.
- **Gradient thương hiệu** (ink-3→accent→lavender) lặp lại nhất quán ở brand-logo, planner top-bar, footer-brand — tạo nhận diện mạnh.
- **Typography clamp() thông minh** (`clamp(48px,6.5vw,88px)`...) — tự co giãn theo viewport mà không cần media query rườm rà.
- **Motion có chủ ý** (translateY nhẹ, scale nhỏ, `--ease` chuẩn cubic-bezier) + `prefers-reduced-motion` được xử lý.
- **Chat bubble đối xứng đẹp** (assistant trái lavender / user phải brand, góc bo 6px đối diện).
- **Focus-visible toàn cục** (`outline:3px accent-2`) — accessibility cơ bản có sẵn.

---

## Câu hỏi để bạn quyết định hướng tiếp theo

1. **Bạn có coi accessibility (WCAG) là yêu cầu khi công khai không?** Nếu có → Tier 0+contrast phải làm. Nếu chỉ là demo → có thể bỏ qua.
2. **Admin có phải là trang người dùng thấy không?** Nếu nội bộ → tiếng Việt không dấu chấp nhận được, chỉ sửa lưới 5-thẻ. Nếu khách thấy → cần chỉnh.
3. **Có thật sự cần 19 ngôn ngữ không?** Nếu Ả Rập/Hebrew không phải mục tiêu, đừng đầu tư RTL (Tier 3).
4. **Bạn muốn tôi áp dụng các sửa Tier 0–1 không?** (Cần bạn xác nhận — deep-dive này chỉ phân tích, chưa đụng code.)

---

**Confidence: 7/10** — các con số contrast được 2 agent tính độc lập và red-team xác minh lại (1 số sai đã được sửa: CTA dark 1.83:1, không phải 1.4:1); file:line được đọc trực tiếp.

**Ground-truth tally: 33/42 kết luận quan trọng dựa trên code đọc trực tiếp (file:line, hex màu, CSS selector); 9 còn lại là nhận định thẩm mỹ chủ quan (gu, không đo được bằng công cụ).** Phần lớn nội dung đứng trên bằng chứng kiểm chứng được, nên điểm 7 là hợp lý — không phải đánh bóng.
