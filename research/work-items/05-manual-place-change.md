# Work Item 05 — Manual Place-Change Feature ("Đổi địa điểm thủ công")

**Lane:** Manual place-change capability (Chức năng đổi địa điểm nên cho thêm người dùng tự đổi thủ công)
**Monorepo:** `D:\Code\aithucchien\ai_travel` (FastAPI `backend/` + Next.js `frontend/`)
**Date:** 2026-08-11 — Research only, no code modified.

---

## 1. Bottom line up front

The manual replace feature **already exists and is functionally complete** for the "replace slot X with a chosen place" scenario. It was built and shipped across the commit series `b142651` ("feat: add itinerary place change and delete actions"), `17a6f9b` ("feat: refine itinerary place replacement popup"), `ab647de`, `8fc15b1`, `1ebf01b`, `4d3b881` (styling/clipping/close-button polish). A user *can* today, per slot:

1. Click **"Thay đổi"** (change-place, `PlanView.tsx:236-254`) and pick **"AI tự động chọn"** → server ranks a similar replacement (`plans.py:462-465` via `_replacement_rank` `plans.py:408-417`).
2. Pick **"Bạn muốn thay thế bằng địa điểm nào?"** (`chooseReplacement`, `PlanView.tsx:286-295`) → search box with live suggestions from the catalog (`GET /replacement-candidates`, `plans.py:524-544`), debounced 300 ms, min 2 chars (`PlanView.tsx:143-165`). Clicking a suggestion submits it as an explicit candidate (`PlanView.tsx:320-334`).
3. Type a **free-text place name** (submit the search form, `PlanView.tsx:299-302`) → server verifies via OSM/Nominatim (`osm_verify.py:121-202`), and if outside the catalog, AI-estimates hours/cost (`plans.py:448-452`, `ai.py:115-146`), then validates eligibility and applies.
4. **Xóa** a stop with a confirm popover (`PlanView.tsx:271`), independent of replace.

So the user's request "nên cho thêm người dùng tự đổi thủ công" is very likely **not** a feature that is entirely missing — it's a *discoverability + power* gap. The two most likely readings:

- The user didn't realize manual replace already exists (discoverability: the popup is a hidden two-step interaction; there is no persistent "edit mode" or visible affordance per slot beyond a small button; `PlanView.tsx:236`).
- The user wants **more powerful manual control** that genuinely does not exist today: **reordering stops**, **swapping two existing slots**, **picking any legal candidate with a visible reason**, and **clear rejection feedback** when a chosen place fails eligibility.

The rest of this document is a verified gap analysis and a scoped, MVP-feasible delta plan (Tier 0/1/2/3). **The gap is not "build manual replace" — it is "make manual control complete, explainable, and reachable."**

---

## 2. What exists today (verified end-to-end)

### 2.1 Backend — the `swipe` (replace) endpoint

- Route: `PATCH /api/plans/{token}/swipe` → `plans.py:420-521`.
- Authorization: `owner(item, x_session_id or payload.ma_phien, authorization)` (`plans.py:431`) — denies shared, read-only links with 403 (`owner` helper `plans.py:74-79`). Verified by `test_api.py:124`.
- Rate limit: `swipe:{session}` **20/hour** (`plans.py:432`), same limiter mechanics as refine/delete (`rate_limit.py:16-27`).
- Payload schema `SwipeRequest` (`schemas.py:48-53`): `diem_bi_loai` (id of slot to replace, required), **either** `dia_diem_thay_the` (explicit catalog id) **or** `ten_dia_diem_thay_the` (free text) — mutually exclusive, enforced `plans.py:434-435`, plus optimistic-concurrency `phien_ban`.

**What the replace endpoint accepts today:**
- A catalog **place id** (`dia_diem_thay_the`) → validated against the eligible candidate set (`plans.py:457-460`). Unknown/ineligible id → 422 `"Địa điểm thay thế không phù hợp với khung giờ hoặc lịch trình"` (`plans.py:460`, verified by `test_api.py:220-221` `test_explicit_replacement_rejects_unknown_id`).
- **Free text** (`ten_dia_diem_thay_the`) → `verify_place_name` (`plans.py:443`), ambiguity-safe (only a unique OSM row resolves; `osm_verify.py:160-163`), far-from-Hanoi rejected (`osm_verify.py:180-181`), non-travel name hints rejected (`osm_verify.py:71-76`, actually applied in `_catalog_match` `osm_verify.py:97`). Out-of-catalog but verified places get **AI-estimated metadata** (open/close hours, cost) via `estimate_place_metadata` (`plans.py:448-451`, `ai.py:115-146`) — note this is a **paid LLM call with `store.record_ai_usage`** (`ai.py:141`), gated by the AI breaker and daily/monthly budget (`ai.py:136 condition, `store.py:43-50`).
- **Neither** → server auto-picks the best-ranked candidate (`plans.py:461-465`).

**Eligibility filter (`_replacement_candidates`, `plans.py:360-405`) — the full constraint set a manual candidate must pass:**
1. Slot being replaced must exist exactly once in the plan (`plans.py:361-364`).
2. Candidate must not already be used in the plan, by id or by folded name (`plans.py:386-387`).
3. Candidate must not be within ~10⁻⁷ lat/lng² (~1 m) of any used place — nucleus/duplicate guard (`plans.py:388-389`).
4. Opening hours of candidate must cover the *existing* slot time window (`plans.py:392-393`), evaluated with the same `_effective_hours` used by the planner (`planner.py:755-764`).
5. Travel time to the *previous* slot and to the *next* slot must fit the existing gaps (`plans.py:394-401`) using `travel_minutes` (`routing.py:54-59`).
6. **Budget**: `(plan.total – removed.cost + candidate.cost × people) // people ≤ ngân sách` (`plans.py:402-403`).
7. Extra: `same_kind` flag (unused by the API today — `swipe`/`candidates` both pass `same_kind=False`; the "AI similar" tie is only in the auto-rank, not the filter; see §6.4).

**Eligible list is re-validated** after mutation via `validate_plan` (`plans.py:506-510` → `planner.py:1393-1448`), which re-checks id/name/coordinate uniqueness, per-slot daily sequential times + opening hours + travel gaps, and budget.

**Versioning / optimistic concurrency:**
- `store.update(item, phien_ban, plan, request, reason)` bumps version and raises `ValueError → 409 VERSION_CONFLICT` on mismatch (`store.py:80-95`; Postgres atomic `UPDATE ... WHERE phien_ban=%s` `postgres_store.py:127-150`). Verified by `test_api.py:206-207` (stale delete → 409).
- Restore-any-version endpoint exists (`plans.py:739-760`), so every manual edit is undoable even after many steps. The frontend surfaces an "undo" button for `ver-1` (`PlanView.tsx:228`).

### 2.2 Backend — candidate search endpoint

- Route: `GET /plans/{token}/replacement-candidates?diem_bi_loai=..&q=..` → `plans.py:524-544`.
- Rate limit **60/hour** (`plans.py:536`), ownership enforced (`plans.py:535`), max 10 results (`plans.py:543`).
- It computes the **same eligibility set** (`plans.py:538`, `_replacement_candidates`), then substring-filters on folded `name kind area` (`plans.py:539-543`). Returns lightweight `{id, ten, loai, khu_vuc}` (`plans.py:544`) validated by `isReplacementCandidate` (`PlanView.tsx:34-41`).
- **Important correctness gap (§6.2):** results are returned in catalog iteration order — `_replacement_rank` is **not** applied. So the suggestion list is not ordered by suitability, unlike the auto-replace path.

### 2.3 Backend — delete endpoint

- Route: `DELETE /plans/{token}/slots` → `plans.py:547-584`, 20/hour limit (`plans.py:558`), ownership (`plans.py:557`), must be unique (`plans.py:561-565`), recomputes `tong_chi_phi` / per-person cost (`plans.py:569-574`), validates with `allow_below_minimum=True` (`plans.py:576`) so a plan may legally drop below the minimum slot count (`planner.py:1406`).
- Frontend `deleteSlot` (`PlanView.tsx:166-209`) with confirm popover (`PlanView.tsx:271`).

### 2.4 Frontend — the change popup UX

- Flow: slot card → "Thay đổi" button (`PlanView.tsx:236-254`) → portal dialog (`PlanView.tsx:273-339`) with:
  - Close button (`PlanView.tsx:280`), Escape-to-close and outside-click-to-close (`PlanView.tsx:129`), `aria-expanded`, `aria-controls`, `role="dialog"` (`PlanView.tsx:238-239, 277-279`).
  - "AI tự động chọn" button → `swipe(id)` with no args (`PlanView.tsx:281-285`).
  - "Bạn muốn thay thế bằng địa điểm nào?" → reveals search form (`PlanView.tsx:286-295`) with `role="combobox"`/`aria-autocomplete="list"` (`PlanView.tsx:312`), debounced search (`PlanView.tsx:165`), suggestions list (`PlanView.tsx:319-335`), and free-text submit (`PlanView.tsx:299-302`).
  - Focus management: auto-focus first choice (`PlanView.tsx:129`), focus returns to trigger on close (`PlanView.tsx:116`).
- Toast messaging on success/failure (`PlanView.tsx:230`), busy spinner with a single `disabled` gate (`PlanView.tsx:112`, `218`).
- **Error mapping is coarse and partly misleading (§6.1):** 404 → `replacementNotFound` ("Không thể xác minh địa điểm này tại Hà Nội"), 422 **and** 503 → `replacementInvalid` ("Địa điểm này không phù hợp với khung giờ hoặc lịch trình"), anything else → generic `actionFailed` (`PlanView.tsx:136`). 409 (version-conflict) is **not** mapped at all — it falls through to generic `actionFailed`.

### 2.5 Tests that pin this behavior (ground truth)

- `test_api.py:193-213` — full contract: candidate search → explicit replace → stale delete 409 → current delete → restore. This is the **most important existing test** for this lane.
- `test_api.py:216-221` — unknown replacement id → 422.
- `test_api.py:224-228` — `_replacement_rank` prefers tag-similarity over distance.
- `test_api.py:231-241` — free-text replace verifies + AI-estimates + labels.
- `test_api.py:124` — ownership 403. `test_api.py:128-167` — locale persistence through swipe.
- `test_api.py:170-184` — replace of a day-2 slot works (multi-day support).

---

## 3. What is missing (verified by reading code, not assuming)

| # | Capability | Status | Evidence |
|---|---|---|---|
| M1 | **Reorder stops** (move up/down, or drag) | **Missing entirely** | Slot card renders only select/change/delete actions (`PlanView.tsx:235-270`); no move affordance anywhere; backend has no reorder/move endpoint; `validate_plan` assumes time-sequential slots (`planner.py:1421-1445`) so reordering needs recompute, not just array splice. |
| M2 | **Swap two existing slots** (or reuse a place from another day/position) | **Missing** | Eligibility forbids any candidate already in the plan (`plans.py:386-387`) — a user cannot move "Văn Miếu" from Day 2 to Day 1, or swap two adjacent stops, because the replacement is always drawn from the unused catalog. |
| M3 | **Why-rejected feedback** | **Weak/misleading** | All four eligibility failures (duplicate, hours, travel, budget) collapse into 422 with one generic string (`plans.py:460`) or a 404 "no eligible candidates" (`plans.py:455-456`) that the frontend maps to **"not verified in Hanoi"** (`PlanView.tsx:136`, `workspace-translations.ts:51`). Budget overflow is never surfaced; the option is silently absent from suggestions too. |
| M4 | **Search suggestions ranked & comprehensive** | Partial | Suggestions unranked by suitability (§6.2) and capped at 10 (`plans.py:543`); out-of-catalog places are invisible in suggestions (only free-text submission discovers them, `plans.py:438-452`). No "reason label" next to each suggestion. |
| M5 | **Constraint relaxation / forced choice** | Missing by design | No way for a user to explicitly pick a place that slightly exceeds budget or hours, even with a warning — eligibility is a hard gate (`plans.py:384-404`). See §6.3. |
| M6 | **Manual edits survive chat refine** | **No** | `refine()` calls `build_plan(refined)` fresh (`plans.py:697-716`) and **discards all manual replace/delete edits**; `regenerate()` also rebuilds from scratch with all current ids excluded (`plans.py:608-624`). No "pin" concept exists to protect a manual edit. |
| M7 | **Suggestions ↔ free-text convergence** | Gap | Search suggestions come only from the catalog (`plans.py:538-544`); the free-text path only resolves one unique OSM hit and shows it in neither the search list nor the itinerary until applied. A user typing a new, uncatalogued cafe sees **no** suggestion, then a submit round-trip that may 404/503. |
| M8 | **Persistent edit affordance / discoverability** | Weak | Change is hidden behind a per-slot "Thay đổi" button + two-level popup (`PlanView.tsx:236-295`). No visible "tap to edit", no move/drag hint, no first-visit tooltip. Given the product request, discoverability is a first-class suspect. Commit history shows this popup was already UX-polished (`17a6f9b`, `8fc15b1`, `4d3b881`), so re-skinning is not the delta — reachability and power are. |

---

## 4. Product expectations — what "edit itinerary" means in comparable travel products

External, web-fetched claims below are **marked [external]** — not verified against primary code/spec, used only as product-market signal:

1. **[external] Utrip itinerary redesign (Rachel Matthews UX case study, racheltheuxdesigner.com/case-studies/travel-itinerary):** "Because giving the user control over their itinerary was paramount, we knew drag and drop functionality was essential. To help the user optimize their schedule, we added context indicators to the drop zones — indicating whether this was a good or bad timeslot in which to move/add the item." → Users expect **move (reorder)** as a first-class gesture, and they expect the app to *tell them when a move is bad* — direct support for M3/M1 and the "reason label" idea (D1).
2. **[external] Itinerally (itinerally.com):** "Add and reorder stops. You can enter cities, towns, regions or countries. Your itinerary will follow this exact route order." → Order is user-asserted, not AI-only → M1.
3. **[external] Trip.com Trip Planner (trip.com/blog/trip-planner-tool, 2025-09-16):** "canvas-style editing, where you can rename, reorder attractions, replace and delete activities and add on notes" — **replace-in-place + reorder + delete** are the four canonical manual verbs. This app already has 3 of 4 (replace, delete, rename≈no); **the missing verb is reorder.**
4. **[external] Wanderlog / TripStone (tineo.ai, tripstone.app blog, 2026):** positioned as "manual planning control" alternatives — manual rework *of an AI/full itinerary* is a validated expectation, not a niche.
5. **[external] Overcode itinerary-app guide (overcode.tech/blog, 2025-06-21):** "Let users manually add, edit, or reorder plans on the fly, combining structured and spontaneous travel styles." Also recommends the AI result be treated as *a draft the user can reshape*.
6. **[external] Google Trips (defunct) — trip-cache.com feature table:** **"Manual trip entry ❌"** is listed among what Google Trips *lacked*; its successors market **manual entry/edit** as a differentiation. Lesson: a read-mostly AI itinerary without manual editing power feels like Google Trips, which was sunset.

**Synthesis for MVP scope:** the universally expected manual verbs are **reorder, replace-with-search, delete** (already present), **free-text add/name-resolution** (present), and **clear "good/bad fit" feedback** (missing). Drag-and-drop and cross-day moves are the ones travel products invest most in, but for this MVP, **adjacent move-up/move-down with a live constraint preview** delivers the same control at a fraction of the drag-and-drop complexity (and is keyboard/ARIA-friendly, matching this codebase's accessibility habits).

---

## 5. Proposed feature deltas (with effort / risk / value)

Each delta is positioned against existing endpoints so we reuse auth, rate limits, versioning, and `validate_plan`.

### D1 — Ranked, reason-labeled candidate picker (High value / Low effort / Low risk)
**What:** In the existing suggestion list (`PlanView.tsx:319-335`), (a) sort results by `_replacement_rank` instead of catalog order, (b) show a one-line "why this fits" label (kind match, distance, travel time, cost delta), (c) when a query yields zero eligible results, return the *reasons* the nearby catalog places were excluded so the empty state says "No place matches *because* you're under time budget" instead of a bare "not found".
**Where:**
- `plans.py:540-544` — sort by rank: `sorted(eligible, key=lambda p: _replacement_rank(p, rejected))`; extend response with reason fields (echo the checks in `plans.py:384-404`).
- `PlanView.tsx:34-41` (`isReplacementCandidate`) + `PlanView.tsx:320-334` render label + reason + cost.
- New i18n keys: `workspace-translations.ts:50-51`.
**Sketch:** the reason engine is a small function in `plans.py` that reruns each eligibility rule and returns structured `{code: "hours"|"travel"|"budget"|"duplicate"}`; API returns `ly_do` per suggestion and `ly_do_gap` for the empty case. No new mutations, no new constraints — pure scoring/annotation. Big UX win for the exact request ("user picks manually" becomes "user picks manually *with full information*").

### D2 — Slot reorder (move up/down) (High value / Medium effort / Medium risk)
**What:** Per-slot up/down arrows on the day timeline that reorder `khoang_gio` and **recompute slot times** for the affected range so `validate_plan` stays satisfied (times must remain sequential — `planner.py:1421-1445`, opening hours — `planner.py:1429-1434`, travel gaps — `planner.py:1435-1445`). Reject moves that cannot be rescheduled with a reason (reuses D3 reason engine). Only same-day moves in v1.
**Where (backend):** new `PATCH /plans/{token}/move` in `plans.py` next to `swipe`/`delete_slot`: payload `{dia_diem_id, huong: "len"|"xuong", phien_ban, ma_phien}` (schema in `schemas.py`), reuse `owner` (`plans.py:74-79`), a new rate-limit key (e.g., 20/hour mirroring `plans.py:432`), then reschedule the affected day with `_pack_day_slots`/`_compute_slot_bounds` (`planner.py:914-991`, `994-1105`) keeping the same stop set, then the exact `validate_plan` + `store.update` block copied from `plans.py:506-518`.
**Effort note:** the rescheduling is the non-trivial 60% — the codebase already has the machinery (`_compute_slot_bounds`, `_pack_day_slots`, `_effective_hours`, `travel_minutes`), so the work is *wiring*, not modeling. Risk is medium mainly because reusing planner internals from a router couples two modules; mitigation: move the reschedule helper into `planner.py` and unit-test it (`test_pipeline.py` style).
**Where (frontend):** `PlanView.tsx:235` slot article — add up/down buttons (reuse the `change-place`/`icon-action` styling `PlanView.tsx:236-270`), optimistic update with the returned `ke_hoach_moi`, failure → D3 message + reload. Add `moveFailure`/`reorderSuccess` i18n.
**Value:** closes the single biggest governance gap (M1) and the historically dominant travel-UX expectation (Utrip, Itinerally, Trip.com all ship reorder).

### D3 — Structured eligibility rejection feedback (High value / Low effort / Low risk)
**What:** Replace the collapsing of every failure into 422 (mapped to wrong text anyway — §6.1) with structured error codes surfaced as precise, friendly messages. Fix the wrong mappings: server 404 "no eligible replacement" (`plans.py:455-456`) currently renders as "Không thể xác minh địa điểm này tại Hà Nội" (`PlanView.tsx:136` → `workspace-translations.ts:51`) — the place may be perfectly real, it just doesn't fit.
**Where:**
- `plans.py:455-465` — return a structured body `{"ma_loi": "no_eligible", "ly_do": "...", "vi_pham": [...]}`; add `ma_loi` to `400/422/404` responses (or a new 422-with-code convention).
- `plans.py:506-518` — wrap `validate_plan` errors with the same structured codes instead of a 503 join (`plans.py:510`).
- `PlanView.tsx:136` — map 404-with-code, 422-with-code, 503 (AI-unavailable ≠ "doesn't fit"), and 409 (version conflict → "tải lại trang") to distinct toasts (`PlanView.tsx:230` + `workspace-translations.ts:50-51`).
**Value:** cheap, high-trust building block; also upgrades the failure paths D1 and D2 depend on.

### D4 — Converge suggestions with free-text name resolution (Medium value / Low-medium effort / Low risk)
**What:** Make the search box show a "chưa có trong danh sách — xác minh qua bản đồ" result for non-catalog text, so the user sees one coherent path: type → (catalog matches | "verify this new place" action) → applied via the existing swipe free-text path (`plans.py:438-452`). Avoid double AI-estimates on retry with the existing OSM cache (`osm_verify.py:79-93, 200-201`).
**Where:** `plans.py:524-544` (allow `replacement-candidates` to accept a `verify=1` hint, or add a tiny `GET /replacement-verify?q=`), `PlanView.tsx:319-335` (render the pending-verification row), `PlanView.tsx:299-302` unchanged.
**Value:** makes the two currently disconnected manual flows (suggestions vs. free text) feel like one; directly addresses M7. Scope tight for MVP.

### D5 — Swap two existing slots (Medium value / Medium-high effort / Medium risk)
**What:** "Swap this stop with that stop" between two positions (same or different day in a later phase). Distinct from D2 because it exchanges two *already-scheduled* places, which today is impossible (eligibility forbids in-plan candidates, `plans.py:386-387`).
**Where:** new `PATCH /plans/{token}/swap` with `{dia_diem_id_a, dia_diem_id_b, phien_ban, ma_phien}`; reschedule both affected days via the same helper as D2; validate + version bump. Frontend: "swap" entry in the change popup (`PlanView.tsx:273-339`) → pick another slot (timeline multi-select) → confirm.
**Out-of-scope-for-MVP note:** cross-day/in-plan reuse beyond swap (e.g., insert a Day-2 place into Day 3) requires allowing in-plan candidates under a new `dia_diem_hien_tai` mode in `_replacement_candidates` (`plans.py:384-405`). Feasible but defer.

**Delta table (rate each):**

| Delta | Effort | Risk | Value | Tier |
|---|---|---|---|---|
| D3 rejection feedback + error-mapping fix | Low (~0.5–1 d) | Low | High | **Tier 0** |
| D1 ranked, reason-labeled picker | Low–Med (~1–2 d) | Low | High | **Tier 0** |
| D2 reorder (move up/down, same day) | Med (~3–5 d) | Med | High | **Tier 1** |
| D4 suggestions↔free-text convergence | Med (~2–3 d) | Low–Med | Med | **Tier 2** |
| D5 swap two slots | Med–High (~4–6 d) | Med–High | Med | **Tier 2** |
| Cross-day reuse / drag-and-drop | High | High | Med (later) | Tier 3 |

---

## 6. Determinism & AI-constraint checks (lane requirement)

- **Place-change must NOT rerun AI copy.** Verified: `swipe` never calls `assemble`; it writes a deterministic `mo_ta` from localized `COPY[3]` and `ghi_chu` from `COPY[4]` templates (`plans.py:481, 476-488`), then replaces images via `image_for` (`plans.py:491-493`). The **only** AI call in the path is `estimate_place_metadata` for free-text out-of-catalog places (`plans.py:448-451`), which is idempotent-by-cache and budget-gated. So D1–D3 (annotation/ordering/messaging) and D2/D5 (reschedule + validate) can stay **zero-AI** and deterministic, exactly like `delete_slot` (`plans.py:547-584`), which sets the pattern to copy.
- **`validate_plan` is the invariant.** Every mutation path re-runs it before `store.update` (`plans.py:508`, `plans.py:576`). Any reorder/swap MUST keep the same stop set and only relocate/re-time them, so the slot-count invariant (`planner.py:1406`), uniqueness (`planner.py:1408-1420`), sequencing (`planner.py:1426-1445`), opening-hours (`planner.py:1429-1434`), and budget (`planner.py:1446-1447`) all re-hold. Reuse `validate_plan` verbatim.
- **Versioning / optimistic concurrency must be preserved.** All new mutation endpoints copy the `store.update(item, payload.phien_ban, plan, item.request, reason)` + 409 mapping pattern (`plans.py:514-516`, `store.py:80-95`, `postgres_store.py:127-150`). Test coverage mirrors `test_api.py:193-213`.
- **Rate limits.** New endpoints should add keys mirroring `swipe`/`delete-slot` 20/hour (`plans.py:432, 558`) and candidate-search 60/hour (`plans.py:536`) — cheap abuse control consistent with the existing surface.
- **Regenerate/refine vs. manual edits (M6):** regeneration intentionally excludes the entire current id set (`plans.py:608-613`), so a manual replace does feed into "make another plan" — but **chat refine rebuilds and throws manual edits away** (`plans.py:697-716`). This is a real product trap once users invest in manual control: the assistant should either (a) preserve manual edits by pinning them and tuning around them, or (b) explicitly warn "tinh chỉnh sẽ làm lại lịch trình và bỏ các thay đổi thủ công". Recommend warning first (cheap), pinning later (Tier 3). Not part of this lane's ship scope, but flagging because it undercuts the entire manual-control investment.

---

## 7. Categorization & roadmap

### Blocker
None — the manual replace feature ships and is tested. Nothing prevents the MVP from demoing manual replace today.

### Tier 0 (do first — cheap, trust-building, directly answers the request's "thủ công rõ ràng")
- **T3.0** Fix error mapping so 404-no-eligible, 422-ineligible, 503-AI-down, and 409-version-conflict each surface the right message, and the "cannot verify in Hanoi" text stops appearing for places that were never the problem (`PlanView.tsx:136`, `workspace-translations.ts:50-51`, backend codes at `plans.py:445, 455-460, 517-518`).
- **T1.0** Rank suggestion results by `_replacement_rank` and annotate each with a "why it fits" reason (`plans.py:540-544` + D1 reason engine).
- **T1.0b** Empty-suggestion state explains the likely blocker (time/budget/duplicate) instead of "No suitable places found." (`PlanView.tsx:317`, `workspace-translations.ts:50-51`).

### Tier 1 (MVP core for "tự đổi thủ công" power)
- **T1.1** D2 — move up/down reorder with rescheduling + live constraint validation (new `move` endpoint; largest single control gain; matches every external expectation found in §4).

### Tier 2 (strong follow-ups, MVP-safe)
- **T1.2** D4 — suggestions harmonized with free-text OSM verification.
- **T1.3** D5 — swap two scheduled stops (same day first).

### Tier 3 (later)
- Cross-day reuse/moving, drag-and-drop, pin/manual-edit preservation across refine, "add a place from map", forced-choice with warning override (M5 — deliberate product decision, not a bug; recommended *not* to relax constraints silently, only to surface them).

### Notes
- Manual edits are already durable, versioned, and undoable (Restore, `plans.py:739-760`) — marketing/UX should surface "mọi thay đổi đều có thể hoàn tác".
- `refine` discarding manual edits (§6, M6) is worth an interim warning string independent of any build.
- The catalog is small (≈35–40 Place records in `data.py:79-285` + optional imported set `data.py:117`), so search returns fast; the reason-labeled ranking (T1.0) is cheap at this scale.

---

## 8. Executive summary (~250 words)

"Manual place change" is **not a missing feature — it is an incomplete and under-discoverable one.** The product already lets a user, per slot, let AI auto-pick a similar place (`plans.py:462-465`), search and explicitly choose a catalog replacement (`plans.py:524-544`, `PlanView.tsx:319-335`), or type any place name which is verified against OSM/Nominatim and, if uncatalogued, AI-estimated and applied (`plans.py:438-452`); delete-with-confirm and full version restore exist (`plans.py:547-584, 739-760`). All mutations are rate-limited, ownership-checked, optimistic-versioned, and re-validated by `validate_plan`.

The genuine gaps: (1) **no reorder capability** — the single manual verb travel products universally ship that is absent (Utrip, Itinerally, Trip.com all name reorder); (2) **no swap/in-plan reuse** — eligibility forbids already-scheduled places; (3) **opaque rejection** — budget/hour/travel/duplicate failures collapse into one message, and a 404 "no eligible candidate" is even mistranslated as "not verified in Hanoi"; (4) **suggestions are unranked** and exclude out-of-catalog places; (5) **chat refine silently discards manual edits**. Recommended MVP deltas: Tier 0 = fix error mapping + rank/annotate candidates with reasons; Tier 1 = move-up/move-down reorder with constraint-driven rescheduling reusing planner machinery; Tier 2 = suggestions/free-text convergence and slot swap. Everything ships deterministically with zero new AI calls by copying the proven swipe/delete mutation pattern.

---

## 9. Top 5 most concerning findings

1. **Misleading rejection UX.** A server 404 for "no eligible replacement" (`plans.py:455-456`) renders as "Không thể xác minh địa điểm này tại Hà Nội" (`PlanView.tsx:136`, `workspace-translations.ts:51`), and 503 (AI down) renders as "không phù hợp với khung giờ" — users get the wrong diagnosis for the two most common manual-replace failures.
2. **Refine destroys manual edits silently.** `refine()` rebuilds a fresh `build_plan` and throws away every replace/delete/move a user made (`plans.py:697-716`); after this lane ships meaningful manual control, that wipe is a product-severity trap.
3. **Reorder is entirely absent** in a segment where reorder is table-stakes (Trip.com, Itinerally, Utrip) — the single biggest "manual control" expectation the product doesn't meet.
4. **In-plan reuse/swap is structurally impossible** because eligibility hard-blocks any scheduled place id or folded name (`plans.py:386-387`) — moving an existing stop between slots requires new endpoint + rescheduling, not a param flag.
5. **Eligibility is a silent hard gate with no partial-information path** (budget overflow, hours mismatch, travel gaps all invisible until a generic error) — users cannot even learn *why* their chosen place was refused, which erodes trust more than the refusal itself.

---

## 10. Confidence & ground-truth tally

**Confidence: 8/10** — extremely high on the *code-level* claims (every capability gap and mapping is verified by reading `plans.py`, `osm_verify.py`, `schemas.py`, `PlanView.tsx`, `workspace-translations.ts`, `planner.py`, `store.py`, and the test suite that pins them; §6 determinism claims are directly corroborated by `test_api.py` and the missing-`assemble` call graph in `swipe`). Marked down from 9 because: (a) the external product-UX claims (§4) are secondary-source web pages, not primary specs or first-party telemetry — labeled external as required; (b) the exact catalog entry count is approximate (≈35–40 core records — counted `data.py:79-285` plus conditional import at `data.py:117`); (c) I did not run the app or the test suite in this environment, so "as-built behavior" rests on code+test reading rather than execution.

**Ground-truth tally (external-checked facts vs. model judgment):**
- Facts verified by reading repo code/tests: 25 (both endpoints + eligibility rules `plans.py:360-405`; rank `408-417`; free-text + AI-estimate `438-452`; version/409 `store.py:80-95`, `postgres_store.py:127-150`; search `524-544`; delete `547-584`; restore `739-760`; frontend popup/suggestions/error-mapping/debounce `PlanView.tsx:129-165, 236-339`; i18n strings `workspace-translations.ts:50-51`; validate/budget/sequencing `planner.py:1393-1448`; refines-discard `plans.py:697-716`; test contracts `test_api.py:193-241`).
- External facts (fetched, not repo-verified): 6 sources in §4 — marked external.
- Model judgment (inference, low ground-truth): precise hold that "most of the user's request is discoverability + missing reorder/feedback rather than fully missing manual replace"; effort estimates for D1–D5; roadmap tiering.

*(Do not round up. 8/10, and the residual uncertainty is concentrated in product-intent interpretation and external-market claims, not in whether the replace code exists.)*