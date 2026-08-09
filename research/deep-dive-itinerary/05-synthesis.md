# 05 — Synthesis: Deep-Dive on AI Travel (itinerary feature)

Date: 2026-08-07
Scope: 4 parallel lanes (01 generation core, 02 frontend/UX, 03 replan/audit, 04 share/integration)
Verification: every claim below was re-verified by direct source read and executed probes in this session.

---

## 1. Two-hundred-word summary (plain English)

The itinerary feature is a heavily engineered **defensive shell around a hollow core**. All the infrastructure
is genuinely production-grade — routability matrix, two-opt optimizer, circuit breaker, rate limits, optimistic
concurrency, SSE streaming, provenance tracking, validator, PDF/ICS export, admin panel — but the *planning logic*
the user actually sees is a deterministic heuristic over a pool of just **66 usable places** (50 routable OSM nodes —
36 cafés, 14 museums — plus 16 curated anchors) with **all hours 07:00–22:00, all costs 0, all durations 60 min**.
The default runtime is `AI_MODE=mock`, where MockAIAdapter returns "candidates[:count]" — there is no LLM at all.

Six owner complaints were checked; four are code-proven defects visible on the first session. The night market
is unreachable because a bug strips the `đ` from "chợ **đ**êm" (never matched), and it is scheduled in the morning
because every venue advertises a 07:00 open. "Hồ Gươm / Lăng Bác" are force-inserted by `_highlight_places` into
any Hanoi plan. The input is a form, not a chatbot — and it rejects its own suggestion chips (2 of 3). There are
zero images anywhere. Replan primitives (swipe/refine/regenerate/versions) all work and return HTTP 200, but
regenerate severs the version chain, refine discards edits, and the Vietnamese intent regexes are byte-corrupted
(đổi/3 người/ngân sách never parse). The share button copies a `http://localhost:3000` URL that is dead for 100%
of recipients; the API URL and CORS are localhost-only by config.

The app is architected like a production system but **behaves like a demo**. The good news: most defects are
mechanical (encoding bugs, a `đ`-folding bug, one config seam) and fixable in days.

---

## 2. Verdict on each of the six complaints

| # | Owner complaint | Verdict | Evidence |
|---|---|---|---|
| 1 | Generated itineraries are bad — worse than plain LLM; night market scheduled in the morning; Hồ Gươm/Hồ Tây/Lăng Bác hardcoded | **CONFIRMED** (all 3 sub-claims) | Fold bug drops `đ` → "chợ đêm" never matches night intent (`planner.py:131-137`); executed probe: "đi chơi buổi tối 2 ngày" → 7 cafés 08:00–15:41. Every venue advertises open_hour=7 via default `osm_verify.py:174-175` + catalog copy; scheduler only reads `open_hour` (`planner.py:536-537`). `_highlight_places` force-inserts all 4 anchors for any context with "Hà Nội" terms (`planner.py:191-211`; `test_pipeline.py:81-93` treats this as desired). "Worse than plain LLM" is structural: in mock mode there is no LLM (MockAIAdapter pass-through, `ai.py:74-95`); in LLM mode the fuzzy matcher maps "Phố cổ"→"Phở hà nội" and "Lăng Bác"→"Lẩu Hơi Lãng Bạc" (`osm_verify.py:100-119`). |
| 2 | Input is not a chatbot | **CONFIRMED (worse than reported)** | Create input is a textarea+people form, not a chat (`Planner.tsx`). Worse: `inferDuration` rejects the app's *own* chips — "Cà phê và đi bộ cuối tuần" and "Ăn ngon, ít di chuyển" get no duration → `BLOCKED` (`Planner.tsx:66-73`, `LocaleProvider.tsx:75`); "cuối tuần" not in the fallback regex. Refine side has a chat panel (`PlanView.tsx:98`) but it is a command line with fixed boilerplate replies (`parseReplyKey`, `PlanView.tsx:25`). |
| 3 | UI is not pretty | **PARTLY (subjective)** | CSS is coherent & culturally themed (rice-paper palette `globals.css:1`) but flat: zero images, no hero, no dark mode, text-only unicode icon buttons, 8-action header that does not wrap on mobile (`globals.css:18`), chat-first mobile ordering buries the itinerary. Dominant driver is "no photos" (complaint #4) + flat cards. |
| 4 | No photos per destination | **CONFIRMED** | No image field on `Place` (`data.py:10-24`), places.json, or `Slot` serializer (`planner.py:543-556`); no `<img>` anywhere in frontend; no `og:image` (`page.tsx:6`). |
| 5 | No replan (back or front) | **PARTLY — primitives exist but don't compose into real replan** | Falsely nothing: swipe/refine/regenerate/versions/restore all wired and return 200 (`plans.py:310-384, 387-423, 452-498, 501-511, 514-535`; `PlanView.tsx:79,80,82,83,87,99`). But regenerate does full-page nav to a new token, orphaning the version chain (`store.py:63-70`, `PlanView.tsx:87`); refine rebuilds from scratch discarding swipe edits (`plans.py:482-488`); Vietnamese intent parsing is dead via mojibake regexes (`SWAP_INTENT`, `PEOPLE_INTENT`, budget regex in `plans.py:30-40,434` — executed probe confirms NO match on "đổi"/"3 người"/"ngân sách 500k"). |
| 6 | Share button doesn't work | **CONFIRMED — with mechanism** | Copy works on creator's localhost, but the shared URL is `location.href` = `http://localhost:3000/plan/<token>` (`PlanView.tsx:77`) — recipients resolve it to *themselves* → connection refused. API URL baked (`api.ts:3`), CORS localhost-only (`config.py:10-14`), no public base URL, no Web Share API, no og:image, 30-day expiry (`store.py:64`). "Share" = copy-of-a-dead-URL for 100% of recipients. |

Cross-lane contradiction resolved: lane 02 read the byte-corrupted backend regexes as "probably self-consistent and would work if byte-identical"; **refuted by execution** — `PEOPLE_INTENT.search("đi 3 người")` returns NO match, so lane 03's "intent parser is dead" stands.

---

## 3. Root-cause clusters

1. **Vietnamese text handling is broken at every layer.**
   - `_ascii_fold` strips `đ` (NFKD + ascii-ignore) in `planner.py:131-137`, `osm_verify.py:63-69`, `plans.py:429`; frontend keeps `đ` (NFD + strip combining, `Planner.tsx:62-64`) → sides disagree. This single bug makes the night market unreachable and walk/evening intent dead.
   - Byte-corrupted backend strings and regexes (double-encoded mojibake): `plans.py` (16× `khÃ´ng`), `schemas.py` (2×), `planner.py` (1×); `SWAP_INTENT`/`PEOPLE_INTENT`/budget regex contain `Æ°á»i` etc. (proven dead by execution).
   - Frontend mojibake: `en` strings contain `â€¦`; `dataNotice` leaks a Vietnamese string into **every** non-VN locale.
   - Downstream: garbled error messages, the "đổi" path silently returns the same plan, budget/people intents silently ignored.
2. **The deterministic cage defeats intent.**
   - Seed rotation (`planner.py:272-280`) pushes the top intent match out of the picking window — the intent is found, then discarded for rotation variety.
   - Hardcoded anchors (`planner.py:191-211`) override intent every time.
   - Fuzzy name matching (`osm_verify.py:100-119`) turns "Phố cổ Hà Nội"→"Phở hà nội", "Lăng Bác"→"Lẩu Hơi Lãng Bạc".
   - Budget is a no-op (costs are all 0); the LLM can only *name* places inside the cage; in mock mode it does nothing at all.
3. **The data model can't express reality.**
   - 3,508 imported places, but only **66** are usable at runtime (50 routable OSM in `distance_matrix.json` — 36 cafés + 14 museums — plus 16 curated anchors; not 68 as lanes reported).
   - All hours 07:00–22:00, all costs 0, all durations 60 (`import_osm_places.py:99-104`); `opening_hours_raw` is discarded (`data.py` loader).
   - Zero evening/nightlife venues → "buổi tối" cannot be satisfied by data, only by bad scheduling.
   - No images on any entity.
4. **Deployment model makes everything localhost-bound.**
   - `NEXT_PUBLIC_API_URL=http://localhost:8000`, CORS `http://localhost:3000` (`config.py:10-14`), no `metadataBase`/og:image, `run.bat`-based startup, `AI_MODE=mock` default (`config.py:23,101`).
5. **Replan exists but doesn't compose.**
   - All primitives wired, but: regenerate severs the version chain, refine discards swipe edits, swap = nearest-place without re-time, no keep/drop constraints, no diff, no visual "what changed".
6. **LLM is underused and mock is the default.**
   - `MockAIAdapter` trivially passes through (`ai.py:74-95`); `draft()` returns `[]` in mock; the LLM-first path is inert in the default runtime.

**Pattern:** the effort went into infrastructure & safety; the risk lives exactly where user-facing value does (intent parsing, catalog quality, scheduling semantics, deployment). Classic "defensive shell around a hollow core."

---

## 4. Recommendations (prioritized)

**Tier 0 — blockers (≈1 day):**
1. Fix `_ascii_fold`: replace NFKD+ascii-ignore with a `đ`-preserving transliteration map (or compare raw + diacritic-insensitive tokens) in `planner.py:131-137`, `osm_verify.py:63-69`, `plans.py:429`. Unblocks night market, evening intent, old-quarter streets, "đổi". (1–2h)
2. Re-encode backend to clean UTF-8 and repair the intent regexes (`plans.py`, `schemas.py`); fix `en` mojibake + `dataNotice` leak. Unblocks đổi/3 người/ngân sách parsing and clean errors. (0.5–1h)
3. Remove or scope the seed rotation (`planner.py:272-280`) so the top intent matches are always in the window. (0.5–1h)
4. Soften `inferDuration` (`Planner.tsx:66-73`): default unknown → `ca_ngay`, and localize the block message; add "cuối tuần". Stops rejecting the app's own chips. (1–2h)

**Tier 1 — this sprint (≈2–3 days):**
5. Public deployment + config seam: `NEXT_PUBLIC_BASE_URL`/API URL, CORS for prod origin, build share URL from token not `location.href` (`PlanView.tsx:77`, `api.ts:3`, `config.py:10-14`). Fixes share 100%. (3–6h)
6. Real catalog: stop discarding `opening_hours_raw`, import nightlife/night-market tags, real hours/costs. (4–8h data work)
7. Photos MVP: `image_url` on Place/Slot + render + og:image. (4–8h)
8. Regenerate in-place (keep token, `store.update`) + link old plan. (3–4h)
9. Refine: confidence-gate — don't claim "done" when no intent parsed; carry edits. (2–3h)

**Tier 2 (next sprint):** keep/drop constraints + UI; diff/what-changed; real AI default in deploy (groq/deepseek) with routability+hour checks; Web Share API; mobile itinerary-first + header wrap; budget UI; TZID Asia/Ho_Chi_Minh.

**Tier 3 (polish):** dark mode, icon set, PWA manifest, a11y (aria-selected, skip-link), comments owner-guard policy, shared-link expiry policy.

---

## 5. What would I change first if I were the PM

Ship **Tier 0 + #5 + #7 in the same sprint** (≈4–5 days). Rationale: Tier 0 unblocks intent fidelity everywhere (directly attacking complaint #1 and #5), #5 makes share (complaint #6) and prod LLM possible, #7 is the cheapest visible wow for complaints #3/#4. Deploy on a public HTTPS origin with real AI mode *before* polishing UI — that is the moment the app stops "behaving like a demo."

---

## 6. The single highest-leverage change

**Fix the Vietnamese text layer (đ-preserving fold + clean re-encoding).** One mechanical root cause sits under complaints #1 (night market unreachable), #5 (đổi/người/ngân sách unparsed, silent wrong results), and the mojibake error surfacing. It also makes the app's own intent machinery actually fire for its own copy ("chợ đêm", "cuối tuần"). Caveat, stated honestly: it does not fix the 66-place, all-daytime, zero-cost pool — that requires the Tier 1 data work (#6). The fold fix is the cheapest lever that moves the most behavior; data + deployment are the second and third levers.

---

## 7. Risks of being wrong (what wasn't verified)

1. The exact "lottery" outcome for "đi chơi buổi tối 2 ngày" (market at 19:55, lane 01 probe 5) — mechanism verified arithmetically, not that exact seed outcome.
2. Mock regenerate "oscillation between 2 variants" (lane 03 §2.2) — model-executed in mock; production LLM variety is inference.
3. Chrome ≥146 `execCommand`-in-microtask no-op (lane 04) — web-evidence based, not executed in a real browser.
4. Zalo WebView clipboard/share specifics — no device testing.
5. Specific catalog-match resolutions (Phở hà nội, Chợ đêm Hàng Đào–Đồng Xuân) — mechanism verified, exact tie-breaks are my replication.
6. "Hồ Gươm/Lăng Bác hardcoded = defect" — code fact verified; the *value judgment* is model judgment (tests treat it as desired).
7. "70–90% of natural create inputs rejected" — regex behavior verified; the frequency is an estimate.
8. Usable-pool count corrected to **66** (50 routable OSM + 16 curated); lanes reported 68 — minor, verified here.
9. No live browser test of the share flow, PWA, or i18n at runtime (static source read).

---

## 8. Confidence & ground-truth tally

**Confidence the as-built app meets the owner's expectations: 15 / 100.**

Reasoning: 6/6 complaints have at least partial merit and 4 are code-proven defects visible on first use; the default runtime is mock with a 66-place, zero-cost, all-daytime catalog; share is structurally dead off-host; generation is near-random in default mode. But the app is genuinely functional (plans, map, swipe, versions, comments, PDF/ICS, i18n, admin) and most defects are mechanical → after Tier 0+1 (≈3–5 days) I estimate 65–75%.

**Ground-truth tally:** 31 external/code-checked facts (direct source reads + executed probes), 4 model-judgment items (#3 judgement, #6 value judgment, #7 estimate, "worse than plain LLM" structural argument). Not rounded up.
