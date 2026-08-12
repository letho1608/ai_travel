# Hệ thống tạo lịch trình như thế nào?

Hệ thống tạo lịch trình bằng cách kết hợp dữ liệu địa điểm thật, thuật toán lọc/sắp tuyến và AI hỗ trợ hiểu yêu cầu, thay vì để AI tự bịa ra lịch trình.

## 1. Người dùng nhập yêu cầu

Người dùng mô tả mong muốn theo dạng chat, ví dụ:

```text
Đi chơi Hà Nội 1 ngày, thích cà phê, đi bộ nhẹ, 2 người, ngân sách 1 triệu.
```

Nếu thiếu thông tin quan trọng như thời lượng, số người hoặc ngân sách, hệ thống có thể hỏi tiếp để người dùng trả lời trong chatbox.

## 2. Backend nhận và chuẩn hóa yêu cầu

Frontend gửi yêu cầu sang backend với các thông tin chính:

- Nội dung người dùng muốn đi đâu/làm gì
- Vị trí bắt đầu
- Thời lượng: vài giờ, nửa ngày, cả ngày hoặc nhiều ngày
- Số người
- Ngân sách
- Ngày đi nếu có
- Mã phiên người dùng

## 3. Hệ thống chọn địa điểm thật

Backend chọn địa điểm từ catalog có sẵn, không để AI tự bịa địa điểm.

Catalog có thể gồm:

- Địa điểm tham quan
- Quán cà phê
- Nhà hàng/quán ăn
- Công viên
- Chợ/chợ đêm
- Bảo tàng

Nguồn dữ liệu có thể đến từ:

- Dữ liệu thủ công đã curated
- OpenStreetMap
- Google Places nếu có cấu hình API key và vẫn nằm trong hạn mức kiểm soát

## 4. Lọc địa điểm phù hợp

Hệ thống lọc địa điểm theo nhiều tiêu chí:

- Trải nghiệm người dùng muốn: chill, cà phê, văn hóa, ẩm thực, đi bộ, chợ đêm...
- Vị trí/khu vực phù hợp
- Giờ mở cửa
- Ngân sách
- Thời lượng chuyến đi
- Không chọn địa điểm trùng tên hoặc trùng ID
- Chợ đêm phải được xếp vào buổi tối

## 5. Sắp xếp tuyến đường

Sau khi có danh sách địa điểm phù hợp, hệ thống sắp xếp lịch trình theo thứ tự hợp lý:

- Tính khoảng cách/thời gian di chuyển giữa các điểm
- Ưu tiên các điểm gần nhau để tuyến đi gọn hơn
- Chèn điểm ăn uống/cà phê/nghỉ theo buổi
- Kiểm tra thời gian di chuyển giữa các điểm
- Nếu điểm nào không phù hợp thời gian thì bỏ hoặc thay bằng điểm khác

## 6. Tạo khung thời gian

Mỗi điểm trong lịch trình sẽ có:

- Giờ bắt đầu
- Giờ kết thúc
- Tên địa điểm
- Mô tả
- Chi phí ước tính
- Ghi chú đi lại
- Nguồn dữ liệu
- Ảnh nếu có

Thời gian gợi ý cho từng địa điểm không nên là ngẫu nhiên. Hệ thống nên chọn khung giờ dựa trên các lý do sau:

### 6.1. Giờ mở cửa của địa điểm

Địa điểm chỉ được xếp trong khoảng giờ mở cửa hợp lệ.

Ví dụ:

- Bảo tàng mở 08:00–17:00 thì không xếp sau 17:00.
- Chợ đêm phải xếp sau 18:00.
- Nhà hàng chỉ mở buổi trưa/tối thì phải khớp khung giờ ăn.

### 6.2. Loại trải nghiệm của địa điểm

Mỗi loại địa điểm có khung giờ phù hợp riêng:

- Cà phê: buổi sáng hoặc buổi chiều
- Ăn trưa: khoảng 11:30–13:30
- Ăn tối: khoảng 18:00–20:00
- Bảo tàng/di tích: buổi sáng hoặc đầu giờ chiều
- Công viên/hồ/đi bộ: sáng sớm hoặc chiều mát
- Chợ đêm/phố đêm: buổi tối

### 6.3. Thời lượng nên ở lại

Mỗi địa điểm có thời lượng trải nghiệm khác nhau:

- Quán cà phê: khoảng 45–60 phút
- Bảo tàng: khoảng 60–90 phút
- Ăn trưa/ăn tối: khoảng 45–60 phút
- Đi bộ/check-in: khoảng 45–75 phút

Ví dụ, nếu `Cà phê Giảng` được xếp `08:00 - 09:15`, lý do có thể là: đây là điểm cà phê phù hợp buổi sáng, cần khoảng 60–75 phút để gọi đồ, ngồi nghỉ và trải nghiệm không gian.

### 6.4. Thời gian di chuyển giữa các điểm

Hệ thống phải chừa khoảng trống để người dùng di chuyển từ điểm A sang điểm B.

Ví dụ:

```text
08:00 - 09:15  Cà phê Giảng
10:00 - 11:00  Dạo quanh Hồ Gươm
```

Khoảng trống `09:15 - 10:00` có thể dùng cho di chuyển, nghỉ nhẹ hoặc tránh lịch quá sát.

### 6.5. Tối ưu tuyến đường

Nếu các điểm gần nhau, hệ thống nên xếp liên tiếp để giảm di chuyển vòng vèo.

Ví dụ cụm Hoàn Kiếm có thể xếp gần nhau:

- Cà phê Giảng
- Hồ Gươm
- Phố cổ
- Phở Bát Đàn

### 6.6. Ngữ cảnh người dùng

Nếu người dùng nói:

```text
Muốn chill, không đi quá nhiều.
```

Hệ thống nên xếp lịch thưa hơn, thời gian ở mỗi điểm dài hơn.

Nếu người dùng nói:

```text
Muốn đi nhiều điểm nổi tiếng.
```

Hệ thống có thể xếp nhiều điểm hơn, mỗi điểm ngắn hơn nhưng vẫn phải đủ thời gian di chuyển.

### 6.7. Thời tiết và trải nghiệm thực tế

Nếu có dữ liệu thời tiết, hệ thống có thể chọn khung giờ dễ chịu hơn:

- Trời nóng: ưu tiên điểm trong nhà vào buổi trưa
- Trời đẹp: ưu tiên hồ/công viên vào sáng hoặc chiều
- Trời mưa: ưu tiên bảo tàng, quán cà phê, nhà hàng

Ví dụ:

```text
15:00 - 16:30  Hồ Tây
```

Lý do: buổi chiều mát hơn, ánh sáng đẹp hơn và phù hợp để ngắm hồ/hoàng hôn.

### 6.8. Ghi chú lý do cho từng slot

Để lịch trình dễ hiểu hơn, mỗi slot thời gian nên có một lý do nội bộ hoặc ghi chú ngắn giải thích vì sao địa điểm đó được xếp vào khung giờ đó.

Ví dụ:

```text
08:00 - 09:15  Cà phê Giảng
Lý do: Phù hợp buổi sáng, gần khu Hồ Gươm, thời lượng vừa đủ để ăn sáng/uống cà phê trước khi đi bộ.

12:30 - 13:30  Phở Bát Đàn
Lý do: Khớp khung giờ ăn trưa, nằm gần tuyến phố cổ, chi phí phù hợp ngân sách.

19:00 - 20:30  Chợ đêm Đồng Xuân
Lý do: Đây là chợ đêm nên phải xếp buổi tối, phù hợp trải nghiệm mua sắm/ăn vặt.
```

Ví dụ lịch trình:

```text
08:00 - 09:15  Cà phê Giảng
10:00 - 11:00  Dạo quanh Hồ Gươm
12:30 - 13:30  Ăn trưa Phở Bát Đàn
15:00 - 16:00  Tham quan Hoàng Thành
```

## 7. Vai trò của AI

AI chỉ hỗ trợ, không được tự quyết định toàn bộ lịch trình một cách không kiểm soát.

AI có thể hỗ trợ:

- Hiểu ý định người dùng
- Gợi ý nhóm địa điểm phù hợp
- Viết mô tả lịch trình tự nhiên hơn
- Ước tính metadata cho địa điểm ngoài catalog nếu người dùng nhập địa điểm mới

Tuy nhiên, backend vẫn kiểm tra cuối cùng:

- Địa điểm phải nằm trong danh sách tin cậy hoặc đã được xác minh
- Không trùng điểm
- Không vượt ngân sách
- Không sai giờ mở cửa
- Không xếp chợ đêm vào buổi sáng
- Timeline phải hợp lý

## 8. Lưu và thao tác với kế hoạch

Sau khi tạo xong, kế hoạch được lưu theo token/session. Người dùng có thể:

- Xem lịch trình
- Lưu kế hoạch
- Tải PDF
- Thêm vào lịch
- Thay đổi một địa điểm
- Xóa địa điểm
- Xem bản đồ
- Click marker trên bản đồ để mở Google, TikTok hoặc Maps xem thêm thông tin/review

## Tóm tắt

Hệ thống không chỉ “dùng AI viết lịch trình”. Nó là một pipeline gồm:

```text
Yêu cầu người dùng
→ Catalog địa điểm thật
→ Lọc theo tiêu chí
→ Sắp tuyến
→ Kiểm tra giờ/ngân sách/trùng lặp
→ AI hỗ trợ diễn đạt/chọn lọc
→ Lịch trình hoàn chỉnh
```

Cách này giúp lịch trình thực tế hơn, ít bị bịa địa điểm và dễ kiểm soát chất lượng.
