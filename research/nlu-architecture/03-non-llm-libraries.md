# 03 — Thư viện và phương pháp NON-LLM cho NLU trip planner

**Làn 3/4** — Người khảo sát: chuyên gia thư viện/phương pháp non-LLM.
**Phạm vi:** tồn tại công cụ chuyên dụng nào cho bài toán parse tiếng Việt tự do của dự án này không, có khớp stack không. Không làm phần làn 1 (regex), làn 2 (LLM), làn 4 (UX).
**Phương pháp:** không có web search. Mọi nhận định về ecosystem, version, benchmark, quality của thư viện đều dựa trên kiến thức model và được gắn nhãn `[unverified — no web access]`. Phần đọc được từ repo (`backend/requirements.txt`, `backend/pyproject.toml`, `frontend/package.json`, `frontend/components/Planner.tsx`) là dữ liệu đã kiểm chứng.

**Stack thật đã xác nhận:**
- Backend: Python 3.10 (dev) / 3.11 (CI, theo đề bài), `pyproject.toml` đặt `target-version = "py310"`. Dependencies: fastapi, uvicorn, pydantic v2, httpx, psycopg3, redis, google-auth, PyJWT, reportlab, pypdf, ortools, pytest, ruff. Không có NLP lib nào.
- Frontend: Next.js ^14.2, React ^18.3, TypeScript ^5.5, leaflet. **Không có chrono-node hay lib parse nào.** Test bằng `node --test`.
- Hiện trạng parse: 8 hàm `infer*` nằm ở frontend `Planner.tsx` (chi tiết ở mục 7).

---

## 1. Nhóm date/time parser

### 1.1 `dateparser` (Python)

Là thư viện "natural language date" phổ biến nhất của Python: nhận chuỗi, trả về `datetime` đơn. Hỗ trợ đa ngôn ngữ, trong đó có tiếng Việt trong bộ dữ liệu ngôn ngữ của nó `[unverified — no web access]` — mức tin: khá cao nhưng phải kiểm chứng bằng spike vì chất lượng locale vi không đồng đều giữa các version.

**Cơ chế phù hợp:**
- Relative date ("tuần sau", "tháng sau", "ngày mai") được tính dựa trên `RELATIVE_BASE` — đúng thứ cần cho "thứ bảy tuần sau".
- Setting đáng chú ý cho tiếng Việt: `DATE_ORDER = 'DMY'` (nếu không đặt, "2/9" có thể bị hiểu thành 9/2 theo trật tự mặc định cho một số locale `[unverified]`).
- Có thể giới hạn `languages=['vi', 'en']` để giảm chi phí load bộ ngôn ngữ.

**Ví dụ theo hiểu biết của tôi (tất cả [unverified — no web access]):**

| Input | dateparser làm được? | Ghi chú |
|---|---|---|
| `"thứ bảy tuần sau"` | Có thể được | Cần locale vi hiểu thứ trong tuần + relative; phải spike |
| `"20/8"` | Được | Trả về 1 datetime; cần đặt DMY |
| `"20/8 đến 22/8"` | **Không** — chỉ parse 1 mốc | Phải tự split theo "đến/tới/-" rồi parse từng đầu |
| `"dịp lễ 30/4"` | Một phần | Parse "30/4" sau khi tự strip "dịp lễ"; từ "dịp" không có trong ngữ pháp |
| `"3 ngày"` | Không đáng tin | Đây là duration, không phải mốc; dateparser không phải duration parser |
| `"9h sáng"` | Có thể | Không phải điểm mạnh |

**Điểm yếu kiến trúc:** trả về mốc đơn, không trả range, không hiểu khoảng, không hiểu "dịp lễ" như khái niệm. Tức là ngay cả khi dùng dateparser, lớp orchestration (tách range, strip từ nối, ánh xạ lễ) vẫn phải viết tay — dateparser chỉ thay được phần **tính ngày tương đối** (weekday + week offset), vốn là phần khó chịu nhất của regex.

**Trọng lượng:** pure Python, kéo theo python-dateutil, regex, tzlocal `[unverified]` — vài dependency con, không cần compiler, chạy được cả 3.10 lẫn 3.11 `[unverified]`. Load lần đầu chậm hơn vài chục-trăm ms nếu không giới hạn ngôn ngữ `[unverified]`.

### 1.2 Duckling (Facebook)

Là hệ thống parse có cấu trúc mạnh nhất về mặt **hình thái output**: trả JSON với các dimension `time` (có cả **range** start/end), `duration`, `number`, `amount-of-money`. Đây là thư viện non-LLM duy nhất trong danh sách này hiểu "từ 9h đến 5h chiều" như một khoảng có cấu trúc, "3 ngày" như duration, và có khả năng (trong locale tương ứng) hiểu cả số viết bằng chữ `[unverified — no web access]`.

**Tiếng Việt:** Duckling có danh sách locale tương đối rộng; tôi tin rằng `vi` tồn tại trong bộ locale của Duckling `[unverified — no web access]`, nhưng chất lượng grammar vi cụ thể (đặc biệt tiền/số bằng chữ) thì không dám khẳng định.

**Trạng thái bảo trì (theo hiểu biết của tôi, [unverified]):** repo Duckling ở chế độ bảo trì thấp — Facebook gần như không còn chủ động phát triển; PR bên ngoài chậm được merge, release thưa; cộng đồng dùng chủ yếu qua Docker image đã đóng gói sẵn. Đây là rủi ro thật cho một dependency sống.

**Chi phí vận hành — lý do chính để loại ở MVP:**
- Viết bằng Haskell. Dùng qua 2 đường: (a) chạy service riêng (binary/Docker sidecar) và gọi HTTP mỗi lượt parse — thêm một service phải deploy, health-check, scale; (b) binding Python (kiểu `python-duckling`) thì phải compile/link Haskell runtime — đau trên CI lẫn máy dev Windows.
- Dự án hiện tại chưa thấy dấu hiệu chạy multi-service (không có docker-compose trong phần đã liệt kê; cần làn khác xác nhận). Thêm sidecar Haskell cho bài toán 6 slot là chi phí vận hành không tương xứng.

**Kết luận:** đúng năng lực nhất, sai chi phí vận hành. Only revisit nếu dự án đã có Docker infra và bài toán phình ra nhiều dimension cùng lúc.

### 1.3 `chrono-node` (JS/TS)

Chrono parse natural date cho JS. Điểm chốt: bộ parser chính thức là en/de/fr/nl/ja (và tương tự) — **không có tiếng Việt** `[unverified — no web access, tin cao]`. Tức là "thứ bảy tuần sau" chrono-node chịu; "20/8" theo kiểu D/M cũng không phải điều chrono-en ưu tiên.

Chrono cho phép viết custom parser, nhưng nếu phải viết tay toàn bộ grammar tiếng Việt trong chrono thì… chính là viết regex có bọc framework, không thu được gì.

Trong `package.json` hiện không có chrono-node. Thêm nó chỉ có lợi cho input **tiếng Anh** (locale `en` có tồn tại trong UI). Nếu giữ UI song ngữ và muốn parse phía client cho input en, chrono-node là lựa chọn hợp lý (nhỏ, MIT, chạy được trong browser `[unverified]`). Nếu không — bỏ.

### 1.4 Lib tiếng Việt riêng cho date/time

Theo hiểu biết của tôi: **không tồn tại thư viện datetime tiếng Việt chuyên dụng nào đáng tin, được维护, có traction** `[unverified — no web access]`. Có thể tồn tại các repo nhỏ lẻ trên GitHub nhưng không đủ tín nhiệm để đưa vào production. Không nêu tên cụ thể để tránh bịa. Kết luận thực dụng: cho date/time tiếng Việt chỉ có 2 đường — `dateparser` (locale vi, unverified chất lượng) hoặc tự viết offset logic (~20–40 dòng).

### 1.5 Ghi chú thêm: bảng ngày lễ

"dịp 2/9", "lễ 30/4", "giỗ tổ" là bài toán **ánh xạ tên → ngày**, không phải parse. Cách làm đúng là bảng map nhỏ (~10 dòng) tên lễ → (ngày, tháng). Thư viện `holidays` của Python có bao gồm Việt Nam `[unverified — no web access]`, nhưng vì danh lễ cần chỉ ~5–10 mốc (Tết dương, 30/4, 1/5, 2/9, 10/3 âm — lưu ý giỗ tổ là **âm lịch**, `holidays` xử lý âm lịch đến đâu thì unverified), bảng tự viết 10 dòng vẫn là lựa chọn đúng theo chính sách lazy-dev.

---

## 2. Nhóm số/tiền: có cần lib không?

So sánh thành thật:

- **Duckling** parse được money ("1 triệu", "500k" nếu grammar locale hỗ trợ `[unverified]`) — nhưng kéo theo toàn bộ chi phí vận hành đã nói ở mục 1.2.
- **dateparser** không dành cho tiền.
- **Regex tự viết:** ngữ pháp tiền Việt thực ra **hẹp**:
  - Số + từ nhân: `nghìn|ngàn|k`, `triệu`, (tỷ — hiếm gặp trong budget du lịch)
  - Số viết: `500k`, `1.000.000đ`, `1,5 triệu`, `1.500.000`
  - Nói: `triệu rưỡi`, `hai triệu năm`, `5 trăm`
  
  Phần core (số + multiplier + đ/dong/vnd) khoảng **25–35 dòng regex**; thêm bảng số chữ ("hai", "năm trăm") + "rưỡi"/"nửa" thì ~50 dòng. Đây chính xác là thứ frontend đã có (`inferBudget`, Planner.tsx:355) và đang hoạt động — đã kiểm chứng bằng code.

**Kết luận: không cần lib.** Regex thắng tuyệt đối ở field này vì (a) grammar hẹp và ổn định, (b) đã có code chạy được, (c) thêm lib chỉ để parse 1 field là vi phạm thứ tự ưu tiên stdlib > dep có sẵn > code tối thiểu. Việc cần làm là **port** inferBudget xuống backend làm nguồn sự thật duy nhất, thêm edge "rưỡi".

---

## 3. Nhóm NLP tiếng Việt: underthesea, VnCoreNLP, PhoNLP, pyvi

Đánh giá nhanh từng lib (trọng lượng/tốc độ/model — mọi số liệu `[unverified — no web access]`):

| Lib | Backend | Trọng lượng | Ghi chú |
|---|---|---|---|
| **underthesea** | pure Python | model cỡ vài MB, không cần torch `[unverified]` | tokenize, POS, NER, phân loại. "Nhẹ" nhất nhóm có NER |
| **pyvi** | pure Python, sklearn/CRF | nhỏ `[unverified]` | chủ yếu tokenize + POS; bảo trì yếu `[unverified]`; NER nếu có cũng rất hạn chế |
| **VnCoreNLP** | **Java server riêng** + client Python | JVM + model `[unverified]` | Mạnh về chất lượng POS/NER thời điểm ra mắt, nhưng phải chạy service Java — chi phí vận hành lớn |
| **PhoNLP/PhoBERT** | PyTorch | model transformer vài trăm MB + torch vài GB `[unverified]` | Chất lượng tốt nhất cho POS/NER tiếng Việt, nhưng tải trọng hoàn toàn không tương xứng |

**Câu hỏi đúng không phải "lib nào tốt" mà là: slot-filling 6 field có cần phân tích ngôn ngữ học không?**

- **Date, duration, giờ, người, tiền:** hoàn toàn là pattern — tokenization/POS không bổ sung gì. "2 người lớn 1 trẻ em" thì regex bắt số + đơn vị; gắn POS vào cũng chỉ ra được đúng thế.
- **Địa điểm:** về lý thuyết NER (tag LOC) giúp bắt được tên nơi chốn mở (open-vocabulary). Nhưng dự án đang dùng **danh sách đóng** 18 điểm đến (DESTINATION_LOCATIONS, Planner.tsx:14) — với danh sách đóng, alias matching + fuzzy (mục 4) chính xác hơn, rẻ hơn, debug được, trong khi NER cho kết quả probabilistic khó giải thích và có thể bắt nhầm "biển" hay "núi" làm LOC.
- **Sở thích/dislike:** là vấn đề **ngữ nghĩa**, không phải cú pháp — NER/POS vô dụng ("sợ độ cao" không có tag nào đánh dấu nó là preference).

**Quan điểm: overkill cho MVP.** Ngay cả underthesea — lib nhẹ nhất — cũng thêm dependency mới + model + độ trễ khởi động + chất lượng NER trên text chat không dấu câu/teencode là dấu hỏi lớn `[unverified]`. Theo đúng bậc thang lazy-dev: chưa có bậc nào trong nhóm này đáng bước vào. **Trigger để cân nhắc lại:** danh sách điểm đến vượt ~100 alias và người dùng bắt đầu nhập POI tự do ngoài danh sách (quán ăn, homestay cụ thể) — lúc đó underthesea NER hoặc chuyển hẳn sang LLM (làn 2) sẽ hợp lý.

---

## 4. Nhóm fuzzy match cho dislike/địa điểm

### 4.1 Từng công cụ

- **`difflib` (stdlib):** `get_close_matches` / `SequenceMatcher.ratio()`. Đủ cho typo mức ký tự trên danh sách nhỏ (< vài trăm chuỗi). Không cần cài gì. Tốc độ với list 100 alias là không đáng kể.
- **`rapidfuzz`:** bản rewrite C++ của fuzzywuzzy; `fuzz.WRatio` / `partial_ratio` xử lý tốt hơn difflib các trường hợp **substring** ("phong nha" trong "động phong nha kẻ bàng") và chuỗi có độ dài lệch nhau. Cần wheel binary — wheel cho cp310/cp311 trên Win/Linux nhiều khả năng có sẵn `[unverified]`. MIT, duy trì tốt `[unverified]`. Đây là ứng viên dependency mới **đáng giá nhất** trong cả bài khảo sát này, nếu alias matching thật sự cần chất lượng substring.
- **`unidecode`:** bỏ dấu tiếng Việt. Nhưng **không cần dep này**: Python stdlib làm được — `unicodedata.normalize('NFD', s)` rồi strip nhóm combining marks, thêm map `đ→d` — đúng kỹ thuật frontend đã dùng (`normalizeText`, Planner.tsx:123, bản NFD + strip `\u0300-\u036f`). Backend: 3 dòng stdlib. Không thêm unidecode.

### 4.2 Tổ hợp đề xuất

Pipeline chuẩn cho mọi entity closed-set (địa điểm, keyword dislike):

```
raw → normalize (lowercase, NFD-strip dấu, đ→d, gộp whitespace)
    → exact match alias table
    → rapidfuzz.extractOne (score_cutoff ≈ 85; fallback difflib nếu không thêm dep)
    → trả entity chính tắc hoặc None
```

Alias table cho dislike nên là **bảng keyword 2 chiều**: mỗi dòng là (cụm bề mặt → profile key), ví dụ:

```
"so do cao", "sợ độ cao", "acrophobia", "khong leo"  →  dislike: heights
"say xe", "motion sickness"                            →  dislike: motion_sickness
"ghet đám đông", "khong on ao"                        →  dislike: crowds
```

~30–50 dòng phủ phần lớn biểu đạt thông thường `[unverified — estimate]`.

### 4.3 Giới hạn nguyên tắc: fuzzy string ≠ semantic

Phải nói thẳng ranh giới:

- **Fuzzy giải quyết được:** cùng một khái niệm, khác bề mặt **gần nhau** (typo, dấu, trật tự từ). "hạ lon" → "hạ long": được. "vợ chồng" → 2 người: được **nhưng nhờ exact keyword, không phải fuzzy**.
- **Fuzzy chịu thua về nguyên tắc:** diễn đạt ngữ nghĩa của cùng preference. "Sợ độ cao" và "không thích chỗ phải leo trèo", "chỗ nào phải trèo là mình bỏ qua" cùng map về `heights`, nhưng khoảng cách chuỗi thì xa — không threshold nào cứu được mà không bắt nhầm thứ khác. Đây là vùng của LLM extraction (làn 2) hoặc xác nhận lại bằng UX (làn 4). Bảng keyword chặn được phần ngọn; phần đuôi dài thừa nhận là không giải quyết bằng non-LLM được.

**Kết luận field dislike:** keyword table + fuzzy = nền tảng đúng, nhưng phải thiết kế sao cho phần không match được sẽ **fallback rõ ràng** (chuyển sang LLM, hoặc hỏi lại) chứ không im lặng bỏ qua.

---

## 5. Nhóm slot-filling/chatbot framework (Rasa, MS Bot Framework…)

**Rasa (Rasa Open Source):** pipeline đầy đủ gồm intent classification + entity extraction (DIET classifier) + dialogue policies + action server. Muốn dùng được phải: viết `domain.yml`, thu thập ~20+ câu mẫu mỗi intent để train `[unverified — heuristic chung]`, chạy `rasa train` ra model (vài chục đến vài trăm MB `[unverified]`), vận hành ≥1 service riêng (rasa + action server), quản lý vòng đời retrain. Rasa OS gần đây được维护 ít hơn do công ty mẹ tập trung bản thương mại `[unverified]`.

**Microsoft Bot Framework / Botpress:** hướng connector + dashboard, kéo theo ràng buộc cloud/hạ tầng của nền tảng — không hợp với backend FastAPI tự quản.

**Đánh giá cho MVP này: không đáng — và quan trọng hơn là không đúng bài toán.** Luồng hiện tại của Planner.tsx là **wizard tuyến tính** (hỏi lần lượt duration → destination → people, mỗi bước validate bằng regex), không phải hội thoại tự do cần phân loại intent hay quản lý policy đối thoại. Framework slot-filling sinh ra cho bài toán khác. Mang Rasa vào đây là thêm toàn bộ chi phí vận hành (training data, model artifact, service, retrain loop) để đổi lấy thứ đang có sẵn 300 dòng regex chạy được.

Không có bậc thang nào biện minh cho framework ở giai đoạn này. Nếu sản phẩm sau này chuyển sang chat tự do đa lượt, thứ đáng cân nhắc trước Rasa gần như chắc chắn là LLM function-calling (làn 2) — không phải framework cổ điển.

---

## 6. Tổng kết kiến trúc NON-LLM đề xuất (field → parser)

| Field | Công cụ | Dep mới | Ước lượng code |
|---|---|---|---|
| Ngày tương đối ("thứ bảy tuần sau") | `dateparser` (spike trước) hoặc tự viết weekday-offset | 0–1 | 1 dòng dùng lib / ~25 dòng tự viết |
| Ngày tuyệt đối + range ("20/8 đến 22/8") | Regex DMY + split "đến/tới" — port từ inferDateRange | 0 | ~60 dòng (đã có sẵn ở FE) |
| Lễ ("dịp 2/9", "30/4") | strip "dịp/lễ" + bảng tên lễ ~10 mốc | 0 | ~15 dòng |
| Duration ("3 ngày", "1 tuần") | Regex — port từ inferDayCount | 0 | ~40 dòng (đã có sẵn ở FE) |
| Khung giờ ("từ 9h đến 5 tối") | Regex — port từ inferClockRange | 0 | ~35 dòng (đã có sẵn ở FE) |
| Số người ("2 người lớn 1 trẻ", "vợ chồng") | Regex — port từ inferPeople, mở rộng adult/child | 0 | ~50 dòng |
| Tiền ("1 triệu", "500k", "1.000.000đ") | Regex — port từ inferBudget + "rưỡi" | 0 | ~45 dòng |
| Địa điểm | Alias table + normalize stdlib + difflib (nâng cấp rapidfuzz nếu cần substring) | 0–1 | ~40 dòng logic + table alias |
| Dislike/sở thích | Bảng keyword → profile key + fuzzy trên keyword | 0 | ~50 dòng + table |
| **Tổng** | | **0–2 dep mới** | **~350–450 dòng backend + test** |

**Nguyên tắc kiến trúc:** mọi parsing chuyển về **một module backend duy nhất** (FastAPI endpoint hoặc hàm thuần trong domain layer); frontend chỉ giữ parse tức thì cho UX của wizard (mục 7). Đây là quyết định ngăn chặn việc nuôi 2 bản sao parser TS/Python lệch nhau — và là finding quan trọng nhất của làn này, dù thuộc vùng giao với làn 1.

**Field nào regex/non-LLM chịu thua, phải nói rõ:**
1. Preference ngữ nghĩa ("không thích chỗ phải leo trèo nhiều") — fuzzy bất lực về nguyên tắc.
2. Ngày tương đối mờ ("đi dịp lễ gần nhất", "cuối tháng này rảnh") — không mốc, không parser nào xử lý nổi thiếu ngữ cảnh.
3. Điểm đến ngoài danh sách + typo xa ("biển đảo nào vắng vắng gần SG") — vừa open-vocab vừa preference, chồng lấn LLM.
4. Đa ý định trong một câu ("đi đâu cũng được, miễn không leo núi, tầm 2tr") — cần tách intent, regex không cấu trúc nổi.

Với các field 1–4, non-LLM nên nhận phần dễ và **chủ động nhường phần khó** (fallback sang làn 2) thay vì cố phủ bằng ngày càng nhiều heuristic.

---

## 7. Audit các hàm `infer*` trong `frontend/components/Planner.tsx`

Đã đọc trực tiếp (kiểm chứng): `normalizeText` (:123), `inferClockRange` (:127), `hourWithMeridiem` (:142), `inferHourSpan` (:149), `inferDateRange` (:178), `inferDayCount` (:234), `inferDuration` (:253), `inferPairedPeople` (:277), `inferPeople` (:286), `inferBudget` (:355), `DESTINATION_LOCATIONS` + `hasDestination`/`destinationLocation` (:14, :331, :336).

**Giữ nguyên (logic đúng, đáng tin):**
- `inferClockRange` — xử lý tốt meridiem + khoảng qua đêm; port xuống backend gần như nguyên样.
- `inferDateRange` — range slash-date có xử lý cuốn năm; giữ.
- `inferDayCount` / `inferDuration` / `inferHourSpan` — bucketing hợp lý; giữ.
- `hourWithMeridiem` — giữ.

**Giữ nhưng mở rộng:**
- `inferPeople` — đã có "vợ chồng" → 2 (:314); cần mở rộng tách `adults/children` cho "2 người lớn 1 trẻ" (hiện đang cộng gộp :296-299) — quyết định schema thuộc làn 1/làn 2, làn này chỉ báo cáo khoảng trống.
- `inferBudget` — thiếu "rưỡi"/"nửa" ("1 triệu rưỡi" sẽ rơi vào `trieu` match nhưng mất 0.5 `[đọc code]`); thêm 1 nhánh regex.

**Chuyển chỗ (không xóa hẳn):**
- `DESTINATION_LOCATIONS` + `hasDestination` — chuyển thành alias table backend (mục 4.2); frontend chỉ giữ nếu cần preview tọa độ lập tức, hoặc bỏ nếu backend trả echo.

**Bỏ/không thay bằng lib nào:**
- `normalizeText` — không thay bằng unidecode/chrono; nhân bản 3 dòng stdlib ở backend.
- Không hàm nào đáng thay bằng thư viện: chrono-node bị loại (không có tiếng Việt), và việc đưa lib JS vào chỉ có nghĩa nếu parser ở lại frontend — trái với nguyên tắc backend-làm-nguồn-sự-thật.
- Ứng viên xóa dài hạn: các bảng `DAY_COUNT_WORDS`/`WEEK_COUNT_WORDS` (:214-232) và wordMap trong inferPeople (:300-311) — khi backend sở hữu parser, frontend không cần lặp lại bảng số-chữ; giữ tạm chỉ nếu wizard cần echo tức thì.

**Việc duy nhất cần spike trước khi chốt:** chạy thử `dateparser.parse("thứ bảy tuần sau", settings={"DATE_ORDER": "DMY", ...})` trên Python 3.11 với `languages=['vi']` để xác nhận locale vi thật sự hiểu chuỗi này `[unverified — chưa chạy]`. Nếu fail: tự viết weekday-offset ~25 dòng, không cần dependency nào.

---

## Phân loại kết luận

| Mức | Nội dung |
|---|---|
| **Blocker** | Không phát hiện blocker từ làn này. |
| **High** | Parser phải quy về một chủ (backend); hiện đang tồn tại song song logic TS ở Planner.tsx — rủi ro 2 nguồn sự thật. |
| **High** | "thứ bảy tuần sau" (date tương đối tiếng Việt) là khoảng trống thật; cần spike dateparser locale vi trước khi chốt, nếu không tự viết offset. |
| **Medium** | Quyết định rapidfuzz vs difflib: spike nhỏ trên alias list thật; difflib đủ dùng ở quy mô hiện tại, rapidfuzz đáng giá khi cần substring matching. |
| **Medium** | Thiết kế fallback rõ ràng cho phần fuzzy không match được (dislike/mở rộng địa điểm) — chuyển làn 2 hoặc hỏi lại, không im lặng bỏ qua. |
| **Low** | Tiền/lễ/duration: regex thuần, port từ code FE đã chạy. |
| **Low** | chrono-node chỉ đáng thêm nếu giữ parse input tiếng Anh phía client; nếu không, bỏ. |
| **Note** | Duckling là công cụ có hình thái output đúng nhất (range/duration/money) nhưng chi phí vận hành (Haskell sidecar, dấu hiệu bảo trì thấp `[unverified]`) không tương xứng với MVP. Revisit nếu có Docker infra. |
| **Note** | Toàn bộ NLP stack tiếng Việt (underthesea/VnCoreNLP/PhoNLP/pyvi) là overkill cho 6 slot closed-set; trigger xem lại: >100 alias + POI open-vocabulary. |
| **Note** | Toàn bộ số liệu về version, benchmark, kích thước model, trạng thái bảo trì ở tài liệu này là `[unverified — no web access]` và phải kiểm chứng trước khi dựa vào đó để chọn version pin. |
