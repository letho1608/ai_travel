# Báo cáo khung — Tính năng · Vấn đề · Cần gì · Chi phí

**Sản phẩm:** Mình Đi Đâu Thế  
**Phạm vi:** Bản đầu tiên, chỉ Hà Nội  
**Cách đọc:** Mỗi tính năng trả lời 4 câu — *làm được gì → giúp gì → cần gì để chạy được → tốn bao nhiêu*

---

## Cách đọc khung

| Mục | Ý nghĩa bằng lời thường |
| --- | --- |
| **Tính năng** | Người dùng nhìn thấy / bấm được gì trên web |
| **Vấn đề giải quyết** | Nỗi phiền nào được bớt đi |
| **Cần gì để chạy được** | Dữ liệu, công cụ, quy tắc nào bắt buộc phải có sẵn |
| **Chi phí** | Tiền cố định mỗi tháng/năm + tiền mỗi lần dùng |

---

## 0. Chi phí “nền” (dùng chung cho hầu hết tính năng)

Những khoản này không gắn với một nút bấm cụ thể, nhưng web không chạy được nếu thiếu:


| Khoản (nói dễ hiểu) | Để làm gì | Chi phí ước tính |
| --- | --- | --- |
| Máy chủ xử lý | Chỗ chạy “bộ não” tạo và sửa kế hoạch | **15–30 USD/tháng** |
| Chỗ đặt giao diện web | Người dùng mở trang trên điện thoại/máy tính | **0 USD** (gói miễn phí; nếu sau này bán hàng thì có thể phải trả phí) |
| Kho lưu dữ liệu + đăng nhập | Lưu kế hoạch, nhớ phiên dùng, đăng nhập bằng Google | **0 USD** (gói miễn phí, dung lượng vừa đủ bản đầu) |
| Bộ nhớ tạm | Giúp trang nhanh hơn, hạn chế người dùng bấm tạo quá nhiều lần liên tục | **0 USD** (gói miễn phí) |
| Tên miền (địa chỉ web) | Có link đẹp để gửi bạn bè | **khoảng 10 USD/năm** |
| Trí tuệ nhân tạo (AI) — mô hình rẻ | Ghép lịch trình + viết mô tả (mỗi kế hoạch gọi AI tối đa 1–2 lần) | **khoảng 0,0023 USD / một kế hoạch**; ngân sách tối đa **300 USD/tháng** |
| AI dự phòng (mô hình khác) | Dùng nếu mô hình chính viết sai / không ổn định | Đắt hơn mô hình chính một chút |
| Phần mềm tính đường (chạy offline, mỗi tuần một lần) | Tạo sẵn bảng “từ điểm A tới điểm B mất bao lâu” cho khoảng 50 địa điểm | **0 USD** chạy hàng ngày (chỉ tốn thời gian máy tính khi cập nhật tuần) |
| Danh sách địa điểm Hà Nội | Lấy từ bản đồ mở + kiểm tra / bổ sung tay các chỗ thiếu giờ mở cửa | **Chủ yếu là công sức người**; nếu phải bổ sung tay hơn ~150 điểm thì nên thu hẹp phạm vi thay vì nhập mãi |

**Quy mô tham chiếu:** khoảng 100 kế hoạch/ngày → tiền AI khoảng **7 USD/tháng**. Ngân sách 300 USD/tháng đủ cho khoảng **130.000** lần tạo kế hoạch (ở mức giá hiện tại).

---

## 1. Các tính năng bản đầu


### 1.1 Nói / nhập nhu cầu + chọn khoảng thời gian

| | Nội dung |
| --- | --- |
| **Tính năng** | Người dùng nhắn hoặc nói bằng tiếng Việt (ví dụ: “cuối tuần này đi với 3 người, nửa ngày”). Hệ thống hiểu số người, thời gian, phong cách, ngân sách và lọc theo: vài giờ / nửa ngày / cả ngày / nhiều ngày. |
| **Vấn đề giải quyết** | Không biết bắt đầu từ đâu; phải tự mở Google Maps, đọc đánh giá, tự ước lượng thời gian. |
| **Cần gì để chạy được** | Màn hình chat hoặc form hỏi đáp; khả năng hiểu tiếng Việt để lấy đúng thông tin; quy tắc lọc theo thời lượng đã thống nhất. |
| **Chi phí** | Gói trong lần tạo kế hoạch (khoảng **0,0012 USD** khi AI ghép nội dung). Không mất thêm phí bản đồ ở bước này. |


### 1.2 Đưa ra đúng một kế hoạch (tính năng cốt lõi)

| | Nội dung |
| --- | --- |
| **Tính năng** | Chỉ trả **một** lịch trình tốt nhất (khoảng 4–6 điểm), có giờ, mô tả, ước tính chi phí. Không đưa 2–3 phương án để người dùng phân vân. |
| **Vấn đề giải quyết** | Nhóm bạn nhắn tin vòng vo không chốt được đi đâu; quá nhiều lựa chọn thì càng khó quyết. |
| **Cần gì để chạy được** | Danh sách địa điểm thật (có giờ mở cửa, vị trí, loại hình); bảng thời gian di chuyển giữa các điểm đã tính sẵn; chương trình tự xếp thứ tự điểm hợp lý; AI chỉ được viết dựa trên danh sách đã chọn sẵn; bộ kiểm tra tự động để AI không bịa địa điểm ngoài danh sách. Cần thử trước: AI có viết đúng định dạng không, và dữ liệu Hà Nội có đủ không. |
| **Chi phí** | Khoảng **0,0012 USD** (ghép kế hoạch) + **0,0004 USD** (nếu phải sửa vì kiểm tra không đạt) ≈ **0,0016–0,0023 USD / một kế hoạch**. Cộng thêm tiền máy chủ và kho lưu (mục 0). |


### 1.3 Xem lịch trình bên trái + bản đồ bên phải

| | Nội dung |
| --- | --- |
| **Tính năng** | Một màn hình: bên trái là lịch theo giờ; bên phải là bản đồ các điểm sẽ đi. |
| **Vấn đề giải quyết** | Chỉ đọc chữ thì khó hình dung đường đi và khoảng cách trong nội đô. |
| **Cần gì để chạy được** | Bản đồ trên web (dùng bản đồ mở, không bắt buộc Google Maps); mỗi địa điểm có tọa độ đúng; lịch và bản đồ khớp nhau; trang mở trong khoảng 2 giây. |
| **Chi phí** | **Khoảng 0 USD** mỗi lần xem. Nếu sau này đổi sang Google Maps có thể phát sinh phí. |


### 1.4 Tự lưu kế hoạch, dùng thử không cần đăng nhập

| | Nội dung |
| --- | --- |
| **Tính năng** | Hệ thống tự lưu lịch trình với mã bí mật khó đoán. Xem lại bằng link, chưa cần tạo tài khoản. Link hết hạn khoảng 30 ngày. |
| **Vấn đề giải quyết** | Đóng trang là mất kế hoạch; sợ phải đăng ký mới được dùng. |
| **Cần gì để chạy được** | Kho lưu kế hoạch; mã phiên tạm cho người chưa đăng nhập; quy tắc tự xóa sau 30 ngày; đường link không chứa tên, SĐT hay thông tin cá nhân. |
| **Chi phí** | Gói miễn phí của kho lưu dữ liệu — gần **0 USD** ở quy mô bản đầu. |


### 1.5 Gửi link cho bạn / nhóm (hiện tiêu đề khi dán Zalo)

| | Nội dung |
| --- | --- |
| **Tính năng** | Sao chép và gửi link kế hoạch. Khi dán vào Zalo hoặc Facebook, hiện tiêu đề + mô tả ngắn để mọi người biết đây là lịch đi chơi gì. |
| **Vấn đề giải quyết** | Nhóm không thống nhất vì mỗi người tự search một kiểu, không cùng nhìn một kế hoạch. |
| **Cần gì để chạy được** | Địa chỉ web thật; tiêu đề và mô tả gắn sẵn trên link; phải thử thật trên Zalo xem có hiện đúng không. Ảnh minh họa đẹp khi chia sẻ để dành giai đoạn sau. |
| **Chi phí** | Tên miền khoảng **10 USD/năm** + chỗ đặt web miễn phí. Làm ảnh chia sẻ đẹp (sau này): thêm công sức. |


### 1.6 Vuốt bỏ một điểm / làm lại toàn bộ

| | Nội dung |
| --- | --- |
| **Tính năng** | Không thích một điểm thì vuốt bỏ — hệ thống tự tìm điểm thay thế trên cùng hành trình. Hoặc bấm “Làm lại” để nhận một kế hoạch mới (vẫn chỉ một phương án). |
| **Vấn đề giải quyết** | Vừa xem hoặc đang đi đã thấy điểm không hợp (đóng cửa, không thích) mà không muốn lên kế hoạch từ đầu. |
| **Cần gì để chạy được** | Danh sách điểm dự phòng cùng khu vực / cùng gu; bảng thời gian di chuyển; quyền sửa kế hoạch của mình; đôi khi cần AI viết lại câu mô tả. |
| **Chi phí** | Đổi một điểm: thường **gần 0 USD** (máy tự tìm trong kho dữ liệu). Nếu cần AI viết lại mô tả: khoảng **0,0007 USD**. Làm lại toàn bộ ≈ một lần tạo mới (**khoảng 0,0023 USD**). |


### 1.7 Học gu người dùng mà không hỏi đánh giá sao

| | Nội dung |
| --- | --- |
| **Tính năng** | Không bắt chấm sao 1–5. Hệ thống nhìn hành vi: giữ điểm nào / vuốt bỏ điểm nào để nhớ gu (ví dụ thích “view đẹp”, không thích “ồn ào”). Khi đăng nhập thì gộp gu từ lúc dùng thử. |
| **Vấn đề giải quyết** | Form đánh giá thường bị bỏ qua; lần sau vẫn gợi ý sai gu. |
| **Cần gì để chạy được** | Ghi nhận thao tác giữ / vuốt; bảng điểm theo nhãn địa điểm; khi đăng nhập thì nối dữ liệu dùng thử với tài khoản. Cách tìm kiếm “thông minh hơn” bằng AI để dành khi đã có rất nhiều thao tác thật (hơn khoảng 5.000 lần vuốt). |
| **Chi phí** | **Khoảng 0 USD** tiền AI ở bản đầu (chỉ lưu và cộng/trừ điểm). |


### 1.8 Đăng nhập Google một chạm + xem lại trên nhiều máy

| | Nội dung |
| --- | --- |
| **Tính năng** | Dùng thử trước → bấm đăng nhập Google một cái → kế hoạch và gu cũ được giữ. Đã đăng nhập thì xem lại lịch sử trên điện thoại khác / máy tính khác. |
| **Vấn đề giải quyết** | Ngại tạo tài khoản; đổi máy là mất lịch sử. |
| **Cần gì để chạy được** | Nút đăng nhập Google; quy trình gộp dữ liệu dùng thử vào tài khoản; chỉ chủ sở hữu mới sửa được kế hoạch của mình. Đăng nhập Apple để dành giai đoạn sau. |
| **Chi phí** | **0 USD** (dịch vụ đăng nhập gói miễn phí + Google không thu phí phần này). Đăng nhập Apple sau này: khoảng **99 USD/năm** phí tài khoản nhà phát triển Apple. |


### 1.9 Nhắc lịch / thời tiết (bản đầu đơn giản; bản sau đầy đủ hơn)

| | Nội dung |
| --- | --- |
| **Tính năng (bản đầu)** | Nhắc trong trang web hoặc gửi email miễn phí. |
| **Tính năng (giai đoạn sau)** | Thông báo đẩy trên điện thoại + cảnh báo thời tiết chủ động hơn. |
| **Vấn đề giải quyết** | Quên lịch; mưa hoặc quán đóng cửa làm hỏng chuyến mà không ai báo sớm. |
| **Cần gì để chạy được (bản đầu)** | Email hoặc dòng nhắc trong trang; nếu cần thời tiết thì lấy từ nguồn dự báo. |
| **Cần gì (giai đoạn sau)** | Thông báo đẩy trên điện thoại — lưu ý: iPhone và mở link trong Zalo thường hạn chế thông báo. |
| **Chi phí** | Bản đầu: **khoảng 0 USD**. Giai đoạn sau: chủ yếu công sức làm thêm; nguồn thời tiết tùy nhà cung cấp (có gói miễn phí hoặc trả phí). |

---

## 2. Bảng tổng hợp nhanh (một trang)


| # | Tính năng | Giúp việc gì | Cần gì để chạy được | Chi phí chính |
| --- | --- | --- | --- | --- |
| 1 | Nhập nhu cầu + chọn thời lượng | Biết bắt đầu từ đâu | Màn hình hỏi đáp + hiểu tiếng Việt | Gói trong tạo kế hoạch |
| 2 | Đúng một kế hoạch tối ưu | Nhóm chốt được đi đâu | Danh sách địa điểm + bảng thời gian đi + AI + bộ kiểm tra | **~0,0023 USD / kế hoạch** |
| 3 | Lịch + bản đồ cạnh nhau | Hình dung đường đi | Bản đồ web + vị trí đúng | **~0 USD / lần xem** |
| 4 | Tự lưu, dùng thử không đăng nhập | Không mất kế hoạch | Kho lưu + mã bí mật + hết hạn 30 ngày | Gói miễn phí |
| 5 | Gửi link cho nhóm | Cùng nhìn một kế hoạch | Tiêu đề trên link + thử thật trên Zalo | Tên miền ~10 USD/năm |
| 6 | Vuốt đổi điểm / làm lại | Đổi nhanh khi không hợp | Điểm dự phòng + bảng thời gian đi | **0 – 0,0023 USD** |
| 7 | Nhớ gu từ hành vi | Lần sau gợi ý đúng hơn | Ghi giữ/vuốt + gộp khi đăng nhập | **~0 USD** |
| 8 | Đăng nhập Google + xem nhiều máy | Không mất lịch sử | Đăng nhập Google + gộp dữ liệu dùng thử | **~0 USD** |
| 9 | Nhắc lịch / thời tiết | Ít quên, ít bị mưa bất ngờ | Email / nhắc trong trang (thông báo đẩy để sau) | **~0 USD** bản đầu |

---

## 3. Chi phí vận hành mỗi tháng (ước lượng)


| Hạng mục (nói dễ hiểu) | Thấp | Trung bình | Ghi chú |
| --- | ---: | ---: | --- |
| Máy chủ xử lý | 15 USD | 30 USD | Chỗ chạy tạo / sửa kế hoạch |
| Chỗ đặt giao diện web | 0 USD | 0 → có phí | Gói miễn phí có giới hạn nếu sau này bán hàng |
| Kho lưu dữ liệu + đăng nhập | 0 USD | từ 25 USD | Khi vượt gói miễn phí |
| Bộ nhớ tạm | 0 USD | từ 10 USD | Khi vượt gói miễn phí |
| Tên miền | ~1 USD/tháng | ~1 USD/tháng | Quy từ ~10 USD/năm |
| Tiền AI | ~7 USD | tối đa 300 USD | Trần cứng 300 USD/tháng; ~100 kế hoạch/ngày ≈ 7 USD |
| **Tổng ước lượng bản đầu** | **~23 USD** | **~50–80 USD** (chưa chạm trần AI) | Trần AI riêng vẫn là 300 USD |

---

## 4. Việc cần kiểm tra trước khi làm lớn

### 4.1 Dữ liệu địa điểm & đường đi
- [ ] Mỗi loại hình × mỗi khu vực có ít nhất 3 địa điểm đủ thông tin (có giờ mở cửa, đang hoạt động)
- [ ] Đã kiểm tra giờ mở cửa / chỗ còn mở
- [ ] Bảng “đi từ A tới B mất bao lâu” khớp thực tế nội đô Hà Nội (sai lệch tốt nhất ≤ 20%)
- [ ] AI không được bịa địa điểm ngoài danh sách đã chọn

### 4.2 Trí tuệ nhân tạo
- [ ] Mô hình chính trả lời đúng định dạng, ổn định, đủ nhanh
- [ ] Có mô hình dự phòng nếu mô hình chính không đạt
- [ ] Có đồng hồ đếm tiền AI và tự dừng khi gần chạm trần 300 USD/tháng
- [ ] Bản đầu **không** bật chế độ “suy luận dài” của AI (dễ tốn tiền hơn nhiều)

### 4.3 Người dùng & chia sẻ
- [ ] Thử với người thật: họ có chấp nhận để AI đưa **một** kế hoạch không?
- [ ] Dán link vào Zalo: tiêu đề + mô tả có hiện đúng không?
- [ ] Đăng nhập Google và gộp dữ liệu dùng thử chạy đúng

---

## 5. Chỗ ghi số liệu thật sau này

| Mục cần đo | Số đo được | Ngày đo | Người ghi |
| --- | --- | --- | --- |
| Tiền AI cho 100 kế hoạch | | | |
| Tỷ lệ kế hoạch đạt kiểm tra ngay lần đầu | | | |
| Số địa điểm “đủ điều kiện” ở Hà Nội | | | |
| Sai lệch thời gian đi (tính máy so với thực tế) | | | |
| Tỷ lệ người mở link khi gửi qua Zalo | | | |

---

*Số liệu chi phí và phạm vi tính năng lấy theo thiết kế tổng thể bản dễ hiểu (`HLD.md` phiên bản 0.3).*
