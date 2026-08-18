# KẾ HOẠCH SỬA LỖI & NÂNG CẤP HỆ THỐNG LẬP LỊCH TRÌNH (FIX.MD)

Tài liệu này tổng hợp toàn bộ các lỗi chí mạng (Critical Bugs), lỗi logic thực tế và các tình huống ngoại lệ phát hiện qua kiểm thử chuyên sâu (Deep-Dive Testing), cùng giải pháp kỹ thuật cụ thể để khắc phục triệt để.

---

## I. TỔNG HỢP 5 LỖI CHÍ MẠNG TRONG LỊCH TRÌNH THỰC TẾ

### 1. Di chuyển con thoi phi lý giữa các thành phố (Ping-pong Routing)
- **Hiện tượng**: Lịch trình 2 ngày ở Đà Nẵng liên tục bắt khách chạy qua lại giữa Đà Nẵng và Hội An (cách nhau 30km) 4 lần trong 2 ngày (sáng ở Đà Nẵng → trưa vào Hội An ăn cơm gà → chiều về Đà Nẵng ngắm Cầu Rồng → hôm sau lại lặp lại).
- **Nguyên nhân**: Bán kính tìm kiếm `DESTINATION_RADIUS_KM = 45km` gom cả Đà Nẵng và Hội An vào chung một tập ứng viên mà không có cơ chế **phân cụm địa lý theo ngày (Spatial Clustering)**.
- **Giải pháp**:
  - Áp dụng thuật toán **K-Means / DBSCAN hoặc gom cụm theo bán kính** cho các điểm đã chọn: Mỗi ngày chỉ được hoạt động trong 1 cụm địa lý duy nhất (Bán kính cụm ≤ 10km).
  - Ngày 1 trọn vẹn ở Cụm Đà Nẵng; Ngày 2 chuyển hẳn sang Cụm Hội An.

### 2. Vi phạm điều cấm (Dislikes Violation) & Bỏ qua sở thích của User
- **Hiện tượng**:
  - User nói *"không thích leo núi mệt"* nhưng hệ thống vẫn xếp **Ngũ Hành Sơn** và **Bà Nà Hills**.
  - User nói *"ngắm hoàng hôn biển"* nhưng bị xếp ra biển lúc **21:12 đêm**.
  - User nói *"thích hải sản"* nhưng bị xếp ăn **Phở House**.
- **Nguyên nhân**: Các từ khóa cấm (`dislikes`) chỉ bị trừ điểm số nhẹ (`score -= 30`), nếu địa điểm có điểm nổi tiếng cao thì điểm tổng vẫn dương và vẫn lọt vào lịch trình.
- **Giải pháp**:
  - Chuyển `Dislikes` thành **Hard Filter (Chặn tuyệt đối)**: Nếu địa điểm chứa tag hoặc tên nằm trong danh sách cấm, loại bỏ 100% ngay từ Vòng 1, không cho phép tính điểm.
  - Gắn nhãn thời gian cho hoạt động biển: Điểm ngắm hoàng hôn biển bắt buộc gán khung giờ cứng `17:00 - 18:30`.

### 3. Trùng lặp địa điểm do dữ liệu bẩn (Duplicate Place Bug)
- **Hiện tượng**: Cùng 1 bảo tàng nhưng bị xếp đi 2 lần liên tiếp: `09:05 - 10:05` (Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng) và `10:10 - 11:25` (Bảo tàng Điêu khắc Chăm).
- **Nguyên nhân**: Dữ liệu có 2 bản ghi khác ID (1 từ OSM, 1 từ curated/seed) với tên gần giống nhau, hàm lọc trùng hiện tại chỉ kiểm tra `place.id` mà chưa chuẩn hóa tên và khoảng cách tọa độ.
- **Giải pháp**:
  - Chuẩn hóa tên bỏ dấu + kiểm tra khoảng cách tọa độ: Nếu 2 địa điểm có độ tương đồng tên ≥ 80% HOẶC cách nhau dưới 150m thì bắt buộc gộp thành 1 điểm duy nhất (Deduplication Layer).

### 4. Thời lượng tham quan phi thực tế (Unrealistic Visit Duration)
- **Hiện tượng**: Xếp Bà Nà Hills từ `16:00 đến 17:00` (đúng 60 phút).
- **Nguyên nhân**: Dữ liệu gán mặc định `duration_min = 60` cho tất cả các điểm mà không phân biệt khu du lịch phức hợp lớn (theme park / núi / đảo) với điểm tham quan nhỏ.
- **Giải pháp**:
  - Xây dựng bảng quy định thời lượng tối thiểu cho các điểm đặc thù:
    - Khu du lịch lớn (Bà Nà Hills, VinWonders, Sun World): Tối thiểu **240 phút (nửa ngày)**.
    - Bảo tàng / Di tích lớn (Đại Nội, Dinh Độc Lập): Tối thiểu **90 - 120 phút**.
    - Điểm check-in / Cầu / Tượng đài: **30 - 45 phút**.

### 5. Văn bản AI Slop lặp lại như vẹt
- **Hiện tượng**: Toàn bộ các slot đều hiển thị cùng một câu mẫu: *"Gợi ý: ... được xếp vào lịch vì phù hợp với yêu cầu 'Cuối tuần này 2 đứa mình...'*.
- **Nguyên nhân**: Template fallback sinh mô tả ghép trực tiếp câu prompt của người dùng vào chuỗi cố định.
- **Giải pháp**:
  - Viết lại bộ sinh mô tả theo ngữ cảnh tự nhiên: Giải thích ngắn gọn đặc trưng của điểm đến (ví dụ: *"Thưởng thức hải sản tươi sống và ngắm cầu Rồng phun lửa về đêm"*), tuyệt đối không lặp lại prompt thô của user.

---

## II. XỬ LÝ CÁC CA NGOẠI LỆ (EDGE CASES)

### 6. Mâu thuẫn địa lý (Geographical Contradiction)
- **Ngoại lệ**: *"Đi Hà Giang tắm biển ngắm san hô"*.
- **Xử lý**: Kiểm tra tính tương thích giữa điểm đến và tag yêu cầu: Nếu vùng miền núi (Hà Giang, Sa Pa, Đà Lạt) mà yêu cầu tag biển (`beach`, `tam_bien`, `san_ho`) → Tự động bỏ qua tag mâu thuẫn và sinh cảnh báo nhẹ trong phần lưu ý: *"Hà Giang là vùng đồi núi, lịch trình đã tập trung vào ngắm cảnh thiên nhiên và trải nghiệm văn hóa thay cho hoạt động biển"*.

### 7. Khung giờ khởi hành tự do trong câu nói (Custom Time Window)
- **Ngoại lệ**: *"Tôi rảnh từ 22h đêm đến 24h đêm ở TP.HCM muốn đi dạo"*.
- **Xử lý**:
  - Bóc tách giờ bắt đầu thực tế từ text (ví dụ: `22:00`).
  - Dịch chuyển con trỏ thời gian `day_start` sang `22:00` thay vì mặc định luôn bắt đầu lúc `08:00` sáng.
  - Tự động chỉ chọn các địa điểm mở cửa đêm (chợ đêm, phố đi bộ, quán bar/pub, cafe 24/7).

### 8. Lọc Dislike cực đoan (User cấm mọi loại hình cơ bản)
- **Ngoại lệ**: *"Không bảo tàng, không di tích, không cafe, không công viên, không ăn ngoài"*.
- **Xử lý**: Khi số lượng điểm khả thi sau khi lọc < số lượng slot yêu cầu → Hệ thống báo `PipelineUnavailable` kèm thông điệp rõ ràng: *"Yêu cầu loại trừ quá nhiều địa điểm khiến hệ thống không đủ dữ liệu để xếp lịch trình hợp lý. Vui lòng mở rộng sở thích của bạn."* (Tuyệt đối không tự ý ép các điểm bị cấm vào lịch).

---

## III. LỘ TRÌNH THỰC THI (ACTION ITEMS)

- [ ] **Task 1**: Cập nhật `clean_selector.py` biến `dislikes` thành Hard Filter và bổ sung hàm khử trùng lặp theo tọa độ + tên tương đồng (`fuzzy_dedupe`).
- [ ] **Task 2**: Viết module phân cụm địa lý theo ngày `cluster_by_day` trong `planner.py` để chấm dứt tình trạng chạy đi chạy lại giữa 2 thành phố.
- [ ] **Task 3**: Cập nhật bảng `DURATION_OVERWRITE_RULES` cho các điểm du lịch lớn (Bà Nà Hills, VinWonders...).
- [ ] **Task 4**: Sửa bộ parser thời gian nhận diện giờ ban đêm (night shift planning).
- [ ] **Task 5**: Thay toàn bộ template mô tả slot để xóa sạch AI Slop và câu văn lặp lại.

---

## IV. NÂNG CẤP LỚP HIỂU INPUT: HYBRID AI INTENT PARSER

### 9. Thay regex cứng bằng schema hiểu ý định chung
- **Hiện trạng**: Phần hiểu câu người dùng đang phụ thuộc nhiều vào regex/alias cứng ở cả frontend và backend: điểm đến, thời lượng, số người, budget, ngày đi, sở thích và dislikes.
- **Vấn đề**: Regex dễ vỡ khi user nói tự nhiên, đổi thứ tự câu, dùng cách diễn đạt mới hoặc nhập thông tin mơ hồ. Hệ thống có nguy cơ đoán sai hoặc fallback im lặng.
- **Hướng đúng**: Dùng mô hình **Hybrid AI Intent Parser**:
  - AI/LLM làm nhiệm vụ đọc hiểu câu tự nhiên và tách ý vào một schema chuẩn.
  - Backend kiểm chứng lại bằng Pydantic/schema, catalog địa điểm, rule logic và business constraints.
  - Nếu thiếu hoặc mơ hồ thì hỏi lại user, không tự đoán bừa.
  - Regex chỉ còn là fallback/offline và bắt các mẫu đơn giản.

### 10. Schema intent chung cần trích xuất
- **Các trường bắt buộc/cốt lõi**:
  - `destination`: điểm đến/thành phố/khu vực user muốn đi.
  - `date_range` hoặc `start_date`: ngày đi, khoảng ngày, hoặc mốc tương đối như ngày mai, tuần sau.
  - `duration`: vài giờ, nửa ngày, 1 ngày, nhiều ngày, hoặc số giờ/ngày cụ thể.
  - `people`: số người đi.
  - `budget`: ngân sách tổng hoặc mỗi người nếu user nói rõ.
- **Các trường tăng chất lượng lịch trình**:
  - `lodging`: nơi lưu trú / điểm xuất phát nếu có.
  - `preferences`: sở thích, ví dụ cafe, biển, văn hóa, check-in, ăn ngon, đi bộ nhẹ.
  - `dislikes`: điều cần tránh, ví dụ không leo núi, không bảo tàng, không đi bộ nhiều.
  - `must_visit`: địa điểm bắt buộc muốn ghé.
  - `constraints`: trẻ em, người lớn tuổi, ăn chay, trời mưa, ít đi bộ, mở cửa đêm, v.v.
  - `uncertainties`: các điểm AI không chắc và cần hỏi lại.

### 11. Luồng hỏi lại thông minh
- **Nguyên tắc**: Hệ thống đọc toàn bộ câu trước, điền được gì thì điền, chỉ hỏi phần còn thiếu hoặc mơ hồ.
- **Không hỏi máy móc nhiều câu một lúc**. Hỏi từng bước theo mức độ quan trọng:
  1. Thiếu điểm đến → hỏi user muốn đi đâu.
  2. Thiếu thời lượng/ngày đi → hỏi đi bao lâu hoặc khi nào.
  3. Thiếu số người → hỏi đi mấy người.
  4. Thiếu budget → có thể hỏi hoặc dùng mặc định trung bình.
  5. Thiếu sở thích → có thể dùng highlight phổ biến.
- **Nếu mơ hồ thì hỏi xác nhận**:
  - “Cuối tuần” → hỏi cuối tuần này hay cuối tuần sau.
  - “Mộc Châu” nếu chưa chắc trong catalog → hỏi xác nhận đúng Mộc Châu, Sơn La không.
  - “Budget 3tr” → nếu cần, hỏi là tổng chuyến đi hay mỗi người.

### 12. Kiểm tra logic sau khi AI tách ý
- **Không tin AI trực tiếp**. Mọi kết quả AI phải qua kiểm chứng:
  - Điểm đến phải match catalog/alias/fuzzy search, không thì hỏi lại.
  - Ngày đi không được ở quá khứ.
  - Số người và budget phải nằm trong giới hạn schema.
  - Thời lượng và khoảng ngày không được mâu thuẫn.
  - Dislikes phải thành hard filter: user nói không leo núi thì không xếp núi/trekking.
  - Destination phải ràng buộc địa lý: user nói Đà Lạt thì không kéo điểm Hà Nội vào.
  - AI không được tự bịa địa điểm ngoài catalog.

### 13. Kiến trúc triển khai đề xuất
- **Backend là source of truth** cho intent parsing.
- Tạo module canon `intent_parse.py` để gom toàn bộ logic hiểu input:
  - LLM structured extraction.
  - Pydantic validation.
  - Catalog grounding/fuzzy matching.
  - Rule fallback/offline.
  - Missing-field/ask-back decision.
- Frontend không nên tự regex sâu nữa. Frontend chỉ gửi câu user lên backend và hiển thị:
  - những gì hệ thống đã hiểu,
  - câu hỏi tiếp theo nếu thiếu,
  - chip/card lựa chọn nếu backend yêu cầu.

### 14. Action items cho intent parser
- [ ] **Task 6**: Thiết kế schema `IntentParseResult` gồm destination, date, duration, people, budget, preferences, dislikes, must_visit, constraints, uncertainties, confidence.
- [ ] **Task 7**: Tạo `intent_parse.py` làm module canon cho LLM extraction + validation + fallback rule-based.
- [ ] **Task 8**: Thêm endpoint backend `/api/intent/parse` hoặc tích hợp vào `/api/plan/generate` để trả về `ready_to_plan` hoặc `ask_user_missing_fields`.
- [ ] **Task 9**: Chuyển logic hỏi lại từ frontend sang backend: FE chỉ render câu hỏi/chip theo response.
- [ ] **Task 10**: Thêm test cho các câu tự nhiên: đủ thông tin, thiếu điểm đến, thiếu thời lượng, mơ hồ “cuối tuần”, dislike, budget, relative date.

---

## V. FEEDBACK CASES CẦN XỬ LÝ TỪ KIỂM THỬ THỰC TẾ

### 15. Lỗi hiểu sai số ngày / thời lượng chuyến đi
- **Các case lỗi**:
  - User nhập: `du lịch Sài Gòn 30 ngày` nhưng hệ thống vẫn tạo lịch trình 2 ngày.
  - User nhập: `du lịch Hà Nội 3 ngày` nhưng hệ thống vẫn tạo lịch trình 2 ngày.
  - User chọn/nhập `30 ngày` nhưng hệ thống vẫn hỏi lại thời gian.
- **Loại lỗi**: `duration parsing / duration propagation`.
- **Nguyên nhân khả nghi**:
  - Regex frontend/backend không bắt ổn số ngày tự nhiên.
  - `nhieu_ngay` đang default về 2 ngày và lấn át số ngày user nhập.
  - FE hiểu được nhưng không truyền đúng xuống backend, hoặc backend parse lại và ghi đè.
- **Hướng xử lý**:
  - Intent parser phải tách rõ `duration_days = 3`, `duration_days = 30`.
  - Nếu user nói số ngày hợp lệ thì không hỏi lại thời lượng.
  - Backend là source of truth: số ngày cuối cùng phải nằm trong `IntentParseResult` và dùng xuyên suốt `build_plan`.
  - Nếu 30 ngày vượt khả năng xếp chi tiết từng slot, hệ thống không nên im lặng cắt còn 2 ngày; phải báo rõ: tạo lịch chi tiết N ngày đầu, hoặc gợi ý chia itinerary theo chặng.

### 16. Lỗi hiểu khung giờ Việt Nam
- **Các case lỗi**:
  - `du lịch Hà Nội từ 15h-18h` báo không đủ thời gian tạo kế hoạch.
  - `15 giờ đến 18 giờ` hệ thống vẫn hỏi lại thời gian.
  - `15h đến 18h` hệ thống vẫn hỏi lại thời gian.
- **Loại lỗi**: `time window parsing / validation`.
- **Nguyên nhân khả nghi**:
  - Regex chưa bắt đủ các dạng `15h-18h`, `15h đến 18h`, `15 giờ đến 18 giờ`.
  - Validation hiểu sai 15h-18h là không đủ, trong khi 3 tiếng vẫn đủ cho lịch ngắn.
- **Hướng xử lý**:
  - Parse time window thành `start_time = 15:00`, `end_time = 18:00`, `duration_minutes = 180`.
  - Với khung 3 tiếng, hệ thống phải tự chuyển sang plan ngắn (`vai_gio`) thay vì báo fail.
  - Nếu khung giờ quá ngắn thật sự, ví dụ dưới 45 phút, mới hỏi lại hoặc báo không đủ.
  - Thêm test cho các dạng: `15h-18h`, `15h đến 18h`, `15 giờ đến 18 giờ`, `từ 15 giờ tới 18 giờ`.

### 17. Input chỉ có intent nhưng thiếu destination
- **Các case lỗi**:
  - `Tôi muốn đi chữa lành` không ra lịch trình.
  - `Tôi muốn đi biển` không ra lịch trình.
  - `Muốn đi leo núi` hệ thống cố tạo lịch nhưng kết quả không đúng trọng tâm.
- **Loại lỗi**: `intent-only request without destination`.
- **Nguyên nhân**:
  - User mới nói loại trải nghiệm, chưa nói điểm đến.
  - Hệ thống hiện chưa có flow gợi ý destination trước khi lập lịch.
- **Hướng xử lý đúng**:
  - Không cố tạo plan nếu thiếu destination bắt buộc.
  - Chuyển sang flow kiểu Layla.ai: gợi ý vài điểm đến phù hợp với intent để user chọn.
  - Sau khi user chọn destination, mới tạo lịch trình.
- **Ví dụ flow đúng**:
  - User: `Tôi muốn đi chữa lành`.
  - Hệ thống: `Bạn muốn đi chữa lành ở đâu? Một vài gợi ý phù hợp: Đà Lạt, Sa Pa, Ninh Bình, Phú Quốc, Huế.`
  - User chọn `Đà Lạt`.
  - Hệ thống mới lập lịch Đà Lạt theo intent chữa lành.

### 18. Mapping intent chưa đủ mạnh: chữa lành / biển / leo núi
- **Các case lỗi**:
  - `Tôi muốn đi chữa lành` không ra lịch trình.
  - `Tôi muốn đi biển` không ra lịch trình.
  - `Muốn đi leo núi` có núi nhưng xen kẽ công viên, bảo tàng, landmark không liên quan.
- **Loại lỗi**: `semantic intent mapping`.
- **Hướng mapping cần có**:
  - `chữa lành`: thiên nhiên yên tĩnh, hồ, rừng, thiền, cafe chill, đi bộ nhẹ, ít đông, view đẹp, nghỉ dưỡng.
  - `biển`: bãi biển, đảo, hoàng hôn, hải sản, resort, cảng/tour biển, hoạt động ven biển.
  - `leo núi`: núi, trekking, trail, viewpoint, đỉnh, đèo, hoạt động ngoài trời.
- **Hướng xử lý**:
  - Tạo intent profile rõ ràng cho từng nhóm.
  - Nếu intent mạnh, candidate pool phải ưu tiên hoặc lọc theo nhóm đó.
  - Không dùng landmark nổi tiếng để lấp slot nếu không liên quan intent.
  - Nếu không đủ địa điểm phù hợp ở destination đã chọn, hỏi lại hoặc gợi ý destination khác.

### 19. Lỗi selection/ranking trộn địa điểm không đúng chủ đề
- **Case lỗi**:
  - User muốn `leo núi` nhưng lịch có núi xen kẽ công viên, bảo tàng.
- **Loại lỗi**: `selection policy / thematic purity`.
- **Nguyên nhân**:
  - Intent hiện chỉ cộng điểm mềm, còn địa điểm nổi tiếng/gần/curated vẫn có thể chen vào.
  - Hệ thống đang cố lấp đủ slot thay vì giữ đúng chủ đề.
- **Hướng xử lý**:
  - Khi intent mạnh (`leo_nui`, `bien`, `chua_lanh`) thì tạo mode `thematic_trip`.
  - Trong `thematic_trip`, candidate pool phải đạt ngưỡng phù hợp intent trước khi được chọn.
  - Nếu thiếu slot, chèn điểm phụ trợ cùng chủ đề (cafe nghỉ chân gần trail, viewpoint, điểm ăn phù hợp) thay vì bảo tàng/landmark ngẫu nhiên.
  - Nếu vẫn thiếu dữ liệu thì hỏi lại user: mở rộng chủ đề hay đổi điểm đến.

### 20. Bias hardcoded landmark: Hà Nội auto ra Lăng Bác
- **Case lỗi**:
  - Ở Hà Nội thì hệ thống gần như tự động đưa Lăng Bác vào lịch.
- **Loại lỗi**: `default landmark bias / over-prioritized highlight`.
- **Nguyên nhân**:
  - Hà Nội highlight/curated landmark đang được ưu tiên quá mạnh.
  - Ranking chưa kiểm tra intent trước khi nhét landmark nổi tiếng.
- **Hướng xử lý**:
  - Lăng Bác chỉ nên xuất hiện khi intent liên quan: lịch sử, văn hóa, landmark lần đầu, chính trị, bảo tàng/di tích.
  - Với intent `chữa lành`, `cafe chill`, `đi bộ nhẹ`, `hẹn hò`, không tự động nhét Lăng Bác.
  - Thêm rule giảm bias landmark nếu không khớp intent.

### 21. Action items bổ sung cho feedback thực tế
- [ ] **Task 11**: Sửa duration parser để `3 ngày`, `30 ngày`, `một tuần`, `2 ngày 1 đêm` không bị rơi về default 2 ngày.
- [ ] **Task 12**: Sửa time-window parser/validation cho `15h-18h`, `15h đến 18h`, `15 giờ đến 18 giờ`; khung 3 tiếng phải tạo được plan ngắn.
- [ ] **Task 13**: Thêm `destination suggestion flow` cho input chỉ có intent: chữa lành, biển, leo núi, ăn ngon, cafe, trekking.
- [ ] **Task 14**: Thêm intent profiles mạnh cho `chua_lanh`, `bien`, `leo_nui` và mapping tag/place-kind tương ứng.
- [ ] **Task 15**: Thêm mode `thematic_trip` để giữ lịch đúng chủ đề, không lấp slot bằng bảo tàng/landmark không liên quan.
- [ ] **Task 16**: Giảm hardcoded Hà Nội/Lăng Bác bias; chỉ đưa Lăng Bác vào khi intent phù hợp.
- [ ] **Task 17**: Thêm acceptance tests cho toàn bộ feedback cases: Sài Gòn 30 ngày, Hà Nội 3 ngày, chữa lành, biển, leo núi, Hà Nội 15h-18h.
