# 02 — LLM Structured Extraction: Khả thi, Thiết kế, Chi phí, Rủi ro

**Làn:** LLM structured extraction (chuyên gia 2/4)
**Repo:** `D:\Code\ai_travel` — FastAPI backend + Next.js frontend, tiếng Việt là ngôn ngữ chính.
**Kết luận nhanh:** **Đáng làm, nhưng chỉ đáng làm một nửa.** LLM extract tốt các trường *định tính* (destination, dislikes, preferences, constraints, must_visit) — và tầng này đã chạy thật, đã có benchmark. LLM extract *định lượng* (ngay_di, so_ngay, so_nguoi, ngan_sach) là **bổ sung biên lợi nhuận thấp hơn chi phí**, vì định lượng hiện nay lấy từ form (`form_chat`) và regex `_trip_timing`, không ai gõ số tự do trong khi UI là form. Đề xuất: giữ LLM ở định tính + làm rõ `relative date → ISO`, thêm pydantic validation + regex cross-check + conflict resolution theo bằng chứng; **KHÔNG** để LLM ghi đè so_nguoi/ngan_sach đã nhập từ form, chỉ dùng LLM khi trường đó null (chat-only flow tương lai) hoặc cho flow refine.

---

## 0. Sự kiện nền kiểm chứng bằng code

- `PlanRequest` (backend/app/schemas.py:28) gồm: `context` (max 500 ký tự, L29), `location: Coordinate` (L30), `thoi_luong: Literal["vai_gio","nua_ngay","ca_ngay","nhieu_ngay"]` (L31), `so_nguoi` (default 2, 1–30, L32), `ngan_sach` (default 1.000.000, 50k–100M VND, L33), `ngay_di: date | None` (L34), `ngon_ngu` (L38). Định lượng đã có validation chặt ở tầng schema.
- `extract_request_intent` (backend/app/services/ai.py:114) gọi Groq/DeepSeek với `response_format={"type":"json_object"}` (L150), `temperature: 0.0` (L151), `max_tokens: 700` (L152), timeout 10s/connect 2s bằng httpx **sync** client (L110), retry 2 lần (L140), circuit breaker 3 lỗi/5 phút → mở 120s (L12–L35).
- Prompt hiện tại **cấm** suy luận số liệu: `"Do not invent missing facts. Do not infer people, budget or trip duration unless the text says it."` (ai.py:127). Output mẫu chỉ có trường định tính: destination_text, preferences, dislikes, constraints, must_visit, mỗi trường kèm `evidence` (ai.py:131–137).
- Planner tiêu thụ intent trong `_request_understanding` (backend/app/pipeline/planner.py:1326): định lượng ghi nguồn `form_chat` (L1341–1343, 1364–1367), định tính merge AI + rule (L1368–1371). Định tuyến gọi AI nằm trong `_safe_ai_intent` (planner.py:1248): lỗi → trả `{}` + nguồn `rule_based_fallback` (L1254–1255), **không chết pipeline**. Đây chính là contract fallback offline đúng nghĩa: `OfflineAIAdapter.extract_request_intent` trả `{}` (ai.py:77–78) và planner coi AI là optional.
- Ngày giờ/số ngày parse từ context bằng regex thuần trong `_trip_timing` (planner.py:249) với `_DATE_RANGE_RE` (L185), `_DAY_RANGE_RE` (L193), `_HOUR_SPAN_RE` (L168), `_HOUR_COMPACT_RE` (L172), `_CLOCK_RANGE_RE` (L158), `MAX_TRIP_DAYS = 30` (L157), clamp 0.75h–12h (L264), roll-forward ngày quá khứ (L311–313).
- Refine qua chat chỉ dùng regex: `PEOPLE_INTENT` (routers/plans.py:47–51), budget regex (plans.py:675–683), keyword cheaper/less travel/cafe (plans.py:684–690). **Không có AI ở refine.**
- Ngân sách chi phí: `daily_ai_budget_usd=10`, `monthly_ai_budget_usd=300` (config.py:54–55), `reserve_cost` fail-closed (services/store.py:40–48, services/postgres_store.py:41), `record_ai_usage` log token/USD từng call (store.py:53).
- `.env` hiện tại: `AI_MODE=groq`, `TEN_MODEL_GROQ=llama-3.3-70b-versatile`, `deepseek-v4-flash` (config.py:262–265).
- **Bảo mật (High, ngoài lề nhưng bắt buộc nói):** `.env` chứa API key Groq thật (dòng `API_KEY_GROQ=gsk_...`). `.gitignore` loại `.env` và whitelist `.env.example` — không bị commit — nhưng key nằm trong working copy đã lộ trong phiên nghiên cứu này; **nên revoke/rotate key ngay**.

---

## 1. Tầng LLM hiện có gì / thiếu gì — và prompt mới

### 1.1 Đủ

| Năng lực | Bằng chứng | Ghi chú |
|---|---|---|
| JSON mode | ai.py:150 | Groq lẫn DeepSeek hỗ trợ `json_object` qua OpenAI-compatible endpoint [unverified — không WebSearch; đúng với llama-3.3 và deepseek-chat theo kiến thức model] |
| Temperature 0 + retry 2 | ai.py:140, 151 | Phù hợp extraction |
| Finish_reason guard | ai.py:158 | Chặn truncation |
| Evidence buộc trong prompt | ai.py:128 | Tốt cho debug/benchmark |
| Fail-soft vào rule fallback | planner.py:1248–1256 | Contract đúng |
| Budget tracking + breaker | ai.py:169–177, 178–183 | |

### 1.2 Thiếu (xếp hạng)

| # | Thiếu | Mức | Bằng chứng |
|---|---|---|---|
| T1 | **Không có pydantic validation payload**; `json.loads(content)` rồi trả dict sống, planner tự lọc mềm (`_ai_text_field` planner.py:1259, `_ai_list` planner.py:1271) — không có range check, không có ngày. LLM trả `"value": 5000` hay `ngay_di: "2007-01-01"` thì không có lớp nào từ chối có thông báo; hiện chỉ bị *bỏ qua ngầm* vì key không được đọc. | High | ai.py:163–165, planner.py:1330–1331 |
| T2 | Prompt cấm số liệu (L127) nhưng UI form đã có sẵn số — mâu thuẫn này **là chủ đích** (ghi chú planner.py:1385: "Định lượng lấy từ form"). Nếu muốn LLM extract định lượng, phải đổi prompt + thêm schema + thêm validation + thêm conflict rule. | High | ai.py:127, planner.py:1377–1385 |
| T3 | Không có `logprobs`/confidence. Chỉ có thể ước lượng confidence bằng heuristics (evidence substring match, regex cross-check). | Medium | ai.py:166–168 chỉ đọc usage |
| T4 | Sync httpx trong endpoint FastAPI. Hiện được bọc bởi `to_thread` (plans.py:154) nên không chặn event loop — nhưng retry ×2 × timeout 10s = **tối đa ~20s trước SSE error**; UI phải chịu khoảng chờ đó. (Chi tiết §6.) | Medium | ai.py:107–111, 140; plans.py:122, 154, 177–178 |
| T5 | Không giới hạn key lạ: payload dict trả về được nhét thẳng vào `dau_vao_da_hieu` (planner.py:1384 chỉ dùng key đọc). Không sao, nhưng nên whitelist key ở pydantic. | Low | planner.py:1256 |
| T6 | `.deepeval/` tồn tại **rỗng** (0 files) — không có infrastructure eval nào của deepeval hoạt động. Benchmark thật là `quality_benchmarks.run_extraction_benchmark` (quality_benchmarks.py:136). | Note | kiểm kê trực tiếp: `.deepeval` 0 files |
| T7 | Không có latency telemetry (p50/p95) cho AI call; `record_ai_usage` chỉ log token/USD. | Medium | store.py:53 |

### 1.3 Prompt mới đề xuất (chỉ đáng cho date-normalization)

Thay vì cho phép LLM suy luận số tự do, đề xuất prompt hẹp, **an toàn tuyệt đối**: giữ nguyên các trường định tính hiện có, thêm `ngay_di_iso` chỉ được phép khi văn bản *nói rõ*, và bắt buộc LLM không tự quy đổi tương đối khi thiếu mốc ("thứ Bảy tuần này" không có today anchor thì không được suy; chỉ quy đổi khi server truyền `ngay_hom_nay` vào prompt):

```json
{
  "yeu_cau": "Extract travel intent from user text in {language}. Extract ONLY what the text states verbatim or via direct paraphrase. Never guess. Numbers (people, budget, days) may be extracted ONLY as raw_text copied verbatim from the text; never converted or inferred. Dates: if the text names a calendar date or a relative date resolvable from ngay_hom_nay supplied below, return ISO in {ngay_hom_nay} timezone; otherwise null. Return strict JSON matching json_mau.",
  "ngay_hom_nay": "2026-08-18",
  "max_days": 30,
  "json_mau": {
    "destination_text": {"value": "string|null", "evidence": "string|null"},
    "ngay_di_iso": {"value": "YYYY-MM-DD|null", "evidence": "verbatim quote|null", "do_tin_cay": false},
    "so_ngay_raw": {"raw_text": "verbatim|null", "evidence": "verbatim|null"},
    "so_nguoi_raw": {"raw_text": "verbatim|null", "evidence": "verbatim|null"},
    "ngan_sach_raw": {"raw_text": "verbatim|null", "evidence": "verbatim|null"},
    "preferences": [{"value": "string", "evidence": "string"}],
    "dislikes": [{"value": "string", "evidence": "string"}],
    "constraints": [{"value": "string", "evidence": "string"}],
    "must_visit": [{"value": "string", "evidence": "string"}]
  }
}
```

Nguyên tắc thiết kế: số ở dạng `raw_text` để regex/server convert (đúng nơi có thẩm quyền về múi giờ, định dạng `k/trieu`, clamp) — LLM chỉ tìm span văn bản. Đây là pattern "LLM locates, code converts", hạn chế hallucination số học. `max_tokens 700` của hiện tại vẫn đủ (output template trên ~350–450 token khi đầy đủ). [Token count ước lượng, unverified về phía tokenizer của model cụ thể.]

**Đánh giá thành thật:** prompt này chỉ đáng triển khai nếu và chỉ nếu frontend có flow chat tự do không dùng form (hiện không có — generate endpoint ăn `PlanRequest` nguyên khối, plans.py:121–122). Nếu không, phần `raw_*` là dead code.

---

## 2. Schema extract đề xuất + validation + ngưỡng tin cậy + conflict resolution

### 2.1 Pydantic model

```python
class TrichXuatLLM(BaseModel):
    model_config = ConfigDict(extra="forbid")  # chặn key lạ (T5)

    destination_text: str | None = Field(default=None, max_length=120)
    ngay_di: date | None = None
    so_ngay: int | None = Field(default=None, ge=1, le=30)        # MAX_TRIP_DAYS planner.py:157
    so_nguoi: int | None = Field(default=None, ge=1, le=30)        # PlanRequest.so_nguoi schema.py:32
    ngan_sach: int | None = Field(default=None, ge=50_000, le=100_000_000)  # schema.py:33
    dislikes: list[str] = Field(default_factory=list, max_length=12, max_item_length=80)     # khớp _ai_list planner.py:1276
    preferences: list[str] = Field(default_factory=list, max_length=12, max_item_length=80)
    constraints: list[str] = Field(default_factory=list, max_length=12, max_item_length=80)
    must_visit: list[str] = Field(default_factory=list, max_length=10, max_item_length=80)
    evidence: dict[str, str] = Field(default_factory=dict, max_length=20)
```

Validation rules từng field (dùng lại hằng số đã có, không phát minh mới):

- `ngay_di`: `@field_validator` — không được trước `date.today() - 1 ngày` (dung sai múi giờ; tương tự logic FlightSearchRequest schemas.py:119), không quá `today + 365 ngày` (trip planner, không phải đặt vé 2030; chặn ca "2007"), và phải parse được từ evidence có chứa token ngày. Ngày LLM trả mà evidence không chứa mẫu số/ngày → loại bỏ, ghi nguồn `ai_rejected_no_evidence`.
- `so_ngay`: 1–30 (MAX_TRIP_DAYS planner.py:157). LLM trả 365 → bị chặn bởi pydantic, không cần hậu xử lý.
- `so_nguoi`: 1–30 đúng PlanRequest (schemas.py:32). Chặn "5000 người".
- `ngan_sach`: 50k–100M VND (schemas.py:33). **Âm bị chặn bởi `ge`**. Nếu LLM trả raw text "2 triệu", chuyển đổi ở server, không tin LLM làm toán: `2 * 1_000_000`.
- `dislikes/preferences/...`: mỗi item ≤ 80 ký tự (hiện `_ai_list` cắt 80, planner.py:1285), list ≤ 12 (L1276), giữ giới hạn hiện có.

**Điểm mấu chốt:** pydantic là lớp phòng thủ thứ hai; lớp thứ nhất là prompt không cho convert số. Dùng cả hai — prompt chặn 95%, pydantic chặn 5% còn lại với thông báo lỗi đọc được, thay vì crash hoặc im lặng.

### 2.2 Ngưỡng tin cậy và conflict resolution

Không dùng điểm confidence (không có logprobs, T3). Dùng **luật theo bằng chứng** — nhất quán với triết lý dự án ("AI chỉ bóc tách intent", planner.py:1385):

| Trường | Tin ngay từ AI | Cần regex cross-check | Luật conflict |
|---|---|---|---|
| `destination_text` | Không — hiện đã có `_destination_context` đối chiếu catalog trước (planner.py:1328, 1330–1331: `destination_label or ai_destination`). | Có: phải map vào `FOCUS_DESTINATIONS`/catalog nếu không sẽ bị hỏi lại. | Catalog thắng. AI chỉ điền chỗ trống. Giữ nguyên — đang đúng. |
| `ngay_di` | Không bao giờ tin ngay. | Có: regex `_DATE_RANGE_RE`/`_DAY_RANGE_RE` (planner.py:185–195) chạy song song. | AI vs regex khớp → nhận. Lệch ≤ 1 ngày → nhận regex, log `conflict_date_minor`. Lệch hẳn → nhận giá trị từ **form** nếu có (request.ngay_di), nếu không thì `missing` + hỏi lại. Không có nhánh "AI thắng". |
| `so_ngay` | Không. | Có: `labeled_days` regex (planner.py:346). | Regex/form `thoi_luong` thắng. AI chỉ đề xuất chuyển `thoi_luong` enum (vd "2 ngày" → `nhieu_ngay`), không ghi đè số ngày cụ thể. |
| `so_nguoi` | Không. | Có: `PEOPLE_INTENT` (plans.py:47) chạy cùng text. | Form > regex > AI. Form đã là input có chủ đích của người dùng; ghi đè bằng suy luận = regression. |
| `ngan_sach` | Không. | Có: budget regex refine (plans.py:675–683) đã tồn tại và đã có bug tiềm ẩn (không phân biệt "dưới 1 triệu" vs "khoảng 1 triệu" — regex `dưới|tối đa` nhưng `khoảng/giá` cũng match — Medium, nhưng thuộc làn 1). | Form > regex > AI. |
| `dislikes/preferences/constraints/must_visit` | **Có** — đây là nơi LLM thực sự hơn regex (phủ nhận mềm "đừng leo núi nhiều", "lịch nhẹ cho trẻ em"). | Optional: rule-based `_disliked_profiles` (planner.py:1209) dùng làm sanity floor, không phải veto. | Union + dedupe (hiện đã có `_dedupe_field_values` planner.py:1314). AI và regex cùng tìm → merge, không conflict. |

**Ngưỡng định lượng đề xuất:**
- Dislike từ AI: yêu cầu `evidence` chứa một trong các marker phủ định (`khong thich`, `tranh`, `so`, `ghet`, `khong muon`, `di ung` — danh sách đang có ở planner.py:1203–1206) **hoặc** chấp nhận nếu model trả sau temperature 0. Nếu không → đưa vào `rang_buoc` thay vì `khong_thich` (dislike là hard filter `_is_place_disliked` planner.py:1220 — sai 1 dislike = mất cả nhóm địa điểm, nên bar phải cao hơn preference).
- Preference từ AI: nhận luôn nếu evidence không rỗng; preference chỉ là boost điểm, không loại địa điểm.
- `must_visit`: phải qua map catalog như destination, nếu không map được thì chuyển thành `rang_buoc` kèm `trang_thai: "unresolved"` — không được tự bịa địa điểm (nguyên tắc dự án, trùng với `trusted_ids` guard ai.py:56–57).

---

## 3. Offline degradation (AI_MODE=offline mặc định)

### 3.1 Hệ thống sống thế nào khi không có AI

Sống tốt, bằng bằng chứng:
- `create_ai_adapter` trả `OfflineAIAdapter` khi `AI_MODE=offline` (ai.py:449–452); `extract_request_intent` trả `{}` (ai.py:77–78); planner nhận `({}, "rule_based_fallback")` (planner.py:1255) và đi tiếp.
- `validate_production` **cấm** offline ngoài local (config.py:99–100, ai.py:450–451) — tức offline là chế độ dev/demo, production phải có provider. Đây là quyết định có chủ đích, không phải thiếu sót.
- Offline vẫn có: destination matching (catalog alias planner.py:1083–1125), dislike regex (planner.py:1301–1311), preference tag (`INTENT_PROFILES`, planner.py:1293–1298), date/day parsing (planner.py:249–348), budget/people từ form (schemas.py:32–33).

### 3.2 "Offline = dumb wizard" vs "offline = regex cũ" — chấp nhận được không

Câu hỏi này đặt sai tiền đề vì offline **hiện đã là regex cũ** (rule_based_fallback), không phải dumb wizard. So sánh UX thực:

| Năng lực | Offline (regex+form) | Online (AI+regex) | Mất gì khi offline |
|---|---|---|---|
| Định lượng | Form bắt buộc nhập | Form bắt buộc nhập | Không mất gì |
| Destination | Catalog alias, ~12 thành phố focus (FOCUS_CITY_FIXTURES quality_benchmarks.py:65–78; FOCUS_DESTINATIONS planner) | + AI gợi text | Phủ tên lạ/ngoài alias |
| Dislike | Regex prefix (planner.py:1203–1206) | + diễn đạt tự nhiên | Câu phức ("đừng cho tụi nhỏ leo trèo") |
| Preference | Tag profile | + câu dài | Câu dài, tiếng lóng |

**Kết luận:** offline = regex cũ là đánh đổi chấp nhận được vì định lượng — thứ quyết định cấu trúc lịch trình — không phụ thuộc AI. LLM chỉ là chất lượng định tính. Điều này đúng với kiến trúc "AI chỉ bóc tách intent, không sinh địa điểm ngoài catalog": phần đáng tin nhất (địa điểm) chưa bao giờ rời khỏi regex+catalog.

Rủi ro UX duy nhất đáng ghi nhận (Medium): thông báo error `missing_required_input` khi destination không match (plans.py:157–165) — offline sẽ hỏi lại nhiều hơn online. Chấp nhận; hỏi lại tốt hơn bịa.

### 3.3 Chạy LLM local?

Nêu, gắn unverified đầy đủ:
- **Ollama** chạy llama-3.1-8b/Qwen2.5-7B trên máy dev, trỏ `AI_BASE_URL=http://localhost:11434/v1` — Ollama expose OpenAI-compatible endpoint, adapter `OpenAICompatibleAIAdapter` hiện tại về nguyên tắc dùng được ngay vì chỉ phụ thuộc base_url + api_key (ai.py:107–111; key có thể đặt dummy vì Ollama bỏ qua). [Unverified: chưa kiểm tra trong repo này; `response_format json_object` support tùy model Ollama; 7B model cho extraction tiếng Việt sẽ kém 70B đáng kể — kỳ vọng F1 định tính giảm 10–20 điểm %, không có số đo.]
- **llama.cpp server** `--jinja` với template JSON [unverified tương tự].
- Đánh đổi: offline-LLM phá vỡ nguyên lý `AI_MODE=offline` cấm ngoài local (config.py:99) vì nó vẫn là AI call; cần thêm chế độ thứ 4 `local_llm` nếu làm. Chi phí infra = RAM 8–16GB, latency 1–4s/request trên CPU/giải pháp yếu — **không đáng cho production**; chỉ đáng cho CI eval nếu muốn benchmark offline. Khuyến nghị: bỏ qua cho tới khi có nhu cầu cụ thể (YAGNI).

---

## 4. Chi phí [unverified — không có WebSearch; số liệu từ kiến thức model, cần kiểm chứng giá thực tế trước khi chốt]

### 4.1 Token/request

Prompt hiện tại: ~350 token template + context ≤ 500 ký tự ≈ 200–350 token tiếng Việt (tiếng Việt tốn token hơn tiếng Anh ~1.3–1.6×) [unverified]. Output với json_mau 5 trường + evidence: 250–500 token, trần max_tokens 700 (ai.py:152). Prompt mới đề xuất §1.3 thêm ~120 token input.

Ước tính 1 request extraction: **~600 input + ~400 output token**. Nếu 1 chat turn = 4 call AI (generate: intent + propose + draft + assemble — hiện thực generate gọi extract_request_intent trong build_plan qua missing_required_inputs, rồi thêm propose/draft/assemble tùy pipeline), extraction chỉ chiếm ~1/4 chi phí AI toàn turn. Bảng dưới tính riêng **extraction call**:

### 4.2 Bảng USD/tháng — extraction call duy nhất

Config hiện tại: `ai_input_usd_per_million=0.14`, `ai_output_usd_per_million=0.28` (config.py:62–63) — giá này gần với DeepSeek-chat [unverified]. Groq free tier: miễn phí nhưng giới hạn request/phút (historically ~30 req/min, ~14.4k token/min, ~500k token/day cho llama-3.3-70b) [unverified, thay đổi thường xuyên].

| Traffic extract/ngày | Groq free/tháng | DeepSeek ($0.14/$0.28)/tháng |
|---|---|---|
| 100 req/ngày | $0 (rate limit) | ~$0.15–0.30 |
| 1.000 req/ngày | $0 nếu dưới token cap; khả năng vượt token/day cap giờ cao điểm → cần paid [$0.04–0.10 per M] [unverified] | ~$1.90–3.20 |
| 10.000 req/ngày | **Không khả thi free tier** — vượt cả rate lẫn token cap; Groq paid ~$0.05–0.09/M [unverified] → $12–25 | ~$19–32 |

So với cap ngân sách dự án 10 USD/ngày, 300 USD/tháng (config.py:54–55, .env): extraction đơn thuần không bao giờ chạm cap ngay cả 10k req/ngày DeepSeek. **Tiền không phải bottleneck; rate limit mới là**, và hiện tại không có queue/backoff khi Groq trả 429 — chỉ có breaker đếm lỗi (ai.py:25–31). 429 liên tục sẽ mở breaker cho mọi AI call, tắt cả assemble (tính năng copy chính) — đó là coupling cần lưu ý (Medium, §6).

---

## 5. Hallucination / Guardrail

### 5.1 Chặn giá trị vô lý

Tuyến phòng thủ đã nêu ở §2.1. Cụ thể từng ca:

| Ca | Chặn ở đâu | Cơ chế |
|---|---|---|
| `ngay_di = 2007-01-01` | pydantic `>= today-1` | Loại + log; không hỏi lại, dùng form/hỏi lại như missing |
| `so_nguoi = 5000` | pydantic `le=30` | Loại; fallback form default 2 |
| `ngan_sach = -500000` | pydantic `ge=50_000` | Loại |
| `so_ngay = 365` | pydantic `le=30` = MAX_TRIP_DAYS | Loại; dùng `thoi_luong` |
| Dislike bịa (không có trong text) | evidence marker check §2.2 | Hạ xuống `rang_buoc` |
| `must_visit` bịa địa điểm không có trong catalog | map catalog bắt buộc, nếu không → `unresolved` | Cùng triết lý `trusted_ids` |
| Destination ngoài 12 focus city | `_destination_context` trả None → hỏi lại | planner.py:1350–1351, hiện đang hoạt động |

### 5.2 So sánh với guard `trusted_ids` trong `assemble`

`_apply_copy` (ai.py:54–71) là guard **tuyệt đối**: AI chỉ được sửa `tieu_de/tom_tat/mo_ta/luu_y`, key `mo_ta_theo_id` phải `<= trusted_ids` nếu không raise ValueError (ai.py:56–57). Extraction hiện tại **không có guard tương đương** — payload dict sống đi thẳng vào planner. Đây là điểm bất đối xứng quan trọng nhất của làn này: dự án đã chứng minh cách làm đúng (whitelist + raise) ở assemble, nhưng chưa áp vào extract. pydantic + evidence check §2 là phiên bản `trusted_ids` cho extraction. **High — phải làm trước khi bật bất kỳ extraction định lượng nào.**

Nguyên tắc dự án "AI chỉ bóc tách intent, KHÔNG sinh địa điểm ngoài catalog" được bảo toàn ở đề xuất này: không trường nào trong schema cho phép AI trả địa điểm không có trong catalog.

---

## 6. Rủi ro vận hành

### 6.1 CircuitBreaker đủ chưa

Chưa đủ cho một số ca (xếp hạng):

- **Không phân biệt loại lỗi** (High cho coupling đã nêu §4): 429 rate limit, 500 provider, JSON parse error đều gọi `breaker.record_failure()` (ai.py:182). Rate limit của extraction có thể kéo breaker, tắt luôn assemble — call giá trị cao nhất. Cần phân biệt: JSON error → không đếm breaker (đó là lỗi prompt/model, không phải hạ tầng); 429 → backoff thay vì fail.
- **Không có backoff/jitter** (Medium): retry ngay 2 lần liên tiếp (ai.py:140) khi provider quá tải = đổ thêm dầu.
- **Shared breaker toàn cục** (Medium): 1 breaker cho mọi phương thức (extract/propose/draft/assemble); chấp nhận được ở quy mô hiện tại nhưng sai khi scale đa provider.
- **Mở 120s cố định** (Note): đủ cho downtime ngắn; không có half-open thăm dò dần, chỉ thăm dò 1 request sau 120s — đơn giản, chấp nhận.

### 6.2 Latency p95 và flow SSE

Đọc code kiểm chứng:
- `generate` endpoint là async, gọi `await to_thread(missing_required_inputs, payload)` (plans.py:154) → `_request_understanding` → `_safe_ai_intent` → sync httpx 10s timeout (ai.py:110) × 2 retry = **worst case ~20s trước khi SSE gửi error event** (plans.py:177–178). SSE gửi `status` event trước (plans.py:151–152) nên client không treo hoàn toàn, nhưng không có progress event nào trong 20s đó.
- p95 của Groq llama-3.3-70b: ~0.5–2s [unverified]; DeepSeek-flash: ~1–3s [unverified]. Retry khi timeout → p99 worst có thể chạm 20s.
- `build_plan` gọi lại `_request_understanding` lần hai (planner.py:4231) sau khi `missing_required_inputs` đã gọi một lần (plans.py:154) — **AI extraction call chạy 2 lần cho mỗi generate request** trong flow online. Lãng phí token + latency ~1–3s. Should cache trong request scope. **High — bug hiệu suất thật, đọc thấy trực tiếp: plans.py:154 rồi planner.py:4231 cùng một request.**
- `refine` endpoint (plans.py:694) là sync def, không to_thread — hiện không gọi AI nên không sao, nhưng nếu thêm AI vào refine sẽ chặn event loop (Medium tiềm năng).

### 6.3 httpx sync chi tiết

Đã kiểm chứng ai.py:107–111: `httpx.Client` (sync), `httpx.Timeout(10, connect=2)`. Không phải bug vì endpoint đã bọc to_thread — nhưng `ai_adapter` là module-level singleton (ai.py:458) được tạo lúc import, nên mọi test phải monkeypatch client. Ghi nhận Note cho testability.

---

## 7. Infrastructure eval hiện có / còn thiếu

### 7.1 Có sẵn (đã kiểm chứng)

- `run_extraction_benchmark` (quality_benchmarks.py:136–180): 12 thành phố × 5 pattern × 4 bản = **240 scenario** (104:108, EXTRACTION_PATTERNS L95–101). Đo: destination exact match, duration, people, budget, semantic tag hit, `no_destination_hallucination` (L156). Gate trong test: `pass_rate >= 0.95`, `hallucination_failures == 0` (test_problem_06_10_acceptance.py:487–488). **Chạy thực tế offline mode: 240 scenario, gate hiện tại FAIL vì assertion `100 <= scenario_count <= 200` đã cũ — 240 > 200** (test_problem_06_10_acceptance.py:485; chạy trực tiếp: `FAILED ... assert 240 <= 200`). Đây là pre-existing test debt, không phải do hướng LLM mới, nhưng phải biết khi thêm trường mới.
- `test_ai.py` (65 dòng): test `_apply_copy` guard (L14–29), breaker status (L32–37), prompt locale/provenance cho assemble (L40–65). Pattern monkeypatch client tốt, dùng lại được.
- `ExtractionScenario` dataclass (quality_benchmarks.py:42–50) đã có `expected_people`, `expected_budget`, `expected_duration` — **infra đo định lượng đã tồn tại**, nhưng hiện người/budget lấy từ form nên check luôn pass; khi thêm AI extract định lượng thì thêm `expected_ngay_di` và check nguồn.
- `store.log(session_id, "boc_tach_yeu_cau", understanding)` (plans.py:156, 174) — đã ghi extraction vào log, đủ nguyên liệu đo online (shadow eval).
- `.deepeval/`: **rỗng, không dùng được** (đếm trực tiếp: 0 files). Nếu team muốn deepeval, phải setup lại từ đầu — thuộc làn khác đánh giá.

### 7.2 Còn thiếu

1. **Không có scenario conflict** (AI vs regex bất đồng) trong benchmark — cần thêm ~30 case adversarial: "ngày 33 tháng 2" (invalid date), "5 triệu VND cho 3 người 2 ngày" (đủ 3 trường định lượng), "đi cuối tuần này" (relative date, cần today anchor), "không quá 8 điểm dừng" (max_places regex L1339).
2. **Không có latency/cost assertion** trong test AI — breaker test chỉ kiểm tra trạng thái (test_ai.py:32).
3. **Không có negative hallucination cho số**: chưa test nào assert AI không trả `so_nguoi=5000` hay ngày 2007 — vì schema chưa có các trường đó. Viết cùng lúc với schema §2.
4. **Offline A/B**: không có test assert offline extraction cho cùng 240 scenario vẫn pass ≥ 0.90 (baseline so sánh khi bật AI).
5. **Shadow logging chưa khai thác**: `boc_tach_yeu_cau` log có sẵn nhưng không có pipeline so log vs benchmark — cần script đơn giản đọc log, chạy lại `run_extraction_benchmark` format.

---

## 8. Bảng tổng hợp findings

| # | Finding | Mức | Bằng chứng |
|---|---|---|---|
| F1 | Extraction call chạy **2 lần**/generate request (missing_required_inputs + build_plan) — tiền ×2, latency ×2 | **High** | plans.py:154, planner.py:4231, planner.py:1329 |
| F2 | Không có pydantic validation payload extraction; guard `trusted_ids` chỉ có ở assemble, không có ở extract — bất đối xứng bảo mật | **High** | ai.py:163–165, ai.py:56–57, planner.py:1259–1271 |
| F3 | Prompt cấm số liệu (L127) là **chủ đích đúng** vì form đã có định lượng; đổi prompt để AI suy luận số tự do = regression về an toàn | **High** (design) | ai.py:127, planner.py:1377–1385 |
| F4 | Breaker không phân biệt 429/JSON error → rate limit extraction kéo chết assemble | **High** | ai.py:180–183 |
| F5 | `.env` chứa Groq API key thật trong working copy — rotate | **High** (security) | .env, .gitignore whitelist |
| F6 | Test debt pre-existing: benchmark 240 scenario, assertion cũ `<=200` đang FAIL | **Medium** | test_problem_06_10_acceptance.py:485, chạy trực tiếp |
| F7 | Không có backoff/jitter; worst case 20s trước SSE error event | **Medium** | ai.py:140, 110; plans.py:151–178 |
| F8 | Refine flow không dùng AI, chỉ regex — đây là nơi LLM extraction đáng tiền nhất (chat tự do, không form) nhưng chưa có | **Medium** | plans.py:668–691 |
| F9 | Không có logprobs/confidence; confidence phải xây bằng heuristics evidence | **Medium** | ai.py:166 |
| F10 | `.deepeval/` rỗng — không có eval infrastructure như tên gọi | **Note** | đếm trực tiếp |
| F11 | Offline = regex cũ là đánh đổi chấp nhận được; định lượng sống bằng form+regex, AI chỉ là chất lượng định tính | **Note** | planner.py:1248–1256, ai.py:77 |
| F12 | Local LLM (Ollama) khả thi về mặt wiring (AI_BASE_URL) nhưng không đáng cho production [unverified] | **Note** | ai.py:107–111 |

---

## 9. Kết luận và khuyến nghị theo thứ tự

1. **Không bật LLM extract định lượng vội.** Lý do kinh tế học: form đã bắt buộc nhập so_nguoi/ngan_sach; regex đã parse ngày/số ngày. LLM extract số tự do chỉ có giá trị khi frontend chuyển sang chat-first không form — chưa có trong codebase hiện tại.
2. **Đáng làm ngay:** (a) cache extraction result trong request scope sửa F1; (b) pydantic validation payload sửa F2; (c) breaker phân biệt lỗi sửa F4. Ba việc này nhỏ, thuần kỹ thuật, không đổi prompt.
3. **Đáng làm nếu có chat-first flow:** prompt §1.3 với `raw_text` pattern (LLM locates, server converts), conflict resolution §2.2 (form > regex > AI, không có nhánh AI thắng), và thêm 30 scenario adversarial vào extraction benchmark.
4. **Không đáng:** local LLM production, deepeval setup (chờ làn 3/4 đánh giá), confidence scoring bằng logprobs (chưa có logprobs, YAGNI).
