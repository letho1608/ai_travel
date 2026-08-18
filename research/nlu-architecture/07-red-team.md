# 07 — RED TEAM: bẻ gãy synthesis 4 tầng

**Làn:** adversarial review (6/6). Địch thủ của `05-synthesis.md`; dữ liệu = 05 + 06 + code thật + test chạy thật trong phiên này. Không sửa code. Mọi trích dẫn dòng đã đọc trực tiếp; phát hiện mới đánh dấu **[mới]**.

**Phương pháp:** đọc đầy đủ 05/06; sau đó tự chạy và grep thay vì tin số của synthesis: chạy pytest benchmark gate (fail đúng như 06), chạy trực tiếp `run_extraction_benchmark` (pass_rate), gọi `_request_understanding` với payload thật, đếm assert `i18n.test.mjs` bằng regex, đọc hết `Planner.tsx`, `i18n.test.mjs`, `schemas.py`, `conftest.py`, các site `_trip_timing`/`build_plan`, `choose_candidates`.

---

## Bảng verdict

| # | Mức | Phát hiện | Chỗ synthesis bị bẻ |
|---|---|---|---|
| B1 | **Blocker** | T0.1 + T0.2 **không thể** "phá 0 test": `i18n.test.mjs:426` assert `/const DEFAULT_LOCATION/`, `:428` assert chữ ký `destinationLocation`, `:429` assert đúng dòng `location: destinationLocation(composedContext)` — chặn fallback Hà Nội đúng chỗ thì 3 assert vỡ ngay; fold `đ` nếu đổi tên/hàm cũng đụng source-assert. | §2.5 bước 1, §3 Tier 0 ("phá 0 test", "lane 4 đã đếm") |
| B2 | **Blocker** | T0.3 "cache `_request_understanding`, effort S" sai cơ chế: hàm nhận `PlanRequest` (pydantic, không hashable) → `lru_cache` không dùng được; cách đúng = đổi chữ ký `build_plan(request, understanding=None)` và compute 1 lần tại `plans.py:154` — lan sang 3 call-site `quality_benchmarks.py:565,603,655` + 57 site test gọi `build_plan`. Effort thật **M**, không phải S. | Tier 0 T0.3, §2.3 item 3 |
| B3 | **Blocker** | Benchmark gate **đang đỏ CI ngay lúc này** (tôi chạy lại: `assert 240 <= 200` FAILED, 2.34s). CI chạy `pytest -v` toàn bộ mỗi push (`.github/workflows/ci.yml`). Synthesis xếp fix này ở **Tier 2 (quý này)** — nghĩa là toàn bộ Tier 0/1 PR không merge-able nếu CI bắt xanh. Thứ tự phải đảo: nới assert/fix fixture là việc **đầu tiên**, không phải T2.3. | Tier table: T2.3 phải thành T0.0 |
| H1 | **High** | T0.2 "chặn fallback Hà Nội, effort S" bất khả thi ở tầng FE một mình: `schemas.py:30` bắt buộc `location: Coordinate` (có bound `ge/le`), FE **không thể bỏ trường này khỏi payload**. "Chặn" thật = hoặc hỏi lại user (UI mới) hoặc backend nhận `location: Optional` — tức thay schema + flow. Ngoài ra FE chỉ biết 18 pattern trong khi backend khớp cả catalog 30k+ place (`planner.py:1105-1149`): FE chặn sẽ **strict hơn backend**, nhốt user gõ điểm đến hợp lệ (vd "Phú Yên") mà backend vốn resolve được. Effort thật **M–L**, kèm quyết định thiết kế chưa có trong synthesis. | Tier 0 T0.2 |
| H2 | **High** | Framing "Blocker unblock ngay" của T0.1 bị phóng đại về giá trị: backend **đã** fold `đ` (`text_utils.py:3-10`) và scan lại context — tôi gọi `_request_understanding` thật với context chứa điểm đến: kết quả `diem_den = Đà Lạt`, `bat_buoc_thieu = []`, tọa độ build đúng (`planner.py:1152-1165` derive từ text). Tác hại thật còn lại của bug FE = wizard **hỏi lại thừa** + tọa độ sai trong payload (bị backend ghi đè bằng text) + log lệch. Vẫn đáng fix (High), nhưng "dữ liệu sai xuống backend" không xảy ra như §1.1-claim 1 mô tả ("Hà Nội mặc định" chỉ là anchor tạm, đã có comment `planner.py:1153-1158` thừa nhận và xử lý). | §1.1 claim 1, giá trị T0.1 |
| H3 | **High** | Xóa wizard (migration bước 6, "sửa ~41 assert") đụng contract lớn hơn số đã nêu: tôi đếm **67 assert lên plannerSource**, ~25 cái lock thẳng cấu trúc wizard (`needsDuration/pendingContext/answerDestination/hasDestination/chip`); thêm test "complete planner contract" bắt đủ **44 key × 19 locale = 836 chuỗi dịch** (`i18n-core.ts:8`, `i18n.test.mjs:115-123`). Con số "~41" của synthesis không có cơ sở từ phép đếm nào tôi tái lập được; chi phí thật của bước 2 là M×(việc dịch 19 locale), không phải sửa assert. | §2.5 bước 6, T1.2 effort |
| H4 | **High** | Shared blind spot cả 4 lane + synthesis: **không có bằng chứng nào** cho (a) tỷ lệ user gõ không dấu, (b) drop-rate khi thêm confirm card vào funnel. Synthesis thừa nhận `[unverified]` cho claim ngành booking nhưng vẫn chốt "parse-then-confirm thắng" dựa trên taps. Bằng chứng ngược tồn tại trong chính repo: funnel hiện tại đã 3–4 lượt hỏi và sản phẩm sống; thêm 1 màn hình xác nhận = thêm 1 điểm rơi, và SSE **chưa có UX** cho nhánh `missing_required_inputs` (`plans.py:157-165` phát `error` event; FE `api.ts:65-71` ném Error hiển thị như lỗi chung chung, không render card). Card "sửa trước submit" cần đường render mới hoàn toàn — chưa ai thiết kế. | §2.1 TẦNG UI, M3, M2 |
| M1 | **Medium** | "1 dòng fold `đ`" không đủ: FE có **2** bản normalize (`Planner.tsx:46` `isUncertainReply` và `:123` `normalizeText`). Sửa 123 bỏ sót 46 → lệch hành vi detect "chưa biết". Synthesis không thấy bản thứ hai. | §3 T0.1 |
| M2 | **Medium** | "FE preview, BE phán quyết, xung đột → BE thắng, UI hiện lại" — cơ chế hồi đáp không tồn tại: stream hiện tại chỉ phát `status`/`result` (`plans.py:150-176`); muốn card hiện lại giá trị BE hiểu phải thêm understanding vào payload result (FE phải render) hoặc thêm endpoint parse — cả hai đều chưa tính vào effort T1.2. Trách nhiệm consistency nếu không có kênh hồi đáp = **không ai**, đúng câu hỏi đặt ra. | §2.1, T1.2 |
| M3 | **Medium** | T1.3 "mở đủ 12 `DISLIKE_PREFIXES`" có rủi ro false-positive cấu trúc: `planner.py:1203-1206` chứa `"so"`, `"ghe"`, `"di ung voi"` — substring match `f"{prefix} {term}"` sẽ ăn "so" (số/sợ), "ghe" (ghé/ghe thuyền). Tôi xác nhận `INTENT_PROFILES["food"]` chứa token `'an'` 2 ký tự (chạy thật) + `relevant_tags` tách cả token đơn → dislike-profile match trên "an" là hit thường trực. Synthesis chỉ nói đúng hướng, thiếu bước "đo precision từng prefix trước khi bật hard-filter". | T1.3, §1.3 hàng Làn 1 B14 |
| M4 | **Medium** | T0.5 đổi `ai_extracted` → `offline_adapter` đụng logic `xuat_xu` tại `planner.py:1380` (key gắn điều kiện `extraction_source == "ai_extracted"`); mọi dashboard/script đọc log `boc_tach_yeu_cau` phải audit. Synthesis gọi đây là fix log thuần là thiếu bước "tìm consumer của nhãn". | T0.5 |
| L1 | **Low** | Tin tốt synthesis chưa biết: chạy trực tiếp benchmark (bỏ qua assert count) cho `pass_rate = 1.0`, `hallucination_failures = 0` trên 240 scenario, `AI_MODE=offline`. Nỗi lo "pass_rate ≥0.95 có giữ được" (follow-up 1) **đã có câu trả lời: giữ được**. T2.3 thu gọn còn việc nới assert. | §4 item 1, T2.3 |
| L2 | **Low** | Số liệu "18 entry FOCUS_DESTINATIONS" khớp đếm thật (18 key, `planner.py:440-549`), khớp 18 pattern FE. Claim này đứng. | — |

---

## 1. Claim chịu tải nào vẫn chưa kiểm chứng / shared blind spot?

**Điểm mù lớn nhất: "parse-then-confirm thắng" là phán quyết UX không có dữ liệu.** Cả 5 làn suy luận từ cấu trúc code (schema 6 trường cố định → phải confirm), không làn nào có analytics. Hai câu hỏi cụ thể:

1. **User VN gõ không dấu chiếm đa số?** Không ai đo. Trớ trêu: nếu đa số gõ không dấu thì bug `đ` của FE **ít gây hại hơn** synthesis tưởng (pattern FE vốn cho chuỗi không dấu), và lớp `ascii_fold` BE mới là chuẩn đúng. Ngược lại nếu đa số gõ có dấu thì FE-fold mới khẩn. Ưu tiên T0.1 đang treo trên dữ liệu không tồn tại. Đáng nói hơn, runtime chứng minh **backend đã tự cứu** context có `đ` (H2) — giá trị T0.1 chủ yếu là UX wizard, không phải "đúng đắn dữ liệu".
2. **Confirm card tăng funnel → drop rate tăng: có bằng chứng ngược không?** Không — không lane nào tìm. Câu hỏi không thể trả lời bằng code; synthesis cần gắn cờ "decision cần đo" thay vì chốt thắng tuyệt đối. Manh mối ngược trong repo: wizard hiện tại đã là funnel 3–4 lượt (sản phẩm sống), và luồng thiếu input hiện phát SSE error mà FE xử lý kém (ném Error chung) — hạ tầng confirm **chưa tồn tại**, phải xây mới, trái giọng "chỉ cần bọc thành endpoint".

**Shared blind spot thứ hai (cả 4 lane + synthesis): giả định "app đã chạy và FE/BE đồng thuận catalog".** 05 bắt được import-crash ở §5.1 — khen đúng; nhưng lớp dưới còn nguyên: FE hardcode 18 pattern trong khi BE khớp full PLACES (mục H1), không lane nào đối chiếu hai bảng tên.

**Claim chịu tải chưa kiểm chứng còn lại:** (i) F1 của relative-date regex vs dateparser (synthesis tự nhận `[unverified]`); (ii) tỷ lệ mismatch FE–BE trong log thật (follow-up 5, đúng là vẫn mở); (iii) số AI call/turn = 5 (follow-up 4, vẫn là suy luận từ grep, chưa chạy).

## 2. Tiêu chí chấp nhận Tier 0 cho phép làm qua loa ở đâu?

- **T0.1 "1 dòng + 1 test, phá 0 test" — sai sự thật.** `i18n.test.mjs` assert tĩnh lên nguồn Planner.tsx (B1): bất kỳ implementer nào làm đúng 1 dòng fold trong `normalizeText` thì test vẫn xanh, OK — nhưng tiêu chí "phá 0 test" tạo ảo tưởng có thể sửa nhanh; đến bước *chặn fallback cùng PR* là vỡ 3 assert (426/428/429), vì chặn fallback = thay/bỏ `?? DEFAULT_LOCATION`. Ai làm qua loa sẽ chọn cách **không đụng fallback** để giữ xanh CI → T0.1 ship, T0.2 im lặng chết. Fix tiêu chí: tách PR, hoặc cập nhật trước 3 assert có chủ đích.
- **T0.2 không có tiêu chí chấp nhận hành vi.** "Chặn fallback im lặng" — nhưng chặn rồi thì chuyện gì xảy ra? Không định nghĩa. Ba kết cục khả dĩ: (a) disable nút submit, (b) hỏi lại destination, (c) gửi thiếu field (bị schema chặn, H1). Mỗi cái là sản phẩm khác nhau. Tiêu chí cho phép qua loa: người làm chọn (a) vì rẻ → dead-end UX worse hơn bug gốc.
- **T0.3 "S/M" không đi kèm thiết kế cache** → implementer sẽ thử `lru_cache`, gặp `unhashable PlanRequest`, rồi chọn cache toàn cục theo `context` string (sai: 2 request khác `so_nguoi` cùng context sẽ ăn cache) hoặc bỏ cuộc. Tiêu chí đúng phải nêu: compute 1 lần tại router, truyền xuống `build_plan` (B2).
- **T0.5 đổi nhãn nhưng không giữ schema `xuat_xu` nhất quán** (M4) — đổi 1 dòng, log "đúng", dashboard im lặng gãy.

## 3. Blind spot của phán quyết: consistency FE preview vs BE canonical

Synthesis §2.1 nói "FE lệch → BE thắng; UI hiện lại giá trị BE hiểu" — **đúng nguyên tắc, thiếu cơ chế**. Kiểm chứng code:

- Kênh hiện có duy nhất từ BE về FE giữa lúc generate là SSE `status` (2 giá trị) và `result` (plan hoàn chỉnh) — `plans.py:150-176`, `api.ts:26-85`. Understanding (`dau_vao_da_hieu`) đi **vào plan** ở cuối (`plans.py:173-174`), tức user chỉ thấy giá trị BE hiểu **sau khi đã build xong**, không "trước submit" như tầng UI hứa. Không có `POST /api/plan/parse`; `missing_required_inputs` trả understanding nhưng nhánh thiếu input render bằng... error event (H4). Vậy câu "ai chịu trách nhiệm consistency" hiện có đáp án thật: **không ai** — cho tới khi có endpoint parse + render card từ understanding. Synthesis cần bổ việc này vào T1.2 (effort vì thế là L, không M).
- **Test contract có bị migration bỏ quên?** Có, một nửa. Synthesis biết ~41 assert sẽ đụng, nhưng bỏ quên hai lớp: (1) test "complete planner contract" nhân **44 key × 19 locale** — gỡ wizard bỏ `dayPrompt/destinationPrompt/...` là đụng 836 chuỗi dịch đang được assert existence (H3); (2) 25 assert khóa cấu trúc wizard không chỉ là con số cần "sửa" mà là **đặc tả hành vi** (ví dụ `:424` `if (!hasDestination(requestContext)) {` bắt buộc vòng hỏi lại) — gỡ wizard là cố tình phá đặc tả, cần viết lại thành đặc tả card, không phải xóa.

## 4. Rủi ro regression của Tier 0

**T0.2 là item duy nhất thay đổi hành vi user-visible trong Tier 0.** Rà soát phụ thuộc:

- Test FE: không test nào assert hành vi fallback (chỉ 3 source-assert B1) — thay đổi không bị test chặn, **nguy hiểm vì không lưới an toàn**.
- Prod path: `generatePlan` gọi `destinationLocation` với mọi input (`Planner.tsx:460`) — chặn fallback không có đường thay thế = mọi input ngoài 18 pattern không generate được, kể cả input backend vốn phục vụ tốt (runtime xác minh catalog-scan đúng). Regression thuần cho tập ngoài-18.
- Wizard path: `answerDestination` (`:550-560`) nhận mọi text; chặn fallback đúng chỗ này kẹt vòng lặp nếu không thông báo.

Kết luận: T0.2 đúng hướng nhưng thiếu điều kiện để là Tier 0 effort S; điều kiện tiên quyết là datalist/catalog hoặc endpoint parse (H1, H4).

## 5. Effort S/M/L có lạc quan không?

Đọc code rồi phán lại:

| Item | Synthesis | Phán red team | Lý do |
|---|---|---|---|
| T0.1 fold `đ` | S | **M** | 2 bản normalize phải đồng bộ (M1); test tĩnh khóa nguồn; +1 test hành vi chưa tồn tại (không test nào assert `normalizeText`, đã xác nhận follow-up 6 của chính synthesis). |
| T0.2 chặn fallback | S | **M–L** | Schema bắt buộc `location`; FE/BE catalog lệch; cần thiết kế UI (H1). |
| T0.3 cache understanding | S/M | **M** | Không cache-able bằng decorator; đổi chữ ký lan `quality_benchmarks` + 57 site test (B2). |
| T0.5 nhãn offline | S | S | Giữ — kèm bước grep consumer. |
| T1.1 canon module | L | L | Khớp. |
| T1.2 UI card | M→L | **L** | Endpoint parse/render hồi đáp chưa có (M2), 836 chuỗi locale nếu đụng key (H3), SSE error UX chưa có. |
| T1.3 dislike hard-filter | M | M | Giữ — thêm bước đo precision 12 prefix (M3). |
| T2.3 benchmark fix | M | **S nhưng phải dời lên Tier 0** | Đã chạy: chỉ cần nới assert; pass_rate = 1.0 rồi (L1). Nhưng gate đỏ đang chặn CI (B3). |

Item thực ra L: **T0.2 và T1.2**.

---

## Khuyến nghị fix cho SYNTHESIS (không phải codebase)

1. **Đảo thứ tự:** thêm **T0.0 — nới assert benchmark (S)** lên đầu bảng Tier 0; ghi rõ CI đang đỏ (bằng chứng chạy trong phiên red-team). Giữ pass_rate 1.0 đã đo vào §1.4.
2. **Sửa T0.1:** ghi nhận backend đã fold `đ` và tự cứu tọa độ (bằng chứng runtime mục H2) → hạ khung giá trị từ "Blocker dữ liệu" xuống "High UX (wizard hỏi lại thừa + payload lệch)"; ghi thêm bản normalize thứ hai `Planner.tsx:46` vào phạm vi; tiêu chí chấp nhận = "2 chuẩn FE trùng `ascii_fold`" chứ không phải "1 dòng".
3. **Sửa T0.2:** tách khỏi PR T0.1; bổ nhiệm thiết kế bắt buộc trước code (một trong: datalist catalog / hỏi lại / endpoint parse); ghi rõ schema `location` bắt buộc và bất đối xứng catalog FE (18) vs BE (full scan) — chặn FE-only gây regression tập ngoài-18.
4. **Sửa T0.3:** xóa chữ "cache"; viết lại thành "compute understanding 1 lần tại router và truyền vào `build_plan` (đổi chữ ký, giữ default để không vỡ 3 site benchmark)"; effort M; phạm vi kèm `quality_benchmarks.py:565,603,655`.
5. **Sửa migration bước 1/6:** bỏ claim "phá 0 test"; viết tường minh 3 source-assert `i18n.test.mjs:426-429` phải được cập nhật *trong cùng PR có chủ đích*; bước 6 bổ sung chi phí **44 key × 19 locale** và việc viết lại 25 assert wizard thành đặc tả card (con số 67 assert plannerSource tổng — đo trong phiên này — thay cho "~41").
6. **Bổ T1.2:** thêm hạng mục "kênh hồi đáp giá trị BE → UI" (parse endpoint hoặc understanding trong SSE result) và chỉ định rõ owner consistency = endpoint/module canon; nếu chưa làm hạng mục này thì câu "BE thắng, UI hiện lại" chỉ là nguyện vọng.
7. **Gắn cờ quyết định UX:** mục mới "điều kiện đo trước khi gỡ wizard": drop-rate funnel hiện tại, tỷ lệ input không dấu (đọc log `boc_tach_yeu_cau` hiện có — hạ tầng log thừa khả năng, không cần analytics mới). Thiếu hai số này, migration bước 6 không được bật đèn xanh.
8. **T1.3:** thêm bước đo precision từng prefix trong `DISLIKE_PREFIXES` trước khi mở đủ 12 (token đơn `an`/`so`/`ghe` đã chứng minh FP cấu trúc).

## Kết luận

**Ground-truth tally (thiết lập mới trong phiên red-team):**
1. `i18n.test.mjs:426/428/429` khóa `DEFAULT_LOCATION` + `destinationLocation` → "phá 0 test" sai.
2. 67 assert plannerSource; ~25 khóa cấu trúc wizard; planner contract = 44 key × 19 locale.
3. Benchmark: `assert 240 <= 200` FAILED thật (2.34s); report trực tiếp: `pass_rate 1.0`, `hallucination_failures 0`, 240 scenario.
4. Runtime: context có alias catalog → backend trả `_destination_context` đúng (Đà Lạt + tọa độ, `bat_buoc_thieu=[]`) dù FE gửi tọa độ Hà Nội → bug `đ` FE nhỏ hơn framing Blocker.
5. `_request_understanding` không hashable-key → "cache S" bất khả thi; chỉ có cách đổi chữ ký.
6. `schemas.py:30` bắt buộc `location` → FE không thể chặn fallback bằng cách bỏ field.
7. FE có 2 bản normalize (`:46`, `:123`), synthesis chỉ biết 1.
8. Nhãn offline `ai_extracted` + token `'an'` trong profile `food`: xác nhận runtime.
9. SSE không có kênh trả understanding về FE giữa luồng → "BE thắng, UI hiện lại" chưa có cơ chế.
10. 18 entry FOCUS_DESTINATIONS đếm đúng; khớp 18 pattern FE.

**Confidence synthesis an toàn để ship làm khuyến nghị: 5/10.** Hướng 4 tầng và các phát hiện kỹ thuật đứng vững qua đối chiếu độc lập; nhưng Tier 0 có 2 item khai tiêu chí sai sự thật khi đối chiếu test (B1), 1 item bất khả thi theo thiết kế nêu (B2), 1 item bị đảo thứ tự so với CI thực đỏ (B3), và item hành vi duy nhất (T0.2) thiếu thiết kế, có đường regression xác định được. Sau khi áp 8 fix → đáng giá ~8/10.
