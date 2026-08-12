# 08 — Synthesis (final, red-team-merged)

> **Status:** final. Supersedes the draft synthesis circulated pre-red-team. All red-team corrections folded in; load-bearing code claims re-verified by red-team 8/8 plus 4 extra.

---

## TL;DR

"Min Di Dau The" MVP is **demos-able but not demo-clean.** The codebase is small, coherent, and surprisingly truthful about its own limitations — but it tells six small lies at once: 3,508 places but 71 routable; 60-minute visits everywhere; images requested but attribution never rendered; manual edits silently discarded by refine; a reproducible "lunch after dinner" itinerary; and Vietnamese text leaking into all 18 locales. None is fatal. All but two are cheap. Fixing them defines the roadmap.

---

## Headline findings (verified file:line)

| # | Finding | Severity | Loc |
|---|---|---|---|
| F1 | Lunch-after-dinner is reproducible (Bữa trưa: 20:10–20:55); relax pass re-widens meal `latest_end` | **Blocker** | `planner.py:980-981,1048-1049` |
| F2 | 18 of 19 locales show Vietnamese (`retryCreate:"Thu lai"`, `dataNotice` verbatim) | Blocker (demo) | `LocaleProvider.tsx:76-93` |
| F3 | Attribution `anh_nguon` declared but never rendered (only `lib/types.ts:1`) | Blocker (license) | `planner.py:1087` → dropped |
| F4 | Dark-mode itinerary actions ≈ 1.99:1 contrast, no dark override | High (demo) | `globals.css` (dark block) |
| F5 | History screen hard-coded vi-VN, no i18n | High (demo) | `history/page.tsx:33-37,113` |
| F6 | Swipe swap inherits displaced place's times | High | `plans.py:476-488` |
| F7 | `refine()` rebuilds from request, discarding manual edits, silently | High | `plans.py:697-716` |
| F8 | All 3,508 places `duration_min=60`; 0 images; wiki tags dropped by OSM import | High | `import_osm_places.py:105` |
| F9 | `_tighten_day_gaps` pads displayed duration up to +90 min as if real visit time | Medium | `planner.py:1130,1156` |
| F10 | OSRM matrix 50 ids → demo draws from ≤71 places (README claims 3,508) | **High (product-truth)** | `routing.py:62-67` |
| F11 | 404→"cannot verify", 503→"doesn't fit" misleading rejection UX | Medium | `PlanView.tsx:136` |
| F12 | Candidates unranked (no ratings/popularity); "best" currently = travel-min | Medium | `planner.py` |
| F13 | `.slot-select` covers whole card → any new link outside `.slot-actions` unclickable | Medium | `globals.css:26` |
| F14 | `visit_guidance.py` uncited "research-backed" durations | Medium | `visit_guidance.py:1,28-133` |
| F15 | Backend Vietnamese error strings ("Máy chủ không trả kế hoạch") leak to UI | Medium | `api.ts:32,42,69,83` |

---

## The two product truths this dive surfaces

1. **The demo's best itinerary is a catalog truth, not an algorithm truth.** 3,508 curated places headline the README; the demo can reach ~71. A "Tạo lại" 4× demo replays ~15. Fixing numbers first (T1.1/T1.9 → curation breadth) is what actually makes "best places" real; OR-Tools is secondary while n≤9.
2. **Manual control is already shipped but unowned.** Manual swap exists; reorder doesn't; refine wipes edits with no warning. The next feature (rank + reorder) *increases* the wipe's blast radius. The cheapest protective move is a refine-time warning, not a rebuild.

---

## Roadmap (red-team-merged)

### Tier 0 — demo blockers (buy the truth first)
- **T0.1** Fix lunch-after-dinner. Exclude `meal_type` from relax widening (`planner.py:980-981`); hard `trua→nghi→toi→dem` precedence. **AC:** structural, ≥3 nonces: `trua.ket_thuc ≤ toi.start`, `toi` after `nghi`, `dem` after `toi`, `trua.ket_thuc ≤ 14:30`. Regression test in **same commit** (suite is 33/33 green today and misses it). Red-team estimate: 15-40 LOC, not 10.
- **T0.2** Kill 18-locale leakage. **AC:** i18n purity regression added to `i18n.test.mjs` (no `/À-ỹ|Thu lai/` in any non-vi locale). Not a copy-paste pass.
- **T0.3** Localize history screen (`history/page.tsx`).
- **T0.4** Render `anh_nguon`: credit + **license** + `File:` link under slot photo AND hero; hidden only when no image. Land **before** T1.1. Note: PDF export has zero images → do not bill "PDF attribution."
- **T0.5** Dark-mode itinerary action contrast to ≥4.5:1 (measured).
- **T0.6** Swipe provenance: recompute replacement's `bat_dau`/`ket_thuc` via `_compute_slot_bounds`; **AC: non-replaced slots must not move.**
- **T0.7** Structured error mapping: `ma_loi` on 404/422/503/409; fold in the 4 `api.ts` Vietnamese strings; 409→"tải lại trang."
- **T0.8** Add `thoi_luong_phut` (pre-padding model value) + `thoi_luong_nguon ∈ {kind_default, curated, catalog, padding, vai_gio_cap}`; UI shows "linh hoạt" caption where padding.

### Tier 1 — rule-making (recommended before scale)
- **T1.1** `enrich_images.py` (safe, synchronous, cached). Gate: only after T0.4.
- **T1.2** Capture wikipedia/wikidata/wikimedia_commons/image tags in OSM import.
- **T1.3** `KIND_DURATION` table. **AC:** ≥2 named sources per kind recorded in code; kill the literal `60` in `import_osm_places.py:105`, `osm_verify.py:193`, `seed_postgres.py:59`; cite-or-demote the 13 uncited `visit_guidance.py` entries; **re-run the T0.1 regression test** (meal durations grow 60→75+ and interact with the relax pass).
- **T1.4** External-links builders (Netflix/Facebook/TikTok/YouTube). Gate TikTok/Google `udm=14` behind a one-time manual check; ship without if misbehaving.
- **T1.5** Rank candidates (rating/popularity sources) — the "best places" lever.
- **T1.6** Post-pass local search expansion (R1). Plus **H1:** refine-time warning "tinh chỉnh sẽ làm lại lịch trình và bỏ thay đổi thủ công" (or pin manual edits) — currently a named risk with **no assigned task**.
- **T1.7** Reorder endpoint — **inside** `planner.py` (reschedule helper), AC: same-day only, `validate_plan`-clean, deterministic, no AI; watch `.slot-select` overlay as drag target.
- **T1.8** Focus traps / keyboard rescue on the `.slot-select` overlay.
- **T1.9** Rating score on cards.

### Tier 2 — efficiency & polish
- **T2.1** Expand OSRM matrix 50 → curated + top-100-per-intent. **← PROMOTED from red-team H2 (the 3,508 vs 71 whitelist is a live-demo discrepancy).** Tier-0 footnote meanwhile: demo either says "50 verified anchors" or ships matrix first.
- **T2.2** Joint orienteering / OR-Tools (deferred while n≤9).
- **T2.3** `khu_vuc` through the slot.
- **T2.4** Kind-gated Commons geosearch (after T1.1 gate + T0.4).
- **T2.5** Suggestions ↔ free-text merge.
- **T2.6** Slot swap (after T0.6 pattern).
- **T2.7** Misc UI hygiene (`.slot-select` overlay → real selection affordance).

### Tier 3 — out of scope / noted
- Language for `trua` window params, live-AI freshness vs determinism tension, `EVENING_PLACE_IDS` dead code (`planner.py:54-61`), point-in-time Overpass census.

---

## Risks (red-team-merged, R1 now has a task)

R1 refine-vs-manual → **T1.6/H1**. R2 attribution gate → **T0.4-before-T1.1**. R3 duration × lunch-bug interaction → T1.3 re-runs T0.1 test. R4 `.slot-select` click-trap → T1.8. R5 external links depend on lane-3 data → T1.4 after T1.1/T0.4. R6 EVENING dead-code → noted. R7 determinism is mock-mode-only (57% claim doesn't pin a live-AI demo). R8 rate hygiene → keep. R9 citation drift (TikTok/udm) → one-time manual gate. R10 token-leak invariant → keep.

---

## Confidence (ground-truth tally)

**Findings: 8/10.** **9/10 for repo-derived claims** — 8/8 red-team re-verified at exact file:line, plus a re-run test suite (33 passed) and a raw parse of `places.json`. Deduction: external facts (TikTok URL, `udm=14`, daylight-API estimates) are second-source.

**Plan: 6/10.** Effort estimates, tier ordering, KIND_DURATION values, OR-Tools deferral are model judgment; two lanes self-grade 7. Plan's numbers are decisions, not ground truth.

**Ground-truth tally:** 14 of 15 headline findings (F1–F15) rest on directly checkable code/data/tests; 1 (F12's "best = travel-min") is partially interpretation. Roadmap numbers rest on model judgment → do not present a single 8/10 as covering the roadmap.

---

## Follow-up flags (carry to implementation)
1. Re-verify Overpass tag census at import time (lane-3 40/41/22 counts are point-in-time).
2. TikTok `?q=` / Google `udm=14` one-time manual check.
3. Re-run T0.1 tour-context regression when T1.3 lands.
4. Confirm who owns "catalog breadth" (T1.5 ranking sources) before selling "best itinerary."