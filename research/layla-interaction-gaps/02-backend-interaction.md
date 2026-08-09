# 02 — Backend User-Interaction Audit (lane: BACKEND USER-INTERACTION)

Auditor lane: backend interaction support. Scope: FastAPI backend in `D:\Code\aithucchien\ai_travel\backend` — routers, pipeline, services, store, schema, config, tests. Question being answered: **what is missing in the backend's user-interaction support relative to a conversational AI trip planner (layla.ai)?** Frontend components and layla.ai feature research are handled by other lanes; this report stays strictly backend.

All `file:line` references are relative to `backend/`.

---

## 1. Current backend interaction surface

The backend is a FastAPI app (`app/main.py`) with routers under `/api`: `plans`, `auth`, `inventory`, `roadtrip`, `support`, `admin`. Storage is `MemoryStore` (local dev) or `PostgresStore` (production), with a Redis fixed-window rate limiter in production (`app/services/rate_limit.py`). The AI pipeline is a hybrid: a deterministic, validated scheduler in `app/pipeline/planner.py` with LLM "copywriting" and place-selection injected through `app/services/ai.py` (DeepSeek/Groq OpenAI-compatible adapter, validated JSON output, circuit breaker, cost accounting).

The interaction surface today, in rough terms:

| Interaction | Endpoint | Streaming | State persisted |
|---|---|---|---|
| Initial plan | `POST /api/plan/generate` (`plans.py:89`) | SSE with 2 coarse status events + 1 full-plan `result` event | plan + request, version 1 |
| Get plan | `GET /api/plans/{token}` (`plans.py:134`) | no | read-only |
| Refine by chat | `POST /api/plans/{token}/refine` (`plans.py:457`) | **none — synchronous JSON** | new version, `request.context` rewritten |
| Swipe a place | `PATCH /api/plans/{token}/swipe` (`plans.py:310`) | none | new version |
| Regenerate | `POST /api/plans/{token}/regenerate` (`plans.py:390`) | none | new version |
| Versions | `GET/POST .../versions` (`plans.py:506`, `519`) | none | version table |
| Comments | `GET/POST/PATCH /api/plans/{token}/comments*` (`plans.py:251-292`) | none | `binh_luan` |
| Feedback | `POST /api/plans/{token}/feedback` (`plans.py:226`) | none | `phan_hoi_chuyen_di` |
| Notifications | `GET /api/notifications`, `PATCH /api/notifications/{id}` (`plans.py:62-86`) | none — polled | `thong_bao` |
| Export | `.ics` / `.pdf` (`plans.py:163`, `210`) | none | — |
| Inventory search | `/api/inventory/*/search` (`inventory.py:29-78`) | none | `inventory_snapshot` |
| Booking assistance | `POST /api/inventory/booking-assistance` (`inventory.py:81`) | none (202, async in *spirit* only) | `yeu_cau_ho_tro_dat` |
| Roadtrip | `/api/roadtrip/route|plan` (`roadtrip.py:30-44`) | none | none (except snapshots via multicity) |
| Auth | `/api/auth/oauth|me|preferences|account` (`auth.py:58-130`) | none | `nguoi_dung`, `consent` |

The **only** streaming endpoint in the entire backend is `POST /api/plan/generate`. There are **no WebSockets, no token streams, no SSE channels for anything other than plan generation, no background-task job system, no notification push channel, and no chat-message store.** Those are the headline gaps. The rest of this report details each focus area.

---

## 2. Gaps ranked by severity

Findings are tagged **(A) exists-but-shallow** or **(B) genuinely absent**. Severity is the impact on a layla-like conversational experience, not on the current shipped product's correctness.

### GAP 1 — No server-side conversation memory; "chat" is a truncated 500-char context blob (Blocker) — (B) genuinely absent

The refine flow is the conversational turn: `POST /api/plans/{token}/refine` (`plans.py:457`) merges the incoming message into a single `context` string and truncates to the last 500 chars:

```
plans.py:433   updates: dict = {"context": f"{current.context}; {message}"[-500:]}
```

Consequences:
- Multi-turn conversations silently lose early context past 500 characters; the AI prompt (`services/ai.py:136`, `ai.py:218` — `"ngu_canh_nguoi_dung": context`) is just that blob.
- There is **no `conversation_id`, no message/turn table, no transcript**. The client cannot resume a conversation, edit an earlier turn, or see what the assistant said in turn N. Versions (`phien_ban_ke_hoach`) snapshot *plans*, not *dialogue*.
- The assistant's reply text (`tra_loi`) is generated ad-hoc and returned in the response (`plans.py:484-486`, `501-503`) but **never persisted** — a reload has no memory of what the assistant offered.
- Intent extraction is regex-only (`plans.py:435-453`: people count, budget, "cheaper", "shorter route", "more cafe"; `SWAP_INTENT` at `plans.py:30`). Anything else is dropped on the floor. A layla-like assistant needs a real NLU + structured intent + follow-up-question state machine; today there is a hardcoded canned reply (`tra_loi_key: "assistantWelcome"`).

This is the single most fundamental gap: **the backend does not model a conversation, so it cannot power a conversational planner.** Blocker for the product goal.

### GAP 2 — No token streaming; AI responses are returned whole (High) — (B) genuinely absent

- The AI adapter always uses non-streaming `client.post("/chat/completions", ...)` with `response_format: {"type": "json_object"}` — `services/ai.py:143`, `ai.py:235`, `ai.py:316`. There is no `"stream": true`, no token deltas, no partial JSON.
- `POST /api/plan/generate` does use SSE (`plans.py:118-131`) but emits only two hardcoded status events (`"finding_places"`, `"routing_plan"`) followed by **one** `result` event containing the entire plan (`plans.py:127`). No per-step plan construction, no incremental itinerary.
- `refine`, `swipe`, `regenerate`, `roadtrip`, and all inventory endpoints return **plain synchronous JSON** (`plans.py:457` is a `def` returning a dict; `plans.py:390`, `310` likewise). The client waits the full LLM latency (~2-3 sequential LLM calls, worst case ~30-60 s) staring at a spinner.
- For a layla-like experience the entire interaction is "watch the assistant work": token deltas in chat, incremental plan building, per-day/per-slot events. None of that is possible today; the server-side "assistant is thinking" state machine is exactly two status strings. **(A)** for coarse SSE status, **(B)** for anything granular.

### GAP 3 — No real-time push channel; notifications and plan updates are poll-only (High) — (B) genuinely absent

- No WebSocket anywhere (grep over `app/` finds zero `websocket` usage). No SSE endpoints besides generate. No push/email/webhook/FCM channel.
- Notifications: delivered into a DB inbox (`thong_bao`, `alembic/versions/0001_initial.sql:110-120`) by (a) an hourly in-process maintenance task (`main.py:63-70`) and (b) a **lazy materialization on read** — `GET /api/notifications` calls `store.materialize_due_reminders()` before returning (`plans.py:70`). Clients must poll `GET /api/notifications` (`plans.py:62`) with no server-initiated signal.
- Plan updates in one device are invisible to other devices until they poll `GET /api/plans` (`plans.py:295`) or `GET /api/plans/{token}` (`plans.py:134`). Multi-device sync relies on client polling + optimistic-concurrency 409s (see Gap 5), not on any push.
- The worker is a single `asyncio.create_task` inside the app process (`main.py:72`). With multiple uvicorn workers each runs its own copy (dedup is safe in Postgres via `FOR UPDATE SKIP LOCKED` / `ON CONFLICT DO NOTHING`, `postgres_store.py:599-634`), but there is no dedicated worker process, no queue, and no channel out to the user.
- `app/services/reminders.py` exists (`due_in_app_reminders`, `reminders.py:10-17`) but is **dead code — not imported anywhere** (grep shows definition only). Its only purpose, "claim and return due reminders", is duplicated by `materialize_due_reminders` which skips the service layer entirely.

### GAP 4 — Notification semantics are shallow (High) — (A) exists-but-shallow

- Read/unread exists: `da_doc` boolean (`alembic:115`), `PATCH /api/notifications/{id}` (`plans.py:74`, `postgres_store.py:654-670`). Ownership scoping for anonymous-vs-user is correct (`postgres_store.py:636-652`).
- **Missing:** unread-count endpoint; bulk mark-all-read; notification types beyond `trip_24h` (`postgres_store.py:627`); per-user notification preferences/digest; any delivery confirmation or retry. No notification is ever generated for plan refinement, comments on a shared plan, booking-request status changes (`support.py` transitions — a human picks up a booking but nothing tells the user), or inventory snapshot expiry.
- The booking queue has a rich state machine (`support.py:10`, `postgres_store.py:377-407`, transitions `requested→reviewing→needs_customer→handed_off`) but **no user-facing event is emitted at any transition** — the user learns the status only by asking/polling. For a "concierge" feel this is the exact gap.

### GAP 5 — Concurrency control exists and is solid, but not exposed as a proper optimistic-concurrency contract (Medium) — (A) exists, shallow contract

The good news first:
- Optimistic concurrency on plan mutation is real. `store.update(item, expected_version, ...)` raises `VERSION_CONFLICT` when the stored version differs: `MemoryStore` (`store.py:82-84`), `PostgresStore` via `WHERE ma_chia_se=%s AND phien_ban=%s RETURNING phien_ban` (`postgres_store.py:132-141`). Routers translate it to HTTP 409 `"Kế hoạch vừa được cập nhật, vui lòng tải lại"` (`plans.py:381-382`, `418-419`, `494-495`, `538-539`). Tested (`test_api.py:272-309` — stale restore returns 409).
- Idempotency: nonce-based dedup for generate and regenerate, per-session scoped (`plans.py:92-106`, `124-125`, `401-405`, `422-426`; persisted in `idempotency_key`, `alembic:46-49`). Tested (`test_api.py:203-269`).

But the contract is shallow:
- Version numbers are passed as **body fields** (`RefineRequest.phien_ban`, `SwipeRequest.phien_ban`, `RestoreVersionRequest.phien_ban_hien_tai`, `schemas.py:50`, `61`, `73`) — not HTTP `ETag`/`If-Match`. Clients get 409s but no `ETag` header, no documented precondition mechanics. `GET /api/plans/{token}` returns `phien_ban` in the body (`plans.py:139`) instead of an `ETag` (`get_plan` is a plain `def`, `plans.py:134-139`).
- `regenerate` **cannot express an expected version at all** (`RegenerateRequest` is `{ma_phien, nonce}`, `schemas.py:54-57`); it blindly passes the `item.version` captured at read time (`plans.py:417`). Two racing regenerates are still caught by OCC (one 409s), but the client has no way to say "only if still v1".
- Idempotency under **concurrency** is race-prone: two parallel requests with the same generate-nonce both pass the pre-check (`plans.py:94` `get_nonce` returns None for both), both run `build_plan` (both billed), then `set_nonce`'s `setdefault` (`store.py:411-413`) lets one win — the loser's plan is saved and **billed but orphaned**. The same applies to regenerate (nonce is set only after `store.update`, `plans.py:422`). Dedup works for sequential retries, not for true concurrent double-submit. Cost/abuse relevant.

### GAP 6 — Long-running work is done inside the request; no task/status/job model (High) — (A) generate uses SSE, (B) everything else blocking

- Generate: `await to_thread(build_plan, payload)` runs inside the SSE generator (`plans.py:122`) — the client holds the connection open, there is no job id, no `/status` endpoint, no reconnection story (a dropped connection kills the work from the client's view; Starlette cancels the generator on disconnect, so the plan is lost unless the client retries).
- Refine/regenerate/swipe/multicity/roadtrip are **fully synchronous request/response** (`plans.py:457`, `390`, `310`; `multicity.py:19-85` makes up to N flight+hotel+OSRM calls inline). The HTTP request thread blocks for the entire upstream duration.
- Timeout: httpx client `timeout=httpx.Timeout(10, connect=2)` (`ai.py:108`). A slow LLM hits 10 s → caught → deterministic fallback (`planner.py:583-590`, `AI_FALLBACK_NOTE` at `planner.py:30-33`). This is good resilience but means users get silently downgraded plans and the LLM work is truncated rather than queued/retried with backoff.
- **No task queue** (no Celery/RQ/arq/Redis Streams), **no status object, no webhook, no resume.** For layla-like long planning jobs (multi-city, bookings, image generation) this is a hard constraint.

### GAP 7 — AI failure handling has retry but no backoff, no queue, no Retry-After (Medium) — (A) exists-but-shallow

- `OpenAICompatibleAIAdapter` retries each call **2× with zero delay** (`for _attempt in range(2)` at `ai.py:141`, `233`, `314`; no sleep between attempts). No exponential backoff, no jitter — a degraded provider gets hammered.
- Circuit breaker exists and is sound: 3 failures in 5 min opens for 120 s (`ai.py:12-38`), diagnostics exposed via `/api/admin/providers/diagnostics` (`admin.py:93-142`). Good.
- Rate limiting is genuinely strong: per-session + per-IP fixed windows for generate (`plans.py:108-112`), regenerate (`plans.py:407-408`), refine (`plans.py:467-468`), swipe (`plans.py:321-322`), comments (`plans.py:266-267`), inventory (`inventory.py:20-26`), roadtrip (`roadtrip.py:12-27`). Redis Lua is atomic and fail-closed (`rate_limit.py:63-90`); the memory fallback is fail-closed too (`rate_limit.py:16-18`). Well tested (`test_api.py:46-111`, `test_rate_limit.py`).
- **Missing on 429:** `Retry-After` header, per-endpoint burst allowance, and a **global in-flight concurrency cap** for LLM calls. There is no throttle on `/api/auth/oauth` (`auth.py:58-80`) or on `support`/`admin` beyond token auth.
- Budget control: endpoints call `store.reserve_cost(0.0, ...)` — **reserving zero** (`plans.py:114`, `plans.py:410`). The real guard is the atomic conditional UPSERT inside `record_ai_usage` (`postgres_store.py:79-90`), which rejects over-budget inserts but does so **after** the LLM call already ran — no pre-flight rejection, no queue, so a burst can spend up to N parallel calls of budget before any is charged.

### GAP 8 — Auth UX: no refresh, no logout/revocation, merge is by client-claimed identity (High) — (A) exists-but-shallow

- Google OAuth + JWT: `auth.py:47-80`. Token lifetime is fixed **7 days** (`auth.py:27`). **No refresh endpoint, no sliding expiry, no `/logout`**, no server-side token revocation list. Expired/invalid tokens both collapse to `resolve_user` → `None` → 401 (`auth.py:32-44`), so the client cannot distinguish "expired, please refresh" from "invalid, re-authenticate". Multi-device logout is impossible — killing one device means deleting the account (`auth.py:116-130`).
- Account deletion does effectively revoke in production because `resolve_user` re-reads the user row (`auth.py:44`; `PostgresStore.delete_user_data` removes it, `postgres_store.py:438-455`), and local mode pops `DEMO_USERS` (`auth.py:128-130`). But there's no *session* concept — just stateless JWTs.
- Anonymous→authenticated merge: `upsert_user_and_claim` claims **every plan whose `ma_phien` matches the client-supplied session id** (`postgres_store.py:523-543`, `claim_session` `postgres_store.py:515-521`). Correct in the happy path (tested, `test_api.py:325-342`), but the session id is a client-provided string (`OAuthRequest.ma_phien`, `schemas.py:299-304`) with **no proof-of-possession** — if an attacker learns a victim's session id they can claim the victim's anonymous plans. Merge is also one-directional and irreversible; no un-merge, no consent flow at merge time beyond the single checkbox.
- Preferences exist (`auth.py:91-113`) but are per-session-or-user with no merge/conflict resolution when both exist (an anonymous session's prefs are silently shadowed after login — `postgres_store.py:457-465`).

### GAP 9 — Error contract is Vietnamese human strings; no codes, i18n keys, or global handler (Medium) — (A) exists-but-shallow

- All errors are `HTTPException(status, detail=<Vietnamese string>)` (e.g. `plans.py:112`, `plans.py:138`, `plans.py:382`, `inventory.py:26`, `roadtrip.py:27`, `support.py:43`). Status codes are meaningful (401/403/404/409/413/422/429/503), and Pydantic yields 422 with field-level detail (`schemas.py` validators).
- **Missing:** a machine-readable error `code` (only the SSE error event has `"code": "503"`, `plans.py:129`), i18n keys (the one key that exists is a *success* key — `tra_loi_key: "swipeSuccess"/"assistantWelcome"`, `plans.py:485`, `502`), `Retry-After`, and an `ETag` on reads. The frontend must string-match Vietnamese text to localize — a real anti-pattern for an app shipping 19 locales.
- **No global exception handler** (grep for `exception_handler`/`add_exception` returns nothing). Unhandled exceptions surface Starlette's bare 500 with no request-id correlation beyond the `X-Request-ID` header (`main.py:103-106`). No RFC 7807/problem-details envelope.
- Error delivery is **inconsistent across the generate flow**: budget failures return an HTTP 503 *before* the SSE stream (`plans.py:113-116`), while pipeline failures arrive as an SSE `error` event inside the stream (`plans.py:128-129`). Clients must handle two different error shapes for one endpoint.

### GAP 10 — Versioning/undo is solid but lacks diff and granular undo (Medium) — (A) exists, features shallow

- Full version history is implemented: `GET /api/plans/{token}/versions` (`plans.py:506`), snapshot-per-version storage (`phien_ban_ke_hoach`, `alembic:56-61`), and non-destructive restore that creates a *new* version (`plans.py:519-540`, `store.update` appends, `store.py:85-91`) — good undo semantics. Tested (`test_api.py:272-309`).
- **Missing:** a diff endpoint (compare vN vs vM — which slots changed, cost delta); restore-by-reason browsing is only via `ly_do` strings (`postgres_store.py:154-158`); no "undo last action" shortcut (client must fetch versions and restore); `list_versions` returns the **full plan JSON for every version** (`store.py:93-94`, `postgres_store.py:152-159`) — a plan with 10 refinements ships 10× the plan payload on every version read. No pagination/ETag on the versions list.

### GAP 11 — Minor/note-level findings

- **SSE composition with GZip middleware** (`main.py:82`, `GZipMiddleware, minimum_size=1000`): Starlette's GZip buffers streaming responses, which can delay/buffer SSE frames and defeat real-time feel. Not proven broken in tests, but a real risk for any future streaming channel. (Note)
- **SSE `result` event carries the entire plan in one line** (`plans.py:127`) — no incremental plan delivery, so even the one streaming endpoint isn't "live". (Note)
- **`reminders.py` is dead code** — `due_in_app_reminders` is never imported; the reminder path bypasses the service layer (`main.py:67`, `plans.py:70`). (Note)
- **Notification timing**: `materialize_due_reminders` fires when `ngay_di BETWEEN current_date AND current_date+1` (`postgres_store.py:621`) — i.e., calendar-day-based, not "within 24 h of now" as the 24-h reminder claims; a departure at 23:59 tomorrow fires ~24 h early. (Note)
- **No SSRF/markup concern, but no HTML sanitization beyond `<>` stripping** for comments/refine text (`schemas.py:41-45`, `81-84`, `226-227`) — out of interaction scope but worth flagging to security lane. (Note)

---

## 3. Top 10 backend capabilities needed for a layla-like interactive experience

Ranked by leverage (not by effort):

1. **Conversation store** — a `conversation` + `message` (turn) model with `conversation_id`, roles, timestamps, and the assistant's reply text persisted per turn; refine appends to the transcript instead of rewriting a 500-char blob (`plans.py:433`). Everything else builds on this.
2. **Token streaming** for chat turns — an SSE/`stream: true` path in `ai.py` that fans out LLM deltas for refine/regenerate/swipe (not just generate), plus granular server-side "assistant is thinking" phases (planning → routing → writing copy → validating) as SSE status events, replacing the two hardcoded strings (`plans.py:119-120`).
3. **Incremental plan delivery** — emit per-day/per-slot `result` events during generate so the UI renders the itinerary as it is built (`plans.py:118-131`), not one atomic blob at the end.
4. **A push channel** — WebSocket (or SSE + `Last-Event-ID` replay) for notifications, shared-plan comments, booking-request status transitions (`support.py:31-44`), and multi-device plan updates, backed by a Postgres `LISTEN/NOTIFY` or Redis pub/sub fan-out from the store layer.
5. **Long-running job model** — a task queue (job id + status endpoint + webhook) so multi-city plans (`multicity.py:19-85`), bookings, and LLM assembly can run outside the request and be resumed after a disconnect; keep SSE only for the live subscribe phase.
6. **Background LLM worker with backoff + queue + concurrency cap** — replace the zero-delay 2× retry (`ai.py:141,233,314`) with exponential backoff/jitter, a bounded queue, and a global in-flight LLM limiter; add `Retry-After` on 429s and pre-flight (non-zero) budget reservation (`plans.py:114`).
7. **Structured, i18n'd error contract** — every error carries a stable `code` + i18n key + optional `params`, plus a global exception handler returning problem-details JSON with request-id correlation; use `ETag`/`If-Match` for plan reads/writes instead of body-embedded version fields.
8. **Conversational turn capability** — server-side intent parsing with follow-up-question state (missing budget? ambiguous "swap" target? `plans.py:469-471` asks but can't persist the pending question), and a "no-op reply" path where the assistant answers conversationally without mutating the plan.
9. **Notification delivery matrix** — in addition to the DB inbox: email/webhook/FCM adapter interface, unread-count + bulk-read endpoints, and event emission at every user-relevant state change (comment, refine, booking status, snapshot expiry).
10. **Auth UX completion** — refresh-token endpoint, sliding expiry, logout with server-side revocation, merge by verified identity (server-issued session cookie/JTI) instead of a client-supplied `ma_phien` string (`postgres_store.py:515-543`), and preferences merge at login.

---

## 4. Executive summary (≈200 words) + confidence + ground truth

**Summary.** The backend is a competent, defensive API around a deterministic Hanoi planner with validated LLM copywriting — but it is **not yet a conversational AI trip planner**. Its only streaming surface is `POST /api/plan/generate`, and even that emits two coarse status events and one atomic plan blob; `refine` — the actual chat turn — is synchronous JSON, runs fully inside the request with no job/status model, and rewrites a single 500-char context string instead of a conversation. There is no WebSocket/push channel, so notifications are a polled DB inbox hydrated by an hourly in-process loop, booking-status changes never reach the user, and multi-device sync is client polling rescued by solid optimistic-concurrency (body-embedded version numbers, not `ETag`). Errors are Vietnamese `detail` strings with no codes/i18n keys and no global handler. Auth has no refresh or logout, and anonymous-merge trusts a client-supplied session id. Rate limiting, circuit breaking, versioning, nonce idempotency, and fail-closed providers are genuine strengths. **The top priorities are: a persisted conversation model, token + incremental streaming, a push channel, a background job model, and a structured error contract.**

**Confidence: 9/10.** Code-verified findings: 24. Judgment-based items (severity assignment, impact framing, layla-gap selection): 6. No code was modified; runtime behavior (GZip/SSE buffering, multi-worker reminder timing) inferred from code, not executed.

**Ground-truth tally:** verified by direct code reading — SSE-only generate, absent WebSockets, absent token streaming, absent conversation store, 500-char context truncation, OCC via version columns, nonce idempotency, hourly reminder worker, DB-only notifications, no diff endpoint, zero-delay LLM retry, no refresh/logout, merge by client session id, no global exception handler, dead `reminders.py`, zero-cost budget reserve.
