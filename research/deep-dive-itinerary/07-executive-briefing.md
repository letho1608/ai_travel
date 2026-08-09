# 07 — Executive Briefing (Tiếng Việt)

Dự án: **Mình Đi Đâu Thế** · Deep-dive: tính năng sinh lịch trình & trải nghiệm
Ngày: 2026-08-07 · Phương pháp: 4 chuyên viên song song → tổng hợp → phản biện (red-team), tất cả kết luận then chốt đều được **chạy thật code** để kiểm chứng.

---

## Kết luận ngay từ đầu

**6/6 vấn đề bạn nêu đều có thật — 4 cái là lỗi code đã được chứng minh bằng cách chạy chương trình, không phải cảm giác.** Ứng dụng được kiến trúc như một hệ thống production (bảo mật, rate limit, circuit breaker, phiên bản, SSE, xuất PDF/ICS) nhưng **hành xử như một bản demo**: mặc định chạy `AI_MODE=mock` (không có AI thật), kho dữ liệu chỉ có **66 địa điểm dùng được** với 100% đều *mở 7h–22h, giá 0đ, thời gian 60 phút*, và một lỗi lọc tiếng Việt khiến hầu hết ý định người dùng bị phá huỷ ngay từ cổng vào.

Tin tốt: hầu hết lỗi là **cơ học** (mã hoá ký tự, một lỗi bỏ mất chữ "đ", một chỗ cấu hình) — sửa trong **3–5 ngày** là sản phẩm đổi tính nết. Hiện tại không nên coi đây là "AI travel app" đang chạy; hãy coi là *khung xương production + phần lõi đang hỏng*.

---

## Trả lời 6 vấn đề (đã kiểm chứng bằng code)

| # | Vấn đề | Phán quyết | Nguyên nhân gốc (file:line) |
|---|---|---|---|
| 1 | Sinh lịch trình củ chuối, chợ đêm vào buổi sáng, hardcode Hồ Gươm/Hồ Tây/Lăng Bác | **ĐÚNG — cả 3 ý** | (a) Hàm `_ascii_fold` dùng NFKD+ascii-ignore nên chữ **"đ" bị xoá hoàn toàn**: `"chợ đêm"` → `"cho em"`, không bao giờ khớp ý định "đêm" (`planner.py:131-137`). (b) Đã chạy thử: gõ "đi chơi buổi tối" → kết quả là **7 quán cà phê 08:00–14:08**, không có chợ đêm — vì danh mục **không có bất kỳ địa điểm tối nào** (100% open 7h) và vòng xoay seed đẩy điểm phù hợp nhất ra ngoài cửa sổ chọn (`planner.py:272-280`). (c) Hồ Gươm/Lăng Bác/Hồ Tây/Phố cổ bị ép vào mọi kế hoạch có từ "Hà Nội" (`planner.py:191-211`), và bản thân prompt AI cũng ra lệnh phải thêm chúng (`ai.py:209-215`). |
| 2 | Đầu vào chưa phải chatbot | **ĐÚNG — còn tệ hơn bạn nói** | Đầu vào là form (textarea + số người + nút), không phải chat. Nghiêm trọng hơn: `inferDuration` (đoán thời lượng từ câu chữ) **từ chối chính 2/3 chip gợi ý mặc định của app**: chip "Cà phê và đi bộ cuối tuần" và "Ăn ngon, ít di chuyển" không chứa từ khoá thời lượng → **bị chặn không cho gửi** (`Planner.tsx:66-73`). |
| 3 | Giao diện chưa đẹp | **Một phần (chủ quan)** | CSS đồng bộ, đúng tông (màu giấy lúa) nhưng **phẳng**: không ảnh, không hero, không dark mode, nút chữ, header 8 nút không gói trên mobile (`globals.css:18`). "Không đẹp" chủ yếu do thiếu ảnh (vấn đề 4) + thẻ phẳng. |
| 4 | Chưa có ảnh minh hoạ từng điểm | **ĐÚNG** | Không có trường ảnh ở `Place` (`data.py:10-24`), `places.json`, hay `Slot` (`planner.py:543-556`); **toàn repo không có thẻ `<img>` nào**; không có `og:image` nên link chia sẻ không có ảnh xem trước (`page.tsx:6`). |
| 5 | Chưa có replan (back + front) | **Một phần — có "cái đinh" nhưng không ghép thành "cái bàn"** | Thực tế **có đủ**: swipe (đổi điểm), "Làm lại" (regenerate), tinh chỉnh bằng chat (refine), lịch sử phiên bản (versions), khôi phục (restore) — đều chạy và trả 200 (`plans.py:310-535`; `PlanView.tsx:79-87`). NHƯNG: "Làm lại" chuyển sang token mới → **mất hết lịch sử phiên bản**; refine **dựng lại từ đầu**, nuốt mọi thay đổi tay trước đó; và regex tiếng Việt bị **mã hoá sai (mojibake)** nên câu "**đổi** điểm này", "**3 người**", "ngân sách 500k" **không khớp nổi** (đã chạy test: không match) → gửi "đổi" mà hệ thống im lặng dựng lại nguyên lịch. |
| 6 | Nút chia sẻ không hoạt động | **ĐÚNG — với cơ chế rõ ràng** | Nút "Chia sẻ" chỉ **sao chép URL hiện tại** = `http://localhost:3000/plan/<token>` (`PlanView.tsx:77`). Người nhận mở ra là **chính máy của họ**, kết nối bị từ chối → 100% người nhận không xem được. API bị bôi cứng `http://localhost:8000` (`api.ts:3`), CORS chỉ cho localhost (`config.py:10-14`), không có Web Share API, không có og:image. Lỗi sâu hơn: trang `/plan/[token]` gọi API **ngay trên server** (`page.tsx:5`) bằng địa chỉ localhost → sang máy khác là gãy cả lúc render. |

---

## 6 cụm nguyên nhân gốc

1. **Xử lý tiếng Việt hỏng ở mọi tầng.** Chữ "đ" bị xoá (`planner.py`, `osm_verify.py`, `plans.py`); hàng chục chuỗi/regex backend bị **mojibake kép** (16× `khÃ´ng`, regex `đổi`/`3 người`/`ngân sách`); frontend `en` còn lẫn `â€¦`; có chuỗi tiếng Việt lọt vào mọi ngôn ngữ khác. Một lỗi này nằm dưới cả vấn đề 1, 2 và 5.
2. **"Chiếc lồng" quyết định nuốt mất ý định người dùng.** Xoay seed làm điểm tốt nhất rớt khỏi cửa sổ chọn; anchor Hồ Gươm/Lăng Bác chèn đè; khớp tên mờ ("Phố cổ Hà Nội" → "**Phở hà nội**"); ngân sách vô nghĩa (giá đều 0).
3. **Mô hình dữ liệu không diễn tả được thực tế.** 3.508 file → 3.524 trong bộ nhớ → nhưng **chỉ 66 dùng được lúc chạy** (50 OSM trong ma trận khoảng cách: 36 cà phê + 14 bảo tàng; + 16 anchor curated). Không địa điểm tối, không giá, không giờ thật.
4. **Mô hình triển khai trói mọi thứ vào localhost.** API/CORS/localhost, `AI_MODE=mock` mặc định, không base URL công khai → chia sẻ và triển khai thật đều chết.
5. **Replan tồn tại nhưng không kết hợp được.** Mất chuỗi phiên bản khi "Làm lại", refine nuốt thay đổi, swap đổi gần nhất không tính lại giờ, không có giữ/bỏ điểm, không có diff.
6. **LLM bị dùng quá ít và mock là mặc định.** `MockAIAdapter` chỉ trả `candidates[:count]` (`ai.py:74-95`) — **không có AI nào cả** ở cấu hình mặc định. `.env.example` ghi `AI_MODE=groq` nhưng **key rỗng** → thực tế ra mắt vẫn là mock.

**Nhận định kiến trúc:** công sức đổ vào *hạ tầng & an toàn*; rủi ro nằm đúng chỗ *giá trị người dùng nhìn thấy* (ý định, danh mục, lịch, triển khai). Kinh điển "vỏ bọc phòng thủ quanh lõi rỗng".

---

## Có gì thật sự tốt (đánh giá thẳng thắn)

- Chuỗi xử lý chặt chẽ đáng tin: ma trận OSRM, tối ưu tuyến two-opt, circuit breaker AI, rate limit fail-closed, **tối ưu lạc quan (optimistic concurrency) theo phiên bản**, SSE tiến trình, validator chặn địa điểm ngoài danh sách tin cậy, xuất PDF/ICS, bình luận nhóm, 19 ngôn ngữ (dù chất lượng dịch chưa đồng đều).
- Kiến trúc backend tách lớp sạch, có test (dù test hiện "xanh giả" — xem dưới).
- Mô hình bảo mật link chia sẻ UUID chỉ-đọc là đúng hướng về mặt thiết kế.

---

## Xác suất thật (thẳng thắn)

**Xác suất app hiện tại đáp ứng kỳ vọng của bạn: 15/100.**
Vì: 6/6 vấn đề có căn cứ, 4 cái là lỗi thấy ngay ở lần chạy đầu; mặc định là mock với 66 điểm, giá 0, toàn giờ ban ngày; share gãy 100% ngoài máy tạo. NHƯNG: app thật sự chạy được (bản đồ, đổi điểm, phiên bản, bình luận, PDF) và hầu hết lỗi là cơ học → sau **đợt Tier 0+1 (~3–5 ngày) tôi ước tính 65–75%**.

**Số liệu nền tảng (ground truth): 31 kết luận được kiểm chứng bằng code thật / đọc nguồn; 4–7 mục còn lại là phán đoán mô hình** (như "tệ hơn LLM tự sinh" là lập luận cấu trúc; tần suất user bị chặn là ước lượng). Điểm này **không làm tròn lên**.

---

## Kế hoạch sửa theo ưu tiên

**Tier 0 — Blocker (≈1 ngày):**
1. Sửa `_ascii_fold`: giữ chữ "đ" (thay NFKD+ascii bằng bảng chuyển đổi hoặc so sánh không dấu giữ nguyên "đ") ở `planner.py:131-137`, `osm_verify.py:63-69`, `plans.py:429`. (1–2h) → **gỡ khoá chợ đêm, buổi tối, phố cổ, "đổi"**.
2. Chuyển lại chuỗi backend về UTF-8 sạch + sửa regex ý định (`plans.py`, `schemas.py`); sửa `en` mojibake + chuỗi `dataNotice` tiếng Việt. (0.5–1h)
3. Gỡ/giới hạn vòng xoay seed (`planner.py:272-280`) để điểm ý định cao nhất luôn nằm trong cửa sổ chọn. (0.5–1h)
4. Nới `inferDuration` (`Planner.tsx:66-73`): mặc định không nhận diện được → `ca_ngay`, bản địa hoá câu chặn, thêm "cuối tuần". (1–2h) → hết cảnh app chặn chip của chính mình.

**Tier 1 — Sprint này (≈2–3 ngày):**
5. Triển khai công khai + khe cấu hình: `NEXT_PUBLIC_BASE_URL`/API, CORS cho domain thật, dựng URL chia sẻ từ token thay vì `location.href` (`PlanView.tsx:77`, `api.ts:3`, `config.py:10-14`) **và render client-side hoặc proxy `/api` cho trang `/plan/[token]`** (`page.tsx:5`). → **sửa chia sẻ 100%**.
6. Danh mục thật: đừng vứt `opening_hours_raw`, nhập giờ/giá/thẻ buổi tối thật. (4–8h data)
7. Ảnh MVP: thêm `image_url` vào Place/Slot + render + `og:image`. (4–8h) → **"wow" rẻ nhất cho vấn đề 3&4**.
8. "Làm lại" tại chỗ (giữ token, `store.update`) + link về lịch cũ. (3–4h)
9. Refine: **ngưỡng tin cậy** — không nói "đã áp dụng" khi không parse được ý định; giữ các thay đổi tay. (2–3h)

**Tier 2:** giữ/bỏ điểm + UI diff "đã đổi gì"; mặc định AI thật khi deploy (groq/deepseek) kèm gate kiểm tra hợp lệ; Web Share API; mobile ưu tiên lịch trình; nút budget; TZID `Asia/Ho_Chi_Minh`.

**Tier 3 (polish):** dark mode, bộ icon, PWA, a11y, chính sách hết hạn link chia sẻ.

**Nếu chỉ làm MỘT việc:** sửa tầng tiếng Việt (giữ "đ" + làm sạch mã hoá). Một lỗi cơ học này nằm dưới vấn đề 1, 2 và 5.

---

## Cảnh báo red-team (đừng bỏ qua)

- **"AI" thực ra đang tắt.** Cấu hình mặc định chạy mock; `.env.example` để key rỗng. Trước khi bật AI thật, phải có **cổng chất lượng** (AI chỉ bật khi lịch qua validator, không thì 503).
- **Chi phí AI không phải vấn đề:** ~$0.0014/lịch → ~7.100 lịch/ngày với trần $10. NHƯNG `MemoryStore` không reset "trần ngày" → thành **trần cả đời tiến trình**; chỉ `PostgresStore` reset theo ngày. Đang chạy MemoryStore mặc định.
- **Bình luận có thể spam bằng cách xoay `ma_phien`** (key rate-limit do client tự đặt, `plans.py:266`); admin token mặc định `local-support-demo` ở local.
- Khi sửa xong, **hãy viết lại tiêu chí chấp nhận thành câu lệnh chạy được** (chạy 3 chip mặc định + 3 yêu cầu tay trong mock, assert số điểm + ý định khớp + giờ tuần tự). Tiêu chí hiện tại không kiểm chứng được.

---

## Nên tiếp tục không?

**Có — nhưng hãy coi đây là bản MVP đang sửa lõi, không phải sản phẩm đã xong.** Ưu tiên tối thượng: Tier 0 + mục 5 + mục 7 trong cùng một sprint (~4–5 ngày), rồi **deploy lên HTTPS công khai và bật AI thật** — đó là lúc app ngừng "hành xử như demo". Đừng đẹp UI trước khi lõi chạy đúng và chia sẻ được ra ngoài.
