# 08 — Red-Team Review: Attacking the Synthesis and Its Recommendation

> Adversarial review of `07-synthesis.md` against its six source lanes (01–06). Nothing here is a defense of the synthesis; the value of the file is finding where a confident recommendation can still waste a solo developer's week. Research-only — no code was changed.
>
> Scope: I read all six lanes in full and the synthesis in full. Every reference below is `file §section` (e.g., `06 §2`). Where I call a number "single-source," it means exactly one independent origin across the whole set, per the lanes' own source-grade conventions. Where I say "unverified for this product," I mean the claim was never measured on THIS repo/audience/catalogue — which is the gap that decides whether the roadmap pays.

---

## 1. Fatal-flow analysis: load-bearing claims that were NOT verified, and which could flip the verdict

The recommendation does not have a single fatal flaw; it has a **/distribution** of unverified load, concentrated exactly where the product's value is claimed to move. Four load-bearing claims to scrutinize:

### 1.1 The perception claim — the load-bearing core, and it is unmeasured for this user
The *entire* case for "intensification, not rewrite" is lane 06's claim that users do not perceive ordering-quality but do perceive copy/intent/data (`06 §3.2`, `06 §8.3`, `07 §1 caveat 1`). Lane 06's own confidence note admits it: *"no A/B against real users exists for this app — 'users notice 5 min of travel' and 'narrative explains the feeling' are reasoned extrapolations from adjacent studies, not measured here"* (`06 §14(a)`). Each adjacent study comes from a non-Vietnamese population: TravelEval/TravelAgent (Chinese/English academic populations), ItiNera (464 users, but on its own deployed dataset), Tripadvisor/Google (US/global). **None of it is a Vietnamese, mobile, budget-market finding.**

If Vietnamese users *do* weight ordering/spread differently than the populations studied, or if copy/intent upgrades fail to move their regenerate-rate, then the entire build order (P1 before P3, spend on copy/intent/data scoring) targets the wrong value channel. The synthesis inherits lane 06's confidence and promotes it to a measured fact ("users do not perceive 5 fewer minutes," `07 §1 caveat 1`) — it is a **model judgment dressed as a finding**. This is the single most dangerous unverified load in the whole deliverable because every phase budget is derived from it.

### 1.2 Vietnamese NL→structured-spec translation quality — zero evidence in any lane
The recommendation's highest-ROI *perceived* leg (`07 §7 P1-c`: "LLM structured extraction → scoring") is a Vietnamese-language LLM capability. The synthesis itself flags this as open question #2 (`07 §6.2`): "the known bottleneck of the whole architecture ... has *zero* Vietnamese evidence in any lane." But then it **bundles that unmeasured capability into a "DAYS" phase (P1) with no acceptance gate and no fail-fast measurement**, while putting the expensive data/plumbing (P3) later.

Direction of the bet: the translation bottleneck collapses at least one formal pipeline from 91.7% → 1.29% on *Chinese* human-style queries (`03 §6.1`; `05 §5`). Vietnamese is lower-resource than Chinese for this kind of nuance capture (dinner/meal culture, "trên đường về," family groupings, tone-marked inflection — the exact class that broke `relevant_tags`, `06 §2` keyword matching). If the flash-class translation is brittle on Vietnamese (a real, unfalsified possibility), the whole "intent elevation" leg under-delivers and the "mapping" feeling persists even after every phase. If robust, the leg pays. **Nothing in the study lets you know which before you spend the days.** This is a load-bearing unverified claim that, if wrong, silently converts the roadmap's flagship upgrade into a vanity feature.

### 1.3 The A/B metrics inherit the matrix/hours error — the gate measures a synthetic world
Phase P2's gate (`07 §7 P2`) compares greedy vs post-pass vs CP-SAT on "score delta, infeasibility count, idle, meal-order violations, wall time." But the feasibility/score/idle quantities are computed against (a) a travel matrix that is haversine for ~95%+ of legs and covers 50/3,529 places (`06 §2`, `06 §9.5`), and (b) OSM hours whose "hard" truth is fabricated where tags are absent/malformed (`05 §1.1` Blocker). So P2 is a *schema-level* A/B: it can certify T0-b "wins on travel minutes" for a quantity that does not exist on the streets, and certify plans "feasible" that are closed doors. The synthesis defers data truth to P3, **after** the decision gate. If this is wrong, the verdict flip is not "more solver," it is "the entire algorithm question was answered against a fiction — and a closed-museum complaint was never algorithmically solvable anyway" (`05 §1.4`).

### 1.4 "Keep the greedy, escape to CP-SAT only at pool>200" — the default direction is chosen under an admitted unmeasured delta
Lane 06's "CP-SAT adds 0–5% over a good post-pass at n≤9" (`06 §3.1`) is labeled **estimate/model judgment** in both lanes (`02 §5.2`, `06 §3.1`), and lane 02's "~1% gap in seconds at n=40" is labeled an interpolation (`02 §2.2`). Neither has been run on this repo (`02 §6`, `07 §6.1` note 1). The synthesis correctly converts this into "measure first" — but "measure first" with the P2 metric set of §1.3 cannot detect the classes of gain that would actually matter (conversion of near-infeasible constructions, real-idle on real legs). **A gate that cannot fail in the direction that matters is not a gate; it is a receipt.**

### Verdict on fatal flows
- The *safe* half of the recommendation (T0-a bugfix, hardened validator, guardrail logging) is first-party measured and low-risk.
- The *valuable* half (intent elevation, scoring data, perception payoff) rests on **two unverified Vietnamese-context claims (perception + VN translation) and one measured-against-fiction decision gate**. Any one of the three being wrong converts "moderate upgrade" into "no perceived change with green checkboxes everywhere." That is the fatal-flow structure: **the fidelity of the outcome (user perception) is inversely correlated with the fidelity of the measurement (objective proxies on fabricated data).**

---

## 2. Attack the acceptance criteria: can "phase N done" be an empty promise?

For each recommendation, the trivially-passing and trivially-failing variants, and what real completion would have to check.

### 2.1 T0-a — meal-window bug fix (`07 §7 P1`, `06 §9.1`)
- **Trivially passes:** "no more 20:10 lunch in the 60 sampled tourism contexts + 2 regression tests." The bug was measured only on full-day *tourism* contexts (`06 §2`, 34/60); other context classes (city-vacation, partial-day, multi-day second legs) were not. The regression tests can be written against the exact 34/60 cases and miss the invariant failing elsewhere. Critically, the 57% figure comes from exactly **one** 60-request sampled run (`06 §2` sources work-item 02) — a single small run, never re-sampled.
- **Trivially fails:** if the acceptance criterion becomes "lunch must be before dinner in *all* contexts" the fix can still ship lunch at 14:30 — ordering-invariant satisfied, yet still culturally wrong and user-visible ("lunch must feel like lunch, real Vietnamese 11:30–13:30 social table," `05 §8` item 2 — a constraint no lane's fix encodes).
- **What "done" must mean:** a *structured invariant* (precedence `trua→nghi→toi→dem` never violated in white-box tests across the full corpus, not just tourism) **plus** a preferred-window envelope assertion (lunch lands inside [11:30, 14:00]) **plus** the existing 60-context sampler re-run green. ~10 LOC is right; the test spec is not.

### 2.2 T0-b — window-respecting local-search post-pass (`07 §7 P1`, `06 §9.2`)
- **Trivially passes:** "travel minutes reduced, tests pass, evening floor and 120-min-gap preserved." Two empty-promise routes: (a) the objective is *haversine* travel; with 95%+ of legs haversine and 71-place whitelist (`06 §2`), the post-pass optimizes a quantity with up to −41%/+25% real-world error (`05 §7`) — "0–38% headroom" is a headroom in synthetic kilometers; (b) the acceptance list in `06 §9.2` ("preserving ≥18:00 floors and ≤120 min gaps") **silently omits re-checking open-hours, meal precedence, and budget on every search move** — a local-search swap that reduces travel by moving a stop into the pre-17:00 closure of a museum **passes all listed criteria and violates the validator gate that lane 05 calls the entire correctness contract** (`05 §9` mitigation #1).
- **Trivially fails:** exact DP for the per-day TSP (`02 §3.4`) at n≤6 is undeniably cheap, but "switch to DP" as a criterion can spend its value on the wrong sub-problem: the pitfall in `06 §2` F3 is that travel weight is 0.15 vs preference range ±50 — a post-pass tuned only on travel can flatten preference ordering and *increase* the perceived "mapping" feeling. A post-pass that reduces travel at the cost of "why are we having lunch in the only café near the road" is optimizing the user's third-priority axis at the cost of their first.
- **What "done" must mean:** every move re-validated against hours+precedence+budget+dedup; **zero new `validate_plan` violations on the corpus**; preference-weighted score non-decreasing (not just travel); perf p95 still sub-second; only then is the "captures the bulk of CP-SAT at this n" claim (`06 §3.3`) earned.

### 2.3 P1-c — structured intent (LLM NL→spec → existing scorer) (`07 §7 P1`, `06 §9.3`)
- **Trivially passes:** "LLM returns valid JSON; signal fields present; cost/latency within budget." The documented failure of this exact component is **silent semantic drift — valid JSON, wrong values, no error** (`03 §2.2`; `05 §5` first bullet), and the translation-loss literature shows constraint capture degrades with naturalness and constraint count (`05 §5` CaStL, NL-PDDL-Bench). A null implementation that parses Vietnamese but drops "no seafood," "bring family," or "morning person" signals will pass every syntax gate and degrade the product vs the deterministic keyword baseline (which at least never silently drops a *declared* must-see).
- **Trivially fails:** a Vietnam translation eval set that is 10 hand-picked requests, or a scorer change with no comparator — then "P1-c done" is exactly as meaningful as "we ran it locally and it felt good" (`06 §8` warns against exactly this, then P1-c ships without the guardrail it prescribes).
- **What "done" must mean:** (i) a held-out VN NL→spec eval (≥~50 real or realistic requests, golden specs) with a measured constraint-capture error rate **beating the `relevant_tags` baseline**, (ii) no dropped must-see/negative constraints in any sampled case, (iii) the *spec* folded into a deterministic cache key so identical requests still produce identical plans (§3.4), (iv) a variant-cohort behavioral test (regenerate-rate) before promotion. If the error rate is not better than keywords, **the correct outcome is to NOT adopt this phase** — an explicitly allowed failure.

### 2.4 Grounded retrieval / substitute fallback (`07 §2.1 [2]`, `06 §9`)
- **Trivially passes:** "substitutes are real catalogue IDs, never free-text POI names" — but if the substitution pool is the same 71-place routable universe, "grounded" is trivially true and *variety* (the actual perception lever "intelligent ≠ same 5 landmarks," `06 §9.5`) is unchanged. The synthesis's own dependency ordering is inverted: T0-b's value and the retrieval variety both grow only after the whitelist/matrix expansion (P3) happens.
- **Trivially fails:** an acceptance that requires freshness but has no refresh cadence (P3 lists it but it is the "2–5 DAYS" step, not a P1 gate).
- **What "done" must mean:** a coverage/variety metric — for N repeated requests with identical intent, distinct POIs served → threshold; catalogue-wide routable reach %; a working refresh pipeline (weekly cadence) actually running, not just a schema.

### 2.5 The CP-SAT A/B gate (`07 §7 P2/P4`)
- **Trivially passes (empty):** on 60 contexts, all three engines produce feasible plans, under 1 s, with score deltas <1%. "Flat → keep P1" (`07 §7 P2`) is then guaranteed **as an artifact of metric coarseness and sample size**, not as a finding. No minimum-detectable-effect, no variance estimate, no CI, no perception axis. A 60-context corpus of a *deterministic* pipeline has zero within-run variance — every engine is a single point estimate per context; "CP-SAT is flat" on 60 points is a fragile conclusion that pre-specifying quantiles cannot rescue.
- **Trivially fails (artifact):** CP-SAT modeled with hours as hard windows computed from OSM tags that are missing/malformed (`05 §1.1` Blocker) produces INFEASIBLE/UNKNOWN storms → "CP-SAT fails at this n" — a modeling-artifact verdict that confirms the no-CP-SAT default against a strawman encoding (this is literally the trap lane 02 §7.2 and lane 05 §3 warn about, then the gate re-runs it).
- **Trivially fails (irrelevance):** the gate measures objective proxies, so even a *correct* run answers "which engine minimizes the synthetic score" — for a decision whose real stake is user-perceived quality (§1.1). If the A/B passes "flat" and the perception problem persists, P4's "whenever gated" trigger (`07 §7`) reads as forever-Meaning: **gating on the unrun A/B is sound as *deferral* (better than choosing by rhetoric), but as designed it is a soft dodge — it externalizes the hard decision to a measurement that cannot detect what would change it.** Two phases of the recommendation (post-pass adoption *and* CP-SAT rejection) are decided by it.

---

## 3. Blind spots: what all lanes collectively assumed that isn't true

1. **Vietnamese NL→spec quality (zero evidence).** No lane fetched a single Vietnamese-language study, benchmark, or eval. Every "translation is the bottleneck" anchor is Chinese or English (`03 §6`, `05 §5`). The claim that macro "flash-class models" handle Vietnamese daily-life travel nuance is an unstated assumption under-pinning P1-c and the §8 "if brittle → fine-tune a 7–20B" hedge — and that hedge has no cost model (data collection for a VN NL→spec corpus, fine-tune infra, eval) for a solo dev on a $300/mo AI budget (`06 §4.3`).

2. **POI data-freshness base rate for THIS catalogue (unmeasured).** Lane 05's own §12(c): "I could not independently estimate the base rate of wrong/closed POIs in the actual Hanoi catalogue." The global evidence (22–73% completeness by class, restaurants churning 20–30%/yr, ~76% cross-catalogue hours mismatch, WeMap 56% category accuracy pre-repair — `05 §1`) is transferred to "a curated OSM catalogue with `KNOWN_HOURS_BY_NAME` overrides" without measurement. Whole sub-recommendations quietly assume the hours are usable as *hard* constraints (Lane 02's model, the P2 gate's infeasibility metric, the validator gate's rule base). **If this catalogue's hours/geo are >10–15% wrong (plausible per the 22–73% and 56% anchors), the "hard" wall that the whole architecture's confidence rests on is a soft wall.**

3. **The reward model — "optimized" is not what a user wants, and nobody checked.** Three independent acknowledgments in-lane (weighted-sum loses Pareto points for maximization, `02 §7.1`; "optimal in math, nonsense for humans," `05 §3`; "ordering detail is a distant third," `06 §8.3`) — yet the post-pass objective *is* travel-minutes, i.e., the tertian-ordered axis, calibrated against no user data (literature populations only). The behavioral-proxy protocol (`06 §10D`) is the honest close-out, but it is scheduled LAST (P5), after the big spends.

4. **Determinism contract vs the new stochastic input upstream.** Today determinism is preserved because the LLM is cosmetic-only (`06 §4.2`). P1-c moves the LLM *into* the decision path (spec → scorer → selection). At temperature 0, hosted LLMs still vary up to 15% accuracy across identical runs; `seed` is best-effort (`05 §4`, `07 §2.3`). The synthesis's determinism claim ("LLM's slop limited to presentation," `07 §2.3`) **stops being true the day spec feeds the planner** unless the spec is cache-keyed on (request-hash, model, prompt, params) — a mechanism mentioned for another purpose (`04 §6`) but not wired into P1-c's acceptance. Without it, "identical request ⇒ identical plan" (`06 §2`) quietly dies on the exact phase that is supposed to say "listening."

5. **Whether user perception tracks plan quality at all.** The premise that any of this moves the product metric (save/regenerate) has zero product-level evidence — no lane measured the current save/regenerate/edit rates (they are prescribed for P5, not measured at P0). The product complaint "mapping, not intelligent" (`06 §8.3`), the anchor for the whole intensification program, is one voice (the founder's), not a user-research finding.

6. **Cost realism for structured-intent + narrative deepening.** The cheap-per-plan arithmetic ($0.002–0.03, `06 §4.3`) is fine *for the calls*, but the change multiplies the LLM's role from 2–3 optional calls to a hard dependency of plan construction: two structured calls now **on the critical path** plus deepened narrative. Solo-dev budgets fine; but nothing prices the *worst case*: a brittle-VN translation triggering the "repair loop over the DSL" (`03 §6.1`) — each repair is another call, and unbounded repair is the documented dollar bomb (`05 §5`, $47k/week class). The phase plan's "unbounded repair loops" NEVER-list (`07 §7`) exists precisely because this is a known failure shape; P1-c should inherit a hard per-request translation-cost breaker by default.

7. **The current pipeline's real defect is not algorithmic at all.** Lane 06's own list (`06 §1`, `06 §11`): one precedence bug, data scoring, intent parsing, copy. All fix in place. The user asked for an *algorithm*; the honest answer is "the algorithm is a minor part of your problem." The synthesis says this (`07 §1`) and then spends its architecture diagram on solver layers — a mismatch between the headline and the spend.

8. **A silent dependency: ratings/popularity/season data for a 3,508-POI OSM/Vietnam catalogue.** Lane 06's §9.4 says "add a column and fold into the score." **No lane verified that this data even exists for these POIs.** A curated OSM catalogue has no ratings by default; buying/google-sourcing 3.5k VN POIs with trustworthy (non-gamed — `05 §1.3`) popularity/rating/season data is a data-acquisition project that every lane treats as a "add a column." This is a catalog-data blind spot that can silently convert "data scoring" into "pseudo-popularity from tag overlap again."

9. **Multi-day and mid-plan flexibility are written out of the plan.** The phase plan is per-day; the A/B corpus is full-day tourism contexts. The product does multi-day (`07 §2`, "≤16 slots"); cross-leg scheduling (the very trigger for P4) is thereby never exercised before P4. Fine as scope discipline, but it means "CP-SAT gated on real deltas" is gated on deltas that exclude the one scenario where CP-SAT's case is strongest — a hole in the gate's logic, not just its power.

---

## 4. Attack the numbers

- **0.6% TravelPlanner (GPT-4, ICML'24).** The most externally verified number in the study: cited in lanes 01/03/05/06, each with ≥2 origins (paper + leaderboard + mirrors). Direction robust. Caveats that matter: it is a 2024-model result on a synthetic-but-verified benchmark; the sweep is about the *pattern*, and later pure-LLM results in the set (TREK "46.2% fully feasible/median 6.6%", ChinaTravel ~0–2.6%, Mystery-Blocksworld 52.8%) keep the ceiling low. Keep it, but note that `0.6%` is an *argument against the architecture this user never proposed adopting* (pure-LLM scheduler) — it decides a question nobody at this repo is asking (§5).

- **"84–94%".** This is the worst-quoted number in the set. C9 (`07 §5`) admits it composites **two different metrics**: ATLAS 84% (live-web multi-turn, Google DeepMind — its 44.4% TravelPlanner FPR is the sibling number) and FormalVerify 93.9% (TravelPlanner, static setting). Quoting "84–94%" as a single band (as `07 §1` TL;DR and `01 §11` finding 1 both do) presents incomparable magnitudes as comparable. **Direction survives** (every solver-backed number ≥~37% vs pure-LLM ≤~10%), but a solo dev will repeat "we go from 0.6% to 84–94%" and that statement is not true for any one system on any one metric. Surgical fix: always pair the number with its setting ("93.9% TravelPlanner formal-verification; 84% ATLAS live-web multi-turn; 37% ChinaTravel NeSy on human-style queries").

- **$2.4/query (GPT-4o, ChinaTravel).** Single benchmark-split cost (`01 §2.3`, `06 §4.3`) on 2024-era GPT-4o pricing, "no constraint-satisfying plans produced." It is (a) not a price card — a different split/current models give materially different numbers, almost certainly cheaper; (b) the *direction* (agent loops cost orders-of-magnitude more than the 2–3-call hybrid) is independently corroborated (U. Twente thesis tokens; config budget `06 §4.3`; cost blogs), so the $2.4's *role* as an order-bound is safe, and its literal value is a hostage to 2024 pricing. Label it "direction-only, price rises/subsides quarterly."

- **93.9% vs 97% (SMT pipeline).** The synthesis's C2 (`07 §5`) calls this "the same paper family reported twice" and collapses to ">90% vs ≤10%." That is a *probable* conflation: lane 03's 97% is Hao et al. (arXiv 2404.11891, OpenReview) while lanes 01/06's 93.9% is the NAACL 2025 long.176 formal-verification work (`01 §2.3`, `06 §4.1`); these may be two distinct papers. **The direction survives either reading** — both are ≥90% on TravelPlanner vs ≤10% for LLM-only o1 — and 3–4pp is not decision-relevant. The synthesis is correct that the architecture conclusion is unaffected; it is not correct that it is one finding. Red-team should pin the paper boundary before anyone quotes "the 97% formal pipeline."

- **Lane 02 vs lane 06 on the same CP result: "seconds–minutes" (`02 §3.1`) vs "hours-of-compute" (`06 §3.1`).** C6 (`07 §5`) calls lane 06 an overstatement and the correction direction is right (those CP runs are minutes-class on 100–200-node corpora). But note **what the two still-misaligned framings do together**: lane 02 uses the CP result to argue *up* ("CP-SAT at n=40 should reach ~1% in seconds"), lane 06 uses the same result to argue *down* ("hours-of-compute academic runs, do not extrapolate down"). Two lanes cite one study to opposite rhetorical purposes; the synthesis's "measure first" resolution is honest, and it is also the only honest resolution, which is exactly why §1.3/§2.5 matter: the deciding measurement is the least externally pinned thing in the whole set.

- **The pool≈34 / n≤9 / whitelist-71 / matrix-50 facts.** Single internal origin (work-item 02, inherited by lane 06). They are *measured first-party facts* (best trust available for this repo), but the sweep to "CP-SAT at n≤9 adds 0–5%" is a lane-06 estimate (`06 §3.1`) the synthesis lifts into the plan's framing. It is the one number the whole "CP-SAT later" stance sits on, and it is model judgment for this distribution, as both lanes state.

- **Is gating on the unrun A/B sound or a dodge?** Sound as *deferral discipline*: it replaces "pick a lane by rhetoric" with measurement, exactly what lanes 02/06 independently demand. Dodge in execution: (a) no pre-specified decision rule or minimum-detectable-effect — "flat" is whatever the 60-point corpus says; (b) metrics measured against fabricated matrix/hours; (c) no perception axis; (d) the strongest CP-SAT regime (multi-day cross-leg) is excluded from the corpus; (e) the trigger "pool > 200, multi-city," is far enough that the gate is effectively a long-term postponement, which *may* be right but is not being argued, it is being deferred. **Net: the gate is the right device wired to the wrong instruments.**

---

## 5. The wrong-question test

**Did the deep dive answer "best modern ALGORITHM," or did it drift into ops/data/copy?** It drifted — consciously and mostly correctly. Lane 06's honest answer is that the algorithm is close-to-fine at n≤9/pool≈34 and the perceived weakness is one bug + data + intent + copy (`06 §1`, `06 §11`); the synthesis adopts that and then still titles its deliverable "the algorithm architecture." The resulting mismatch: the strongest verified numbers in the study (pure-LLM failure, solver-backed >90%, Tripadvisor/Google convergence) argue *against a plan this user was never going to adopt*, while the numbers that actually decide this user's choice (greedy-vs-post-pass-vs-CP-SAT at n≤9 on THIS corpus) are the least verified. The deep dive answered the question the literature made it easy to answer, and answered the user's real question with an unmeasured extrapolation.

**Is the honest answer possibly "the algorithm is fine; the perceived-weakness is elsewhere" — and does the recommendation still serve the user if so?** Yes, that is likely the honest answer (everything lane 06 measured supports it). The recommendation *can* serve the user under that reframe — **only if the perception assumption is turned into a gate rather than a caption**. As written, the perception claim is asserted up front, the objective-only A/B is in the middle, the behavioral proxy is at the end, and the data plumbing that reality-gates everything is third. A user who acts on §7 in order will spend ~1–2 weeks, mark every phase done, and may have moved none of the perceived-quality signals that justified the phases — concluding the research was wrong, when the research's *real* finding (measure behavior first) was delivered last.

Surgical fix: **re-order so the perception question is investigated before the build question** — ship the variant-cohort telemetry (nonce mechanism exists, `06 §10D`) *as* the P0/P1 mezzanine with T0-a, not in P5. Then every subsequent spend is justified or killed by regenerate-rate, not by the lane consensus.

---

## 6. Agenda-echo check: default-option bias

"Keep what you built; do targeted fixes" is the comfortable answer — it confirms (a) the founder's prior that the product isn't fundamentally broken, (b) lane 06's prior (its author wrote the audit that says "don't rewrite"), and (c) the consensus-formation pressure of a six-agent loop whose job description is *converge*. The two forces are hard to disentangle:

- **It is also the right answer on the evidence as measured.** Lane 06's first-party numbers (fast, deterministic, feasible, testable, one real bug) and the cost/risk asymmetry (§1.1–§1.4) genuinely support repair-over-rewrite at this n. The direction is not manufactured.
- **But the recommendation inherits every consensus-mechanism bias the structure set up.** The only substantive disagreement (C1, CP-SAT) was resolved by *deferral* ("measure first") — the least-committal, most-agreeable possible resolution, and the one most likely to be honored in the breach (§2.5). Every lane reached the same final shape (§7 TL;DR "converged"), which is suspicious in a fair process and exactly what an aggregation role rewards. No lane was assigned to argue "the solver is the moat," "rewrite the core," or "the feature isn't the growth lever" — the counterfactuals that would stress-test comfort.

The uncomfortable truth the recommendation does not front-load: **at n≤9/34, the product has probably maxed out its algorithmic headroom, and the marginal investment with real signal is user-behavior measurement and (unverifiable) Vietnamese data quality — i.e., the least glamorous items, which are scheduled last.** Default-option bias is present; the fix is not to flip the verdict but to promote the instruments (behavioral telemetry, data-truth audit, VN translation eval) to gate positions so the comfortable answer is *earned* rather than assumed.

---

## 7. Blocker / High / Medium / Low list with surgical corrections

### Blocker

1. **The perception claim is load-bearing and unmeasured, and the decision gate cannot catch it.**
   - References: `06 §3.2`/`14(a)`; `07 §1 caveat 1`; `07 §7 P2/P5`.
   - Correction: add a **P0-to-P1 mezzanine gate**: wire the existing `nonce` variant mechanism (`06 §10D`) to compare baseline vs P1-intent+narrative on **regenerate-rate / edit-rate / retention-of-plan** before any P3 spend. P2 runs only *after* this gate; emptiness of P2 must be read against it.

2. **Vietnamese NL→spec is the flagship upgrade and has zero evidence; it must be a fail-fast gate, not a phase.**
   - References: `07 §6.2`; `03 §6.1` (1.29% collapse); `05 §5` (translation-loss class); `06 §9.3`.
   - Correction: before P1-c "done," require (i) a VN NL→spec eval set (~≥50 real/realistic requests, golden specs, human-checked) with constraint-capture error rate beating `relevant_tags`; (ii) zero dropped must-see/dislike constraints in samples; (iii) spec folded into the deterministic cache key (`03 §2`/`04 §6`); (iv) hard per-request cost breaker. **Explicitly allow the outcome "don't adopt."**

### High

3. **The CP-SAT A/B gate measures a synthetic world; as specced it can't decide the question.**
   - References: `07 §7 P2`; `06 §2` (haversine ~95%, matrix 50/3529); `05 §1.1` (fabricated hard-hours); `02 §5.2`.
   - Correction: pre-specify a decision rule + minimum-detectable-effect; treat the 60-context set as a point estimate with a permutation/CI treatment; run the gate **after** the data-truth audit (§8) so it measures real-leg feasibility; add a behavioral-perception leg.

4. **Data truth for this catalogue is unmeasured and its plumbing is sequenced after the algorithm work — even though lane 05 marks it the #1 failure mode.**
   - References: `05 §1.1`/`1.2`/`12(c)`; `07 §7 P3` vs `05 §9` mitigation #7.
   - Correction: insert a **Phase 0.5 data-truth audit** (hours-coverage %, malformed/missing base rate, expected closure-velocity, ratings availability for the 3,508 POIs) as a P1 sibling; sequence whitelist/matrix expansion and refresh cadence into/before P2, not P3.

5. **P1-c breaks the determinism contract; the plan-identity story must be updated in the same commit.**
   - References: `07 §2.3` (determinism contract) vs `07 §7 P1-c`; `06 §2` ("identical request ⇒ identical plan"); `05 §4` (15% temp-0 variance).
   - Correction: define explicitly: spec is cache-keyed on (request-hash, model/params, catalogue-snapshot) and is part of plan identity; regression test asserts identical-request identity still holds through the spec step.

6. **T0-a's acceptance criterion is too narrow to be the promised fix; T0-b's is too loose.**
   - References: `06 §9.1`/`9.2`, `05 §8` item 2, `05 §9` mitigation #1.
   - Correction: T0-a = structural invariant + preferred-window envelope across *all* context classes, not "no 20:10 in the 60 sampler." T0-b = every move re-validated (hours/precedence/budget/dedup), zero new `validate_plan` violations, preference score non-decreasing, and objective specified against real (post-audit) legs, not haversine.

### Medium

7. **"84–94%" and "$2.4/query" are used as composite/singular numbers and survive only as direction.**
   - References: `07 §5 C9`, `01 §11`, `06 §4.3`, `03 §6.1`.
   - Correction: always attach setting/metric to each number; mark $2.4 "GPT-4o-era, one split, direction-only."

8. **93.9% vs 97% — possibly two distinct papers collapsed into one finding.**
   - References: `01 §2.3` (NAACL long.176) vs `03 §6.1` (Hao et al., arXiv 2404.11891); `07 §5 C2`.
   - Correction: pin the actual paper boundary before any downstream writeup; direction survives both.

9. **The D0 headroom (0–38% travel, 5–15 min/day) is a one-run internal estimate promoted to a benefit.**
   - References: `06 §3.1` (work-item 02 §8); `06 §14`.
   - Correction: re-sample the 60-context corpus (or extend) before T0-b's expected-benefit framing is quoted to stakeholders.

10. **The "constraint capture" eval corpus (VTNL etc.) does not exist yet; capacity assumptions on flash-class pricing are third-party-index single-source.**
    - References: `06 §4.3` (tokenrate/costperprompt/openrouter), `02 §6` (ortools-import unmeasured).
    - Correction: price quotes are directional; verify quarterly, and keep the fine-tune-7–20B hedge costed (data-collection + eval) before relying on it.

### Low

11. **Minor data/catalogue drift (3,508 vs 3,529) and metric syntax issues in HiMAP arithmetic.**
    - References: `07 §5 C4`/`C5`.
    - Correction: merge to "~3.5k"; drop HiMAP's "+17.7pp" if unreplicable, per C4.

---

## End matter

### 250-word summary

The synthesis is directionally correct and operationally fragile. Its verified core — pure-LLM scheduling fails, solver-backed hybrid dominates, production converges on LLM-translator + deterministic core + validator, data is the common killer — is multi-sourced and secure. The problem is that this verified core **answers a question this user was never going to ask** (should we adopt pure-LLM?), while the user's actual decision (does intensification beat rewrite at n≤9/pool≈34?) rests on claims that are **unmeasured for this product**: that Vietnamese users perceive copy/intent and not ordering; that Vietnamese NL→spec translation works on flash-class models; that this catalogue's hours/geo can anchor *hard* feasibility; that a 60-context A/B on haversine-matrix, fabricated-hours metrics can discriminate; that ratings/popularity data for 3.5k Vietnamese POIs even exists. Every phase can "pass" while the user's "mapping, not intelligent" feeling persists. The comfortable verdict ("keep your system, small fixes") is also likely the right verdict — but it is currently *assumed, then asserted, then measured last*, which is the textbook default-option structure. The surgical fix is to promote the instruments to the front: a Vietnamese translation eval, a data-truth audit of the catalogue, and a live variant-cohort regenerate-rate gate all run as or before Phase 1, so each later spend is justified or killed by measurement instead of by a converging chorus of lanes.

### The single most likely way this recommendation fails in practice

The solo dev executes P1's perceived-quality legs (structured-intent LLM, copy deepening, scoring-data) with green checkboxes on syntax-level criteria — Vietnamese NL→spec is subtly lossy, ratings data silently absent, the post-pass tuned on haversine/whitelist legs — while the P2 objective A/B reports "flat, no CP-SAT needed." Two weeks elapse; every phase is stamped done; the "mapping" feeling and the regenerate-rate do not move; the founder concludes the deep-dive was wrong, and the *measured* parts (bugfix, validator, guardrail logging) get buried along with the unmeasured parts in the rejection.

### Honest confidence

**4/10 that the synthesis's recommendation is safe to follow as written** (order matters, and the follow-order is what's unsafe). Confidence that the *safe half* (T0-a, validator hardening, guardrail logging) is safe to follow: 8/10. Confidence that the *valuable half* (intent elevation, scoring data, perception payoff, and the CP-SAT-deferral verdict) is safe to follow **in sequence as written**: 4/10.

**Ground-truth tally (do not round up):** of ~15 load-bearing claims in the recommendation, I can honestly count **8 as directionally externally verified** from the set itself with ≥2 independent origins (pure-LLM benchmark failure incl. 0.6%; hybrid/converged production pattern per first-party Google + Tripadvisor direction; solver-backed >90% vs ≤10% magnitude-independent; self-correction-degrades; global data-freshness dominance; greedy-weakest/CP-closes-small-literature; LLM-as-judge caveats; LLM-minimal-cost direction via multiple independent cost lines). **7 rest on single-source, in-repo-unmeasured, or pure model judgment** — and, decisively, the **three that carry the recommendation's value** (Vietnamese perception; Vietnamese NL→spec quality; this-catalogue data base rate) are unverified for this product by anyone, verified-for-other-populations or not at all. Everything above that says "recommended" with high confidence is the part a solo dev will do second.

*Do not round up.*