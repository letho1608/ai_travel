# Work Item 02 — Itinerary Generation Algorithm ("Nghiên cứu thuật toán để sinh lịch trình tốt nhất")

**Lane:** itinerary generation algorithm evaluation
**Repo:** `D:\Code\aithucchien\ai_travel` (FastAPI backend) — **research only, no code was changed**
**Date:** 2026-08-11
**Method:** full read of `planner.py` (1912 lines), `routing.py` (96), `visit_guidance.py` (153), `data.py` (376), `schemas.py`, `test_pipeline.py` (737); direct execution of the real planner in `AI_MODE=mock` (read-only) to collect empirical numbers; plus external OR literature (sources cited inline, 2+ per claim where numerical).

---

## 1. TL;DR

The current planner is a **deterministic, constraint-guaranteed, domain-tuned heuristic** that is genuinely good at *feasibility* (every sampled plan respects opening hours, travel time, budget, dedup, night-market ≥18:00 floors). It is **not globally optimal** on any crisp objective, and it contains **one reproducible user-visible bug**: in ~57% of full-day *tourism* contexts the **"Bữa trưa" (lunch) slot is scheduled at 20:10–20:55 — after dinner and the night market** (`planner.py:974–983` relax-window widening combined with the rest-penalty ordering at `planner.py:1048–1049`). The existing test suite does not cover this context combination, so all 33 tests pass today.

Beyond the bug, the core architectural gap is that **place-selection and routing/scheduling are solved sequentially, not jointly** — i.e., the problem is really the *Orienteering Problem with Time Windows* (select ≈4–6 of ~50 candidates maximizing fit under a time budget), but the code does selection-by-score first and feasibility-routing second. For n≈6–9 stops this can be fixed cheaply (exhaustive/beam search over the chosen set); integrating OR-Tools is a larger, later, optional step. Estimated benefit of the highest-leverage cheap fixes ≈ removes a visible defect + ~5–15% travel reduction on spread-out plans; OR-Tools adds maybe 0–38% travel headroom in the *worst* (spread-out) cases but competes with the preference/window objective and adds a heavyweight dependency.

---

## 2. Ground truth: what the code actually runs on (measured)

Measured by executing the planner (mock AI, local data, seeded identical to tests):

| Quantity | Value | Evidence |
|---|---|---|
| Places loaded | 3529 (3508 OSM + 21 curated) | `data.py:79–307`; runtime |
| OSRM matrix edges | 2500 (= 50×50), 50 place_ids, all OSM ids | `distance_matrix.json` metadata (`place_count:50`); `routing.py:14–41` |
| **Routable (schedulable) places in local mode** | **71** (50 in matrix + 21 curated/nominatim) | `is_routable` `routing.py:62–67`; runtime |
| Matrix vs haversine per-edge | median |Δ| 10 min, p95 39, max 58 | measured over all 2500 matrix edges |
| Matrix hits in typical plans | 0–2 of 8–17 consecutive pairs | measured over 60 plans |
| Selection pool (`choose_candidates`) | ≈34 per tourism request; quality_pool cap 80–120 | `planner.py:1371`; runtime |
| Typical full-day cardinality | 9 slots (4–5 sights + 2 meals + rest + evening) | measured |
| Build latency (mock) | 116–477 ms | measured |
| Determinism | identical for identical request; varies by `nonce` | measured; `planner.py:212–223, 1383–1389` |
| **Late-lunch bug rate** | **34 / 60 sampled full/multi-day plans (57%)** | measured, sections 4.4 & 6 |

Key implication: in the default/local mode the planner **effectively operates on a 71-place whitelist** (`routing.py:62–67`). 3458 of 3508 OSM places can *never* appear in a local plan even though the README advertises "3.508 địa điểm OSM và ma trận OSRM đã kiểm chứng" (`README.md:17`). Production mode (PostgreSQL `bang_khoang_cach`) lifts this, but the local demo experience is the whitelist.

---

## 3. Current algorithm, reverse-engineered (step by step, with file:line)

### 3.1 Inputs and global limits
`LIMITS = {"vai_gio":(4,300,1), "nua_ngay":(5,600,1), "ca_ngay":(8,900,1), "nhieu_ngay":(16,900,2)}` (count, minutes/day, days) — `planner.py:24–30`. Day clock always **08:00 → 08:00+max_minutes** (08:00–23:00 for full/multi day) — `planner.py:1843–1846`. Meal windows, durations and preferred starts are hand-coded constants — `planner.py:35–49`. Night-market plane places and evening fallbacks hard-coded — `planner.py:54–61, 155–165`.

### 3.2 Candidate selection — `choose_candidates` (`planner.py:1332–1390`)
1. Derive context tags via `relevant_tags` (ascii-folded words, bigrams, trigrams) — `planner.py:200–209`.
2. Match against `INTENT_PROFILES` (hanoi_highlights, coffee, food, culture, night, walk) — `planner.py:122–153, 231–248`.
3. Filter PLACES by: not excluded, `cost <= ngan_sach`, `is_routable`, not a non-travel business name, old-quarter curation gated, night places excluded for short durations, cafes excluded absent coffee intent — `planner.py:1340–1357`.
4. **Sort (the ranking is the "score function")** — `planner.py:1358–1370`, lexicographic tuple:
   `-intent_score`, sight-kind, `dia_danh/bao_tang`, source=curated, tag-overlap count, haversine distance to request origin, cost, seeded hash tiebreak.
   `_intent_score` gives **+3 per matching profile kind** and **+1 per overlapping tag** — `planner.py:239–248`.
5. Keep top `max(80, min(len,120))` as `quality_pool` (normally ALL, since pool ≈34) — `planner.py:1371`. Send only `candidates[:80]` to the AI proposer — `planner.py:1471–1489`.
6. **Deterministic variety**: for intent matches, pin top `min(keep,3)` then `random.Random(seed).shuffle` the rest (seed = SHA-256 of context|duration|people|budget|session|nonce) — `planner.py:1378–1387`; otherwise rotate pool by `seed % len(pool)` — `planner.py:1388–1389`. Curated **highlights are force-prepended** — `planner.py:1376–1387`.

### 3.3 Sight selection — `_select_sight_places` (`planner.py:1727–1756`)
Hierarchy: **(a) LLM-first** names verified via Nominatim (`_select_llm_first_places` + `verify_place_name`, `planner.py:1527–1576, 1548`), else **(b) AI `propose_place_ids`** over the constrained payload (ids only; copy comes later from the fixed list), else **(c) deterministic greedy-in-rank `_select_within_budget`** (take in candidate order while cost fits budget) — `planner.py:1451–1468, 1747–1750`. Count of sights to select: `_sight_total = count − meals_total − reserve(2)` (full/multi-day) → e.g. ca_ngay central 8 − 2 meals − 2 = **4 sights**; nhieu_ngay 16 − 4 − 2 = **10 sights** — `planner.py:485–490`.

**Weakness (structural):** this phase has **no timing information at all**. It does not check opening-hour conflicts between chosen stops (e.g., two morning-only places), does not check route length, and does not consider the time budget. It is a *score-greedy selection*, not an *orienteering selection*.

### 3.4 Ordering heuristics (the "routing" layer)
- `_ordered_route` (`planner.py:1682–1724`): partition chosen sights into **morning-only / flexible / outdoor / evening**, and within each group sort by haversine bearing from current cursor, then **run `nearest_neighbor` + `two_opt` only if the group has >2 places**. `nn` uses haversine (`routing.py:70–79`); `two_opt` *improves* using matrix-based `route_cost`/`travel_minutes` (`routing.py:82–96, 54–59`). This ordering determines the **multi-day day-split**: `split_index=(len+1)//2`, day1 = first half — `planner.py:1775–1781`.
- `_interleave_meals` (`planner.py:691–725`): rebuild the day as `morning → morning_flex → LUNCH → outdoor/afternoon_flex → DINNER → evening places → other meals`, splitting flexible sights roughly evenly between morning and afternoon.
- `_build_day_route` (`planner.py:622–688`): insert **midday rest** (`nghi`, a cafe chosen nearest anchor) right after lunch slot when budget allows; optionally add an **extra sight** after lunch if the day is thin; always append an **evening stop** (`dem`) after dinner for full/multi-day, choosing from hard-coded `EVENING_PLACE_IDS` → `EVENING_FALLBACK_IDS` → any `_is_evening_place` (`planner.py:504–512, 571–619`).
- **Crucially, the final slot order is NOT the 2-opt order.** Both `_ordered_route` (group order) and `_interleave_meals` only *seed* the list handed to `_pack_day_slots`, which then greedily re-ranks every step (below). The 2-opt output affects only (a) which weights go to morning vs afternoon within a group and (b) which sights land on day 1 vs day 2 for `nhieu_ngay`.

### 3.5 Slot assignment — `_compute_slot_bounds` + `_pack_day_slots` (the real scheduler)
`_pack_day_slots` (`planner.py:994–1105`) simulates time by a **single greedy pass with one-step lookahead**:
- cursor starts 08:00; for each step, for each remaining stop, compute `arrive = cursor + travel`; call `_compute_slot_bounds` (`planner.py:914–991`) which returns `(start, end, visit)` satisfying: place opening hours (`_effective_hours`, `planner.py:755–764`), `day_end`, preferred window (`_pick_visit_window`, `planner.py:816–842`), and visit duration (`_visit_minutes_for`, `planner.py:849–861`). A **`relax=True` pass re-widens `latest_end` to `min(closing, day_end)`** whenever the strict pass fails — `planner.py:979–983` (this is the meal-window bug locus).
- Score each feasible candidate — `planner.py:1037–1062`:
  `score = preference_score(place, meal, hour)` − `idle×0.6` − `travel×0.15` − `(5 if relax)`; plus ordering penalties: dinner −30 while lunch pending; rest −40 while lunch pending; **anything −55 while rest pending** (`planner.py:1048–1049`); dinner −45 while daytime sights pending; evening −50 while dinner pending; evening sights −50 while dinner pending. `_preference_score` (`planner.py:864–905`) is a hand-tuned piecewise function over preferred windows (range ≈ [−50, 20]).
- Take the argmax, build the slot dict, append, advance cursor/previous — `planner.py:1063–1103`.

### 3.6 Gap management and repair
- `_tighten_day_gaps` (`planner.py:1108–1157`): extend an earlier visit's end to absorb gaps ≤90 min above reserve, capped by preferred-window end, close hour, day end.
- `_backfill_day_gaps` (`planner.py:1165–1277`): for any inter-slot gap ≥ 55 min (`MAX_GAP_BEFORE_FILL_MINUTES`, `planner.py:52`), repeatedly query `_choose_extra_sight` (nearest, ranked, must be routable & midday windows) until one fits the gap with travel, then insert; retries on failure (tested at `test_pipeline.py:308–341`). **Note:** gap-fill never tries a *different* neighborhood candidate ordering — it is `current → option → next`, constrained to place time + travel into `next_start`.

### 3.7 Validation, AI adapter, determinism
- `validate_plan` (`planner.py:1393–1448`) re-checks: slot cardinality within `_min_plan_slots`/`_max_plan_slots` (`planner.py:493–501`), ids trusted, no duplicate ids/names, chronological+non-overlapping slots, opening-hour fit, ≥ travel-time between consecutive places, budget.
- `build_plan` runs selection→ordering→day-split→per-day meals→schedule→backfill, then lets the AI adapter `assemble` **rewrite only copy/notes from the fixed list** (`planner.py:1901–1908`; `ai.py _apply_copy` enforces `mo_ta_theo_id ⊆ trusted_ids`), re-validates, and raises `PipelineUnavailable` on violation — `planner.py:1909–1911`.
- Determinism: everything except the AI calls is seeded from `_request_seed` (session+nonce); shuffle uses a per-request `Random(seed)`. In `AI_MODE=mock` the whole pipeline is deterministic (verified: identical requests → identical slot ids; different nonces → different). With live AI (proposal/LLM-first/assemble), outputs can vary by design.

---

## 4. Measured behavior

### 4.1 Cardinality / timing
Full-day tourism plans: 9 slots typical (4–5 dia_danh/bao_tang + trua + toi + nghi(rest) + dem(evening)); travel total 49–75 min/day; idle-beyond-travel 17–75 min/day (portion is intentional window-wait, e.g., waiting for Hồ Gươm 16:00 window). Multi-day: 18 slots, travel 183 min. Build time 116–477 ms — there is ample headroom for stronger search (≤10 ms exact search over ≤9 stops is trivial).

### 4.2 Determinism
Verified: same request (same session+nonce) → identical slot id sequence; changing nonce → different sequence. Consistent with `test_same_intent_can_generate_different_routes_with_new_nonce` (`test_pipeline.py:403–412`).

### 4.3 OSRM matrix usage
Only **0–2 of the 8–17 consecutive inter-stop pairs** in sampled plans are matrix-backed; the rest use `haversine ×1.4/22 km/h` fallback (`routing.py:59`). For the 50 OSM-matrix ids the matrix differs from the haversine fallback materially (median gap 10 min, p95 39 min, max 58 min), confirming it is real OSRM data — it just *never touches curated anchors and most OSM stops*, which dominate plans. Any "optimized day" claim is therefore mostly haversine-based.

### 4.4 Reproducible meal-ordering bug ("lunch at 20:10")
Across 60 sampled full/multi-day requests (10 contexts × 6 nonces), **34 (57%)** produced this pattern:

```
08:00–09:15 Hồ Tây | 09:27–10:27 Lăng Bác | 10:34–12:00 Phố cổ Hà Nội | 12:30–13:15 Café Đinh (nghi)
13:20–15:20 Hàng Dầu | 16:00–17:40 Hồ Gươm | 18:00–18:45 Bún chả Đắc Kim (toi)
18:50–20:05 Chợ đêm Hàng Đào (dem) | 20:10–20:55 **Phở Bát Đàn (trua)**
```

Mechanism (traced through the code):
1. `_build_day_route` inserts the rest (`nghi`) into `route_stops` right *after* the lunch item (`planner.py:635–642`).
2. In `_pack_day_slots`, while any rest is pending, **every non-rest stop loses 55 points** (`planner.py:1048–1049`), including lunch — so at ~12:00 the rest wins the slot (12:30) **before** lunch.
3. After the rest, lunch competes normally against attractions; Hồ Gươm's 16:00 window, dinner, and the evening stop each outscore it, so lunch is deferred.
4. Because evening/night-market floors are only on `earliest` (`planner.py:934–935, 960–971`) while **`relax=True` widens `latest_end` for mealtimes too** (`planner.py:979–983`), a 20:10 "lunch" eventually passes the relax pass with ~ −20 score vs nothing.

Aggravating factor: for `ca_ngay`, lunch window bounds `earliest=max(arrive, 11:00)`, `latest_end = preferred_close (13:30)` even in strict mode (`planner.py:936–940`), so the *strict* pass correctly rejects 20:10 — the relax pass is the escape hatch. **Existing tests do not cover this** because the tourism backbone context is only asserted for names (`test_pipeline.py:495–507`) and the meal-timing tests use the chilled 'ăn ngon' context (`test_pipeline.py:11, 71–100`) where lunch lands at 11:59. All 33 pipeline tests currently pass (verified by running `pytest tests/test_pipeline.py`).

---

## 5. Complexity and soundness

- **Complexity:** candidate selection O(PLACES×tags) ≈ trivial; greedy scheduling O(n² × bounds_cost) with bounds ≤13 `_compute_slot_bounds` recomputations; `two_opt` O(k³) per group with k≤group size (small). Backfill rescans `_choose_extra_sight` over a filtered PLACES pool per gap (O(PLACES) per candidate). Everything is comfortably sub-second.
- **Feasibility soundness:** high. Hard constraints (hours, day_end, travel, budget, dedup, night floor) are enforced in two independent layers (`_compute_slot_bounds` and `validate_plan`) and, empirically, no sampled plan violated them. The `relax` escape guarantees a plan exists in almost all cases — at the price of soft-goal violations (the lunch bug).
- **Optimality soundness:** low by construction. There is no objective being *optimized*: `_preference_score` weights (0.6 idle, 0.15 travel, −5 relax, −30/−40/−45/−50/−55 ordering) are hand-tuned, interdependent, unvalidated against user preference, and unreachable thresholds (e.g., −30 dinner "while lunch pending" vs a 60-min travel difference) make small-travel degradations acceptable to the greedy. The final route is a greedy chain, **not** a TSP/TSP-TW solution, and not followed by any post-pass re-optimization of the final slots.
- **Multi-day coupling:** day 2 starts fresh at the same origin coefficient 08:00 (`planner.py:1843–1846`); no leg is counted between "hotel→first stop" or "last stop→hotel" on either day, and no end-of-day return is modelled. Day split is a naive halving of the 2-opt chain (`planner.py:1775–1781`) — cross-day travel correlation is not optimized.
- **Time-of-day travel:** `travel_minutes` is time-invariant (single profile from matrix/`driving`); rush-hour Hanoi congestion is not modeled (`distance_matrix.json` metadata `profile: driving`).

---

## 6. Findings catalog (severity-tagged)

| # | Severity | Finding | Evidence / locus |
|---|----------|---------|------------------|
| F1 | **Blocker** | **Lunch ("trua") slots scheduled at 20:10–20:55, after dinner and night market, in ~57% of tourism full-day plans.** Violates the meal-window design intent and is plainly wrong for users; the test suite misses it. | `planner.py:979–983, 1048–1049`; measured 34/60 sampled days |
| F2 | High | **Selection is decoupled from schedule feasibility** (orienteering gap). Sight selection ignores time windows, route length, and the day's feasibility; nothing prevents selecting 2 afternoon-only or 2 morning-only museums. Repair is reactive (backfill/relax) rather than preventive. | `planner.py:1727–1756` vs `994–1105`; OPTW/TOPTW literature §7.1 |
| F3 | High | **2-opt does not optimize the final day route.** The greedy `_pack_day_slots` reorders the seeded list by `preference − idle×0.6 − travel×0.15` (travel weight ≈0.15 vs preference range ±50), so inter-stop travel can zigzag when preference dominates. `two_opt` runs only on intra-group order & the day-split (multi-day). | `planner.py:1037–1042, 1682–1724`; measured feasible-travel headroom up to 38% on culture plans §8 |
| F4 | High | **Local-mode routable universe is only 71 places** (50 OSM + 21 curated) of 3529. 3458 OSM places can never appear in local/dev plans despite README dedicated catalogue; PoC/quality and dev/prod parity risk; also caps the candidate pool diversity that drives "variety". | `routing.py:62–67`; `distance_matrix.json`; measured |
| F5 | Medium | **Travel times for most of the day are haversine-estimated, not road-based.** Matrix covers only 50 OSM ids; 0–2 of the typical 8–17 route legs use it. Within-Hanoi road vs straight-line error can be 2–4× (e.g., cross-River, Old Quarter one-ways). | `routing.py:54–59`; measured; `README.md:58` (PoC-2 already flags OSRM-vs-haversine deviation) |
| F6 | Medium | **Scoring has no popularity / rating / season / weather dimension**; the best-opened search is over `_intent_score` (tag overlap) + curated flag + distance + cost. "Best possible itinerary" for users is currently = "flows into intent tags & is near center". | `planner.py:1358–1370, 239–248`; scoring/POI-utility literature §7.4 |
| F7 | Medium | **Multi-day legs under-counted**: no first-leg departure travel from origin, no end-of-day return, day 2 reuses origin; cross-day coupling is a naive 2-way split. Under-counting each day by ≤20 min of travel affects true feasibility margins. | `planner.py:1775–1781, 1843–1846` |
| F8 | Medium | **Ordering penalties are ad-hoc & brittle** (`−30/−40/−45/−50/−55`), not data-derived; small changes create surprising priorities (the 55-block is precisely the lunch-bug driver). No unit tests assert the rationale. | `planner.py:1043–1062` |
| F9 | Medium | **Determinism is not end-to-end** when live AI is on. LLM-first and `propose_place_ids` are external calls; tests only pin mock-mode determinism. If "deterministic for tests" must include AI=live, the AI selection layer needs a seeded/fallback path. | `planner.py:1492–1576`; `test_pipeline.py:403–412, 536–683` |
| F10 | Low | `vai_gio` mode always inserts a refreshment stop even without coffee intent and defaults to 2 sights + lunch (4 slots) — arguably more than "vài giờ" (a couple hours). | `planner.py:668–688, 32–33` |
| F11 | Low | Hard-coded `EVENING_PLACE_IDS`/`EVENING_FALLBACK_IDS` will silently fail once the curated catalog is expanded; evening selection should derive from tags + windows as `_is_night_market` already does. | `planner.py:54–61, 571–619` |
| F12 | Note | `MEAL_WINDOWS`/`MEAL_DURATION`/`MAX_IDLE_MINUTES` constants are static; an evening *meal profile* (e.g., "light dinner + late supper") is not supported though two dining stops appear late in many plans. | `planner.py:35–52` |
| F13 | Note | Backfill gap-fill accepts only `current→option→next` single insertions and never allows two small fills in one gap (though gap retries exist). Lower priority given `_tighten_day_gaps` absorbs most leftover idle. | `planner.py:1165–1277` |

---

## 7. What "best possible itinerary" means here, and what the literature prescribes

### 7.1 The problem class is TTDP = *(T)OPTW* (select + order + time-assign)
The tourist trip design problem is standardly modelled as the **Orienteering Problem (OP)** for single-day and **Team OP with Time Windows (TOPTW)** for multi-day, where the objective is *maximize total score of visited POIs within a time limit/time windows* — not pure TSP.
- Gavalas D., Konstantopoulos C., Mastakas K., Pantziou G., **"A survey on algorithmic approaches for solving tourist trip design problems"**, *J. of Heuristics* 20(3):291–328, 2014. https://dl.acm.org/doi/10.1007/s10732-014-9242-5
- Gunawan A., Lau H.C., Vansteenwegen P., **"Orienteering problem: A survey of recent variants, solution approaches and applications"**, *EJOR* 254(2):315–332, 2016. https://www.sciencedirect.com/science/article/pii/S037722171630296X
- Ruiz-Meza J., Montoya-Torres J.R., **"A systematic literature review for the tourist trip design problem: Extensions, solution techniques and future research lines"**, *Operations Research Perspectives* 9:100228, 2022. https://doi.org/10.1016/j.orp.2022.100228 (uses OP as the dominant model).

**Takeaway:** the planner's *selection-then-order* split mirrors classic two-step systems, but the literature's best practice is joint selection+ordering (TOPTW), which for n≤50 can be solved close-to-optimally with greedy-construction + local search (IL-1/VNS/heuristics below).

### 7.2 Greedy vs local search quality (TSP/VRP-with-windows)
- Mishra D., **"Heuristics for the Traveling Salesman Problem"** (KTH survey): tour-construction heuristics ~10–15% above optimal; NN ~25% above the Held–Karp bound; Lin–Kernighan ~2%; 2-opt is a local minimum operator. https://www.isid.ac.in/~dmishra/doc/htsp.pdf
- Tuononen J., Fränti P., **"Simple and fast TSP initialization by Delaunay graph"** (*SN Computer Science*/UEF preprint): NN averages 9.25% (Dots) / 25% (TSPLIB) gap and worst-case 52%/42%; a good candidate graph reduces this to ~2.7–5.8%. https://erepo.uef.fi/server/api/core/bitstreams/09eff966-e6c9-4b1d-8273-8830b9fbbbb8/content
- denishotii/tsp-genai-benchmark (TSPLIB runs): greedy NN 15–24% gap; simulated annealing with 2-opt moves 0–5.5%. https://github.com/denishotii/tsp-genai-benchmark

**Takeaway:** for a 6–9 stop chain, replacing/refining the greedy order with a small local-search pass (2-opt/3-opt, SA, or exact permutation search n! ≪ 362880 at n=9) is cheap and closes most of the gap seen in our experiments (F3: up to −38% travel in the worst spread-out case, 0–11% typical).

### 7.3 Solver options
- **Google OR-Tools routing (VRPTW)**: supports time matrices, per-node time windows, optional nodes via disjunctions (needed for *selection*), and `first_solution_strategy=PATH_CHEAPEST_ARC` + `metaheuristic=GUIDED_LOCAL_SEARCH`. Docs: https://developers.google.com/optimization/routing/vrptw ; https://developers.google.com/optimization/routing/routing_options. Deterministic in single-thread runs: confirmed by OR-Tools lead (Laurent Perron) — https://groups.google.com/g/or-tools-discuss/c/ECR_9doYUBg ("MIP and routing should be [deterministic]"); community reproduces determinism concerns mainly for CP-SAT parallel/seed issues — https://github.com/google/or-tools/issues/2793. Benchmark context: https://github.com/rootztigmod/vrptw-benchmark (OR-Tools used as SOTA baseline on Gehring–Homberger instances).
- **LKH-3** (Helsgaun): state-of-the-art for large TSP/VRP; "best known solutions are often obtained" on benchmarks — http://webhotel4.ruc.dk/~keld/research/LKH-3/ ; report: http://webhotel4.ruc.dk/~keld/research/LKH-3/LKH-3_REPORT.pdf. But it is a heavy native binary, tuned for large instances, and its value at n≤9–50 minuscule versus a 5-line exhaustive/beam search.
- **OR in the literature for tourism/TOP family**: variable-neighborhood search and others achieve optimal/near-optimal on most small TOPTW benchmark instances (see §7.1 surveys; also *Sciencedirect S0360835217305053*, multi-start sim annealing for TOPTW-MV, 2017; *EJOR 220(1):15–27*, LP-based granular VNS for TOPTW, 2012).

**Recommendation on solvers:** at the problem sizes here (candidate pool ≤ 80, scheduled ≤ 9/stop-day), a **deterministic in-house search** (exhaustive over the chosen 6–9 stops, or a 2-opt/3-opt + beam over the top-k candidates) is strictly better value than OR-Tools or LKH-3. OR-Tools becomes interesting only if/when the candidate pool is expanded to the full catalogue and selection must be co-optimized at scale. LKH-3 is overkill and risks heffalump integration (native build, license, determinism setup).

### 7.4 Scoring — popularity/rating/tag-fit/season
- Chen C. et al., **"Automatic Itinerary Planning for Traveling Services"**, *IEEE TSC* 7(3), 2014: POI weight from user review scores; itinerary = weighted set-packing (multi-day TOP); they report **20–80% quality improvement** over vanilla TOP baselines and user-preference weighting shifting results — https://www.comp.nus.edu.sg/~atung/publication/automatic2013.pdf
- **EffiTourRec** (Springer KAIS, 2022): reward = popularity × interest × … with time budgets via adaptive MCTS; better tour precision/recall vs baselines — https://link.springer.com/article/10.1007/s10115-021-01648-3
- Google Maps Places Insights guidance on custom weighted location scores (normalization + user-weights) — https://developers.google.com/maps/architecture/places-aggregate-location-score

**Takeaway:** adding a `rating/popularity/season` score to `_intent_score` (currently tag-overlap only) is the highest-ROI *score* upgrade, aligned with the platform literature, and requires no algorithm change — just a data column (see lane 3).

### 7.5 Time-window feasibility and robustness
The window logic here is already reasonable (strict/relax dual pass, floors for night markets, morning-only enforcement at `planner.py:936–971`). The defect is not the presence of relax but its **unconditional application to meals** (F1). The literature on robust time-window feasibility (e.g., stochastic OP with TW, Verbeeck/Vansteenwegen, EJOR 255, 2016) supports the practical pattern of *soft* windows + explicit penalties — the planner already has this shape; it only needs meals exempted from the relax widening and a hard `lunch ≤ dinner ≤ evening` precedence.

---

## 8. Expected benefit, quantified honestly

Assumptions: a typical Hanoi day = 6–9 stops, candidate pool 30–80, travel ≈49–92 min/day, build budget 0.1–0.5 s (mock).

| Change | Expected benefit | Cost / risk | Recommendation stance |
|---|---|---|---|
| **T0-a: Fix meal relax-widening** (exclude `meal_type` from `latest_end` widening; add hard lunch-before-dinner precedence) | Eliminates the visible "lunch at 20:10" defect in ~57% of tourism plans. Near 100% quality gain where triggered; zero downside. | ~10 LOC; risk≈0; add 2 tests. | **Do first.** |
| **T0-b: Post-pass local search on final slots** (2-opt/3-opt or exhaustive over the 6–9 scheduled stops, window-respecting, travel-min among near-equal preference score) | Removes 0–38% of travel on spread-out plans; typical 5–15 min/day; also shrinks idle waits when windows allow shifting. | ~80–150 LOC; deterministic; must preserve slot count/times (>18:00 floors, ≤120 min gaps) for tests. | **Do second.** |
| **T0-c: score weight calibration + popularity/season column** | Better *which* stops: modern "best possible" = preference-weighted, not tag-overlap-weighted. User-visible relevance ↑. | data work (lane 3 coordination); no behavior break; existing tests check structure not weights. | Do with data lane. |
| **T1: Joint orienteering over candidate pool** (top-k beam / DP-often exact because n≤9 after candidates filter; optional OR-Tools) | Select+order+assign optimally for the chosen objective; also *prevents* infeasible selections (F2) instead of repairing them. Literature (Chen et al.) shows 20–80% relative quality gains for TOP-family against naive greedy *on benchmarks*; transferable upside here is moderate because pool is small & curated-dominant. | Medium: refactor selection into scheduler; re-validate 33 tests + api tests. | Worthwhile after T0; not before. |
| **OR-Tools VRPTW integration** | Same as T1 but robust for larger pools; determinism OK in single-thread; ~30–80 MB dependency, pure-Python wheels, offline. | Higher integration & parity risk; the greedy seed already near-feasible, so observed gains over T0-b are likely ~0–5% at n≤9 (model judgment; single source: this experiment set). | Defer/Tier 2; re-evaluate if pool grows to full catalogue (F4 fixed). |
| **LKH-3 / ORS** | Excellent on big instances only. | Native binary, config/licensing, overkill at n≤50. | **Skip** for MVP. |

Diminishing returns note: after T0-a (correctness) and T0-b (order), the residual quality gap between this tuned heuristic and an exact solver on a 6–9-stop curated day is small — most autonomy is lost not in ordering but in *selection scoring* (no ratings/season) and *travel data* (haversine), which are data problems, not algorithm problems. Upgrading the algorithm without fixing matrix coverage (F4/F5) will keep producing structurally-good-but-meter-inaccurate plans.

---

## 9. Test impact

- Current: `backend/tests/test_pipeline.py` (33 tests) **pass** on unmodified code (verified locally).
- T0-a must keep passing: `test_full_day_plan_includes_scheduled_dining` (`≥11:30` lunch, `≥18:00` dinner — unaffected), `test_full_day_has_midday_rest_and_evening_after_dinner` (rest window; lunch-before-rest assertions use the non-tourism context where lunch is already fine), night-market floor tests (`test_each_night_market_tag_has_hard_evening_floor_in_normal_and_relax`, `test_untagged_osm_night_market_name_still_has_evening_floor`, `test_night_market_is_skipped_when_evening_window_is_too_short`) must remain valid — the fix does not touch `earliest` floors.
- **Add coverage**: a test asserting, for the tourism context (`"du lịch Hà Nội lần đầu, tham quan điểm nổi tiếng"` + a nonce), that every `trua` slot `ket_thuc ≤` every `toi` `bat_dau` and `≤ 14:30`, and that rest precedes lunch-window closure. This is the regression that would have caught F1.
- T0-b reorder: assert slot count, gap ≤120 min, hours respected, evening/night floors unchanged (deterministic per payload). Existing api-level tests (Swipes, regenerate, store) call `build_plan` — they must be re-run (they are not touched by code but validate output contract).
- Any solver change must keep determinism: seed any RNG or restart loops from `_request_seed`.

---

## 10. Recommendation — prioritized plan

**Tier 0 (bugs, ~1 session, low risk)**
1. F1 fix: in `_compute_slot_bounds`, never widen `latest_end` for `meal_type` even under `relax` (`planner.py:979–983`), and enforce precedence `trua → nghi → toi → dem` in `_pack_day_slots` scores (replace the −55 block with an explicit hard ordering that only schedules `nghi` after lunch window start, dinner after rest, etc.). Add tourism-context regression tests.
2. F3 fix: after `_pack_day_slots`/backfill, run a **window-respecting local search** over the final slots (2-opt/3-opt, adjacent swaps, exhaustive for ≤9), optimizing travel while keeping preference score within a small tolerance of the greedy best; deterministic.
3. F6 seed: add rating/popularity/season attributes (coordinate with data lane 3) and fold into `_intent_score`/`choose_candidates` sort; keep existing tie-break shape so tests stay green.

**Tier 1 (quality, ~1–2 weeks)**
4. F4/F5 data: expand the offline OSRM matrix from 50 → all routable (dev whitelist) or at least curated + top-100 candidates per intent profile; keep weekly offline rebuild (README). This also unlocks true routability of the catalogue (F4) and better travel accuracy (F5).
5. F2 structural: convert sight selection into a **beam/enumeration orienteering step** gated over the (now full) candidate pool with the same `_compute_slot_bounds` as feasibility oracle; results remain deterministic and testable.
6. F9: add seeded fallback so that AI-live determinism is preserved for tests (re-run AI proposal only when a `nonce` flag/gate prefers freshness).

**Tier 2 (scale-out, optional)**
7. OR-Tools VRPTW as an alternative back-end behind a feature flag for when pool >200 or multi-day team routing is desired; verify determinism in single-thread; keep the in-house solver as the offline/demo default.

**Tier 3 (future)**
8. Time-dependent travel (rush-hour buckets) if the matrix build is extended; end-of-day return-to-hotel legs + overnight travel on multi-day; evening meal-profile variant (F12).

---

## 11. Executive summary (≈250 words)

The "Minh Đi Đâu Thế" scheduler is a deterministic, constraint-safe heuristic: it selects 4–10 places by a hand-tuned intent score, splits them morning/afternoon/evening, interleaves meals/rest/evening stops, then assigns concrete times with a greedy one-step pass that enforces opening hours, travel times, budget, and dedup, re-validating everything afterwards. Measured on the real code, it always produced feasible plans, stayed deterministic for identical requests, and ran in ~0.1–0.5 s. But it is not "best possible": it optimizes no single objective, and it has one clearly visible, reproducible defect — in ~57% of full-day tourism plans the lunch slot lands at 20:10–20:55, after dinner and the night market, because the relax pass drops meal windows while ordering penalties force the midday "rest" before lunch. The test suite misses this. Beyond the bug, the main structural gap is that place-selection and routing are solved sequentially (it is really an Orienteering-with-time-windows problem), 2-opt refines group order but not the final chain, and travel time is haversine-estimated for most legs because the OSRM matrix covers only 50 of 3529 places. The highest-ROI plan is: fix the meal-window relax bug + add tourism-context regression tests (Tier 0), add a window-respecting post-pass local search on the final slots (Tier 0), then expand matrix coverage and popularity/season scoring (Tier 1). OR-Tools is a reasonable later option only if the candidate pool grows; LKH-3 is overkill at this scale.

## 12. Top 5 most concerning findings

1. **Lunch scheduled after dinner/night market in ~57% of tourism full-day plans** (reproducible; currently uncaught by tests). `planner.py:979–983, 1048–1049`.
2. **Selection is decoupled from scheduling feasibility** — no joint orienteering; infeasible sets are only *repaired*, never *prevented* (`planner.py:1727–1756` vs `994–1105`).
3. **Travel optimization is haversine-based for ~95%+ of route legs** — the OSRM matrix covers 50 of 3529 places (0–2/8–17 legs per plan) (`routing.py:54–67`; measured).
4. **Middle-layer determinism depends on AI-mock**: live AI (LLM-first / proposal) breaks "deterministic for tests" (`planner.py:1492–1576`).
5. **Scoring ignores popularity/rating/season** — "best possible" today means tag-overlap + proximity + curated flag (`planner.py:1358–1370`).

## 13. Confidence and ground-truth tally

**Confidence: 8/10.** Every structural claim (flow, greedy scoring, relax mechanism, matrix coverage 50/3529, 71-whitelist, day-split, validation layering, determinism) was verified by reading `planner.py`/`routing.py`/`data.py` and by executing the real planner (build_plan) in mock mode; the lunch bug and its ~57% frequency are attested by direct execution across 60 sampled requests and a traced code path. Literature citations are genuinely from OR/arXiv-class sources with independent corroboration for the numerical claims (NN gap numbers appear in ≥2 independent sources; OPTW/TOPTW framing in ≥3). The residual uncertainty (−2) is because: (a) no A/B against user satisfaction exists, so "benefit" numbers are analytic/empirical, not validated against users; (b) live-AI end-to-end behavior (F9) and production Postgres matrix behavior were not run (no DB); (c) the OR-Tools vs in-house gain comparison at n≤9 is partly model judgment.

**Ground-truth tally:**
- Verified by reading code / direct execution: 21 claims (all §2–§6 mechanics, bug mechanism+frequency, determinism, matrix stats, trade-of test status).
- Corroborated by external sources (≥2): 5 claims (NN/greedy quality gaps; LKH; OR-Tools determinism + VRPTW capability; OPTW/TOPTW model; popularity-weighted scoring value).
- Model judgment / single-source (flagged in text): OR-Tools-vs-T0-b gap at n≤9; exact user-value of weighting changes; "lunch fix removes 57%" extrapolation to user satisfaction.
- Unverified, needs follow-up: production (PostgreSQL) routable universe and matrix freshness; whether `bang_khoang_cach` covers the full catalogue (`routing.py:14–29` local-path only).