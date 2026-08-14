# Yêu cầu chi tiết cho AI thực hiện (tự chứa)

File này là đầy đủ yêu cầu để AI triển khai hệ thống sinh lịch trình du lịch. AI không cần đọc tài liệu nào khác. Mọi bối cảnh, quyết định, công thức, nguồn dữ liệu và tiêu chí hoàn thành đều nằm trong file này.

## 1. Tổng quan hệ thống

Hệ thống nhận yêu cầu du lịch của người dùng bằng câu tự nhiên và biểu mẫu, rồi tạo ra một lịch trình có giờ giấc, có lý do cho từng lựa chọn.

Luồng hoạt động 10 bước:

```
Người dùng gõ yêu cầu
→ 1. Hiểu yêu cầu: rút ra số ngày, số người, sở thích, điều không thích, ràng buộc.
→ 2. Thu thập dữ liệu: thu thập địa điểm từ bộ địa điểm và các nguồn bổ sung.
→ 3. Lọc và xếp hạng: chấm điểm từng địa điểm theo mức phù hợp.
→ 4. Cung cấp thông tin: giờ mở cửa, vị trí, giá, nhận xét, ảnh.
→ 5. Chọn thời điểm: gắn khung giờ thích hợp cho từng điểm.
→ 6. Ước lượng thời lượng: mỗi điểm nên dành bao lâu.
→ 7. Tính thời gian di chuyển: giữa các điểm với nhau.
→ 8. Sinh lịch trình: bộ giải xếp các điểm vào khung giờ của từng ngày.
→ 9. Giải thích: kèm lý do cho từng lựa chọn.
→ 10. Đánh giá chất lượng: chạy thước đo tính khả thi, độ phủ, độ hợp lệ.
→ Lịch trình cuối cùng
```

Nói gọn: bước 1 đến 7 chuẩn bị nguyên liệu (địa điểm, giờ giấc, thời lượng, khoảng cách), bước 8 tạo ra lịch, bước 9 và 10 làm lịch đáng tin cậy.

Thị trường phục vụ: du lịch nội địa Việt Nam. Tám thành phố trọng tâm: Hà Nội, TP.HCM, Hạ Long, Đà Nẵng, Hội An, Nha Trang, Phú Quốc, Sa Pa.

## 2. Thuật ngữ

- **Bóc tách**: chuyển câu tự nhiên thành dữ liệu có cấu trúc.
- **Bộ địa điểm**: kho dữ liệu địa điểm nội bộ của hệ thống.
- **Nhãn dán (tag)**: nhãn mô tả địa điểm, gồm loại hình cơ bản (tham quan, ăn uống, di tích...) và tag ngữ nghĩa (healing, chữa lành, phù hợp trẻ em, giá rẻ...).
- **Mức phù hợp**: thước đo độ khớp giữa địa điểm và sở thích người dùng. Định nghĩa vận hành: số sở thích người dùng nêu có ít nhất một địa điểm đáp ứng, tính theo kiểu cần đủ (không lấy trung bình). Chỉ chấm trên nhãn do con người gán, không bao giờ dùng điểm số của chính hệ thống làm đáp án chuẩn.
- **Bộ giải**: chương trình toán học xếp các địa điểm vào khung giờ để ra lịch trình khả thi.
- **Chặn cứng**: loại hẳn địa điểm trước khi chấm điểm (ví dụ đóng cửa, quá xa, thiếu dữ liệu quan trọng).
- **Đáp án vàng**: kết quả mẫu do con người làm để chấm hệ thống.
- **Học vẹt**: hệ thống đạt điểm cao vì thuộc lòng bộ kiểm tra chứ không thực sự làm đúng.
- **Thước đo gian lận**: cách đạt điểm bằng lối tắt (ví dụ trả lịch rỗng để đạt độ hợp lệ).
- **Bản chụp đóng băng**: dữ liệu cố định có số phiên bản để kiểm tra, không gọi dịch vụ trực tiếp khi đo.
- **Chính sách độ cũ dữ liệu**: quy định mỗi loại dữ liệu dùng được trong bao lâu và nhịp làm mới.

## 3. Quy tắc chung

- Viết theo chuẩn dự án: tiếng Việt rõ ràng, không dùng dấu gạch ngang (ngang dài, ngang ngắn) trong câu văn.
- Không tự bịa số liệu, giờ, thời lượng, điểm đánh giá. Thiếu dữ liệu thì đánh dấu "thiếu dữ liệu".
- Mọi quyết định phải kèm ghi chú xuất xứ: mục này từ đâu, lấy lúc nào.
- Trọng số và tham số đưa ra phải ghi rõ là "mức khởi đầu" và nêu cách kiểm chứng.
- Ghi nhật ký mỗi lần thay đổi thuật toán hoặc trọng số: phiên bản, lý do, kết quả trước và sau.
- Không bao giờ để trí tuệ nhân tạo tự viết điểm đánh giá, giờ mở cửa, thời lượng hoặc lý do mới.
- Trí tuệ nhân tạo không nằm trong vòng sinh lịch (bước 8); nó chỉ dùng ở bước 1 (bóc tách) và bước 9 (diễn đạt câu trả lời từ bằng chứng đã khóa).

## 4. Kiến trúc tổng thể

Luồng dữ liệu chính:

```
Thông tin đầu vào (biểu mẫu + bóc tách bằng trí tuệ nhân tạo, đã kiểm tra)
    ▼
Xác định vùng và điểm đến (đối chiếu bản đồ, gán vùng, chặn lỗi "Hạ Long ra Hà Nội")
    ▼
Thu thập dữ liệu (bộ địa điểm + bản đồ mở + bộ địa điểm mở + dữ liệu cào Google Maps lưu tạm + cẩm nang) [lọc trạng thái đóng cửa]
    ▼
Lọc và xếp hạng (chấm điểm nhiều tiêu chí + gom theo không gian)
    ▼
Sinh lịch trình (bộ giải tối ưu theo ràng buộc)
    ▼
Giải thích + kiểm tra chất lượng
    ▼
Lịch trình cuối cùng
```

Dữ liệu nền (lớp phụ, phục vụ mọi bước): giờ hoạt động, sự kiện, lịch nghỉ lễ Việt Nam, thời tiết và thiên văn, thời lượng (khoảng cộng độ tin cậy), tính đường và xe buýt metro (thử nghiệm), cẩm nang và lịch trình mẫu.

## 5. Các nguồn dữ liệu và điều kiện

-**OpenStreetMap (bản đồ mở)**: Nguồn chính để lấy địa điểm thật trên toàn Việt Nam: nhà hàng, cafe, khách sạn, nhà nghỉ, điểm tham quan, di tích, bãi biển, núi, hang động, công viên…Lấy ra Tên địa điểm, loại địa điểm, tọa độ, khu vực, địa chỉ nếu có, tag, giờ mở cửa nếu OSM có, nguồn URL, mã OSM.
- **Wikimedia Commons**: Lấy ảnh cho một số địa điểm nổi tiếng nếu match được. Lấy Mã Wikidata, liên kết định danh cho địa điểm nổi tiếng, một số metadata dùng để xác nhận địa điểm đúng.
- **Wikidata**: Lấy mã định danh/thông tin liên kết cho các địa điểm nổi tiếng. Lấy Ảnh địa điểm, credit ảnh, Commons category nếu có.
- **Google Places API**: Dùng runtime khi có API key để lấy/cập nhật thông tin mới hơn cho địa điểm được gọi trong lịch trình, rồi cache lại.Lấy Ảnh mới hơn, thông tin Google Place, giờ mở/đóng cửa nếu bật cấu hình, metadata địa điểm theo Google, dữ liệu cache theo địa điểm đã gọi.

- **Google Maps (cào dữ liệu địa điểm)**: dùng cho chi tiết địa điểm (giờ mở cửa, điểm đánh giá, nhận xét, ảnh, giá, mô tả, trạng thái đóng cửa). Mất phí (hạ tầng cào gồm trình duyệt tự động, mạng đổi địa chỉ IP, công bảo trì). Lấy được toàn bộ nhận xét và ảnh, kể cả giờ đông người. **Vi phạm điều khoản của Google**: rủi ro chặn địa chỉ IP, khóa tài khoản, khiếu nại pháp lý. Phải lưu tạm vào bộ nội bộ và cào khi cần để giảm rủi ro.

- **Wikivoyage (cẩm nang du lịch mở)**: dùng cho lớp biên tập (điểm đáng đi). Giấy phép CC BY SA, tệp nội dung chính khoảng 130 MB, có bản tiếng Việt nhỏ (khoảng 1.500 bài).
- **Foursquare OS Places (bộ địa điểm mở)**: dùng bổ sung hoặc đối chiếu. Khoảng 100 triệu bản ghi (con số do hãng tự công bố, chưa có kiểm toán độc lập), giấy phép Apache 2.0. Giao diện dữ liệu cũ ngừng hoạt động từ 15/5/2026.
- **Cơ sở dữ liệu du lịch quốc gia**: khoảng 980 điểm đến theo 34 tỉnh, thành (Việt Nam sáp nhập còn 34 tỉnh, thành từ 1/7/2025). Nguồn chính thức cho nội dung địa phương. Hạn chế: phủ thưa, tọa độ đôi khi không chính xác, chưa có cổng dữ liệu công khai ổn định.
- **Dịch vụ chỉ đường Google**: dùng cho thời gian dự kiến tính giao thông và xe máy hiển thị. Mất phí theo mức sử dụng, miễn phí hạn chế theo gói và theo từng cặp xuất phát và điểm đến. Chế độ xe máy thuộc gói trả phí cao nhất.
- **Valhalla**: chương trình tính đường tự lưu trữ, bản phát hành hiện tại 3.8.3 (ngày 24/7/2026). Tính đường, bảng thời gian di chuyển, vùng tới được, tối ưu thứ tự điểm, phương tiện công cộng kết hợp lịch xe buýt. Miễn phí phần mềm, tốn vận hành. Giao thông thời gian thực ở Việt Nam gần như không có, nên thời gian dự kiến chỉ là đường thông thoáng. Tối ưu thứ tự điểm không hỗ trợ phương tiện công cộng. Hồ sơ xe máy hiện là gần đúng thô.
- **Dữ liệu lịch trình phương tiện công cộng (GTFS)**: ở Việt Nam chỉ có đúng một nguồn công khai cho xe buýt Hà Nội (World Bank và TUMI), lịch đóng băng năm 2018, không còn khớp mạng lưới thực tế (tháng 3/2026: 155 tuyến, 5.024 điểm dừng, 11 đơn vị vận hành). Hà Nội và Transerco chưa công bố dữ liệu chính thức cho 2025 và 2026. Metro Hà Nội tuyến 2A (từ 11/2021), đoạn trên cao tuyến 3.1 (từ 8/2024), metro TP.HCM tuyến 1 (từ 22/12/2024). Phương tiện công cộng chỉ ở trạng thái thử nghiệm: dữ liệu chỉ được nạp nếu lịch mới không quá 90 ngày và khớp danh sách tuyến chính thức; dữ liệu 2018 phải bị chặn tự động.
- **OpenMeteo**: dự báo thời tiết và thiên văn. Miễn phí chỉ phi thương mại; dùng thương mại thì mất phí.
- **Tripadvisor Terra**: dùng cho nhận xét và nội dung du lịch. Tài khoản mới bắt buộc. Giao diện dữ liệu cũ ngừng hoạt động 31/8/2026.
- **Amadeus**: dùng cho tour, hoạt động, vé. Chỉ qua cổng doanh nghiệp. Cổng tự phục vụ đóng 17/7/2026.
- **Trang web chính thức của địa điểm**: dùng cho giờ, giá, tour, biểu diễn, sự kiện, thời lượng. Miễn phí, phải tự lấy từng trang.

Quyết định chung về nguồn: dữ liệu cào OpenStreetMap / Overpass làm nguồn chính cho chi tiết địa điểm,Wikimedia Commons và Wikidata làm nguồn bổ sung dữ liệu cho các địa điểm tham quan, Google mapp bổ sung dữ liệu còn thiếu khi hệ thống sinh lịch trình gọi tới địa điểm đó mà còn thiếu trường dữ liệu, cơ sở dữ liệu quốc gia làm nguồn nội dung địa phương. Không phụ thuộc một nguồn.

## 6. Phạm vi bản thử nghiệm


- Phải tuyên bố rõ phạm vi: toàn bộ 10 bước là "làm một lần rồi thôi". Nếu bản thử nghiệm là trò chuyện, phải thêm chức năng "làm lại hoặc đổi 1 điểm" ("đổi A lấy B", "ngày 2 nhẹ lại"): khóa khung giờ đã xác nhận, chạy lại bộ giải phần còn lại, áp lại ràng buộc toàn cục (sở thích "không thích" phải gỡ ở mọi ngày, không chỉ hôm nay). Hoặc ghi rõ "bản thử nghiệm làm một lần, mỗi thay đổi là sinh lại lịch". Không được im lặng nhận lệnh đổi rồi bỏ qua.

* * *

## 7. Bài toán 1: Hiểu yêu cầu đầu vào

**Vấn đề:** Người dùng gõ câu tự nhiên, ví dụ "Tôi đi Hạ Long 2 ngày, thích ăn hải sản, muốn đi những chỗ nổi tiếng, không thích cáp treo và mỗi ngày không muốn đi quá 4 chỗ." Hệ thống phải ra dữ liệu có cấu trúc: điểm đến, số ngày, số người, ngân sách, sở thích, không thích, ràng buộc, mục bắt buộc. Không được bịa phần người dùng không nói.

**Quyết định:** Dùng phương án C: phần định lượng dễ sai (số người, ngân sách) khóa cứng bằng biểu mẫu, phần định tính (sở thích, không thích) cho trí tuệ nhân tạo bóc tách, bộ kiểm tra đứng sau cùng để chặn bịa. Không để trí tuệ nhân tạo tự đoán mọi thứ vì sai ngày nghĩa là sai toàn bộ lịch.

**Nhiệm vụ:**
- [ ] Tách phần bóc tách bằng trí tuệ nhân tạo khỏi biểu mẫu, dùng chung một khung dữ liệu đầu ra.
- [ ] Gắn ghi chú xuất xứ cho từng mục: giá trị lấy từ biểu mẫu hay do trí tuệ nhân tạo suy ra.
- [ ] Khi thiếu mục bắt buộc, hệ thống hỏi lại người dùng, không được đoán.
- [ ] Lưu kết quả bóc tách để đo chất lượng (xem Bài toán 10, nhiệm vụ đo 2 bước trí tuệ nhân tạo).

**Tiêu chí hoàn thành:**
- Khung dữ liệu đầu ra có đủ các trường liệt kê ở trên.
- Không có trường nào bị bịa khi người dùng không nói.
- Mọi giá trị đều có ghi chú xuất xứ.

## 8. Bài toán 2: Thu thập dữ liệu

**Vấn đề:** Từ yêu cầu, thu thập danh sách địa điểm thật, đúng vùng, đúng loại. Đây là tầng quyết định chất lượng nhất: dữ liệu nghèo thì mọi bước sau đều kém.

**Quyết định:** Nguồn như mục 5. Ngoài ra phải làm 3 điều bắt buộc: bước xác định vùng riêng, lọc địa điểm đã đóng cửa, giới hạn bản thử nghiệm một điểm đến.

**Nhiệm vụ:**
- [ ] Xây bước xác định vùng riêng trong đường ống: chuyển tên điểm đến thành vùng tìm kiếm, chặn lỗi "Hạ Long ra Hà Nội".
- [ ] Lọc địa điểm đã đóng cửa (đóng hẳn hoặc tạm đóng) trước khi đưa vào bộ địa điểm, vì đưa người dùng tới điểm đã đóng là kết cục tệ nhất.
- [ ] Giới hạn bản thử nghiệm ở một điểm đến.
- [ ] Kiểm tra luồng cào Google Maps: lấy, lưu tạm, tránh bị chặn địa chỉ IP.

**Tiêu chí hoàn thành:**
- Kiểm tra tự động không còn lỗi "yêu cầu Hạ Long trả về Hà Nội".
- Không có địa điểm đã đóng cửa trong danh sách ứng viên.
- Bản thử nghiệm chạy đúng cho một điểm đến.

## 9. Bài toán 3: Lọc và xếp hạng địa điểm

**Vấn đề:** Có từ 50 đến 100 ứng viên nhưng chỉ nên cho người dùng thấy từ 5 đến 10 cái tốt nhất theo: mức phù hợp, điểm đánh giá, khoảng cách, giờ mở cửa, giới hạn số điểm mỗi ngày.

**Quyết định:** A cộng B. A chấm điểm nhiều tiêu chí để chọn danh sách, B gom theo không gian để giảm di chuyển trước khi dồn lịch. Trọng số phải được định nghĩa và kiểm tra bằng bộ kiểm tra ở Bài toán 10, không để tự do. Ưu tiên địa điểm gần vị trí người dùng và gần tuyến di chuyển (dựa vào location). Ánh xạ thêm tag ngữ nghĩa (healing, chữa lành, phù hợp trẻ em, giá rẻ...) ngoài loại hình cơ bản. Trọng số sẽ thay đổi tùy theo cách người dùng sử dụng hệ thống.

**Công thức chấm điểm (mức khởi đầu):** 5 tiêu chí, mỗi tiêu chí chuẩn hóa về thang 0 đến 100:
- **Mức phù hợp** (trọng số khởi đầu 30): số sở thích khớp với loại hình hoặc tag chia tổng sở thích nhân 100. Khớp thêm tag ngữ nghĩa cộng 5 mỗi tag, tối đa cộng 20. Khớp điều người dùng "không thích" thì trừ 30. Không có sở thích nào thì cho 50.
- **Điểm đánh giá** (trọng số khởi đầu 25): điểm Google chia 5 nhân 100, ví dụ 4,5 sao ra 90. Thiếu thì cho 40 và đánh dấu thiếu dữ liệu.
- **Vị trí và khoảng cách** (trọng số khởi đầu 20): dưới 1 km được 100, từ 1 đến 3 km được 80, từ 3 đến 5 km được 60, từ 5 đến 10 km được 40, trên 10 km được 20. Gần tuyến di chuyển chính cộng 10. Quá 15 km chặn cứng.
- **Mức khớp giờ mở cửa** (trọng số khởi đầu 15): mở đủ khung giờ dự kiến được 100, mở một phần được 50, đóng trong khung giờ chặn cứng, thiếu dữ liệu giờ chặn cứng.
- **Số nhận xét** (trọng số khởi đầu 10): từ 1.000 trở lên được 100, từ 100 đến 999 được 80, từ 10 đến 99 được 60, từ 1 đến 9 được 40, không có được 20.

Điểm tổng = (30 nhân mức phù hợp + 25 nhân điểm đánh giá + 20 nhân vị trí + 15 nhân mức khớp giờ + 10 nhân số nhận xét) chia 100, làm tròn 2 chữ số. Xếp hạng theo điểm giảm dần sau khi gỡ trùng.

**Các phương án thay đổi trọng số theo người dùng** (chọn ít nhất 1):
1. Học theo hành vi cá nhân: sau mỗi phiên, so địa điểm người dùng giữ lại với địa điểm bị bỏ, tăng trọng số của tiêu chí mà địa điểm được giữ vượt trội, giảm trọng số của tiêu chí mà địa điểm bị bỏ vượt trội.
2. Theo nhóm người dùng: gom người dùng có hành vi giống nhau (đi cùng gia đình, thích ăn uống, đi tiết kiệm, đi nhanh) thành nhóm, mỗi nhóm một bộ trọng số; người mới dùng trọng số của nhóm hợp nhất để giảm lạnh lúc đầu.
3. Tối ưu theo đáp án vàng: định kỳ hiệu chỉnh trọng số chung để tái tạo thứ tự xếp hạng mẫu do con người làm.
4. Người dùng tự chỉnh: cho người dùng kéo mức ưu tiên trong giao diện (sở thích, điểm đánh giá, khoảng cách), lưu vào hồ sơ người dùng.
5. Theo ngữ cảnh chuyến đi: đổi trọng số theo hoàn cảnh (đi cùng gia đình, đi một mình, tiết kiệm, cần yên tĩnh).

**Nhiệm vụ:**
- [ ] Triển khai chấm điểm 5 tiêu chí theo công thức trên.
- [ ] Áp chặn cứng trước khi chấm điểm: đóng cửa, quá 15 km, thiếu giờ.
- [ ] Ánh xạ tag ngữ nghĩa cho địa điểm từ dữ liệu cào và nguồn biên tập.
- [ ] Xây đường ống thu thập tín hiệu hành vi và triển khai ít nhất 1 phương án thay đổi trọng số.
- [ ] Áp giới hạn an toàn: mỗi trọng số lệch tối đa 15 điểm quanh giá trị khởi đầu trừ khi đáp án vàng ủng hộ; chỉ dùng tín hiệu hành vi thật (giữ, bỏ, xem chi tiết), không dùng điểm của chính hệ thống; ghi nhật ký mỗi lần đổi; người mới dùng bộ mặc định tới khi đủ 5 lượt giữ hoặc bỏ.
- [ ] Triển khai bước B gom theo không gian trước khi dồn lịch.

**Tiêu chí hoàn thành:**
- Có bộ kiểm tra xếp hạng với đáp án vàng do con người gán.
- Kết quả xếp hạng giải thích được bằng điểm từng tiêu chí.
- Nhật ký đổi trọng số có phiên bản và lý do.

## 10. Bài toán 4: Cung cấp thông tin để người dùng đánh giá

**Vấn đề:** Người dùng cần đủ thông tin để giữ hoặc bỏ một địa điểm: điểm đánh giá, số nhận xét, ảnh, giờ mở cửa, giá, mô tả, nguồn. Thiếu thông tin thì người dùng không tin lịch.

**Quyết định:** Cào làm chuẩn (điểm đánh giá, nhận xét, ảnh đầy đủ), trang web chính thức cho dữ liệu vận hành quan trọng (giờ, vé, lịch biểu diễn), nguồn bổ trợ làm phụ. Không bao giờ để trí tuệ nhân tạo tự viết điểm đánh giá hay giờ.

**Nhiệm vụ:**
- [ ] Đảm bảo mỗi địa điểm có: điểm đánh giá, số nhận xét, ảnh, giờ mở cửa, giá, mô tả, nguồn.
- [ ] Lấy dữ liệu vận hành từ trang web chính thức khi cần.
- [ ] Chặn hoàn toàn việc trí tuệ nhân tạo tự sinh điểm đánh giá hoặc giờ.

**Tiêu chí hoàn thành:**
- Địa điểm thiếu dữ liệu quan trọng bị đánh dấu rõ hoặc bị loại.
- Không có nhận xét hoặc giờ nào do trí tuệ nhân tạo bịa ra.

## 11. Bài toán 5: Chọn thời điểm phù hợp để đến

**Vấn đề:** "Được đi lúc nào" và "nên đi lúc nào" là hai việc khác nhau. Ví dụ: bảo tàng mở 10 giờ đến 17 giờ nên được đi trong khoảng đó; chợ đêm chỉ sống buổi tối nên đi sau 18 giờ; điểm ngắm cảnh nên đi gần hoàng hôn.

**Quyết định:** A (lịch hoạt động: giờ mở cửa cộng lịch tour, biểu diễn, sự kiện) cộng B (thiên văn cộng thời tiết cộng sự kiện). C (giờ đông người) chỉ dùng khi có dịch vụ trả phí bên thứ ba. Bắt buộc thêm lịch nghỉ lễ Việt Nam: Tết Nguyên đán, từ 30/4 đến 1/5, 2/9. Mọi nguồn dữ liệu đều sai giờ mở cửa trong tuần Tết, mà Tết là tuần cao điểm nhất. Cần ghi chú "giờ có thể đổi theo từng năm".

**Nhiệm vụ:**
- [ ] Research thêm các tiêu chí về thời gian đi ngoài danh sách hiện có (giờ mở cửa, giờ đông người, bữa ăn, tránh nắng): mùa du lịch, lễ hội và sự kiện, thời tiết theo khung giờ, giờ cao điểm giao thông, khung giờ khuyến nghị của từng địa điểm.
- [ ] Với mỗi tiêu chí đề xuất, đánh giá độ khả thi về dữ liệu (có nguồn không, lấy được không) rồi mới đưa vào.
- [ ] Bổ sung lịch nghỉ lễ Việt Nam và ghi chú giờ có thể đổi theo từng năm.
- [ ] Gắn thiên văn (hoàng hôn) vào bộ lập lịch.
- [ ] Lưu ý OpenMeteo: nếu sản phẩm thương mại phải mua gói trả phí, không dùng mức miễn phí.

**Tiêu chí hoàn thành:**
- Danh sách tiêu chí thời gian đi đã cập nhật, mỗi tiêu chí kèm nguồn dữ liệu.
- Lịch trình sinh cho tuần Tết không dùng giờ mở cửa bình thường.

## 12. Bài toán 6: Thời gian nên ở mỗi địa điểm

**Vấn đề:** Trả lời được "sao A 2 giờ, B 45 phút?". Không nên gán một thời lượng cố định cho mọi điểm.

**Quyết định:** Ưu tiên B (khuyến nghị từ nguồn chính thức hoặc cẩm nang), rồi mới C (khoảng theo đặc tính địa điểm). C dùng dạng khoảng cộng độ tin cậy, không ép thành một số. Khoảng dự phòng theo loại, ví dụ bảo tàng lớn từ 90 đến 180 phút, điểm ngắm cảnh từ 30 đến 90 phút, quán cà phê từ 45 đến 90 phút. Đây là ước lượng có cấu trúc, phải kiểm tra và hiệu chỉnh.

**Nhiệm vụ:**
- [ ] Lưu thời lượng dạng khoảng cộng độ tin cậy.
- [ ] Thứ tự lấy dữ liệu: nguồn Google, nguồn chính thức và cẩm nang, hướng dẫn đã kiểm chứng, cuối cùng là phương án dự phòng theo loại.
- [ ] Trí tuệ nhân tạo không được tự bịa thời lượng khi thiếu bằng chứng.

**Tiêu chí hoàn thành:**
- Mọi thời lượng đều có nguồn hoặc bị đánh dấu là ước lượng.

## 13. Bài toán 7: Tính thời gian di chuyển

**Vấn đề:** Thời gian thực từ A đến B phụ thuộc phương tiện, giờ khởi hành, giao thông. Đây là chỗ dễ làm lịch "ảo" nhất.

**Quyết định:** Cho bản thử nghiệm dùng phương pháp đơn giản: nối các địa điểm theo đường thẳng, khoảng cách và thời gian tính theo tốc độ chim bay. Đây là phương án tạm, phải ghi rõ trạng thái này, vì nó mâu thuẫn với quyết định chung: không dùng công thức đường chim bay làm nguồn chính cho sản phẩm thật, sai số di chuyển trong thành phố quá lớn. Hướng dài hạn: Valhalla cho bảng thời gian di chuyển của bộ giải (triển khai từ ngày đầu khi đủ điều kiện), Google cho thời gian dự kiến tính giao thông và xe máy hiển thị. Lưu tạm bảng thời gian di chuyển theo thành phố và khung giờ để giảm chi phí. Xe máy là phương tiện chủ đạo ở Việt Nam: nếu không dùng gói có chế độ xe hai bánh, phải công bố rõ thời gian dự kiến là đường thông thoáng, không phải chính xác xe máy.

**Nhiệm vụ:**
- [ ] Triển khai tính khoảng cách giữa hai địa điểm theo đường thẳng từ tọa độ.
- [ ] Triển khai tính thời gian bằng khoảng cách chia tốc độ chim bay giả định cho từng phương tiện (đi bộ, xe máy, ô tô).
- [ ] Định nghĩa tốc độ giả định ban đầu và hệ số nhân để bù sai số so với đường thực.
- [ ] Đưa kết quả vào bảng thời gian di chuyển và dùng trong bộ giải.
- [ ] Ghi chú trong tài liệu: đây là cách tạm cho bản thử nghiệm, không phải quyết định thay thế.
- [ ] Làm rõ chi tiết: nêu rõ công thức, giới hạn sai số, cách kiểm chứng.

**Tiêu chí hoàn thành:**
- Bảng thời gian di chuyển chạy được cho bản demo.
- Tài liệu ghi rõ trạng thái "tạm cho bản thử nghiệm".

## 14. Bài toán 8: Sinh lịch trình hoàn chỉnh

**Vấn đề:** Từ địa điểm, giờ mở cửa, thời lượng, thời gian di chuyển, sở thích, ràng buộc, ra được lịch trình khả thi thật sự: không vi phạm giờ, không vượt tổng thời gian, hạn chế đi vòng, đúng sở thích.

**Quyết định:** A (tối ưu theo ràng buộc) cộng B (đồ thị địa điểm) làm phần lõi, C (điều chỉnh lịch trình mẫu) làm mốc so sánh hoặc phương án dự phòng. Trí tuệ nhân tạo không nằm trong vòng sinh lịch. Thuật toán đề xuất: OR Tools CP SAT (phù hợp từ 50 đến 100 ứng viên). Thứ tự ưu tiên chặt: tính khả thi, rồi độ phủ sở thích, rồi giảm di chuyển và chờ.

**Nhiệm vụ:**
- [ ] Triển khai bộ giải theo thứ tự ưu tiên: tính khả thi, độ phủ sở thích, giảm di chuyển và chờ.
- [ ] Dùng OR Tools CP SAT.
- [ ] Bổ sung ràng buộc ngân sách (đã thu ở bài toán 1 nhưng bộ giải chưa áp dụng).
- [ ] Bổ sung xử lý chỗ lưu trú (khách sạn đã được chọn nhưng chưa bài toán nào phụ trách).
- [ ] Quy định nhật ký ghi gì ở ranh giới bài toán 8 sang bài toán 9: ứng viên, điểm số từng tiêu chí, ràng buộc đã áp, thời gian, nguồn, ngày giờ lấy dữ liệu.
- [ ] Xử lý "làm lại hoặc đổi 1 điểm" theo phạm vi bản thử nghiệm ở mục 6.

**Tiêu chí hoàn thành:**
- Lịch trình trả về luôn khả thi về giờ giấc.
- Mọi lệnh đổi điểm đều được xử lý, không im lặng bỏ qua.

## 15. Bài toán 9: Giải thích vì sao chọn lịch trình

**Vấn đề:** Người dùng hỏi "sao chọn A trước B?", "sao 2 giờ ở A?". Hệ thống phải trả lời bằng bằng chứng, không bằng lời khẳng định.

**Quyết định:** A lưu dữ liệu (nhật ký bằng chứng), B tạo câu trả lời bằng luật và điểm số, C dùng trí tuệ nhân tạo làm đẹp câu chỉ khi đã khóa bằng chứng. Kèm chính sách độ cũ dữ liệu.

**Nhiệm vụ:**
- [ ] Lưu nhật ký bằng chứng cho mọi quyết định.
- [ ] Tạo câu trả lời từ nhật ký, ví dụ "A được chọn vì điểm đánh giá 4,7, cách B 12 phút, giờ mở cửa khớp khung giờ".
- [ ] Trí tuệ nhân tạo chỉ viết lại cho dễ đọc, bị cấm thêm sự thật.
- [ ] Xây chính sách độ cũ dữ liệu: thời hạn dùng theo từng loại mục (giờ mở cửa, giá, trạng thái hoạt động) và nhịp làm mới; trả lời được câu "dữ liệu cũ bao lâu thì không dùng nữa".

**Tiêu chí hoàn thành:**
- Mọi câu giải thích đều truy ra được bằng chứng trong nhật ký.
- Có chính sách độ cũ cụ thể theo từng loại mục.

## 16. Bài toán 10: Đánh giá chất lượng giải pháp

**Vấn đề:** So sánh các phương án bằng cùng một bộ kiểm tra, không chọn theo cảm giác. Bộ kiểm tra phải phủ: thông tin đầu vào rõ và thiếu, nhiều ràng buộc, dữ liệu mâu thuẫn, địa điểm đặc thù, lịch không khả thi, không có thời lượng, giờ cao điểm, xe buýt metro.

**Quyết định:** A (bộ kiểm tra cố định) cộng B (mô phỏng lịch trình) làm trước và định lượng; C (đánh giá chuyên gia) dùng kiểm chứng định tính sau mỗi thay đổi thuật toán. Ghi kết quả trước và sau mỗi lần đổi bộ giải.

**Đặc tả bắt buộc (chống "tự chấm bài"):**
1. Định nghĩa "mức phù hợp" vận hành: độ phủ là số sở thích người dùng nêu có ít nhất một địa điểm đáp ứng, tính theo cần đủ (không lấy trung bình); chấm trên nhãn do con người gán; không bao giờ lấy điểm số của chính hệ thống làm đáp án chuẩn (tránh vòng tròn tự chấm bài).
2. Chống học vẹt: 300 đến 600 kịch bản phân tầng (40 đến 75 mỗi thành phố), tách riêng 20 phần trăm để kiểm tra cuối, kèm 2 thành phố cách ly hẳn (thư mục riêng, chỉ đọc qua chương trình báo cáo); bản chụp dữ liệu đóng băng có số phiên bản (nhãn dán của bộ địa điểm và kết quả bóc tách, không gọi dịch vụ trực tiếp khi đo); đăng ký trước thước đo chính và ngân sách xem kết quả trước khi tinh chỉnh; khoảng tin cậy theo từng vùng; đáp án vàng từ chuyên gia với mức đồng thuận từ 0,6 trở lên; bộ kịch bản ngoài vùng quen chỉ chạy khi phát hành.
3. Mốc so sánh bắt buộc trong mọi lần chạy: (a) bộ giải phiên bản cũ; (b) lịch trình mẫu do người biên tập làm sẵn cho thành phố; (c) trí tuệ nhân tạo chung không học thêm (như ChatGPT, Gemini) bóc tách vào cùng khung dữ liệu. Hai mốc (b) và (c) nguy hiểm nhất: với 8 thành phố trọng tâm, lịch trình mẫu biên tập kỹ và trí tuệ nhân tạo chung nhiều khả năng thắng bộ sinh lịch tự động ở tình huống thông thường. Nếu bộ giải thua lịch trình mẫu ở tình huống phổ biến ("Hạ Long 2 ngày"), dùng lịch trình mẫu làm mặc định, bộ giải phục vụ nhu cầu ít gặp. Thua mốc so sánh là không được phát hành và phải báo rõ trong báo cáo.
4. Chống thước đo gian lận: lịch dùng ít hơn 60 phần trăm khung giờ khả thi là không hợp lệ (chặn "trả lịch rỗng"); gác thử theo thứ tự tính khả thi, rồi độ phủ, rồi chất lượng.
5. Đo cả 2 bước trí tuệ nhân tạo (bài toán 1 bóc tách, bài toán 9 giải thích): bài toán 1 đo độ chính xác, độ đầy đủ từng mục, tỷ lệ bịa trên 100 đến 200 yêu cầu tiếng Việt có nhãn; bài toán 9 đo so khớp từng câu với nhật ký (không được thêm sự thật) cộng lấy mẫu đối chiếu nguồn.
6. Đo sau khi ra mắt: tỷ lệ người dùng sửa khung giờ, mức người dùng có đi theo lịch không, tỷ lệ bỏ dở, và 1 nghiên cứu thực địa ở thành phố trọng điểm.
7. Đánh giá chuyên gia (C): cần bảng tiêu chí chấm điểm (phù hợp, hợp lý, thực tế, đúng sự thật, giải thích), thử trước đến khi mức đồng thuận từ 0,6 trở lên; không bao giờ dùng trí tuệ nhân tạo làm người chấm duy nhất cho thước đo chặn phát hành.

**Nhiệm vụ:**
- [ ] Xây bộ kiểm tra theo đặc tả trên.
- [ ] Chạy mốc so sánh (a), (b), (c) trong mọi lần chạy.
- [ ] Ghi báo cáo trước và sau mỗi lần đổi bộ giải.

**Tiêu chí hoàn thành:**
- Bộ kiểm tra chạy được và cho báo cáo trước sau mỗi lần đổi bộ giải.
- Không phát hành nếu thua mốc so sánh.

## 17. Dữ liệu

**Quyết định:** Cơ sở dữ liệu ban đầu ở mức thô sơ, đủ để chạy. Sau khi người dùng sử dụng hệ thống, dùng phía client của người dùng để bổ sung dữ liệu. Có thuật toán loại bỏ địa điểm thiếu dữ liệu khỏi lịch trình.

**Nhiệm vụ:**
- [ ] Dựng dữ liệu khởi tạo thô sơ cho 8 thành phố trọng tâm: tên, tọa độ, loại hình, giờ mở cửa (nếu có).
- [ ] Xây luồng bổ sung dữ liệu qua client người dùng: thu thập thông tin người dùng xem, giữ, dùng và gửi về để bổ sung.
- [ ] Xây thuật toán lọc: loại bỏ địa điểm thiếu dữ liệu quan trọng (tên, tọa độ, giờ mở cửa) khỏi lịch trình.
- [ ] Ghi nhãn nguồn gốc cho từng bản ghi: dữ liệu khởi tạo hay do người dùng bổ sung.

**Tiêu chí hoàn thành:**
- Hệ thống chạy được với dữ liệu khởi tạo.
- Dữ liệu do người dùng bổ sung đi vào đúng luồng và có nhãn nguồn gốc.
- Địa điểm thiếu dữ liệu không xuất hiện trong lịch trình.

* * *

## 18. Bảng theo dõi tiến độ

| Nhiệm vụ | Trạng thái | Ghi chú |
|---|---|---|
| Bài toán 1: bóc tách yêu cầu | [ ] | |
| Bài toán 2: thu thập dữ liệu | [ ] | |
| Bài toán 3: trọng số, location, tag | [ ] | |
| Bài toán 4: thông tin địa điểm | [ ] | |
| Bài toán 5: thêm tiêu chí thời gian đi | [ ] | |
| Bài toán 6: thời lượng khoảng cộng độ tin cậy | [ ] | |
| Bài toán 7: thời gian di chuyển đường thẳng | [ ] | |
| Bài toán 8: bộ giải OR Tools CP SAT | [ ] | |
| Bài toán 9: giải thích bằng bằng chứng | [ ] | |
| Bài toán 10: bộ kiểm tra và mốc so sánh | [ ] | |
| Dữ liệu: khởi tạo, bổ sung qua client, lọc thiếu | [ ] | |

Khi hoàn thành một nhiệm vụ, ghi vào cột Ghi chú: bằng chứng hoàn thành và ngày làm xong.
