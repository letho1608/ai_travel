# Replan Feature Audit — Lane 3 (end-to-end)

**Product:** Mình Đi Đâu Thế (Vietnamese AI travel app)
**Repo:** `D:\Code\aithucchien\ai_travel`
**Date:** 2026-08-07
**Mode:** pure research — no code modified.
**Scope:** regenerate / refine / swipe / versions / restore, backend (`backend/app/routers/plans.py`, `services/store.py`, `schemas.py`, `pipeline/planner.py`) and frontend (`components/PlanView.tsx`, `lib/api.ts`, `app/plan/[token]/page.tsx`, `components/Planner.tsx`).

## 0. Verdict in one paragraph

The product owner's claim — *"chưa có replan cả back và frontend"* (no replan on either side) — is **false as stated**, and simultaneously **true in substance**. Every replan primitive exists, is wired end-to-end, and returns 200 in real API calls I ran: swipe (`PATCH /plans/{token}/swipe`), "Làm lại" (`POST …/regenerate`), chat refine (`POST …/refine`), version history (`GET …/versions`) and restore (`POST …/versions/{v}/restore`). The owner's own product report (`Baocao.md:94-101`) and parity matrix (`PARITY_MATRIX.md:10`) describe these as shipped features. **But** none of them add up to what a user means by "replan": regenerate is a full-page navigation that orphans the old plan and breaks the version chain; chat refine silently ignores the two most important Vietnamese constraints (people count, budget) because its regexes are double-encoded mojibake; the most natural Vietnamese swap verb *"đổi"* is not recognized at all while the UI's own example prompt tells users to type exactly that; and there is no keep/drop constraint set, no in-place update, and no diff view. So: **replan primitives exist; a replan feature does not.**

---

## 1. Evidence methodology (what I actually ran)

All checks ran in **mock mode** (`AI_MODE=mock`, `APP_ENV=local`, Python 3.10.8 system, `datetime.UTC` shim, `PYTHONIOENCODING=utf-8`) against the real routers via `fastapi.TestClient`, plus direct calls to `build_plan`, `_refined_request`, and the regex objects. `reportlab` was installed (project dependency in `requirements.txt`) to permit importing `plans.py`. Results below are quoted verbatim from execution.

---

## 2. Regenerate / "Làm lại"

### 2.1 Backend logic
`plans.py:387-423`. It re-serializes the stored request, takes **only the first slot's `dia_diem_id`** as `excluded` (`plans.py:408-412`), calls `build_plan(request, excluded)` (`plans.py:413`), then **saves a brand-new plan via `store.save`** (`plans.py:416` → `store.py:63-70`): new UUID token, version reset to 1, fresh single-entry version history. Nonce gives idempotency (`plans.py:398-402`, tested by `test_regenerate_nonce_is_idempotent`).

### 2.2 Does it produce a different plan in mock? (my hypothesis was half-wrong)
`build_plan` is deterministic for identical args — I verified `build_plan(req) == build_plan(req)` is **True**. The only inputs are the request (seed = hash of context+duration+people+budget+session+nonce, `planner.py:152-163`) and `excluded`.

In mock mode, `_select_llm_first_places` returns `candidates[:count]` (`ai.py:86-92` returns `[]`, so the fallback loop at `planner.py:395-402` fills from candidates), so selection is a pure function of the rotated candidate ranking. Excluding the first slot shifts the `quality_pool` boundary (`planner.py:265`), which **cascades**:

```
Plan A:   lang-bac | hang-dau | hang-ngang | hang-duong | ho-guom | ho-tay | pho-co
Plan B:   hang-bac | hang-ma  | ho-guom    | ho-tay     | cho-dem | hang-dao | pho-co   (excluded lang-bac)
```
So mock "Làm lại" changes **4 of 7** places on the first press — more variety than the "drop first stop" hypothesis predicts, because the `min(len,120)` pool slice shifts (the 121st-ranked place enters the pool). **But** repeating the operation 4 times reveals the truth:

```
iter 1 == iter 3;  iter 2 == iter 4
```
The planner **oscillates between two near-identical variants** (6/7 shared places, same order, only the excluded first-stop and one filler swap). There is no progressive exploration — it cycles.

### 2.3 Frontend behavior — full page reload, old plan orphaned
`PlanView.regenerate` (`PlanView.tsx:87`) does `location.assign('/plan/' + data.token)` — a **full page reload to a new URL**. Everything in-memory (chat conversation, selected slot, open drawers) is discarded; the old token remains in the store (30-day TTL, `store.py:64`) and in `/history`, but the new page has **no link back** and no version relationship to the old plan. The only way to reach the old plan is the browser back button.

### 2.4 Severity: **High** (functional but weak)
- "Làm lại" is a "regenerate the same request again" button, not a replan. In production the only variety is LLM temperature + one excluded id.
- New token + fresh v1 = version history chain severed (see §5).
- No constraints: users cannot say "keep these, drop those, cheaper, longer".

---

## 3. Refine (chat-based edit)

### 3.1 It is a full rebuild, not an edit
`_refined_request` (`plans.py:426-449`) appends the message to context (truncated to 500, `plans.py:429`), then attempts regex extraction, then `refine` calls `build_plan(refined)` from scratch (`plans.py:482-488`). `store.update` then **overwrites `item.plan` entirely** (`store.py:78-91`).

**What is lost:** every manual change. Swipes made earlier on the same plan are stored only inside `item.plan`; `build_plan` never reads `item.plan` — it re-plans from the stored *request*. So: 2 swipes + 1 refine ⇒ the 2 swipe swaps vanish. I verified this end-to-end: after `swipe` (v2) then refine "đổi điểm này thành cà phê" (v3), the rebuilt plan had **4 brand-new `osm-*` places** that were never in the original and the selected place was gone. There is no diff; the user cannot tell which of their edits survived (none did).

### 3.2 The regexes are mojibake — verified broken for Vietnamese
`SWAP_INTENT` (`plans.py:30-35`) contains `Ä‘á»•i`, the mojibake double-encoding of *"đổi"* (U+0111 U+1ED5 U+0069 encoded as UTF-8 bytes C4 91 E1 BB 95 69, mis-decoded to U+00C4 U+2018 U+00E1 U+00BB U+2022 U+0069). I executed the regex directly:

```
SWAP_INTENT.search('đổi')                     -> NO MATCH
SWAP_INTENT.search('đổi điểm này thành cà phê') -> NO MATCH
SWAP_INTENT.search('ĐỔI quán này')            -> NO MATCH
SWAP_INTENT.search('thay điểm này')           -> MATCH ('thay')
SWAP_INTENT.search('replace this place')      -> MATCH
```

**The single most natural Vietnamese swap verb does not trigger the swap path.** `refine()` then falls through to `_refined_request` → full rebuild. The frontend makes this worse: the chat placeholder (`workspace-translations.ts` vi: `chatPlaceholder` = *"Ví dụ: đổi điểm này"*) and the `swipeSuccess` copy both use "đổi" — the app **instructs users to type a phrase it cannot understand as a swap**. (Note: `_refined_request` applies its cafe rule to the ASCII-folded string, so "…thành cà phê" does at least append a cafe-bias context — by accident, not by design.)

`PEOPLE_INTENT` (`plans.py:36-40`) has the same defect:
```
PEOPLE_INTENT.search('3 người')  -> NO MATCH   (so_nguoi stays 2)
PEOPLE_INTENT.search('4 people') -> '4'
```
The budget regex (`plans.py:433-441`, `ngÃ¢n sÃ¡ch|dÆ°á»›i|tá»‘i Ä‘a|nghÃ¬n|triá»‡u`) is also mojibake:
```
'ngân sách 500k' -> NO MATCH   (ngan_sach stays 1,000,000)
'budget 500k'    -> budget 500k
```
Only the ASCII-folded rules work (I verified): `"Rẻ hơn"` → budget ×0.8 (`plans.py:442-444`), `"Ít di chuyển"` → nearby context (`445-446`), `"Thêm cafe"`/`"cà phê"` → cafe context (`447-448`, via fold).

### 3.3 Is "rebuild from scratch + append context" a legitimate replan? — **No**
It is a **hack**: it cannot guarantee the user's selected point is the one changed (I verified the selected place was dropped only as a side effect of the whole plan changing), it silently discards the user's edits, it changes far more than asked, and its claim of "đã áp dụng yêu cầu" (applied your request) is false whenever the regexes miss (which is always for Vietnamese people/budget).

### 3.4 Test suite gives false green
`test_chat_refine_creates_version_and_restore_is_optimistic` (`test_api.py:252-286`) sends *"đi 3 người, ngân sách tối đa 500k và ưu tiên yên tĩnh"* — proper Vietnamese that **cannot parse** under the mojibake regexes — and asserts only `200` + `phien_ban == 2`. It never asserts `so_nguoi == 3` or `ngan_sach == 500_000`. `test_quick_refine_cheaper_reduces_saved_budget` (`test_api.py:289-299`) at least asserts the budget change, but only for the ASCII form `"Re hon"`. **The people/budget extraction is untested and broken.**

### 3.5 Severity: **Blocker** (primary feature silently fails its core promise)

---

## 4. Swipe (replace one place)

### 4.1 Backend (`plans.py:310-384`) — works, with quality caveats
E2E: 7/7 swipes returned 200, version bumped 1→8 sequentially, each slot replaced with a same-kind place. Candidate filter requires same `kind`, unused, open at the slot window (`plans.py:334-341`); replacement = **nearest by Euclidean distance to the rejected place** (`plans.py:344-347`), then the slot is patched with generic copy (`plans.py:358-369`: `mo_ta = COPY[3].format(...)`, `ghi_chu = COPY[4]`) and costs recomputed (`371-372`).

Quality problems:
- **No cost guard in candidate selection.** `plans.py:334-341` never filters `p.cost`, so a cheap plan can be handed an expensive replacement; `validate_plan` then fails the budget check (`planner.py:307-308`) and the user gets a 503 *after* the swipe attempt. In the mock catalog most places are free so I could not force it, but the path is real.
- **No re-timing.** The slot keeps its original `bat_dau`/`ket_thuc`; travel time between the new neighbor and the route is not recomputed, and the description is downgraded to a two-line generic template, losing any LLM-written copy.
- **Rare-kind failure.** For a kind with no candidate open in the slot window the endpoint 404s (`plans.py:342-343`) with mojibake *"KhÃ´ng cÃ³ Ä‘á»‹a Ä‘iá»ƒm thay tháº¿ phÃ¹ há»£p"*. In mock the catalog is rich (1191 café, 1489 nhà hàng, 156 chợ…); in the real Postgres catalog sparser kinds (bảo tàng 39) make this more likely.
- Rate limit `20/hr` per session (`plans.py:321`, window 3600s default in `rate_limit.py:16`) — verified the 21st check returns False. Same for refine (20/hr, `plans.py:462`) and regenerate (5/hr, `plans.py:404`).

### 4.2 Frontend (`PlanView.tsx:79`) — correct wiring
Sends `{diem_bi_loai, phien_ban: ver, ma_phien}`, validates `ke_hoach_moi` shape, updates `plan`/`ver` in place, and re-selects the replacement slot. The ↻ button is per-slot (`PlanView.tsx:99`). **This is the only replan primitive that behaves like an edit** (in place, one slot, versioned).

### 4.3 Severity: **Medium** (works, quality-constrained)

---

## 5. Versions / restore

### 5.1 What works
`store.update` (`store.py:78-91`) does optimistic concurrency: `item.version != expected_version → ValueError("VERSION_CONFLICT")` → 409. `list_versions` returns newest-first (`store.py:93-94`). Restore works within a token (E2E: restore old-token v1 → 200, version 5). Verified stale `phien_ban` → **409** with mojibake detail `'Lá»‹ch trÃ¬nh vá»«a Ä‘Æ°á»£c cáº­p nháº­t, vui lÃ²ng táº£i láº¡i'`.

### 5.2 The chain breaks at "Làm lại" — confirmed
Regenerate calls `store.save` → **new token, version 1, single entry** (`store.py:63-70`). E2E result:

```
OLD token versions: [(4, None), (3, 'Tinh chá»‰nh: …'), (2, None), (1, 'Tạo mới')]
NEW token versions: [(1, 'Tạo mới')]
```
Combined with the frontend `location.assign` navigation, after "Làm lại" the user is on a plan whose version drawer shows **one row (current version)** — no restore button is rendered because `entry.phien_ban === ver` (`PlanView.tsx:95`). The old plan's 4-version history is unreachable from the new page. **There is no way to see the history of the new plan and no diff between "before" and "after Làm lại".** Browser-back is the only escape hatch.

### 5.3 Severity: **High** (undo/revert — the one true replan affordance — is severed by the regenerate flow)

---

## 6. Concurrency, failure paths, and mojibake

### 6.1 Concurrency
Optimistic versioning is sound at the store level. UX is weak: on a 409 the frontend just shows the generic `actionFailed` (*"Không thể hoàn tất thao tác. Lịch hiện tại được giữ nguyên."* — `workspace-translations.ts`), which is **misleading** when the conflict was caused by another tab changing the plan; there is no "reload to see the newer version" prompt. Two tabs editing one plan silently clobber the loser.

### 6.2 Do users see mojibake? Mostly not — by accident
I traced every error-display path:

- **PlanView swipe/refine/restore/regenerate**: on `!response.ok` it does `throw new Error()` and the catch shows a **generic translated key** (`actionFailed`, `refineFailed`, `regenerateFailed`…). The backend's mojibake `detail` is never rendered. (`PlanView.tsx:79-87`)
- **PlanView refine reply**: `tra_loi` (mojibake, e.g. `'Ä\x90Ã£ Ã¡p dá»¥ng yÃªu cáº§u …'`) is **ignored**; only `tra_loi_key` (allow-listed to `swipeSuccess|assistantWelcome`, `PlanView.tsx:25`) is used. So mojibake text is masked.
- **Initial generation** (`Planner.tsx:137-141`): `consumePlanStream` throws `Error(parsed.detail)` (`api.ts:13`) but Planner maps **every** failure to the generic `generateFailed`; the SSE `error` event discards `detail` entirely (`api.ts:40` → hardcoded *"Plan generation failed"*).
- **Plan 404 page** (`app/plan/[token]/page.tsx:5`): ignores API detail, `notFound()`.

**Where mojibake IS visible:** Swagger docs, raw API responses, stored version `ly_do` fields (`'Tinh chá»‰nh: đổi điểm này thành cà phê'` in the DB/payload), admin/support pages that render `payload.detail` (`frontend/app/admin/page.tsx:133,157,…`), and any future UI that reads `detail`. This is a latent bug masked by today's generic-error design.

### 6.3 Full mojibake inventory (backend user-facing strings)
`plans.py` — the entire HTTPException set and reply strings are mojibake: `:55,69,85,138,167,214,234,238,246,254,267,291,302,319,322,326,328,332,343,379,405,466,479,490,496,527,531`. Regex mojibake: `SWAP_INTENT` `:30-35`, `PEOPLE_INTENT` `:36-40`, budget regex `:434`. `schemas.py` — `:105,163,215`. `planner.py` — `AI_FALLBACK_NOTE` `:30`. Contrast: `store.py` is **clean** proper Vietnamese (`:41,46,48,…`), and `planner.py COPY` (`:35-54`) and `validate_plan` errors are clean. The frontend `workspace-translations.ts` is clean UTF-8. So the corruption is a one-time encoding slip in the router/schema layer, pervasive there.

### 6.4 Severity: **High** (H3)

---

## 7. What "replan" means vs what exists — gap map

A real replan lets a user adjust constraints and regenerate **in place with a diff**, preserving their choices. Current state:

| True-replan capability | Exists today? | Where |
|---|---|---|
| Adjust budget / people / style | Partial (EN + ASCII-folded only; VN broken) | `plans.py:426-449` |
| Keep/drop specific places | **No** (only single-slot swipe; regenerate excludes only slot #1) | `plans.py:412` |
| Regenerate in place (same token/URL) | **No** (full nav to new token) | `PlanView.tsx:87` |
| Diff between versions | **No** | — |
| Undo / revert | Partial — within one token only; severed by "Làm lại" | `store.py:93-100` |
| Constraint UI | **No** (only 3 quick chips + free text) | `PlanView.tsx:47,98` |
| Carry user edits into rebuild | **No** (rebuilds from stored request) | `plans.py:482-488` |

The roadmap confirms this is *known* future work: `IMPLEMENTATION_ROADMAP.md` Phase 2 lists "Chat liên tục với context/version history; natural-language extraction", and "regenerate with constraints, undo/version compare" — none of which is implemented in the shipped code.

### Prioritized, sized gap-closing list
1. **Fix the mojibake** in `plans.py` strings + `SWAP_INTENT`/`PEOPLE_INTENT`/budget regexes (rewrite with proper UTF-8, test "đổi", "3 người", "ngân sách 500k"). ~2h. **Blocker.**
2. **Regenerate in place**: keep the same token, `store.update` to a new version (mirror `refine`), and make "Làm lại" call `setPlan` instead of `location.assign` — or persist a parent link and surface it. ~3-4h. **High.**
3. **Keep/drop constraints**: extend `excluded`/add `required` to `build_plan`; send keep/drop sets from the UI (per-slot "keep"/"drop" toggle). Backend ~4-6h, frontend ~2-3h. **High.**
4. **Constraint UI** (budget/people inputs + chips in the workspace) mapped to the now-working extraction. ~3-4h. **Medium.**
5. **Diff view** for versions (added/removed/swapped slots) + a "what changed after this action" toast. ~4-6h. **Medium.**
6. **409 handling**: on version conflict, offer one-click reload to the latest version instead of the misleading "your plan is unchanged". ~1-2h. **Medium.**
7. **Intent-parsing tests** asserting resolved values (`so_nguoi==3`, `ngan_sach==500_000`), not just 200/version. ~1h. **Low cost, high value.**

Rough total to close the gap to a real replan: **~20-28h**.

---

## 8. Truth table — owner claim vs reality

| Owner claim | Reality (evidence) | Broken? |
|---|---|---|
| "Chưa có replan backend" | Replan endpoints exist and return 200 end-to-end (swipe/regenerate/refine/versions/restore, §3-5 E2E runs). Owner's own `Baocao.md:94-101` and `PARITY_MATRIX.md:10` document them. | **Claim false** — but backend replan is only a partial approximation |
| "Chưa có replan frontend" | Full UI wired: ↻ per-slot swap (`PlanView:99`), chat + quick chips (`:98`), "Làm lại" (`:92`), version drawer (`:95`). | **Claim false** |
| Regenerate gives a new plan | Yes, but it oscillates between 2 near-identical variants in mock; only exclusion signal is slot #1 | Partially — **meaningful variety: no** |
| Chat refine edits the plan | It rebuilds from scratch, discards all swipe edits, and ignores VN people/budget | **Yes — silently** |
| Swap by chat ("đổi") | "đổi" never matches (mojibake); "thay"/EN words do | **Yes** |
| Version history | Works within a token; **severs at "Làm lại"** (new token, v1, old history unreachable) | **Yes** |
| Concurrency safety | Optimistic 409 correct; UX hides it behind misleading generic message | Partial |
| User-facing Vietnamese text | Clean on frontend; **mojibake on backend wire** (masked in current UI, visible in Swagger/admin/API) | **Yes — latent** |

---

## 9. Executive summary (250 words)

Replan is **not absent** — it is **present but not real**. All five primitives (swipe, "Làm lại", chat refine, version history, restore) are implemented and wired; I exercised every one over the real API in mock mode and got 200s with correct version bumps. The owner's "chưa có replan" is therefore factually wrong on both layers, and contradicts the project's own documentation. The problem is that the primitives do not compose into a replan: the only in-place edit is single-slot swipe; "Làm lại" is a full-page hop to a brand-new plan whose version history starts empty (the old one becomes unreachable); and chat refine rebuilds the plan from scratch, silently discarding every swipe the user made. Three defects are outright silent breakage: the most natural Vietnamese swap verb *"đổi"* is not recognized because the regex is double-encoded mojibake (while the UI itself prompts users to type it); Vietnamese people-count and budget phrases ("3 người", "ngân sách 500k") are also mojibake-broken and ignored while the app claims success; and the test suite green-lights this because it only asserts HTTP 200/version, never the extracted constraints. A second, latent mojibake layer corrupts every backend user-facing string — currently masked by the frontend's generic error keys, but visible in Swagger, admin, stored version reasons, and any future detail-rendering UI. Fixing the mojibake, making regenerate stay on-token, carrying keep/drop constraints into `build_plan`, and adding a diff view would convert this approximation into a genuine replan in roughly one focused sprint (~20-28h).

---

## 10. Top 5 findings

1. **[Blocker] "đổi" is unrecognized.** `SWAP_INTENT` (`plans.py:30-35`) stores mojibake `Ä‘á»•i`; executed regex shows `'đổi điểm này thành cà phê'` → NO MATCH → silent full rebuild. The UI prompt literally says *"Ví dụ: đổi điểm này"*.
2. **[Blocker] Vietnamese constraint extraction is dead.** `PEOPLE_INTENT` (`:36-40`) and budget regex (`:434`) never match "3 người"/"ngân sách 500k" (verified). `test_api.py:252-286` asserts only status/version, so CI is green while the feature does nothing.
3. **[High] Version chain severs at "Làm lại".** `store.save` (`store.py:63-70`) makes a new token at v1; `PlanView.tsx:87` navigates away. Verified: OLD token had `[4,3,2,1]`, NEW has `[1]`. No undo/diff across "Làm lại".
4. **[High] Chat refine is rebuild-from-scratch, not an edit.** `plans.py:482-488` never reads `item.plan`; verified it discards prior swipes and swaps in unrelated `osm-*` places. User edits are silently lost with no diff.
5. **[High, latent] Backend-wide mojibake.** ~30 user-facing strings in `plans.py`/`schemas.py` are double-encoded; masked today only because the frontend throws `new Error()` and renders generic keys, but visible in Swagger/admin/API and stored version reasons.

## 11. Confidence and ground-truth tally

**Confidence: 7/10.**

**Ground-truth tally: 10 of 13 load-bearing conclusions were verified by executing code** (regex matching against real Vietnamese strings; `build_plan` determinism; regenerate oscillation across 4 iterations; full E2E wiring of swipe/refine/regenerate/versions/restore/409; rate-limit limits at the 21st/6th call; version-history severing; mojibake in wire responses and stored `ly_do`; `tra_loi`/`detail` masking paths). The remaining 3 rest on static reading of unambiguous code and repo docs (frontend `location.assign` navigation, test-suite assertion gaps, owner docs). Confidence is capped at 7, not higher, because: production behavior (real LLM adapter, Postgres catalog, Redis limiter, Next.js SSR) was not executed; the regenerate-variety finding is specifically mock-mode (in production the LLM's temperature adds uncontrolled variety, which the mock cannot show); and mojibake *user visibility* depends on browser rendering I did not reproduce in a live browser. None of those unverified factors could flip the headline conclusion — the primitives exist, are wired, and are not a real replan — but they could change the exact magnitude of user impact.
