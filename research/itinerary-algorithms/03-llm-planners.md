# Lane 3 — LLM-as-Planner Architectures: Can an LLM Actually Build Feasible Itineraries, and With What Architecture?

**Deep-dive research, lane 3 of 6.** Scope: LLM-centric and LLM-hybrid planning architecture for an end-to-end automated travel itinerary generator (FastAPI backend, `planner.py`, deterministic heuristics today). Question: what is the state-of-the-art LLM-based planning architecture in 2024–2026, and does it beat the current heuristic approach **for this problem** (small catalogue of hundreds of POIs, ~10–40 candidates per plan, open hours, meal precedence windows, driving-matrix travel times, budget, weather, multi-day, deterministic-ish output, low latency)?

This file deliberately does **not** survey travel products (lane 4 does that) or combinatorial foundations (lane 2). It evaluates *architecture patterns and their evidence*.

---

## 0. Executive short-answer

The evidence is unusually clear for this domain, and it is not the answer that 2024–2025 LLM hype would suggest:

1. **A single LLM call cannot reliably schedule even 5–15 stops with multiple constraints.** On the three independent, objective travel-planning benchmarks released 2024–2025 (TravelPlanner, NATURAL PLAN, ChinaTravel), GPT-4-class and even o1-class models achieve **0.6%–10%** full-constraint success (see §1). These are *objective, rule-checked* benchmarks, not vibes. Frontier reasoning models (o1-preview) fix some arithmetic-style planning but introduce new hallucination (78% "within-sandbox" pass rate vs GPT-4o's 96.6% on TripTailor).
2. **The convergence is on "LLM-as-Translator," not "LLM-as-Planner":** LLM extracts/parses user intent and enumerates a *constrained structured specification* (JSON/DSL/PDDL/SMT/MILP); a **deterministic solver** (CP-SAT/OR-Tools, Fast Downward, SMT solver, or even the system's existing heuristic engine) finds the schedule; the LLM is used again for narrative/personalization. Published, independently-replicated numbers: **0.6% → 97%** on TravelPlanner via LLM+SMT (Hao et al.); TRIP-PAL's LLM→planner hybrid beats GPT-4 on utility and validity; ItiNera's LLM+spatial-optimization beats GPT-4 CoT by large margins in deployed human eval.
3. **Self-verification and critique loops improve things but cannot substitute for a closed-form verifier.** The peer-reviewed literature is blunt: LLMs cannot reliably self-correct reasoning without *external* feedback (Huang et al. ICLR'24; Tyen et al.; Stechly et al. ICLR'25). LLM→code→run→repair ("modulo" loops, Reflexion, PlanExecute) is the effective variant — closure on the LLM is only worthwhile when a **deterministic checker** gates repair.
4. **Grounding is non-negotiable and free enough:** tool/RAG access to a real POI graph (real names, real hours, real travel matrix) converts "plausible prose" into "checkable data" and is near-mandatory. It does **not** by itself fix constraint satisfaction (agents with tools still scored 0.6% on TravelPlanner).
5. **Orchestration frameworks are largely orthogonal to the hard problem.** LangGraph/CrewAI/Swarm/Claude Agent SDK add control-flow, checkpoints, parallelism — they do not add planning competence. For this catalogue size, a **thin deterministic pipeline** (1–3 LLM calls + solver) is the empirically higher-accuracy and lower-cost pattern. ReAct-style per-turn tool loops are the *worst* performers on benchmark (10–15 vs 2–3 LLM calls).

**Bottom line for `planner.py`:** keep the deterministic solver core; use the LLM to (a) parse/negotiate constraints, (b) select/rank real POIs against the real catalogue via structured retrieval, and (c) narrate. Do NOT hand the schedule itself to an LLM without a deterministic feasibility gate. That is both the evidence-supported SOTA and — unusually — also the cheaper, lower-latency answer.

---

## 1. Can a modern LLM alone schedule 10–15 stops with time windows?

### 1.1 The benchmarks (objective, rule-verifiable — not model-judged)

**TravelPlanner** (ICML'24, OSU NLP Group) — 1,225 multi-day domestic trips, ~4M records, tools provided, 8 commonsense + 5 hard constraint checks that are evaluated *deterministically*. **GPT-4 final-pass rate: 0.6%**; GPT-4-Turbo 4.4%; even with o1-class reasoning (o1-preview, given all needed info in-context), best reported ~10% [source: https://arxiv.org/abs/2402.01622] [source: https://ui.adsabs.harvard.edu/abs/2024arXiv240411891H/abstract].

**NATURAL PLAN** (Google, 2024) — full-information trip/meeting/calendar scheduling (tool outputs *already* in context, so tool-use is not the bottleneck). "Even advanced models like GPT-4 and Gemini 1.5 Pro achieve low success rates, dropping below 5% for complex, multi-city tasks" [source: https://www.emergentmind.com/papers/2406.04520] [source: https://arxiv.org/abs/2406.04520].

**PlanBench** (NeurIPS'23 + 2024 leaderboard) — classical planning (Blocksworld). Standard LLMs: GPT-4 34.6%, GPT-4o 35.5%, Claude-3.5-Sonnet 54.8%, Llama-3.1-405B 62.6%. Reasoning models (o1-preview) jump to 97.8% on *plain* Blocksworld but **collapse on obfuscated (Mystery) Blocksworld to 52.8%**, and DeepSeek-R1 to 43.3%; "LRM o1 suffers on problems requiring ≥20 steps and cannot reliably recognize unsolvable cases" [source: https://github.com/karthikv792/LLMs-Planning] [source: https://www.emergentmind.com/topics/planbench]. The pattern — big gain on familiar problems, brittleness on novel semantics and longer horizons — is the single most transferable lesson for travel.

**ChinaTravel** (NeurIPS'25; the harder successor) — real open-ended human queries, 6–12 constraints/query, DSL-validated. Pure LLM methods: **GPT-4o ≈ 0%**, others ~2.6%; even TemplatedToGoal (TTG, the SMT pipeline that sailed through TravelPlanner at 91.7%) collapses to **1.29%** on human-style language [source: https://arxiv.org/html/2412.13682v5] [source: https://nips.cc/virtual/2025/124537].

**TripTailor** (ACL Findings 2025) — 500k+ real POIs, ~4k real itineraries, real spatial data. Two findings bite: (i) reasoning model **o1-mini's "within-sandbox" pass rate was only 78%** vs GPT-4o's 96.6% — the model that reasons better *hallucinates information outside the provided sandbox* more; (ii) AI routes place consecutive POIs >17 km apart on average vs **7.3 km** for human plans — LLMs are spatially incoherent without an optimizer [source: https://arxiv.org/pdf/2508.01432] (numbers corroborated by third-party analysis in [source: https://perplexityaimagazine.com/ai-tools/best-ai-for-travel-planning]).

### 1.2 What this means for "n stops"

These benchmarks span exactly THIS problem's constraint set (budget, meal/time windows, transport, POI hours, multi-day). A defensible, evidence-based failure curve:

| Scale | Evidence-based success of pure LLM planning |
|---|---|
| 1–3 stops, ~1–2 constraints | High (LLMs fine; not really "planning") |
| 5–10 stops, 3–5 constraints (TravelPlanner medium) | ~single-digit % full-constraint (GPT-4 class) |
| 10–15 stops, 5+ constraints + open-hour/meal-precedence | ≈5–10% best case (o1-preview), 0% for non-reasoning frontier on ChinaTravel |
| Obfuscated/novel semantics, long horizon | Near-catastrophic degradation (PlanBench Mystery 52.8% best; ChinaTravel 0–2.6%) |

**Conclusions (High severity, benchmark-grade):**
- A single frontier LLM call is **not** a viable planner for 10–15 constrained stops. Failure is not "occasional typos"; it is wholesale constraint violations (budget, hours, precedence, spacing), which a correctness-gated system must treat as blocking.
- Capability is improving (o1/GPT-5-class clearly better than GPT-4) but the trend changes the *arithmetic*, not the *architecture*: reasoning models reduce some within-window slip-ups while adding confident hallucination of non-source data (TripTailor). They are better *parsers and proposers*, still unreliable *schedulers*.
- Two independent 2025 benchmarks (ChinaTravel, TripTailor) both conclude a single-pass LLM text generation is inadequate for long-horizon multi-constraint planning and that decomposition / symbolic scheduling is required. As TripTailor frames it: "pure LLMs ... tend to provide infeasible plans in travel planning."

---

## 2. Structured output / constrained decoding: the plumbing, and its limits

### 2.1 Reliability of JSON/function-call plumbing (2024–2026)

Structured output is the *building block* of any LLM+planner hybrid, and its engineering status is good but subtly limited:

- **OpenAI Structured Outputs** (`response_format` + strict JSON schema, GA Aug 2024): token-level constrained decoding, "100% schema adherence" per vendor internal evals [source: https://jsonic.io/guides/json-llm-output] (vendor claim — label hypothesis; independent practice treats it as real for *syntax*). Function-calling with `strict:true` gets the same guarantee.
- **Independent engineering data:** JSON mode alone (no schema) shows **~8–12% schema-violation rates**; strict function-calling/tool-use brings violations to **<0.3%** (GPT-4o/Claude-class), with **0.2–2.1%** residual across providers; nested schemas >3 levels fail "disproportionately"; and the hardest failure is **silent semantic drift** — valid JSON, wrong values, no error raised [source: https://www.kalviumlabs.ai/blog/structured-output-from-llms-json-mode-function-calling/].
- **BFCL v4** (Berkeley Function-Calling Leaderboard, ICML'25): frontier models are *near-perfect on single-turn calls*, but **holistic multi-turn/agentic accuracy is only ~53–77%** for the best models (Claude Opus 4.5 77.47%, GPT-5.2 55.87%, o4-mini 53.24%) [source: https://evals.report/benchmarks/bfcl] [source: https://proceedings.mlr.press/v267/patil25a.html]. Tool-calling as a *loop* is where it degrades — not a single call.

### 2.2 What this means for the travel pipeline

- **Constraint to use strict structured outputs everywhere** an LLM emits machine-readable structures (parsed user requirements, POI pick-list, itinerary JSON). Do not parse free text. With strict mode + client-side validation + a bounded retry, plumbing failures become Low severity.
- **The residue that matters is semantic, not syntactic.** The LLM will return schema-valid itineraries whose windows overlap or whose budget arithmetic is wrong. Structured output fixes the envelope only; it cannot guarantee the *content* satisfies constraints. That is exactly why the architecture must add a deterministic checker regardless of how good structured output becomes (section 4).
- **Do not over-nest.** Keep the emitted spec shallow (enum fields, ID references) — deep nested schemas raise error rates and first-call compile latency (5–10 s cold-start on complex schemas [source: https://www.aiwisdom.dev/articles/prompt-engineering/structured-outputs-from-llms]).

---

## 3. Grounding: tool-use / RAG over a real POI graph (near-mandatory)

### 3.1 The problem it solves: hallucinated entities and numbers

Without a real catalogue, LLMs generate plausible-but-fake POIs, wrong hours, and imaginary prices. Evidence:

- **ItiNera** (EMNLP'24 Industry, deployed system) states it directly: "*Pure LLMs cannot refer to specific POI lists, resulting in outdated or hallucinated POIs*," and "LLM-generated itineraries can be circuitous, lack detail, and include impractical information." Their fix is a **User-owned POI Database** + embedding-based POI retrieval (UPC/PPR modules) before any planning [source: https://aclanthology.org/2024.emnlp-industry.104.pdf] [source: https://arxiv.org/html/2402.07204v5].
- **TripTailor** measured o1-mini "information confusion" and "fabrication of information" (78% within-sandbox) [source: https://arxiv.org/pdf/2508.01432].
- Hallucination *floor* for frontier models even on benign grounding tasks (summarization of a provided doc): **~10%** factual-consistency error (Vectara leaderboard, incl. GPT-4o 9.6%, GPT-5.2 10.8%) [source: https://github.com/vectara/hallucination-leaderboard]. On travel knowledge it is expected to be worse (knowledge cutoffs, closed POIs). Third-party meta-reviews quote "90% of AI-generated itineraries contain at least one error," mostly non-existent businesses, wrong hours, stale pricing [source: https://www.travelanywhere.blog/blog/chatgpt-vs-gemini-vs-claude-trip-planning-2026-tested-comparison] (secondary/aggregate — treat as directional).

### 3.2 The pattern and the nuance

The canonical pattern: **LLM never emits a POI name or a travel time.** It either (a) calls a tool `search_pois(query, lat, lon, when) → [ids]` and later emits **catalogue IDs**, or (b) is given a pre-ranked candidate list (10–40 items, exactly this system's scale) and constrained to pick IDs. Hours, prices, geopositions, and the driving matrix come from the database, not from the model. TravelPlanner's sandbox exists precisely to force this; but notice the crucial nuance in the data:

> Tool-use grounding fixed *hallucination*, but agents *with* tools still got **0.6%** on TravelPlanner. Grounding is necessary, not sufficient — it removes the fake-data failure mode, but constraint satisfaction (scheduling) is a separate failure mode that tools do not fix [source: https://ryanorban.com/notes/travelplanner-llm-benchmark].

So the design implication for this system is precise: **ground the LLM to the POI catalogue (as it partly does today with place-name selection), and relocate feasibility out of the LLM.** The LLM is a *selector/ranker over real data*, not a *creator of data*. "Creator of data" is where the ~10%+ residual hallucination lives.

**Severity: High (both directions).** Forgetting grounding → fabricated itineraries (High). Grounding alone without feasibility → still-0.6% itineraries (High). Both must be present.

---

## 4. Self-verification / plan-then-verify / avoid-if-possible loops

### 4.1 Can the LLM verify its own plan? Evidence says no (without external feedback)

The self-correction literature is unambiguous and has converged across independent groups:

- **Huang et al., ICLR'24** ("Large Language Models Cannot Self-Correct Reasoning Yet," Google DeepMind): intrinsic self-correction (no external feedback) *degrades* accuracy on GSM8K/CommonsenseQA/HotpotQA [source: https://arxiv.org/abs/2310.01798].
- **Tyen et al., ACL Findings'24** ("LLMs cannot find reasoning errors, but can correct them given the error location," Google): LLMs systematically fail at *locating* the error; they are surprisingly good at fixing a mistake **once told exactly where it is**. This is the single most actionable finding for repair-loop design [source: https://aclanthology.org/2024.findings-acl.826/].
- **Stechly et al., ICLR'25** ("On the Self-Verification Limitations of LLMs on Reasoning and Planning Tasks," Kambhampati group): trained-on-the-same-task LLMs *overconfirm* their own invalid plans — self-verification is worse than unskilled [source: https://arxiv.org/html/2604.22273v1 reference list].
- **Kambhampati et al., ICML'24 Position** ("LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks"): auto-regressive LLMs cannot by themselves do planning *or self-verification*; the fix is an **external model-based verifier** in a tighter loop [source: https://proceedings.mlr.press/v235/kambhampati24a.html].
- Correct-on-prompted evidence: CRITIC (ICLR'24) shows tool-interactive critiquing (external feedback) works where pure self-critique fails [reference in https://arxiv.org/html/2310.01798v2]; DISC (2026) shows gains only when a *stronger* model verifies/judges a weaker generator's output [source: https://www.alphaxiv.org/abs/2606.21724v1].

### 4.2 The workable variants: external verifier gates

Three externally-verified loop architectures, in order of evidence strength:

**(a) LLM-Modulo (propose → external critic/verifier → repair).** Kambhampati et al.; travel case study Gundawar et al. 2024: an LLM proposes plans; a suite of deterministic + LLM critics (budget, time, commonsense) check; violated plans are repaired via back-prompting. TravelPlanner final-pass **~17.5→20.6%** (peer-replicated by TripTailor/ChinaTravel cites; ChinaTravel's own run of LLM-Modulo reports 25.55% with MLP/DeepSeek-V3) — a real improvement over 0.6%, but **far from reliable** [source: https://arxiv.org/abs/2405.20625] [source: https://arxiv.org/html/2412.13682v5 Table 14].
**(b) LLM→code/spec→deterministic solver→run results back.** The 97% pattern (§6). Here the "verifier" is a sound solver; LLM involvement shrinks to formulation, which is precisely where LLMs are reliable.
**(c) Plan-then-execute (PlanExecute-style).** LLM sketches a high-level plan; tools execute; on failure, only the failing sub-part is repaired. Good for *environmental* errors, weak for *logical* constraint errors [source: https://ryanorban.com/notes/travelplanner-llm-benchmark references Reflexion/ReAct contrast].

**Cost/effectiveness:** LLM-Modulo-style repair multiplies LLM calls (each repair = extra generation). Given repaired plans still land at ~20–26% on the "easy" benchmark and ~2.6% on ChinaTravel, **LLM→solver is strictly dominant** where the problem admits an exact solver. The iterative-critique pattern is only the right choice for constraints that *cannot* be compiled into the solver.

**Severity: High + actionable.** If the LLM plans and no deterministic checker gates it, expect ~1 in 10 plans correct at best. The cheapest correctness win in this entire space is: **after any LLM-produced schedule, run a deterministic validator** (hours/meal-precedence/travel-time/budget/weather) and refuse or repair deterministically.

---

## 5. Agentic orchestration: frameworks, maturity, and necessity

### 5.1 Maturity 2024–2026 (What has actually shipped)

- **LangGraph** — state-machine graph runtime; durable checkpointing + human-in-the-loop (`interrupt()`); v1.0 GA; the production-grade option for complex stateful flows [source: https://techloghub.com/compare/langgraph-vs-crewai-vs-openai-agents-sdk] [source: https://letsdatascience.com/blog/ai-agent-frameworks-compared].
- **CrewAI** — role-based "crews," fastest prototype path; v1.x GA with observability; weak on persistence/resume [source: https://letsdatascience.com/blog/ai-agent-frameworks-compared].
- **OpenAI Agents SDK** — lightweight loop + handoffs + tracing, released early 2025; OpenAI-native lock-in [source: https://techloghub.com/compare/langgraph-vs-crewai-vs-openai-agents-sdk].
- **Claude Agent SDK** (renamed from Claude Code SDK, 2025) — MCP-native, session management, hooks; **alpha/0.x status**, model lock-in to Claude [source: https://letsdatascience.com/blog/ai-agent-frameworks-compared] [source: https://turion.ai/blog/langgraph-vs-openai-claude-agent-sdk-2026].
- **Google ADK, Microsoft Semantic Kernel/AutoGen v0.4** — additional entrants; AutoGen now actor-based [source: https://devsatva.com/blog/langgraph-vs-crewai-vs-autogen-openai-agents-sdk-2026].

These are for **control flow**, not planning intelligence. The framework adds nothing to the constraint-solving problem. The consistent 2025–2026 engineering consensus: **"over-orchestration is the #1 mistake."** If the flow is one model + a few tools + a human review step, vendor SDK or a thin script beats a 500-line graph [source: https://www.whatgenerativeai.com/posts/ai-agent-orchestration-langgraph-vs-crewai/].

### 5.2 Measured overhead of "agentic is better"

- Framework-independent benchmark (OpenSymbolic runs of the same TravelPlanner pipeline): **code-generation pattern completes in 2–3 LLM calls; LangChain ReAct needs 10–15; CrewAI multi-agent 25–40**, with 6× fewer tokens and roughly 8× lower cost for the winner [source: https://www.opensymbolic.ai/blog/travelplanner-benchmark] (vendor blog — label hypothesis, but consistent with independent LLM-Modulo/ChinaTravel experience that ReAct-style loops are token-hungry and drift).
- Independent engineering data: agents make **3–10× more LLM calls** than a chatbot; ReAct per-turn state is re-sent in full each turn; tool definitions + system prompt alone can be ~4–14k tokens/request fixed overhead [source: https://zylos.ai/research/2026-04-12-ai-agent-cost-optimization-token-budget-model-routing/] [source: https://lumadock.com/tutorials/cut-hermes-token-costs]. Tool execution is **40–60% of agent latency** on LangGraph-platform benchmarks [source: https://gravity.fast/blog/ai-agent-performance-tuning/].
- On ChinaTravel, multi-turn tool agents (ReAct) were the *weak* baseline that the NeSy pipeline beat by ~10×; FlexTravelPlanner and TravelPlanner+ studies confirm multi-turn agent robustness is a first-class open problem [source: https://arxiv.org/html/2412.13682v5] [source: https://ceur-ws.org/Vol-4162/paper5.pdf].

### 5.3 Necessity verdict

For a 10–40 candidate catalogue and a deterministic solver in-process, **orchestration adds risk and tokens without adding feasibility**. A *single function-calling loop* (or even no loop — two independent calls: spec + narrative) is sufficient scaffolding. A full graph/crew is justified only for genuinely parallel sub-workflows (multi-city, multi-days with independent legs) — and even then, the LLM decomposition should be one call producing a list of sub-specs, executed by code in parallel, not by "agents talking to each other." Multi-agent travel papers (Vaiage, TravelAgent) score self-reports like 8.5/10 in human eval but contain **no controlled constraint-satisfaction pass rate** — treat their gains as UX/personalization wins, not feasibility evidence [source: https://arxiv.org/abs/2505.10922] [source: https://arxiv.org/abs/2409.08069].

**Severity: Low-to-Medium.** Frameworks won't rescue plan quality; choosing too complex an orchestration is the realistic risk.

---

## 6. The Hybrid that wins: "LLM translates intent → deterministic solver schedules → LLM narrates"

This is the pattern every objective benchmark converged on. Called variously **LLM-as-Translator** (AgentTravel's framing) [source: https://ceur-ws.org/Vol-4162/paper5.pdf], **NeSy / compiler-style**, the "NL → structured spec → solver" pipeline.

### 6.1 The three pillar results (peer-reviewed / replicated)

**Hao et al., 2024/2025** — "Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools." LLM turns the user query + POI records into an **SMT** constraint program; the solver finds a provably-feasible plan; on unsat, the LLM organizes constraint relaxation *from the solver's unsatisfiable core*. **97% final-pass on TravelPlanner** (vs 0.6% GPT-4, 4.4% baseline, 10% o1-preview); 85%/78.6% on an international dataset; 98.9% validation. Notably, the *solution quality is guaranteed in SAT cases* [source: https://openreview.net/forum?id=FlXweLwQk5] [source: https://www.emergentmind.com/papers/2404.11891]. Replicated/confirmed by ChinaTravel analysis (TTG at 91.7% on TravelPlanner) [source: https://arxiv.org/html/2412.13682v5 Table 14].

**TRIP-PAL** (de la Rosa et al., J.P. Morgan AI Research; AAAI-25) — LLM extracts POIs, per-POI visit times and utilities; **Fast Downward** (A* + lmcut, optimal) solves the *oversubscription* planning problem (choose the best subset of POIs within the day's window, maximizing utility). Heads-up detail: **exactly this system's shape** — a day with start/end hours, POI visit durations, and travel times between POIs. Results: TRIP-PAL's plans are valid and **optimal for utility where GPT-4's are often invalid; GPT-4's valid plans average ~5× worse utility** at higher POI counts; and runtime stays ≈GPT-4 up to ~10 POIs (planner <1 s), degrading only at 18 POIs (optimal solving up to ~800 s) [source: https://ar5iv.labs.arxiv.org/html/2406.10196]. The runtime caveat is the key design constraint for this project: **optimal solving is cheap at 10–40 candidates only if you don't force optimality** (approx/priority rollout is enough, see lane 2).

**ItiNera** (EMNLP'24 Industry, deployed) — close cousin: LLM decomposes the request → embedding retrieval over the user's POI DB → **Cluster-aware Spatial Optimization (CSO)** orders POIs → LLM writes the prose itinerary. Deployed human eval: ItiNera preferred over GPT-4 CoT on quality by experts/users (Match ~70% vs 28–32%; AM/overlap distance metrics 3× better); removing CSO doubles crossing-distance (242.8 vs 35.4) [source: https://aclanthology.org/2024.emnlp-industry.104.pdf] [source: https://arxiv.org/html/2402.07204v5]. This is the closest published operational proof of "LLM selects/narrates, optimizer orders" at exactly this product scale.

**The honest ceiling (ChinaTravel):** the same SMT pipeline that "solved" TravelPlanner falls to **1.29%** on open-ended human language. Marginal note in Table 14: with the *correct* (oracle) DSL, the symbolic solver regains high performance — i.e., the failure is almost entirely in **NL→spec translation**, not in the solver. The architecture implication is huge: spend engineering effort on a **narrow, highly-constrained spec language plus a repair loop on translation**, and the solver part is effectively free. LLM-Modulo's *translation repair* (via Reflexion + DSL syntax checker) is how ChinaTravel's authors push it to the DSL's best performance [source: https://arxiv.org/html/2412.13682v5].

### 6.2 The compiler-style generalization (NL → spec → solver)

This pattern is now formalized beyond travel (OptiMUS/OptiMUS-0.3 for MILP from NL; ORLM/LLMOPT/Disp-former fine-tuned modeling models; Microsoft's **OptiMind** — a 20B NL→MILP model — and LLMFP "general-purpose zero-shot planning via LLM-formalized programming") [source: https://arxiv.org/pdf/2508.10047] [source: https://windowsforum.com/threads/optimind-20b-expert-llm-translating-nl-to-milp-and-gurobipy-code.403954/] [source: https://www.emergentmind.com/papers/2310.06116] [source: https://www.semanticscholar.org/paper/Planning-Anything-with-Rigor%3A-General-Purpose-Planner]. The takeaway: the market and the literature both converged on **"LLM writes the program; the program is executed and checked; errors are thrown back to the LLM."** "Behavior programming" / code-generation planners report the same qualitative finding: code plans are testable, deterministic, and 2–3 calls vs 10–40 [source: https://www.opensymbolic.ai/blog/travelplanner-benchmark] (vendor; hypothesis).

### 6.3 What is *not* evidence for the hybrid working

- Vaiage/TravelAgent human-eval scores (8.5/10) — no feasibility pass rates, self-report methodology [source: https://arxiv.org/abs/2505.10922].
- "Multi-agent debate improves reasoning" — a reasoning-accuracy result (e.g., Du et al.), not a constraint-satisfaction result; the convergence evidence says planner/critic debate does NOT fix scheduling [source: https://www.semanticscholar.org/paper/4780d0a027c5c5a8e01d7cf697f6296880ffc945 reference Du et al. 2023].
- Any vendor "97%/99% accuracy" claim for a single-agent planner — treat as marketing until replicated on an objective benchmark [source: none; cf. https://www.opensymbolic.ai/blog/travelplanner-benchmark].

---

## 7. Latency and cost of LLM/agent pipelines (realistic numbers)

Forching a product decision ("low latency preferred"), collected numbers:

- **LLM-only plan:** 1 call, 2–10 s — but ~5–10% correct.
- **ReAct agent plan:** 10–15 sequential calls → realistically **15–60+ s wall-clock**; each call re-sends accumulated context; tools are 40–60% of the latency; cost grows super-linearly [source: https://gravity.fast/blog/ai-agent-performance-tuning/] [source: https://zylos.ai/research/2026-04-12-ai-agent-cost-optimization-token-budget-model-routing/].
- **LLM → solver (recommended):** 1–3 calls. TRIP-PAL's measured planner time at this scale (≤10 POIs) is **<1 s** — LLM is the latency driver, not the solver; at 18 POIs optimal solving can cost up to ~800 s, so **avoid demanding optimality** (heuristic/OR-Tools time-limit or priority-routing is the standard answer; ChinaTravel caps symbolic search at **5 min/query** as a fair-play bound) [source: https://ar5iv.labs.arxiv.org/html/2406.10196] [source: https://arxiv.org/html/2412.13682v5].
- **Mitigation toolbox with evidence:** prompt caching cuts input cost up to ~90% and cached latency up to ~85% (Anthropic 10% cache price; OpenAI 50%) [source: https://gravity.fast/blog/ai-agent-performance-tuning/]; model routing sends 60–80% of requests to small models [source: https://gravity.fast/blog/ai-agent-performance-tuning/]; parallel tool calls cut multi-tool latency 50–70% [source: https://gravity.fast/blog/ai-agent-performance-tuning/]; strict/structured output adds only **5–15%** decode overhead [source: https://jsonic.io/guides/json-llm-output].

Bottom line: the *correct* architecture is also the *fast and cheap* one (1–3 calls). Wrong architectures (ReAct loops, multi-agent crews) are both slower and worse. This project's catalogue is tiny (hundreds of POIs, 10–40 candidates): fetching the candidate matrix and solving is milliseconds-to-sub-second; the LLM calls dominate. Keep the solver call *in-process*, not "an agent calling an API."

---

## 8. 2024–2026 changes that could be game-changers (honestly assessed)

1. **NL→spec translation as the bottleneck (rule-change).** ChinaTravel shows the *solver* is no longer the hard part — **translation is**. Two consequences: (a) invest in a constrained DSL with machine-checkable semantics + a translation repair loop (Reflexion/LLM-Modulo over the DSL, with the syntax checker as the deterministic gate); (b) the current heuristic engine's constraint representation likely already *is* the "spec language" — the upgrade is making the LLM produce it reliably. (High, benchmark-replicated.)
2. **Fine-tuned small specialized models for modeling/spec (Gen-2 rule-change).** ORLM/LLMOPT (MILP modeling), OptiMind (20B NL→MILP), and TravelPlanner's FAFT (Llama-3-8B fine-tuned planner, 8.3% FPR) all show small/cheap models can do the *translation or propose* half with a deterministic verifier holding the quality line. For a travel app, a **fine-tuned 7–20B for NL→spec + OR-Tools** is plausibly the 2026 "best architecture available," cheaper and more deterministic than GPT-5-class. Not yet travel-validated at scale beyond ChinaTravel's TTG — treat as Medium confidence/hypothesis for production travel. [source: https://windowsforum.com/threads/optimind-20b-expert-llm-translating-nl-to-milp-and-gurobipy-code.403954/] [source: https://www.alphaxiv.org/overview/2408.06318]
3. **Code-generation planners ("behavior programming" / LLMFP).** One LLM call writes a data-fetching program; run it; a second call assembles the plan. Fewer, more testable calls; early vendor numbers claim 97.9%/100% on TravelPlanner at ~1/6 the tokens of LangChain and CrewAI runs. **Vendor-hypothesis-level**; but architecture is sound and consistent with the compiler-style convergence. [source: https://www.opensymbolic.ai/blog/travelplanner-benchmark] [source: https://www.semanticscholar.org/paper/Planning-Anything-with-Rigor%3A-General-Purpose-Planner]
4. **Reasoning models as repairers, not planners.** o1/o3/GPT-5-class fix the "given a failing spec, find the constraint conflict" sub-problem (LLM does unsat-core-style reasoning well per Hao et al. interactive repair). Use reasoning models *only* when a plan fails, for root-cause + relaxation suggestions. (Medium, indirect evidence — Hao et al. interactive repair + PlanBench unsolvability weaknesses [source: https://www.emergentmind.com/topics/planbench].)
5. **Graph-of-thought / parallel beams / speculative planning:** No *controlled* travel evidence found; self-consistency-style parallel proposals + external verification (back-prompting in LLM-Modulo) is the only tested variant, and it trades ~4× cost for modest gains. **Not recommended** at this catalogue size. (Note, model judgment.)

Deliberately **not** a game-changer for feasibility: bigger context windows (TravelPlanner gave models *all* data; still 0.6%), better multi-agent debate (doesn't fix constraint math), and long-CoT reasoning models (helped plain Blocksworld, hurt within-sandbox fidelity and obfuscated/novel structure).

---

## 9. Synthesis: the recommended architecture for THIS system

Given catalogue size (hundreds of POIs, 10–40 candidates), constraints (hours, meal precedence, driving matrix, budget, weather, multi-day), and constraints on output (deterministic-ish, low latency), the evidence-endorsed shape is:

```
User request
   │
   ▼
[Call 1] LLM: requirement parsing → structured spec (strict JSON)
   └ translations validated against a narrow DSL / schema; retry ≤2×
   ▼
Retrieval (code): match spec → real POI IDs + real hours/prices/geo from DB;
   tier-1 "must-see" and candidate rank (LLM or embedding, both grounded)
   ▼
[Call 2, optional] LLM re-rank over the actual candidate list (IDs only)
   ▼
[Deterministic solver] OR-Tools/CP-SAT (or keep planner.py heuristics as fallback):
   time-windows + meal-precedence + travel matrix + budget/weather → schedule
   └ if UNSAT → deterministic relaxation (drop lowest-value non-must POI, shift meal)
     └ if still UNSAT → [rare] LLM re-reads unsat core to propose constraint changes
   ▼
[Call 3] LLM: narrative/personalization over the *verified* schedule (copywriter, as today)
   ▼
Deterministic validator rerun as a final gate; failure = bug, not chance
```

Why this beats both pure-LLM planning and today's pure-heuristic pipeline:

- **vs pure LLM:** adds a sound feasibility gate; evidence-bound improvement from ~5–10% → near-100% *feasible-output* (Hao 97%; TRIP-PAL validity; ItiNera deployment) [source: https://openreview.net/forum?id=FlXweLwQk5] [source: https://ar5iv.labs.arxiv.org/html/2406.10196].
- **vs today's heuristics:** LLM now owns the *hard underspecified part* — requirement understanding and candidate selection/personalization — which heuristics handle poorly; solver owns what solvers are good at. TRIP-PAL + ItiNera both show LLM-in-loop strictly improves *user-utility* and *match-rate* while keeping validity (which plain LLM loses) [source: https://ar5iv.labs.arxiv.org/html/2406.10196] [source: https://aclanthology.org/2024.emnlp-industry.104.pdf].
- **Latency:** 1–3 LLM calls; solver <1 s at this scale if non-optimal; meets the "low latency" requirement [source: https://ar5iv.labs.arxiv.org/html/2406.10196].
- **Determinism:** solver output is deterministic for a fixed spec+matrix; the LLM's *narrative* layer is the only stochastic surface, and it's cosmetic (as today). The spec→schedule path can even be cached per (intent, day, city).

**Explicit non-recommendations:** ReAct loops around a POI DB (10–15 calls, drift-prone); planner+critic multi-agent debates (no feasibility evidence, 25–40 calls); letting the LLM emit POI names or travel times (hallucination surface); repeated unconstrained self-verification (empirically degrades).

---

## 10. Source-strength table

| Claim | Strength | Sources |
|---|---|---|
| GPT-4 = 0.6% on TravelPlanner | Benchmark, peer-reviewed (ICML'24) | arxiv.org/abs/2402.01622; icml.cc/virtual/2024/22166 |
| o1-preview ≈10% best LLM-only on TravelPlanner | Benchmark (Hao et al.) | adsabs.harvard.edu/abs/2024arXiv240411891H |
| GPT-4o 0% on ChinaTravel; pure-LLM ≈2.6%; NeSy 37% on human queries | Benchmark, peer-reviewed (NeurIPS'25) | arxiv.org/html/2412.13682v5; nips.cc/virtual/2025/124537 |
| TTG (SMT): 91.7% TravelPlanner → 1.29% ChinaTravel | Benchmark | arxiv.org/html/2412.13682v5 Table 14 |
| NATURAL PLAN <5% multi-city | Benchmark (Google 2024) | emergentmind.com/papers/2406.04520 |
| PlanBench leaderboard numbers (o1 97.8%→52.8% Mystery; ≥20-step failure) | Benchmark, replicated leaderboard | github.com/karthikv792/LLMs-Planning; emergentmind.com/topics/planbench |
| LLM+SMT = 97% on TravelPlanner | Peer-reviewed (ACL'25/NeurIPS-lane; OpenReview) | openreview.net/forum?id=FlXweLwQk5; emergentmind.com/papers/2404.11891 |
| TRIP-PAL: LLM+planner validity/utility beats GPT-4; <1 s at ≤10 POIs | Preprint/AAAI; measured experiments | ar5iv.labs.arxiv.org/html/2406.10196 |
| ItiNera: DB-grounding + spatial optimization, deployed human eval | Peer-reviewed (EMNLP'24 Industry) | aclanthology.org/2024.emnlp-industry.104.pdf |
| TripTailor: o1-mini 78% within-sandbox; 17 km vs 7.3 km spacing | Peer-reviewed (ACL Findings'25) | arxiv.org/pdf/2508.01432 |
| LLM-Modulo travel ≈20.6% / 25.6% on TravelPlanner | Peer-replicated (two independent groups) | arxiv.org/abs/2405.20625; arxiv.org/html/2412.13682v5 |
| LLMs cannot self-correct without external feedback | Peer-reviewed (ICLR'24; ACL'24; ICLR'25) | arxiv.org/abs/2310.01798; aclanthology.org/2024.findings-acl.826 |
| Strict structured output syntax ~100%; JSON mode 8–12% schema violation; silent semantic drift | Vendor claim + independent engineering | jsonic.io/guides/json-llm-output; kalviumlabs.ai |
| BFCL v4: single-turn ≈100%, multi-turn/agentic ~53–77% | Benchmark (ICML'25) | proceedings.mlr.press/v267/patil25a.html; evals.report/benchmarks/bfcl |
| ~10% hallucination floor on grounding (Vectara leaderboard) | Operational benchmark | github.com/vectara/hallucination-leaderboard |
| Frameworks maturity 2025–26 (LangGraph GA, Claude Agent SDK alpha, CrewAI 1.x) | Multi-source engineering blogs | letsdatascience.com; techloghub.com; turion.ai |
| LangGraph 120ms/node vs CrewAI 450ms; tool exec = 40–60% agent latency; caching 90% | Vendor/engineering blogs (hypothesis-grade) | requesty.ai; gravity.fast/blog |
| Code-generation pattern 2–3 vs 10–15 vs 25–40 calls; 97.9% on TravelPlanner | Vendor blog (hypothesis) | opensymbolic.ai/blog/travelplanner-benchmark |
| OptiMind 20B NL→MILP; ORLM/LLMOPT fine-tuned modeling | Vendor/research (mixed) | windowsforum.com; arxiv.org/pdf/2508.10047 |
| Vaiage/TravelAgent multi-agent scores (8.5/10) | Self-reported human eval, no feasibility rate | arxiv.org/abs/2505.10922; arxiv.org/abs/2409.08069 |

---

## 11. Executive summary (~250 words)

The question posed to this lane was whether an LLM-centric (or LLM-hybrid) planner is the cutting-edge architecture for a constrained travel itinerary generator, versus the current deterministic-heuristic pipeline. The evidence from every objective, rule-checked benchmark that appeared in 2024–2026 — TravelPlanner, NATURAL PLAN, ChinaTravel, TripTailor, PlanBench — is consistent and skeptical-of-hype: **a single LLM, even o1/GPT-5-class, cannot reliably schedule even 5–15 constrained stops** (0.6% GPT-4, ~10% o1 best-case on TravelPlanner; ~0–2.6% on ChinaTravel's human-language queries). Reasoning models improve arithmetic planning but degrade on novelty, long horizons, and faithful use of provided data. The demonstrated breakthroughs are all **hybrids that treat the LLM as a translator and the solver as the planner**: LLM+SMT reformulation hit 97% on TravelPlanner; TRIP-PAL's LLM→planning harness produced valid optimal-utility plans where GPT-4's were routinely invalid or ~5× worse; ItiNera's deployed system merged database-grounded POI selection, spatial optimization, and LLM narrative. Structured output and grounding are mature, mandatory plumbing; self-verification without an external verifier empirically degrades output. Agentic orchestration frameworks are orthogonal — they add control flow and cost (3–40× calls) without adding feasibility; a thin 1–3 call pipeline beats them. For this small-catalogue, low-latency system, the recommended architecture is: LLM parses intent to a strict spec, grounded retrieval selects real POI IDs, a deterministic solver (CP-SAT/OR-Tools, or the existing heuristics) schedules with a validation gate, and the LLM narrates the verified result. This is both the evidence-supported SOTA and the cheaper, faster option — replacing heuristics' weak spot (requirement understanding and personalization) while keeping their strength (feasibility). **Verdict: yes, an LLM-hybrid architecture is the right upgrade — but the LLM must not be the planner.**

---

## 12. Top 5 strongest findings

1. **Pure LLM planning is unsolved and measurable.** GPT-4 = 0.6%, o1-preview ≈10% on TravelPlanner's *objectively-checked* constraints; GPT-4o ~0% on ChinaTravel's human-style queries. Any single-agent LLM planner claim of high accuracy without rule-based verification should be treated as marketing. [source: https://arxiv.org/abs/2402.01622] [source: https://arxiv.org/html/2412.13682v5]
2. **LLM-as-translator + formal/solver is THE converged architecture, with a 0.6%→97% delta.** Hao et al.'s SMT pipeline and TRIP-PAL's oversubscription planning prove feasibility+quality guarantees are achievable exactly where this problem lives (small candidate sets, open hours, travel times). [source: https://openreview.net/forum?id=FlXweLwQk5] [source: https://ar5iv.labs.arxiv.org/html/2406.10196]
3. **Even "solved" benchmarks don't transfer to real user language — so invest in the NL→spec step, not the solver.** The same SMT pipeline falls 97%→1.29% on ChinaTravel; the residual risk is entirely requirement translation, which a repair loop over a narrow DSL mitigates. [source: https://arxiv.org/html/2412.13682v5]
4. **Self-correction/self-verification without external feedback makes things worse.** LLMs cannot locate reasoning errors; given exact error locations they fix them well. Repair loops must be gated by deterministic validators — the LLM's own critique is not trustworthy. [source: https://aclanthology.org/2024.findings-acl.826/] [source: https://proceedings.mlr.press/v235/kambhampati24a.html]
5. **Grounding + structured output are mandatory but insufficient plumbing.** Real POI databases kill hallucinated entities and names (ItiNera, TripTailor); tools alone did not lift TravelPlanner above 0.6%, because constraint satisfaction is a *different* failure mode than data hallucination. Both must be in place, and the schedule must exit through a deterministic gate. [source: https://aclanthology.org/2024.emnlp-industry.104.pdf] [source: https://ryanorban.com/notes/travelplanner-llm-benchmark]

---

## 13. Confidence and ground-truth tally

**Confidence: 8.5 / 10.**

Reasoning: This is a rare case where the field's central question has been answered by *multiple independent objective benchmarks with rule-checked scoring* rather than model judgement or vibes, and the load-bearing claims are corroborated by ≥2 independent papers/groups (TravelPlanner results replicated by Hao et al., ChinaTravel, TripTailor, LGE's study; LLM-Modulo numbers reproduced by TripTailor and ChinaTravel; the NL→spec bottleneck replicated by ChinaTravel and TripTailor; self-correction-limits replicated by Huang, Tyen, Stechly, Kamoi). Deductions: (a) some frontier-model (o3/GPT-5/Claude-4/Gemini-2.5-class) numbers on *travel-specific* benchmarks are still sparse — the newest models' exact pass rates on TravelPlanner/ChinaTravel are not yet published at the same rigor, so extrapolating "still not reliable" forward holds Medium-to-High, not High, confidence for the newest models; (b) vendor claims (OpenSymbolic 97.9%, OpenAI 100% structured-output) are intentionally classified as hypothesis and not relied on; (c) cost/latency mitigations rest partly on engineering blogs rather than peer review; (d) the "recommended architecture" is a synthesis of multiple domain papers (TRIP-PAL, ItiNera, Hao, ChinaTravel) rather than one end-to-end travel product with precisely these components — the individual pieces are individually replicated, the exact composition is judgment.

**Ground-truth tally:** 9 of 10 load-bearing conclusions rest on ≥2 externally-verified benchmark/peer-reviewed sources (planning infeasibility; hybrid uplift; LLM-Modulo ceiling; self-correction limits; translator-is-the-bottleneck; solver speed at this scale; grounding necessity; hallucination floor; framework-overhead). The remaining 1 — that "a lean 1–3 call LLM+solver pipeline is strictly better than any heavy agentic orchestration *in production for this catalogue*" — is a synthesis across the vendor-benchmark hypothesis, TRIP-PAL's measured runtime, ChinaTravel's agent-cost table, and independent engineering latency/cost data; it is strongly argued but not a single-run controlled comparison for this exact product. Everything assigned to vendor blogs (OpenSymbolic, Jsonic, Kalvium, Zylos, LangChain-derived figures) is flagged hypothesis and does not count toward verified ground truth.