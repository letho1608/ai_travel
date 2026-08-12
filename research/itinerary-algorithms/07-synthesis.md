# 07 — Unified Synthesis: Best Algorithm Architecture for an Automated Travel Itinerary Generator

> Synthesis agent review of lanes 01–06 (`01-empirical-landscape`, `02-optimization-foundations`, `03-llm-planners`, `04-production-architecture`, `05-failure-modes`, `06-honest-baseline`). Problem context: solo developer, Vietnamese travel AI product, FastAPI + Next.js; current pipeline `backend/app/pipeline/planner.py` is a deterministic heuristic "mapping" (intent→tags, score-ranked candidates, greedy slot packing with penalties, NN+2-opt routing, time-window + meal-precedence, budget guard, validation gate; LLM only for place-name selection + copywriting). Question: what is the best, most modern, premium replacement architecture for input→itinerary? Research-only — no code changes made.
>
> Method: full read of all six lane files; every load-bearing number traced back to its lane and cross-checked against sibling lanes; contradictions resolved by re-reading the primary source each lane cites (where the source is quoted/described in two or more lanes, the disagreement is reported as a cross-lane record conflict, not silently absorbed). All six lane files are internally careful about source-grade; this file adds the *between-lane* audit that none of them performed.

---

## 1. TL;DR — direct answer

**The best, most modern, premium architecture is not one algorithm — it is a reliably-wired pipeline:** an LLM (or a fine-tuned small model) that translates Vietnamese intent into a narrow, machine-checked structured spec; grounded retrieval that selects real POI IDs from a curated catalogue; a deterministic feasibility/optimization layer — in this system's current size, a strengthened search over the existing core, escalating to a time-budgeted CP-SAT orchestrator when the candidate pool is large — plus an independent hard validator gate through which every plan must pass; and an LLM narrating only the *verified* result. That is the architecture the peer-reviewed benchmarks, the two strongest first-party production disclosures (Google, Tripadvisor), and every documented deployed system converge on. It is also the **cheapest and fastest** option in the evidence, not a premium spend.

**Honest verdict, in one sentence:** your current system is already a *weak hybrid of exactly this shape* — the upgrade that survives scrutiny is intensification (structured intent extraction, real scoring data, an exact micro-TSP and a window-respecting search post-pass, a validator that catches the lunch-after-dinner bug, deeper narrative) plus two infrastructure moves (data versioning/freshness, self-hosted OSRM matrix), **not a rewrite and definitively not "pure LLM planning".** Pure-LLM scheduling is the empirically worst option available: 0.6% final pass on TravelPlanner, ~0–2.6% on human-style ChinaTravel queries.

Two cautions before the detail:
1. **The "premium" framing is the trap.** Every benchmark, both first-party production posts, and lane 06's measured, first-party code audit say the same thing: users do not perceive 5 fewer minutes of travel. They perceive a 20:10 lunch after dinner (measured in ~57% of this app's full-day plans today), a closed museum, and copy that doesn't explain *why*. The perceivable upgrade is data, intent, and explanation — not a fancier objective function.
2. **The exact-solver "warrant" is scale-dependent and genuinely disputed across lanes 02 and 06** (Section 5, contradiction #1). Both lanes agree on *what to do*: measure on your own corpus before committing (lane 02 explicitly calls its sub-second/~1% figure "an interpolation... that must be validated on this project's own instance distribution"; lane 06 says "run T0-b first and measure"). The build order in Section 8 operationalizes that agreement instead of picking a winner by rhetoric.

---

## 2. The converged recommended architecture

Six independent lanes, approaching from literature, OR theory, LLM capability, production engineering, adversarial failure analysis, and measured baseline — converge on one shape. It differs from today's system only in *where intelligence sits* and *how feasibility is enforced*.

### 2.1 Reference pipeline

```
 User request (Vietnamese NL)
    │  [1] LLM / structured-intent extraction (STRICT JSON, ≤2 retries)
    ▼     → narrow, machine-checked spec: days, party, budget, must-sees,
           dislikes, meal/rhythm priors, hotel anchor. This is a DSL, not prose.
 [2] Grounded selection (code, deterministic)            ▲ LLM never emits:
    │   match spec → real POI IDs from curated catalogue   • POI names/locations
    │   (hours, prices, geo from DB, not from the model)   • hours, prices
    ▼   tier-1 must-see + ranked candidate pool (10–40)    • travel times
 [3] Deterministic feasibility/optimization layer
    │   selection+day-assignment → per-day order → timing
    │   (Phase-1: exact micro-TSP + window-respecting local search
    │    Phase-2+: CP-SAT with hard time budget, greedy warm-start,
    │    relaxation-then-tighten, gap-as-output)
    │   hard: open-hours, meals+precedence, travel-time budget, budget guard
    │   soft: preferred windows, "vibes"/meal-culture → normalized tiers
    ▼
 [4] Independent hard validator gate (decoupled from planner)
    │   rule-checks hours/travel/precedence/budget/dedup on EVERY plan.
    │   Violation ⇒ bug, not chance (blocking).
    ▼
 [5] LLM narrative/copywriting over the VERIFIED plan  (the only stochastic
     surface is this cosmetic layer, exactly as today)
    ▼  [streaming as-is] SSE on-the-fly, is_disconnected(), nonce-replay
 Result  (+ "check before you go", special-hours caveat — keep, 20 languages)
```

### 2.2 Where each piece sits — and what stays from the current system

| Layer | Role | Evidence lane(s) | Kept from today / new |
|---|---|---|---|
| **LLM = translator, not planner** | parse/negotiate intent → spec; re-rank candidates by IDs; narrate. Never schedules. | 01 §2/§4, 03 §1/§6, 04 §1, 05 §5, 06 §4 | Today it already does selection+copy. New: make intent extraction *structured+validated* (ItiNera-style decomposition feeding the existing scorer), not `relevant_tags` keyword matching (06 §9, 03 §8-consequence). |
| **Grounded retrieval** | real catalogue IDs + real attributes; substitutes when must-see infeasible | 01 §2.6/§4, 03 §3, 04 §2 | Today mostly in place (trusted-ID selection). New: candidates pulled via grounded search with substitute fallback (Google pattern), never free-text LLM POIs. |
| **Feasibility/optimization core** | selection+day-assignment (combinatorial), order, O(n) timing. Strictly deterministic. | 02 (architecture), 06 (sizing), 05 (failure contracts) | Today: greedy packing + NN+2-opt. Upgrade: (a) per-day TSP exact DP at n≤6–10 (both lanes 02 §3.4 and 06 §6: enumeration/DP dominates heuristics at this n); (b) window-respecting search post-pass over ≤9 final slots; (c) if/when pool grows → CP-SAT with budget+fallback. |
| **Independent validator gate** | decoupled rule-checker; correctness contract | 05 §9 (Iti-Validator, TripScore, TravelPlanner deterministic checks, DiDi rule-verifiers); 03 §4; 06 | Today: two-layer validation exists but it *shares the planner's own precedence rules* — which is how the 20:10 lunch bug shipped. New: validator hardened against the bug class (06 T0-a), treated as the referee. |
| **Streaming/status** | SSE on-the-fly, disconnect-safe, replay | 04 §3 | Already in place (`plans.py`); add `is_disconnected()` and phase persistence. No job queue yet (in-request is correct at this scale). |
| **Data plumbing** | versioned catalogue + refresh cadence + quality metadata; self-hosted OSRM(CH) matrix + H3-cached routes | 04 §2; 01 §9; 05 §1 | Matrix today covers 50/3,529 POIs, haversine-dominant. New: OSRM CH matrix + H3/Redis route cache, catalogue snapshots + seed propagation for "same input ⇒ same plan" as a contract. |
| **Eval stack** | deterministic validators → calibrated LLM-judge (pairwise, 0–5, decomposed rubric, human spot-check) → product telemetry (save/regenerate/edit rates) | 04 §4, 06 §10 | Largely new; replaces "test locally, feel it in prod." |

### 2.3 The data flows (the load-bearing parts, per lane 04 §2 + lane 05 §1)

- **Catalogue is the product.** Tripadvisor's #1 documented lesson: "you need your data in one place, with high accuracy, taxonomy, and metadata." Every architecture in every lane dies on stale/absent OSM hours, not on the algorithm. Curated overlays over OSM (which `KNOWN_HOURS_BY_NAME`/`visit_guidance` already *are*) plus a weekly/monthly refresh and a `specialDays`-TTL harvest (if a paid Places feed is later affordable) is the industry answer at solo scale.
- **Travel-time realism before solver ambition.** Static OSM-speed estimates carry −41% to +25% error vs reality (ISSIG/ISPRS peer-reviewed). A 20-min buffer is load-bearing margin, not a nicety. Self-hosted OSRM CH on a ~$10–20/mo VPS removes the matrix cost entirely (~$0.03/element-equivalent vs Google's $5/1k); an H3 res-9 → `route_cost:{h3a}:{h3b}` Redis cache with nightly pre-warm gives >95% hit ratio (directional, engineering-blog sourced).
- **Determinism contract.** LLM-at-temperature-0 is not deterministic (up to 15% accuracy variation across identical runs; provider `seed` is "best effort"). So plan *identity* must come from the deterministic core: frozen catalogue snapshot + matrix version + seeded search, with the LLM's slope limited to presentation. Today's nonce-replay is the right mechanism — extend it with an explicit catalogue/matrix version in the key.

---

## 3. Strongest validated findings (with backing lanes)

1. **Pure-LLM single-shot planning is an empirical failure, across every objective benchmark — and this is the most externally-verified claim in the study.** GPT-4: 0.6% final pass on TravelPlanner (ICML 2024); ≤10% best reasoning-model result (Hao et al. eval); <5% at 10 cities (Natural Plan, Google); GPT-4o ~0% / ~2.6% on human-style ChinaTravel (NeurIPS 2025); o1-mini hallucinates *more* out-of-sandbox information (TripTailor, ACL 2025). Verified in lanes 01/03/06, each citing ≥2 independent sources. **The architecture conclusion that follows — never let the LLM own feasibility — is load-bearing and 2+ sourced.**
2. **The documented production systems all reserve the LLM to translation/copy and keep feasibility in code — two first-party posts** (Google AI trip ideas: LLM proposes → per-day DP enumeration + day-level set-packing local search + search-substitute sourcing; Tripadvisor: removed the LLM from recommendation formation, review-graph ranks, latency 40→6.5 s, perceived quality +30%, save-rate 2×). Lanes 01/04/06 all read them the same way. Google + Tripadvisor mutually corroborate; individual metric magnitudes are single-first-party (see Section 6).
3. **"LLM translates → formal/solver decides" is the only pattern with large, reproduced feasibility deltas:** NAACL 2025 formal-verification (SMT/Z3) ~94%/97% on TravelPlanner vs 10% LLM-only; ChinaTravel neuro-symbolic 37.0% FPR (10× over pure neural); To the Globe/MILP ~5 s end-to-end; TRIP-PAL valid near-optimal at ≤10 POIs; ItiNera deployed with 464-user + 33-expert human preference. Lanes 01/03/06 agree on direction; the exact headline numbers have cross-lane deltas — see Section 5.
4. **Self-verification/self-critique without external feedback degrades, does not help** (Huang ICLR'24; Tyen ACL'24: models fix errors only when told *where*; Stechly/Parlay ICLR'25; Kambhampati LLM-Modulo ICML'24; TravelPlanner+ self-correction "largely ineffective"); unbounded refine loops demonstrably decay (ChinaTravel: ≤1 error/iteration after 3–5 rounds; FixMyPlan reverts to original spec). Lanes 01/03/05/06 align. **Design consequence: the repair loop, if any, is gated by a deterministic checker — and capped in rounds and cost.**
5. **The residual hard problem is NL→structured-spec translation, not solving.** The pipeline that "sailed" TravelPlanner at 91.7% collapses to ~1.29% on human-style, under-specified Chinese queries (ChinaTravel Table 14; replicated direction by formalization studies: naturalness and constraint count both degrade capture — ACL'25, CaStL, NL-PDDL-Bench). Lanes 03/05. **Money follows: a narrow DSL with a syntax-checker-gated translation repair loop; for the Vietnamese market, this is the area that most needs your own data.**
6. **Grounding is mandatory but insufficient by itself.** Tools alone didn't lift TravelPlanner past 0.6% — constraint satisfaction is a different failure mode from hallucination. Lanes 01/03/05. Both must be present.
7. **The problem is the (T)OP/TTW family with a clean factorization: selection+day-assignment is the combinatorial core; given the order, optimal timing is O(n) forward/backward interval propagation.** Postal/service feasibility intervals (Savelsbergh et al.); exact timing is not a penalty game. Lane 02 (§2, §4) — this is the single most actionable OR insight and it re-frames what the current planner optimizes. Lane 06's first-party audit independently flags the same thing ("selection ignores schedule feasibility" F2, "timing/penalty machinery" as wrong subproblem). Two lanes agree without having seen each other's files.
8. **Constructive greedy is the weakest OR tier; decent metaheuristics sit 0.3–5% above best-known; plain CP provably closes this size range** (122/304 best-knowns matched, 49/66 known optima proven, on 100–200-node TOPTW corpora — Gedik 2017; 99/168 BKS + 64 new, ~1.64% avg gap — Kirac et al. 2023). Lane 02. The *magnitude* of the win at this app's actual n (≤9 scheduled, pool ≈34) is contested — see contradictions.
9. **Data freshness is the #1 production failure mode, common to all architectures.** OSM opening-hours: ~quarter of tagged values problematic, <10% uncorrectable; POI classes at 22–73% completeness; restaurants churn 20–30%/yr; closures lag weeks even at Google scale; hours disagree across authorities (~76% of a Finnish sample mismatched Google-vs-Apple); WeMap Vietnamese crowdsourced categories at 56% accuracy pre-repair; ~16% of Yelp reviews machine-flagged fake. Verified in lane 05 with heavy peer-reviewed/primary support. **Any acceptable architecture must treat data as the primary investment.**
10. **RL/learned schedulers are not viable here: NCO is a scale play that loses at n≤10** (exact/exhaustive beats it), distribution-shift hazard on catalogue change, reward-hacking risk, opaque for a correctness contract. Lane 06 §6 + lane 05 §6. Production RL-for-itinerary has exactly one claim (DiDi DeepTravel, ~82% online, 3 months) — single arXiv+vendor, un-audited. Skipped with confidence.
11. **Cost/latency economics favor LLM-minimalism decisively**: 2–3 structured calls (+ deterministic verify) vs 10–40 calls in naive ReAct/CrewAI loops; a compute-matched comparison measured a planner-executor at 177,560 tokens/query vs 89,013 single-agent, +5.2pp commonsense, no final-pass gain (U. Twente thesis); ChinaTravel measured $2.4/query for a GPT-4o pure-agent run that produced zero satisfying plans; current app build latency 116–477 ms vs 47–124 s vendor agent-run figures. Lanes 01/03/04/06. Single-source anchors flagged in Section 6, but the *direction* is cross-verified (ChinaTravel + thesis + OpenSymbolic vendor table + Anthropic "simplest solution" guidance).
12. **First-party current-state facts that anchor every decision** (lane 06, measured on the actual code): latency 116–477 ms deterministic; 33 pipeline tests pass; every sampled plan satisfied hard constraints in two enforcement layers; one reproducible user-visible blocker — lunch at 20:10–20:55 *after* dinner/night-market in 34/60 (~57%) full-day tourism plans, caused by `relax` widening meal windows; travel matrix covers only 50/3,529 places (haver-sine for ~95%+ of legs); 71-place local routable whitelist; LLM already boxed (`_apply_copy` enforces trusted-ID subset). **These measured facts mean the upgrade is a delta, not a rebuild.**

---

## 4. Falsified / downweighted claims (did NOT survive cross-check or are single-source)

- **"Multi-agent/multi-orchestration LLM planners are the premium answer."** Falsified across lanes 01/03/04. Multi-agent LLM travel papers report valence-style human evals (8.5/10) with *no controlled constraint-satisfaction pass rate*; the only compute-matched comparison shows 2× tokens and no feasibility gain. Framework choice is orthogonal to planning competence (lane 03 §5). Treat "agentic" as a cost center, not a quality lever.
- **"Bigger model / longer reasoning / self-correction fixes planning."** Downweighted with strong evidence: scaling does not stably improve (TravelEval), reasoning models regress out-of-sandbox fidelity (TripTailor o1-mini 78% vs GPT-4o 96.6%), Mystery-Blocksworld collapse to 52.8%, ≥20-step failure, self-correction degrades (Section 3.4).
- **"LLM-as-judge alone is a reliable eval."** Downweighted — position/verbosity/self-preference biases documented; judged valid only with calibration, pairwise ordering, 0–5 scale, and human spot-checks (lanes 03/04/06). "40→6.5 s / +30% / 2× / +10% CSAT" Tripadvisor numbers: retained as *strong first-party direction*, flagged as single-source magnitudes.
- **"Mem0 / cross-session 'memory' is load-bearing for itinerary quality."** Specifically invented-and-falsified: lane 01 §7 found zero evidence that product-memory framing affects itinerary quality — documented memory is preference persistence or search caching. Nice UX, not an algorithm.
- **"Learned routing/scheduling will displace local search any time soon."** Downweighted — no learned solver displaces local search on TOPTW benchmarks as of 2025 (lane 01 §1.1); exact/DP beats NCO at this n (lane 06).
- **Vendor marketing numbers treated as claims, not facts:** Mindtrip/Layla/Wanderlog/Expedia "architecture" reads; "6.5M POIs", "10M itineraries", "98% email parse", "10× retention"; Sabre+PayPal agentic booking PR; DeepTravel 82% (single arXiv+vendor); OpenSymbolicAI 97.9%/"100%" and its per-call cost table (vendor, explicitly hypotheses in all three lanes that cite it); TREK "46.2% fully feasible / median 6.6%" (single 2026 preprint — keep for direction, not magnitude); Roam Around's $35k/mo davinci-burn story (founder single-source, used only as order-of-magnitude).
- **"The itinerary engine is the product moat."** Downweighted by convergent evidence: sustainment is data + eval + unit economics, not the solver (lanes 01/04/05).

---

## 5. Contradictions between lanes — and how each is resolved

**C1 — Is an exact solver (CP-SAT) warranted at n≈40?** Lane 02 says yes, as the "final authority" over a greedy warm-start, expected to reach optimality-or-~1% in seconds (HIGH direction; the seconds figure labeled interpolation requiring in-repo A/B). Lane 05 doesn't dispute warrant; it enumerates the solver's failure surface (UNKNOWN-under-time-limit ambiguity, over-constrained real inputs, int64 normalization traps, run-to-run INFEASIBLE↔OPTIMAL flakiness anecdotes, reward-model blindness) and demands operational contracts (relaxation-then-tighten, restricted cores, fallback hierarchy, pinned version+seed). **Lane 06 is the actual contradiction,** measured on the deployed reality: at ≤9 scheduled stops/day from a ~34-POI pool, a good local-search post-pass captures the measurable headroom (0–38% travel worst case, typical 5–15 min/day); CP-SAT adds an estimated 0–5% at n≤9 — so "CP-SAT now" is a net LOSE vs targeted fixes, with a documented gate at pool>200 / full-catalogue joint selection.
*Resolution: the disagreement is about priority and scale, and both lanes already converge on the same empirical gate.* Lane 02 §5.2 and lane 06 §3.3 both say: build the A/B first. The synthesis preserves both truths as a phase plan (Section 8): harden the core in place (Phase 1, captures most value at 1/10 cost); run the greedy-vs-post-pass-vs-CP-SAT comparison on the actual corpus (Phase 2); promote CP-SAT/PyVRP only when (a) the A/B shows material infeasibility/idle/score deltas or (b) the pool joins the full catalogue (roughly >200) or multi-day cross-leg coupling appears. Nobody in any lane claims CP-SAT hurts at n=40 in the abstract; the dispute is whether n=40 is this product's operative scale, and lane 06's measured pool (~34) and scheduled n (≤9) say it currently is not.
**C2 — Formal verification success: 93.9% vs 97% — same paper family reported twice.** Lane 01 §2.3 reports the NAACL 2025 formal-verification/SMT result at 93.9% (vs 10% o1) with 81.6–91.7% unsat-core repair; lane 03 §6.1 reports "Hao et al." at 97% final-pass on TravelPlanner. Both cite essentially the same research line, both ≥90%, direction unaffected. *Resolution: treat as one verified finding ("SMT-backed planning lifts TravelPlanner from ~10% to >90%"); the 4-pp spread is a reporting delta the red-team should pin to the actual paper.* (Lane 04 corroborates ">90% vs ≤10%" via MIT-IBM news; lane 06 uses 93.9%.)
**C3 — "TTG" is two different systems with colliding acronyms and almost-identical 91%-scale numbers.** Lane 01's "TTG" = **To the Globe** (EMNLP 2024 demo: LLM→MILP, ~91% NL→symbolic exact-match, ~5 s, cost-ratio 0.979). Lanes 03/05's "TTG" = **TemplatedToGoal**, ChinaTravel's re-implementation/measurement of the Hao-et-al. SMT pipeline — 91.7% TravelPlanner pass → **1.29% collapse on human-style queries**. These are different systems, different metrics, different papers; the 1.29% collapse belongs to the SMT/formal-verification pipeline (which lane 01 separately reports at 93.9%), NOT to To the Globe. A reader scanning tables could attribute the 1.29% to the wrong product. *Resolution: disambiguate in any downstream writeup; the "translation is the bottleneck" conclusion (C3-pointed) stands regardless of which system's number you read.* This is the single most dangerous inherited-terminology hazard in the set.
**C4 — HiMAP-Travel "+17.7pp over ATLAS" arithmetic.** Lane 01 §2.4 reports ATLAS 44.4% and HiMAP 52.8% TravelPlanner FPR, yet says "+17.7pp over ATLAS" — 52.8−44.4 = **8.4pp**. Internally inconsistent. It's a single-source 2026 preprint, so nothing load-bearing rides on it; flag for red-team to re-verify or drop.
**C5 — Catalogue size drift: 3,508 vs 3,529 POIs.** Lane 04 §2.2 says "3,508 curated OSM places"; lane 06 §2 says "matrix covers 50 of 3,529 places." First-party number drift across measurement dates. Minor; merge as "~3.5k curated OSM places."
**C6 — CP-TOPTW runtimes: "seconds–minutes" vs "hours-of-compute."** Lane 02 (Gedik 2017: seconds–minutes; Kirac 2023: ~203 s average including hard large instances) vs lane 06 §3.1 characterising the same results as "hours-of-compute academic runs." Lane 06 overstates; direction unchanged (these are 100–480-node corpora, not this app's n). Correction: the CP runs that matter here are minutes-class on 100–200 nodes, which only strengthens lane 02's interpolation claim — and lane 06's "the solver isn't the bottleneck at n≤9" finding stands independently.
**C7 — Tripadvisor latency: 40→6.5 s (v2 recommender) vs "10–15 s first-draft" (2025 review).** Different generations/sources of the same product; not a contradiction — the 40→6.5 s is the documented v2 change, the 10–15 s is a third-party UX observation later. Both reported as-is.
**C8 — LLM-Modulo improvements: "~4.6× (GPT-4-Turbo)" (01) vs "17.5→20.6% / 25.55% final-pass" (03).** Reconcilable: 4.4%×~4.6 ≈ 20%. Same underlying result at two granularities. Not a contradiction.
**C9 — "84–94%" headline range (01 §11).** Composites two different metrics: ATLAS **84%** is multi-turn live-web pass; FormalVerify **93.9%** is TravelPlanner benchmark. Both sourced, but the range shouldn't be quoted as one number. Use "~84–94% across two measured settings" with the metric caveat.

**Net:** no flat contradiction survives on anything that changes the architecture recommendation. The one *substantive* dispute (C1) is a scale/priority difference that both sides agree to resolve by in-repo measurement; the rest are reporting deltas and an acronym collision.

---

## 6. Where evidence is thin (open questions / single-source claims to verify)

1. **CP-SAT at precisely this problem (n=40, 16 slots, meals, driving matrix) reaching ~1% in seconds is an interpolation, not a measurement** — no `ortools` run exists in-repo (lane 02 couldn't install it in its environment; lane 06's numbers are for *post-pass vs greedy*). This is the single biggest gap between "recommended" and "verified." Needs: one afternoon's A/B on the existing 60-request corpus.
2. **Vietnamese-language NL→structured-spec quality.** The known bottleneck of the whole architecture (C3/1.29%) has *zero* Vietnamese evidence in any lane. We don't know whether flash-class models translate Vietnamese meal/habit/nuance reliably, what the VN API cost/latency profile is, or whether a 7–20B fine-tune beats frontier for this slice. Highest-value open question for *this* product.
3. **Exact-magnitude anchor numbers that are single/first-party-only:** Tripadvisor 40→6.5 s & +30%/2×/CSAT (first-party, independent press corroborates direction only); U. Twente 177,560-vs-89,013 tokens (single, rigorous thesis) — treated as the strongest directional anchor but un-replicated; $47k/week runaway loop and provider-uptime/incident economics (practitioner blog magnitudes); 76.1% Google-vs-Apple hours mismatch (single marketing study); OSM/Vietnam-specific hours-missing base rate measured on *this* catalogue (never computed — lane 05 says magnitude is first-party-measurable); H3 cache ">95% hit ratio" and "$3k–6k/mo API bill at 5k users" (engineering-blog estimates); the pool>200 CP-SAT trigger (model judgment in lane 06).
4. **2026 preprint SOTA numbers** (HiMAP-Travel 52.8%, TriFlow, Behavior Forest, TREK 46.2%/median 6.6%, Frontier formalization) are single-source and some internally inconsistent (C4). Treat as direction only; none is load-bearing for the recommendation.
5. **Human-perceived value of "5 min less travel" vs "copy that matches taste"** — reasoned extrapolation from TravelEval/TravelAgent dimensions; no user A/B exists for this product. Lane 06's behavioral-proxy protocol (regenerate/edit rates + variant cohorts) is the honest way to close this.
6. **DeepTravel/DiDi 82% online accuracy** — one production RL claim, un-audited, vendor-adjacent; keep as "the only RL production datapoint," not as evidence to adopt RL.
7. **Vietnam-specific data quality on the actual catalogue** (hours missing %, category-label accuracy under WeMap-56% baseline, Tết special-hours). Unmeasured; affects whether "hard hours" are even trustworthy (lane 05 §1.1 Blocker).

---

## 7. Decision tree / build order for a solo developer

Order is ROI-first and measurement-gated; each phase leaves the app shippable with green tests.

```
P0  (already satisfied)  Institutionalize honesty:
     guardrail logging on every plan: validate_plan violations (should be 0),
     latency p95, $/plan, retry counts. (Lane 06 §10A — cheapest correctness floor.)
P1  Fix-in-place (DAYS)               ── lane 06 §9, cost ~1/10 of any rewrite:
  ├─ T0-a: meal-window relax bug (20:10 lunch) → exclude meal from latest_end
  │        widening; harden trua→nghi→toi→dem precedence. +2 regression tests.
  ├─ T0-b: window-respecting local-search post-pass over ≤9 final slots
  │        (or exact DP for per-day TSP at n≤6–10 — lanes 02/06 both approve).
  ├─ Structured intent: small LLM call → structured signals → existing scorer
  │        (ItiNera-style decomposition). LLM stays boxed; spec is the DSL seed.
  ├─ Data scoring: ratings/popularity/season into the score.
  └─ Hardened validator gate as its own module (decode from planner's rules).
P2  Measurement gate (HALF-DAY TO DAYS):
     A/B on existing 60-request corpus: current greedy vs P1-post-pass vs a
     time-limited CP-SAT sketch. Metrics: score delta, infeasibility count,
     idle, meal-order violations, p95 wall time. (Lane 02 §5.2, lane 06 §3.3.)
       → if CP-SAT is flat at the pool's n: keep P1 core; revisit at gate below.
       → if CP-SAT removes material infeasibility/idle: promote it (P4).
P3  Production infra (2–5 DAYS):
     self-hosted OSRM(CH) + Redis H3 route-cost cache + haversine prefilter;
     catalogue snapshot versioning + refresh cadence + quality metadata;
     extend matrix coverage beyond 50 places; widen 71-place routable whitelist.
     (Lane 04 §2/§6: determinism contract = frozen data + seed.)
P4  Escalation layer (WHEN GATED):
     pool > ~200 (full-catalogue joint selection) OR multi-city cross-leg
     coupling OR P2 shows a real delta → CP-SAT orchestrator (hard windows,
     meals/precedence, lexicographic tiers, max_time_in_seconds, greedy
     warm-start, relaxation-then-tighten, version+seed pinned). PyVRP as the
     <1 s speed floor if latency ever demands. (Lane 02 §8; lane 06 gate.)
P5  Eval + product telemetry (ONGOING):
     P1-logs → deterministic regression corpus in CI → calibrated pairwise
     LLM-judge (0–5, decomposed rubric, ~30–50 human-scored for calibration)
     → behavioral proxies (regenerate/edit rates, variant cohorts via nonce).
     (Lane 06 §10; lane 04 §4.)
NEVER  pure-LLM scheduler; multi-agent/crew graphs; NCO/learned scheduler;
       vector-DB-as-primary-store; unbounded repair loops (hard max-iter + cost
       breaker per lane 05 §9); Mem0-style memory as an algorithm feature.
```

Why this sequence is correct (not just defensible): it front-loads the two things every lane agrees are the *observed* differentiators — a deterministic feasibility/validator core (01/03/04/05 all: "semantics are the LLM's; feasibility and optimality are a solver's") and data grounding (04/05: "the catalogue is the product") — and it defers the only contested component (CP-SAT) until your own measurement, not a lane's rhetoric, says it pays.

---

## 8. What would change the recommendation

- **If an in-repo A/B shows CP-SAT/PyVRP materially reducing infeasible/idle constructions even at pool ≈34** → promote the solver layer into P1's slot; the phase plan explicitly allows this. (Confidence in the *architecture* direction is independent of this; only the timing changes.)
- **If Vietnamese NL→spec translation proves brittle on flash-class models** (expected given ChinaTravel's 1.29%) → invest in a narrow DSL + syntax-checker repair loop + a fine-tuned 7–20B spec-translator *before* widening the LLM's role. If it's robust, the thin-translator pattern is confirmed locally.
- **If the catalogue grows to full-catalogue joint selection (>~200) or multi-city cross-leg coupling** → exact global optimization changes from "maybe" to "default"; re-read lane 02 as the primary spec.
- **If per-request latency budget falls below ~1 s or catalogue sizes exceed ~60 candidates** → PyVRP becomes the default feasibility engine over CP-SAT (lane 02 §3.3).
- **If real production numbers appear for agentic-RL travel planners at comparable scale with independent audits** (only DeepTravel exists today, un-audited) → revisit learned-*verifier*-hybrids; the deterministic gate stays.
- **If POI data freshness cannot be brought under control in Vietnam** (hours-missing base rate stays high, no refresh pipeline) → shift investment from *any* algorithm to the data harness; the "never infeasible" contract is un-meetable otherwise (lane 05 §1 blocker).
- **If the daily AI budget or latency ceiling tightens** → the LLM-minimalist 2–3-call design is the safest posture (lanes 01/03/06 economics).

---

## 9. Executive summary (≈250 words)

Six independent research lanes — empirical landscape, OR foundations, LLM-planner evaluation, production engineering, adversarial failure modes, and an honest baseline audit of this repo's actual planner — converge on a single architecture. The premium answer is not pure LLM planning, not an end-to-end learned model, and not a naked CP-SAT rewrite either; it is a **hybrid pipeline**: an LLM translates Vietnamese intent into a narrow, machine-checked spec; grounded retrieval selects real POI IDs from a curated catalogue; a deterministic feasibility layer (exact micro-TSP + window-respecting local search today, escalating to time-budgeted CP-SAT if the pool grows) owns hours, meals/precedence, budget, and timing; an independent validator gate rejects anything infeasible; and the LLM narrates only the verified plan. This is what Google and Tripadvisor ship, what every objective benchmark rewards (pure-LLM success is 0.6–4.4%; solver-backed reaches >90%), and — critically for this repo — it is a delta on code that already sketches it, not a rewrite. The measured facts are decisive: the app is fast (116–477 ms), deterministic, and fully feasible today, with one real defect (20:10 lunch in ~57% of full-day plans) and real data gaps (50/3,529 POIs matrixed, haversine-dominant legs, keyword intent parsing). Build order: fix the meal bug + add a search post-pass + structured intent + rating/season scoring, then measure CP-SAT against your own corpus before adopting it, then add OSRM/H3 data plumbing and a three-layer eval stack. Defer multi-agent frameworks, learned schedulers, and memory — none has production evidence of paying at this scale. The architecture is settled; the open questions are Vietnamese translation quality, your own data freshness, and measuring, not predicting, the solver's payoff.

---

## 10. Verification-flags for red-team / follow-up

Six load-bearing claims the red-team should specifically check (each is either single-source, cross-lane inconsistent, or interpolation):

1. **Formal-verification/SMT headline: 93.9% (NAACL 2025, lanes 01/06) vs 97% (arXiv/OpenReview, lane 03) — pin the paper's actual reported TravelPlanner success number; also confirm the "81.6–91.7% unsat-repair" figure's scope (C2).**
2. **"TTG" disambiguation: confirm To-the-Globe (EMNLP 2024, MILP, ~91% backtranslation) and TemplatedToGoal (ChinaTravel's SMT pipeline, 91.7%→1.29%) are distinct systems, and that the 1.29% collapse attaches to the SMT pipeline (C3).**
3. **ChinaTravel "$2.4/query (GPT-4o, zero constraint-satisfying plans)": confirm against the actual paper/table, and note it's one benchmark split's cost, not a price card (lanes 01/06).**
4. **U. Twente thesis (177,560 vs 89,013 tokens/query; no pass-rate gain) — the load-bearing "multi-agent is wasteful" anchor is a single, rigorous-but-unreplicated source; seek an independent replication or accept it as direction-only (lanes 01/04).**
5. **CP-SAT-at-n=40 "≤~1% gap in seconds" interpolation vs lane 06's "0–5% over a good post-pass at n≤9": the deciding A/B on this repo's own 60-request corpus has never been run — treat every secondary use of these magnitudes as unverified until it is (C1).**
6. **HiMAP-Travel "+17.7pp over ATLAS" is arithmetically inconsistent (52.8−44.4 = 8.4) — drop if unreplicable (C4); likewise TREK 46.2%/6.6% and DeepTravel 82% are single-source 2026 claims to keep as direction only.**

---

## 11. Confidence

**Combined confidence: 7/10.** Consistent with the confidence rule: the headline recommendation rests on *consensus across all six lanes grounded in cited sources* (four+ independent peer-reviewed benchmark families, two first-party production engineering posts, OR peer-reviewed foundations, and the repo's own measured baseline) — that qualifies for the 7–8 band; I do **not** round up to 8 for three reasons: (a) the one component whose magnitude is contested (CP-SAT's payoff at this scale) is centered on an unrun in-repo A/B — i.e., the part of the recommendation a solo dev must *act on* first is the least externally pinned; (b) the product's specific bottlenecks (Vietnamese NL→spec translation, Vietnamese POI data freshness) have zero direct evidence in any lane; (c) several headline magnitudes (Tripadvisor metrics, $2.4/query, token ratios, 2026 preprints) are single/first-party-source and some are internally inconsistent (C2–C4).

**Ground-truth tally (do-not-round-up):**
- **11 of 14 direction-level load-bearing conclusions are externally verified across lanes (≥2 independent cited sources each):** pure-LLM planning fails on objective benchmarks; hybrid/solver-backed wins by large margins; production convergence on LLM-in-middle + deterministic core (Google+Tripadvisor+MIT-IBM); self-verification unreliable without external feedback; NL→spec is the residual bottleneck (ChinaTravel + 3 formalization studies); grounding is mandatory-but-insufficient; TOPTW-family + O(n) exact timing given order (2+ OR papers); greedy = weakest tier and CP closes small instances (2+ peer papers); data freshness/hours is the dominant shared failure mode (TRB + Safegraph + primary + FourSquare); learned/RL schedulers not production-viable at this n (OR + NCO venue + single DeepTravel anchor); cost/latency favor LLM-minimalism (ChinaTravel + thesis + Anthropic guidance). Full first-party set: current app speed/feasibility/test-mechanisms + the 34/60 meal bug are measured in-repo (lane 06).
- **2 direction-level conclusions rest on strong single-source evidence only:** Tripadvisor's specific magnitude set (40→6.5 s, +30%, 2×, +10% CSAT — first-party, independently-corroborated direction, not numbers) and the U. Twente multi-agent token comparison (rigorous but un-replicated).
- **1 is model judgment/interpolation for this instance distribution:** CP-SAT at pool≈34/n≤9 beating a well-tuned post-pass (lanes 02/06 both flag this gap-magnitude claim as in-repo-unmeasured).
- All single-source 2026-preprint SOTA, vendor cost/latency tables, and marketing product reads are excluded from the tally per the lane-01 convention.

*Net: 11/14 direction-level conclusions externally verified; the recommendation rests on the verified block. Confidence 7/10 — do not round up.*