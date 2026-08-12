# Lane 2 — Combinatorial Optimization Foundations: the Route + Scheduling Layers

**Research deep-dive: "What is the best SOTA algorithm architecture for an end-to-end automated tour itinerary generator?"**
**Agent lane:** exact/approximate algorithms for OP, TOPTW, TSP, VRPTW, CP-SAT, MIP, metaheuristics — theory and practical libraries/benchmarks.
**Scale context (fixed input):** 10–40 candidate POIs, ≤16 slots across 1–N days, meals at fixed windows with precedence, driving-time matrix, hard open-hours + soft preferred windows, seconds-latency budget, deterministic/near-deterministic preference.
**Current baseline in repo:** rule-based heuristic: intent tags → ranked candidates → greedy slot packing with penalty scores → NN + 2-opt routing → validation (`backend/app/pipeline/planner.py`; `two_opt` in `backend/app/pipeline/routing.py:87`, nearest-neighbor at `routing.py:71`).

**Source strength legend:** **[PR]** peer-reviewed (OR journal / INFORMS / arXiv); **[DOC]** official library/vendor docs; **[BLOG]** blog / Q&A / vendor marketing; **[WEAK]** unreviewed or self-published.
**Severity tiers:** Blocker / High / Medium / Low / Note. Tiers grade *risk to the recommendation* if ignored, not research quality.

---

## 1. The problem is a known, well-named family: OP → TOPTW → multi-period TOPTW with meals

The itinerary problem at this repo's scale is *not* an exotic problem. It is the (Team) Orienteering Problem with Time Windows (TOPTW), extended with mandatory visits, multi-day (multi-period) structure, and coupled meal/window constraints. The OP family is precisely "choose a subset of locations to visit, each with a score, a service time and a time window, to maximize collected score under a time budget" [PR: https://arxiv.org/html/2512.16865v1]; TOPTW is its time-windowed, multi-path version, and is the acknowledged formal model of the "Personalized Electronic Tourist Guide" (TTDP = tourist trip design problem) [PR: https://www.sciencedirect.com/science/article/pii/S030505480900080X]. Extensions with one-or-more per-path attribute budgets (money, cuisine types) are the Multi-Constraint TOPTW (MCTOPTW) [PR: https://pubsonline.informs.org/doi/10.1287/trsc.1110.0377]; mandatory nodes are TOPTW-MV [PR: https://ideas.repec.org/a/ids/ijores/v46y2023i1p20-42.html]; the multi-day case is the Multi-period OP [PR: https://arxiv.org/html/2512.16865v1]. So the correct *formulation vocabulary* — and the correct benchmark corpus (Solomon/Cordeau-derived instances hosted by KU Leuven and OPLib) — already exists [PR: https://www.mech.kuleuven.be/en/mim/op].

**The decomposition that matters.** The optimization has exactly two coupled decisions: (a) *which* POIs on *which day* (selection + day-assignment), and (b) *in what order and at what clock times* (per-day sequencing + timing). Only (a) is genuinely combinatorial — it is a knapsack layered on a partition. (b) decomposes per day and, once the order is fixed, becomes a trivial O(n) timing problem (§4). This split is exactly what the SOTA literature exploits via "giant tour + DP splitting" [PR via: https://arxiv.org/html/2512.16865v1] and "cluster-first route-second" LNS [PR via: https://arxiv.org/html/2512.16865v1]. Everything below follows from this factorization.

---

## 2. Exact methods: MIP / ILP and CP-SAT at n = 10–40 / ≤16 slots

### 2.1 Plain MIP at this size is easy on paper — but the *encoding* of feasibility is the trap

A two-index TOPTW MIP has O(n²) binary arc variables ≈ 1600 for n=40 and O(n) time variables. Modern MILP solvers handle thousands of binary variables routinely; dimension alone is not the blocker. The blocker is *representing routing feasibility*: subtour elimination for the OP typically uses either Miller–Tucker–Zemlin (MTZ) or flow/consecutive-one constraints [PR: https://www.sciencedirect.com/science/article/abs/pii/S0377221710002973; https://arxiv.org/html/2512.16865v1]. MTZ weakens the LP relaxation badly (order-of-magnitude more branching); the good practice at small n is (i) no subtour constraints initially, (ii) lazy-constraint callbacks that add violated subtour-elimination cuts only when a subtour appears. This is the standard "solve, then separate" pattern, and the largest-scale OP result — Kobeaga et al.'s branch-and-cut solving OP instances *up to 7,397 nodes* — is precisely this kind of lazy-cut scheme [PR via: https://arxiv.org/html/2512.16865v1]. Lagrangian relaxation and branch-and-price are the tools for *proving* optimality on hard 100–480-node TOPTW instances and are open research territory there [PR: https://academic paper via https://arxiv.org/html/2512.16865v1 §3.3]; **at n=40 they are overkill** [HIGH, model judgment + scaling evidence from large-instance exact literature]. The practical exact route at this scale is a single-shot complete solver with a time limit, not a research-grade pricing scheme.

### 2.2 CP-SAT is the empirical default for exactly this shape of problem

Google OR-Tools' CP-SAT is a hybrid CDCL-SAT + CP + LP-MIP hybrid with built-in interval variables, `no_overlap`/`cumulative`, `circuit`/`multiple_circuit` routing primitives, and an internal LNS portfolio [DOC: https://developers.google.com/optimization/cp/cp_solver; PR: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3]. Its owner-contextualized capabilities statement is unusually explicit and directly on-point for us:

- **Scheduling**: "competitive or better than state of the art on academic benchmarks; better than commercial solvers on small to medium scheduling problems; missing heuristics for large instances." [PR/DOC: https://schedulingseminar.com/presentations/SchedulingSeminar_LaurentPerron.pdf]
- **ILP**: "better than all open source solvers, closing in on the best commercial solvers" [PR/DOC: https://schedulingseminar.com/presentations/SchedulingSeminar_LaurentPerron.pdf]
- CP-SAT has "consistently dominated the international MiniZinc Challenge since 2013" [PR: https://www.mdpi.com/2227-7390/14/12/2179].

That is a documented, authoritative match to our envelope: *small-to-medium, constraint-heavy, integral (integerized) scheduling/routing*. Independent evidence in the same direction: an author-reply comparison on job-shop scheduling shows CP-SAT proving optimality easily on small–medium instances while a learned heuristic only beats it at ≥8,000 operations [WEAK—author rebuttal, concretely itemized, https://arxiv.org/html/2402.17606v3]; an independent JSSP makespan benchmark in 2026 still uses CP-SAT as the primary baseline because it "has been extensively used both in research and industrial applications" [PR: https://www.mdpi.com/2227-7390/14/12/2179].

On TOPTW specifically there is direct peer-reviewed evidence that a *plain CP* model (interval variables + global constraints) is strongly competitive with the best metaheuristics on the standard benchmark corpus:

- Gedik et al. 2017, CP for TOPTW (304 Solomon/Cordeau-derived instances, up to 200 nodes): **122/304 best-known solutions matched, 49 of 66 known optima proven, plus two new optimality proofs** [PR: https://www.sciencedirect.com/science/article/pii/S0360835217301134].
- Kirac, Gedik & Oztanriseven 2023, CP for TOPTW with mandatory visits (168 instances): **99 best-known matched, 64 new best-known, average optimality gap 1.64%**, with an average solve time of ~203 s accounted for largely by the hard large instances [PR: https://ideas.repec.org/a/ids/ijores/v46y2023i1p20-42.html; https://www.academia.edu/118232701/].

Consider what that implies for *our* size: those are 100–200-node instances with up to 480 nodes in the Cordeau tier; we run 10–40 candidates and ≤16 slots per plan. If plain CP closes a big fraction of those instances to optimality, then **CP-SAT at 40 POIs/16 slots should be expected to reach optimality or a ~1%-gap solution in well under a few seconds** for most problem draws, and essentially instantly for typical draws. This expectation is an interpolation from published large-instance results, not an unreferenced claim — but it must be validated on this project's own instance distribution (§5.2). **[HIGH confidence on the interpolation direction; the exact seconds figure is an in-repo measurement obligation, not a literature constant.]**

### 2.3 The "exact-or-die" warning

Exactly-solved does not mean *provably optimal*; CP-SAT is exact in the sense of complete search (it will close the instance or prove optimality if given enough time), but under a hard time limit it returns a feasible solution with an optimality-gap certificate [DOC: https://developers.google.com/optimization/cp/cp_solver; PR: https://d-krupke.github.io/cpsat-primer/benchmarking.html]. The design consequence for a latency-bound API: **run CP-SAT with `max_time_in_seconds` as a hard budget, treat the gap as a tunable, and fall back on the existing greedy path if the solver returns UNKNOWN/infeasible.** [HIGH]

---

## 3. Heuristics/metaheuristics: what is the "right default" at n = 10–40

### 3.1 The evidence hierarchy at this size

The published head-to-head numbers on TOPTW benchmarks give a clean quality ladder:

| Method | Reported gap to best-known / optimal | Time | Source |
|---|---|---|---|
| ILS (insert + shake) | 1.8% avg gap to BKS | "decreased by a factor of several hundreds" vs prior | [PR: https://www.sciencedirect.com/science/article/pii/S030505480900080X] |
| ILS on large sets | 2.7% avg gap to optimal | low effort | [PR: https://link.springer.com/chapter/10.1007/978-3-642-00939-6_2] |
| GRASP+ILS hybrid (HIGLS) | 5.19% avg gap; 32% of instances matched/beat | **1.5 s** | [PR: https://pubsonline.informs.org/doi/10.1287/trsc.1110.0377] |
| CP (interval variables) | 122/304 BKS + 49/66 opts proven | seconds–minutes | [PR: https://www.sciencedirect.com/science/article/pii/S0360835217301134] |
| Giant-tour GRASP+ELS, DP split | **0.30% optimality gap**, 57 BKS | comparable to SOTA heuristics | [PR via: https://arxiv.org/html/2512.16865v1] |
| Well-tuned SAILS / ILS | 50 (SA) / 37 (ILS) new BKS on 304-instance corpus | — | [PR: https://link.springer.com/article/10.1057/s41274-017-0244-1] |

Consistent picture: **the gap between a decent metaheuristic and the best-known solution is 1–5%; the gap between a *constructive-only greedy* and optimal is much larger and instance-dependent**, with clustered/time-window-tight instances (exactly our POI+meal structure) being where constructive greedy degrades most. [MEDIUM]

### 3.2 Where the current pipeline sits

`planner.py` is a constructive heuristic (ranking → greedy packing with penalty scores → NN+2-opt). The nearest-neighbor construct then a 2-opt polish is the textbook *weakest* respectable combination: 2-opt alone is documented at 5–10% above optimum on Euclidean TSP instantiations while LK/LKH is within fractions of a percent [BLOG: https://metricgate.com/docs/lin-kernighan-tsp-heuristic/ (weak source; figure consistent with the TSP-literature consensus); PR: reinforced-LKH paper at https://www.sciencedirect.com/science/article/pii/S0950705122012400; http://webhotel4.ruc.dk/~keld/research/LKH]. Two refinements, in increasing order of value:

1. **Make the constructive heuristic *grasp-ified* and *solver-verified*.** Run the greedy several times with randomized tie-breaking / insertion-ratio scoring (CT vs DPV-style node-selection metrics, exactly as in Granda & Vitoriano's results where randomized 100-solution pools cost little extra) [PR: https://link.springer.com/article/10.1007/s44196-025-00797-5], keep the best, and use it only as a *warm start* for the solver below. GRASP+ILS with a tabu perturbation phase is the documented 1.5-second recipe for this problem family [PR: https://pubsonline.informs.org/doi/10.1287/trsc.1110.0377].

2. **Add an exact/LNS layer above it.** At 40×16 the simplest robust "default" is: *CP-SAT as the final authority*, with the greedy as initial hint and a time limit. That is strictly more powerful than any bespoke metaheuristic at this size because CP-SAT *embeds* LNS on the routing/circuit structure, and its internal LNS ("8 incomplete subsolvers… rins/rens, rnd_var_lns,…") re-optimizes neighborhoods of the incumbent using propagation + exact sub-solves [PR: https://d-krupke.github.io/cpsat-primer/lns.html].

**Native-LNS-in-CP-SAT vs a hand-rolled ALNS:** the primer's recommendation is explicit and matches the evidence: "If you already know how to use CP-SAT, you can stick with it to solve big problems… This technique, called Large Neighborhood Search, often outperforms all other approaches" [PR: https://d-krupke.github.io/cpsat-primer/lns.html]. At n=40 you are in CP-SAT's native sweet spot (small-to-medium) where an *external* ALNS buys little. [MEDIUM-HIGH]

### 3.3 When would a bespoke LNS/ALNS beat CP-SAT at this scale?

Only in two cases: (i) if the objective/constraints are non-scalarizable or probabilistic (they are not here), or (ii) if per-request latency must be *sub-second* and the solver's LNS overhead is felt. In that second case the correct move is not an ALNS — it is **PyVRP** (below), a C++ hybrid-genetic ILS that is SOTA for VRPTW and supports optional-prize clients (TOPTW shape), designed to run hundreds of nodes in seconds and seedable for reproducibility [PR: https://arxiv.org/abs/2403.13795; DOC: https://github.com/PyVRP/PyVRP]. A hybrid-niche position: **fast deterministic route optimizer = PyVRP; exact-enclosing, constraint-rich, meal/weather/preference objective = CP-SAT.** For the purposes of this lane, pick CP-SAT first, PyVRP as the "speed floor" alternative. [MEDIUM]

### 3.4 LKH / 3-opt / evolutionary algorithms — the honest sizing

For the *per-day* TSP sub-problem (once selection/day-assignment are fixed), routes are tiny (≈2–6 stops after meals). At n≤10 an exact TSP solve is trivially cheap: Held–Karp DP is O(n²2ⁿ) ≈ 10⁵ ops at n=10; even brute-force permutation check is 10! = 3.6M, still milliseconds in Python. LKH — the near-optimal champion that solves most TSPLIB optima including a 109,399-city instance [PR/DOC: http://webhotel4.ruc.dk/~keld/research/LKH] — and EAX/GAs and 3-opt are all *relevant to the wrong regime* (n ≫ 100). **Lin-Kernighan at n≈6 is a category error; keep 2-opt or switch to exact DP for the per-day route.** [HIGH]

---

## 4. The schedule subproblem: given the chosen set + order, optimal timing is O(n)

### 4.1 The canonical result you already half-implement

For a *fixed* route and *hard* time windows, the schedule that (a) is feasible and (b) minimizes total waiting/idling is computed by a single forward pass: at each stop, `start_i = max(earliest_arrival_i, window_open_i)`; recursively. If you want to *position* visits near a preferred window rather than as early as feasible, you do a forward pass for the lower bound, a backward pass for slack, and shift stops within their (forward-backward) feasible envelopes. This is standard textbook practice in the VRPTW literature (window-feasibility via cumulative propagation; e.g., Savelsbergh-style insertion checks and "feasibility intervals" propagating `[l_i, u_i]` along a route) [PR: https://www2.isye.gatech.edu/people/faculty/Martin_Savelsbergh/publications/insertion-final.pdf; PR: http://alvarestech.com/temp/vrptw/Vehicle%20Routing%20Problem%20with%20Time%20Windows.pdf (column-generation text, §3, feasibility-interval recursion); DOC: https://developers.google.com/optimization/routing/vrptw]. The repository's `_pick_visit_window`, `_tighten_day_gaps(` `planner.py:1175`) and `_backfill_day_gaps` are ad-hoc instances of this; an interval-propagation formulation makes it *correct and closed-form* rather than heuristic.

**Reframing for the scheduler:** once the planner has chosen POIs and an order, the timing step is *not an optimization problem at our scale* — it is an O(n) propagation, guaranteed to achieve "no idle, windows respected, preferred-window-aligned as much as envelope allows" simultaneously. Any residual "can't place it nicely" is a *selection-ordering* problem, not a *timing* problem. This is the single most important scheduling-lane insight: **stop penalizing timing; fix timing exactly and move the optimization budget upstream.** [HIGH]

### 4.2 Hard vs soft windows: the modeling fault line

- **Hard windows** are required only for *actual* open hours (and Google-affirmed closure), and for meal anchors. Violating them must make a candidate infeasible.
- **Preferred windows** (e.g., "this garden at lunch, outdoor POIs in the afternoon") and time-of-day *preference scores* must be **soft objectives**, not constraints. Modeling them hard manufactures infeasibility and brittleness for zero benefit. The correct soft-handling pattern exists in the literature: soft-time-window routing with a **lexicographic objective (routes → violations → distance)** [PR: https://pubsonline.informs.org/doi/10.1287/trsc.2014.0558], and time-window relaxation with service-start placement heuristics used inside search. Concretely: hard windows on open-hours/meals; a *small-penalty* soft deviation term on preferred windows (per §7, tiered); the feasibility intervals of §4.1 then decide whether a soft preference is achievable at all.

### 4.3 Meals, precedence, and weather as scheduling constraints

Meals with fixed windows and (soft) precedence (lunch before dinner, morning sight before lunch) are *interval variables + `AddNoOverlap`/`start_before_start`* in CP-SAT — native, cheap, and exactly the disjunctive-scheduling structure where CP beats MIP [DOC: https://developers.google.com/optimization/cp/cp_solver; PR: https://www.sciencedirect.com/science/article/abs/pii/S0305054820301532 (CP + LNS on disjunctive machine scheduling cites Laborie 2018: CP outperforms MILP on scheduling)].

Weather: if a POI is weather-exposed and rain is forecast in a window, the *clean* formulation is a conditional hard block ("this POI only in dry windows") or a rain-penalty added to the window-preference term — both are linearizable in CP-SAT and do not change the structure of the model. Treating weather as a hard *day-level* filter upstream (as schedulers generally do on outdoor places) is a reasonable simplification; coupling it to per-slot position is a nicer objective and equally cheap. [MEDIUM]

### 4.4 "Itinerary as job-shop" literature — verdict

The agency to frame itinerary construction as a machine-scheduling problem (POIs = jobs, time = machines/calendar, meals = setup/precedence) exists and consistently lands on CP as the winning family for exactly these disjunctive, windowed, precedence-laden problems [PR: https://www.sciencedirect.com/science/article/abs/pii/S0305054820301532; PR: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3; PR: https://www.mdpi.com/2227-7390/14/12/2179]. It confirms — rather than adds to — the §2.2 conclusion.

---

## 5. Is global optimization even necessary at n ≤ 40? Measurement, not ideology

### 5.1 What the literature actually shows about greedy-vs-optimal gaps

There is **no clean peer-reviewed head-to-head of "pure nearest-neighbour greedy vs optimal" on 40-node TOPTW** in what I could find — the honest state of the record is triangulated:

1. **Exact methods close small-to-mid TOPTW instances**: 49/66 known optima proven by plain CP on the 100–200-node corpus [PR: https://www.sciencedirect.com/science/article/pii/S0360835217301134]; on established small TOPTW-MV benchmarks, multi-start SA "obtained better solutions than Gurobi for 13 instances and the same solutions… for the remaining" 72 small instances [PR via: https://www.academia.edu/80904569/]. This says the *optimum is achievable* at this size — hence greedy leaves real money on the table somewhere.
2. **SOTA metaheuristics sit 0.3–5% above best-known** (table in §3.1), and constructive rules — even well-tuned ones with better node-selection metrics — are the *weakest* tier in every comparison surveyed [PR: https://link.springer.com/article/10.1007/s44196-025-00797-5; https://link.springer.com/chapter/10.1007/978-3-642-00939-6_2]. Top-plateau constructives show "small or non-existent" gaps *only on small casual landscapes*; the gap opens as landscape size and window tightness grow [PR: https://link.springer.com/article/10.1007/s44196-025-00797-5].
3. **The reverse direction matters for our latency value proposition**: on real-sized case studies, exact MIP itself stalls (25–47% MIP gap after 20 min–24 h) — the lesson there is that *exact* search plus *good heuristic warm-starts* complement each other [PR: https://link.springer.com/article/10.1007/s44196-025-00797-5].

### 5.2 The honest verdict for this repo

**At n=40 / ≥16 slots with hard windows + soft preferences + day assignment + meal precedence, greedy+penalty is provably suboptimal on *selection*, and the fix is cheap.** The expected win is *not* primarily "higher score": it is *fewer violated/infeasible constructions, less idle, better meal anchoring, and deterministic behavior* — the failure modes that rule-based packing produces (see Lane 5). The expected *score* delta is plausibly a few percent given the metaheuristic-tier gaps above, but that number should be treated as **unconfirmed for this instance distribution** until the repo measures it. Rule-based planning is the right thing to keep as a *reference/warm-start/fallback*, not as the *final* layer. Recommended A/B: run the current greedy path and a CP-SAT(TW)-with-time-limit on the existing test corpus/trip matrix; report score delta, violation delta, idle delta, wall time. **[HIGH recommendation; the gap magnitude is an open empirical question (my confidence in the *benefit*, not the magnitude, is high).]**

One regime where greedy is definitively fine: **the per-day TSP after selection** (n≤6). Exact/DP beats any heuristic there at lower latency and zero nondeterminism. [HIGH]

---

## 6. Practical library landscape, 2024–2026

| Library | Engine | Suits | Latency/deps at our scale | Determinism | Verdict |
|---|---|---|---|---|---|
| **OR-Tools CP-SAT** | CDCL+CP+LP hybrid [PR: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2023.3] | windowed scheduling/routing, logical constraints, meals, circuit | Solve at n=40: expected sub-second to low-seconds (see §2.2–2.3). Import/warm cost per process ≈ well under a second on modern wheels but non-zero — prewarm at startup (Low-confidence, could not be measured in this environment: `ortools` is not installed here) | **Configurable**: `num_search_workers=1` is not reliably deterministic as of v9.5–9.8 (two closed issues); deterministic multi-worker search via `interleave_search:true, share_binary_clauses:false, num_workers:N` but "usually way slower" [PR/BLOG: https://github.com/google/or-tools/issues/3590; https://github.com/google/or-tools/issues/3943; https://groups.google.com/g/or-tools-discuss/c/lPb1FzhTMt0] | **Primary pick.** Interval vars, `circuit`, native LNS, gap certificates, Apache-2.0. |
| **PyVRP** | C++ HGS + ILS, VRPTW + optional-prize clients [PR: https://arxiv.org/abs/2403.13795; DOC: https://github.com/PyVRP/PyVRP] | fastest route optimizer with time windows, prize collecting (TOP-shape) | ms–seconds at hundreds of nodes; enables <1 s at our size | Seedable (near/deterministic given seed) [DOC: https://github.com/PyVRP/PyVRP] | Strong "speed floor" second layer / fallback. MIT. |
| **python-mip / HiGHS** | CBC/HiGHS MILP [BLOG: https://stackoverflow.com/questions/73552667/] | pure ILP; no CP scheduling constructs | Model-creation overhead at n=40 is negligible (python-mip's own n-Queens benchmark shows overhead in tens of ms at thousands of vars) [DOC: https://python-mip.readthedocs.io/en/latest/bench.html] | Yes (fixed options) | Usable, but you'd re-derive circuit/scheduling encodings CP-SAT gives free. |
| **PuLP** | CBC backend | simple LP/MILP scratch | heavier modeling-layer overhead; no CP | Yes | Only if you already depend on it; weaker engine. |
| **OR-Tools Routing library** | legacy CP local search for VRPTW [DOC: https://developers.google.com/optimization/routing/vrptw] | classic VRPTW/CVRP, time windows built-in | Fast; API verbose; heuristic-only | No (local-search guided search, seeded) | Keep as mental benchmark, not top pick here. |
| **Timefold / optaPy** | Java/Kotlin CP + local search | heavy constraint models with visual workbench | JVM dependency in a light async FastAPI service is disproportionate | Seeded | Avoid unless an organization-wide constraint modeling platform is wanted (Lane 4 territory). |
| **networkx** | approx TSP heuristics only | toy experiments, TSP n≤20 | trivial | Yes | Not a solver; do not rely on it for quality results. |

**Latency engineering notes:** (1) CP-SAT results in a long-running FastAPI worker are fine *if* you (a) `import ortools` at process start, (b) cap `max_time_in_seconds`, (c) consider 1 worker per solver call to keep the event loop unblocked, or a dedicated solver process/executor pool. (2) A budget of ~2–5 s per request is entirely consistent with published speed behavior at this size — the §2.2 CP results that take 200 s average are on 100–200-node corpora and their hard tails; our horns are much smaller. (3) If determinism must be *bit-for-bit* for tests, pin CP-SAT parameters per the deterministic-search recipe above, or use PyVRP/numpy-DP for the route-only layer and keep CP-SAT for the selection layer where a fresh-seeded near-deterministic solve is acceptable. **[MEDIUM–HIGH; determinism-BEFORE-fix is the Blocker-grade point here.]**

---

## 7. Multi-objective: folding intent score / preferences into a solver

### 7.1 What the theory says, precisely

Single-scalarization options, in descending order of robustness at this scale:

1. **Weighted sum** (`max Σ w_i·f_i`) is the simplest and most common, *but* the approximation theory is genuinely negative for our setting: weighted-sum-supported solutions provably **do not form an ε-approximation set for multiobjective *maximization* problems in general** — the guarantee holds only for minimization [PR: https://link.springer.com/article/10.1007/s00186-023-00823-2, citing Bazgan et al. 2022]. Itinerary score maximization is a maximization family. Practically this means weighted sum can silently discard Pareto-optimal trade-offs (e.g., "fewer POIs but perfectly timed"), which is acceptable only if the weight vector *encodes an explicit, stable user preference* — which an intent-tag score effectively is. **[MEDIUM; the theoretical limitation is real, the practical relevance depends on product intent.]**
2. **Lexicographic / hierarchical tiers** — the OR-practice backbone: feasibility (hard windows, meals) > day-length feasibility > preferenced POI selection > preferred-time alignment > idle/distance. This is literally how SOTA soft-TW VRP is posed (routes → violations → distance) [PR: https://pubsonline.informs.org/doi/10.1287/trsc.2014.0558], and how "nice itinerary" multi-day value is often defined (maximize the worst day) [PR: https://www.math.uwaterloo.ca/~cswamy/papers/trips-wsdmfnl.pdf]. **Recommended.** Implementation: either successive solves (solve tier k, convert to constraint, solve tier k+1) or a single CP-SAT model weighting tiers by huge priority coefficients (fixing tier ordering), with per-tier metrics normalized to comparable scales. [HIGH]
3. **ε-constraint / constraint-style** (optimize one tier, bound the others by tolerances) — the rigorous way to find a Pareto point on one axis; costs repeated solves. Fine as a legacy fallback, unnecessary for a single-shot planner. [LOW]

### 7.2 The two practical pitfalls regardless of choice

- **Normalization is the difference between a sane objective and a garbage one.** Scores, minutes-of-idle, and deviation-from-preferred-window have incomparable units and ranges. Every OR practice source and every competitive implementation normalizes each term (e.g., to [0,1] by reachable range) before weighting; the soft-time-window VLSN work explicitly uses lexicographic stages to avoid unit mixing [PR: https://pubsonline.informs.org/doi/10.1287/trsc.2014.0558]. The current planner's penalty-score regime is vulnerable exactly here (hand-tuned penalties in raw minutes). **Recommendation: three normalized tiers, weighted sum inside a tier only.** [HIGH]
- **Soft preferences must not masquerade as hard constraints**, else the solver spends its entire latency budget proving infeasibility (a documented real-world CP-SAT failure mode on TOPTW — the OR-SE question where a TOPTW model turned infeasible under naive `y[i,p]`-enforced start-time windows; Perron's answer: use `circuit`) [BLOG: https://or.stackexchange.com/questions/10711/; DOC/example: https://github.com/google/or-tools/blob/stable/examples/python/prize_collecting_vrp_sat.py]. The pattern to copy is the prize-collecting-VRP CP-SAT example (optional nodes, prize objective) which is *literally* the OP/TOPTW shape the framework authors reach for. [HIGH]

---

## 8. Synthesis: the recommended architecture (research-level, no code changes)

1. **Keep and harden the greedy path** — as warm-start, fallback, and A/B baseline (it already exists; §3.2).
2. **Add a CP-SAT orchestrator layer** as the final authority: model = optional-POI prize objective with `circuit` per day, hard windows on hours/meals, soft-token preferred-window deviation, meals as interval+precedence, weather as conditional blocks, three lexicographic tiers (feasibility → day-length → preference+alignment+idle normalized in-tier), `max_time_in_seconds` budget, deterministic-search parameters if tests need bit-for-bit runs, greedy solution as hint.
3. **Day-assignment/selection is the combinatorial core**; timing is an O(n) forward/backward propagation fixed by the solver, not by the heuristic on the floor (§4.1).
4. **Per-day routing after selection: exact DP (n≤10)**, not 2-opt/LK (§3.4).
5. **Scale headroom lane (if POIs ever exceed ~60, or latency must go <1 s): swap or augment with PyVRP** (§6).
6. **Validate with an in-repo benchmark**: current-greedy vs CP-SAT vs PyVRP on the existing trip corpora; report score delta, infeasibility count, idle, and p95 latency, before committing to any single layer (§5.2). This is the experimental crux the literature cannot answer for this distribution.

**Severity roll-up:** [HIGH] adopt a solver layer rather than tuning penalties (correctness/robustness rationale); [HIGH] fixed-sequence timing is O(n)-exact, stop optimizing it heuristically; [HIGH] normalize per-tier objectives, don't mix raw units; [HIGH][Blocker-if-untested] determinism must be configured explicitly or tests/reruns will flake; [MEDIUM] CP-SAT time-budget + gap + fallback is the operational contract; [MEDIUM] soft vs hard window modeling; [LOW] LKH/evolutionary/Tabu — unnecessary at this size; [NOTE] LNS-in-CP-SAT obviates a bespoke ALNS at n=40.

---

## 9. Executive summary (~250 words)

The itinerary problem is the (Team) Orienteering Problem with Time Windows, extended with mandatory nodes, multi-day structure and meal precedence — a well-trodden problem family with standard benchmarks, not a bespoke research problem. It factorizes into (a) *selection + day-assignment* (the genuinely combinatorial, knapsack-on-partition core) and (b) *per-day order + clock times*. Part (b) is trivial once (a) is fixed: for a fixed route and hard windows, the minimum-idle, window-respecting schedule is an O(n) forward/backward propagation — so the current greedy timing/penalty machinery optimizes the wrong, too-hard sub-problem. For selection, the literature is unambiguous that constructive greedy is the weakest tier (SOTA metaheuristics are 0.3–5% above best-known; plain CP proves ~74% of known optima on 100–200-node TOPTW corpora), so global optimization at n=40/16 slots is both warranted and cheap: CP-SAT is documented as best-in-class exactly on small-to-medium constraint-heavy scheduling, embeds LNS, and at our size should reach optimality or ~1% in seconds. Recommended architecture: keep greedy as warm-start/fallback/A-B baseline; add a CP-SAT orchestrator with hard windows on hours/meals, soft normalized preference tiers (lexicographic: feasibility → day length → preference+alignment+idle), `circuit` per day, a hard time budget and gap-as-output; exact DP for tiny per-day routes; PyVRP as the ultra-fast alternative. Two load-bearing operations gotchas: normalize units before weighting (the current penalty regime is vulnerable), and configure CP-SAT determinism explicitly or tests will flake. The expected win is robustness (fewer infeasible/idle plans) more than score; the gap magnitude must be measured in-repo.

## Top 5 strongest findings

1. **The problem is TOPTW, and exact CP provably closes this size range.** Plain CP matched 122/304 best-knowns and proved 49/66 known optima on 100–200-node TOPTW; at n=40/16 slots CP-SAT should be expected to reach optimality or ~1% in seconds (interpolated; needs in-repo A/B) [PR: https://www.sciencedirect.com/science/article/pii/S0360835217301134].
2. **Given the order, optimal timing is O(n), not a penalty game.** Forward/backward interval propagation yields minimum-idle schedules and places visits optimally within preferred-window envelopes — the current greedy+penalty timing should be replaced by closed-form propagation [PR: https://www2.isye.gatech.edu/people/faculty/Martin_Savelsbergh/publications/insertion-final.pdf].
3. **Constructive greedy is the weakest tier by a wide, documented margin; metaheuristics sit at 0.3–5% above best-known — so a solver layer materially reduces waste/infeasibility** [PR: https://pubsonline.informs.org/doi/10.1287/trsc.1110.0377; PR via: https://arxiv.org/html/2512.16865v1].
4. **CP-SAT is the right default engine here**: small-to-medium scheduling is its documented sweet spot ("better than commercial solvers on small to medium scheduling"), with built-in LNS and `circuit`, and determines its own gap under time limits [PR/DOC: https://schedulingseminar.com/presentations/SchedulingSeminar_LaurentPerron.pdf; https://d-krupke.github.io/cpsat-primer/lns.html].
5. **Multi-objective folding should be lexicographic tiers with per-tier normalization**, not a single raw-unit weighted penalty (weighted-sum scalars provably do not approximate maximization problems; SOTA soft-TW VRP practice is lexicographic) [PR: https://pubsonline.informs.org/doi/10.1287/trsc.2014.0558; https://link.springer.com/article/10.1007/s00186-023-00823-2].

## Confidence and ground-truth tally

**Confidence: 7/10.** Strength: the mapping of the problem to TOPTW, the CP-vs-greedy quality ordering, the O(n) timing-schedule result, the CP-SAT capability positioning, and the lexicographic-objective practice are all directly supported by peer-reviewed or first-party sources, several with numbers. Weaknesses that cost a full 10: (i) I found **no published head-to-head "pure NN greedy vs optimal" benchmark at n≈40 for this exact structure** — the key magnitude claim ("a few percent + fewer violations") is therefore triangulated, not measured, and must be A/B'd in-repo; (ii) CP-SAT per-request latency at our exact size is extrapolated from published 100–200-node corpora and community benchmarks, not measured here (`ortools` is not installed in this environment); (iii) the import/warm-up cost of `ortools` on Windows is unmeasured (Low-confidence claim); (iv) determinism findings come from closed GitHub issues + maintainer guidance (strong but not peer-reviewed), and (v) the equal-best example of the "optimize timing exactly, penalties for preferences" pattern as applied to *tourist* itineraries specifically is inferred from routing literature, on model judgment.

**Ground-truth tally: 5 of 10 load-bearing conclusions externally verified** (TOPTW-mapping + CP and ILS benchmark numbers; fixed-sequence O(n) timing being exact-and-standard; CP-SAT being competitive on small/medium scheduling and dominating MiniZinc; lexicographic soft-window VRPTW practice; weighted-sum non-approximability for maximization). The remaining 5 rest on model judgment and interpolation: CP-SAT reaching ~1% in seconds at n=40; greedy-vs-solver score gap being a few percent at *this* instance distribution; a solver layer reducing infeasible-plan count materially; determinism configuration being operationally sufficient; and library import/latency profiles in an async FastAPI worker.