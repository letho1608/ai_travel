# 06 — Honest Baseline: Does Replacing the Current Pipeline Actually Win?

**Lane:** honest cost/benefit — the skeptic's advocate (this lane decides whether any proposed upgrade beats *doing nothing / cheap fixes*).
**System under evaluation:** FastAPI + `backend/app/pipeline/planner.py` (1993 lines), `routing.py`, `services/ai.py`. Rule-based "mapping" pipeline: intent→tag mapping, score-ranked candidate selection, greedy slot packing with penalty scores, NN+2-opt routing, time-window scheduler, meal precedence, budget guard, full validation gate, LLM only for place-name selection + copywriting.
**Date:** 2026-08-12. Research-only; no code was changed.
**Method:** read of current code; direct execution data inherited from work-item 02 (same repo, same planner, `AI_MODE=mock`); external literature search with citations; every unverified number labeled **estimate**.

---

## 1. TL;DR — the verdict table

The question is not "which algorithm is most sophisticated." It is: *for a solo developer with a shipping, tested product, does a rewrite measurably improve user-perceived quality once you pay for latency, spend, risk, and maintenance?* Honest answer, per candidate:

| Candidate upgrade | Expected quality delta (evidence) | Engineering cost | Operational cost | Risk (regression/nondeterminism/new failure modes) | Verdict vs current baseline |
|---|---|---|---|---|---|
| **(a) Exact global optimizer (CP-SAT/OR-Tools) over the full pool** | Small-to-moderate. At n≈9/day the greedy is already near-optimal; measured headroom is 0–38% travel *in worst spread-out cases*, typical 5–15 min/day. Actual optimal-vs-greedy gap on such small instances is typically <4% score. | 1–2 weeks + dependency (or-tools ~30–80 MB wheel), model rework for meals/evening floors = soft constraints + infeasibility handling | ~0 (deterministic, fast) | Medium. New failure mode: model infeasibility; solver-version nondeterminism drift; 33 tests + api contract revalidation. | **LOSE vs targeted fixes (T0).** Most of the benefit is captured by a window-respecting local-search post-pass at ~1/10 the effort. *Conditional win only if the candidate pool grows to the full catalogue (join selection at scale).* |
| **(b) LLM-as-planner (replace the scheduler with an agent)** | Feasibility collapses. Benchmarks: GPT-4 0.6% final-pass on TravelPlanner; best published 4.4%; even Google/ItiNera do *not* ship pure-LLM itineraries; LLM self-correction is empirically ineffective. The pipeline you replace today yields 100% feasible plans under measurement. | weeks (agent loop, eval harness, guardrails, retries) | LLM spend $0.01–$0.10/plan (cheap model single-call) to $1+/plan (frontier agent loop); latency 47–124 s vs current 0.5 s → breaks the current SSE UX unless fully streamed/refactored | **High.** Nondeterminism (evals + regression cases needed), hallucinated POIs, constraint-drop. | **LOSE hard as a replacement.** **WIN only as an augmentation** (narrative/intent) — which the codebase already does, architecturally. |
| **(c) LLM + solver hybrid** | Best measured option in the literature: ItiNera ~30% relative on rule-based quality metrics over baselines; Google ships exactly this pattern (LLM suggests, joint optimizer guarantees feasibility), and Personal Travel Solver (ACL 2025). | days–1 week on top of current structure (structured intent extraction + narrative pass) | modest: 1–2 extra LLM calls/plan, cents | Low-medium. Nondeterministic narrative; need guardrail logging. | **WIN**, but only as the *moderate upgrade* — and the current code is already a weak sketch of this (LLM-first selection + copy wrap). The gap is *intensity*, not architecture. |
| **(d) Learned / ML planner (NCO: POMO, GFACS, DeCoST class)** | Correct-architecture quality is real (DeCoST 1–3% gap at n=50–100) but irrelevant here: at n≤10 scheduled / pool ≤80, exact or exhaustive search strictly dominates; models add training data, GPU, eval, and OOD risk for a problem a 10-line enumeration already solves. | weeks+ (dataset, training, serving infra) | infra (GPU/inference host) + training runs | High. Distribution shift when POI catalogue or constraints change; opacity for a feedback loop users see errors in. | **LOSE decisively at this scale.** Revisit only if you someday schedule hundreds of POIs per query. |

**The 30-second answer:** keep the deterministic core; fix the known meal-ordering defect; add a window-respecting local-search post-pass; feed the LLM in deeper at the *edges* (structured intent extraction → better scoring; stronger narrative layer with guardrails). That captures most of what "intelligent" reads as, at single-digit percent of the rewrite's cost and risk. The current pipeline is not the problem; the scoring data and the one visible bug are.

---

## 2. The baseline, quantified before you spend anything

Replacement must beat a *moving* baseline, because two cheap fixes already in hand at near-zero cost change the comparison. Measured on this exact codebase (work-item 02, direct execution, `AI_MODE=mock`, 60 sampled tourism requests):

- Build latency 116–477 ms, deterministic for identical (context, nonce) input, 33 pipeline tests pass. [source: `research/work-items/02-itinerary-algorithm.md` — first-party measurement]
- Every sampled plan satisfied hard constraints (opening hours, travel time, budget, dedup, night-market ≥18:00 floor). Feasibility is enforced in two independent layers (`_compute_slot_bounds` + `validate_plan`). [source: same + `planner.py:914–991, 1464–1529`]
- One reproducible, user-visible Blocker: in **34/60 (57%)** of full-day tourism contexts, lunch ("trua") is scheduled 20:10–20:55, *after* dinner and the night market, because the `relax` pass widens the meal window while ordering penalties force the midday rest first. [source: work-item 02 §4.4; mechanism at `planner.py:979–983, 1048–1049`]
- Structural weaknesses: selection ignores schedule feasibility (no joint orienteering); 2-opt does not optimize the final chain (travel weight 0.15 vs preference range ±50); travel time is haversine for ~95%+ of legs (OSRM matrix covers 50 of 3,529 places; local routable universe = 71 places); score has no popularity/rating/season dimension. [source: work-item 02 §6 F2–F6]

Interpretation for this lane: the "mapping, not intelligent" feeling the user reports is **not caused by a missing global optimizer or a missing agent.** It is caused by (i) a visible correctness bug, (ii) data that scoring ignores (ratings/season), and (iii) a selection/scoring pipeline that never listens to timing feasibility. All three are fixable *in place*. The measured 116–477 ms latency also means there is enormous free compute headroom to run stronger search on the existing core (work-item 02 estimated a ≤10 ms exact search over the ≤9 scheduled stops). "Do nothing" is not the right baseline; "T0-fixes" is.

---

## 3. Candidate (a): exact global optimizer (CP-SAT) over the full candidate pool

### 3.1 What the OR literature says about the achievable quality gap

At n≤10 (this app schedules ≤9 stops/day, ≤16 for multi-day) a *good* deterministic greedy injector plus light local search is already close to optimal, and exact/CP methods only pull ahead meaningfully at larger sizes or when the greedy is weak:

- A constraint-programming (CP) model for TOPTW reaches best-known solutions on 122/304 benchmark instances (and 49/66 known-optimals), but these are hours-of-compute academic runs on 100–480-customer instances, not real-time planning. [source (strong): https://www.sciencedirect.com/science/article/pii/S0360835217301134 ; corroborated by the abstract at https://dl.acm.org/doi/10.1016/j.cie.2017.03.017]
- On the smaller TOPTW-MV benchmarks, a multi-start simulated annealing **beat Gurobi outright on 13/72 small instances and tied the remaining 59, in less average time** — i.e., a well-tuned local-search heuristic matches or beats an exact solver on the *small* cases that matter here. [source (strong): https://www.sciencedirect.com/science/article/pii/S0360835217305053]
- On OPTW with time windows at n=50–100, an incremental local search reaches ~4.2% optimality gap in ~2–7 s; exact branch-and-cut is 0% gap but the runtimes (200 ms at n=50, ~1 s at n=100) are the *only* place exact clearly wins — and those are clean academic instances without this planner's meal-precedence/evening-floor/relax machinery. [source (strong, ICLR 2026 peer venue): https://arxiv.org/pdf/2603.06260]
- General tourist-trip design surveys confirm that for TTDP the standard practice is greedy-construction + local search (ILS/VNS/SA), with exact methods reserved for small instances or as an improvement oracle. [source (strong): https://www.sciencedirect.com/science/article/pii/S037722171630296X ; http://webhotel4.ruc.dk/~keld/research/LKH-3/ is the other pole and is explicitly overkill here]

Mapping to this app: the planner's biggest numeric weaknesses are (F2) selection-feasibility decoupling and (F3) the greedy chain not being post-optimized. A **joint** orienteering pass over the pool could, in the worst spread-out cases, cut day travel by up to 38% (measured headroom, work-item 02 §8) with typical 5–15 min/day. That is real, but it is exactly what a deterministic beam/exhaustive step over the ≤9 chosen stops (or a 2-opt/3-opt post-pass with window checks) delivers. CP-SAT adds value only if you want the *selection+order+time* solved jointly against a pool of hundreds — which this app does not have today (pool ≈34 typical, 71 routable local). [estimate: per work-item 02 §7.3, "OR-Tools vs T0-b gain at n≤9 is likely ~0–5%"; flagged as model judgment]

### 3.2 Expected quality delta, honestly

- Travel/feasibility: moderate; captured by T0-b local search in most realistic cases. 0–38% travel reduction only in sparse days; 0–5% *additional* over T0-b at n≤9. [estimate]
- **User-perceived**: near zero by itself. Users do not notice 5 fewer minutes of walking; they notice a 20:10 lunch slot, a closed museum, and an itinerary that ignores their stated "coffee" or "night market" preference. The exact solver optimizes an objective no user stated (min travel); it does not fix perceived relevance. Field evidence on what travelers value (feasibility + preference match first, order detail second) is consistent with this. [source (moderate, survey framing): https://arxiv.org/html/2606.01046v1 (TravelEval: six dimensions; feasibility/rationality precede "user experience utility"); https://arxiv.org/abs/2409.08069 (TravelAgent: Rationality > Comprehensiveness > Personalization, human-rated)]

### 3.3 Costs, risk, and solo-dev burden

- Engineering: model in CP-SAT requires moving meal windows, relaxed evening floors, "rest must precede dinner," and the preference function into integer constraints or soft-cost terms. That is the subtle part — and exactly where infeasibility becomes a new failure mode (no model = no plan = `PipelineUnavailable`) that *must* be handled with slack/degradation, versus today's greedy which gracefully relaxes stop-by-stop. The very OR papers note exact methods can be unusable for operational time limits the moment constraints accumulate (COPTW: "exact methods are too slow for operational purposes"). [source (moderate): https://www.sciencedirect.com/science/article/pii/S240584402031046X]
- Determinism: CP-SAT is deterministic single-threaded but its *outputs change across solver versions*; a solo dev shipping weekly will need solver-version pinning + golden-plan baselines, or tests become flaky-by-upgrade. Andor-Tools community has documented determinism subtleties. [source (moderate): https://github.com/google/or-tools/issues/2793 ; lead's statement in https://groups.google.com/g/or-tools-discuss/c/ECR_9doYUBg]
- Operational: ~0 CPU cost at this size. Main cost is *maintenance attention* — a third-party solver and a model that only you understand.

**Verdict: LOSE vs T0 for now; document a "join at scale" trigger** (e.g., pool >200 or multi-city team routing with cross-leg coupling). Run T0-b first and measure — if post-pass already removes the bad cases, CP-SAT has nothing left to claim at n≤9.

---

## 4. Candidate (b): LLM-as-planner (agent replaces the scheduler)

### 4.1 The benchmark evidence is unambiguous and damaging

- **TravelPlanner (ICML 2024)**: 1,225 curated multi-constraint travel tasks; even GPT-4 scored **0.6% final-pass** (delivered plan, all commonsense + hard constraints); in sole-planning (all info pre-given) the best frontier result climbs only to **4.4%**. [source (strong): https://arxiv.org/abs/2402.01622 ; leaderboard confirm: https://benchmarklist.com/benchmarks/travelplanner]
- **TravelPlanner follow-up (arXiv 2408.06318)**: the "sobering" second-order finding is that **LLM-based self-correction is largely ineffective** — LLM feedback generators could not reliably detect constraint violations, produced false negatives on valid plans, and refinement loops mostly cancelled themselves out; only an *oracle rule-based* feedback source improved plans. If an LLM cannot reliably critique its own itinerary, an agent that is expected to self-repair in production will burn tokens and still fail. [source (strong): https://arxiv.org/html/2408.06318]
- **ChinaTravel (2025)**: on open-ended human queries pure-LLM agents collapse to ~0–2.6% final-pass; neuro-symbolic (LLM extracts constraints + **a deterministic solver verifies**) reaches 37% / 97% on the template benchmark. [source (strong): https://arxiv.org/html/2412.13682v5]
- **Formal-verification wrapper (NAACL 2025)**: with all needed data supplied, o1-preview still only produced 10% viable plans; adding a sound SMT/CP verification+repair layer lifts it to 93.9%. The moral is universal across 2024–2026: **"feasible itinerary" is a constraint-satisfaction job that an LLM doing arithmetic-in-text cannot be trusted to carry alone.** [source (strong): https://aclanthology.org/2025.naacl-long.176/]
- **Scaling does not fix it**: TravelEval (2026) reports that merely scaling the model "*does not stably improve travel planning and even leads to regression in advanced models*" on multi-constraint global planning. [source (strong): https://arxiv.org/html/2606.01046v1]

### 4.2 But map this to what the pipeline actually does

The failure numbers above are for *unconstrained end-to-end itinerary generation with tool use*. This app deliberately does the opposite: the LLM is **boxed** — it may propose place ids / names from a trusted list, and it may write copy; it can never alter times, costs, hours, order, or feasibility, and the output is re-validated (`_apply_copy` enforces `mo_ta_theo_id ⊆ trusted_ids`, `ai.py:54–71`; `assemble` retries then falls back to the draft, `planner.py:1982–1989`). So the architecture already *is* "LLM on top of a safe core," and the feasibility risk of full LLM planning is already neutralized by design.

That means the honest LLM-as-planner question splits in two:

1. *Replace the scheduler itself with an LLM agent?* **No-go.** You would give up a guaranteed-feasible, 0.5 s, testable core for a 0.6–4% feasibility author that needs evals, retries, circuit-breakers (already present), and a monitoring budget. This is the classic "your baseline is better than the thing you'd upgrade to" case. Every production deployment with public evidence — Google AI Overviews trip planning, ItiNera, Personal Travel Solver — uses an *optimizer underneath*. Google: "the produced itineraries are practical and feasible … an algorithm that jointly optimizes for similarity to the LLM plan and real-world factors." [source (strong, first-party industry): https://research.google/blog/optimizing-llm-based-trip-planning ; corroborated by ItiNera https://arxiv.org/html/2402.07204v5 : "Pure LLMs cannot refer to specific POI lists … lack the optimization capabilities … circuitous, lack detail, impractical" and TravelAgent https://arxiv.org/abs/2409.08069]
2. *Is the LLM adding perceptible value on top of the core?* **Yes — and this app already exercises it.** LLM-selected names with "why/activity/tip" copy is precisely the personalization layer that human studies reward. ItiNera's human evaluation (19 users + 33 expert travel assistants) preferred the hybrid across all criteria; their qualitative pathology is the *unoptimized* LLM output, not the copy. [source (strong): https://aclanthology.org/2024.emnlp-industry.104/ , table 3]

### 4.3 Costs, measured against real 2026 prices

Rough per-itinerary LLM cost (label these **estimates**; they move quarterly):

- Current pipeline (already LLM-wrapped): `propose_place_ids` (≤60 candidates → ~4–8 K tokens in, ≤900 out), `draft_itinerary_places` (≤1,400 out), `assemble` (full draft in, ≤1,800 out). Total ≈ 10–30 K tokens/plan. At mid-2026 flash-class prices — DeepSeek V4 Flash **$0.10/M in, $0.20/M out** (V3.2 $0.269/$0.40; cached input ~50% cheaper) → **≈$0.002–0.01/plan**; at a 70B-class Groq endpoint (**~$0.59 in / $0.79 out**, llama-3.3-70b-class, **estimate** — verify quarterly) → ≈$0.01–0.05/plan. [sources (strong pricing, labeled as of mid-2026; moves quarterly): https://tokenrate.dev/blog/providers/deepseek-api-pricing-guide-2026 ; https://costperprompt.com/models/deepseek-deepseek-v3-2 ; https://openrouter.ai/deepseek/deepseek-v3.2 ; Groq https://groq.com/pricing (anchor only)]
- A ReAct-style agent loop that actually searches tools multiplies this by the loop length: published third-party runs show 13.5 LLM calls/44 K tokens/$0.051 per task (LangChain-style) to 39.6 calls/81 K tokens/$0.10 (CrewAI-style) *on one benchmark split* — and those are vendor numbers, mark as **vendor claim, likely flattering**. [source (vendor, treat as claim): https://www.opensymbolic.ai/blog/travelplanner-benchmark]
- Latency is the hidden regressor: the same runs average 47–124 s vs your current 116–477 ms, and an SSE UI that today streams a plan in ~1 s would sit at a spinner for 1–2 minutes or need a full streaming refactor. [source: vendor latency numbers above + first-party current latency]

Monthly budget context from the repo: daily AI budget $10, monthly $300 (`config.py:21–22`). At ~$0.002–0.02/plan *without* agent looping, the current envelope supports tens of thousands of plans/month; an agent loop at $0.05–0.10/plan still fits *today* but changes the unit economics permanently (one ReAct-split run on ChinaTravel cost a reported **$2.4/query with GPT-4o and produced zero constraint-satisfying plans** [source (strong): https://arxiv.org/html/2412.13682v4]) and raises the 429/failure surface (solo dev: provider outages already have a circuit-breaker; looping compounds it).

**Verdict: LOSE as replacement; keep (and deepen) as augmentation.** Rate each planned LLM task against the question "is this adding perceived personalization or merely adding tokens to re-assert what the core already guarantees?"

---

## 5. Candidate (c): LLM + solver hybrid — the one upgrade with a positive evidence track record

The literature consistently reports the *hybrid* (LLM understands intent/preference; optimizer guarantees structure) as the ingredient that moves perceived quality, not either half alone:

- **ItiNera (EMNLP 2024 Industry, KDD UrbComp best paper)**: LLM request decomposition → preference-aware POI retrieval → **cluster-aware spatial optimization** → generation. Beat GPT-4-CoT on every rule-based and LLM-judged metric (≈30% improvement on rule-based personalization metrics; itineraries only ≈100 m/POI longer than a TSP-optimal path — i.e., near-optimal spatial coherence *with* personalization), and its **human preferences (464 regular users + 33 expert travel assistants) confirm the LLM-judge win rates**. [source (strong): https://arxiv.org/html/2402.07204v5 ; https://aclanthology.org/2024.emnlp-industry.104/]
- **Google AI Overviews trip planning**: LLM proposes; a joint optimizer enforces opening hours/travel times and can swap in substitutes. Opposite failure mode shown: LLM-only produced a cross-city-hopping day that the optimizer corrected. This is the largest-scale public proof-of-pattern in the world. [source (strong, first-party): https://research.google/blog/optimizing-llm-based-trip-planning]
- **Personal Travel Solver (ACL 2025)**: LLM translator/preference-encoder + **SCIP solver** for the plan; "LLM-as-judge" used only to compare personalization. [source (weak-moderate; abstract+method seen): https://aclanthology.org/2025.acl-long.1339.pdf]
- The neuro-symbolic results (§4.1) are the same message from the benchmarking side: constraint satisfaction is the solver's job.

**Expected quality delta:** This is the only candidate with plausible *user-perceived* upside: intention-sensitivity (LLM reads "avoid crowds," "newbie, bring family," "nightlife" into a *structured scoring signal* instead of tag-overlap) and copy/narrative that read as a local, not a list. Where the current system's LLM touch is thin is: (i) intent is still essentially keyword-to-tag mapping (`relevant_tags`, `INTENT_PROFILES`), and (ii) narrative is per-slot boilerplate. Depth work — structured intent extraction (like ItiNera's request decomposition) feeding the existing scorer, plus a guardrailed narrative pass — prices at 1–2 extra LLM calls/plan (≈$0.005–0.03 on flash-class models) and days of effort. [estimate; architecture mirrors ItiNera / TravelAgent]

**Verdict: WIN — but this is precisely the "moderate upgrade" of §9, not a rewrite.** The current code is already a weak hybrid; tightening it is ~days of work against the core scheduler that stays untouched and testable.

---

## 6. Candidate (d): learned / ML planner (neural combinatorial optimization)

The best NCO work reaches single-digit optimality gaps *where it is competitive*: DeCoST (ICLR 2026) reports 1.06–1.97% gap at n=50–100 with 30–158 ms inference, beating greedy and local-search baselines. [source (strong): https://arxiv.org/pdf/2603.06260]

Why it still loses here:

1. **Scale mismatch.** This app selects ≤9/stops per day from ≈34–80 candidates. Optimal joint solutions at that size are reachable by exhaustive/DP/CP in ms — there is no gap for a learned model to close. NCO pays off in *generalizing* a solver policy to thousands of large instances; you have dozens of tiny ones.
2. **Distribution shift is a live hazard.** Training data is synthetic OPTW/TOPTW; your instance mixes curated POIs, Vietnamese meal windows, night-market floors, and a hand-tuned preference function. Every catalogue/constraint change would demand retraining and re-validating or silently degrade.
3. **Infra/ops for a solo dev.** Data pipeline + training runs + inference host + evals that no test in the repo can pin deterministically. This is the largest maintenance surface of all four candidates for the least marginal benefit at n≤10.

**Verdict: LOSE decisively. Put a note in the docs: revisit only if multi-city/regional planning makes per-query POI counts approach hundreds.**

---

## 7. Cost and risk model, side by side (2026 basis)

| Dimension | Current (fix-in-place) | CP-SAT | LLM-agent | Hybrid (augment) | NCO |
|---|---|---|---|---|---|
| Latency/plan | ~0.1–0.5 s (measured) | ~ms–s | **47–124 s (vendor runs)** | 1–3 s (adds 2 LLM calls) | ~ms inference, but |
| LLM spend/plan | $0.002–0.02 (current wrap) | $0 | $0.01–0.10+ (up to **$2.4/query** in one benchmarked pure-neural run) | $0.005–0.03 extra | $0 context |
| New failure modes | (bug already known) | infeasibility (no plan), solver-version drift, constraint-not-in-model | hallucinated places, dropped constraints, dead loops, 429s | (existing guards handle) | OOD on catalogue change |
| Testability | 33 deterministic tests pass | golden-invariants + solver pinning | evals + guardrails + probes (est. 15–25% of an AI eng's time on eval infra — [source: https://galileo.ai/blog/llm-as-a-judge-vs-human-evaluation] "elite teams treat evaluation as continuous infrastructure") | existing tests + new fixture | dataset + regression evals, nondeterministic training |
| Ops attention / solo dev | low | medium (solver model maintenance) | **high** (provider drift, budgets, evals) | low | high |

The "hidden multiplier" the current pipeline already defends against is the *agentic token loop*: prompt-caching alone makes a loaded 128 K context cost 4–6× a short one, and per-task agent costs that look like "0.05–0.13" (coding-agent benchmarks) and "47–124 s" (benchmark framework runs) — [sources: https://www.kunalganglani.com/blog/ai-agent-cost-per-task-2026 (0.03–0.13/task); OpenSymbolic vendor table — **estimate/vendor claim for travel agents**] — translate to a permanently higher per-request margin and a latency class change. Every dollar moved from "guaranteed structure" to "LLM re-derives structure" is spent buying back reliability you're currently not paying anything for.

---

## 8. Opportunity cost for a solo developer — the difference that decides

Three solo-dev realities make the *maintenance* asymmetry more decisive than any single number above:

1. **Debugging an infeasible CP model vs debugging greedy rules.** Today, a bad plan is a *validation error with a Vietnamese message*, traceable to one `_compute_slot_bounds` call. A CP-SAT infeasibility is a combinatorial void — you add soft constraints, relax, and debug *why the whole model says UNKNOWN* at 03:00. OR literature consistently shows exact methods choke exactly as "real" constraints (sync, optionality, custom windows) accumulate. [source (moderate): https://www.sciencedirect.com/science/article/pii/S240584402031046X]
2. **Deterministic tests are the cheapest quality insurance a solo dev has.** Greedy heuristics + validation layer test like normal code (33 pass today). LLM paths need, at minimum, recorded prompts, retry accounting, breaker state, cost dashboards (already exist: `store.record_ai_usage`) and *non-deterministic-tolerant* tests — while the entire demo/dev experience in `AI_MODE=mock` silently reverts to deterministic, which means **you will not see what users see** unless eval fixtures cover live-AI runs. Current F9 (end-to-end determinism differs with live AI) is a *medium* finding that a rewrite will widen, not close. [source: code `ai.py` + work-item 02 F9]
3. **The user's "mapping vs intelligent" complaint is mainly a copy/explanation and scoring-data problem.** The highest-leverage question is "does the itinerary *explain why* and *match taste*," which the LLM copy + rating/season data address — not the ordering engine. Travelers' evaluations in the literature foreground feasibility and preference-matching; ordering detail is a distant third. [source: TravelEval dimensions https://arxiv.org/html/2606.01046v1 ; TravelAgent criteria https://arxiv.org/abs/2409.08069]

A rewrite steals 3–6 weeks a solo dev can't bill on experiments. The fix-in-place path (§9) delivers most of the value in days.

---

## 9. The moderate upgrade — cheap, high-ROI changes, in order

Ranked by ROI-per-day-of-work (evidence where available):

1. **Fix the meal-window relax bug (T0-a).** Exclude `meal_type` from `latest_end` widening and harden `trua→nghi→toi→dem` precedence. Removes the lunch-at-20:10 defect in ~57% of tourism plans; near-100% quality gain *where triggered*, zero downside; ~10 LOC + 2 regression tests. [source: work-item 02 T0-a — first-party measurement of 34/60 rate]
2. **Window-respecting local-search post-pass (T0-b).** 2-opt/3-opt or exhaustive over the ≤9 final slots, deterministic, preserving ≥18:00 evening floors and ≤120 min gaps. Removes 0–38% travel on spread plans, typical 5–15 min/day; ~80–150 LOC; deterministic; tests keep passing. This captures the bulk of what CP-SAT would offer at this n. [source: work-item 02 T0-b + §7.3 solver comparison]
3. **Elevate intent parsing: LLM structured extraction → scoring.** Replace/augment `relevant_tags`-keyword matching with a small LLM call (ItiNera-style request decomposition) that outputs structured signals (mood, demography, disliked categories, restaurant budget, morning vs evening bias) mapped onto the *existing* scorer. Moves "mapping" toward "listening" without touching the scheduler. Evidence it works: ItiNera's decomposition step drove its ≈30% metric gain. [source (strong): https://arxiv.org/html/2402.07204v5]
4. **Data-first scoring: ratings/popularity/season.** Add a column and fold into the score so "best possible" stops reflecting popularity, not tag overlap. Literature re-weighted TOP (Chen et al.) reports 20–80% relative quality gains on benchmark TOP-family from popularity/user weights; Google's Places guidance endorses weighted location scores. [sources (moderate): https://www.comp.nus.edu.sg/~atung/publication/automatic2013.pdf ; https://developers.google.com/maps/architecture/places-aggregate-location-score]
5. **Matrix coverage + travel accuracy (F4/F5).** Expand the offline OSRM matrix beyond 50 places and widen the local routable whitelist (71 today). Cheap, purely data-side, immediately improves real-world accuracy of every plan and unlocks the catalogue's variety — which is what "intelligent ≠ same 5 landmarks" reads as. [source: work-item 02 F4/F5, first-party measured 0–2/8–17 matrix-backed legs]
6. **Deepen the narrative layer (guardrailed).** The `assemble`/`draft_itinerary_places` outputs should be the *perceived* upgrade: local-feeling why/activity/tip for every stop, festival/weather-aware. Is already the architecture; polish makes the "mapping→intelligent" delta user-visible at ~cents/day.

Why this beats a rewrite: it changes the *inputs the scheduler receives* (better scoring data, better travel data, structured intent) and the *presentation of the output* (explanation), while leaving the guarantee-laden core untouched and its 33 tests green. The known defects (F1–F3) are directly targeted. Expected aggregate effect on the "mapping" complaint: large; on a top-of-a-spreadsheet "optimality" metric: small-but-real (travel 5–15 min/day). [estimate — no human A/B exists yet; see §10 for how to get one]

---

## 10. How to *actually* validate that an upgrade improves perceived quality

The trap: upgrading without a measurement gate means you'll decide by anecdotes. Concretely, for a solo dev:

**A. Continuous guardrail logging (cheap, do first).** Pipe every generated plan through `validate_plan` again and log violations (they should be 0), latency p95, cost/plan, LLM retry counts, breaker state. This is the feasibility floor any change must not regress. It also turns the lunch-bug class of defect into a dashboard card instead of a support ticket.

**B. Offline reference corpus + regression evals (days, not weeks).** Reuse the exact recipe that found F1: a fixed set of contexts × nonces (work-item 02 ran 10×6), plus structural metrics — travel minutes, idle-beyond-travel, slot counts, opening-hour violations, meal-order violations. Deterministic in `AI_MODE=mock`; run in CI. Any upgrade must not regress these before touching human judgment.

**C. LLM-as-judge as a proxy — with human calibration, never alone.** Evidence: with a decomposed rubric, LLM judges reach ≈80% agreement with human raters — about the same as human-human agreement — but only once calibrated; naive judges carry position bias, verbosity bias, and self-preference (judges favor their own family's outputs), and 93% of teams struggle with judge implementation. [sources (strong-moderate): https://github.com/hankimis/llm-judge-bench (self-preference measurement), https://galileo.ai/blog/llm-as-a-judge-vs-human-evaluation , https://aclanthology.org/2025.ijcnlp-long.18.pdf (judge choice >> position), https://arxiv.org/abs/2404.13076 (self-recognition→self-bias), scale effects in https://arxiv.org/abs/2601.03444 (0–5 scale maximizes human-LLM alignment)]
   Practical protocol for this app: pairwise ("new vs old plan for the same request"), randomized order, 1–5 scale (best human-LLM agreement), rubric decomposed into binary checks (feasible? matches stated intent? romantic/relaxed pacing? reasons feel local?), and a **held-out set of ~30–50 plans scored by one human** (the solo dev + 2 friends) to calibrate and to detect judge drift (e.g., judge now prefers longer plans because the new output is longer). This is the ItiNera pattern (LLM win-rates confirmed by human preference study). [source (strong): https://aclanthology.org/2024.emnlp-industry.104/]

**D. Online measurement (low-traffic-safe).** You already have a `nonce`/`ma_phien` mechanism that produces deterministic variation — use a feature flag or cohort tag so that `?variant=baseline|v2` maps to different pipelines for the same request, then compare *behavioral* signals: plans generated per user, regenerate rate (how many times a user hits "try again" — direct dissatisfaction proxy), edits made, share/favor "back to a plan" actions, plus a lightweight post-plan qualitative ask. At solo-dev volume, favor *regenerate-rate and edit-rate* deltas over statistical significance; they are the cheapest real-yield proxies for "the plan felt wrong." [estimate-var; no single external source describes this exact flow — flag as practice recommendation]

**E. Never let the LLM be the only referee.** Formal-verification and benchmark evidence exist because no one outside the lab trusts LLM self-assessment on feasibility. Keep `validate_plan` as the objective referee for structure; reserve LLM-as-judge strictly for the subjective axes (matching taste, narrative quality) where humans also vary ~20–30%. [source: TravelPlannerPlus feedback-limitation https://arxiv.org/html/2408.06318 — LLM critique unreliable even for constraint *violations*; humans not a gold standard either — https://arxiv.org/abs/2309.16349 — so measure agreement, not "truth"]

---

## 11. Bottom-line decision framing

- **If the user's real complaint is "the output reads like a map, not a plan":** the fix is copy/narrative depth + rating/season data + structured intent — *not* the scheduling engine. Cost: days. Risk: near zero.
- **If the complaint is "the plan is sometimes infeasible/wrong"** (e.g., a 20:10 lunch): fix T0-a, add regression tests. Cost: an afternoon. This is the only known *blocking* defect today, and the replacement candidates do not fix it by themselves.
- **Replacing the scheduler with CP-SAT/LKH/NCO now:** loses on cost/risk; the literature's gains and this app's measured headroom are already captured by a local-search post-pass. Revisit only at pool>200 or multi-day cross-leg coupling (gate: measure T0-b first).
- **Adding a full LLM agent to plan the schedule:** loses on feasibility (0.6–4% benchmark pass rates vs your 100%-guarded core) and costs 100× latency and dollars. It is the one option that *registers a quality regression while costing the most*.
- **Winning move (this lane's recommendation):** T0-a bugfix + T0-b local search + structured-LLM-intent + data scoring + richer narrative, all *around* a scheduler that stays exactly what it is today: deterministic, cheap, fast, testable. Then instrument (§10) so the next upgrade is decided by regenerate-rates and calibrated judge scores, not by feeling.

---

## 12. Executive summary (≈250 words)

Minh Đi Đâu Thế's planner is a deterministic, guardrailed heuristic that is already fast (~0.1–0.5 s), feasible-by-construction (two independent enforcement layers), and testable (33 pass). Against that moving baseline, none of the celebrity upgrades win on merit: a CP-SAT/OR-Tools replacement adds at most a few minutes of travel per day at n≤9 (measured headroom 5–15 min typical, 0–38% in sparse worst cases), and that is captured at ~1/10 the effort by a window-respecting local-search post-pass the current code has compute headroom to run in ms. LLM-as-planner is actively dangerous: TravelPlanner-class benchmarks give frontier models 0.6–4.4% feasibility pass rates, LLM self-correction is empirically unreliable, and not even Google ships LLM itineraries without a solver underneath. Learned solvers (NCO) are wrong at this scale — exact search beats them at n≤10. The upgrade with the only positive human-evaluation evidence is the *hybrid*: LLM understands intent, optimizer guarantees feasibility — and the code already sketches it (LLM selection + copy wrap). The honest diagnosis is that "mapping, not intelligent" comes from (1) a known lunch-after-dinner defect in ~57% of tourism plans, (2) scoring that ignores ratings/season, and (3) intent parsing that is still keyword tagging. All three fix in place in days: fix the meal-window bug, add a deterministic slot post-pass, feed the LLM as a structured-intent extractor, enrich scoring data, deepen the narrative — then measure with guardrail logs, offline deterministic evals, and a human-calibrated LLM judge on regenerate/edit rates.

## 13. Top 5 findings (severity-tagged)

1. **[Blocker]** The current pipeline already has one real, user-visible correctness defect — lunch scheduled 20:10 after dinner/night market in ~57% of full-day tourism plans — and fixing it (relax-window + precedence, ~10 LOC) is a higher-ROI act than any replacement algorithm. [first-party measurement, work-item 02]
2. **[High]** Pure-LLM itinerary planning has *benchmarked* feasibility of 0.6–4.4% (TravelPlanner); LLM self-correction is ineffective; Google/ItiNera/PTS all put a solver underneath. Replacing this scheduler with an agent would buy a measured quality regression at 100× latency and cost. [arXiv 2402.01622, 2408.06318, research.google]
3. **[Medium]** The measurable quality headroom of a global optimizer over this greedy at n≤9 is small (0–38% travel worst-case, ~5–15 min/day typical) and is fully capturable by a deterministic local-search post-pass — CP-SAT only pays off if the candidate pool grows well past 200. [work-item 02 §8; arXiv 2603.06260; CiE 17 CP-TOPTW]
4. **[Medium]** The LLM+solver hybrid is the only candidate with positive human-evaluation evidence (ItiNera ≈30% metric gain, human-confirmed; Google production pattern), and the current architecture is already a weak hybrid — the win is *intensification* (structured intent → existing scorer, deeper narrative), not rewrite. [EMNLP 2024 ItiNera; Google Research blog]
5. **[Medium]** The correct measurement stack is guardrail logging + deterministic offline evals + a *human-calibrated* LLM judge (pairwise, 0–5, decomposed rubric) feeding behavioral proxies (regenerate/edit rates) — LLM-as-judge alone is biased (position/verbosity/self-preference) and 93% of teams misimplement it. [Galileo; llm-judge-bench; IJCNLP 2025; Grading-Scale 2026]

## 14. Confidence and ground-truth tally

**Confidence: 8/10.** The claims about the current system (latency, determinism, 33 tests, feasible-by-construction, 71-place whitelist, haversine-dominant travel, the 34/60 lunch bug) are first-party, measured on the actual code in work-item 02. The external load-bearing claims (TravelPlanner pass rates, LLM self-correction failure, ItiNera/Google hybrid pattern, LLM-judge biases, local-search-vs-exact gaps at small n, 2026 model prices) are each supported by ≥2 independent sources of at least moderate strength. Confidence is not 9–10 because: (a) no A/B against real users exists for *this* app — "users notice 5 min of travel" and "narrative explains the feeling" are reasoned extrapolations from adjacent studies, not measured here; (b) several benefit numbers (CP-SAT-vs-T0-b delta at n≤9, quantile of perceived gain from scoring data, per-plan agent-loop cost from vendor blogs) are labeled estimates/model judgment in the text; (c) DeepSeek/Groq pricing and the OpenSymbolic framework numbers move quarterly and some are vendor claims.

**Ground-truth tally (external-checked facts vs model judgment):**
- First-party (code + measured execution, work-item 02): 12 claims (latency range, determinism, test count, bug mechanism + 34/60 rate, whitelist 71, matrix 50/3529, 0–2 matrix legs, two-layer validation, budget/daily caps, LLM boxed-copy guard, circuit-breaker, SSE stream flow).
- Externally corroborated (≥2 independent sources, each verified by web search during this run): 13 claims (TravelPlanner 0.6% final pass [ICML 2024 page + OSU leaderboard]; sole-planning best 4.4% [paper §5]; TravelPlannerPlus LLM-self-correction unreliable + oracle-rules works [2408.06318 paper + alphaXiv]; ItiNera ≈30% rule-based gain, ≈100 m/POI headroom, 464-user+33-expert human preference, hybrid pattern [EMNLP Industry PDF + arXiv v5 + GitHub]; formal-verification wrapper 93.9% vs o1 10% [NAACL 2025 long.176]; ChinaTravel 37.0% NeSy vs 2.6% pure-neural, 10×, $2.4/query GPT-4o [arXiv v4 + GitHub + OpenReview]; refinement-error decay ≤1/iteration after 3–5 rounds [2412.13682 §5]; MSA beats Gurobi on 13/72 small TOPTW-MV and ties the rest in less time [CiE 2017 (DOI 10.1016/j.cie.2017.10.020 + ScienceON)]; LLM-as-judge ≈80% human agreement once debiased + position/verbosity/self-enhancement bias [MT-Bench 2306.05685 + IJCNLP 2025 position-bias study + EMNLP 2025 self-preference]; 0–5 grading scale maximizes human-LLM agreement [arXiv 2601.03444 + ISSTA 2502.06193 corroboration that scale choice matters]; Google hybrid pattern [research.google blog + booboone mirror]; DeepSeek V4 Flash $0.10/$0.20, V3.2 $0.269/$0.40 mid-2026 [TokenRate + costperprompt + OpenRouter]; effective-solver-on-small-instance phenomenon also visible in Hexaly/Gurobi/OR-Tools TOP comparison (OR-Tools gap grows to 11.7–15.5% as n→400, i.e., solvers only matter at scale) [Hexaly benchmarks 2026]).
- Model judgment / single-source, flagged in text as estimate: CP-SAT-vs-T0-b residual gain at n≤9; transferability of TOP popularity-weight 20–80% to this catalogue; per-plan agent-loop cost & latency (vendor tables); magnitude of perceived quality lift from narrative/data scoring; behavioral-proxy protocol (no external source describes it).
- Unverified pending follow-up: production Postgres path (bang_khoang_cach coverage/freshness beyond the 50-matrix local path); live-AI (non-mock) end-to-end behavior at volume; any user A/B.