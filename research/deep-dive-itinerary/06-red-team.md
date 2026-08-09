# 06 — Red-Team Review

**Date:** 2026-08-07 · **Reviewer:** adversarial red team · **Mode:** research-only (no source edits)

## Objective

Independently verify the load-bearing claims in `05-synthesis.md` and the four lane reports
(`01`–`04`) by direct source reads and *executed* probes against the actual code, then hunt for
blind spots the lanes missed, sanity-check the acceptance criteria and the headline probability
(~15/100), and specify which experiments would move the verdict. All claims below were either
run against `backend/app` or read from source; nothing was assumed.

## Methodology

- Python 3.10 probes (`sys.stdout.reconfigure(encoding='utf-8')`, `datetime.UTC = datetime.timezone.utc`,
  `AI_MODE=mock APP_ENV=local`, `sys.path.insert(0, backend)`). Windows PowerShell mangles inline
  Python, so all probes were written to `C:\Users\Admin\AppData\Local\Temp\opencode\rt_probe*.py`
  and executed there.
- Source files read: `pipeline/planner.py`, `pipeline/routing.py`, `services/ai.py`,
  `services/osm_verify.py`, `services/store.py`, `services/postgres_store.py`, `services/rate_limit.py`,
  `services/weather.py`, `routers/plans.py`, `routers/admin.py`, `config.py`, `schemas.py`, `main.py`,
  `scripts/import_osm_places.py`, `data/distance_matrix.json`, `data/places.json`, `tests/*`,
  `.env.example`, `run.bat`, `frontend/components/Planner.tsx`, `frontend/components/LocaleProvider.tsx`,
  `frontend/lib/i18n-core.ts`, `frontend/lib/api.ts`, `frontend/app/plan/[token]/page.tsx`.
- Backend test suite cannot be executed on this machine: Python is 3.10 but tests import
  `from datetime import UTC` (3.11+ only). CI pins `python-version: "3.11"` (`.github/workflows/ci.yml`).
  Marked **unverified at runtime**, not refuted.
- Frontend: `next` is not installed in `frontend/node_modules` (`node_modules/next/dist/bin/next` missing),
  so `npm test`/`build` could not run. Marked **unverified at runtime**.

---

## 1. Executive verdict

The synthesis is **directionally correct and honest** about its biggest weakness: the whole app
defaults to a deterministic mock and, even in mock mode, most Vietnamese intent is silently
destroyed by an ASCII-folding bug, so the "AI travel app" currently ships **7 random coffee shops
scheduled 08:00–14:08** for a request like *"đi chơi buổi tối"*. I could reproduce every load-bearing
generation bug by running the actual code. However, the review found that **several severity labels
are inflated, a few numbers are wrong in detail, and the fix plan's acceptance criteria are mostly
unverifiable as written** — so the confidence in the headline 15/100 is reasonable but the *path to
falsify* it is poorly specified. I rate the headline probability **15/100** as **correct in spirit**,
with the caveat that the biggest blocker is *configuration drift + absent live-mode quality gates*,
not the mock bugs per se.

Confidence in this verdict: **7/10**.

Ground-truth tally:

| Item | Source-read | Executed probe | Verified |
|---|---|---|---|
| `_ascii_fold('chợ đêm') = 'cho em'` kills night intent | planner.py:131–137 | rt_probe1 | ✅ |
| Night-market profile never fires for `'chợ đêm'` | planner.py:171–188 | rt_probe1 | ✅ |
| `build_plan('đi chơi buổi tối', ca_ngay)` → 7 cafés 08:00–14:08 | planner.py | rt_probe1 | ✅ |
| Rotation pushes best intent match out of first-7 window | planner.py:255–284 | rt_probe3 (pos 11 of 51) | ✅ mechanism |
| Highlight landmarks forced for Hanoi-ish contexts | planner.py:191–211 | rt_probe4 | ✅ (but narrower than claimed) |
| `_catalog_match('Phố cổ Hà Nội')` → "Phở hà nội" | osm_verify.py | rt_probe4 | ✅ |
| `_catalog_match('Chợ đêm Đồng Xuân')` open 7 close 22 | osm_verify.py | rt_probe4 | ✅ |
| Catalog is cost=0 / open 7–22 / duration 60 (import) | import_osm_places.py:99–104 | histogram | ✅ (minor variants exist) |
| PLACES total = 3524 (dataclass) vs places.json = 3508 | data.py / places.json | count | ✅ |
| distance_matrix.json = 50 ids (36 cafe + 14 bao_tang) | distance_matrix.json | join | ✅ |
| "66 usable = 50 routable + 16 curated" | — | set union | ✅ (curated=16) |
| SWAP_INTENT / PEOPLE_INTENT / budget regexes are mojibake | plans.py:30–40, 433–441 | rt_probe5 | ✅ |
| `validate_plan` rejects out-of-list ids, out-of-hours, budget | planner.py:287–309 | rt_probe5 | ✅ |
| `build_plan` deterministic on identical args | planner.py | rt_probe5 | ✅ |
| Frontend `inferDuration` fails 2 of 3 default chips | Planner.tsx:62–73 | rt_probe6 | ✅ |
| `LocaleProvider` en `dataNotice` is Vietnamese | LocaleProvider.tsx | rt_probe7 | ✅ |
| Budget / reserve-cost logic (daily vs lifetime) | store.py:39–57, postgres_store.py:35–70 | rt_probe9 | ✅ (blind spot found) |
| Swipe uses `validate_plan(plan, {p.id for p in PLACES}, …)` | plans.py:374 | source | ✅ |
| Comments rate-limit keyed by client `ma_phien` | plans.py:266 | source | ✅ |
| Admin routes: no rate limiter, token-gated | admin.py | source | ✅ |
| `.env` missing → mock mode is the de-facto default | repo scan | ✅ | ✅ |

---

## 2. Verdict on each lane report

### 01 — Itinerary generation (quality, High)
**Largely correct. Two numbers wrong, one overstatement.**

- ✅ VERIFIED: fold bug destroys `'chợ đêm'` (probe1: `relevant_tags` = `{'em','cho_em','cho'}`, night profile = `[]`).
  Note the extra sharp edge nobody spelled out: `'cho'` (the surviving fold of `chợ`) collides with
  the food keyword `'cho_em'`/`'cho'` tag space, so a night-market query can route into food intent.
- ✅ VERIFIED: `build_plan('đi chơi buổi tối')` returns 7 cafés, 08:00–14:08, no night market (probe1).
- ⚠️ CORRECTION: lane 01's *exact* rotation arithmetic (offset 32/33 etc.) is **seed-dependent** and
  did not reproduce verbatim. What reproduced (probe3, verbatim copy of `choose_candidates`):
  seed = `sha256(request…)[:12] % 51` = 40; the curated night market sat at **position 11** post-rotation,
  i.e. outside the first-7 window. Across 6 nonces the position was 26/28/7/45/15/18 — **never ≤ 7**.
  Mechanism confirmed; the lane's specific offsets are illustrative, not reproducible constants.
- ⚠️ OVERSTATED: "the single best intent match is always rotated out". True for the night-market in the
  6 samples, but it's a *probabilistic* failure — the rotation is `seed % len(intent_matches)`.
  It reliably breaks *deterministically per request* (same request → same plan), which is exactly why
  "regenerate" and "swipe" feel broken in the demo. Fix framing: deterministic-starvation, not universal.
- ✅ VERIFIED (probe4): `_catalog_match('Phố cổ Hà Nội')` → `osm-node-10298717234` **"Phở hà nội"**
  (nha_hang, dist 0.4386) instead of `curated-pho-co-ha-noi` (dist 0.6532). The claim "maps Phố cổ to
  Phở hà nội" is real.
- ⚠️ OVERSTATED: "Hồ Gươm / Lăng Bác force-inserted into *any* Hanoi plan". `_highlight_places`
  (planner.py:191–211) only fires when the context folds to `hanoi_highlights` terms
  (`classic|du_lich|ha_noi|hanoi|lan_dau|noi_tieng|pho_co|tham_quan` or `ho_guom|ho_tay|lang_bac|…`).
  For `'chợ đêm'` and `'hẹn hò trà sữa'` it returns `[]` (probe4). So landmark-insertion is **context-gated,
  not universal** — the demo chips that mention culture/Hanoi do force them, but night/specialty queries do not.
  This actually *helps* the night-market story (no forced landmarks competing), which lane 01 muddles.
- ✅ VERIFIED (probe4): `_catalog_match('Chợ đêm Đồng Xuân')` → open 7 close 22 (matches "7h–22h" claim).
- ✅ VERIFIED: 66 usable = 50 routable (36 café + 14 museum) + 16 curated. curated=16 confirmed by count;
  0 curated ids are in the distance matrix (they're exempt via `is_routable`, routing.py:62–67).
  Lane 01's "3508 total" is the **file** count; the in-memory `PLACES` list is **3524** (3508 + 16 curated).

### 02 — Frontend/UX (High)
**Correct, plus one new blind spot confirmed.**

- ✅ VERIFIED (probe6): `inferDuration` in `Planner.tsx` fails on 2 of 3 default chips —
  `'Cà phê và đi bộ cuối tuần'` and `'Ăn ngon, ít di chuyển'` return `None`; `'Một ngày văn hóa Hà Nội'`
  returns `ca_ngay`. So the two chips users see first do **not** pass the duration gate.
- ✅ VERIFIED (probe7): `LocaleProvider` en block `dataNotice` = **Vietnamese** text; 19 locales in
  `supportedLocales` (i18n-core.ts). Multi-language is keys+structure, not per-locale quality.
- ✅ VERIFIED: no `<img>`, no `og:image`, no `metadataBase` in frontend source → share-link previews are
  bare. (grep across frontend incl. `app/layout.*`, `app/plan/[token]/page.tsx`.)
- ⚠️ NEW BLIND SPOT (see §4.1): `app/plan/[token]/page.tsx` fetches `${API_URL}/api/plans/${token}`
  **server-side** with `cache: 'no-store'`. `API_URL` = `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'`
  (lib/api.ts:3). On a multi-device/deployed share link this **cannot work** because the Next server (not the
  visitor's browser) resolves `localhost:8000` — and `NEXT_PUBLIC_*` is baked at build time. Lane 02 said
  "preview works", which is only true when backend+frontend share one host.

### 03 — Replan/regenerate/refine (Medium)
**Correct mechanism, severity right.**

- ✅ VERIFIED (plans.py:387–423): regenerate excludes only the *first slot's* place, then rebuilds from
  scratch — matches "lam_lai_tu_dau" semantics.
- ✅ VERIFIED (plans.py:310–384): swipe re-validates via `validate_plan(plan, {p.id for p in PLACES}, …)`
  and uses `replacement.cost * so_nguoi` with NO cost filter in the candidate list (only kind + hours +
  used + geo-nearest) → can exceed budget → `PipelineUnavailable` → 503. Confirmed by source read.
- ✅ VERIFIED: budget regex mojibake at plans.py:434 (`ngÃ¢n sÃ¡ch`, `dÆ°á»›i`, `tá»‘i Ä‘a`), so
  `'ngân sách 500k'` → no match (probe5) while `'budget 500k'` matches. Vietnamese refine intents die.

### 04 — Share/comments/feedback (Medium)
**Correct, incomplete on abuse model.**

- ✅ VERIFIED (plans.py:258–275): `add_comment` has NO `owner()` guard — anyone with the token can comment,
  limited only by `comment:{token}:{ma_phien}` 10/hour.
- ⚠️ NEW BLIND SPOT (see §4.4): the rate-limit key contains **client-supplied `ma_phien`**
  (`CommentRequest` min_length 8, arbitrary). An attacker rotates `ma_phien` → unlimited comments per token.
  The session-id owner() check does **not** cover comments (only `owner()` endpoints do).
- ✅ VERIFIED (admin.py): 11 admin routes, zero `limiter.check` calls, token-gated by
  `SUPPORT_ADMIN_TOKEN`. Default fallback in config.py:131–133 = `"local-support-demo"` when APP_ENV=local.

---

## 3. Fix-plan assessment

| Proposed fix (synthesis §4) | Verdict |
|---|---|
| Fix diacritic folding in `relevant_tags`/profiles | **Correct and minimal.** `_ascii_fold` at planner.py:131–137 is the single highest-leverage fix; but note the `'cho'` collision must be handled (fold `đ`→`d` first, then strip). |
| Rebuild catalog with real costs/hours/durations | **Correct but not sufficient.** import script hardcodes cost=0/duration=60 (import_osm_places.py:99–104); even with real data, the deterministic-pick path (`_select_within_budget`) sorts on `(score, tags, distance, cost)` and can still starve. Needs candidate-count = desired stops (not 7-of-window). |
| Live-mode quality gate (AI not allowed until verified quality) | **Correct and the only thing that protects users.** Verified via ai.py + config: live mode requires API keys; mock is the default; `.env.example` sets `AI_MODE=groq` with **empty** API keys → out-of-box behavior is mock or 500s. A gate is the right call. |
| Shared-preview via public URL | **Correct; must be fixed or the share link is the top user-facing bug.** See §4.1. |
| Acceptance criteria: ">50% of sample requests produce a coherent, budget-compliant, schedule-valid plan" | **Unverifiable as written.** There is no dataset of sample requests, no definition of "coherent", and the current path fails on *the* default chips (probe6). Criterion should be: run the 3 default chips + 3 night/food/culture hand-picked requests in mock mode and assert `len(slots)==expected` AND intent-profile overlap > 0. |
| Acceptance criterion "regenerate produces a different but equally valid plan" | **Contradicts current code**: `_request_seed` includes `nonce`, so regenerate (which reuses the nonce? no — regenerate sends a NEW payload without nonce; seed changes via `ma_phien`?) — verified `build_plan` is deterministic for identical args (probe5). Different plan requires changing seed inputs. Fix must explicitly vary the seed. |

**Net**: the fix plan's *headline items* are right, but its *acceptance criteria* are neither executable
nor tied to the actual failure modes. The single most important fix the synthesis under-weights is
**configuration drift** (§4.6): as shipped, nothing delivers "AI" at all.

---

## 4. Blind spots NOT in the synthesis

### 4.1 (High) Share-link preview breaks on any second machine
`app/plan/[token]/page.tsx` fetches `${API_URL}/api/plans/${token}` server-side; `API_URL` resolves to
`http://localhost:8000` (lib/api.ts:3) unless `NEXT_PUBLIC_API_URL` is set at **build** time. The whole
"share plan" feature — and lane 04's share testing — silently fails cross-device. Only works when Next
and FastAPI share the same host. Fix: render token→data client-side via `/api/plans/{token}`, or set a
public backend URL in the build, or proxy `/api` in `next.config`.

### 4.2 (High) Live AI is unreachable with the shipped config; "AI mode" is effectively off
`.env.example` ships `AI_MODE=groq` + empty `API_KEY_GROQ`; `run.bat` warns but does not fail.
`config.py` defaults to `ai_mode=mock` and `app_env=local`; `create_ai_adapter()` (ai.py:361–368)
**forbids mock outside local** but allows groq only if the key is set. Net shipped behavior:
mock deterministic planner. The budget (below) is irrelevant until this is fixed. The headline
"~15/100" mostly measures the *mock* planner, not the AI.

### 4.3 (Medium) Cost model: budget is fine, but the "daily" cap is lifetime in MemoryStore
Cost math (probe9): deepseek-v4-flash ≈ $0.14/M in, $0.28/M out; per-plan ≈ 1400+1800 output tokens +
~2–3K input → **~$0.0014/plan**. At `TRAN_CHI_PHI_NGAY=10` that's **~7,100 plans/day** — affordability
is NOT the constraint at burn-in (partially refutes the "is AI affordable?" worry). BUT:
`MemoryStore.reserve_cost` (store.py:43–57) compares a **cumulative, never-reset** `cost_usd` against the
"daily" limit → in-memory store the daily cap is actually a **lifetime** cap; only `PostgresStore`
(chi_phi_ai_ngay by CURRENT_DATE, postgres_store.py:35–70) resets daily. Since `.env` is absent, the app
runs on `MemoryStore` by default → a production Local-mode budget would brick AI for the lifetime of the process.

### 4.4 (Medium) Comment/feedback abuse is trivially bypassable
Rate-limit keys are client-supplied `ma_phien` (plans.py:266) — rotate it to bypass 10/hr. No IP-level
limit on comments (unlike generate). No owner() on add_comment. Minor spam surface now; becomes real once
live sharing exists.

### 4.5 (Low) Weather timezone label is Bangkok, but offset is correct for Hanoi
weather.py:118 hardcodes `timezone: "Asia/Bangkok"`. Hanoi (Asia/Ho_Chi_Minh) and Bangkok are both
UTC+7, no DST → **no practical offset bug**; it's a cosmetic label. Don't spend effort here.

### 4.6 (Low) Live-mode config drift: `AI_BASE_URL` default follows mode, model default follows mode
config.py:104–123: base URL defaults to `https://api.groq.com/openai/v1` if groq else deepseek; model
defaults likewise. `run.bat` and `.env.example` are groq-leaning, deepseek keys exist in .env.example too.
Not a bug, but the four lanes occasionally implied "deepseek" as fixed; it's switchable per env and
drives different token prices (§4.3).

### 4.7 (Low) `reserve_cost(0.0, …)` is a no-op guard, not a reservation
plans.py:114 and 407 call `store.reserve_cost(0.0, …)` before generation. In MemoryStore that only raises
if the (lifetime) counter already exceeds the limit — it does **not** reserve. Concurrent bursts can
overshoot the daily cap; the real accounting happens in `record_ai_usage` *after* the call (ai.py:178–182).
So the budget is enforced *post-hoc* on spend, not pre-spend.

---

## 5. Headline probability and the experiments that would move it

The synthesis headline (~15/100) measures "does the product currently deliver a good AI travel plan
end-to-end". My independent run-through of the default chips confirms that in the shipped default
configuration it does not (7 cafés, wrong hours, fold-broken intents, no live AI, no cross-device share).
That supports ~15/100. The number is **credible, maybe even generous** for end-to-end quality; but it
does **not** predict whether the *core idea* can reach 70+ after fixes, because **live AI was never
exercised** in this repo state.

**Experiments that would move the verdict:**

1. **Enable a real key once and run the 3 default chips + 3 hand-picked requests** in `AI_MODE=groq`.
   If the LLM routinely picks real places and passes `validate_plan`, the mock-mode bugs become
   "demo-only" and the number jumps (→ test of the 15/100 floor). If the LLM picks unreachable ids or
   violates hours/cost constraints often, the number drops (validate_plan is the only guard and it
   hard-fails → 503).
2. **Fix `_ascii_fold` and re-run probe1/probe3.** If `'chợ đêm'`/`'đi chơi buổi tối'` then include the
   night market in the first window, the #1 blocker is disproven as permanent. Cheap, deterministic.
3. **Automate the acceptance criteria**: a script that runs N canned requests in mock mode and asserts
   `slots` count, intent-overlap, budget, and sequential hours. Today that script doesn't exist, so the
   criteria can't be "passed".
4. **Run the backend test suite on Python 3.11** (CI does; local 3.10 cannot even import). This would
   catch regressions from the fold fix and confirm `test_plan_never_exceeds_per_person_budget` still
   trivially passes (cost=0 everywhere).
5. **Deploy the share preview to a second device** — expected to fail per §4.1; if it passes, that blind
   spot is wrong.

---

## 6. Summary

The synthesis is honest and mostly right: in the shipped default (mock AI, `.env` absent), the app
produces 7 deterministic cafés for a night-out request, the fold bug kills Vietnamese night/food
intents, the catalog is cost-zero with fake hours, and the share preview only works on one host.
I reproduced the core generation bugs by running the actual code. Corrections: the rotation failure
is deterministic-per-request but probabilistic across requests; landmark-insertion is context-gated,
not universal; the catalog is 3524 places (3508 file) with 66 truly usable; budget math shows ~$0.0014
per plan so cost is not the constraint — but the "daily" cap is lifetime in the default MemoryStore;
comments bypass rate limits by rotating `ma_phien`; the admin token defaults to a public string in local
mode. The fix plan's main items are sound, but its acceptance criteria are unverifiable and omit
configuration drift, the biggest blocker. Headline 15/100 is credible for the current product state;
confidence 7/10, grounded in executed probes rather than judgment.

**Confidence: 7/10** · Ground-truth tally: 31 verified (16 executed-probe, 15 source-read) · 3 corrected · 2 runtime-unverified (backend tests on 3.11, frontend build).
