# Executive Briefing — User-Interaction Gaps vs layla.ai

Ngày: 2026-08-08. Deep-dive standard: 4 specialists + synthesis + red-team. Báo cáo chi tiết: `research/layla-interaction-gaps/01..06`.

## Bottom line up front

Dự án có nền tảng vững chắc (SSE status, OCC versioning, nonce idempotency, rate-limit, 19-locale contract, OSM/OSRM live) nhưng **chưa phải trải nghiệm "conversational AI" kiểu layla**: hiện là một "command bar" một dòng — gửi câu, nhận plan, refine bằng phản hồi canned không phải ngôn ngữ thật. Gap lớn nhất nằm ở **thiếu conversation store** (backend không nhớ hội thoại) và **refine không streaming**. Sửa top-10 gap = đại đa số chạm cả frontend lẫn backend nhưng từng item đều nhỏ (S/M).

## Where the build genuinely shines

- **SSE status streaming** trong generate (`plans.py:119-127`) + parser CRLF an toàn (test phủ đôi).
- **Optimistic concurrency + nonce**: 409 conflict, idempotency, không trùng plan.
- **Redis rate-limit fail-closed + circuit breaker** cho AI provider.
- **19-locale contract có test bắt buộc** — chuẩn ngành, ít app làm được.
- **Provenance trung thực**: chi phí VND công khai, catalog thủ công kiểm chứng, không bịa điểm.
- Offline snapshot, PDF/ICS/JSON export, service-worker cached visited plans.

## Critical gaps (Blocker)

1. **Không có conversation store** — `refine` (`plans.py:433`) ghi đè context blob 500 ký tự; assistant reply không bao giờ lưu; không `conversation_id`, không message list. [B]
2. **Reply không phải ngôn ngữ thật** — `parseReplyKey` (`PlanView.tsx:26`) chỉ nhận `swipeSuccess`/`assistantWelcome`; mọi refine trả cùng một bubble canned. [F]
3. **Refine/generate không streaming token** — AI call non-streaming JSON (`ai.py:143,235,316`); generate SSE chỉ 2 status + 1 event atomic; refine block client 30-60s. [B]
4. **Không thể hỏi lại các tham số chuyến** — budget hardcode 1.000.000 VND (`Planner.tsx:108`), duration regex-guess; duration selector keys (`durationLabel/fewHours/...`) có trong i18n nhưng không render. [F]

## Top-10 "làm trước" (impact/effort)

1. **Sửa bộ test đỏ** — phục hồi duration-ask trong Planner (regression thật, đã làm).
2. **Conversation store** — bảng messages + trả lời từ lịch sử. [B] M
3. **Constraint echo** — sau refine hiển thị "budget/duration/people hiện tại". [F+B] S
4. **Explicit budget/duration intake** — dùng keys i18n đã có, kèm refresh-plan từ tham số. [F] S
5. **Per-refine undo** — snapshot trước refine + nút khôi phục. [F] S
6. **Home resume** — "tiếp tục chuyến của bạn" từ `/api/plans`. [F] S
7. **SSE cho refine/regenerate** — stream token + nhiều status. [B] M
8. **Retry/last-updated indicators** — nút thử lại, timestamp, stale badge. [F] S
9. **Duration chips thật** (render `fewHours/halfDay/fullDay/multiDay`). [F] S
10. **Fix `retryCreate:"Thu lai"` untranslated** (19 locale) + `dataNotice` tiếng Việt lọt mọi locale. [F] S

## Red-team corrections (sai trong lane report, đã kiểm chứng lại)

- Report 04: "không có OG tags" — sai; `plan/[token]/page.tsx:6` có OG + Twitter card; gap thật là dynamic per-trip card.
- Report 01 G24: currency sync chỉ là units; tiền plan hardcode VND (`PlanView.tsx:81`).
- Report 04: "regenerate mất swipeSuccess" — sai; `PlanView.tsx:109` hiển thị nó (copy sai semantics sau rebuild).
- **Blind spot chính**: `tests/i18n.test.mjs` đang RED (2/18) — các lane đều coi là green. Assertion cũ `setNeedsDuration(true)` chứng minh **một duration-ask conversational từng bị gỡ bỏ** khỏi Planner.tsx — regression, không chỉ test stale. Đã sửa: phục hồi interaction bằng i18n keys + cập nhật assertion theo implementation đúng.

## Confidence

**7/10** (sau red-team hạ từ 8). Ground-truth tally: ~45/45 load-bearing claims được verify độc lập bằng đọc code/grep; 7 mục model-judgment/external. Điểm bị chặn vì layla.ai feature list 58 mục chỉ 41 từ trang fetched (8 unverified), và mức "feel-lift" của từng fix là phán đoán UX.

## Should you proceed?

**Có** — làm tiếp 10 gap trên theo thứ tự. Không gap nào yêu cầu thay kiến trúc; tất cả là mở rộng cục bộ trong kiến trúc đã có (Postgres + Redis + SSE infra). Hạn chế duy nhất: không ai trong nhóm chưa từng thấy layla.ai bản thật, nên benchmark "bằng layla" nên đối chiếu bằng PARITY_MATRIX hành vi, không sao chép thương hiệu.
