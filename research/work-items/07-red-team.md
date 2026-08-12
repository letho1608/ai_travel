# 07 — Red-Team Review (adversarial pass on the synthesis)

> **Role:** adversarial reviewer. Job: TRY TO BREAK the synthesis before it reaches the product owner.
> **Method:** re-read the actual repo files, re-verify load-bearing claims, attack the plan, hunt shared blind spots.
> **Status:** complete. Every load-bearing claim was checked against the working tree; test suite re-run (`33 passed`).

---

## Verdict

**The diagnosis survives. The plan, as written, is shippable — but only if acceptance criteria are tightened and four blind spots are patched.** 8/8 primary code targets verified; zero fabricated line numbers or counts. The plan's problems are of *precision*, not *validity*.

**Confidence split:** 8/10 for the findings (9/10 for repo-derived claims); **6/10 for the plan's numbers** (effort, tier ordering, KIND_DURATION values, OR-Tools deferral remain model judgment).

---

## 1. Load-bearing claim verification

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| (a) | Lunch bug: `relax` widens `latest_end` for meals too | **VERIFIED** | `planner.py:979-981` widening applies to all places; the meal cap at `:937-940` (`latest_end=preferred_close`, lunch=13:30 from `MEAL_WINDOWS["trua"]=(11,0,13,30)` at `:37`) is undone on the relax pass |
| (a2) | Rest wins before lunch (−55) | **VERIFIED** | `planner.py:1048-1049`: `if any(mt=="nghi"...): score -= 55` while lunch pending; 20:10 lunch feasible because strict rejects but relax re-widens `latest_end` |
| (b) | 3,508 places all `duration_min=60` | **VERIFIED** | `import_osm_places.py:105`; parsed `places.json` directly: 3508/3508 = 60, kind split exact, 100% source_url, 0 wiki-tagged, 0 image |
| (c) | 18-locale Vietnamese leakage | **VERIFIED** | `LocaleProvider.tsx:76-93`: all 18 non-`vi` blocks paste `retryCreate:"Thu lai"` + `dataNotice` (Vietnamese, `en` block transliterated w/o diacritics) |
| (d) | Swipe keeps old slot times | **VERIFIED** | `plans.py:476-488`: `new_target.update({...})` — no `bat_dau`/`ket_thuc` key; inherits displaced place's clock |
| (e) | `refine()` discards manual edits | **VERIFIED** | `plans.py:697-716`: `build_plan(refined)` rebuilds from request, no pinning, no warning |
| (f) | `.slot-select` covers whole card | **VERIFIED** | `.slot-select{position:absolute;inset:0}`; siblings z-index:2 + pointer-events:none; only `.slot-actions`/`.icon-action`/`.source` get pointer-events:auto |
| (g) | `anh_nguon` never rendered | **VERIFIED** | only occurrence in `frontend/` = `lib/types.ts:1`; emitted by `planner.py:1087`, dropped |
| (h) | `_tighten_day_gaps` +90min | **VERIFIED** | `planner.py:1130`: `extend=min(gap-reserve-8,90)`; mutates `ket_thuc` at `:1156`; meals skipped (`:1123`) |
| (x1) | Dark-mode contrast ~2.0:1, no override | **VERIFIED** | computed `#086b27` on `--green-soft` (#173528 dark) = **1.99:1**; `.itinerary-regenerate`/`.itinerary-summary-actions .secondary` absent from `@media(prefers-color-scheme:dark)` block |
| (x2) | History hard-coded Vietnamese | **VERIFIED** | `history/page.tsx:33-37` (`vi-VN` formatters), `:113` hard-coded strings |
| (x3) | OSRM matrix covers 50 ids | **VERIFIED** | `distance_matrix.json`: 50 place_ids, 50×50 |
| (x4) | Tests green & miss the bug | **VERIFIED** | ran `pytest tests/test_pipeline.py` in `backend/`: **33 passed**, no meal-sequencing assertion |

**Bottom line:** every claim attacked survived direct inspection.

---

## 2. Attack on the plan

### 2.1 Acceptance criteria that admit trivially-passing implementations

- **T0.2 (locale leakage):** AC must add i18n purity regression to `frontend/tests/i18n.test.mjs` (e.g. `doesNotMatch(/[À-ỹ]|Thu lai/)` for all 18 locales) — otherwise a copy-paste pass on one locale passes while intent is half-met.
- **T0.4 (attribution):** AC = "credit + license + `File:` page link under slot photo AND hero; hidden only when no image." Also: **the PDF path ships zero images today** (`pdf_export.py` has no image rendering) — "attribution in PDF" is currently moot; don't bill it.
- **T0.6 (swipe):** AC = "replacement's `bat_dau`/`ket_thuc` recomputed via `_compute_slot_bounds`/`_pack_day_slots` + re-pass `validate_plan`; non-replaced slots must NOT move" (re-packing whole day reorders other manual edits — same trap class as M6/R1).
- **T0.8 (thoi_luong):** AC = "`thoi_luong_phut` = model duration BEFORE `_tighten_day_gaps` padding; `thoi_luong_nguon ∈ {kind_default, curated, catalog, padding}`" — otherwise it re-encodes the lie lane-6 kills.
- **T1.3 (KIND_DURATION):** AC = "each kind backed by ≥2 named sources recorded in code; `import_osm_places.py:105`, `osm_verify.py:193`, `seed_postgres.py:59` all drop literal `60`; the 13 uncited `visit_guidance.py` entries (`:28-133`) are cited or demoted from 'research-backed' claims."

### 2.2 Assumptions that aren't true

1. **"~10 LOC" for the lunch bug is optimistic.** Excluding `meal_type` from relax widening (`planner.py:980-981`) is ~2-5 LOC; but hard `trua→nghi→toi→dem` ordering interacts with `ca_ngay.reserve(2)` and `nhieu_ngay` day-split → realistically 15-40 LOC + tourism-context regression tests. AC should be *structural*, not "lunch isn't at 20:10": assert `trua` ends ≤ every `toi` start, `toi` after `nghi`, `dem` after `toi`, `trua.ket_thuc ≤ 14:30`, ≥3 nonces.
2. **OR-Tools deferral smuggles a frame:** "best itinerary" = travel-minimization. User-perceived "best" is selection quality (no ratings/popularity — lane-2 F6), parked in Tier 1. Plan must say which "best" it buys first.
3. **71-place whitelist is under-escalated.** `routing.py:62-67` makes 3,458/3,508 places unschedulable in the demo mode the PO will run. README claims "3.508 địa điểm" while a demo draws from ≤71; regenerate 4× → same ~15 places. **Promote curated + top-100-per-intent matrix expansion from T2.1 → Tier 1**; add Tier-0 footnote (UI says "50 verified anchors" or ship expanded matrix first).

### 2.3 Blind spots (missing entirely)

- **R1 (refine-vs-manual-edits) has NO task.** After T1.5/T1.7 ship, one demo act (change a place → "thêm một quán cà phê" → edits gone) surfaces the trap. **Add to Tier 0/1: refine-time toast "tinh chỉnh sẽ làm lại lịch trình và bỏ thay đổi thủ công"** (or pin manual edits).
- **Lunch-bug regression test must land in the SAME commit** as the fix, or CI stays green over the defect (it is green today: 33/33).
- **`_visit_minutes_for` `vai_gio` caps (`planner.py:857-860`)** untracked by duration ACs: sights truncate to 35/30 min; `thoi_luong_phut` (model value) will exceed displayed duration → enum needs `vai_gio_cap` value.
- **T0.4 needs a license allowlist AC:** if T1.1 ships before T0.4, CC-BY images show with credit but no license (still non-compliant). Order T0.4 before T1.1 (already done) + AC requires license + link.
- **Backend→UI Vietnamese strings:** `api.ts:32,42,69,83` ("Máy chủ không trả kế hoạch") leak into every locale; fold into T0.7 (generate path, not just swipe).

### 2.4 Severity & ordering

UI demo-blockers correctly identified; leak (T0.2) correctly first. Dark-mode 2.0:1 is polish-not-false — keep Tier 0 (~6 CSS lines) but don't let it displace T0.1.

**"Fix lunch first" + T1.3?** Yes — orthogonal layers (`_compute_slot_bounds` vs `duration_min` data), but outputs interact: after T1.3, `toi` grows 60→75 min (60-cap at `:851` lifts for 90-min restaurants) and sight durations 75-90, tightening the same windows. Lunch fix removes the relax escape BEFORE the added pressure. **T1.3 ticket must re-run the T0.1 regression test.**

### 2.5 Is 8/10 justified?

As a **diagnosis**: yes, arguably higher (8/8 + 4 extra verified). But synthesis confidence inherits the **weakest lane** (lane-1 and lane-4 self-report 7/10), and plan decisions (effort, tiers, KIND_DURATION, OR-Tools, TikTok URL) are model judgment. **Report 8/10 findings, ≤6/10 plan numbers.** Carry implementation-time flags: TikTok `?q=`, Google `udm=14`, re-verify Overpass tag census at import (lane-3 counts are point-in-time).

---

## 3. Shared blind spots (all agents, same model)

1. **"Best itinerary" prior** — all lanes imported OR/TOPTW framing (travel-minimize, score-max). None questioned whether a Hanoi demo wants 9 slots with forced lunch+evening at all.
2. **"Redesign = polish CSS" prior** — lane-1's "polish not rebuild" is consistent; the `.slot-select` full-card overlay (worst structural UX wart, also drag-target for T1.7) is rated Low by lane-1 yet a "gotcha" in lane-4; nobody flagged the overlay *itself*. Reconsider at T1.7.
3. **"Manual change = drag-and-drop" prior** — lanes lean on Trip.com/Google Trips case studies; for a chat-first MVP, the chat layer knowing about manual edits (R1) is deprioritized behind "add reorder". A warning string is cheaper and protects existing feature.
4. **"Determinism is sacred"** — a demo virtue that costs live-AI freshness; biases plan toward "no AI in edit paths" — right for swipe, ironic for refine() rebuilding deterministically.
5. **Nobody measured except lane-2** — "57% lunch rate" is **mock-mode-only**; if the PO demos live-AI, deterministic bug claims no longer pin. Plan should say so.

---

## 4. Blocker / High / Medium / Low with surgical fixes

### Blockers
- **B1. Lunch-after-dinner.** `planner.py:980-981` + `:1048-1049`. Fix: exclude `meal_type` from relax widening AND enforce `trua→nghi→toi→dem` hard ordering, regression test in same commit. NOT a bare 5-line patch.
- **B2. Attribution never rendered while CC-BY images shown.** `types.ts:1`/`planner.py:1087`/`PlanView.tsx:223`. Fix (T0.4): credit + license + `File:` link under slot photo & hero; land before T1.1; AC requires license.

### High
- **H1. Refine wipes manual edits, no warning.** `plans.py:697-716`. Fix: interim warning string at refine time (lane-5 §6); pinning later. ~1 hour; protects manual-control investment T1.5/T1.7 creates.
- **H2. Demo advertises 3,508 but routes on ≤71.** `routing.py:62-67`, matrix 50 ids. Fix: promote matrix expansion T2.1 → Tier 1; Tier-0 demo-copy footnote.
- **H3. Reorder (T1.7) will fight `.slot-select` overlay + `validate_plan` sequential-time assumption (`planner.py:1421-1445`).** Fix: reschedule helper inside `planner.py`; AC = same-day only, `validate_plan`-clean, deterministic, no AI.
- **H4. 18-locale leakage.** Already Tier 0; add i18n purity regression to `i18n.test.mjs`.

### Medium
- **M1.** `_tighten_day_gaps` padding shown as visit time. Fix (T0.8): pre-padding model value + `nguon="padding"`; "linh hoạt" caption; cap drift (lane-6 §6.2).
- **M2.** Swipe inherits displaced clock. Fix (T0.6): recompute bounds; AC pins other slots don't move.
- **M3.** 404→"cannot verify in Hanoi", 503→"doesn't fit" (`PlanView.tsx:136`). Fix (T0.7): `ma_loi` on 404/422/503/409; 409→"tải lại trang".
- **M4.** `visit_guidance.py` uncited "research-backed" durations (`:1,28-133`) survive T1.3. Fix: cite or demote in same PR.
- **M5.** Backend Vietnamese error strings (`api.ts:32,42,69,83`). Fix: fold into T0.7.

### Low / notes
- **L1.** Dark-mode pill/contrast — Tier 0 CSS; AC = ≥4.5:1 measured.
- **L2.** `EVENING_PLACE_IDS`/`FALLBACK` hard-coded (`planner.py:54-61`) — keep as R7 note.
- **L3.** TikTok URL / `udm=14` — gate behind one-time manual check; ship without if misbehaves.
- **L4.** `.slot-select` overlay as UX wart — revisit at T1.7, not before.

---

## 5. Final verdict

**Safe to hand to the PO?** Yes — as a *verified diagnosis* (first artifact telling the truth about where the 60-minute number, images, and manual-edit wipe come from, and demonstrably accurate). Do NOT hand the Tier 0-2 plan as a costed commitment without §2.1 AC tightening and H1/H2 additions — five Tier-0/1 items can be "completed" without achieving intent, and two product traps (refine-wipe, 71-place whitelist) have no assigned work.

**Safe confidence:** **8/10 findings** (9/10 repo-derived; deduction = external facts + mock-mode-only 57%). **6/10 plan.** Do not present a single 8/10 to the PO as covering the roadmap; it covers the diagnosis.
