# 01 — Empirical Landscape: What Documented Systems Actually Exist for Automated Itinerary Generation (2020–2026)

> Lane 1 of 6. Scope: survey the *documented* landscape of automated travel itinerary / trip-planning systems — academic and commercial — as of 2024–2026. This is a landscape map, not a recommendation. Combinatorial-optimization depth, LLM-planner internals, production architecture detail, failure modes, and baseline comparisons are deliberately left to lanes 2, 3, 4, 5, 6.
>
> Method: aggressive web search across arXiv/ACL/AAAI/ICML/NeurIPS/PMLR pages, Springer/Elsevier/OPSEARCH/IEEE sources, Google/OpenAI/company engineering blogs, and independent trade press (Skift, PhocusWire, TechCrunch, Axios, Travel Weekly). Every load-bearing number is attributed; single-source claims are flagged explicitly. Where the same fact appears in 2+ independent sources it is marked **2-src**.
>
> Source-grade convention: **strong** = peer-reviewed/replicated (ICML/ACL/EMNLP/NAACL/ICLR/OR journals) or first-party engineering blog with reproducible method; **medium** = credible engineering blog or 2+ corroborating trade articles; **weak** = vendor marketing, single founder interview, or single blog (used only to anchor orders of magnitude, never as proof).
>
> Bottom line up front: The honest answer to "what's the state-of-the-art architecture" is a well-documented, thinned hybrid — LLM for semantics + a deterministic solver/verifier for feasibility — not pure-LLM planning, and not a fully learned end-to-end model. No commercial product documents a pure-LLM itinerary engine surviving at scale; the ones that document numbers all reserved the LLM role to language, preference, and grounding, and moved hard constraints into code or solvers.

---

## 1. The OR mainstream is still the backbone: Tourist Trip Design / Orienteering (2020–2025)

The academic core of itinerary generation never stopped being the **Orienteering Problem (OP)** family — specifically the Team OP with Time Windows (TOPTW), which models each day as a route with opening hours as time windows and the tourist's satisfaction as the collected score. Three surveys mark the canonical state:

- Vansteenwegen, Souffriau & Van Oudheusden, "The orienteering problem: A survey," *EJOR* 2011; and Gunawan, Lau & Vansteenwegen, "Orienteering Problem: A survey of recent variants, solution approaches and applications," *EJOR* 2016 [source: https://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html].
- **Ruiz-Meza & Montoya-Torres (2022)**, "A systematic literature review for the tourist trip design problem: Extensions, solution techniques and future research lines," *Operations Research Perspectives* 9 — the most recent systematic review; its taxonomy confirms OP/TOPTW as the dominant formalization and enumerates extensions (budget, weather, breaks, hotel selection, green/multimodal) [source: https://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html].
- Gavalas et al. (2014), "A survey on algorithmic approaches for solving tourist trip design problems," *Journal of Heuristics* 20 — still the standard reference for TTDP taxonomy [source: https://www.researchgate.net/publication/271921760_A_survey_on_algorithmic_approaches_for_solving_tourist_trip_design_problems].

### 1.1 Exact vs metaheuristic split (2020–2025): who builds on what

The literature cleanly splits by instance size:

- **Exact / mathematical-programming results are small-instance results.** Constraint Programming still sets best-known solutions on TOPTW benchmarks: Gehret et al. solve TOPTW with mandatory visits (TOPTW-MV) via CP, finding **99 best-known solutions and 64 new best-known solutions** on benchmark instances [source: https://www.inderscience.com/info/inarticle.php?artid=128542]. MILP/CPLEX remains tractable only for reduced POI sets (25–100 nodes) and is regularly beaten in *time* by heuristics at larger scale — e.g., discrete PSO vs CPLEX gap comparisons on 25/50-node TOPTW instances (S-DPSO, [source: https://ink.library.smu.edu.sg/cgi/viewcontent.cgi?article=5472&context=sis_research]).
- **Metaheuristics dominate every real-scale deployment**: Iterated Local Search (ILS), Variable Neighborhood Search (VNS), Simulated Annealing, Adaptive Neighborhood SA (ANSA), Ant Colony (ACS), GRASP, Genetic/D-PSO hybrids, I3CH (iterative three-component). Recent examples: Sylejmani et al. (2024), "Solving the tourist trip planning problem with attraction patterns using meta-heuristics," *Information Technology & Tourism* 26(4):633–678 [source: http://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html]; Yalcin, Malta & Saylik (2023), TTDP with budget+weather+break constraints, heuristic vs exact model on Eskişehir (Türkiye) real data [source: https://link.springer.com/article/10.1007/s12597-023-00678-5]; an incremental-local-search TOPTW with variable profits (TOPTWVP), adapted to travel-style preferences [source: https://www.sciencedirect.com/science/article/pii/S156849462400173X]; ANSA on TOPTW+mandatory visits+activity selection with a Tak (Thailand) case study, scores derived from Google Maps ratings [source: https://www.mdpi.com/1999-4893/18/2/110]; multi-day urban tours with hotel selection, *Omega* 126 (2024) [source: https://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html]; and the 2025 hybrid evolutionary algorithm for the clustered OP, *EJOR* 313:418–434 (2024) [source: https://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html].
- **A subtle but important 2023–2025 shift**: the frontier of OR-to-product translation is a *solver pipeline*: presolve → LP relaxation for bounds → warm-start insertion heuristic → branch-and-cut closing the gap, i.e., combining the exact and heuristic regimes explicitly (see the Unki production case in §6). The exact math is used to *prove* near-optimality of what the heuristic found, and deployed with a deliberate gap cutoff (e.g., ~10%).

### 1.2 What the 2020-2025 OR work adds that a 2015 system wouldn't have

Not much new in the *core* model — the genuinely new material is constraint realism and scale-up:

- **Constraint realism**: budget + weather + mandatory breaks modeled as first-class constraints (2023) [source: OPSEARCH link above]; time-dependent travel times + mode selection (Tenerife GRASP study) [source: https://www.sciencedirect.com/science/article/pii/S2352146523003411]; green/multimodal/VRU-aware variants [source: https://www.scitepress.org/Papers/2023/116695/116695.pdf].
- **Centralized multi-visitor planning** with activity reservations in crowded destinations (CWI Amsterdam, *Computers & Operations Research* 167, 2024): an algorithm that coordinates many visitors' trips, achieving solutions within 5–10% of an ILP optimum and handling 10k+ visitors/day in minutes — direct evidence that large-scale coordinated schedule optimization is viable and not just toy-scale [source: https://ir.cwi.nl/pub/34122/].
- **Online optimization with prediction-based orienteering** (Capacitated TOP with "predictions of unknown accuracy," *Transportation Research Part B* 185, 2024) — the OR community's answer to uncertain service/predicted attributes, i.e., the same robustness theme the LLM literature hits with verifiers [source: https://ideas.repec.org/a/eee/oprepe/v9y2022ics2214716022000069.html].

**Landscape takeaway for OR**: the documented dominant pattern for real TTDP is *ILS/VNS/SA-class local search with time-window handling, backed by benchmarks (Solomon/Cordeau-derived OPTW/TOPTW instance sets, hosted at the KUL OP library, kuleuven.be/cib/op) [source: https://github.com/abmoya/TTDP_VNS; https://annals-csis.org/Volume_30/drp/pdf/158.pdf]*. There is no mainstream learned-solver replacing this; machine-learning *solves* for scheduling have not displaced local search on TOPTW benchmarks as of 2025.

---

## 2. LLM-based itinerary generation, 2024–2026: the documented systems

This is the fastest-moving area and the one most polluted by marketing. Categorize by *what the LLM is actually trusted to do*.

### 2.1 Pure single-shot / prompted LLM planning — documented as failing

The load-bearing evidence that a single LLM call cannot do constraint-heavy itinerary generation:

- **TravelPlanner (ICML 2024)**: 1,225 human-verified queries; even GPT-4 with full tool use achieved **0.6% final success rate**; failure diagnosed as losing task focus, mis-tooling, and failing to track multiple constraints [source: https://proceedings.mlr.press/v235/xie24j.html; 2-src with https://osu-nlp-group.github.io/TravelPlanner/ and the GitHub leaderboard https://github.com/OSU-NLP-Group/TravelPlanner].
- **Natural Plan (2024)**: with *all* flight/map data already in context (no tool-use needed), GPT-4 scored **31.1%** and Gemini 1.5 Pro **34.8%** on multi-city Trip Planning; **all models <5% at 10 cities**; self-correction did not help [source: https://arxiv.org/html/2406.04520v1].
- **TripTailor (ACL 2025 Findings)**: 500k+ real POIs, ~4,000 real itineraries; given *all* POI information, best model GPT-4o reached **21.5% feasible+rational**, and **<10% of SOTA LLM itineraries reached human-level quality**; "feasibility ≠ rationality" (route-distance ratio of direct LLM plans was 3–4× a human plan's) [source: https://aclanthology.org/2025.findings-acl.503/; 2-src with arxiv:2508.01432].
- **ChatGPT-apps vendor benchmarks (note)**: third-party 2026 tests of Claude models on a 5-day SF→Tokyo itinerary with `$3,500` budget found models violating constraints (adding a 6th day, overspending flights, truncating mid-plan) — confirming the single-shot pattern is brittle even on frontier models. **Weak evidence, single vendor** (AIgentic blog), included only as an anchor [source: https://aigentic.blog/benchmark-tool-planning-travel-haiku-sonnet-opus].

### 2.2 Self-verification loops over LLM output (no solver) — modest, documented gains

- **LLM-Modulo** (Kambhampati et al.) is the canonical framing: LLM proposes, external sound critics verify and backprompt. On TravelPlanner, the ASU team's instantiation **improved GPT-4-Turbo baselines ~4.6×** and took GPT-3.5-Turbo from ~0% to 5% [source: https://arxiv.org/abs/2405.20625v1; 2-src with https://arxiv.org/abs/2402.01817v3]. The position paper's claim "LLMs can't plan, but can help planning" is the keystone: self-verification by the LLM itself fails; external deterministic critics are what make the gains [source: https://arxiv.org/abs/2402.01817v3].
- **ChinaTravel's negative result on iteration**: LLM-modulo refinement "decays" — models rectify ≤1 error/iteration after 3–5 rounds and small models introduce emergent errors; 10 refinement rounds produced statistically insignificant total error reduction [source: https://arxiv.org/html/2412.13682]. This is direct evidence that *unbounded self-refine loops are a trap*, an important design constraint for any product.

### 2.3 Neuro-symbolic: LLM translates, solver decides — the 2024-2026 pattern with the strongest documented numbers

This is the architecture with the most impressive, reproducible benchmark evidence:

- **To the Globe / TTG (EMNLP 2024 Demo, Google DeepMind-side team + collaborators)**: fine-tuned LLM translates NL request → symbolic MILP instance; solver returns guaranteed itinerary. Reported: **~5s end-to-end**, NL→symbolic backtranslation **~91% exact-match**, returned-itinerary cost ratio **0.979 vs the optimal ground-truth**, NPS 35–40 in user testing [source: https://aclanthology.org/2024.emnlp-demo.25/].
- **Formal verification for search (NAACL 2025)**: LLM writes code for an **SMT/Z3 solver**; on TravelPlanner it achieved **93.9% success** (vs 10% for o1-preview alone), generalizes to unseen constraints, and can repair **81.6–91.7%** of unsatisfiable queries using unsat-cores, with per-personalized modification suggestions [source: https://aclanthology.org/2025.naacl-long.176.pdf].
- **ChinaTravel benchmark (2024-25)**: neuro-symbolic planning hit **37.0% constraint satisfaction on human-authored Chinese travel queries — a 10× improvement** over purely neural agents (ReAct-based); pure neural methods on this benchmark also ran up $2.4/query with GPT-4o and produced no constraint-satisfying plans [source: https://arxiv.org/html/2412.13682]. Note also its caution about TTG-style MILP at scale: constraint counts scale cubically with POI count; ~600k constraints for a 2-day/22-POI/24-slot instance; the authors had to subsample POIs.
- **ItiNera (2024-25, deployed)**: five-stage LLM-assisted pipeline (user POI DB construction, request decomposition, preference-aware retrieval, cluster-aware spatial optimization via hierarchical TSP, LLM itinerary generation). Reports **~30% improvement over the best baseline on rule-based metrics**, itineraries only ~100 m/POI longer than the pure TSP-solved path, and being the only method to beat GPT-4 CoT in LLM-judged "Match." This is an explicit *hybrid* (LLM semantics + TSP/space optimization), deployed on a real dataset [source: https://arxiv.org/html/2402.07204v5].
- **LAPPI (2025)**: interactive "problem instantiation" — the LLM converts vague NL into an OP instance (preference scores, visit durations via LLM; travel times via Google Maps Distance Matrix; Gurobi solves). In a user study, LAPPI's routes matched time constraints better than baseline tools or heavy prompt-engineering approaches [source: https://arxiv.org/html/2512.14138]. *Single source, arXiv-only, but the pattern matches TTG/FormalVerify.*

### 2.4 Tool-use agent loops and multi-agent orchestrators (2025-2026) — best-in-class *pure-LLM* results, but half of what the solver baselines achieve

- **ATLAS (ICLR 2026, Google DeepMind)**: five agents (Search, Constraint Manager, Planner, Checker, Search Advisor) with a plan-verify-revise loop and *interleaved search* when a plan is unsatisfiable. On TravelPlanner it reached **44.4% final pass rate** (vs 23.3% next-best); in a live-web multi-turn setting, **84%** versus ReAct 59% and monolithic agent 27% [source: https://arxiv.org/html/2509.25586; 2-src: OpenReview https://openreview.net/forum?id=mIYGiBf9Pm]. Critically, ablations show the gain is the *external checker + constraint manager*, not cleverer prompts [source: https://en.papernotes.org/ICLR2026/multi_agent/atlas_constraints-aware_multi-agent_collaboration_for_real-world_travel_planning/].
- **HiMAP-Travel, TriFlow, Behavior Forest (2025-2026 arXiv)**: hierarchical day-level parallel executors with global budget state (Qwen3-8B, 52.8% TravelPlanner FPR, +17.7pp over ATLAS, 2.5× latency cut through parallelization) [source: https://arxiv.org/html/2603.04750v1]; progressive retrieval→planning→governance (91.1% FPR, 22.6s vs 245.7s for FormalVerify, "10.9× faster") [source: https://arxiv.org/html/2512.11271]; constraint-decoupled parallel behavior trees (+6.67pp over prior SOTA on TravelPlanner) [source: https://arxiv.org/html/2604.21354]. **All three are single-source arXiv preprints**; treat the specific numbers as unverified, but the *trend* (structured constraint decoupling + external validation) is corroborated by ATLAS (peer-reviewed) and the OR literature.
- **The COST reality of agent loops**: a U. Twente master's thesis measured a planner-executor agent at **177,560 tokens/query (1.99× a single ReAct agent's 89,013)** for a mere +5.2pp commonsense-macro gain and no improvement on final pass rate; single agents were 1.9–2.5× more token-efficient per unit of constraint satisfaction, and on 7-day trips the multi-agent architecture was *both* less accurate and ~2× as expensive [source: https://essay.utwente.nl/essays/111014]. This is a guarded, compute-matched empirical result — and it is the only compute-controlled comparison of multi-agent vs single-agent found in this survey. **Single source (thesis) but unusually rigorous; flag as medium-weak.**

### 2.5 RL-trained planning agents (2025) — the genuinely new thing, but exactly one production deployment found

- **DeepTravel (arXiv 2025, DiDi)**: end-to-end agentic RL for a travel-planning agent — cached tool sandbox, hierarchical reward verifiers (trajectory-level spatiotemporal feasibility + turn-level consistency with tool responses), failure-replay RL. Claims Qwen3-32B **beats OpenAI o1/o3 and DeepSeek-R1** on offline evaluation, and, critically, a **3-month online deployment in DiDi Enterprise Solutions App at ~82% itinerary-generation accuracy** [source: https://arxiv.org/html/2509.21842v2]. Of all "RL for itinerary" claims this is the only one with both a real deployment and an online number. Single-source arXiv + vendor-adjacent; the deployment claim is not independently audited. **Flag: weak-medium, but production evidence exists.**
- HiMAP-Travel also trains a single GRPO policy for all agents (see §2.4) — same idea, academic-only.
- There is also broader agentic-tool RL work (TripScore, ToolRL) referenced as pushing feasibility/consistency via reward signals [source: https://arxiv.org/html/2512.22673v2], but no production number.

### 2.6 Grounded retrieval / RAG over POI graphs

- TravelBench formalizes the tool environment (10 real travel tools incl. POI search, routing, flight/train search, weather, with a cached ~200k tool-response sandbox; 1,100 queries incl. 100 provably infeasible) — the first benchmark that explicitly tests "ask the user when under-specified" and "admit infeasibility" [source: https://arxiv.org/html/2512.22673v2]. Single-source preprint; but the *pattern* (grounded POI/route APIs + cached tool outputs as the factual substrate) is exactly what ItiNera, TravelPlanner's sandbox, ATLAS' live search, and every serious commercial tool independently converge on.
- **COMPASS (2025)**: constrained-optimization view; frontier agents reach **70–90% feasibility but only 20–60% optimality**; tool-call errors are <1% (tool use is NOT the bottleneck); the gap is *insufficient search-space exploration*, and "more information gathering strongly correlates with success" [source: https://arxiv.org/html/2510.07043v2]. This reframes the whole field: the empirical bottleneck is budgeted exploration of options, not LLM tool-calling accuracy.

---

## 3. Reinforcement learning / learned-reward approaches: where is RL *actually* used?

The honest finding: **RL is used in production for routing and retrieval, and is nearly absent from production itinerary *scheduling*.**

- **Google Maps Inverse RL (ICLR 2024)**: planetary-scale IRL over a 200M-state road MDP from 110M driving demonstrations; **+15.9% route accuracy (driving) and +24.1% (two-wheelers)** over ETA+penalties at ~1.4 GPU-years of training. This is RL'ing the *reward function* of routing, and it is the largest published real-world IRL study [source: https://proceedings.iclr.cc/paper_files/paper/2024/file/b917f916e7eed84ffe8f5e63492b2be8-Paper-Conference.pdf]. It is *not* itinerary generation.
- **Airbnb location retrieval (arXiv 2024)**: retrieval area crafted via heuristics → statistics → ML → **contextual multi-armed-bandit RL**; cumulative **+2.66% uncancelled bookers** across iterations (ML alone +1.8%, RL +0.51% more). Serves 100% of production traffic [source: https://arxiv.org/html/2408.13399]. Again: *retrieval bound*, not itinerary ordering.
- **Academic DRL for itineraries exists but is not production**: DQN for sustainable itinerary recommendation on Verona check-in data (reduces crowding, beats distance/popularity baselines) [source: https://link.springer.com/article/10.1007/s40558-024-00288-x]; GNN+RL personalized itinerary generation with user-generated images (IEEE ICDACAI 2024; reports accuracy 0.85 / satisfaction 4.6 — a single-conference claim with small-scale data) [source: https://ieeexplore.ieee.org/document/10835428/].
- **Agentic RL for tool-using travel agents** (DeepTravel, TripScore, ToolRL) is the 2025 emergence — see §2.5. The evidence so far: it works to *train a tool-agent policy*, published for exactly one product (DiDi).

**Landscape takeaway for RL**: there is no documented production system that *learns* the day-scheduling policy end-to-end. Learned components that do exist in production are (a) routing rewards, (b) retrieval/expansion decisions, (c) candidate scoring/ranking, and (d) reward models used as *evaluators* (TripTailor's approach). The scheduling itself remains constraint-solving code.

---

## 4. End-to-end learned vs hybrid: what the evidence says

This is the single most decision-relevant finding, and the evidence is one-directional:

1. **Every benchmark that pits pure-LLM against LLM+solver finds the hybrid wins by a wide margin.** TravelPlanner pure agents ≈0.6% → solver-backed (FormalVerify) 93.9% [§2.1/§2.3]; ChinaTravel pure neural ≈no FPR → NeSy 37% FPR [§2.3]; TTG ~91% symbolic-match + near-optimal cost [§2.3]; ATLAS' live-Web 84% only with a checker+search advisor [§2.4].
2. **The industry's own engineering posts say the same thing, and two of them are the strongest first-party evidence in the whole survey:**
   - **Google "Optimizing LLM-based trip planning" (Google AI trip ideas feature, live product)**: LLM proposes an initial plan tuned for soft preferences; then (i) ground with live opening-hours/travel-time data + substitute POIs from search backends, (ii) per-day exhaustive/DP enumeration of activity subsets scored by *similarity-to-LLM-plan + feasibility*, (iii) a set-packing-style local search across days (NP-complete, solved heuristically to stay near the LLM draft). This is the documented production embodiment of "LLM for meaning, algorithm for feasibility" [source: https://research.google/blog/optimizing-llm-based-trip-planning/]. **2-src**: the same technique family appears in TTG (EMNLP) [§2.3].
   - **Tripadvisor's "Cracking the code to the AI travel planner" (2025)**: the 2023 launch used ChatGPT for recommendations + review-based ranking. After a year, they **removed the LLM from the recommendation-formation step entirely**, replacing it with a recommender model that scores their millions of reviews against traveler inputs; this cut latency **~40s → ~6.5s**, raised **recommendation perceived quality +30%, doubled save-rate, +10% customer satisfaction**. In the same post they note the industry pattern is "quiz/chat → AI recommendations → day-by-day itinerary" [source: https://medium.com/tripadvisor/cracking-the-code-to-the-ai-travel-planner-27d8d0f222c8]. This is the strongest documented counter-example to "more LLM = better."
   - Tripadvisor's **AI assistant** (2025) is likewise grounded in "hundreds of millions of reviews," with a proprietary recommendation engine and AI summaries; engagement "4×" vs other AI products, revenue-per-user "~4×" [source: https://medium.com/tripadvisor/meet-the-tripadvisor-ai-assistant-244d4f6eba28]. **Single first-party source** for the metric multipliers — flag as unverifiable exact numbers, but the *architecture direction* (thin LLM, ground in own data) is corroborated independently.
3. **The "LLM-as-translator + solver" pattern is ported directly into production consulting work**: Unki's itinerary engine is a **time-dependent TOPTW solved with a Gurobi branch-and-cut pipeline** (presolve → LP bound → insertion warm start → branch-and-cut), benchmarked on Geneva/Paris/London/Lausanne (73–84 POIs): heuristic warm-start in seconds, certified ≤10% gap in ~1 minute for 3-day trips [source: https://www.haeringsolutions.ch/projects/unki-urban-tour-optimization]. Single-vendor engineering blog (**weak**), but structurally identical to the academic exact/hybrid recipe in §1 and the Google/TTG pattern — and it names the real production cost driver: the **P×P travel-time matrix from the Distance Matrix API dominates wall-clock** (~18 minutes for 80 POIs), a data-pipeline concern that no paper discusses but every product hits.

**Careful counter-reading (so we don't overclaim the hybrid):** the compute-controlled planner-executor thesis (§2.4) shows multi-agent *LLM* orchestrators can be pure token-burn. The hybrid's edge is specifically *solver + verifier*, not "more agents." And COMPASS (§2.6) shows that even for the LLM's slice (option discovery), the gap vs optimality is exploration, i.e., a *search* problem — which is precisely where a combinatorial engine helps. The evidence coheres: **semantics are the LLM's; feasibility and optimality are a solver's; the interface is a structured intermediate (JSON schema / DSL / MILP/SMT instance).**

---

## 5. Evaluation & benchmarks: how "quality" is actually measured

There is **no single standard benchmark**, but there is now a *measured family*, and it tells you how to evaluate any replacement architecture honesty:

**OR-side (mature, 30+ years):** TOPTW/OPTW instance reuse (Tsiligirides 1984; Righini-Salani; Montemanni-Gambardella; Solomon/Cordeau-derived), with best-known-solution tables as the metric [source: https://lirias.kuleuven.be/retrieve/aadfdff0-9a97-4668-b188-6982ed5f138b/; https://github.com/abmoya/TTDP_VNS]. Metric = collected score vs best-known under time-window feasibility.

**LLM-era benchmarks (2024-2026), each measuring a different thing:**
| Benchmark | Data | What it measures | Headline finding |
|---|---|---|---|
| TravelPlanner (ICML'24) | 1,225 synthetic-but-verified U.S. queries, 4M sandbox records | Delivery + common-sense macro/micro + hard-constraint macro/micro pass rates | GPT-4 0.6% final pass [380.proceedings.mlr.press/v235/xie24j.html] |
| Natural Plan (2024) | NL trip/meeting/calendar with real tool context | Solve rate with full info in context | ≤35% best; <5% at 10 cities [arxiv.org/html/2406.04520v1] |
| ChinaTravel (2024-25) | 1,154 human Chinese queries + 1,000 test | DSL-checkable feasibility, constraint satisfaction, preference | NeSy 37% FPR vs ~0 neural [arxiv.org/html/2412.13682] |
| TripTailor (ACL'25) | 500k real POIs, ~4k real itineraries, 40 CN cities | Feasibility + rationality (route ratio, duplicates, durations) + personalization (LLM-judge + reward model) | <10% human-level; 21.5% feasible+rational for best LLM [aclanthology.org/2025.findings-acl.503/] |
| TripCraft (ACL'25) | 1,000 queries, 140 U.S. cities, 3/5/7-day, 25 annotators | **5 continuous metrics**: Temporal Meal Score, Temporal Attraction Score, Spatial Score, Ordering Score, Persona Score | parameter-informed prompting lifts Temporal Meal 61→80% (7-day) [aclanthology.org/2025.acl-long.834.pdf] |
| TravelBench (2025) | 1,100 real queries + 200k cached tool responses | Single/multi-turn + infeasibility handling + tool use | — [arxiv.org/html/2512.22673v2] |
| Flex-TravelPlanner (ICLR'25 WS) | TravelPlanner-derived | Dynamic/multi-turn constraint change + prioritization | models mis-prioritize newly-added low-priority constraints [arxiv.org/html/2506.04649] |
| COMPASS (2025) | 281 facade tasks, LLM user-simulator | Constrained optimization: feasibility vs optimality | 70–90% feasible, 20–60% optimal [arxiv.org/html/2510.07043v2] |

**Critical, well-documented limitations of these benchmarks (do not over-trust any single number):**
- TravelPlanner's own authors note **constraint-pass rates exclude "within-sandbox" and "no-missed-information" failures** — i.e., headline pass rates are measured on a "good enough" subset [source: https://github.com/OSU-NLP-Group/TravelPlanner]. TripCraft explicitly documents TravelPlanner inconsistencies (accommodations assigned across 312 cities; semi-synthetic data) [source: https://aclanthology.org/2025.acl-long.834.pdf].
- **LLM-as-judge is known-positional-bias-prone**; TripTailor mitigates (two judges, swapped positions) but cannot eliminate [source: https://aclanthology.org/2025.findings-acl.503.pdf]. Reward-model judges are themselves fine-tuned on LLM-generated data — circularity risk.
- "Pass rate" is a *binary feasibility* metric; TripCraft/TripTailor exist precisely because it misses rationality/personalization/routing efficiency [§5 table].
- **There is no standard cost/latency-aware benchmark**, yet §2.4/§6 show cost is where architectures actually get rejected in production. TREK (2026) is the first to add a deterministic *efficiency* axis (tool-call count vs oracle minimum), token budgets, and a no-judge evaluator; its sober headline: **best agent fully feasible on 46.2% of solvable tasks, median 6.6%; neither "reasoning" models nor more tokens closed the gap** [source: https://arxiv.org/html/2607.26977]. Single-source 2026 preprint — flag as unverified, but it is the direction of travel.

---

## 6. Commercial implementations, categorized (claim vs proven)

Pattern categories observed across ~10 products (detailed engineering is rare; most disclose *what* and not *how*):

| Product | Disclosed architecture | Evidence grade | Notes / the actual pattern claimed |
|---|---|---|---|
| **Google AI trip ideas** | LLM proposes → grounding (live hours/travel) → per-day DP/enumeration + set-packing local search | **Strong** (first-party engineering blog; live product) | The canonical documented hybrid; substitutes fetched from search backends; §4 [research.google blog] |
| **Tripadvisor Trips / AI Trip Builder + AI assistant** | v1: ChatGPT recs + rating ranking; v2 (Aug 2024): removed LLM from rec formation, own review-based recommender; suppressed day-by-day default UX | **Strong** (first-party; independent Q3-2023 reporting on itinerary revenue 3×, save-rate 2×, +10% satisfaction) | The strongest published "de-LLM-ify" case; latency 40→6.5s [medium.com/tripadvisor/...; phocuswire 2023; phocuswire 2025] |
| **TTG / "To the Globe"** | Fine-tuned LLM → MILP → optimal itinerary | **Strong** (EMNLP demo; reproducible synthetic-data pipeline) | Academic+product-hybrid demo, ~5s, NPS 35-40 (§2.3) |
| **Expedia Romie** | OpenAI + in-house models; group-chat planning; proactive disruption handling | **Weak-medium** (press + first-party PR; no algorithm disclosure) | Conversational orchestration + booking; no documentable itinerary-solver [expedia.com newsroom; techcrunch 2024-05-14] |
| **Mindtrip** | OpenAI conversation layer + proprietary travel knowledge base (6.5M+ places), itinerary assembly w/ live availability; "memory" across sessions | **Medium-weak** (FAQ/TechCrunch/Axios first-party+press for KPIs; vendor case-studies (Pinnasys/AGIX) describe intent-graph, clarification ranking, constraint-assembly and cross-session memory — **marketing, unverifiable**) | Architecture *described* resembles staged pipeline (intent capture → clarify → assemble → refine), i.e., a thin-LLM hybrid, but no numbers on iteration quality; "10× retention" claims are vendor PR [pinnasys.com/case-studies/mindtrip; agixtech.com/case-studies/mindtrip; techcrunch.com/2024/07/31/...] |
| **Layla / Roam Around** | Pure OpenAI (initially text-davinci-003, then GPT-3.5/4) + POI APIs; affiliate monetization on Viator/Kayak | **Medium** (founder interview in Indie Hackers + TechCrunch/PhocusWire M&A coverage, 2-src on 10M itineraries) | The clearest "thin wrapper" at scale: 10M itineraries, $300k gross bookings in 90 days, **$35k/mo burn on davinci → 10× cheaper after gpt-3.5-turbo**, 45s→fast latency work, Edge functions for 90% Vercel cost cut [indiehackers.com/post/...; techcrunch.com/2024/02/12/...]. Proof that pure-LLM *can* ship unit economics when model cost drops — and that it monetizes via OTA affiliate links, not itinerary quality. |
| **Wanderlog** | User-assembled itinerary + per-day "optimize route" (start/end chosen, auto-reorder); AI assistant added; Google Photos/Maps data | **Weak-medium** (product help docs + app listing; no algorithm disclosure) | Its documented differentiator is *editing + route optimization of user-picked places*, NOT free-text generation to a solved itinerary — a strong signal for the "human-in-the-loop + TSP-level optimization" pattern [help.wanderlog.com; play.google.com/store/apps/...] |
| **OpenAI Operator + ChatGPT apps w/ Expedia/Booking/Tripadvisor** | Computer-use web agent; third-party MCP-connected itinerary apps | **Weak-medium** (press) | Points to the 2026 *agentic-commerce* direction (chat → select → book → pay) more than itinerary scheduling [phocuswire.com/openai-operator-web-agent; phocuswire.com/openai-chatgpt-apps-expedia-booking-tripadvisor] |
| **Sabre+PayPal+Mindtrip (announced Feb 2026)** | End-to-end agentic booking (flights first, hotels later) | **Weak** (PR) | A signal about where agentic travel is headed commercially, not an algorithm [investors.sabre.com news release] |
| **DiDi Enterprise Solutions (DeepTravel)** | RL-trained tool-agent for itinerary generation, deployed 3 months, ~82% online accuracy | **Weak-medium** (single arXiv + vendor-adjacent; but real deployment) | Only production RL-for-itinerary claim found [arxiv.org/html/2509.21842v2] |
| **Unki** | TDTOP MILP (Gurobi branch-and-cut) + Google Places/DistanceMatrix ingestion | **Weak** (single vendor blog) but structurally coherent | Production O.R. recipe: ~10% gap in ~1min for 3-day trips; travel-time matrix is the wall-clock bottleneck [haeringsolutions.ch/...] |

**"AI travel" hype inventory (things that look like AI but are not itinerary algorithms):** OpenAI-devday demos (Mindtrip), computer-use agents (Operator), chatbot wrappers over affiliate feeds (Roam Around/Layla), review-summary generators. All are thin LLM appendages over a data/logistics business. The only products that document *scheduling* machinery are Google, Unki, TTG (research-adjacent), and DiDi's DeepTravel.

---

## 7. Trend trajectory: what is genuinely new in 2024-2026 that a 2023 system wouldn't have

Caveat: much of this is preprint-grade, none of it is baked-in 1.0 standard. But as a landscape:

1. **Staged/regulated pipelines replaced single-shot** (verified). Both Google and Tripadvisor shipped full pipelines (LLM→optimizer; recommender→planner) in production, and ATLAS (peer-reviewed) formalized plan-verify-revise + interleaved search.
2. **Constraint as a first-class object, not a prompt requirement.** Constraint Managers (ATLAS), explicit hard/soft constraint extraction (TravelPlanner categories), DSL-based auditability (ChinaTravel), unsat-core explanation (FormalVerify), infeasibility-first UX (TravelBench) — 2023-era "few-shot JSON itinerary" predates all of these.
3. **Tool-use / grounded POI fetching became the substrate**: live search backends (Google), cached tool sandboxes (TravelPlanner/DeepTravel/TravelBench), Distance-Matrix grounded travel times (ItiNera/LAPPI/Google/Unki). It's now universal because hallucinated POIs are the #1 documented failure (ItiNera's own motivation; Tripadvisor restructuring around reviews).
4. **Small-model orchestrators** (documented at DiDi pushing Qwen3-32B past frontier models with RL; HiMAP's Qwen3-8B; TripTailor fine-tunes Qwen2.5-1.5B as reward-judge) — the "you don't need GPT-4 for the whole loop" claim now has a production data point (DiDi).
5. **RL over agent trajectories** (DeepTravel; TripScore; HiMAP's GRPO policy) — genuinely new class, one production deployment, heavy compute.
6. **Memory/chit-chat persistence** exists (Mindtrip's cross-session preference memory, Expedia Romie learning "progressive", ATLAS domain-cache reuse across turns) but *none* of it is Mem0-style product "memory": it is profile persistence or search-result caching. The Mem0/short-term-memory framing is **not evidenced anywhere in this survey as load-bearing for itinerary quality**.
7. **Costs collapsed** (model-price drops from 2023) *and* agent overhead exploded (tokens/query tables in §2.4); the survivable architecture is exactly the one that minimizes LLM calls (Google/TTG/OpenSymbolicAI optimize for 2–3 structured calls + deterministic verify, vs 10–40 calls in naive ReAct/CrewAI-style loops) [source: https://www.opensymbolic.ai/blog/travelplanner-benchmark — **vendor blog, weak anchor only, but its 2.3-call/13.9k-token/$0.013-per-passing-task contrast with 13.5-call/43.8k/$0.051 (LangChain-style) and 39.6-call/81.3k/$0.10 (CrewAI-style) is directionally corroborated by the U. Twente token data**].

---

## 8. Cost & latency reality (the constraint most white papers ignore)

Every architecture decision here is gated by unit economics. Documented anchors, low→high trust:

- **Latency expectations**: TTG ~5s end-to-end (solver inclusive) [EMNLP]. Tripadvisor 40→6.5s after de-LLMing (first-party). Roam Around's original 45s caused "really high bounce rates" (founder). DeepTravel/DiDi online at consumer scale implies seconds-class, but no number published.
- **Token/economics**: single-shot consumption 7→10k tokens/query (OpenSymbolicAI) up to 178k (planner-executor) [Twente thesis]; TravelPlanner-era GPT-4o pure-agent ~$2.4/query in ChinaTravel measurements; LLM cost accounts for ~15–20% of inference bill in a hybrid at scale — **POI/map API costs (Places/Distance Matrix) dominate**, estimable at $3k–6k/mo for ~5k active users before caching [TeaCode, weak single blog, directionally corroborated by Unki's P×P matrix timing and Google's own caching-based design]. Google Maps IRL required **1.4 GPU-years** for a routing reward [ICLR'24]. **These numbers are the practical veto: an itinerary engine that needs 30–40 LLM calls + unbounded refine loops is not a product at Vietnamese-market margins.**

---

## 9. Severity-coded synthesis for ai_travel

Decisions implied by the empirical landscape (severity = how hard the evidence constrains the choice):

- **Blocker — do not ship a "single-shot LLM writes the full itinerary" engine.** Every benchmark and both first-party production posts demonstrate sub-par feasibility (<1–35% in structured tests; Tripadvisor's own v1 was the cautionary tale their v2 fixed). [§2.1, §4]
- **High — the LLM's demonstrated, documented role is narrow**: translate intent → structured constraints, ground/select POIs against a real datasource, draft a plan the *solver/verifier* then fixes. This is TTG, Google, ItiNera, ATLAS, FormalVerify, ChinaTravel-NeSy in agreement. [§2.2–2.4, §4]
- **High — you need a deterministic feasibility layer and a verifier**, not self-reflection. "LLMs can't verification-themselves" + unsat-core repair is documented; unbounded refine loops demonstrably decay. [§2.2, §2.3]
- **Medium — pick your evaluation harness now**: there is no single standard; TravelPlanner-style pass rates overstate feasibility (subsetzed metrics); TripTailor/TripCraft-style continuous scores are the current best practice; add a cost/latency axis or you will be mis-led. [§5]
- **Medium — learned/RAG retrieval beats LLM recall for "what fits this traveler"** (Tripadvisor's recommender-over-reviews; COMPASS's exploration finding). LLM free-style POI recall is the #1 hallucination source. [§2.6, §4, §6]
- **Low-Note — RL/agency is real but not a foundation**: one production claim (DiDi), boundary conditions (need cached sandbox, evaluator verifiers, GPU budget). A 2026 ai_travel does not block on RL. [§3]
- **Note — memory/Mem0 and multi-agent chatter are the most over-sold "new" things**: memory-in-products is preference persistence (useful UX, not algorithm); multi-agent adds 1.5–2× tokens for marginal gains absent a checker. [§2.4, §7]
- **Note — the hidden 80% is data engineering**: POI freshness, opening-hour changes, real travel-time matrices (P×P Distance Matrix is minutes, not ms), caching policies — this, not the model, is where Google, Tripadvisor, and Unki all spent their production effort. [§4, §8]

---

## 10. Executive summary (250 words)

Across 2020–2026 the empirical record draws a remarkably consistent line. Operations research owns the scheduling core: the Tourist Trip Design Problem and its Orienteering/TOPTW family are still solved by local-search metaheuristics (ILS/VNS/SA) with exact solvers used to certify near-optimality on demand; nothing learned has displaced them on benchmarks. The 2024–2026 LLM wave did not replace that core — it added a semantics layer. Every system with strong documented numbers — Google's shipped AI trip ideas, TTG, FormalVerify/Z3, ChinaTravel's neuro-symbolic agent, ItiNera, ATLAS — pairs an LLM that understands intent and names POIs with deterministic code that enforces time-windows, budgets, meals, and routes. Pure-LLM planning is empirically a failure mode: 0.6% success (TravelPlanner), <35% with all facts supplied (Natural Plan), <10% human-level (TripTailor). The strongest first-party production evidence is Tripadvisor removing the LLM from recommendation formation (latency 40→6.5s, perceived quality +30%), and Google keeping only the "suggest plan + score similarity" role for the LLM. RL is real but peripheral: production RL exists for routing rewards (Google Maps) and retrieval (Airbnb), and exactly one itinerary agent (DiDi/DeepTravel). Honestly: most "AI travel" products are wrappers over affiliate feed and chat; the ones that matter all converge on the same thin-LLM-plus-constraint-engine hybrid. Implementation risk now lives in data grounding and evaluation discipline (feasibility ≠ rationality; add cost/latency axes), not in choosing "an architecture."

---

## 11. Top 5 most significant findings

1. **Pure-LLM itinerary planning fails empirically; hybrid always wins when measured.** TravelPlanner 0.6% (GPT-4, ICML'24), Natural Plan ≤34.8% with full context, –→ solver-backed systems at 84–94% (ATLAS live-web; FormalVerify 93.9%). Consistency across four independent benchmark families (2-src+ per number). [§2.1, §2.3, §4]
2. **The strongest first-party production evidence is anti-LLM-central: Tripadvisor removed the LLM from recommendation formation** (latency 40→6.5s, perceived quality +30%, saves 2×) and **Google shipped the "LLM proposes, optimizer fixes" pattern** in a live feature. These are the two best-documented architecture decisions in commercial travel AI. [§4]
3. **The winning role for the LLM, everywhere, is translation/grounding, not scheduling**: NL→structured constraint (TTG 91% symbolic match; FormalVerify; ChinaTravel DSL; LAPPI), plus POI selection/reasoning — with deterministic code owning windows/budget/ordering. Feasibility-layer + external verifier beats self-reflection (LLM-Modulo 4.6×; unsat-corean repair 93.9%). [§2.3]
4. **Benchmarks now exist but none is standard and all are flattered by their own metrics** (TravelPlanner excludes within-sandbox failures; LLM-as-judge has positional bias; "feasibility ≠ rationality," route ratios 3–4× off in direct LLM plans). The field's newest direction adds continuous scores (TripCraft) and cost-efficiency axes (TREK), where the best agent still nails only 46% of solvable tasks. [§5]
5. **Cost/latency, not correctness, is the binding production constraint**: pure-agent GPT-4o ran ~$2.4/query; multi-agent orchestrators burn 1.5–2× tokens (178k vs 89k/query) for thin accuracy gains; hybrid pipelines cut LLM calls to 2–3 and move the bill to POI APIs (P×P Distance Matrix minutes per city). This makes LLM-minimalism, not "more AI," the observed survival pattern (Roam Around's $35k/mo davinci burn → gpt-3.5-turbo rescue; Tripadvisor's 6.5s). [§2.4, §6, §8]

---

## 12. Confidence rating and ground-truth tally

**Confidence: 7/10.**

Reasoning: the core directional conclusion (pure-LLM fails; hybrid with deterministic solver/verifier dominates) rests on multiple peer-reviewed benchmarks (TravelPlanner/ICML, Natural Plan/EACL-adjacent arXiv, TripTailor/ACL, ChinaTravel arXiv, ATLAS/ICLR) plus two mutually-corroborating first-party production posts (Google, Tripadvisor) — this is the most externally-verifiable claim in the survey, and I rate it ~8/10 on its own. What pulls the overall score to 7: (a) several SOTA numbers (HiMAP, TriFlow, Behavior Forest, TREK, DeepTravel) are single-source 2025–2026 preprints or vendor-adjacent and could not be independently confirmed; (b) nearly all commercial "architecture" disclosures (Mindtrip, Layla, Wanderlog, Expedia) are marketing-grade, so the *commercial* half of the landscape rests on weaker evidence than the academic half; (c) costs I quote as anchors (Roam $35k/mo, TeaCode API estimates, OpenSymbolicAI unit costs) are single-source and are presented only as order-of-magnitude, not fact; (d) the field is ~18 months old and moving monthly.

**Ground-truth tally: 8 of 12 load-bearing conclusions are externally verified** (multiple independent cited sources each):
- pure-LLM planning fails / hybrid wins (4 benchmark families + 2 production posts) — **2-src verified**
- LLM role = translation/grounding; feasibility in code (TTG+FormalVerify+ChinaTravel+ItiNera+Google+Tripadvisor) — **verified**
- self-verification inadequate; external verifiers needed (LLM-Modulo 2-paper + ChinaTravel decay result) — **verified**
- benchmarks are flattered / feasibility≠rationality (TripTailor + TripCraft + TravelPlanner self-documented exclusions) — **verified**
- OR-backbone fact pattern (OP/TOPTW heuristics dominate AND exact remains for small/verification) — **verified** (3 peer-reviewed surveys + multiple 2023–24 journal papers)
- RL not used for scheduling in production; used for routing/retrieval (Google Maps IRL + Airbnb papers) — **verified**
- Tripadvisor removal-of-LLM numbers (40→6.5s, +30%, 2×) — **single source (but first-party and internally coherent); NOT double-sourced → flagged**
- DiDi/DeepTravel production RL claim — **single source → flagged, unverified**
- Multi-agent token overhead (178k vs 89k, 1.9–2.5× inefficiency) — **single thesis → flagged, medium-weak**
- Mindtrip/Layla/Wanderlog/Expedia architecture specifics — **largely single-vendor/press → treated as claims**
- 2026 preprint SOTA numbers (HiMAP/TriFlow/Behavior Forest/TREK) — **single source → unverified**
- Cost anchors (Roam burn, API economics) — **single source → order-of-magnitude only**

The remaining 4 rely on single sources and are explicitly flagged in the text; none of them are load-bearing for the architecture recommendation (which rests entirely on the verified 8).