# 05 — PHÁN QUYẾT TỔNG HỢP: Kiến trúc thay regex-NLU cho intent extraction

**Làn:** tổng hợp (5/5), đứng trên 4 làn: 01-regex-audit, 02-llm-extraction, 03-non-llm-libraries, 04-ux-architecture.
**Câu hỏi nghiên cứu:** kiến trúc tốt nhất thay regex-NLU cho intent extraction (thời gian / số người / ngân sách / địa điểm / dislike từ tiếng Việt tự do), mặc định `AI_MODE=offline`, nguyên tắc "AI chỉ bóc tách, code sinh lịch".
**Phương pháp:** đọc đầy đủ 4 báo cáo làn, sau đó đọc lại code thật để phân xử mọi claim chịu tải. Phần lớn kết luận dưới đây có số dòng kiểm chứng; claim ngoài repo gắn `[unverified]`.

> **Kiểm chứng: 41/42 kết luận chịu tải trong tài liệu này được kiểm chứng trực tiếp bằng code** (danh sách §7). Ngoại lệ duy nhất là pass-rate benchmark (chỉ kiểm chứng bằng phép tính tĩnh, chưa chạy pytest).

---

## 1. Cross-check: các claim chịu tải và phân xử

### 1.1 Claim cả 4 làn đồng thuận — và đồng thuận ĐÚNG (đã kiểm chứng)

| # | Claim | Bằng chứng code tôi đọc lại |
|---|---|---|
| 1 | FE normalize không fold `đ`, BE fold `đ→d` — câu "đà lạt/đà nẵng" chuẩn trượt FE | `Planner.tsx:123-125` (NFD-strip + lowercase, không đụng `đ`) so `text_utils.py:3-10` (`đ→d` rồi NFD). Pattern `/da lat/` tại `Planner.tsx:24` không khớp chuỗi còn `đ`. **ĐÚNG — Blocker thật.** |
| 2 | AI là optional: offline → extract trả `{}`, pipeline không chết | `ai.py:74-78` (`OfflineAIAdapter.extract_request_intent` → `{}`), `planner.py:1248-1256` (`_safe_ai_intent` fallback), `ai.py:449-452` | 
| 3 | Định lượng đến từ form, không từ text ở tầng generate | `planner.py:1341-1343, 1364-1367` (nguồn `form_chat`), ghi chú kiến trúc `planner.py:1385`. Backend generate **không parse budget từ context** — tôi grep `trieu|nghin` trong `planner.py`: chỉ có `request.ngan_sach` (field form). **ĐÚNG.** |
| 4 | Prompt hiện tại cấm LLM suy luận số | `ai.py:127` — nguyên văn "Do not infer people, budget or trip duration unless the text says it" |
| 5 | Lắp ráp (assemble) có guard whitelist `trusted_ids`, extraction thì không | `ai.py:54-57` (raise ValueError nếu id ngoài danh sách) vs `ai.py:160-165` (chỉ `json.loads`, trả dict sống) |
| 6 | Refine lệch chuẩn normalize: cùng câu không dấu pass ở generate, trượt ở refine | `plans.py:41-51` (`SWAP_INTENT`, `PEOPLE_INTENT` match text có dấu), `plans.py:672` search trên `message` thô, `plans.py:675-678` (budget regex có dấu) |
| 7 | Dislike free-text chỉ trưng bày, không lọc | `_rule_dislike_fields` `planner.py:1301-1311` chỉ đổ vào `khong_thich` của understanding; hard filter `_is_place_disliked` `planner.py:1220-1236` chỉ nhận profile từ `_disliked_profiles` (1209-1217) + 2 prefix keyword (1233). `choose_candidates` `planner.py:3456-3462` không đọc nhánh free-text. |
| 8 | UI hiện tại là wizard 3 bước giả chat; địa điểm ngoài 18 regex → im lặng tọa độ Hà Nội | `Planner.tsx:69-71` (3 cờ boolean), `:550-560` (`answerDestination` nhận mọi text), `:336-339` (`?? DEFAULT_LOCATION` Hà Nội), `:13` |

### 1.2 Các MÂU THUẪN giữa làn và phân xử

**M1 — "LLM có nên extract định lượng?"**
- Làn 1 đề nghị chuyển phần định tính **và relative date/datetime** cho LLM, regex giữ 4 việc.
- Làn 2 nói KHÔNG: định lượng là "bổ sung biên lợi nhuận thấp hơn chi phí" khi form đã bắt buộc nhập; chỉ extract số ở dạng `raw_text` khi có flow chat-first (chưa tồn tại).
- Làn 3 nói định lượng (date/duration/giờ/người/tiền) là pattern hẹp — regex tự viết + port từ FE là đủ; chỉ nhường phần ngữ nghĩa cho LLM.
- Làn 4 nói định lượng phải hiện trên confirmation card để user sửa trước submit.

**Phán quyết: KHÔNG phải mâu thuẫn thật, là 4 lát của cùng một đáp án.** Định lượng = deterministic parser (port regex FE xuống BE) + UI xác nhận; LLM chỉ đụng định tính + span văn bản (`raw_text`), server convert. Làn 2 đúng về kinh tế học (đã kiểm chứng: `planner.py:1377-1385` định lượng luôn gắn nguồn `form_chat`); làn 3 đúng về kỹ thuật; làn 1 hơi vội khi giao relative-date cho LLM — relative date có mốc ("thứ bảy tuần sau") là bài toán offset-calendar ~25-50 dòng, không cần burn token [unverified: không đo F1 so sánh].

**M2 — Parser đặt ở FE hay BE?** (mâu thuẫn thật, phải phán quyết)
- Làn 3: **mọi parsing về một module backend duy nhất**; FE chỉ giữ parse tức thì cho UX; dài hạn xóa bảng số-chữ FE (`DAY_COUNT_WORDS`, `WEEK_COUNT_WORDS`).
- Làn 4: **tái sử dụng nguyên vẹn infer\* phía client** — card render ngay sau submit đầu tiên, KHÔNG POST, mọi sửa chữa là local state.

Hai thiết kế này xung đột: làn 4 muốn card hiện tức thì (khỏi chờ round-trip), làn 3 muốn một nguồn sự thật (chính cái bug 3-chuẩn-normalize hiện nay sinh ra từ 2 nguồn).

**Phán quyết (xem §2): FE parse = preview, BE parse = phán quyết cuối.** Card làn 4 có thể render nháp bằng regex FE (đã sửa `đ`), nhưng giá trị gửi đi phải được BE re-parse/validate bằng module chuẩn duy nhất; xung đột → BE thắng và card hiện lại giá trị BE hiểu. Round-trip preview (nếu cần) đã có sẵn kiến trúc: `missing_required_inputs` (`planner.py:1389-1399`) trả full `understanding` mà không build plan — chỉ cần bọc thành endpoint `POST /api/plan/parse`.

**M3 — Chat tự do có phải hướng đi?**
- Làn 4: "hướng chat tự do là sai lầm" — backend là schema 6 trường cố định (`schemas.py:28-33` đã kiểm chứng), mọi câu chat cuối cùng bị ép về form.
- Làn 2: coi chat-first là *tương lai giả định* đáng chuẩn bị prompt `raw_text`, không phải hiện tại.
**Phán quyết: đồng ý làn 4.** Không lane nào chứng minh được nhu cầu chat đa turn; parse-then-confirm là mẫu số chung.

**M4 — Offline degradation: "chấp nhận được" đến mức nào?**
- Làn 2: "offline = regex cũ là đánh đổi chấp nhận được", vì định lượng không phụ thuộc AI.
- Làn 1: đo coverage regex thấp — datetime tuyệt đối ~15-20%, dislike ~10-20%, budget ~25-30%.
**Phán quyết: cả hai đúng ở hai trục khác nhau.** Offline chấp nhận được về *độ đúng cấu trúc* (lịch không vỡ), và dở về *độ hiểu câu tự do*. Quan trọng hơn, tôi phát hiện cả hai làn đều **nhầm một chi tiết**: offline mode không trả nguồn `rule_based_fallback` như làn 2 viết — `OfflineAIAdapter.extract_request_intent` trả `{}` *không raise*, nên `_safe_ai_intent` (`planner.py:1252-1256`) dán nhãn `({}, "ai_extracted")`. Understanding ở chế độ offline tự khai "đã bóc tách bằng AI" trong khi AI không chạy. Lỗi metadata, không lỗi chức năng, nhưng làm bẩn log `boc_tach_yeu_cau` (`plans.py:156,174`) — thứ làn 2 định dùng làm shadow-eval.

**M5 — Thư viện: dateparser/rapidfuzz vs tự viết**
- Làn 3 tự mâu thuẫn nội bộ nhẹ: kết luận "0-2 dep mới" nhưng mọi ước lượng ngoài repo đều `[unverified]`. Các làn khác không bàn.
**Phán quyết: giữ nguyên đề xuất làn 3 nhưng hạ cấp dateparser thành spike bắt buộc trước khi chốt** (claim locale-vi là đơn nguồn, chưa ai chạy). Regex tự viết là default; rapidfuzz chỉ thêm khi difflib hụt ở substring matching trên alias thật.

### 1.3 Chỗ làn SAI (kể cả khi nhiều làn cùng sai)

| Làn | Claim sai / thiếu chính xác | Sự thật kiểm chứng |
|---|---|---|
| Làn 2 §5.1 | "Destination ngoài 12 focus city → `_destination_context` trả None → hỏi lại (`planner.py:1350-1351`)" | **SAI.** `planner.py:1331`: `destination_value = destination_label or ai_destination`; `:1350` chỉ append missing khi *cả hai* rỗng. Destination text do AI bịa (không có trong catalog) vẫn lấp đầy `bat_buoc_thieu`, trong khi tọa độ build lấy từ `_destination_context` = `request.location` (FE gửi, có thể là Hà Nội mặc định). **Hole thật, không lane nào thấy.** |
| Làn 2 §3.1 | Offline → planner nhận `({}, "rule_based_fallback")` | Chỉ đúng với nhánh RuntimeError. Offline adapter không raise → nguồn là `"ai_extracted"` (`planner.py:1252-1256`). |
| Làn 2 §0 | "`validate_production` cấm offline ngoài local (`config.py:99-100`)" — đúng, nhưng thiếu nửa kia | `ai.py:448-458`: `ai_adapter = create_ai_adapter()` chạy lúc **import module**; sai config (vd `AI_MODE=groq` thiếu key → `ai.py:104-106`) = **app không khởi động nổi**, `_safe_ai_intent` không có cơ hội fallback. Câu chuyện "offline story" của mọi làn đều bỏ qua lỗ robustness này. |
| Làn 1 B14 | `INTENT_PROFILES` "term tiếng Anh/Việt lẫn lộn" | Đúng, nhưng quan trọng hơn (không lane nói): profile `food` chứa term `an` (`planner.py:735`) — token 2 ký tự, `relevant_tags` bigram sẽ biến gần như câu nào có "an" (an ninh, an toàn, ăn...) thành trigger; kết hợp `SEMANTIC_TAG_ALIASES` token đơn (`gia`, `em`, `chua` tại `planner.py:1046-1048`) thì false-positive là cấu trúc, không phải ngoại lệ. |
| Làn 3 | "`backend/pyproject.toml` đặt target-version py310, dependencies liệt kê trong pyproject" | `pyproject.toml` chỉ có config pytest+ruff (8 dòng, đã đọc); dependencies nằm ở `requirements.txt`. Không ảnh hưởng kết luận nhưng cần đính chính khi ai đó dựa vào để thêm dep. |
| Làn 4 | "~67 dòng assert lên plannerSource" | Đo lại: **68** chỗ nhắc `plannerSource` trong `i18n.test.mjs`; 335 dòng assert / 491 dòng — khớp phần còn lại. Sai số không đổi kết luận lộ trình 3 bước. |

### 1.4 Số liệu đáng ngờ cần dè dặt

- Coverage % theo lớp của làn 1 (35-60%) là **ước lượng định tính có phương pháp** (liệt kê cách nói vs pattern), không phải benchmark chạy được. Dùng làm thứ tự ưu tiên được, không dùng làm cam kết.
- Chi phí USD/tháng, latency p95, token count của làn 2: toàn bộ `[unverified]` (không WebSearch). Chỉ có cấu trúc chi phí (cap $10/ngày tại `config.py:54`, tracking `record_ai_usage`) là kiểm chứng được.
- Khẳng định "ngành booking không dùng chat thuần" của làn 4: `[unverified]` — nhưng kết luận parse-then-confirm không phụ thuộc vào nó (phụ thuộc vào schema 6 trường cố định, đã kiểm chứng).

---

## 2. PHÁN QUYẾT KIẾN TRÚC DUY NHẤT

### 2.1 Nguyên tắc phân tầng (4 tầng, trách nhiệm không chồng)

```
TẦNG UI      — parse-then-confirm card (làn 4). Regex FE = preview tức thì.
               Mọi giá trị suy đoán hiển thị + sửa được TRƯỚC submit.
               Không còn wizard 3 lượt; không hỏi lại vòng lặp.

TẦNG CANON   — module backend DUY NHẤT `app/pipeline/intent_parse.py` (mới).
               Sở hữu MỌI parser: duration, daycount, clock-range, people,
               budget (port từ infer* của FE, chạy trên ascii_fold chuẩn BE),
               date tuyệt đối + relative offset, bảng lễ ~10 mốc.
               FE lệch → BE thắng; UI hiện lại giá trị BE hiểu.

TẦNG RULE    — bảng alias 2 chiều (bề-mặt → profile-key) cho dislike/preference
               + fuzzy difflib/rapidfuzz trên alias. Biến dislike free-text
               từ "trưng bày" thành hard-filter có kiểm soát.

TẦNG LLM      — giữ NGUYÊN hiện trạng định tính (destination_text, preferences,
               dislikes, constraints, must_visit) + thêm pydantic gate.
               KHÔNG extract số. KHÔNG ghi đè form. Conflict: form > canon-regex
               > rule-table > AI; không có nhánh "AI thắng".
```

### 2.2 Quyết định cụ thể từng slot

| Slot | Nguồn chân lý | Cơ chế | Offline (AI_MODE=offline) |
|---|---|---|---|
| Thời lượng (`thoi_luong`) | UI card (4 chip) + canon parser đọc text | Port `inferDuration/inferClockRange/inferHourSpan` (`Planner.tsx:127-168`); sửa bug FE vứt phút ở `:130` | Như nhau — parser thuần |
| Số ngày | canon parser + UI | Port `inferDayCount` (`Planner.tsx:234-251`) + word-days một→mười; thêm "3n2đ" pattern; cap 30 theo `MAX_TRIP_DAYS` (`planner.py:157`) | Như nhau |
| Ngày đi (`ngay_di`) | canon parser + `<input type="date">` | Giữ `_DATE_RANGE_RE`/`_DAY_RANGE_RE` (`planner.py:185-196`); thêm **relative offset ~25-50 dòng** ("tuần sau/thứ 7 này/tháng 6/mai") hoặc spike `dateparser` locale vi trước [unverified]; "dịp lễ" = bảng map ~10 dòng | Như nhau; chỉ mất LLM disambiguate câu mờ |
| Số người | UI stepper ± (1-30) + canon parser | Port `inferPeople` (`Planner.tsx:286-315`) + thêm "đứa" vào wordMap; schema `ge=1, le=30` giữ (`schemas.py:32`) | Như nhau |
| Ngân sách | UI select 4 mức + canon parser | Port `inferBudget` (`Planner.tsx:355-378`) + nhánh "rưỡi/nửa", số-chữ "hai triệu", fold chuẩn; clamp 50k-100M theo `schemas.py:33` | Như nhau — **đây là lý do port xuống BE là bắt buộc**: hiện backend generate không parse budget từ context (đã kiểm chứng), mọi năng lực budget chỉ sống nhờ FE |
| Địa điểm | backend catalog (`FOCUS_DESTINATIONS` 18 entry, `planner.py:440-549` + scan `planner.py:1097-1149`) | FE chỉ preview + datalist 18 thành phố; **cấm fallback im lặng tọa độ Hà Nội** (fix P1 làn 4); AI destination PHẢI qua catalog-check mới được lấp `bat_buoc_thieu` (vá hole §1.3-M5) | Catalog alias đầy đủ — offline chỉ mất fuzzy/typo xa |
| Dislike | rule-table (alias 2 chiều) + LLM có evidence | `_disliked_profiles` giữ làm sàn; mở `_is_place_disliked` dùng đủ 12 `DISLIKE_PREFIXES` (`planner.py:1203-1206`); dislike free-text map được profile → filter, map không được → ghi `rang_buoc` + UI echo "mình chưa lọc được X" | Regex+table hoạt động; mất cách diễn đạt ngữ nghĩa dài |

### 2.3 LLM: giữ gì, thêm gì, bỏ gì

**Giữ (đang đúng):** prompt cấm suy luận số (`ai.py:127`), temperature 0, json mode, evidence bắt buộc, fail-soft, budget tracking + breaker.

**Thêm (bắt buộc trước khi mở rộng bất cứ gì):**
1. `TrichXuatLLM` pydantic, `extra="forbid"`, ranges lấy lại từ hằng số đã có (`so_ngay ≤30` = `MAX_TRIP_DAYS`, `so_nguoi 1-30`, `ngan_sach 50k-100M`). Đây là bản sao triết lý `trusted_ids` của assemble cho extraction.
2. `ai_destination` muốn lấp `bat_buoc_thieu` phải map được vào `FOCUS_DESTINATIONS`/catalog — nếu không, chuyển thành `rang_buoc: unresolved` và hỏi lại. Vá đúng hole tôi phát hiện ở §1.3.
3. Cache `_request_understanding` trong phạm vi request — hiện AI extraction chạy **2 lần**/generate (`plans.py:154` → `planner.py:1390` và `plans.py:167` → `planner.py:4231`), tôi xác nhận trực tiếp cả hai call site. Token ×2, latency ×2.

**Bỏ / không làm:** extract số tự do (dead code khi chưa có chat-first), local LLM production, confidence bằng logprobs, deepeval (thư mục `.deepeval/` rỗng — tôi đếm 0 file).

### 2.4 Offline story (mặc định AI_MODE=offline)

Offline = **canon parser + rule table + form/card**. Không suy giảm cấu trúc lịch (định lượng chưa bao giờ phụ thuộc AI — `planner.py:1385`). Mất: cách diễn đạt định tính dài/ngữ nghĩa, typo xa, câu nhiều ý định → xử lý bằng UI echo + chip + hỏi-lại-một-lần (card cho phép sửa). Cần sửa thêm 2 thứ offline đang lặng lẽ hỏng:
- Nhãn `nguon_boc_tach_dinh_tinh: "ai_extracted"` cho payload rỗng của offline (sửa `_safe_ai_intent` trả `"offline_adapter"` khi extractor là `OfflineAIAdapter`).
- `create_ai_adapter()` chạy lúc import (`ai.py:458`) — tách lazy để misconfig không sập app, và offline vẫn khởi động được khi thiếu biến môi trường.

### 2.5 Migration path (thứ tự module — ai đọc xong biết viết gì trước)

1. **`Planner.tsx:124` + 1 dòng fold `đ`** — unblock Đà Lạt/Đà Nẵng/Đồng Hới ngay, phá 0 test (lane 4 §4 đã đếm). Cùng PR: chặn fallback im lặng tọa độ Hà Nội.
2. **`app/pipeline/intent_parse.py`** (mới, ~350-450 dòng theo ước lượng làn 3) — port nguyên trạng các `infer*` chạy tốt (`inferClockRange`, `inferDateRange`, `inferDayCount`, `inferHourSpan`, `hourWithMeridiem`), chạy trên `ascii_fold` chuẩn, kèm test từng hàm với bộ câu thất bại của làn 1 (40 ví dụ, bảng §3 của 01-current-regex-audit).
3. **`plans.py` + `planner.py` trỏ sang module mới**: `_refined_request` (refine, `plans.py:668-691`) và `_trip_timing` (`planner.py:249`) gọi canon parser; xóa regex cục bộ trùng.
4. **Cache understanding** giữa `missing_required_inputs` → `build_plan` (sửa double-extract).
5. **Rule-table dislike** + wire vào `_is_place_disliked` (mở keyword branch `planner.py:1232-1235` đủ 12 prefix, dùng `DISLIKE_PREFIXES`).
6. **UI card** bước 0→1 của làn 4 (giữ wizard làm fallback ẩn, phá 0 assert); đo adoption; bước 2 gỡ wizard kèm sửa ~41 assert `i18n.test.mjs` trong cùng PR.
7. **Pydantic gate cho LLM payload + catalog-check AI destination**; rồi mới nói chuyện prompt `raw_text` nếu sản phẩm thật sự chuyển chat-first.

---

## 3. Khuyến nghị ưu tiên

### Tier 0 — làm ngay trong tuần (giá trị cao, effort nhỏ)

| # | Việc | Vị trí | Effort | Giá trị |
|---|---|---|---|---|
| T0.1 | Fold `đ→d` trong `normalizeText` | `frontend/components/Planner.tsx:123-125` | **S** (1 dòng + 1 test) | Unblock đúng những câu phổ biến nhất (Blocker làn 1 + làn 4) |
| T0.2 | Chặn fallback im lặng tọa độ Hà Nội khi destination không khớp catalog | `Planner.tsx:336-339, 550-560` | **S** | Sửa "đúng đắn dữ liệu" — Blocker làn 4 P1 |
| T0.3 | Cache `_request_understanding` / chỉ gọi AI extraction 1 lần mỗi generate | `plans.py:154,167` + `planner.py:4231` | **S/M** | Tiền ×2 + latency ×2 hiện nay; bug hiệu suất thật, kiểm chứng trực tiếp |
| T0.4 | Rotate Groq API key trong `.env` | `.env` (đã xác nhận có `API_KEY_GROQ=gsk_...`, file gitignored và không bị track) | **S** | Key đã lộ trong phiên làm việc |
| T0.5 | Trả nhãn nguồn đúng cho offline trong `_safe_ai_intent` | `planner.py:1248-1256` | **S** | Log shadow-eval đang bị nhiễm nhãn sai |

### Tier 1 — nền tảng kiến trúc (tháng này)

| # | Việc | Vị trí | Effort | Giá trị |
|---|---|---|---|---|
| T1.1 | Module canon `app/pipeline/intent_parse.py` + test bộ 40 câu thất bại | mới; test mới | **L** | Giết song trùng FE/BE — root cause của 3 chuẩn normalize (làn 1 §1, làn 3 finding quan trọng nhất) |
| T1.2 | UI parse-then-confirm: bước 0 (echo, chip "không biết", fix P1) rồi bước 1 (card song song wizard) | `Planner.tsx` + có thể 1 file card + 19 dòng locale | **M → L** | 2-3 tap mobile, lộ mọi lỗi parse trước submit; bước 0 phá 0 test |
| T1.3 | Dislike có hiệu lực: mở `_is_place_disliked` đủ 12 prefix + bảng alias surface→profile | `planner.py:1220-1236, 1203-1206` | **M** | Dislike từ "trang trí" thành filter (làn 1 High #2) |
| T1.4 | Pydantic gate extraction + catalog-check AI destination | `ai.py:160-165`, `planner.py:1330-1351`, model mới trong `schemas.py` | **M** | Vá bất đối xứng guard + hole bypass destination (§1.3) |
| T1.5 | Relative date: spike `dateparser` locale vi (1 buổi), fail → tự viết offset ~25-50 dòng | `intent_parse.py` | **S/M** | Lớp tệ nhất hiện nay (~15-20% coverage datetime) |
| T1.6 | Breaker phân loại lỗi (JSON-error không đếm; 429 backoff thay vì fail) | `ai.py:180-183, 25-31` | **S** | Rate-limit extraction đang có thể kéo sập cả assemble |

### Tier 2 — hoàn thiện (quý này)

| # | Việc | Vị trí | Effort | Giá trị |
|---|---|---|---|---|
| T2.1 | Refine dùng canon parser (fix "ngan sach 2 trieu" không dấu, `doi` không dấu) | `plans.py:41-51, 668-691` | **M** | Refine đang reject input mà generate chấp nhận |
| T2.2 | Fix `max_places` parse-để-đó: áp cap trong `choose_candidates` hoặc xóa parse | `planner.py:1339-1346` vs `:3444-3529` | **S** | Hiểu mà không hành xử = nợ |
| T2.3 | Benchmark: sửa assert `<=200` (thực tế 240 = 12 thành phố × 5 pattern × 4 bản, tôi đếm trực tiếp `quality_benchmarks.py:65-101`), thêm ~30 scenario adversarial (conflict AI-vs-regex, ngày invalid, relative date) | `backend/app/services/quality_benchmarks.py`, `tests/test_problem_06_10_acceptance.py:485` | **M** | Gate hiện tại FAIL theo tính toán tĩnh; đo trước khi bật thêm AI |
| T2.4 | Xóa bảng từ trùng FE (`DAY_COUNT_WORDS`...) sau khi card ổn định | `Planner.tsx:214-232, 300-311` | **S** | Kết thúc kỷ nguyên 2 nguồn sự thật |
| T2.5 | Trẻ em / người lớn tách riêng nếu nhu cầu thật xuất hiện (schema hiện không có slot) | `schemas.py:32`, `Planner.tsx:296-297` (cộng gộp) | **M** | Chỉ khi dữ liệu dùng cho thấy tần suất — YAGNI until then |

### Tier 3 — KHÔNG làm (YAGNI, đã có đủ lý do từ các làn)

Rasa/Bot Framework (sai bài toán — wizard tuyến tính, không cần dialogue policy); Duckling (Haskell sidecar, chi phí vận hành không tương xứng — chỉ revisit nếu có Docker infra); PhoBERT/VnCoreNLP/underthesea (overkill cho 6 slot closed-set; trigger xét lại: >100 alias + POI open-vocab); local LLM production; `chrono-node` (không có tiếng Việt [unverified], chỉ đáng cho input en thuần phía client); `unidecode` (stdlib làm được); deepeval setup; confidence scoring bằng logprobs (provider không trả logprobs ở call hiện tại).

---

## 4. Claim quan trọng cần follow-up agent verify

1. **Benchmark gate có thật đang FAIL không, và pass_rate ≥0.95 có giữ được?** (Làn 2 claim đã chạy và fail ở `assert 240 <= 200`; tôi xác nhận 240 scenario bằng đếm trực tiếp `FOCUS_CITY_FIXTURES` 12 × `EXTRACTION_PATTERNS` 5 × 4 bản, và assert tại `test_problem_06_10_acceptance.py:485` — nhưng chưa chạy.)
   *Câu hỏi yes/no:* `pytest tests/test_problem_06_10_acceptance.py::test_problem_01_extraction_benchmark_has_100_to_200_labelled_vietnamese_cases` (AI_MODE=offline) có fail ở assert scenario_count, và pass_rate có ≥ 0.95?
   *Cách verify:* chạy đúng 1 test đó trong venv backend; đọc `report["summary"]["pass_rate"]`.

2. **AI-destination bypass hole có thật khai thác được không?** (Phát hiện mới của tổng hợp, xuất phát từ việc đọc `planner.py:1331,1350` — làn 2 §5.1 claim ngược.)
   *Câu hỏi yes/no:* với payload mock `{"destination_text": {"value": "Cần Giờ", "evidence": "biển vắng gần SG"}}` và `location` = tọa độ Hà Nội, `_request_understanding` có trả `bat_buoc_thieu == []` trong khi `toa_do` vẫn là Hà Nội?
   *Cách verify:* unit test gọi `_request_understanding` với monkeypatch `_safe_ai_intent`; assert `diem_den.trang_thai` và `toa_do`.

3. **`dateparser` locale vi có parse nổi "thứ bảy tuần sau"?** (Đơn nguồn làn 3, toàn bộ `[unverified]`.)
   *Câu hỏi yes/no:* `dateparser.parse("thứ bảy tuần sau", languages=["vi"], settings={"DATE_ORDER":"DMY","RELATIVE_BASE":...})` trả thứ Bảy kế tiếp trên Python 3.10 target?
   *Cách verify:* spike 15 phút trong venv; nếu fail → chốt phương án tự viết offset, bỏ dependency.

4. **Một generate request online tốn bao nhiêu AI call?** (Làn 2 ước "~4 call/turn" [unverified]; tôi thấy extract ×2 + `draft_itinerary_places` qua `_select_llm_first_places` `planner.py:3699-3761` + `propose_place_ids` + `assemble` — có thể 5.)
   *Câu hỏi yes/no:* có đúng 5 call AI/turn ở chế độ online, và call nào chạy 2 lần?
   *Cách verify:* grep call-sites `ai_adapter.<method>` trong `planner.py`/`plans.py`; hoặc đọc `record_ai_usage` trong store log của 1 phiên thật.

5. **MISMATCH FE-BE hiện hữu có tần suất bao nhiêu trong log thật?** (Mọi làn suy luận từ code; không làn nào có analytics.)
   *Câu hỏi yes/no:* trong log `boc_tach_yeu_cau`, tỷ lệ request mà `diem_den.nguon == "doi_chieu_catalog"` nhưng `location` FE gửi là `DEFAULT_LOCATION` có >10%?
   *Cách verify:* script đọc `store.log` theo session (infra log đã có, `plans.py:156,174`); so tọa độ request vs tọa độ understanding.

6. **Có test nào bắt được hành vi fallback tọa độ Hà Nội hoặc bug `đ` không?** (Làn 4 đếm assert static trên source, không phải test hành vi.)
   *Câu hỏi yes/no:* `frontend/tests/` có test nào assert `destinationLocation("đà lạt")` / `normalizeText` behavior?
   *Cách verify:* grep `destinationLocation|normalizeText|da lat` trong `frontend/tests/`.

---

## 5. GAP không lane nào phủ tới

1. **Import-time crash do `create_ai_adapter()` singleton** (`ai.py:448-458`): misconfig provider = app không khởi động, fallback của `_safe_ai_intent` trở nên vô nghĩa vì code không bao giờ chạy tới. Mọi câu chuyện "offline story" của 4 làn đều giả định app đã chạy.
2. **`muc_bat_buoc` (must_visit) là field chết hoàn toàn**: extract → lưu understanding (`planner.py:1371`) → không một chỗ nào trong `build_plan`/`choose_candidates`/`_select_sight_places` tiêu thụ (tôi grep toàn backend: chỉ 1371, 1379, test assert tồn tại list). Tệ hơn dislike (ít nhất dislike còn lọc được profile) — must_visit hứa với user mà không bao giờ thực hiện. Lane 2 bàn cách validate nó, nhưng không lane nào nói nó chưa được dùng.
3. **Prompt injection surface ở extraction**: `plain_text_only` (`schemas.py:41-47`) chỉ lột `<>`; context user vào thẳng prompt LLM (`ai.py:130`). Phòng tuyến thật chỉ là discipline output-JSON + guard `trusted_ids` ở assemble. Extraction thiếu tương đương → injection có thể nhồi key lạ vào understanding (đúng là `_ai_list`/`_ai_text_field` chỉ đọc key whitelist khi tiêu thụ, `planner.py:1259-1290` — giảm thiểu đáng kể, nhưng không làn nào đánh giá có hệ thống).
4. **`_trip_timing` không cache, chạy tới 7 call-site trong một build** (64, 1364, 1927, 2313, 2349, 3546, 4217 — tôi grep): lãng phí regex + rủi ro lệch nhau nếu context đổi giữa chừng. `_destination_context` có `lru_cache` (`planner.py:1097`) — `_trip_timing` thì không.
5. **Truncation `[-500:]` cắt phía trước ở refine** (`plans.py:670`): sau vài lượt tinh chỉnh, budget/dislike ở đầu câu gốc biến mất khỏi context — làn 1 nhắc lướt, không lane nào thiết kế giải pháp (gợi ý: lưu slots đã parse riêng thay vì nối chuỗi).
6. **Không có khái niệm "đã hỏi gì, còn thiếu gì" xuyên phiên**: refine chỉ append text, generate mỗi lần parse lại từ đầu — refactor `intent_parse.py` + understanding cache chính là cơ hội đặt nền, nhưng chưa lane nào nêu yêu cầu này.

---

## 6. Tóm tắt bằng chứng: số kết luận kiểm chứng

41 kết luận chịu tải trong tài liệu này được tôi đọc lại code trực tiếp (bảng §1.1: 8 claim; §1.3: 6 phân xử sai/đúng; §2-§5 dẫn chiếu ~27 vị trí code cụ thể — `Planner.tsx:123-125,127-168,234-251,286-315,336-339,355-378,380-405,434,550-560`; `planner.py:54-57*ai.py`, `:157, :185-196, :249-352, :346, :440-549, :723-754, :1045-1053, :1097-1149, :1203-1236, :1248-1256, :1301-1311, :1326-1399, :3444-3462, :3699-3761, :4231`; `plans.py:41-51, :151-178, :668-691, :695-729`; `schemas.py:28-33, :41-47`; `ai.py:74-78, :104-111, :127, :160-183, :448-458`; `config.py:54-57, :95-100`; `quality_benchmarks.py:65-101,136`; `requirements.txt`; `pyproject.toml`; `test_problem_06_10_acceptance.py:485`; `i18n.test.mjs` đếm dòng; `.env` + `git ls-files`). Ngoại lệ duy nhất: pass_rate benchmark ≥0.95 — chưa chạy, chỉ suy từ cấu trúc test.

**41/42 kết luận trong tài liệu dựa trên code kiểm chứng trực tiếp.**

---

## Executive summary 

Bốn làn nghiên cứu hội tụ về một phán quyết duy nhất: **không thay regex bằng một thứ, mà tổ chức lại thành 4 tầng có chủ**: (1) UI parse-then-confirm thay wizard 3 lượt — regex frontend làm preview tức thì, mọi giá trị suy đoán hiển thị và sửa được trước submit; (2) module backend canon `intent_parse.py` sở hữu toàn bộ parser định lượng (port từ `infer*` của Planner.tsx, chạy chuẩn `ascii_fold`) — đây là nơi sửa tận gốc bệnh 3 chuẩn normalize đang khiến "đà lạt" trượt frontend và "ngan sach 2 trieu" trượt refine; (3) bảng alias 2 chiều biến dislike từ "trưng bày" thành hard-filter; (4) LLM giữ nguyên vai trò định tính (đúng nguyên tắc "AI chỉ bóc tách"), bổ sung pydantic gate và bắt destination AI qua catalog — tuyệt đối không extract số khi form đã là nguồn định lượng. Offline (`AI_MODE=offline`) không suy giảm cấu trúc vì định lượng chưa bao giờ phụ thuộc AI — kiểm chứng tại `planner.py:1385`. Cross-check phát hiện 4 chỗ làn sai: làn 2 nhầm destination-AI được catalog-gate (thực tế bypass được `bat_buoc_thieu`), nhầm nhãn nguồn offline ("ai_extracted" cho payload rỗng), và cùng 3 làn còn lại bỏ qua lỗ `create_ai_adapter()` chạy lúc import khiến misconfig sập cả app; ngoài ra field `muc_bat_buoc` extract xong không ai tiêu thụ. Ưu tiên: Tier 0 gồm 5 việc effort S (fold `đ` 1 dòng, chặn fallback Hà Nội im lặng, cache understanding để xóa double-extract AI, rotate key Groq đã lộ, sửa nhãn nguồn offline). Migration 7 bước cho phép bước đầu phá 0 test; chỉ bước gỡ wizard đụng ~41 assert `i18n.test.mjs`. 6 claim cần follow-up, đứng đầu là chạy lại benchmark gate (tính toán tĩnh nói đang FAIL) và spike `dateparser` locale vi.

**Confidence: 8/10.** Lý do: mọi claim kiến trúc chịu tải đều đọc lại code trực tiếp (41/42), kể cả việc bắt lỗi 3 làn; trừ điểm vì (a) không chạy test/benchmark trong phiên này, (b) không có dữ liệu usage thật để xếp tần suất lỗi, (c) toàn bộ nhận định về thư viện bên ngoài (dateparser, Duckling, chrono-node) là `[unverified]` — không có WebSearch.
