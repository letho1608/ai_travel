# 06 — Follow-up Verification: 6 claim chịu tải từ synthesis

**Làn:** xác minh độc lập, bằng chứng cục bộ (pytest chạy thật + grep + đọc code). Không WebSearch, không sửa code.
**Thời gian chạy:** pytest đơn 2.36s (giới hạn 120s tuân thủ).

---

## Bảng verdict

| # | Claim | Verdict | Bằng chứng khóa |
|---|---|---|---|
| 1 | Benchmark gate fail vì 240 > 200 | **verified** | chạy pytest thật; `assert 240 <= 200` tại `tests/test_problem_06_10_acceptance.py:485` |
| 2 | Extraction chạy 2 lần/request | **verified** | `plans.py:154` + `plans.py:167` → `planner.py:1390` và `planner.py:4231`; `_request_understanding` không cache |
| 3 | Offline trả `{}` nhưng dán nhãn `ai_extracted` | **verified** | `ai.py:77-78` + `planner.py:1252-1256` |
| 4 | `must_visit`/`muc_bat_buoc` là field chết | **verified** | grep toàn `backend/app`: chỉ 1 nơi extract, 1 nơi ghi metadata |
| 5 | Singleton import-time → app không khởi động khi misconfig | **verified** (kèm điều kiện chính xác) | `ai.py:448-458` + `planner.py:43` + import order `main.py:16` trước `main.py:20` |
| 6 | `normalizeText` không fold `đ` → "đi đà lạt" fail, gửi tọa độ Hà Nội | **verified** | `Planner.tsx:123-125` vs pattern `:24` và fallback `:338` |

---

## Claim 1 — Benchmark gate: verified

Chạy trong `D:\Code\ai_travel\backend` với `AI_MODE=offline`:

```
python -m pytest tests/test_problem_06_10_acceptance.py::test_problem_01_extraction_benchmark_has_100_to_200_labelled_vietnamese_cases -q
```

Output (2.36s):

```
>       assert 100 <= report["scenario_count"] <= 200
E       assert 240 <= 200
FAILED tests/test_problem_06_10_acceptance.py::test_problem_01_extraction_benchmark_has_100_to_200_labelled_vietnamese_cases
1 failed in 2.36s
```

Số 240 khớp đếm tĩnh của synthesis (12 thành phố × 5 pattern × 4 bản, `quality_benchmarks.py:65-101`). Test chết ở assert count, **chưa kịp** đo `pass_rate` — câu hỏi phụ "pass_rate ≥ 0.95?" vẫn unverifiable qua test này; cần nới assert về `<=240` hoặc đọc `report` trực tiếp để trả lời.

## Claim 2 — Extraction chạy 2 lần: verified

Chuỗi gọi trong một happy-path request (khi `missing_fields` rỗng):

1. `app/routers/plans.py:154` — `required = await to_thread(missing_required_inputs, payload)`
2. → `planner.py:1389-1390` — `missing_required_inputs` gọi `_request_understanding(request)` → **AI extraction lần 1**
3. `app/routers/plans.py:167` — `plan = await to_thread(build_plan, payload)`
4. → `planner.py:4231` — `input_understanding = _request_understanding(request)` → **AI extraction lần 2**

Cache check: `def _request_understanding` (`planner.py:1326`) **không** có decorator cache. Grep `lru_cache|memoize` trong `planner.py`: chỉ 2 chỗ — `planner.py:1097` (`_destination_context`) và `:1996` (hàm khác) — không trùm `_request_understanding`. `plans.py` và `ai.py`: 0 cache. Verified đúng cơ chế synthesis mô tả.

Lưu ý phạm vi: trên nhánh thiếu input (`missing_fields` đầy), response trả sớm tại `plans.py:166` nên chỉ 1 lần. "×2" áp dụng cho nhánh build-thành-công — đúng nhánh tốn tiền.

## Claim 3 — Offline `{}` gắn nhãn `ai_extracted`: verified

Cơ chế chính xác:

- `OfflineAIAdapter.extract_request_intent` (`ai.py:77-78`) trả `{}` và **không raise**.
- `_safe_ai_intent` (`planner.py:1248-1256`): extractor callable → vào `try`; `payload = {}` không raise → dòng 1256: `return payload if isinstance(payload, dict) else {}, "ai_extracted"` → trả `({}, "ai_extracted")`.
- Nhánh `rule_based_fallback` chỉ kích hoạt khi extractor không callable (`:1250-1251`) hoặc raise `RuntimeError` (`:1254-1255`) — offline adapter không rơi vào nhánh nào.

Hệ quả: understanding ở chế độ offline tự khai "đã bóc tách bằng AI" với payload rỗng, làm bẩn log `boc_tach_yeu_cau` (`plans.py:156,174`) đúng như synthesis §1.2-M4 và đính chính ở §1.3 (làn 2 nhầm `rule_based_fallback`).

## Claim 4 — `must_visit`/`muc_bat_buoc` field chết: verified

Grep `must_visit|bat_buoc` toàn `backend/app` (loại `bat_buoc_thieu` — đó là key điều khiển khác, được tiêu thụ tại `planner.py:1391`):

| Vị trí | Vai trò |
|---|---|
| `ai.py:136` | schema prompt yêu cầu LLM trả `must_visit` |
| `planner.py:1371` | extract: `"muc_bat_buoc": _dedupe_field_values(_ai_list(ai_payload, "must_visit"))` |
| `planner.py:1379` | liệt kê `muc_bat_buoc` dưới nhãn nguồn `ai_extracted` (metadata) |
| `tests/test_pipeline.py:45` | `assert isinstance(understood["muc_bat_buoc"], list)` — chỉ assert tồn tại |

Trong `build_plan` (`planner.py:4213-4252` đọc trực tiếp), `choose_candidates`, `_select_sight_places`: **0 chỗ đọc `muc_bat_buoc`**. Field được LLM bóc tách, lưu vào understanding, không ai tiêu thụ downstream. Verified — "hứa với user mà không bao giờ thực hiện".

## Claim 5 — Singleton import-time: verified, kèm điều kiện chính xác

Chuỗi sự kiện:

- `ai.py:458` — `ai_adapter = create_ai_adapter()` chạy **lúc import module**.
- `planner.py:43` — `from app.services.ai import ai_adapter`.
- `main.py:16` — import routers (→ planner → ai), **trước** `main.py:20` — `settings.validate_production()`.

Điều kiện app chết lúc import (raise trong `create_ai_adapter` / constructor):

| Cấu hình | Kết quả |
|---|---|
| `AI_MODE=groq` hoặc `deepseek`, thiếu `API_KEY_*` | `OpenAICompatibleAIAdapter.__init__` raise `RuntimeError` (`ai.py:104-106`) → sập import |
| `AI_MODE=offline`, `APP_ENV != local` | `create_ai_adapter` raise `"AI_MODE=offline is forbidden outside local mode"` (`ai.py:450-451`) → sập import |
| `AI_MODE` giá trị lạ | raise `"AI_MODE không được hỗ trợ"` (`ai.py:455`) → sập import |
| `AI_MODE=offline` + `APP_ENV=local` (mặc định `config.py:56-57`) | khởi động bình thường |
| key hợp lệ | adapter tạo thành công; lỗi runtime sau đó được `_safe_ai_intent` bắt (`planner.py:1254`) → graceful |

Điểm đáng chú ý: `validate_production` (`config.py:95-100`, chặn offline/thiếu key ngoài local) tồn tại nhưng chạy tại `main.py:20` — **sau** dòng import đã gây sập ở `main.py:16`. Trong môi trường non-local misconfig, import-crash xảy ra trước cả validation. Vậy synthesis đúng: fallback của `_safe_ai_intent` vô nghĩa trong mọi cấu hình mà adapter không tạo được, vì app không bao giờ chạy tới đó.

## Claim 6 — FE fold `đ`: verified (1 dòng bằng chứng)

`normalizeText` (`Planner.tsx:123-125`): `NFD` + strip `[\u0300-\u036f]` + lowercase — `đ` (U+0111, letter, không phải combining mark) sống sót → `"đi đà lạt"` → `"đi đa lat"`; pattern `/\b(da lat|dalat|lam dong)\b/` (`Planner.tsx:24`) không khớp → `hasDestination` false (`:331-334`), `destinationLocation` (`:336-339`) rơi về `DEFAULT_LOCATION = { lat: 21.0285, lng: 105.8542 }` (Hà Nội, `:13`).

---

## Điều gì thay đổi trong synthesis nếu có claim lật (~200 từ)

Không claim nào bị lật — cả 6 verdict là **verified**, nên synthesis §4/§5 giữ nguyên và được nâng cấp bằng chứng từ "đọc code + đếm tĩnh" sang "đã chạy/grep xác nhận". Điểm duy nhất cần đính chính nhẹ là claim 1: test gate fail ở **assert count**, không đo được pass_rate — synthesis §1.4 đã ghi ngoại lệ này, nay xác nhận thêm rằng pass_rate ≥0.95 vẫn là câu hỏi mở cho tới khi nới assert (đề xuất T2.3 giữ nguyên, thêm 1 việc phụ: đọc `report["summary"]["pass_rate"]` trực tiếp trước khi sửa ngưỡng). Claim 5 có bổ sung sắc hơn đáng nêu vào synthesis: import-crash xảy ra tại `main.py:16` **trước** `validate_production` tại `main.py:20` — tức cơ chế validation sản xuất không phải tuyến phòng thủ cho lỗi này; fix lazy-singleton (synthesis §2.4) là tuyến duy nhất. Claim 2 cần ghi chú phạm vi: double-extract chỉ nhân 2 trên nhánh build-thành-công, nhánh thiếu input chỉ 1 lần — không thay đổi ưu tiên T0.3. Các khuyến nghị Tier 0/1 giữ nguyên thứ tự.
