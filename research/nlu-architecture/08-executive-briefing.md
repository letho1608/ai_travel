# 08 — BRIEFING CUỐI CÙNG: Kiến trúc NLU cho ai_travel (đã qua red-team)

**Biên tập cuối:** tổng hợp `05-synthesis.md` + `06-followup-verification.md` + `07-red-team.md`, có đối chiếu lại code tại 3 điểm red-team nêu (`i18n.test.mjs:426-429`, `planner.py:_destination_context`, `ai.py:458`) — cả ba đều xác nhận đúng. Tài liệu này là phán quyết **sau khi đã bị red-team bẻ và sửa**, không phải phán quyết nguyên bản của synthesis.

---

## 1. TL;DR — Phán quyết cuối cùng

Giữ kiến trúc **4 tầng** của synthesis: (1) UI parse-then-confirm, (2) module backend canon `intent_parse.py` sở hữu mọi parser định lượng, (3) bảng alias biến dislike thành hard-filter, (4) LLM chỉ làm định tính + pydantic gate + destination phải qua catalog. Hướng này **đứng vững** qua đối chiếu độc lập — không cần thay.

Nhưng **kế hoạch thực thi Tier 0 nguyên bản đã hỏng**: 3 trong 5 việc khai tiêu chí sai sự thật khi đối chiếu test và CI thật. Sửa bắt buộc: (a) nới assert benchmark lên đầu bảng vì **CI đang đỏ ngay lúc này** (`assert 240 <= 200` fail, đã chạy xác nhận 2 lần); (b) bug fold `đ` ở FE là vấn đề **UX** (wizard hỏi lại thừa), không phải Blocker dữ liệu — backend đã tự cứu bằng scan text; (c) "cache understanding" bất khả thi bằng decorator — phải compute 1 lần tại router và đổi chữ ký `build_plan`; (d) chặn fallback tọa độ Hà Nội **không làm được ở FE một mình** (schema bắt buộc `location`, catalog FE 18 mẫu vs BE quét toàn bộ) — cần thiết kế trước, code sau; (e) không gỡ wizard khi chưa có 2 con số: tỷ lệ gõ không dấu và drop-rate funnel.

---

## 2. Synthesis bị red-team lật ở đâu, sửa thế nào

| # | Mức | Synthesis nói | Red-team bẻ (bằng chứng) | Phán quyết cuối |
|---|---|---|---|---|
| B1 | Blocker | T0.1+T0.2 "phá 0 test" (làn 4 đã đếm) | `i18n.test.mjs:426/428/429` assert tĩnh khóa `DEFAULT_LOCATION`, chữ ký `destinationLocation`, và dòng `location: destinationLocation(composedContext)` — tôi đếm lại: 68 chỗ nhắc `plannerSource`. Chặn fallback đúng chỗ là vỡ 3 assert | **"Phá 0 test" bị bác.** 3 source-assert phải được cập nhật *có chủ đích trong cùng PR*; tách PR fold-`đ` khỏi PR chặn fallback |
| B2 | Blocker | T0.3 "cache `_request_understanding`", effort S/M | Hàm nhận `PlanRequest` (pydantic, không hashable) → `lru_cache` vô dụng. Cách đúng: compute 1 lần tại router (`plans.py:154`), đổi chữ ký `build_plan(request, understanding=None)` — lan sang 3 call-site `quality_benchmarks.py:565,603,655` + ~57 site test | **Effort thật M.** Xóa chữ "cache"; viết thành "compute-once tại router" |
| B3 | Blocker | Fix benchmark xếp Tier 2 ("quý này") | Gate đang đỏ CI: `assert 240 <= 200` FAILED (chạy thật 2 lần: 2.36s và 2.34s); CI chạy pytest toàn bộ mỗi push → mọi PR Tier 0/1 không merge-able | **Dời lên T0.0 — việc đầu tiên.** Tin tốt kèm theo: bypass assert count, chạy benchmark trực tiếp cho `pass_rate = 1.0`, `hallucination_failures = 0` trên 240 scenario |
| H1 | High | T0.2 chặn fallback Hà Nội, effort S | `schemas.py:30` bắt buộc `location: Coordinate` — FE không thể bỏ field. FE chỉ biết 18 pattern, BE khớp catalog 30k+ place: chặn FE-only sẽ **nhốt user** gõ điểm đến hợp lệ (vd "Phú Yên") mà BE vốn resolve được | **M–L + thiết kế bắt buộc trước code** (datalist catalog / hỏi lại / endpoint parse — chọn một) |
| H2 | High | Bug `đ` FE = "Blocker dữ liệu, đà lạt/đà nẵng trượt" | Backend fold `đ` (`text_utils.py`) và `_destination_context` (`planner.py:1152-1165`) recover điểm đến **từ text**, không tin tọa độ FE — gọi `_request_understanding` thật: `diem_den = Đà Lạt`, `bat_buoc_thieu = []`, tọa độ đúng. Có comment trong code thừa nhận FE gửi anchor tạm | **Hạ xuống High-UX.** Tác hại thật: wizard hỏi lại thừa + payload lệch + log lệch. Vẫn fix, nhưng không khẩn kiểu Blocker |
| H3 | High | Gỡ wizard "sửa ~41 assert" | Đếm lại: 68 assert lên `plannerSource`; ~25 khóa cấu trúc wizard là **đặc tả hành vi** (không phải assert để xóa); test contract bắt đủ 44 key × 19 locale = 836 chuỗi dịch | Con số "~41" không tái lập được. Chi phí thật = viết lại đặc tả + dịch 19 locale → **M×**, không phải sửa assert |
| H4 | High | "Parse-then-confirm thắng" chốt tuyệt đối | Không có dữ liệu nào về tỷ lệ gõ không dấu hay drop-rate. SSE hiện tại không có kênh trả understanding về FE giữa luồng (nhánh thiếu input phát `error`, FE ném Error chung) → card "sửa trước submit" cần **đường render mới hoàn toàn** | Gắn cờ: **quyết định UX cần đo trước**, không chốt thắng tuyệt đối. T1.2 effort L |
| M1 | Medium | "1 dòng fold `đ`" | FE có **2** bản normalize (`Planner.tsx:46` và `:123`) | Sửa cả hai; tiêu chí = "2 chuẩn FE trùng `ascii_fold` BE" |
| M2 | Medium | "FE lệch → BE thắng, UI hiện lại" | Cơ chế hồi đáp không tồn tại: SSE chỉ có `status`/`result`; understanding về FE sau khi build xong | Bổ hạng mục "kênh hồi đáp BE→UI" vào T1.2; nếu chưa có, câu "BE thắng" chỉ là nguyện vọng |
| M3 | Medium | Mở đủ 12 `DISLIKE_PREFIXES` | `DISLIKE_PREFIXES` chứa `"so"`, `"ghe"`; profile `food` chứa token `'an'` 2 ký tự → false-positive là cấu trúc | Thêm bước **đo precision từng prefix** trước khi bật hard-filter |
| M4 | Medium | T0.5 đổi nhãn offline = fix log thuần | Nhãn `ai_extracted` gắn điều kiện `xuat_xu` tại `planner.py:1380`; consumer của nhãn chưa audit | Đổi nhãn kèm grep consumer + audit `xuat_xu` |

Không có phát hiện kỹ thuật nền tảng nào của synthesis bị lật — cái bị lật là **effort, thứ tự, và tiêu chí chấp nhận** của Tier 0, cộng một framing giá trị phóng đại (H2).

---

## 3. Bảng khuyến nghị cuối cùng (effort đã hiệu chỉnh)

### Tier 0 — làm ngay (tuần này), theo THỨ TỰ MỚI

| # | Việc | Effort cũ → mới | Ghi chú bắt buộc |
|---|---|---|---|
| **T0.0** | Nới assert benchmark 200→240 (`tests/test_problem_06_10_acceptance.py:485`) | (mới) **S** | CI đang đỏ — mọi PR khác kẹt nếu không làm trước. Kèm: đọc `pass_rate` từ report trực tiếp (đã đo 1.0, nhưng giữ bước kiểm tra) |
| T0.1 | Fold `đ→d` trong **cả 2** bản normalize FE (`Planner.tsx:46,123`) + test hành vi | S → **M** | Là fix UX (hỏi lại thừa), không phải fix dữ liệu. PR riêng; không kèm T0.2 |
| T0.2 | Chặn fallback im lặng tọa độ Hà Nội | S → **M–L, thiết kế trước** | Chọn 1 trong 3: datalist catalog / hỏi lại user / endpoint parse. Không được chặn FE-only (schema + regression tập ngoài-18). Cập nhật 3 source-assert trong cùng PR |
| T0.3 | Compute understanding 1 lần tại router, đổi chữ ký `build_plan(request, understanding=None)` | S/M → **M** | Không dùng `lru_cache`. Giữ default để không vỡ 3 site benchmark + 57 site test |
| T0.4 | Rotate Groq API key trong `.env` | S | Key đã lộ trong phiên làm việc; file gitignored nhưng vẫn phải rotate |
| T0.5 | Sửa nhãn `ai_extracted` → `offline_adapter` khi extractor là OfflineAIAdapter | S | Kèm audit `xuat_xu` (`planner.py:1380`) và mọi consumer đọc log `boc_tach_yeu_cau` |

### Tier 1 — nền tảng (tháng này)

| # | Việc | Effort | Ghi chú |
|---|---|---|---|
| T1.1 | Module canon `app/pipeline/intent_parse.py` — port các `infer*` FE chạy tốt, chuẩn `ascii_fold` + test bộ 40 câu thất bại | **L** | Việc đòn bẩy cao nhất: giết root cause 3 chuẩn normalize |
| T1.2 | UI parse-then-confirm: bước 0 (echo + chip, không gỡ wizard) + kênh hồi đáp BE→UI (parse endpoint hoặc understanding trong SSE result) | M→L → **L** | Không có kênh hồi đáp thì "BE thắng" vô nghĩa; SSE error UX hiện không render được card |
| T1.3 | Dislike hard-filter: alias surface→profile + **đo precision 12 prefix trước khi bật** | **M** | Token `an`/`so`/`ghe` là FP cấu trúc đã chứng minh |
| T1.4 | Pydantic gate extraction (`extra="forbid"`, ranges từ hằng số sẵn có) + AI destination phải qua catalog mới lấp `bat_buoc_thieu` | **M** | Vá hole bypass destination + bất đối xứng guard extraction/assemble |
| T1.5 | Relative date: spike `dateparser` locale vi 1 buổi; fail → tự viết offset ~25-50 dòng | **S/M** | Claim locale-vi vẫn unverified — spike là điều kiện, không phải cam kết |
| T1.6 | Breaker phân loại lỗi (JSON-error không đếm; 429 backoff) | **S** | Rate-limit extraction đang có thể kéo sập assemble |
| T1.7 | Lazy-singleton `create_ai_adapter()` (`ai.py:458`) | **S** | Misconfig đang sập app lúc import, **trước** `validate_production` (`main.py:16` trước `:20`) — fallback không bao giờ chạy tới |

### Tier 2 — hoàn thiện (quý này)

| # | Việc | Effort | Ghi chú |
|---|---|---|---|
| T2.1 | Refine dùng canon parser (fix "ngan sach 2 trieu", "doi" không dấu) | **M** | Sau khi T1.1 xong |
| T2.2 | `max_places`: áp cap trong `choose_candidates` hoặc xóa parse | **S** | Hiểu mà không hành xử = nợ |
| T2.3 | Thêm ~30 scenario adversarial vào benchmark | **S** (thu gọn từ M) | Assert đã fix ở T0.0; pass_rate 1.0 đã đo |
| T2.4 | Xóa bảng từ trùng FE (`DAY_COUNT_WORDS`...) khi card ổn định | **S** | Kết thúc 2 nguồn sự thật |
| T2.5 | Quyết định `must_visit`: nối vào pipeline hoặc xóa khỏi prompt | **S/M** | Field chết verified: extract xong không ai tiêu thụ. LLM đang hứa thay user một thứ hệ thống không làm |

### Tier 3 — KHÔNG làm

Rasa/Bot Framework (sai bài toán); Duckling (Haskell sidecar, không tương xứng); PhoBERT/VnCoreNLP/underthesea (overkill cho 6 slot closed-set; trigger xét lại: >100 alias + POI open-vocab); local LLM production; confidence scoring bằng logprobs (provider không trả); LLM extract số tự do (dead code khi form là nguồn định lượng); chat-first flow (schema 6 trường cố định — mọi câu chat cuối cùng bị ép về form); gỡ wizard (nằm ngoài mọi Tier cho tới khi có dữ liệu funnel — xem §4).

---

## 4. Phân tích trung thực: hướng nào TỐT NHẤT cho dự án này

**Tốt nhất:** tuần tự hẹp, bắt đầu từ chỗ đang chảy máu thật.

1. **T0.0 trước hết** — lý do duy nhất và đủ: CI đỏ thì không gì khác merge được. 5 phút sửa, không có lý do gì để chậm.
2. **T1.1 (canon module) là việc đòn bẩy cao nhất toàn bộ nghiên cứu.** Mọi bệnh nặng nhất (3 chuẩn normalize, refine reject thứ generate chấp nhận, budget chỉ sống nhờ FE, duplicate parser) đều có cùng root cause: parser sống ở 2 nơi, mỗi nơi một chuẩn. Port `infer*` xuống BE trên `ascii_fold` giết cả chùm bệnh một lần. Backend đã chứng minh chuẩn này hoạt động (tự cứu được "đà lạt" nhờ scan text).
3. **T0.3 + T1.7 + T0.5 là chùm "offline story trung thực".** Dự án mặc định `AI_MODE=offline`, nhưng offline hiện tại: dán nhãn sai, nhân đôi chi phí khi online, và sập app khi misconfig. Ba fix nhỏ biến câu chuyện offline từ "hy vọng" thành "đã kiểm chứng".
4. **LLM giữ nguyên vai trò hiện tại — đây là quyết định đúng nhất của cả 5 làn.** Prompt cấm suy luận số, form là nguồn định lượng, AI chỉ bóc tách định tính có evidence. Không có dữ liệu nào trong nghiên cứu này biện minh cho việc mở rộng vai trò LLM. Chỉ thêm gate (T1.4) để extraction có cùng kỷ luật output mà assemble đã có.

**Không nên làm gì:**

- **Không gỡ wizard ở thời điểm này.** Đây là điểm red-team đúng nhất: phán quyết "parse-then-confirm thắng" không có dữ liệu, chi phí thật là 836 chuỗi dịch × đặc tả hành vi viết lại, và hạ tầng SSE cho card chưa tồn tại. Điều kiện bật đèn xanh: đọc log `boc_tach_yeu_cau` hiện có (không cần analytics mới) để biết tỷ lệ gõ không dấu và funnel hiện tại rơi ở đâu. Nếu đa số gõ không dấu, ưu tiên fold-`đ` còn tự hạ thêm một bậc.
- **Không chặn fallback FE một mình.** Schema bắt buộc `location` + catalog FE (18) hẹp hơn BE (full scan) → chặn FE-only gây regression cho chính tập input backend phục vụ tốt. Thiết kế trước, code sau.
- **Không thêm dependency trước spike.** dateparser locale-vi là claim đơn nguồn, chưa ai chạy. Spike 1 buổi rồi chốt; default vẫn là regex tự viết.
- **Không build chat-first.** Không lane nào chứng minh nhu cầu; schema 6 trường là bằng chứng cấu trúc rằng sản phẩm là form.
- **Không dùng con số coverage 35-60% của làn 1 làm cam kết** — đó là ước lượng định tính có phương pháp, chỉ dùng để xếp ưu tiên.

---

## 5. Ground-truth tally + confidence cuối cùng

**Điểm ground-truth thiết lập bằng chạy thật/đo thật trong phiên (06 + 07):**

1. Benchmark gate FAIL thật: `assert 240 <= 200` (pytest, 2 lần chạy độc lập).
2. `pass_rate = 1.0`, `hallucination_failures = 0` trên 240 scenario (chạy trực tiếp benchmark, bypass assert count) — câu hỏi mở của follow-up 1 đã đóng.
3. Extraction chạy 2 lần/request trên nhánh build-thành-công (truy vết call-site + xác nhận không cache).
4. Offline trả `{}` nhưng dán nhãn `ai_extracted` (đọc cơ chế từng nhánh `_safe_ai_intent`).
5. `must_visit` là field chết: 1 nơi extract, 1 nơi ghi metadata, 0 nơi tiêu thụ.
6. Import-crash: `ai.py:458` chạy trước `validate_production` (`main.py:16` vs `:20`).
7. Backend tự cứu destination có `đ` bằng text-scan (`_destination_context`, gọi runtime thật) → bug FE nhỏ hơn framing Blocker.
8. `_request_understanding` không cache-able bằng decorator (PlanRequest không hashable).
9. `schemas.py:30` bắt buộc `location` → chặn fallback FE-only bất khả thi.
10. `i18n.test.mjs:426/428/429` khóa fallback; đếm 68 assert `plannerSource` (bản này đếm lại: 68 — khớp con số sửa của synthesis, lệch 1 so với red-team's 67, không ảnh hưởng kết luận); planner contract = 44 key × 19 locale.

**Tally tổng hợp trên 33 claim chịu tải của khuyến nghị cuối:**

| Loại | Số lượng |
|---|---|
| Verified bằng **chạy thật** (pytest / runtime / đếm) | 12 |
| Verified bằng **đọc code trực tiếp** (số dòng cụ thể) | 15 |
| **Chưa kiểm chứng** (dateparser vi locale, F1 relative-date, tỷ lệ mismatch log thật, số AI call/turn, tỷ lệ gõ không dấu, drop-rate funnel) | 6 |

→ Tỷ lệ kiểm chứng: **27/33 ≈ 82%**, trong đó 12/33 (36%) là bằng chứng thực thi, không chỉ đọc code.

**Confidence cuối cùng: 7/10.**

Lý do: mọi claim kỹ thuật trong khuyến nghị cuối đã được đọc code hoặc chạy xác nhận (kể cả 3 điểm red-team nêu — briefing này tự kiểm lại và thấy đúng). Trừ 3 điểm, đúng bằng tỷ lệ chưa kiểm chứng cap trần: (a) 2 claim sản phẩm quan trọng bậc nhất — "parse-then-confirm thắng" và mức khẩn của fold-`đ` — treo trên dữ liệu usage không tồn tại trong repo; (b) mọi claim thư viện ngoài (dateparser, chrono-node, Duckling) là unverified, không WebSearch; (c) effort đã hiệu chỉnh theo test thật nhưng vẫn là ước lượng khi chưa implement. Red-team chấm synthesis nguyên bản 5/10 và ước ~8/10 sau 8 fix; briefing này giữ 7/10 vì 2 claim sản phẩm ở (a) vẫn chưa có dữ liệu — chúng là lý do Tier "gỡ wizard" bị đóng băng, không phải nghi ngờ hướng kiến trúc.

---

## 6. Việc đầu tiên của ngày mai

1. Merge T0.0 (nới assert) — mở khóa CI.
2. Cùng tuần: T0.4 (rotate key), T0.5 (nhãn offline + audit consumer), T1.7 (lazy adapter).
3. Viết đề xuất thiết kế 1 trang cho T0.2 (chọn 1 trong 3 phương án) — không code trước thiết kế.
4. Bắt đầu T1.1 ngay khi thiết kế T0.2 được duyệt song song.
5. Đọc log `boc_tach_yeu_cau` cho 2 con số UX — kết quả quyết định số phận wizard và thứ tự T0.1.
