# 04 — KIẾN TRÚC UX TƯƠNG TÁC: Nhập liệu & Xác nhận trong Trip Planner

Làn nghiên cứu: **UX tương tác** (form vs chat vs hybrid, parse-then-confirm).
Dữ liệu: đọc code thật tại `frontend/components/Planner.tsx` (720 dòng), `frontend/app/page.tsx`, `frontend/tests/i18n.test.mjs`, `frontend/lib/i18n-core.ts`, `frontend/components/LocaleProvider.tsx` (19 locale), `frontend/app/globals.css`. Mọi nhận định về ngành bên ngoài repo đều gắn `[unverified]`.

---

## 1. Hiện trạng: "chat" nhưng thực chất là form ẩn trong transcript

### 1.1 Cơ chế thật trong code

`Planner.tsx` không phải hội thoại. Nó là một máy trạng thái 3 bước điều khiển bởi 3 cờ boolean (`needsDuration`, `needsDestination`, `needsPeople` — Planner.tsx:69-71):

1. User gõ câu đầu tiên → `submit()` (Planner.tsx:584) chạy `inferDuration()`. Nếu regex thất bại → hỏi lại thời lượng (`durationQuestion()`), kèm 4 chip.
2. `answerDuration()` kiểm tra `hasDestination()` qua **18 regex thành phố** (`DESTINATION_LOCATIONS`, Planner.tsx:14-33). Thiếu → hỏi địa điểm, kèm 8 chip.
3. `continueOrAskPeople()` chạy `inferPeople()`. Thiếu → hỏi số người ("Bạn đi mấy người?").
4. Đủ → `generatePlan()` POST lên `/api/plan/generate` với schema cố định: `context`, `location`, `thoi_luong`, `so_nguoi`, `ngan_sach`, `ngay_di`, `ma_phien`, `ngon_ngu`, `nonce` (Planner.tsx:458-468).

Vậy NLU hiện tại = hàm `infer*` thuần regex (inferDuration, inferClockRange, inferHourSpan, inferDateRange, inferDayCount, inferPeople, inferBudget — tổng ~200 dòng) đã viết sẵn. Backend chỉ nhận **6 trường cấu trúc**. Đây là dữ kiện quyết định toàn bộ thiết kế UX phía dưới.

### 1.2 Điểm đau cụ thể (đọc từ code, không suy đoán)

**P1 — Blocker: địa điểm không nhận dạng được thì bị im lặng gán tọa độ Hà Nội.**
`answerDestination()` (Planner.tsx:550) chấp nhận **mọi** text không rỗng làm "địa điểm" mà không validate; nhưng `destinationLocation()` (Planner.tsx:336) chỉ khớp 18 regex, còn lại rơi về `DEFAULT_LOCATION` = Hà Nội (21.0285, 105.8542). User gõ "Quy Nhơn biển đảo 2 người" ở bước hỏi địa điểm vẫn được gửi đi với tọa độ… Hà Nội nếu regex lệch (ví dụ gõ "quy nhơn", "quy nhon" — regex chỉ match `quy nhon`). Không có bất kỳ tín hiệu nào cho user biết hệ thống hiểu sai.

**P2 — High: vòng lặp hỏi lại không có lối thoát.**
`answerDuration()` (Planner.tsx:517-533): parse fail và không phải câu "tùy/không biết" → hỏi lại đúng câu hỏi cũ, vô hạn. `answerPeople()` (Planner.tsx:573-577) tương tự. User không thấy "vì sao câu trả lời bị từ chối", không có nút skip, không có gợi ý định dạng nào ngoài dòng chữ dài trong `durationQuestion()`. Trên mobile, mỗi lần hỏi lại là một lần bàn phím phải hoạt động.

**P3 — High: im lặng trích xuất mà không cho thấy.**
`inferBudget()` trả về null thì mặc định `1000000` (Planner.tsx:434); `inferDateRange()` âm thầm đẻ ra `ngay_di` (Planner.tsx:435); `composeRequestContext()` tự nối thêm text thời lượng/số người vào ý tưởng (Planner.tsx:380-405). User không bao giờ thấy 3 giá trị này trước khi submit — và không sửa được. Sai một chỗ thì phải đợi cả plan được sinh ra (tới 180s timeout) mới phát hiện.

**P4 — Medium: chip chỉ phủ một phần.**
Bước địa điểm có 8 chip (Hà Nội…TP.HCM) nhưng catalog backend có 18 thành phố. Bước số người không có chip/stepper nào — user buộc phải gõ bàn phím, dù đáp án là một số nguyên 1-30 (trường hợp điển hình nhất cho `<input type="number">` hoặc stepper ±).

**P5 — Medium: string cứng tiếng Việt/Anh giữa component "19 locale".**
`peopleQuestion()` (Planner.tsx:327-329), câu mặc định khi "không biết" ở `answerDuration()` (Planner.tsx:524-526) và `answerPeople()` (Planner.tsx:569-571) là ternary `vi`/`en` cứng — 17 locale còn lại nhận text sai ngôn ngữ ngay giữa trang đã set `lang`. Test i18n không bắt được lỗi này (chỉ assert key tồn tại, không assert nguồn string).

**P6 — Medium: landing chip không tự submit.**
`promptPlanner()` (Planner.tsx:37) chỉ điền text vào input và focus; user vẫn phải bấm gửi. Trên mobile đó là 1 tap thừa, và `popularCities` + tiêu đề nhiều section trong `page.tsx` là tiếng Việt cứng bất chấp locale (page.tsx:48-55, 119, 149, 171, 198, 216).

**P7 — Low: không có chỉ báo tiến trình.**
Không có "bước 2/3", không có echo "mình hiểu là…". `messages[]` chỉ phình ra; user không biết đã cung cấp được gì.

---

## 2. So sánh 4 pattern thu thập intent

Ngữ cảnh đo: 6 trường (ý tưởng, thời lượng, địa điểm, số người, ngày đi, ngân sách), mobile-first, user VN. "Taps" = số chạm vào UI element (không đếm phím gõ — phím gõ được ghi riêng vì chi phí bàn phím mobile cao hơn tap nhiều lần).

| Tiêu chí | (a) Form-first thuần | (b) Chat thuần | (c) Hybrid widget trong bubble | (d) Parse-then-confirm |
|---|---|---|---|---|
| Taps hoàn tất (best case) | ~7-9 | 1 | ~6-7 | **2-3** |
| Taps (repair case) | 0 (không có parse) | 6-10 | 4-6 | +1 mỗi trường sai |
| Gõ phím | Trung bình (3-4 trường) | Nhiều (mỗi lượt hội thoại) | Ít | **Ít nhất** (1 câu duy nhất) |
| Lộ lỗi parse | Không tồn tại | Ẩn hoàn toàn | Một phần (qua widget) | **Hiện toàn bộ trước submit** |
| Chi phí dev | Thấp | Cao nhất | Trung bình-cao | **Trung bình — rẻ nhất ở dự án này** vì engine `infer*` đã có sẵn |
| Phù hợp schema backend cố định | Tốt | Kém | Khá | Tốt |

Ngành booking làm gì (tất cả [unverified], dựa kiến thức model, không web search):

- **Booking.com, Airbnb, Traveloka, Agoda: form-first thuần**, thanh search đa trường với autocomplete điểm đến + datepicker + guest stepper là màn hình chủ đạo. Chat/assistant nếu có thì đứng *sau* hoặc *ngoài rìa* (AI trip summary, trợ lý nhắn tin với chỗ nghỉ), không phải luồng đặt chỗ chính. Lý do ngành thường nêu: funnel cấu trúc đo conversion dễ, lỗi input được chặn bằng control chuẩn. [unverified]
- **Chatbot booking (WhatsApp Business của các hãng bay/khách sạn, Klook, các "AI concierge"): hybrid (c)** — quick-reply buttons/chips trong hội thoại. Được dùng cho tư vấn và cross-sell nhiều hơn là thu thập 6 trường bắt buộc. Tỷ lệ hoàn tất booking end-to-end trong chat thuần được các phân tích ngành đánh giá thấp hơn form; chat thắng ở engagement, form thắng ở conversion. [unverified]
- **Google (Maps/Travel), Skyscanner, Hopper: query một câu → disambiguation → màn hình kết quả cấu trúc có thể sửa**, tức biến thể của (d). Xu hướng được nói đến nhiều là "structured confirmation after free-text": cho user nói tự do một lần, rồi đưa ra bản tóm tắt *đọc được, sửa được* trước hành động tốn tiền/tốn thời gian. [unverified]
- **Amazon Alexa/Messaging commerce**: bài học phổ biến được trích dẫn — hội thoại voice/chat nhiều lượt có abandonment cao khi số slot > 3; các thiết kế tốt gộp slot-filling về một màn hình xác nhận. [unverified]

**Kết luận thẳng: hướng "chat tự do" là sai lầm cho sản phẩm này.** Lý do không phải ý kiến:

1. Backend đã là schema 6 trường cố định (`thoi_luong`, `so_nguoi`, `ngan_sach`, `ngay_di`, `location`, `context`). Chat tự do chỉ có giá trị khi backend chấp nhận intent mở. Ở đây mọi câu chat cuối cùng bị ép về đúng cái form — vậy thì hiển thị cái form sớm hơn, đừng giả vờ hội thoại.
2. NLU hiện tại là regex hữu hạn (18 thành phố, ~30 pattern thời lượng). Chat tự do hứa hẹn một năng lực hiểu mà hệ thống không có; mỗi lần hứa hụt chính là vòng lặp P2 và im lặng P1.
3. Ngành booking lớn không dùng chat thuần cho luồng chính [unverified]. Copy ngược chiều ngành mà không có dữ liệu người dùng ủng hộ là cược sai.

**Hướng chọn: (d) parse-then-confirm, giao diện là confirmation card editable, với (c) làm lớp fallback** (chip/stepper/date native gắn ngay trên card cho trường parse thiếu). Giữ lại *một* ô nhập tự do duy nhất làm cửa vào (đúng phần chat đang làm tốt: user gõ 1 câu), xóa bỏ máy trạng thái hỏi-đáp 3 lượt.

---

## 3. Thiết kế cụ thể cho dự án này

### 3.1 Component tree (đề xuất)

```
<Planner>                              (form, onSubmit → extract → confirm → generatePlan)
├─ <ChatWelcome/>                      (bubble "assistant" duy nhất — giữ nguyên)
├─ <IntentComposer/>                   (ô nhập 1 câu + nút gửi; giữ id="planner-context")
│   └─ ví dụ placeholder + 3 chip idea từ landing (di chuyển promptPlanner vào đây)
├─ <TripConfirmationCard/>             (render sau lần submit đầu tiên; role="group")
│   ├─ <SummaryEcho/>                  (1 dòng nhắc lại câu user, aria-live="polite")
│   ├─ <FieldRow destination/>         combobox + datalist 18 thành phố
│   ├─ <FieldRow duration/>            segmented 4 chip (giữ chip hiện có, bỏ bubble hỏi)
│   ├─ <FieldRow date/>                <input type="date"> native (iOS/Android picker)
│   ├─ <FieldRow people/>              stepper: button − / value / button + (min 1 max 30)
│   ├─ <FieldRow budget/>              <select> 4 mức + "Tùy"
│   ├─ <ParseNotes/>                   (chỉ hiện khi có trường suy đoán: "hiểu X là Y — chạm để đổi")
│   └─ <SubmitPrimary/>                "Tạo lịch trình" — disable tới khi 3 trường bắt buộc hợp lệ
└─ <StatusPanel/> + <ErrorPanel/>      (giữ nguyên role="status"/role="alert")
```

Không thêm file component mới nếu muốn tối thiểu: tất cả có thể viết inline trong `Planner.tsx` (file đã 720 dòng — nếu tách thì **1 file** `TripConfirmationCard.tsx` là đủ, không hơn).

### 3.2 Thứ tự render

1. Load: welcome bubble + composer (đúng hiện trạng).
2. User bấm gửi lần đầu (`submit()`): chạy **toàn bộ** `infer*` trên text → dựng `draft` → render `TripConfirmationCard` ngay lập tức, không POST.
3. Card hiển thị: trường parse được đánh dấu "đã hiểu" (confidence dot), trường đoán mặc định kèm dòng ParseNotes, trường thiếu hiện chip/stepper ở trạng thái trống với autofocus vào trường thiếu đầu tiên.
4. User sửa bao nhiêu lần tùy ý (mỗi lần sửa chỉ cập nhật local state, không hỏi lại gì cả).
5. Bấm "Tạo lịch trình" → `generatePlan()` giữ nguyên body request hiện tại.

Điểm mấu chốt: **không còn turn hội thoại nào sau turn đầu tiên**. Transcript 3-bubble biến mất; wizard biến mất.

### 3.3 State flow

```
draft: {
  idea: string,
  duration: Duration | null,          // inferDuration()
  dayCount: number | null,            // inferDayCount()
  destination: string | null,         // match catalog 18 → nếu null thì user PHẢI chọn
  people: number | null,              // inferPeople(), clamp 1..30
  budget: number,                     // inferBudget() ?? 1_000_000
  date: string | null,                // inferDateRange()
  guessed: Set<field>                 // các trường dùng default → hiện ParseNotes
}
phase: "compose" | "confirm"          // đúng 2 pha, không cần needsDuration/needsDestination/needsPeople
```

Mọi hàm `infer*` hiện có được **tái sử dụng nguyên vẹn** — không cần viết lại logic parse nào (phần đó thuộc làn regex/LLM, làn này chỉ tiêu thụ). `hasDestination()` chuyển từ "cửa chặn đối thoại" thành "nguồn gợi ý cho combobox": không khớp catalog thì field destination hiện trạng thái chưa hợp lệ và liệt kê 8-18 thành phố phổ biến làm chip — thay vì im lặng rơi về tọa độ Hà Nội (fix P1).

### 3.4 Xử lý "không biết / tùy"

`isUncertainReply()` (Planner.tsx:45) giữ nguyên, đổi vai trò: nhận diện "tùy/không biết" → điền default + đưa trường đó vào `guessed`:

- Thời lượng "tùy" → `ca_ngay` (giữ logic hiện tại) + ParseNotes: "Mặc định 1 ngày — đổi được".
- Số người "tùy" → 2 (giữ) + ParseNotes tương tự.
- Địa điểm "tùy" → KHÔNG default được; hiện chip thành phố.
- Mỗi chip trong ParseNotes là button sửa nhanh (1 tap), không phải hỏi lại.

Nguyên tắc: **mọi default phải nhìn thấy được và sửa được trước submit** — đây là khác biệt bản chất so với im lặng hiện nay.

### 3.5 Layout confirmation card (mobile ≤ 360px)

```
┌──────────────────────────────────────┐
│  TÓM TẮT CHUYẾN ĐI                   │
│  "cà phê phố cổ đà lạt cuối tuần"    │
├──────────────────────────────────────┤
│  Điểm đến                            │
│  ┌────────────────────────────────┐  │
│  │ Đà Lạt                   ✎ ▾   │  │
│  └────────────────────────────────┘  │
│  ( HN ) ( ĐN ) ( SG ) ( Phú Quốc )   │
│                                      │
│  Thời lượng                          │
│  [Vài giờ][Nửa ngày][◉Cả ngày]       │
│  [Nhiều ngày]                        │
│                                      │
│  Ngày đi (tùy)                       │
│  ┌────────────────────────────────┐  │
│  │  20/08/2026            📅      │  │
│  └────────────────────────────────┘  │
│                                      │
│  Số người          ( − )  2  ( + )   │
│  Ngân sách     [ ~1.000.000đ   ▾ ]   │
├──────────────────────────────────────┤
│  ⓘ "cuối tuần" được hiểu là Cả ngày  │
│    và 20/08 (T7). Chưa đúng? Chạm    │
│    vào ô bên trên để đổi.            │
└──────────────────────────────────────┘
│ [        TẠO LỊCH TRÌNH  →          ]│
└──────────────────────────────────────┘
```

Card dùng control native (`<input type="date">`, `<select>`, `<button>`) → zero CSS framework mới, tương thích 19 locale và RTL (globals.css đã có xử lý `dir` cho ar/he trong LocaleProvider).

---

## 4. Test contract: thay đổi UX phá bao nhiêu assert?

Đếm thật từ `i18n.test.mjs` (491 dòng, 335 dòng chứa `assert.`):

- Test lớn `"planner keeps its timeout, safe status and request contracts"` (test.mjs:396-475): **67 dòng assert lên `plannerSource`** + vòng lặp 4 duration chip (dòng 463) + 2 assert status backend (dòng 471-473) ≈ **73 runtime assert**.
- Test `"all supported locales contain the complete planner contract"` (test.mjs:115-123): 19 locale × 46 key (`plannerTranslationKeys`, i18n-core.ts:8) = **874 assertKey** + **1 exact-string** (`destinationPrompt:"Bạn muốn đi ở đâu?"`).

Phân loại 73 assert planner:

**Nhóm A — ~30 assert, KHÔNG được phá (hợp đồng request/parse, độc lập UI):**
`setTimeout…180000`, `plan-generate-nonce`, `requestNonce(fingerprint)`, `clearNonce(); setSession`, các hàm `inferDuration/inferClockRange/inferHourSpan/inferDateRange/inferPeople/inferDayCount/composeRequestContext`, `ngay_di: ngayDi`, `DEFAULT_LOCATION`, `DESTINATION_LOCATIONS`, `destinationLocation(composedContext)`, `lastRequest.current = {…}`, `AbortError`, `setErrorKey("generateFailed")`, `setErrorDetail`, `thoi_luong: duration`, mapping 2 SSE status, 3 tên thành phố catalog.

**Nhóm B — ~41 assert, PHẢI cập nhật nếu bỏ wizard (pattern assert cụ thể):**
- Máy trạng thái: `setNeedsDuration(true)`, `needsDuration &&`, `const [needsDestination,…]`, `needsDestination &&`, `const [pendingContext,…]`, `const [pendingDuration,…]`, `const [needsPeople,…]`, `if (needsPeople) {`, `if (needsDuration) {`, `if (!duration) {`, `setNeedsDestination(true)`.
- Hàm đối thoại: `function answerDestination`, `function answerPeople`, `function peopleQuestion`, `function hasDestination`, `if (!hasDestination(requestContext))`, `if (!hasDestination(answer))`, `continueOrAskPeople(requestContext, duration, inferPairedPeople(answer))` (×2).
- Chat UI: `role="log" aria-live="polite"`, `role="group" aria-label={t("durationLabel")}`, `role="group" aria-label={t("destinationPrompt")}`, `className="chat-composer"`, `className="chat-box chat-input-shell"`, `className="chat-input-icon" aria-hidden="true"`, `className="chat-send"`, `transcriptEnd.current?.scrollIntoView`, `const requestContext = \`${pendingContext…}`, `từ 20/8 đến 22/8`, `const bareNumber = normalized.match`, `function inferPairedPeople`.
- Negative assert sẽ ngược nghĩa khi bỏ wizard: `doesNotMatch(id="planner-people")`, `doesNotMatch(htmlFor="planner-people")`, `doesNotMatch(id="planner-duration")`, `doesNotMatch(chat-prompt-chips)`, `doesNotMatch(Bạn muốn đi trong bao lâu)` — bỏ wizard thì step-2 muốn *có* `id="planner-people"` cho stepper a11y.
- CSS planner trong `globalsSource` (`.chat-input-shell{border-radius:999px}`, `.chat-send{border-radius:50%}`): không phá nếu giữ composer.

**Nhóm C — key locale (874 assert):** thêm key mới = an toàn (assertKey chỉ yêu cầu có mặt); **bỏ** `chatWelcome/chatPlaceholder/sendChat` khỏi `plannerTranslationKeys` mà không đồng bộ 19 dòng locale trong `LocaleProvider.tsx` = vỡ 57 assert ngay; nếu đổi chuỗi `destinationPrompt` tiếng Việt = vỡ exact-string dòng 122. Thực tế bước 1 (thêm card) chỉ **thêm** key → chi phí là dịch 1 dòng × 19 locale, không phá assert nào.

Kết luận: **Bước incremental (giữ wizard, thêm card) phá 0 assert.** Bước thay thế hoàn toàn phá ~41 assert nhóm B — phải sửa `i18n.test.mjs` cùng PR với code, không thể lách.

---

## 5. Accessibility

### 5.1 Wizard hiện tại — đang tốt

- `role="log" aria-live="polite" aria-relevant="additions text"` trên transcript (Planner.tsx:645) — đúng pattern cho feed tin nhắn.
- `role="status"` (line 701), `role="alert"` (line 706) cho trạng thái/lỗi.
- Chip bọc trong `role="group"` + `aria-label` (line 652, 666).
- Icon-button có `aria-label`: `t("sendChat")`, icon ⌕ có `aria-hidden`.
- Focus management: `focusPlannerInput` sau `promptPlanner()` (Planner.tsx:56-61); auto-scroll `scrollIntoView` khi có message mới.
- Hỗ trợ `prefers-reduced-motion` và dark-mode ở globals.css.

### 5.2 Wizard hiện tại — đang hỏng

- **Screen reader không biết đang ở bước mấy.** Câu hỏi mới vào `aria-live` log nhưng ngữ cảnh "bước 2/3" không tồn tại; focus vẫn nằm ở input cũ.
- **17/19 locale đọc text sai ngôn ngữ** (P5 — string cứng vi/en). Mismatch `lang="th"` + text tiếng Việt/Anh là lỗi a11y nghiêm trọng với TTS.
- Bubble `p.bubble` không có marker phân biệt role user/assistant ngoài CSS — user VoiceBack/TalkBack không nghe ai nói.
- Câu hỏi dạng inline string chứa 4 phương án ("…hoặc chọn: Vài giờ, Nửa ngày…") — nghe rất dài qua TTS dù đã có chip bấm thay thế.

### 5.3 Yêu cầu a11y cho confirmation card

1. Card là `<form>` con hoặc `<fieldset>` với `<legend>` = "Tóm tắt chuyến đi" — không dùng `role="dialog"` trừ khi thực sự chặn nền (mobile: chặn nền + bàn phím là trải nghiệm tệ).
2. Mỗi `FieldRow`: `<label htmlFor>` thật (chính là lúc cần `id="planner-people"`, `id="planner-duration"` — hiện đang bị test cấm, cần cập nhật test nhóm B).
3. Destination combobox: ưu tiên `<input list>` + `<datalist>` native (a11y và i18n miễn phí); nếu tự viết combobox phải có `role="combobox" aria-expanded aria-activedescendant` + arrow-key navigation — PlanView.tsx đã có tiền lệ combobox (được assert `role="combobox" aria-autocomplete="list"`), có thể copy pattern.
4. Stepper số người: 2 `<button type="button" aria-label="Giảm/Tăng">` + giá trị `aria-live="polite"` hoặc `output`; toàn bộ chạm được bằng phím (không cần JS phím riêng vì là button thật).
5. Submit: validate phía client; khi lỗi → focus trường thiếu đầu tiên + message trong `role="alert"`; không dùng màu đỏ làm kênh duy nhất.
6. Vùng ParseNotes/SummaryEcho: `aria-live="polite"` để đọc lại khi re-parse.
7. Touch target ≥ 44px — codebase đã có chuẩn này (`.itinerary-export-actions .button-link{min-height:44px}` trong assert test:225), card phải kế thừa.
8. RTL (ar/he): dùng logical properties (`margin-inline-start`, `inset-inline-end` — globals.css đã dùng).
9. `prefers-reduced-motion`: không animate re-parse của card.

---

## 6. Lộ trình incremental (đã đếm file thật)

Repo frontend có 29 file nguồn (8 components, 11 app pages, 7 lib, 3 tests). Đề xuất 3 bước:

**Bước 0 — vá đau ngay, phá 0 test (1 file):** `Planner.tsx`
- Fix P1: từ chối im lặng fallback tọa độ — khi destination không khớp catalog, thêm note vào context kèm `location` đúng mặc định + cảnh báo, hoặc chặn submit bước địa điểm với chip gợi ý.
- Fix P5: đưa 4 string cứng (peopleQuestion, 2 câu mặc định "không biết") vào key locale mới (**thêm** key → cần `i18n-core.ts` + 19 dòng `LocaleProvider.tsx`, vẫn 0 assert vỡ vì assertKey chỉ đòi có mặt). Tổng: 3 file (`Planner.tsx`, `i18n-core.ts`, `LocaleProvider.tsx`).
- Thêm chip "Không biết" cạnh chip thời lượng/số người → tắt vòng lặp P2 với 1 tap.
- Thêm bubble echo sau mỗi câu trả lời ("Mình hiểu: Đà Lạt — cả ngày") → giảm P7.
- Ước lượng: 3 file, ~80 dòng, giữ nguyên 335 assert hiện hành.

**Bước 1 — thêm parse-then-confirm song song wizard, phá 0 test (4-5 file):**
- Thêm `TripConfirmationCard` (1 file mới hoặc inline): sau submit đầu tiên, render card thay vì hỏi tiếp; wizard cũ giữ làm fallback ẩn (các `needsX` vẫn tồn tại → nhóm B sống nguyên).
- Thêm key mới cho card (19 dòng locale). Chạm: `Planner.tsx`, file card mới, `i18n-core.ts`, `LocaleProvider.tsx`, `globals.css`. Ước lượng 5 file, 1-2 ngày công.
- Đo: nếu >80% user hoàn tất qua card (metric tự gắn) → sang bước 2.

**Bước 2 — gỡ wizard, phá ~41 test (6 file):**
- Xóa `needsDuration/needsDestination/needsPeople`, `answer*`, `peopleQuestion`, transcript chat 3 bubble; composer + card là toàn bộ UI.
- Cập nhật `i18n.test.mjs` nhóm B (~41 assert: đảo negative, thêm assert card: fieldset/legend, stepper, datalist, focus-management), thêm assert mới chống regress P1 (không fallback tọa độ im lặng).
- Giữ nguyên nhóm A + nhóm C. Chạm: `Planner.tsx` (viết lại ~300 dòng), `i18n.test.mjs`, `globals.css`, `page.tsx` (chip landing có thể tự submit thẳng vào card draft thay vì chỉ điền input), `i18n-core.ts`, `LocaleProvider.tsx`.
- Ước lượng 6 file. Đây là bước duy nhất phá test; bắt buộc đi cùng PR.

**Không làm:** voice input, chat đa turn tự do, datepicker tự viết, combobox tự viết khi `datalist` đủ, i18n framework (hệ 19-dòng đang chạy).

---

## 7. Bảng phân loại tổng hợp

| # | Finding | Mức | Bằng chứng code |
|---|---|---|---|
| 1 | Địa điểm ngoài 18 regex → im lặng tọa độ Hà Nội, không validate | **Blocker** | Planner.tsx:13,331-339,550-560 |
| 2 | Vòng lặp hỏi lại không lối thoát (duration/people) | High | Planner.tsx:521-533,573-577 |
| 3 | Budget/date/daycount trích xuất im lặng, không sửa được trước submit | High | Planner.tsx:380-405,434-438 |
| 4 | "Chat tự do" sai hướng cho schema 6 trường cố định | High | Planner.tsx:458-468 |
| 5 | String cứng vi/en giữa 19 locale (a11y: TTS sai ngôn ngữ) | Medium | Planner.tsx:317-329,524,569 |
| 6 | Landing chip prompt tiếng Việt cứng mọi locale; chip không tự submit | Medium | page.tsx:48-55,83-87,183 |
| 7 | ~41/73 assert buộc phải viết lại nếu bỏ wizard; bước 1 phá 0 | Medium | i18n.test.mjs:396-475 |
| 8 | Không có tiến trình/echo trong hội thoại | Low | Planner.tsx:638-676 |
| 9 | Ngành booking lớn dùng form-first hoặc query+confirm, không chat thuần cho funnel chính | **Note** [unverified] | — |
| 10 | Engine `infer*` 200 dòng đã có sẵn → parse-then-confirm gần như miễn phí về mặt parse | **Note** | Planner.tsx:123-378 |

---

## Executive summary

UX hiện tại của ai_travel là một form 6 trường ngụy trang thành chat wizard 3 lượt. Đọc code cho thấy: luồng hội thoại chỉ là máy trạng thái `needsDuration/needsDestination/needsPeople` trên một ô input duy nhất; NLU là ~200 dòng regex `infer*` chạy client-side; backend nhận schema cố định. Ba lỗi đau gốc: (1) địa điểm không khớp 18 regex thì bị im lặng gán tọa độ Hà Nội — Blocker về đúng đắn dữ liệu; (2) parse fail thì lặp lại câu hỏi cũ vĩnh viễn, không nút thoát; (3) ngân sách, ngày đi, số ngày được trích xuất âm thầm và không thể sửa trước khi chờ sinh plan tới 180 giây. So sánh 4 pattern thu thập intent: form-first rẻ nhưng phí lợi thế "gõ một câu"; chat thuần sai lầm vì backend không chấp nhận intent mở và ngành booking lớn không dùng nó cho funnel chính [unverified]; hybrid widget khá nhưng thừa lớp hội thoại; **parse-then-confirm thắng** với 2-3 tap mobile, lộ toàn bộ lỗi parse trước submit, và gần như miễn phí vì engine regex đã có sẵn. Thiết kế đề xuất: giữ một composer duy nhất làm cửa vào; sau lần gửi đầu tiên dựng TripConfirmationCard với 6 hàng field (combobox datalist điểm đến, segmented chip thời lượng, date native, stepper số người, select ngân sách) cùng vùng "được hiểu là…" cho mọi giá trị suy đoán; xử lý "tùy/không biết" bằng default nhìn-thấy-được thay vì im lặng. Ràng buộc test: test suite chứa ~73 assert lên Planner.tsx (≈30 hợp đồng phải giữ, ≈41 luồng wizard phải viết lại khi thay thế) và 875 assert locale; lộ trình 3 bước cho phép bước 0 và 1 phá đúng 0 assert. A11y hiện tại khá ở live-region nhưng hỏng ở string cứng vi/en giữa 19 locale và thiếu chỉ báo bước. Khuyến nghị: làm bước 0 ngay (3 file), đo adoption của card, rồi gỡ wizard trong PR kèm cập nhật test.

## Top 5 findings

1. **Blocker — định vị sai im lặng:** `answerDestination` chấp nhận mọi text nhưng `destinationLocation` chỉ khớp 18 regex, còn lại mặc định tọa độ Hà Nội; user không hề được báo (Planner.tsx:550-560, 336-339).
2. **Sai hướng nếu làm chat tự do:** backend là schema 6 trường cố định; chat chỉ có giá trị ở cửa vào một câu, toàn bộ phần "hội thoại" hiện nay là overhead gây vòng lặp (Planner.tsx:458-468) [unverified: ngành booking lớn cũng không dùng chat thuần cho funnel chính].
3. **Parse-then-confirm là hướng đúng và rẻ nhất:** engine `infer*` 200 dòng đã tồn tại; card xác nhận editable đưa taps hoàn tất về 2-3, biến mọi lỗi parse thành thứ nhìn thấy và sửa được trước submit.
4. **Test contract khả thi để đi incremental:** ~73 assert trên Planner.tsx chia rõ 30 "hợp đồng" (nonce, timeout, infer*, request body) và ~41 "luồng wizard" (needsX, answer*, chat class); bước đầu thêm card phá 0 assert, chỉ bước gỡ wizard mới phải sửa ~41 assert trong cùng PR.
5. **Nợ i18n/a11y nghiêm trọng:** 4 string cứng vi/en trong Planner và prompt tiếng Việt cứng trên landing chạy giữa 19 locale (sai với 17 locale, TTS đọc sai `lang`); đồng thời không có chỉ báo bước tiến trình cho screen reader.

## Confidence

**8/10.** Trừ phần so sánh ngành. **11/14 kết luận chịu tải được kiểm chứng bằng code** (toàn bộ finding 1-8 trong bảng phân loại dẫn chiếu số dòng cụ thể; chỉ finding 9 về ngành, ước lượng tap tuyệt đối, và ngưỡng adoption 80% là suy luận/không kiểm chứng). Điểm trừ: không có dữ liệu analytics thật của user nên thứ tự ưu tiên P2/P3 dựa trên cơ chế code chứ không phải tần suất occurrence ngoài production.
