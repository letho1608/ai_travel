# Testcase End-User — Chatbot "Mình Đi Đâu Thế"

Kiểm thử thủ công qua giao diện người dùng (black-box / UAT). Không yêu cầu kiến thức code.

- **Ứng dụng:** http://localhost:3001 (hoặc URL frontend do launcher in ra)
- **Backend:** http://localhost:8000
- **Ngôn ngữ test:** Tiếng Việt (mặc định)
- **Ký hiệu kết quả:** ✅ PASS · ❌ FAIL · ⚠️ N/A
- **Mức ưu tiên:** P1 = phải đạt trước khi phát hành · P2 = quan trọng · P3 = nên có

## Tiền điều kiện

1. Backend và frontend đang chạy (xem README / `run.bat`).
2. Mở trình duyệt ở chế độ ẩn danh (Incognito) để có phiên mới sạch.
3. `AI_MODE=offline` (mặc định) để kết quả tạo plan ổn định.

---

## Nhóm A — Chat tạo kế hoạch (trang chủ)

### A-01 · Tạo plan khi nhập đầy đủ thông tin — P1
**Các bước:**
1. Vào trang chủ.
2. Trong ô chat nhập: `Đi chơi chill Hà Nội, cả ngày, 2 người`
3. Nhấn nút gửi (↑).

**Kết quả mong đợi:**
- Lời chào hiển thị trước khi nhập.
- Sau khi gửi hiển thị trạng thái lần lượt: `Đang gửi yêu cầu...` → `Đang tìm địa điểm tin cậy...` → `Đang xếp tuyến và kiểm tra lịch trình...`
- Tự chuyển hướng sang trang kế hoạch `/plan/{token}`.
- Kế hoạch có lịch trình 1 ngày với các điểm, chi phí, thời tiết, tham số `2 người`.

### A-02 · Thiếu thời lượng → chatbot hỏi lại — P1
**Các bước:**
1. Nhập: `Đi Hà Nội, 2 người`
2. Nhấn gửi.

**Kết quả mong đợi:**
- Chatbot trả lời câu hỏi thời lượng: `Bạn muốn một ngày thế nào? Có thể ghi 2 giờ, từ 9h đến 17h, từ 20/8 đến 22/8, hoặc chọn: ...`
- Hiện 4 chip gợi ý: `Vài giờ`, `Nửa ngày`, `Cả ngày`, `Nhiều ngày`.

### A-03 · Chọn chip thời lượng rồi thiếu điểm đến → hỏi điểm đến — P1
**Các bước:**
1. Nhập: `đi chơi chill và ăn ngon, 2 người` (không có điểm đến).
2. Nhấn gửi → bấm chip `Cả ngày`.

**Kết quả mong đợi:**
- Hiện câu hỏi `Bạn muốn đi ở đâu?`.
- Hiện chip điểm đến: `Hà Nội`, `Hạ Long`, `Huế`, `Đà Nẵng`, `Hội An`, `Nha Trang`, `Đà Lạt`, `TP.HCM`.

### A-04 · Chọn chip điểm đến → tiếp tục hỏi số người — P1
**Các bước:**
1. Từ bước A-03, bấm chip `Hà Nội`.

**Kết quả mong đợi:**
- Hiện câu hỏi `Bạn đi mấy người?`.
- Nhập `3 người` → tạo được plan với `3 người`.

### A-05 · Yêu cầu không có điểm đến (server-side) — P2
**Các bước:**
1. Nhập: `đi chơi chill và ăn ngon cả ngày` (không tên thành phố, thời lượng ghi trực tiếp).
2. Nhấn gửi.

**Kết quả mong đợi:**
- Chatbot vẫn hỏi lại điểm đến (không tự bịa điểm đến mặc định).

### A-06 · Nút gửi bị khoá khi đang xử lý — P2
**Các bước:**
1. Gửi một yêu cầu hợp lệ (vd câu ở A-01).
2. Ngay khi trạng thái `Đang gửi yêu cầu...` xuất hiện, thử nhập tiếp và nhấn gửi.

**Kết quả mong đợi:**
- Ô nhập và nút gửi bị disable (mờ đi) tới khi xong/đổi trang. Không gửi trùng yêu cầu.

### A-07 · Giới hạn độ dài ô nhập — P3
**Các bước:**
1. Thử nhập hơn 500 ký tự vào ô chat.

**Kết quả mong đợi:**
- Không thể nhập quá 500 ký tự (bị chặn tại ô nhập).

### A-08 · Nhập rỗng → không gửi — P2
**Các bước:**
1. Để trống ô chat, nhấn gửi.

**Kết quả mong đợi:**
- Không gửi yêu cầu; hiển thị thông báo lỗi tạo kế hoạch (`Không thể tạo kế hoạch. Vui lòng thử lại.`) hoặc ô bắt buộc nhắc nhập.

### A-09 · Lỗi tạo plan → nút "Thử lại" — P2
**Các bước:**
1. Ngắt mạng hoặc tắt backend (để tạo plan thất bại).
2. Gửi yêu cầu hợp lệ.

**Kết quả mong đợi:**
- Hiện thông báo `Không thể tạo kế hoạch. Vui lòng thử lại.` + nút `Thử lại`.
- Bật lại mạng/backend, bấm `Thử lại` → plan được tạo và chuyển hướng bình thường.

### A-10 · Timeout yêu cầu — P3
**Các bước:**
1. Làm chậm backend (hoặc dùng proxy chặn) để yêu cầu vượt 180 giây.

**Kết quả mong đợi:**
- Hiện `Yêu cầu quá thời gian. Vui lòng thử lại.` + nút `Thử lại`.

### A-11 · Không tạo plan trùng khi gửi lại (nonce idempotent) — P2
**Các bước:**
1. Gửi yêu cầu A-01 tạo thành công plan X.
2. Bấm Back về trang chủ, gửi lại đúng cùng câu.

**Kết quả mong đợi:**
- Nhận đúng plan X cũ (cùng token) thay vì tạo plan mới trùng lặp; không tốn thêm lượt tạo.

### A-12 · Hiểu nhiều cách viết thời lượng — P2
**Các bước (mỗi dòng là một lần test, dùng phiên mới):**
1. `Đi Hà Nội 2 giờ`
2. `Đi Hà Nội từ 9h đến 17h`
3. `Đi Hà Nội từ 20/8 đến 22/8`
4. `Đi Hà Nội cuối tuần`

**Kết quả mong đợi:**
- (1)(2) → plan ngắn (vài giờ/nửa ngày theo số giờ); (3)(4) → plan nhiều ngày. Không hỏi lại thời lượng.

### A-13 · Lọc HTML trong yêu cầu — P2
**Các bước:**
1. Nhập: `<script>alert(1)</script> đi chơi Hà Nội cả ngày`
2. Nhấn gửi.

**Kết quả mong đợi:**
- Không có popup/script chạy; yêu cầu vẫn xử lý thành plan; văn bản hiển thị là nội dung đã được lọc ký tự `<` `>`.

---

## Nhóm B — Chat tinh chỉnh trong kế hoạch (`/plan/{token}`)

### B-01 · Hội thoại khởi đầu — P1
**Các bước:**
1. Tạo plan từ A-01 để vào workspace.

**Kết quả mong đợi:**
- Panel `Trợ lý chuyến đi` hiển thị lời chào: `Mình đã xếp lịch theo đường đi, giờ mở cửa và ngân sách. Chọn một điểm trên lịch hoặc bản đồ để tinh chỉnh.`
- Lịch sử hội thoại chứa câu nhập ban đầu của người dùng.

### B-02 · Đổi số người và ngân sách qua chat — P1
**Các bước:**
1. Trong panel chat workspace nhập: `đi 3 người, ngân sách tối đa 500k`
2. Nhấn gửi.

**Kết quả mong đợi:**
- Xuất hiện bubble người dùng rồi bubble assistant xác nhận đã áp dụng.
- Tham số hiển thị đổi thành `3 người` và ngân sách ~500.000 VND; tổng chi phí plan được tính lại.
- Phiên bản plan tăng lên (ví dụ `Phiên bản 2`).

### B-03 · Chat nhiều lượt liên tiếp (multi-turn) — P1
**Các bước:**
1. Từ B-02, tiếp tục nhập: `4 người, ưu tiên yên tĩnh`
2. Nhấn gửi.

**Kết quả mong đợi:**
- Số người đổi thành 4, ngân sách giữ nguyên ~500.000 VND.
- Chatbot nhớ ngữ cảnh lượt trước (vẫn áp dụng ràng buộc ngân sách cũ).
- Hội thoại hiển thị đầy đủ các lượt theo thứ tự user → assistant.

### B-04 · Yêu cầu "rẻ hơn" → giảm ngân sách — P2
**Các bước:**
1. Nhập: `Re hon` hoặc `rẻ hơn`.
2. Nhấn gửi.

**Kết quả mong đợi:**
- Ngân sách giảm ~20% so với mức hiện tại; plan được xếp lại ưu tiên điểm rẻ.

### B-05 · Yêu cầu địa điểm gần nhau — P2
**Các bước:**
1. Nhập: `chọn địa điểm gần nhau, ít di chuyển`.
2. Nhấn gửi.

**Kết quả mong đợi:**
- Plan mới ưu tiên các điểm gần nhau hơn (khoảng cách/đường đi giảm).

### B-06 · Yêu cầu thêm quán cafe — P3
**Các bước:**
1. Nhập: `thêm quán cafe`.
2. Nhấn gửi.

**Kết quả mong đợi:**
- Plan mới có nhiều điểm loại cafe/đồ uống thư giãn hơn (nếu phù hợp khung giờ).

### B-07 · Đổi 1 điểm đang chọn — P1
**Các bước:**
1. Chọn 1 điểm trên lịch trình (hoặc bấm điểm trên bản đồ).
2. Trong chat nhập: `đổi điểm này`.
3. Nhấn gửi.

**Kết quả mong đợi:**
- Điểm đã chọn được thay bằng điểm khác tương tự; thông báo `Đã thay đúng một điểm và kiểm tra lại lịch trình.`
- Phiên bản tăng; tổng chi phí tính lại.

### B-08 · "Đổi điểm" khi chưa chọn điểm — P2
**Các bước:**
1. Không chọn điểm nào, nhập `đổi điểm này` và gửi.

**Kết quả mong đợi:**
- Hiện thông báo hướng dẫn phải chọn một điểm cần đổi (`Hãy chọn một địa điểm cần đổi`). Không làm thay đổi plan.

### B-09 · Xung đột phiên bản (đã đổi từ tab khác) — P2
**Các bước:**
1. Mở cùng plan ở 2 tab (tab A, tab B).
2. Ở tab A chat `đi 3 người` (tạo phiên bản 2).
3. Ở tab B vẫn ở phiên bản 1, chat `đi 4 người`.

**Kết quả mong đợi:**
- Tab B báo lỗi rằng kế hoạch vừa được cập nhật, phải tải lại; không ghi đè thay đổi của tab A.

### B-10 · Link chia sẻ chỉ đọc — P2
**Các bước:**
1. Tạo plan, dùng nút Chia sẻ để lấy link.
2. Mở link đó ở trình duyệt khác/ẩn danh (không cùng phiên).

**Kết quả mong đợi:**
- Xem được plan nhưng không tinh chỉnh được (bị từ chối quyền sửa).

### B-11 · Chat bị khoá khi đang chạy thao tác khác — P2
**Các bước:**
1. Nhấn nút `Làm lại` (regenerate) hoặc đổi điểm.
2. Ngay lúc đó thử gõ và gửi tin chat.

**Kết quả mong đợi:**
- Ô chat + nút gửi bị disable cho tới khi thao tác xong; không gửi chồng.

### B-12 · Hội thoại còn lại sau khi reload — P1
**Các bước:**
1. Thực hiện B-02 rồi reload trang (F5).

**Kết quả mong đợi:**
- Toàn bộ hội thoại (câu đã gửi + câu trả lời) và plan phiên bản mới vẫn hiển thị đầy đủ.

### B-13 · Lịch sử phiên bản sau tinh chỉnh — P2
**Các bước:**
1. Tinh chỉnh 2 lần (vd B-02 rồi B-03).
2. Mở `Lịch sử phiên bản`.

**Kết quả mong đợi:**
- Danh sách phiên bản tăng dần theo mỗi lần tinh chỉnh; khôi phục phiên bản cũ hoạt động.

### B-14 · Đổi ngôn ngữ giao diện — P2
**Các bước:**
1. Chuyển ngôn ngữ sang English (hoặc ngôn ngữ khác).

**Kết quả mong đợi:**
- Lời chào, placeholder chat (`For example: replace this place`), và thông báo assistant hiển thị theo ngôn ngữ đã chọn.

### B-15 · HTML bị lọc trong tin nhắn chat — P2
**Các bước:**
1. Trong chat workspace nhập: `<script>alert(1)</script> rẻ hơn` và gửi.

**Kết quả mong đợi:**
- Không có script chạy; yêu cầu "rẻ hơn" vẫn được áp dụng; văn bản hiển thị đã lọc ký tự `<` `>`.

---

## Ma trận kết quả

| ID | Mô tả | Ưu tiên | Kết quả | Ghi chú |
|----|-------|---------|---------|---------|
| A-01 | Tạo plan đủ thông tin | P1 | | |
| A-02 | Hỏi lại thời lượng | P1 | | |
| A-03 | Hỏi điểm đến | P1 | | |
| A-04 | Hỏi số người | P1 | | |
| A-05 | Thiếu điểm đến server-side | P2 | | |
| A-06 | Khoá nút khi đang xử lý | P2 | | |
| A-07 | Giới hạn 500 ký tự | P3 | | |
| A-08 | Nhập rỗng | P2 | | |
| A-09 | Lỗi + nút Thử lại | P2 | | |
| A-10 | Timeout | P3 | | |
| A-11 | Không tạo trùng (nonce) | P2 | | |
| A-12 | Hiểu nhiều dạng thời lượng | P2 | | |
| A-13 | Lọc HTML | P2 | | |
| B-01 | Lời chào workspace | P1 | | |
| B-02 | Đổi số người + ngân sách | P1 | | |
| B-03 | Chat nhiều lượt | P1 | | |
| B-04 | "Rẻ hơn" | P2 | | |
| B-05 | Địa điểm gần nhau | P2 | | |
| B-06 | Thêm quán cafe | P3 | | |
| B-07 | Đổi điểm đang chọn | P1 | | |
| B-08 | Đổi điểm khi chưa chọn | P2 | | |
| B-09 | Xung đột phiên bản | P2 | | |
| B-10 | Link chia sẻ chỉ đọc | P2 | | |
| B-11 | Khoá chat khi busy | P2 | | |
| B-12 | Reload giữ hội thoại | P1 | | |
| B-13 | Lịch sử phiên bản | P2 | | |
| B-14 | Đổi ngôn ngữ | P2 | | |
| B-15 | Lọc HTML chat workspace | P2 | | |