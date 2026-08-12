# Executive Briefing — Thuật toán tốt nhất cho "input → lịch trình"

*Deep-dive nghiên cứu, 6 lane chuyên gia + synthesis + red-team. Research-only, không sửa code.*

---

## Bottom line up front

**Thuật toán lịch trình hiện tại của bạn không phải là vấn đề. Vấn đề là dữ liệu, bản dịch ý định (Vietnamese NL→constraint), và copy — và việc nâng cấp nên là *làm dày hệ thống lai hiện tại*, không phải viết lại từ đầu.**

Đáp án thẳng cho câu hỏi "thuật toán xịn hiện đại nhất là gì":

> **Hybrid: LLM dịch ý định → truy vấn POI có căn cứ (grounded retrieval) → bộ solver/verifier tất định giữ tính khả thi → LLM viết văn. Không có hãng nào đang ship "thuần LLM làm lịch" cả.**

Hệ thống của bạn **đã là một hybrid yếu** (LLM chọn tên + viết copy, core tất định lo phần ràng buộc). Điều các bằng chứng chỉ ra: bạn không cần đổi kiến trúc, bạn cần dày đặc hóa và sửa dữ liệu.

---

## Honest confidence: 6/10

Do red-team hạ từ mức 7–8 của synthesis xuống. Lý do:

- **Phần an toàn (8/10):** "thuần LLM hỏng, hybrid thắng, data là kẻ giết" — đã được chứng minh bằng 4+ họ benchmark độc lập và 2 post engineering first-party (Google, Tripadvisor). Chắc.
- **Phần có giá trị (4/10):** lợi ích thực tế cho SẢN PHẨM CỦA BẠN là chưa đo. Ba chân chống của phần giá trị đều chưa kiểm chứng cho đúng sản phẩm này: (1) người Việt có thấy "map" không? (2) LLM dịch tiếng Việt→ràng buộc ổn không? (3) catalogue POI Hà Nội của bạn hỏng dữ liệu bao nhiêu?

**Ground-truth tally: 8 của 15 kết luận mang tải được xác minh ngoài (≥2 nguồn/lane); 7 còn lại single-source hoặc model judgment — và 3 cái nặng nhất (perception, bản dịch tiếng Việt, base-rate dữ liệu catalogue) là chưa đo cho sản phẩm này.**

---

## Điều xác minh: điều gì THẬT SỰ chạy tốt ngoài kia

| Phát hiện | Độ mạnh bằng chứng |
|---|---|
| Pure-LLM scheduling thất bại: TravelPlanner 0.6% (GPT-4); o1 ≈10%; human-style tiếng Trung ~0–2.6% | 4 họ benchmark độc lập |
| Solver-backed đạt 84–94% chung hệ (con số ghép 2 metric) | Nhiều lane, ≥2 nguồn |
| LLM dịch NL→structured, solver+verifier ngoài giữ tính khả thi (SMT pipeline 1 cặp: 93.9% hay 97% — hướng chắc dù sai số) | ≥2 nguồn |
| Tripadvisor bỏ LLM khỏi khâu tạo gợi ý: latency 40→6.5s, chất lượng cảm nhận +30% | First-party post (single) |
| Google: "LLM đề xuất, optimizer chỉnh" — LLM chỉ giữ vai trò đề + chấm điểm tương đồng | research.google (first-party) |
| RL chỉ thắng ở tầng reward/routing (Google Maps) — không dùng cho scheduling | Ngang tầm học thuật |
| "Tối ưu toán học" ≠ "người thấy tối ưu" — reward model là bẫy | Ngang tầm OR + UX |
| 2 OR/CP benchmark: greedy là tầng yếu nhất được ghi nhận; metaheuristic/LNS chắc hơn | OR literature |

---

## Điều KHÔNG sống sót qua kiểm chứng (bị hạ/giảm giá)

- **"84–94%"** — là cộng dồn 2 metric khác nhau (feasibility + preference), không phải 1 con số sạch.
- **$2.4/query GPT-4o** — single-source, mức giá thời GPT-4o; nay DeepSeek V4 Flash ~$0.10/$0.20M. Không nên dùng làm mức quyết định.
- **HiMAP "+17.7pp over ATLAS"** — sai số học (52.8−44.4 = 8.4). Loại.
- **Hai lane báo cùng SMT pipeline là "93.9%" vs "97%"** — có thể là 2 paper khác nhau; hướng chắc nhưng con số cụ thể chưa định viền.
- **"CP-SAT chạy giây" vs "chạy hàng giờ"** — lane 06 phóng đại; lane 02 nói seconds–203s trung bình. Vẫn là chưa đo trên n thật của bạn.

---

## Phát hiện chính của red-team (điều khiến confidence không lên 7-8)

1. **Cả 3 chân giá trị đều chưa đo cho sản phẩm này:** cảm nhận người dùng VN, chất lượng dịch tiếng Việt→ràng buộc, base-rate dữ liệu catalogue. Không lane nào đo 3 cái này.
2. **Cổng A/B CP-SAT có thể "pass giả" hoặc "fail giả":** nó đo trên thế giới ma trận/giờ mở cửa giả định (haversine + giờ tưởng tượng), nên không phát hiện được điều thật sự thay đổi quyết định.
3. **Các tiêu chí chấp nhận lỏng:** fix bữa trưa vẫn có thể pass với lunch 14:30; post-pass có thể pass trong khi vi phạm giờ mở cửa/precedence từng bước.
4. **Wrong-question drift:** lane 06 tự thừa nhận "algorithm không phải là khuyết điểm"; synthesis vẫn dẫn đầu bằng framing thuật toán — vì người hỏi hỏi vậy.
5. **BXH "mapping"** có thể không đến từ thuật toán: mô tả, độ tươi POI, thời lượng, bữa trưa muộn, lỗi giờ đóng cửa — là thứ người dùng cảm nhận, không phải "thiếu AI".

**Cách thất bại khả dĩ nhất của khuyến nghị:** mọi phase được dán nhãn "xong" trong ~2 tuần, nhưng cảm giác "mapping" và regenerate-rate không nhúc nhích — vì đo sai thứ cần đo và sửa thứ không phải là gốc.

---

## Điều này nghĩa là gì cho quyết định của bạn

**Đừng thay core.** Hãy: (0) đo base-rate dữ liệu catalogue của bạn trước, (1) sửa lỗi bữa ăn + giờ cửa mà validation đã có công cụ, (2) nâng chất lượng copy/mô tả (đây là "mapping feel" thật), (3) mới tính tới solver/LLM-dịch — mỗi bước có một "cổng đo" rõ ràng. Đó là lộ trình thấp-risk, giá trị-cao từ bằng chứng.

---

## Cây quyết định

- **Xây (hiện tại):** làm dày hybrid hiện có — fix ràng buộc meal/window, thêm post-pass local-search tôn giờ mở cửa, huấn luyện eval harness đo "người thấy tốt hơn không".
- **Xây nếu A/B tại n thật của bạn = count + correct:**
  1. Bổ sung LLM-dịch NL tiếng Việt → cấu trúc ràng buộc (test bản dịch tiếng Việt thực sự trước).
  2. CP-SAT vào, chỉ nếu post-pass không đủ giảm idle/travel.
- **Đừng xây:** pure-LLM planner, multi-agent framework (2× token, không gain), vector-DB-first retrieval (solo thừa), ML/NCO cho scheduling (chưa an toàn correctness).

---

## Ưu tiên hành động

| Tier | Hành động | Lý do |
|---|---|---|
| **T0** | Đo base-rate dữ liệu: bao nhiêu % POI catalogue có giờ mở cửa đúng/thiếu/sai; churn nhà hàng | Toàn bộ kiến trúc đứng trên file dữ liệu; chưa ai đo |
| **T0** | Sửa lỗi bữa sáng/trưa/precedence theo đúng ràng buộc đã khai báo (MEAL_WINDOWS 11:00–13:30...) | Rẻ nhất, có test sẵn, đập vào thứ người dùng cảm nhận |
| **T1** | Eval: ghi regenerate-rate, đánh dấu plan có lỗi giờ/bữa, LLM-as-judge calibration đo >80% đồng thuận với người | Đo trước khi sửa — nếu không bạn không biết thắng |
| **T1** | Post-pass local-search tôn giờ mở cửa/preference để giảm idle (giữ deterministic, seed ổn định) | Bắt giữ phần lớn gain của "solver" với độ phức tạp thấp |
| **T2** | LLM-dịch tiếng Việt → ràng buộc (structured output), grounded retrieval POI thật, LLM narrator | Hybrid "xịn", nhưng test tiếng Việt trước khi cam kết |
| **T2** | CP-SAT gated: A/B so post-pass trên dữ liệu thật của bạn, n≤9/ngày | Chỉ vào nếu đo ra thật thắng |
| **Không** | Rewrite core / pure-LLM / multi-agent / NCO | Bằng chứng nói loại |

---

## Điều gì sẽ đổi quyết định này

- **Lên (7-8/10):** bạn đo được base-rate dữ liệu catalogue + A/B post-pass vs hiện tại trên plan thật của người dùng VN, và LLM-dịch tiếng Việt→ràng buộc test ra >80% chuẩn.
- **Xuống (4/10):** catalogue POI của bạn phần lớn giờ đúng và lịch đã hợp lý → nên dồn ngân sách vào copy/UX/spread không phải logic.
- **Đổi hướng:** nếu regenerate/quit-rate cho thấy người dùng bỏ vì thiếu nội dung đa dạng hay hình ảnh — điều đó không phải thuật toán nào giải được, nói tôi biết và ta quay lại.