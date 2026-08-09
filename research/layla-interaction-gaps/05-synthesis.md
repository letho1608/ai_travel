# 05 — Synthesis: "Mình Đi Đâu Thế" vs layla.ai — Unified Interaction-Gap Assessment

**Author lane:** Synthesis / oversight.
**Inputs:** `01-frontend-interaction.md` (37 findings, G1–G37), `02-backend-interaction.md` (11 gaps), `03-layla-features.md` (external product research), `04-ux-gaps.md` (8 stages, 30+ gaps).
**Verification performed by this lane:** re-read `PlanView.tsx`, `Planner.tsx`, `MapView.tsx`, `Navigation.tsx`, `page.tsx`, `history/page.tsx`, `explore/page.tsx`, `settings/page.tsx`, `app/plan/[token]/page.tsx`, `lib/api.ts`, `public/sw.js`, `app/globals.css`, `lib/workspace-translations.ts`, `LocaleProvider.tsx`, `tests/i18n.test.mjs`, `backend/app/routers/{plans,auth,support}.py`, `backend/app/services/{ai,store,reminders}.py`, `backend/app/services/postgres_store.py` (reminder + notification paths), `backend/app/schemas.py`, `backend/app/main.py`; plus greps for `websocket`, `scrollIntoView`, `onLine`, `offline-plan` reads, boundary files (`loading/error/not-found/global-error`), and `.bubble.typing` usage. **No code modified.**

---

## 1. TL;DR verdict

**This is a disciplined, resilient single-shot itinerary generator, not a conversational trip planner.** The single defining gap — agreed unanimously by all four lanes and re-verified here — is that the "chat" is a command bar wearing a chat costume: every refinement (`rẻ hơn`, `thêm cafe`, any free text) returns the **same canned i18n bubble** from the backend (`plans.py:484-485, 501-502`) which the frontend accepts and renders verbatim (`PlanView.tsx:26, 102, 122`). There is **no conversation store** (refine rewrites a 500-char context blob, `plans.py:433`), **no token or even status streaming** on the refine path (a blocking POST, `plans.py:457`), and **no server-side memory** of what the assistant ever said. Trip intake hardcodes budget to 1,000,000 VND (`Planner.tsx:108`), location to Hanoi (`Planner.tsx:105`), and regex-guesses duration with a silent full-day default (`Planner.tsx:65-72`) — while the duration UI translations sit dead in `LocaleProvider.tsx`. The backend has **no WebSocket/push channel anywhere**, notifications are a polled DB inbox (`plans.py:62-86`) with only one type (`trip_24h`), and booking-queue transitions never reach the user (`support.py:31-45`).

**What it would take to "feel like layla":** persist a real conversation + reply in natural language, ask budget/dates explicitly, stream the refine, push events instead of polling, and let users undo/edit with a visible diff. The first three of these are Blocker-grade.

---

## 2. Where the app genuinely shines (agreed across lanes, verified)

- **Verified-catalog integrity + deterministic routing.** Places are a hand-verified catalog (`PLACES`); AI may edit copy but never inventory/constraints (`ai.py:54-71` `_apply_copy` only takes `mo_ta`, `tieu_de`, `tom_tat`, `luu_y`; validated IDs). Honest provenance/disclaimers throughout (Explore `sourceFetchedExpires`, plan estimate disclaimers). Strong trust posture — report 04 calls this a genuine strength.
- **Optimistic-concurrency + versioned undo that actually works.** `store.update(item, expected_version, …)` raises `VERSION_CONFLICT` (`store.py:82-84`), routers → 409 ("tải lại") (`plans.py:381-382, 494-495`); restore is non-destructive (creates a new version) (`plans.py:519-540`). Versioning is *solid but blind* (no diff) — see gaps.
- **Idempotency via nonces** for generate/regenerate (`plans.py:92-106, 401-405`; `store.py:411-413`), tested (`test_api.py:203-269` per 02).
- **Rate limiting + circuit breaker + fail-closed providers.** Per-session/IP fixed windows on every mutating endpoint; Redis Lua atomic and fail-closed; circuit breaker 3-failures/5min → 120 s open (`ai.py:12-38`); deterministic fallback when LLM times out (10 s httpx timeout, `ai.py:108`).
- **UI discipline:** universal disable-during-flight with ref-guards, 30–90 s timeouts, 401 self-healing, nonce replay guard, clipboard + Web Share with typed feedback, map↔itinerary two-way selection sync, 19-locale i18n enforced by tests.
- **Export is free and complete** — PDF + `.ics` + JSON (`plans.py:163, 210`; `PlanView.tsx:116`). Layla gates PDF behind a $49.99/yr premium (report 03 §2.8). A real product advantage.
- **Static share-card infrastructure already exists:** `app/plan/[token]/page.tsx:6` emits OpenGraph + Twitter `summary_large_image` with `/og.png` — the per-trip dynamic card is missing, but the plumbing is half-done.

---

## 3. Unified prioritized gap list

Tag: **[F]** frontend-only, **[B]** backend-only, **[F+B]** both. Sev = agreed severity. `file:line` refs verified by this lane unless marked ⚠ (see §6).

### (A) BLOCKER — must-have for a conversational feel

| # | Gap | Sev | Tag | file:line | Smallest fix path |
|---|---|---|---|---|---|
| A1 | **Assistant replies are canned i18n keys, not language.** `parseReplyKey` accepts only `swipeSuccess`/`assistantWelcome`; every refine returns one fixed bubble ("Đã thay đúng một điểm…") even for budget/pace requests. | Blocker | F+B | `PlanView.tsx:26,102,122`; `plans.py:484-485,501-502`; `workspace-translations.ts:5` | Store turns in a `message` table (`role, text, ngay_tao, plan token`) + have refine return a real NL reply (LLM-generated or template-echo of the user's message) and **persist** it; render `item.text` free-text in `PlanView.tsx:122`. |
| A2 | **No server-side conversation memory.** Refine rewrites one `context` blob, truncated to last 500 chars; the assistant's reply is never persisted; versions snapshot plans, not dialogue. Multi-turn context silently dies. | Blocker | B | `plans.py:433`; `ai.py:136,217` (`ngu_canh_nguoi_dung`) | Add `conversation_id` + turn table; append turns instead of `[-500:]`; reconstruct AI context from the transcript; expose `GET /plans/{token}/messages` for resume-after-reload. |
| A3 | **Refine is a blocking, non-streaming POST** with only a bare `busy` line; 10–60 s with zero progress. The only streaming surface in the whole backend is `generate` (and even that is 2 hardcoded statuses + 1 atomic result, `plans.py:118-131`). | Blocker | F+B | `PlanView.tsx:102,118`; `plans.py:457`; `ai.py:143,235,316` (no `stream:true`) | SSE for refine: reuse `finding_places`/`routing_plan` statuses + a `result` event; or wire token deltas via `stream:true` in `ai.py`. Frontend: render status events in the chat panel. |
| A4 | **Trip parameters are never asked or settable.** Budget hardcoded 1,000,000 (`Planner.tsx:108`); location hardcoded Hanoi (`:105`); duration regex-inferred with silent `ca_ngay` default (`:65-72`); no date range / transport style. Duration UI keys exist but are dead (`LocaleProvider.tsx:75+`; test *asserts* absence, `i18n.test.mjs:255`). | Blocker | F+B | `Planner.tsx:65-72,105,108` | Add budget-band + duration segmented control (and optionally a destination chip row) to the planner; backend trusts explicit params over regex (`_refined_request`), i.e. send them as fields, not only in free text. |

### (B) HIGH — high impact on the core loop

| # | Gap | Sev | Tag | file:line | Smallest fix path |
|---|---|---|---|---|---|
| B1 | **No follow-up / clarifying questions; chips are static.** Backend intent extraction is regex-only (`plans.py:435-453`); frontend has 3 hardcoded chips (`PlanView.tsx:68`). Layla's signature is *questions-first* generation (report 03 §2.1). | High | F+B | `plans.py:435-453,469-471`; `PlanView.tsx:68` | Return `suggested_next_chips` + an optional `cau_hoi` (pending question) field on refine; persist pending-question state; render chips from the reply, not a constant. |
| B2 | **No push channel — poll-only everything.** No WebSocket anywhere (grep: zero); notifications are a DB inbox hydrated on read (`plans.py:70`) + hourly loop (`main.py:63-70`); booking-queue status changes never notify the user (`support.py:31-45`); comments/plan-updates on a shared plan are invisible until reload. | High | B | `main.py:63-70`; `plans.py:62-86`; `support.py:31-45` | Minimal: emit a `thong_bao` row on every booking transition + new comment; add unread-count endpoint. Real: SSE/WebSocket fan-out (Postgres `LISTEN/NOTIFY` or Redis pub/sub). |
| B3 | **No undo in the chat; restore is blind (no diff).** Undo is buried in a header drawer of version numbers; `list_versions` returns the full plan JSON per version (`store.py:93-94`); no diff endpoint. Users fear breaking a plan, so they stop experimenting. | High | F+B | `PlanView.tsx:104-105`; `store.py:85-94`; `plans.py:506-516` | Per-turn "Hoàn tác" button on assistant bubbles wired to existing restore; client-side diff (added/removed names + cost delta) in the drawer. Cheap — the data is already fetched. |
| B4 | **No direct editing of the itinerary** (reorder / time / insert-a-place are chat-only; slots are read-only display). | High | F | `PlanView.tsx:123` (slots render-only) | Drag handles + inline time steppers + "+ add here" between slots; add a backend `POST /plans/{token}/reorder`-style endpoint (or reuse swipe+restore). |
| B5 | **Returning users get no resume path; anonymous plans silently strand.** Home page is static marketing; no "continue" list, no sign-in nudge, no account toggle in workspace; `Navigation` reads auth once on mount (`Navigation.tsx:20-24`) so admin link is stale. | High | F | `page.tsx:24-108`; `history/page.tsx:55`; `Navigation.tsx:20-24` | Fetch `/api/plans` on `/` and show 3 recent "Tiếp tục chuyến đi" cards; dismissible "saved only on this device — sign in" bar on plan pages for anonymous sessions. |
| B6 | **Constraints are never echoed back.** `trip-facts` shows weather/cost/place-count only (`PlanView.tsx:117`); nothing states what the system believes (pax, budget, duration, style). Every turn is guess-the-intent. | High | F | `PlanView.tsx:117`; `Planner.tsx:105-108` | A persistent constraint strip above the itinerary fed from the create/refine request; every assistant reply confirms the delta ("Giảm còn ~500k/người, đã thay 3 điểm"). |
| B7 | **"Why this place" reasoning is generated but thrown away.** `draft_itinerary_places` asks the AI for per-place `why` (`ai.py:214-228`), but `_apply_copy` copies only `mo_ta`/`tieu_de`/`tom_tat`/`luu_y` into the final plan (`ai.py:54-71`) — the rationale never surfaces, so every suggestion looks unearned. | High | B+F | `ai.py:54-71,214-228` | Carry a `ly_do` field through `_apply_copy` → plan schema → slot card; reply text states reasons ("đổi vì gần tuyến xe buýt, giảm 20 phút di chuyển"). |

### (C) MEDIUM

| # | Gap | Sev | Tag | file:line | Smallest fix path |
|---|---|---|---|---|---|
| M1 | **Typing indicator is dead CSS.** `.bubble.typing` + `typingPulse` exist (`globals.css:22`) with zero `.tsx` usage. | Med | F | `globals.css:22`; `PlanView.tsx:118` | Render `<div className="bubble typing"><span/><span/><span/></div>` while `busy` is set. Trivial. |
| M2 | **No auto-scroll, input disabled while working, no chat-level reset.** `.messages` is `overflow:auto` but no `scrollIntoView` anywhere (grep: zero); `disabled = busy!==null` (`PlanView.tsx:110`); regenerate is header-only (`:109`). | Med | F | `globals.css:22`; `PlanView.tsx:109-110,122` | `useRef` + `scrollIntoView({behavior:"smooth"})` on conversation change; keep input enabled; add a chat "Bắt đầu lại" reset button. |
| M3 | **No skeletons, no optimistic updates, no retry actions.** No `loading.tsx`/`error.tsx`/`not-found.tsx`/`global-error.tsx` in `app/` (glob: zero); plan page blocks on server fetch with no shell (`plan/[token]/page.tsx:5`); `fail()` only sets text (`PlanView.tsx:86`); swipe/refine/restore all wait for full round-trip. | Med | F | `PlanView.tsx:86,101-109`; `plan/[token]/page.tsx:5`; `history/page.tsx:53` | Add `loading.tsx` per route; optimistic slot swap (apply replacement locally, reconcile); add Retry buttons wherever a `*Failed` message is shown. |
| M4 | **No live plan state / last-updated / stale indicator.** One-shot comments fetch only (`PlanView.tsx:96`); plan changed in another tab/device never surfaces; header shows version number but no timestamp (`PlanView.tsx:116`). | Med | F+B | `PlanView.tsx:96,116`; `plans.py:134-139` | Return `ngay_cap_nhat` from `GET /plans/{token}`; show "cập nhật X phút trước"; poll or SSE for version drift. |
| M5 | **Error contract is Vietnamese `detail` strings; no codes/i18n keys; no global exception handler; SSE error shape differs from HTTP error shape.** Frontend must string-match to localize (19 locales). | Med | B | `plans.py:112,138,382,494`; `main.py` (no `exception_handler`) | Add a stable `code` + `tra_loi_key`-style key to every error; add a global handler returning problem-details JSON; keep the SSE `error` event consistent with HTTP errors. |
| M6 | **Swap gives no choice — one replacement auto-picked by distance (`plans.py:344-347`).** No "see 3 options" picker. | Med | B+F | `plans.py:344-347`; `PlanView.tsx:101` | Return the top-3 candidates ranked; frontend opens a mini-sheet picker; chat renders as a decision log. |
| M7 | **Offline is half-built.** `offline-plan:<token>` is written (`PlanView.tsx:97`) but never read back (grep: zero); SW caches GETs only (`sw.js:16-26`); no `navigator.onLine` listener (grep: zero). Offline users get a dead page with saved-but-unusable data. | Med | F | `PlanView.tsx:97`; `sw.js:16-26` | On `online`/mount, if fetch fails read `offline-plan:<token>`; add an offline banner; listen for `online`/`offline`. |
| M8 | **Auth UX incomplete: 7-day JWT, no refresh, no logout, merge trusts a client-supplied session id.** Expired vs invalid both → 401; multi-device logout impossible; `upsert_user_and_claim` claims every plan whose `ma_phien` matches the client string (`auth.py:27,72-74`). | Med | B | `auth.py:27,32-44,72-74`; `schemas.py:299-304` | Add refresh-token endpoint + logout/revocation; bind merge to a server-issued proof-of-possession (cookie/JTI) instead of a client-supplied string. |
| M9 | **Long-running work runs inside the request; no job/status model.** Refine/regenerate/multicity block synchronously; SSE disconnect cancels generation (Starlette cancels the generator); no `/status`, no resume, no webhook. | Med | B | `plans.py:118-131,390,457`; `ai.py:108` | Job id + status endpoint for heavy endpoints; keep SSE only for the live phase; persist in-progress plans so a disconnect can resume. |
| M10 | **Day-by-day overview missing.** Only one day visible at a time; no condensed multi-day strip, no day cost/pace signal (report 04 §3.1). | Med | F | `PlanView.tsx:123` | A scrollable day-summary strip above the tabs (place count, walking time, cost, busiest day) computed client-side. |
| M11 | **Toasts / notification feedback missing; success and failure render identically** in one top-of-page status div (`PlanView.tsx:118`). | Med | F | `PlanView.tsx:118` | Lightweight toast layer (success green / error red, auto-dismiss, near the trigger). |
| M12 | **Accessibility: drawers are not dialogs** (inline `<section>`, no `role="dialog"`, focus trap, Escape), no skip link, no error boundary, map markers are click-only circleMarkers (`MapView.tsx:37-45`), day-tabs use class not `aria-selected`. | Med | F | `PlanView.tsx:119-121,123`; `MapView.tsx:37-45`; `app/layout.tsx` | Dialog role + focus trap + Escape for drawers; skip-link; keyboard-accessible markers; `aria-selected` on tabs. |
| M13 | **Notification semantics shallow** — no unread count, no mark-all-read, single type `trip_24h`, no per-user prefs, no events for comments/refine/booking/snapshot-expiry. | Med | B | `plans.py:62-86`; `postgres_store.py:617-634`; `history/page.tsx:12,55` | Unread-count + bulk-read endpoints; emit notifications at booking transitions and new comments. |
| M14 | **Traveler profile never captured** (style, pace, companions, diet, mobility). Layla's core differentiator is *ask and remember*; this app produces one generic balanced plan for everyone. | Med | F+B | `Planner.tsx:192-203` (only people count) | Add a 60-second companion profile (couple/family/group, pace, dietary) stored in preferences and reflected in the constraint strip. |

### (D) LOW / NOTE

| # | Gap | Sev | Tag | file:line | Smallest fix path |
|---|---|---|---|---|---|
| L1 | **Mutation has no animation / highlight** — a refine/swipe changes slots with no visual cue (`PlanView.tsx:101-102`); regenerate drops `swipeSuccess` with no confirmation. | Low | F | `PlanView.tsx:101-102,109` | Animate/highlight changed slots; confirm before "Làm lại". |
| L2 | **Share card is a static `/og.png`, not per-trip.** OG tags DO exist (`plan/[token]/page.tsx:6`) — the gap is only the dynamic summary image. ⚠ this corrects report 04 §6.2. | Low | F | `plan/[token]/page.tsx:6`; `public/og.png` | Generate a day-by-day one-pager image server-side; keep the OG plumbing. |
| L3 | **Preferences barely reach the experience:** plan cost is always VND (`PlanView.tsx:81` hardcodes `currency:"VND"`), so setting USD only changes Explore; `dataNotice` leaks untranslated Vietnamese into all 19 locales (`LocaleProvider.tsx:75-93`). | Low | F | `PlanView.tsx:81`; `LocaleProvider.tsx:75` | Render plan prices in the chosen currency (with "≈" note) or label it Explore-only; translate `dataNotice`. |
| L4 | **No in-plan search/filter; long plans are one long scroll.** | Low | F | `PlanView.tsx:123` | Per-day filter row (all/food/culture/free) + search box. |
| L5 | **Feedback is one-shot and owner-only**; no in-session "was this helpful?"; no trip-mates' voices (`plans.py:226-248`). | Low | F+B | `plans.py:226-248`; `PlanView.tsx:108` | Post-trip share-to-rate prompt; per-day inline thumbs. |
| L6 | **Trip lifecycle is dead air until T-24h** — only touchpoint is the reminder inbox. No packing list, weather-refresh nudge, "day 1 in 3 days" cadence. | Low | B | `main.py:63-70`; `postgres_store.py:617-634` | A per-plan dashboard + in-app touchpoints; optional email later. |
| L7 | **No rebooking / "plan this again" loop** after a successful trip. | Low | F | `history/page.tsx:55` | "Tạo chuyến tương tự" button cloning a plan into a prefilled planner session. |
| L8 | **History is a bare list** — no dates/search/rename/duplicate/archive/delete (`history/page.tsx:55`). | Low | F | `history/page.tsx:55` | Rich cards + lifecycle actions; "copy and adjust" flow. |
| L9 | **Explore/roadtrip polish:** no skeleton loaders, no retry, expiry shows misleading `searchFailed` (`explore/page.tsx:38`), roadtrip map has no `loading:` fallback. | Low | F | `explore/page.tsx:38`; `app/roadtrip/page.tsx:10` | Skeletons; "data expired — search again" message; `loading` prop on dynamic map. |
| L10 | **LLM economics:** 2× zero-delay retry (`ai.py:141,233,314`), budget reserved as 0.0 pre-flight (`plans.py:114,410`) so a burst can overspend before rejection, no global in-flight cap, no `Retry-After` on 429. | Low | B | `ai.py:141`; `plans.py:114,410` | Exponential backoff + jitter; non-zero pre-flight reservation; global concurrency limiter; `Retry-After` header. |
| L11 | **Dead code + timing bug:** `reminders.py` (`due_in_app_reminders`) is never imported (grep: definition only); postgres `materialize_due_reminders` fires on `BETWEEN current_date AND current_date+1` (`postgres_store.py:621`) — calendar-day, so a 23:59 departure fires ~24 h early (memory store uses the correct 24 h window). | Note | B | `reminders.py:10`; `postgres_store.py:621` | Delete `reminders.py` or route through it; switch the WHERE to `>= now()` AND `<= now()+interval '24 hours'` (already the memory-store semantics). |
| L12 | **GZip middleware (`main.py:82`) can buffer SSE frames**, defeating real-time feel for any future streaming channel. | Note | B | `main.py:82` | Exclude `text/event-stream` from GZip or lower `minimum_size`. |

---

## 4. Top-10 "do these first" ranking

Impact-driven, with effort (S = ~1 day, M = ~1 week, L = multi-week) and a mapped gap id.

| # | Action | Effort | Gap |
|---|---|---|---|
| 1 | **Make the workspace chat reply in real language + echo the user's request.** Minimum viable: backend returns `"Đã áp dụng: {message} — xem lại lịch trình nhé"` and frontend renders free text; full version persists turns. Biggest feel-win per hour. | S→M | A1, A2 |
| 2 | **Add explicit budget + duration intake** (segmented controls), stop hardcoding 1M VND / trusting only the regex. | S | A4 |
| 3 | **Constraint strip + reply confirms the delta** (budget/pax/duration/style visible; "đã giảm còn ~500k/người"). | S | B6 |
| 4 | **Wire the dead typing indicator** + auto-scroll the message list. | S | M1, M2 |
| 5 | **Per-turn undo + version diff in the drawer** (client-side diff over already-fetched versions). | S | B3 |
| 6 | **Home resume list + anonymous sign-in nudge.** Reuses `/api/plans`; pure frontend. | S | B5 |
| 7 | **SSE/status streaming for refine** (reuse `finding_places`/`routing_plan` statuses) so a 10–60 s refine shows progress. | M | A3 |
| 8 | **Swap-with-3-options picker** (return ranked candidates, pick in a sheet). | M | M6 |
| 9 | **Notifications at booking/comments transitions + unread count** (event emission before any push channel). | M | B2, M13 |
| 10 | **Skeletons + retry actions + toasts** across history/plan/explore; add `loading.tsx` boundaries. | M | M3, M11 |

**Ordering rationale:** 1–5 are cheap (S) and attack the two Blocker pillars (conversation + explicit constraints) that the layla research (report 03 §3) shows are the actual product identity; 7 is the first backend lift that makes the chat feel live; 8–10 deliver agency, reach, and polish. Deferred deliberately: direct itinerary editing (B4, M effort), push channel (B2), traveler profile (M14), long-running job model (M9) — all M/L, later waves.

---

## 5. Cross-report contradictions resolved

1. **OpenGraph/share-card (report 04 §6.2 vs code).** Report 04 lists "no … OpenGraph tags on `/plan/{token}`" as a *done-looks-like*. **Code shows OG + Twitter `summary_large_image` tags already exist** with a static `/og.png` (`plan/[token]/page.tsx:6`; file exists). **Resolution:** the real gap is *per-trip dynamic* cards (L2), not missing OG plumbing. Reports 01/02 did not flag OG at all — minor miss.

2. **Generate-phase "streaming" is thinner than reports imply.** Reports 01 ("single best real-time moment") and 04 §2.6 praise the creation SSE. **Code shows both status events are yielded back-to-back *before* the pipeline runs** (`plans.py:119-120` then `to_thread(build_plan)`), followed by one atomic `result` (`plans.py:127`). So generation "streams" status text but no incremental plan; refine (A3) streams nothing. **Resolution:** keep the praise, but the whole streaming story is 2 hardcoded strings + 1 blob; the layla gap is even larger than 01 states.

3. **Currency preference reach (report 01 G24 vs report 04 §4.2).** 01 says preferences flow "solidly" and cites `PlanView.tsx:94` — that's **unit/temperature only**; plan money is hardcoded VND (`PlanView.tsx:81`). 04 is correct that currency never reaches the plan. **Resolution:** 04's version stands (L3); 01's "solid" is accurate only for units.

4. **Reminder semantics (report 02 Gap 3/11 vs store code).** 02 flagged the calendar-day timing. Verified: the **postgres** path uses `BETWEEN current_date AND current_date+1` (`postgres_store.py:621`), while the **memory** store uses a correct `now ≤ departure ≤ now+24h` window (`store.py:415-431`). **Resolution:** 02 is right for production; the two stores disagree — worth a code-comment fix (L11).

5. **`reminders.py` dead code (report 02 Gap 3).** Confirmed by grep: `due_in_app_reminders` is definition-only; both stores implement `claim_due_reminders` and `materialize_due_reminders` directly. **Resolution:** confirmed dead; fix path = delete or route through it (L11).

6. **Severity of offline gap (report 01 G31 "Medium" vs report 04 §5 silent-strand "Low/Med").** Both agree on the fact (write-no-read). No contradiction — 01's Medium severity for the *broken offline claim* is consistent with 04's separate strand issue. **Resolution:** keep 01's Medium (M7); 04's strand issue folds into B5.

7. **Layla research boundaries (report 03).** Streaming, interrupt-mid-generation, co-editing, and 16-language claims are **unverified/contested** per 03's own §2 legend. This synthesis therefore does **not** treat "layla streams tokens" as load-bearing — only that layla is *chat-native with questions-first generation and multi-turn editing*, which is multiply sourced.

---

## 6. Claims needing follow-up verification (≤6)

Single-sourced or unverified in my pass:

1. **Postgres OCC clause** — report 02 cites `postgres_store.py:132-141` (`WHERE ma_chia_se=%s AND phien_ban=%s RETURNING phien_ban`). I verified the MemoryStore path (`store.py:82-84`) and the router 409s, but not those exact postgres lines.
2. **Postgres anonymous-merge mechanics** — `upsert_user_and_claim` / `claim_session` ownership scoping (`postgres_store.py:515-543`); I verified the function names + `auth.py:72-74` call, not the merge body / preference-shadowing at `postgres_store.py:457-465`.
3. **`multicity.py:19-85`** — claim that up to N flight/hotel/OSRM calls run inline per request (report 02 Gap 6).
4. **`rate_limit.py` Redis Lua fail-closed semantics + `record_ai_usage` budget UPSERT** (`postgres_store.py:79-90`) — report 02 Gap 7, not re-read.
5. **`planner.py` AI fallback** (`AI_FALLBACK_NOTE` at `planner.py:30-33,583-590`) — the "silent downgrade to deterministic plan" claim rests on report 02 reading only.
6. **Runtime behaviors** (not executable in this pass): GZip buffering of SSE frames (`main.py:82`), Starlette generator-cancel on SSE disconnect, and cross-worker reminder dedup. Report 02 also cites `test_api.py:203-309` and `alembic/versions/0001_initial.sql:110-120` unverified here.

---

## 7. Combined confidence + ground-truth tally

**Combined confidence: 8/10.**

The four lanes scored 7, 9, 7, 8. The synthesis capped it down: every code-level load-bearing claim I attempted to verify **was verified against actual source** in this pass (no contradiction found between claim and code except the OG correction, which I resolved). The cap comes from (a) the six follow-up items above, (b) impact/severity/effort ranking is model judgment, (c) two framework-behavior claims are inference not execution, and (d) report 03's external layla claims carry their own unverified set. 8/10 is the honest ceiling given ~0.84 verified-ratio.

**Ground-truth tally (load-bearing conclusions):**
- **Verified against source by direct read/grep in this synthesis pass: 38.**
  - Frontend: canned-reply contract (`PlanView.tsx:26,102,122` + `workspace-translations.ts`), conversation reset-on-reload + append-only (`:76,92`), no retry in workspace (`:86`), no optimistic updates (`:101-109`), regenerate body has no version + drops `swipeSuccess` (`:109`), input disabled while busy (`:110`), budget/location hardcode + regex duration (`Planner.tsx:65-72,105,108`), dead duration keys (`LocaleProvider.tsx:75+`) + test asserting absence (`i18n.test.mjs:255`), dead typing CSS (`globals.css:22`), `overflow:auto` messages with no scroll (`globals.css:22`), offline-plan write-no-read (`PlanView.tsx:97` + grep), SW GET-only cache (`sw.js:16-26`), VND-hardcoded money (`PlanView.tsx:81`), OG tags with static image (`plan/[token]/page.tsx:6`), featured cards focus-only (`page.tsx:54,103`), stale auth nav (`Navigation.tsx:20-24`), map click-only markers (`MapView.tsx:37-45`), no boundary files (glob), explore expiry→`searchFailed` (`explore/page.tsx:38`), history bare list (`history/page.tsx:55`), settings inline delete with typed phrase (`settings/page.tsx:35,37`), `dataNotice` untranslated in all locales (`LocaleProvider.tsx`).
  - Backend: 500-char truncation (`plans.py:433`), regex intents (`plans.py:30-40,435-453`), canned `tra_loi`/`tra_loi_key` (`plans.py:484-485,501-502`), SSE only-in-generate + 2 statuses + atomic result (`plans.py:118-131`), no `stream:true` anywhere (`ai.py:143,235,316`), OCC 409 (`store.py:82-84`, `plans.py:381-382,494-495`), nonce `setdefault` race (`store.py:411-413`), regenerate no expected-version (`schemas.py:54-57`), `reserve_cost(0.0)` (`plans.py:114,410`), 2× zero-delay retry + breaker 3/5min/120s (`ai.py:12-38,141`), auth 7-day no-refresh (`auth.py:27`) + merge by client `ma_phien` (`auth.py:72-74`), Vietnamese `detail` errors + no global handler (routers + `main.py`), version list full-plan (`store.py:93-94`), notifications single-type DB inbox + read-materialize (`plans.py:62-70`, `postgres_store.py:617-634`), calendar-day reminder window (`postgres_store.py:621`), dead `reminders.py` (grep), no WebSocket/scrollIntoView/onLine (greps), GZip middleware (`main.py:82`), `why`-field dropped by `_apply_copy` (`ai.py:54-71,214-228`), support transitions emit no notification (`support.py:31-45`).
- **Model judgment / external / not re-verified here: 7.** Severity–effort–priority weighting across §3–§4; layla.ai feature baseline (report 03, own tally: 41 verified / 8 contested); GZip-SSE buffering & disconnect-cancel behavior (inference, not executed); and the six follow-up items in §6.
- **Correction applied to source lane output:** 1 (report 04 §6.2 OG claim — narrowed to "dynamic card missing").

**Bottom line for the product owner:** do §4 items 1–5 first (~1–1.5 weeks); they convert the command bar into a conversation and remove the silent-defaults trust killer — without touching the backend's real strengths (verified catalog, routing, OCC, rate limits, exports). Items 7–10 are the first M-size lifts that make it feel live and reach the user.
